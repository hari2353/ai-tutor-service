# Causal Inference for Marketing: Uplift/CATE Modeling, Diff-in-Diff, Propensity Score Matching, Instrumental Variables, Synthetic Control

> **Track:** T32 Applied NLP & Marketing ML · **Time:** 3h · **Prereqs:** T32-experiment-design, basic regression/classification · **Updated:** 2026-08-02
> **Module id:** `T32-causal-inference` · **Tags:** stats, critical

## The 30-second version

A model trained to predict "will this user convert" is optimizing the wrong target for marketing decisions — it will happily rank users who would have converted anyway (the "sure things") above users who convert *because of* the treatment (the "persuadables"), because both groups have high predicted conversion probability and the model was never asked to tell them apart. Uplift modeling fixes this by estimating the **conditional average treatment effect (CATE)** — `E[Y(1)-Y(0) | X]`, the difference between a user's potential outcome under treatment and under control, conditional on their features — via a two-model (T-learner) approach, class-transformation, or causal forests, each with different bias-variance tradeoffs. When you can't randomize at all, difference-in-differences, propensity score matching, instrumental variables, and synthetic control are the four standard quasi-experimental tools for recovering a causal estimate from observational data, each leaning on a different untestable assumption (parallel trends, unconfoundedness, instrument exogeneity, donor-pool comparability respectively) that you must be able to name and defend. The single most expensive mistake in applied marketing ML is deploying a correlation-trained propensity/conversion model to decide who gets targeted: it optimizes prediction accuracy, not incremental lift, and routinely burns budget on users who needed no persuasion at all.

## Why this gets asked

Expedia Marketing Content ML Science exists to answer "did this content change, this promotion, this personalization actually cause more bookings, or did it just correlate with users who were going to book anyway." The interviewer has watched a targeting model with excellent AUC get deployed, watched marketing spend go up, and watched incremental revenue barely move — because the model was excellent at finding likely bookers, not at finding bookers who needed the nudge. They want to know you reach for CATE estimation and quasi-experimental design as the default framing for "does X cause Y," not predictive ML dressed up as causal inference.

---

## Lineage: past → present → future

**What came before.** The Rubin Causal Model / potential outcomes framework (Neyman 1923 for randomized experiments, generalized by Donald Rubin in the 1970s) formalized what "causal effect" even means: `Y_i(1) - Y_i(0)`, the difference between what would happen to unit `i` under treatment versus control — the fundamental problem being you only ever observe one of the two for any given unit, never both. Before this was widely operationalized in industry, marketing measurement relied almost entirely on observational correlation — response modeling, propensity-to-buy scores, RFM segmentation — none of which distinguish a caused conversion from a coincidental one. Randomized controlled trials solve the identification problem cleanly by construction (randomization makes treatment independent of potential outcomes), which is why online controlled experiments became the gold standard the moment web-scale randomization was feasible, but not everything can be randomized: pricing changes with legal/PR risk, macro campaigns with no valid control group, historical data with no experiment ever run on it.

**Where it stands now.** Uplift modeling is mainstream at large-scale marketing and ad-tech organizations, with mature open-source tooling (Microsoft's EconML, Uber's CausalML) implementing meta-learners (S/T/X-learners) and causal forests (Athey, Tibshirani, Wager, 2019, generalizing Breiman's random forest to target heterogeneous treatment effects instead of outcome prediction) as standard building blocks. For observational (non-randomized) causal questions, difference-in-differences and synthetic control are the econometrics-derived defaults for aggregate/geo-level marketing measurement (media mix modeling's incrementality validation layer routinely uses geo holdouts analyzed via DiD or synthetic control), while propensity score matching remains common but increasingly criticized in the causal inference literature for concealing rather than removing confounding when there's imbalance in the underlying covariate distributions. The live disagreement: **PSM's declining reputation** — King and Nielsen's widely-cited "Why Propensity Scores Should Not Be Used for Matching" (2019) argues PSM can *increase* imbalance and model dependence versus simpler matching or no matching at all in some regimes, while it remains extremely common in practice because it's intuitive and easy to communicate to non-technical stakeholders — a real tension between statistical rigor and organizational usability that a senior candidate should be able to name.

