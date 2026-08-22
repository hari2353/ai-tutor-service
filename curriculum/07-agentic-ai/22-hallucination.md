# Hallucination: Taxonomy, Detection, and What Actually Reduces It

> **Track:** T07 Agentic AI · **Time:** 2.5h · **Prereqs:** `T07-attribution`, `T07-trust-calibration` · **Updated:** 2026-07-26
> **Module id:** `T07-hallucination` · **Tags:** trust, critical

## The 30-second version

Split it before you discuss it: **faithfulness** failures (output contradicts or is unverifiable from the *provided source*) are testable with the source in hand and are where 90% of your engineering effort goes; **factuality** failures (output contradicts the *world*) need an external knowledge source and are much harder. Cross that with **intrinsic** (contradicts the source) versus **extrinsic** (source is silent), and you have the four cells that make the conversation precise. Hallucination is a **structural consequence of the objective, not a bug**: next-token prediction has no truth term and no null token, so a model must emit *something*; Kalai & Vempala (STOC 2024) proved a calibrated model must hallucinate arbitrary facts at a rate bounded below by the **monofact rate** — the fraction of facts appearing exactly once in training — minus miscalibration, independently of architecture or data quality; and post-training makes it worse because binary accuracy scoring pays positive expected value for a guess and zero for "I don't know". Detection is real but unsolved: self-consistency and semantic entropy top out around **0.53-0.67 AUC-PR / ~0.6 AUROC** on hard benchmarks and are structurally blind to confident consistent falsehood, while grounding checks against a source catch far more (Bedrock contextual grounding filters over 75% of hallucinated RAG responses). The honest mitigation ranking is **grounding in retrieval > constrained decoding and structured output > verification passes > abstention > decomposition and tools**, and the things that do not work are the two things everyone tries first: instructing the model to be accurate (clinical study: 65.9% → 44.2%, still 44%) and setting temperature to 0 (66.5%, statistically indistinguishable from default).

## Why this gets asked

Because an executive has asked the interviewer "when will you fix the hallucinations?" and they need engineers who will neither promise zero nor shrug. The specific incident behind the question is usually one of three: a summary that confidently contradicted the document it summarised, a support answer that invented a policy clause, or a model upgrade that improved every benchmark and *increased* fabrication — which really happens, and OpenAI's own o3/o4-mini system card is the citable case, with PersonQA hallucination going from **16% for o1 to 33% for o3 and 48% for o4-mini**. The probe is whether you treat this as an engineering problem with a measurable error budget or as a moral failing of the model. At staff level they will push on the ranking: which interventions actually move the number, in what order, at what cost, and which ones are cargo cult. Anyone who leads with "prompt engineering" or "temperature 0" has not measured anything.

---

## Lineage: past → present → future

**What came before.** The word arrived from image captioning and neural machine translation around 2018, describing content in the output with no basis in the input. The taxonomy that still governs the field came from summarisation: **Maynez et al. (ACL 2020)** on faithfulness in abstractive summarisation separated **intrinsic** hallucination (the summary contradicts the article) from **extrinsic** (the summary adds content the article does not support), and the pain that made it urgent was brutally concrete — ROUGE could not detect either, so a model could win on the leaderboard while producing summaries that said the opposite of the source. **Ji et al. (2023, *Survey of Hallucination in Natural Language Generation*)** consolidated intrinsic/extrinsic across tasks, and **Huang et al. (2023, *A Survey on Hallucination in LLMs*)** added the orthogonal split that matters more for LLMs: **factuality** hallucination (factual inconsistency and factual fabrication, measured against reliable resources) versus **faithfulness** hallucination (instruction inconsistency, context inconsistency, logical inconsistency).

Then the theory arrived and changed the conversation from "fix it" to "bound it". **Kalai & Vempala, *Calibrated Language Models Must Hallucinate* (STOC 2024, arXiv:2311.14648)** proved a statistical lower bound: for arbitrary facts whose veracity cannot be determined systematically from training data, a *calibrated* model must produce falsehoods at a rate related to the **monofact rate** (the fraction of facts appearing exactly once in the corpus, connected to the Good-Turing missing-mass estimator) minus its miscalibration. Nothing about transformers, nothing about data quality. **Xu et al. (2024, *Hallucination is Inevitable*)** made a complementary computability argument. **Kalai, Nachum, Vempala & Zhang (2025, arXiv:2509.04664, *Why Language Models Hallucinate*)**, with the follow-on *Nature* paper *Evaluating large language models for accuracy incentivizes hallucinations* (2026), added the socio-technical half: pretraining pressure toward calibration produces the lower bound, and post-training evaluation pressure removes the incentive to abstain, because a good hallucination benchmark cannot outvote hundreds of accuracy benchmarks that award zero for "I don't know". The 2026 PNAS empirical investigation (arXiv:2502.08666) tested the monofact prediction directly and found it holds.

**Where it stands now.** Four points of consensus. (1) **It is structural**, and the serious question is the error budget, not elimination. (2) **Faithfulness is tractable and factuality is not** — with the source in context, small NLI checkers do well; without one, you are fact-checking the world. (3) **Detection is unsolved in the general case**: no published detector holds high AUROC across domains, and the consistency family is structurally blind to confident consistent error. (4) **Benchmark numbers must be quoted with the task attached** — Vectara HHEM summarisation puts 2026 frontier models at roughly **1.0-2.5%** (down from 3-8% in 2023) on a 7,700+ article set, while the harder FACTS Benchmark Suite has **no model above 70% overall, Gemini 3 Pro leading at 68.8%**, and AA-Omniscience (arXiv:2511.13029; 6,000 questions across six domains, correct answers rewarded, hallucinations penalised, refusals free, index scaled −100 to +100) reports **most frontier models below zero**, i.e. answering wrong more than right on hard knowledge, with the July 2026 leader at index 40. Quoting "1% hallucination" as your production expectation because you read the HHEM leaderboard is the single most common mistake in this area.

The live disagreements. First, **whether "hallucination" is a useful term at all**: HalluLens (arXiv:2504.17550) argues the field conflates extrinsic hallucination, intrinsic hallucination, and general factual error, and that lumping them produces incomparable benchmarks; a growing camp wants the word retired in favour of the specific failure. Second, **whether reasoning training helps or hurts**: reasoning models are more faithful in CoT terms and *more* prone to fabrication on entity-recall benchmarks (o3 at 33% versus o1 at 16% on PersonQA, with OpenAI writing that "more research is needed"), and AbstentionBench found reasoning fine-tuning degrades abstention. Third, **whether scale fixes it**: the AA-Omniscience result that knowledge and hallucination-avoidance are partially decoupled — models can get more knowledgeable and no more reliable — cuts against the scaling answer. Fourth, **detection-as-gate versus detection-as-router**: with detectors at ~0.6 AUROC on hard sets, using one as a hard filter costs you a lot of correct answers, so several teams now use it only to route to verification or a human.

**Where it's heading.** High confidence: **abstention-aware scoring spreads**, because AA-Omniscience-style indices where refusal is free and error is penalised directly implement the Kalai et al. prescription, and the labs proposing it own the leaderboards. High confidence: **grounding becomes the default architecture** for anything factual, with closed-book generation treated the way unparameterised SQL is treated now. Medium confidence: **formal and symbolic verification expands in narrow domains** — Bedrock Automated Reasoning checks (GA August 2025, up to 99% verification accuracy on formalised policy) show the shape, and the bottleneck is the formalisation labour, not the technique. Medium confidence: **span-level detectors replace response-level scores**, because "which sentence" is actionable and "0.31" is not. Speculative, flag it: architectures with an explicit non-parametric factual pathway so facts are never stored lossily in weights, and training objectives with a truth term. Interesting, not shippable.

---

## Mental model

The 2×2 that makes the conversation precise, plus the mechanism.

