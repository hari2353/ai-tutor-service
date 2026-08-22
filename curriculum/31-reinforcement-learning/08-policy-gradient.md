# Policy Gradients: REINFORCE Derived, Baselines, Variance Reduction, Actor-Critic

> **Track:** T31 Reinforcement Learning · **Time:** 3h · **Prereqs:** T31-dqn, T31-monte-carlo-td · **Updated:** 2026-08-03
> **Module id:** `T31-policy-gradient` · **Tags:** deep-rl, critical
> **Lab:** `labs/py/31-08-policy-gradient/`

## The 30-second version

Policy gradient methods optimize a parameterized policy `π_θ(a|s)` directly by gradient ascent on expected return, sidestepping the `\max_a Q(s,a)` operation that makes value-based methods (`T31-dqn`) awkward for continuous or huge action spaces. The policy gradient theorem is the mathematical foundation: it proves `\nabla_\theta J(\theta) = \mathbb{E}_{\pi_\theta}[\nabla_\theta\log\pi_\theta(a|s)\, Q^\pi(s,a)]`, a remarkable result because naively you'd expect differentiating through the environment's (possibly unknown, possibly non-differentiable) transition dynamics to be required — the theorem shows the environment-dependent terms cancel and you're left with only a log-probability gradient weighted by a value. REINFORCE is the direct Monte Carlo estimator of this expectation using the observed return `G_t` in place of `Q^π(s,a)`, and it's correct but has punishing variance, exactly the Monte Carlo variance problem from `T31-monte-carlo-td` showing up again in a new context. Baselines — subtracting any state-dependent function `b(s)` from the return — provably don't change the expected gradient (a clean, derivable fact) while dramatically cutting variance when `b(s)\approx V^\pi(s)`, which is precisely the **advantage** `A(s,a)=Q(s,a)-V(s)` from `T31-mdp`. Actor-critic methods make this practical by learning `V(s)` (the critic) alongside `π_θ` (the actor), replacing REINFORCE's full-episode Monte Carlo return with a bootstrapped, lower-variance advantage estimate — the same TD-vs-MC bias-variance tradeoff from `T31-monte-carlo-td`, now steering a policy instead of a value table.

## Why this gets asked

Because the policy gradient theorem's derivation is the second-most-tested "prove this from scratch" moment in RL interviews after the Bellman equation, and it's specifically designed to catch people who've used `torch.distributions.Categorical(...).log_prob(a) * advantage` in code without ever working through *why* that expression is the right gradient. Interviewers who've trained policy-gradient agents (or shipped RLHF, which is built on this exact machinery, `T31-ppo`) have personally watched REINFORCE's variance make training either not converge or converge absurdly slowly, and want to know you understand baselines and actor-critic as *necessary* variance-reduction engineering, not optional refinements.

---

## Lineage: past → present → future

**What came before.** Value-based methods (`T31-dynamic-programming` through `T31-dqn`) learn `V` or `Q` and derive a policy indirectly by acting greedily — which works cleanly for discrete actions but hits a wall for continuous action spaces, where `\max_a Q(s,a)` has no closed form and must be approximated at real computational cost. Williams' REINFORCE algorithm (1992) was the original direct-policy-optimization method, predating deep RL entirely, built on the insight (formalized later as the policy gradient theorem, Sutton et al., 2000) that you can differentiate the *expected return* with respect to policy parameters without needing a model of the environment's dynamics — the pain it solved was exactly the "value-based methods don't handle continuous actions cleanly" gap, at the cost of a genuinely hard new problem: gradient estimates from sampled trajectories are extremely high-variance, and REINFORCE alone was often impractically slow to train.

**Where it stands now.** **Where it stands now. ** Actor-critic architectures — REINFORCE's unbiased gradient direction, but with a learned critic supplying a much lower-variance value/advantage estimate instead of raw Monte Carlo returns — are the settled foundation under essentially every modern deep policy-gradient method, from A2C/A3C (2016) through PPO (`T31-ppo`) to the RLHF pipelines behind production LLM post-training (`T31-rl-for-llms`). The live technical question isn't "policy gradient vs value-based" in the abstract (both remain standard, chosen per problem shape) but specifically how much of the actor-critic machinery a given production system needs: full trust-region methods (TRPO, PPO) versus simpler advantage-actor-critic; single global baselines versus per-timestep learned value functions; and how aggressively to trade bias (via bootstrapping, small-λ GAE) for variance reduction depending on how expensive environment interaction is. GRPO (`T31-rl-for-llms`), DeepSeek's 2024 method for LLM RL, is a genuinely notable recent departure — it removes the learned critic entirely, replacing it with a group-relative baseline computed from multiple sampled rollouts of the same prompt, a real structural alternative to the actor-critic pattern this module builds, motivated by the critic's cost being roughly as large as the policy model itself at LLM scale.

**Where it's heading.** High confidence: some form of variance reduction beyond raw REINFORCE remains essential wherever policy gradients are used — the theorem's unbiasedness was never the practical bottleneck, variance always was, and nothing in nearer-term hardware or model scale changes that fundamental statistical fact. Medium confidence: critic-free or critic-light methods (GRPO-style group baselines, and related ideas) continue gaining share specifically in large-model RL settings where training a separate critic network is expensive relative to the policy itself, a cost tradeoff that doesn't apply the same way in classic, much-smaller-scale control RL. Speculative: whether critic-free approaches generalize meaningfully beyond the specific structure of LLM RL (many i.i.d. samples of the same "state" via repeated sampling at temperature) back into classic sequential control problems is an open, actively debated question, not settled.

---

## Mental model

