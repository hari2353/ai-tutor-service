# Exploration vs Exploitation: ε-Greedy, UCB, Thompson, Intrinsic Motivation

> **Track:** T31 Reinforcement Learning · **Time:** 2h · **Prereqs:** T31-q-learning-sarsa · **Updated:** 2026-08-03
> **Module id:** `T31-exploration` · **Tags:** fundamentals, critical

## The 30-second version

Exploration is the part of RL that has no supervised-learning analogue at all: you must choose actions that might be suboptimal specifically to learn whether they're suboptimal, and every action spent exploring is an action not spent exploiting the best policy you currently know. ε-greedy is the naive baseline — explore uniformly at random with probability ε — and its weakness is that it explores *blindly*, wasting exploration budget on arms you already confidently know are bad. UCB fixes this by exploring *optimistically*: pick the action with the highest upper confidence bound on its value, so uncertain actions get tried specifically because they're uncertain, and the bound shrinks (provably, at a known rate) as evidence accumulates. Thompson sampling fixes it via a different route — maintain a full posterior distribution over each action's value and sample from it, so exploration probability is automatically proportional to genuine uncertainty without any hand-tuned bonus term. All three assume a good state representation already exists; **intrinsic motivation** (curiosity, novelty/count-based bonuses) is what you reach for when reward is so sparse that none of the above ever sees a nonzero signal to exploit in the first place, replacing "explore to reduce value uncertainty" with "explore to reduce *world-model* uncertainty" as a reward signal in its own right.

## Why this gets asked

Because "just use ε-greedy" is the single most common under-baked answer in RL interviews, and interviewers who've shipped bandits or RL in production (ad serving, pricing, recommendation) have all watched a naive fixed-ε policy burn real revenue exploring arms that were obviously bad from the first hundred samples. This module is where they check whether you understand exploration as a genuine statistical estimation problem (how much do I actually know about this action's value, and how should that govern how often I try it) rather than a knob you set once and forget — and whether you know when sparse reward makes the whole value-uncertainty framing insufficient and a different kind of exploration signal is required.

---

## Lineage: past → present → future

**What came before.** The formal exploration/exploitation tradeoff predates deep RL by decades — it's the central question of the multi-armed bandit literature going back to Thompson's original 1933 paper (proposing what's now called Thompson sampling, for clinical trial allocation) and Robbins' 1952 formalization of the problem. ε-greedy is the folk-theorem baseline: simple, has no optimality guarantee, and was the default for a long time mainly because it's trivial to implement, not because it's good. The pain that better methods solve is regret: ε-greedy's *cumulative* regret (the gap between what you'd have earned playing optimally and what you actually earned) grows *linearly* in the number of steps if ε is held fixed, because it keeps exploring known-bad arms forever at the same fixed rate no matter how much evidence accumulates against them.

