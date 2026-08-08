# Trust Calibration: Confidence, Abstention, Saying I Don't Know

> **Track:** T07 Agentic AI · **Time:** 2.5h · **Prereqs:** `T07-explainability`, `T06-latency-accuracy` · **Updated:** 2026-07-26
> **Module id:** `T07-trust-calibration` · **Tags:** trust, critical
> **Lab:** `labs/py/23-trust-calibration/`

## The 30-second version

Calibration is a testable property, not a vibe: a system is calibrated if, across all the times it says 80%, it is right 80% of the time, and you measure the gap with expected calibration error, `ECE = Σ_m (|B_m|/n)·|acc(B_m) − conf(B_m)|` over M bins. LLMs are badly calibrated in the channel product teams actually use — **verbalised** confidence clusters in the 80-100% band almost regardless of accuracy, with measured ECE ranging from about 0.05 on constrained JSON tasks to 0.61 on open-domain QA — because nothing in RLHF trains the confidence token and human raters reward decisiveness. Logprob confidence is better but measures *surface* likelihood, so probability mass splits across paraphrases of the same true answer; **semantic entropy** (Farquhar et al., *Nature* 630:625-630, 2024) fixes that by clustering samples into meaning classes by bidirectional entailment and taking entropy over clusters, at a cost of n sampled generations plus O(n²) entailment checks. The engineering deliverable is not a confidence number in the UI, it is a **selective predictor**: one calibrated threshold, a risk-coverage curve, and a stated product SLO of the form "≤2% error at ≥90% coverage", with everything below threshold routed to a clarifying question, a stronger model, or a human. And you communicate uncertainty by **changing the action, not the adjective** — a system that hedges every sentence reads as broken while a system that answers confidently, abstains rarely, and abstains *legibly* reads as trustworthy.

## Why this gets asked

Because the interviewer has shipped a confidence score that meant nothing. Someone put `confidence: 0.92` in a response payload, a downstream team thresholded on it at 0.8, and six months later it turned out the model emits 0.9 for everything including fabrications, so the threshold filtered nothing and the whole review workflow was theatre. Or worse: the support bot answered every question, including the 4% it had no basis for, and the cost of those 4% was a regulatory complaint. The probe is whether you know that **confidence is a measurement problem with an established methodology** and not a field you make up. At staff level they push on the second-order question, which is the one that separates people: abstention is not free. Every "I don't know" is a user you did not help, and a product that abstains 25% of the time gets uninstalled. The candidate they want can state the tradeoff as a curve, pick an operating point with a number attached, and say who owns the decision.

---

## Lineage: past → present → future

**What came before.** Calibration is old and came from weather forecasting: Brier (1950) gave the proper scoring rule, Murphy (1973) decomposed it into reliability, resolution, and uncertainty, and reliability diagrams were standard practice in meteorology decades before ML adopted them. Classical ML got post-hoc recalibration in Platt scaling (1999) and isotonic regression, and for a while shallow models were roughly calibrated out of the box. That ended with deep nets: **Guo et al., "On Calibration of Modern Neural Networks" (ICML 2017, arXiv:1706.04599)** showed modern networks are systematically *overconfident*, that depth, width, weight decay, and batch norm all make it worse, and that a single-parameter **temperature scaling** on the logits fixes most of it on a held-out split. The pain that made this urgent was concrete: softmax scores were being used as thresholds for automated action, and a model with 70% accuracy emitting 0.99 confidence silently converted a review queue into a rubber stamp.

For LLMs the specific pain arrived with RLHF. The GPT-4 technical report's own calibration plots on an MMLU subset show the pre-trained model sitting essentially on the diagonal and the post-trained model pulled well above it: **post-training measurably hurt calibration**. The mechanism is not subtle. Preference data rewards answers that read as authoritative, and there is no reward term anywhere for "the stated confidence matched the outcome frequency".

**Where it stands now.** Four things are settled and one is genuinely contested. Settled: (1) **verbalised confidence is overconfident across models, domains, and elicitation strategies**, concentrating in the 80-100% range regardless of accuracy, with task-dependent ECE spanning roughly 0.05 (constrained JSON) to 0.61 (NQ-Open) in 2026 benchmark work such as ConfidenceBench (arXiv:2607.20526). (2) **Token logprobs are a usable but biased signal** for constrained outputs (multiple choice, classification, extraction) and a poor one for free-form generation, because likelihood is over surface forms. (3) **Semantic entropy is the right shape of fix** — cluster samples by bidirectional entailment, take entropy over meaning classes — published in *Nature* in June 2024 and now the reference method, with **semantic entropy probes** (arXiv:2406.15927) approximating it from hidden states in a single forward pass when you cannot afford n samples. (4) **Abstention is unsolved**: AbstentionBench (arXiv:2506.09038), 20 datasets and 35k+ unanswerable queries, found that scaling does not help and that *reasoning fine-tuning actively degrades* the ability to abstain — which is a genuinely uncomfortable finding for anyone whose plan was "use the reasoning model".

The live disagreements. First, **why models hallucinate rather than abstain**: Kalai, Nachum, Vempala & Zhang, *Why Language Models Hallucinate* (arXiv:2509.04664, OpenAI, 2025), and the follow-on *Nature* paper *Evaluating large language models for accuracy incentivizes hallucinations* (2026) argue the cause is the scoreboard — binary accuracy metrics award zero for "I don't know" and positive expected value for a guess, so the training and evaluation ecosystem selects for guessing, and one hallucination benchmark cannot outvote hundreds of accuracy benchmarks. The proposed fix is socio-technical: change the scoring to penalise confident errors more than abstentions. Not everyone accepts that this is the dominant cause versus a statistical lower bound on arbitrary-fact recall (which the same line of work also proves). Second, **whether verbalised confidence is fixable by training**: 2026 work reports large improvements — process supervision on confidence margins cutting ECE by up to 88%, `Abstain-R1`-style verifiable RL for calibrated abstention — while other 2026 work reports that models verbalise uncertainty and then **fail to act on it** (*Are LLM Decisions Faithful to Verbal Confidence?*, arXiv:2601.07767), meaning the number improves without the behaviour changing. Third, **whether entropy-family signals suffice**: *Entropy Alone is Insufficient for Safe Selective Prediction in LLMs* (arXiv:2603.21172) argues they miss confidently-wrong modes where all samples agree on the same falsehood, which is exactly the failure that matters most.

**Where it's heading.** High confidence: **selective prediction becomes a first-class product API** — response envelopes carrying an abstention decision and a calibrated risk tier rather than a raw score, and eval suites gating on coverage-at-risk instead of raw accuracy. High confidence: **eval reform lands partially**, with abstention-aware scoring appearing in major benchmarks because the argument is simple and the labs proposing it own the leaderboards. Medium confidence: **cheap internal-state probes replace sampling** for most production confidence, because 10x sampling cost is unacceptable in the hot path and probes are one extra matmul; the open question is whether probes trained on one distribution transfer to yours. Medium confidence: **conformal risk control gets used for real** in narrow, structured settings — it gives a distribution-free marginal coverage guarantee at level 1−α from a calibration split, which is exactly what a compliance conversation wants. Speculative, and flag it: conformal guarantees for open-ended generation. There are 2026 impossibility results (arXiv:2606.29054) showing the guarantee degrades or vanishes for structured/free-form outputs without strong assumptions, so treat "we'll wrap the LLM in conformal prediction and have a proof" as a research claim, not a design.

