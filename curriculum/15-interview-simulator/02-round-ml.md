# Boss: ML/DL Depth Round

> **Track:** T15 Interview Simulator · **Time:** 1h · **Prereqs:** none · **Updated:** 2026-08-01
> **Module id:** `T15-round-ml` · **Tags:** boss

**Runs under `tutor-mock` as round type `ai-depth` (classical ML + DL half).**

## The round in 30 seconds

45 minutes of classical ML and deep learning pushed to derivation, not definition. This screens for whether the candidate actually understands the mechanism behind the vocabulary they use daily, or has learned to say "bias-variance tradeoff" and "regularization" as retrieval cues without being able to derive either on a whiteboard. A pass looks like: deriving why L2 regularization is equivalent to a Gaussian prior on the weights, explaining precisely why AUC can be a misleading metric under class imbalance with a worked numeric example, and walking through backprop through at least one nontrivial layer without reaching for "the chain rule handles it." A fail looks like reciting definitions that were true five years ago as if they are unconditional facts, or answering "why does XGBoost usually beat a random forest" with "it's boosting, so it's better" instead of naming the bias-reduction mechanism.

## Format

- **45 minutes**, no coding, no whiteboard diagram requirement — this is a derivation-and-discussion round, verbal or on a shared doc for equations.
- **Minute-by-minute shape:**
  - 0:00–5:00 — warmup calibration: 1-2 fast factual questions to establish baseline (bias/variance, what a confusion matrix cell means) — not scored heavily, used to set the difficulty ramp.
  - 5:00–20:00 — classical ML depth: regularization, ensembles, metrics, feature engineering judgment.
  - 20:00–38:00 — deep learning depth: backprop, activations, architectures (CNN/RNN/Transformer), training pathologies.
  - 38:00–45:00 — one open-ended "which model would you pick and why" scenario question, then close.
- **What the interviewer does:** asks for derivations, not definitions ("derive the L2 gradient update, don't just say it shrinks weights"); asks for a numeric worked example when a metric is claimed to be misleading; pushes for the mechanism behind any comparative claim ("boosting reduces bias — through what mechanism, specifically?").
- **What the interviewer does not do:** accept "it depends" as a complete answer without a follow-up demanding what it depends on; let a wrong derivation pass uncorrected if the candidate doesn't self-correct; confirm correctness mid-answer.
- Calibrated upward from a typical mid-level round: definitions alone score no better than a 2/5 on Correctness/depth even when accurate, because a definition is not a derivation.

## What is actually being tested