**Where it's heading.** Causal ML meta-learners (X-learner, R-learner, DR-learner) that combine flexible ML function approximation with formal debiasing (Neyman orthogonality / double machine learning, Chernozhukov et al. 2018) are becoming the default over naive two-model approaches wherever teams have the statistical maturity to implement them correctly — moderate-to-high confidence, this is where causal ML research has concentrated for the past several years and where CausalML/EconML tooling has invested. Post-cookie identity loss (see the marketing-measurement module) is pushing geo-level and aggregate causal methods (DiD, synthetic control, geo holdouts) back into prominence relative to user-level attribution, since aggregate methods don't require the individual-level tracking that's disappearing — high confidence this shift is real and already underway. More speculative: automated, continuously-running "causal AI" platforms that treat every product change as an implicit experiment and estimate its incremental effect via a standing DiD/synthetic-control pipeline rather than a bespoke analysis per question — exists in early internal-tooling form at a few large tech companies, not yet a settled industry pattern.

---

## Mental model

The persuadables quadrant — why a plain conversion model targets the wrong people:

```
                        WOULD CONVERT              WOULD NOT CONVERT
                        WITHOUT TREATMENT           WITHOUT TREATMENT

  CONVERTS WITH        "Sure things"                "Persuadables"
  TREATMENT             high predicted P(convert)    the ONLY group where
                         -- a plain model loves       treatment causally
                         them, but treating them       matters. Often modest
                         wastes budget: they were       predicted P(convert)
                         converting anyway.              -- a plain model
                                                          ranks them LOW.

  DOESN'T CONVERT      "Lost causes"                "Sleeping dogs" /
  WITH TREATMENT        never converts either way    "Do-not-disturbs"
                         -- wasted spend either way.   treatment actively
                                                        HURTS them (e.g. an
                                                        email nudge that
                                                        reminds them to
                                                        cancel). Only
                                                        uplift modeling
                                                        finds this group.
```

A plain propensity/conversion model ranks by `P(convert | treated, X)` and cannot distinguish "sure thing" from "persuadable" because both have high predicted probability. Uplift modeling ranks by the *difference* `P(convert|treated,X) - P(convert|control,X)`, which is exactly zero for sure things and lost causes, positive for persuadables, and negative for sleeping dogs.

---

## How it actually works

### Uplift / CATE modeling: two-model, class transformation, causal forests

**The estimand.** CATE is `tau(x) = E[Y(1) - Y(0) | X=x]` — the expected treatment effect for units with features `x`. You never observe both `Y(1)` and `Y(0)` for the same unit (the fundamental problem of causal inference), so every uplift method is really a strategy for estimating this unobservable difference from a randomized (or quasi-randomized) dataset where each unit shows only one of the two outcomes.

**Two-model approach (T-learner).** Fit one model `mu_1(x) = E[Y|X=x, W=1]` on the treated group and a separate model `mu_0(x) = E[Y|X=x, W=0]` on the control group, then estimate `tau_hat(x) = mu_1(x) - mu_0(x)`. Simple, works with any off-the-shelf regressor/classifier, and is the standard first baseline. Its weakness: each model is fit independently and can have very different bias/variance/regularization behavior, so subtracting two separately-fit, separately-noisy models can amplify noise in the difference — small errors in each model don't cancel, they compound. It also doesn't share statistical strength across the treatment and control populations, which hurts when one arm is much smaller than the other (common in marketing, where "treated" is often a minority of exposed users versus a huge organic control pool).

**Class transformation (class variable transformation / "Lai's" approach).** Construct a transformed target `Z = Y*W + (1-Y)*(1-W)` (or, more commonly cited, flips the label for the control group and combines both arms into one dataset), so a single binary classifier trained on `Z` directly estimates `2*P(Z=1|X) - 1 ≈ tau(x)` under a balanced (50/50) randomized assignment. Advantage: one model instead of two, avoiding the two-model approach's noise-compounding problem, and it's cheap to implement with any standard classifier. Disadvantage: the equivalence to CATE only holds cleanly under exactly-balanced treatment assignment (`P(W=1)=0.5`); with unbalanced assignment (again, very common in real marketing data — you rarely treat exactly half your users) it requires a correction, and skipping that correction silently biases the estimate.