---

## Mental model

Two diagrams. The first is the reliability diagram — the only picture that makes "calibrated" concrete.

```
RELIABILITY DIAGRAM (bin by stated confidence, plot observed accuracy)

 accuracy
   1.0 ┤                                              ╱ ●  perfect
       │                                        ╱   ●        (on diagonal)
   0.8 ┤                                  ╱   ●
       │                            ╱   ●
   0.6 ┤                      ╱   ●
       │                ╱   ●                    ▲ ▲ ▲ ▲ ▲   TYPICAL LLM
   0.4 ┤          ╱   ●                                      verbalised conf:
       │    ╱   ●                                            everything lands
   0.2 ┤ ╱ ●                                                 in 0.8-1.0 and is
       │╱                                                    right ~55% of it
   0.0 ┼────┬────┬────┬────┬────┬────┬────┬────┬────┬────
      0.0  0.1  0.2  0.3  0.4  0.5  0.6  0.7  0.8  0.9  1.0
                          stated confidence

  gap in bin m = |acc(B_m) − conf(B_m)|      ECE = Σ_m (|B_m|/n) · gap_m
  OVERCONFIDENT = points BELOW the diagonal.  LLMs live bottom-right.
  Note: verbalised confidence barely populates bins 0.0-0.7 at all, which is
  itself the diagnosis — no resolution, so no threshold can separate anything.
```

The second is the risk-coverage curve, which is what you actually operate on.

```
SELECTIVE PREDICTION: pick an operating point, not a "confidence feature"

 error rate on ANSWERED items (selective risk)
  12% ┤                                                    ● 100% coverage
      │                                            ●            (answer all)
   8% ┤                                    ●
      │                            ●
   4% ┤                     ●
      │              ●                    ← SLO line: risk ≤ 2%
   2% ┼───────●───────────────────────────────────────────────
      │  ●
   0% ┼──┬────┬────┬────┬────┬────┬────┬────┬────┬────┬───
        10   20   30   40   50   60   70   80   90  100
                       coverage (% of queries answered)

  You do not ship "a confidence score". You ship ONE threshold τ chosen so
  that risk ≤ target on a held-out set, and you report the coverage you got.
  "≤2% error at 88% coverage" is a product SLO. "confidence: 0.92" is not.
  AURC = area under this curve = the signal's quality, threshold-free.
  A useless signal gives a FLAT curve: abstaining removes wrong and right
  answers at the same rate.
```

The one-line version: **calibration is about the numbers being honest; selective prediction is about the product doing something different when they are low.** Teams ship the first and forget the second, which is how you get a confidence field nobody reads.

---

## How it actually works

### Calibration, formally

A predictor with confidence `p̂` is **perfectly calibrated** if

```
P( Ŷ = Y  |  p̂ = p ) = p     for all p ∈ [0,1]
```

You cannot evaluate that conditional directly with finite data, so you bin:

```
ECE  = Σ_{m=1..M}  (|B_m| / n) · | acc(B_m) − conf(B_m) |      # weighted mean gap
MCE  = max_m | acc(B_m) − conf(B_m) |                           # worst bin
ACE  = same as ECE but with equal-MASS (adaptive) bins          # fixes empty bins
Brier= (1/n) Σ (p̂ᵢ − yᵢ)²                                       # proper scoring rule
     = reliability − resolution + uncertainty   (Murphy 1973)
```

Four things to know about ECE that get asked as follow-ups:

1. **It is not a proper scoring rule.** A model that always outputs the base rate has ECE 0 and is useless. ECE measures reliability only; you need **resolution** too, which is why you report Brier or NLL alongside, or read AURC off the risk-coverage curve.
2. **Bin count is a free parameter with no principled default** — M=10 and M=15 are both conventional (Guo et al. used 15). Fewer bins hide miscalibration. **Always report M.** If someone shows you an ECE without M, the number is unfalsifiable.
3. **Equal-width bins break on LLM verbalised confidence** because 90%+ of the mass lands in the top two bins and the rest are empty. Use equal-mass (adaptive) binning, or the number is dominated by one bin.
4. **ECE is estimated with downward bias** at small n and coarse binning, so cross-model ECE comparisons at different sample sizes are not comparable.

### Why LLMs are badly calibrated in verbalised confidence

Mechanically, three reasons, and you should give all three:

- **No training signal.** The tokens `"confidence": 0.9` are generated by the same next-token objective as everything else. There is no loss term comparing that number to the empirical outcome frequency. It is a *stylistic* prediction of what a confident-sounding answer looks like.
- **RLHF actively pushes the wrong way.** Human raters prefer decisive, complete answers; hedging is rated as unhelpful. So preference optimisation increases stated confidence independent of correctness. The GPT-4 report's calibration plots are the cleanest published evidence: near-diagonal pre-training, visibly overconfident after post-training.
- **The scoreboard rewards guessing.** Under binary accuracy scoring, abstaining scores 0 and guessing scores `p(correct) > 0`, so any training or selection process that optimises accuracy selects against abstention. This is the Kalai et al. argument, and the practical corollary is that you should expect models to guess *by default* and treat abstention as something you must build, not elicit.

Observable symptom in your own logs: **plot a histogram of the model's self-reported confidence. If more than ~80% of mass sits above 0.8 while your eval accuracy is 60%, the field is decorative.** That one plot is worth more than any amount of prompt tuning on the confidence instruction.

### Logprob-based confidence and its limits

For a generated sequence `y = y₁..y_T`:

```
logP(y|x)          = Σ_t log p(y_t | x, y_<t)        # penalises length, unusable raw
mean token logprob = (1/T) Σ_t log p(y_t | ...)      # length-normalised, common default
min token logprob  = min_t log p(y_t | ...)          # catches the one fabricated token
answer-span only   = restrict to the extracted answer tokens
```

What works and what does not:

| Setting | Signal | Quality |
|---|---|---|
| Multiple choice | logprob of each option letter, softmax over options | **Good.** This is the setting where pre-trained LLMs are genuinely well-calibrated |
| Classification / routing with a fixed label set | logprob over label tokens | **Good.** Recalibrate with temperature scaling on a validation split |
| Extraction ("what is the invoice number") | mean or min logprob over the extracted span | **Usable.** min-token is better at catching one hallucinated digit |
| Free-form answer | sequence-level logprob | **Poor.** See below |
| Long-form report | anything sequence-level | **Useless.** Aggregate over atomic claims instead |

The reason free-form fails is worth stating precisely, because it is the motivation for the next section: probability mass is spread over **surface forms**, not meanings. "Paris", "It's Paris", "The capital is Paris" are three sequences expressing one fact. A model that is *certain* of the fact may assign only 0.35 to each of three paraphrases, and a model that is *guessing between two different facts* may assign 0.5 to each. Sequence-level entropy cannot distinguish those. That is the whole insight.

A second practical limit: **API access.** OpenAI and several others expose top-k logprobs; some providers expose none, and reasoning models often do not expose logprobs for the thinking tokens. Design your confidence signal so it degrades to a sampling-based fallback rather than assuming logprobs exist.

