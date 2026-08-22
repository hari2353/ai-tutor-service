# Squeezing Accuracy: Recall@k → MRR → nDCG, Error Analysis Loop

> **Track:** T06 RAG (Retrieval-Augmented Generation) · **Time:** 2.5h · **Prereqs:** 03-vector-index-internals, 04-hybrid-search, 05-reranking · **Updated:** 2026-08-01
> **Module id:** `T06-accuracy-tuning` · **Tags:** eval,critical

## The 30-second version

Retrieval metrics are not interchangeable — Recall@k asks "is the answer anywhere in the top k," Precision@k asks "how much of the top k is useful," MRR asks "how far down the list is the *first* correct answer," MAP averages precision across all correct answers' positions, and nDCG is the only one of the five that handles graded relevance and rewards putting the *best* result first, not just *a* correct one — and picking the wrong metric to optimize for your product (nDCG for a ranked feed, Recall@k for a RAG system feeding a generator that will read the whole context anyway) is a real, common mistake. None of these numbers mean anything without a golden set built from real queries and real documents with careful annotation guidelines, sized enough (dozens to low hundreds minimum, not a handful of hand-picked easy cases) that a metric swing isn't noise. The single highest-leverage discipline in this module is the error-analysis loop: sample failures, classify each one as a retrieval miss, ranking miss, chunking miss, or generation miss, fix whichever class dominates, and re-measure — because you cannot rerank your way out of a recall miss, and teams that skip this classification step burn cycles improving the wrong stage. Offline metrics correlate only weakly with online outcomes (published correlations in the 0.3 range are typical, not 0.8+), so an offline win is a hypothesis to validate online, not a finish line.

## Why this gets asked

The interviewer has watched a team spend a sprint tuning a reranker's threshold because "accuracy is low," only to discover the actual problem was that the first-stage retriever never surfaced the right chunk at all — no amount of reranking fixes a candidate set that's missing the answer. They want to know whether you have a *method* for diagnosing which stage of the pipeline is actually broken before you start changing things, or whether you just try plausible-sounding fixes and hope one sticks.

---

## Lineage: past → present → future

**What came before.** Classical information retrieval evaluation (TREC-style, from the 1990s onward) built the metric vocabulary this module uses — Precision, Recall, MAP, nDCG — for a world of ranked document lists returned to a human who reads down the list until satisfied. The pain that generic classical IR didn't fully anticipate: RAG doesn't have a human reading a ranked list, it has an LLM consuming a fixed top-k context window, which changes which metric actually predicts downstream quality (a document at rank 15 is worthless to a human who never scrolls that far, but genuinely worthless to a RAG system that only reads the top 5 regardless of what rank 15 contains) and adds two new failure classes classical IR eval didn't need to separate: whether the *chunk boundary* preserved the answer (`01-chunking`), and whether the *generator* used the retrieved context correctly even when retrieval succeeded (RAGAS-style faithfulness, `10-rag-eval`).

**Where it stands now.** RAG evaluation has split into two complementary layers: classical retrieval metrics (this module) measure whether the right chunks were found and ranked well, while RAGAS-style decomposed metrics (`10-rag-eval` — context precision/recall, faithfulness, answer relevancy) measure the generation side using an LLM judge. The consensus is that both layers are necessary and neither substitutes for the other — a system can have perfect retrieval and still hallucinate, or perfect faithfulness to a wrong retrieved chunk. What's less settled, and where teams lose real time, is the discipline of error analysis: classifying failures by root cause before attempting a fix. Ad hoc tuning — raising `efSearch`, adding a reranker, increasing chunk overlap — without first measuring which stage is actually failing is still extremely common in practice despite being a well-known anti-pattern, precisely because it feels like progress (something changed) without being progress (the metric that matters didn't move, or moved for the wrong reason).

**Where it's heading.** LLM-as-judge is increasingly used to scale error classification itself — not just faithfulness scoring, but automatically bucketing failures into retrieval-miss/ranking-miss/chunking-miss/generation-miss categories from raw traces — which is real and shipping in observability tooling as of 2026, moderate confidence it becomes standard practice given the same LLM-judge reliability caveats that apply to RAGAS (`10-rag-eval`) apply here too. The open, unresolved problem is offline-to-online metric correlation: published research consistently finds weak correlation (Pearson coefficients often in the 0.3 range) between offline ranking metrics and online engagement/task-success outcomes, and there is no universal offline metric guaranteed to predict online results — this is an active area, not a solved one, and the honest practitioner treats offline gains as a hypothesis for an online experiment, not a conclusion.

