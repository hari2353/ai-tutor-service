# Text Classification: Naive Bayes → Linear → Fine-Tuned Transformers, Multi-Label, Imbalance

> **Track:** T32 Applied NLP & Marketing ML · **Time:** 2.5h · **Prereqs:** T32-nlp-classical, T32-word-embeddings · **Updated:** 2026-08-02
> **Module id:** `T32-text-classification` · **Tags:** nlp

## The 30-second version

Text classification has three real tiers, and the skill is picking the cheapest one that clears your accuracy bar, not defaulting to the most powerful. Naive Bayes applies Bayes' rule with a conditional-independence assumption between features that's obviously false for language and works anyway, because it needs the *ranking* of class probabilities to be right, not the probabilities themselves — it's the fastest, cheapest, most interpretable baseline and still a legitimate production choice for high-volume, latency-sensitive filtering. Linear models (logistic regression, linear SVM) drop the independence assumption and the generative framing entirely, learning discriminative decision boundaries directly, and are usually the best cost-to-accuracy ratio for structured, moderate-complexity classification tasks. Fine-tuned transformers buy real accuracy on tasks with genuine contextual ambiguity, at real GPU cost and latency, and are worth it specifically when that gap matters to the business outcome, not by default. Two things break naive implementations of all three tiers: class imbalance, which silently collapses a model toward predicting the majority class unless you weight the loss or resample; and miscalibration, where a model's output "probability" doesn't mean what a downstream system assumes it means — a 0.9 score should correspond to being right 90% of the time, and for most models, especially over-parameterized neural ones, it doesn't without explicit calibration (temperature scaling, Platt scaling, or isotonic regression). Multi-label classification needs its own framing entirely — independent per-label sigmoid outputs and binary cross-entropy per label, not a single softmax — because an item can belong to zero, one, or many classes at once, and treating it as many-class-softmax silently forces mutual exclusivity that doesn't exist.

## Why this gets asked

Somewhere behind this question is a team that shipped a 99%-accurate spam/content classifier that was useless in production because the corpus was 98% negative class and the model just learned to predict the majority label, or a team that trusted a neural classifier's confidence score to gate automated decisions and got burned because the model was badly overconfident. The interviewer wants evidence you'd catch both before shipping — that you know accuracy alone is not the metric on an imbalanced corpus, that you know a softmax probability isn't automatically a calibrated one, and that you can defend starting with the cheapest model that works rather than reaching for a transformer because it's the default motion.

---

## Lineage: past → present → future

**What came before.** Rule-based text classification (keyword lists, regex triggers) preceded any of this and is still occasionally the right answer for narrow, high-precision rules (a filter that flags any mention of a specific banned term) — it fails the moment the classification boundary needs more than a handful of surface patterns, because the rule set grows unmanageably and never generalizes to phrasing the author didn't anticipate. Naive Bayes (applied to text classification concretely by the late 1990s, though the underlying Bayes' rule is centuries old) was the first statistically learned classifier to see wide production use for text, cheap enough to train and run at any volume the era's hardware could handle, and it remains the textbook baseline every later method is measured against. The pain that pushed the field past pure Naive Bayes: its conditional independence assumption, while surprisingly tolerable for classification ranking, genuinely limits how much accuracy is available on tasks where feature interactions actually matter (negation, multi-word idioms), and it has no natural way to incorporate arbitrary overlapping features the way a discriminative model can.

**Where it stands now.** Linear discriminative models (logistic regression, linear SVM — both maturing through the 2000s alongside better-understood regularization) largely displaced Naive Bayes as the default production baseline for anything beyond the simplest filtering, because dropping the generative independence assumption and optimizing the actual classification objective directly typically buys real accuracy for a small added training cost, while keeping inference just as cheap. Fine-tuned transformers (BERT-era encoders, 2018 onward) then became the accuracy ceiling for genuinely context-dependent classification — sentiment with negation and sarcasm, nuanced content moderation, intent classification with subtle distinctions — at the real cost of GPU inference and materially higher latency per document. The live disagreement is almost entirely about where the accuracy-cost crossover sits for a given task and volume: some teams default to fine-tuning a small transformer for everything because infrastructure for it now exists and engineer time is the scarcer resource; others hold the line that a linear TF-IDF baseline should always be measured first and only replaced when the accuracy gap is shown, not assumed. Both are defensible engineering cultures, and the honest answer names the actual crossover point rather than picking a side dogmatically.

**Where it's heading.** High confidence: zero-shot and few-shot LLM classification keeps taking share at the low-volume, rapidly-changing-taxonomy end of the spectrum — exactly where standing up any trained classifier (Naive Bayes through fine-tuned transformer) has a real fixed cost that a prompt doesn't. Moderate confidence: calibration is becoming a first-class production requirement rather than an afterthought, as more classification output feeds automated downstream decisions (auto-routing, auto-moderation) where an uncalibrated confidence score causes real harm if trusted naively — expect calibration checks to become as standard in a classification pipeline's eval as accuracy and F1 already are. Speculative: some argue fine-tuned small transformers will fully absorb the linear-model tier as inference cost keeps falling and distillation/quantization make transformer inference cheap enough to match linear models' cost profile — this is directionally plausible but not yet true at the very high end of production volume (many millions of documents/day) most large content platforms operate at, and treating that crossover as already arrived is a real gap between research trend and deployed reality.

---

## Mental model

