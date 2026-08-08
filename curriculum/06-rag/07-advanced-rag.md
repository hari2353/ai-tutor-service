# Advanced RAG: CRAG, Self-RAG, GraphRAG, Parent-Document, Multi-Hop, Agentic RAG

> **Track:** T06 RAG (Retrieval-Augmented Generation) · **Time:** 3h · **Prereqs:** 03-vector-index-internals, 04-hybrid-search, 05-reranking, 06-query-transformation · **Updated:** 2026-07-27
> **Module id:** `T06-advanced-rag` · **Tags:** advanced

## The 30-second version

Naive RAG — embed, retrieve top-k, stuff into context — fails in three specific, nameable ways: it can't tell when retrieval was bad and just proceeds anyway, it can't answer questions that require connecting facts across multiple documents, and it can't preserve rich context when small chunks retrieve well but lack surrounding detail. CRAG (Corrective RAG) fixes the first by grading retrieved documents and falling back to web search or query rewriting when they're weak — it's model-agnostic and the cheapest of these to bolt onto an existing pipeline. Self-RAG fixes it differently, training a model to emit reflection tokens that decide whether to retrieve at all and critique its own output, which is more principled but requires a specially trained model, not a wrapper around any LLM. GraphRAG builds an explicit knowledge graph with community summaries to answer questions no single chunk can answer, at a real and substantial indexing cost. Parent-document retrieval and small-to-big chunking solve the precision-vs-context tradeoff by retrieving small chunks and returning their larger parent for generation. Of these, parent-document retrieval, CRAG-style grading, and basic multi-hop decomposition are genuinely deployed in production today; full Self-RAG (which needs a fine-tuned model) and full Microsoft-style GraphRAG (which costs $20-40 per million tokens to index) are used selectively, by teams who've verified the cost is justified by query patterns that actually need cross-document reasoning — most RAG traffic doesn't.

## Why this gets asked

The interviewer wants to know if you can distinguish a genuinely deployed pattern from a paper that reads well but nobody has actually run at your company's scale and budget. They've likely watched a team spend a quarter building a GraphRAG pipeline for a corpus where 95% of queries were single-document lookups that hybrid search plus reranking already solved — or watched a "self-correcting" RAG system silently loop on a bad retrieval because nobody defined a termination condition for the correction step. They're testing whether you reach for these patterns because a specific, diagnosed failure mode calls for them, or because they're the current conference-talk trend.

---

## Lineage: past → present → future

**What came before.** Naive RAG (Lewis et al., 2020, and the wave of implementations that followed 2022-2023) treated retrieval as a single, unconditional step: embed the query, take the top-k chunks, concatenate into the prompt, generate. This works when the corpus is well-chunked, the query is well-formed, and the answer lives in one or two chunks — and fails silently otherwise, because there's no mechanism to detect a bad retrieval before it's already baked into the generated answer. The pain that motivated every technique in this module is the same: naive RAG has no feedback loop. It doesn't know its own retrieval was garbage, it doesn't know a question needs three documents instead of one, and it doesn't preserve the difference between "what retrieves precisely" and "what generation actually needs to read."

**Where it stands now.** CRAG (Yan et al., 2024) adds a lightweight retrieval evaluator that grades retrieved documents as correct/ambiguous/incorrect and branches accordingly — refining and using the documents if correct, falling back to web search if incorrect, or blending both if ambiguous. It's model-agnostic (any LLM can be the grader) and is the cheapest corrective pattern to retrofit onto an existing pipeline, which is why it shows up in production LangGraph implementations. Self-RAG (Asai et al., 2023) takes a more architecturally invasive approach: it trains a model (both a critic and a generator, sharing an expanded vocabulary of reflection tokens — `Retrieve`, `ISREL`, `ISSUP`, `ISUSE`) to decide when to retrieve at all, grade relevance, check whether generated statements are actually supported by retrieved evidence, and judge overall usefulness — all as part of next-token prediction, not a wrapper prompt. This is more principled (the model learns the correction behavior rather than being scripted through it) but requires that specific fine-tuned model, so it doesn't drop into an arbitrary LLM pipeline the way CRAG does. GraphRAG (Microsoft, 2024, 20,000+ GitHub stars) builds an explicit entity-relationship graph from the corpus, clusters it into hierarchical communities via the Leiden algorithm, and pre-summarizes each community with an LLM — enabling "global" queries ("what are the main themes across this entire corpus") that no single-chunk retrieval can answer, at the cost of expensive upfront indexing (roughly $20-40 per million tokens with GPT-4o-class models, versus roughly $0.50 for lighter alternatives like LightRAG). Parent-document / small-to-big retrieval is the least controversial of the group: index small chunks for precise vector matching, but return the larger parent chunk or section to the generator, and it's reported to outperform flat chunking by 15-25% on complex multi-hop questions. Multi-hop and agentic RAG (an agent loop that evaluates each retrieval, and can expand scope, switch strategies, or reformulate the query based on what it learns) is now genuinely deployed — production write-ups describe agentic RAG systems with CRAG-, Self-RAG-, and multi-hop-decomposition-style steps running in verticals like healthcare and legal search. The live disagreement is squarely about cost-justification: GraphRAG and full Self-RAG are real, working systems, but the 2026 practitioner consensus is that "the boring middle of the ladder" — hybrid search, reranking, parent-document retrieval, and lightweight corrective grading — is where most teams get their biggest, cheapest wins, and GraphRAG/Self-RAG-level complexity is justified only when query patterns actually require cross-document or global reasoning at meaningful volume.

