# Bayesian Inference for Experimentation: Priors, Conjugates, Hierarchical Models, MCMC, and Bayesian A/B Testing

> **Track:** T32 Applied NLP & Marketing ML · **Time:** 3h · **Prereqs:** probability fundamentals (conditional probability, distributions), frequentist hypothesis testing helps but is not required · **Updated:** 2026-08-02
> **Module id:** `T32-bayesian-methods` · **Tags:** stats, critical

## The 30-second version

Bayesian inference treats a parameter as a random variable with a distribution, not a fixed unknown: you start with a prior belief, observe data, and combine them through Bayes' rule into a posterior that is exactly proportional to `likelihood × prior`. Conjugate priors (Beta-Binomial for conversion rates, Normal-Normal for continuous metrics) make this a closed-form update — no numerical integration needed — which is why they're the default for online A/B testing dashboards. Hierarchical models extend this by letting each group (each campaign, each locale, each store) have its own parameter while those parameters are pulled toward a shared population distribution — partial pooling — which is the correct way to handle low-traffic segments instead of either ignoring them (no pooling, noisy) or lumping them together (complete pooling, biased). MCMC, specifically Hamiltonian Monte Carlo with the No-U-Turn Sampler (NUTS), is how you get posteriors for models with no closed form: it's not integrating the posterior, it's drawing correlated samples from it and treating sample statistics as the answer, and you know it worked when R-hat is under 1.01 and effective sample size is in the thousands. Bayesian A/B testing's real selling point over frequentist testing is that you can monitor a metric continuously without inflating error rates the way naive peeking does under a fixed-horizon t-test — but that immunity is conditional on a proper stopping rule and an honest prior, not automatic, and the prior itself is a real modeling choice an interviewer will push on.

## Why this gets asked

Expedia's Marketing Content ML Science team runs experiments on content variants (descriptions, images, ranking of amenities) across a catalog with wildly uneven traffic — a flagship property in Manhattan gets thousands of views a day, a boutique inn in a secondary market gets a handful a week. The interviewer has watched a naive per-property A/B test declare a "winner" off eleven bookings and watched that decision get reversed the next quarter. They want to know whether you reach for hierarchical pooling and honest uncertainty quantification by default, or whether you fit and ship a point estimate and call it done. They're also testing whether you can explain a posterior probability to a VP without them walking away thinking it means something it doesn't — Bayesian numbers get misread as "95% chance we're right" far more than confidence intervals do, and the person who can't stop that misreading in the room becomes a liability.

---

## Lineage: past → present → future

