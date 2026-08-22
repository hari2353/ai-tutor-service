# Experiment Design: Factorial & Fractional-Factorial, Multivariate Testing, Stratified Sampling, Power Analysis, SRM, CUPED

> **Track:** T32 Applied NLP & Marketing ML · **Time:** 3h · **Prereqs:** T32-bayesian-methods (frequentist/Bayesian contrast helps), basic hypothesis testing · **Updated:** 2026-08-02
> **Module id:** `T32-experiment-design` · **Tags:** stats, critical

## The 30-second version

Good experiment design is decided before a single user is bucketed: what factors to test and in what combination (full factorial vs. fractional factorial vs. one-factor-at-a-time), what unit to randomize on (user, session, device — mismatched units are a top source of invalid variance estimates), how much traffic you need (power analysis, deriving MDE from baseline rate, variance, and desired power), and how to keep unlucky randomization from adding noise (stratification and blocking on known covariates). Multivariate testing (MVT) — testing multiple factors' full combinatorial space at once — buys you interaction detection that sequential single-factor tests structurally cannot see, but the cost is combinatorial: a 4-factor, 3-level MVT needs 81 cells, and each cell needs the same per-cell sample size a simple two-arm test would need, so total traffic requirement multiplies by cell count. Sample ratio mismatch (SRM) — where the observed traffic split deviates from the intended one by more than chance — is the single most common real-world bug that invalidates an experiment's result, and it is caught with one chi-squared test that should run automatically before anyone reads a single metric. CUPED (Controlled-experiment Using Pre-Experiment Data) cuts required sample size by regressing out pre-experiment covariate variance, commonly delivering 30-50% variance reduction on metrics with a strong historical predictor, without touching the randomization at all.

## Why this gets asked

Expedia Marketing Content ML Science ships and evaluates a constant stream of content variants — descriptions, imagery, layout — across dozens of markets and device types simultaneously. The interviewer has been the one paged when a "winning" variant's lift evaporated post-launch, and traced it back to a randomization unit mismatch, an SRM nobody checked, or an underpowered test that got read as a null result instead of "we didn't collect enough data to know." They want evidence you design the experiment to survive contact with real traffic, not just that you can run a t-test after the fact.

---

## Lineage: past → present → future

**What came before.** Formal experimental design predates the internet by decades: Ronald Fisher's work at Rothamsted Experimental Station in the 1920s-30s (*The Design of Experiments*, 1935) established randomization, blocking, and factorial design for agricultural field trials — the same logic that governs a modern web experiment, just with crop yield instead of conversion rate. Full factorial designs were the default whenever you had the plots (or, later, traffic) to run every combination; Genichi Taguchi's work in the 1950s-80s on fractional factorial designs and orthogonal arrays, developed for Japanese manufacturing quality control, made it practical to estimate main effects and key interactions from a carefully chosen subset of combinations instead of the full combinatorial grid. Online, the earliest large-scale controlled experiments (Google, Amazon, Microsoft, roughly 2000-2010) mostly ran simple two-arm A/B tests, because the tooling and cultural muscle for anything more complex didn't exist yet, and traffic was the binding constraint that discouraged multivariate designs.

**Where it stands now.** Ron Kohavi's synthesis at Microsoft's Experimentation Platform (the "trustworthy online controlled experiments" body of work, culminating in the 2020 book with Tang and Xu) is the closest thing the industry has to a canonical reference: it formalized SRM as *the* first integrity check, CUPED as the default variance-reduction technique, and the operational discipline (guardrail metrics, pre-registration, automated health checks) that separates a mature experimentation platform from a hobbyist one. MVT is used but selectively — most production platforms default to sequential or Bayesian-monitored two-arm tests for velocity, and reserve full or fractional factorial designs for cases where interaction effects are specifically suspected (e.g., "does the headline change interact with the image change") because the traffic cost is real and most teams don't have Google or Amazon-scale volume to spend on it. The live disagreement is less about the math (power analysis, CUPED, and factorial design are settled statistics) and more about **process**: how much of this rigor should be automated into a self-serve platform versus left to a data scientist's judgment, and how aggressively to push CUPED-adjusted metrics into dashboards non-statisticians read directly.