**Where it's heading.** Cost reduction for graph-based RAG is an active, fast-moving area — production reports of cutting GraphRAG token costs by roughly 90% via cheaper community summarization and selective graph traversal are already appearing, moderate-to-high confidence this becomes standard rather than a one-off optimization. Adaptive RAG (routing between naive, corrective, and multi-hop strategies per-query based on a cheap upfront classification of query complexity) is converging as the practical answer to "when do I pay for the expensive techniques" — moderate confidence, already a named pattern in production agentic RAG write-ups. More speculative: end-to-end trained retrieval-correction models that fold CRAG's grading and Self-RAG's reflection into a single lighter-weight model specifically distilled for this task, reducing the extra-LLM-call tax that both approaches currently pay; this exists in research prototypes but is not yet a settled production pattern.

---

## Mental model

Naive RAG is a straight line with no feedback. Every technique in this module inserts either a **feedback loop** (grade retrieval, correct if bad) or **structural richness** (graph, hierarchy, multi-hop) that naive RAG's single retrieve-then-generate pass doesn't have:

```
NAIVE RAG:        query → retrieve top-k → generate                (no feedback, no structure)

CRAG:              query → retrieve → GRADE(correct/ambiguous/incorrect)
                                          │correct        │ambiguous      │incorrect
                                          ▼               ▼               ▼
                                    refine+use      blend web+docs   web search fallback
                                          └───────────────┴───────────────┘
                                                          ▼
                                                       generate

SELF-RAG:           query → [Retrieve?] → retrieve (0..N times, model decides)
                                          → [ISREL] grade each passage
                                          → generate → [ISSUP] check groundedness
                                          → [ISUSE] score overall usefulness
                     (all reflection tokens predicted BY the model, not scripted)

GRAPHRAG:            corpus → extract entities/relations → build graph
                            → Leiden clustering → community summaries (C0..C3, coarse→fine)
                     query → "global" (theme-level, hits community summaries)
                           → "local" (entity-level, hits graph neighborhood)

PARENT-DOCUMENT:     corpus → split into SMALL child chunks (indexed, precise match)
                            → each child linked to its LARGER parent chunk/section
                     query → retrieve small chunks → return their PARENTS to the generator

MULTI-HOP/AGENTIC:   query → retrieve → agent EVALUATES: does this answer it?
                            → no → expand scope / switch strategy / reformulate → retrieve again
                            → yes → generate
```

---

## How it actually works

### CRAG: retrieval evaluator + corrective branching

**Mechanism.** After the initial retrieval pass, a lightweight evaluator (a smaller/cheaper model than the main generator, or even a fine-tuned classifier) scores each retrieved document as **Correct**, **Incorrect**, or **Ambiguous** relative to the query. Correct documents are refined (a "decompose-then-recompose" step strips irrelevant strips within the document) and passed to generation as-is. Incorrect triggers a fallback: discard the retrieved documents and issue a web search instead. Ambiguous blends both — refined retrieved documents plus web search results.

**Cost.** One extra, typically cheap, model call per retrieved document (or per batch) for grading, plus — on the incorrect/ambiguous path — an additional web search round-trip. On the common "correct" path, the overhead is just the grading call; on the fallback path, it's grading plus a full extra retrieval-and-generation cycle.

**Why it's the cheapest corrective pattern to adopt.** It's model-agnostic — any LLM (including the same one used for generation) can serve as the grader — and it bolts onto an existing retrieve-then-generate pipeline as an inserted branch, with no fine-tuning required. This is why CRAG shows up as a LangGraph node pattern in production write-ups faster than Self-RAG does.

### Self-RAG: reflection tokens trained into the model

**Mechanism.** Self-RAG expands the model's vocabulary with reflection tokens predicted alongside ordinary text: `Retrieve` (should I retrieve now, retrieve again, or skip retrieval entirely for this segment), `ISREL` (is this retrieved passage relevant to the query), `ISSUP` (is this generated statement actually supported by the retrieved evidence — fully, partially, or not at all), and `ISUSE` (how useful is the overall response, on a graded scale). Both a critic model (which generates training signal for the reflection tokens) and the generator model are trained on this augmented vocabulary via standard next-token prediction — the reflection behavior is learned, not scripted with a separate prompt or wrapper.