**Where it stands now.** UCB (Auer, Cesa-Bianchi & Fischer, 2002, formalizing Lai & Robbins' 1985 asymptotic theory) and Thompson sampling both achieve *logarithmic* cumulative regret in the standard stochastic bandit setting — a qualitatively better guarantee than ε-greedy's linear regret, and both are well-understood, widely deployed in production bandit systems (ad ranking, content recommendation, pricing) where the state space is small enough that per-arm confidence bounds or posteriors are tractable to maintain. In deep RL specifically, none of the classic bandit algorithms transfer cleanly — UCB's confidence bound and Thompson sampling's posterior both assume a small, enumerable set of arms with tractable per-arm statistics, which breaks down completely once "arms" are actions in a huge or continuous state-action space reached via a neural network. The live, unresolved area is exactly this: **deep exploration** — how to get UCB/Thompson-style principled uncertainty-driven exploration to work when the value function is a neural net rather than a table. Approaches include bootstrapped/ensemble DQN (train several value networks, treat their disagreement as a UCB-like uncertainty signal), and intrinsic-motivation methods (count-based bonuses via density models, curiosity via prediction error, Random Network Distillation) that sidestep needing a calibrated posterior entirely by rewarding novelty directly.

**Where it's heading.** High confidence: RND-style and ensemble-based intrinsic motivation remain the practical default for sparse-reward deep RL exploration, because they scale to function approximation without needing an exact Bayesian posterior. Medium confidence: exploration in the LLM-agent and RLHF/RLVR setting (`T31-rl-for-llms`) is a genuinely different problem than classic bandit/deep-RL exploration — the "arms" are entire generated sequences from an astronomically large action space, and current practice leans on sampling temperature and diverse rollout generation rather than anything resembling UCB or count-based bonuses; whether principled exploration theory from this module transfers meaningfully to that setting is unsettled and an active research question, not solved. Speculative: some 2025-2026 work explores using a pretrained model's own calibrated uncertainty (or an auxiliary model) as a exploration-bonus signal for agentic RL — promising in early results but not yet a settled production pattern.

---

## Mental model

```
  epsilon-greedy:   explore UNIFORMLY at random, epsilon of the time
                     "I don't know which unknown thing to try, so I'll try anything"

  UCB:              explore the action with the highest UPPER BOUND on plausible value
                     value_estimate + confidence_bonus(how few times I've tried this)
                     "I'll try the thing that MIGHT be best, given what I don't yet know"

  Thompson:         sample a value from each action's POSTERIOR belief, act on the sample
                     "I'll act as if a random draw from my current uncertainty is the truth"

  Intrinsic motiv:  reward NOVELTY/prediction-error directly, on top of (or instead of) task reward
                     "when task reward is silent, reward reducing my own ignorance of the world"
```

ε-greedy explores like flipping a coin before every decision to decide whether to ignore everything you've learned. UCB and Thompson sampling both explore like a careful statistician: they track how *confident* you are in each estimate, not just the estimate itself, and steer exploration toward the things you're least sure about — the crucial upgrade neither ε-greedy nor "always pick the current best guess" makes.

---

## How it actually works

### ε-greedy: the baseline and its guaranteed failure mode

With probability `1-ε`, act greedily (`\arg\max_a \hat{Q}(a)`); with probability `ε`, act uniformly at random. Simple, and provably suboptimal in a specific way: because it explores every non-greedy action with equal probability *forever* at a constant rate (if ε is fixed), its cumulative regret grows **linearly** in the number of steps `T` — `O(\epsilon T)` — since a constant `ε` fraction of all-time steps go to random (often bad) actions regardless of how well-established their badness is. The fix that's almost always paired with ε-greedy in practice is **decay**: `\epsilon_t \to 0` as `t\to\infty` (e.g. `\epsilon_t = 1/t`, or a scheduled decay). A policy with the right decay schedule and enough exploration in the limit is called **GLIE** (Greedy in the Limit with Infinite Exploration) — it explores every action infinitely often (needed for Q-learning's convergence proof, `T31-q-learning-sarsa`) while `ε_t\to 0`, so it eventually becomes greedy. GLIE ε-greedy is what makes the tabular convergence theorems in this track actually apply, not fixed-ε.

### UCB: optimism under uncertainty, derived

For each action `a`, maintain the sample-mean reward `\hat{Q}(a)` and the visit count `N(a)`. UCB1 selects:

$$a_t = \arg\max_a \left[\hat{Q}(a) + c\sqrt{\frac{\ln t}{N(a)}}\right]$$

The bonus term `c\sqrt{\ln t/N(a)}` is a confidence-interval width, derived from Hoeffding's inequality: for a bounded random variable, the sample mean over `N` draws deviates from the true mean by more than `\sqrt{\ln(1/\delta)/(2N)}` with probability at most `δ`. Setting `δ` to shrink appropriately with `t` (so the bound holds with high probability *uniformly over time*, not just at one fixed `t`) produces exactly the `\sqrt{\ln t/N(a)}` form. The mechanics this produces: an action tried few times (`N(a)` small) gets a large bonus regardless of its current estimate, forcing exploration of under-sampled actions; as `N(a)` grows, the bonus shrinks toward zero (the `\sqrt{1/N(a)}` term), and the choice converges toward pure exploitation of `\hat{Q}(a)`. Crucially, the bonus also grows (slowly, logarithmically) with `t` for *every* action — this is what guarantees an action is never permanently written off: even a seemingly-bad action's bound eventually grows enough that it gets revisited if all other actions have been tried disproportionately more, keeping the guarantee that no action's true value goes unverified forever. UCB1 achieves `O(\log T)` cumulative regret in the standard stochastic bandit setting — provably optimal up to constants (matching the Lai-Robbins lower bound).

### Thompson sampling: exploration via posterior sampling