**What came before.** Classical (frequentist) statistics, formalized by Fisher, Neyman, and Pearson through the 1920s-1930s, treats the parameter as fixed and unknown and quantifies uncertainty through the sampling distribution of an estimator over hypothetical repeated experiments — a p-value is the probability of data this extreme *given the null*, not the probability the null is true, a distinction that trips up even experienced practitioners. This machinery is what powers the standard two-sample t-test and chi-squared test still run in every A/B testing platform today. Bayesian inference is actually older (Bayes' essay was published posthumously in 1763, Laplace independently developed and popularized it), but it was computationally impractical for anything beyond simple conjugate models until the 1990s: computing a posterior for a realistic model meant solving an intractable high-dimensional integral by hand. The frequentist school won the 20th century largely because its math was tractable with pencil, paper, and lookup tables, not because it was philosophically preferred by most statisticians who used it.

**Where it stands now.** MCMC methods — the Metropolis-Hastings algorithm (1953/1970) and Gibbs sampling — made Bayesian inference computationally feasible for arbitrary models starting in the late 1980s, and modern gradient-based samplers (Hamiltonian Monte Carlo, and specifically NUTS, Hoffman & Gelman 2011/2014) made it fast enough for routine industrial use. Probabilistic programming languages — Stan (2012), PyMC (current major line PyMC 5.x), NumPyro — turned "write the model, get the posterior" into a few dozen lines of code. In A/B testing specifically, Bayesian methods are now mainstream at consumer-scale companies: Google's early public write-ups on Bayesian testing, VWO and Optimizely both ship Bayesian statistical engines alongside or instead of frequentist ones, and internal experimentation platforms at large e-commerce and travel companies default to Bayesian dashboards for exactly the "peek whenever you want" property. The live disagreement is not "Bayesian vs frequentist" as ideology — most practicing statisticians now treat them as tools for different jobs — it is about **default priors and stopping rules in automated dashboards**: a platform that lets a PM stare at a live-updating posterior and stop "whenever it looks good" is not actually immune to inflated false-positive rates unless the stopping rule was fixed in advance or a proper loss-function-based decision rule is enforced, and a lot of shipped tooling glosses over this.

**Where it's heading.** Hierarchical and multilevel models as the default for any metric segmented by geography, device, or campaign are close to settled best practice at companies with the data science maturity to run them — moderate-to-high confidence, this is where Expedia-scale travel and marketplace companies with wildly uneven segment sizes are already operating. "Always-valid inference" — confidence sequences and mixture sequential probability ratio tests that give frequentist-valid continuous monitoring without going Bayesian — is a genuinely competitive alternative gaining traction inside large experimentation platforms (Optimizely's Stats Engine, Netflix and Spotify's internal platforms have published on this), and the honest answer to "Bayesian or frequentist for continuous monitoring" in 2026 is that anytime-valid frequentist methods solve the same problem without requiring a prior — a real, not speculative, competing approach worth naming in an interview. More speculative: automated prior elicitation from historical experiment databases (using the outcomes of thousands of past tests to set an empirical Bayes prior for a new one) is an active area at large experimentation-heavy companies but is not a settled, widely-published production pattern yet.

---

## Mental model

Bayes' rule as an update, not a formula to memorize blind:

```
                    likelihood: how well does this hypothesis
                    explain the data we saw?
                          │
   prior belief           ▼
   about θ    ──────▶  P(D|θ) P(θ)
   before data          ──────────  =  P(θ|D)   posterior belief
                         P(D)                    about θ after data

   P(D) = ∫ P(D|θ) P(θ) dθ   — the normalizing constant ("evidence"),
                                the reason closed-form posteriors are special:
                                for most models this integral has no
                                analytic solution, which is exactly why MCMC exists.
```

Think of the prior as a starting position on a number line and the likelihood as a magnet that pulls it toward what the data says. A tight, confident prior with little data barely moves. A weak, flat prior with the same little data moves almost entirely to where the likelihood points — this is the whole reason "the prior is a real choice" is not a throwaway line: a strong prior on a metric you don't actually have strong grounds to be confident about is silently overriding your data.

Hierarchical pooling as three positions on a spectrum:

```
NO POOLING              PARTIAL POOLING              COMPLETE POOLING
each group's own          hierarchical model:          one shared
independent estimate,     each group's estimate         estimate for
ignores other groups.     shrunk toward the group        every group.
Noisy for small groups.   mean, shrinkage strength ∝     Biased for
                           1/(group's own sample size).   atypical groups.
     θ_A  θ_B  θ_C              θ_A  θ_B  θ_C                  θ
      |    |    |                 ↘   |   ↙                    |
   (independent)              (pulled toward θ_pop)      (all forced equal)
```

---

## How it actually works

### Bayes' rule to posterior, worked with numbers

`P(θ|D) = P(D|θ) P(θ) / P(D)`. In words: posterior ∝ likelihood × prior. The denominator `P(D)` doesn't depend on θ, so for most practical purposes you work with the unnormalized posterior `P(D|θ) P(θ)` and normalize at the end (or never need to, if you're just comparing two hypotheses via a ratio — that ratio is the **Bayes factor**).

### Conjugate priors: Beta-Binomial derived end to end

A conjugate prior is one where the posterior is in the same distributional family as the prior, so the update is closed-form algebra instead of numerical integration. This is the workhorse of Bayesian A/B testing because conversion rate problems are exactly Binomial likelihoods.

Setup: you're testing a new "Book now" button color. Variant B gets `n=1000` visitors, `k=120` conversions. Prior belief about the true conversion rate `θ`: Beta(α=1, β=1), i.e. uniform over [0,1] (uninformative — you're claiming no prior knowledge, which is itself a choice).

The Binomial likelihood is `P(k|θ,n) = C(n,k) θ^k (1-θ)^(n-k)`. The Beta prior is `P(θ) ∝ θ^(α-1) (1-θ)^(β-1)`. Multiply them:

```
P(θ|k,n) ∝ θ^k (1-θ)^(n-k) · θ^(α-1) (1-θ)^(β-1)
         = θ^(α+k-1) (1-θ)^(β+n-k-1)
```

That's the kernel of a `Beta(α+k, β+n-k)` distribution. So the update rule is simply: **posterior α = prior α + successes, posterior β = prior β + failures.** With `α=1, β=1, k=120, n=1000`: posterior is `Beta(121, 881)`. Posterior mean `= α/(α+β) = 121/1002 ≈ 0.1208`, essentially the raw conversion rate, because the flat prior contributed almost nothing with n=1000 data points. Posterior standard deviation `= sqrt(αβ / ((α+β)^2 (α+β+1))) ≈ 0.0103` — about a 1-point standard deviation on a ~12.1% rate, giving a 95% credible interval roughly `[0.101, 0.141]` (computed from the Beta quantile function, not the normal approximation, though the normal approximation is close here because α and β are both large).

Now put a second variant next to it. Variant A: `n=1000, k=95` → posterior `Beta(96, 906)`, mean ≈ 0.0959. To answer "what's the probability B beats A" you either (a) draw, say, 100,000 samples from each posterior and compute the fraction where `sample_B > sample_A` (Monte Carlo, trivial to code, the standard practical approach), or (b) use the closed-form expression for `P(X>Y)` for two Beta-distributed variables, which exists but is rarely worth the extra complexity over Monte Carlo sampling at this scale. Either way this gives a direct, interpretable answer — "there's a 97.3% probability B has a higher true conversion rate than A" — that a frequentist p-value cannot give you, because a p-value is not the probability the alternative hypothesis is true.