```
                      ┌──────────────────────────────┬──────────────────────────────┐
                      │  INTRINSIC                   │  EXTRINSIC                   │
                      │  contradicts the source      │  source is SILENT on it      │
  ┌───────────────────┼──────────────────────────────┼──────────────────────────────┤
  │ FAITHFULNESS      │ "policy says 30 days" when   │ "processing takes 2 days"     │
  │ vs the PROVIDED   │ the doc says 14              │ — plausible, doc never says it│
  │ source/instruction│                              │                              │
  │  ✅ TESTABLE with │ detect: NLI CONTRADICTION    │ detect: NLI NEUTRAL           │
  │     the source    │ action: DROP the sentence    │ action: flag / abstain        │
  ├───────────────────┼──────────────────────────────┼──────────────────────────────┤
  │ FACTUALITY        │ contradicts the world AND    │ world-fact the source doesn't │
  │ vs the WORLD      │ a retrievable source         │ cover at all                 │
  │  ⚠ needs an       │ detect: retrieval + NLI      │ detect: search / KB / expert  │
  │    external KB    │ action: correct or abstain    │ action: abstain or mark       │
  └───────────────────┴──────────────────────────────┴──────────────────────────────┘

  ENGINEERING TRUTH: you can build a good faithfulness gate this quarter.
  A factuality gate is a fact-checking product, and you probably should not build it.
```

```
WHY NEXT-TOKEN PREDICTION PRODUCES THIS (three independent reasons)

 1. NO NULL TOKEN. Decoding must emit a distribution over the vocabulary at every
    step. "I don't know" is a SEQUENCE the model must have learned to prefer; it is
    not an architectural escape hatch. Compare a database: NULL is a value.

 2. LOSSY FACT STORAGE → PLAUSIBLE NEIGHBOURS. Facts live smeared across weights.
    Approximate recall returns something in the right REGION of representation
    space: right shape, wrong value. That is why hallucinations are always
    plausible — "Lyon" not "banana", "§4.2" not "§Q9", "2019" not "17 trillion".

 3. CALIBRATION FORCES IT (Kalai & Vempala, STOC 2024). If ~20% of the facts in
    your corpus appear EXACTLY ONCE, a calibrated model must put mass on
    plausible-but-false completions of that kind at a rate on that order.
    Being well-calibrated and never wrong are in tension, provably.

 + POST-TRAINING MAKES IT WORSE, not better:
      score(guess) = p(correct) > 0        score("I don't know") = 0
   Any process optimising binary accuracy selects FOR guessing. RLHF also degrades
   calibration, so the guess arrives sounding certain.
```

The one-liner for interviews: **hallucination is not the model lying, it is the model interpolating in a space where it has no data and no way to say so.** Everything downstream follows from that: you either give it data (grounding), take away the ability to say the wrong thing (constraints), check what it said (verification), or let it stop (abstention).

---

## How it actually works

### The taxonomy, operationally

| Cell | Definition | Detector | Action |
|---|---|---|---|
| Intrinsic faithfulness | Output contradicts provided context | NLI **contradiction** vs cited chunk, high threshold | Drop the sentence; log a corpus conflict |
| Extrinsic faithfulness | Output not entailed by any provided context | NLI **neutral** (no entailment above τ) | Flag as unsupported, or abstain |
| Intrinsic factuality | Contradicts a retrievable authority | Retrieve then NLI | Correct or abstain |
| Extrinsic factuality | Unverifiable world claim | Search / KB / human | Mark unverified; usually out of scope |

Huang et al.'s faithfulness subtypes are worth naming because they catch failures teams miss: **instruction inconsistency** (answered a different question than asked — very common, rarely measured), **context inconsistency** (contradicts provided context), **logical inconsistency** (the reasoning steps do not support the conclusion, e.g. correct intermediate arithmetic with a wrong final sum). Only the middle one is caught by a grounding check. Instruction inconsistency needs an instruction-following eval, and logical inconsistency needs step-level checking.

**Fluency is a red herring and a trap.** The reason hallucinations pass review is that reason 2 above guarantees they are drawn from the plausible neighbourhood. A fabricated section number looks like a section number. This is why "it read fine to me" is not a QA process, and why human review without the source open is worthless.

### Numbers, with the task attached

Keep these straight; interviewers use them to test whether you understand benchmarks or just collect them.

| Setting | Rate | What it means |
|---|---|---|
| Vectara HHEM summarisation, 2026 frontier | **~1.0-2.5%** (was 3-8% in 2023) | Easiest possible grounding: short source in context, summarise. **Not your production number** |
| FACTS Benchmark Suite (Grounding v2 + parametric + search + multimodal) | **no model >70%; leader 68.8%** | Longer docs, harder reasoning. The honest picture |
| AA-Omniscience index (6k questions, 6 domains, refusal free, error penalised) | **most frontier models < 0** | On hard knowledge they answer wrong more than right |
| PersonQA (OpenAI system card, Apr 2025) | o1 **16%** → o3 **33%** → o4-mini **48%** | Newer and smarter is not automatically less fabricating |
| Commercial legal RAG (Stanford RegLab) | **17-33%** vs GPT-4 **43%** | RAG reduces; does not eliminate |
| Deep research agents, citation fact-check | **24-77%**, degrading 79%→17% from 2 to 150 tool calls | More search made attribution worse |
| Clinical vignettes with one incorrect detail injected | **50-82%** | Adversarial premises are the worst case |

The takeaway to state out loud: **hallucination rate is a property of (model, task, source availability, adversariality), and a single number without those four is meaningless.**

### Detection methods and their actual effectiveness

**1. Self-consistency sampling (SelfCheckGPT).** Generate one main answer at low temperature, then n stochastic samples (the original work used n=20), and score each sentence by agreement with the samples using BERTScore, an NLI contradiction probability, n-gram likelihood, or a prompted judge. Reported best-variant **AUC-PR in the ~0.53-0.67 range** on the original benchmark; on harder 2026 sets the best combination has been reported near **0.58 AUROC**. Cost: n extra generations, so 5-20x tokens. Verdict: real signal, weak detector, expensive.

**2. Semantic entropy** (Farquhar et al., *Nature* 630:625-630, 2024). Cluster n samples into meaning classes by bidirectional entailment, take entropy over classes. Strictly better than surface-form entropy because it stops counting paraphrases as disagreement. Reported near **0.60 AUROC** on hard 2026 benchmarks, much stronger on the confabulation-heavy sets it targets. Cost: n generations plus O(n²) NLI, reducible to O(n·|C|). Semantic entropy probes (arXiv:2406.15927) approximate it from hidden states in one forward pass. See `T07-trust-calibration` for the mechanics.

**3. NLI / grounding verification.** With a source in context this is the strongest practical detector: MiniCheck-FT5 (~770M) matches Claude 3 Opus on LLM-AggreFact, AlignScore-large is 355M, HHEM-2.1-open is smaller and beats several larger models, and LettuceDetect flags unsupported *spans*. Managed: Bedrock Guardrails contextual grounding **filters over 75% of hallucinated responses** on RAG and summarisation. Cost: tens of milliseconds batched. Verdict: **the best effectiveness-per-dollar in the whole list**, and the only one that catches consistent falsehood, but it requires a source, so it detects faithfulness failures and not factuality ones.

**4. Retrieval verification (post-hoc fact check).** Take each atomic claim, retrieve independently, check entailment against what you retrieve rather than what was in context. This is the only method that addresses *factuality*, and it is expensive: one or more retrievals plus one entailment check per claim, so a 15-claim answer is 15+ retrievals. High precision on checkable facts (dates, numbers, named entities, quotes), useless on unverifiable or subjective content. Verdict: reserve for high-stakes and offline eval.