---

## Mental model

The ceiling argument, drawn as a pipeline where each stage can only work with what the previous stage handed it:

```
  [ full corpus ]
        │
        ▼
  RETRIEVAL  ──► did the right chunk make it into the candidate set at all?
        │           (Recall@k measures THIS stage specifically)
        ▼
  RANKING    ──► is the right chunk near the TOP of the candidate set?
        │           (MRR / nDCG measure THIS stage specifically)
        ▼
  CONTEXT    ──► does the chunk actually CONTAIN the answer, uncut?
   (chunking)     (a chunking miss looks identical to a retrieval miss
        │          in the final answer, but the fix is completely different)
        ▼
  GENERATION ──► did the LLM use the retrieved context correctly?
        │           (faithfulness / answer relevancy, see 10-rag-eval)
        ▼
  [ final answer ]

  A failure at the FINAL answer can originate at ANY of these four stages.
  Reranking can only fix RANKING. It cannot promote a chunk retrieval never
  surfaced, and it cannot fix a chunk that was cut mid-answer at ingest time.
  This is the ceiling argument: each stage bounds what every stage after it
  can possibly achieve.
```

---

## How it actually works

### The metrics, defined precisely

Let `k` be the cutoff (top-k results considered), and for a single query let there be a set of *relevant* documents in the corpus, some subset of which appear in the top-k retrieved.

**Recall@k** — of all relevant documents that exist for this query, what fraction appear in the top-k?
```
Recall@k = |{relevant docs} ∩ {top-k retrieved}| / |{relevant docs}|
```
Binary relevance is the usual assumption. This is the metric for "can the generator possibly get this right" — if the answer-bearing chunk isn't in the top-k at all, nothing downstream can recover.

**Precision@k** — of the top-k retrieved, what fraction are actually relevant?
```
Precision@k = |{relevant docs} ∩ {top-k retrieved}| / k
```
This is the metric for "how much noise is the generator wading through" — low precision at a fixed k means the LLM has to sift signal from junk in its context window, which matters for cost and can matter for faithfulness even when recall is fine.

**MRR (Mean Reciprocal Rank)** — averaged over queries, the reciprocal of the rank position of the *first* relevant result:
```
RR(query) = 1 / rank_of_first_relevant_result
MRR = mean(RR) across all queries
```
MRR only cares about the first correct answer's position, not how many correct answers exist or where the rest of them rank — the right metric when there's essentially one right answer per query (a specific fact lookup, "what is our refund policy") and no product value in surfacing a second or third relevant document.

**MAP (Mean Average Precision)** — averaged over queries, the average of Precision@k computed at every rank position where a relevant document appears:
```
AP(query) = (1/|relevant docs|) · Σ_{k where doc_k is relevant} Precision@k
MAP = mean(AP) across all queries
```
Unlike MRR, MAP credits finding *multiple* relevant documents and rewards finding them early — the right metric when a query can have several genuinely relevant documents and product value scales with finding more of them, not just the first.

**nDCG@k (Normalized Discounted Cumulative Gain)** — the only one of these five that natively supports *graded* relevance (not just relevant/not-relevant, but a 0-3 or similar relevance scale) and explicitly rewards ranking the *best* result highest, not just *a* correct result anywhere in the top-k:
```
DCG@k  = Σ_{i=1}^{k}  rel_i / log2(i + 1)
IDCG@k = DCG@k of the IDEAL ranking (relevant docs sorted by relevance, descending)
nDCG@k = DCG@k / IDCG@k
```
`rel_i` is the graded relevance of the document at position `i` (e.g. 3 = perfect answer, 2 = partially relevant, 1 = tangentially relevant, 0 = irrelevant). The `log2(i+1)` denominator is the position discount — a highly relevant document at rank 1 contributes `rel/log2(2) = rel/1`, the same document at rank 10 contributes only `rel/log2(11) ≈ rel/3.46`, formalizing the intuition that position matters, with diminishing sensitivity to rank further down the list. Normalizing by IDCG makes the score comparable across queries with different numbers of relevant documents, since a query with only one relevant document can never achieve as high a raw DCG as one with five, but both can achieve nDCG = 1.0 if ranked ideally for their own relevance distribution.