```
  VALUE-BASED (T31-dqn):     learn Q(s,a) -> derive policy: pi(s) = argmax_a Q(s,a)
                              needs an argmax over actions -- awkward/intractable for continuous A

  POLICY GRADIENT:           learn pi_theta(a|s) DIRECTLY -- a differentiable function outputting
                              an action distribution -- and push its parameters uphill on J(theta)
                              via gradient ASCENT, no argmax over actions ever required

  gradient direction:  nudge theta so actions that led to HIGH return become MORE likely,
                        and actions that led to LOW return become LESS likely
                        (weighted nudge, not a hard argmax choice)

        ∇J(θ) = E[ ∇log π_θ(a|s) · (how good was this action, really) ]
                       ▲                          ▲
                push probability UP           weight of the push:
                for actions taken            Q, or G_t, or advantage --
                                              this module's whole story
                                              is refining THIS term
```

Value-based RL asks "what's the best action, computed by comparing values" and forces a hard choice. Policy gradient asks "how should I nudge my action *probabilities* so that better-than-average outcomes become more likely" — a soft, differentiable, gradient-based nudge rather than an argmax. Everything in this module — REINFORCE, baselines, actor-critic — is about how to compute a good, low-variance estimate of "how good was this action, really" (the weight multiplying the log-probability gradient).

---

## How it actually works

### The policy gradient theorem, derived from scratch

Define `J(\theta) = \mathbb{E}_{\tau\sim\pi_\theta}[G(\tau)]`, the expected return over trajectories `τ` sampled by running `π_θ`. We want `\nabla_\theta J(\theta)`. Write the expectation as an integral over trajectories weighted by their probability under `π_θ`:

$$J(\theta) = \int P_\theta(\tau)\, G(\tau)\, d\tau \qquad \nabla_\theta J(\theta) = \int \nabla_\theta P_\theta(\tau)\, G(\tau)\, d\tau$$

Here's the key algebraic trick — the **log-derivative trick** (also called the REINFORCE trick or score-function trick), a single identity from calculus: `\nabla_\theta P_\theta(\tau) = P_\theta(\tau)\nabla_\theta\log P_\theta(\tau)`, which follows directly from `\nabla_\theta \log P_\theta(\tau) = \nabla_\theta P_\theta(\tau)/P_\theta(\tau)`, just rearranged. Substituting:

$$\nabla_\theta J(\theta) = \int P_\theta(\tau)\,\nabla_\theta\log P_\theta(\tau)\, G(\tau)\, d\tau = \mathbb{E}_{\tau\sim\pi_\theta}\left[\nabla_\theta\log P_\theta(\tau)\, G(\tau)\right]$$

This is already usable — it turns a gradient of an expectation (hard, since the *sampling distribution itself* depends on `θ`) into an expectation of a gradient (easy, estimable by sampling trajectories and averaging), which is the entire point of the trick. Now expand `P_\theta(\tau)`, the probability of a full trajectory `s_0,a_0,s_1,a_1,\dots`, using the chain rule of probability:

$$P_\theta(\tau) = \rho_0(s_0)\prod_{t=0}^{T-1}\pi_\theta(a_t|s_t)\,P(s_{t+1}|s_t,a_t)$$

Taking `\log` turns the product into a sum: `\log P_\theta(\tau) = \log\rho_0(s_0) + \sum_t \log\pi_\theta(a_t|s_t) + \sum_t \log P(s_{t+1}|s_t,a_t)`. Now take `\nabla_\theta` of this sum, term by term: `\rho_0(s_0)` (the initial state distribution) doesn't depend on `θ`, so its gradient is zero. `P(s_{t+1}|s_t,a_t)` — the environment's transition dynamics — also doesn't depend on `θ` (the environment isn't a function of the policy's parameters), so *its* gradient is zero too. This is the genuinely important step in the whole derivation: **every environment-dependent term vanishes**, leaving only:

$$\nabla_\theta\log P_\theta(\tau) = \sum_{t=0}^{T-1}\nabla_\theta\log\pi_\theta(a_t|s_t)$$

Substituting back:

$$\boxed{\nabla_\theta J(\theta) = \mathbb{E}_{\tau\sim\pi_\theta}\left[\left(\sum_{t=0}^{T-1}\nabla_\theta\log\pi_\theta(a_t|s_t)\right) G(\tau)\right]}$$

This is the punchline: **you never needed to know or differentiate through the environment's transition dynamics at all** — the gradient is computable purely from the policy's own log-probabilities and the observed return, which is exactly why this works for environments with unknown, non-differentiable, or even discrete/stochastic dynamics (a simulator you can only sample from, never differentiate through). A refined, lower-variance version of this same result (using the **causality trick** — that `a_t` can only affect rewards from time `t` onward, not earlier ones, so each log-prob term should be weighted by the return *from that point forward*, `G_t`, not the whole-trajectory `G(\tau)`) gives the more commonly used per-timestep form:

$$\nabla_\theta J(\theta) = \mathbb{E}_{\pi_\theta}\left[\sum_t \nabla_\theta\log\pi_\theta(a_t|s_t)\, G_t\right] = \mathbb{E}_{\pi_\theta}\left[\nabla_\theta\log\pi_\theta(a|s)\, Q^{\pi_\theta}(s,a)\right]$$

The last equality (replacing the sampled `G_t` with its expectation `Q^{\pi_\theta}(s,a)`) is the formal statement of the **policy gradient theorem**: the true, exact gradient direction only requires the log-probability gradient weighted by the *true* action-value function — `G_t` is simply an unbiased, high-variance Monte Carlo estimator of that `Q` value, which is exactly the MC-vs-TD story from `T31-monte-carlo-td` reappearing here as "which estimator of `Q` do you plug into this weight."