**5. Internal-state probes.** Linear probes on hidden states, semantic-entropy probes, and 2026 work using attention-sink statistics as a hallucination signal (arXiv:2604.10697). One forward pass, essentially free at inference. Requires white-box access and, critically, **the probe is fit to a distribution** — transfer to your traffic is an empirical question, not a given. Verdict: best cost profile, unproven generality, needs your own labelled set.

**6. LLM-as-judge.** Most accurate on genuinely hard entailment; 10-100x the cost; and if the judge shares a family with the generator, errors are correlated and it under-detects exactly the cases you care about. Verdict: adjudicate the band near your threshold, not every response.

**The honest summary you should give:** no single detector is production-sufficient. What works is a **cheap ensemble used as a router, not a filter** — grounding check plus one or two cheap signals feeding a small calibrated classifier, whose output decides whether to answer, flag, verify harder, or escalate. Using a ~0.6-AUROC detector as a hard gate throws away a large number of correct answers for a modest reduction in errors, and the risk-coverage curve from `T07-trust-calibration` is how you prove that to a PM.

### What actually reduces it, ranked

**1. Grounding in retrieval — the biggest single win.** Moves the task from recall-from-weights to read-from-context, and the theoretical lower bound on arbitrary-fact hallucination stops applying because the fact is no longer arbitrary. Measured: legal RAG products at 17-33% versus 43% closed-book GPT-4. Necessary conditions people skip: retrieval recall has to be good (you cannot ground on a document you did not retrieve, so this converts into a retrieval problem — `T06-hybrid-search`), the corpus must not be internally contradictory or stale, and the prompt must instruct the model to prefer context over prior knowledge. Failure mode to know by name: **RAG-induced distraction**, where irrelevant retrieved chunks make output worse than no retrieval, which is why a relevance filter on retrieved chunks is part of grounding and not an optional extra.

**2. Constrained decoding and structured output.** Eliminates whole classes rather than reducing a rate. A JSON schema with enums makes an out-of-vocabulary category impossible; a citation grammar over the in-context id set makes a fabricated document id impossible; a regex-constrained field makes a malformed identifier impossible. This is the highest-certainty intervention available because it is a *structural* impossibility rather than a probabilistic improvement, and it is nearly free. It does not touch free-text factual claims, which is why it is second, not first. See `T07-structured-output`.

**3. Verification passes.** A grounding gate that drops contradicted sentences, flags unsupported ones, and can trigger abstention. This is where Bedrock's >75% figure lands, and where a small NLI checker earns its keep at tens of milliseconds. Cost: latency in the response path, plus the product decision about what to do with a failed sentence. Regeneration after a failed check helps but must be bounded — two attempts, then abstain, or you have built an unbounded loop with a token bill.

**4. Abstention.** Converts a wrong answer into a non-answer. It does not make the model more accurate; it makes the *system* less wrong at the cost of coverage, and the accounting only works when the alternative to answering is better than a guess (a clarifying question, a stronger model, a human, a documentation link). Requires the calibrated signal from `T07-trust-calibration`. Note the honest caveat: AbstentionBench found scaling does not improve abstention and reasoning fine-tuning degrades it, so this is something you build in the harness rather than something you get from the model.

**5. Decomposition and tool use for what tools do better.** Do not ask the model to do arithmetic, date maths, unit conversion, ID lookup, or aggregation — those are hallucination-dense operations with exact-answer tools available. Route them out. This is the most under-rated intervention on the list because it removes error categories completely rather than reducing them, and it is usually a day of work.

**6. Fine-tuning on abstention and refusal data.** Verifiable-reward approaches (`Abstain-R1`-style, 2026) and process supervision on confidence margins report real gains, including ECE reductions up to 88% in the confidence literature. Risks: over-refusal, which is its own product failure and shows up as users routing around your product; and distribution specificity, since a refusal-tuned model refuses in *your* training distribution's shape.

**7. Decoding-time interventions.** Context-aware decoding (CAD, arXiv:2305.14739) contrasts logits with and without context to force the model to trust the context, reporting **≈14.3% factuality gain for LLaMA on summarisation** and being especially effective in knowledge-conflict cases; DoLa contrasts early and late layer logits; ITI shifts activations along truthfulness directions. All require white-box access or provider support, deliver modest single-digit-to-low-double-digit gains, and are unavailable behind most APIs. Real, but seventh.

**8. Prompting.** Last, and this is the point of the section.

### What does not work

- **"Be accurate." "Do not hallucinate." "Only use the provided context."** These help a little and nowhere near enough. The clinical adversarial study is the cleanest number: hallucination rate **65.9% under the default prompt, 44.2% with a mitigation prompt** — a real 22-point improvement, and still 44%. Anyone who calls that solved has not read the number. Prompting cannot create knowledge the model lacks or install a null token.
- **Temperature 0 alone.** Same study: **66.5% at zero temperature versus 65.9% default — no significant change**. Broader work finds temperature in 0.0-1.0 has no statistically significant effect on problem-solving accuracy. Greedy decoding makes output *reproducible*, which is valuable for debugging and evals; it does not make it *true*. The intuition "randomness causes hallucination" is wrong: the model's mode is frequently the plausible falsehood.
- **A bigger or newer model.** o1 16% → o3 33% → o4-mini 48% on PersonQA. AA-Omniscience shows knowledge and reliability are partially decoupled. Capability upgrades must be re-evaluated on your hallucination suite, not assumed.
- **More context.** Context rot (`T07-context-engineering`) plus the deep-research finding that fact-check accuracy fell 79% → 17% as tool calls went 2 → 150. Stuffing 100 sources into synthesis makes attribution worse, not better.
- **Self-verification by the same model.** Correlated errors. It catches sloppiness, not belief.
- **RLHF as a fix.** It degrades calibration, so it makes the guess sound *more* certain.
- **A single detector as a hard gate.** At ~0.6 AUROC on hard distributions you lose a lot of correct answers per error prevented. Route, don't filter.

---

## Build it from scratch

A detection ensemble that returns a *routing decision*, not a score. Grounding check plus semantic clustering plus a cheap surface signal, combined by a calibrated linear model, with the threshold fit to a risk target.