### Semantic entropy

Farquhar, Kossen, Kuhn & Gal, *Detecting hallucinations in large language models using semantic entropy*, **Nature 630:625-630 (June 2024)**. The algorithm:

```
1. Sample n generations at T≈1.0 (n = 5-10 typical; the paper uses ~10).
2. Cluster them into semantic equivalence classes C by BIDIRECTIONAL entailment:
   a and b are in the same class iff  a ⊨ b  AND  b ⊨ a   (an NLI model, e.g.
   DeBERTa-MNLI-size, or an LLM asked to judge entailment both ways).
3. Discrete semantic entropy:
      SE = − Σ_{c ∈ C}  p(c) log p(c),      p(c) = |c| / n
   (the paper's length-normalised variant sums sequence likelihoods within each
   cluster instead of counting, which is better when logprobs are available)
4. High SE  → the model disagrees with itself about the MEANING → likely
   confabulation.  Low SE with a wrong answer → confidently wrong, which SE
   cannot catch, and that is the known hole.
```

Cost, which is the thing interviewers press on: **n forward passes plus up to O(n²) pairwise entailment checks**. At n=10 that is 10 generations (so 10x the token cost) and up to 45 NLI calls, though you can cut to O(n·|C|) by comparing each new sample only against one representative per existing cluster. A DeBERTa-size NLI model runs in roughly 10-40ms per pair on a single GPU, so the NLI cost is small; the sampling cost is not. Two mitigations: (a) reserve semantic entropy for the abstention decision on high-stakes queries only; (b) use **semantic entropy probes** (arXiv:2406.15927), a linear probe on hidden states trained to predict SE, which costs one forward pass and recovers much of the AUROC — the tradeoff being that a probe is fit to a distribution and may not transfer to yours.

Be honest about effectiveness numbers, because this is where people oversell. Reported AUROC for consistency-family detectors is strongly benchmark-dependent: SelfCheckGPT's best variant reports AUC-PR in the ~0.53-0.67 range on its original benchmark, and on harder 2026 benchmarks both SelfCheckGPT and semantic entropy have been reported near 0.58-0.60 AUROC — i.e. only modestly better than chance on adversarial sets, while performing far better on the confabulation-heavy sets they were designed for. The correct claim is *"semantic entropy is the strongest general-purpose unsupervised signal published and it is nowhere near a solved detector"*. Anyone quoting a single AUROC as if it generalises has not read the benchmarks.

### p(true) and self-evaluation

Ask the model, in a separate call, "Is the following answer to this question correct? Answer only True or False," and read the logprob of the `True` token. This often beats verbalised percentage confidence because it is a **single-token binary decision with logprob access**, which is the regime where LLM calibration is least bad. It is still overconfident, still needs temperature scaling on a validation split, and it costs an extra call. Useful as one input to an ensemble, not as the answer.

### Abstention policy: the decision, not the score

An abstention policy needs three inputs, and candidates usually name only the first:

1. **A confidence signal** `s ∈ ℝ` (any of the above, or an ensemble).
2. **The stake** of the query — a `read_only` lookup and a `financial` action do not share a threshold. Use the risk taxonomy from `T07-human-oversight`.
3. **What abstention costs**, i.e. what happens instead. Abstention is only a good move if there is a better next step: a clarifying question, a stronger model, a retrieval retry, a human, or a documented "we don't cover this".

The rule, per stake tier:

```
if s ≥ τ_answer[tier]:                    answer
elif s ≥ τ_flag[tier]:                    answer + mark unverified claims + offer sources
elif query is underspecified:              ask ONE clarifying question   ← highest-value tier
elif escalation available:                 route to stronger model / human
else:                                      decline with a reason and a next step
```

Note the ordering: the clarifying-question tier sits above declining, and it is the tier that recovers the most value. A large share of low-confidence cases in real products are not knowledge failures, they are **underspecified queries** — the AbstentionBench taxonomy explicitly separates unanswerable, underspecified, false-premise, subjective, and stale-information cases. A system that says "do you mean the 2025 or 2026 policy?" converts an abstention into an answer. A system that says "I don't know" throws the interaction away.

Thresholds are **calibrated, not chosen**: sweep `τ` on a held-out set, pick the smallest `τ` meeting your risk target, and report the coverage. Re-run that sweep on every model or prompt change, because a threshold is a property of the model+prompt+distribution triple, not a constant.

### Selective prediction and the coverage/accuracy curve

Definitions you should be able to write down (Chow, 1970 gives the classical rejection rule):

```
coverage        φ = (# answered) / n
selective risk  R = (# wrong among answered) / (# answered)
AURC            = area under the risk-coverage curve   (lower is better)
coverage@risk≤r = the max coverage achievable while keeping R ≤ r    ← the SLO
```

The property that makes this useful: **as you lower coverage, risk should fall**. If your curve is flat, your confidence signal has no resolution and abstention is discarding correct and incorrect answers at the same rate — a real and common outcome when the signal is verbalised confidence. Plot the curve before you argue about thresholds.

Two operating points to keep in mind: at 100% coverage `R` is just your error rate, and at very low coverage the estimate becomes noisy (below ~200 answered items the confidence interval on `R` swamps the number). Report `coverage@risk` with a bootstrap CI, not a point estimate.

### Conformal prediction, in one honest paragraph

Split conformal gives a **distribution-free marginal coverage guarantee**: hold out a calibration set, compute a nonconformity score `s` for each item, take the `⌈(n+1)(1−α)⌉/n` empirical quantile `q̂`, and the prediction set `{y : s(x,y) ≤ q̂}` contains the truth with probability ≥ 1−α, assuming exchangeability. For **classification and MCQ over LLM outputs this works and is worth doing**, because a guarantee is what compliance conversations want. Two caveats you must volunteer: the guarantee is **marginal, not conditional** — 90% coverage overall can be 99% on easy slices and 60% on the hard slice you care about — and it assumes exchangeability, which distribution shift breaks. For free-form generation there are 2026 impossibility and bounds results (arXiv:2606.29054) showing you cannot get the clean guarantee without extra assumptions. Say "conformal for the label-set decisions, calibrated thresholds for the generation" and you sound like you have used it.

### Communicating uncertainty without making the product feel broken

The failure mode on both sides is real. Hedge everything and the product reads as useless; hedge nothing and one caught error destroys trust in every prior answer. Four rules that hold up:

1. **Change the action, not the adjective.** Low confidence should produce a *different interaction* (a clarifying question, a source-first answer, a handoff), not the same answer wrapped in "I think" and "possibly". Adverbial hedging is the worst of both worlds: it costs trust and conveys nothing actionable.
2. **Do not show raw probabilities to lay users.** They are misread systematically, and a wrong answer labelled 73% is more damaging than an unlabelled one because it looks like the system knew. Use a small number of discrete states with different visual treatment and different affordances: *verified* (citation-backed, entailment-checked), *unverified* (answer shown, claims flagged, sources offered), *needs input* (one clarifying question), *out of scope* (decline + route).
3. **Asymmetric surfacing.** Do not annotate everything. Annotate only what failed verification. Constant labelling becomes wallpaper within a session — the same habituation that produces alert fatigue.
4. **Abstention needs a next step or it is a dead end.** "I don't know" is a bad product. "I can't confirm this from your policy documents; here are the two closest sections, or I can open a ticket with the billing team" is a good one. Same underlying decision, opposite user experience.
5. **Budget it.** Treat abstention rate as an SLO with an owner: e.g. *"≤2% incorrect answers at ≥88% coverage; abstention over 12% triggers a review of retrieval, not of the threshold."* Without a budget, every incident pushes the threshold up until the product stops answering.

