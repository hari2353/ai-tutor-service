# PPO & TRPO: Trust Regions, Clipped Objectives, GAE — the Workhorse of RLHF

> **Track:** T31 Reinforcement Learning · **Time:** 3h · **Prereqs:** T31-policy-gradient, T31-mdp · **Updated:** 2026-08-03
> **Module id:** `T31-ppo` · **Tags:** deep-rl, critical, rlhf

## The 30-second version

Vanilla policy gradient (`T31-policy-gradient`) has no notion of step size safety: because the policy determines the data you collect next, a single overlarge update can move the policy into a region where the surrogate objective no longer approximates the true objective, and — unlike supervised learning — there's no way to just retry with a smaller learning rate after the fact, because the bad policy has already poisoned the next batch of data. TRPO (Schulman et al., 2015) fixes this by solving a constrained optimization problem directly: maximize a surrogate objective subject to a hard KL-divergence constraint between old and new policy, using a natural-gradient step (conjugate gradient, avoiding an explicit Fisher-information-matrix inversion) plus a backtracking line search — provably stable, but second-order and expensive to implement correctly. PPO (Schulman et al., 2017) gets nearly the same stability with plain first-order SGD by replacing the hard KL constraint with a **clipped surrogate objective**, `min(r(\theta)A, \text{clip}(r(\theta),1-\epsilon,1+\epsilon)A)`, where `r(\theta)=\pi_\theta(a|s)/\pi_{\theta_{\text{old}}}(a|s)` — the clip removes the optimizer's incentive to push the probability ratio far from 1 in a single step, without ever computing a KL divergence or its gradient. **Generalized Advantage Estimation (GAE)** supplies the advantage signal both feed on, and is exactly TD(λ)'s bias-variance dial (`T31-monte-carlo-td`) applied to advantages instead of values: `\lambda=0` gives the low-variance, high-bias one-step `\delta_t`, `\lambda\to1` recovers the full Monte Carlo advantage. Production defaults are narrow and worth memorizing: clip `\epsilon\approx0.2`, GAE `\lambda\approx0.95`, `\gamma\approx0.99` (or close to 1 for short-horizon RLHF), 3-10 PPO epochs per collected batch.

## Why this gets asked

PPO is the algorithm underneath the original InstructGPT RLHF pipeline and remains a default RL fine-tuning method for LLMs and continuous control alike, so interviewers use it to separate "I called `PPOTrainer.step()`" from "I understand why the clip exists." The real failure mode being probed: engineers who treat PPO's clip as an arbitrary regularization trick rather than a first-order approximation to a real constrained-optimization problem (TRPO's), and who therefore can't reason about why a training run diverges when the clip alone isn't enough (a real, common RLHF failure requiring an *additional* explicit KL penalty against the reference model, not covered by the clip at all). Anyone who has actually run PPO at scale has watched a policy collapse from a batch of correlated, high-advantage samples slipping past the clip's local per-step guarantee — because the clip bounds one update's *ratio* excursion, not cumulative drift across many updates.

---

## Lineage: past → present → future

**What came before.** Vanilla policy gradient and one-step actor-critic (`T31-policy-gradient`) update `\theta` in the direction of `\mathbb{E}[\nabla_\theta\log\pi_\theta(a|s)A(s,a)]` with no constraint on how far a single gradient step actually moves the policy in *behavior* space — only in parameter space, which is not the same thing for a neural network policy (a small parameter change can correspond to a large behavioral change in poorly-conditioned regions, and vice versa). The pain this caused in practice: training runs that looked fine for many iterations, then collapsed irrecoverably after one bad update, because the new (bad) policy is what collects the *next* batch of data — there's no "undo" the way there is in supervised learning, where you can lower the learning rate and retry on the same fixed dataset. Kakade & Langford's performance-difference lemma (2002) gave the first formal language for exactly how far a policy update's benefit is a *local* approximation, valid only near the old policy, setting up TRPO's constraint as a direct, principled response rather than a heuristic.

**Where it stands now.** PPO (2017) is the dominant practical choice specifically because it trades TRPO's exact, provable per-step monotonic-improvement guarantee for an approximate one that's dramatically simpler to implement — first-order SGD instead of conjugate-gradient Hessian-vector products and a line search — and in practice performs comparably or better across most benchmarks. It's the RL algorithm named explicitly in OpenAI's InstructGPT paper (Ouyang et al., 2022) that established the modern RLHF recipe, and PPO-based RLHF remains in production use at multiple frontier labs as of 2026, though it now sits alongside critic-free alternatives — GRPO (`T31-rl-for-llms`) specifically removes PPO's learned value function, a direct response to critic cost at LLM parameter scale — and DPO, which removes the RL loop entirely. The live disagreement: PPO's clip alone is known to be an imperfect proxy for a real trust region — empirically, the clipped ratio can still drift substantially over many updates even though each individual step looks bounded — which is why most production RLHF implementations add an *explicit* KL penalty term against a fixed reference policy on top of the clip, a different mechanism solving a different problem (cumulative drift vs. single-step size) that a purist "PPO is just the clip" description misses.

**Where it's heading.** High confidence: the clipped-surrogate-plus-GAE recipe remains the default wherever a critic is affordable and stable on-policy updates matter (robotics, game-playing agents, most classic deep RL benchmarks) — nothing about frontier-model scale changes the underlying single-batch-update instability problem PPO addresses. Medium confidence: for LLM-scale RL specifically, critic-free methods (GRPO and its relatives) continue gaining share because a separate value network at LLM parameter count is a real, large cost that doesn't exist the same way in classic control — this is a scale-driven shift, not a claim that PPO's clipping mechanism itself is flawed. Speculative: whether second-order trust-region methods (TRPO's original approach) see a resurgence given better Hessian-vector-product hardware support is an open, largely unrealized possibility as of 2026 — PPO's simplicity advantage has held for nearly a decade.