```python
"""Hallucination router. python 3.11+, stdlib + numpy.
Injectable model callables so it runs with stubs.
    python router.py
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Callable
import math, re
import numpy as np

Generate = Callable[[str, float], str]                    # (prompt, temperature) -> text
Nli = Callable[[list[tuple[str, str]]], list[float]]      # [(premise, hyp)] -> P(entail)

SENT = re.compile(r'(?<=[.!?])\s+(?=[A-Z0-9"\(])')
NUMERIC = re.compile(r"\b\d[\d,\.]*\b|\b(?:19|20)\d{2}\b|§\s?[\d\.]+")


@dataclass
class Signals:
    grounding_min: float = 1.0      # weakest sentence's entailment vs context
    grounding_mean: float = 1.0
    unsupported_frac: float = 0.0
    semantic_clusters: int = 1      # from n samples; >1 means self-disagreement
    semantic_entropy: float = 0.0
    numeric_density: float = 0.0    # numbers/dates/§refs per sentence — error-dense content
    answer_sentences: int = 0
    tool_error: bool = False

    def vector(self) -> np.ndarray:
        return np.array([self.grounding_min, self.grounding_mean, self.unsupported_frac,
                         self.semantic_entropy, self.numeric_density,
                         math.log1p(self.answer_sentences), float(self.tool_error)])


@dataclass
class Decision:
    action: str                     # answer | answer_flagged | verify_harder | abstain
    p_hallucination: float = 0.0
    unsupported: list[str] = field(default_factory=list)
    contradicted: list[str] = field(default_factory=list)
    reason: str = ""


def sentences(text: str) -> list[str]:
    return [s.strip() for s in SENT.split(text) if s.strip()]


def grounding_signals(answer: str, context: list[str], nli: Nli,
                      tau: float = 0.6, contra: Nli | None = None) -> tuple[Signals, list, list]:
    """Faithfulness check: does the PROVIDED context entail each sentence?
    Split long premises into 3-sentence windows and max-pool — NLI models are
    trained on short premises and drift to neutral on 1500-token chunks."""
    sents = sentences(answer)
    if not sents:
        return Signals(), [], []
    windows: list[str] = []
    for c in context:
        cs = sentences(c) or [c]
        windows += [" ".join(cs[i:i + 3]) for i in range(max(1, len(cs) - 2))]
    scores, unsupported, contradicted = [], [], []
    for s in sents:
        best = max(nli([(w, s) for w in windows])) if windows else 0.0
        scores.append(best)
        if best < tau:
            if contra is not None and max(contra([(w, s) for w in windows])) > 0.7:
                contradicted.append(s)
            else:
                unsupported.append(s)
    nd = sum(len(NUMERIC.findall(s)) for s in sents) / len(sents)
    sig = Signals(grounding_min=min(scores), grounding_mean=float(np.mean(scores)),
                  unsupported_frac=(len(unsupported) + len(contradicted)) / len(sents),
                  numeric_density=nd, answer_sentences=len(sents))
    return sig, unsupported, contradicted


def semantic_signals(prompt: str, generate: Generate, nli: Nli, n: int = 5) -> tuple[int, float]:
    """Semantic entropy, cheap variant. Bidirectional entailment clustering, but only
    against ONE representative per existing cluster -> O(n·|C|) not O(n²)."""
    samples = [generate(prompt, 1.0) for _ in range(n)]
    reps: list[str] = []
    counts: list[int] = []
    for s in samples:
        placed = False
        for i, r in enumerate(reps):
            fwd, bwd = nli([(r, s), (s, r)])
            if fwd > 0.5 and bwd > 0.5:              # bidirectional == same meaning
                counts[i] += 1
                placed = True
                break
        if not placed:
            reps.append(s)
            counts.append(1)
    p = np.array(counts) / sum(counts)
    return len(reps), float(-(p * np.log(p)).sum())


class Router:
    """Calibrated combiner. Fit on a few hundred labelled production examples;
    a logistic regression over cheap features beats any single signal and costs
    nothing at inference. Thresholds are VERSIONED artefacts, refit per model."""

    def __init__(self, w: np.ndarray, b: float,
                 tau_answer: float = 0.15, tau_verify: float = 0.45):
        self.w, self.b = w, b
        self.tau_answer, self.tau_verify = tau_answer, tau_verify

    def p(self, sig: Signals) -> float:
        z = float(self.w @ sig.vector() + self.b)
        return 1.0 / (1.0 + math.exp(-z))

    def decide(self, sig: Signals, unsupported: list[str], contradicted: list[str]) -> Decision:
        ph = self.p(sig)
        if contradicted:
            return Decision("abstain", ph, unsupported, contradicted,
                            "context contradiction: source conflict or intrinsic hallucination")
        if ph <= self.tau_answer:
            return Decision("answer", ph, unsupported, contradicted, "grounded")
        if ph <= self.tau_verify:
            return Decision("answer_flagged", ph, unsupported, contradicted,
                            f"{len(unsupported)} unsupported sentence(s)")
        return Decision("verify_harder", ph, unsupported, contradicted,
                        "route to independent retrieval verification or human")

    @staticmethod
    def fit_threshold(scores: np.ndarray, is_hallucination: np.ndarray,
                      target_risk: float = 0.02, min_answered: int = 200) -> dict:
        """Risk-coverage: the deliverable is (threshold, coverage), not a score."""
        order = np.argsort(scores)                      # low p(hallucination) first
        bad = is_hallucination[order].astype(float)
        k = np.arange(1, len(bad) + 1)
        risk = np.cumsum(bad) / k
        ok = (risk <= target_risk) & (k >= min_answered)
        if not ok.any():
            return {"feasible": False}
        i = int(np.max(np.flatnonzero(ok)))
        return {"feasible": True, "threshold": float(scores[order][i]),
                "coverage": round(float(k[i] / len(bad)), 3), "risk": round(float(risk[i]), 4)}


if __name__ == "__main__":
    context = [
        "Refund policy v2.1. Scope: all plans. Refunds are available within 30 days "
        "of the invoice date. Annual plans are pro-rated.",
        "Invoice INV-8841. Issued 2026-07-11. Plan: monthly. Amount 49.00 USD.",
    ]
    answer = ("Refunds are available within 30 days of the invoice date. "
              "Invoice INV-8841 was issued on 2026-07-11. "
              "Processing takes two business days and a 3 USD fee applies.")

    def stub_nli(pairs):                 # lexical overlap stand-in for MiniCheck/HHEM
        tok = lambda t: set(re.findall(r"[a-z0-9\.]+", t.lower()))
        return [len(tok(h) & tok(p)) / max(1, len(tok(h))) for p, h in pairs]

    sig, unsup, contra = grounding_signals(answer, context, stub_nli, tau=0.75)
    print("signals:", sig)
    print("unsupported:", unsup)

    # weights would come from logistic regression on labelled data; illustrative here
    w = np.array([-3.0, -1.5, 4.0, 1.2, 0.35, 0.1, 2.0])
    router = Router(w, b=1.0)
    print("\ndecision:", router.decide(sig, unsup, contra))

    rng = np.random.default_rng(1)
    s = np.clip(rng.beta(2, 6, 3000), 0, 1)
    y = (rng.random(3000) < s).astype(int)
    print("\nthreshold fit:", Router.fit_threshold(s, y, target_risk=0.10))
```

Two design decisions to defend: the router returns an **action**, so a weak detector degrades into "verify harder" rather than into a wrong filter decision; and **contradiction is handled separately from low confidence**, because a contradicted sentence is a different bug (source conflict or intrinsic hallucination) with a different fix (drop it and investigate the corpus) than an unsupported one.

Running it, the third sentence ("processing takes two business days and a 3 USD fee applies") is unsupported by anything in context, `unsupported_frac` goes to 2/3, and the router returns `verify_harder` rather than silently suppressing the answer. The `fit_threshold` call is the piece to point at in an interview: on the synthetic signal it returns a threshold with **~26% coverage at 10% risk**, and at a 5% risk target it returns `{"feasible": False}` — which is the correct and useful answer, because a signal that cannot meet the target should say so rather than hand you a threshold that quietly misses the SLO.

Lab **`(lab pending)`** wires in MiniCheck batched on GPU, real semantic entropy, an independent-retrieval verifier for atomic claims, and a CI gate that fails the build if unsupported-sentence rate regresses on the golden set.

---

## How it's done in production

**The stack, in order, and what each layer buys.**

```
 1  RETRIEVE + relevance-filter chunks      ← biggest single win; also the ceiling
 2  CONSTRAIN the output shape (schema, enums, citation-id grammar)   ← eliminates classes
 3  GENERATE with an explicit "prefer context; say you don't know" instruction  ← small
 4  VERIFY per sentence (NLI grounding gate; drop contradictions)     ← >75% filtered
 5  ROUTE on the ensemble signal: answer / flag / verify harder / abstain
 6  BOUNDED REGENERATION (max 2) then abstain                        ← never unbounded
 7  LOG everything with versions; sample for human audit             ← this is your labels
```

**Managed pieces worth knowing by name.** Bedrock Guardrails contextual grounding (grounding and relevance scores with tunable thresholds, >75% of hallucinated RAG/summarisation responses filtered) and Automated Reasoning checks (GA August 2025, up to 99% verification accuracy where a policy has been formalised into logic, with natural-language test Q&A generation added in November 2025). Vertex AI grounding with support scores. Azure AI Content Safety groundedness detection. All of them operate at response or coarse-span granularity, so if your UI shows sentence-level claims you still need your own pass.