Maintain a Bayesian posterior over each action's expected reward — for Bernoulli rewards (click/no-click), a Beta distribution `Beta(\alpha_a,\beta_a)` per action is the natural conjugate choice, updated by `\alpha_a \mathrel{+}= 1` on success, `\beta_a \mathrel{+}= 1` on failure. At each step: sample `\theta_a \sim \text{Beta}(\alpha_a,\beta_a)` for every action, then act greedily on the *sampled* values, `a_t = \arg\max_a \theta_a`. This is the entire algorithm — no explicit bonus term to tune. Why it explores correctly: an action with a wide, uncertain posterior occasionally produces a high sampled `θ`, purely by chance, which makes it get chosen and thereby tested — exploration probability is automatically, exactly proportional to genuine remaining uncertainty, without hand-designing a bonus formula. As evidence accumulates, each posterior concentrates around the true mean, sampled values stop varying much, and the algorithm converges to pure exploitation naturally. Thompson sampling also achieves `O(\log T)` regret in standard settings, empirically often outperforming UCB despite having a less clean theoretical worst-case bound, and it's the more common choice in production ad/content bandit systems specifically because it handles delayed/batched updates and contextual features more gracefully than UCB's confidence-interval bookkeeping.

### UCB vs Thompson vs ε-greedy, compared precisely

| | ε-greedy | UCB | Thompson sampling |
|---|---|---|---|
| Exploration mechanism | Uniform random, rate `ε` | Deterministic bonus for under-sampled actions | Random sample from a posterior |
| Regret (stochastic bandit) | `O(\epsilon T)` if ε fixed; can be `O(\log T)` with a tuned decay schedule | `O(\log T)`, near-optimal | `O(\log T)`, near-optimal, often better constants in practice |
| Needs a model of uncertainty? | No — just point estimates | Yes — a confidence bound derived analytically | Yes — a full posterior distribution |
| Handles delayed/batched feedback | Trivially (no ordering assumption) | Awkward — confidence bound assumes sequential updates | Naturally — posterior update order doesn't matter |
| Extends to contextual bandits/deep RL cleanly | Yes, trivially, but with the same blind-exploration weakness | Harder — confidence bounds over a function-approximated value are not simple closed forms | Harder — full posteriors over neural net weights are expensive; addressed via ensembles/dropout-as-approximate-posterior |

### Intrinsic motivation: exploration when reward itself is the problem

All three methods above assume the environment gives *some* informative reward signal often enough that value-uncertainty-driven exploration eventually finds it. **Sparse-reward** tasks (a maze with reward only at the exit, many steps away; a robotics task that only rewards final success) break this assumption completely — a random or lightly-biased exploration policy may never stumble into the one region with nonzero reward, so there's no value signal to be uncertain *about* yet. Intrinsic motivation adds a second reward term computed from the agent's own experience, independent of task reward, specifically to solve this:

