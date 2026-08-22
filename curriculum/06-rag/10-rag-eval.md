# RAGAS Decomposed, Golden Sets, Synthetic Questions, Retrieval@k

> **Track:** T06 RAG (Retrieval-Augmented Generation) · **Time:** 2h · **Prereqs:** 04-hybrid-search, 05-reranking, 07-advanced-rag · **Updated:** 2026-07-28
> **Module id:** `T06-rag-eval` · **Tags:** eval

## The 30-second version

RAG evaluation has to be decomposed into retrieval quality and generation quality, measured separately, because a system that answers confidently and fluently can still be wrong for a reason that lives entirely in retrieval — the right chunk was never surfaced, so no amount of generation-quality tuning fixes it. RAGAS's four core metrics map directly onto that split: context precision and context recall score what retrieval did, faithfulness and answer relevancy score what generation did with what it was given, and running all four rather than a single end-to-end "is this answer good" score is what lets you attribute a regression to a specific subsystem instead of debugging blind. Golden sets — a curated, human-verified set of (question, correct answer, correct supporting chunks) triples — are the ground truth everything else calibrates against, and synthetic question generation exists because building a golden set by hand doesn't scale, but every synthetic generator needs a human-labeled subset to check it's actually producing realistic, answerable questions rather than trivia the retriever can nail by keyword match alone. The single most important habit is checking retrieval metrics before trusting an end-to-end answer-quality score: a high answer-quality score with mediocre context recall usually means the eval set is too easy, not that the system is good, and a low answer-quality score with high context recall means the fix belongs in the generation prompt, not in retrieval tuning.

## Why this gets asked

The interviewer has watched a team ship a RAG system that scored well on an internal "vibe check" — a handful of manually-reviewed example answers that looked good — and then fall over in production because the eval never actually measured whether retrieval was surfacing the right evidence, only whether the final answer read fluently. They want to know if you'll build an eval that can tell you *which* part of the pipeline broke when quality regresses, or if you'll ship a system whose only quality signal is "an engineer read ten examples and they seemed fine."

---

## Lineage: past → present → future

**What came before.** Early RAG evaluation was almost entirely manual: engineers ran a handful of representative queries, read the answers, and judged them subjectively "good" or "bad." This didn't scale past a demo — it caught nothing systematically, couldn't be run in CI, and gave no signal about *why* an answer was wrong, only that it was. The next step was borrowing generic NLP metrics (BLEU, ROUGE, embedding-similarity-to-a-reference-answer) from summarization and translation, which measured surface overlap with a reference answer but couldn't detect a fluent, well-worded answer that was factually unsupported by the retrieved context — the exact failure mode (hallucination grounded in nothing, or confidently wrong due to missing retrieval) that matters most in RAG specifically.