**Evals as the actual control.** The thing that keeps hallucination bounded over time is not a runtime check, it is a regression gate: a golden set of 200-500 real cases (including the adversarial ones — false premises, underspecified questions, questions whose answer is genuinely absent from the corpus), scored on unsupported-sentence rate, citation recall, abstention correctness, and instruction-following, run in CI on every prompt and model change, failing the build on regression. Without that, every improvement you ship gets eroded by the next prompt tweak.

**Watch for the eval trap** that Kalai et al. name: if your internal leaderboard scores binary accuracy, your team will optimise toward guessing, exactly like the industry did. Score it AA-Omniscience style — reward correct, penalise wrong, treat abstention as neutral — or your metrics will fight your goals.

### What breaks at scale

| Symptom | Cause | Fix |
|---|---|---|
| Summaries confidently state the opposite of the document | Intrinsic hallucination; no contradiction check | NLI in contradiction direction; drop sentence; alert on rate |
| Answer invents a plausible section number or clause | Lossy parametric recall filling a gap; grounding not enforced | Grounded generation + citation-id constraint + verbatim quote check |
| Hallucination rate rose after a model upgrade | Newer/reasoning models can fabricate more (o1 16% → o3 33% → o4-mini 48% on PersonQA) | Gate upgrades on your own hallucination suite; pin versions |
| Adding more retrieved documents made answers worse | RAG-induced distraction / attention dilution; fact-check falls with search depth | Relevance-filter chunks; cap sources per section; verify per section |
| Detector flags 30% of answers, most are fine | Detector used as a hard gate at ~0.6 AUROC | Route instead of filter; fit the threshold to a risk target and report coverage |
| Users complain the assistant refuses constantly | Over-refusal from refusal fine-tuning or too tight a threshold | Measure refusal rate as an SLO; add clarifying-question tier before decline |
| Regeneration loop burns tokens on a hard query | Unbounded "verify then retry" | Cap at 2 attempts then abstain; count attempts in the budget |
| Arithmetic in the answer is wrong but the reasoning looks right | Logical-inconsistency hallucination; no tool for the computation | Route arithmetic/date/aggregation to tools; verify the tool result, not the prose |
| Eval score improves while user complaints rise | Binary-accuracy internal leaderboard rewarding guessing | Score with abstention-aware metrics; add adversarial cases to the golden set |
| One customer's corpus produces 5x the hallucination rate | Corpus is contradictory or contains superseded documents | Supersession metadata, contradiction sweep, per-tenant hallucination dashboard |

---

## Tradeoffs & when NOT to use it

- **Do not promise zero.** It is provably not available: a calibrated model must hallucinate arbitrary facts at a rate bounded below by the monofact rate minus miscalibration. Promise an error budget with a measurement method. Interviewers specifically listen for whether you will over-promise.
- **Detection is not free and it is not accurate enough to gate on alone.** At ~0.6 AUROC on hard distributions, a hard filter trades many correct answers for a modest error reduction. Show the risk-coverage curve before shipping a gate.
- **Do not build a factuality checker.** Faithfulness (against a source you control) is an engineering task. Factuality (against the world) is a fact-checking product with its own corpus, freshness, and dispute-resolution problems. Scope to faithfulness and mark unverifiable world claims as unverified.
- **Grounding has a coverage cost and moves the problem.** It converts hallucination into a retrieval-recall problem plus an abstention rate. If your corpus does not contain the answer, a grounded system correctly says so, and a stakeholder will call that a regression. Have the coverage number ready.
- **Over-refusal is a real failure mode.** A model tuned to abstain aggressively becomes a product users route around, which is worse than a flagged wrong answer in low-stakes contexts. Track refusal rate with the same seriousness as error rate.
- **Some tasks want it.** Brainstorming, fiction, naming, hypothesis generation, synthetic data, adversarial test-case generation — here "generating plausible content not present in the source" is the product, and there is published work on hallucination being *useful* in drug-discovery ideation. Applying a grounding gate to a brainstorming feature makes it worse. Know which of your surfaces are which.
- **Verification in the hot path costs p95.** Sentence-level NLI batched is tens of milliseconds; unbatched over HTTP it is hundreds. If the budget will not take it, verify asynchronously and accept that retraction is a worse UX than latency, or restrict verification to the high-stakes tier.
- **Do not spend the quarter on decoding-time interventions.** CAD, DoLa, and ITI are real and modest (CAD around 14.3% factuality gain on summarisation for LLaMA), need white-box access, and sit below grounding, constraints, verification, abstention, and tool routing on the priority list. If you are on an API you cannot use them at all.
- **Do not let hallucination work displace the boring fix.** Most production "hallucination" tickets I would expect to resolve as retrieval failures, chunking failures, stale corpus content, or a question the corpus genuinely does not answer. Diagnose before you mitigate.

---

## Interview questions

### Q1 — Define hallucination. Give me a taxonomy you can test against.
**Testing:** whether you have a usable framework or a vibe.
**Answer:** Two orthogonal axes. **Faithfulness versus factuality**: faithfulness is consistency with the provided source and instruction, factuality is consistency with the world. **Intrinsic versus extrinsic**: intrinsic contradicts the source, extrinsic is content the source is silent on. That gives four cells with different detectors: intrinsic faithfulness is NLI contradiction against context, extrinsic faithfulness is NLI neutral (no entailment above threshold), intrinsic factuality needs retrieval plus NLI, extrinsic factuality needs search or a human. The engineering consequence is the important part: faithfulness is testable this quarter with the source in hand, factuality is a fact-checking product. Huang et al. also split faithfulness into instruction, context, and logical inconsistency, and only context inconsistency is caught by a grounding check — answering a different question than asked and reasoning that does not support its own conclusion need separate evals.
**Follow-up trap:** *"Which cell do most of your production tickets fall in?"* — extrinsic faithfulness: a plausible sentence the retrieved documents simply do not support. And most of those are not really generation failures, they are retrieval failures, stale corpus content, or questions the corpus does not answer, which is why diagnosis precedes mitigation.

### Q2 — Why is hallucination structural rather than a bug?
**Testing:** the core theoretical point.
**Answer:** Three independent reasons. First, the objective: next-token prediction maximises the likelihood of plausible continuations with no truth term, and there is no null token — decoding must emit a distribution at every step, so "I don't know" is a learned sequence, not an architectural escape hatch. Second, storage: facts live smeared across weights, so approximate recall returns something in the right region of representation space — right shape, wrong value — which is exactly why hallucinations are always plausible rather than absurd. Third, and this is the one that settles it, Kalai & Vempala proved at STOC 2024 that a *calibrated* model must produce falsehoods about arbitrary facts at a rate bounded below by the monofact rate, the fraction of facts appearing exactly once in training, minus miscalibration — nothing to do with transformers or data quality, and empirically validated in a 2026 PNAS study. Then post-training makes it worse rather than better: binary accuracy scoring gives positive expected value to a guess and zero to abstention, and RLHF degrades calibration so the guess arrives sounding certain.
**Follow-up trap:** *"If it's provably unavoidable, why bother?"* — because the bound is on *arbitrary facts recalled from weights*, and grounding removes the arbitrariness by putting the fact in context. The bound tells you which architecture to choose, not that the problem is hopeless. It also tells you to stop promising zero and start managing an error budget.