One warning from the 2026 literature: models that verbalise uncertainty frequently **fail to act on it** (arXiv:2601.07767). Do not let the model decide whether to abstain inside its own answer text. Extract a signal, apply the threshold in your code, and let the harness own the decision. That is an architectural point and it lands well in interviews.

---

## Build it from scratch

Runnable. ECE with adaptive binning, temperature scaling, the risk-coverage curve, and threshold calibration to a risk target.

```python
"""Selective prediction toolkit. python 3.11+, numpy only.
    pip install numpy
    python selective.py
"""
from __future__ import annotations
import numpy as np


def ece(conf: np.ndarray, correct: np.ndarray, bins: int = 15,
        adaptive: bool = True) -> tuple[float, list[dict]]:
    """Expected calibration error. ALWAYS report `bins` alongside the number.
    adaptive=True uses equal-MASS bins, which is mandatory for LLM verbalised
    confidence (equal-width bins leave 13 of 15 empty)."""
    n = len(conf)
    order = np.argsort(conf)
    conf, correct = conf[order], correct[order].astype(float)
    if adaptive:
        edges_idx = np.linspace(0, n, bins + 1).astype(int)
        groups = [(edges_idx[i], edges_idx[i + 1]) for i in range(bins)]
    else:
        edges = np.linspace(0.0, 1.0, bins + 1)
        groups = [(int(np.searchsorted(conf, edges[i], "left")),
                   int(np.searchsorted(conf, edges[i + 1], "right"))) for i in range(bins)]
    total, rows = 0.0, []
    for lo, hi in groups:
        if hi <= lo:
            continue
        c, a = conf[lo:hi].mean(), correct[lo:hi].mean()
        w = (hi - lo) / n
        total += w * abs(a - c)
        rows.append({"n": hi - lo, "conf": round(c, 3), "acc": round(a, 3),
                     "gap": round(a - c, 3)})
    return total, rows


def mce(conf, correct, bins=15):
    _, rows = ece(conf, correct, bins)
    return max(abs(r["gap"]) for r in rows)


def brier(conf, correct):
    """Proper scoring rule. Report WITH ece: a constant predictor has ece≈0."""
    return float(np.mean((conf - correct.astype(float)) ** 2))


def fit_temperature(logits: np.ndarray, labels: np.ndarray,
                    grid=np.arange(0.05, 5.0, 0.01)) -> float:
    """Guo et al. 2017 temperature scaling: one parameter, fit on a HELD-OUT
    split by NLL. Works on any logit vector; the LLM analogue is the logits over
    a fixed label set (MCQ options, class tokens)."""
    def nll(T):
        z = logits / T
        z = z - z.max(axis=1, keepdims=True)
        logp = z - np.log(np.exp(z).sum(axis=1, keepdims=True))
        return -logp[np.arange(len(labels)), labels].mean()
    return float(min(grid, key=nll))


def risk_coverage(score: np.ndarray, correct: np.ndarray):
    """Sort by confidence DESC, answer the top-k, measure risk on answered."""
    order = np.argsort(-score)
    c = correct[order].astype(float)
    k = np.arange(1, len(c) + 1)
    risk = 1.0 - np.cumsum(c) / k
    return k / len(c), risk, score[order]


def aurc(score, correct) -> float:
    cov, risk, _ = risk_coverage(score, correct)
    return float(np.trapezoid(risk, cov))


def calibrate_threshold(score, correct, target_risk=0.02, min_answered=200):
    """The deliverable. Returns the LOWEST threshold meeting the risk target,
    plus the coverage you actually get. This pair IS your product SLO."""
    cov, risk, s_sorted = risk_coverage(score, correct)
    ok = (risk <= target_risk) & (np.arange(1, len(risk) + 1) >= min_answered)
    if not ok.any():
        return {"feasible": False, "best_risk_at_min_n": float(risk[min_answered - 1])
                if len(risk) >= min_answered else None}
    i = int(np.max(np.flatnonzero(ok)))          # largest coverage that still passes
    return {"feasible": True, "threshold": float(s_sorted[i]),
            "coverage": float(cov[i]), "risk": float(risk[i]),
            "n_answered": i + 1}


if __name__ == "__main__":
    rng = np.random.default_rng(7)
    n = 4000

    # --- signal A: a real signal (e.g. semantic-entropy-derived confidence) ---
    latent = rng.normal(size=n)                       # true difficulty
    correct = (rng.random(n) < 1 / (1 + np.exp(-1.6 * latent))).astype(int)
    good = 1 / (1 + np.exp(-1.3 * latent))            # informative, overconfident

    # --- signal B: LLM verbalised confidence, mass jammed into 0.8-1.0 ---
    verbalised = np.clip(rng.normal(0.90, 0.05, n), 0, 1)

    for name, s in [("semantic-entropy conf", good), ("verbalised conf", verbalised)]:
        e, rows = ece(s, correct, bins=15, adaptive=True)
        print(f"\n=== {name}")
        print(f"  accuracy {correct.mean():.3f}   mean conf {s.mean():.3f}")
        print(f"  ECE(M=15, adaptive) {e:.4f}   MCE {mce(s, correct):.4f}   "
              f"Brier {brier(s, correct):.4f}   AURC {aurc(s, correct):.4f}")
        print("  " + str(calibrate_threshold(s, correct, target_risk=0.10)))
        print("  worst bins:", sorted(rows, key=lambda r: -abs(r["gap"]))[:3])
```

Running it: the informative signal yields a downward-sloping risk-coverage curve and a feasible threshold at a real coverage number; the verbalised signal yields an **AURC close to the base error rate and no feasible threshold**, because abstaining removes right and wrong answers in the same proportion. That contrast is the whole module in one output, and it is the demo to describe in an interview.

Lab **`labs/py/23-trust-calibration/`** adds the semantic-entropy implementation with bidirectional-entailment clustering, `p(true)` elicitation, a split-conformal wrapper for MCQ, and a regression test asserting AURC does not degrade across prompt versions.

---

## How it's done in production

**Where the signal comes from.** In descending order of cost-effectiveness: (1) *provider-side grounding scores* — Bedrock Guardrails contextual grounding returns grounding and relevance scores with configurable thresholds and filters over 75% of hallucinated responses on RAG and summarisation workloads, which is the cheapest real signal for a RAG product; (2) *NLI entailment coverage* — the fraction of answer sentences entailed by retrieved context, which is a confidence signal and an attribution signal at once (`T07-attribution`); (3) *logprobs over a constrained label set* with temperature scaling for anything classification-shaped; (4) *semantic entropy* on high-stakes queries only; (5) *a judge model* as a second opinion, remembering the judge is also miscalibrated and correlated with the generator when it is the same family.