### REINFORCE: the direct Monte Carlo estimator

REINFORCE is precisely the boxed result above with `G_t` (the observed Monte Carlo return from time `t`) used as the sample estimate of `Q^{\pi_\theta}(s_t,a_t)`:

$$\theta \leftarrow \theta + \alpha \sum_t \nabla_\theta\log\pi_\theta(a_t|s_t)\, G_t$$

Correct, unbiased (an on-policy Monte Carlo estimate of a genuinely unbiased gradient formula), and — inheriting Monte Carlo's variance problem exactly as diagnosed in `T31-monte-carlo-td` — often too noisy to train efficiently. Two independent variance sources compound here specifically: `G_t`'s own trajectory variance (the MC problem), *and* the stochastic policy's own action-sampling noise (`\nabla_\theta\log\pi_\theta(a_t|s_t)` itself varies across which action got sampled), together making raw REINFORCE gradient estimates extremely high-variance in practice, especially with long horizons.

### Baselines: variance reduction that doesn't touch the expected gradient

Subtract a **baseline** `b(s_t)` — any function of the state (must *not* depend on the action, or the proof below breaks) — from `G_t` before weighting:

$$\theta \leftarrow \theta + \alpha \sum_t \nabla_\theta\log\pi_\theta(a_t|s_t)\, \left(G_t - b(s_t)\right)$$

**Why this doesn't bias the gradient, derived.** The claim is `\mathbb{E}_{a\sim\pi_\theta(\cdot|s)}[\nabla_\theta\log\pi_\theta(a|s)\, b(s)] = 0` for any state-dependent (action-independent) `b(s)`. Proof: pull `b(s)` out of the expectation over `a` (it doesn't depend on `a`), leaving `b(s)\,\mathbb{E}_{a\sim\pi_\theta}[\nabla_\theta\log\pi_\theta(a|s)]`. Now use the identity `\mathbb{E}_{a\sim\pi_\theta}[\nabla_\theta\log\pi_\theta(a|s)] = \sum_a \pi_\theta(a|s)\frac{\nabla_\theta\pi_\theta(a|s)}{\pi_\theta(a|s)} = \sum_a \nabla_\theta\pi_\theta(a|s) = \nabla_\theta\sum_a\pi_\theta(a|s) = \nabla_\theta(1) = 0` — the sum over `a` of a probability distribution is always exactly 1 regardless of `θ`, so its gradient is exactly 0. This is a clean, exact algebraic fact, not an approximation: subtracting *any* state-dependent baseline leaves the expected gradient exactly unchanged.

**Why it reduces variance.** `\text{Var}(X-b) = \text{Var}(X) - 2\,\text{Cov}(X,b) + \text{Var}(b)`; when `b(s)` is well-correlated with `G_t` (which it is, whenever `b(s)\approx\mathbb{E}[G_t|s_t=s]=V^\pi(s)`), the covariance term is large and positive, cutting variance substantially below `\text{Var}(G_t)` alone. The provably variance-minimizing baseline is not `V^π(s)` exactly (the optimal choice is a slightly different, action-noise-weighted quantity) but `V^π(s)` is close to optimal, easy to estimate (a learned critic, next section), and is the standard practical choice.

**The advantage function falls out naturally.** With `b(s)=V^\pi(s)`, the weight becomes `G_t - V^\pi(s_t) \approx Q^\pi(s_t,a_t) - V^\pi(s_t) = A^\pi(s_t,a_t)` — exactly the advantage function defined via the `V\le\max_a Q` identity in `T31-mdp` and used in Dueling DQN (`T31-dqn`). This is a genuinely satisfying convergence: three different parts of this track (the policy improvement theorem's `Q-V` inequality, Dueling DQN's architecture, and policy-gradient baselines) all arrive at the same quantity because it answers the same underlying question — "how much better than average was this specific action" — from three different angles.

### Actor-critic: replacing Monte Carlo `G_t` with a bootstrapped estimate

REINFORCE-with-baseline still uses the full Monte Carlo return `G_t` in the advantage estimate `G_t - V(s_t)`, inheriting MC's variance and its need to wait for episode completion. **Actor-critic** methods train two things jointly: the **actor** `π_θ(a|s)` (the policy, updated via the policy gradient) and the **critic** `V_φ(s)` or `Q_φ(s,a)` (a learned value function, updated via ordinary TD learning, `T31-monte-carlo-td`). The critic supplies a bootstrapped advantage estimate instead of a Monte Carlo one:

$$A(s_t,a_t) \approx \delta_t = r_{t+1} + \gamma V_\phi(s_{t+1}) - V_\phi(s_t) \qquad \theta \leftarrow \theta + \alpha\,\nabla_\theta\log\pi_\theta(a_t|s_t)\,\delta_t$$

Notice `δ_t` is exactly the TD error from `T31-monte-carlo-td`, doing double duty: it's simultaneously the critic's own training signal (`V_φ` is updated to reduce `δ_t`, ordinary TD(0) prediction) *and*, remarkably, an unbiased-in-expectation estimate of the advantage `A^\pi(s_t,a_t)` used to train the actor — a fact worth stating precisely: `\mathbb{E}[\delta_t|s_t,a_t] = \mathbb{E}[r_{t+1}+\gamma V^\pi(s_{t+1})|s_t,a_t] - V^\pi(s_t) = Q^\pi(s_t,a_t) - V^\pi(s_t) = A^\pi(s_t,a_t)`, using the Bellman equation identity from `T31-mdp` directly. This bootstrapped `δ_t` trades some bias (the critic `V_φ` is itself an imperfect, still-training estimate — the same TD bias discussed in `T31-monte-carlo-td`) for a large variance reduction relative to full Monte Carlo `G_t`, and crucially allows *online*, per-step updates rather than waiting for episode completion, exactly mirroring TD's advantage over MC in the pure prediction setting.