**Normal-Normal conjugacy** is the same idea for continuous metrics (revenue per booking, session length): a Normal likelihood with known variance and a Normal prior on the mean gives a Normal posterior, with the posterior mean a precision-weighted average of the prior mean and the sample mean. Precision (`1/variance`) is additive under conjugate Normal updates, which is the cleanest way to internalize "more data always sharpens the posterior, and a tighter prior needs more data to move."

### Hierarchical / partial pooling models

Say you're evaluating a content template change across 50 hotel-brand campaigns, each with a different sample size — some ran on 50,000 visitors, some on 400. A **no-pooling** model fits each campaign's conversion rate independently: the 400-visitor campaign's estimate swings wildly with a handful of conversions and is essentially noise. A **complete-pooling** model fits one global rate and applies it to every campaign, ignoring real differences in luxury vs. budget segments. A **hierarchical (partial-pooling)** model puts a population-level prior over the campaign-level rates — e.g. each campaign's `logit(θ_i) ~ Normal(μ_pop, τ_pop)`, and `μ_pop, τ_pop` themselves get priors and are estimated from all 50 campaigns jointly. The result: small campaigns get shrunk hard toward the population mean (because their own data carries little information), large campaigns are barely shrunk at all (their own data dominates). This is not a heuristic — it's the mathematically optimal estimator under squared-error loss for exactly this structure (this is the James-Stein / empirical Bayes result generalized to the full hierarchical model), and it's why any experimentation team with segments of very different size should default to it rather than run 50 independent tests.

**Non-centered parameterization** is the production detail that actually matters when you build these: naively parameterizing `θ_i ~ Normal(μ_pop, τ_pop)` directly creates a "funnel" in the posterior geometry (when `τ_pop` is small, all the `θ_i` are forced tightly together, which is a pathological shape for gradient-based samplers to explore) that causes divergent transitions in NUTS. The fix is reparameterizing as `θ_i = μ_pop + τ_pop * z_i` with `z_i ~ Normal(0,1)`, sampling the `z_i` instead of `θ_i` directly — same model, dramatically better sampling behavior. This is one of the most common "why is my Bayesian model not converging" bugs in practice.

### MCMC and why it works

For any model without a conjugate closed form (basically anything with more than one or two parameters and non-conjugate priors — logistic regression with a Normal prior, any hierarchical model, any model with a non-standard likelihood), the posterior has no analytic formula. MCMC solves this by constructing a Markov chain whose stationary distribution *is* the posterior, then running it long enough that the samples it produces are (approximately) draws from that posterior. You never compute the posterior's normalizing constant — you don't need to, because MCMC only needs the unnormalized `likelihood × prior` to decide how to move.

**Metropolis-Hastings**, the classical version: propose a new point, accept it with probability `min(1, [P(θ')L(D|θ')] / [P(θ)L(D|θ)])` (weighted by the proposal-density ratio for asymmetric proposals) — this simple accept/reject rule is enough to guarantee the chain converges to the posterior, but naive random-walk proposals explore high-dimensional spaces extremely slowly (the "drunk man's walk" problem — correlated samples, low effective sample size per iteration).

**Hamiltonian Monte Carlo (HMC)** fixes this by treating the negative log-posterior as a potential energy surface and simulating physics: introduce auxiliary momentum variables, run Hamiltonian dynamics (using the gradient of the log-posterior) for a number of leapfrog steps, and accept/reject the resulting point with a Metropolis correction. Because it uses the gradient, it moves in informed, long, low-correlation steps instead of a random walk — this is *why* HMC-based samplers need 10-100x fewer iterations than Metropolis-Hastings for equivalent effective sample size.

**NUTS (No-U-Turn Sampler)**, the default in Stan and PyMC, automates HMC's two hardest hyperparameters (step size, via dual averaging during warm-up to hit a target acceptance rate typically ~0.8; and the number of leapfrog steps, by simulating until the trajectory starts to double back on itself — the "U-turn") so practitioners don't hand-tune them.

**Convergence diagnostics you must know cold:** `R-hat` (Gelman-Rubin statistic) compares between-chain and within-chain variance across multiple independent chains (typically 4) — values should be **below 1.01**; anything meaningfully above signals the chains haven't mixed to the same distribution and your posterior samples are not trustworthy. **Effective sample size (ESS)** corrects the raw sample count for autocorrelation between consecutive draws — a common floor is **ESS > 400** per parameter (both bulk-ESS for the center of the distribution and tail-ESS for the extremes) before trusting posterior summaries. **Divergent transitions** (HMC-specific) indicate the sampler hit a region of extreme curvature it couldn't integrate through accurately — even a handful of divergences (not zero) is a real warning sign, and the standard fixes are reparameterizing (non-centered, above) or increasing `target_accept` (raising it from 0.8 toward 0.95-0.99, which shrinks the step size).

### Bayesian A/B testing vs. frequentist: the honest tradeoff

