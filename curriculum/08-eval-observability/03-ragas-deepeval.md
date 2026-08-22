# RAGAS + DeepEval Internals, Promptfoo, LangSmith Evals

> **Track:** T08 Eval & Observability · **Time:** 2.0h · **Prereqs:** none · **Updated:** 2026-08-01
> **Module id:** `T08-ragas-deepeval` · **Tags:** eval

## The 30-second version

RAGAS, DeepEval, Promptfoo, and LangSmith are not four different ways of measuring quality — they're four different harnesses wrapped around the same primitive, an LLM judge scoring a decomposed piece of output, and the internals matter because every one of their "metrics" inherits the judge's noise and blind spots wholesale. Faithfulness and context recall decompose text into atomic claims and check each against a source (2-8 LLM calls per example depending on claim count); answer relevancy and context precision use embedding similarity or rank-weighted judge calls, and none of the four can see a mistake that both the generator and the judge are equally wrong about. These scores are continuous and noisy, not pass/fail — a single re-run at nonzero temperature can shift a faithfulness score by several points, so a delta smaller than roughly 0.05-0.08 on a few hundred examples is usually indistinguishable from re-run noise, not a real regression, until you check it with a paired test. DeepEval turns metrics into pytest assertions, Promptfoo turns them into a CI-native prompt-regression matrix across providers, and LangSmith turns them into dataset experiments plus continuous production sampling — all three give you the plumbing to run judge calls at scale, and none of them make the judge more reliable than it already is. A metric from any of these frameworks that hasn't been checked against a human-labeled subset is decoration on a dashboard, not evidence.

## Why this gets asked

The interviewer has adopted one of these frameworks, watched the CI badge turn green, and later found out in a postmortem that the framework's canned metric prompt was scoring something subtly different from what the team assumed it measured — RAGAS's "faithfulness" checking claims against retrieved context, not against the world, or DeepEval's default G-Eval rubric being generic enough to pass almost anything fluent. They want to know whether you'll treat these tools as ground truth because they output a clean number, or whether you know what LLM calls are actually happening under the `.evaluate()` call, what that costs, and how many examples you need before a score change means anything.

---

## Lineage: past → present → future

**What came before.** Before any of these existed, RAG and LLM-app teams ran the same ad-hoc loop described in `T08-eval-harness` — a notebook cell, five remembered examples, a manual "looks fine" — or borrowed BLEU/ROUGE from machine translation, which can't detect a fluent, well-worded hallucination because it only measures string overlap with a reference. RAGAS (Es et al., 2023) was the first widely-adopted framework to formalize the retrieval/generation split as four LLM-judged metrics rather than one blended score (full derivation in `T06-rag-eval`). DeepEval followed shortly after from Confident AI, explicitly positioned as the pytest-native alternative — the pain it targeted was that RAGAS-style evals lived outside the normal test suite and CI pipeline, so nobody ran them on every PR the way they ran unit tests. Promptfoo emerged from a narrower, sharper pain: teams needed to regression-test a *specific prompt* across model/provider changes (a new GPT or Claude version, a temperature tweak) and didn't want to stand up a RAG-shaped eval harness just to catch "this rewrite broke the JSON output." LangSmith (LangChain, 2023) grew out of the observation that RAG/agent teams needed tracing and eval in the same tool, because debugging a bad eval score without the underlying trace is guesswork.

**Where it stands now.** The ecosystem has converged on the same underlying primitive — claim decomposition plus an LLM verdict — even where the marketing differs: DeepEval's faithfulness and hallucination metrics, RAGAS's faithfulness, and LangSmith's built-in RAG evaluators all do some version of "break the answer into atomic claims, ask a judge if each is supported." DeepEval has broadened well past RAG into agents, safety, and summarization metrics, and ships a hosted layer (Confident AI) for dataset versioning and a dashboard, which is now a common pairing with its open-source pytest core. Promptfoo has become the default choice specifically for prompt-level, provider-matrix regression testing gated in CI, and added a red-teaming plugin for adversarial/security testing of prompts. LangSmith in 2026 markets itself less as "a tracing tool with eval bolted on" and more as a full agent-engineering platform, with unified cost tracking across a trace and dataset/experiment tooling that supports both offline (`evaluate()`/`aevaluate()`) and online (continuous, reference-free) evaluators [What is LangSmith? 2026 Guide to LLM Observability](https://www.metacto.com/blogs/what-is-langsmith-a-comprehensive-guide-to-llm-observability) — accessed 2026-08-01. The live disagreement isn't whether the decomposition approach works, it's whether any framework's *default, out-of-the-box* metric prompt is trustworthy for a specific domain without recalibration — the honest consensus among practitioners writing about this in 2026 is no, and every framework's docs now say some version of "customize the rubric for your task" in the fine print that teams skip.