**Which to optimize for which product:**

| Product shape | Right metric | Why |
|---|---|---|
| RAG system feeding an LLM that reads the whole top-k context | Recall@k (primarily), Precision@k (secondarily, for noise/cost) | The LLM will read all of the top-k regardless of internal order in many pipelines — getting the answer *into* the context matters more than its exact position within it, though ranking still matters when context budget forces a smaller k |
| Single-best-answer lookup (FAQ bot, "what is X") | MRR | Only the first correct hit matters; nobody needs the second-best FAQ entry |
| Ranked feed or search results page shown to a human | nDCG (graded relevance) | Position matters continuously, not just "in or out," and not all relevant results are equally good |
| Multi-document synthesis (a report that should cite several sources) | MAP or Recall@k at a higher k | Product value scales with finding *multiple* good sources, not just the first one |

### Building a golden set that is not garbage

A golden set is a labeled set of (query, relevant-document-ids, relevance-grade) tuples built from real usage, not invented queries. Guidance:

- **Size**: fewer than 30 labeled queries produces metrics that are mostly noise — a single query flipping from a hit to a miss swings the aggregate by several percentage points. A practical starting floor is 50+ queries before gating any pipeline change on the resulting metric, growing toward 100-200+ as the product and query diversity mature, stratified across query types (short factual, multi-hop, ambiguous, adversarial) and, for multilingual products, per locale (`12-multilingual`).
- **Source**: real user queries (sampled from logs) plus deliberately adversarial and edge-case queries a real user is likely to eventually type, not exclusively hand-picked easy cases that make the system look good.
- **Annotation**: label with graded relevance (not just binary) where the product benefits from nDCG-style discrimination, and have every case reconciled by at least two annotators independently before disagreements are resolved — a single annotator's judgment call, especially on ambiguous relevance, is not a reliable ground truth on its own. Annotator guidance should include a worked explanation of *why* each labeled example is relevant or not, not just the label, since that guidance is what keeps future annotators (including a future version of the same team, a year later) consistent.
- **Freshness**: re-annotate or refresh the golden set periodically — a corpus that changes (new documents, deprecated ones) makes old relevance labels stale, and a golden set frozen at launch silently drifts out of sync with what "correct" even means for the current corpus.

### The error-analysis loop as a repeatable method

This is the actual discipline, stated as a loop you repeat, not a one-time audit:

1. **Sample failures.** Pull a representative sample of queries where the end-to-end answer was wrong or unsatisfactory — from the golden set eval, from production traces with negative user feedback, or both.
2. **Classify each failure by root cause**, using the ceiling-argument stages: was the answer-bearing document **absent from the retrieved candidate set entirely** (retrieval miss)? Present in the candidate set but **ranked too low to make the final context** (ranking miss)? Present and ranked well but **the chunk boundary cut the answer** so the retrieved unit didn't actually contain what was needed (chunking miss, `01-chunking`)? Or was everything upstream correct and **the LLM still got it wrong** (generation miss — hallucination, misreading the context, ignoring it)?
3. **Fix the dominant class.** If 70% of sampled failures are retrieval misses, improving the reranker or the prompt does nothing measurable — the fix belongs in retrieval (embedding model, hybrid search, chunk size). Chasing the *loudest* individual failure instead of the *most common category* is the classic mistake this step prevents.
4. **Re-measure**, on the same golden set plus fresh production samples, and **repeat**. Each pass should shift the dominant failure class — if retrieval misses drop but the overall answer-quality metric doesn't move, something in the classification or the fix was wrong, and that's itself a signal to re-examine, not a reason to declare victory on the metric that did move.

### The ceiling argument, made explicit

