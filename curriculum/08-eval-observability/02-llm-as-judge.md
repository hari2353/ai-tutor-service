# LLM-as-Judge and Its Failure Modes; Judge Calibration

> **Track:** T08 Eval & Observability · **Time:** 2h · **Prereqs:** none
> **Module id:** `T08-llm-as-judge` · **Tags:** sprint, eval, critical
> **Lab:** `labs/py/02-judge-calibration/`

## The 30-second version

LLM-as-judge replaces a human rater with an LLM prompted to score or compare outputs, and it is the only way to eval free-text generation at the volume production needs — but the judge has the same failure modes as the thing it's judging, plus new ones specific to comparison. It reliably shows position bias (swapping answer order flips the verdict 10-15 points of win rate), verbosity bias (15-30 points of preference for longer answers regardless of quality), and self-preference (a model scores its own family's outputs 10-25% higher). None of that means don't use it; it means you calibrate the judge against human labels before you trust it, report agreement with Cohen's kappa or Krippendorff's alpha, and re-calibrate every time you touch the rubric or swap the judge model. A judge you haven't calibrated is a number you can't defend in a postmortem.

## Why this gets asked

Because every team that ships an LLM feature eventually needs to grade thousands of outputs a human can't read one by one, and the naive move — "ask GPT-4 to rate it 1-10" — is the first thing every senior engineer has watched fail silently. The interviewer has shipped a judge that agreed with itself more than with humans, and wants to know if you'll notice before a bad model ships behind a green dashboard. At staff level they're probing whether you understand that the judge is a *model with its own biases*, not a ground truth oracle, and whether you know what to do when the judge and the thing it's judging share a blind spot.

---

## Lineage: past → present → future

**What came before.** Automated NLG evaluation started with n-gram overlap metrics — BLEU (2002) for translation, ROUGE (2004) for summarization — which count matching word sequences against a reference. They correlate weakly with human judgment on anything beyond translation and fail completely on open-ended generation: a paraphrase that says the same thing in different words scores near zero. Embedding-based metrics (BERTScore, 2019) improved semantic matching but still needed a reference and still couldn't judge things like "is this helpful" or "did this follow instructions," which have no single correct string. Human evaluation was the fallback, and it does not scale: it is slow, expensive, and itself inconsistent — human-human agreement on subjective quality judgments is often only moderate.

**Where it stands now.** Zheng et al.'s "Judging LLM-as-a-Judge with MT-Bench and Chatbot Arena" (2023) established that GPT-4 as a judge agrees with human preference at roughly 80-85%, which is close to human-human agreement (~81%), and this result launched LLM-as-judge as the default eval method for chat, RAG, and agent quality. The current consensus: pairwise comparison judges are more reliable than pointwise scoring for ranking two systems, pointwise is necessary when you need an absolute number (a quality gate, a trend line), and reference-based grading (giving the judge a gold answer to compare against) is the most reliable of the three when a gold answer exists. The live disagreement is over how much to trust an uncalibrated judge at all — a 2026 study found frontier models exceeding 50% error rates on adversarial bias benchmarks, and no single judge model is uniformly reliable across task types. What's actually deployed at scale: cheap judges (small fine-tuned classifiers, or a mid-tier model like GPT-4o-mini/Haiku) gate CI and run on 100% of traffic; frontier judges (GPT-5-class, Claude Opus-class) run on a sampled subset for calibration and hard cases; and every serious shop validates the judge against a human-labeled set before trusting it, computing inter-rater agreement the same way you would for two human labelers.

**Where it's heading.** Fine-tuned small "judge models" (e.g., MiniCheck-class, purpose-built reward/verifier models) are increasingly used in place of prompting a general frontier model, because they're 10-100x cheaper per call and can be calibrated end to end — this is real and shipping. Rubric-as-code (structured, programmatic rubrics with explicit point allocations rather than a free-text prompt) is gaining ground because it makes judges auditable and reduces prompt sensitivity — moderate confidence, actively being adopted. More speculative: using ensembles of heterogeneous judges (different model families) specifically to cancel out shared family-level bias, and automatically detecting judge-generator collusion by measuring whether a judge's scores correlate suspiciously well with which model produced the output — early research, not yet standard practice.

---

## Mental model