- **Count-based bonuses**: reward `\propto 1/\sqrt{N(s)}` (or a density-model-estimated pseudo-count for continuous/high-dimensional states where exact counting is impossible) — directly incentivizes visiting under-visited states, the same shrinking-bonus-with-visits idea as UCB, applied to *state coverage* rather than *action-value estimation*.
- **Curiosity / prediction error** (e.g. Pathak et al.'s Intrinsic Curiosity Module, 2017): train a forward model to predict the next state from the current state and action; reward the agent proportional to that model's *prediction error*. High error means the agent is in an unfamiliar or poorly-understood part of the environment — reward visiting it, which both explores and improves the model, shrinking future bonuses there.
- **Random Network Distillation (RND)** (Burda et al., 2018): fix a randomly-initialized, never-trained target network; train a second predictor network to match its output on states the agent visits. Novel states have high predictor error (the predictor hasn't seen them enough to match the fixed random target); this error is used as an intrinsic reward. RND sidesteps a known failure mode of prediction-error curiosity — the "noisy TV problem," where a stochastic, unpredictable part of the environment (visual noise, a TV playing static) has permanently high prediction error under a *forward dynamics* model and becomes an inexhaustible, exploitable source of fake intrinsic reward, since RND's target is a fixed deterministic function of the state, not a stochastic environment outcome, so there's nothing inherently unpredictable for the predictor to chase forever.

The total reward optimized becomes `r_{\text{total}} = r_{\text{extrinsic}} + \beta \cdot r_{\text{intrinsic}}`, with `β` a real, sensitive hyperparameter — too small and sparse-reward tasks remain unsolvable; too large and the agent can start optimizing for novelty over the actual task, a form of reward hacking specific to this setup (chasing intrinsic reward instead of task success, sometimes literally called "curiosity addiction" in the literature).

---

## Build it from scratch

ε-greedy, UCB1, and Thompson sampling on a 10-armed Bernoulli bandit, comparing cumulative regret directly — the standard testbed for making the regret differences visible and measurable:

```python
import numpy as np

class BernoulliBandit:
    def __init__(self, n_arms=10, seed=0):
        rng = np.random.default_rng(seed)
        self.true_p = rng.uniform(0.1, 0.9, size=n_arms)
        self.best_p = self.true_p.max()
        self.n_arms = n_arms

    def pull(self, a, rng):
        return float(rng.random() < self.true_p[a])

def run_eps_greedy(bandit, T=2000, eps=0.1, seed=1):
    rng = np.random.default_rng(seed)
    Q = np.zeros(bandit.n_arms)
    N = np.zeros(bandit.n_arms)
    regret = np.zeros(T)
    for t in range(T):
        a = rng.integers(bandit.n_arms) if rng.random() < eps else int(np.argmax(Q))
        r = bandit.pull(a, rng)
        N[a] += 1
        Q[a] += (r - Q[a]) / N[a]
        regret[t] = bandit.best_p - bandit.true_p[a]
    return np.cumsum(regret)

def run_ucb1(bandit, T=2000, c=2.0, seed=1):
    rng = np.random.default_rng(seed)
    Q = np.zeros(bandit.n_arms)
    N = np.zeros(bandit.n_arms)
    regret = np.zeros(T)
    for t in range(T):
        if t < bandit.n_arms:
            a = t                                    # initial round-robin to avoid N(a)=0
        else:
            bonus = c * np.sqrt(np.log(t + 1) / N)
            a = int(np.argmax(Q + bonus))
        r = bandit.pull(a, rng)
        N[a] += 1
        Q[a] += (r - Q[a]) / N[a]
        regret[t] = bandit.best_p - bandit.true_p[a]
    return np.cumsum(regret)

def run_thompson(bandit, T=2000, seed=1):
    rng = np.random.default_rng(seed)
    alpha = np.ones(bandit.n_arms)     # Beta(1,1) = uniform prior
    beta = np.ones(bandit.n_arms)
    regret = np.zeros(T)
    for t in range(T):
        samples = rng.beta(alpha, beta)
        a = int(np.argmax(samples))
        r = bandit.pull(a, rng)
        if r > 0.5:
            alpha[a] += 1
        else:
            beta[a] += 1
        regret[t] = bandit.best_p - bandit.true_p[a]
    return np.cumsum(regret)

if __name__ == "__main__":
    bandit = BernoulliBandit()
    reg_eps = run_eps_greedy(bandit)
    reg_ucb = run_ucb1(bandit)
    reg_ts = run_thompson(bandit)
    for name, reg in [("eps-greedy(0.1)", reg_eps), ("UCB1", reg_ucb), ("Thompson", reg_ts)]:
        print(f"{name:16s} cumulative regret at T=2000: {reg[-1]:.2f}")
    # Expect: eps-greedy's regret keeps growing roughly linearly late in the run
    # (still exploring known-bad arms at a fixed rate); UCB1 and Thompson should
    # show visibly slowing (sublinear, ~logarithmic) regret growth by comparison.
```

Plot `reg_eps`, `reg_ucb`, `reg_ts` against `t` (not shown here, but trivial to add) and the qualitative difference in *shape* — fixed-ε's roughly straight line vs UCB/Thompson's curve that visibly bends and flattens — is the single most convincing empirical demonstration of the `O(\epsilon T)` vs `O(\log T)` regret distinction this module is built around.

---

## How it's done in production

| Layer | What you actually use | What it adds |
|---|---|---|
| Small-scale bandits (ad ranking, pricing) | Thompson sampling with a conjugate posterior (Beta-Bernoulli, or Gaussian for continuous reward) | Handles delayed, batched, and asynchronous feedback naturally — the common real-world pattern where reward (a click, a conversion) arrives well after the action was taken |
| Contextual bandits at scale | LinUCB / contextual Thompson sampling (posterior over a linear or shallow model's weights, conditioned on context features) | Extends UCB/Thompson to the case where the "best arm" depends on a per-request context, without needing full deep RL |
| Sparse-reward deep RL | Intrinsic motivation (RND, curiosity) added to the training reward, or ensemble/bootstrapped value networks for a UCB-like signal | Makes learning tractable when task reward alone almost never fires early in training |
| LLM/agentic RL exploration | Sampling temperature, diverse rollout generation (multiple samples per prompt), sometimes entropy bonuses in the RL objective | A different, less theoretically principled substitute for classic bandit exploration in a combinatorially huge action space (`T31-rl-for-llms`) |

### Failure modes

| Symptom | Cause | Fix |
|---|---|---|
| Bandit system keeps serving a known-bad arm at a roughly constant rate indefinitely | Fixed (non-decaying) ε-greedy | Decay ε (GLIE schedule), or switch to UCB/Thompson which naturally reduce exploration of confidently-bad arms |
| Agent's intrinsic-motivation reward stays high and its behavior looks obsessive/repetitive around one part of the environment | The "noisy TV problem" — a stochastic, unpredictable environment element gives permanently high prediction error under a forward-dynamics curiosity signal | Switch to RND (fixed random target, not a stochastic environment outcome) or otherwise decouple the novelty signal from irreducible environment stochasticity |
| Task performance degrades even as intrinsic reward keeps climbing | Intrinsic reward weight `β` too high relative to task reward — agent is optimizing novelty over task success | Tune `β` down, or anneal it toward zero over training as task reward becomes reliably available |
| A/B-test-style bandit shows worse *aggregate* performance than a fixed A/B split during a promotional or seasonal spike | Posterior/confidence estimates were built on stale, pre-spike data and haven't caught up — a non-stationarity problem exploration algorithms don't automatically solve | Add explicit non-stationarity handling (discounted/windowed statistics, periodic resets, or a change-detection mechanism) — none of UCB/Thompson/ε-greedy assume a non-stationary reward distribution by default |

---

## Tradeoffs & when NOT to use it

- **Don't use fixed-ε ε-greedy in any system where exploration has real cost, without at least a decay schedule.** Its `O(T)` regret is a real, provable liability, not a theoretical footnote — every unit of time spent exploring a known-bad option indefinitely is a unit of avoidable lost reward.
- **Don't reach for UCB when feedback is delayed or arrives out of temporal order.** Its confidence-bound bookkeeping implicitly assumes a clean, sequential update process; Thompson sampling handles asynchronous/batched updates far more gracefully and is usually the better production default for that reason alone.
- **Don't add intrinsic motivation to a task that already has dense, informative reward.** It adds a real hyperparameter (`β`) and a real risk (curiosity-driven distraction from the task) for no benefit when the task reward already provides enough signal for value-uncertainty-driven exploration to work.
- **Don't assume any of these methods handle non-stationary reward distributions by default.** All the regret guarantees above are proven for *stationary* bandits; a reward distribution that shifts over time (seasonality, a changing user base, model drift) needs explicit handling — windowing, discounting old evidence, or periodic resets — layered on top.
- **When the arm/action set is small and enumerable, prefer UCB or Thompson over any deep-exploration technique** (ensembles, RND) — the latter exist specifically to handle function approximation and huge state spaces, and are unnecessary complexity when a tabular confidence bound or posterior is tractable.

---

## Interview questions

### Q1 — Why does fixed-ε ε-greedy have linear regret, and what's the standard fix?
**Answer:** With ε fixed, a constant fraction `ε` of all-time steps go to a uniformly random action regardless of how much evidence has accumulated that some actions are worse — so the expected regret per step from exploration doesn't shrink over time, and cumulative regret grows `O(\epsilon T)`, linear in the horizon. The standard fix is decaying ε toward 0 (e.g. `\epsilon_t=1/t`) under a GLIE (Greedy in the Limit with Infinite Exploration) schedule — enough exploration early to visit every action infinitely often (needed for Q-learning's convergence guarantee), converging to greedy as `t\to\infty`.
**Follow-up trap:** *"If GLIE ε-greedy can also achieve sublinear regret with the right schedule, why bother with UCB or Thompson at all?"* — getting the decay schedule right requires knowing (or guessing) the right rate in advance, whereas UCB and Thompson sampling achieve near-optimal `O(\log T)` regret automatically, adapting to the actual uncertainty in the data rather than following a fixed, hand-tuned schedule — less tuning, better worst-case guarantees.

### Q2 — Derive where UCB's confidence bonus term, `\sqrt{\ln t / N(a)}`, comes from.
**Answer:** From a Hoeffding-style concentration inequality for bounded random variables: the sample mean over `N` i.i.d. draws deviates from the true mean by more than a threshold with a probability that decays exponentially in `N` times the threshold squared. Solving for the threshold that keeps the failure probability appropriately small — and small *uniformly across all time steps*, not just one fixed `t` (requiring the failure probability to shrink with `t`) — produces a bound of the form `\sqrt{\ln t / N(a)}`: it shrinks as `N(a)` grows (more evidence, tighter bound) and grows (slowly) with `t` (guarding against ever writing off an action permanently).
**Follow-up trap:** *"What does the constant `c` in `c\sqrt{\ln t/N(a)}` actually control, practically?"* — how aggressively the algorithm explores relative to exploiting the current estimate; a larger `c` widens the confidence bound, making the algorithm more willing to try under-sampled actions even when their point estimate looks mediocre, at the cost of more short-term regret in exchange for (provably) better long-term guarantees.

### Q3 — Explain why Thompson sampling explores "automatically" without an explicit bonus term.
**Answer:** Thompson sampling maintains a full posterior distribution over each action's value and samples from it before acting; an action with a wide (uncertain) posterior occasionally produces a high sampled value purely by chance, causing it to be selected and tested. The exploration probability for any action is thus mathematically exactly the probability that a sample from its posterior exceeds samples from all other actions' posteriors — which is automatically higher for actions we know less about, with no separate bonus formula needed; the posterior's width *is* the exploration signal.
**Follow-up trap:** *"Does Thompson sampling ever stop exploring an action entirely?"* — not in principle: any action's posterior always has some probability mass everywhere, so there's always a nonzero (if vanishingly small as evidence accumulates) chance it gets sampled highest — this asymptotic "never fully zero" property is part of why it retains strong regret guarantees, similar in spirit to UCB's bonus never fully vanishing.

### Q4 — Compare the regret guarantees of ε-greedy, UCB, and Thompson sampling precisely.
**Answer:** Fixed-ε ε-greedy: `O(\epsilon T)`, linear in `T`. Decayed/GLIE ε-greedy with a well-chosen schedule: can achieve `O(\log T)` but requires tuning the schedule correctly. UCB1: `O(\log T)`, provably near the Lai-Robbins lower bound for stochastic bandits, no schedule tuning needed. Thompson sampling: also `O(\log T)` in standard settings, with a Bayesian-regret analysis showing near-optimal constants, and it frequently outperforms UCB empirically despite a less clean textbook worst-case bound.
**Follow-up trap:** *"Does 'logarithmic regret' mean the algorithm eventually stops exploring entirely?"* — no — logarithmic regret means the *rate* of regret accumulation per unit time shrinks toward zero, not that exploration literally halts; both UCB's bonus and Thompson's posterior sampling retain a nonzero (shrinking) chance of trying any action indefinitely, which is required to keep the guarantee valid against any possible true reward distribution.

### Q5 — Why doesn't UCB or Thompson sampling transfer cleanly to deep RL with a neural network value function?
**Answer:** Both rely on tractable per-action statistics — UCB needs a closed-form confidence bound derivable from a visit count and bounded-reward assumption; Thompson sampling needs an exact, updatable posterior over each action's value. Neither is naturally available for a neural network's output over a huge or continuous action space — there's no simple visit count per action in a continuous space, and computing a true Bayesian posterior over network weights (which would let you sample plausible value functions) is computationally expensive and not solved in closed form the way Beta-Bernoulli conjugacy is.
**Follow-up trap:** *"What's the practical workaround used in deep RL to approximate a UCB/Thompson-style signal?"* — bootstrapped or ensemble value networks (train several value networks on different data subsets/initializations and treat their disagreement as an uncertainty signal, sampling from one network per episode as an approximate Thompson-sampling analogue) — a genuine, used approximation, but strictly an approximation, not the same theoretical guarantee as tabular UCB/Thompson.

### Q6 — What is the "noisy TV problem" and which intrinsic motivation method specifically fixes it?
**Answer:** A curiosity signal based on the prediction error of a *forward dynamics model* (predict next state from current state and action) can be permanently, inexhaustibly high on any part of the environment that's genuinely stochastic and unpredictable (visual noise, a randomly-changing TV screen) — the model can never learn to predict noise, so the agent gets stuck maximizing "curiosity" by staring at the noise forever, a real, documented failure mode. Random Network Distillation (RND) fixes this by making the prediction target a *fixed, deterministic* function of the state (a frozen, randomly-initialized network's output), not a stochastic environment outcome — there's nothing irreducibly unpredictable about a fixed function, so the predictor's error genuinely shrinks as the agent visits and revisits states, rather than staying high forever on inherently noisy regions.
**Follow-up trap:** *"Could you fix the noisy-TV problem by just modeling aleatoric uncertainty explicitly and subtracting it out of the curiosity signal?"* — in principle yes (predicting a distribution over next states and using something like reduction in *epistemic* uncertainty specifically, rather than raw prediction error, as the reward), but this is harder to implement well and less robust in practice than RND's simpler fixed-target trick, which is why RND became the more common default despite the theoretically cleaner alternative existing.

### Q7 — Design an exploration strategy for a sparse-reward robotics task (reward only at final task success, hundreds of steps away). Walk through your reasoning.
**Testing:** synthesis under a realistic constraint.
**Answer:** Value-uncertainty-driven methods (ε-greedy, UCB, Thompson) all assume you occasionally see nonzero reward to be uncertain *about* — with reward only at a distant terminal success, early random exploration may never reach it, so none of these alone solves the problem. Add an intrinsic motivation signal (RND is a reasonable default, given it sidesteps the noisy-TV risk that real robot sensors — genuinely noisy — would otherwise trigger under simple forward-model curiosity) to reward state-space coverage directly, with the total reward `r_{ext}+\beta r_{int}` and `β` tuned (or annealed down over training) so the agent doesn't end up preferring novel-but-useless states over ultimately reaching the sparse task reward.
**Follow-up trap:** *"Your agent's intrinsic reward stays high and task success rate stays at zero after a long training run. What do you check first?"* — whether `β` is too large relative to task reward (agent genuinely prefers novelty over the task, a form of intrinsic-motivation reward hacking), and separately, whether the state representation itself makes "novel" state coverage actually correlated with getting closer to the task goal — if novelty is measured on an irrelevant part of the state (e.g. sensor noise or a visually busy but task-irrelevant background), the intrinsic signal can be high while providing zero guidance toward the actual objective.

### Q8 — A production ad-serving bandit has been running Thompson sampling for months. Suddenly, aggregate revenue drops even though the bandit hasn't been changed. What's your first hypothesis?
**Testing:** recognizing exploration algorithms don't handle non-stationarity by default.
**Answer:** The underlying reward distribution likely shifted (seasonality, a new user cohort, a competitor's pricing change, a UI change elsewhere in the product) — Thompson sampling's posterior, like UCB's confidence bound, is built on the *stationary*-bandit assumption and will keep confidently favoring arms that were good under the old distribution, taking a long time to update because the accumulated historical evidence (large `α,β` counts) makes the posterior slow to move even as new, contradicting evidence comes in.
**Follow-up trap:** *"How would you modify the algorithm to handle this, concretely?"* — discount or window the posterior update (e.g. multiply `α,β` by a decay factor `<1` before each update, so old evidence contributes less over time, effectively giving the posterior a shorter "memory"), or run periodic full resets, or add explicit change-point detection that triggers a reset when observed reward diverges significantly from what the current posterior predicts.

### Q9 — Why is exploration in LLM/agentic RL (RLHF, RLVR) considered a fundamentally different problem than classic bandit exploration, even though the framing (choose an action, observe reward, update) looks the same?
**Testing:** connecting this module forward to `T31-rl-for-llms`.
**Answer:** The "action space" in a single-response RLHF setup is the set of all possible token sequences — astronomically large and effectively continuous in practice, nowhere close to the small, enumerable arm sets UCB/Thompson sampling are designed for, and there's no tractable way to maintain a confidence bound or posterior per "arm" (per possible full response). Current practice substitutes much cruder mechanisms — sampling temperature to get response diversity, generating multiple rollouts per prompt, sometimes an entropy bonus in the training objective to discourage premature policy collapse — none of which carry the regret guarantees this module's classic methods do.
**Follow-up trap:** *"Does that mean the theory in this module is irrelevant to LLM RL?"* — not irrelevant, but not directly transferable either: the *concepts* (uncertainty-driven exploration beats blind randomness, exploration probability should reflect genuine remaining uncertainty) remain the right intuition, and some 2025-2026 research explores model-uncertainty-based exploration bonuses for agentic RL, but treat any specific claim that a UCB- or Thompson-style guarantee has been rigorously extended to this setting as unproven rather than established.

### Q10 — You're told "just increase ε, we're not exploring enough." When is this the wrong fix, and what would you check instead?
**Testing:** whether the candidate reaches for the crude lever reflexively or diagnoses first.
**Answer:** Increasing ε is the wrong fix if the actual problem is that exploration is *unfocused* rather than *insufficient in volume* — ε-greedy explores uniformly at random regardless of what's already confidently known, so raising it just wastes more budget re-testing arms you're already sure are bad, without necessarily improving coverage of the genuinely uncertain ones. Before raising ε, check whether the real issue is (a) reward sparsity, in which case intrinsic motivation is the right lever, not more random exploration, or (b) exploration that's uniform when it should be uncertainty-weighted, in which case switching to UCB or Thompson sampling (which redirect exploration toward what's actually uncertain, without needing a manually tuned exploration *rate* at all) is the structurally correct fix rather than a bigger version of the same blunt instrument.
**Follow-up trap:** *"Give a concrete symptom that would tell you it's specifically a reward-sparsity problem rather than an exploration-strategy problem."* — if the agent has visited a very wide range of states/actions (broad coverage, confirmed by logging visitation counts) but almost none of them ever produced nonzero reward, more exploration volume won't help because there's nothing informative to find more of — that's the specific signature pointing at reward sparsity (needing intrinsic motivation or reward shaping) rather than an exploration-strategy defect (needing UCB/Thompson instead of ε-greedy).

---

## Red flags that fail you

- Defaulting to "just use ε-greedy" without mentioning decay/GLIE or its linear-regret weakness.
- Not knowing UCB and Thompson sampling both achieve logarithmic regret, or why that's qualitatively different from ε-greedy's linear regret.
- Describing Thompson sampling as "random" without explaining that its randomness is calibrated to genuine posterior uncertainty.
- Recommending intrinsic motivation for a task that already has dense reward, with no acknowledgment of the added risk/complexity.
- Not knowing what the noisy-TV problem is, or which method (RND) specifically addresses it.
- Assuming any of these exploration methods handle non-stationary reward distributions without modification.
- Treating UCB/Thompson as directly usable off-the-shelf on a deep RL problem with a huge action space, without acknowledging the tractability gap.

---

## Cheat card

```
EPS-GREEDY     explore uniformly at rate eps; fixed eps -> regret O(eps*T), LINEAR
               fix: decay eps (GLIE: greedy in limit + infinite exploration) -> visits
               every (s,a) infinitely often (needed for Q-learning convergence) then -> greedy
UCB1           a_t = argmax_a [ Q_hat(a) + c*sqrt(ln(t)/N(a)) ]
               bonus derived from Hoeffding concentration bound; shrinks as N(a) grows,
               grows (slowly) with t so no action permanently written off
               regret: O(log T), near Lai-Robbins optimal, NO schedule tuning needed
THOMPSON       sample theta_a ~ posterior(a) for every action, act greedy on the SAMPLE
               Beta(alpha,beta) for Bernoulli reward; alpha+=1 success, beta+=1 failure
               exploration prob automatically = P(this posterior sample is highest)
               regret: O(log T); often beats UCB empirically; handles delayed/batched
               feedback far better than UCB's sequential confidence-bound bookkeeping
DEEP RL GAP    UCB/Thompson need tractable per-arm stats -- don't transfer to huge/continuous
               action spaces or NN value fns directly. Workaround: bootstrapped/ensemble
               Q-networks, disagreement as approximate uncertainty signal
INTRINSIC MOTIV needed when reward is SPARSE -- no signal to be uncertain about yet
  count-based    bonus ~ 1/sqrt(N(s)) or pseudo-count via density model
  curiosity      reward = forward-model prediction error -- BREAKS on stochastic envs
                 ("noisy TV problem": permanently high error on irreducible noise)
  RND            predict a FIXED random network's output; error shrinks with visits since
                 target is deterministic, not stochastic -- fixes noisy-TV problem
  total reward   r_ext + beta*r_int; beta too high -> curiosity-chasing over task (reward hacking)
NON-STATIONARY  none of UCB/Thompson/eps-greedy handle this by default -- need windowing/
               discounted posteriors/change-point detection layered on top
LLM RL         action space (token sequences) too large for UCB/Thompson; practice uses
               sampling temperature + multi-rollout diversity + entropy bonus instead (T31-rl-for-llms)
```

## Sources

- [Auer, Cesa-Bianchi & Fischer — Finite-time Analysis of the Multiarmed Bandit Problem (2002)](https://link.springer.com/article/10.1023/A:1013689704352) — UCB1 and its regret bound — accessed 2026-08-03
- [Russo, Van Roy et al. — A Tutorial on Thompson Sampling (2018)](https://arxiv.org/abs/1707.02038) — accessed 2026-08-03
- [Pathak et al. — Curiosity-driven Exploration by Self-supervised Prediction (2017)](https://arxiv.org/abs/1705.05363) — the noisy-TV problem and ICM — accessed 2026-08-03
- [Burda et al. — Exploration by Random Network Distillation (2018)](https://arxiv.org/abs/1810.12894) — accessed 2026-08-03
- [Sutton & Barto — Reinforcement Learning: An Introduction (2nd ed.), ch. 2](http://incompleteideas.net/book/the-book-2nd.html) — bandit foundations, GLIE — accessed 2026-08-03

## Changelog
- 2026-08-03 — created
