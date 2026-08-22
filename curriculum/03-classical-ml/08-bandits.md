# Multi-Armed and Contextual Bandits: ε-Greedy, UCB, Thompson Sampling, LinUCB

> **Track:** T03 Classical ML · **Time:** 2h · **Prereqs:** T03-recsys · **Updated:** 2026-08-03
> **Module id:** `T03-bandits` · **Tags:** rl, critical
> **Lab:** `labs/python/08-bandits/`

## The 30-second version

Every bandit algorithm is answering the same question — allocate the next trial to maximize cumulative reward while you don't yet know which option is best — and they differ only in *how* they trade exploration against exploitation. ε-greedy is the crudest answer: exploit the current best arm `1-epsilon` of the time, explore uniformly at random `epsilon` of the time, forever, which wastes exploration budget on arms already known to be bad and never fully commits even once an arm is provably best. UCB (Upper Confidence Bound) fixes this with "optimism under uncertainty": pick the arm maximizing `mean_reward + confidence_bonus`, where the bonus (classically `sqrt(2*ln(t)/n_i)` for arm `i` pulled `n_i` times at round `t`) shrinks as an arm accumulates pulls, so exploration is automatically concentrated on under-sampled arms rather than wasted uniformly. Thompson sampling takes a Bayesian view: maintain a posterior distribution over each arm's true reward rate (a Beta distribution for Bernoulli rewards, updated in closed form with every observation), sample one value from each arm's posterior, and pick the arm with the highest sample — arms with more uncertainty (wider posteriors) get sampled a wider range of values, naturally encouraging exploration proportional to actual uncertainty without a hand-tuned exploration parameter, and it consistently performs at least as well as UCB in empirical comparisons while requiring less tuning. LinUCB extends UCB to contextual bandits, where the reward depends on both the chosen arm and a context vector (user features, page features) — it maintains a ridge-regression estimate of each arm's expected reward as a linear function of context, with the confidence bonus derived from the same ridge regression's uncertainty, letting the algorithm personalize its exploration/exploitation decision per context rather than treating every round as identical. This entire family matters in production precisely where full A/B testing is too slow or too costly for irreversible-feeling decisions made continuously — recommendation ranking, pricing, content selection — because a bandit adapts its allocation online instead of waiting for a fixed-horizon experiment to conclude.

## Why this gets asked

Because this candidate's own resume includes PySpark/EMR contextual bandits, an interviewer will treat "bandits" as a topic where a surface-level answer ("it's like A/B testing but smarter") gets probed hard for whether the underlying math and the operational tradeoffs were genuinely internalized during that work, not just the vocabulary. It's also asked broadly because bandits are the standard production answer to "we need to learn which option is best while we're still serving traffic, and every trial has real cost," which shows up constantly in recommendation, pricing, and content-ranking systems, and separates candidates who understand the regret-minimization framing from those who only know "explore vs exploit" as a phrase.

---

## Lineage: past → present → future

**What came before.** Before bandit algorithms were the standard framing, sequential decision-making under uncertainty in production was handled either by fixed-horizon A/B tests (commit a fixed traffic split for a fixed duration, then decide) or by pure exploitation heuristics with no principled exploration at all — both have real costs: A/B testing wastes traffic on a clearly-losing variant for the entire test duration by design (a fixed 50/50 split doesn't adapt even after the losing arm's badness becomes statistically obvious partway through), while pure exploitation risks permanently committing to a suboptimal option discovered early by chance, with no mechanism to revisit that decision. The multi-armed bandit problem itself is much older than its ML-production application (Robbins, 1952; Lai & Robbins, 1985 established the theoretical regret lower bounds that UCB-family algorithms are designed to approach), but its adoption as a practical alternative to fixed A/B testing in tech industry production systems is comparatively recent, driven by the recognition that continuously-running systems (a ranking or pricing engine making millions of decisions per day) have both the trial volume and the online-adaptation need that make bandit algorithms' advantages over static A/B testing concretely worth the added complexity.

**Where it stands now.** ε-greedy remains common specifically because of its simplicity and ease of explaining to non-technical stakeholders, despite being provably suboptimal (its regret grows linearly in the worst case if `epsilon` doesn't decay, versus UCB/Thompson sampling's logarithmic regret) — the practical consensus is that UCB-family and Thompson sampling are both strong choices for most production stateless (non-contextual) bandit problems, with Thompson sampling generally preferred where a natural conjugate prior exists (Beta-Bernoulli for click/no-click being the most common case) because of its strong empirical performance and comparatively simpler tuning (no confidence-bonus scaling constant to hand-tune). For contextual problems, LinUCB and Thompson-sampling variants with a linear (or more complex, e.g., neural) reward model are the standard production approach, and the field's live disagreement is less about the exploration strategy itself and more about how to combine bandits cleanly with off-policy evaluation and safe deployment practices — a bandit that's actively exploring is, by definition, sometimes serving a worse-than-optimal arm, which requires careful monitoring and often an explicit "safety net" (a minimum floor on how much exploration is allowed, or a kill-switch based on real-time performance) that pure academic bandit theory doesn't always address directly.