### Q3 — Rank interventions by measured effect. Be specific about what does not work.
**Testing:** the module's central question.
**Answer:** In order: (1) **grounding in retrieval**, the biggest single win — commercial legal RAG at 17-33% versus 43% for closed-book GPT-4 — with the caveat that it converts into a retrieval-recall problem and needs a relevance filter, since irrelevant chunks make things worse. (2) **Constrained decoding and structured output**, because it makes whole classes structurally impossible rather than less likely: schema enums, citation grammars over in-context ids, regex-constrained identifiers, at near-zero cost. (3) **Verification passes** with a small NLI checker, dropping contradictions and flagging unsupported sentences — Bedrock's contextual grounding filters over 75% of hallucinated RAG responses, and a 770M MiniCheck matches Claude 3 Opus at a fraction of the cost. (4) **Abstention**, which converts wrong answers into non-answers and only pays off when the fallback beats a guess. (5) **Decomposition and tool routing** for arithmetic, dates, lookups, aggregation — removes categories entirely, usually a day of work, chronically under-rated. (6) **Abstention fine-tuning**, real gains and an over-refusal risk. (7) **Decoding-time interventions** like CAD (~14.3% factuality gain on LLaMA summarisation), DoLa, ITI — modest and white-box only. (8) **Prompting**, last. What does not work: "be accurate" instructions took a clinical adversarial study from 65.9% to 44.2%, real but nowhere near sufficient; temperature 0 measured 66.5% against 65.9% default, statistically indistinguishable; a bigger model is not a fix, since PersonQA went 16% for o1 to 33% for o3 to 48% for o4-mini; more context makes it worse; and self-verification by the same model has correlated errors.
**Follow-up trap:** *"Why is temperature 0 useless here? It feels like it should help."* — because the failure is not sampling noise, it is that the model's *mode* is frequently the plausible falsehood. Greedy decoding picks the most likely token, and when the model has no knowledge the most likely token is the well-formed guess. Temperature 0 buys reproducibility, which genuinely matters for debugging and evals, and it buys no truth.

### Q4 — Which detection method would you actually deploy, and what does it miss?
**Testing:** operational judgment plus honesty.
**Answer:** A grounding check as the backbone — a small NLI model (MiniCheck-FT5, AlignScore-large, or HHEM-2.1-open) scoring each decontextualised sentence against 3-sentence windows of the retrieved context with max-pooling, batched into one forward pass, tens of milliseconds. Then two or three cheap extra features (min-token logprob, retrieval top-1 score and top1−top2 gap, numeric density since numbers and section references are error-dense) into a small calibrated classifier whose output selects an action. What it misses: anything about the *world* that the context does not cover, since it only checks faithfulness. And I would explicitly not put self-consistency or semantic entropy in the hot path — 5-20x tokens for AUC-PR around 0.53-0.67 and AUROC near 0.6 on hard sets — reserving them for the high-stakes tier or replacing them with a hidden-state probe.
**Follow-up trap:** *"Semantic entropy is in Nature. Why isn't it your default?"* — because its cost profile and its blind spot are both wrong for the default case. It costs n generations, and it is structurally silent when all samples agree on the same falsehood, which is the confidently-wrong case that hurts most. It is the best *unsupervised* signal when there is no source to check against; when there is a source, a grounding check is cheaper and catches the class entropy cannot.

### Q5 — Your model upgrade improves every benchmark and hallucination goes up. What happened, and what do you do?
**Testing:** whether you know this really occurs.
**Answer:** It really occurs and there is a citable case: OpenAI's o3/o4-mini system card reports PersonQA hallucination at 16% for o1, 33% for o3, and 48% for o4-mini, with the note that the newer models make more claims overall, producing both more accurate and more inaccurate ones, and that "more research is needed". AA-Omniscience shows the same decoupling — knowledge and reliability move partly independently, and most frontier models score below zero on an index that penalises errors and gives refusal a free pass. Operationally: gate the upgrade on my own hallucination suite rather than on public benchmarks, pin model versions so an alias bump cannot do this silently, re-fit every calibrated threshold since they are properties of the model, and re-check abstention behaviour specifically because reasoning fine-tuning has been found to degrade it.
**Follow-up trap:** *"You have to ship the upgrade for a capability the business needs. Now what?"* — ship it behind a stronger harness rather than blocking it: raise the grounding threshold, tighten abstention on the affected query classes, add the regressed cases to the golden set as a gate, and where the fabrication is concentrated in one class, route that class to the old model. Then quantify the residual risk and hand the decision to whoever owns it. The senior move is compensating in the harness, not vetoing.

### Q6 — A stakeholder read that hallucination is down to 1%. Respond.
**Testing:** benchmark literacy.
**Answer:** That number is almost certainly the Vectara HHEM summarisation leaderboard, where 2026 frontier models sit around 1.0-2.5%, down from 3-8% in 2023. It is a real number for the easiest possible grounding task: a short source document in context, summarise it, check the summary against the source. It is not a production number for anything else. On the harder FACTS Benchmark Suite no model breaks 70% overall, with the leader at 68.8%. On AA-Omniscience most frontier models score below zero. Commercial legal RAG products measured 17-33%. Clinical vignettes with one incorrect detail injected reached 50-82%. So the honest framing is: hallucination rate is a function of model, task, source availability, and adversariality, and a rate without those four attached is not information.
**Follow-up trap:** *"So what number do we tell the customer?"* — one we measured on our own golden set with our corpus, expressed as an unsupported-sentence rate on answered queries plus a coverage number, with the measurement method documented in the system card and re-measured per release. Anything else is quoting someone else's benchmark as our SLA.

### Q7 — Design the hallucination controls for a clinical documentation assistant.
**Testing:** high-stakes design with the right conservatism.
**Answer:** Scope it hard first: the assistant drafts and extracts, a clinician approves, and it never asserts an unsourced clinical claim. Then the stack. Retrieval restricted to the patient record and an approved formulary/guideline corpus with versioning, no open web. Structured output where every extracted element carries the source span and the quote, with a verbatim substring check on the quote at zero cost. Claim-level rather than sentence-level verification, because a sentence can carry two claims and only one may be supported, accepting 3-8x verification cost in this domain. Numbers, doses, dates, and units routed to tools and never generated, since that is where the error density is. Contradiction detection in both directions against the record, with any contradiction blocking rather than flagging. Aggressive abstention with a mandatory clinician gate on everything, and an explicit design for the adversarial case, because the clinical literature shows 50-82% hallucination when a vignette contains one incorrect detail — so the assistant must surface a false premise rather than build on it. Plus the oversight design from `T07-human-oversight`: the reviewer sees the source span next to every claim, unsupported items are visually distinct, and approval is per-claim rather than one blanket accept, because a single accept button on a full draft is a rubber stamp.
**Follow-up trap:** *"Clinicians say the flags slow them down and want them off."* — that is the automation-bias conversation, and the answer is measurement, not capitulation: run an error-injection study where a random half of drafts contain one corrupted claim and compare detection rates with flags on and off. If flags do not improve detection, they are decoration and I will remove them and find something that works. If they do, the data goes to whoever owns clinical risk and it is their call, documented. What I would not do is quietly disable a safety control because of a usability complaint.

### Q8 — What is the difference between using a detector as a gate and as a router?
**Testing:** whether you can handle an imperfect detector correctly.
**Answer:** A gate is a binary filter: below threshold, suppress. With a detector at roughly 0.6 AUROC on hard distributions that costs a large number of correct answers per error prevented, and the loss is invisible because suppressed correct answers do not generate complaints. A router uses the same score to choose among several actions — answer, answer with flags, escalate to a deeper verification (independent retrieval per claim, or a frontier judge), ask a clarifying question, hand to a human — so a weak signal degrades into "spend more compute" rather than into "withhold a correct answer". Practically it also lets you spend asymmetrically: cheap checks on 100% of traffic, expensive checks on the few percent in the uncertain band.
**Follow-up trap:** *"How do you prove the router is better than the gate?"* — the risk-coverage curve. Plot selective risk against coverage for both policies and show that at equal risk the router achieves higher coverage, and at equal coverage lower risk. Then include the cost axis, because the router spends more compute on the uncertain band, so the comparison is a three-way tradeoff among risk, coverage, and cost, and picking the operating point is a business decision, not an engineering one.