**Where it's heading.** Automated, always-on health checks (SRM, guardrail metric monitoring, novelty-effect detection) built directly into experimentation platforms rather than run manually by an analyst — high confidence, this is already standard at large tech companies and increasingly at mid-size ones. Sequential/anytime-valid testing combined with CUPED-style variance reduction, letting teams both peek continuously and get the variance benefit, is an active area of published research (Netflix, Microsoft, and academic groups have all published in this space through 2025) and is moving from research paper to production feature — moderate confidence on timeline, high confidence on direction. More speculative: automated factor-selection for MVT designs using historical experiment databases to predict which interactions are worth the traffic cost before running them, rather than a human guessing — exists in research prototypes, not yet a settled production pattern.

---

## Mental model

Full factorial vs. fractional factorial vs. one-factor-at-a-time, for two factors (headline: A/B, image: A/B):

```
ONE-FACTOR-AT-A-TIME          FULL FACTORIAL (2x2)         FRACTIONAL FACTORIAL
sequential, 2 tests:          one test, 4 cells:            (example: half fraction,
  test 1: headline A vs B      H-A/I-A   H-A/I-B             confounds a chosen
          (image fixed)        H-B/I-A   H-B/I-B             interaction with a factor)
  test 2: image A vs B         all combinations run          fewer cells than full,
          (headline fixed)     simultaneously --             assumes some higher-order
CANNOT see headline x image   CAN estimate the               interactions are
interaction. Cheaper.         headline x image               negligible to save traffic
                               interaction directly.
```

Randomization unit as "the thing that must not leak across arms": if you randomize by session but a user has five sessions, the same user can land in both arms across sessions, contaminating the comparison — the unit of randomization must match the unit at which the treatment plausibly has a stable, non-leaking effect.

---

## How it actually works

### Factorial and fractional-factorial design

A **full factorial** design with `k` factors, each at `L` levels, requires `L^k` cells. Two factors at two levels each (2x2) is 4 cells; three factors at two levels (2^3) is 8 cells; four factors at three levels (3^4) is 81 cells. Every cell needs approximately the same per-arm sample size a simple two-arm test would need to hit the same power, so **total required traffic scales with cell count**, not with the number of factors linearly — this is the mechanical reason MVT is expensive.

The payoff is that a full factorial design estimates **interaction effects** directly: the effect of factor A can depend on the level of factor B (e.g., a bold CTA button might lift conversion on a minimalist page layout but hurt it on a busy one). A sequence of independent A/B tests, run one factor at a time, cannot detect this — each test holds the other factor fixed at whatever value happened to be "control" during that test, and never observes the crossed condition.

**Fractional factorial** designs run a carefully chosen subset of the full combinatorial grid — a "half fraction" of a 2^4 design runs 8 of the 16 cells instead of all 16 — chosen so that main effects remain estimable and only specific, deliberately chosen higher-order interactions are confounded (aliased) with each other. The design assumes those confounded interactions are negligible; if that assumption is wrong, the design silently attributes one effect's variance to another. This is a real bet, not a free lunch: fractional designs buy traffic efficiency by explicitly sacrificing the ability to distinguish certain interactions, and picking which interactions to sacrifice (via the design's "generator") requires domain judgment about what's actually likely to interact.

### Multivariate testing and its interaction-detection cost

MVT is the marketing-industry name for a full (or fractional) factorial design applied to creative/content elements — headline, hero image, CTA copy, layout — tested in combination rather than sequentially. The interaction-detection benefit is real: you learn not just "does headline B outperform A" but "does headline B's advantage depend on which image it's paired with," which single-factor sequential testing structurally cannot answer. The cost is combinatorial and often underestimated by marketing stakeholders who think of MVT as "just testing more things at once": a 4-factor, 3-level-each MVT is 81 cells; at even a modest 10,000 visitors/cell requirement for a detectable effect, that's 810,000 visitors before the test can conclude — traffic most campaigns simply don't have. The practical resolution is almost always fractional factorial (accept some confounded higher-order interactions you judge unlikely) or restricting MVT to the 2-3 factors most plausibly interacting, testing the rest sequentially.

### Stratified sampling and blocking