You cannot rerank your way out of a recall miss: a reranker (`05-reranking`) only reorders candidates that retrieval already surfaced. If the answer-bearing chunk never entered the candidate set — because the embedding model didn't score it high enough, or the first-stage `k1` was too small — no downstream stage, no matter how sophisticated, can recover it. This is why error classification must happen *before* choosing a fix: teams that skip straight to "let's improve the reranker" when the actual bottleneck is retrieval recall spend real engineering time on a stage that structurally cannot move the metric they care about.

### Ablation discipline

When multiple changes ship together (new chunk size, new embedding model, new reranker), a metric improvement tells you the *bundle* helped, not which component did, or whether some components helped while others actively hurt and got masked by the ones that helped more. Ablation discipline means changing one variable at a time against the same golden set (or, when that's too slow, holding out one variable at a time in a factorial-lite design) before attributing credit — otherwise the next person to "simplify" the pipeline by removing what looks like a redundant step may remove the one component that was actually carrying the improvement.

### Offline-to-online metric correlation, and why it is often weak

Offline metrics (recall@k, nDCG against a golden set) are cheap, fast, and reproducible, which is exactly why they're used to gate changes before an online experiment. But published research on ranking systems consistently finds only weak correlation between offline metric improvements and online outcome improvements — Pearson correlation coefficients around 0.3 are typical in reported studies, not the 0.8+ a team might assume. Reasons this happens: golden sets are a curated, static snapshot of "relevant," while real user satisfaction depends on factors a golden set doesn't capture (result diversity, personalization, how a user's actual intent differs from what an annotator assumed); and in multi-stage systems, an improvement at one stage can be offset or masked by interactions with other stages in ways a component-level offline metric doesn't see. The practical consequence: an offline win is a *hypothesis* worth testing online, not a stopping point — ship behind an A/B test where the product supports one, and track online task-success/engagement metrics as the actual arbiter, not the offline number that got you permission to ship.

---

## Build it from scratch

```python
# untested sketch — illustrates the metric computations and the error-
# classification loop's data structure, not a production eval harness
import math
from collections import Counter

def recall_at_k(retrieved: list[str], relevant: set[str], k: int) -> float:
    if not relevant:
        return 0.0
    top_k = set(retrieved[:k])
    return len(top_k & relevant) / len(relevant)

def precision_at_k(retrieved: list[str], relevant: set[str], k: int) -> float:
    top_k = retrieved[:k]
    if not top_k:
        return 0.0
    return len([d for d in top_k if d in relevant]) / len(top_k)

def reciprocal_rank(retrieved: list[str], relevant: set[str]) -> float:
    for i, doc_id in enumerate(retrieved, start=1):
        if doc_id in relevant:
            return 1.0 / i
    return 0.0

def average_precision(retrieved: list[str], relevant: set[str]) -> float:
    if not relevant:
        return 0.0
    hits, precisions = 0, []
    for i, doc_id in enumerate(retrieved, start=1):
        if doc_id in relevant:
            hits += 1
            precisions.append(hits / i)
    return sum(precisions) / len(relevant) if precisions else 0.0

def dcg_at_k(graded_relevance_in_rank_order: list[float], k: int) -> float:
    return sum(rel / math.log2(i + 2) for i, rel in enumerate(graded_relevance_in_rank_order[:k]))

def ndcg_at_k(retrieved_relevance: list[float], ideal_relevance: list[float], k: int) -> float:
    dcg = dcg_at_k(retrieved_relevance, k)
    idcg = dcg_at_k(sorted(ideal_relevance, reverse=True), k)
    return dcg / idcg if idcg > 0 else 0.0


FAILURE_CLASSES = ("retrieval_miss", "ranking_miss", "chunking_miss", "generation_miss")

def classify_failure(answer_bearing_chunk_id: str, retrieved_ids: list[str], k_used_by_generator: int,
                      chunk_contains_full_answer: bool, generation_correct: bool) -> str:
    """Mechanical version of the diagnostic questions in the error-analysis loop."""
    if answer_bearing_chunk_id not in retrieved_ids:
        return "retrieval_miss"
    rank = retrieved_ids.index(answer_bearing_chunk_id) + 1
    if rank > k_used_by_generator:
        return "ranking_miss"
    if not chunk_contains_full_answer:
        return "chunking_miss"
    if not generation_correct:
        return "generation_miss"
    return "no_failure"

def dominant_failure_class(classified: list[str]) -> tuple[str, float]:
    counts = Counter(c for c in classified if c != "no_failure")
    if not counts:
        return ("none", 0.0)
    cls, n = counts.most_common(1)[0]
    return (cls, n / sum(counts.values()))
```

---

## How it's done in production

**Metric computation**: `pytrec_eval` (Python wrapper around the TREC evaluation tool) or `ranx` for standard IR metrics at scale; RAGAS for the generation-side decomposition (`10-rag-eval`). **Golden set management**: version-controlled alongside the corpus, with per-query-type and per-locale stratification tracked as metadata, not just a flat query list. **Error classification at scale**: LLM-as-judge pipelines that read a full trace (query, retrieved chunks, generated answer, ground truth) and output a failure-class label, spot-checked by humans given the same LLM-judge reliability concerns that apply to RAGAS scoring. **Online validation**: A/B testing infrastructure gating any offline-validated change before full rollout, tracking task-success or engagement metrics as the actual decision criterion.

| Symptom | Cause | Fix |
|---|---|---|
| Reranker tuning shows no measurable improvement despite real engineering effort | Dominant failure class was actually retrieval misses, not ranking misses — reranking can't promote what retrieval never surfaced | Run the error-analysis classification first; if retrieval misses dominate, fix `k1`/embedding model/hybrid search instead |
| A pipeline change improves the blended eval score but specific query types get worse | Aggregate metric masking a regression in one query-type or locale slice, offset by gains elsewhere | Report metrics per query-type/locale slice, not only blended (mirrors the same discipline as `12-multilingual`'s per-locale requirement) |
| Golden-set metrics look great, production complaints continue | Distribution mismatch between golden-set queries/documents and real production traffic, or weak offline-online correlation generally | Rebuild golden set from real production logs; validate the change online via A/B test rather than trusting the offline number alone |
| Team ships three "improvements" in one release and the metric moves, but nobody knows which change mattered | No ablation discipline — bundled changes with no per-variable isolation | Re-run each change independently against the same golden set before attributing credit, or hold out one variable at a time |
| MRR looks perfect but users complain results feel shallow or repetitive | MRR only measures the first correct hit's position and says nothing about the rest of the ranked list or result diversity | Switch to nDCG (or MAP, if multiple relevant documents genuinely matter) if the product needs credit for more than just the first hit |
| A metric improves for months, then plateaus despite continued tuning | Approaching the ceiling of what the current retrieval architecture can deliver — further reranking/prompt tuning can't move a bottleneck sitting earlier in the pipeline | Re-run error analysis; a plateau in one metric with a stable dominant failure class in an earlier stage means it's time to change that stage's architecture, not keep tuning the current one |

---

## Tradeoffs & when NOT to use it

- **Don't optimize nDCG for a RAG system whose generator reads the whole top-k context regardless of internal order.** You'll spend effort perfecting a within-k ordering that the downstream LLM barely benefits from; Recall@k is the metric that actually predicts whether the generator *can* get the answer right.
- **Don't build a golden set from hand-picked easy queries.** It will report a flattering number that has no relationship to production difficulty, and every pipeline change will look like a win against it.
- **Don't skip error classification and jump straight to a fix "that usually helps."** This is the single most common way teams waste a sprint — most retrieval-quality techniques (reranking, chunk-size changes, prompt tuning) only fix one specific failure class, and applying the wrong one produces no measurable improvement no matter how well-executed.
- **Don't treat an offline metric win as sufficient justification to ship without an online check**, when the product and traffic support A/B testing. The published weak correlation between offline and online metrics means an offline win is evidence worth testing, not a conclusion.
- **Don't chase small metric deltas (a fraction of a percentage point) on a golden set under ~100 queries.** The noise floor on a small golden set can exceed the effect size you're trying to detect; either grow the golden set or treat sub-threshold deltas as statistically meaningless.

---

## Interview questions

### Q1 — Define Recall@k and Precision@k precisely, and explain when a RAG system should optimize primarily for one over the other.
**Testing:** whether the candidate can state the formulas exactly, not just gesture at them.
**Answer:** Recall@k = |relevant ∩ top-k| / |relevant| — of everything relevant, how much did you find. Precision@k = |relevant ∩ top-k| / k — of what you returned, how much was relevant. A RAG system whose generator reads the whole top-k context should optimize primarily for Recall@k, since getting the answer into the context matters more than its internal position, with Precision@k as a secondary concern for context noise and token cost.
**Follow-up trap:** *"If you improve Precision@k but Recall@k stays flat, did retrieval get better?"* — no, it got *cleaner*, not more capable of finding the answer; these measure different things and a Precision@k improvement alone says nothing about whether more answers are now reachable.

### Q2 — Derive nDCG and explain what the log2 discount represents.
**Answer:** `DCG@k = Σ rel_i / log2(i+1)`, normalized by the IDCG (DCG of the ideal ranking) to get `nDCG@k = DCG@k / IDCG@k`. The `log2(i+1)` term discounts a relevant result's contribution based on its rank position — a document at rank 1 contributes `rel/log2(2) = rel`, the same document at rank 10 contributes only about `rel/3.46` — formalizing that position matters, with diminishing marginal sensitivity further down the list rather than a linear penalty.
**Follow-up trap:** *"Why divide by IDCG instead of just using raw DCG?"* — raw DCG isn't comparable across queries with different numbers of relevant documents (a query with 5 relevant docs can achieve a higher raw DCG ceiling than one with 1), so normalizing by each query's own achievable maximum makes scores comparable across the golden set.

### Q3 — What's the difference between MRR and MAP, and when would you pick one over the other?
**Answer:** MRR averages the reciprocal rank of only the *first* relevant result per query — it's blind to whether more relevant documents exist further down. MAP averages precision computed at every rank where a relevant document appears, so it credits finding *multiple* relevant documents and rewards finding them early. Pick MRR for single-best-answer products (FAQ lookup); pick MAP when multiple genuinely relevant documents add product value (multi-source synthesis).
**Follow-up trap:** *"Could two systems have identical MRR but very different actual quality?"* — yes, easily: MRR ignores everything after the first hit, so a system that finds one relevant document at rank 1 and nothing else scores identically on MRR to one that finds five relevant documents at ranks 1, 2, 3, 4, 5 — MAP would distinguish them clearly.

### Q4 — What makes a golden set "not garbage," concretely?
**Answer:** Real queries sampled from production (plus deliberate edge cases), a size floor around 50+ queries before trusting the metric to gate decisions (fewer than 30 is mostly noise), reconciled labeling from at least two independent annotators rather than one person's judgment call, graded relevance where the product needs it, and periodic refresh as the corpus changes so labels don't go stale.
**Follow-up trap:** *"What if you only have 15 labeled queries right now?"* — say so plainly and treat any metric computed from it as directional at best, not a gating threshold; shipping a change because it "improved" a 15-query eval is exactly the noise-chasing this module warns against.

### Q5 — Describe the error-analysis loop as a repeatable method, not a one-time exercise.
**Answer:** Sample real failures, classify each by root cause using the pipeline stages (retrieval miss / ranking miss / chunking miss / generation miss), fix whichever class is most common in the sample (not the loudest individual failure), then re-measure and repeat — each pass should shift the dominant failure class, and if it doesn't, the classification or the fix was wrong.
**Follow-up trap:** *"What if two failure classes are roughly tied?"* — investigate the cheaper or higher-confidence fix first, but say explicitly that you'd expect the other class to become dominant next and plan the following loop iteration around it, rather than trying to fix both simultaneously and losing the ability to attribute the resulting metric change to either.

### Q6 — Explain the "ceiling argument": why can't a reranker fix a recall miss?
**Answer:** A reranker only reorders candidates that first-stage retrieval already surfaced (`05-reranking`). If the answer-bearing chunk was never in the candidate set — because the embedding model didn't score it highly enough, or `k1` was too small — there's nothing for the reranker to promote. The bug is upstream of where the reranker operates, so no amount of reranker tuning can move a metric bottlenecked by retrieval recall.
**Follow-up trap:** *"How do you prove that's actually what's happening rather than assuming it?"* — measure recall@k1 of the first stage in isolation against the golden set; if the answer-bearing document isn't even in that set, the reranker is provably blameless.

### Q7 — Why is a chunking miss easy to misdiagnose as a retrieval miss?
**Answer:** Both produce the same downstream symptom — the LLM doesn't have the answer and says so, or hallucinates. But a retrieval miss means the right document was never found at all, while a chunking miss means the right document *was* found and ranked well, but the chunk boundary cut the answer so the retrieved unit doesn't actually contain what's needed. The fixes are completely different (retrieval architecture vs. chunk size/strategy), so conflating them sends the fix to the wrong stage.
**Follow-up trap:** *"How do you tell them apart in practice?"* — check whether the answer-bearing source document was retrieved at all (even if split across chunks); if the correct document appears in the candidate set but no single retrieved chunk contains the full answer, that's a chunking miss, not a retrieval miss.

### Q8 — What's ablation discipline, and why does it matter when multiple changes ship together?
**Answer:** When several changes (new chunk size, new embedding model, new reranker) ship in one bundle, an aggregate metric improvement tells you the bundle helped overall, not which individual component did — some components could even be actively hurting while others mask it. Ablation means isolating and measuring each change independently against the same golden set before attributing credit.
**Follow-up trap:** *"Isn't that slower than just shipping the bundle and moving on?"* — yes, and that's the real tradeoff; the cost of skipping it is a future regression when someone removes what looks like a redundant piece of the bundle that was actually carrying the improvement, with no record of which piece that was.

### Q9 — Why is offline-online metric correlation often weak, and what does that mean practically?
**Answer:** Published research on ranking systems commonly reports Pearson correlations around 0.3 between offline metric changes and online outcome changes, far from a reliable predictor. Golden sets are a static, curated snapshot of "relevant" that doesn't capture real factors like diversity, personalization, or genuine user intent variance, and in multi-stage systems a component-level offline gain can be offset by interactions elsewhere in the pipeline online. Practically: treat an offline win as a hypothesis worth an online A/B test, not a stopping point.
**Follow-up trap:** *"So should teams stop using offline metrics at all?"* — no, offline metrics are still the cheap, fast, reproducible gate that filters out clearly bad changes before spending online experiment budget; the mistake is treating an offline win as sufficient on its own when online validation is available.

### Q10 — A stakeholder asks for "the highest possible retrieval accuracy" with no other constraint stated. How do you respond?
**Answer:** Ask which metric maps to the product's actual definition of "accurate" — Recall@k for a RAG generator reading the whole context, MRR for single-best-answer lookup, nDCG for a ranked results page — because "accuracy" isn't one number, and optimizing the wrong metric can actively hurt the dimension that mattered. Then name the cost/latency tradeoffs any further accuracy gain will carry (deeper reranking, larger `k1`, more expensive models), since "highest possible" with no budget constraint is not a real target.
**Follow-up trap:** *"What if they insist there's no budget constraint?"* — there always is one implicitly (latency, infra cost, engineering time); surfacing that rather than accepting the framing at face value is exactly the senior signal being tested.

### Q11 — Staff-level: your team has been improving nDCG for two consecutive quarters, but a downstream survey shows user-perceived answer quality hasn't moved. Diagnose and respond.
**Testing:** synthesis of metric selection, offline-online correlation, and the ceiling argument together.
**Answer:** Two live hypotheses, and both need checking rather than picking one: (1) nDCG may be the wrong metric for this product — if it's a RAG system whose generator ingests the whole top-k regardless of order, nDCG improvements largely capture within-k reordering the generator doesn't benefit much from, and Recall@k (or a generation-side metric like faithfulness) may be the metric actually gating perceived quality. (2) Retrieval may already be past its practical ceiling for the current architecture, and the bottleneck has shifted to chunking or generation — an error-analysis pass classifying recent failures would reveal whether retrieval/ranking misses are now the minority and generation misses now dominate, which nDCG tuning cannot touch. Either way, the fix is to re-run error classification and, if warranted, switch the metric being optimized rather than continuing to push the same number.
**Follow-up trap:** *"Isn't nDCG a 'better' metric than Recall@k in general, since it's more sophisticated?"* — no metric is universally better; sophistication (graded relevance, position-sensitivity) is only valuable when the product actually benefits from that discrimination, and forcing a more sophisticated metric onto a product shape it doesn't fit wastes exactly the two quarters described in this scenario.

### Q12 — How would you size a golden set for a new RAG product with no existing production traffic to sample from?
**Answer:** Start from a smaller, deliberately constructed set (real target users' likely queries, informed interviews or a beta cohort, plus adversarial/edge cases) — accept it's below the 50+ ideal floor initially and treat early metrics as directional, not gating. Grow it aggressively from real logs the moment production traffic exists, and re-annotate/expand per query-type and locale as soon as volume allows stratification.
**Follow-up trap:** *"Would you delay launch until the golden set is large enough?"* — no; ship with the smaller set and explicit uncertainty caveats on any metric it produces, and treat golden-set maturity as a fast-follow investment rather than a launch blocker, since real production data is the fastest path to a golden set that actually reflects reality.

---

## Red flags that fail you

- Confusing Recall@k, Precision@k, MRR, MAP, and nDCG, or not being able to write any of their formulas.
- Optimizing nDCG for a product where the generator reads the whole top-k regardless of order.
- Trusting a golden set under ~30 queries as a gating metric.
- Jumping to "add a reranker" or "tune the prompt" without first classifying which pipeline stage is actually failing.
- Believing an offline metric win is sufficient justification to ship without any online validation, when online validation is available.
- Shipping bundled changes and attributing the aggregate metric improvement to a specific component without ablation.
- Not knowing that offline-online metric correlation is typically weak, not strong.

---

## Cheat card

```
RECALL@k     |relevant ∩ top-k| / |relevant|        -- can the answer possibly be found
PRECISION@k  |relevant ∩ top-k| / k                  -- how much noise in the top-k
MRR          mean(1 / rank_of_first_relevant)        -- only the FIRST hit's position
MAP          mean(avg of Precision@k at each relevant-doc rank) -- credits MULTIPLE hits
nDCG@k       DCG@k / IDCG@k ; DCG@k = Σ rel_i/log2(i+1) -- GRADED relevance, position-sensitive

PICK METRIC   RAG (generator reads whole top-k) -> Recall@k primary
              single-best-answer lookup -> MRR
              ranked feed shown to a human -> nDCG
              multi-source synthesis -> MAP or Recall@k at higher k

GOLDEN SET   <30 queries = noise. Floor: 50+, grow to 100-200+.
             Real queries + adversarial cases, NOT hand-picked easy ones.
             2+ independent annotators reconciled, graded relevance, refresh periodically.

ERROR-ANALYSIS LOOP   sample failures -> classify (retrieval miss / ranking miss /
    chunking miss / generation miss) -> fix the DOMINANT class -> re-measure -> repeat

CEILING ARGUMENT   reranker/ranking fixes can't recover a retrieval miss -- they only
    reorder what retrieval already surfaced. Fix the earliest broken stage first.

ABLATION   bundled changes + one metric win = you don't know which change mattered.
    Isolate one variable at a time before attributing credit.

OFFLINE-ONLINE CORRELATION   typically weak (Pearson ~0.3 in published studies), not
    ~0.8+. Offline win = hypothesis for an online A/B test, not a conclusion.
```

## Sources

- [Discounted cumulative gain — Wikipedia](https://en.wikipedia.org/wiki/Discounted_cumulative_gain) — accessed 2026-08-01
- [Normalized Discounted Cumulative Gain (NDCG): Where To Use It — Arize](https://arize.com/blog-course/ndcg/) — accessed 2026-08-01
- [LLM Eval Golden Set Design: A 2026 Engineering Guide — FutureAGI](https://futureagi.com/blog/llm-eval-golden-set-design-2026/) — accessed 2026-08-01
- [Evaluating AI: Your Guide to Using Golden Test Sets — Bloomreach](https://www.bloomreach.com/en/blog/evaluating-ai-your-guide-to-using-golden-test-sets) — accessed 2026-08-01
- [Online vs offline correlation: Validating test sets — Statsig](https://www.statsig.com/perspectives/online-vs-offline-validation) — accessed 2026-08-01
- [Offline A/B testing for Recommender Systems (arXiv:1801.07030)](https://arxiv.org/pdf/1801.07030) — accessed 2026-08-01

## Changelog
- 2026-08-01 — created