---

## Mental model

```
UNCONSTRAINED POLICY GRADIENT STEP:

  J(theta)
    │                    ⚠ true objective surface (unknown, only locally approximated)
    │        ___
    │       /   \___                  surrogate L(theta) is only a good
    │      /        \___              approximation of J(theta) NEAR theta_old
    │     / theta_old   \________
    │    /                       \________  <- big step lands here: surrogate
    │   /                                  \    said "better," true objective
    │__/____________________________________\_ says much WORSE. No undo --
       theta_old      big step ->  theta_new    theta_new now collects the
                                                  next batch of (bad) data.

TRUST REGION (TRPO): constrain KL(pi_old, pi_new) <= delta so the step
  never leaves the region where the surrogate approximation is trustworthy.
  Solved via natural gradient (2nd order, Fisher info) + line search.

PPO'S CLIP: same GOAL, cheaper mechanism -- no KL computed at all.
  ratio r(theta) = pi_theta(a|s) / pi_old(a|s)   (how much MORE likely
                                                    is this action now)
  L^CLIP = E[ min( r*A, clip(r, 1-eps, 1+eps)*A ) ]

  A > 0 (good action): pushing r above 1+eps stops helping the objective
  A < 0 (bad action):  pushing r below 1-eps stops helping the objective
  -> gradient saturates to ZERO past the clip boundary in the "helpful"
     direction -- the optimizer has no incentive to overstep, first-order,
     no KL, no Hessian.
```

The trust-region story in one sentence: your surrogate objective is a first-order (or, for TRPO, second-order-constrained) local model of the true objective, and it's only trustworthy in a neighborhood of the policy you collected data with — everything in this module is a different mechanism for keeping the optimizer inside that neighborhood.

---

## How it actually works

### Why unconstrained policy gradient steps are destructive, derived

Recall `\nabla_\theta J(\theta) = \mathbb{E}_{\pi_\theta}[\nabla_\theta\log\pi_\theta(a|s)Q^\pi(s,a)]` from `T31-policy-gradient`. This gradient is estimated from data collected under the *current* policy `\pi_{\theta_{\text{old}}}`, but the objective you actually care about, `J(\theta_{\text{new}})`, depends on the state distribution the *new* policy would induce, `d^{\pi_{\theta_{\text{new}}}}`, which you have no samples from. The **performance difference lemma** (Kakade & Langford, 2002) makes this gap precise:

$$J(\pi') - J(\pi) = \mathbb{E}_{s\sim d^{\pi'},\, a\sim\pi'}\left[A^\pi(s,a)\right]$$