**Where it stands now.** RAGAS (Es et al., 2023, and its subsequent framework growth) established the now-standard decomposition: evaluate retrieval and generation as separate axes, using an LLM-as-judge to score each of four metrics — context precision, context recall, faithfulness, answer relevancy — rather than one blended score. This is the dominant framework as of 2026, alongside comparable tooling (DeepEval, Confident AI's suite, TruLens, Arize Phoenix) that largely converged on the same decomposition even where the specific metric names differ. The live disagreement isn't over whether decomposition matters — that's settled — it's over LLM-as-judge reliability itself: judge models have their own biases (a documented tendency to prefer longer answers, verbosity bias, and inconsistent scoring across repeated runs of the same judge on the same input), so teams increasingly report calibrating LLM-judge scores against a human-labeled subset before trusting them at scale, rather than treating judge output as ground truth. Synthetic test-set generation (RAGAS's `TestsetGenerator`, and comparable tools across the ecosystem) has become the practical answer to "we don't have thousands of hand-labeled questions," using an LLM to generate document-grounded question-answer pairs with controllable difficulty (simple single-hop factoid vs. multi-hop reasoning vs. conditional/comparison questions), but the consensus caveat is that synthetic questions still need a human-reviewed subset to confirm they're realistic and non-trivial, since a generator left unchecked tends to produce questions the retriever can answer by keyword overlap with the source chunk, which doesn't stress-test anything.

**Where it's heading.** Automated, per-pull-request RAG evaluation — running the full RAGAS-style decomposition on every change to chunking, embedding model, or prompt, gated in CI — is becoming standard practice at teams serious about the pipeline, the same way unit tests gate code changes; high confidence this keeps spreading, since the tooling (pytest-native synthesizers, CI-friendly evaluation harnesses) now exists specifically for this. Multi-agent and persona-based synthetic data generation — simulating different user personas asking questions in different styles to stress-test robustness beyond single-shot factoid QA — is an active direction with real early tooling but isn't yet a settled default; moderate confidence. More speculative: fully automated judge calibration that continuously re-validates an LLM judge against a small live human-labeled stream without a human explicitly re-running a calibration study is discussed but not a mainstream shipped pattern yet.

---

## Mental model

Think of RAG evaluation as a two-stage funnel, and every metric belongs to exactly one stage:

```
                    RETRIEVAL STAGE                       GENERATION STAGE
   question  ──>  [retrieve top-k chunks]  ──────────>  [generate answer from chunks]
                         │                                        │
                         v                                        v
              did we get the RIGHT evidence?          did we use the evidence WELL?
              ┌─────────────────────────┐            ┌──────────────────────────┐
              │ Context Precision:       │            │ Faithfulness:            │
              │  of what we retrieved,   │            │  is the answer actually  │
              │  how much was relevant?  │            │  supported by what we    │
              │                          │            │  retrieved, or invented? │
              │ Context Recall:          │            │ Answer Relevancy:        │
              │  of what we NEEDED,      │            │  does the answer address │
              │  how much did we get?    │            │  the actual question?    │
              └─────────────────────────┘            └──────────────────────────┘

  A high answer score with LOW context recall = the eval question was answerable
  from the model's own knowledge, or the eval set is too easy -- it's not testing RAG.

  A LOW answer score with HIGH context recall = the fix is in the prompt/generation,
  not in retrieval -- don't waste time re-tuning the retriever.
```

The core discipline: never trust a single blended "answer quality" number without also knowing what context recall and precision were on the same examples, because the blended number can't tell you which half of the pipeline to fix.

---

## How it actually works

### RAGAS's four metrics, decomposed precisely

**Context Precision** asks: of the chunks retrieved, what fraction were actually relevant/useful for answering the question? It's computed (in RAGAS's implementation) by using an LLM judge to assess each retrieved chunk's relevance to the ground-truth answer, then computing a precision-at-rank-weighted score so chunks ranked higher that are relevant contribute more than relevant chunks buried lower in the ranked list — this rewards not just retrieving relevant material, but ranking it well. Low context precision with otherwise fine answers usually means your `k` is too large or your reranker isn't doing its job (see `T06-reranking`), padding the context with noise the generation model has to wade through.

**Context Recall** asks: of what was actually needed to construct the ground-truth answer, how much did retrieval surface? This requires a reference answer (or reference supporting facts) to compare against — the judge checks whether each claim in the reference answer can be attributed to something in the retrieved context. Low context recall is a retrieval failure, full stop: no amount of prompt engineering on the generation side fixes a fact that was never retrieved. This is the metric most directly analogous to `Recall@k` (covered in depth in `T06-accuracy-tuning`), but computed against decomposed reference *facts* rather than a single binary "was the right document in the top-k" check.

**Faithfulness** asks: is the generated answer actually grounded in the retrieved context, or does it contain claims the context doesn't support? Computed by decomposing the generated answer into individual claims (via an LLM), then checking each claim against the retrieved context for support. Low faithfulness with high context recall is the clearest possible hallucination signal — the right information was right there in the context, and the model still said something the context doesn't support.

**Answer Relevancy** asks: does the generated answer actually address the question that was asked? Computed (in RAGAS's approach) by having a judge model generate several plausible questions the given answer could be answering, then measuring the embedding similarity between those reverse-generated questions and the original question — a low score means the answer, however faithful to the retrieved context, drifted off-topic or answered a different (possibly adjacent) question than the one asked.

**Why all four, not one blended score:** each metric isolates a different, independently-fixable failure. A regression that shows up only in context recall points at retrieval (chunking, embedding model, index recall — the concerns of `01-chunking` through `T06-vector-index-internals`). A regression only in faithfulness points at the generation prompt or model, not retrieval at all. Running only an end-to-end score conflates these and makes debugging a guessing game.

### The LLM-as-judge reliability problem

Every one of RAGAS's four metrics, as typically implemented, relies on an LLM to make a relevance/support/attribution judgment — which means the eval itself inherits LLM failure modes. Documented judge biases include favoring longer, more verbose answers regardless of actual quality, positional bias in pairwise comparisons (preferring whichever answer is shown first or second, inconsistently across setups), and score instability — the same judge scoring the same input differently across repeated runs, especially at temperature > 0. The practical mitigation, converged on across teams: calibrate the LLM judge against a human-labeled subset (a few hundred examples scored by a human, compared against the judge's scores on the same examples) before trusting judge scores on the full eval set at scale, and re-run this calibration check whenever the judge model itself changes, since a judge-model upgrade silently shifts the scoring distribution.

### Golden sets: what they are and why synthetic generation doesn't replace them

A golden set is a curated set of `(question, ground-truth answer, ground-truth supporting chunks)` triples, ideally human-verified, that represents the actual distribution of queries the system needs to handle well — including edge cases (ambiguous questions, questions requiring multi-hop reasoning, questions with no good answer in the corpus at all, to test refusal behavior). It's the reference every other metric ultimately calibrates against: context recall needs ground-truth supporting facts, context precision and faithfulness need a reference answer to check claims against, and the LLM judge itself needs occasional calibration against human judgments on a subset of this same set.

Building one by hand at the scale needed for statistically meaningful regression detection (typically several hundred to a few thousand examples, stratified across query types and corpus sections) is expensive and slow, which is why synthetic question generation exists: an LLM reads a document (or a chunk), generates a plausible question that document could answer, along with the reference answer and supporting evidence, at a controllable difficulty level — single-hop factoid, multi-hop (requiring synthesis across multiple chunks or documents), or comparison/conditional questions that test reasoning rather than lookup. RAGAS's `TestsetGenerator` and comparable tools (DeepEval's Synthesizer, LlamaIndex's dataset generator) implement variations of this pattern, typically with "question evolution" heuristics that take a simple generated question and systematically complicate it (add a constraint, require combining two facts, rephrase to remove an obvious keyword match to the source chunk).

**The trap synthetic generation falls into if unchecked**: a generator producing a question directly from a single chunk tends to produce questions with high lexical overlap to that chunk (the question restates the chunk's own vocabulary), which a retriever can answer via keyword match or a barely-competent embedding, without stress-testing anything realistic about how actual users phrase questions. The mitigation is twofold — deliberately including question-evolution steps that paraphrase away from source vocabulary and require multi-chunk synthesis, and always holding out a human-reviewed subset (reviewing a sample of the generated set for realism, answerability, and whether the "ground truth" answer is actually correct) before trusting the synthetic set as a regression-detection tool. Human-labeled data remains the calibration standard specifically because synthetic generators, however good, inherit blind spots from whatever LLM generated them — including sharing failure modes with the very generation model the eval is meant to test, if the same model family is used for both.

### Retrieval@k vs. answer quality: the discipline

The single highest-leverage evaluation habit is refusing to trust an answer-quality number in isolation. Concretely: before shipping a change, check context recall/precision *and* faithfulness/answer relevancy on the same eval set, not just one. A common, misleading pattern: a prompt-engineering change improves the blended "does this look like a good answer" score, but context recall was unchanged — meaning the improvement came from the model getting better at sounding confident given the same (possibly insufficient) evidence, not from getting more correct. This is exactly the deceptive case a decomposed eval catches and a blended eval hides. The inverse pattern is equally real: a retrieval change (better chunking, a reranker) improves context recall substantially, but the blended answer-quality score barely moves — meaning the generation step isn't making good use of better evidence, which points at the generation prompt (is it actually instructed to use all provided context? does it need explicit instructions to cite/cross-reference multiple chunks?) as the next lever to pull, not further retrieval tuning.

---

## Build it from scratch

A minimal decomposed eval harness — not RAGAS itself, but enough to demonstrate the mechanics of separating retrieval and generation scoring, and to show what a judge call actually does under the hood.

```python
# untested sketch -- illustrates the RAGAS-style decomposition, not a production harness
from dataclasses import dataclass

@dataclass
class EvalExample:
    question: str
    ground_truth_answer: str
    ground_truth_facts: list[str]      # decomposed reference facts, for recall
    retrieved_chunks: list[str]
    generated_answer: str

def context_recall(example: EvalExample, judge_llm) -> float:
    """Fraction of ground-truth facts attributable to the retrieved context."""
    supported = 0
    for fact in example.ground_truth_facts:
        prompt = (
            f"Fact: {fact}\nRetrieved context:\n{example.retrieved_chunks}\n"
            "Is this fact supported by the retrieved context? Answer yes/no."
        )
        if judge_llm(prompt).strip().lower().startswith("yes"):
            supported += 1
    return supported / max(len(example.ground_truth_facts), 1)

def context_precision(example: EvalExample, judge_llm) -> float:
    """Rank-weighted fraction of retrieved chunks that were actually relevant."""
    relevance = []
    for chunk in example.retrieved_chunks:
        prompt = (
            f"Question: {example.question}\nGround truth: {example.ground_truth_answer}\n"
            f"Chunk: {chunk}\nIs this chunk relevant to answering the question? yes/no."
        )
        relevance.append(judge_llm(prompt).strip().lower().startswith("yes"))
    # precision@rank: weight earlier-ranked relevant chunks more heavily
    if not any(relevance):
        return 0.0
    weighted_sum = sum(
        (sum(relevance[: i + 1]) / (i + 1)) for i, rel in enumerate(relevance) if rel
    )
    return weighted_sum / sum(relevance)

def faithfulness(example: EvalExample, judge_llm) -> float:
    """Fraction of claims in the generated answer supported by retrieved context."""
    claims_prompt = f"List the individual factual claims in this answer:\n{example.generated_answer}"
    claims = judge_llm(claims_prompt).split("\n")
    supported = 0
    for claim in claims:
        prompt = f"Claim: {claim}\nContext:\n{example.retrieved_chunks}\nSupported? yes/no."
        if judge_llm(prompt).strip().lower().startswith("yes"):
            supported += 1
    return supported / max(len(claims), 1)

def answer_relevancy(example: EvalExample, judge_llm, embedder, n_reverse: int = 3) -> float:
    """Similarity between the original question and questions the answer could be answering."""
    prompt = f"Generate {n_reverse} questions this answer could be responding to:\n{example.generated_answer}"
    reverse_questions = judge_llm(prompt).split("\n")[:n_reverse]
    q_vec = embedder.embed(example.question)
    sims = [cosine_similarity(q_vec, embedder.embed(rq)) for rq in reverse_questions]
    return sum(sims) / len(sims)

def cosine_similarity(a, b):
    import numpy as np
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))
```

The point of building this by hand once is to internalize that every one of these "metrics" is really a structured LLM-judge prompt, which is exactly why judge calibration against human labels matters — the metric's reliability is bounded by the judge's reliability, not by the elegance of the framework computing it.

---

## How it's done in production

**RAGAS** — the reference open-source framework for the four-metric decomposition and `TestsetGenerator`-based synthetic data. **DeepEval** — pytest-native, designed to run inside CI as part of a normal test suite, with its own Synthesizer for test data. **Confident AI / TruLens / Arize Phoenix** — hosted or self-hosted eval platforms layering dashboards, regression tracking over time, and span-level tracing (which chunk, which prompt, which model call) on top of similar metric decompositions. **Human-in-the-loop review tools** — used specifically for calibrating LLM judges and reviewing synthetic question quality, not for scoring every example at production scale.

| Symptom | Cause | Fix |
|---|---|---|
| Answer-quality score improves after a prompt change, but users report more wrong answers in production | The eval only tracked a blended/generation-side score; context recall on the same eval set was unchanged or dropped, meaning the model got better at sounding right, not being right | Always report context recall/precision alongside any answer-quality metric; treat an answer-quality improvement with flat/falling recall as a red flag, not a win |
| Synthetic eval set shows near-perfect retrieval scores that don't match production experience | Generated questions have high lexical overlap with their source chunk, making them trivially retrievable by keyword match, and don't represent how real users phrase questions | Add question-evolution/paraphrasing steps to the generator; hold out a human-reviewed sample to check realism before trusting the synthetic set |
| LLM judge gives inconsistent scores across repeated runs on the same input | Judge temperature > 0, or the judge model itself has scoring instability on ambiguous cases | Lower judge temperature, average over multiple judge calls, and calibrate against a human-labeled subset to quantify (not eliminate) the noise |
| High faithfulness score but users still report hallucinations | Faithfulness only checks claims against *retrieved* context; if retrieval itself surfaced wrong-but-plausible context (a context recall failure), a faithful answer can still be substantively wrong | Check context recall/precision on the same failing examples — a faithfulness-only view can't distinguish "grounded in good context" from "grounded in bad context" |
| Eval scores look great in CI but production quality metrics (user thumbs-down rate, escalation rate) disagree | Golden/synthetic set doesn't represent the actual production query distribution — missing edge cases, ambiguous questions, or corpus sections that get disproportionate real traffic | Periodically refresh the golden set from actual production query logs (with PII handling per `T06-rag-production`), not just the original curated/synthetic set |

---

## Tradeoffs & when NOT to use it

- **Don't rely on synthetic question generation as your only eval data source, ever.** It systematically underrepresents the ambiguity, typos, and unusual phrasing of real user queries, and can inherit the blind spots of whatever LLM generated it. Always hold a human-reviewed and, ideally, production-log-derived subset alongside it.
- **Don't trust an LLM judge's absolute score without calibration.** Judge biases (verbosity preference, positional bias, run-to-run instability) are well-documented; an uncalibrated judge can tell you *direction* of change reasonably well but its absolute numbers are not comparable across judge-model versions without recalibration.
- **Don't run only a blended end-to-end score if you have any budget for evaluation at all.** The entire value of RAGAS-style decomposition is attribution — skipping it to save eval cost/complexity means every regression becomes a full-pipeline debugging session instead of a targeted fix.
- **Don't over-invest in RAGAS-style automated eval for a low-stakes, low-volume internal tool where a human spot-check genuinely suffices.** The eval infrastructure (golden sets, judge calibration, CI integration) has real setup and maintenance cost; it earns its keep at meaningful query volume or when regressions have real business cost, not for every internal proof-of-concept.
- **Don't treat context recall as a substitute for `Recall@k` derived properly against a full relevance-labeled retrieval benchmark** (see `T06-accuracy-tuning`) — RAGAS's context recall is judge-estimated against a single reference answer's decomposed facts, which is a useful proxy but not the same rigor as a labeled retrieval benchmark built for that specific purpose.

---

## Interview questions

### Q1 — Why decompose RAG evaluation into retrieval and generation metrics instead of one end-to-end score?
**Testing:** basic grasp of why attribution matters.
**Answer:** A single blended score can't tell you whether a bad answer came from missing evidence (retrieval failure) or from misusing good evidence (generation failure), which means every regression requires manual investigation from scratch. Decomposed metrics (context precision/recall for retrieval, faithfulness/answer relevancy for generation) let you attribute a regression to a specific subsystem immediately.
**Follow-up trap:** *"Isn't a single score simpler to track over time?"* — simpler to report, not simpler to act on; you'd still need to decompose it manually the moment it regresses, so the "simplicity" is illusory.

### Q2 — Define context precision and context recall precisely, and give an example of each failing independently.
**Answer:** Context recall = of what was needed to answer correctly, how much did retrieval surface (a recall failure means a fact was never retrieved, unfixable by prompt tuning). Context precision = of what was retrieved, how much was actually relevant, rank-weighted (a precision failure means noisy/irrelevant chunks are diluting the context, even if the needed fact is technically present somewhere in the retrieved set). You can have high recall with low precision (retrieved everything needed plus a lot of noise) or the reverse (retrieved a small, precise set that's missing a key fact).
**Follow-up trap:** *"Which one would you prioritize fixing first if both are mediocre?"* — recall first, generally, since a precision problem at least gives the generation model a chance to find the right fact amid noise, while a recall problem means the fact is structurally absent no matter how good generation is.

### Q3 — What does faithfulness measure, and what's the clearest signal of hallucination in the decomposed metrics?
**Answer:** Faithfulness checks whether each claim in the generated answer is supported by the retrieved context, typically by decomposing the answer into individual claims and checking each against the context. High context recall (the right facts were retrieved) combined with low faithfulness (the answer doesn't reflect them) is the clearest hallucination signal — the model had what it needed and still invented something unsupported.
**Follow-up trap:** *"What if faithfulness is high but context recall is low?"* — that's a faithful-but-incomplete or faithful-but-wrong answer: the model correctly used what it was given, but what it was given wasn't enough or wasn't the right evidence — a retrieval problem masquerading as an apparently well-grounded answer.

### Q4 — Why can't answer relevancy alone tell you whether a RAG system is working well?
**Answer:** Answer relevancy only checks whether the answer addresses the question asked — it says nothing about whether the answer is factually correct or grounded in retrieved evidence. A confidently on-topic but hallucinated answer can score high on relevancy while being substantively wrong, which is exactly why it has to be read alongside faithfulness and context recall, not in isolation.
**Follow-up trap:** *"How is answer relevancy actually computed in RAGAS?"* — by having a judge model generate several questions the given answer could plausibly be answering, then measuring embedding similarity between those reverse-generated questions and the original question.

### Q5 — What are the documented reliability problems with using an LLM as a judge for these metrics?
**Answer:** Verbosity bias (judges tend to prefer longer answers regardless of quality), positional bias in pairwise comparisons, and run-to-run score instability, especially at nonzero temperature. The practical mitigation is calibrating the judge against a human-labeled subset before trusting its scores at scale, and re-calibrating whenever the judge model changes.
**Follow-up trap:** *"How would you detect that your judge has drifted after a model upgrade?"* — re-run the calibration check (compare judge scores to the same human-labeled subset) after any judge-model version change; a silent shift in the scoring distribution is exactly the failure this catches.

### Q6 — Why does synthetic question generation risk producing questions that don't stress-test retrieval realistically?
**Answer:** A generator producing a question directly from a single source chunk tends to reuse that chunk's own vocabulary, making the question trivially retrievable by keyword or weak-embedding match — this doesn't represent how real users phrase questions, which often paraphrase, combine multiple facts, or omit obvious keywords entirely.
**Follow-up trap:** *"How would you fix a synthetic generator that's producing these trivial questions?"* — add question-evolution/paraphrasing steps that deliberately remove source vocabulary overlap and require multi-chunk synthesis, and hold out a human-reviewed sample to verify realism before trusting the generated set.

### Q7 — Why does human-labeled data remain necessary even with a good synthetic question generator?
**Answer:** Synthetic generators inherit the blind spots and failure modes of whatever LLM generated them, and if the same model family generates both the questions and the answers under test, the eval risks being systematically blind to that model family's specific weaknesses. Human labels are also the only reliable calibration standard for checking LLM-judge scoring itself.
**Follow-up trap:** *"How much human-labeled data is 'enough' for calibration?"* — there's no universal number; a commonly cited practical range is a few hundred examples, enough to compute agreement statistics between human and judge scores with reasonable confidence — size it against your actual variance, not a memorized constant.

### Q8 — A prompt-engineering change improves your blended answer-quality score. What do you check before shipping it?
**Answer:** Context recall and precision on the same eval examples, unchanged. If recall didn't improve (or dropped) while the answer-quality score rose, the improvement likely came from the model sounding more confident or fluent given the same (possibly insufficient) evidence, not from being more correct — a classic decomposed-eval catch that a blended score would hide.
**Follow-up trap:** *"What if recall improved too?"* — then check faithfulness specifically, since improved recall alone doesn't guarantee the generation step is actually using the additional evidence correctly rather than still hallucinating around it.

### Q9 — Design a golden-set refresh strategy for a production RAG system with real user traffic.
**Testing:** whether the candidate treats the golden set as a living artifact rather than a one-time deliverable.
**Answer:** Periodically sample real production queries (with PII handling per `T06-rag-production`), route a subset through human review to label ground-truth answers and supporting evidence, and merge them into the golden set — this catches distributional drift the original curated/synthetic set misses (new corpus sections getting real traffic, new phrasing patterns, edge cases nobody anticipated). Keep the synthetic-generated portion for volume and the production-log-derived portion for realism.
**Follow-up trap:** *"How often would you refresh it?"* — tie it to observed drift, not a fixed calendar interval: monitor a proxy signal (user thumbs-down rate, escalation rate, or judge-score trend on a rolling window of live traffic) and refresh when it moves meaningfully, since a fixed schedule can both over- and under-refresh depending on how fast the corpus and query distribution actually change.

### Q10 — Your context recall is high and stable, but faithfulness has been dropping over the last month with no pipeline changes. What do you investigate?
**Answer:** Since retrieval-side metrics are stable, the fault is on the generation side despite no obvious pipeline change — check for silent upstream changes: has the generation model been auto-upgraded by the provider, has the prompt template been touched by another team, has average retrieved-context length grown (more chunks/noise diluting the model's grounding even with unchanged recall)? A regression with a stable retrieval signal and no acknowledged pipeline change is a strong hint at an unannounced or overlooked generation-side change.
**Follow-up trap:** *"What if it turns out to be a provider-side model update you didn't control?"* — this is exactly why faithfulness/context-recall monitoring needs to run continuously in production, not just at deployment time — provider-side model updates are a real, recurring RAG failure mode outside your own release cadence.

### Q11 — Why is "Recall@k" from a classic IR benchmark not the same thing as RAGAS's context recall?
**Answer:** Recall@k (see `T06-accuracy-tuning`) is typically computed against a labeled relevance benchmark — a fixed, pre-annotated mapping of which documents are relevant to which queries — and measures whether relevant documents appear in the top-k retrieved set. RAGAS's context recall is judge-estimated per example, checking whether a single reference answer's decomposed facts are attributable to the retrieved context for that specific question, without a broader pre-labeled relevance benchmark behind it. Context recall is a faster, cheaper proxy; a labeled Recall@k benchmark is more rigorous but far more expensive to build and maintain.
**Follow-up trap:** *"Which would you build first for a new RAG system?"* — context recall via RAGAS-style eval, since it's cheaper to stand up; invest in a full labeled Recall@k benchmark once the system is mature enough that retrieval tuning ROI justifies the extra labeling cost.

### Q12 — How would you design an eval specifically to catch multi-hop reasoning failures that single-hop question generation would miss?
**Answer:** Use question-evolution techniques in the synthetic generator to explicitly require combining facts from two or more chunks/documents (e.g., "what is the difference between X's approach in document A and Y's approach in document B") rather than only generating questions answerable from a single chunk. Score both context recall (did retrieval surface facts from *all* the needed chunks, not just one) and faithfulness (did the answer correctly synthesize across them, not just restate one side).
**Follow-up trap:** *"What's the retrieval-side risk unique to multi-hop questions?"* — a single top-k retrieval pass optimized for one dominant relevant chunk can starve out a second, differently-worded relevant chunk needed for the other half of the answer — this is exactly the class of problem query decomposition (`T06-query-transformation`) and multi-hop retrieval (`T06-advanced-rag`) exist to address.

### Q13 — What's wrong with using BLEU or ROUGE to evaluate RAG answer quality?
**Answer:** These metrics measure surface n-gram overlap with a reference answer, which rewards a fluent answer that happens to share vocabulary with the reference and penalizes a correct answer phrased differently — neither correlates well with whether the answer is factually grounded in retrieved evidence, which is the failure mode that matters most for RAG specifically (hallucination despite good phrasing, or correct paraphrase scored as wrong).
**Follow-up trap:** *"So are they useless?"* — not entirely; they're cheap, deterministic, and can catch gross regressions (e.g., an empty or garbled answer) cheaply as a fast pre-filter before running more expensive LLM-judge metrics, but shouldn't be the primary quality signal.

### Q14 — Design an evaluation gate for a CI pipeline that blocks a chunking-strategy change from merging if it regresses retrieval quality.
**Answer:** Run the RAGAS-style decomposed eval (at minimum context precision/recall) against a fixed golden/synthetic set on every pull request touching chunking, embedding, or retrieval config; compare against the current production baseline with a defined regression threshold (e.g., more than a few points drop in context recall on the full set, or on any stratified subset representing a specific query type); fail the build if the threshold is crossed. Keep the eval set static across comparisons so score changes reflect the code change, not eval-set drift.
**Follow-up trap:** *"What if the eval set itself needs periodic refreshing, per Q9 — doesn't that break the fixed-baseline comparison?"* — version the golden/eval set alongside the code; when the eval set is refreshed, re-baseline against it explicitly and document the reset, rather than silently comparing new-code-against-old-eval-set or new-eval-set-against-old-code numbers as if they were comparable.

### Q15 — A stakeholder asks for "one number" that tells them if the RAG system is good. What do you tell them?
**Testing:** communicating the decomposition tradeoff to a non-technical audience without either refusing the request or giving a misleading single number.
**Answer:** You can report a single blended score for a dashboard-level summary, but it should be explicitly framed as a summary of several underlying signals (retrieval recall/precision, faithfulness, relevancy), with the decomposed numbers available and monitored underneath — and any time the blended number moves, the investigation still needs to look at the decomposed metrics to know what changed. Offering only the single number trades diagnosability for simplicity in a way that will cost more time later, the first time something regresses.
**Follow-up trap:** *"What if they insist on just one number, no dashboard?"* — pick the one metric most correlated with real business outcomes for this specific product (often faithfulness for compliance-sensitive domains, or context recall for knowledge-completeness-sensitive ones) and be explicit that it's a proxy, not a complete picture, so expectations are set correctly before the first regression investigation.

---

## Red flags that fail you

- Reporting a single blended "answer quality" score with no retrieval-side breakdown.
- Trusting an LLM judge's absolute score without ever calibrating it against human labels.
- Using only synthetic questions with no human-reviewed subset and no production-log-derived questions.
- Not knowing the difference between a context-recall failure (retrieval never surfaced the fact) and a faithfulness failure (the fact was there and the model ignored it anyway).
- Treating BLEU/ROUGE-style overlap metrics as a sufficient RAG quality signal.
- Assuming a synthetic generator produces realistic, non-trivial questions by default without checking for source-vocabulary overlap.
- Not re-baselining an eval when the golden/eval set itself is refreshed, leading to apples-to-oranges score comparisons.

---

## Cheat card

```
RAGAS 4 METRICS (retrieval axis | generation axis)
  Context Precision: of RETRIEVED chunks, how many relevant? rank-weighted.
    low + fine answers -> k too large / reranker not working
  Context Recall: of NEEDED facts, how many retrieved? judge checks reference
    answer's decomposed facts against retrieved context.
    low recall = retrieval failure, UNFIXABLE by prompt tuning
  Faithfulness: is generated answer supported by retrieved context? decompose
    answer into claims, check each vs context.
    high recall + LOW faithfulness = clearest hallucination signal
  Answer Relevancy: does answer address the actual question? judge generates
    reverse questions from the answer, embeds, compares to original question.

DECISION RULE: never trust a blended score alone.
  answer score up + recall flat/down  -> model sounds better, isn't more correct
  recall up + answer score flat       -> generation not using better evidence,
                                          fix the PROMPT not retrieval

LLM-JUDGE RELIABILITY: verbosity bias, positional bias, run-to-run instability
  (esp. temp>0). MUST calibrate against human-labeled subset (~hundreds of ex.)
  before trusting scale scores. Recalibrate after every judge-model change.

GOLDEN SET: (question, ground-truth answer, ground-truth supporting chunks),
  human-verified, includes edge cases (ambiguous, multi-hop, no-answer/refusal).
  Refresh from production query logs (PII-handled), not just original curated set.

SYNTHETIC GENERATION (RAGAS TestsetGenerator, DeepEval Synthesizer, etc.)
  trap: question generated from 1 chunk reuses chunk's own vocabulary ->
    trivially retrievable by keyword match, doesn't stress-test anything
  fix: question-evolution (paraphrase, multi-chunk synthesis, add constraints)
  ALWAYS hold out human-reviewed sample before trusting synthetic set

RETRIEVAL@K vs ANSWER QUALITY: RAGAS context recall = judge-estimated per
  example. Formal Recall@k = pre-labeled relevance benchmark (see accuracy-tuning
  module) -- more rigorous, far more expensive. Build context recall first,
  invest in labeled Recall@k benchmark once retrieval-tuning ROI justifies it.
```

## Sources
- [RAG Evaluation Metrics in 2026: Faithfulness & More — FutureAGI](https://futureagi.com/blog/rag-evaluation-metrics-2025/) — accessed 2026-07-28
- [RAGAS for RAG in LLMs: A Comprehensive Guide to Evaluation Metrics — Medium](https://dkaarthick.medium.com/ragas-for-rag-in-llms-a-comprehensive-guide-to-evaluation-metrics-3aca142d6e38) — accessed 2026-07-28
- [Synthetic Test Data generation — Ragas Documentation](https://docs.ragas.io/en/v0.1.21/concepts/testset_generation.html) — accessed 2026-07-28
- [Synthetic Datasets for RAG in 2026: Methods, QA, and Tools — FutureAGI](https://futureagi.com/blog/synthetic-datasets-rag-2025/) — accessed 2026-07-28
- [The path to a golden dataset, or how to evaluate your RAG? — Data Science at Microsoft / Medium](https://medium.com/data-science-at-microsoft/the-path-to-a-golden-dataset-or-how-to-evaluate-your-rag-045e23d1f13f) — accessed 2026-07-28
- [Retrieval Quality VS. Answer Quality: Why RAG Evaluation Fails — Deepchecks](https://deepchecks.com/retrieval-vs-answer-quality-rag-evaluation/) — accessed 2026-07-28
- [A complete guide to RAG evaluation: metrics, testing and best practices — Evidently AI](https://www.evidentlyai.com/llm-guide/rag-evaluation) — accessed 2026-07-28
- [LLM-as-a-judge: a complete guide to using LLMs for evaluations — Evidently AI](https://www.evidentlyai.com/llm-guide/llm-as-a-judge) — accessed 2026-07-28
- [RAG Evaluation Metrics: Assessing Answer Relevancy, Faithfulness, Contextual Relevancy — Confident AI](https://www.confident-ai.com/blog/rag-evaluation-metrics-answer-relevancy-faithfulness-and-more) — accessed 2026-07-28

## Changelog
- 2026-07-28 — created