**Actor-critic architectures in practice.** A2C (Advantage Actor-Critic) is the synchronous, single-estimate version of this idea; A3C (Asynchronous Advantage Actor-Critic, Mnih et al., 2016) runs many parallel actor-learners with asynchronous updates to a shared model — the parallelism itself acts as an additional variance-reduction and decorrelation mechanism (many different trajectories contributing gradient estimates simultaneously, similar in spirit to why a replay buffer decorrelates DQN's updates, though achieved differently here since actor-critic is on-policy and can't use a replay buffer the same way). GAE (Generalized Advantage Estimation, Schulman et al., 2016, used centrally in `T31-ppo`) generalizes the single-step `δ_t` advantage to the exact same `λ`-weighted blend of n-step advantage estimates that TD(λ) uses for value functions (`T31-monte-carlo-td`), letting the actor-critic bias-variance tradeoff be tuned continuously via one hyperparameter rather than being stuck at either the pure-TD (`λ=0`) or pure-MC (`λ=1`) extreme.

---

## Build it from scratch

REINFORCE with a learned value-function baseline, and a one-step actor-critic variant, on a small discrete-action environment, structured to make the variance difference between the two directly measurable:

```python
import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F

class PolicyNet(nn.Module):
    def __init__(self, obs_dim, n_actions, hidden=64):
        super().__init__()
        self.net = nn.Sequential(nn.Linear(obs_dim, hidden), nn.Tanh(), nn.Linear(hidden, n_actions))

    def forward(self, s):
        return F.softmax(self.net(s), dim=-1)   # action distribution

class ValueNet(nn.Module):
    def __init__(self, obs_dim, hidden=64):
        super().__init__()
        self.net = nn.Sequential(nn.Linear(obs_dim, hidden), nn.Tanh(), nn.Linear(hidden, 1))

    def forward(self, s):
        return self.net(s).squeeze(-1)

def compute_returns(rewards, gamma=0.99):
    """G_t for every t in one episode, computed backward (same trick as T31-monte-carlo-td)."""
    G, returns = 0.0, []
    for r in reversed(rewards):
        G = r + gamma * G
        returns.insert(0, G)
    return returns

def reinforce_with_baseline_episode(env, policy, value_fn, policy_opt, value_opt, gamma=0.99):
    s = env.reset()
    log_probs, states, rewards = [], [], []
    done = False
    while not done:
        s_t = torch.tensor(s, dtype=torch.float32)
        probs = policy(s_t)
        dist = torch.distributions.Categorical(probs)
        a = dist.sample()
        log_probs.append(dist.log_prob(a))
        states.append(s_t)
        s, r, done, _ = env.step(int(a.item()))
        rewards.append(r)

    returns = torch.tensor(compute_returns(rewards, gamma), dtype=torch.float32)
    states_t = torch.stack(states)
    baseline = value_fn(states_t)                 # V_phi(s_t) for every visited state

    advantage = returns - baseline.detach()        # G_t - b(s_t); detach so the actor's
                                                    # gradient doesn't flow into the critic
    policy_loss = -(torch.stack(log_probs) * advantage).sum()   # ascent -> minimize the negative
    value_loss = F.mse_loss(baseline, returns)     # critic trained toward the SAME MC return

    policy_opt.zero_grad(); policy_loss.backward(); policy_opt.step()
    value_opt.zero_grad(); value_loss.backward(); value_opt.step()
    return sum(rewards)

def actor_critic_step(s, policy, value_fn, policy_opt, value_opt, env, gamma=0.99):
    """One-step (online) actor-critic: bootstrapped TD advantage instead of full-episode G_t."""
    s_t = torch.tensor(s, dtype=torch.float32)
    probs = policy(s_t)
    dist = torch.distributions.Categorical(probs)
    a = dist.sample()
    log_prob = dist.log_prob(a)

    s2, r, done, _ = env.step(int(a.item()))
    s2_t = torch.tensor(s2, dtype=torch.float32)

    v_s = value_fn(s_t)
    with torch.no_grad():
        v_s2 = value_fn(s2_t) if not done else torch.tensor(0.0)
        td_target = r + gamma * v_s2

    delta = td_target - v_s                        # TD error = advantage estimate AND critic's own loss signal
    policy_loss = -(log_prob * delta.detach())      # actor uses delta as the advantage weight
    value_loss = delta.pow(2)                       # critic minimizes its own TD error, squared

    policy_opt.zero_grad(); policy_loss.backward(); policy_opt.step()
    value_opt.zero_grad(); value_loss.backward(); value_opt.step()
    return s2, r, done
```