**What Bayesian gets you:** (1) direct probability statements — "P(B > A | data) = 0.97" instead of a p-value that answers a different question than the one stakeholders think it answers; (2) continuous monitoring without the naive-peeking inflation that plagues a fixed-horizon t-test, *provided* the decision rule is fixed in advance (e.g., "stop and ship when P(B>A) > 0.95 AND expected loss from being wrong < $X") rather than "peek until it looks good and stop" — an unprincipled stopping rule inflates false-positive rates in Bayesian testing too, just less severely and less predictably than in naive frequentist peeking; (3) natural handling of small samples and hierarchical structure via the same machinery, versus needing entirely different frequentist tools (random-effects models, shrinkage estimators bolted on after the fact) for the same job.

**What it costs you:** (1) the prior is a real modeling decision an interviewer will push on — a flat/uninformative prior on a metric where you actually have five years of historical data is throwing away information, but an informative prior set carelessly (or dishonestly, to make a launch look better) silently biases the "objective-sounding" posterior probability; (2) computational cost for anything beyond conjugate models (MCMC runtime, convergence diagnostics, engineering to run this at the query latency an experimentation dashboard needs); (3) stakeholder confusion in the other direction — "97% probability B is better" gets over-trusted as certainty in a way a p-value, precisely because it's harder to parse, sometimes doesn't; (4) no universally agreed decision rule — frequentist testing has one dominant convention (α=0.05), Bayesian testing has several competing ones (posterior probability threshold, expected loss threshold, ROPE — region of practical equivalence) and picking one is itself a judgment call you need to defend.

**The honest synthesis for an interview answer:** Bayesian and frequentist are both valid under their own assumptions; the practical decision driver is usually *organizational* — do you need continuous monitoring and intuitive probability statements for stakeholders (Bayesian, or anytime-valid frequentist sequential testing), or do you need a single well-understood, audit-friendly convention across hundreds of simultaneous tests run by teams who won't individually reason about priors (frequentist, or Bayesian with a strictly enforced non-informative prior and a fixed decision rule)? Naming both real costs, not picking a side as ideology, is the senior signal.

---

## Build it from scratch

```python
# untested sketch — Beta-Binomial Bayesian A/B test, no external Bayesian library required
import numpy as np

def beta_binomial_ab_test(
    conversions_a: int, visitors_a: int,
    conversions_b: int, visitors_b: int,
    prior_alpha: float = 1.0, prior_beta: float = 1.0,
    n_samples: int = 200_000, seed: int = 0,
) -> dict:
    rng = np.random.default_rng(seed)

    post_a_alpha = prior_alpha + conversions_a
    post_a_beta = prior_beta + (visitors_a - conversions_a)
    post_b_alpha = prior_alpha + conversions_b
    post_b_beta = prior_beta + (visitors_b - conversions_b)

    samples_a = rng.beta(post_a_alpha, post_a_beta, n_samples)
    samples_b = rng.beta(post_b_alpha, post_b_beta, n_samples)

    prob_b_beats_a = float(np.mean(samples_b > samples_a))
    lift_samples = (samples_b - samples_a) / samples_a
    expected_loss_choosing_b = float(np.mean(np.maximum(samples_a - samples_b, 0.0)))
    expected_loss_choosing_a = float(np.mean(np.maximum(samples_b - samples_a, 0.0)))

    return {
        "posterior_a": (post_a_alpha, post_a_beta),
        "posterior_b": (post_b_alpha, post_b_beta),
        "p_b_beats_a": prob_b_beats_a,
        "expected_lift_pct": float(np.mean(lift_samples) * 100),
        "credible_interval_lift_95": (
            float(np.percentile(lift_samples, 2.5) * 100),
            float(np.percentile(lift_samples, 97.5) * 100),
        ),
        "expected_loss_if_ship_b": expected_loss_choosing_b,   # decision rule: ship B if this < threshold
        "expected_loss_if_ship_a": expected_loss_choosing_a,
    }

# Hierarchical partial pooling with PyMC — untested sketch
# import pymc as pm
# with pm.Model() as hierarchical_model:
#     mu_pop = pm.Normal("mu_pop", mu=0, sigma=1.5)          # population logit-mean
#     tau_pop = pm.HalfNormal("tau_pop", sigma=1.0)          # population logit-sd
#     z = pm.Normal("z", mu=0, sigma=1, dims="campaign")      # non-centered
#     theta_logit = mu_pop + tau_pop * z
#     theta = pm.Deterministic("theta", pm.math.invlogit(theta_logit), dims="campaign")
#     y = pm.Binomial("y", n=visitors_per_campaign, p=theta, observed=conversions_per_campaign)
#     idata = pm.sample(2000, tune=1000, target_accept=0.9, chains=4)
# import arviz as az
# az.summary(idata, var_names=["mu_pop", "tau_pop", "theta"])  # check r_hat < 1.01, ess_bulk > 400
```

Reference next: PyMC's own multilevel-modeling example gallery walks the non-centered reparameterization end to end; Stan's user guide has the canonical write-up of the funnel geometry problem.

---

## How it's done in production