```
                         ┌─────────────────────────────┐
  candidate output(s) ──▶│         THE JUDGE            │
                         │  (prompt + rubric + model)   │
                         └───────────────┬───────────────┘
                                         │
                    ┌────────────────────┼────────────────────┐
                    ▼                    ▼                    ▼
              POINTWISE            PAIRWISE            REFERENCE-BASED
           score A alone         A vs B, pick        score A against
           on a 1-5/1-10        winner (or tie)        a gold answer
             rubric

     Reliable for:          Reliable for:           Reliable for:
     absolute gates,        ranking two systems,     factual/RAG tasks
     trend lines over       A/B model comparison     where a gold answer
     time                                             exists

     Vulnerable to:         Vulnerable to:            Vulnerable to:
     score drift, no        POSITION bias (order      judge anchors too
     anchor across          flips verdict),           hard on reference
     sessions               VERBOSITY bias            phrasing (misses
                                                       valid paraphrases)

                    ▼                    ▼                    ▼
              ┌─────────────────────────────────────────────────┐
              │   CALIBRATION: score N traces with 2-3 humans,   │
              │   compute inter-annotator kappa; score same      │
              │   traces with judge, compute judge-vs-human      │
              │   kappa. Ship only if judge-vs-human >= 0.6.      │
              └─────────────────────────────────────────────────┘
```

The judge is not a fact-checker plugged into your pipeline — it's a second model whose output you have to validate exactly like you'd validate the first one, using the same human-labeling discipline.

---

## How it actually works

### Pairwise vs pointwise vs reference-based

| Mode | What it does | Strongest at | Weakest at |
|---|---|---|---|
| **Pointwise / single-answer grading** | Judge assigns an absolute score (e.g. 1-5) to one output against a rubric | Trend lines, absolute quality gates, when you only have one candidate | Score drift across sessions — a "4" today may not mean the same thing as a "4" last month, because the judge has no fixed anchor |
| **Pairwise comparison** | Judge sees two outputs (usually plus the prompt), picks winner or declares a tie | A/B testing two models or prompts, ranking, Elo-style leaderboards (Chatbot Arena) | Absolute quality — a pairwise win tells you nothing about whether both outputs are actually bad |
| **Reference-based / reference-guided** | Judge is given a gold answer and grades the candidate against it | Factual QA, RAG faithfulness, translation, anything with a correct answer | Penalizing valid paraphrases or alternate-but-correct approaches that don't textually resemble the reference |

G-Eval (Liu et al., 2023) formalized a stronger pointwise recipe: have the judge first generate its own chain-of-thought evaluation steps from the criterion, then use those steps as a form to fill in, and take a probability-weighted score across the top logprobs rather than the single sampled token. This consistently beats naive "just output a number" prompting on correlation with human judgment for criteria like coherence and consistency, because it forces the judge to externalize its reasoning before committing to a score, and the probability weighting smooths out the judge's own sampling noise.

### The documented biases, with real magnitudes

- **Position bias.** Swapping the order of two candidates in a pairwise prompt shifts the win rate by roughly 10-15 percentage points, independent of quality (Zheng et al., 2023, MT-Bench paper). Mitigation: always run both orderings (A-then-B and B-then-A) and only count a win if it's consistent in both; if the verdict flips, score it a tie.
- **Verbosity bias.** Judges systematically prefer longer answers even when they're not better — measured at 15-30 points of inflated preference for verbose responses across GPT-4, Claude, and PaLM-2 judges (Wang et al., 2023). Mitigation: explicit "do not prefer longer answers solely for length" instruction in the rubric, plus length-controlled analysis (bucket by output length and check if the preference holds within a bucket).
- **Self-preference bias.** A judge scores outputs from its own model family 10-25% higher than equivalent-quality outputs from a different family (arXiv:2410.21819, "Self-Preference Bias in LLM-as-a-Judge"). This is the one you cannot fully surface by staring at scores — the fix is structural: never use the same model (or a close relative — same lab, same base) as both judge and candidate in a comparison you're using to pick a winner.
- **Sycophancy.** The judge's score shifts toward whatever framing or stated preference is embedded in the prompt — if the prompt implies the user already likes an answer, the judge rates it higher regardless of actual quality. This compounds with self-preference when the "user" in a synthetic eval loop is itself an LLM that anchors on its own priors.
- **Format bias.** Structured output (bullet points, headers, markdown) gets rated higher than equally correct prose. A 2410.02736 study ("Justice or Prejudice?") catalogued 12 distinct bias types (including position, verbosity, self-preference, and format/style biases) and found that even advanced models show significant biases on specific bias-stress-test tasks, despite strong aggregate scores — meaning a judge can look reliable on average while failing hard on the exact dimension you're testing.