Two details worth flagging as load-bearing: `advantage = returns - baseline.detach()` — detaching the baseline before it weights the policy gradient is what keeps the proof from the derivation above valid (the baseline must not itself depend on `θ` *in the actor's gradient computation*, even though `φ` is being trained separately), and `delta.detach()` in the actor-critic version for the identical reason. Training both the REINFORCE-with-baseline version and the one-step actor-critic version on the same environment and logging the variance of the policy gradient's magnitude across episodes (not just mean reward) is the concrete, measurable version of "actor-critic trades bias for lower variance" — plot the gradient norm's variance, not just final performance, to see the effect this module is built around.

---

## How it's done in production

| Layer | What you actually use | What it adds |
|---|---|---|
| Framework | Stable-Baselines3 (A2C, PPO), RLlib, CleanRL | Correct log-prob computation for common distribution types (categorical, diagonal Gaussian for continuous actions), entropy regularization, and the dozens of small numerical-stability details (log-prob clipping, advantage normalization) |
| Parallelism | Vectorized environments (many parallel rollouts feeding one batch update) rather than A3C's original asynchronous-gradient scheme | Modern practice mostly replaced true asynchronous updates with synchronous vectorized rollouts (simpler to reason about, equally effective on modern accelerators) |
| Advantage estimation | GAE (`T31-ppo`) almost universally, rather than either raw MC returns or single-step TD | The continuous bias-variance dial, tuned per problem rather than fixed at either extreme |
| LLM-scale policy gradient | PPO or GRPO (`T31-rl-for-llms`) | GRPO specifically removes the learned critic, a direct response to critic cost at LLM parameter scale |

### Failure modes

| Symptom | Cause | Fix |
|---|---|---|
| Training reward is extremely noisy episode-to-episode, barely trending upward | Raw REINFORCE (no baseline), inheriting full Monte Carlo variance | Add a learned value-function baseline at minimum; consider full actor-critic with a bootstrapped advantage |
| Policy collapses to a single action very early in training, stops exploring | Entropy of the policy distribution not regularized, or learning rate too high causing premature over-confidence in one action | Add an entropy bonus to the loss (`-\beta\,\mathcal{H}[\pi_\theta(\cdot|s)]`, encouraging the distribution to stay spread out longer); lower the actor's learning rate |
| Policy gradient updates are unstable/diverge despite a baseline being used | Baseline gradient not detached — the "baseline" is inadvertently coupled to the actor's gradient computation, breaking the zero-bias proof's requirement that `b(s)` not depend on the action *or* leak gradient back through the actor's parameters improperly | Explicitly `.detach()` the baseline/advantage before it multiplies the log-probability term |
| Critic's value estimates lag badly behind the actor's rapidly-changing policy | Critic learning rate too low relative to actor, or critic and actor sharing a network body without appropriate loss weighting | Tune relative learning rates; consider separate networks or careful loss-weighting if sharing a trunk |

---

## Tradeoffs & when NOT to use it

- **Don't use raw REINFORCE (no baseline) in anything beyond a toy problem or a first correctness check.** Its variance is a real, provable, first-order barrier to sample-efficient training — a baseline is not an optional refinement, it's close to a prerequisite for practical use.
- **Prefer value-based methods (`T31-dqn`) over policy gradient when the action space is small and discrete and sample efficiency matters more than continuous-action flexibility** — off-policy value-based methods can reuse a replay buffer; on-policy actor-critic generally can't reuse old rollouts the same way (the policy gradient theorem's derivation assumes actions are sampled from the *current* `π_θ`), making it typically less sample-efficient per environment interaction than a well-tuned off-policy value method on problems where both apply.
- **Policy gradient (and its actor-critic and PPO descendants) is close to mandatory, not optional, for continuous action spaces** — this is the structural gap value-based methods can't cleanly fill (`T31-dqn`'s tradeoffs section), and it's the main reason this family of methods dominates robotics and continuous control (`T31-continuous-control`).
- **Don't assume a shared actor-critic network body is free.** Sharing lower layers between actor and critic saves parameters and can help representation learning, but couples their optimization — a critic loss that dominates gradient updates can degrade the actor's learning signal, and vice versa, requiring explicit loss-weighting most single-network implementations get wrong on a first pass.
- **For LLM-scale RL specifically, weigh critic cost explicitly.** A full actor-critic setup implies a second, often similarly-sized network purely for advantage estimation — a real, substantial cost at LLM parameter counts, which is exactly the tradeoff GRPO (`T31-rl-for-llms`) was designed around.

---

## Interview questions