**Where it's heading.** Agentic evaluation is being absorbed into all three frameworks rather than staying a separate discipline — DeepEval, LangSmith, and Promptfoo are each adding tool-call and trajectory-shaped metrics (see `T08-agent-eval` for the underlying methodology, which predates and is being retrofitted into these tools). This is real and shipping, moderate-to-high confidence. A push toward "eval-as-code" — metrics, thresholds, and datasets checked into the same repo as prompts, exactly like `T08-eval-harness` describes for a hand-rolled harness — is visible across all three frameworks' CI integrations. More speculative: a standardized, cross-framework metric definition (so a "faithfulness" score means the identical computation regardless of which tool produced it) has been discussed by practitioners frustrated with framework lock-in, but no such standard exists yet, and framework-specific metric internals change between minor versions without much fanfare — which is itself an operational hazard, covered below.

---

## Mental model

```
                         YOUR HARNESS CALLS ONE OF THESE
        ┌───────────────┬────────────────┬────────────────┬────────────────┐
        │     RAGAS      │    DeepEval     │    Promptfoo    │   LangSmith    │
        │  metric funcs   │ pytest metrics  │  YAML assertions │ evaluate() SDK │
        └───────┬────────┴────────┬────────┴────────┬────────┴────────┬───────┘
                │                 │                 │                 │
                └────────────────┴────────┬────────┴─────────────────┘
                                          ▼
                     EVERY "METRIC" REDUCES TO ONE OF TWO PRIMITIVES:

              (a) CLAIM DECOMPOSITION + JUDGE VERDICT             (b) EMBEDDING SIMILARITY
              1 call: split answer into N atomic claims          1 call: generate reverse
              N calls (or 1 batched): is each claim              questions from the answer
              supported by {context | reference}?                embed + cosine-similarity
              score = supported / N                              vs the original question

              used by: faithfulness, context recall,              used by: answer relevancy
              hallucination, most "groundedness" metrics          (RAGAS-style)

        BOTH PRIMITIVES INHERIT: judge bias (position/verbosity/self-preference,
        see T08-llm-as-judge), run-to-run score noise at temp>0, and blindness to
        anything the judge and the generator are BOTH wrong about.

        cost per example ≈ (1 + N_claims) LLM calls PER metric that uses (a)
        a 4-metric RAG eval ≈ 10-20 judge calls per single row
```

The frameworks differ in ergonomics — pytest assertions vs. YAML config vs. dataset experiments — not in what's actually happening on the wire. If you can't say which primitive a given metric uses, you can't reason about its cost, its noise, or its blind spot.

---

## How it actually works

### The four RAGAS-style metrics, computationally, and what each can't see

Full RAG-specific derivation of these four (with the retrieval/generation attribution table) lives in `T06-rag-eval`; here's the computation and blind spot for each, since DeepEval and LangSmith reimplement close variants of the same thing under different names:

- **Faithfulness** — decompose the generated answer into atomic claims (1 LLM call), then check each claim against the retrieved context (1 call per claim, or a single batched call in newer implementations). Score = supported claims / total claims. **Blind spot:** it only checks the answer against *retrieved* context, never against the world — a faithfulness score of 1.0 on an answer grounded in a wrong retrieved chunk is a perfectly "faithful" hallucination. It's also blind to *omission*: an answer that faithfully repeats one supported claim and ignores three others it should have surfaced still scores high.
- **Answer relevancy** — judge generates several reverse-engineered questions the given answer could be answering, embeds them, and measures cosine similarity to the original question. **Blind spot:** entirely blind to factual correctness. An answer can be perfectly on-topic and completely wrong and still score high, because relevancy never touches truth, only topical alignment.
- **Context precision** — judge scores each retrieved chunk's relevance to the reference answer, rank-weighted so earlier-ranked relevant chunks count more. **Blind spot:** assumes rank position matters uniformly for the generation step that follows; a generation prompt that reads the whole context window unordered (common with short contexts) makes the rank-weighting moot even though the score still penalizes it.
- **Context recall** — needs a reference answer decomposed into facts, then checks whether each fact is attributable to the retrieved context. **Blind spot:** it's only as good as the reference answer. A wrong or incomplete reference produces a wrong or incomplete recall score with no signal that the reference itself, not the retriever, is the problem.