**Blocking** groups experimental units into strata sharing a known source of variance (device type, geography, new vs. returning user, day-of-week traffic pattern) *before* randomization, then randomizes treatment assignment independently within each block. This removes the blocked variable's variance from the treatment-effect estimate entirely, rather than hoping randomization balances it by chance — with small-to-moderate sample sizes, chance imbalance in a high-variance covariate (e.g., a handful of very high-spend users landing disproportionately in one arm) can materially bias or add noise to a naive comparison. **Stratified sampling** is the same idea applied to how you draw or weight your sample for analysis: post-stratification re-weights observed strata to match known population proportions after the fact, useful when blocking wasn't (or couldn't be) done at assignment time. Netflix's own published guidance is notable here: they favor **post-assignment** variance reduction (post-stratification, CUPED) over **at-assignment** stratified sampling for large-scale experiments, because at-assignment stratification adds real operational complexity (the randomization service must know every stratifying variable in advance and enforce balanced allocation live) for a variance-reduction benefit that CUPED, applied after the fact using pre-experiment data, often matches or exceeds with far less engineering cost.

### Randomization units

The randomization unit is the entity you flip a coin for — user, session, device, cookie, geographic cluster (geo experiments) — and it must be chosen so the unit doesn't leak across treatment arms in a way that contaminates the comparison. Randomizing by session when a single user has multiple sessions per day means the same user can experience both variants, diluting the observed effect toward zero (if the treatment has a genuine effect but the user experiences a blend of both). Randomizing by user (typically via a hashed user or device ID, stable across sessions) is the standard default for anything with a plausible per-user, not per-visit, effect. For network-effect-sensitive changes (anything involving sharing, referrals, or content that spreads between users), even user-level randomization leaks — this is when you need **cluster randomization** (randomize by friend-group, geographic market, or store) to keep the treatment's spillover contained within one arm.

### Power analysis and MDE, derived

Statistical power is `P(reject H0 | H0 is false)` — the probability your test actually detects a real effect of a given size, given your sample size, baseline variance, and significance threshold. The standard two-proportion sample size formula, derived from the normal approximation to the difference of two proportions:

```
n per arm = (z_alpha/2 + z_beta)^2 * (p1(1-p1) + p2(1-p2)) / (p2 - p1)^2
```

where `z_alpha/2` is the critical value for your significance level (1.96 for two-sided alpha=0.05), `z_beta` is the critical value for your desired power (0.84 for 80% power, 1.28 for 90% power), `p1` is the baseline conversion rate, and `p2` is the rate under the minimum effect you want to detect. **Minimum detectable effect (MDE)** is the same formula solved for `(p2-p1)` given a fixed `n` — the smallest true effect your test is powered to reliably catch at that sample size.

Worked example: baseline conversion `p1 = 0.05` (5%), you want to detect a relative lift of 10% (`p2 = 0.055`), at `alpha=0.05` two-sided and 80% power (`z_alpha/2=1.96, z_beta=0.84`):

```
n = (1.96+0.84)^2 * (0.05*0.95 + 0.055*0.945) / (0.005)^2
  = 7.84 * (0.0475 + 0.051975) / 0.000025
  = 7.84 * 0.099475 / 0.000025
  ≈ 31,205 per arm
```

So detecting a 10% relative lift on a 5% baseline needs roughly **31,000 visitors per arm** (~62,000 total). Halving the effect you want to detect (a 5% relative lift instead of 10%) roughly **quadruples** the required sample size, because the effect size term is squared in the denominator — this is the single most important intuition to carry into a stakeholder conversation about "can we just detect a smaller lift": no, not without a proportionally much larger sample or more traffic-efficient methodology (CUPED, sequential testing, a bigger MDE they're willing to accept).

### Sample ratio mismatch: the #1 real-world bug

SRM is when the observed split between arms deviates from the intended split (say, observed 48.2%/51.8% against an intended 50/50) by more than chance would produce. It is detected with a simple chi-squared goodness-of-fit test against the expected ratio; a conventional trigger threshold is `p < 0.001` (deliberately much stricter than the usual 0.05, because SRM checks run on every single experiment and a looser threshold would flag healthy experiments constantly by chance). **SRM invalidates the experiment's causal comparison, full stop, until root-caused** — the missing or excess users are essentially never a random subset; they're disproportionately whichever type of user was most affected by a bug in redirect logic, bot-filtering, page load failure, or a tracking pixel that got broken specifically by one variant's code (a JavaScript error in the treatment variant is a commonly reported real-world cause in e-commerce testing — the treatment code breaks a tracking event, so treatment-arm users with that condition silently vanish from the logged sample, biasing every downstream metric even though the raw numbers "look" close to significant). Root causes span the whole pipeline: assignment-stage bugs (broken bucketing, ID collisions), execution-stage bugs (redirect failures, a variant's own bug preventing users from completing the funnel and being logged), logging-stage bugs (a broken join dropping rows differentially by arm), and analysis-stage bugs (a post-hoc filter applied asymmetrically). An SRM check should run automatically before any metric is even displayed, and a triggered SRM should hard-block the experiment's dashboard rather than let a stakeholder scroll past it to the headline number.

### CUPED for variance reduction

CUPED (Deng, Xu, Kohavi, Walker — Microsoft, 2013) reduces the variance of the treatment effect estimator by using a pre-experiment covariate `X` (typically the same metric measured *before* the experiment started, for the same users) that's correlated with the outcome metric `Y` but, critically, was measured before treatment assignment and therefore cannot itself be affected by treatment. The adjusted metric is:

```
Y_cuped = Y - theta * (X - E[X])
theta = Cov(X, Y) / Var(X)     (the OLS regression coefficient of Y on X)
```

`theta` is estimated once (often pooled across both arms, since it's estimated from the covariate-outcome relationship, not the treatment effect itself) and applied uniformly; the treatment effect is then estimated on `Y_cuped` instead of raw `Y`, with the same expectation but strictly lower variance whenever `X` and `Y` are correlated. The variance reduction is `Var(Y_cuped) = Var(Y) * (1 - rho^2)` where `rho` is the correlation between `X` and `Y` — a pre-experiment metric correlated at `rho=0.7` with the outcome metric cuts variance by `1 - 0.49 = 51%`, which translates directly into either running the same test with roughly half the required sample size, or detecting roughly `sqrt(0.51) ≈ 71%` of the original MDE at the same sample size. Microsoft and Netflix both report this magnitude of variance reduction (commonly cited range 30-50%, sometimes higher on metrics with strong historical predictors like prior-period revenue) as typical in production, with the exact number depending entirely on how predictive the chosen covariate actually is — a poorly chosen covariate (weak correlation with the outcome) buys almost nothing.

---

## Build it from scratch

```python
# untested sketch — power analysis, SRM check, and CUPED adjustment from first principles
import numpy as np
from scipy import stats

def sample_size_two_proportion(p1: float, mde_relative: float, alpha: float = 0.05, power: float = 0.8) -> int:
    p2 = p1 * (1 + mde_relative)
    z_alpha = stats.norm.ppf(1 - alpha / 2)
    z_beta = stats.norm.ppf(power)
    pooled_var = p1 * (1 - p1) + p2 * (1 - p2)
    n = ((z_alpha + z_beta) ** 2) * pooled_var / ((p2 - p1) ** 2)
    return int(np.ceil(n))

# sample_size_two_proportion(0.05, 0.10) -> ~31,205 per arm

def srm_check(n_control: int, n_treatment: int, expected_ratio: float = 0.5, threshold: float = 0.001) -> dict:
    total = n_control + n_treatment
    expected_control = total * expected_ratio
    expected_treatment = total * (1 - expected_ratio)
    chi2, p_value = stats.chisquare(
        f_obs=[n_control, n_treatment],
        f_exp=[expected_control, expected_treatment],
    )
    return {"chi2": chi2, "p_value": p_value, "srm_detected": p_value < threshold}

def cuped_adjust(y: np.ndarray, x: np.ndarray) -> np.ndarray:
    theta = np.cov(x, y, ddof=1)[0, 1] / np.var(x, ddof=1)
    return y - theta * (x - np.mean(x))

# usage: adjust outcome metric using each user's pre-experiment value of the same metric,
# then run the normal two-sample test on y_cuped_control vs y_cuped_treatment --
# same expected treatment effect, lower variance, smaller required sample or tighter CI.
```

---

## How it's done in production

Experimentation platforms — Microsoft's ExP, Netflix's XP, Statsig, Optimizely, Eppo, internal platforms at most large travel/e-commerce companies — implement SRM checks, CUPED (or an equivalent regression-adjustment technique), and guardrail metric monitoring as automated, always-on pipeline stages, not manual analyst steps. Randomization services hash a stable unit ID (user ID, device ID) into a bucket, and most mature platforms support layered/orthogonal experimentation (multiple concurrent experiments on independent layers, so unrelated tests don't collide) precisely because a naive shared-traffic model would force a choice between running many small tests or few large ones.

| Symptom | Cause | Fix |
|---|---|---|
| Chi-squared SRM check fires (p < 0.001) on a "simple" 50/50 test | Assignment, execution, logging, or analysis-stage bug — commonly a JS error in one variant breaking the tracking pixel | Root-cause across the pipeline stage by stage; do not read any metric from the experiment until resolved |
| Test declared "no significant difference" but was underpowered | MDE was never computed, or was computed at an optimistic baseline/effect size that didn't hold | Always report the MDE the test was actually powered to detect alongside a null result — "no effect" and "not powered to see this effect" are different claims |
| Required sample size balloons when stakeholders ask to detect a smaller lift | MDE appears squared in the denominator of the sample-size formula — halving MDE roughly quadruples required n | Show the tradeoff curve (n vs. MDE) explicitly rather than absorbing an arbitrary smaller-MDE request silently |
| MVT test takes months to reach significance | Cell count from a full factorial design multiplying required traffic (L^k cells, each needing near-full per-arm sample size) | Move to fractional factorial, or restrict full-factorial treatment to only the 2-3 factors most plausibly interacting |
| Treatment effect estimate noisier than expected despite adequate total sample | Randomization unit leaking across arms (e.g., session-level randomization for a user-level effect), diluting the observed effect toward zero | Re-randomize at the correct unit (user/device), and audit for any surface that lets a user experience both arms |
| CUPED adjustment barely reduces variance | Chosen covariate weakly correlated with the outcome metric (`rho` low) | Pick a covariate with a demonstrated strong historical correlation to this specific metric — often the same metric measured pre-experiment, not a generic proxy |

---

## Tradeoffs & when NOT to use it

- **Don't run a full factorial MVT when traffic can't support the cell count.** An underpowered MVT cell produces a wide, useless interval per cell and burns weeks of traffic to answer a question a sequential pair of A/B tests could answer faster, even without interaction detection — know the traffic math before proposing MVT to stakeholders.
- **Don't use fractional factorial designs without naming which interactions you're assuming away.** The confounding structure is a real bet on domain knowledge; if you can't say which interaction is aliased with which, you don't understand the design well enough to defend it under questioning.
- **Don't stratify/block on a variable with weak correlation to the outcome.** Blocking has real operational cost (the randomization service must track and balance the stratifying variable at assignment time); blocking on something with little relationship to the metric buys negligible variance reduction for real engineering cost — CUPED, applied after the fact, is usually the better lever unless the imbalance risk on a specific known confounder is severe.
- **Don't use session-level or cookie-level randomization for a change with a plausible per-user, cross-session effect** (anything affecting habit formation, retention, or trust) — you'll dilute a real effect toward an unreliable null.
- **CUPED is close to a free lunch when a strong pre-experiment covariate exists, but it isn't when no such covariate exists** (a brand-new user cohort, a genuinely novel metric with no historical analog) — don't force it in cases where the covariate correlation is weak; it adds analysis complexity for near-zero benefit there.

---

## Interview questions

### Q1 — Derive the sample size formula for a two-proportion test and compute it for a 5% baseline and a 10% relative MDE.
**Testing:** can you derive, not just recall, the formula.
**Answer:** From the normal approximation to the sampling distribution of `p2-hat - p1-hat`, solving for `n` such that the test has power `1-beta` at significance `alpha`: `n = (z_alpha/2 + z_beta)^2 * (p1(1-p1)+p2(1-p2)) / (p2-p1)^2`. At `p1=0.05, p2=0.055, alpha=0.05, power=0.8`: `n ≈ 31,205` per arm.
**Follow-up trap:** *"What happens to n if you ask for a 5% relative MDE instead of 10%?"* — it roughly quadruples, because `(p2-p1)` is halved and it's squared in the denominator; know this scaling cold, it's the number stakeholders actually need to hear.

### Q2 — What is sample ratio mismatch, and why is it "the number one real-world bug" rather than a rare edge case?
**Answer:** SRM is when the observed split between arms deviates from the intended allocation by more than chance, detected via a chi-squared test against expected proportions (commonly triggered at p<0.001). It's the top real-world bug because it can arise anywhere in the pipeline — assignment, execution (a variant's own bug breaking the tracking pixel), logging, analysis — and because the missing/excess users are systematically, not randomly, different, which biases every downstream metric even when the raw split "looks" close.
**Follow-up trap:** *"If SRM triggers but the treatment still looks significantly better, do you trust it?"* — no; SRM invalidates the causal comparison until root-caused, regardless of how convincing the headline metric looks — the missing users are exactly the ones most likely to differ systematically.

### Q3 — Explain CUPED and derive why it reduces variance.
**Answer:** `Y_cuped = Y - theta*(X - E[X])`, `theta = Cov(X,Y)/Var(X)`, using a pre-experiment covariate X correlated with outcome Y but unaffected by treatment. `Var(Y_cuped) = Var(Y)*(1-rho^2)` where rho is the X-Y correlation — this drops directly out of OLS variance algebra. At rho=0.7, variance drops ~51%, translating to roughly half the sample size needed for the same power, or detecting a smaller MDE at the same sample.
**Follow-up trap:** *"Does CUPED bias the treatment effect estimate?"* — no, in expectation it's unbiased as long as X is measured strictly before treatment assignment (so it can't be affected by treatment); using a post-treatment covariate would introduce real bias.

### Q4 — What's the difference between full factorial and fractional factorial design, and what do you give up with the fractional version?
**Answer:** Full factorial runs every combination of every factor level (`L^k` cells), estimating all main effects and all interactions. Fractional factorial runs a deliberately chosen subset, saving traffic at the cost of confounding (aliasing) certain higher-order interactions with each other or with main effects — you're betting those confounded interactions are negligible.
**Follow-up trap:** *"How do you decide which interactions to sacrifice?"* — via the design's generator/defining relation, informed by domain judgment about which interactions are actually plausible; a candidate who can't name what's confounded in their own proposed design hasn't actually designed it.

### Q5 — Why does multivariate testing (MVT) need so much more traffic than a sequence of A/B tests, and what does it buy you that sequential testing can't?
**Answer:** Cell count scales as `L^k` — a 4-factor, 3-level design is 81 cells, each needing roughly the same per-arm sample as a standalone A/B test, so total traffic multiplies by cell count. What it buys: direct estimation of interaction effects (does factor A's effect depend on factor B's level), which sequential single-factor tests structurally cannot see because each test holds the other factor fixed.
**Follow-up trap:** *"When would you refuse to run a full MVT even if stakeholders want it?"* — when the traffic math doesn't support adequately powering every cell; better to name the required traffic explicitly and offer fractional factorial or a reduced factor set than run an underpowered MVT that produces uninterpretable noise.

### Q6 — What's the difference between blocking and stratified sampling, and when would you pick one over the other?
**Answer:** Blocking randomizes treatment independently within known strata *at assignment time*, removing that variable's variance from the comparison by design. Stratified/post-stratified sampling re-weights or adjusts *after the fact* using known strata proportions, without requiring the randomization service to enforce balance live. Netflix's own guidance favors post-assignment techniques (post-stratification, CUPED) over at-assignment stratification for large-scale experiments because the operational cost of live-balanced blocking often isn't repaid by the variance reduction versus a simpler post-hoc adjustment.
**Follow-up trap:** *"Is there a case where at-assignment blocking is still worth it?"* — yes, when a specific known confounder is both highly variable and could plausibly imbalance badly by chance in a smaller sample (e.g., a handful of whale accounts) — blocking guarantees balance where CUPED only corrects for it statistically after the fact.

### Q7 — Explain randomization units and how a mismatch biases results.
**Answer:** The randomization unit (user, session, device, cluster) must match the level at which the treatment's effect is plausible and non-leaking. Randomizing by session for a per-user effect means the same user can land in both arms across sessions, diluting the true effect toward zero as they experience a blend of both conditions rather than a clean single treatment.
**Follow-up trap:** *"What about a change with network effects, like a referral feature?"* — even user-level randomization leaks there, because a treated user's action (e.g., sharing) affects a control user; you need cluster randomization (by friend-group or geo-market) to contain spillover within an arm.

### Q8 — A stakeholder asks "can we just detect a 1% lift instead of the 10% lift you powered for, using the same sample size?" How do you respond?
**Answer:** No — MDE and required sample size have a squared inverse relationship, so detecting a 10x smaller effect needs roughly 100x the sample at fixed power and alpha. Show the actual sample-size-vs-MDE curve rather than a vague "no"; if the traffic genuinely can't support it, the honest options are accepting a larger MDE, running longer, or applying variance reduction (CUPED) to buy back some sensitivity without more traffic.
**Follow-up trap:** *"How much does CUPED actually help here?"* — it scales required sample by `(1-rho^2)`, a real but bounded gain (e.g., 50% at rho=0.7) — it narrows the gap, it doesn't erase a 100x traffic deficit.

### Q9 — Walk through the pipeline stages where SRM can originate and how you'd root-cause a triggered SRM check.
**Answer:** Assignment stage (bucketing bugs, ID collisions, inconsistent hashing across services), execution stage (a variant's own bug — often a JS error — breaking event firing or causing redirect failures), logging stage (a join that drops rows differentially by arm), analysis stage (an asymmetric post-hoc filter). Root-cause by checking each stage in order, starting with assignment-service logs for raw bucket counts before any filtering, then checking whether the treatment arm specifically has elevated error rates or missing event fires in observability data.
**Follow-up trap:** *"What if the SRM is small, like 49.7/50.3?"* — statistical significance at p<0.001 with large n can flag even small deviations; still investigate, because a systematic (non-random) small skew is exactly the kind of subtle logging bug that also quietly biases the metric you actually care about, not just the ratio.

### Q10 — Your team wants to run a 3-factor MVT (headline x image x CTA color) but only has 15,000 visitors/week. Design the study.
**Testing:** synthesis — traffic-constrained real-world design.
**Answer:** Compute the cell count for the desired design (e.g., 2 levels each = 8 cells) and the per-cell sample size needed for the smallest MDE stakeholders will accept; compare against available traffic over an acceptable test duration. If a full factorial doesn't fit, propose a half-fraction fractional factorial (4 cells instead of 8, aliasing the 3-way interaction with a chosen main effect if that interaction is judged implausible), or drop to testing the two factors most likely to interact (headline x image) as a full 2x2 and testing CTA color sequentially afterward. State the traffic math explicitly rather than silently running an underpowered design.
**Follow-up trap:** *"What if stakeholders insist on all 3 factors simultaneously regardless of traffic?"* — surface the actual MDE the constrained sample size buys per cell, and let them decide with the number in front of them rather than absorbing the request and shipping an uninterpretable result.

### Q11 — Why is "we ran the test and saw no significant difference" not the same claim as "the treatment has no effect"?
**Answer:** A null result only means the observed effect (if any) fell within the noise band implied by the test's power at the sample size actually collected. If the test wasn't powered to detect the effect size that would actually matter (i.e., a true effect smaller than the MDE), a null result is uninformative about whether that smaller — but still meaningful — effect exists.
**Follow-up trap:** *"How do you prevent stakeholders from misreading a null result as 'proven no effect'?"* — always report the achieved MDE alongside a null result, and phrase the conclusion as "we can rule out an effect larger than X%" rather than "no effect."

### Q12 — What's the practical difference between CUPED and simply controlling for the same covariate via regression (ANCOVA) on the raw outcome?
**Answer:** They're closely related — CUPED is essentially a specific, computationally light implementation of regression adjustment using a single strongly predictive pre-period covariate, designed for the speed and simplicity needed at experimentation-platform scale (compute `theta` once, apply as a simple linear adjustment, no need to refit a full regression per analysis). Full ANCOVA/regression adjustment can include multiple covariates and interaction terms for potentially more variance reduction, at the cost of more modeling complexity and assumptions.
**Follow-up trap:** *"When would you reach for full regression adjustment instead of plain CUPED?"* — when you have several strong, largely independent pre-experiment covariates and the platform can support the added modeling complexity — CUPED is the 80/20 answer for a single strong covariate, not a hard ceiling on variance reduction technique.

---

## Red flags that fail you

- Reading a null result as "the treatment has no effect" without checking whether the test was even powered to detect a meaningful effect size.
- Not knowing SRM is checked with a chi-squared test and treating a skewed split as a curiosity rather than a hard blocker on trusting the result.
- Proposing a full-factorial MVT without doing the cell-count-times-per-cell-sample-size math first.
- Applying CUPED (or any covariate) using a post-treatment value, which biases the estimate rather than just reducing its variance.
- Randomizing by session or cookie for a change with an obvious per-user or cross-session effect.
- Not being able to say which interactions a proposed fractional-factorial design confounds away.

---

## Cheat card

```
FACTORIAL     full: L^k cells, all interactions estimable, traffic scales with cell count
              fractional: subset of cells, confounds chosen higher-order interactions,
                real bet on domain knowledge about what's negligible
MVT           = factorial design on creative elements; interaction detection sequential
                tests can't see, but cost is combinatorial (4 factors x 3 levels = 81 cells)
BLOCKING      randomize within known strata AT assignment -- guarantees balance, real ops cost
STRAT SAMPLE  post-hoc reweight/adjust by strata -- Netflix prefers this + CUPED over
                at-assignment stratification at scale
RAND UNIT     must match level of a non-leaking effect: user/device default; cluster
                (geo/friend-group) for network-effect-sensitive changes
POWER/MDE     n = (z_a/2 + z_b)^2 * (p1(1-p1)+p2(1-p2)) / (p2-p1)^2
              z_a/2=1.96 (alpha .05 2-sided), z_b=0.84 (80% power), 1.28 (90% power)
              p1=.05, 10% relative MDE -> n ~31,205/arm. Halve MDE -> ~4x n (squared denom)
SRM           chi-squared test on observed vs expected split, trigger threshold p<0.001
              #1 real-world bug: assignment/execution/logging/analysis-stage causes
              INVALIDATES the test until root-caused -- missing users are never random
CUPED         Y_cuped = Y - theta*(X - E[X]), theta = Cov(X,Y)/Var(X), X pre-experiment only
              Var reduction = 1 - rho^2 (rho=0.7 -> ~51% variance cut -> ~2x smaller n needed)
```

## Sources

- [Diagnosing Sample Ratio Mismatch in A/B Testing — Microsoft Research](https://www.microsoft.com/en-us/research/articles/diagnosing-sample-ratio-mismatch-in-a-b-testing/) — accessed 2026-08-02
- [What is Sample Ratio Mismatch (SRM)? — Analytics Toolkit Glossary](https://www.analytics-toolkit.com/glossary/sample-ratio-mismatch/) — accessed 2026-08-02
- [Addressing the Challenges of Sample Ratio Mismatch in A/B Testing — DoorDash Engineering](https://careersatdoordash.com/blog/addressing-the-challenges-of-sample-ratio-mismatch-in-a-b-testing/) — accessed 2026-08-02
- [Improving the Sensitivity of Online Controlled Experiments: Case Studies at Netflix (Deng, Xu, et al.)](https://www.researchgate.net/publication/305997925_Improving_the_Sensitivity_of_Online_Controlled_Experiments_Case_Studies_at_Netflix) — accessed 2026-08-02
- [Deep Dive Into Variance Reduction — Microsoft Research ExP](https://www.microsoft.com/en-us/research/group/experimentation-platform-exp/articles/deep-dive-into-variance-reduction/) — accessed 2026-08-02
- [Subset Selection for Stratified Sampling in Online Controlled Experiments](https://arxiv.org/pdf/2509.15576) — accessed 2026-08-02
- [Improving the sensitivity of online controlled experiments by utilizing pre-experiment data (CUPED, Deng, Xu, Kohavi, Walker)](https://www.academia.edu/18476564/Improving_the_sensitivity_of_online_controlled_experiments_by_utilizing_pre_experiment_data) — accessed 2026-08-02

## Changelog
- 2026-08-02 — created