**Causal forests.** Generalize Breiman's random forest so that instead of splitting nodes to reduce prediction-outcome variance, splits are chosen to maximize *heterogeneity in the estimated treatment effect* across the resulting leaves — each tree partitions the feature space to separate high-uplift regions from low/negative-uplift regions, and the forest averages many such trees for stability, with an "honest" splitting procedure (using disjoint samples for choosing splits versus estimating effects within them) that gives asymptotically valid confidence intervals for `tau(x)` — a genuine statistical guarantee the two-model and class-transformation approaches don't offer out of the box. Cost: more complex to implement and tune correctly, more compute, and the interpretability of a single decision path is lost relative to a single causal tree (the non-ensembled precursor).

**Why "the correlation-trained model optimizes the wrong thing" is the central point of this whole module.** A conversion-probability model trained the standard supervised-learning way — maximize AUC/log-loss predicting `Y` from `X` on the treated population — has *no mechanism* in its objective function to distinguish a user who converts because of the treatment from a user who converts regardless of it. It will rank both as "high probability," and a targeting policy built on that ranking will spend disproportionately on sure things, the group where treatment is pure waste. This isn't a subtle implementation detail; it's the core reason targeting models built for click-through or conversion prediction routinely show great offline AUC and mediocre-to-negative incremental lift when actually A/B tested against a holdout.

### Difference-in-differences (DiD)