**Ensembling.** In practice a small logistic regression over 4-6 cheap features (entailment coverage, min-token logprob, retrieval top-1 score, retrieval score gap top1−top2, answer length, whether a tool errored) trained on a few thousand labelled production examples beats any single signal and costs nothing at inference. It also gives you a calibrated probability by construction. This is the highest-return engineering move in the whole module and almost nobody mentions it.

**Cascades.** Calibrated confidence is what makes model routing safe rather than a coin flip: answer with the cheap model when confidence is high, escalate to the expensive one below threshold. 2026 work on cost-optimal cascade routing (`UCCI`, arXiv:2605.18796) formalises this. The tradeoff is real: you pay the cheap model's cost on every query plus the expensive model's on the escalated fraction, so a cascade only wins if the escalation rate stays low and the cheap model's confidence signal has resolution. If escalation exceeds roughly 40-50%, just call the good model.

**What to log, per response** — non-negotiable, because you cannot calibrate what you did not record: the confidence signal(s) and version, the threshold and its version, the decision (answered / flagged / clarified / escalated / declined), the stake tier, and the downstream user action (accepted, edited, thumbs-down, escalated, abandoned). That last field is your label source. Without it you will be relitigating thresholds from anecdote forever.

### What breaks at scale

| Symptom | Cause | Fix |
|---|---|---|
| Confidence histogram is a spike at 0.9; threshold filters ~nothing | Verbalised confidence, no resolution | Replace with logprob/NLI/entropy signal; plot risk-coverage before shipping |
| Risk-coverage curve is flat | Signal uncorrelated with correctness | Do not ship abstention on it. Build the feature-ensemble signal instead |
| ECE looked great in eval, terrible in prod | Equal-width bins hid empty-bin structure, or calibration split came from the same prompt distribution as eval | Adaptive bins + report M + calibrate on a sample of production traffic |
| Abstention rate jumped from 6% to 24% overnight | Model version bumped behind an alias, or retrieval index rebuilt and scores shifted | Pin model@version; treat thresholds as versioned artefacts re-fit per model; alert on abstention-rate delta |
| Users learn to rephrase until the bot answers | "Abstention shopping" — threshold applied per turn with no memory | Track abstentions per session+topic; after 2 abstentions on the same topic, escalate instead of re-answering |
| Reasoning-model upgrade increased confident errors | Reasoning fine-tuning degrades abstention (AbstentionBench) | Re-fit thresholds; add abstention cases to the regression suite as a gate |
| Cascade cost went up, not down | Escalation rate too high because the cheap model's confidence has no resolution | Measure escalation rate; above ~40-50% the cascade loses to calling the strong model directly |
| Semantic entropy misses a whole class of errors | All samples agree on the same false answer (low entropy, wrong) | Add a grounding/entailment check against retrieval; entropy alone is insufficient (arXiv:2603.21172) |
| p99 latency tripled after adding confidence | Sampling n=10 in the hot path | Entropy probes or provider grounding score in-path; sampling only for high-stake tiers or async |

---

## Tradeoffs & when NOT to use it

- **Do not add abstention to a low-stakes, high-volume feature.** For autocomplete, tagging, or search suggestions the cost of a wrong suggestion is one ignored suggestion, and the cost of abstaining is a feature that looks dead. Abstention earns its keep where an error is expensive and a handoff exists.
- **Abstention without a fallback is worse than a hedged answer.** If there is no human, no stronger model, and no clarifying question available, "I don't know" is just a failed request with extra latency. Build the fallback first, then the threshold.
- **Do not ship a numeric confidence to end users.** Probabilities are systematically misread, and a labelled wrong answer damages trust more than an unlabelled one because the label implies the system knew. Discrete states with different affordances, or nothing.
- **A calibrated benchmark number does not transfer.** ECE measured on MMLU or TriviaQA says almost nothing about your domain. Calibration is a property of model+prompt+distribution; re-measure on your traffic, and re-measure after every prompt change. Anyone who quotes a paper's ECE as their system's ECE is bluffing.
- **Do not let the model decide whether to abstain in its own prose.** 2026 work shows verbalised uncertainty does not reliably translate into behaviour. Extract the signal, threshold in code, own the decision in the harness.
- **Sampling-based confidence is often unaffordable.** n=10 semantic entropy is a 10x token bill and a serial latency hit. If your product is a 200ms interaction, this is not a design option, and saying so is better than proposing it and being asked for the p99.
- **Self-consistency and entropy are blind to systematic error.** If the model reliably believes something false, every sample agrees and entropy is near zero. Grounding checks catch this class; entropy never will. This is the single most important limitation to volunteer.
- **Over-tuned thresholds are a fairness risk.** A global threshold meeting 2% risk overall can carry 8% risk on a minority slice, because marginal calibration is not conditional calibration. If your decisions affect people, report risk per slice or you have shipped a disparate error rate.

---

## Interview questions

### Q1 — What does it mean for a model to be calibrated, and how do you measure it?
**Testing:** whether you can state the definition formally.
**Answer:** Calibrated means `P(Ŷ = Y | p̂ = p) = p` for all p — of all the times it says 80%, it is right 80% of the time. You cannot evaluate that conditional directly, so you bin predictions by stated confidence and compare per-bin accuracy to per-bin mean confidence: `ECE = Σ_m (|B_m|/n)·|acc(B_m) − conf(B_m)|`, typically M=10 or 15, plus MCE for the worst bin. Overconfidence shows as points below the diagonal on a reliability diagram, which is where essentially all deep models and all RLHF'd LLMs sit.
**Follow-up trap:** *"What is wrong with ECE as your only metric?"* — it is not a proper scoring rule. A model that always outputs the base rate is perfectly calibrated and completely useless, because it has no *resolution*. Report Brier or NLL alongside, and report AURC off the risk-coverage curve since that is what your product actually depends on. Also: bin count is a free parameter, ECE is downward-biased at small n, and equal-width bins are meaningless for LLM verbalised confidence because everything lands in the top two bins.

### Q2 — Why are LLMs poorly calibrated when they state a confidence in words?
**Testing:** mechanism, not just the observation.
**Answer:** Three reasons. There is no training signal: the tokens `0.9` are produced by next-token prediction with no loss comparing them to observed outcome frequency, so it is a stylistic prediction of what confident text looks like. RLHF pushes the wrong way, because raters prefer decisive answers and penalise hedging, so post-training increases stated confidence independent of correctness — the GPT-4 technical report's calibration plots show a near-diagonal pre-trained model and a visibly overconfident post-trained one. And the evaluation ecosystem rewards guessing: binary accuracy gives 0 for abstaining and positive expected value for a guess, which is the Kalai et al. argument in *Why Language Models Hallucinate* and the follow-on *Nature* paper. Empirically the mass sits in 0.8-1.0 with ECE ranging from ~0.05 on constrained JSON to ~0.61 on open-domain QA.
**Follow-up trap:** *"Can you fix it with a better prompt?"* — marginally and unreliably. Asking for a number in a rubric, or asking for `p(true)` as a single token whose logprob you read, both help because you move toward the regime where LLM calibration is least bad. What actually fixes it is a post-hoc calibrator: fit a mapping from your signal to probability on held-out data, and re-fit per model version. Prompting cannot create resolution that is not in the signal.