```
                    accuracy on genuinely context-dependent tasks
                                    ▲
FINE-TUNED TRANSFORMER  ───────────┤  ms-tens of ms latency, GPU inference,
                                    │  real infra cost. Worth it when context matters.
                                    │
LINEAR (logreg / SVM)  ────────────┤  sub-ms to low-ms, CPU, cheap to retrain.
   on TF-IDF/n-gram features        │  Best cost-to-accuracy for structured tasks.
                                    │
NAIVE BAYES  ───────────────────────┤  fastest, most interpretable, no gradient descent.
   generative, independence assumed │  Legitimate default for high-volume filtering.
                                    └──────────────────────────────────────────────▶
                                              cost / latency / infra complexity

The independence assumption Naive Bayes makes is FALSE for language ("not good" ≠ independent
"not" and "good") — and it works anyway for classification RANKING, because NB only needs
P(class_A|doc) > P(class_B|doc) to hold, not the individual probabilities to be accurate.
```

The one thing to internalize: every tier above is solving the same task with a different amount of *representational flexibility purchased at a specific cost*. The question in an interview is never "which is best" — it's "which is the cheapest one that clears the accuracy bar this specific task and volume actually need," and being able to justify that with numbers is the whole signal.

---

## How it actually works

### Naive Bayes, derived

Bayes' rule gives the posterior probability of a class `c` given a document `d`:

```
P(c | d) = P(d | c) * P(c) / P(d)
```

Since `P(d)` is constant across classes for a fixed document, classification reduces to choosing the class maximizing `P(d|c) * P(c)` — the **MAP (maximum a posteriori)** decision rule. The "naive" part: assume every word in the document is conditionally independent of every other word, given the class:

```
P(d | c) = P(w_1, w_2, ..., w_n | c) ≈ Π_{i=1}^{n} P(w_i | c)
```

This is obviously false for real language ("not" and "good" are not independent — their combination flips meaning), but classification only requires the *comparison* `P(c_A|d)` vs `P(c_B|d)` to come out correctly ranked, not the individual probability estimates to be accurate — errors from the independence assumption tend to affect both class comparisons similarly and often cancel in the ranking, which is the empirical reason Naive Bayes classifies far better than the assumption's implausibility would suggest.

**Multinomial NB** models `P(w_i|c)` as word *frequency* (how many times each word occurs), which is the standard choice for text classification with count or TF-weighted features. **Bernoulli NB** models `P(w_i|c)` as word *presence/absence* (binary — did this word appear at all, ignoring how many times), which discards frequency information but can outperform Multinomial NB on short documents where a word's mere presence carries most of the signal and repetition counts are noisy or nearly absent. **Laplace (additive) smoothing** fixes the zero-probability problem — any word absent from a class's training documents would otherwise get `P(w|c) = 0`, which zeroes out the entire product for any test document containing that word, regardless of how strongly every other word points to that class:

```
P(w | c) = ( count(w, c) + α ) / ( Σ_{w'} count(w', c) + α * V )
```

`V` is vocabulary size, `α` is the smoothing pseudo-count (α=1 is classic Laplace smoothing; smaller values like 0.01-0.1 are common in practice and tuned like any other hyperparameter). Training is a single pass over the corpus computing counts — `O(n*d)` for `n` documents and `d` features, no gradient descent, no iterative optimization loop — which is precisely why Naive Bayes remains the fastest classifier in this module by a wide margin and a legitimate choice whenever training/retraining speed at very high volume matters more than the last few points of accuracy.

### Linear models: logistic regression and linear SVM

Both drop Naive Bayes's generative framing (model `P(d|c)` and invert with Bayes' rule) in favor of **discriminative** modeling — learn `P(c|d)` or a decision boundary directly from data, without any assumption about how documents are generated. **Logistic regression** models `P(c|d) = σ(w·x + b)` (sigmoid of a linear function of the feature vector, typically TF-IDF), trained by minimizing cross-entropy loss via gradient descent, with L2 (or L1, for sparse feature selection) regularization controlling overfitting on the — often tens of thousands of dimensions — TF-IDF feature space. **Linear SVM** instead maximizes the margin between classes, minimizing hinge loss `max(0, 1 - y*(w·x+b))` rather than cross-entropy — this tends to produce a decision boundary less sensitive to points far from the margin, which can help on noisy or heavy-tailed feature distributions, at the cost of not natively producing a calibrated probability the way logistic regression's sigmoid output does (SVM scores need an extra calibration step, commonly Platt scaling, to become probability-like at all). In practice, on TF-IDF text features at moderate scale, logistic regression and linear SVM perform comparably, and the choice between them is often driven by whether you need a native probability output (logistic regression) or slightly more robust margin behavior (SVM) rather than a large expected accuracy gap.

### Fine-tuned transformers

Fine-tuning a pretrained transformer encoder (BERT, RoBERTa, DeBERTa, or a smaller distilled variant) for classification means adding a linear classification head on top of the encoder's pooled or `[CLS]`-token representation and training the whole stack (or, for parameter-efficient fine-tuning, a small adapter/LoRA layer) end to end on labeled examples, with the pretrained weights providing a strong starting point that needs far fewer labeled examples to reach good accuracy than training a comparable-capacity model from scratch. The real gain over linear models comes specifically from **contextual representation** — the encoder's attention mechanism lets the model represent negation scope, long-range dependency, and sarcasm-adjacent context that a bag-of-words TF-IDF feature vector structurally cannot, which is exactly the polysemy/context argument from the word-embeddings module applied to whole-document classification instead of individual words. The real cost is inference: even a small fine-tuned transformer typically needs single-digit to tens of milliseconds per document on a GPU (materially more on CPU), against sub-millisecond to low-single-digit-millisecond inference for a linear model on the same hardware tier — at production content volume, this difference compounds into a real infrastructure bill, which is exactly why "fine-tune a transformer for everything by default" is not automatically the right engineering call even when it's clearly the right accuracy call.