Compares the change over time in a treated group against the change over time in a comparable untreated (control) group: `DiD = (Y_treat,post - Y_treat,pre) - (Y_control,post - Y_control,pre)`. The identifying assumption is **parallel trends**: absent treatment, the treated group's outcome would have moved in parallel with the control group's — an assumption you cannot directly test on post-treatment data (by definition), only support with pre-treatment trend evidence (do the two groups' outcomes move together *before* treatment?). This is the standard tool for geo-level marketing incrementality: launch a campaign in a subset of markets, treat the rest as control, and use pre/post trend comparison to estimate lift, especially useful when true randomization at the individual level isn't feasible (a national TV or radio campaign, a pricing change that can't be individually randomized for legal reasons).

### Propensity score matching (PSM)

Estimate `e(x) = P(W=1|X=x)` (the propensity score — probability of receiving treatment given covariates) via a logistic regression or similar model on observational data, then match treated units to control units with similar propensity scores, and compare outcomes within matched pairs. The identifying assumption is **unconfoundedness / ignorability**: conditional on `X`, treatment assignment is as good as random — i.e., you've measured every confounder that affects both treatment assignment and the outcome. This is the assumption's weak point: it's fundamentally untestable, because you can never be sure you haven't omitted an important confounder, and any omitted confounder that affects both treatment and outcome biases the estimate in an unknown direction. PSM's practical reputation has declined in the causal inference literature (King & Nielsen, 2019) because matching on a single scalar propensity score can, in some regimes, *increase* covariate imbalance and model dependence relative to full matching or direct covariate adjustment — it remains common in industry because it's intuitive to explain ("we compared similar users") even where more robust alternatives exist.

### Instrumental variables (IV)

Used when unconfoundedness is implausible — there's a suspected unobserved confounder affecting both treatment and outcome — and you have access to an **instrument** `Z`: a variable that affects treatment assignment but affects the outcome *only through* its effect on treatment (the exclusion restriction), and is otherwise independent of the confounders (instrument exogeneity). The classic marketing example: geographic or temporal variation in ad server outages or auction pricing quirks that shift who sees an ad for reasons unrelated to their underlying propensity to buy, used as an instrument for ad exposure. Two-stage least squares (2SLS) is the standard estimator: regress treatment on the instrument (first stage), then regress the outcome on the *predicted* treatment from the first stage (second stage) — this isolates the variation in treatment that's driven by the instrument (assumed exogenous) rather than by confounders. The exclusion restriction is the assumption you cannot test and must defend with a domain argument, and a weak instrument (one that barely predicts treatment) produces a highly unstable, high-variance estimate even if the exclusion restriction technically holds.

### Synthetic control

When you have one (or a few) treated unit(s) — one market, one region, one store chain — and a pool of untreated "donor" units, construct a **synthetic control** as a weighted combination of donor units chosen so the weighted combination closely tracks the treated unit's outcome *before* treatment; then use the gap between the treated unit and its synthetic counterpart *after* treatment as the estimated causal effect. This generalizes DiD's single-control-group comparison to a data-driven weighted blend of many potential controls, and is the standard tool when you have exactly one or a handful of treated geos and no single obviously-comparable control market. The identifying assumption is that the synthetic control, built from pre-treatment fit, would have continued to track the treated unit absent treatment — the same logical structure as parallel trends, but constructed rather than assumed to hold for a single arbitrary control group.

---

## Build it from scratch

```python
# untested sketch — two-model uplift estimator and a class-transformation baseline
import numpy as np
from sklearn.ensemble import GradientBoostingClassifier

def two_model_uplift(X_treat, y_treat, X_control, y_control, X_query):
    model_treat = GradientBoostingClassifier().fit(X_treat, y_treat)
    model_control = GradientBoostingClassifier().fit(X_control, y_control)
    p1 = model_treat.predict_proba(X_query)[:, 1]
    p0 = model_control.predict_proba(X_query)[:, 1]
    return p1 - p0  # tau_hat(x); target the top of this ranking, not top of p1 alone

def class_transformation_uplift(X, y, w, X_query):
    # requires balanced treatment assignment (P(W=1) ~= 0.5); correct otherwise
    z = (y * w) + ((1 - y) * (1 - w))
    model = GradientBoostingClassifier().fit(X, z)
    p_z = model.predict_proba(X_query)[:, 1]
    return 2 * p_z - 1  # approximates tau(x) under balanced assignment

# Difference-in-differences point estimate, untested sketch
def did_estimate(y_treat_pre, y_treat_post, y_control_pre, y_control_post):
    return (np.mean(y_treat_post) - np.mean(y_treat_pre)) - (
        np.mean(y_control_post) - np.mean(y_control_pre)
    )

# Propensity score matching, minimal nearest-neighbor version
from sklearn.linear_model import LogisticRegression
from sklearn.neighbors import NearestNeighbors

def psm_match(X, w, y):
    propensity = LogisticRegression().fit(X, w).predict_proba(X)[:, 1].reshape(-1, 1)
    treated_idx = np.where(w == 1)[0]
    control_idx = np.where(w == 0)[0]
    nn = NearestNeighbors(n_neighbors=1).fit(propensity[control_idx])
    _, match_idx = nn.kneighbors(propensity[treated_idx])
    matched_control_y = y[control_idx][match_idx.flatten()]
    return np.mean(y[treated_idx]) - np.mean(matched_control_y)
```

Reference next: Uber's `causalml` and Microsoft's `EconML` libraries for production-grade meta-learners (S/T/X/R-learners), causal forests, and double machine learning; both ship benchmark datasets to sanity-check an implementation against known ground truth.

---

## How it's done in production

**CausalML** (Uber) and **EconML** (Microsoft) are the two dominant open-source libraries — CausalML leans toward marketing/growth use cases with uplift trees and meta-learners out of the box, EconML leans toward the econometrics-flavored double machine learning and orthogonal-learner family. **DoWhy** (Microsoft) provides a structured causal-graph-first workflow (define assumptions explicitly via a DAG, identify the estimand, estimate, then refute) that's increasingly used to force the "what are you assuming" conversation into the actual codebase rather than a slide. Geo-level incrementality testing (holding out entire markets from a campaign) commonly analyzed via DiD or synthetic control is the standard companion to media mix modeling at large advertisers, precisely because it doesn't require individual-level identity resolution.

| Symptom | Cause | Fix |
|---|---|---|
| Uplift model's top-decile targets show great offline AUC but flat incremental lift when A/B tested | Model was trained/evaluated as a conversion predictor, not an uplift estimator — it's ranking sure things, not persuadables | Re-frame the objective as CATE estimation (two-model, class transformation, causal forest) and evaluate with an uplift-specific metric (Qini curve / uplift AUC), not classification AUC |
| Class-transformation uplift estimate looks biased | Treatment assignment wasn't actually 50/50 in the training data | Apply the correction factor for unbalanced assignment, or switch to the two-model approach / causal forest, which don't require balance |
| Two-model uplift estimates are extremely noisy, flipping sign on similar users | Independent models on treatment/control amplify each other's individual noise when subtracted | Increase regularization on both models symmetrically, pool more data, or move to a causal forest / X-learner that shares information across arms |
| DiD estimate looks implausibly large | Parallel trends assumption violated — treated and control groups were already diverging before treatment | Plot pre-treatment trends explicitly; if they weren't parallel before, DiD is not identified here regardless of what the post-period gap shows |
| PSM "matched" comparison still shows residual imbalance on an important covariate | Propensity score is a single scalar summarizing many covariates — units with similar scores can still differ substantially on any individual covariate | Check covariate balance post-matching directly (standardized mean differences), not just propensity score balance; consider full/exact matching on the most important confounders instead |
| Synthetic control's pre-treatment fit is poor | Donor pool doesn't contain units similar enough to the treated unit to construct a good synthetic match | Expand or curate the donor pool; if no good synthetic fit is achievable, the method isn't identified for this case and a different design is needed |

---

## Tradeoffs & when NOT to use it

- **Don't deploy a plain conversion/propensity model as a targeting policy and call the result "incrementality."** It optimizes prediction accuracy on `Y`, not the treatment effect, and will systematically over-target sure things — always validate a targeting policy's actual incremental lift with a genuine holdout, not offline AUC.
- **Don't use PSM as your only causal method when you can instead run — or already have — a real experiment.** PSM's unconfoundedness assumption is unfalsifiable; if randomization is available at any reasonable cost, it beats every observational method on identification strength alone.
- **Don't use an instrumental variable without a defensible, domain-grounded exclusion restriction.** A weak or implausible instrument produces an estimate that looks precise (a number comes out) but rests on an assumption you cannot support if challenged — naming a bad instrument in an interview is itself a red flag.
- **Don't use synthetic control with a thin, dissimilar donor pool.** A poor pre-treatment fit means the "synthetic" unit isn't actually tracking what the treated unit would have done, and the post-treatment gap reflects donor-pool mismatch as much as any real effect.
- **Causal forests are overkill for a simple, well-powered, single-treatment-effect question** — if you just need the average treatment effect with no heterogeneity analysis, a straightforward difference-in-means from a randomized experiment is simpler, more interpretable, and no less valid; reach for CATE machinery specifically when heterogeneity and targeting are the actual business question.

---

## Interview questions

### Q1 — Why does a standard conversion-probability model make a bad targeting policy for a marketing campaign?
**Testing:** the core conceptual point of the module.
**Answer:** It's trained to predict `P(Y=1|X)`, which is high for both "sure things" (would convert regardless) and "persuadables" (convert because of treatment) — the model has no signal in its training objective that distinguishes them. A targeting policy built on this ranking spends disproportionately on sure things, where treatment is pure waste, and can miss persuadables who have a modest baseline conversion probability but a large treatment effect.
**Follow-up trap:** *"Couldn't you just target everyone with predicted probability above some threshold?"* — that still doesn't separate sure things from persuadables within the high-probability group; the fix is estimating the treatment effect directly (CATE/uplift), not adjusting a threshold on a conversion-probability score.

### Q2 — Define CATE and explain why it can't be observed directly for any individual.
**Answer:** `tau(x) = E[Y(1)-Y(0)|X=x]`. Any given unit is either treated or not, so you only ever observe `Y(1)` or `Y(0)`, never both — the fundamental problem of causal inference. CATE is estimated by comparing outcomes across similar units in the treated and control groups (or via meta-learners built on this comparison), never measured directly for a single unit.
**Follow-up trap:** *"So is uplift modeling just imputing the missing potential outcome?"* — functionally, meta-learners like the T-learner are doing exactly that (predicting the counterfactual outcome with a model trained on the other arm), and naming this explicitly shows you understand what the models are actually doing under the hood.

### Q3 — Walk through the two-model (T-learner) approach and its main weakness.
**Answer:** Fit `mu_1(x)` on the treated group and `mu_0(x)` on the control group independently, estimate `tau_hat(x) = mu_1(x)-mu_0(x)`. Weakness: the two models are fit independently with potentially different bias/variance behavior, so their difference can amplify noise rather than cancel it — especially when one arm has much less data than the other, a common real-world imbalance.
**Follow-up trap:** *"How would you fix the noise-amplification problem without switching methods entirely?"* — symmetric regularization across both models, or pooling more data / features shared across arms; if that's insufficient, move to an X-learner or causal forest, which share information across arms by design.

### Q4 — What does class-transformation uplift modeling assume that the two-model approach doesn't need?
**Answer:** It assumes (or requires correcting for) balanced treatment assignment — `P(W=1) ≈ 0.5` — because the transformed label `Z` only maps cleanly to `2P(Z=1|X)-1 ≈ tau(x)` under that balance. The two-model approach has no such requirement since it fits each arm separately regardless of relative arm sizes.
**Follow-up trap:** *"Your marketing data has 20% treated, 80% control — can you still use class transformation?"* — yes, but only with the correction factor for unbalanced assignment; using the uncorrected version on unbalanced data silently biases the estimate, and a candidate who doesn't flag this hasn't fully understood the method's assumptions.

### Q5 — What does a causal forest optimize for that a standard random forest doesn't?
**Answer:** Standard random forests split nodes to reduce prediction error on the outcome. Causal forests split to maximize *heterogeneity in the estimated treatment effect* across the resulting leaves, using "honest" splitting (disjoint samples for choosing splits vs. estimating effects) to get asymptotically valid confidence intervals on `tau(x)` per leaf/region — a formal statistical guarantee the two-model and class-transformation approaches don't provide out of the box.
**Follow-up trap:** *"Given that guarantee, why wouldn't you always use a causal forest?"* — more compute, more complex tuning, loss of single-decision-path interpretability versus a single causal tree, and it's overkill when you only need an average effect with no heterogeneity/targeting use case.

### Q6 — Explain difference-in-differences and its key untestable assumption.
**Answer:** `DiD = (Y_treat,post - Y_treat,pre) - (Y_control,post - Y_control,pre)`, isolating the treated group's change over the control group's change. Key assumption: parallel trends — absent treatment, the two groups' outcomes would have moved together — which can't be directly verified post-treatment, only supported by evidence that pre-treatment trends were actually parallel.
**Follow-up trap:** *"How would you defend a DiD estimate if someone challenges the parallel trends assumption?"* — show the pre-treatment trend lines explicitly, run a placebo test (check for a "fake" effect in a pre-treatment period where none should exist), and be honest that this is support, not proof, since the assumption is fundamentally about an unobserved counterfactual.

### Q7 — What's the identifying assumption behind propensity score matching, and why has it lost credibility in parts of the causal inference literature?
**Answer:** Unconfoundedness/ignorability — conditional on measured covariates `X`, treatment assignment is as good as random, i.e., no unmeasured confounders. It's lost credibility partly because King & Nielsen (2019) showed matching on a single scalar propensity score can, in some regimes, increase covariate imbalance and model dependence relative to full/exact matching or direct adjustment — a counterintuitive but real critique of a very widely used method.
**Follow-up trap:** *"If PSM is criticized, why is it still so common?"* — it's intuitive to communicate ("we compared similar users") and easy to implement, which matters for stakeholder buy-in even where a more statistically robust alternative exists; naming this organizational reality, not just the statistics, is the senior-level answer.

### Q8 — Explain instrumental variables and the exclusion restriction with a marketing-relevant example.
**Answer:** An instrument `Z` affects treatment assignment but affects the outcome only *through* treatment (exclusion restriction), and is independent of unmeasured confounders. Marketing example: a temporary ad-server outage or auction-pricing quirk that shifts which users happen to see an ad for reasons unrelated to their underlying purchase intent — using that exposure variation (rather than raw exposure, which is confounded by intent) to estimate the causal effect of ad exposure via two-stage least squares.
**Follow-up trap:** *"What breaks the exclusion restriction in that example?"* — if the outage also correlates with something that independently affects purchasing (e.g., it happened during a site-wide performance issue that also slowed checkout), the instrument now affects the outcome through a channel other than ad exposure, and the exclusion restriction is violated.

### Q9 — When would you use synthetic control instead of a simple difference-in-differences?
**Answer:** When you have one or very few treated units (a single market, a single store chain) and no single obviously comparable control — synthetic control constructs a data-driven weighted blend of many donor units chosen to match the treated unit's pre-treatment trajectory, generalizing DiD's single-control comparison into something more defensible when no natural single control exists.
**Follow-up trap:** *"What if the donor pool doesn't produce a good pre-treatment fit?"* — then the method isn't identified for this case; a poor pre-treatment fit means the "synthetic" counterfactual doesn't actually resemble what the treated unit would have done, and the post-period gap conflates donor mismatch with real effect — say this rather than reporting the number anyway.

### Q10 — How would you evaluate an uplift model, given that you can never observe both potential outcomes for the same user?
**Answer:** Use uplift-specific evaluation on a randomized holdout: the Qini curve / uplift AUC, which ranks users by predicted uplift and measures cumulative incremental conversions captured as you target progressively larger fractions of the ranked population, compared against random targeting. This works because on a randomized holdout you can compute *group-level* incremental lift for any top-k slice (treated minus control conversion rate within that slice) even though you still can't see individual counterfactuals.
**Follow-up trap:** *"Why can't you just use classification AUC on the uplift score?"* — because there's no single ground-truth label for uplift per individual to score against; Qini/uplift-AUC works around this by evaluating aggregate lift within ranked subgroups on a properly randomized dataset instead.

### Q11 — Design a causal measurement plan for whether a new personalized email campaign increases bookings, given you cannot run a clean randomized holdout because Legal has blocked withholding personalization from any user for fairness reasons.
**Testing:** synthesis under a real organizational constraint, close to what actually happens.
**Answer:** Push back first on whether a true holdout is really infeasible (a small percentage holdout, even 5%, is usually defensible and vastly preferable to no randomization at all — this is worth escalating before abandoning it). If genuinely blocked, fall back to a geo-level design: roll out to a subset of markets/regions first (staggered rollout), and estimate incremental lift via difference-in-differences or synthetic control comparing rolled-out vs. not-yet-rolled-out geos, checking pre-period parallel trends explicitly. As a secondary check, use propensity score matching on user-level covariates as a sensitivity analysis, but flag its unconfoundedness assumption as the weakest link and don't treat it as the primary estimate.
**Follow-up trap:** *"What if even staggered geo rollout isn't possible because it's a global simultaneous launch?"* — then you're limited to purely observational methods (PSM, or an instrument if one exists) and should explicitly communicate the resulting estimate as lower-confidence, ideally paired with a request to build a proper holdout into the *next* version of the campaign rather than accepting permanently weak identification.

### Q12 — A colleague built a "propensity to churn" model and wants to use its output directly to prioritize retention-offer targeting. What's wrong with that plan?
**Answer:** Same core issue as Q1 in a different guise: a churn-propensity model predicts `P(churn|X)`, not the effect of the retention offer. Some high-churn-propensity users would stay regardless of the offer (wasted spend on sure-stays, i.e., not the same as sure-things but analogous — treating people already leaving no matter what), and some low-churn-propensity users might be exactly the ones a retention offer would save. The plan needs an uplift/CATE model estimating the *effect of the offer on retention*, ideally from a randomized offer-vs-no-offer experiment, not a churn-propensity ranking.
**Follow-up trap:** *"What about 'sleeping dogs' in this context?"* — a segment for whom the retention offer actually *increases* churn (e.g., an offer email that reminds an inattentive-but-otherwise-fine customer that they have a subscription they'd forgotten about, prompting them to reconsider and cancel) — only an uplift model, not a propensity model, can surface this group, and it's a genuinely reported failure mode in retention marketing.

---

## Red flags that fail you

- Calling a conversion/propensity model's output "incrementality" or "causal impact" without ever estimating a treatment effect.
- Not knowing that DiD's core assumption (parallel trends) is fundamentally untestable on post-treatment data.
- Presenting a PSM result without acknowledging unconfoundedness is unfalsifiable and depends on having measured every relevant confounder.
- Using an instrument without being able to defend the exclusion restriction in plain language.
- Evaluating an uplift model with classification AUC instead of an uplift-specific metric (Qini / uplift AUC).
- Not recognizing "sleeping dogs" (negative uplift) as a real, distinct segment from "lost causes."
- Treating class-transformation uplift estimates as valid without checking treatment-assignment balance.

---

## Cheat card

```
CATE          tau(x) = E[Y(1)-Y(0)|X=x]. Never observed per-unit (fundamental problem of
              causal inference) -- estimated by comparing treated vs control groups.
QUADRANTS     sure things (convert regardless, wasted spend) / persuadables (uplift target)
              lost causes (never convert) / sleeping dogs (treatment HURTS them, negative uplift)
TWO-MODEL     mu_1(x), mu_0(x) fit separately, tau_hat = mu_1-mu_0. Simple, noise-amplifying,
              no data sharing across arms.
CLASS TRANSF  Z = Y*W + (1-Y)*(1-W), one classifier, tau_hat = 2*P(Z=1|X)-1.
              Needs ~balanced treatment assignment (P(W=1)=0.5) or a correction.
CAUSAL FOREST splits maximize treatment-effect heterogeneity (not outcome variance);
              "honest" splitting gives asymptotically valid CIs on tau(x). More compute/complexity.
DID           (Y_t,post - Y_t,pre) - (Y_c,post - Y_c,pre). Assumption: PARALLEL TRENDS
              (untestable post-hoc, support via pre-period trend evidence + placebo tests)
PSM           match on propensity score e(x)=P(W=1|X). Assumption: UNCONFOUNDEDNESS
              (no unmeasured confounders -- unfalsifiable). King & Nielsen 2019: can increase
              imbalance vs. full/exact matching.
IV            instrument Z affects W but affects Y ONLY through W (exclusion restriction) +
              independent of confounders. 2SLS: regress W on Z, then Y on predicted W.
              Weak instrument -> unstable estimate even if exclusion restriction holds.
SYNTH CONTROL weighted blend of donor units matching pre-treatment trend of ONE treated unit;
              post-period gap = effect. Needs a donor pool that fits well pre-treatment.
EVAL          Qini curve / uplift AUC on a RANDOMIZED holdout -- classification AUC is wrong
              because there's no per-individual uplift ground truth to score against.
KEY POINT     correlation-trained conversion models optimize P(Y|X), not the treatment
              effect -- they systematically over-target sure things, miss persuadables and
              sleeping dogs.
```

## Sources

- [Uplift Modeling Overview — Emergent Mind](https://www.emergentmind.com/topics/uplift-modeling) — accessed 2026-08-02
- [causalml (Uber) — Methodology docs](https://causalml.readthedocs.io/en/latest/methodology.html) — accessed 2026-08-02
- [Causal Inference and Uplift Modeling: A review of the literature — Gutierrez & Gérardy, PMLR](https://proceedings.mlr.press/v67/gutierrez17a/gutierrez17a.pdf) — accessed 2026-08-02
- [Evaluating Uplift Modeling under Structural Biases: Insights into Metric Stability and Model Robustness](https://arxiv.org/html/2603.20775v2) — accessed 2026-08-02
- [Difference-in-Differences Meets Synthetic Control: Doubly Robust Identification and Estimation](https://arxiv.org/html/2503.11375v1) — accessed 2026-08-02
- [Balancing, Regression, Difference-In-Differences and Synthetic Control Methods: A Synthesis](https://arxiv.org/pdf/1610.07748) — accessed 2026-08-02
- [What is Incrementality in Marketing? — Incrmntal](https://www.incrmntal.com/resources/how-do-we-measure-incrementality) — accessed 2026-08-02
- [Measuring the Incrementality of Marketing with Causal Inference — Saxifrage](https://www.saxifrage.xyz/post/causal-inference) — accessed 2026-08-02

## Changelog
- 2026-08-02 — created