### Q3 — I have logprobs. Is that my confidence?
**Testing:** whether you know the surface-form problem.
**Answer:** For constrained outputs, largely yes — logprob over multiple-choice option letters or over a fixed label set is the setting where LLMs are genuinely usable, and temperature scaling on a validation split cleans it up further. For free-form generation, no, and the reason is that likelihood is over surface forms, not meanings. "Paris", "It's Paris", and "The capital is Paris" split the mass three ways for a model that is completely certain, while a model torn between two different facts might put 0.5 on each. So sequence entropy conflates *linguistic* variation with *epistemic* uncertainty. Practical partial fixes: length-normalise, use min-token logprob to catch a single fabricated digit or name, and restrict to the extracted answer span rather than the whole response.
**Follow-up trap:** *"So what would you use for free-form?"* — semantic entropy: sample n≈10 at temperature 1, cluster by bidirectional entailment into meaning classes, take entropy over the clusters. That is the *Nature* 2024 method and it directly targets the surface-form problem. Then immediately give the cost: 10x generations plus up to O(n²) NLI calls, which is why it goes on high-stake queries or behind a hidden-state probe, not in a 200ms path.

### Q4 — Explain semantic entropy and where it fails.
**Testing:** depth on the reference method, and honesty about its hole.
**Answer:** Sample n generations at T≈1, cluster them by bidirectional entailment (a and b are equivalent iff each entails the other), then compute `−Σ p(c) log p(c)` over clusters with `p(c)` from cluster mass or summed sequence likelihoods. High entropy means the model disagrees with itself about the *meaning* of its answer, which correlates with confabulation. Cost is n forward passes plus pairwise entailment, reducible to O(n·|C|) by comparing each sample only against one representative per existing cluster; the NLI model itself is cheap at ~10-40ms per pair. Where it fails, and this is the important half: **low entropy with a wrong answer**. If the model reliably believes something false, all n samples agree, entropy is near zero, and semantic entropy is silent. 2026 work makes this explicit — entropy alone is insufficient for safe selective prediction. So you pair it with a grounding check against retrieved evidence, which catches exactly the systematic-error class entropy cannot.
**Follow-up trap:** *"What AUROC should I expect?"* — refuse the single number. It is strongly benchmark-dependent: strong on the confabulation-heavy sets it was designed for, and reported near 0.58-0.60 on harder 2026 benchmarks where SelfCheckGPT's best variant sits at ~0.58 too and its original AUC-PR was ~0.53-0.67. Quote a range with the benchmark named or you are overselling.

### Q5 — Design abstention for a customer-support assistant. Give me numbers.
**Testing:** whether you can turn this into a product spec.
**Answer:** First, the SLO, agreed with the business, not invented by me: *≤2% incorrect answers on answered queries at ≥88% coverage*, with a separate hard rule that any query touching billing amounts, cancellations, or legal terms is a `financial` tier requiring higher confidence or a human. Signal: a logistic regression over cheap features — NLI entailment coverage of answer sentences against retrieved docs, retrieval top-1 score, the top1−top2 score gap, min-token logprob on the answer span, and whether any tool errored — trained on ~3-5k production examples labelled by downstream user action. Threshold: sweep on a held-out set, take the lowest τ hitting 2% risk with at least 200 answered items in the estimate, report the coverage you got, bootstrap a CI on it. Behaviour below threshold, in order: if the query is underspecified, ask exactly one clarifying question; else escalate to the stronger model; else hand to a human with the trace attached; else decline with the closest documentation sections and a ticket offer. Monitoring: abstention rate as a dashboard SLI with an alert on a >4-point week-over-week move, plus risk per intent slice, because a global 2% can hide 8% on one intent.
**Follow-up trap:** *"Abstention rate hits 30% after a model upgrade. What do you do?"* — do not touch the threshold first; that hides the regression. Diagnose in order: did the model alias move (pin versions), did retrieval change (index rebuild shifting score distributions), or did the model genuinely get worse at abstaining — which is a documented effect, since AbstentionBench found reasoning fine-tuning *degrades* abstention. Then re-fit the threshold on fresh labelled data as a versioned artefact and add the failing cases to the regression gate. Threshold constants that are not versioned per model are a latent outage.

### Q6 — What is the risk-coverage curve and what does a flat one tell you?
**Testing:** whether you think in operating points.
**Answer:** Sort predictions by confidence descending, answer the top-k, and plot error rate among answered (selective risk) against the fraction answered (coverage). A good signal gives a monotonically falling curve as coverage drops; AURC is the threshold-free summary and `coverage@risk≤r` is the number you put in the SLO. A flat curve means the signal has no resolution: abstaining discards correct and incorrect answers in the same proportion, so you are buying nothing with the coverage you gave up. That is the actual outcome when teams threshold on verbalised confidence, and plotting this curve is the cheapest way to kill a bad confidence feature before it ships.
**Follow-up trap:** *"You get risk ≤ 1% at 40% coverage. Ship it?"* — depends entirely on what happens to the other 60%, and on the cost asymmetry. If those 60% go to a human queue that cannot absorb them, you have moved the failure, not fixed it. If the alternative to answering is a documentation link and the errors were legally expensive, 40% coverage may be great. Also check the low-coverage estimate's confidence interval — below a couple of hundred answered items the risk number is noise.

### Q7 — Does conformal prediction solve this?
**Testing:** calibration about a fashionable technique.
**Answer:** Partly, in narrow settings. Split conformal gives a distribution-free **marginal** coverage guarantee at level 1−α from a calibration split under exchangeability: compute nonconformity scores, take the `⌈(n+1)(1−α)⌉/n` quantile, emit the prediction set below it. For MCQ, classification, and routing decisions over LLM outputs this genuinely works and it is the only thing in the toolkit that gives a *guarantee*, which matters in compliance conversations. Two caveats I would volunteer: the guarantee is marginal, not conditional, so 90% overall can be 60% on the slice you care about, and exchangeability fails under distribution shift, which is the normal state of production traffic. For open-ended generation there are 2026 impossibility and bounds results showing you cannot get the clean guarantee for structured or free-form outputs without strong extra assumptions.
**Follow-up trap:** *"So the guarantee is worthless in production?"* — no, it is *conditional on assumptions you must monitor*. The engineering response is to re-calibrate on a rolling window of recent traffic, monitor the empirical coverage against the nominal 1−α as a drift alarm, and stratify calibration by slice to approximate conditional coverage. That turns a fragile theorem into a usable control.