**Why it's more principled but less portable.** Because retrieval-necessity and groundedness-checking are baked into the model's own token distribution, Self-RAG can decide to retrieve zero, one, or several times per generation, adaptively, and can flag its own unsupported claims at generation time rather than via a bolted-on post-hoc check. The cost is that this requires the specific fine-tuned Self-RAG model (or retraining your own on the same recipe) — you cannot drop Self-RAG's reflection-token behavior onto an arbitrary off-the-shelf LLM the way you can wrap any LLM in a CRAG grading step.

### GraphRAG: entities, communities, and global queries

**Mechanism.** An LLM extracts entities and relationships from the corpus into a graph. The Leiden algorithm (an improved, more stable version of Louvain community detection) clusters the graph hierarchically into communities — typically on the order of 50-500 communities for a moderate corpus, at multiple coarseness levels (root/coarse `C0` down to fine-grained `C3`). Each community gets an LLM-generated summary. At query time, "global" questions (broad, corpus-wide themes) are answered by combining relevant community summaries — reported to use roughly 20-70% of the tokens that summarizing raw source text directly would require, with root-level summaries needing about 97% fewer tokens than processing source text. "Local" questions (specific entity-centered facts) traverse the graph neighborhood around the relevant entities directly.

**The cost that gates adoption.** Full Microsoft GraphRAG indexing with a GPT-4o-class model runs roughly **$20-40 per million tokens** of source corpus — this is upfront indexing cost, paid once (until the corpus changes and needs re-indexing), not a per-query cost, but it's substantial enough that it only pays off for corpora and query patterns that genuinely need cross-document, theme-level reasoning. Lighter alternatives (LightRAG and similar) report roughly **$0.50 per million tokens** by trading off some of the graph richness — a roughly 40-80x cost difference that matters enormously at corpus scale.

**When it's worth it.** Questions like "summarize the main risks discussed across this entire document set" or "what are the recurring themes in these 10,000 support tickets" — genuinely global, cross-document questions that no amount of top-k chunk retrieval answers, because the answer isn't in any single chunk, it's a property of the whole corpus. It is not worth it for corpora that are predominantly answered by single-document lookups, which is most enterprise FAQ/support/documentation RAG traffic.

### Parent-document retrieval / small-to-big

**Mechanism.** Split source documents into small child chunks (optimized purely for retrieval precision — a small chunk embeds a narrow, specific idea well) but keep a mapping from each child chunk back to a larger parent (a full section, or several paragraphs of surrounding context). At query time, retrieve using the small child chunks' embeddings (precise matching), but pass the larger parent chunk to the generator instead of the small child chunk alone.

