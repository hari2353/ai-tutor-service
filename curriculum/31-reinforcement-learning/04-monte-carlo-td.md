# Monte Carlo vs Temporal Difference, TD(λ), Eligibility Traces

> **Track:** T31 Reinforcement Learning · **Time:** 2.5h · **Prereqs:** T31-mdp, T31-dynamic-programming · **Updated:** 2026-08-03
> **Module id:** `T31-monte-carlo-td` · **Tags:** tabular
> **Lab:** `labs/py/31-04-monte-carlo-td/`

## The 30-second version

Monte Carlo and temporal difference are the two model-free ways to estimate `V^π` or `Q^π` from sampled experience instead of a known `P` — the thing `T31-dynamic-programming` needed and model-free RL doesn't have. MC waits until an episode ends, computes the actual observed return `G_t`, and updates `V(s_t)` toward it — unbiased (it's a direct sample of the true expectation) but high-variance (one full trajectory's worth of randomness compounds into a single number). TD updates immediately, after one step, toward `r_{t+1} + γV(s_{t+1})` — bootstrapping off its own current estimate rather than waiting for the true outcome — which is biased whenever `V` is still wrong, but low-variance, because it only depends on one transition's randomness instead of an entire trajectory's. TD(λ) and eligibility traces are the dial that interpolates continuously between these two extremes: `λ=0` recovers pure one-step TD, `λ=1` recovers Monte Carlo, and everything in between blends multi-step returns with exponentially decaying weight, usually landing at lower error than either endpoint. This bias-variance knob is the single idea the rest of tabular and deep RL keeps rediscovering — it's exactly what n-step returns and GAE (`T31-ppo`) are doing later in the track.

## Why this gets asked

Because "when would you use MC over TD, and why" is the cleanest way to test whether a candidate actually understands bias-variance tradeoffs mechanically, versus having memorized "TD is better because it's online." Interviewers who've shipped value-based RL have watched training either converge frustratingly slowly (variance too high — MC or a poorly-tuned high-λ setting) or converge fast to a confidently wrong answer (bias from bootstrapping off a badly-initialized value function early in training) and want to know you can diagnose which failure you're looking at from the symptom alone.

---

## Lineage: past → present → future

**What came before.** Dynamic programming (`T31-dynamic-programming`) requires a known model; classical Monte Carlo methods for estimating expectations (unrelated to RL specifically) go back to Ulam and von Neumann's work in the 1940s and are the natural fallback when you can sample outcomes but don't know the generating distribution in closed form. The gap DP left was obvious: almost no real environment hands you `P(s'|s,a)`. Applying plain Monte Carlo to RL — play out full episodes, average the observed returns — was a natural and correct first model-free method, but it inherited two real costs: you must wait for episode termination before learning anything (useless for continuing, non-episodic tasks, and slow even for episodic ones with long horizons), and the variance of a full-trajectory return can be enormous. Sutton's temporal-difference learning (1988) was the fix specifically for these two costs: bootstrap off your own current value estimate after just one step, so you can learn online, incrementally, before the episode ends, at far lower variance — at the well-understood cost of introducing bias while `V` is still wrong.

**Where it stands now.** TD learning (and its control variants, `T31-q-learning-sarsa`) is the dominant model-free foundation underneath essentially all deep value-based RL — DQN's loss is a TD error, squared. Pure Monte Carlo estimation survives mainly in specific corners: policy gradient's REINFORCE (`T31-policy-gradient`) is fundamentally a Monte-Carlo-return method before baselines are added, and MC-based value estimates are sometimes used as one term in a variance-reduction blend (exactly what TD(λ) and GAE do). The live, well-settled consensus is that some blend of TD and MC (n-step TD, TD(λ), GAE) essentially always beats either pure extreme empirically, which is why almost no modern deep RL algorithm uses pure `λ=0` TD or pure `λ=1` MC in isolation — they use an intermediate λ or a fixed n-step horizon, tuned per problem. What's still genuinely contested is exactly where on that spectrum to sit for a given problem — there's no closed-form answer, and it remains an empirical hyperparameter (GAE's λ in `T31-ppo` is the direct descendant of this exact knob).

**Where it's heading.** High confidence: the bias-variance blending idea (TD(λ)/GAE-style) stays central; nobody is proposing to go back to either pure extreme. Medium confidence: adaptive or learned λ (letting the tradeoff itself be tuned per-state or per-training-phase rather than a single fixed scalar) is an active research thread with some production adoption in large-scale RL systems, but a fixed, well-tuned λ remains the default outside of research settings. Eligibility traces themselves, as an *implementation mechanism* (as opposed to the underlying TD(λ) idea), have partly given way in deep RL to the mathematically related but more GPU-friendly n-step return / GAE formulations, because traces as originally formulated assume per-parameter online updates that don't map cleanly onto minibatch, replay-buffer-based deep learning — treat "eligibility traces" as the tabular-RL vocabulary for an idea that deep RL implements differently but not differently in spirit.

---

## Mental model

```
   ONE EPISODE:   s0 -a0-> s1 -a1-> s2 -a2-> s3 -a3-> ... -> s_T (terminal)
                   r1        r2        r3        r4

   MONTE CARLO:  V(s0) <- G_0 = r1 + γr2 + γ²r3 + ... + γ^(T-1)r_T
                 (wait for the WHOLE episode; target uses REAL rewards all the way to the end)

   TD(0):        V(s0) <- r1 + γV(s1)
                 (update after ONE step; target uses one real reward + a GUESS for the rest)

   TD(λ):        V(s0) <- (1-λ)Σ_{n=1}^∞ λ^(n-1) G_0^(n)     (weighted blend of ALL n-step returns)
                 λ=0 → pure TD(0)         λ=1 → pure Monte Carlo
```

Think of estimating how good a chess opening is. Monte Carlo plays the *entire game* to checkmate, then credits the opening with the final win/loss — a true, unbiased signal, but one game's worth of noise (a blunder on move 40 has nothing to do with the opening, yet it's baked into the number). TD looks one move ahead and asks its own current judgment "how good does the position look now" — faster, lower-variance, but only as trustworthy as that judgment already is, which early in training is not very.

---

## How it actually works

### Monte Carlo prediction, precisely

For each visited state `s_t` in an episode, the observed return is `G_t = \sum_{k=0}^{T-t-1}\gamma^k r_{t+k+1}` — computed only once the *whole* episode (through terminal time `T`) is known. The update, incremental-mean form:

$$V(s_t) \leftarrow V(s_t) + \alpha\left[G_t - V(s_t)\right]$$

Two variants matter operationally: **first-visit MC** updates `V(s)` using only the return following the *first* occurrence of `s` in an episode; **every-visit MC** updates using the return following *every* occurrence. Both converge to `V^π` (first-visit has a cleaner classical convergence proof via the law of large numbers on i.i.d. per-episode samples; every-visit's samples within an episode aren't independent, but it converges too and is used more often in practice for its lower variance from using more data per episode).

**Why MC is unbiased.** `G_t` is by construction a direct, literal sample of the random variable whose expectation defines `V^\pi(s) = \mathbb{E}_\pi[G_t|s_t=s]`. Averaging i.i.d. (or near-i.i.d.) samples of a random variable is the textbook unbiased estimator of its mean — `\mathbb{E}[\hat{V}(s)] = V^\pi(s)` exactly, with no approximation beyond finite-sample noise. There is no bootstrapping, no dependence on any other, possibly-wrong estimate.

**Why MC is high-variance.** `G_t` is a sum of `T-t` random rewards, each shaped by every stochastic action and transition from `t` all the way to termination. `\text{Var}(G_t)` accumulates variance contributions from every one of those steps — a long or highly stochastic episode means a single sample of `G_t` can be wildly different from another sample starting at the identical state, purely from what happened later, unrelated to how good `s_t` actually was.

### TD(0) prediction, precisely

$$V(s_t) \leftarrow V(s_t) + \alpha\underbrace{\left[r_{t+1} + \gamma V(s_{t+1}) - V(s_t)\right]}_{\text{TD error, } \delta_t}$$

The **TD target** `r_{t+1}+\gamma V(s_{t+1})` replaces the true (unknown, not-yet-observed) `G_{t+1}` with the *current estimate* `V(s_{t+1})` — this substitution is bootstrapping, and it's exactly the same substitution made inside the Bellman equation's derivation in `T31-mdp` (`G_t = r_{t+1}+\gamma G_{t+1}`, with `G_{t+1}` replaced by its expectation `V(s_{t+1})`). The update needs only `(s_t, a_t, r_{t+1}, s_{t+1})` — one transition — so it can happen immediately, online, in continuing tasks with no terminal state at all.

**Why TD is biased (while V is still wrong).** The target `r_{t+1}+\gamma V(s_{t+1})` is only an unbiased estimate of `V^\pi(s_t)` if `V(s_{t+1})` already equals the true `V^\pi(s_{t+1})`. Early in training it doesn't — `V` starts arbitrary (often all zeros) — so the target itself is systematically off by however wrong `V(s_{t+1})` currently is, and that error propagates into `V(s_t)`. This bias is not permanent: as `V` converges toward `V^π` through repeated updates, the bias shrinks toward zero (TD(0) is proven to converge to `V^π` under standard step-size conditions, via a stochastic-approximation argument related to but distinct from the DP contraction proof), but at any given point mid-training, the estimate is provably biased in a way MC's is not.

**Why TD is low-variance.** The TD target depends on exactly one sampled reward and one bootstrapped value — the randomness of everything *after* `s_{t+1}` is replaced by `V(s_{t+1})`'s point estimate rather than propagated through as raw sampled noise. You've traded "everything downstream contributes variance" for "everything downstream is summarized by (possibly wrong) `V`," which is a much smaller, much more stable source of noise per update.

### The bias-variance tradeoff, stated precisely

| | Monte Carlo (`G_t`) | TD(0) (`r_{t+1}+\gamma V(s_{t+1})`) |
|---|---|---|
| Bias | None — unbiased estimator of `V^π(s_t)` | Biased whenever `V(s_{t+1}) \ne V^\pi(s_{t+1})`, shrinking to zero as training converges |
| Variance | High — accumulates noise from every step to episode end | Low — one transition's worth of noise |
| Needs episode to end? | Yes | No — works in continuing tasks, updates online |
| Uses Markov property? | No — doesn't need it (just averages observed outcomes) | Yes — bootstrapping via `V(s_{t+1})` assumes `s_{t+1}` is a sufficient statistic |
| Convergence with function approximation | Converges to the least-squares-optimal fit even under approximation (minimizes MC error directly) | Can converge to a *different*, sometimes worse fixed point under function approximation — a real, documented failure mode, not a footnote |

That last row matters more than it looks: under linear function approximation, TD and MC provably converge to *different* solutions in general, because TD is implicitly solving a different fixed-point equation (satisfying the Bellman equation approximately) than MC (directly minimizing squared error to observed returns). This is part of why the deadly triad (`T31-rl-framing`) singles out bootstrapping as a genuine, separate risk factor from bias alone.

### N-step returns: the explicit bridge

Instead of jumping straight from 1-step TD to full-episode MC, define the **n-step return**:

$$G_t^{(n)} = r_{t+1}+\gamma r_{t+2}+\cdots+\gamma^{n-1}r_{t+n}+\gamma^n V(s_{t+n})$$

`n=1` recovers TD(0) exactly; `n\to\infty` (or `n=T-t`, running to the terminal state) recovers Monte Carlo exactly. Every intermediate `n` uses `n` real, sampled rewards (contributing variance, reducing bias) plus one bootstrapped tail (contributing bias, reducing variance) — a direct, tunable dial. Empirically, an intermediate `n` (not 1, not "all the way") frequently outperforms both extremes because it captures more of the real reward signal than 1-step TD while cutting off the variance-accumulating tail that plain MC pays for.

### TD(λ) and eligibility traces, derived

TD(λ)'s **forward view** defines the `λ`-return as an exponentially-weighted average over *all* n-step returns:

$$G_t^\lambda = (1-\lambda)\sum_{n=1}^{\infty}\lambda^{n-1}G_t^{(n)}$$

The `(1-λ)` normalizes the geometric weights `λ^{n-1}` to sum to 1 (same geometric-series fact used for discounting in `T31-mdp`). At `λ=0`: only the `n=1` term survives (`(1-0)\cdot\lambda^0 = 1`, all higher terms vanish), recovering `G_t^{(1)}` — pure TD(0). At `λ=1`: the weighting degenerates to place all weight on the full-episode return, recovering Monte Carlo exactly (a careful limit, since `λ^{n-1}\to 1` for all finite `n` as `λ\to 1`, effectively removing the exponential decay so the return is dominated by the longest, terminal-reaching term once episode length is finite). Intermediate `λ` blends smoothly, weighting near-term n-step returns more and far n-step returns exponentially less.

The forward view is conceptually clean but requires knowing the *whole future* trajectory to compute `G_t^\lambda`, defeating TD's online advantage. The **backward view**, using **eligibility traces**, achieves the mathematically equivalent update *online*, one step at a time, without waiting:

$$e_t(s) = \gamma\lambda\, e_{t-1}(s) + \mathbb{1}[s_t = s] \qquad V(s) \leftarrow V(s) + \alpha\,\delta_t\, e_t(s) \text{ for all } s$$

Mechanically: every state carries a trace `e(s)` — "how much credit does this state currently deserve for the TD error about to be computed" — that decays by `γλ` each step (so recently-visited states retain more eligibility) and gets bumped up by 1 each time that state is actually visited. When a TD error `δ_t` is computed at each step, it's distributed backward to *every* state in proportion to its current trace, not just the single most-recent state. This is why it's called the backward view: instead of one state looking forward to compute a blended return, the TD error at each step looks backward and updates every recently-visited state proportionally to how eligible it is. The forward and backward views are provably equivalent in total update over an episode for the offline (batch) case, and closely related online — this equivalence (not just an analogy) is a genuine, nontrivial result and a common "wait, why are these the same" moment.

`λ` and `γλ` decay interact: a state visited `k` steps ago has trace weight `(\gamma\lambda)^k` remaining — high `γλ` means credit propagates far back in time per TD error, approaching MC's "credit the whole trajectory" behavior; `γλ=0` means only the immediately preceding state gets credited, recovering TD(0)'s one-step locality.

---

## Build it from scratch

First-visit MC, TD(0), and tabular TD(λ) with eligibility traces, all estimating `V^π` for a fixed random policy on a small random walk — chosen because it's the textbook environment for visibly comparing convergence speed and error between the three:

```python
import numpy as np

class RandomWalk:
    """5 non-terminal states (0..4) in a line, terminals at -1 (left) and 5 (right).
    Reward +1 only for reaching the right terminal, 0 otherwise. gamma=1 (episodic)."""
    def __init__(self):
        self.n = 5

    def reset(self):
        self.s = 2   # start in the middle
        return self.s

    def step(self):
        self.s += 1 if np.random.rand() < 0.5 else -1
        if self.s == -1:
            return None, 0.0, True     # terminal, no state
        if self.s == self.n:
            return None, 1.0, True
        return self.s, 0.0, False

def mc_first_visit(env, n_episodes=200, alpha=0.05, gamma=1.0):
    V = np.full(env.n, 0.5)
    for ep in range(n_episodes):
        s = env.reset()
        trajectory = [(s, 0.0)]          # (state, reward-that-led-INTO-this-state)
        done = False
        while not done:
            s2, r, done = env.step()
            trajectory.append((s2, r))
        # trajectory = [(s0,0), (s1,r1), (s2,r2), ..., (None, r_terminal)]
        states = [t[0] for t in trajectory[:-1]]     # s0..s_{T-1} (non-terminal states)
        rewards = [t[1] for t in trajectory[1:]]      # r1..r_T, aligned so rewards[t] follows states[t]
        G = 0.0
        for t in reversed(range(len(states))):
            G = rewards[t] + gamma * G
            s_t = states[t]
            if s_t not in states[:t]:                 # first-visit check
                V[s_t] += alpha * (G - V[s_t])
    return V

def td0(env, n_episodes=200, alpha=0.05, gamma=1.0):
    V = np.full(env.n, 0.5)
    for ep in range(n_episodes):
        s = env.reset()
        done = False
        while not done:
            s2, r, done = env.step()
            target = r if done else r + gamma * V[s2]
            V[s] += alpha * (target - V[s])
            s = s2
    return V

def td_lambda(env, n_episodes=200, alpha=0.05, gamma=1.0, lam=0.7):
    V = np.full(env.n, 0.5)
    for ep in range(n_episodes):
        s = env.reset()
        e = np.zeros(env.n)                # eligibility traces, reset each episode
        done = False
        while not done:
            s2, r, done = env.step()
            target_next_V = 0.0 if done else V[s2]
            delta = r + gamma * target_next_V - V[s]
            e *= gamma * lam                # decay all traces
            e[s] += 1.0                     # bump the just-visited state
            V += alpha * delta * e          # update ALL states, weighted by eligibility
            s = s2
    return V

TRUE_V = np.array([1/6, 2/6, 3/6, 4/6, 5/6])   # known closed-form solution for this env

if __name__ == "__main__":
    np.random.seed(0)
    v_mc = mc_first_visit(RandomWalk())
    v_td = td0(RandomWalk())
    v_lam = td_lambda(RandomWalk(), lam=0.7)
    for name, v in [("MC", v_mc), ("TD(0)", v_td), ("TD(0.7)", v_lam)]:
        rmse = np.sqrt(np.mean((v - TRUE_V) ** 2))
        print(f"{name:8s} RMSE={rmse:.4f}  V={np.round(v,3)}")
    # Expect TD(0) to typically reach lower RMSE than MC at this alpha/episode count
    # (lower variance dominates at moderate sample sizes); TD(lambda) with a well-chosen
    # lambda often does best of all -- run with different seeds to see the variance itself.
```

The `TRUE_V` values here are the known closed-form solution for this specific random walk (derivable directly from the Bellman equation, `T31-mdp`, since it's a small enough MDP to solve exactly), which makes this a genuine, checkable comparison rather than a vibes-based one. Run with several random seeds and log the RMSE distribution, not just one run — MC's higher variance should show up as a wider spread of RMSE across seeds even when its average error is comparable to TD's.

---

## How it's done in production

| Layer | What you actually use | What it adds |
|---|---|---|
| Tabular / small-scale | TD(0) or TD(λ) directly, as above | Rarely deployed at scale unmodified; mainly pedagogical and for small structured problems |
| Deep value-based RL | TD(0)-style targets with a target network (`T31-dqn`) | The bootstrapped target is the same idea, computed with a neural net instead of a table, plus target-network stabilization for the non-stationarity this introduces |
| Deep policy-gradient / actor-critic | N-step returns or GAE (Generalized Advantage Estimation, `T31-ppo`) | GAE *is* TD(λ)'s bias-variance blending idea applied to the *advantage* estimate instead of the value estimate directly — same math, different target quantity |
| Distributed / replay-buffer-based systems | N-step returns computed at replay-buffer construction time (Rainbow, Ape-X) rather than online eligibility traces | Traces assume sequential online updates; replay buffers break that assumption, so systems that sample randomly from a buffer use precomputed fixed-n-step targets instead |

### Failure modes

| Symptom | Cause | Fix |
|---|---|---|
| Value estimates are noisy, don't stabilize across runs with identical hyperparameters | Pure Monte Carlo (or λ too close to 1) on a long or highly stochastic episode | Lower λ, or switch toward TD(0)/small-n n-step returns to cut variance |
| Value estimates converge fast but are consistently, systematically wrong in one direction | TD bias not yet washed out — bootstrapping off a badly initialized or still-training `V`, especially early in training or after a distribution shift | Don't over-trust value estimates in the first N updates; consider λ closer to 1 temporarily, or better initialization |
| TD(λ) with eligibility traces gives wildly different results than the equivalent n-step-return implementation | Trace decay applied in the wrong place (decaying before vs after the increment; using `λ` instead of `γλ` for the decay) or traces not reset at episode boundaries | Match the exact `e_t(s) = \gamma\lambda e_{t-1}(s) + \mathbb{1}[s_t=s]` update order, and explicitly zero traces on `reset()` |
| Deep RL training with n-step returns from a replay buffer is unstable in a way tabular TD(λ) never was | N-step returns computed off-policy from stale, buffered transitions are a biased estimate of the *current* policy's return (a real, separate off-policy correction problem) | Either use short n, or apply an off-policy correction (importance sampling, or accept it as an approximation as Rainbow/Ape-X do) |

---

## Tradeoffs & when NOT to use it

- **Don't use pure Monte Carlo for continuing (non-episodic) tasks.** It structurally can't produce an update before the episode ends, and continuing tasks may never end — TD is the only option in this setting, not a preference.
- **Don't use pure Monte Carlo when episodes are long or highly stochastic and you need many updates quickly.** The variance cost compounds directly with episode length and stochasticity; TD's online, low-variance updates will generally get you a usable value function faster in wall-clock terms even though each individual update is biased.
- **Don't default to TD(0) either, without checking whether a small n-step or moderate λ helps.** Pure one-step TD's bias can be a real problem when `V` is far from converged (early training, or after any distribution shift), and empirically an intermediate blend nearly always beats either pure extreme — treat λ (or n) as a hyperparameter worth tuning, not a binary choice.
- **Eligibility traces specifically are awkward with replay buffers and minibatch training** — they assume sequential, online, single-trajectory updates. In modern deep RL, reach for precomputed n-step returns or GAE instead of literal traces when training off a buffer.
- **Under function approximation, remember TD and MC can converge to different fixed points.** If you're debugging an approximate value function that "looks stable but wrong," check whether that's an expected consequence of the TD fixed point differing from the least-squares MC fit, not necessarily a bug.

---

## Interview questions

### Q1 — In one sentence each: why is Monte Carlo unbiased, and why is TD(0) biased?
**Answer:** MC's target `G_t` is by construction a direct sample of the exact random variable whose expectation defines `V^π(s)`, so averaging samples is an unbiased estimator with no approximation. TD(0)'s target `r_{t+1}+\gamma V(s_{t+1})` substitutes the current, possibly-still-wrong estimate `V(s_{t+1})` for the true (unobserved) continuation, so the target itself carries whatever error `V(s_{t+1})` currently has.
**Follow-up trap:** *"Does TD's bias ever fully disappear?"* — yes, asymptotically, as `V` converges to `V^π` under standard step-size conditions the bootstrapped target becomes correct in expectation and TD converges to the true `V^π`; the bias is a property of *training-time* estimates, not a permanent limitation of the method.

### Q2 — Why does MC have higher variance than TD, mechanically — not just "because it's longer"?
**Answer:** `G_t` sums `T-t` random rewards, and its variance accumulates contributions from every stochastic action and transition between `t` and termination. TD's target replaces everything after the very next state with a single point estimate `V(s_{t+1})`, so its variance comes from only one transition's randomness (the immediate reward and the one-step transition), not the whole remaining trajectory.
**Follow-up trap:** *"So does that mean TD's target is always 'more accurate' than MC's?"* — no — lower variance and unbiasedness are different properties; TD trades bias for variance, it doesn't strictly dominate MC in accuracy. Early in training, when `V` is far from correct, TD's bias can make its estimates worse than MC's despite the lower variance, which is exactly why the bias-variance tradeoff is a real tradeoff and not a free win.

### Q3 — Derive the n-step return and show that it recovers TD(0) and MC as special cases.
**Answer:** `G_t^{(n)} = r_{t+1}+\gamma r_{t+2}+\cdots+\gamma^{n-1}r_{t+n}+\gamma^n V(s_{t+n})` — `n` real sampled rewards plus a bootstrapped tail. At `n=1`: `G_t^{(1)}=r_{t+1}+\gamma V(s_{t+1})`, exactly TD(0)'s target. At `n=T-t` (running all the way to termination), the bootstrap term `\gamma^n V(s_{t+n})` either vanishes (terminal states have value 0) or isn't needed, and the sum becomes the full observed return — exactly `G_t` from Monte Carlo.
**Follow-up trap:** *"Why might an intermediate n (say n=4) beat both n=1 and n=∞ in practice?"* — it captures more real reward signal than n=1 (reducing bias) while cutting off the long variance-accumulating tail that n=∞ pays for — empirically this middle ground frequently has lower total error than either endpoint, which is the entire motivation for TD(λ)'s continuous version of the same idea.

### Q4 — Derive the TD(λ) forward-view return and show it reduces to TD(0) at λ=0 and MC at λ=1.
**Answer:** `G_t^\lambda = (1-\lambda)\sum_{n=1}^\infty \lambda^{n-1} G_t^{(n)}`, an exponentially-weighted average over all n-step returns, normalized so weights sum to 1 (geometric series). At `λ=0`: `(1-0)\lambda^0=1` for `n=1` and 0 for all `n>1` (since `0^{n-1}=0`), so only `G_t^{(1)}` survives — TD(0) exactly. At `λ=1`: the geometric decay `λ^{n-1}` disappears (stays 1 for all finite n), and for a finite episode the weighting effectively concentrates on the return that runs to termination, recovering MC.
**Follow-up trap:** *"What's the practical problem with computing G_t^λ directly via this forward-view formula?"* — it requires the full future trajectory (all n-step returns up to termination) before you can compute the update for time `t`, which defeats TD's whole advantage of updating online without waiting — this is exactly why the backward view (eligibility traces) exists, as a mathematically equivalent way to get the same total update without needing to see the future.

### Q5 — Explain eligibility traces: what do they track, and how do they let TD(λ) update online?
**Answer:** Each state maintains a trace `e(s)` that decays by `γλ` every step and is incremented by 1 whenever that state is visited: `e_t(s)=\gamma\lambda e_{t-1}(s)+\mathbb{1}[s_t=s]`. At every step, the TD error `δ_t` computed from the current transition is distributed backward to *all* states in proportion to their current trace: `V(s)\leftarrow V(s)+\alpha\delta_t e_t(s)` for every `s`. This lets recently-visited states get credited for a TD error discovered later, without needing to know the future — the "looking forward to compute a blended return" of the forward view becomes "looking backward from each new TD error to update everything still eligible."
**Follow-up trap:** *"What happens to a state's trace if it's revisited before it's fully decayed?"* — the increment `+1` adds on top of whatever trace remains from the decay, so a state visited twice in quick succession accumulates a higher trace than one visited once — this is the "accumulating traces" variant; a "replacing traces" variant instead resets the trace to exactly 1 on revisit rather than adding, which behaves differently (and often better) when states are revisited frequently within an episode.

### Q6 — Under linear function approximation, do TD and MC converge to the same fixed point? Why does this matter?
**Answer:** No, in general they converge to different fixed points. MC directly minimizes mean-squared error between the function approximator's output and the observed returns — a standard least-squares fit. TD instead converges to the fixed point of the *projected* Bellman equation (its target itself depends on the approximator, so it's solving a different, self-referential equation), which is not generally the same minimizer as the direct MC least-squares fit. This matters because it means "TD converged" and "TD converged to the best possible approximation of `V^π`" are not the same claim once you leave the tabular setting.
**Follow-up trap:** *"Is this difference the deadly triad, or something separate?"* — it's related but distinct: the deadly triad is about *divergence risk* (training might not converge at all) when function approximation, bootstrapping, and off-policy learning combine; this TD-vs-MC fixed-point difference is about *what you converge to* even in the on-policy, stable case — a genuinely different and more subtle issue than outright divergence.

### Q7 — Your value function's estimates look stable across training but are wrong in a consistent direction. What's your first hypothesis, and how do you test it?
**Testing:** diagnosing bias vs variance from a symptom, not from code.
**Answer:** First hypothesis: TD bias that hasn't washed out, likely from bootstrapping off a poor early value initialization or a real non-stationarity (a moving policy) that keeps refreshing the bias faster than it decays. Test by comparing against a small-sample Monte Carlo estimate on the same states — if MC (unbiased but noisy) roughly agrees with TD's *direction* of error over many episodes, it confirms a systematic issue rather than TD-specific bias; if TD is consistently offset from MC's average in one direction, that's the signature of unwashed bootstrapping bias.
**Follow-up trap:** *"MC agrees with TD almost exactly, but both are wrong compared to a known ground truth. What does that rule out?"* — it rules out TD-specific bias as the cause (since MC, which has none, shows the same error) and points instead at something upstream and shared — a wrong reward function, a non-Markov state representation, or a genuinely wrong environment model, not a TD-vs-MC estimation issue at all.

### Q8 — Why do modern deep RL systems using replay buffers (Rainbow, Ape-X) use precomputed n-step returns instead of literal eligibility traces?
**Answer:** Eligibility traces are inherently sequential and online — they assume you update states in the order visited, along one continuous trajectory, decaying and accumulating step by step. Replay buffers store individual transitions (or short n-step segments) and sample them randomly out of order for minibatch training, which breaks the sequential-update assumption traces are built on. Precomputing a fixed n-step return at the time each transition is stored in the buffer sidesteps this entirely — the n-step target is just a number attached to that transition, independent of sampling order.
**Follow-up trap:** *"Does using n-step returns sampled from a replay buffer introduce any bias that pure online TD(λ) wouldn't have?"* — yes: transitions in the buffer were generated by an older version of the policy, so the n intermediate actions in an n-step return may not match what the *current* policy would have done — an off-policy mismatch that grows with n. This is why most systems keep n small (often 3-5) rather than pushing toward full-episode returns, trading some of the bias-reduction benefit of larger n against this off-policy staleness cost.

### Q9 — Give a concrete production scenario where you'd deliberately choose λ close to 1 despite the variance cost.
**Answer:** Sparse-reward tasks where most transitions carry zero reward and the informative signal only arrives rarely (e.g., a long robotic assembly task that only rewards final success) — one-step TD's bootstrap can take a very long time to propagate a rare terminal reward backward one step per update per episode, while a higher λ (or larger n) directly incorporates several real steps of the trajectory into each update, propagating sparse reward signal backward faster in wall-clock training time despite the added variance.
**Follow-up trap:** *"Isn't that exactly the situation where variance is most dangerous, since episodes are long?"* — yes, and that's the real tradeoff, not a reason to avoid higher λ automatically: the fix is usually pairing higher λ with variance-reduction elsewhere (larger batch sizes, baseline subtraction in the policy-gradient case, `T31-policy-gradient`) rather than reflexively defaulting to λ=0 and accepting slow credit propagation instead.

### Q10 — Explain how GAE in PPO is "the same idea" as TD(λ), applied to a different quantity.
**Testing:** synthesis, connecting this module forward to `T31-ppo`.
**Answer:** GAE (Generalized Advantage Estimation) computes the *advantage* `A(s,a)=Q(s,a)-V(s)` as an exponentially-weighted average over n-step advantage estimates, using a parameter (also called `λ`) that plays the identical structural role as TD(λ)'s `λ`: at `λ=0` it reduces to the single-step TD-error-based advantage estimate (low variance, biased), and as `λ→1` it approaches a Monte-Carlo-style full-trajectory advantage estimate (unbiased, high variance). It's literally the same exponentially-decayed blending formula, just applied to advantage terms built from TD errors rather than directly blending n-step value-function returns.
**Follow-up trap:** *"If it's the same idea, why does PPO need its own separate name (GAE) instead of just calling it TD(λ) for advantages?"* — because the object being estimated (advantage, a difference of two value quantities used to scale a policy gradient) and the downstream use (weighting a log-probability gradient rather than directly updating a value table) are different enough that GAE's derivation and its role inside the actor-critic/policy-gradient objective (`T31-policy-gradient`, `T31-ppo`) deserve their own treatment — but recognizing the shared bias-variance-blending DNA is exactly the connection an interviewer is checking for.

---

## Red flags that fail you

- Saying "TD is always better than MC" or vice versa, without naming the bias-variance tradeoff.
- Claiming Monte Carlo can be used online, before an episode terminates.
- Describing TD's bias as permanent rather than something that shrinks as `V` converges.
- Not knowing that TD and MC can converge to different fixed points under function approximation.
- Confusing the forward view (needs the future) with the backward view (eligibility traces, online) or claiming they're unrelated rather than provably equivalent.
- Being unable to state what `λ=0` and `λ=1` reduce to in TD(λ).
- Not connecting this module's bias-variance blend to GAE when asked, in a PPO-adjacent conversation.

---

## Cheat card

```
MC TARGET     G_t = full observed return (wait for episode end)
              unbiased (direct sample of E[G_t|s_t=s]); HIGH variance (accumulates over
              whole trajectory); doesn't need Markov property; can't be used online
TD(0) TARGET  r_{t+1} + gamma*V(s_{t+1})   (bootstrap after ONE step)
              biased while V != V^pi (shrinks to 0 as V converges); LOW variance
              (one transition's noise only); works online, in continuing tasks
BIAS-VAR      MC: no bias, high var.  TD: bias (transient), low var.  Neither dominates.
FN APPROX     TD and MC converge to DIFFERENT fixed points under linear function
              approximation (TD solves projected Bellman eq; MC = least-squares fit)
N-STEP RETURN G_t^(n) = r_{t+1}+...+gamma^(n-1)r_{t+n} + gamma^n V(s_{t+n})
              n=1 -> TD(0);  n=T-t (to terminal) -> MC
TD(lambda)    G_t^lambda = (1-lambda) * sum_n lambda^(n-1) * G_t^(n)
              lambda=0 -> TD(0);  lambda=1 -> MC  (forward view; needs future traj)
ELIG TRACE    e_t(s) = gamma*lambda*e_{t-1}(s) + 1[s_t=s]   (backward view, ONLINE)
              update ALL states: V(s) += alpha * delta_t * e_t(s)
              forward/backward views PROVABLY EQUIVALENT (offline case exactly, online closely)
REPLAY BUFFER traces don't fit random-order minibatch sampling -> use precomputed
              fixed n-step returns instead (Rainbow, Ape-X); n small (3-5) to limit
              off-policy staleness of intermediate actions
GAE           = TD(lambda) applied to ADVANTAGE estimates instead of value estimates;
              same lambda-weighted blend, same bias-variance knob (T31-ppo)
```

## Sources

- [Sutton & Barto — Reinforcement Learning: An Introduction (2nd ed.), ch. 5-7, 12](http://incompleteideas.net/book/the-book-2nd.html) — canonical MC/TD/TD(λ) and eligibility trace treatment — accessed 2026-08-03
- [Sutton, R. — Learning to Predict by the Methods of Temporal Differences (1988)](https://link.springer.com/article/10.1007/BF00115009) — origin paper for TD learning and the random walk example — accessed 2026-08-03
- [Q-Learning Interview Questions (2026)](https://github.com/Devinterview-io/q-learning-interview-questions) — accessed 2026-08-03
- [100+ Reinforcement Learning Interview Questions and Answers (2026)](https://www.wecreateproblems.com/interview-questions/reinforcement-learning-interview-questions) — accessed 2026-08-03

## Changelog
- 2026-08-03 — created