### Q8 — How do you show uncertainty to users without making the product feel broken?
**Testing:** product judgment, the part most engineers skip.
**Answer:** Change the action, not the adjective. Adverbial hedging on every sentence costs trust and conveys nothing actionable; the low-confidence path should produce a *different interaction*. Concretely, four discrete states with different affordances: **verified** (citation-backed and entailment-checked, shown plainly), **unverified** (answered, but the specific unsupported sentences are marked and sources offered), **needs input** (exactly one clarifying question), **out of scope** (decline plus the nearest documentation plus an escalation path). No raw percentages for lay users, because they are systematically misread and a labelled wrong answer damages trust more than an unlabelled one. Annotate asymmetrically — flag only what failed verification, since constant labelling becomes wallpaper the same way alerts do. And treat abstention rate as a budgeted SLO so incidents do not ratchet the threshold up until the product stops answering.
**Follow-up trap:** *"Your ratings drop after you add uncertainty UI. What now?"* — first check whether abstention rate rose or only the labelling did; those need opposite fixes. If it is labelling, you are probably annotating too much and it reads as the system doubting itself, so restrict flags to failed verifications. If it is abstention, the threshold is too tight or the fallbacks are dead ends, and the fix is better fallbacks — clarifying questions convert abstentions into answers, whereas "I don't know" converts them into churn. What I would not do is remove the honesty signal to recover a rating; I would take that tradeoff to whoever owns the risk, with the risk-coverage curve in hand.

### Q9 — Your model is confidently wrong on a whole category of questions. Which detector catches it?
**Testing:** whether you know the blind spot of the consistency family.
**Answer:** None of the self-consistency family. Semantic entropy, SelfCheckGPT, and sampling variance all measure *disagreement between samples*; a systematic false belief produces agreement, so entropy is near zero and every consistency detector is silent. What catches it: grounding against an external source — NLI entailment of each claim against retrieved evidence, or a tool/database lookup, or formal verification where the domain is formalisable, e.g. Bedrock Automated Reasoning checks. Additionally, offline: an eval set built specifically from the category, because once you know the category exists, detection is a regression test, not an uncertainty problem.
**Follow-up trap:** *"How would you have discovered the category in the first place?"* — not from confidence signals. From downstream signals: thumbs-down clustering, edit-distance between the model's answer and the human's final answer grouped by topic, escalation reasons, and support tickets. Cluster those in embedding space and the category shows up as a dense blob. Confidence signals find *unknown unknowns per query*; production feedback finds *known unknowns per topic*, and you need both.

### Q10 — What is `p(true)` and why might it beat asking for a percentage?
**Testing:** breadth on elicitation methods.
**Answer:** A second call that presents the question and the candidate answer and asks for a single token, True or False, and you read the logprob of `True` as the confidence. It tends to beat verbalised percentages because you have moved into the regime where LLM calibration is least bad — a single-token binary decision with logprob access — instead of asking the model to generate a number that has no training signal attached. It is still overconfident, so temperature-scale it on a validation split, and it costs an extra call. I would use it as one feature in an ensemble rather than as the confidence.
**Follow-up trap:** *"Same model or a different one?"* — a different model, or at minimum a different family, if you can afford it. Self-evaluation with the same weights shares the same false beliefs, so errors are correlated and the ensemble gains less than the arithmetic suggests. This is the same correlation problem as LLM-as-judge with the generator's own family.

### Q11 — You are asked to put a confidence score in the public API response. What do you push back on?
**Testing:** interface design and long-term thinking.
**Answer:** I would not expose a raw score, because the moment it is in a public contract, downstream teams threshold on it and I can never change its distribution — a model upgrade that improves accuracy but shifts the score distribution silently breaks every consumer's threshold. What I would expose instead: a **decision** and a **stable tier** — `{"status": "answered" | "answered_unverified" | "needs_input" | "declined", "risk_tier": "low"|"medium"|"high", "unsupported_claims": [...], "evidence": [...]}` — plus a documented statement of what the tiers mean operationally ("high risk tier: measured ≤2% error on this class"). That keeps the calibration decision on my side of the boundary, where I can re-fit thresholds per model version without breaking consumers.
**Follow-up trap:** *"A partner insists on a number."* — give a number with a versioned semantic contract: `confidence_version: "v3"`, documented as "calibrated so that bucket 0.8-0.9 has measured accuracy 0.8-0.9 on distribution X as of date Y", with a commitment to bump the version on any re-fit and to publish the reliability diagram. That is defensible. An undocumented float is a future incident.

### Q12 — How does abstention interact with an agent loop rather than a single answer?
**Testing:** transfer to the domain he claims expertise in.
**Answer:** Three differences. First, abstention becomes **per step**, and the useful action is usually not "stop" but "gather more" — retry retrieval with a rewritten query, call a different tool, ask the user one question — so the low-confidence branch should route back into the loop with a budget decrement, not out of it. Second, **confidence compounds badly**: at ten steps and 95% per-step reliability the run succeeds ~60% of the time, so a per-step threshold that looks generous is not, and you need a run-level check before any irreversible action rather than only per-step checks. Third, **the abstention decision belongs to the harness, not the model**, since 2026 work shows models verbalise uncertainty and then act anyway; the loop should extract a signal and gate the tool call in code. Practically: gate on confidence *before* side-effecting tools, allow free retries only on read-only tools, cap total gathering steps, and on exhaustion emit a structured "insufficient evidence" observation with what was tried — which is both an honest output and a good trace.
**Follow-up trap:** *"Where do you put the threshold in a multi-agent system?"* — at every boundary where a subagent's output becomes another agent's input, because a confident-looking summary from a subagent launders away the uncertainty of everything upstream. The subagent's return contract should carry its own coverage/abstention state, and the supervisor should treat an unverified subagent claim as unverified rather than as fact. Losing uncertainty at handoff is the characteristic multi-agent failure.

### Q13 — Rank interventions by how much they improve calibration per unit of effort.
**Testing:** prioritisation, and whether you have done this rather than read about it.
**Answer:** 1) **Plot the histogram and the risk-coverage curve on your current signal** — an afternoon, and it frequently kills a planned feature or reveals you already have a usable signal. 2) **Log the downstream user action** per response, because that is your label source and without it everything else is guesswork. 3) **Fit a small logistic regression over 4-6 cheap features** you already compute (entailment coverage, retrieval top-1 and top1−top2 gap, min-token logprob, tool-error flag) — a few days, calibrated by construction, and it beats every single signal. 4) **Temperature-scale anything with a fixed label set** — one parameter, held-out split, near-free. 5) **Semantic entropy on the high-stakes tier only** — real gains on confabulation, 10x cost, so scope it. 6) **Conformal wrapping of label-set decisions** where a guarantee has organisational value. Dead last: prompt-engineering the model into stating better percentages. It is the first thing everyone tries and the lowest-yield thing on the list.
**Follow-up trap:** *"Why is the logistic regression above semantic entropy?"* — because it is cheap enough to run on every request, its features are already computed by the pipeline, and it is trained on *your* distribution, which is where calibration lives. Semantic entropy is a better *unsupervised* signal and a worse *engineering default*. If I have labels, supervised beats unsupervised; semantic entropy earns its place on the queries where labels do not exist yet and the stake justifies 10x sampling.

---

## Red flags that fail you

- Reporting ECE without saying how many bins, or treating ECE as sufficient on its own.
- Saying "we ask the model for a confidence score" with no reliability diagram and no threshold calibration.
- Not knowing that RLHF degrades calibration relative to the pre-trained model.
- Claiming logprobs are semantic confidence for free-form generation.
- Proposing semantic entropy without stating the ~10x sampling cost, or without naming its blind spot for confidently-wrong answers.
- Treating abstention as free: no fallback, no coverage number, no owner for the abstention rate.
- Exposing a raw confidence float in a public API with no version and no documented semantics.
- Claiming conformal prediction gives a guarantee, without mentioning marginal-versus-conditional coverage or exchangeability.
- Showing users raw percentages, or hedging every sentence and calling it transparency.
- Assuming a reasoning model abstains better. AbstentionBench found reasoning fine-tuning makes it worse.
- Letting the model decide in its own prose whether to abstain, instead of gating in the harness.