### Multi-label classification

Standard multi-class classification assumes each item belongs to exactly one of `K` classes, modeled with a softmax output (probabilities across all classes sum to 1, enforcing mutual exclusivity). **Multi-label** classification allows an item to belong to zero, one, or many classes simultaneously (a hotel description might be tagged both "family-friendly" and "beach" and "luxury" at once), and the correct architecture reflects that: `K` independent sigmoid outputs, one per label, each trained with its own binary cross-entropy loss, with no constraint that the outputs sum to 1. Using a softmax for a genuinely multi-label problem silently and incorrectly forces the model to treat labels as mutually exclusive, actively fighting the training signal whenever multiple labels are simultaneously true — a real, common implementation bug. Evaluation for multi-label problems needs its own conventions: **micro-averaged F1** (aggregate true/false positives/negatives across all labels before computing F1 — dominated by frequent labels), **macro-averaged F1** (compute F1 per label, then average — treats rare and common labels equally, which can be exactly what you want or exactly the wrong choice depending on whether rare-label performance matters as much as common-label performance), **subset accuracy / exact match ratio** (the strictest metric — credit only if every label for an item is predicted correctly, no partial credit, directly analogous to entity-level F1's exact-match convention from the NER module), and **Hamming loss** (fraction of individual label predictions that are wrong, treating each label as an independent binary decision — the most forgiving of the standard metrics). Per-label decision thresholds also need independent tuning — the default 0.5 sigmoid threshold is rarely optimal for every label simultaneously, especially under class imbalance (below), and production systems commonly tune a separate threshold per label against a validation set rather than using one global cutoff.

### Class imbalance

Real classification corpora are rarely balanced — spam is a small fraction of email, a specific content-moderation violation is a small fraction of listings, a rare intent category is a small fraction of queries — and an unaddressed imbalance silently biases every model in this module toward the majority class, because minimizing average loss over an imbalanced training set is dominated by getting the majority class right. **Class weighting** (multiply each class's loss contribution by a weight inversely proportional to its frequency, commonly `weight_c = N / (K * n_c)` for `N` total examples, `K` classes, `n_c` examples in class `c`) rebalances the effective training signal without changing the data itself, and is the simplest, usually first-tried fix. **Focal loss** (Lin et al., 2017, originally for object detection but widely adopted in imbalanced text classification) goes further, adding a modulating factor that down-weights well-classified, easy examples and up-weights hard or misclassified ones:

```
FL(p_t) = -(1 - p_t)^γ * log(p_t)
```

`p_t` is the model's estimated probability for the true class, `γ` (commonly 2 in the original paper) controls how aggressively easy examples are down-weighted — as `p_t → 1` (an easy, confidently-correct example), `(1-p_t)^γ → 0`, shrinking that example's loss contribution toward zero regardless of class frequency, which is a genuinely different mechanism from class weighting (frequency-based) since focal loss reweights by *difficulty*, and the two are often combined. **Resampling** (oversample the minority class, undersample the majority, or synthetic oversampling like SMOTE — though SMOTE's interpolation-in-feature-space logic is less natural for the high-dimensional sparse TF-IDF space than for dense tabular features, and less commonly used for text than for structured data) is a data-level alternative to the loss-level fixes above. Whichever mechanism you use, **evaluation must change too**: accuracy on an imbalanced corpus is close to meaningless (a model predicting the majority class for everything can score 95%+ "accuracy" on a 95/5 split while catching zero minority-class examples — the exact same trap as NER's token-vs-entity-level F1 issue from the previous module, recurring here at the document-classification level), and **PR-AUC (precision-recall area under the curve)** is the standard replacement for ROC-AUC under heavy imbalance, because ROC-AUC's false-positive-rate axis is computed against the (large) majority class and stays deceptively good-looking even as precision on the minority class collapses.

### Calibration

A model's raw output score being high does not automatically mean the model is *correct* that often. **Calibration** is the property that a predicted probability matches the true empirical frequency of correctness — among all predictions the model assigns 0.9 confidence, roughly 90% should actually be correct, for the score to be trustworthy as a probability rather than merely a ranking signal. Modern over-parameterized neural networks (including fine-tuned transformers) are frequently and systematically **overconfident** — a well-established empirical finding (Guo et al., 2017) — meaning their softmax outputs cluster near 0 and 1 far more than their actual accuracy justifies, which is dangerous specifically when a downstream system uses the raw score to gate an automated decision (auto-approve any prediction above 0.95 confidence, for instance) without checking whether 0.95 actually means what it claims to mean. **Temperature scaling** is the simplest and most widely used fix for neural classifiers: divide the pre-softmax logits by a single learned scalar `T > 1` before applying softmax, which smooths (flattens) the output distribution without changing which class ranks highest — `T` is fit on a held-out validation set by minimizing negative log-likelihood, and because it's a single parameter, it's cheap to fit and cannot change the model's accuracy or ranking, only its confidence calibration. **Platt scaling** (fit a logistic regression on top of the raw model scores) and **isotonic regression** (a non-parametric, monotonic mapping from raw scores to calibrated probabilities, more flexible but needs meaningfully more validation data to fit reliably without overfitting) are the standard alternatives, with isotonic regression generally preferred when there's enough validation data and the miscalibration pattern is more complex than a single global temperature can fix. **Expected Calibration Error (ECE)** is the standard scalar metric: bin predictions by confidence, compute the gap between average confidence and actual accuracy within each bin, and take the weighted average gap across bins — a reliability diagram (plotting predicted confidence against actual accuracy per bin) is the standard visual complement, and both should be a routine part of any classification eval whose output feeds an automated downstream decision, not an afterthought added after an incident.

---

## Build it from scratch

```python
# untested sketch — minimal Multinomial Naive Bayes with Laplace smoothing, and
# temperature scaling for calibrating an already-trained model's logits
import numpy as np
from collections import defaultdict

class MultinomialNB:
    def __init__(self, alpha: float = 1.0):
        self.alpha = alpha
        self.class_log_prior: dict = {}
        self.feature_log_prob: dict = {}     # class -> array of log P(word|class)
        self.classes: list = []

    def fit(self, X: np.ndarray, y: list, vocab_size: int):
        """X: (n_samples, vocab_size) word count matrix. y: list of class labels."""
        self.classes = sorted(set(y))
        n = len(y)
        for c in self.classes:
            mask = np.array([label == c for label in y])
            n_c = mask.sum()
            self.class_log_prior[c] = np.log(n_c / n)

            word_counts_c = X[mask].sum(axis=0)              # total count per word in class c
            total_words_c = word_counts_c.sum()
            # Laplace-smoothed P(word|class), in log space
            self.feature_log_prob[c] = np.log(
                (word_counts_c + self.alpha) / (total_words_c + self.alpha * vocab_size)
            )

    def predict(self, X: np.ndarray) -> list:
        scores = np.array([
            self.class_log_prior[c] + X @ self.feature_log_prob[c]     # Σ count*log P(w|c)
            for c in self.classes
        ]).T                                                            # (n_samples, n_classes)
        return [self.classes[i] for i in scores.argmax(axis=1)]


def fit_temperature(logits: np.ndarray, labels: np.ndarray, lr: float = 0.01, steps: int = 200) -> float:
    """Single-parameter temperature scaling, fit on a held-out validation set."""
    T = 1.0
    for _ in range(steps):
        scaled = logits / T
        probs = np.exp(scaled - scaled.max(axis=1, keepdims=True))
        probs /= probs.sum(axis=1, keepdims=True)
        # gradient of NLL w.r.t. T (finite-difference approximation for the sketch)
        eps = 1e-3
        nll = -np.log(probs[np.arange(len(labels)), labels] + 1e-12).mean()
        scaled_eps = logits / (T + eps)
        probs_eps = np.exp(scaled_eps - scaled_eps.max(axis=1, keepdims=True))
        probs_eps /= probs_eps.sum(axis=1, keepdims=True)
        nll_eps = -np.log(probs_eps[np.arange(len(labels)), labels] + 1e-12).mean()
        grad = (nll_eps - nll) / eps
        T -= lr * grad
    return T
```

The three things a real implementation adds that this sketch skips: sparse matrix support for `X` (a real TF-IDF/count matrix is far too large to hold dense at production vocabulary size), a proper gradient-based optimizer (L-BFGS is the standard choice for fitting temperature scaling in practice, not manual finite-difference gradient descent), and cross-validated threshold tuning per label for the multi-label case rather than a fixed 0.5 cutoff. `sklearn.naive_bayes.MultinomialNB` and `sklearn.calibration.CalibratedClassifierCV` are the references to read next.

---

## How it's done in production

**scikit-learn** — `MultinomialNB`/`BernoulliNB`, `LogisticRegression`, `LinearSVC`, and `CalibratedClassifierCV` (wrapping Platt scaling or isotonic regression around any scikit-learn classifier) cover the entire non-transformer tier of this module and are the standard first stop. **Hugging Face `transformers`** (`AutoModelForSequenceClassification`) — the reference fine-tuning path for transformer classification, with native multi-label support via a sigmoid-plus-BCE loss configuration rather than the default softmax. **imbalanced-learn** — the reference Python library for resampling strategies (SMOTE and its variants, though used more for structured/tabular data than sparse text features in practice). **`netcal` / manual ECE implementations** — the standard tooling for computing Expected Calibration Error and reliability diagrams as part of a classification eval. **Distillation and quantization** (a smaller student model trained to mimic a larger fine-tuned transformer's outputs, or a quantized/lower-precision version of the same model) — the standard production middle ground when a linear model's accuracy isn't sufficient but a full-size transformer's latency/cost is too high; this is frequently the actual answer to "how do we get transformer-level accuracy at closer-to-linear-model cost."

| Symptom | Cause | Fix |
|---|---|---|
| Model reports 95%+ accuracy but catches almost none of the rare/important class in production | Class imbalance — accuracy is dominated by majority-class performance, hiding minority-class failure | Switch to PR-AUC and per-class F1/recall as the reported metrics; apply class weighting or focal loss during training |
| Auto-approval pipeline gated on "confidence > 0.9" is approving a meaningfully wrong fraction of items | Model is uncalibrated — raw softmax/sigmoid scores don't reflect true correctness frequency (common in over-parameterized neural models) | Fit temperature scaling (or Platt/isotonic) on a held-out set; recompute ECE before and after to confirm the fix; never gate an automated decision on a raw, unvalidated confidence score |
| Multi-label classifier's predicted labels for an item look mutually exclusive when they shouldn't be | Softmax used instead of independent per-label sigmoid outputs | Switch to `K` independent sigmoids with per-label binary cross-entropy; verify the training data genuinely allows multiple simultaneous labels per item |
| Naive Bayes model performs unexpectedly badly on a task with strong negation-sensitive language | Independence assumption breaks down harder than usual — negation genuinely violates feature independence in a way the ranking-robustness argument doesn't rescue | Move to a linear model or fine-tuned transformer for this specific task; don't assume NB's usual robustness generalizes to every task |
| Fine-tuned transformer classifier's accuracy gain over the linear baseline is smaller than expected given the added cost | Task doesn't have enough genuine context-dependence to benefit from contextual representation — the classification signal was mostly lexical to begin with | Ship the linear baseline; re-evaluate the transformer only if the task changes to have more genuine contextual ambiguity |
| Threshold tuned on the training/validation distribution performs poorly after a data distribution shift | Class balance or label distribution in production has drifted from what the threshold was tuned against | Monitor prediction distribution drift as a leading indicator; re-tune thresholds periodically against a fresh sample rather than treating them as permanent |

---

## Tradeoffs & when NOT to use it

- **Don't skip the Naive Bayes or linear baseline and jump straight to fine-tuning a transformer.** At minimum, fit both cheaply (minutes, not hours) to establish an honest accuracy floor before spending GPU budget and engineering time on a transformer whose gain over that floor needs to be demonstrated, not assumed.
- **Don't report accuracy as the headline metric on an imbalanced corpus.** This is the document-classification analogue of NER's token-vs-entity-level F1 trap — a model can look excellent on accuracy while being useless on the class that actually matters; report PR-AUC and per-class metrics instead.
- **Don't trust a raw softmax or sigmoid score as a calibrated probability without checking.** Especially for any pipeline where the score gates an automated action — compute ECE and a reliability diagram before wiring a raw confidence threshold into production logic, and calibrate (temperature/Platt/isotonic) if the gap is meaningful.
- **Don't use a softmax output for a genuinely multi-label task.** It's a real, common implementation bug, not a stylistic choice — softmax's mutual-exclusivity constraint actively fights a training signal where multiple labels can be simultaneously true.
- **Don't fine-tune a transformer for narrow, high-precision, pattern-driven classification tasks a simpler model already handles well (obvious keyword-triggered filters, well-separated categories with distinctive vocabulary).** The accuracy ceiling a transformer buys is specifically valuable for genuine contextual ambiguity; paying its cost for a task that doesn't have much of that is a wasted investment.

---

## Interview questions

### Q1 — Derive Naive Bayes' decision rule from Bayes' theorem and explain what "naive" means precisely.
**Testing:** whether you can derive it, not recite the name.
**Answer:** `P(c|d) = P(d|c)*P(c)/P(d)`; since `P(d)` is constant across classes for a fixed document, the MAP decision picks the class maximizing `P(d|c)*P(c)`. "Naive" is the assumption that `P(d|c) = Π P(w_i|c)` — every word is conditionally independent of every other word given the class, which is false for real language (negation, idioms) but doesn't need to be true for classification, because only the *relative ranking* of `P(c_A|d)` vs `P(c_B|d)` needs to come out correctly, not the individual probability estimates.
**Follow-up trap:** *"If the independence assumption is false, why does NB still work reasonably well?"* — errors from the false assumption tend to bias both classes' probability estimates in similar directions, which cancels out in the pairwise comparison the decision rule actually needs — a real, if informal, explanation for NB's empirical robustness despite its implausible assumption.

### Q2 — Why does Naive Bayes need Laplace smoothing, and derive the formula.
**Answer:** Without smoothing, any word absent from a class's training documents gets `P(w|c) = 0`, and since the class likelihood is a product over all words, one zero-probability word zeroes the entire product for that class regardless of how strongly every other word supports it. Laplace smoothing adds a pseudo-count `α` to every word-class count: `P(w|c) = (count(w,c) + α) / (Σ count(w',c) + α*V)`, guaranteeing no probability is ever exactly zero while barely affecting words that already have substantial counts.
**Follow-up trap:** *"What happens if α is set very large?"* — the smoothed probabilities converge toward a uniform distribution over the vocabulary regardless of the actual observed counts, washing out the signal the model is supposed to learn — α is a real hyperparameter to tune, not a fixed constant to set and forget.

### Q3 — Multinomial vs. Bernoulli Naive Bayes: when would you choose each?
**Answer:** Multinomial models word frequency (how many times each word occurs) and is the standard choice for most text classification, especially longer documents where repetition carries signal. Bernoulli models only word presence/absence, discarding frequency, and can outperform Multinomial on short documents where a word's mere appearance carries most of the signal and frequency counts are sparse or noisy.
**Follow-up trap:** *"Would Bernoulli ever penalize a document for NOT containing a word that's strongly associated with a class?"* — yes, and this is a real structural difference from Multinomial: Bernoulli's likelihood explicitly includes a term for every vocabulary word's absence as well as presence, so a document missing a class-indicative word is actively penalized, not just failing to get credit for it — Multinomial has no equivalent mechanism.

### Q4 — Logistic regression vs. linear SVM for text classification: what's the actual difference in what they optimize?
**Answer:** Logistic regression minimizes cross-entropy loss on a sigmoid output, directly modeling `P(c|d)`. Linear SVM minimizes hinge loss, maximizing the margin between classes, and doesn't natively produce a calibrated probability — SVM decision scores need an extra calibration step (commonly Platt scaling) to become probability-like. In practice on TF-IDF features the two perform comparably; the practical choice is often about whether you need a native probability output.
**Follow-up trap:** *"Does SVM's margin-maximization make it more robust to outliers than logistic regression?"* — the hinge loss's flat region for correctly-classified points beyond the margin means those points contribute zero loss and gradient, so SVM is less influenced by points far from the decision boundary; logistic regression's loss never fully flattens, so distant points still contribute (diminishing) gradient — a real, nuanced difference worth naming rather than a blanket "SVM is more robust."

### Q5 — What specifically does a fine-tuned transformer buy over a linear TF-IDF model for classification, mechanically?
**Answer:** Contextual representation — the encoder's attention mechanism can represent negation scope, long-range dependency, and context-sensitive meaning that a bag-of-words TF-IDF vector structurally discards (word order is lost, and each word contributes independently of surrounding context). This is the same polysemy/context argument from static-vs-contextual word embeddings, applied at the document level instead of the word level.
**Follow-up trap:** *"If the task has no negation, sarcasm, or long-range dependency, would you still expect a transformer to beat the linear model?"* — the gain would likely be small, since the linear model's TF-IDF features already capture most of what a mostly-lexical classification signal needs — this is exactly the "measure before assuming the gain" pattern that should drive the tier choice, not defaulting to the most powerful model.

### Q6 — Design a multi-label classifier for tagging hotel listings with amenities (a listing can have any number of amenities). What architecture and why?
**Answer:** `K` independent sigmoid outputs, one per amenity, each trained with its own binary cross-entropy loss — not a softmax, since a listing can have zero, one, or many amenities simultaneously and softmax's forced mutual exclusivity would actively fight that training signal. Tune a separate decision threshold per amenity against a validation set rather than a single global 0.5 cutoff, since amenity base rates vary widely across the label set.
**Follow-up trap:** *"How would you evaluate this model?"* — report both micro-F1 (dominated by common amenities) and macro-F1 (treats rare and common amenities equally) since they answer different questions, plus subset accuracy/exact-match if getting every amenity right per listing matters for the downstream use case — a single blended number hides which of these tradeoffs actually matters to the business.

### Q7 — Your classifier reports 96% accuracy on a content-moderation task, but the violation class is 3% of the corpus. Should you trust that number?
**Testing:** the central class-imbalance trap.
**Answer:** No — a model predicting the non-violation class for every single item scores 97% accuracy on a 97/3 split while catching zero actual violations, so 96% accuracy tells you almost nothing about whether the model works. Report PR-AUC and per-class precision/recall/F1 instead, with specific attention to the violation class's recall, since that's almost certainly the metric the business actually cares about.
**Follow-up trap:** *"What if the model does have decent violation-class recall, but the false-positive rate is unacceptably high?"* — this is exactly why precision matters alongside recall under imbalance — PR-AUC captures the tradeoff curve, and the actual operating threshold should be chosen against the specific cost of a false positive (flagging clean content) versus a false negative (missing a real violation) for this task, not a default 0.5 cutoff.

### Q8 — Explain focal loss and how it differs mechanically from class weighting.
**Answer:** Class weighting multiplies each class's loss by a fixed weight inversely proportional to its frequency — a static, frequency-based rebalancing. Focal loss `FL(p_t) = -(1-p_t)^γ * log(p_t)` instead reweights by *difficulty*: as the model's confidence in the correct class `p_t` approaches 1 (an easy, well-classified example, regardless of that example's class frequency), the modulating factor `(1-p_t)^γ` shrinks toward zero, down-weighting easy examples' contribution to the loss and implicitly up-weighting hard or misclassified ones.
**Follow-up trap:** *"Could focal loss alone fix a severe class imbalance without any frequency-based weighting?"* — it helps but isn't a complete substitute — focal loss addresses difficulty, not directly frequency, and the two mechanisms are commonly combined (a class-weighted focal loss) rather than treated as interchangeable, since a rare class can still be systematically under-represented in the loss even after down-weighting easy majority-class examples.

### Q9 — What does it mean for a classifier to be "calibrated," and why might a fine-tuned transformer be badly calibrated even with high accuracy?
**Answer:** Calibration means predicted probabilities match empirical correctness frequency — among predictions the model assigns 0.9 confidence, roughly 90% should actually be correct. Modern over-parameterized neural networks, including fine-tuned transformers, are frequently and systematically overconfident (Guo et al., 2017) — their softmax outputs cluster near 0/1 more than their actual accuracy justifies, a phenomenon largely independent of raw accuracy, meaning a highly accurate model can still be badly miscalibrated.
**Follow-up trap:** *"Does higher accuracy imply better calibration?"* — no, they're largely independent properties; a model can be highly accurate and badly overconfident, or less accurate but well-calibrated (its uncertainty honestly reflects when it's likely wrong) — conflating the two is a common and consequential mistake when a raw confidence score is used to gate automated decisions.

### Q10 — Walk through temperature scaling: what does it fix, what does it not fix, and how is `T` fit?
**Answer:** Temperature scaling divides pre-softmax logits by a single learned scalar `T > 1` before applying softmax, smoothing (flattening) the output distribution to counteract overconfidence, without changing which class ranks highest — it fixes miscalibration, not accuracy or ranking. `T` is fit by minimizing negative log-likelihood on a held-out validation set (a one-dimensional optimization, cheap and fast, commonly done via L-BFGS in practice).
**Follow-up trap:** *"Would temperature scaling fix a model that's miscalibrated differently across different confidence ranges (e.g. overconfident at high confidence but underconfident at low confidence)?"* — no, and this is temperature scaling's real limitation — it's a single global parameter, so it can only apply one uniform correction; a more complex, non-uniform miscalibration pattern needs isotonic regression's non-parametric, monotonic mapping instead, at the cost of needing more validation data to fit reliably.

### Q11 — Why is ROC-AUC a misleading metric under severe class imbalance, and what should you use instead?
**Answer:** ROC-AUC's x-axis is false positive rate, computed as false positives divided by the (large) number of true negatives — under severe imbalance, the majority (negative) class is so large that even a substantial number of false positives barely moves the false positive rate, making ROC-AUC look deceptively good while precision on the minority class collapses. PR-AUC (precision-recall AUC) doesn't have this blind spot, since precision is computed against predicted positives directly, which shrinks meaningfully as false positives accumulate regardless of how large the negative class is.
**Follow-up trap:** *"Is ROC-AUC ever still the right metric?"* — yes, on roughly balanced classes or when false positive rate against the full negative population is genuinely the quantity of interest (some fraud/security contexts specifically care about FPR against a huge population) — the choice depends on which axis of error actually matters for the downstream decision, not a blanket rule that PR-AUC always wins.

### Q12 — Your team wants to auto-approve any classification with confidence above 0.95 to cut manual review volume. What do you check before agreeing to that threshold?
**Testing:** the calibration-meets-production-decision synthesis.
**Answer:** First and foremost, whether the model is calibrated at all — compute ECE and a reliability diagram, specifically checking the accuracy of predictions that actually fall in the 0.95+ confidence bin, not overall accuracy. If the model is overconfident (a well-documented default assumption for neural classifiers), a raw 0.95 score might correspond to genuine accuracy well below 95%, meaning the "auto-approve" threshold is silently approving more errors than the business believes. Calibrate first (temperature/Platt/isotonic), then re-derive the threshold against the calibrated scores and the actual acceptable error rate for auto-approval.
**Follow-up trap:** *"What if calibration fixes the overall ECE but the high-confidence bin specifically is still off?"* — check calibration per-bin, not just the aggregate ECE number, since an aggregate metric can look acceptable while the specific bin the business is about to act on is still poorly calibrated — this is exactly why a reliability diagram, not just a single scalar ECE, belongs in the pre-launch review.

### Q13 — Compare the cost/latency profile of Naive Bayes, a linear model, and a fine-tuned transformer at 10 million documents/day. What would actually change your recommendation?
**Answer:** Naive Bayes and linear models both run comfortably on CPU at that volume, with per-document inference in the sub-millisecond to low-single-digit-millisecond range and no GPU dependency — the infrastructure cost difference between them is minor. A fine-tuned transformer at 10M documents/day needs either a large GPU fleet or batched, throughput-optimized serving, and the infrastructure cost difference against the linear tier is real and substantial at that volume. The recommendation changes specifically when the accuracy gap between the linear baseline and the transformer, measured on your actual task, translates into a business-value gain that exceeds that infrastructure delta — not a general preference for either tier.
**Follow-up trap:** *"What if the transformer's accuracy gain is large but only on 5% of the traffic (a specific hard subpopulation)?"* — a cascade/routing architecture is the right answer here: run the cheap linear model on all traffic, and route only the subset it's uncertain about (low-confidence predictions) to the more expensive transformer for a second pass — this captures most of the accuracy gain at a fraction of the full-transformer infrastructure cost, and naming this pattern is a strong senior signal.

### Q14 — A Naive Bayes spam filter that's worked well for years starts missing an increasing fraction of a new spam campaign. What's happening and how do you fix it without over-engineering the response?
**Answer:** Almost certainly vocabulary/concept drift — the new campaign uses different vocabulary the model's word-class probability estimates haven't seen or have under-weighted, the same underlying issue as the classical-NLP module's vocabulary-drift failure mode, recurring here at the classifier level. The proportionate fix, given NB's near-instant retraining cost, is frequent incremental retraining on recent labeled examples (spam filters are one of the clearest cases where NB's O(n*d) single-pass training cost is a genuine production advantage, since it supports much more frequent retraining than a gradient-trained model would at the same infrastructure budget) rather than jumping straight to a heavier model.
**Follow-up trap:** *"If retraining frequently doesn't fully fix it, would you then escalate to a transformer?"* — only if you've confirmed the failure is genuinely about missing contextual signal (obfuscated phrasing, semantic evasion of keyword-level detection) rather than just needing fresher training data — escalate the model tier only after ruling out the cheaper explanation and fix.

### Q15 — Design the text classification strategy for a marketing content platform that needs to route user-generated reviews to different moderation queues (spam, policy violation, needs-response, routine) at high volume with a tight latency SLA.
**Testing:** synthesis across tiers, imbalance, calibration, and multi-label framing.
**Answer:** This is likely multi-label in practice (a review can be both spam and a policy violation simultaneously) rather than single-label, so start with the correct architecture — independent per-label sigmoids, not softmax. Given the tight latency SLA and high volume, start with a linear model on TF-IDF features as the production baseline, measuring its accuracy against a fine-tuned transformer fitted on the same data to establish the real accuracy gap before committing to the more expensive tier; if the gap is concentrated in specific hard categories (nuanced policy violations needing contextual understanding) rather than uniform across all labels, a cascade — linear model handles the high-confidence bulk, low-confidence or specifically-hard-category items route to a transformer second pass — captures most of the accuracy where it matters without paying transformer cost on every review. Class imbalance is real here (most reviews are routine, policy violations are rare) — use class-weighted or focal loss during training and report PR-AUC per label, not blended accuracy. Calibrate before wiring any confidence-based auto-routing decision, since misrouting a policy violation to "routine" because of an overconfident low score is a real operational and possibly compliance risk.
**Follow-up trap:** *"How would you handle a brand-new policy category added mid-flight, with no labeled training data yet?"* — this is exactly where a zero-shot LLM call earns its cost, temporarily, for the new category specifically — route only that category's classification through an LLM call while collecting labeled examples via active learning (directly connecting back to the NER module's annotation-bootstrapping pattern), then fold it into the trained multi-label model once enough data exists, rather than either waiting for a full retrain cycle or paying LLM cost for the whole pipeline indefinitely.

---

## Red flags that fail you

- Reporting accuracy as the headline metric on a visibly imbalanced classification task.
- Not knowing why Naive Bayes' independence assumption doesn't need to be true for the classifier to rank classes correctly.
- Using a softmax output for a genuinely multi-label problem.
- Treating a raw softmax/sigmoid score as a calibrated probability without checking ECE or a reliability diagram.
- Not knowing modern neural classifiers are typically overconfident by default (Guo et al., 2017), or claiming high accuracy implies good calibration.
- Reaching for a fine-tuned transformer as the default first model without measuring a cheaper baseline first.
- Confusing class weighting (frequency-based) with focal loss (difficulty-based) as if they were the same mechanism.
- Not knowing PR-AUC is the standard replacement for ROC-AUC under severe class imbalance, or why.

---

## Cheat card

```
NAIVE BAYES   P(c|d) ∝ P(c) * Π P(w_i|c)  [independence assumed, false but ranking-robust]
  Multinomial: word FREQUENCY. Bernoulli: word PRESENCE/ABSENCE (better on short docs).
  Laplace smoothing: P(w|c) = (count(w,c)+α)/(Σcount(w',c)+α*V)   [α=1 classic, tune it]
  training O(n*d), no gradient descent — fastest classifier here, cheap frequent retraining.

LINEAR MODELS   discriminative, no independence assumption.
  LogReg: sigmoid + cross-entropy, native probability output.
  Linear SVM: hinge loss, margin-max, NOT natively calibrated (needs Platt scaling).
  Best cost/accuracy ratio for most structured classification tasks.

TRANSFORMER   contextual representation (negation, long-range dep, sarcasm-adjacent context) —
  the real accuracy lever bag-of-words structurally lacks. Cost: single-digit-tens ms/doc on GPU
  vs sub-ms-few-ms for linear on CPU. Worth it only when context genuinely matters AND measured.

MULTI-LABEL   K independent sigmoids + per-label BCE, NOT softmax (softmax forces exclusivity).
  Tune per-label thresholds, not one global 0.5.
  Eval: micro-F1 (common labels dominate) · macro-F1 (equal weight per label) ·
        subset accuracy/exact-match (strict, no partial credit) · Hamming loss (most forgiving)

CLASS IMBALANCE   accuracy is near-meaningless (majority-class model can score 95%+, catch 0%).
  class weighting: weight_c = N/(K*n_c), frequency-based.
  focal loss: FL(p_t) = -(1-p_t)^γ * log(p_t), γ≈2, DIFFICULTY-based, easy examples → 0 loss.
  metric: PR-AUC (not ROC-AUC — ROC's FPR axis stays deceptively good vs huge negative class)

CALIBRATION   confidence ≠ correctness by default. Neural nets are typically OVERCONFIDENT
  (Guo et al. 2017) regardless of accuracy — the two are independent properties.
  Temperature scaling: logits/T before softmax, single param, fit via NLL on held-out set,
    fixes global miscalibration, doesn't touch ranking/accuracy.
  Platt scaling: logistic regression on raw scores. Isotonic regression: nonparametric,
    handles non-uniform miscalibration, needs more validation data.
  ECE: bin by confidence, avg |confidence − accuracy| per bin, weighted. Check PER-BIN,
    not just aggregate, before gating an automated decision on a threshold.

COST TIER RULE   measure NB/linear baseline FIRST. Escalate to transformer only when the
  measured accuracy gap justifies the latency/GPU cost. Cascade (cheap model on bulk traffic,
  expensive model on low-confidence subset) often captures most of the gain at a fraction of cost.
```

## Sources

- [Naive Bayes and Text Classification I — Raschka (arXiv survey)](https://arxiv.org/abs/1410.5329) — accessed 2026-08-02
- [Naive Bayes text classification — Stanford IR Book](https://nlp.stanford.edu/IR-book/html/htmledition/naive-bayes-text-classification-1.html) — accessed 2026-08-02
- [MultinomialNB — scikit-learn documentation](https://scikit-learn.org/stable/modules/generated/sklearn.naive_bayes.MultinomialNB.html) — accessed 2026-08-02
- [Focal Loss for Dense Object Detection — Lin et al., 2017](https://arxiv.org/abs/1708.02002) — accessed 2026-08-02
- [On Calibration of Modern Neural Networks — Guo, Pleiss, Sun, Weinberger, 2017](https://arxiv.org/abs/1706.04599) — accessed 2026-08-02
- [Calibrating Deep Neural Networks using Focal Loss — Mukhoti et al., 2020](https://arxiv.org/abs/2002.09437) — accessed 2026-08-02
- [scikit-learn CalibratedClassifierCV documentation](https://scikit-learn.org/stable/modules/generated/sklearn.calibration.CalibratedClassifierCV.html) — accessed 2026-08-02
- [BERT: Pre-training of Deep Bidirectional Transformers for Language Understanding — Devlin et al., 2018](https://arxiv.org/abs/1810.04805) — accessed 2026-08-02
- [Machine Learning Scientist III, NLP at Expedia Group — WORK180 (Bayesian, LDA, NER, Random Forests requirements)](https://work180.com/en-us/for-women/employer/expedia/job/458598/machine-learning-scientist-iii-nlp) — accessed 2026-08-02

## Changelog
- 2026-08-02 — created