### Q1 — Derive the policy gradient theorem from `J(\theta)=\mathbb{E}_\tau[G(\tau)]`. Where specifically does the environment's transition model drop out?
**Answer:** Write `J(\theta)=\int P_\theta(\tau)G(\tau)d\tau`, apply the log-derivative trick `\nabla_\theta P_\theta(\tau)=P_\theta(\tau)\nabla_\theta\log P_\theta(\tau)` to get `\nabla_\theta J(\theta)=\mathbb{E}_\tau[\nabla_\theta\log P_\theta(\tau)\,G(\tau)]`. Expand `\log P_\theta(\tau)=\log\rho_0(s_0)+\sum_t\log\pi_\theta(a_t|s_t)+\sum_t\log P(s_{t+1}|s_t,a_t)`. Taking `\nabla_\theta`, the initial-state term and the transition-probability term both vanish because neither `\rho_0` nor `P(s_{t+1}|s_t,a_t)` depends on `θ` — that's precisely where the environment model drops out — leaving only `\sum_t\nabla_\theta\log\pi_\theta(a_t|s_t)`.
**Follow-up trap:** *"Does this mean the gradient doesn't depend on the environment's dynamics at all?"* — the *formula* for the gradient doesn't reference `P(s'|s,a)` explicitly, but the *expectation* is still taken over trajectories `τ` sampled by actually running `π_θ` in that environment — the dynamics still fully determine which trajectories (and returns) you observe and average over, they just don't need to be differentiated through or even known in closed form.

### Q2 — Prove that subtracting a state-dependent baseline doesn't change the expected policy gradient.
**Answer:** Need `\mathbb{E}_{a\sim\pi_\theta(\cdot|s)}[\nabla_\theta\log\pi_\theta(a|s)\,b(s)]=0`. Pull `b(s)` out of the expectation over `a` since it doesn't depend on `a`: `b(s)\mathbb{E}_{a\sim\pi_\theta}[\nabla_\theta\log\pi_\theta(a|s)]`. Then `\mathbb{E}_{a\sim\pi_\theta}[\nabla_\theta\log\pi_\theta(a|s)]=\sum_a\pi_\theta(a|s)\frac{\nabla_\theta\pi_\theta(a|s)}{\pi_\theta(a|s)}=\sum_a\nabla_\theta\pi_\theta(a|s)=\nabla_\theta\sum_a\pi_\theta(a|s)=\nabla_\theta(1)=0`, since a probability distribution always sums to exactly 1 regardless of `θ`.
**Follow-up trap:** *"What breaks in this proof if the baseline depends on the action, `b(s,a)`, instead of just the state?"* — you can no longer pull `b(s,a)` out of the expectation over `a` (step one of the proof), so the sum `\sum_a\pi_\theta(a|s)\nabla_\theta\log\pi_\theta(a|s)b(s,a)` doesn't collapse to `b(s)\nabla_\theta\sum_a\pi_\theta(a|s)` — it generally doesn't vanish, meaning an action-dependent baseline *does* bias the gradient in general, which is exactly why baselines must be state-only.

### Q3 — Why does using `V^π(s)` as the baseline produce the advantage function, and why is that specific choice appealing beyond just "any valid baseline works"?
**Answer:** With `b(s_t)=V^\pi(s_t)`, the weight `G_t-b(s_t)` becomes (in expectation) `Q^\pi(s_t,a_t)-V^\pi(s_t)=A^\pi(s_t,a_t)`, the advantage — a natural, interpretable quantity ("how much better than average was this specific action") rather than an arbitrary variance-reducing constant. It's appealing beyond arbitrary validity because `V^π(s)` is highly correlated with `G_t` by construction (it's literally `G_t`'s conditional expectation given `s_t`), which per the variance formula `\text{Var}(X-b)=\text{Var}(X)-2\text{Cov}(X,b)+\text{Var}(b)` makes it a genuinely strong variance reducer, not just a technically-valid one.
**Follow-up trap:** *"Is V^π(s) the theoretically variance-minimizing baseline?"* — no, interestingly: the exact variance-minimizing baseline is a slightly different, action-noise-weighted quantity (weighted by the squared score function), not simply `V^π(s)` — but `V^π(s)` is close to optimal in practice, vastly easier to estimate (a standard value-function regression problem, unlike the theoretically optimal one), and is the standard choice for that practical reason, not because it's provably the absolute best.

### Q4 — What's the exact bias-variance tradeoff actor-critic makes relative to REINFORCE-with-baseline, and derive why the TD error `δ_t` is an unbiased estimate of the advantage.
**Answer:** REINFORCE-with-baseline uses `G_t-V(s_t)`, an unbiased (Monte Carlo) but high-variance advantage estimate. Actor-critic uses `\delta_t=r_{t+1}+\gamma V_\phi(s_{t+1})-V_\phi(s_t)`, a bootstrapped, lower-variance but biased (while `V_φ` is imperfect) estimate — exactly TD's tradeoff versus MC (`T31-monte-carlo-td`) reapplied here. Unbiasedness of `δ_t` as an advantage estimator, given a *perfect* critic `V_\phi=V^\pi`: `\mathbb{E}[\delta_t|s_t,a_t]=\mathbb{E}[r_{t+1}+\gamma V^\pi(s_{t+1})|s_t,a_t]-V^\pi(s_t)=Q^\pi(s_t,a_t)-V^\pi(s_t)=A^\pi(s_t,a_t)`, using the Bellman equation identity `Q^\pi(s,a)=\mathbb{E}[r+\gamma V^\pi(s')|s,a]` directly from `T31-mdp`.
**Follow-up trap:** *"That derivation assumed a perfect critic — what happens to the bias-variance claim with a still-training, imperfect critic?"* — the estimate becomes biased by however wrong `V_φ` currently is (identical to the TD bias story in `T31-monte-carlo-td`), which is precisely why actor-critic is a genuine tradeoff and not a strict improvement — early in training, when the critic is far from converged, its bias can genuinely hurt more than raw Monte Carlo's variance would, and this is a real, empirically observed failure mode, not just theoretical hedging.

### Q5 — Why must the baseline (or critic output) be detached from the actor's gradient computation in code?
**Answer:** The zero-bias-of-baseline proof (Q2) relies on `b(s)` being treated as a fixed number from the actor's perspective when computing `\nabla_\theta\log\pi_\theta(a|s)\,(G_t-b(s))` — if `b(s)`'s own gradient with respect to `θ` (or a shared parameter) is allowed to flow back through this term during backpropagation, the actual computed gradient is no longer the clean policy-gradient-theorem expression the proof covers, and the zero-expected-bias guarantee no longer straightforwardly applies. Detaching (`.detach()` / `stop_gradient`) ensures the baseline contributes only its *value*, not its own gradient, to the actor's update.
**Follow-up trap:** *"If the critic and actor share a network trunk, doesn't the critic's loss still affect the actor's parameters through the shared layers, defeating the point of detaching?"* — yes, and this is a real, distinct issue from the detach requirement: shared-trunk architectures do let the critic's loss influence the actor's representation through backpropagation via the shared layers, which is a deliberate design choice (shared representation learning) but requires careful loss-weighting between actor and critic terms to avoid one dominating the other — detaching the *advantage value* used in the policy-gradient weight is still necessary and separate from this shared-trunk consideration.

### Q6 — A colleague's REINFORCE implementation has a bug: they use `G_t - b(s_t)` where `b` is a hand-picked constant (e.g. the running average reward across all episodes so far) instead of a learned `V_φ(s_t)`. Is this wrong?
**Testing:** whether the candidate distinguishes "must be state-dependent" from "must be the optimal choice."
**Answer:** Not wrong in the sense of biasing the gradient — a *global* constant baseline is a special (degenerate) case of a state-dependent baseline (constant in `s` too), and the zero-bias proof still applies exactly, since it holds for any `b(s)` including a constant. It's a worse *practical* choice: a single global average doesn't capture that some states are inherently higher- or lower-value than others, so it captures much less of `G_t`'s variance via the covariance term than a properly state-dependent `V(s)` would — the gradient stays unbiased, but the variance reduction is far weaker.
**Follow-up trap:** *"Is there any scenario where a global constant baseline is actually the right choice, not just an acceptable degenerate one?"* — a bandit-like setting (`T31-rl-framing`) where there's effectively only one state, or states are so similar in value that a state-dependent baseline wouldn't capture meaningfully more variance than the global mean — in genuinely single-state or near-single-state problems, a learned `V(s)` collapses to essentially the same thing as the global average anyway, so the extra machinery buys little.

### Q7 — Explain GAE's relationship to TD(λ) precisely, and why PPO needs it rather than a fixed-n n-step advantage.
**Answer:** GAE computes the advantage as the identical `λ`-weighted exponential blend of n-step *advantage* estimates that TD(λ) (`T31-monte-carlo-td`) uses for n-step *value* estimates — `λ=0` gives the single-step `δ_t` (low variance, biased by an imperfect critic), `λ\to1` approaches a full Monte-Carlo-style advantage (unbiased, high variance). PPO needs a continuously tunable bias-variance dial rather than a fixed `n` because the right tradeoff point is genuinely problem-dependent (episode length, reward density, how good the critic currently is during training) and a single fixed `n` can't adapt as training progresses the way a well-chosen `λ` empirically tends to perform robustly across a wider range of settings.
**Follow-up trap:** *"If λ=0 GAE is just the one-step actor-critic advantage from this module, why does PPO specifically need GAE rather than plain one-step actor-critic?"* — PPO trains on batches of multi-step rollouts collected before any update (unlike a fully online per-step actor-critic), and empirically the pure one-step bootstrap (`λ=0`) tends to have too much bias early in training when the critic itself is still poorly calibrated on the current policy's distribution — GAE's intermediate `λ` values (commonly 0.9-0.97 in practice) are chosen specifically because they perform better across this realistic training regime than either extreme.

### Q8 — Why can't a policy-gradient method straightforwardly reuse old rollouts the way DQN reuses a replay buffer?
**Answer:** The policy gradient theorem's derivation (Q1) computes an expectation *over trajectories sampled from the current `π_θ`* — the expectation `\mathbb{E}_{\pi_\theta}[\cdots]` is specifically with respect to the policy being updated. A rollout collected under an old `π_{\theta_{\text{old}}}` is a sample from a *different* distribution, so directly averaging its log-probabilities and returns as if they were samples from the current policy computes a biased estimate of the wrong quantity — this is fundamentally the on-policy character carried over from `T31-q-learning-sarsa`'s SARSA discussion, now showing up in the policy-gradient setting instead of tabular TD control.
**Follow-up trap:** *"Is there any principled way to reuse old rollouts in a policy-gradient method?"* — yes: importance sampling, reweighting old-policy samples by the probability ratio `\pi_{\theta}(a|s)/\pi_{\theta_{\text{old}}}(a|s)` to correct for the distribution mismatch — this is exactly the mechanism underlying PPO's ability to do multiple gradient epochs per batch of collected data (`T31-ppo`), and the reason that ratio needs to be *clipped* (PPO's core mechanism) is that importance weights become unreliable (high variance, potentially huge) once the current and old policies have drifted too far apart.

### Q9 — Your actor-critic training shows the critic's loss decreasing steadily but the actor's policy isn't improving (task reward flat). What do you check?
**Testing:** diagnosing a real, specific actor-critic failure mode.
**Answer:** A decreasing critic loss only shows the critic is successfully predicting *something* — check first whether it's tracking a moving target well (the critic chasing a policy that's itself still changing, a mild non-stationarity distinct from but related to the deadly-triad concerns in `T31-dqn`) versus tracking a genuinely converged, accurate value function. Separately: check whether the advantage estimates (`δ_t`) being fed to the actor are near-zero on average or lack meaningful variation across actions — if the critic has converged to a value function that makes most actions look equally (un)attractive relative to `V(s)` (e.g. due to insufficient state coverage or a degenerate reward structure), the actor gets almost no useful gradient signal even though the critic's own loss looks fine. Also verify the policy's entropy hasn't collapsed prematurely (Q from the failure-mode table), starving the actor of the exploration needed to discover better actions in the first place.
**Follow-up trap:** *"You confirm advantages have healthy variance and entropy hasn't collapsed. What's left?"* — check the actor and critic learning rates relative to each other; a critic that's learning much faster than the actor can update can produce advantage estimates that shift meaningfully between the time a trajectory is collected and when it's used for the actor's update (especially in synchronous batch settings), effectively feeding the actor a signal that's already stale relative to the critic's latest belief — a subtler timing/staleness issue distinct from a raw convergence problem.