**PyMC** and **Stan** (via `cmdstanpy`/`brms` in R) are the standard tools for anything beyond conjugate models — Stan for raw performance and a mature ecosystem, PyMC for a Python-native workflow that integrates with the rest of an ML stack. **NumPyro** (JAX-backed) is the choice when you need GPU-accelerated MCMC or want autodiff-based HMC inside a broader JAX pipeline. Commercial experimentation platforms (VWO, Optimizely, Statsig) ship Bayesian engines as a toggle alongside frequentist ones, usually built on conjugate Beta-Binomial or Normal models for speed at dashboard scale — real hierarchical MCMC is rarely run live in a self-serve dashboard because of latency, and is instead run as an offline weekly or nightly job for cross-campaign shrinkage analysis.

| Symptom | Cause | Fix |
|---|---|---|
| Posterior probability "flip-flops" day to day early in a test | Small sample size, genuinely wide posterior, being read as a confident signal | Report the credible interval alongside the point probability; set a minimum sample-size floor before displaying a go/no-go recommendation |
| MCMC sampler reports divergent transitions | Funnel geometry from a directly-parameterized hierarchical model | Non-centered reparameterization; raise `target_accept` toward 0.95-0.99 as a second lever |
| R-hat > 1.01 after the default number of iterations | Chains haven't mixed — multimodal posterior, poor initialization, or too few iterations | Run more iterations/longer warm-up, check for identifiability issues in the model, try different chain initializations |
| Two variants both show P(B>A) ≈ 0.5 despite what looks like a visible gap in raw conversion rates | Small sample, wide posteriors overlapping heavily — the "gap" is well within noise | This is the model working correctly — report it as inconclusive, don't let a compelling-looking raw number override the posterior |
| Bayesian dashboard shows "98% probability of a winner" after 200 visits per arm | Uninformative or default prior barely constraining a tiny-n posterior, and/or a team peeking without a defined stopping rule | Enforce a minimum sample/duration floor regardless of the posterior; audit the actual prior being used by the platform, not just the vendor's marketing claim about "no peeking penalty" |
| Hierarchical model's shrinkage looks "too strong" — small segments all clustered near the population mean | `tau_pop` (between-group variance) posterior concentrated near zero because groups genuinely don't differ much in the data, or prior on `tau_pop` too tight | Check `tau_pop`'s posterior and prior; if the model is right this is correct behavior, not a bug — verbalize this distinction to stakeholders who expected their segment to look special |

---

## Tradeoffs & when NOT to use it

- **Don't reach for full MCMC-based Bayesian inference when a conjugate model already answers the question.** Beta-Binomial in closed form is faster, has zero convergence-diagnostic overhead, and is auditable by anyone who knows the algebra — MCMC is for when the model genuinely needs it (hierarchical structure, non-conjugate likelihoods, custom loss functions), not by default.
- **Don't use an informative prior you can't defend in the room.** If a VP asks "why did you assume that," and the honest answer is "it made the result look better," that's not a modeling choice, that's manufacturing significance with extra steps — the Bayesian framing makes this both easier to do and easier to hide, which is exactly why it should be avoided.
- **Don't claim "no peeking penalty" as an unconditional fact.** It's true for a fixed, pre-registered decision rule under standard assumptions; it is not automatically true for an analyst staring at a live dashboard and stopping whenever the number looks good enough — that's still a form of optional stopping and can still bias results.
- **Hierarchical pooling is the wrong tool when segments are genuinely, structurally different** (e.g., B2B vs. B2C conversion funnels) rather than noisy variations around a shared mean — pooling in that case actively biases the atypical segment's estimate toward an irrelevant population.
- **For a single, well-powered, standard two-arm test where the org already has frequentist tooling, dashboards, and institutional trust in p-values, switching to Bayesian buys little** and adds a real cost in stakeholder re-education — pick your battles about which experiments actually need the hierarchical/continuous-monitoring benefits.

---

## Interview questions

### Q1 — State Bayes' theorem and explain what each term means in an A/B testing context.
**Testing:** baseline fluency, not just formula recall.
**Answer:** `P(θ|D) = P(D|θ)P(θ)/P(D)`. `θ` is the true conversion rate you're trying to learn; `P(θ)` is your prior belief about it before seeing data; `P(D|θ)` is the likelihood — how probable the observed conversions are under a given rate; `P(θ|D)` is the posterior, your updated belief after the experiment; `P(D)` is a normalizing constant, often intractable, which is why MCMC exists for non-conjugate models.
**Follow-up trap:** *"Is P(θ|D) the same as the p-value?"* — no, and conflating them is the single most common mistake; a p-value is `P(data this extreme | null true)`, the posterior is `P(parameter value | observed data)` — different conditioning entirely.