### Calibrating a judge against human labels

This is the step most teams skip and the one interviewers actually probe.

1. Sample 100-300 real traces (not a synthetic eval set — production distribution, including hard/ambiguous cases).
2. Have 2-3 humans independently label each trace on the *exact rubric the judge will use* — same categories, same scale, same instructions.
3. Compute inter-annotator agreement first:
   - **Cohen's kappa** for exactly 2 raters.
   - **Krippendorff's alpha** for 3+ raters, ordinal/interval scales, or missing labels (more flexible, handles any rater count).
   - Interpretation: kappa/alpha < 0.4 → the rubric is ambiguous, fix it before blaming the judge. 0.4-0.6 → weak, tune the rubric. > 0.6 → acceptable. > 0.8 → strong.
4. Score the same traces with the LLM judge using the identical rubric prompt.
5. Compute judge-vs-human agreement (Cohen's kappa between judge label and the human majority vote, or judge-vs-each-human averaged).
   - **kappa > 0.6**: judge is production-acceptable.
   - **kappa > 0.8**: strong, safe to lean on heavily.
   - **kappa < 0.6**: do not gate a release on this judge yet.
6. Re-run this whenever you change the rubric, swap the judge model, or upgrade the judge model's version — a silent model alias bump can shift judge behavior with no code change on your side.

In practice, a first-pass rubric typically lands at kappa 0.4-0.5; iterating on rubric clarity (concrete examples of each score level, explicit "do not consider X" exclusions) gets well-calibrated judges to 0.65-0.80. Getting to 1.0 is not the goal — human raters don't agree with each other perfectly either, and a judge that agrees with humans *better* than humans agree with each other is a red flag for judge-human collusion (the judge picked up on a superficial cue that correlates with the label but isn't the thing you're actually measuring).

### Cheap judge vs frontier judge

| | Cheap judge (small model / fine-tuned classifier / GPT-4o-mini-class) | Frontier judge (GPT-5-class / Opus-class) |
|---|---|---|
| Cost per call | Fractions of a cent, tens of ms | 10-100x more, seconds |
| Where it belongs | CI gates on every PR, 100% of production traffic sampling, high-frequency regression detection | Calibration runs, adjudicating disagreements, hard/ambiguous cases, nuanced rubrics (e.g. subtle harmfulness, multi-step reasoning quality) |
| Risk | Misses nuance, higher variance on hard cases | Cost and latency prohibit running on every request; still has all the same biases, just usually smaller magnitude |
| When it's *sufficient* | The rubric is close to a checklist (did it cite a source, is the JSON valid, does it contain a disallowed word) — these are near-deterministic and a cheap model gets them right almost all the time | N/A — use frontier when the criterion requires judgment, not lookup |

Rule of thumb: if a competent human could apply the rubric in under 10 seconds without re-reading the source material, a cheap judge suffices. If the human needs to think, cross-reference, or weigh tradeoffs, use a frontier judge for at least the calibration set and route only the confident/easy cases to the cheap judge in production (a router, not a blanket downgrade).

### Rubric design

- Write the rubric as if it will be read by someone who's never seen the task — spell out what "helpful," "correct," or "concise" means for *this* task, don't rely on the judge's prior.
- Give concrete anchor examples for each score level (a 1, a 3, a 5), not just adjectives.
- Explicitly exclude the dimensions you don't want scored (e.g. "ignore formatting; do not penalize length; do not compare to your own preferred answer style").
- One criterion per rubric call. A rubric asking for "correctness, helpfulness, and tone" in one pass conflates independent signals into a single number you can't debug later; run three focused passes instead.
- Ask for reasoning before the score (G-Eval's chain-of-thought-then-score pattern) — it's both a bias mitigation and a debugging aid, since you can read *why* the judge gave the score.

### The shared-blind-spot failure

The most dangerous failure mode isn't the documented biases above — it's when the judge and the generator share a training-time blind spot. If both models were trained on similar data and neither knows a fact, the judge will happily certify a fabricated answer as correct because the fabrication matches the judge's own (equally wrong) prior. This is why reference-based grading against a verified gold answer, or grounding the judge in retrieved source documents it must cite against, catches errors that judge-alone-with-no-source cannot: the judge is checking the candidate against something outside both models' shared knowledge, not against its own recall. A judge with no ground truth to check against is only as good as the union of what it and the candidate both happen to know — which is exactly correlated with what they'll both get wrong together.

---

## Build it from scratch

Minimal pairwise judge with position-bias mitigation and a calibration harness — the shape of the code an interviewer may ask you to sketch.

```python
# untested sketch
from dataclasses import dataclass
from sklearn.metrics import cohen_kappa_score

RUBRIC = """You are grading which of two AI responses better answers the user's
question. Judge ONLY correctness and helpfulness. Do NOT prefer a response
merely because it is longer or uses more formatting. Do NOT compare to how
you personally would answer.

Question: {question}
Response A: {a}
Response B: {b}

Think step by step about which response is more correct and more helpful,
then output exactly one line: "WINNER: A", "WINNER: B", or "WINNER: TIE"."""

@dataclass
class JudgeResult:
    winner: str          # "A", "B", or "TIE"
    reasoning: str

def judge_pair(llm_call, question: str, a: str, b: str) -> JudgeResult:
    """Runs both orderings; only returns a decisive winner if consistent."""
    r1 = llm_call(RUBRIC.format(question=question, a=a, b=b))
    r2 = llm_call(RUBRIC.format(question=question, a=b, b=a))  # swapped

    w1 = parse_winner(r1)                      # "A" or "B" or "TIE"
    w2_raw = parse_winner(r2)
    w2 = {"A": "B", "B": "A", "TIE": "TIE"}[w2_raw]   # un-swap

    if w1 != w2:
        return JudgeResult(winner="TIE", reasoning="position-bias flip: treated as tie")
    return JudgeResult(winner=w1, reasoning=r1)

def calibrate(human_labels: list[str], judge_labels: list[str]) -> float:
    """Cohen's kappa between judge and human majority vote."""
    return cohen_kappa_score(human_labels, judge_labels)

# Gate: only trust this judge in CI if calibrate(...) >= 0.6 on your held-out set.
```

Full version with Krippendorff's alpha for 3+ raters, a G-Eval-style CoT-then-score pointwise grader, and a bias-stress-test suite (position, verbosity, self-preference probes): **`labs/py/02-judge-calibration/`**.

---

## How it's done in production

Frameworks: **DeepEval** (broadest open-source metric coverage, pytest-native, good for CI-gated unit-test-style evals), **Ragas** (RAG-specific: faithfulness, answer relevancy, context precision/recall — reference-free), **Braintrust** and **LangSmith** (full lifecycle: dataset management, scoring, production monitoring, CI release gates, human annotation queues), **Arize Phoenix** (OpenTelemetry-native trace capture plus eval, strong for drift detection in production). None of these frameworks make bias disappear — they give you the harness to run the calibration workflow above at scale and track kappa over time as a metric in itself.

**Failure-mode table:**

| Symptom | Cause | Fix |
|---|---|---|
| Judge always prefers model B in an A/B eval regardless of which model actually produced better output | Position bias, or B happens to be the more verbose model | Swap-and-check both orderings; only count consistent verdicts; add explicit anti-verbosity instruction |
| Judge scores rise release over release but user complaints also rise | Judge-generator collusion, or judge drift after a silent model version bump | Re-run calibration against human labels after every judge model change; pin judge model version explicitly |
| Judge-vs-human kappa is high (>0.9) — feels great | Possible red flag: judge may be picking up a superficial correlate of the label rather than the underlying quality signal (e.g. answer length correlating with your human raters' fatigue-driven leniency) | Audit disagreement cases the judge and humans DO share; check if the judge's high agreement holds on an adversarial subset |
| Reference-based judge marks obviously-correct paraphrases as wrong | Judge is doing near-string-match against the reference rather than semantic grading | Rewrite rubric to explicitly instruct "credit answers that are substantively equivalent even if worded differently"; consider embedding-similarity as a pre-filter |
| Same-family judge rates its own model's outputs suspiciously well across every eval | Self-preference bias | Use a judge from a different model family/lab than any candidate being scored |
| Judge certifies a fabricated fact as correct | Judge and generator share a training-data blind spot; no external ground truth in the judge's context | Give the judge the retrieved source or gold answer to check against, not just its own parametric knowledge |

---

## Tradeoffs & when NOT to use it

- **Do not use LLM-as-judge as the sole gate for anything safety-critical or irreversible** (financial transactions, medical guidance, destructive agent actions) without a human in the loop — a kappa of 0.7 still means real disagreement on 30%+ of cases, and you don't get to choose which 30%.
- **Do not skip calibration because "GPT-4 is smart."** An uncalibrated judge is a vibe, not a metric — you cannot defend a dashboard number in an incident review if you never measured it against a human baseline.
- **Do not use the same model family as both judge and candidate** when the eval result will influence a model-selection decision; self-preference bias will quietly tilt the outcome.
- **Pointwise absolute scores are the wrong tool for model-selection A/B tests** — the score anchor drifts across sessions and doesn't compare cleanly; use pairwise for ranking decisions.
- **Don't over-index on aggregate agreement.** A judge with 0.75 overall kappa can still fail completely on one bias dimension (e.g., always losing to verbosity) — run the documented bias stress-tests (swap order, pad one response with irrelevant length, submit outputs from the judge's own family) as part of calibration, not just aggregate correlation.
- **For purely deterministic, checklist-style criteria** (valid JSON, contains required field, matches a regex), a judge is the wrong tool entirely — write a deterministic check. Reserve the judge for genuinely subjective or open-ended criteria.

---

## Interview questions

### Q1 — What is LLM-as-judge and why not just use BLEU/ROUGE?
**Testing:** baseline understanding of why reference-overlap metrics fail on open-ended generation.
**Answer:** BLEU/ROUGE measure n-gram overlap with a reference string; they correlate weakly with human judgment on anything beyond translation because a correct paraphrase scores near zero. LLM-as-judge prompts a model to assess quality directly (pointwise, pairwise, or reference-based), which handles open-ended criteria like helpfulness or faithfulness that have no single correct string.
**Follow-up trap:** *"So the judge is ground truth now?"* — no. The judge is a model with its own failure modes (position bias, verbosity bias, self-preference) and must be calibrated against human labels before you trust its scores, exactly like you'd validate any other model output.

### Q2 — Explain the difference between pairwise, pointwise, and reference-based judging, and when you'd use each.
**Testing:** whether the candidate has actually deployed more than one mode.
**Answer:** Pointwise assigns an absolute score to one output against a rubric — good for trend lines and quality gates, weak because the score anchor drifts across sessions. Pairwise shows the judge two outputs and asks which is better — most reliable for ranking two systems or models, but tells you nothing about absolute quality (both could be bad). Reference-based grades a candidate against a gold answer — most reliable when a correct answer exists (factual QA, RAG), but can wrongly penalize valid paraphrases.
**Follow-up trap:** *"Which do you use for a monthly quality dashboard vs. an A/B test between two prompts?"* — dashboard: pointwise (you need a number over time), A/B: pairwise (you need a relative winner, and pairwise judges are measurably more reliable at ranking than two independent pointwise scores compared after the fact).

### Q3 — What is position bias and how do you mitigate it?
**Testing:** whether they know a specific number, not just the concept.
**Answer:** Swapping the order of two candidates in a pairwise prompt shifts the win rate 10-15 percentage points independent of actual quality (Zheng et al., 2023). Mitigation: run both orderings and only count a win if the verdict is consistent in both; if it flips, score it a tie rather than picking one arbitrarily.
**Follow-up trap:** *"Doesn't running both orderings double your cost?"* — yes, and that's the correct tradeoff for anything gating a release decision; for high-volume low-stakes monitoring you can sample a subset for the double-check and extrapolate the bias rate, applying a correction rather than paying 2x on every call.

### Q4 — What is verbosity bias and what's the measured magnitude?
**Answer:** Judges systematically prefer longer answers regardless of quality — measured at 15-30 points of inflated preference across GPT-4, Claude, and PaLM-2 judges (Wang et al., 2023). Mitigate with an explicit rubric instruction not to prefer length, plus length-bucketed analysis to check the preference doesn't persist within a length band.
**Follow-up trap:** *"What if the correct answer genuinely IS longer for one of the two candidates?"* — that's exactly why length-controlled analysis matters more than a blanket instruction: bucket comparisons by output-length similarity and check whether the win rate still tilts to the longer one within a bucket where lengths are close. If it does, that's real bias, not real quality.

### Q5 — What is self-preference bias?
**Answer:** A judge scores its own model family's outputs 10-25% higher than equivalent-quality outputs from a different family (arXiv:2410.21819). It's structural, not a prompting problem, and no rubric wording reliably surfaces it because the judge doesn't know it's exhibiting the bias.
**Follow-up trap:** *"You're comparing two fine-tunes of the SAME base model — does this still apply?"* — potentially yes, and worse: family-level bias can extend to close relatives sharing training data or lineage, not just identical models. Use a judge from a genuinely different lab/family whenever the eval outcome affects a real decision.

### Q6 — How do you calibrate a judge, step by step?
**Testing:** the core production process, not just definitions.
**Answer:** Sample 100-300 real traces, have 2-3 humans label them on the exact rubric the judge will use, compute inter-annotator agreement (Cohen's kappa for 2 raters, Krippendorff's alpha for 3+), then score the same traces with the judge and compute judge-vs-human kappa. Ship only if judge-vs-human kappa exceeds ~0.6, treat >0.8 as strong. Re-calibrate after any rubric change or judge model version bump.
**Follow-up trap:** *"Your inter-annotator kappa among humans is only 0.5. What does that tell you?"* — the rubric itself is ambiguous; fix the rubric (concrete anchor examples, explicit exclusions) before blaming the judge, because you can't hold the judge to a bar the humans themselves can't clear.

### Q7 — Cohen's kappa vs Krippendorff's alpha — when do you use which?
**Answer:** Cohen's kappa is for exactly two raters and nominal/ordinal categories. Krippendorff's alpha generalizes to any number of raters, handles ordinal/interval scales, and tolerates missing observations (not every rater labels every item). Use kappa for a simple judge-vs-single-human-baseline check; use alpha once you have 3+ human labelers or incomplete label coverage.
**Follow-up trap:** *"Why not just use raw percent agreement?"* — percent agreement doesn't correct for chance agreement, so on an imbalanced label set (e.g. 90% of outputs are "pass") two raters who both mostly say "pass" look highly agreed even if they're not actually tracking the same signal. Kappa/alpha subtract out the expected chance-agreement rate.

### Q8 — When is a cheap judge sufficient, and when do you need a frontier model?
**Answer:** Cheap judges suffice for near-checklist criteria a competent human could apply in seconds without re-reading source material (valid JSON, cites a source, contains a disallowed term). Frontier judges are needed when the criterion requires genuine judgment — nuanced correctness, multi-step reasoning quality, subtle harm. In production: cheap judge on 100% of traffic and CI, frontier judge for calibration runs and routing hard/ambiguous cases.
**Follow-up trap:** *"Your cheap judge and frontier judge disagree on 15% of cases. What do you do?"* — don't average them. Route disagreements to human adjudication, and use that adjudicated set to see if the disagreement clusters around a specific failure pattern (e.g. the cheap judge misses multi-hop reasoning errors) — that tells you which cases need to be escalated to the frontier judge in production, not just in calibration.

### Q9 — Design a rubric for grading RAG answer faithfulness. What goes wrong with a naive rubric?
**Answer:** A naive rubric ("is this response faithful to the source? 1-5") conflates faithfulness (matches the provided context) with factuality (matches the world), so a response that's unfaithful to a wrong retrieved chunk but happens to be factually correct gets penalized incorrectly, or vice versa. A better rubric explicitly scopes to faithfulness only, gives the judge the retrieved chunks as the sole source of truth, and asks it to flag specific unsupported sentences rather than a single aggregate score.
**Follow-up trap:** *"What if the retrieved context itself is wrong?"* — faithfulness and factuality are separate axes on purpose; a faithfulness judge should mark the answer as faithful to (wrong) context and a *separate* factuality check (against a verified source, not the judge's own recall) catches the underlying retrieval error. Conflating them hides which system — retrieval or generation — actually broke.

### Q10 — What is the shared-blind-spot failure mode, and how do you catch it?
**Testing:** whether the candidate understands the judge isn't an independent oracle.
**Answer:** If the judge and the generator were trained on similar data and neither actually knows a fact, the judge will certify a fabrication as correct because the fabrication matches its own equally-wrong prior — the judge has no ground truth outside its shared training distribution with the candidate. Catch it by grounding the judge in something external to both models: a retrieved source document it must check citations against, or a verified gold answer, not just "does this sound right to you."
**Follow-up trap:** *"Doesn't giving the judge the source document just move the problem — what if the source is itself wrong?"* — yes, and that's why faithfulness (vs. provided source) and factuality (vs. the world) have to be evaluated as separate axes; a faithfulness-only judge with a correct source catches generator fabrication, but a wrong source requires a genuinely external fact-check, which is a different, more expensive pipeline stage.

### Q11 — Your judge-vs-human kappa is 0.95. Is that good news?
**Testing:** staff-level skepticism of a suspiciously good number.
**Answer:** Not automatically — audit it. Extremely high agreement can mean the judge is genuinely well-calibrated, or it can mean the judge and your human raters are both keying off a superficial correlate of the label (like output length, or a specific phrase) rather than the actual quality signal the rubric intends. Check agreement on an adversarial subset specifically designed to break that correlate before trusting the aggregate number.
**Follow-up trap:** *"How would you build that adversarial subset?"* — deliberately construct cases where the superficial correlate and the true label diverge: a short-but-excellent answer, a long-but-wrong answer, an answer in the judge's own model family's style that's actually worse. If kappa drops sharply on this subset, the aggregate number was measuring the wrong thing.

### Q12 — G-Eval's chain-of-thought-then-score approach — why does it outperform "just output a number"?
**Answer:** G-Eval has the judge first generate its own evaluation steps from the criterion, then fill those steps in as a form, then take a probability-weighted score across the top logprobs rather than the single sampled token. Forcing the reasoning to be externalized before the score reduces the chance the judge anchors on a surface cue, and probability-weighting smooths sampling noise that would otherwise make a single-token score jump around between identical inputs.
**Follow-up trap:** *"What if the model doesn't expose logprobs (e.g., behind an API that only returns text)?"* — fall back to sampling the judge N times at low-but-nonzero temperature and taking the modal or averaged score; you lose the elegance of true probability-weighting but you still get the CoT-before-score benefit and some noise-averaging.

### Q13 — How do you build a CI gate on an LLM judge that doesn't flake?
**Answer:** Fix the judge model version explicitly (don't track "latest"), set temperature low/zero for reproducibility on the judge call itself, run pairwise comparisons in both orderings and treat a flip as a tie rather than noise, and set the pass/fail threshold based on the judge's calibrated agreement with humans — not an arbitrary score cutoff picked because it "felt right." Track judge-vs-human kappa as its own monitored metric, not just the eval score, so drift shows up before it silently degrades the gate.
**Follow-up trap:** *"The judge model provider deprecates the version you pinned. Now what?"* — you have to re-run the full calibration against human labels on the new version before swapping it in; a same-numbers-different-model swap is exactly the kind of silent shift that breaks a gate everyone assumed was stable.

### Q14 — A model upgrade improves your LLM-judge score on every internal eval. Ship it?
**Testing:** whether accuracy-only optimization traps are understood (ties to Goodhart's law).
**Answer:** Not on judge score alone. If the new model is in the same family as the judge, rising scores could partly be self-preference bias inflating the number rather than real quality improvement. Cross-check with a judge from a different family, and validate against the calibrated human-labeled set specifically, not just the automated eval suite the new model might be (even unintentionally) optimized-adjacent to.
**Follow-up trap:** *"The cross-family judge agrees the new model is better. Ship now?"* — check user-facing signals too (complaint rate, task success in production) before fully trusting any offline judge, cross-family or not — offline judges correlate with but don't perfectly predict production outcomes, especially on distribution shift the eval set doesn't cover.

### Q15 — Design the eval strategy for a coding assistant that grades "is this a good PR description."
**Testing:** whether they can apply the whole toolkit to a concrete open-ended task.
**Answer:** Pointwise judge for a quality-trend dashboard (score 1-5 against a rubric: summarizes the change, explains why, notes testing/risk); pairwise judge when comparing two prompt versions for the description-generation feature; calibrate against 100-200 human-labeled real PR descriptions with 2-3 raters, targeting kappa > 0.6 before gating a release on the score. Explicitly instruct the rubric not to prefer longer descriptions (verbosity bias is a real risk here — more text looks more thorough). Use a judge model from a different family than the coding assistant's underlying model to avoid self-preference.
**Follow-up trap:** *"Your calibration kappa is 0.55 no matter how you tune the rubric. What's actually going on?"* — the underlying quality dimension itself may be genuinely subjective/ambiguous to humans too (a good PR description is partly a matter of team style), so check inter-human kappa first — if that's also capped around 0.55-0.6, the ceiling isn't the judge's fault, and you should either narrow the rubric to more objective sub-criteria or accept a lower-confidence signal for this dimension specifically.

---

## Red flags that fail you

- Treating the judge's score as ground truth with no human calibration step, ever.
- Saying "GPT-4 as judge" without naming a single documented bias.
- Not knowing the rough magnitude of position bias or verbosity bias (a specific number, not just "it exists").
- Using the same model family as both judge and candidate in a decision-driving comparison.
- Reporting an eval result with no agreement statistic (kappa/alpha) attached.
- Not distinguishing pairwise, pointwise, and reference-based, or picking the wrong one for the task (e.g. pointwise for an A/B ranking decision).
- Assuming a high judge-vs-human kappa is automatically good news without auditing for collusion on a superficial correlate.

---

## Cheat card

```
MODES        pointwise (absolute score, drifts across sessions) · pairwise (A vs B,
              most reliable for ranking) · reference-based (vs gold answer, best
              when gold exists, misses valid paraphrases)

BIASES        position:      10-15pt win-rate swing on order swap (Zheng 2023)
              verbosity:     15-30pt preference for longer answers (Wang 2023)
              self-pref:     +10-25% for judge's own model family (arXiv:2410.21819)
              format:        prefers bullets/headers over equal-quality prose
              sycophancy:    shifts toward the framing embedded in the prompt

CALIBRATE     1) 100-300 real traces  2) 2-3 humans label, same rubric
              3) inter-annotator: Cohen's kappa (2 raters) / Krippendorff's alpha (3+)
              4) judge scores same traces  5) judge-vs-human kappa
              THRESHOLDS: <0.4 rubric ambiguous · 0.4-0.6 weak · >0.6 ship · >0.8 strong
              re-calibrate on ANY rubric change or judge model version bump

CHEAP vs      cheap (small/fine-tuned/mini): CI gates, 100% traffic, checklist-style
FRONTIER      frontier (GPT-5/Opus-class): calibration set, hard cases, nuanced judgment

MITIGATIONS   position -> run both orderings, flip = tie
              verbosity -> explicit rubric line + length-bucketed analysis
              self-pref -> judge from a DIFFERENT model family than any candidate
              shared blind spot -> ground judge in external source/gold answer

G-EVAL        CoT-generate-steps -> form-fill -> probability-weighted score
              beats naive "output a number" on correlation w/ human judgment

RED FLAG      judge-vs-human kappa suspiciously high (>0.9) -> audit for collusion
              on a superficial correlate before trusting it
```

## Sources

- [Judging LLM-as-a-Judge with MT-Bench and Chatbot Arena (Zheng et al., arXiv:2306.05685)](https://arxiv.org/abs/2306.05685) — accessed 2026-07-26
- [Justice or Prejudice? Quantifying Biases in LLM-as-a-Judge (arXiv:2410.02736)](https://arxiv.org/pdf/2410.02736) — accessed 2026-07-26
- [Self-Preference Bias in LLM-as-a-Judge (arXiv:2410.21819)](https://arxiv.org/pdf/2410.21819) — accessed 2026-07-26
- [LLM-as-a-Judge: Why Frontier Models Fail 50%+ Bias Tests — Adaline](https://www.adaline.ai/blog/llm-as-a-judge-reliability-bias) — accessed 2026-07-26
- [How to Calibrate Your LLM Judge With Human Annotations — Galileo](https://galileo.ai/blog/calibrate-llm-judge-human-annotations) — accessed 2026-07-26
- [How to measure human-LLM judge alignment — Arize AI](https://arize.com/blog/measuring-human-llm-judge-alignment/) — accessed 2026-07-26
- [LLM-as-Judge Best Practices in 2026: Calibration, Bias, and Cost — FutureAGI](https://futureagi.com/blog/llm-as-judge-best-practices-2026) — accessed 2026-07-26
- [Evaluating the Effectiveness of LLM-Evaluators — Eugene Yan](https://eugeneyan.com/writing/llm-evaluators/) — accessed 2026-07-26
- [DeepEval alternatives (2026) — Braintrust](https://www.braintrust.dev/articles/deepeval-alternatives-2026) — accessed 2026-07-26

## Changelog
- 2026-07-26 — created