The true improvement of a new policy `\pi'` over the old `\pi` is an expectation under `\pi'`'s *own* state distribution `d^{\pi'}` — the one you don't have samples from. The tractable surrogate everyone actually optimizes substitutes the *old* policy's state distribution as a stand-in:

$$L_\pi(\pi') = \mathbb{E}_{s\sim d^\pi,\, a\sim\pi'}\left[A^\pi(s,a)\right]$$

This substitution is only a good approximation to the true `J(\pi')-J(\pi)` when `\pi'` is close to `\pi` — because only then is `d^{\pi'}\approx d^\pi`. TRPO's paper proves a formal bound quantifying exactly how wrong the substitution can be:

$$J(\pi') \ge L_\pi(\pi') - C\cdot\max_s D_{KL}\!\left(\pi(\cdot|s)\,\|\,\pi'(\cdot|s)\right), \qquad C = \frac{4\epsilon_{\max}\gamma}{(1-\gamma)^2}$$

where `\epsilon_{\max}=\max_{s,a}|A^\pi(s,a)|`. This is the formal statement of "trust region": the true objective is guaranteed to be at least as good as the surrogate's estimate *minus a penalty proportional to how much the policy changed*, measured in KL divergence. An unconstrained gradient step that maximizes `L_\pi(\pi')` alone, with no penalty term, can happily walk into a region where the guaranteed lower bound is vacuous — the surrogate says "better" while the true objective is actually much worse, and because `\pi'` now collects the next batch, there's no recovering by simply retrying with a smaller step on the *same* data (there is no fixed dataset the way there is in supervised learning).

### TRPO: the constrained optimization, solved

TRPO turns the bound above into a direct, practical algorithm: maximize the surrogate subject to an explicit trust-region constraint rather than an unconstrained penalty (a constraint is easier to tune reliably than the constant `C`, which is a very loose, worst-case bound in practice):

$$\max_\theta L_{\theta_{\text{old}}}(\theta) \quad \text{s.t.} \quad \bar{D}_{KL}(\theta_{\text{old}},\theta) \le \delta$$

with `\delta\approx0.01` a typical value from the original paper. Solving this exactly per step is intractable (the constraint is over the whole state distribution), so TRPO linearizes the objective and quadratically approximates the KL constraint using the **Fisher information matrix** `F` (the local curvature of KL divergence around `\theta_{\text{old}}`):

$$\max_d\; g^Td \quad \text{s.t.} \quad \tfrac{1}{2}d^TFd\le\delta$$

Lagrangian stationarity gives the **natural gradient** step direction: `d^* = \sqrt{\frac{2\delta}{g^TF^{-1}g}}F^{-1}g`. Explicitly forming and inverting `F` (size = parameter count squared) is infeasible for a deep network, so TRPO computes `F^{-1}g` via **conjugate gradient**, which only requires Fisher-vector products (computable without materializing `F`), and then runs a **backtracking line search** along `d^*` to find the largest step that both satisfies the KL constraint *and* actually improves the surrogate objective — necessary because the quadratic approximation of KL is itself only locally accurate, and an overlarge natural-gradient step can violate the true (non-quadratic) constraint.

### PPO's clipped surrogate objective, derived explicitly

PPO keeps the constrained-optimization *goal* — don't let the policy move too far in one step — but abandons the second-order machinery entirely. Define the probability ratio:

$$r(\theta) = \frac{\pi_\theta(a|s)}{\pi_{\theta_{\text{old}}}(a|s)}$$

`r(\theta)=1` at the start of every update (before any gradient step, `\theta=\theta_{\text{old}}`). The **unclipped** surrogate `r(\theta)A` is exactly `L_{\theta_{\text{old}}}(\theta)` from above (importance-sampling-corrected, `T31-policy-gradient` Q8), and maximizing it with no constraint reproduces the destructive-step problem. PPO's fix:

$$L^{\text{CLIP}}(\theta) = \mathbb{E}_t\left[\min\Big(r_t(\theta)A_t,\ \text{clip}\big(r_t(\theta), 1-\epsilon, 1+\epsilon\big)A_t\Big)\right]$$

**Work the mechanism through numerically.** Take `A_t=+1` (a good action), `\epsilon=0.2`, and suppose an unclipped gradient step would push `r_t(\theta)` up to `1.5`. The clipped term is `\text{clip}(1.5,0.8,1.2)\cdot1=1.2`; the unclipped term is `1.5`. The objective takes `\min(1.5,1.2)=1.2` — the **clipped** branch. Once `r_t(\theta)` exceeds `1+\epsilon`, the clip function is *constant* in that region (`\text{clip}(r,\cdot,\cdot)=1+\epsilon` regardless of how much larger `r` gets), so its gradient with respect to `\theta` is exactly zero there — and because the objective takes the min (the more pessimistic of the two terms whenever `A_t>0` and `r_t` has overshot), the optimizer sees **zero gradient signal** to keep pushing `r_t` any higher. The symmetric case, `A_t<0` (a bad action) and `r_t` shrinking below `1-\epsilon`: the clipped term becomes constant at `(1-\epsilon)A_t`, and by an identical min-selection argument the gradient vanishes once `r_t` drops below `1-\epsilon`. In both cases, the effect is the same: **the optimizer has no incentive to push the ratio further than `\epsilon` away from 1 in the direction that would locally look "helpful,"** which is precisely how TRPO's trust region behaved, achieved here with zero KL computation, zero Hessian-vector products, and an ordinary first-order optimizer.

**Why the `min`, specifically, and not just the clipped term alone.** Taking the `min` of the clipped and unclipped terms makes `L^{\text{CLIP}}` a **pessimistic lower bound** on the unclipped surrogate everywhere, never an optimistic one — if the clip alone (without the min) were used, there exist edge cases (the ratio moving in the direction that *decreases* the objective, e.g. `A_t>0` but `r_t<1-\epsilon` from an unrelated earlier update) where clipping without the min-comparison could actually give a *more* optimistic estimate than the true surrogate, defeating the purpose. The `\min` guarantees `L^{\text{CLIP}}\le L^{\text{CLIP,unclipped}}` in every case, which is the property that actually prevents over-optimization.

**What the clip does *not* do.** It bounds a single update's ratio excursion — it says nothing about cumulative drift across many sequential updates, each individually satisfying the clip. This is the real, empirically observed gap that motivates adding an **explicit KL penalty** against a fixed reference policy in production RLHF pipelines (`T31-rl-for-llms`): `\mathcal{L} = L^{\text{CLIP}}(\theta) - \beta\, D_{KL}(\pi_\theta\|\pi_{\text{ref}})`, a different mechanism for a different failure mode (long-horizon distributional drift from the SFT/reference model, not single-step destructive updates) — conflating the two is a common, checkable interview mistake.

### Generalized Advantage Estimation (GAE), derived from the TD(λ) family

`T31-policy-gradient` established the one-step advantage estimate `\delta_t = r_{t+1}+\gamma V_\phi(s_{t+1})-V_\phi(s_t)` (low variance, biased by however wrong `V_\phi` currently is). Define the **n-step advantage estimator** by telescoping:

$$\hat{A}_t^{(n)} = \sum_{l=0}^{n-1}\gamma^l\delta_{t+l} = -V(s_t) + r_{t+1}+\gamma r_{t+2}+\cdots+\gamma^{n-1}r_{t+n}+\gamma^nV(s_{t+n})$$

(verify by expanding the sum of `\delta`'s: every intermediate `+\gamma^l V(s_{t+l})` from one term cancels the `-\gamma^{l}V(s_{t+l})` implicit in the next, leaving only the boundary terms — identical telescoping to TD(λ)'s value-estimator derivation in `T31-monte-carlo-td`). `n=1` recovers the single-step `\delta_t`; `n\to\infty` recovers the full Monte Carlo advantage `G_t - V(s_t)`. **GAE** is the exponentially-weighted average of every `n`-step estimator, with weight `(1-\lambda)\lambda^{n-1}` on the `n`-step term — exactly TD(λ)'s forward view applied to advantages instead of values:

$$\hat{A}_t^{\text{GAE}(\gamma,\lambda)} = (1-\lambda)\sum_{n=1}^\infty \lambda^{n-1}\hat{A}_t^{(n)} = \sum_{l=0}^\infty (\gamma\lambda)^l\,\delta_{t+l}$$

(the compact geometric-sum form on the right is the standard identity, derivable by substituting the n-step definitions into the weighted sum and re-collecting terms by power of `\gamma\lambda`). `\lambda=0` collapses this to `\delta_t` exactly (single-step, low variance, high bias); `\lambda=1` recovers the full Monte Carlo advantage (telescoping the infinite sum of `\delta`'s exactly cancels every `V(\cdot)` term except `-V(s_t)`, leaving `\sum_l\gamma^l r_{t+l+1} - V(s_t)`, unbiased, high variance). `\lambda` is a **continuous dial** between these extremes, tuned empirically rather than fixed at either end — the real reason PPO needs GAE rather than a fixed-`n` n-step advantage (`T31-policy-gradient` Q7): the right bias-variance point is problem- and training-stage-dependent, and a single fixed horizon can't track that.

### The real numbers

- **Clip `\epsilon`**: `0.2` is the standard default (original paper and virtually every production framework); typical explored range `0.1`-`0.3`.
- **GAE `\lambda`**: `0.95` is the common default; range `0.9`-`0.99` depending on episode length and reward density.
- **`\gamma`**: `0.99` for classic control/robotics; for RLHF (short, often single-response-length episodes with deterministic token transitions), `\gamma` is frequently set close to or at `1` since the effective horizon (`T31-mdp`'s `1/(1-\gamma)`) only needs to cover one response's length.
- **PPO epochs per batch**: `3`-`10` — multiple gradient epochs over the *same* collected rollout, made valid (approximately) by the clip bounding how stale the importance-sampling ratio is allowed to get across epochs (`T31-policy-gradient` Q8's importance-sampling answer, directly).
- **Rollout length before an update**: commonly `2048` timesteps per environment in classic MuJoCo-style benchmarks (Stable-Baselines3 defaults).
- **Value loss coefficient**: `~0.5`; **entropy bonus coefficient**: `~0.01` (prevents premature entropy collapse, `T31-policy-gradient`'s failure-mode table).
- **RLHF-specific KL target**: many production PPO-for-RLHF setups monitor the running KL divergence against the reference policy and **early-stop or adapt `\beta`** to keep it near a small target (commonly on the order of `0.01`-`0.02` nats per token in various published recipes) — separate from and in addition to the `\epsilon=0.2` clip.

---

## Build it from scratch

Extending the actor-critic scaffold from `T31-policy-gradient` into a minimal but complete PPO update: GAE computation, the clipped objective, and multiple epochs over one collected batch.

```python
# untested sketch -- minimal PPO update step, single environment, illustrative not optimized
import torch
import torch.nn.functional as F

def compute_gae(rewards, values, dones, last_value, gamma=0.99, lam=0.95):
    """rewards, values, dones: lists over one rollout. values has len(rewards) entries;
    last_value is V(s_{T}) bootstrapped for the final (possibly non-terminal) state."""
    T = len(rewards)
    advantages = [0.0] * T
    gae = 0.0
    values_ext = values + [last_value]
    for t in reversed(range(T)):
        mask = 1.0 - dones[t]                      # zero the bootstrap across episode boundaries
        delta = rewards[t] + gamma * values_ext[t + 1] * mask - values_ext[t]
        gae = delta + gamma * lam * mask * gae      # the (gamma*lambda)^l geometric recursion
        advantages[t] = gae
    returns = [a + v for a, v in zip(advantages, values)]   # target for the value function
    return advantages, returns

def ppo_update(policy, value_fn, optimizer, states, actions, old_log_probs,
               advantages, returns, clip_eps=0.2, epochs=4, vf_coef=0.5, ent_coef=0.01):
    advantages = (advantages - advantages.mean()) / (advantages.std() + 1e-8)  # normalize -- standard, stabilizes scale
    for _ in range(epochs):                          # MULTIPLE epochs over the SAME collected batch
        dist = policy(states)
        new_log_probs = dist.log_prob(actions)
        ratio = torch.exp(new_log_probs - old_log_probs)     # r(theta) = pi_new/pi_old, via log-space subtraction

        unclipped = ratio * advantages
        clipped = torch.clamp(ratio, 1 - clip_eps, 1 + clip_eps) * advantages
        policy_loss = -torch.min(unclipped, clipped).mean()   # negative: ascent -> minimize

        values_pred = value_fn(states)
        value_loss = F.mse_loss(values_pred, returns)

        entropy_bonus = dist.entropy().mean()          # encourages continued exploration, prevents collapse

        loss = policy_loss + vf_coef * value_loss - ent_coef * entropy_bonus
        optimizer.zero_grad()
        loss.backward()
        torch.nn.utils.clip_grad_norm_(policy.parameters(), max_norm=0.5)
        optimizer.step()
```

Two details are load-bearing, not stylistic: computing `ratio` via `torch.exp(new_log_probs - old_log_probs)` rather than `new_probs/old_probs` directly (numerically stable, and `old_log_probs` must be detached/stored from the rollout-collection pass, never recomputed with gradients flowing); and the GAE backward recursion `gae = delta + gamma*lam*mask*gae`, which computes the infinite geometric sum in the compact `\sum_l(\gamma\lambda)^l\delta_{t+l}` form in a single backward pass over the rollout, rather than materializing every n-step estimator separately.

---

## How it's done in production

| Layer | What you actually use | What it adds |
|---|---|---|
| Classic control/robotics RL | Stable-Baselines3 PPO, CleanRL, RLlib | Correct GAE implementation, vectorized environments, the numerical-stability details (advantage normalization, gradient clipping, orthogonal weight init) a from-scratch version easily gets subtly wrong |
| RLHF for LLMs | Hugging Face TRL's `PPOTrainer`, or bespoke internal pipelines at frontier labs | Adds the explicit KL penalty against a frozen reference/SFT model, reward-model integration, per-token vs per-sequence advantage handling |
| Trust-region-exact settings (rare) | TRPO reference implementations (e.g. `garage`, original Schulman code) | Used where the exact monotonic-improvement guarantee is worth the second-order implementation cost — largely research/benchmark contexts today |

### Failure modes

| Symptom | Cause | Fix |
|---|---|---|
| Policy performance suddenly collapses after many "stable-looking" updates | The clip bounds one update's ratio excursion, not cumulative drift across many updates — small, compounding, within-clip-bound drift eventually walks the policy somewhere it shouldn't be | Monitor cumulative KL divergence against a fixed reference policy, not just per-step clip statistics; add an explicit KL penalty term if using PPO for RLHF |
| Reward metric climbs steadily but generated outputs get visibly worse (RLHF) | Reward hacking against an imperfect reward model — the clip/KL machinery constrains policy *movement*, not reward-model correctness (`T31-rl-for-llms`) | Requires reward-model-side fixes (better reward model, KL penalty tuned tighter against reference), not a PPO hyperparameter change |
| Value loss dominates total loss, actor barely updates | `vf_coef` too high relative to policy loss magnitude, or a shared actor-critic trunk where the critic's gradient overwhelms the actor's | Lower `vf_coef`, or separate the networks if sharing a trunk |
| Training is very sensitive to the exact clip epsilon, small changes cause instability | Advantage estimates not normalized, or GAE `\lambda` mismatched to episode length/reward density | Always normalize advantages per-batch; tune `\lambda` before tuning `\epsilon` |
| Early in training, most `ratio` values sit exactly at the clip boundary (`1-\epsilon` or `1+\epsilon`) | The unclipped step would be very large — a sign the underlying policy gradient estimate itself is extremely noisy (small batch, high-variance advantage estimate) | Increase rollout batch size before collecting more gradient epochs on a noisy batch; check the critic isn't badly miscalibrated early on |

---

## Tradeoffs & when NOT to use it

- **Don't use PPO (or TRPO) when a value function/critic is prohibitively expensive relative to the policy** — at LLM parameter scale, a full second network purely for advantage estimation is a real, large cost, which is exactly the tradeoff GRPO (`T31-rl-for-llms`) is built around; PPO is the right default when the critic's cost is a minor addition (most classic control and robotics settings).
- **Don't reach for TRPO over PPO by default.** TRPO's exact monotonic-improvement guarantee is real, but the conjugate-gradient/Fisher-vector-product/line-search machinery is substantially harder to implement correctly and more expensive per update; PPO's approximate guarantee is empirically close enough across most benchmarks that TRPO is now mostly a research/pedagogical reference rather than a production default.
- **Don't treat the clip alone as sufficient regularization in RLHF.** It bounds single-step ratio excursions, not cumulative drift from a reference policy over the whole training run — production RLHF needs the explicit KL penalty as a separate mechanism.
- **PPO is on-policy** (`T31-policy-gradient`'s tradeoffs) — it can reuse a batch for a handful of epochs via the importance-sampling-bounded clip, but it fundamentally can't reuse old rollouts the way an off-policy method (DQN's replay buffer, SAC's, `T31-continuous-control`) can; if environment interaction is the real bottleneck and sample efficiency matters more than on-policy stability guarantees, an off-policy actor-critic method is usually the better fit.
- **Don't skip GAE's `\lambda` tuning and assume `\lambda=1` (full Monte Carlo) is "more correct."** It's unbiased but high-variance; the whole reason GAE exists is that intermediate `\lambda` values (`0.9`-`0.97`) usually train faster and more stably in practice, at the cost of some bias from an imperfect critic.

---

## Interview questions

### Q1 — Why can't you just use vanilla policy gradient with a small enough learning rate to avoid destructive updates?
**Testing:** whether the on-policy data-collection problem is understood, not just "small steps are safer."
**Answer:** The issue isn't step size in parameter space alone — it's that the policy generating the *next* batch of training data is whatever policy the last update produced. A destructive update doesn't just temporarily hurt performance the way an overlarge supervised-learning step does (recoverable by retrying on the same fixed dataset); it changes what data gets collected next, and there's no "undo" once the new, bad policy is out collecting bad trajectories. A smaller learning rate reduces the *frequency* of destructive updates but doesn't change the fundamental lack of a safety guarantee.
**Follow-up trap:** *"So does a hard KL constraint (TRPO) actually solve this completely?"* — no, it bounds each *individual* update's KL divergence from the previous policy, which per the performance-difference-lemma bound gives a guarantee on that one step, but doesn't prevent gradual, compounding drift across many updates each individually satisfying the constraint — the same gap that motivates an explicit reference-policy KL penalty in RLHF on top of PPO's clip.

### Q2 — Derive the performance difference lemma's role in motivating a trust region. What specifically breaks when the surrogate objective is optimized with no constraint?
**Answer:** `J(\pi')-J(\pi) = \mathbb{E}_{s\sim d^{\pi'},a\sim\pi'}[A^\pi(s,a)]`, an expectation under the *new* policy's state distribution, which you have no samples from. The tractable surrogate `L_\pi(\pi')` substitutes the *old* policy's state distribution `d^\pi` instead — valid only when `\pi'\approx\pi` so that `d^{\pi'}\approx d^\pi`. TRPO's bound, `J(\pi')\ge L_\pi(\pi') - C\max_sD_{KL}(\pi\|\pi')`, quantifies exactly how the substitution's error grows with how much the policy changed. Optimizing `L_\pi(\pi')` with no constraint can push `\pi'` far enough from `\pi` that this bound becomes vacuous — the surrogate reports improvement while the true objective can be much worse.
**Follow-up trap:** *"Is the constant `C` in that bound actually a tight, useful number to compute in practice?"* — no, it's a loose, worst-case bound (scales with `\max_{s,a}|A^\pi(s,a)|` and `\gamma/(1-\gamma)^2`), essentially never computed directly in practice — TRPO instead enforces a fixed, empirically-chosen KL budget `\delta` directly as a constraint, sidestepping the need to compute `C` at all.

### Q3 — Walk through TRPO's optimization procedure: what's approximated, and why is conjugate gradient used instead of directly inverting the Fisher information matrix?
**Answer:** TRPO linearizes the surrogate objective (`g^Td`) and quadratically approximates the KL constraint via the Fisher information matrix (`\frac{1}{2}d^TFd\le\delta`), giving a closed-form natural-gradient direction `d^*=\sqrt{2\delta/(g^TF^{-1}g)}\,F^{-1}g` by Lagrangian stationarity. Directly forming and inverting `F` costs `O(|\theta|^2)` to `O(|\theta|^3)`, infeasible for a deep network's parameter count; conjugate gradient computes `F^{-1}g` using only Fisher-vector products (`Fv` computable cheaply via automatic differentiation without ever materializing `F`), converging in relatively few iterations for well-conditioned problems.
**Follow-up trap:** *"After computing the conjugate-gradient step direction, why is a separate backtracking line search still needed?"* — the natural-gradient direction relies on a quadratic (local) approximation of the KL constraint, which is only accurate very close to `\theta_{\text{old}}`; a full-length step along `d^*` can overshoot and actually violate the true (non-quadratic) KL constraint or fail to improve the true surrogate — the line search shrinks the step until both the constraint and an actual objective improvement are verified directly, rather than trusted from the local approximation alone.

### Q4 — Derive PPO's clipped objective's effect precisely: why does the gradient vanish once the ratio exceeds `1+\epsilon` for a positive-advantage action?
**Answer:** For `A_t>0`, `L^{\text{CLIP}}=\min(r_tA_t,\text{clip}(r_t,1-\epsilon,1+\epsilon)A_t)`. Once `r_t>1+\epsilon`, `\text{clip}(r_t,\cdot,\cdot)=1+\epsilon`, a constant with respect to `\theta` in that region — its gradient is exactly zero. Since `A_t>0`, `r_tA_t` grows with `r_t` while the clipped term stays fixed at `(1+\epsilon)A_t`; once `r_t>1+\epsilon`, the clipped term is smaller, so the `\min` selects it — and the objective the optimizer actually differentiates has zero gradient in that region, removing all incentive to push `r_t` any higher.
**Follow-up trap:** *"Work out the symmetric case for `A_t<0` — does the clip still stop the 'helpful' direction, even though decreasing the action's probability is generally what you want for a bad action?"* — yes: as `r_t` drops below `1-\epsilon`, the clipped term becomes the constant `(1-\epsilon)A_t`; since `A_t<0`, this constant is *more negative* than the shrinking `r_tA_t` would eventually become as `r_t\to0`, so the `\min` again selects the clipped (now zero-gradient) term once `r_t<1-\epsilon` — the clip caps the incentive to decrease the ratio too, in the direction that's locally "helpful" (lowering probability further), for exactly the same overstepping-risk reason.

### Q5 — Why does PPO take the `min` of the clipped and unclipped terms instead of just using the clipped term alone?
**Answer:** Taking the `\min` makes `L^{\text{CLIP}}` a pessimistic lower bound on the unclipped surrogate in every case, not just the common one. Without the min, there are edge cases — e.g., a ratio that moved in the *unhelpful* direction relative to the advantage's sign due to an unrelated earlier update — where the clipped term alone could report a more optimistic (larger) value than the true unclipped surrogate, which would defeat the entire purpose of bounding over-optimistic updates.
**Follow-up trap:** *"Give a concrete numeric case where clip-without-min and min(clip,unclipped) actually differ."* — `A_t=-1`, `r_t=0.5`, `\epsilon=0.2`: unclipped `=0.5\times(-1)=-0.5`; clipped `=(1-0.2)\times(-1)=-0.8`. `\min(-0.5,-0.8)=-0.8` (correctly pessimistic — the true unclipped value is actually the larger, less-penalized one here, and the min correctly always reports the smaller/more-conservative of the two, whichever that happens to be for the given sign of `A_t` and position of `r_t`).

### Q6 — Derive GAE from the n-step advantage estimator and explain what `\lambda=0` and `\lambda=1` reduce to.
**Answer:** `\hat{A}_t^{(n)}=\sum_{l=0}^{n-1}\gamma^l\delta_{t+l}`, which telescopes to `-V(s_t)+\sum_{l=1}^n\gamma^{l-1}r_{t+l}+\gamma^nV(s_{t+n})`. GAE exponentially weights every `n`-step estimator by `(1-\lambda)\lambda^{n-1}` and sums, which collapses (by re-collecting terms by power of `\gamma\lambda`) to the compact form `\hat{A}_t^{\text{GAE}}=\sum_{l=0}^\infty(\gamma\lambda)^l\delta_{t+l}`. At `\lambda=0`, only the `l=0` term survives: `\hat{A}_t=\delta_t`, the single-step, low-variance, critic-biased estimate. At `\lambda=1`, the sum telescopes fully (every intermediate `V(\cdot)` term cancels) to `\sum_l\gamma^lr_{t+l+1}-V(s_t)`, the full, unbiased Monte Carlo advantage.
**Follow-up trap:** *"If λ=0 is just the one-step actor-critic advantage from `T31-policy-gradient`, why does PPO specifically need GAE rather than that single-step estimate directly?"* — PPO trains on batches of multi-step rollouts collected before any update, and the pure one-step bootstrap tends to carry too much bias early in training when the critic is still poorly calibrated on the current policy's state distribution; GAE's intermediate `\lambda` (commonly `0.9`-`0.97`) empirically performs more robustly across this realistic training regime than either bias-variance extreme.

### Q7 — A production RLHF PPO run's clip statistics look fine (ratios mostly within `[0.8,1.2]`), yet the model's outputs drift noticeably from the reference model's style/quality over many training steps. What's happening, and what's the standard fix?
**Testing:** the specific, real gap between per-step clipping and cumulative drift.
**Answer:** PPO's clip is a per-update, per-token/per-sample bound on the probability ratio relative to the *immediately preceding* policy — it says nothing about the cumulative divergence from a fixed reference (typically the SFT model) accumulated across hundreds or thousands of such updates, each individually well within the clip bound. The standard fix is an explicit KL-divergence penalty term against the fixed reference policy, `\mathcal{L}=L^{\text{CLIP}}-\beta D_{KL}(\pi_\theta\|\pi_{\text{ref}})`, monitored and often adaptively tuned (`\beta` increased if the running KL exceeds a target) — a separate mechanism from the clip, addressing a separate failure mode.
**Follow-up trap:** *"Could you instead just shrink `\epsilon` to make each step's allowed drift smaller?"* — that reduces the *rate* of drift somewhat but doesn't bound the *cumulative* drift over an unboundedly long training run — a smaller `\epsilon` slows the walk but the walk still has no destination-independent ceiling without an explicit reference-anchored penalty, which is a qualitatively different kind of constraint (anchored to a fixed reference point, not to the immediately preceding policy).

### Q8 — Why does PPO allow multiple gradient epochs over the same collected batch, when the policy gradient theorem's derivation (`T31-policy-gradient`) assumed on-policy sampling from the *current* policy?
**Answer:** After the first gradient epoch, `\theta` has moved away from `\theta_{\text{old}}` (the policy that actually collected the batch), technically making subsequent epochs' gradient estimates off-policy relative to the data. The probability ratio `r(\theta)=\pi_\theta/\pi_{\theta_{\text{old}}}` is exactly the importance-sampling correction (`T31-policy-gradient` Q8) that makes reusing this data valid to a bounded degree — and the clip mechanism directly bounds how far `\theta` (and thus how unreliable the importance weight) is allowed to drift within those extra epochs, making the reuse approximately valid rather than exactly valid.
**Follow-up trap:** *"If you ran, say, 50 epochs instead of the typical 3-10, would that still be safe?"* — no; even with the clip bounding per-sample ratio excursions, running enough epochs lets the aggregate policy drift far enough from `\theta_{\text{old}}` that the importance-sampling correction becomes unreliable in aggregate (many individually-small-looking updates compounding) — empirically, `3`-`10` epochs is the range found to balance sample reuse against this drift risk; there's no formal guarantee for arbitrarily many epochs.

### Q9 — Why does DQN-style function approximation instability (`T31-dqn`'s deadly triad) not apply the same way to PPO's actor update?
**Testing:** connecting across the track rather than treating each algorithm as isolated.
**Answer:** The deadly triad is specifically function approximation + bootstrapping + **off-policy** learning. PPO's actor update is (approximately, per Q8) on-policy — the clip and limited epoch count keep it close enough to on-policy that the specific instability mechanism from `T31-dqn` (a gradient step at one state shifting the bootstrap target for a *different* state the next backup depends on, compounding under off-policy reuse) doesn't manifest the same way. PPO's critic (`V_\phi`), however, *is* trained via ordinary TD bootstrapping and does share some of that risk in principle, though in practice it's far less severe than DQN's setting because the critic isn't driving a `\max_a` operation and the data distribution shifts much more slowly under PPO's bounded updates.
**Follow-up trap:** *"So is PPO immune to any form of value-function instability?"* — no; a critic that's badly miscalibrated (e.g., after a distribution shift the clip didn't fully prevent) can still feed unreliable advantage estimates into the actor update, which is exactly the "critic lag" failure mode flagged in `T31-policy-gradient`'s interview questions — PPO reduces but doesn't eliminate this class of problem, it's mitigated by the same bounded-update mechanism, not a categorically different guarantee.

### Q10 — Design the RL fine-tuning setup for a code-generation LLM using PPO. What's the state, action, and reward structure, and where specifically would you expect PPO's clip to matter most versus the explicit KL penalty?
**Testing:** synthesis, applying PPO's specific mechanisms to the RLHF/LLM setting rather than reciting the classic-control version.
**Answer:** State = prompt plus tokens generated so far; action = next token (or, in a coarser formulation, deciding to continue vs. stop); reward is typically sparse, delivered at sequence end from a reward model (unit-test pass/fail signal, or a learned preference-based reward model) — the same short-horizon, deterministic-transition MDP shape discussed in `T31-mdp` Q12. The clip matters most for controlling *within-batch* noise from initial exploration (early training, when a batch of highly-variable-quality completions could otherwise produce enormous, destabilizing ratio swings on any single completion); the explicit KL penalty against the reference (SFT) model matters most for the *longer-horizon* concern — preventing the model's code style/general capability from drifting away from the reference model's broader competence over the full training run, a concern the clip structurally can't address since it only sees the immediately preceding policy.
**Follow-up trap:** *"If the reward model itself is imperfect (as it always is), does either mechanism protect against reward hacking?"* — no — both the clip and the KL penalty constrain *how the policy moves*, not whether the reward signal it's chasing is itself correct; a policy can hack an imperfect reward model while satisfying both the clip and a modest KL budget perfectly, which is why reward hacking (`T31-rl-for-llms`) is a separate, additional failure mode requiring reward-model-side mitigations, not a PPO-hyperparameter fix.

### Q11 — A colleague claims TRPO is strictly obsolete now that PPO exists. Push back or agree — under what circumstance would you actually still reach for TRPO?
**Testing:** whether the tradeoff is understood as a real one, not "PPO always wins."
**Answer:** Disagree with "strictly obsolete." TRPO's guarantee (approximate monotonic improvement per step, backed by an explicit, checkable KL constraint with a line search verifying it) is stronger and more directly auditable than PPO's, which only approximately bounds step size via a first-order proxy with no formal per-step guarantee. In safety-critical or research settings where a verifiable trust-region guarantee matters more than implementation simplicity or wall-clock training speed — and where the cost of conjugate-gradient/Fisher-vector-product machinery is acceptable — TRPO remains the principled choice; PPO's popularity reflects an engineering tradeoff (simplicity, first-order-only, comparable empirical performance), not a strict dominance result.
**Follow-up trap:** *"Name a concrete real-world setting where that stronger guarantee would actually change a decision, not just be nice to have."* — a regulated or safety-critical control application (e.g. a physical system where a policy regression during training risks real damage, and a verifiable per-update improvement bound is a genuine risk-management requirement, not a convenience) — most RLHF and game-playing applications don't have this requirement, which is exactly why PPO dominates there instead.

---

## Red flags that fail you

- Describing PPO's clip as "just gradient clipping" rather than a clipped *objective* bounding the probability ratio.
- Unable to derive why the gradient vanishes past the clip boundary, or confusing which direction (`A>0` vs `A<0`) the clip bounds.
- Claiming the clip alone fully solves RLHF policy drift, without knowing an explicit KL penalty against a reference model is typically also required in production.
- Not knowing GAE's relationship to TD(λ), or treating `\lambda` as an arbitrary tuning knob rather than a bias-variance dial with derivable extremes.
- Confusing TRPO's hard KL constraint with PPO's soft, ratio-based approximation, or claiming they solve the problem via the same mechanism.
- Not knowing PPO trains for multiple epochs per batch, or not understanding why that's only approximately valid (importance sampling, bounded by the clip).
- Treating PPO's clip/KL machinery as a defense against reward hacking, when it only constrains how the policy moves, not whether the reward signal is correct.

---

## Cheat card

```
WHY UNCONSTRAINED STEPS BREAK: policy determines NEXT batch's data -- destructive
  update has no "undo" (unlike supervised learning's fixed dataset)
PERF DIFF LEMMA  J(pi')-J(pi) = E_{s~d^pi', a~pi'}[A^pi(s,a)]  <- needs samples
  from pi' (unavailable); surrogate L_pi(pi') substitutes d^pi (OLD dist) instead,
  valid only when pi' close to pi
TRPO             max L(theta) s.t. KL(theta_old, theta) <= delta (~0.01)
                 natural gradient: d* = sqrt(2*delta/(g^T F^-1 g)) F^-1 g
                 F^-1 g via CONJUGATE GRADIENT (avoids O(|theta|^2/3) inversion)
                 + backtracking LINE SEARCH (quadratic KL approx only local)
PPO RATIO        r(theta) = pi_theta(a|s) / pi_theta_old(a|s);  r=1 at step start
PPO CLIP OBJ     L^CLIP = E[ min( r*A, clip(r,1-eps,1+eps)*A ) ]
                 A>0: gradient -> 0 once r > 1+eps (clip branch selected, constant)
                 A<0: gradient -> 0 once r < 1-eps (symmetric)
                 MIN required: makes L^CLIP a PESSIMISTIC lower bound always
CLIP != KL PENALTY  clip bounds ONE step's ratio excursion; does NOT bound
  cumulative drift across many updates -- RLHF adds explicit beta*KL(pi||pi_ref)
  on top, separate mechanism, separate failure mode
GAE              A_t^GAE = sum_l (gamma*lambda)^l * delta_{t+l}
                 lambda=0 -> delta_t (1-step, low var, high bias)
                 lambda=1 -> full MC advantage (telescopes fully, unbiased, high var)
NUMBERS          clip eps ~0.2 (range 0.1-0.3), GAE lambda ~0.95 (0.9-0.99),
                 gamma ~0.99 (control) or ~1.0 (short RLHF horizon),
                 3-10 PPO epochs/batch, rollout ~2048 steps/env (MuJoCo default),
                 vf_coef ~0.5, entropy coef ~0.01, RLHF KL target ~0.01-0.02
MULTI-EPOCH REUSE  valid only APPROXIMATELY -- clip bounds importance-sampling
  staleness across epochs; too many epochs breaks this (no formal guarantee)
GRPO CONTRAST    removes the critic entirely -- group-relative reward
  normalization instead of V(s) baseline (T31-rl-for-llms) -- LLM-scale cost tradeoff
```

## Sources

- [Schulman et al. — Trust Region Policy Optimization (2015)](https://arxiv.org/abs/1502.05477) — accessed 2026-08-03
- [Schulman et al. — Proximal Policy Optimization Algorithms (2017)](https://arxiv.org/abs/1707.06347) — accessed 2026-08-03
- [Schulman et al. — High-Dimensional Continuous Control Using Generalized Advantage Estimation (2016)](https://arxiv.org/abs/1506.02438) — accessed 2026-08-03
- [Kakade & Langford — Approximately Optimal Approximate Reinforcement Learning (2002)](https://people.eecs.berkeley.edu/~pabbeel/cs287-fa09/readings/KakadeLangford-icml2002.pdf) — performance difference lemma — accessed 2026-08-03
- [Spinning Up — Trust Region Policy Optimization](https://spinningup.openai.com/en/latest/algorithms/trpo.html) — accessed 2026-08-03
- [PPO — Stable Baselines3 documentation](https://stable-baselines3.readthedocs.io/en/master/modules/ppo.html) — default hyperparameters — accessed 2026-08-03
- [Ouyang et al. — Training language models to follow instructions with human feedback (InstructGPT, 2022)](https://arxiv.org/abs/2203.02155) — accessed 2026-08-03
- [PPO Hyperparameter Tuning for LLMs — apxml.com](https://apxml.com/courses/rlhf-reinforcement-learning-human-feedback/chapter-4-rl-ppo-fine-tuning/ppo-hyperparameter-tuning-llms) — accessed 2026-08-03

## Changelog
- 2026-08-03 — created