### Q9 — How does hallucination behave differently in an agent loop than in a single call?
**Testing:** transfer to his actual domain.
**Answer:** Worse, in three specific ways. **It compounds**: a hallucinated intermediate becomes the premise of the next step and the agent reasons confidently from a false fact, so the observable symptom is a trace where step 7 is internally coherent and grounded in step 3's fabrication. **Tool arguments are a high-value hallucination target**: a fabricated record id, path, or filter that happens to be well-formed will execute, and unlike prose there is no reader to catch it, which is exactly why write and destructive tools need a validation and approval gate rather than a text check. **Uncertainty is laundered at handoffs**: a subagent's summary reads as fact to the supervisor, so the supervisor's confident output rests on an unverified claim. Mitigations: verify observations before they enter the context (schema validation, existence checks on ids, cross-checks on numbers), require subagent returns to carry their own support state rather than prose, gate side-effecting tools on grounding rather than only on the model's intent, and checkpoint so a detected fabrication can be rolled back to a good state rather than restarting.
**Follow-up trap:** *"Where exactly do you put the check in the loop?"* — on the *observation* path, before the tool result enters context, and again on the *action* path, before any side-effecting call. Checking only the final answer is too late, because by then the fabrication has already been acted on. And keep the checks cheap and deterministic where possible — an id existence lookup is worth more than an NLI call on a tool result.

### Q10 — What are the risks of over-mitigating?
**Testing:** whether you see both failure directions.
**Answer:** Over-refusal, which is a product failure users respond to by routing around you, and it is harder to detect than errors because non-answers generate churn rather than complaints. Coverage collapse from too tight a grounding threshold, where the system correctly declines because the corpus lacks the answer and a stakeholder reads it as a regression. Latency and cost from verification everywhere including where the stake is trivial. Alert fatigue from flagging every sentence, which makes the flags wallpaper. And the subtle one: applying grounding gates to surfaces where generating novel plausible content *is* the product — brainstorming, naming, fiction, synthetic data, adversarial test generation — where the mitigation actively destroys value. The right frame is that hallucination controls are per-surface, sized by stake, not a global switch.
**Follow-up trap:** *"How do you measure over-refusal?"* — refusal rate as a first-class SLI split by query class, plus a labelled set of queries the system *should* answer (including ones that look risky but are fine) that acts as a false-refusal regression test, plus behavioural signals: users rephrasing the same question repeatedly, session abandonment after a refusal, and escalation volume where escalation was not warranted.

### Q11 — Your internal eval scores keep improving and user complaints keep rising. Diagnose.
**Testing:** whether you know the eval trap by name.
**Answer:** Most likely the eval rewards guessing. If the internal leaderboard scores binary accuracy, abstention scores zero and a guess has positive expected value, so every prompt and model change is selected for confident guessing — which is precisely the Kalai et al. argument about the industry's scoreboards, and it happens inside a single team just as easily. Second candidate: the golden set is drawn from happy-path traffic and contains no false premises, no underspecified questions, and no questions the corpus cannot answer, so it cannot see the failures users hit. Third: the metric is response-level rather than claim-level, so an answer with nine right claims and one fabricated one scores well. Fixes: score abstention-aware in the AA-Omniscience style, with correct rewarded, wrong penalised more heavily, and refusal neutral; add adversarial and unanswerable cases explicitly; move to claim-level scoring; and build the golden set from real production failures rather than from author imagination.
**Follow-up trap:** *"How heavily do you penalise a wrong answer relative to a refusal?"* — derive it from the business, not from taste. Estimate the cost of a wrong answer in the domain, estimate the cost of a refusal, take the ratio, and put that ratio in the scoring function; then state it in the eval documentation so the tradeoff is explicit and arguable. In a clinical or legal setting the ratio can be 20:1 or worse; in content brainstorming it can be under 1.

### Q12 — When is hallucination acceptable or even desirable?
**Testing:** whether you can distinguish surfaces.
**Answer:** When the value of the output is novelty rather than accuracy and a human is the filter: brainstorming, naming, fiction, marketing variants, hypothesis generation, synthetic training data, and adversarial test-case generation, where "produces plausible content not present in the source" is the feature and there is published work on hallucination being useful for drug-discovery ideation. The condition is that nothing downstream treats the output as a fact. The moment a generated hypothesis is written to a system of record, or a synthetic example enters a training set without labelling, the tolerance disappears. So the design rule is per-surface controls, with a documented boundary where creative output must be marked before it can cross into a factual context.
**Follow-up trap:** *"Someone copies a brainstormed 'fact' into a customer email. Whose failure?"* — the system's, for not marking provenance at the boundary. The fix is technical and cheap: creative-surface outputs carry a provenance marker, copy paths into factual surfaces either strip or warn, and the factual surface treats unmarked pasted content as unverified. Blaming the user for a missing affordance is the wrong answer in an interview and in a postmortem.

### Q13 — Give me the observable symptom for each of intrinsic hallucination, extrinsic hallucination, and RAG distraction.
**Testing:** whether you can debug from telemetry.
**Answer:** **Intrinsic**: NLI contradiction score above threshold between a generated sentence and a retrieved chunk that was in context — in a trace, the cited chunk literally says the opposite, and the aggregate signature is a rising contradiction count concentrated in one corpus area, which usually means two document versions coexist in the index. **Extrinsic**: no retrieved window entails the sentence at any threshold, entailment scores clustered near neutral, and the sentence typically contains numbers, dates, or section references (high numeric density), with the aggregate signature being unsupported-rate rising while retrieval scores stay normal. **RAG distraction**: answer quality falls as k rises, so the signature is an eval sweep where accuracy at k=10 is worse than at k=3, plus per-chunk relevance scores showing a long tail of low-relevance chunks in context, and traces where the answer references a chunk that had nothing to do with the question.
**Follow-up trap:** *"You see all three at once in one tenant. Where do you start?"* — the contradiction signal, because it is the most diagnosable and usually the cheapest fix: two versions of a document in the index. Fix corpus hygiene first, then re-measure, because supersession noise inflates both the unsupported rate and the distraction effect and you will otherwise chase phantoms.

### Q14 — What would you say to an executive asking when hallucinations will be fixed?
**Testing:** communication and whether you will over-promise.
**Answer:** "Not fixed, bounded — and here is the current bound and the plan to lower it." Then three sentences of substance: it is a structural property of models that predict text, with a proven statistical floor for facts recalled from weights, so the engineering goal is an error budget like latency or availability rather than elimination; our current measured unsupported-sentence rate on our own golden set is X% at Y% coverage, measured this way; and the next three interventions in priority order with their expected effect and cost. Then the boundary: for the irreversible actions we gate on a human, and that gate is not going away regardless of the model, because the residual rate will never be zero.
**Follow-up trap:** *"A competitor claims zero hallucination."* — they are measuring citation resolution or summarisation faithfulness on an easy task, or they are wrong. The Stanford legal study is the public precedent: a vendor marketed "100% hallucination-free linked legal citations" and independent measurement found 17-33% hallucination. I would offer to run our golden set against their product, and offer to publish our own methodology, because in this area a documented number beats an undocumented zero with any buyer who has been burned once.

---

## Red flags that fail you

- Promising zero hallucination, or claiming RAG eliminates it.
- Leading with prompt engineering or temperature 0 as mitigations.
- Not distinguishing faithfulness from factuality, or intrinsic from extrinsic.
- Quoting a 1% hallucination rate from a summarisation leaderboard as a production expectation.
- Assuming a newer or bigger model hallucinates less. PersonQA: 16% → 33% → 48%.
- Proposing a single detector as a hard gate with no risk-coverage analysis.
- Asking the generating model to check its own output and calling that verification.
- Treating "the output read fine" as QA. Hallucinations are drawn from the plausible neighbourhood by construction.
- No abstention path, so "no supported answer exists" is not a reachable output.
- Scoring internal evals on binary accuracy, thereby paying your own team to guess.
- Applying grounding gates to creative surfaces, or none to factual ones.
- Not knowing that more retrieved context can make faithfulness worse.