1. **Mechanism over vocabulary.** Whether "regularization prevents overfitting" comes with the actual gradient-level mechanism (L2 shrinks weights proportionally, is equivalent to a zero-mean Gaussian prior via MAP estimation; L1 induces sparsity because its subgradient is constant magnitude, pushing small weights exactly to zero) or stops at the vocabulary.
2. **Numeric literacy about metrics.** Whether the candidate can construct a concrete confusion matrix where AUC looks great and the model is useless in production (severe class imbalance, e.g., 1:10,000 fraud rate), rather than just stating "AUC lies under imbalance" as received wisdom.
3. **Derivation stamina.** Whether backprop through a specific layer (a single sigmoid neuron, or a 2-layer network) can be walked through step by step under a bit of pressure, including correctly identifying where the vanishing-gradient problem originates mechanically (repeated multiplication of derivatives less than 1 in the chain rule, specifically the sigmoid's max derivative of 0.25).
4. **Architecture judgment, not architecture trivia.** Whether "why a Transformer over an RNN for this sequence task" comes with the actual mechanism (parallelizable training via no sequential dependency, O(1) path length between any two tokens vs. RNN's O(n), at the cost of O(n²) attention memory) rather than "Transformers are the state of the art now."
5. **Honest uncertainty.** Whether the candidate says "I'd need to check empirically" for genuinely open questions (does dropout or batch norm matter more for this specific architecture) instead of asserting a confident answer to a question that doesn't have one context-free answer.

## Question bank

### Warmup

**Q1 — Explain the bias-variance tradeoff, and give a numeric example of each failure mode.**
- **Strong:** Decomposes expected test error into bias² + variance + irreducible noise, states the decomposition (`E[(y - f̂(x))²] = Bias[f̂(x)]² + Var[f̂(x)] + σ²`), gives a concrete pair: a linear model on clearly nonlinear data (high bias, underfits both train and test) versus a depth-20 decision tree with no pruning (high variance, near-zero train error, high test error).
- **Weak:** "High bias means underfitting, high variance means overfitting" with no decomposition and no numeric example — a definition, not a derivation.
- **Follow-up trap:** *"Your model has 2% train error and 25% test error. Is that bias or variance, and what's your first move?"* Wants: variance (the gap, not the absolute train error, is diagnostic), first move is more data or regularization, not a bigger model.

**Q2 — What does an ROC curve actually plot, and derive AUC's interpretation as a probability.**
- **Strong:** True positive rate vs. false positive rate at every threshold; AUC equals the probability that a randomly chosen positive example is ranked above a randomly chosen negative example (the Mann-Whitney U statistic connection).
- **Weak:** "AUC tells you how good the model is, higher is better" with no threshold-sweep mechanism and no probabilistic interpretation.
- **Follow-up trap:** *"Two models have identical AUC of 0.90. Can they still have very different production behavior at your actual operating threshold?"* Yes — AUC aggregates over all thresholds, so two curves can cross and have equal area while one is far better at the specific threshold you'll actually deploy at. This is the real answer to "why AUC lies."

### Mid

**Q3 — Derive why AUC can be misleading under severe class imbalance, with numbers.**
- **Strong:** Constructs a matrix: 10,000 negatives, 100 positives (1% base rate). A model with 95% TPR and 20% FPR gets AUC that still looks decent, but at that FPR you flag 2,000 negatives to catch 95 positives — precision of ~4.5%. AUC does not see the imbalance because both axes are rates within their own class; precision does, because it's conditioned on all flagged predictions. Concludes: use PR-AUC or precision@threshold for rare-event detection, not ROC-AUC.
- **Weak:** "AUC lies with imbalanced data" stated as a fact with no constructed example and no alternative metric named with a reason.
- **Follow-up trap:** *"Your fraud model has PR-AUC of 0.6 and everyone says that's bad. Is it?"* Depends on the base rate — PR-AUC's baseline (a random classifier) equals the positive class prevalence, so 0.6 against a 0.1% base rate is dramatically better than 0.6 against a 40% base rate. Tests whether the candidate anchors metrics to their baseline rather than to an absolute number.

**Q4 — Derive the L2-regularized linear regression gradient update and connect it to a Bayesian prior.**
- **Strong:** Writes the loss `L = ||y - Xw||² + λ||w||²`, derives the gradient `∇L = -2Xᵀ(y - Xw) + 2λw`, and connects to MAP estimation: minimizing this loss is equivalent to MAP estimation with a zero-mean Gaussian prior on `w` with variance `σ²/λ`. States that larger λ corresponds to a tighter (more confident) prior that weights should be near zero.
- **Weak:** "L2 adds a penalty on large weights to prevent overfitting" — correct but stops before the derivation, and can't produce the actual gradient term.
- **Follow-up trap:** *"Why doesn't L2 produce sparse weights the way L1 does — derive it from the two subgradients."* L2's gradient at w is proportional to w itself (shrinks proportionally, never reaches exactly zero for finite λ); L1's subgradient is a constant `±λ` regardless of magnitude, which can drive a small weight exactly to zero once the loss gradient can no longer counteract that constant pull. This is a mechanism question, not a memorized fact.

**Q5 — Why does gradient boosting typically beat a random forest on tabular data, and when does it not?**
- **Strong:** Random forest reduces variance via bagging + feature subsampling on high-variance, low-bias trees; boosting reduces bias by sequentially fitting each new tree to the residual (or negative gradient) of the current ensemble, so it can reach lower bias than any single tree in the forest. Boosting typically wins on structured/tabular data with enough tuning; it's more prone to overfitting with noisy labels or few samples, and slower to tune (learning rate, tree depth, number of rounds are all coupled) versus a forest that mostly needs `n_estimators` and default depth.
- **Weak:** "Boosting is stronger because it's sequential" with no bias/variance framing and no failure case named.
- **Follow-up trap:** *"Your boosted model outperforms your forest on train/test split but underperforms in production six months later. What's your first hypothesis?"* Wants: boosting overfit to the specific residual structure of the training distribution and is more brittle to distribution shift than the forest's variance-averaged, more robust ensemble — a real production failure mode, not a generic "retrain more often."

**Q6 — Walk through precision, recall, F1, and when optimizing for F1 is itself the wrong move.**
- **Strong:** Precision = TP/(TP+FP), recall = TP/(TP+FN), F1 = harmonic mean, which penalizes imbalance between the two more than the arithmetic mean would. States that F1 implicitly assumes precision and recall have equal business cost, which is rarely true — a fraud model usually needs to trade precision for recall (catching fraud matters more than false alarms) or vice versa depending on review capacity, so the right target is often F-beta with a beta chosen from the actual cost ratio, or a direct cost-weighted objective.
- **Weak:** "F1 balances precision and recall" with no mention of the equal-cost assumption or when it breaks.
- **Follow-up trap:** *"Derive F-beta and tell me what beta=2 means in plain language."* `F_beta = (1+β²)·P·R / (β²·P + R)`; β=2 weights recall twice as important as precision — used when missing a positive (false negative) is worse than a false alarm, e.g., cancer screening or fraud detection.

**Q7 — Explain missing data mechanisms (MCAR, MAR, MNAR) and how the mechanism changes your imputation strategy.**
- **Strong:** MCAR (missing completely at random, unrelated to any variable) — mean/median imputation is unbiased. MAR (missingness depends on observed variables) — model-based imputation (regression, MICE) conditioned on those observed variables can be unbiased. MNAR (missingness depends on the unobserved value itself, e.g., high earners refusing to report income) — no imputation strategy is unbiased without an explicit model of the missingness mechanism; sometimes the missingness indicator itself is the useful feature.
- **Weak:** "Just use mean imputation or drop the rows" with no mechanism distinction.
- **Follow-up trap:** *"A feature is missing 40% of the time and dropping those rows halves your training set. What do you actually do?"* Add a missingness indicator as a feature (often carries signal, especially under MAR/MNAR), consider whether the missingness itself predicts the target before assuming it's noise, and validate any imputation against a held-out set rather than assuming a textbook method transfers.

### Staff / Principal

**Q8 — Derive backpropagation through a single sigmoid neuron and show mechanically where the vanishing gradient problem originates.**
- **Strong:** For `a = σ(z)`, `z = wx + b`, derives `∂a/∂z = σ(z)(1-σ(z))`, notes this is maximized at `z=0` where it equals 0.25 and approaches 0 at the tails where the sigmoid saturates. In a deep network, the gradient at layer 1 is a product of these per-layer derivatives via the chain rule; with each factor bounded by 0.25, a 10-layer network multiplies gradients by at most `0.25^10 ≈ 1e-6`, so the earliest layers receive a vanishingly small learning signal. Connects this to why ReLU (derivative is exactly 1 for z>0) and residual connections (identity shortcut bypasses the multiplicative chain) were the two dominant fixes.
- **Weak:** "Vanishing gradients happen in deep networks with sigmoid activations" with no derivative bound, no multiplication argument, and no mechanism for why ReLU or residuals fix it.
- **Follow-up trap:** *"ReLU fixes vanishing gradients. Does it introduce a new failure mode?"* Yes — dying ReLU: once a unit's weighted input is permanently negative (large negative bias update, or an unlucky learning-rate spike), its gradient is exactly zero for all future inputs and it never recovers, because both the forward activation and the backward gradient are pinned at zero. Fixes: Leaky ReLU, better initialization (He init), lower learning rate, or batch norm to keep activations centered.
- **Note:** this is the single highest-value derivation in the round — if the candidate cannot produce the 0.25 bound and the multiplication argument, treat the rest of the deep learning section skeptically.

**Q9 — Why does batch normalization help training, and what's the actual mechanism versus the originally claimed mechanism?**
- **Strong:** Normalizes layer inputs to zero mean, unit variance per mini-batch (then applies learnable scale γ and shift β), and states that the original 2015 paper's claimed mechanism (reducing "internal covariate shift") has since been challenged; a widely cited 2018 result (Santurkar et al.) shows BatchNorm's main benefit is smoothing the loss landscape (reducing the Lipschitz constant of the loss and its gradients), allowing larger stable learning rates, rather than the covariate-shift story. A candidate who names both the mechanism and the fact that the original explanation is contested is showing real depth, not memorized folklore.
- **Weak:** "BatchNorm normalizes activations so training is more stable" — true but stops one level above the mechanism and doesn't know the covariate-shift explanation is disputed.
- **Follow-up trap:** *"Your model behaves differently at train time vs. inference time because of BatchNorm. Why, and how do you handle it?"* Train time uses per-batch statistics; inference uses a running (exponential moving) average of mean/variance accumulated during training, because a single inference example (or a batch of 1) has no meaningful batch statistics of its own. Forgetting to switch the layer to eval mode is a specific, common, and observable production bug (predictions drift or destabilize when a small inference batch is used with training-mode batch stats).

**Q10 — CNN vs. RNN vs. Transformer for a sequence task: derive the actual computational and representational tradeoffs.**
- **Strong:** RNN: O(n) sequential steps, cannot parallelize across the sequence dimension during training, path length between distant tokens is O(n) so long-range dependencies suffer from the vanishing-gradient chain above. CNN (dilated/causal): parallelizable, path length is O(log n) with dilation, fixed receptive field per layer. Transformer: O(1) path length between any two tokens via full self-attention, fully parallelizable training, but O(n²) time and memory in sequence length — this quadratic cost is the actual reason for context-length engineering (sparse attention, sliding window attention, linear attention approximations) in production LLMs.
- **Weak:** "Transformers are better because of attention" with no path-length argument and no acknowledgment of the O(n²) cost.
- **Follow-up trap:** *"Your inference latency is dominated by attention at 32k context. Name two concrete mitigations and their tradeoff."* KV-caching (trades memory for avoiding recomputation of past keys/values — doesn't reduce the O(n²) but avoids redundant work per new token), or sliding-window / sparse attention (reduces the effective quadratic term at the cost of losing some long-range interactions, which is a real accuracy tradeoff, not free).

**Q11 — Derive why softmax + cross-entropy has a clean gradient, and what happens numerically if you compute softmax naively.**
- **Strong:** For softmax `p_i = e^{z_i} / Σe^{z_j}` combined with cross-entropy loss `L = -Σ y_i log(p_i)`, the gradient with respect to the logits simplifies to `∂L/∂z_i = p_i - y_i` — a remarkably clean result that's why the pairing is standard rather than either component being used alone with a different loss. Numerically, naive exponentiation of large logits overflows; the fix is the log-sum-exp trick, subtracting `max(z)` from all logits before exponentiating, which is mathematically identical but numerically stable.
- **Weak:** "Softmax turns logits into probabilities, cross-entropy measures the difference" — true but doesn't derive the clean gradient or know the numerical stability issue.
- **Follow-up trap:** *"Your training loss is NaN after epoch 3. Walk me through your diagnostic order."* Check for exploding gradients (unclipped, especially in RNNs), check learning rate (too high), check for the log-sum-exp instability if a custom softmax/cross-entropy was hand-rolled instead of using a numerically stable library implementation, check for a division by zero or log(0) from a probability that underflowed to exactly 0.

**Q12 — Explain the exploration-exploitation tradeoff in a contextual bandit and derive why a supervised ranker trained on logged clicks has a structural blind spot.**
- **Strong:** A ranker trained on historical clicks only ever sees outcomes for items the previous policy chose to show, so it optimizes a biased, incomplete slice of the item space and can never learn that an unshown item might have been better — this is off-policy bias, not just "cold start." A contextual bandit frames each recommendation as an arm pull conditioned on context, updates from observed reward, and explicitly allocates some traffic to exploration (via ε-greedy, Thompson sampling, or UCB) to gather unbiased signal on under-shown arms. States the real cost: unbounded exploration in a live product means showing genuinely worse content to real users, so exploration must be bounded and monitored.
- **Weak:** "Bandits explore and rankers don't" with no mechanism for why the ranker's blind spot exists (it's a distributional bias problem from the logging policy, not a lack of cleverness in the model).
- **Follow-up trap:** *"How do you evaluate a candidate bandit policy offline before risking live traffic?"* Off-policy evaluation via inverse propensity scoring (reweighting logged rewards by the ratio of the new policy's probability to the old policy's logged probability for the action actually taken) — and the honest caveat that IPS has high variance when the policies diverge a lot, which is exactly when you'd want the estimate most.

**Q13 — Derive why dropout works as a regularizer, and explain the train/inference scaling discrepancy.**
- **Strong:** Dropout randomly zeroes each unit with probability p during training, forcing the network to not rely on any single unit (an implicit ensemble-averaging argument: each mini-batch trains a different random subnetwork, and at test time you're approximating the geometric mean of an exponential number of subnetworks). Because units are zeroed at rate p during training but present at inference, the expected magnitude of the layer's output differs between train and inference unless corrected — either scale activations by `1/(1-p)` during training (inverted dropout, the standard modern implementation) or scale by `(1-p)` at inference (the original 2014 formulation). States that using inverted dropout means inference requires no special-casing.
- **Weak:** "Dropout randomly turns off neurons to prevent overfitting" with no ensemble argument and no awareness of the train/inference scaling issue — which is a specific, real bug source if hand-implemented.
- **Follow-up trap:** *"You hand-rolled dropout and your model's validation loss is inexplicably higher than training loss even accounting for normal generalization gap. What's your first hypothesis?"* Forgot the inverted-dropout scaling correction, or forgot to disable dropout at eval time entirely (same class of bug as the BatchNorm train/eval mode bug in Q9) — mechanically similar failure across two different layers is worth naming explicitly, since it shows pattern-level understanding rather than two disconnected facts.

**Q14 — When would you deliberately choose a simpler model (logistic regression, a shallow tree) over a deep network, and defend it against the assumption that more capacity is always better?**
- **Strong:** Names concrete conditions: small labeled dataset (deep nets need data volume the task doesn't have), a need for interpretability the business genuinely requires (regulated lending, medical triage where a coefficient must be explainable to an auditor), a latency budget that a deep model can't hit at the required QPS without disproportionate serving cost, or a tabular problem where gradient boosting reliably beats deep learning absent very large data and heavy tuning (a well-documented empirical pattern, not an opinion). States the real cost of the "just use a bigger model" reflex: serving cost, debugging difficulty, and interpretability loss are real prices paid for capacity the problem may not need.
- **Weak:** "Simpler models are more interpretable" as the entire answer, with no latency/data/cost dimension and no acknowledgment that this is a judgment call with real counter-examples.
- **Follow-up trap:** *"Your stakeholder wants a neural network because 'AI' sounds better to their board. What do you actually do?"* Tests backbone: the correct move is to push back with the evidence (offline comparison numbers, cost delta, interpretability requirement) rather than silently building what was asked, while being pragmatic about political reality — naming that tension honestly is itself a seniority signal.

**Q15 — What does it mean for a classifier to be "well-calibrated," derive why a model can have excellent AUC and terrible calibration simultaneously, and name a fix.**
- **Strong:** A calibrated classifier's predicted probabilities match observed frequencies — of all examples predicted at 0.7, roughly 70% should actually be positive. States precisely why AUC and calibration are independent properties: AUC only depends on the *ranking* of predicted scores (is a positive scored above a negative), so a monotonic transformation of the scores (e.g., squashing everything toward 0 or 1, or an uncalibrated boosted-tree's raw margin output) leaves AUC completely unchanged while destroying calibration. Names the practical consequence: any downstream decision that treats the score as an actual probability (expected-value thresholding, cost-weighted decisions, combining scores across models) is silently wrong under miscalibration even though the model "performs well" by AUC. Names concrete fixes: Platt scaling (fitting a logistic regression on top of the raw scores) for a roughly sigmoid-shaped miscalibration, or isotonic regression for a more flexible, non-parametric correction when there's enough calibration data to avoid overfitting the correction itself.
- **Weak:** "Calibration means the probabilities are accurate" with no derivation of why it's independent of AUC/ranking metrics, and no named fix.
- **Follow-up trap:** *"Gradient-boosted trees are notoriously poorly calibrated out of the box. Why, mechanically, and does more trees or more depth fix it?"* Boosted trees optimize a ranking/log-loss objective that pushes predictions toward the extremes (0 and 1) faster than the true underlying probabilities would justify, because each additional tree keeps correcting residuals in a way that sharpens rather than calibrates the score distribution — more trees or depth makes this worse, not better, since it's a property of the boosting objective's behavior, not underfitting. The fix is a post-hoc calibration step (Platt/isotonic) on held-out data, not more boosting rounds.

## Rubric

| Dimension | 1-2 | 3 | 4-5 |
|---|---|---|---|
| Correctness / depth | States definitions only, cannot produce a derivation when asked; gets a mechanism wrong and doesn't self-correct when challenged | Produces most derivations with prompting; gets the mechanism right but the derivation has a gap (e.g., states the sigmoid derivative bound without deriving it) | Derives unprompted (gradient equations, the 0.25 bound, the softmax+CE simplification); connects mechanism to a concrete production failure mode without being asked |
| Structure / method | Jumps straight to an answer with no framing; when asked to construct a numeric example, produces vague or inconsistent numbers | Constructs a numeric example when asked but it takes prompting to get there; reasoning is correct but not sequenced (jumps between claims) | Unprompted: states the framework before filling it in ("there are three regimes here, let me take them in order"); constructs numeric examples proactively to support a claim |
| Communication | Reaches for jargon without being able to unpack it when pushed; cannot explain their own claim a second way when the first explanation doesn't land | Explains clearly on the first pass; struggles to rephrase when the interviewer signals confusion | Explains at the right altitude for the question, rephrases fluently on a follow-up, uses a concrete number or worked example unprompted to ground an abstract claim |
| Seniority signals | Never states a real limitation of their own claim; treats every technique as strictly better with no failure mode named | States one limitation when asked directly | States tradeoffs and failure modes unprompted (dying ReLU after naming ReLU as the vanishing-gradient fix; F1's equal-cost assumption after defining F1); admits genuine uncertainty precisely rather than confidently answering an ill-posed question |

## Score bands

- **17-20 — STRONG HIRE.** Derives the hard mechanisms unprompted (backprop through saturation, softmax+CE gradient, the L2-as-prior connection), names failure modes of their own proposed fixes without being asked, and constructs numeric counter-examples proactively. This is what a candidate who has actually debugged these systems in production looks like, not one who has read about them.
- **13-16 — HIRE.** Gets to correct derivations with one or two prompts, mechanism is right even if not maximally crisp, names at least one unprompted tradeoff per major topic area.
- **9-12 — LEAN HIRE.** Definitions are solid and mostly accurate, but derivations require heavy scaffolding from the interviewer and the candidate cannot get there independently even with a nudge. Passes as competent, not as staff-plus depth.
- **5-8 — NO HIRE.** Definitions are shaky or outdated (e.g., treats AUC as unconditionally trustworthy, or can't state what F1 assumes), no derivations produced even with prompting, no failure modes named for any technique discussed.
- **0-4 — STRONG NO HIRE.** Cannot correctly state basic mechanisms (confuses precision and recall, cannot describe what backprop computes), asserts confident wrong answers and does not update when directly corrected.

## Red flags that end the round

- Stating a comparative claim ("boosting is better than bagging") with no mechanism, and being unable to produce one when pressed twice.
- Treating AUC, F1, or accuracy as unconditionally good metrics with no awareness of the conditions under which each is misleading.
- Cannot derive the vanishing-gradient bound for sigmoid even with the derivative formula given.
- Confidently asserting a claim that was true of an older architecture generation as if it's still the frontier consensus, and not updating when asked "is that still true in 2026."
- Answering "it depends" to a derivation question and stopping there instead of picking a concrete scenario and deriving within it.

## Time-management failures

- **Getting stuck defending a wrong derivation instead of re-deriving from first principles.** The clock punishes pride here more than in any other round — a candidate who says "let me redo this from the loss function" at minute 15 recovers; one who argues for their wrong sign error until minute 20 does not.
- **Spending 10+ minutes on the warmup calibration questions.** These exist to set the ramp, not to be exhaustively answered; over-elaborating a "what is bias-variance" answer eats into the higher-value derivation time.
- **No numeric example ready when a metric question lands.** Constructing a confusion matrix from scratch under time pressure (rather than having the shape memorized: "imagine 10,000 negatives, 100 positives...") costs 2-3 minutes that should cost 30 seconds.
- **Trying to cover CNN, RNN, and Transformer in exhaustive equal depth.** The interviewer wants the comparative tradeoff, not three independent lectures; spending 15 minutes on RNN internals before ever reaching the Transformer comparison is a pacing failure.

## Cheat card

```
BIAS-VARIANCE: E[(y-f̂)²] = Bias² + Var + σ². Train 2% / test 25% → variance, not bias.
AUC = P(random positive ranked above random negative). Lies under class imbalance:
      construct 10k neg / 100 pos, 95% TPR/20% FPR → still ~4.5% precision.
PR-AUC baseline = positive class prevalence, NOT 0.5. Anchor to base rate.
F1 = harmonic mean(P,R), assumes EQUAL cost of FP/FN — usually false. Use F-beta.
L2 grad: ∇=-2Xᵀ(y-Xw)+2λw → MAP w/ Gaussian prior, var=σ²/λ. Shrinks, never zeroes.
L1 subgradient = const ±λ regardless of magnitude → CAN zero out small weights.
Boosting: sequential, reduces BIAS (fits residuals). Bagging: parallel, reduces VARIANCE.
sigmoid deriv max = 0.25 at z=0 → chain of 10 layers ≤ 0.25^10 ≈ 1e-6 → vanishing grad.
ReLU fixes vanishing grad (deriv=1, z>0) but introduces DYING ReLU (deriv=0 forever).
BatchNorm: real mechanism is loss-landscape smoothing (Santurkar 2018), not the
           original "covariate shift" claim. Train=batch stats, eval=running avg.
softmax+CE gradient simplifies to (p_i - y_i). Naive softmax overflows → log-sum-exp.
RNN: O(n) sequential, O(n) path length. CNN: parallel, O(log n) path (dilated).
Transformer: O(1) path length, O(n²) compute/memory — the reason for KV-cache,
             sliding-window attention at long context.
Dropout: ensemble-of-subnetworks argument. INVERTED dropout scales by 1/(1-p) at
         TRAIN time so inference needs no special-casing — forgetting it is a real bug.
Contextual bandit ≠ ranker: ranker only sees outcomes for what the OLD policy showed.
Always: name the mechanism, then the failure mode of your own fix, unprompted.
```

## Sources

- [25 Machine Learning Interview Questions for 2026 (And How Senior Candidates Actually Answer Them) — InterviewPal](https://www.interviewpal.com/blog/25-machine-learning-interview-questions-for-2026-and-how-senior-candidates-actually-answer-them) — accessed 2026-08-01
- [Machine Learning Interview Questions & Answers (2026) — Exponent](https://www.tryexponent.com/blog/top-machine-learning-interview-questions) — accessed 2026-08-01
- `curriculum/03-classical-ml/` and `curriculum/04-deep-learning/` — mechanism-level source material this round derives from (internal).
- **Unverified claim flagged:** the Santurkar et al. 2018 "loss-landscape smoothing" reframing of BatchNorm is well-established in the deep learning literature as of this writing but was not independently re-verified via a fresh source lookup for this module; treat the citation as recalled rather than freshly confirmed.

## Changelog
- 2026-08-01 — created