**Cost per example, concretely.** A typical generated answer decomposes into roughly 3-6 atomic claims. Faithfulness alone is therefore 1 (decompose) + 3-6 (per-claim check) = 4-7 LLM calls for a single example. Running all four metrics on one row commonly lands at 10-20 total judge calls, because context recall needs a comparable claim-decomposition pass against the reference answer. This is not a framework quirk you can configure away — it's inherent to the claim-decomposition approach, and it's why a full four-metric RAGAS/DeepEval suite over a few hundred rows is a few thousand LLM calls, not a few hundred.

### How noisy the scores actually are, and how many examples before a delta is real

These are continuous 0-1 scores, not binomial pass/fail, which changes the sample-size math from the binomial-proportion arithmetic in `T08-eval-harness`. Two sources of noise stack: (1) judge sampling noise — the same example, same judge, same prompt, rerun at nonzero temperature, produces a different score; a 2026 study on LLM-judge reliability measured a **14% mean flip rate** on pairwise judge comparisons re-run under identical conditions [The Coin Flip Judge? Reliability and Bias in LLM-as-a-Judge Evaluation (arXiv)](https://arxiv.org/pdf/2606.13685) — accessed 2026-08-01, and continuous claim-level scores show comparable instability; (2) sample noise from your eval set being a finite sample of the true distribution, with reported bootstrap confidence-interval half-widths on LLM-eval scores typically landing around **3-5 percentage points** at a few hundred examples.

To tell a real regression from noise, use a **paired difference test** across the same examples run before and after a change (paired t-test or bootstrap on the per-example score differences), not a comparison of two independent means. Back-of-envelope sample size using the standard two-sample-mean formula n ≈ 2σ²(z_{α/2}+z_β)²/δ², with a typical faithfulness-score standard deviation of roughly σ ≈ 0.15-0.25 and a minimum meaningful shift of δ = 0.05: n lands around **100-250 paired examples** to reliably detect a 5-point mean shift at conventional power (80%, α=0.05) — the same order of magnitude as the ~250-example binomial guidance in `T08-eval-harness`, arrived at differently because these scores are continuous, not pass/fail. Below that, a 3-5 point swing in a nightly dashboard is exactly the re-run noise described above, not a signal.

### DeepEval's assertion model

DeepEval's core move is making a metric behave like a pytest assertion: it returns a 0-1 score and a human-readable reason, and `assert_test()` fails the test when the score drops below a threshold you set, so a prompt regression fails the build exactly like a broken unit test [Unit Testing in CI/CD — DeepEval docs](https://deepeval.com/docs/evaluation-unit-testing-in-ci-cd) — accessed 2026-08-01.

```python
# untested sketch
import pytest
from deepeval import assert_test
from deepeval.metrics import FaithfulnessMetric, GEval
from deepeval.test_case import LLMTestCase, LLMTestCaseParams

faithfulness = FaithfulnessMetric(threshold=0.7, model="gpt-4o-mini")

conciseness = GEval(
    name="Conciseness",
    criteria="Does the response answer the question without unnecessary padding?",
    evaluation_params=[LLMTestCaseParams.INPUT, LLMTestCaseParams.ACTUAL_OUTPUT],
    threshold=0.6,
)

@pytest.mark.parametrize("row", load_golden_rows("rag_golden_v14.json"))
def test_rag_answer_quality(row):
    tc = LLMTestCase(
        input=row.question,
        actual_output=generate_answer(row.question),
        retrieval_context=retrieve(row.question),
    )
    assert_test(tc, [faithfulness, conciseness])
    # deepeval test run picks this up in CI exactly like any other pytest suite
```

`GEval` is DeepEval's G-Eval implementation: give it a plain-English criterion, it generates its own chain-of-thought evaluation steps and scores against them, rather than requiring a fixed metric definition — this is the same G-Eval technique described in `T08-llm-as-judge`, packaged as a reusable metric class. The Confident AI hosted layer syncs golden datasets and run history so `deepeval test run` in CI writes results somewhere durable instead of only printing to a CI log.

### Promptfoo: prompt-level regression across providers

Promptfoo is YAML-config-driven and built around a matrix: N prompts × M providers/models, each cell scored by a list of assertions. Three assertion tiers, cheapest first: deterministic (`contains`, `equals`, `regex`, `cost`, `latency` — free, instant, exact), model-graded (`llm-rubric`, `similar`, `answer-relevance` — sends the output to a judge LLM), and custom code (inline JavaScript or Python for anything the first two can't express) [Promptfoo Tutorial — DataCamp](https://www.datacamp.com/tutorial/promptfoo-tutorial) — accessed 2026-08-01.

```yaml
# promptfooconfig.yaml — untested sketch
prompts:
  - "Summarize this ticket in one sentence: {{ticket}}"
providers:
  - openai:gpt-4o-mini
  - anthropic:claude-sonnet-4-6
tests:
  - vars:
      ticket: "Customer reports checkout button unresponsive on Safari 18."
    assert:
      - type: contains
        value: "Safari"
      - type: cost
        threshold: 0.002
      - type: llm-rubric
        value: "Summary is one sentence and names the affected browser"
```

The GitHub Action runs this matrix on every PR and posts a before/after diff as a review comment, which is the specific gap Promptfoo fills that a full RAG harness doesn't: a one-line prompt tweak that needs a fast provider-comparison regression check, not a four-metric retrieval/generation attribution suite. Best practice mirrors `T08-eval-harness`'s deterministic-first rule: exhaust `contains`/`regex`/`cost`/`latency` checks before reaching for `llm-rubric`, because the deterministic tier is free and has zero judge noise.

### LangSmith evals: datasets, experiments, and online evaluators

LangSmith's model is a **dataset** (versioned examples) plus an **experiment** (one run of a system-under-test against that dataset, capturing outputs, evaluator scores, and full traces per example). The `evaluate()`/`aevaluate()` SDK functions run a target function against a dataset with a list of evaluators (LLM-as-judge, custom code, or routed to human review), and the run-comparison UI flags per-example regressions between two experiments side by side [Evaluation concepts — LangChain docs](https://docs.langchain.com/langsmith/evaluation-concepts) — accessed 2026-08-01. Separately, **online evaluators** score live production traces continuously with no reference output required — a reference-free judge call sampled against real traffic, feeding the same dashboards as offline experiments, which is the "eval and monitoring share one system" pattern flagged as a live direction in `T08-eval-harness` and `T09-model-monitoring`. Because traces, evals, and cost are captured in one system, LangSmith can show a regression in eval score next to the cost and latency of the exact trace that produced it, which none of the other three tools do natively — Promptfoo has no production trace concept, and DeepEval's cost tracking is per-test-run, not per-live-trace.

### The honest take

None of these frameworks make the underlying judge more reliable. A team that installs RAGAS, gets a faithfulness score of 0.91, and ships is trusting a canned rubric and a canned judge prompt they didn't write and haven't checked against a single human label — the exact failure `T08-llm-as-judge` describes, wearing a framework's UI. The discipline doesn't change because the tool changed: sample 100-300 real examples, get human labels on the same rubric the framework's metric claims to measure, compute agreement (Cohen's kappa or Krippendorff's alpha), and only trust the framework's number at the volume the calibration supports. Recalibrate whenever you upgrade the framework version — metric prompts inside RAGAS, DeepEval, and LangSmith's built-in evaluators change between releases without a changelog entry most teams read, and a silent prompt change shifts the score distribution exactly like a silent judge-model swap does.

### Cost and latency of running a full suite

Back-of-envelope, not a vendor-published figure: a four-metric RAGAS/DeepEval suite at ~15 judge calls/example, ~500 input + 150 output tokens per call, on a mid-tier judge (roughly GPT-4o-mini-class pricing) costs on the order of a few dollars for a 300-row PR-gate run and tens of dollars for a multi-thousand-row nightly run with a frontier judge substituted in for calibration or hard cases. Latency compounds fast if calls run serially: 300 rows × 15 calls × ~1s median judge latency is over an hour of wall-clock time run sequentially — the reason every one of these frameworks defaults to async/concurrent execution, and why a PR gate needs a small stratified subset (mirroring the tiering strategy in `T08-eval-harness` and `T08-agent-eval`) rather than the full golden set on every commit.

---

## Build it from scratch

A minimal claim-decomposition faithfulness metric shaped like what DeepEval's `FaithfulnessMetric` does internally — the point is seeing that "the metric" is two LLM calls and a ratio, not magic:

```python
# untested sketch
from dataclasses import dataclass

@dataclass
class MetricResult:
    score: float
    reason: str

def faithfulness_metric(question: str, answer: str, context: list[str], judge_llm) -> MetricResult:
    claims_prompt = f"List the atomic factual claims in this answer, one per line:\n{answer}"
    claims = [c.strip() for c in judge_llm(claims_prompt).split("\n") if c.strip()]

    if not claims:
        return MetricResult(score=1.0, reason="no factual claims to check")

    supported = 0
    unsupported = []
    for claim in claims:
        verdict_prompt = (
            f"Context:\n{context}\n\nClaim: {claim}\n"
            "Is this claim directly supported by the context above? Answer yes or no."
        )
        if judge_llm(verdict_prompt).strip().lower().startswith("yes"):
            supported += 1
        else:
            unsupported.append(claim)

    score = supported / len(claims)
    reason = "all claims supported" if not unsupported else f"unsupported: {unsupported}"
    return MetricResult(score=score, reason=reason)

def assert_metric(result: MetricResult, threshold: float = 0.7):
    assert result.score >= threshold, f"faithfulness {result.score:.2f} < {threshold}: {result.reason}"
```

This is 1 + N_claims calls exactly as described above — running it against a 300-row eval set with an average of 4 claims per answer is 1,500 judge calls, which is the number to have in your head before agreeing to run a metric like this on every PR.

---

## How it's done in production

| Symptom | Cause | Fix |
|---|---|---|
| Eval scores shift a few points after upgrading RAGAS/DeepEval/LangSmith, with no code or prompt change | Framework changed its default metric prompt or judge model between versions, undocumented in a way most teams notice | Pin the framework version explicitly in CI; re-baseline (and recalibrate against human labels) on any intentional upgrade, treat it like a judge-model swap |
| Full 4-metric suite takes 40+ minutes and gets skipped or disabled | Serial execution of ~15 judge calls/example across the full golden set on every commit | Run a small stratified subset synchronously on PR, full suite async/concurrent on a nightly or merge-to-main cadence (same tiering as `T08-eval-harness`) |
| Promptfoo's `llm-rubric` assertion passes one run and fails the next with no prompt change | Grading model running at temperature > 0 | Pin judge temperature to 0, or average N grading calls and threshold on the mean |
| DeepEval's G-Eval and RAGAS's faithfulness disagree on the same example | Different claim-decomposition granularity and/or different underlying judge model between the two frameworks | Don't treat frameworks as interchangeable oracles; pick one as the source of truth per metric family and calibrate that one specifically |
| LangSmith online evaluator flags a spike in low-faithfulness production traces | Ambiguous without more context — could be a real regression or a shift in traffic mix toward harder queries | Cross-reference the flagged traces' cost/latency and input distribution in the same trace view before concluding it's a model regression rather than a traffic shift |
| A metric reports 0.95+ faithfulness that doesn't match spot-checked reality | The retrieved context itself is wrong, and faithfulness only checks the answer against context, not against the world | Add a context-recall or reference-based check in parallel; faithfulness alone cannot catch this by design |

---

## Tradeoffs & when NOT to use it

- **Don't run all four tools at once.** Pick one primary eval harness for your system's shape (RAGAS/DeepEval for a RAG or generation-heavy system, LangSmith/Braintrust if you want tracing and eval unified) and use Promptfoo surgically for fast prompt-level A/B checks pre-merge — running every framework in parallel triples judge-call cost for marginal additional signal.
- **Don't trust a framework's canned metric prompt as calibrated for your domain out of the box.** Every one of these ships a generic rubric; rewrite it with the same anchor-example, single-criterion discipline from `T08-llm-as-judge` before trusting it past a demo.
- **Don't gate every PR on the full four-metric suite for a low-traffic or low-stakes feature.** The judge-call cost and CI wall-clock time is real; `T08-eval-harness`'s "don't build a full harness for a three-user internal tool" applies directly here — a lighter deterministic-plus-one-metric check is proportionate.
- **Don't use Promptfoo's `llm-rubric` as your only quality gate for a RAG system.** It doesn't decompose retrieval from generation the way RAGAS/DeepEval do, so you lose the attribution table that tells you whether a regression is a retrieval problem or a generation problem — see `T06-rag-eval`.
- **Don't compare a framework's absolute score across framework versions or across frameworks as if it were the same measurement.** A 0.85 faithfulness in RAGAS v1 and a 0.85 in DeepEval are not guaranteed to mean the same thing; only trends within one pinned framework version, calibrated once, are comparable.

---

## Interview questions

### Q1 — What is actually happening under the hood when RAGAS computes a faithfulness score?
**Testing:** whether the candidate understands the metric is a structured judge call, not a black box.
**Answer:** The generated answer is decomposed into atomic factual claims by one LLM call, then each claim is checked against the retrieved context by a judge call (or one batched call), and the score is the fraction of claims supported. For a typical 3-6 claim answer that's 4-7 LLM calls for this one metric.
**Follow-up trap:** *"So a faithfulness score of 1.0 means the answer is correct?"* — no, it means every claim is supported by the *retrieved context*, which says nothing about whether that context itself is correct; a faithful answer grounded in a wrong chunk still scores 1.0.

### Q2 — Why can't answer relevancy alone tell you the RAG system is working?
**Answer:** Answer relevancy measures topical alignment between the answer and the question via reverse-question generation and embedding similarity — it's entirely blind to factual correctness. A confidently on-topic, completely wrong answer scores well.
**Follow-up trap:** *"How would you catch that specific failure?"* — pair relevancy with faithfulness and context recall; a high-relevancy, low-faithfulness combination is exactly the "on-topic but hallucinated" signature.

### Q3 — Your faithfulness score moved from 0.82 to 0.77 after a prompt change. Is that a real regression?
**Testing:** whether they apply statistical discipline to continuous eval scores, not just binomial pass rates.
**Answer:** Not necessarily — continuous judge-graded scores carry both judge sampling noise (rerun instability, on the order of a double-digit percent flip rate on comparisons) and sample noise from a finite eval set (bootstrap CI half-widths commonly 3-5 points). A 5-point swing needs a paired difference test across the same examples before and after, not a bare before/after comparison.
**Follow-up trap:** *"Your eval set only has 40 examples. Does the paired test still help?"* — less so; at that size you likely don't have the statistical power to detect anything short of a large effect, which is why the module targets roughly 100-250 paired examples for a reliable 5-point-shift detection.

### Q4 — How many LLM calls does a full four-metric RAGAS/DeepEval suite cost per example, roughly, and why does that matter?
**Answer:** Roughly 10-20 judge calls per example, because faithfulness and context recall both require a claim-decomposition pass (1 + N_claims calls each) on top of the single-call metrics. It matters because it directly drives CI wall-clock time and dollar cost — running the full suite on every PR at that call volume is the reason teams tier: small subset on PR, full suite nightly/async.
**Follow-up trap:** *"Can you cut this cost without losing signal?"* — batch claim-verdict checks into a single call per answer instead of one call per claim where the provider supports structured output, and reserve the full per-claim granularity for the slower nightly run or for examples that fail the batched check.

### Q5 — What does DeepEval's `assert_test()` actually do, and how is it different from a normal pytest assertion?
**Answer:** It runs the specified metrics against an `LLMTestCase`, gets back continuous scores and reasons, and raises an assertion failure if any score is below its configured threshold — mechanically it's a normal pytest assertion, but the value being asserted on is itself a noisy LLM-judge output rather than a deterministic computation.
**Follow-up trap:** *"Doesn't that make your test suite flaky by definition?"* — yes, more than a typical unit test, which is exactly why the threshold needs headroom above the metric's known noise floor and why CI gates on this kind of test should track a run-set or trend, not treat a single failing run as proof of a regression.

### Q6 — Design a CI strategy using Promptfoo for a prompt that runs across three model providers.
**Answer:** Config the providers array with all three, deterministic assertions (`contains`, `cost`, `latency`) for cheap invariant checks that should hold regardless of provider, `llm-rubric` only for the genuinely subjective quality dimension, and wire the GitHub Action to post the before/after diff on every PR touching the prompt file so a reviewer sees the regression across all three providers at once, not just the one the author tested manually.
**Follow-up trap:** *"One provider fails the rubric check but the other two pass. Do you block the merge?"* — depends on whether that provider is in the production routing path; if it's a fallback/secondary provider, flag it as a known gap and track it rather than blocking, but never silently drop the failing provider from the matrix.

### Q7 — What's the difference between LangSmith's offline `evaluate()` and its online evaluators?
**Answer:** `evaluate()`/`aevaluate()` runs a system-under-test against a versioned dataset with known (or at least fixed) examples, producing an experiment you can diff against a previous one. Online evaluators score live production traces continuously and reference-free, feeding the same dashboards without needing a pre-built dataset — this is where eval and production monitoring overlap (see `T09-model-monitoring`).
**Follow-up trap:** *"If online evaluators don't need a reference, what are they actually checking?"* — typically reference-free judge criteria (coherence, groundedness against the trace's own retrieved context, policy compliance) or deterministic checks (schema validity, latency, cost) that don't require a ground-truth answer to evaluate.

### Q8 — A teammate says "let's just run RAGAS, DeepEval, and LangSmith evals all in parallel for redundancy." What's wrong with that plan?
**Answer:** It roughly triples judge-call volume and cost for marginal signal, since all three implement close variants of the same claim-decomposition primitive — you're not getting three independent measurements, you're paying three times for correlated noise from similar judge architectures. Better to pick one as the calibrated source of truth and use the others surgically for what they're specifically good at (Promptfoo for provider-matrix regression, LangSmith for trace-linked production sampling).
**Follow-up trap:** *"What if the three disagree on the same example?"* — that's useful signal about judge instability, not a reason to average all three scores together; investigate the specific example manually rather than treating disagreement as something a blended score should paper over.

### Q9 — Why does upgrading a framework version count as a risk in the same category as swapping the judge model?
**Answer:** These frameworks' built-in metrics have their own internal prompt templates and sometimes their own pinned judge defaults, and both can change silently between minor versions with no changelog entry most teams read. A score shift after an upgrade with no code change on your side is indistinguishable from a real regression unless you know to check the framework's release notes and re-baseline.
**Follow-up trap:** *"How do you protect against this in practice?"* — pin the framework version explicitly in your dependency lockfile, treat any intentional upgrade as requiring a re-run of your human-label calibration check before trusting the new scores, exactly like a judge-model version bump.

### Q10 — Design the eval strategy for a small team that just added RAG to an existing chat product and has no eval infrastructure yet.
**Testing:** applying the whole toolkit in the right order rather than reaching for every tool at once.
**Answer:** Start with `T08-eval-harness`'s structure (dataset, runner, scorers, reporting) using a small hand-curated golden set from real support tickets. Add DeepEval's `FaithfulnessMetric` and `AnswerRelevancyMetric` as pytest assertions gating merges to the retrieval/generation code paths, deterministic checks first for anything checklist-shaped (valid JSON, required citation format). Add Promptfoo only once there's a specific prompt under active multi-provider iteration. Hold off on LangSmith/production tracing until there's real production traffic to sample — the online-evaluator value only exists once traffic exists.
**Follow-up trap:** *"The team wants to skip the human-labeled calibration step to move faster. What do you tell them?"* — that's the step that determines whether any of the scores from the next three tools mean anything; skipping it doesn't save time, it defers the cost to the first postmortem where someone asks "how do we know 0.85 is good" and there's no answer.

### Q11 — Your faithfulness metric costs $40/night to run on the full golden set with a frontier judge. Leadership asks you to cut it to $10.
**Answer:** Switch the nightly full-suite judge to a cheap model (mini-class) for the bulk of examples, and route only disagreements or borderline scores (near the threshold) to the frontier judge for adjudication — the same cheap-judge/frontier-judge router pattern from `T08-llm-as-judge`. Batch per-claim verdict checks into fewer calls where the provider supports structured multi-claim output in one response, cutting the per-example call count directly.
**Follow-up trap:** *"Does using a cheaper judge change what the score means?"* — potentially yes; a cheap judge and a frontier judge don't always agree at the same rate on the same rubric, so re-run the human-label calibration check specifically against the cheaper judge before trusting its absolute numbers, not just its relative trend.

### Q12 — What's the risk of treating a passing DeepEval/RAGAS/Promptfoo suite as sufficient sign-off before shipping a RAG feature?
**Answer:** None of these frameworks replace human calibration, and none of them catch a failure mode both the generator and the judge share (the shared-blind-spot problem from `T08-llm-as-judge` and `T06-rag-eval`) — a passing suite tells you the system agrees with an uncalibrated judge's opinion of itself, not that it's correct.
**Follow-up trap:** *"The suite has 95% pass rate and support tickets are still rising. What do you check first?"* — exactly the eval-set-staleness diagnosis from `T08-eval-harness`: whether the golden set still represents current traffic, and separately whether the framework's canned rubric was ever calibrated against human labels for this specific product's definition of "good."

---

## Red flags that fail you

- Describing RAGAS/DeepEval/LangSmith/Promptfoo scores as ground truth with no mention of judge calibration.
- Not knowing that faithfulness and context recall involve multiple LLM calls per example (claim decomposition plus per-claim verdicts).
- Treating a small score change (a few points) as a confirmed regression with no paired significance check.
- Running all four frameworks in parallel "for redundancy" without recognizing the cost multiplication and correlated noise.
- Comparing absolute scores across framework versions or across different frameworks as if they measured the same thing.
- Using Promptfoo's `llm-rubric` as the sole quality gate for a RAG system with no retrieval/generation attribution.
- Not having a plan for what happens to CI runtime when someone adds a fifth metric to the nightly suite.

---

## Cheat card

```
PRIMITIVES     (a) claim decomposition + judge verdict: faithfulness, context
                   recall, hallucination-style metrics. Cost = 1 + N_claims calls.
               (b) reverse-question + embedding similarity: answer relevancy.

RAGAS 4        faithfulness (blind: bad context = "faithful" hallucination)
METRICS        answer relevancy (blind: factual correctness, only checks topic)
               context precision (blind: assumes rank always matters to gen.)
               context recall (blind: only as good as the reference answer)
               (full retrieval/gen attribution: T06-rag-eval)

COST/EXAMPLE   ~3-6 claims per answer -> faithfulness alone = 4-7 calls
               full 4-metric suite ~= 10-20 judge calls/example
               300-row PR suite, mid-tier judge: few $ ; nightly frontier: tens of $

NOISE          judge rerun flip rate ~14% on comparisons (2026 study)
               bootstrap CI half-width ~3-5pp on continuous scores
               use PAIRED test on same examples, not raw before/after means

SAMPLE SIZE    continuous score, sigma~0.15-0.25, detect delta=0.05 ->
               n ~ 100-250 paired examples (80% power, alpha=0.05)
               below that: a 3-5pt swing is noise, not signal

DEEPEVAL       assert_test() + threshold = pytest assertion on a noisy score
               GEval = CoT rubric-as-metric class; Confident AI = hosted dataset/dash

PROMPTFOO      YAML: prompts x providers matrix. Assertion tiers:
               deterministic (contains/regex/cost/latency) -> model-graded
               (llm-rubric/similar) -> custom code. GH Action = PR diff view.

LANGSMITH      dataset + experiment (evaluate()/aevaluate()), regression flags
               online evaluators: reference-free, continuous, on live traffic
               only tool here joining eval score + cost + latency on one trace

HONEST TAKE    a framework score with no human-label calibration is decoration.
               recalibrate on: judge model swap, rubric edit, FRAMEWORK VERSION BUMP
               (metric prompts change silently between releases)

DON'T          run all 4 frameworks in parallel · trust canned rubrics uncalibrated
               · full suite on every PR for a low-stakes feature · compare scores
               across framework versions as if identical measurements
```

## Sources

- [Unit Testing in CI/CD — DeepEval docs](https://deepeval.com/docs/evaluation-unit-testing-in-ci-cd) — accessed 2026-08-01
- [deepeval · PyPI](https://pypi.org/project/deepeval/) — accessed 2026-08-01
- [Promptfoo Tutorial: A Hands-On Guide to LLM Evaluation — DataCamp](https://www.datacamp.com/tutorial/promptfoo-tutorial) — accessed 2026-08-01
- [Testing LLM prompts like code: regression evals in CI/CD with promptfoo — Medium](https://medium.com/@alexrodriguesj/testing-llm-prompts-like-code-regression-evals-in-ci-cd-with-promptfoo-5242b4dcb9be) — accessed 2026-08-01
- [What is LangSmith? 2026 Guide to LLM Observability — MetaCTO](https://www.metacto.com/blogs/what-is-langsmith-a-comprehensive-guide-to-llm-observability) — accessed 2026-08-01
- [Evaluation concepts — LangChain docs](https://docs.langchain.com/langsmith/evaluation-concepts) — accessed 2026-08-01
- [List of available metrics — Ragas docs](https://docs.ragas.io/en/stable/concepts/metrics/available_metrics/) — accessed 2026-08-01
- [The Coin Flip Judge? Reliability and Bias in LLM-as-a-Judge Evaluation (arXiv:2606.13685)](https://arxiv.org/pdf/2606.13685) — accessed 2026-08-01
- [RAG Evaluation Metrics in 2026: Faithfulness & More — FutureAGI](https://futureagi.com/blog/rag-evaluation-metrics-2025/) — accessed 2026-08-01

## Changelog
- 2026-08-01 — created