### Q2 — Derive the Beta-Binomial posterior update from scratch.
**Testing:** can you actually do the algebra, not just quote the answer.
**Answer:** Multiply the Binomial likelihood `θ^k(1-θ)^(n-k)` by the Beta prior kernel `θ^(α-1)(1-θ)^(β-1)`, combine exponents to get `θ^(α+k-1)(1-θ)^(β+n-k-1)`, recognize that as the kernel of `Beta(α+k, β+n-k)`. Posterior α = prior α + successes; posterior β = prior β + failures.
**Follow-up trap:** *"What if you use a Beta(0,0) prior?"* — that's an improper prior (doesn't integrate to 1) equivalent to Haldane's prior; it can still yield a proper posterior once you have at least one success and one failure, but with zero successes or zero failures it produces a degenerate posterior — flag this as a real edge case, not a safe default.

### Q3 — Two variants: A has 95/1000 conversions, B has 120/1000. Walk through how you'd decide whether to ship B.
**Answer:** Fit posteriors `Beta(96,906)` for A and `Beta(121,881)` for B (flat prior). Monte Carlo sample both, compute `P(B>A)` directly — call it ~97%. But don't stop at that number: compute expected loss for each decision (`E[max(θ_A - θ_B, 0)]` if you ship B, and vice versa) and compare against a threshold tied to the actual cost of being wrong, not just a probability cutoff — a 97% probability of a 0.5-point lift is a very different decision than 97% probability of a 5-point lift.
**Follow-up trap:** *"What if the sample sizes were 20 and 24 instead of 95 and 120?"* — the posteriors would be far wider and overlap heavily; report the credible interval, not just the point probability, and say explicitly that you would not ship off that sample size regardless of what the probability says.

### Q4 — What's a conjugate prior, and why does it matter operationally, not just mathematically?
**Answer:** A prior where the posterior stays in the same distributional family, giving a closed-form update instead of requiring numerical integration or MCMC. Operationally this means an A/B testing dashboard can compute updated posteriors on every page load with negligible latency and zero convergence diagnostics to monitor — which is exactly why every major experimentation platform's Bayesian engine is conjugate-model-based (Beta-Binomial for rates, Normal-Normal for continuous metrics), not full MCMC, at the live-dashboard layer.
**Follow-up trap:** *"When would conjugacy not be available?"* — any model with a non-standard likelihood, a hierarchical structure spanning multiple metrics, or a prior chosen for interpretability rather than mathematical convenience — that's when you fall back to MCMC.