### Q10 — Design the policy-gradient setup for a robotic arm with continuous joint torques as the action space. Why is this a natural fit for this family of methods rather than DQN?
**Testing:** synthesis connecting policy gradients to the continuous-action gap flagged throughout the module.
**Answer:** Use a policy network outputting the parameters of a continuous distribution (commonly a diagonal Gaussian: mean and log-std per action dimension) rather than a softmax over discrete choices; `\log\pi_\theta(a|s)` is then the Gaussian log-density, still perfectly compatible with the policy gradient theorem's derivation, which never assumed a discrete action space anywhere in the proof. Pair with an actor-critic setup (a learned `V_φ(s)` critic) and GAE for the advantage estimate, exactly as derived in this module — this is a natural fit specifically because DQN-family methods require `\max_a Q(s,a)`, intractable to compute exactly over continuous joint-torque space (`T31-dqn`'s tradeoffs), while the policy gradient theorem's derivation never required enumerating or maximizing over actions at all — it only ever needed to sample from `π_θ` and differentiate its log-density, both of which continuous distributions support natively.
**Follow-up trap:** *"Your Gaussian policy's learned standard deviation collapses toward zero early in training, and exploration stops. Is this the same entropy-collapse failure mode as in the discrete case?"* — yes, structurally identical, just manifesting differently: a near-zero standard deviation is the continuous-action analogue of a near-deterministic discrete distribution, and the fix is the same in spirit — an entropy bonus in the loss (computable in closed form for a Gaussian) or an explicit lower bound / minimum floor on the learned standard deviation to prevent the policy from prematurely eliminating its own exploration capacity.