## Cheat card

```
CALIBRATED   P(Ŷ=Y | p̂=p) = p         reliability diagram: below diagonal = overconfident
ECE = Σ_m (|B_m|/n)·|acc(B_m) − conf(B_m)|   M=10 or 15 — ALWAYS state M
  MCE = worst bin · ACE = equal-MASS bins (mandatory for LLM verbalised conf)
  ECE is NOT a proper scoring rule → report Brier/NLL too (constant predictor: ECE≈0)
  ECE is downward-biased at small n; cross-model comparison needs equal n + equal M

WHY LLMs MISCALIBRATED (verbal)
  no loss term on the confidence token · RLHF rewards decisiveness · accuracy
  scoreboards pay for guessing (Kalai et al. arXiv:2509.04664 + Nature 2026)
  GPT-4 tech report: near-diagonal pre-training, overconfident after post-training
  measured: mass in 0.8-1.0; ECE ≈0.05 (JSON) … 0.61 (NQ-Open) — ConfidenceBench 2607.20526

SIGNALS, cheap→expensive
  provider grounding score (Bedrock ctx grounding: >75% of hallucinations filtered)
  NLI entailment coverage of answer sentences vs retrieved docs
  logprobs: MCQ/label-set GOOD · min-token catches one bad digit · free-form POOR
           (mass splits over PARAPHRASES, not meanings)
  p(true): 2nd call, single True/False token, read logprob — beats verbalised %
  SEMANTIC ENTROPY (Nature 630:625-630, 2024): sample n≈10 @T=1 → cluster by
    BIDIRECTIONAL entailment → SE = −Σ p(c) log p(c);  cost 10x gens + O(n²) NLI
    (reduce to O(n·|C|) w/ one representative per cluster; NLI ~10-40ms/pair)
    probes (2406.15927) approximate SE from hidden states in 1 forward pass
  BEST DEFAULT: logistic regression over 4-6 cheap features, trained on YOUR labels
  temperature scaling (Guo 2017, 1706.04599): one param T, fit on held-out NLL

BLIND SPOT  all consistency methods are silent on CONFIDENTLY WRONG (samples agree)
            → needs grounding/entailment/formal verification, not entropy
            arXiv:2603.21172 "entropy alone is insufficient"

SELECTIVE PREDICTION
  coverage φ = answered/n · selective risk R = wrong/answered · AURC = area
  FLAT risk-coverage curve = signal has NO resolution = do not ship abstention
  deliverable = ONE calibrated τ + stated SLO: "≤2% error at ≥88% coverage"
  need ≥ ~200 answered items before the risk estimate means anything
  marginal ≠ conditional: check risk PER SLICE or you shipped disparate error

ABSTENTION LADDER (in order)
  answer → answer+flag unsupported → ASK ONE CLARIFYING QUESTION → escalate → decline+route
  underspecified ≫ unanswerable in real traffic; clarify recovers coverage
  AbstentionBench 2506.09038: 20 datasets/35k queries; scaling doesn't help;
    REASONING FINE-TUNING DEGRADES ABSTENTION
  thresholds are versioned artefacts per model+prompt+distribution — re-fit on upgrade
  harness owns the decision, not the model's prose (arXiv:2601.07767)

CONFORMAL  split conformal: q̂ = ⌈(n+1)(1−α)⌉/n quantile of nonconformity → set covers ≥1−α
  MARGINAL not conditional · assumes exchangeability · works for MCQ/labels
  free-form: 2026 impossibility/bounds results (2606.29054) — not a design

UX  change the ACTION not the adjective · no raw % to lay users
    4 states: verified / unverified+flags / needs-input / out-of-scope+route
    flag ONLY failed verifications (constant labels → wallpaper, cf. alert fatigue)
    abstention rate = budgeted SLO with an owner
CASCADE  escalate below τ; if escalation rate >40-50% just call the strong model
LOG PER RESPONSE  signal+version · threshold+version · decision · stake tier ·
                  downstream user action ← this is your label source
```

## Sources

- [Detecting hallucinations in large language models using semantic entropy (Farquhar et al., Nature 630:625-630, 2024)](https://www.nature.com/articles/s41586-024-07421-0) — accessed 2026-07-26
- [Semantic Entropy Probes: Robust and Cheap Hallucination Detection in LLMs (arXiv:2406.15927)](https://arxiv.org/pdf/2406.15927) — accessed 2026-07-26
- [Why Language Models Hallucinate (Kalai, Nachum, Vempala & Zhang, arXiv:2509.04664)](https://arxiv.org/pdf/2509.04664) — accessed 2026-07-26
- [Evaluating large language models for accuracy incentivizes hallucinations (Nature, 2026)](https://www.nature.com/articles/s41586-026-10549-w) — accessed 2026-07-26
- [On Calibration of Modern Neural Networks (Guo et al., arXiv:1706.04599)](https://arxiv.org/abs/1706.04599) — accessed 2026-07-26
- [GPT-4 Technical Report (arXiv:2303.08774) — calibration on MMLU, pre- vs post-training](https://arxiv.org/pdf/2303.08774) — accessed 2026-07-26
- [AbstentionBench: Reasoning LLMs Fail on Unanswerable Questions (arXiv:2506.09038)](https://arxiv.org/html/2506.09038v1) — accessed 2026-07-26
- [ConfidenceBench: Evaluating Confidence Calibration in Large Language Models (arXiv:2607.20526)](https://arxiv.org/html/2607.20526) — accessed 2026-07-26
- [Are LLM Decisions Faithful to Verbal Confidence? (arXiv:2601.07767)](https://arxiv.org/html/2601.07767v1) — accessed 2026-07-26
- [Entropy Alone is Insufficient for Safe Selective Prediction in LLMs (arXiv:2603.21172)](https://arxiv.org/pdf/2603.21172) — accessed 2026-07-26
- [When Can Conformal Risk Control Certify LLM Outputs? Bounds, Impossibility, and Adaptation for Structured Generation (arXiv:2606.29054)](https://arxiv.org/html/2606.29054v1) — accessed 2026-07-26
- [UCCI: Calibrated Uncertainty for Cost-Optimal LLM Cascade Routing (arXiv:2605.18796)](https://arxiv.org/pdf/2605.18796) — accessed 2026-07-26
- [SelfCheckGPT — method summary and reported AUC-PR](https://npnkhoi.github.io/2024/08/26/selfcheckgpt.html) — accessed 2026-07-26
- [Amazon Bedrock Guardrails — contextual grounding checks](https://aws.amazon.com/bedrock/guardrails/) — accessed 2026-07-26
- [CURE 2026: Communicating Uncertainty to foster Realistic Expectations via Human-Centered Design](https://cureworkshop.github.io/cure-2026/) — accessed 2026-07-26

## Changelog
- 2026-07-26 — created