**Why it resolves the precision-vs-context tradeoff.** Small chunks retrieve precisely (a narrow embedding matches a narrow query well) but often lack the surrounding context the generator needs to produce a complete, correct answer. Large chunks carry more context but retrieve less precisely (a large chunk's embedding is an average over many ideas, diluting the match to any one specific query). Parent-document retrieval gets both: precise retrieval targeting, rich context for generation. Reported gains are 15-25% over flat chunking specifically on complex, multi-hop questions, where the extra surrounding context in the parent chunk is what supplies the connecting information a narrow child chunk alone would miss.

**Cost.** Effectively free at query time beyond a lookup (child chunk ID → parent chunk ID mapping, typically a simple key-value store or metadata field) — the only added cost is at ingestion, maintaining the child-to-parent mapping and storing both granularities.

### Multi-hop and agentic RAG

**Mechanism.** Rather than a single fixed retrieve-then-generate pass, an agent loop evaluates each retrieval result against the query: does this actually answer it, fully or partially? If not, the agent can expand scope (fetch the parent section or a wider neighborhood), switch retrieval strategy (dense to lexical, or vector to structural/graph traversal), or reformulate the query (see 06-query-transformation) based on what the failed retrieval revealed, then retrieve again. This continues until the agent judges the accumulated evidence sufficient or a budget (max hops, max latency, max tokens) is exhausted.

**Why this needs an explicit termination condition.** Without a hard cap on hops, a multi-hop agent can loop indefinitely on a question the corpus genuinely cannot answer, burning latency and cost with no way to know it should stop. Production systems set a max-hop budget (commonly 2-4 hops) and a fallback ("insufficient evidence, say so") rather than looping until an arbitrary token or time budget silently truncates the loop mid-reasoning.

---

## Build it from scratch

```python
# untested sketch — a minimal CRAG-style corrective loop, no framework
from dataclasses import dataclass
from enum import Enum

class Grade(Enum):
    CORRECT = "correct"
    AMBIGUOUS = "ambiguous"
    INCORRECT = "incorrect"

@dataclass
class RetrievedDoc:
    text: str
    score: float

def grade_document(query: str, doc: RetrievedDoc, grader_llm) -> Grade:
    """Cheap LLM call: does this document actually help answer the query?"""
    resp = grader_llm.classify(
        prompt=f"Query: {query}\nDocument: {doc.text}\n"
               f"Is this document relevant and sufficient to help answer the query? "
               f"Answer exactly one of: correct, ambiguous, incorrect.",
    )
    return Grade(resp.strip().lower())

def corrective_retrieve(query: str, retrieve_fn, web_search_fn, grader_llm, top_k: int = 5):
    docs = retrieve_fn(query, k=top_k)
    grades = [grade_document(query, d, grader_llm) for d in docs]

    correct_docs = [d for d, g in zip(docs, grades) if g == Grade.CORRECT]
    any_incorrect = any(g == Grade.INCORRECT for g in grades)
    any_ambiguous = any(g == Grade.AMBIGUOUS for g in grades)

    if correct_docs and not any_incorrect and not any_ambiguous:
        return correct_docs  # confident: use retrieved docs as-is (after refinement, omitted here)

    if not correct_docs:
        # nothing usable retrieved — fall back entirely to web search
        return web_search_fn(query)

    # ambiguous mix: blend retrieved-correct docs with a web search pass
    return correct_docs + web_search_fn(query)


def multi_hop_agent(query: str, retrieve_fn, sufficiency_check_fn, reformulate_fn, max_hops: int = 3):
    """untested sketch — bounded multi-hop retrieval loop with an explicit stop condition."""
    evidence: list[str] = []
    current_query = query
    for hop in range(max_hops):
        docs = retrieve_fn(current_query, k=5)
        evidence.extend(d.text for d in docs)
        if sufficiency_check_fn(query, evidence):
            return evidence, hop + 1
        current_query = reformulate_fn(query, evidence)  # e.g. step-back or decomposition
    return evidence, max_hops  # budget exhausted — caller must decide how to answer with partial evidence
```

The two things a real implementation adds that this sketch skips: the "refine" step in CRAG (stripping irrelevant strips within an otherwise-correct document via a decompose-then-recompose pass, rather than using the raw chunk verbatim), and a real `sufficiency_check_fn` that itself needs to be a calibrated model call, not a naive heuristic, or the loop either stops too early (incomplete answers) or never stops early enough (wasted hops).

---

## How it's done in production

**LangGraph** is the dominant framework for wiring CRAG-, Self-RAG-, and multi-hop-style branching logic as explicit graph nodes with conditional edges — this is exactly the branch-on-grade pattern CRAG needs, and LangGraph's ecosystem has made CRAG implementation accessible without a research team or fine-tuning budget. **Microsoft's `graphrag` package** (open-sourced July 2024) is the reference GraphRAG implementation; **LightRAG** and similar lighter alternatives trade some graph richness for roughly 40-80x lower indexing cost. **LlamaIndex** ships parent-document / auto-merging retrievers as a built-in retriever type. Production GraphRAG deployments in specific verticals (reported: 14+ months in production with zero reported safety incidents and customer satisfaction above 4.5/5 in at least one write-up) exist, but they're selective — teams that verified their query mix genuinely needed cross-document/global reasoning before paying the indexing cost.

| Symptom | Cause | Fix |
|---|---|---|
| Multi-hop agent loops for many hops without converging | No sufficiency check, or a check that never confidently returns "enough evidence" | Cap `max_hops` explicitly (2-4 is typical), and have a defined "insufficient evidence" fallback response rather than looping to budget exhaustion |
| GraphRAG indexing bill far higher than expected | Full entity/relationship extraction plus community summarization run with a GPT-4o-class model across the entire corpus, re-run on every corpus update | Use a cheaper extraction model, index incrementally (only re-process changed documents), or move to a lighter graph-RAG variant (LightRAG-style) if full fidelity isn't required |
| CRAG's web-search fallback triggers on most queries | Grader threshold miscalibrated (grading too many documents as incorrect), or retrieval itself has a real recall problem the grader is correctly detecting | Check the grader's calibration against a labeled sample first; if retrieval really is that bad, fix the underlying index/embedding/chunking issue rather than papering over it with web search fallback |
| Self-RAG-style behavior "ported" onto an unrelated base model gives inconsistent reflection judgments | Reflection tokens are learned behavior specific to the fine-tuned Self-RAG model/recipe; prompting an arbitrary LLM to "output ISREL/ISSUP/ISUSE" doesn't reproduce the trained calibration | Either use the actual Self-RAG-trained model/checkpoint, or use CRAG-style prompted grading instead, which is designed to be model-agnostic |
| Parent-document retrieval returns parents so large that generation context is mostly irrelevant filler | Parent granularity chosen too coarse (e.g., whole-document parents for a corpus of long documents) | Tune parent granularity to a section/subsection level relative to typical document length, not a fixed one-size-fits-all page count |
| GraphRAG "global" queries return vague, generic answers | Community summaries too coarse (top-level `C0` communities only) for a question that actually needs mid-level specificity | Query at a finer community level (`C1`/`C2`) or blend levels rather than always hitting the coarsest summary tier |

---

## Tradeoffs & when NOT to use it

- **CRAG is nearly free to try and should usually be the first corrective pattern evaluated**, precisely because it's model-agnostic and doesn't require retraining anything — but its extra grading call and possible web-search fallback still add latency, so don't apply it unconditionally to every query; gate it behind a confidence signal from the base retrieval, the same way query transformation should be gated.
- **Self-RAG is the wrong choice unless you're prepared to use or train the specific model** — it is not a prompting technique you can retrofit onto GPT-4o or Claude by asking for reflection tokens in the output; the calibration of `ISREL`/`ISSUP`/`ISUSE` comes from training, not prompting.
- **GraphRAG is the wrong choice for corpora dominated by single-document lookup queries.** The $20-40/million-token indexing cost only pays for itself when a meaningful fraction of real queries are genuinely global/cross-document; verify this with actual query logs before committing, not assumption. For a support-ticket or documentation corpus where 95% of queries are "how do I do X," standard hybrid search plus reranking usually wins on cost and often on latency.
- **Parent-document retrieval is nearly always worth doing** when chunk size is already a live tension in your system (small chunks retrieve precisely but lack context) — it's cheap, has no query-time cost beyond a lookup, and the failure mode of getting it wrong (poorly chosen parent granularity) is easy to tune. There's little reason not to use it once you've accepted chunking at all.
- **Multi-hop/agentic RAG is the wrong choice for latency-sensitive, high-volume, mostly-single-hop traffic.** Every hop is a full retrieval-plus-evaluation round trip; applying this pattern indiscriminately to traffic that's mostly single-fact lookups multiplies latency and cost for a small minority of queries that actually need it. Route to multi-hop only when a cheap upfront classifier flags a query as likely multi-hop (adaptive RAG).
- **Never adopt any of these because of what a conference talk or blog post claims without a query-pattern audit of your own corpus.** The "boring middle" — hybrid search, reranking, parent-document retrieval, lightweight CRAG-style grading — captures most of the achievable gain for most RAG systems; GraphRAG- and Self-RAG-level investment should be justified by a measured, not assumed, need.

---

## Interview questions

### Q1 — What specific failure mode does CRAG fix that naive RAG can't?
**Testing:** precision about the mechanism, not just recall of the name.
**Answer:** Naive RAG has no way to know its own retrieval was bad — it retrieves top-k and generates regardless of whether those chunks actually answer the query. CRAG inserts a grading step that classifies retrieved documents as correct/ambiguous/incorrect and branches: uses refined documents if correct, falls back to web search if incorrect, blends both if ambiguous. It's model-agnostic, so any LLM can serve as the grader without retraining.
**Follow-up trap:** *"What's the added cost?"* — at minimum one grading call per retrieved document (or batch), and on the incorrect/ambiguous path, a full extra web-search-and-generation round trip; don't present it as a free accuracy win.

### Q2 — How does Self-RAG differ architecturally from CRAG, and why can't you just prompt any LLM to behave like Self-RAG?
**Answer:** Self-RAG trains reflection tokens (`Retrieve`, `ISREL`, `ISSUP`, `ISUSE`) into the model's own vocabulary via next-token prediction, using both a trained critic and generator — the decision to retrieve, the relevance grading, and the groundedness check are all learned behavior baked into that specific model. CRAG is model-agnostic — a prompted grading step wrapped around any LLM. You can't port Self-RAG's calibrated reflection-token behavior onto an arbitrary LLM by asking it to output similarly-named tokens in a prompt; the calibration comes from training on that specific recipe.
**Follow-up trap:** *"Which would you pick for a team without ML infra to fine-tune models?"* — CRAG, unambiguously; Self-RAG requires either using the released checkpoint as-is (constraining your model choice) or reproducing its training recipe, which most application teams aren't set up to do.

### Q3 — Walk through how GraphRAG answers a "global" question that naive chunk retrieval structurally cannot.
**Answer:** GraphRAG extracts entities and relationships into a graph, clusters it hierarchically via the Leiden algorithm into communities (roughly 50-500 for a moderate corpus, at multiple coarseness levels), and pre-summarizes each community with an LLM. A global, corpus-wide question ("what are the main themes discussed across this document set") is answered by combining relevant community summaries rather than retrieving individual chunks — because the answer isn't located in any single chunk, it's an emergent property of the whole corpus that only a pre-aggregated summary structure can surface.
**Follow-up trap:** *"What does this cost, and when is it worth it?"* — full GraphRAG indexing with a GPT-4o-class model runs roughly $20-40 per million tokens of source corpus, a one-time (per corpus version) cost; it's worth it only when a meaningful share of real query traffic is genuinely global/cross-document, which most enterprise RAG corpora are not — verify with query logs, don't assume.

### Q4 — Explain parent-document retrieval and why small-to-big beats using one fixed chunk size everywhere.
**Answer:** Small chunks embed narrow, specific ideas precisely, so they retrieve well against a specific query, but lack surrounding context the generator needs for a complete answer. Large chunks carry more context but their embeddings average over multiple ideas, diluting match precision. Parent-document retrieval indexes small child chunks for precise matching but returns the larger parent chunk to the generator, getting retrieval precision and generation context simultaneously — reported to outperform flat chunking by 15-25% on complex multi-hop questions specifically, where the extra context in the parent is what supplies connecting information a narrow chunk alone would miss.
**Follow-up trap:** *"What's the failure mode if parent granularity is chosen wrong?"* — too coarse (e.g., whole-document parents) returns mostly irrelevant filler to the generator, diluting the useful context exactly the way an oversized flat chunk would; parent size needs to be tuned relative to typical document structure, not fixed arbitrarily.

### Q5 — Why does a multi-hop/agentic RAG loop need an explicit hop budget, and what happens without one?
**Answer:** Without a hard cap, an agent evaluating "does this evidence answer the query" can loop indefinitely on a question the corpus genuinely can't answer, since there's no natural stopping signal from a sufficiency check that never confidently returns "enough." Production systems cap hops (commonly 2-4) and define an explicit "insufficient evidence" fallback rather than letting the loop run until an arbitrary token or time budget silently truncates it mid-reasoning.
**Follow-up trap:** *"How would you decide the hop cap?"* — empirically, from measuring how many hops your real multi-hop query distribution actually needs to converge (via the sufficiency check) on a labeled eval set, not a guessed constant.

### Q6 — Your CRAG-based system's web-search fallback is triggering on most queries. What do you check first?
**Answer:** Whether the grader itself is miscalibrated (grading too many genuinely-correct documents as incorrect) versus whether retrieval genuinely is failing that often, in which case the grader is correctly surfacing a real upstream problem. Check the grader's judgments against a labeled sample before assuming the grader is the bug; if retrieval really is that bad, the fix is in the index/embedding/chunking layer, not papering over it by defaulting to web search on every query.
**Follow-up trap:** *"What if fixing retrieval isn't feasible short-term?"* — then the web-search fallback rate is a real signal to surface to stakeholders (this corpus/index isn't ready), not something to silently absorb by letting the fallback carry more traffic than intended; that's a cost and latency regression hiding behind a "working" system.

### Q7 — When would you recommend against GraphRAG even though a team is excited about its multi-hop reasoning capability?
**Answer:** When the actual query logs show the corpus is dominated by single-document lookup questions — most enterprise FAQ, support, and documentation RAG traffic fits this — in which case standard hybrid search plus reranking already handles the bulk of traffic at a fraction of the cost, and the $20-40/million-token indexing bill buys capability the query mix doesn't use.
**Follow-up trap:** *"What would change your recommendation?"* — a query-log audit showing a meaningful volume of genuinely cross-document, theme-level questions ("summarize risks across all these documents") that hybrid search structurally cannot answer regardless of reranking quality; that's the actual justification, not the technique's novelty.

### Q8 — Compare the cost profile of Microsoft GraphRAG versus LightRAG, and what's traded away for the cheaper option.
**Answer:** Full Microsoft GraphRAG indexing with a GPT-4o-class model runs roughly $20-40 per million tokens; LightRAG-style lighter alternatives run roughly $0.50 per million tokens, a 40-80x difference. The tradeoff is graph richness and summarization depth — lighter approaches typically do less exhaustive entity/relationship extraction and simpler community structuring, which can reduce answer quality on genuinely complex global queries even as it dramatically cuts indexing cost.
**Follow-up trap:** *"Would you always pick the cheaper option?"* — no; this is a cost-vs-quality tradeoff that should be validated against your actual global-query accuracy requirements, not decided purely on indexing cost, especially for corpora where global reasoning quality is the entire point of adopting graph-based RAG in the first place.

### Q9 — Design a RAG pipeline for a corpus where 90% of queries are single-fact lookups but 10% require synthesizing information across many documents.
**Testing:** synthesis; whether the candidate applies adaptive routing rather than one-size-fits-all.
**Answer:** This is squarely an adaptive-RAG shape: a cheap upfront classifier (or even a rule-based heuristic on query phrasing — "summarize," "across," "compare all") routes the 90% single-fact traffic straight to hybrid search plus reranking (05-reranking), which is fast and handles that majority case well. The 10% flagged as cross-document is routed to a more expensive path — either a full GraphRAG-backed global-query mode if the corpus and volume justify the indexing cost, or a bounded multi-hop agentic loop if GraphRAG's upfront cost isn't justified by that 10%'s volume. State explicitly that building GraphRAG for the whole corpus to serve only 10% of traffic is usually the wrong sizing decision unless that 10% carries disproportionate business value.
**Follow-up trap:** *"How would you validate the classifier's routing accuracy?"* — a labeled eval set of real queries tagged single-fact vs. cross-document, measuring both false-negative rate (cross-document queries wrongly routed to the cheap path, producing an incomplete answer) and false-positive rate (single-fact queries wrongly paying the expensive path's latency).

### Q10 — What's the actual mechanism by which Self-RAG decides whether to retrieve at all, and why is that different from always retrieving unconditionally?
**Answer:** The `Retrieve` reflection token is predicted by the trained generator as part of ordinary next-token generation — the model itself decides, per generation segment, whether retrieval is needed, needed again, or should be skipped entirely, based on what it's already generated and what it judges it still needs. This differs from naive RAG's unconditional single retrieval pass by allowing zero, one, or multiple retrieval calls adaptively within a single response, driven by the model's own learned judgment rather than a fixed pipeline step.
**Follow-up trap:** *"Isn't this just routing, dressed up?"* — no; routing (06-query-transformation) decides which index/strategy to use before retrieval happens once, while Self-RAG's `Retrieve` token is a per-segment, potentially repeated decision made during generation itself, interleaved with the model's own reasoning about what it still needs.

### Q11 — A team wants to add multi-hop agentic RAG to reduce hallucination on complex questions. What's the actual risk if the sufficiency check is poorly calibrated?
**Answer:** Two failure modes in opposite directions: an overly lenient sufficiency check stops too early, returning incomplete evidence that the generator then either hallucinates around or gives an incomplete answer from; an overly strict sufficiency check never confidently returns "enough," burning the full hop budget on every query regardless of whether it needed multiple hops, multiplying latency and cost for the majority of queries that didn't need it.
**Follow-up trap:** *"How would you calibrate it?"* — measure the sufficiency check's judgments against a labeled eval set where you know the ground-truth number of hops actually needed, tuning until the false-early-stop and false-continue rates are both acceptable, not just optimizing for one direction.

### Q12 — Why is CRAG described as "model-agnostic" and why does that matter operationally?
**Answer:** CRAG's retrieval evaluator is a prompted classification step — any LLM (including a cheaper one than the main generator) can serve as the grader, with no fine-tuning or specific model architecture required. Operationally this matters because it means CRAG can be added to an existing production pipeline as an inserted branch without a model-training investment or a hard dependency on one specific vendor's checkpoint, unlike Self-RAG.
**Follow-up trap:** *"Does grader quality vary a lot by which LLM you use?"* — yes; a weaker grader model can miscalibrate the correct/ambiguous/incorrect classification, so grader choice should be validated against labeled examples, not assumed to work equally well across any LLM just because the pattern is architecturally model-agnostic.

### Q13 — GraphRAG's community summaries come in coarseness levels C0-C3. Why does querying at the wrong level produce vague answers?
**Answer:** Root-level (`C0`) community summaries are heavily compressed — reported to use roughly 97% fewer tokens than processing source text directly — which makes them fast and cheap for broad thematic questions but too abstracted for questions needing mid-level specificity. Querying a specific, moderately-scoped question against only the coarsest summary tier returns a generically-worded answer because the specific supporting detail was compressed away at that level.
**Follow-up trap:** *"How would you fix a vague-answer complaint?"* — query at a finer community level (C1/C2) or blend levels rather than defaulting every query to the coarsest, cheapest tier; this is a query-time tuning knob, not something that requires re-indexing.

### Q14 — Is parent-document retrieval ever the wrong choice?
**Answer:** Yes — if parent granularity is chosen too coarse relative to the corpus's document structure (e.g., using whole long documents as parents), the "parent" returned to the generator becomes mostly irrelevant filler, which is exactly the context-dilution problem parent-document retrieval was meant to solve in the first place, just relocated to a different chunk boundary. It's also unnecessary overhead for corpora where a single flat chunk size already captures both precision and context well (short, atomic documents where child and reasonable parent are nearly the same thing).
**Follow-up trap:** *"So when is flat chunking actually fine?"* — corpora of short, self-contained documents (FAQ entries, short policy clauses) where there's little meaningful difference between a "precise child chunk" and "sufficient context," making the parent-document machinery unnecessary complexity for no real gain.

### Q15 — Rank CRAG, Self-RAG, GraphRAG, parent-document retrieval, and multi-hop agentic RAG by how likely you are to actually deploy each, and justify the order.
**Testing:** honest calibration between hype and deployment reality — the core "advanced RAG" competency question.
**Answer:** Parent-document retrieval first — cheap, low-risk, broadly applicable whenever chunking is already a live design decision. CRAG second — model-agnostic, bolts onto an existing pipeline, cheap to try and to remove if it doesn't help. Multi-hop/agentic RAG third — genuinely deployed but needs an explicit hop budget and should be routed to selectively (adaptive RAG), not applied to all traffic. GraphRAG fourth — real production deployments exist, but the indexing cost gates it to corpora and query mixes that are verified (not assumed) to need cross-document/global reasoning at volume. Self-RAG last for most application teams — architecturally the most principled, but it requires a specific trained model or reproducing its training recipe, which is a real barrier most teams building on top of commercial LLM APIs can't clear.
**Follow-up trap:** *"Isn't this just recency bias toward the cheaper techniques?"* — no; it's a cost-to-adopt versus payoff ranking specific to typical application-team constraints (no fine-tuning infra, existing pipeline to retrofit, cost-sensitive indexing budget) — a team with different constraints (say, an in-house model-training pipeline already running) could reasonably rank Self-RAG higher.

---

## Red flags that fail you

- Recommending GraphRAG or Self-RAG without first checking whether the query mix actually needs cross-document or global reasoning.
- Claiming Self-RAG's reflection tokens can be reproduced by prompting an arbitrary LLM to output similarly-named tokens.
- Describing a multi-hop/agentic RAG loop with no hop budget or termination condition.
- Treating CRAG's web-search fallback rate as acceptable without checking whether it's masking an underlying retrieval quality problem.
- Not knowing GraphRAG's indexing cost is substantial and upfront (roughly $20-40/million tokens with GPT-4o-class models), not a rounding error.
- Recommending parent-document retrieval with a fixed, un-tuned parent granularity regardless of document structure.
- Presenting any of these techniques as strictly better than naive RAG rather than as targeted fixes for specific, named failure modes.

---

## Cheat card

```
CRAG        retrieval evaluator grades docs: correct/ambiguous/incorrect
            correct → refine+use · incorrect → web search fallback · ambiguous → blend
            MODEL-AGNOSTIC (any LLM as grader). Cheapest to retrofit. No fine-tuning needed.

SELF-RAG    reflection tokens TRAINED into model: Retrieve / ISREL / ISSUP / ISUSE
            Retrieve: retrieve 0..N times, model decides. ISREL: passage relevant?
            ISSUP: statement grounded in evidence? ISUSE: response useful?
            NOT portable to arbitrary LLM via prompting — needs the trained checkpoint/recipe.

GRAPHRAG    entities+relations → graph → Leiden clustering → community summaries (C0 coarse..C3 fine)
            "global" query → community summaries (C0: ~97% fewer tokens than raw text)
            "local" query → graph neighborhood traversal
            COST: full MS GraphRAG ~$20-40/1M tokens (GPT-4o-class) · LightRAG ~$0.50/1M (40-80x cheaper, less rich)
            Worth it ONLY if query logs show real cross-document/global demand.

PARENT-DOC  index SMALL child chunks (precise match) → return LARGER parent to generator
            +15-25% over flat chunking on complex multi-hop questions. ~free at query time.
            Nearly always worth doing once you've accepted chunking at all.

MULTI-HOP/  agent evaluates retrieval sufficiency → expand scope / switch strategy / reformulate
AGENTIC     MUST cap hops (2-4 typical) + define "insufficient evidence" fallback, or it loops forever.
            Route via adaptive classifier — don't apply to all traffic (most queries are single-hop).

DEPLOYMENT  parent-doc > CRAG > multi-hop(capped) > GraphRAG(verified need) > Self-RAG(needs trained model)
            "boring middle" (hybrid+rerank+parent-doc+CRAG) wins most RAG systems' biggest cheapest gains.
```

## Sources

- [Corrective RAG (CRAG) 2026: Self-Evaluating Retrieval That Fixes Wrong Answers — EduinX](https://eduinx.in/blog-repository/corrective-RAG-(CRAG)-2026.php) — accessed 2026-07-27
- [Self-RAG, CRAG, and Agentic Retrieval — Elegant Software Solutions](https://www.elegantsoftwaresolutions.com/blog/building-rag-systems-advanced-patterns) — accessed 2026-07-27
- [Agentic RAG: The 2026 Production Guide — MarsDevs](https://www.marsdevs.com/guides/agentic-rag-2026-guide) — accessed 2026-07-27
- [RAG in Production 2026: GraphRAG, Hybrid Retrieval, and Evals](https://ailearningguides.com/rag-production-patterns-2026/) — accessed 2026-07-27
- [SELF-RAG GitHub — akariasai/self-rag](https://github.com/akariasai/self-rag) — accessed 2026-07-27
- [SELF-RAG: Learning to Retrieve, Generate, and Critique — arXiv](https://arxiv.org/pdf/2310.11511v1) — accessed 2026-07-27
- [GraphRAG: New tool for complex data discovery — Microsoft Research](https://www.microsoft.com/en-us/research/blog/graphrag-new-tool-for-complex-data-discovery-now-on-github/) — accessed 2026-07-27
- [GraphRAG Costs Explained — Microsoft Community Hub](https://techcommunity.microsoft.com/blog/azure-ai-foundry-blog/graphrag-costs-explained-what-you-need-to-know/4207978) — accessed 2026-07-27
- [Cutting GraphRAG Token Costs by 90% in Production — Alexander Shereshevsky, Graph Praxis](https://medium.com/graph-praxis/cutting-graphrag-token-costs-by-90-in-production-5885b3ffaef0) — accessed 2026-07-27
- [Modified RAG: Parent Document & Bigger Chunk Retriever — LanceDB](https://www.lancedb.com/blog/modified-rag-parent-document-bigger-chunk-retriever-62b3d1e79bc6) — accessed 2026-07-27
- [Agentic RAG vs Standard RAG: Why AI Agents Need Multi-Layer Retrieval — MindStudio](https://www.mindstudio.ai/blog/agentic-rag-vs-standard-rag-multi-layer-retrieval) — accessed 2026-07-27

## Changelog
- 2026-07-27 — created