---

## Red flags that fail you

- Stating the policy gradient theorem's formula without being able to derive it, especially the log-derivative trick step.
- Not knowing why the environment's transition probabilities drop out of the gradient (attributing it to "we don't need a model" without deriving *why*).
- Claiming a baseline must equal `V^π(s)` exactly, or that any baseline choice biases the gradient.
- Forgetting to detach the baseline/advantage from the actor's gradient computation, or not understanding why that matters.
- Describing actor-critic as strictly better than REINFORCE-with-baseline without naming the bias it introduces.
- Not connecting the advantage function here to the same quantity from `T31-mdp`/`T31-dqn`.
- Assuming policy-gradient rollouts can be freely reused like a DQN replay buffer without importance-sampling correction.

---

## Cheat card

```
POLICY GRAD    grad_theta J(theta) = E_tau[ grad_theta log P_theta(tau) * G(tau) ]
THEOREM        log-derivative trick: grad P = P * grad(log P)
DERIVATION     log P_theta(tau) = log rho_0(s0) + sum_t log pi(a_t|s_t) + sum_t log P(s'|s,a)
               grad_theta of the LAST TWO non-pi terms = 0 (env doesn't depend on theta)
               -> grad_theta J = E[ sum_t grad log pi(a_t|s_t) * G(tau) ]  -- NO env model needed
CAUSALITY      weight each log-prob term by G_t (return FROM t onward), not full-traj G(tau)
FINAL FORM     grad J = E[ grad log pi(a|s) * Q^pi(s,a) ]   (policy gradient theorem, exact)
REINFORCE      theta += alpha * grad log pi(a_t|s_t) * G_t   -- unbiased, HIGH variance (MC)
BASELINE       theta += alpha * grad log pi(a_t|s_t) * (G_t - b(s_t))
               b(s) must be STATE-ONLY (not action-dependent) or the zero-bias proof breaks
ZERO BIAS PF   E_a[grad log pi(a|s)] = sum_a grad pi(a|s) = grad sum_a pi(a|s) = grad(1) = 0
BEST BASELINE  b(s)=V^pi(s) -> weight becomes ADVANTAGE A(s,a)=Q(s,a)-V(s)  (same A as T31-mdp, Dueling DQN)
ACTOR-CRITIC   delta_t = r + gamma*V_phi(s') - V_phi(s)   <- TD error, doubles as advantage estimate
               E[delta_t | s,a] = A^pi(s,a) exactly, GIVEN a perfect critic (bias if critic imperfect)
               trades REINFORCE's variance for TD's bias -- same tradeoff as T31-monte-carlo-td
DETACH         baseline/advantage MUST be .detach()-ed before weighting log-prob, or gradient
               leaks incorrectly and the zero-bias proof no longer applies to the actual computed grad
GAE            same lambda-blend as TD(lambda), applied to advantage estimates (T31-ppo uses this)
ON-POLICY      grad theorem's E[.] is over trajectories from CURRENT pi_theta -- can't freely reuse
CONSTRAINT     old rollouts like a replay buffer; needs importance-sampling ratio pi/pi_old (-> PPO clip)
CONTINUOUS FIT policy grad needs only SAMPLE from pi_theta + differentiate log-density -- no max_a
               required anywhere -- natural fit for continuous actions where DQN's max_a breaks
```

## Sources

- [Sutton, McAllester, Singh & Mansour — Policy Gradient Methods for Reinforcement Learning with Function Approximation (2000)](https://papers.nips.cc/paper/1713-policy-gradient-methods-for-reinforcement-learning-with-function-approximation) — the policy gradient theorem — accessed 2026-08-03
- [Williams, R. — Simple Statistical Gradient-Following Algorithms for Connectionist Reinforcement Learning (1992)](https://link.springer.com/article/10.1007/BF00992696) — REINFORCE origin — accessed 2026-08-03
- [Mnih et al. — Asynchronous Methods for Deep Reinforcement Learning (2016)](https://arxiv.org/abs/1602.01783) — A3C — accessed 2026-08-03
- [Schulman et al. — High-Dimensional Continuous Control Using Generalized Advantage Estimation (2016)](https://arxiv.org/abs/1506.02438) — GAE — accessed 2026-08-03
- [Sutton & Barto — Reinforcement Learning: An Introduction (2nd ed.), ch. 13](http://incompleteideas.net/book/the-book-2nd.html) — canonical policy gradient treatment — accessed 2026-08-03

## Changelog
- 2026-08-03 — created