### Q5 — Explain partial pooling and why it beats both no-pooling and complete-pooling.
**Answer:** No pooling fits each group independently, so small groups get noisy, unstable estimates that overreact to a handful of data points. Complete pooling forces every group to the same estimate, which is biased whenever groups genuinely differ. Partial pooling (hierarchical model) lets each group have its own parameter, shrunk toward a shared population estimate by an amount inversely proportional to that group's own sample size — small groups borrow strength from the population, large groups are barely shrunk. This minimizes total mean squared error across all groups simultaneously, which is a real, provable statistical result (related to Stein's paradox), not just a heuristic.
**Follow-up trap:** *"Give a concrete case where partial pooling would be wrong."* — when groups are structurally different rather than noisy variations of the same underlying process (e.g., pooling luxury and budget hotel segments' conversion rates), shrinkage actively biases the atypical group toward an irrelevant mean.

### Q6 — What is MCMC actually doing, mechanically? Why does it converge to the posterior?
**Answer:** MCMC constructs a Markov chain whose stationary distribution equals the target posterior, then runs it long enough that later samples are (approximately) draws from that posterior. Metropolis-Hastings does this via propose-and-accept/reject with an acceptance probability derived so that detailed balance holds with respect to the posterior — you never need the normalizing constant because it cancels in the acceptance ratio. HMC/NUTS improve efficiency by using the log-posterior's gradient to propose informed, low-autocorrelation moves instead of a naive random walk.
**Follow-up trap:** *"Does MCMC give you exact posterior samples?"* — no, they're correlated draws from a chain that only converges to the target distribution asymptotically and after discarding a warm-up period; that's exactly why R-hat and ESS diagnostics exist.

### Q7 — How do you know an MCMC run actually converged?
**Answer:** R-hat (Gelman-Rubin statistic) below 1.01 across multiple independent chains — it compares between-chain and within-chain variance, and a value near 1 means the chains agree on where the distribution's mass is. Effective sample size above roughly 400 per parameter, correcting for autocorrelation in the chain. For HMC/NUTS specifically, zero (or very few) divergent transitions, which flag regions of extreme posterior curvature the sampler couldn't integrate through accurately.
**Follow-up trap:** *"R-hat looks fine but you have divergences — do you trust the results?"* — no; divergences indicate a specific geometric pathology (often a funnel in a hierarchical model) that R-hat can miss if it happens in a region the chains didn't spend much time in; investigate and reparameterize before trusting posterior summaries.

### Q8 — Why do hierarchical models cause "funnel" geometry, and how do you fix it?
**Answer:** When the population-level variance parameter (`tau_pop`) is small, the group-level parameters are forced tightly around the population mean, creating a posterior shaped like a narrowing funnel — a region where the appropriate step size for the sampler changes dramatically depending on where in the funnel you are, which breaks HMC's fixed-step-size assumption within a trajectory. The fix is non-centered parameterization: sample standardized `z` variables (`Normal(0,1)`) and construct `theta = mu + tau * z` deterministically, which decouples the group-level parameters from `tau` in the sampled space and gives the sampler a much more uniform geometry to explore.
**Follow-up trap:** *"Does non-centering always help?"* — no; for models where groups have a lot of their own data (weak shrinkage, large `tau_pop`), a centered parameterization can actually sample better — the right choice depends on where the data puts you on the pooling spectrum, and a senior answer names this rather than treating non-centering as a universal fix.

### Q9 — Is Bayesian A/B testing immune to the "peeking" problem that inflates frequentist false-positive rates?
**Answer:** Not unconditionally. The claim is often oversold. Bayesian posteriors update validly with every new data point, but if the *decision rule* itself is "keep looking until it looks good, then stop," the stopping rule is data-dependent and can still bias results toward false positives, just as in frequentist optional stopping — a milder effect in practice for many priors, but not zero. True immunity requires either a pre-registered stopping rule tied to a fixed threshold/loss function, or genuinely reporting continuous uncertainty rather than a single stop/go decision made off the mode of "whenever it crosses 95%."
**Follow-up trap:** *"So what would you actually enforce on a self-serve dashboard used by non-statisticians?"* — a minimum sample size or duration floor before any go/no-go recommendation is shown, and a fixed, documented decision rule (posterior probability threshold AND expected-loss threshold) rather than letting individual PMs eyeball a live number.

### Q10 — When would you pick frequentist over Bayesian for an experimentation platform, honestly?
**Answer:** When you need one auditable, well-understood convention (α=0.05) applied uniformly across hundreds of simultaneous tests run by teams who won't individually reason about priors — a shared frequentist convention avoids the "whose prior was this" argument entirely. Also when stakeholders are already fluent in p-values and confidence intervals and the switching cost of re-educating an organization outweighs the intuitive-probability benefit Bayesian gives you. Anytime-valid frequentist sequential testing (confidence sequences) is also a legitimate answer to "I want to peek" that doesn't require adopting Bayesian machinery at all.
**Follow-up trap:** *"Isn't that just avoiding the hard question?"* — no; naming the organizational tradeoff explicitly, rather than treating this as a purely statistical question with one right answer, is exactly the senior-level answer the interviewer wants.

### Q11 — How would you explain a posterior probability of 92% to an SVP who is about to walk out of the room and greenlight a launch off that one number?
**Answer:** State plainly what it means ("given the data we've seen, there's about a 92% chance the true effect is positive") and immediately attach the magnitude and uncertainty ("but the credible interval for the size of that effect is -0.3% to +4.1% — it could be a strong win or a rounding error, and 92% is not the same as 100%"). Pair the probability with the expected-loss framing if the launch is costly to reverse: "expected loss from launching if we're wrong is X, expected loss from waiting another week is Y."
**Follow-up trap:** *"What if they push back with 'just give me a yes or no'?"* — give the recommendation implied by your pre-agreed decision rule, but explicitly restate that the underlying uncertainty doesn't disappear because a single number was chosen to represent it; the decision rule, not the interviewer's or SVP's gut feel, should be what's being defended.

### Q12 — Design a Bayesian hierarchical framework for evaluating a new content template across 200 hotel-brand campaigns with wildly uneven traffic (some at 500K impressions/month, some at 200).
**Testing:** synthesis at the level the Expedia team actually operates.
**Answer:** Model each campaign's conversion rate as `logit(theta_i) ~ Normal(mu_pop, tau_pop)`, non-centered, with `mu_pop` and `tau_pop` estimated jointly from all 200 campaigns. Small campaigns get pulled toward the population estimate; large campaigns dominate their own posterior. Add a second hierarchical level if there's a natural grouping (e.g., by market/region) to share strength within a region before falling back to the global population. Run this as an offline batch job (MCMC doesn't need to be live-dashboard fast) refreshed daily or weekly, and surface per-campaign posterior probability of improvement plus a flag on campaigns still dominated by the prior (i.e., too little of their own data to say anything campaign-specific yet).
**Follow-up trap:** *"What breaks if you skip the hierarchy and just run 200 independent Beta-Binomial tests?"* — the smallest campaigns will show wildly unstable week-to-week probability estimates and generate false "winners" and "losers" off single-digit conversion counts, which is exactly the failure mode hierarchical pooling exists to prevent.

### Q13 — What's the difference between a credible interval and a confidence interval, precisely?
**Answer:** A 95% credible interval is a statement about the posterior: there's a 95% probability the true parameter lies in that range, given the model and the data — a direct probability statement about the parameter. A 95% confidence interval is a statement about the *procedure*: if you repeated the experiment many times, 95% of the intervals constructed this way would contain the true parameter — it says nothing about the probability the true value is in any *one particular* interval you computed.
**Follow-up trap:** *"So can I just say a 95% CI means 95% probability the true value is in it?"* — no, that's the single most common statistical misstatement in industry and interviewers listen for exactly this; the credible interval is what actually licenses that sentence, and only under the stated model and prior.

### Q14 — A colleague sets an informative prior "based on similar past campaigns" and the posterior comes back favorable for a launch they were already pushing for. How do you evaluate this?
**Testing:** integrity and rigor under social pressure, a real staff-level signal.
**Answer:** Ask to see the prior's parameters and how they were derived — was it fit from an honest, pre-specified reference class of past campaigns, or chosen after seeing this campaign's early data (which is prior-hacking, functionally equivalent to p-hacking)? Run a sensitivity analysis: refit with a flat/uninformative prior and see how much the conclusion changes. If the launch recommendation only holds under the informative prior and reverses under a flat one, that's a load-bearing modeling choice that needs to be surfaced to whoever is making the launch call, not buried in a slide that just shows the final probability.
**Follow-up trap:** *"What if the informative prior is genuinely well-justified?"* — then it should survive a sensitivity check and a plain-language justification of the reference class used; the process of checking is the point, not assuming bad faith by default.

---

## Red flags that fail you

- Saying a p-value is "the probability the null hypothesis is true" (that's the posterior, not the p-value — and even the posterior needs a stated prior to mean that).
- Claiming Bayesian testing has "no peeking penalty" as an unconditional fact rather than a property that depends on a pre-specified stopping rule.
- Not knowing that R-hat and ESS are the two convergence diagnostics to check before trusting any MCMC output.
- Treating a hierarchical model's shrinkage as always desirable regardless of whether groups are structurally different or just noisy variants of one process.
- Presenting a posterior probability to stakeholders without the accompanying credible interval or effect-size magnitude.
- Not being able to derive the Beta-Binomial update from the Binomial likelihood and Beta prior kernel when asked.
- Picking Bayesian or frequentist as an ideological default instead of naming the organizational and statistical tradeoffs of each.

---

## Cheat card

```
BAYES        posterior ∝ likelihood × prior;  P(D) is the (often intractable) normalizer
CONJUGATE    Beta-Binomial: post_alpha = prior_alpha + successes, post_beta = prior_beta + failures
             Normal-Normal: posterior mean = precision-weighted avg of prior mean & sample mean
HIERARCHICAL partial pooling: theta_i ~ Normal(mu_pop, tau_pop); shrinkage ∝ 1/(group's own n)
             non-centered param (theta = mu + tau*z) fixes funnel geometry / divergences
MCMC         Metropolis-Hastings: accept w.p. min(1, posterior_ratio). Random walk, slow mixing.
             HMC/NUTS: gradient-informed trajectories, 10-100x fewer iters for same ESS
             DIAGNOSTICS: R-hat < 1.01, ESS > ~400/param, ~0 divergent transitions
BAYESIAN AB  gets you: direct P(B>A), continuous monitoring w/o naive-peeking inflation (IF
             stopping rule fixed in advance), natural small-sample/hierarchy handling
             costs you: prior is a real defensible choice, compute cost beyond conjugate models,
             "no peeking penalty" is conditional not automatic, no single agreed decision rule
CI vs CrI    credible interval: P(true value in range | data) = 95%, direct parameter statement
             confidence interval: 95% of intervals built this way contain the true value (about
             the PROCEDURE, not this one interval)
DECISION     don't ship off posterior probability alone — pair with expected loss / effect size
             and a pre-agreed threshold, not a live-dashboard gut call
```

## Sources

- [Straightforward Bayesian A/B testing with Dirichlet posteriors](https://arxiv.org/pdf/2508.08077) — accessed 2026-08-02
- [Bayesian A/B Testing — Bayesian Inference and Functional Programming](https://jonnylaw.rocks/posts/2025-09-21-bayesian-ab-testing/) — accessed 2026-08-02
- [Frequentist vs Bayesian A/B Testing: How to Choose — Convert](https://www.convert.com/blog/a-b-testing/frequentist-vs-bayesian-ab-testing/) — accessed 2026-08-02
- [Bayesian A/B Testing vs Frequentist: When to Use Each — Statsig](https://www.statsig.com/perspectives/bayesian-ab-testing-vs-frequentist) — accessed 2026-08-02
- [Bayesian AB Testing is Not Immune to Optional Stopping Issues — Analytics-Toolkit](https://blog.analytics-toolkit.com/2017/bayesian-ab-testing-not-immune-to-optional-stopping-issues/) — accessed 2026-08-02
- [Is Bayesian A/B Testing Immune to Peeking? Not Exactly — Variance Explained](http://varianceexplained.org/r/bayesian-ab-testing/) — accessed 2026-08-02
- [Anytime-Valid Confidence Sequences in an Enterprise A/B Testing Platform](https://arxiv.org/pdf/2302.10108) — accessed 2026-08-02
- [Hierarchical Bayesian Regression with PyMC: When Groups Share Strength](https://sesen.ai/blog/hierarchical-bayesian-regression-pymc) — accessed 2026-08-02
- [A Primer on Bayesian Methods for Multilevel Modeling — PyMC example gallery](https://www.pymc.io/projects/examples/en/latest/generalized_linear_models/multilevel_modeling.html) — accessed 2026-08-02

## Changelog
- 2026-08-02 — created