## Cheat card

```
TAXONOMY (2 axes, 4 cells)
  FAITHFULNESS vs provided source   ✅ testable now (NLI)   ← where the work goes
  FACTUALITY   vs the world          ⚠ needs external KB    ← a different product
  INTRINSIC = contradicts source (NLI CONTRADICTION → drop sentence)
  EXTRINSIC = source silent        (NLI NEUTRAL → flag / abstain)
  Huang subtypes: instruction · context · logical inconsistency (only ctx caught by grounding)

WHY STRUCTURAL
  no NULL token — decoding must emit something
  lossy fact storage → plausible NEIGHBOUR (Lyon not banana) → always plausible → fluency ≠ truth
  Kalai & Vempala STOC 2024 (2311.14648): calibrated LM must hallucinate arbitrary facts at
    ≥ MONOFACT RATE (fraction of facts seen exactly once) − miscalibration; PNAS 2026 confirms
  post-training worsens it: score(guess)=p>0, score(IDK)=0 → optimising accuracy pays for guessing
  RLHF degrades calibration → the guess sounds certain

NUMBERS (always attach the task)
  Vectara HHEM summarisation 2026: 1.0-2.5% (was 3-8% in 2023) ← EASIEST task, not your SLA
  FACTS Benchmark Suite: no model >70%, leader 68.8%
  AA-Omniscience (6k Qs, 6 domains, refusal free): most frontier models BELOW ZERO
  PersonQA (o3/o4-mini system card 4/2025): o1 16% → o3 33% → o4-mini 48%
  Legal RAG (Stanford RegLab): 17-33% vs GPT-4 43%
  Deep research citations: fact check 24-77%; 79% @2 tool calls → 17% @150
  Clinical, one wrong detail injected: 50-82%

DETECTION, effectiveness/cost
  NLI grounding vs source      BEST value · MiniCheck-FT5 ~770M ≈ Claude 3 Opus · 10-40ms batched
                               Bedrock ctx grounding filters >75% of hallucinated RAG responses
  semantic entropy (Nature '24) n gens + O(n·|C|) NLI · ~0.60 AUROC hard sets · BLIND to consistent falsehood
  SelfCheckGPT self-consistency n=20 · AUC-PR ~0.53-0.67 · ~0.58 AUROC hard sets
  retrieval verification        only method for FACTUALITY · 1+ retrieval per claim
  internal-state probes         1 forward pass, white-box, probe is fit to a distribution
  LLM judge                     10-100x cost, correlated if same family → adjudicate the band only
  ⇒ NO detector is production-sufficient. ROUTE, don't FILTER.

WHAT REDUCES IT (ranked)
  1 grounding in retrieval (+ RELEVANCE FILTER; irrelevant chunks make it worse)
  2 constrained decoding / schema / citation-id grammar   ← eliminates CLASSES, ~free
  3 verification pass (drop contradictions, flag unsupported)
  4 abstention (needs a calibrated signal AND a fallback)
  5 decomposition + tools for arithmetic/dates/lookup/aggregation  ← underrated, 1 day
  6 abstention fine-tuning (watch over-refusal)
  7 decoding interventions: CAD ≈14.3% factuality gain (LLaMA summ.), DoLa, ITI — white-box only
  8 prompting

WHAT DOESN'T
  "be accurate"/"don't hallucinate": 65.9% → 44.2% (real, still 44%)
  temperature 0: 66.5% vs 65.9% — NOT significant. buys reproducibility, not truth
  bigger/newer model · more context · self-verification (same model) · RLHF · single hard gate

PRODUCTION ORDER  retrieve+filter → constrain → generate → verify → route → bounded regen (≤2) → log
EVAL TRAP  binary-accuracy internal leaderboards pay YOUR team to guess.
           Score AA-Omniscience style: reward correct, penalise wrong, refusal neutral.
           Golden set MUST include false premises, underspecified, and unanswerable cases.
AGENT LOOP  compounds (step 7 grounded in step 3's fabrication) · fabricated tool ARGS execute ·
            uncertainty laundered at subagent handoff → check on the OBSERVATION path and
            before any side-effecting call, not only on the final answer
DESIRABLE   brainstorming · naming · fiction · synthetic data · adversarial test gen
            (mark provenance at the boundary into factual surfaces)
```

## Sources

- [Why Language Models Hallucinate (Kalai, Nachum, Vempala & Zhang, arXiv:2509.04664)](https://arxiv.org/pdf/2509.04664) — accessed 2026-07-26
- [Calibrated Language Models Must Hallucinate (Kalai & Vempala, STOC 2024, arXiv:2311.14648)](https://arxiv.org/pdf/2311.14648) — accessed 2026-07-26
- [Hallucination, monofacts, and miscalibration: An empirical investigation (PNAS)](https://www.pnas.org/doi/10.1073/pnas.2533582123) — accessed 2026-07-26
- [Evaluating large language models for accuracy incentivizes hallucinations (Nature, 2026)](https://www.nature.com/articles/s41586-026-10549-w) — accessed 2026-07-26
- [OpenAI o3 and o4-mini System Card (April 2025) — PersonQA hallucination rates](https://cdn.openai.com/pdf/2221c875-02dc-4789-800b-e7758f3722c1/o3-and-o4-mini-system-card.pdf) — accessed 2026-07-26
- [AA-Omniscience: Evaluating Cross-Domain Knowledge Reliability in LLMs (arXiv:2511.13029)](https://arxiv.org/pdf/2511.13029) — accessed 2026-07-26
- [HalluLens: LLM Hallucination Benchmark (arXiv:2504.17550)](https://arxiv.org/pdf/2504.17550) — accessed 2026-07-26
- [Detecting hallucinations in large language models using semantic entropy (Nature 630:625-630, 2024)](https://www.nature.com/articles/s41586-024-07421-0) — accessed 2026-07-26
- [Trusting Your Evidence: Hallucinate Less with Context-aware Decoding (arXiv:2305.14739)](https://arxiv.org/abs/2305.14739) — accessed 2026-07-26
- [Evaluating the Impact of Temperature and Instruction Strategies on Hallucination in LLMs (Gazi Univ. J. Science Part A, 2026)](https://dergipark.org.tr/en/pub/gujsa/article/1819131) — accessed 2026-07-26
- [Multi-model assurance analysis: LLMs are highly vulnerable to adversarial hallucination attacks during clinical decision support (PMC)](https://pmc.ncbi.nlm.nih.gov/articles/PMC12318031/) — accessed 2026-07-26
- [Hallucination-Free? Assessing the Reliability of Leading AI Legal Research Tools (Magesh et al., 2025)](https://onlinelibrary.wiley.com/doi/full/10.1111/jels.12413) — accessed 2026-07-26
- [Cited but Not Verified: Source Attribution in LLM Deep Research Agents (arXiv:2605.06635)](https://arxiv.org/html/2605.06635v1) — accessed 2026-07-26
- [Introducing the Next Generation of Vectara's Hallucination Leaderboard](https://www.vectara.com/blog/introducing-the-next-generation-of-vectaras-hallucination-leaderboard) — accessed 2026-07-26
- [AI Model Hallucination Rates 2026: Vectara HHEM & AA-Omniscience Rankings](https://codingfleet.com/blog/ai-model-hallucination-rates-2026/) — accessed 2026-07-26
- [Amazon Bedrock Guardrails — contextual grounding and Automated Reasoning checks](https://aws.amazon.com/bedrock/guardrails/) — accessed 2026-07-26
- [AbstentionBench: Reasoning LLMs Fail on Unanswerable Questions (arXiv:2506.09038)](https://arxiv.org/html/2506.09038v1) — accessed 2026-07-26

## Changelog
- 2026-07-26 — created