**Where it's heading.** Contextual and deep-learning-augmented bandits (using a neural network rather than linear ridge regression to model reward as a function of rich context) continue to see production adoption where context is high-dimensional or has complex nonlinear structure, though linear contextual bandits (LinUCB and its Thompson-sampling analogue) remain the default first choice given their strong theoretical guarantees, comparative simplicity, and lower risk of the exploration behaving unpredictably relative to a well-understood linear model. There's continued, active work on off-policy evaluation for bandits (estimating how a new policy would have performed using only data logged under an old policy, without deploying it) and on combining bandits with reinforcement learning framings for problems with longer-horizon reward structure (a recommendation's effect on long-term retention, not just immediate click) — this longer-horizon extension is genuinely unsettled and an active research area as of 2026, distinct from the well-established single-step bandit theory this module covers.

---

## Mental model

```
THE CORE TENSION every bandit algorithm resolves differently:

  EXPLOIT: pick the arm with the best observed average so far
    -- risk: you committed too early based on noisy early observations,
       and a truly-better arm never gets enough trials to prove itself

  EXPLORE: try arms you're uncertain about, even if their average looks worse
    -- risk: you waste trials on arms that really are worse, forever, if you
       never stop exploring proportionally to what you've already learned

  epsilon-GREEDY:  fixed exploration rate forever, uniform across all arms
                   (doesn't concentrate exploration on UNCERTAIN arms specifically)

  UCB:             pick argmax( mean_reward_i + confidence_bonus_i )
                   bonus SHRINKS as arm i accumulates pulls -> automatically explores
                   under-sampled arms more, converges to pure exploitation of the best arm

  THOMPSON:        maintain a POSTERIOR distribution per arm; sample ONE value from
                   each posterior; pick the arm with the highest SAMPLE (not highest mean)
                   wide posterior (uncertain) -> wide range of possible samples -> more
                   likely to occasionally "win" the sampling draw -> natural exploration

       arm A posterior: narrow, high mean       arm B posterior: WIDE, lower mean
              ___                                    ___
             /   \  (confident, well-estimated)     /     \  (uncertain -- could be
            /     \                                /       \   much better OR much worse)
           /_______\                              /_________\
       Thompson sampling occasionally samples FAR into B's wide tail, testing it --
       exactly the exploration UCB's confidence bonus achieves via a different mechanism

  LINUCB (CONTEXTUAL): same idea as UCB, but mean_reward_i is now a per-arm RIDGE
    REGRESSION on context x: reward_i(x) ~= theta_i . x, with confidence bonus derived
    from that regression's own uncertainty (grows in directions of x-space with less data)
```

The one-line mental model: **every bandit algorithm is a different mechanism for making exploration proportional to genuine uncertainty rather than fixed or uniform — UCB does it via an explicit shrinking confidence bonus, Thompson sampling does it via sampling from a posterior whose width IS the uncertainty, and LinUCB/contextual Thompson sampling do either of these per-context rather than globally.**

---

## How it actually works

### ε-greedy: the simplest baseline, and precisely why it's provably suboptimal

At each round, with probability `1-epsilon` pick the arm with the highest observed mean reward so far; with probability `epsilon`, pick uniformly at random among all arms. The problem is structural, not a tuning issue: a fixed `epsilon` explores *every* arm equally often in expectation, including arms that have already accumulated enough evidence to be confidently ruled out — this means ε-greedy's cumulative regret (the total reward lost relative to always having played the best arm) grows **linearly** in the number of rounds if `epsilon` is held constant, because a constant fraction of all future rounds keeps getting wasted on uniform exploration forever, even after the optimal arm is essentially certain. A decaying `epsilon` (e.g., `epsilon_t = c/t`) can achieve logarithmic regret with careful tuning of the decay schedule, but this reintroduces exactly the hand-tuning problem UCB and Thompson sampling are designed to avoid.

### UCB: optimism under uncertainty, derived

UCB1 (Auer, Cesa-Bianchi, Fischer, 2002) selects, at round `t`, the arm maximizing `mean_reward_i + sqrt(2*ln(t) / n_i)`, where `n_i` is the number of times arm `i` has been pulled so far. The bonus term is derived from a Chernoff-Hoeffding concentration bound: with high probability, the true mean reward of arm `i` lies within `sqrt(2*ln(t)/n_i)` of its observed sample mean, so `mean_reward_i + bonus_i` is (with high probability) an **upper bound** on arm `i`'s true mean reward — picking the arm with the highest such upper bound is "optimistic": you're always acting as if every arm is exactly as good as its plausible best case, which naturally pulls under-sampled arms (large bonus, since `n_i` is small) into contention even if their observed mean looks mediocre, while well-sampled arms' bonuses shrink toward zero as `n_i` grows, converging the algorithm toward pure exploitation of whichever arm's true mean is actually highest. This gives UCB1 a provable regret bound of `O(log t)` — exploration naturally tapers as evidence accumulates, rather than continuing at a fixed rate forever as in ε-greedy.

### Thompson sampling: Bayesian posterior sampling, worked for Bernoulli rewards

For a Bernoulli reward (click/no-click), Thompson sampling maintains a Beta distribution posterior for each arm's true click-through rate, initialized to `Beta(1,1)` (uniform prior, no information) and updated in closed form after every observation: `Beta(alpha, beta) -> Beta(alpha+1, beta)` after an observed success, `Beta(alpha, beta+1)` after a failure — this closed-form conjugate update is exactly why Beta-Bernoulli is the standard textbook and production case, since it requires no numerical approximation at all. At each round, sample one value from every arm's current Beta posterior and pick the arm with the highest sampled value — an arm with few observations has a wide posterior (its Beta distribution puts meaningful probability mass across a broad range of possible true rates), so it will occasionally produce a high sample purely from that width, giving it a genuine chance to be selected and thereby explored, in rough proportion to how uncertain it actually is; an arm with many observations has a narrow posterior tightly concentrated around its true rate, so its samples reliably reflect that arm's actual quality with little further exploration value. Empirically, Thompson sampling matches or beats UCB-family algorithms across a wide range of published bandit benchmarks while requiring no hand-tuned confidence-bonus scaling constant, which is a large part of its popularity in production.

### LinUCB: extending UCB to contextual bandits

In a contextual bandit, the reward for choosing arm `i` given context `x` (e.g., a user's feature vector) is modeled as `E[reward | x, arm=i] = theta_i . x`, a per-arm linear function of context. LinUCB (Li et al., 2010) maintains, for each arm `i`, a ridge regression estimate `theta_i_hat = (D_i^T D_i + lambda*I)^-1 D_i^T c_i` (where `D_i` is the matrix of context vectors observed when arm `i` was chosen, `c_i` the corresponding observed rewards — exactly the ridge closed form from the regularization module) and selects, at each round, the arm maximizing `x^T theta_i_hat + alpha * sqrt(x^T (D_i^T D_i + lambda*I)^-1 x)` — the second term is a context-dependent confidence bonus derived from the ridge regression's own uncertainty, which grows specifically in directions of context-space where arm `i` has seen little data (a novel combination of context features it hasn't encountered much), and shrinks in well-explored directions. This lets LinUCB personalize its exploration: it can be confidently exploiting arm `i` for a well-understood segment of users while still exploring arm `i` more aggressively for a segment of users whose context looks unlike anything seen before, all within a single unified model rather than requiring separate bandit instances per segment.

### Regret: the metric that actually matters, and why "accuracy" isn't the right frame

Cumulative regret is defined as `sum_t (reward_of_best_arm - reward_of_chosen_arm_at_t)` — the total reward *lost* relative to a hypothetical oracle that always played the single best arm from the start. This is the correct evaluation frame for bandit algorithms specifically because it accounts for the cost of exploration itself: an algorithm that eventually identifies the best arm perfectly but took many rounds of costly exploration to get there has higher regret than one that converges faster, even if both eventually "learn the right answer" — this is a meaningfully different evaluation question than a classifier's accuracy, and confusing the two (e.g., evaluating a bandit only on "did it eventually find the best arm" without weighting by how much reward was lost during the process) misses the entire point of the exploration-exploitation tradeoff.

---

## Build it from scratch

```python
import numpy as np

def epsilon_greedy(true_means, n_rounds, epsilon=0.1, seed=0):
    rng = np.random.default_rng(seed)
    n_arms = len(true_means)
    counts, sums = np.zeros(n_arms), np.zeros(n_arms)
    rewards = []
    for t in range(n_rounds):
        if rng.random() < epsilon:
            arm = rng.integers(n_arms)
        else:
            means = np.where(counts > 0, sums / np.maximum(counts, 1), np.inf)
            arm = np.argmax(means)
        reward = rng.random() < true_means[arm]          # Bernoulli reward
        counts[arm] += 1
        sums[arm] += reward
        rewards.append(reward)
    return rewards

def ucb1(true_means, n_rounds, seed=0):
    rng = np.random.default_rng(seed)
    n_arms = len(true_means)
    counts, sums = np.zeros(n_arms), np.zeros(n_arms)
    rewards = []
    for t in range(1, n_rounds + 1):
        if np.any(counts == 0):
            arm = np.argmin(counts)                       # play every arm at least once first
        else:
            means = sums / counts
            bonus = np.sqrt(2 * np.log(t) / counts)
            arm = np.argmax(means + bonus)
        reward = rng.random() < true_means[arm]
        counts[arm] += 1
        sums[arm] += reward
        rewards.append(reward)
    return rewards

def thompson_sampling(true_means, n_rounds, seed=0):
    rng = np.random.default_rng(seed)
    n_arms = len(true_means)
    alpha, beta = np.ones(n_arms), np.ones(n_arms)         # Beta(1,1) uniform prior
    rewards = []
    for t in range(n_rounds):
        samples = rng.beta(alpha, beta)
        arm = np.argmax(samples)
        reward = rng.random() < true_means[arm]
        alpha[arm] += reward                               # closed-form conjugate update
        beta[arm] += (1 - reward)
        rewards.append(reward)
    return rewards

def lin_ucb(true_theta, context_fn, n_arms, n_rounds, d, alpha_bonus=1.0, lam=1.0, seed=0):
    """true_theta: (n_arms, d), context_fn(t) -> d-dim context vector."""
    rng = np.random.default_rng(seed)
    A = [lam * np.eye(d) for _ in range(n_arms)]           # D_i^T D_i + lambda*I, incremental
    b = [np.zeros(d) for _ in range(n_arms)]
    rewards = []
    for t in range(n_rounds):
        x = context_fn(t)
        scores = []
        for i in range(n_arms):
            A_inv = np.linalg.inv(A[i])
            theta_hat = A_inv @ b[i]
            mean = x @ theta_hat
            bonus = alpha_bonus * np.sqrt(x @ A_inv @ x)
            scores.append(mean + bonus)
        arm = np.argmax(scores)
        true_reward_prob = 1 / (1 + np.exp(-(true_theta[arm] @ x)))    # logistic ground truth
        reward = rng.random() < true_reward_prob
        A[arm] += np.outer(x, x)
        b[arm] += reward * x
        rewards.append(reward)
    return rewards
```
The lab exercise runs all four on the same synthetic multi-armed setup (five arms with known true click rates, 10,000 rounds, averaged over many random seeds) and plots cumulative regret curves side by side — the exercise is specifically designed so ε-greedy's regret grows visibly linearly while UCB and Thompson sampling's regret curves visibly flatten (logarithmic growth), making the theoretical regret-bound difference concrete rather than asserted; the contextual `lin_ucb` variant is then compared against a context-blind UCB on a setup where reward genuinely depends on context, showing the accuracy gap that ignoring context produces.

---

## How it's done in production

| Symptom | Cause | Fix |
|---|---|---|
| A bandit-driven ranking/pricing system shows persistently worse average performance than a simple fixed A/B test would have, long after launch | `epsilon` (for ε-greedy) or the confidence-bonus scaling constant (for UCB) is poorly tuned, causing excessive ongoing exploration well past the point where the best arm is confidently known | Switch to Thompson sampling (no exploration-rate constant to hand-tune) or properly decay `epsilon`/tune the UCB bonus constant against a regret-minimization objective, not a fixed default |
| A contextual bandit performs well on average but noticeably poorly for a specific, identifiable user segment | That segment's context region has been under-explored (LinUCB's confidence bonus for that region may be poorly calibrated if `lambda` or `alpha_bonus` is mistuned, or the segment is simply rare in traffic) | Check per-segment cumulative regret specifically, not just aggregate regret; consider a segment-specific or hierarchical prior for genuinely rare segments |
| A bandit exploring in production occasionally serves a clearly bad arm to a real user, causing a visible, embarrassing outcome | This is expected, inherent behavior of any exploring bandit — exploration necessarily means sometimes serving a suboptimal arm, by definition | Add an explicit safety floor (never explore options below a minimum quality threshold, determined offline) or exclude known-catastrophic arms entirely from the exploration set rather than trusting the bandit's own convergence to rule them out fast enough |
| Offline evaluation of a new bandit policy using historical logs from an old policy gives an unreliable or clearly biased estimate | Historical logs reflect the old policy's own action-selection probabilities — naively averaging logged rewards for actions the new policy would have chosen doesn't correct for how differently the old and new policies allocate traffic | Use inverse propensity scoring (weight each logged reward by 1/probability the old policy assigned to that action) or a doubly-robust estimator for offline policy evaluation, and validate against a genuine online experiment before full rollout |
| A LinUCB-based system's exploration bonus stays large indefinitely for a specific arm despite substantial traffic | `lambda` regularization in the ridge estimate may be set too high relative to actual data volume, keeping the confidence region artificially wide, or the arm's context distribution is genuinely high-dimensional/sparse relative to observed samples | Re-tune `lambda` against held-out validation, or apply dimensionality reduction to the context features feeding that arm's ridge regression if genuine data sparsity in high dimensions is the root cause |

---

## Tradeoffs & when NOT to use it

- **Don't use a bandit algorithm when you need a rigorous, statistically well-powered comparison between a small, fixed number of variants for a one-time decision (e.g., "should we ship variant A or B permanently").** A bandit continuously reallocates traffic based on accumulating evidence, which makes classical significance testing and confidence intervals on the *final* comparison more complicated to interpret correctly than a standard fixed-horizon A/B test explicitly designed for that purpose — use a bandit when the decision is ongoing/continuous (which of many options to serve *right now*, repeatedly), not when it's a one-shot ship/no-ship call.
- **Don't use ε-greedy in a new production system when Thompson sampling or UCB are equally available.** ε-greedy's linear regret and need for manual `epsilon` tuning (or a hand-designed decay schedule) make it strictly dominated by either alternative for most practical purposes — its main remaining justification is simplicity of explanation to non-technical stakeholders, not technical merit.
- **Don't deploy an exploring bandit without an explicit safety floor or exclusion list for catastrophically bad options**, especially in domains where a bad outcome (a wildly wrong price, an offensive recommendation) has real cost beyond lost reward — pure bandit theory optimizes cumulative regret, which doesn't distinguish "moderately suboptimal" from "unacceptable," and production systems need that distinction enforced explicitly, outside the bandit's own logic.
- **Don't use a linear contextual bandit (LinUCB) when the true reward function is known or strongly suspected to be highly nonlinear in context, without validating the linear assumption first.** A meaningfully nonlinear true relationship will cause LinUCB's ridge-regression reward model to systematically misestimate expected reward in ways its own confidence bonus doesn't fully correct for — validate with a simpler offline model comparison (does a nonlinear model meaningfully outperform ridge on logged data) before committing to the added complexity of a nonlinear contextual bandit variant.

---

## Interview questions

### Q1 — Why does ε-greedy have linear regret in the worst case (fixed epsilon), and what's the actual definition of regret being violated?
**Testing:** the precise mechanism, not just "epsilon-greedy explores too much."
**Answer:** Cumulative regret is `sum_t (reward_of_best_arm - reward_of_chosen_arm_at_t)`. With a fixed `epsilon`, a constant fraction `epsilon` of *every* round (not just early rounds) is spent choosing uniformly at random among all arms, including arms that have already accumulated enough evidence to be confidently known as suboptimal — since a constant fraction of rounds keep incurring a nonzero expected regret contribution (from occasionally picking a bad arm) forever, the cumulative sum grows linearly in the number of rounds `t`, rather than the logarithmic growth UCB/Thompson sampling achieve by tapering exploration as evidence accumulates.
**Follow-up trap:** *"Can a decaying epsilon (e.g., epsilon_t = c/t) fix this, and if so, what's the remaining downside?"* — yes, a properly decaying epsilon schedule can achieve logarithmic regret matching UCB/Thompson sampling asymptotically, but this reintroduces a hand-tuning problem (the decay rate `c` and schedule shape) that UCB and Thompson sampling largely avoid — in practice, a poorly-chosen decay schedule can decay too fast (premature convergence to a possibly-wrong arm) or too slow (regret closer to the fixed-epsilon case for a long transient period), so "just decay epsilon" isn't a free fix.

### Q2 — Derive UCB1's confidence bonus term and explain the statistical principle ("optimism under uncertainty") it embodies.
**Testing:** connecting the bonus formula to its actual concentration-inequality justification, not treating it as an arbitrary formula.
**Answer:** The bonus `sqrt(2*ln(t)/n_i)` comes from a Chernoff-Hoeffding concentration bound, which guarantees that with high probability (increasing with `t`), the true mean reward of arm `i` lies within this bonus of its observed sample mean — so `mean_reward_i + bonus_i` is, with high probability, an upper bound on arm `i`'s true mean. "Optimism under uncertainty" means: act as if every arm is as good as its plausible best case (the upper confidence bound), which automatically favors under-sampled arms (large `bonus_i` since `n_i` is small) enough to explore them, while well-sampled arms' bonuses shrink toward zero, converging the algorithm to pure exploitation of the actually-best arm as evidence accumulates.
**Follow-up trap:** *"Why does the bonus include ln(t) in the numerator rather than just depending on n_i alone?"* — the `ln(t)` term ensures the confidence bound tightens appropriately as the *total* number of rounds grows (accounting for the fact that with more total rounds, you're implicitly making more simultaneous confidence-interval claims across all arms, which requires slightly wider individual bounds to maintain the same overall confidence level) — without it, the algorithm's exploration guarantee wouldn't hold uniformly across all arms as the total horizon grows, a subtlety that matters for the formal regret bound proof even though it's a secondary effect compared to the `n_i` term's dominant role.

### Q3 — Walk through exactly how Thompson sampling updates its belief about a Bernoulli arm's success rate, and explain why the Beta distribution specifically is used.
**Testing:** the conjugate-prior mechanism, precisely, not just "it uses Bayesian updating."
**Answer:** Each arm's belief starts as `Beta(1,1)` (uniform over [0,1], representing no prior information). After observing a success, the posterior updates to `Beta(alpha+1, beta)`; after a failure, `Beta(alpha, beta+1)` — this is the closed-form conjugate update for a Beta prior with Bernoulli/Binomial likelihood, requiring no numerical integration or approximation at all, which is exactly why Beta-Bernoulli is the standard textbook and production case for Thompson sampling on click-through-rate-style problems. At each round, sampling one value from each arm's current Beta posterior and picking the highest sample naturally explores arms with wide (uncertain) posteriors more than arms with narrow (well-estimated) ones, without any separate hand-tuned exploration parameter.
**Follow-up trap:** *"What would you need to do differently if the reward were continuous (e.g., revenue per conversion) rather than binary click/no-click?"* — you'd need a different conjugate prior-likelihood pair matching the reward's actual distribution (e.g., a Normal-Inverse-Gamma prior for Gaussian rewards with unknown mean and variance), or fall back to a non-conjugate Bayesian update requiring approximate inference (e.g., Markov chain Monte Carlo or variational approximation) if no clean conjugate pair exists for the assumed reward distribution — Thompson sampling's simplicity in the Beta-Bernoulli case doesn't automatically generalize to every reward type without additional work.

### Q4 — What's the core structural difference between UCB/Thompson sampling and LinUCB, and why does that difference matter for a recommendation system with millions of distinct users?
**Testing:** the context-dependence of LinUCB's reward model and why treating every context as an independent bandit instance is impractical.
**Answer:** Plain UCB/Thompson sampling treats each arm's reward as a single, context-independent quantity to be estimated (one mean/posterior per arm, full stop). LinUCB models each arm's expected reward as a *function of context* (`theta_i . x`), sharing statistical strength across all rounds where similar contexts were observed, rather than requiring a completely separate bandit instance (with its own independent learning curve) per distinct context. For a system with millions of distinct users, treating each user as their own independent bandit instance would mean nearly zero data per instance and essentially no ability to generalize — LinUCB's linear reward model lets observations from one user inform predictions for other users with similar context/features, which is the only way a bandit approach is practically viable at that scale.
**Follow-up trap:** *"If context includes something like a raw user ID (a categorical with millions of distinct values, effectively no shared structure across users), does LinUCB's context-sharing advantage still hold?"* — no, not for that specific feature; a raw high-cardinality ID with no inherent structure provides LinUCB's linear model nothing to generalize from (it would need to see that exact ID before learning anything about it), exactly like a one-hot-encoded ID feature offers no information transfer between unseen category values in the classic-models module's Naive Bayes/linear-model discussion — the benefit of LinUCB's context-sharing specifically requires genuinely informative, generalizable features (demographics, behavior summaries, embeddings), not raw identity, which is a common practical mistake when first setting up a contextual bandit's feature set.

### Q5 — Why is cumulative regret, rather than "did the algorithm eventually find the best arm," the correct way to evaluate a bandit algorithm?
**Testing:** understanding that regret accounts for the cost of exploration itself, not just eventual correctness.
**Answer:** Two algorithms can both eventually converge to correctly identifying the best arm, but one might take far longer or waste far more reward during the exploration process to get there — cumulative regret specifically sums up the reward lost at every single round relative to an oracle that always played the best arm, so it directly penalizes slow or wasteful exploration, not just eventual correctness. An algorithm that "eventually learns the right answer" after an enormous amount of wasted exploration has high regret despite technically succeeding at the identification task, which is exactly the failure mode a regret-based evaluation is designed to catch and a pure "did it find the right answer eventually" evaluation would miss entirely.
**Follow-up trap:** *"Is there a scenario where minimizing cumulative regret is NOT actually the right objective for a real production bandit?"* — yes; if the actual business goal is "identify the single best arm as confidently and quickly as possible, and it's acceptable to sacrifice reward during a dedicated exploration phase to get there fastest" (the "best arm identification" or "pure exploration" bandit variant, distinct from cumulative-regret-minimizing bandits), a different algorithm family optimized specifically for that objective (not UCB/Thompson sampling, which are tuned for regret minimization) would be more appropriate — conflating "minimize regret while running" with "identify the best arm as fast as possible, cost of interim reward be damned" is a real, consequential mismatch between objective and algorithm choice.

### Q6 — A teammate proposes running a standard fixed-horizon A/B test instead of a bandit for a continuously-running product ranking decision, arguing it's simpler and more statistically rigorous. When are they right, and when are they wrong?
**Testing:** the genuine tradeoff between A/B testing and bandits, not a reflexive "bandits are always better" answer.
**Answer:** They're right if the actual decision is a one-time, permanent choice between a small number of fixed variants (ship variant A or B, forever) — a fixed-horizon A/B test's statistical framework (power analysis, significance testing, confidence intervals) is specifically designed for exactly this kind of one-shot decision and is more straightforward to interpret rigorously than a continuously-adapting bandit's implicit online decision-making. They're wrong if the actual scenario is an ongoing, repeated decision (which of many options to serve *right now*, over and over, with the option set or context potentially changing over time) — a bandit's core advantage is adapting the allocation continuously as evidence accumulates, avoiding the "waste traffic on a clearly-losing variant for the entire fixed test duration" cost inherent to a static A/B split, which matters when the volume and continuity of the decision make that wasted traffic a real, ongoing cost rather than a bounded one-time cost.
**Follow-up trap:** *"Can you combine both approaches, and what would that look like?"* — yes; a common pattern is using a bandit to continuously optimize among currently-known options in production, while periodically running a fixed-horizon, bandit-free A/B test specifically to rigorously validate a genuinely new, structurally different candidate before adding it to the bandit's live option set — this combines the bandit's ongoing-decision efficiency with the A/B test's more rigorous one-shot validation for major new candidates, rather than treating the two as mutually exclusive choices.

### Q7 — Why does an exploring bandit necessarily, sometimes, serve a suboptimal option to a real user, and what production safeguard addresses the resulting risk?
**Testing:** recognizing this as an inherent property of exploration, not a bug, and knowing the standard mitigation.
**Answer:** By definition, any bandit algorithm that explores (which all of UCB, Thompson sampling, ε-greedy, and LinUCB do, to varying degrees) must, at least occasionally, choose an arm other than the currently-best-known one specifically to gather more information about it — if it never did this, it would be pure exploitation, with no mechanism to correct an early wrong impression about which arm is actually best. This means some fraction of real users will, by design, be served an option the algorithm currently believes is not the best, which is an inherent cost of the exploration the algorithm needs to converge correctly, not a malfunction. Production safeguard: an explicit safety floor (options below some offline-vetted minimum quality threshold are excluded from the live exploration set entirely, regardless of what the bandit's own uncertainty estimate says) or a hard cap on how large a fraction of traffic exploration is allowed to consume.
**Follow-up trap:** *"Wouldn't imposing a hard safety floor bias the bandit's regret calculation, or is that an acceptable tradeoff?"* — it does technically change the regret being measured (the bandit is no longer minimizing regret over the *full* unrestricted option space, only over the pre-vetted safe subset), but this is a deliberate, acceptable, and often necessary tradeoff in production — pure regret-minimization theory doesn't distinguish "moderately suboptimal" from "unacceptable, high real-world cost," and production systems must enforce that distinction explicitly via a safety floor rather than trusting the bandit to learn to avoid catastrophic options fast enough purely from its own reward signal.

### Q8 — What specifically goes wrong if you try to evaluate a new bandit policy purely by averaging the rewards logged under an old, different policy for the actions the new policy would have chosen?
**Testing:** off-policy evaluation bias, connecting back to the recsys module's selection-bias discussion in a bandit-specific form.
**Answer:** The old policy's logs only contain reward observations for the actions the old policy actually chose to take, with a frequency proportional to how often the old policy chose each action in each context — naively averaging logged rewards restricted to "rounds where the old policy happened to choose the same action the new policy would choose" implicitly conditions on a biased subsample (contexts/rounds where the two policies happen to agree), which doesn't give an unbiased estimate of how the new policy would perform across the *full* range of contexts and actions it would actually select in live deployment, including many it would choose that the old policy rarely or never did.
**Follow-up trap:** *"What does inverse propensity scoring do differently, and what does it require to be valid?"* — it reweights each logged reward by the inverse of the probability the *old* policy assigned to the action actually taken in that context, correcting for the old policy's own action-selection frequencies so the reweighted average becomes an unbiased estimate of the new policy's expected reward — but this requires knowing (or reliably estimating) the old policy's exact action-selection probabilities per context, which isn't always available for older or undocumented systems, and the resulting estimator's variance grows large when the old and new policies disagree substantially on which actions to take, a real practical limitation of the technique.

### Q9 — Design question: you're asked to add a contextual bandit to an existing recommendation ranking system that currently uses a static, non-adaptive ranking model. What would you check before concluding a bandit approach is actually the right addition?
**Testing:** staff-level judgment about when bandit complexity is actually justified versus when it's premature.
**Answer:** First, confirm there's a genuine, ongoing decision with real uncertainty to resolve — if the current static model's ranking is already well-validated and stable, and the actual open question is something like "which of several new, previously-untested ranking strategies should we adopt," that's more naturally a fixed-horizon A/B test than a bandit problem. Second, check whether sufficient context features exist and are informative enough to make a *contextual* bandit worthwhile over a simpler non-contextual one — if there isn't genuinely differentiable context-dependent behavior to exploit, the added complexity of LinUCB over plain UCB/Thompson sampling isn't earning its keep. Third, verify the organization has the operational maturity to monitor an actively-exploring system safely (safety floors, per-segment regret monitoring, off-policy evaluation tooling) before deploying something that will, by design, occasionally serve suboptimal recommendations to real users.
**Follow-up trap:** *"If the team doesn't yet have off-policy evaluation tooling built, does that disqualify a bandit rollout entirely?"* — not necessarily; a bandit can still be deployed responsibly with a conservative exploration budget and reliance on straightforward online monitoring (tracking cumulative reward/regret proxies directly rather than sophisticated off-policy estimation) for an initial rollout, while off-policy evaluation tooling is built out in parallel for evaluating *future* policy changes more efficiently — the absence of mature tooling is a reason for a more conservative, closely-monitored initial rollout, not necessarily a blocker on starting at all, provided the safety floor and monitoring basics are in place.

### Q10 — Why might a linear contextual bandit (LinUCB) systematically underperform in a setting where the true relationship between context and reward is strongly nonlinear, and how would you detect this before it causes a production problem?
**Testing:** recognizing the linear-model assumption's limitation and connecting to earlier modules' bias discussion.
**Answer:** LinUCB's reward model `theta_i . x` can only represent linear relationships between context and expected reward — if the true relationship has a strong nonlinear or interaction structure (context feature A only matters in combination with feature B in a way a linear model can't represent without hand-engineered interaction terms), the ridge regression estimate will have systematic bias no amount of additional data resolves, exactly the "high bias" regime from the regularization module's learning-curve discussion, just applied to the bandit's reward model rather than a standalone supervised model. Detect this by comparing, on logged historical data, how well a more flexible nonlinear model (a shallow tree ensemble, or a neural reward model) predicts observed rewards versus the linear ridge model — a large, persistent gap that doesn't close with more data is evidence the linear assumption is the bottleneck, not insufficient data or tuning.
**Follow-up trap:** *"If you find this bias, is switching immediately to a neural contextual bandit the right fix?"* — not automatically; first check whether the nonlinearity can be captured with a modest number of hand-engineered interaction/nonlinear features fed into the same LinUCB framework (much simpler to reason about, tune, and maintain than a full nonlinear bandit), which is often sufficient — only reach for a genuinely nonlinear contextual bandit model when the interaction structure is too complex or too poorly understood to hand-engineer effectively, mirroring the same "cheap feature engineering before a more complex model" judgment call from the recsys module's LambdaMART-versus-deep-ranker discussion.

---

## Red flags that fail you

- Cannot explain why ε-greedy has linear regret with a fixed epsilon, or thinks it's simply "less good" without the mechanism.
- Cannot derive or explain UCB's confidence bonus as coming from a concentration inequality, or describes it as an arbitrary formula.
- Doesn't know Thompson sampling uses posterior *sampling* (not the posterior mean) to select an arm, or can't explain why sampling specifically achieves exploration.
- Cannot explain the structural difference between a context-blind bandit and a contextual bandit (LinUCB), or why raw high-cardinality IDs don't help LinUCB generalize.
- Evaluates a bandit purely on "did it eventually find the best arm" without understanding cumulative regret as the correct objective.
- Has no answer for the safety-floor/exploration-risk question — treats exploration as cost-free.

---

## Cheat card

```
CORE TENSION: exploit (best observed mean) vs explore (reduce uncertainty) -- every
  algorithm below makes exploration proportional to genuine uncertainty differently

EPSILON-GREEDY: 1-eps exploit, eps uniform-random explore, FOREVER (fixed eps)
  -> LINEAR regret (wastes a constant fraction of ALL future rounds, even post-convergence)
  decaying eps_t=c/t can reach log regret but reintroduces hand-tuning

UCB1: argmax(mean_i + sqrt(2*ln(t)/n_i))  <- Chernoff-Hoeffding upper confidence bound
  bonus SHRINKS as n_i grows -> auto-tapers exploration -> O(log t) regret
  "optimism under uncertainty": act as if every arm is as good as its plausible best case

THOMPSON SAMPLING (Beta-Bernoulli): prior Beta(1,1), update Beta(a+1,b) on success /
  Beta(a,b+1) on failure (closed-form conjugate). SAMPLE one value per arm's posterior,
  pick highest SAMPLE (not highest mean) -- wide posterior -> more exploration, automatically
  matches/beats UCB empirically, NO hand-tuned exploration constant needed

LINUCB (contextual): per-arm ridge regression theta_i_hat=(D_i^T D_i+lambda*I)^-1 D_i^T c_i
  pick argmax(x.theta_i_hat + alpha*sqrt(x^T (D_i^TD_i+lambda*I)^-1 x))
  bonus grows in UNDER-EXPLORED directions of context space -- personalizes explore/exploit
  needs INFORMATIVE features (demographics/behavior), raw high-cardinality ID gives no
  cross-context generalization (same lesson as one-hot IDs elsewhere in this track)

REGRET = sum_t(best_arm_reward - chosen_arm_reward) -- the CORRECT eval metric, penalizes
  slow/wasteful exploration, not just "did it eventually find the best arm"

PRODUCTION SAFEGUARDS: exploration is NOT free -- some real users get a suboptimal option
  by design. Use a safety floor (exclude catastrophic options from exploration set) or
  traffic cap on exploration. Off-policy eval: inverse propensity scoring reweights logged
  rewards by 1/P(old policy chose this action) -- always confirm with a real online test.

BANDIT vs FIXED A/B TEST: bandit for ONGOING/repeated decisions (adapts allocation
  continuously); fixed A/B test for a ONE-TIME permanent ship/no-ship choice between
  a small set of variants -- can combine: bandit live, periodic A/B test for new candidates
```

## Sources

- [Some Aspects of the Sequential Design of Experiments — Robbins (1952)](https://projecteuclid.org/euclid.bams/1183517370) — accessed 2026-08-03
- [Asymptotically Efficient Adaptive Allocation Rules — Lai & Robbins, Advances in Applied Mathematics (1985)](https://www.sciencedirect.com/science/article/pii/0196885885900028) — accessed 2026-08-03
- [Finite-time Analysis of the Multiarmed Bandit Problem (UCB1) — Auer, Cesa-Bianchi, Fischer, Machine Learning (2002)](https://link.springer.com/article/10.1023/A:1013689704352) — accessed 2026-08-03
- [A Contextual-Bandit Approach to Personalized News Article Recommendation (LinUCB) — Li et al., WWW (2010)](https://arxiv.org/abs/1003.0146) — accessed 2026-08-03
- [An Empirical Evaluation of Thompson Sampling — Chapelle & Li, NeurIPS (2011)](https://papers.nips.cc/paper/2011/hash/e53a0a2978c28872a4505bdb51db06dc-Abstract.html) — accessed 2026-08-03

## Changelog
- 2026-08-03 — created
