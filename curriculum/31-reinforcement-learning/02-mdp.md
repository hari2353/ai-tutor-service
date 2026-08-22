# MDPs: States, Actions, Transitions, Discounting, Bellman Equations Derived

> **Track:** T31 Reinforcement Learning · **Time:** 3h · **Prereqs:** T31-rl-framing · **Updated:** 2026-08-03
> **Module id:** `T31-mdp` · **Tags:** fundamentals, critical

## The 30-second version

A Markov Decision Process is the tuple `(S, A, P, R, γ)` — states, actions, a transition kernel `P(s'|s,a)`, a reward function `R(s,a,s')`, and a discount `γ ∈ [0,1)` — and it's the *entire* mathematical object every RL algorithm in this track is trying to solve. The value functions `V^π(s)` and `Q^π(s,a)` are defined as expected discounted return, and because return has a recursive structure (`G_t = r_{t+1} + γG_{t+1}`), the value functions satisfy the Bellman expectation equations — not by assumption, by algebra, straight from linearity of expectation. Swap "expectation under `π`" for "max over `a`" and you get the Bellman optimality equations, whose unique fixed point is the optimal value function `V*` — unique because the Bellman optimality operator is a γ-contraction in the max-norm, which is also the one-paragraph reason value iteration and Q-learning are guaranteed to converge. Everything from dynamic programming through DQN is one of two things: a way to compute or approximate this fixed point when you know the model, or a way to learn it from samples when you don't.

## Why this gets asked

Because "explain the Bellman equation" is the single most common RL interview question, and the near-universal failure mode is reciting the formula without being able to derive it — which means the candidate can't debug it when an implementation is subtly wrong (off-by-one on the discount, using `s` instead of `s'` in the reward, forgetting the max is over `a'` not `a`). Interviewers who've shipped RL have debugged exactly these off-by-ones at 2am and want to know you'd catch them by re-deriving from the recursive definition of return rather than pattern-matching a memorized formula. It's also the module that separates "knows RL vocabulary" from "can prove why value iteration converges," which staff-level RL interviews increasingly probe directly.

---

## Lineage: past → present → future

**What came before.** The MDP formalism comes from Richard Bellman's work on dynamic programming in the 1950s, developed for deterministic optimal control (aerospace trajectory optimization, resource allocation) where the "state" was a physical quantity and the goal was minimizing a cost-to-go. The pain Bellman's principle of optimality solved was combinatorial explosion: naively evaluating every possible sequence of decisions over a horizon `T` with `|A|` choices per step costs `O(|A|^T)`; Bellman's insight — an optimal policy from any state onward is optimal regardless of how you got there — lets you solve the whole problem by solving `|S|` much smaller subproblems and combining them, collapsing exponential search into polynomial dynamic programming. Markov's own contribution (1906, Markov chains) supplied the "memoryless" structural assumption that makes this decomposition valid: if the future depends on the past only through the present state, you never need to carry history forward.

**Where it stands now.** The MDP is the unchallenged formal substrate for essentially all of RL — nobody has proposed a materially different foundational object that displaced it, though POMDPs (partial observability) and constrained MDPs (safety/budget constraints via a Lagrangian) are standard, well-understood extensions rather than replacements. What's live is not the formalism but the *scale* at which it's solved: exact dynamic programming (`T31-dynamic-programming`) requires enumerable states and a known `P`, which real problems essentially never provide, so almost all deployed RL is approximate — learned value functions (`T31-monte-carlo-td` onward) or approximated planning (`T31-model-based`). The other live thread is how the Bellman equation itself gets *stretched*: reward models in RLHF (`T31-rl-for-llms`) are typically single-step or few-step MDPs where the "state" is a prompt-plus-partial-response, which is a much shorter-horizon object than a robotics or game MDP, and understanding that the same equations apply at a completely different timescale is part of what makes `T31-rl-for-llms` make sense later.

**Where it's heading.** High confidence: the MDP formalism itself is stable and will remain the reference object — it's math, not an engineering trend. Medium confidence: more RL-adjacent systems are moving toward treating the "state" as learned/latent representations (world models, `T31-model-based`) rather than hand-engineered features, which doesn't change the Bellman structure but changes what's practical to compute exactly vs approximate. Speculative: research into non-discounted or average-reward formulations for very-long-horizon or continuing agentic tasks (an LLM agent operating indefinitely) is active but not yet a settled alternative to discounted return in practice — treat `γ`-discounting as the default you should be able to justify deviating from, not the other way around.

---

## Mental model

```
                    ┌─────────────────────────────────────────┐
                    │              STATE  s                    │
                    └───────────────────┬───────────────────────┘
                                         │ agent picks a ~ π(·|s)
                                         ▼
                    ┌─────────────────────────────────────────┐
                    │   ENVIRONMENT applies P(s'|s,a),          │
                    │   emits reward R(s,a,s')                  │
                    └───────────────────┬───────────────────────┘
                                         │
                        branches over all possible s' with prob P(s'|s,a)
                    ┌────────────┬───────┴────────┬────────────┐
                    ▼            ▼                 ▼            ▼
                  s'_1         s'_2              s'_3         s'_4
                (recurse: same structure from each s', discounted by γ)
```

`V(s)` is "how good is it to be in state `s`, averaged over everything that could happen from here on, weighted by how likely and how soon." The Bellman equation is just this tree written as an equation: the value of the root equals the immediate reward plus `γ` times the (probability-weighted) value of the children — which is a recursive definition because each child is the root of an identical subtree.

---

## How it actually works

### The MDP tuple, precisely

- **States `S`**: finite or continuous set. Must satisfy the Markov property — `P(s_{t+1}|s_t,a_t) = P(s_{t+1}|s_0,a_0,\dots,s_t,a_t)` — the present screens off the past.
- **Actions `A`**: available choices, possibly state-dependent (`A(s)`).
- **Transition kernel `P(s'|s,a)`**: the environment's dynamics, `P: S \times A \times S \to [0,1]`, `\sum_{s'} P(s'|s,a) = 1` for every `s,a`.
- **Reward function `R(s,a,s')`** (or the simpler `R(s,a)` = expectation over `s'`): the scalar payoff. Where you place the reward's dependence (on `s`, on `(s,a)`, on `(s,a,s')`) is a real modeling choice, not cosmetic — a reward that depends on `s'` can encode "reward for arriving somewhere," which `R(s,a)` alone cannot.
- **Discount `γ ∈ [0,1)`**: weights future reward.

### Discounting, derived, not asserted

The return is `G_t = \sum_{k=0}^{\infty} \gamma^k r_{t+k+1}`. Two questions deserve derivation, not assertion: *why does this sum converge*, and *what does γ actually mean*.

**Convergence.** If rewards are bounded, `|r_t| \le R_{\max}` for all `t`, then:

$$|G_t| = \left|\sum_{k=0}^{\infty}\gamma^k r_{t+k+1}\right| \le \sum_{k=0}^{\infty}\gamma^k R_{\max} = R_{\max}\sum_{k=0}^{\infty}\gamma^k = \frac{R_{\max}}{1-\gamma}$$

using the geometric series formula, valid because `0 \le \gamma < 1`. This is why `γ` must be strictly less than 1 for continuing (non-episodic) tasks: at `γ=1` the geometric series doesn't converge and an infinite-horizon return can be unbounded for any policy earning non-zero average reward, making policies impossible to compare by return alone. `γ=1` is fine *only* when the task is guaranteed to terminate (episodic, with an absorbing terminal state contributing 0 further reward).

**What γ means, derived.** Consider an alternative formulation: at every step, with probability `1-γ` the "task" ends right now (a random horizon), and with probability `γ` it continues. The expected return under this random-horizon model is:

$$\mathbb{E}[G_t] = \sum_{k=0}^{\infty} P(\text{survive } k \text{ steps}) \cdot r_{t+k+1} = \sum_{k=0}^{\infty}\gamma^k r_{t+k+1}$$

identical to the discounted sum. So `γ` is not merely "a knob that shrinks future rewards" — it is exactly equivalent to believing the episode has a `1-γ` chance of ending at every timestep, i.e. an expected remaining horizon of `1/(1-γ)` steps. `γ=0.99` means "the agent should plan roughly 100 steps ahead"; `γ=0.9` means roughly 10. This is the number you use to sanity-check a hyperparameter choice against your task's actual horizon — a robot control task with meaningful 500-step dependencies picked with `γ=0.9` is structurally unable to represent that dependency, no matter how well it's trained.

### Value functions, defined

$$V^\pi(s) = \mathbb{E}_\pi\left[G_t \mid s_t = s\right] \qquad Q^\pi(s,a) = \mathbb{E}_\pi\left[G_t \mid s_t = s, a_t = a\right]$$

`V^π` is "expected return starting from `s`, thereafter following `π`." `Q^π` is the same but with the *first* action pinned to `a`, thereafter following `π`. The relationship between them: `V^\pi(s) = \sum_a \pi(a|s) Q^\pi(s,a)` — the state's value is the action-value averaged over the policy's own action distribution. This identity is used constantly (actor-critic methods estimate `Q` and derive advantage `A = Q - V` from it, `T31-policy-gradient`).

### The Bellman expectation equation, derived from scratch

Start from the definition of `G_t` and its one-step recursive structure:

$$G_t = r_{t+1} + \gamma r_{t+2} + \gamma^2 r_{t+3} + \cdots = r_{t+1} + \gamma\left(r_{t+2} + \gamma r_{t+3} + \cdots\right) = r_{t+1} + \gamma G_{t+1}$$

This is pure algebra — factor `γ` out of every term past the first. Now substitute into the definition of `V^π`:

$$V^\pi(s) = \mathbb{E}_\pi[G_t \mid s_t = s] = \mathbb{E}_\pi[r_{t+1} + \gamma G_{t+1} \mid s_t = s]$$

By linearity of expectation, split the sum:

$$V^\pi(s) = \mathbb{E}_\pi[r_{t+1} \mid s_t=s] + \gamma\,\mathbb{E}_\pi[G_{t+1} \mid s_t=s]$$

Now expand each expectation by conditioning on the action and the next state, using the law of total expectation over the policy's action distribution and the environment's transition kernel:

$$\mathbb{E}_\pi[r_{t+1}\mid s_t=s] = \sum_a \pi(a|s) \sum_{s'} P(s'|s,a)\, R(s,a,s')$$

For the second term, the key step: `\mathbb{E}_\pi[G_{t+1} \mid s_t=s]` conditions on being in `s` at time `t`, but by the **Markov property**, once we know `s_{t+1}=s'`, everything about the future (including `G_{t+1}`) is independent of how we got to `s'` — so `\mathbb{E}_\pi[G_{t+1} \mid s_{t+1}=s'] = V^\pi(s')` exactly, by definition of `V^π`. This is the step where the Markov property is *used*, not just assumed — without it, `\mathbb{E}[G_{t+1}|s_t=s]` would depend on the whole history through `s`, and `V^π(s')` alone wouldn't capture it. So:

$$\mathbb{E}_\pi[G_{t+1}\mid s_t=s] = \sum_a \pi(a|s) \sum_{s'} P(s'|s,a)\, V^\pi(s')$$

Combining both terms gives the **Bellman expectation equation for `V`**:

$$\boxed{V^\pi(s) = \sum_a \pi(a|s) \sum_{s'} P(s'|s,a)\left[R(s,a,s') + \gamma V^\pi(s')\right]}$$

The identical derivation, pinning the first action instead of averaging over `π`, gives the **Bellman expectation equation for `Q`**:

$$Q^\pi(s,a) = \sum_{s'} P(s'|s,a)\left[R(s,a,s') + \gamma \sum_{a'} \pi(a'|s') Q^\pi(s',a')\right]$$

Notice the inner sum is exactly `V^π(s') = \sum_{a'}\pi(a'|s')Q^\pi(s',a')` from the identity above — so `Q^\pi(s,a) = \sum_{s'}P(s'|s,a)[R(s,a,s') + \gamma V^\pi(s')]`, a cleaner equivalent form worth recognizing on sight.

### The Bellman optimality equation, derived from the expectation equation

Define `V^*(s) = \max_\pi V^\pi(s)` — the best achievable value from `s` under any policy. The claim: the optimal policy, in any state, should pick the action that maximizes the *right-hand side* of the Bellman equation rather than average over some `π`. Here's why, precisely: for a fixed policy `π`, the Bellman expectation equation says `V^\pi(s) = \sum_a \pi(a|s) Q^\pi(s,a)` — a weighted average of `Q^π(s,a)` over actions. Any weighted average is upper-bounded by its maximum term. So for *any* policy `π`:

$$V^\pi(s) = \sum_a \pi(a|s)Q^\pi(s,a) \le \max_a Q^\pi(s,a)$$

with equality iff `π` puts all its probability mass on `\arg\max_a Q^\pi(s,a)` — i.e., iff `π` is greedy with respect to its own `Q^π`. This is the seed of the policy improvement theorem used in `T31-dynamic-programming`. Applying this at the optimum, where by definition no policy does better, forces `V^*` to satisfy equality with the max rather than an average:

$$\boxed{V^*(s) = \max_a \sum_{s'} P(s'|s,a)\left[R(s,a,s') + \gamma V^*(s')\right]}$$

and correspondingly:

$$\boxed{Q^*(s,a) = \sum_{s'} P(s'|s,a)\left[R(s,a,s') + \gamma \max_{a'} Q^*(s',a')\right]}$$

The crucial structural difference from the expectation equation: the optimality equation is a **system of nonlinear equations** (because of the `max`), whereas the expectation equation for a *fixed* `π` is **linear** in `V^π` and can in principle be solved directly by matrix inversion, `V^\pi = (I - \gamma P^\pi)^{-1} R^\pi`, for small enough `|S|`. The `max` is what forces iterative methods (value iteration, policy iteration) instead of a closed form — this is the one-sentence reason `T31-dynamic-programming` needs an algorithm at all rather than solving a linear system once.

### Why value iteration converges: the contraction argument

Define the **Bellman optimality operator** `T` acting on any value function `V`: `(TV)(s) = \max_a \sum_{s'}P(s'|s,a)[R(s,a,s') + \gamma V(s')]`. `V^*` is by definition a fixed point of `T` (`TV^* = V^*`, directly from the boxed equation above). The convergence guarantee comes from showing `T` is a **γ-contraction in the max-norm** `\|V\|_\infty = \max_s |V(s)|`:

$$\|TV_1 - TV_2\|_\infty \le \gamma \|V_1 - V_2\|_\infty$$

Sketch: for any `s`, `(TV_1)(s) - (TV_2)(s) = \max_a[\dots V_1 \dots] - \max_a[\dots V_2 \dots]`. Using the fact that `|\max_a f(a) - \max_a g(a)| \le \max_a|f(a)-g(a)|` (the max operator is itself non-expansive), this reduces to bounding `\gamma\sum_{s'}P(s'|s,a)|V_1(s')-V_2(s')| \le \gamma \max_{s'}|V_1(s')-V_2(s')| = \gamma\|V_1-V_2\|_\infty`, since `P(s'|s,a)` sums to 1 and a probability-weighted average is bounded by the max. Because `γ<1`, `T` strictly shrinks distance between any two value functions on every application. By the **Banach fixed-point theorem**, a contraction on a complete metric space has a *unique* fixed point, and iterating `T` from *any* starting `V_0` converges to it: `T^n V_0 \to V^*` as `n\to\infty`, geometrically, at rate `γ^n`. This single argument is why value iteration (`T31-dynamic-programming`) is guaranteed to converge to the unique optimum regardless of initialization, and it's the mathematical ancestor of every convergence claim made about TD learning and Q-learning later in this track.

---

## Build it from scratch

A tiny MDP, its Bellman expectation equation solved exactly (linear system), and a hand-check against the optimality equation — deliberately small enough to verify by hand:

```python
import numpy as np

# 2-state MDP: s0 (start), s1 (goal, absorbing). Action 'stay' or 'go'.
# From s0: 'go' -> s1 w.p. 0.8 (reward +10), stays at s0 w.p. 0.2 (reward -1)
#          'stay' -> stays at s0 w.p. 1.0 (reward -1)
# s1 is absorbing: any action -> s1, reward 0 (goal reached, episode value is 0 onward)
states = ["s0", "s1"]
actions = ["go", "stay"]
gamma = 0.9

P = {  # P[(s,a)] = list of (prob, s', reward)
    ("s0", "go"):   [(0.8, "s1", 10.0), (0.2, "s0", -1.0)],
    ("s0", "stay"): [(1.0, "s0", -1.0)],
    ("s1", "go"):   [(1.0, "s1", 0.0)],
    ("s1", "stay"): [(1.0, "s1", 0.0)],
}

def bellman_expectation_solve(policy: dict) -> dict:
    """Solve V^pi = (I - gamma P^pi)^-1 R^pi exactly for a fixed policy (linear system)."""
    n = len(states)
    idx = {s: i for i, s in enumerate(states)}
    A = np.eye(n)
    b = np.zeros(n)
    for s in states:
        a = policy[s]
        for prob, s_next, r in P[(s, a)]:
            A[idx[s], idx[s_next]] -= gamma * prob
            b[idx[s]] += prob * r
    V = np.linalg.solve(A, b)
    return {s: V[idx[s]] for s in states}

def bellman_optimality_step(V: dict) -> dict:
    """One application of the Bellman optimality operator T (value iteration step)."""
    V_new = {}
    for s in states:
        V_new[s] = max(
            sum(prob * (r + gamma * V[s_next]) for prob, s_next, r in P[(s, a)])
            for a in actions
        )
    return V_new

if __name__ == "__main__":
    # Fixed policy: always 'go' from s0 -- solve exactly via the linear system
    policy = {"s0": "go", "s1": "go"}
    V_pi = bellman_expectation_solve(policy)
    print("V^pi (always go):", V_pi)

    # Value iteration toward V* -- should converge to the same answer here,
    # since 'go' is in fact optimal from s0 (verify by hand: E[go] > E[stay])
    V = {s: 0.0 for s in states}
    for i in range(100):
        V_next = bellman_optimality_step(V)
        delta = max(abs(V_next[s] - V[s]) for s in states)
        V = V_next
        if delta < 1e-10:
            print(f"value iteration converged in {i+1} sweeps")
            break
    print("V* (value iteration):", V)
    # Expect V_pi == V* here: verify by hand that E[G|go from s0] > E[G|stay from s0]
    # at these numbers -- if it didn't match, that's a bug-finding exercise.
```

Running this: `V^π` (always-go) and `V*` (value iteration) should land on the same numbers, because `go` genuinely is optimal from `s0` at these reward values — a deliberate check that the linear-system solve (expectation equation) and the iterative fixed-point solve (optimality equation) agree when the fixed policy happens to be optimal. Full tabular policy/value iteration on a real gridworld is built in `T31-dynamic-programming`; this module's lab is deliberately just the equations, by hand, so the derivation above has a concrete anchor.

---

## How it's done in production

| Layer | What you actually use | What it adds |
|---|---|---|
| Exact MDP solving | Rare in production directly — used for small, well-modeled subproblems (e.g. inventory control with known dynamics) | Guaranteed optimal solution when `S`, `A`, `P` are known and tractable |
| Approximate value functions | Neural network `V_θ(s)` or `Q_θ(s,a)` (`T31-dqn` onward) | Handles continuous/huge state spaces where enumeration is impossible |
| Simulators as an implicit `P` | Physics engines, market simulators, game engines | You never write `P(s'|s,a)` down explicitly; you sample from it by stepping the simulator |
| Reward model as `R` | Learned reward models in RLHF (`T31-rl-for-llms`) | `R` itself becomes learned and imperfect, reintroducing the reward-hacking risk from `T31-rl-framing` at the definition level |

### Failure modes

| Symptom | Cause | Fix |
|---|---|---|
| Value iteration or a Bellman-backup-based training loop diverges or oscillates | `γ ≥ 1` used on a continuing (non-terminating) task, so returns are unbounded | Enforce `γ < 1` for continuing tasks; only use `γ = 1` with a guaranteed absorbing terminal state |
| Learned value function is systematically wrong near episode boundaries | Terminal state's value not forced to 0 (bootstrapping past a `done` flag) | Explicitly zero the bootstrap target when `done=True`: `target = r` not `r + γV(s')` |
| Two engineers get different "correct" Bellman equations and can't agree | Ambiguity in whether reward depends on `s`, `(s,a)`, or `(s,a,s')` | Pin the reward function's exact signature in the MDP spec before writing any code; it changes the equation's structure, not just notation |
| Policy converges to something clearly suboptimal despite "correct" code | State representation isn't actually Markov (violates the property the whole derivation relies on) | Revisit `T31-rl-framing`'s POMDP section; add history/recurrence |

---

## Tradeoffs & when NOT to use it

- **Don't hand-derive and hand-solve an MDP when the state space is large.** The linear-system solve for `V^π` is `O(|S|^3)` (matrix inversion) — fine for a handful of states, useless past a few thousand. That's precisely why the rest of the track exists: dynamic programming avoids the matrix inverse with iteration, and everything from `T31-monte-carlo-td` onward avoids needing `P` at all.
- **Don't assume a convenient discount factor without checking it against the task's real horizon.** A `γ` picked by habit (0.99 is common) that's mismatched to the task's actual decision horizon silently caps what the agent can learn to care about — always ask "what's `1/(1-γ)` and does that match how far ahead this task actually requires planning."
- **Don't force a non-Markov problem into this framework without acknowledging the cost.** If you frame a POMDP as an MDP for convenience (feeding a single noisy observation), every one of these derivations technically no longer applies exactly, and the mismatch shows up as unexplained variance in learned values, not a clean error.
- **The MDP formalism itself is nearly always the right model for the problem** — the tradeoff decision in practice isn't "MDP vs something else," it's "exact solution vs which approximation," which is what the rest of this track is about.

---

## Interview questions

### Q1 — Define an MDP. What does the Markov property buy you mathematically?
**Testing:** baseline precision.
**Answer:** `(S,A,P,R,γ)` with `P(s'|s,a)` the transition kernel and `R` the reward function. The Markov property, `P(s_{t+1}|s_t,a_t)=P(s_{t+1}|\text{full history})`, means the current state is a sufficient statistic for the future — it's what lets `V^\pi(s')` alone (no history) capture everything needed to compute expected future return, which is the exact step used in deriving the Bellman equation.
**Follow-up trap:** *"What breaks if the Markov property doesn't hold?"* — the derivation of the Bellman equation fails at the step where `\mathbb{E}[G_{t+1}|s_t=s]` is replaced by `V^\pi(s')`; without the Markov property that replacement is wrong because the true expectation depends on history the state doesn't capture, and you get systematically biased value estimates (a POMDP problem, `T31-rl-framing`).

### Q2 — Derive the Bellman expectation equation for `V^π` from the definition of return. Don't just state it.
**Answer:** `G_t = r_{t+1} + \gamma G_{t+1}` by factoring `γ` out of the tail of the sum. Then `V^\pi(s) = \mathbb{E}_\pi[G_t|s_t=s] = \mathbb{E}_\pi[r_{t+1}|s_t=s] + \gamma\mathbb{E}_\pi[G_{t+1}|s_t=s]`. Expand the first term by summing over the policy's action distribution and the transition kernel. For the second term, use the Markov property to replace `\mathbb{E}_\pi[G_{t+1}|s_{t+1}=s']` with `V^\pi(s')` exactly, then take the same expectation over actions and transitions. Combine: `V^\pi(s)=\sum_a\pi(a|s)\sum_{s'}P(s'|s,a)[R(s,a,s')+\gamma V^\pi(s')]`.
**Follow-up trap:** *"Where exactly did you use the Markov property, specifically?"* — the single step replacing `\mathbb{E}_\pi[G_{t+1}|s_t=s]` (which conditions on the full trajectory up to `t`) with a sum over `V^\pi(s')` weighted by `P(s'|s,a)` — this substitution is only valid because the future given `s_{t+1}=s'` doesn't depend on how you arrived at `s'`.

### Q3 — Why is the Bellman optimality equation nonlinear while the Bellman expectation equation (fixed π) is linear? Why does that matter algorithmically?
**Answer:** The expectation equation for a fixed `π` has `V^π(s')` appearing linearly inside a fixed weighted sum (weights are `π(a|s)P(s'|s,a)`, both fixed), so it's a linear system solvable by direct matrix inversion, `V^\pi=(I-\gamma P^\pi)^{-1}R^\pi`. The optimality equation has a `max_a` over the action, and `max` is a nonlinear operator — you can't invert a matrix through a max. That's precisely why finding `V*` requires an iterative algorithm (value iteration, or policy iteration alternating linear solves with policy improvement) instead of one closed-form solve.
**Follow-up trap:** *"So why not just enumerate all deterministic policies and solve the linear system for each?"* — that's technically valid (policy iteration's inner loop does exactly this per policy) but the number of deterministic policies is `|A|^{|S|}`, combinatorially explosive; value iteration instead iterates the nonlinear operator directly on value functions, `O(|S|^2|A|)` per sweep, avoiding ever enumerating policies.

### Q4 — Prove that value iteration converges to a unique `V*`, at a level deeper than "it's a known result."
**Answer:** Define the Bellman optimality operator `T`. `V^*` is its fixed point by definition. Show `T` is a `γ`-contraction under the max-norm: `\|TV_1-TV_2\|_\infty \le \gamma\|V_1-V_2\|_\infty`, using that `max_a` is non-expansive and that `P(s'|s,a)` is a probability distribution so a probability-weighted difference is bounded by the max difference. By the Banach fixed-point theorem, a contraction on a complete metric space has a unique fixed point, and repeated application from any starting `V_0` converges to it geometrically at rate `γ^n`.
**Follow-up trap:** *"Does this argument still work if `γ=1`?"* — no, the contraction constant is exactly `γ`; at `γ=1` you lose the strict contraction and the theorem's convergence guarantee no longer applies (this connects directly to why `γ<1` was required for return itself to converge in the first place).

### Q5 — What's the relationship between `V^π(s)` and `Q^π(s,a)`? Derive it.
**Answer:** `V^\pi(s) = \mathbb{E}_{a\sim\pi(\cdot|s)}[Q^\pi(s,a)] = \sum_a \pi(a|s)Q^\pi(s,a)` — directly from the definitions: `V^\pi(s)=\mathbb{E}_\pi[G_t|s_t=s]` and `Q^\pi(s,a)=\mathbb{E}_\pi[G_t|s_t=s,a_t=a]`; conditioning `V^\pi` on the action taken via the law of total expectation and using `a_t\sim\pi(\cdot|s_t)` gives exactly this weighted sum.
**Follow-up trap:** *"Use that relationship to show `V^\pi(s) \le \max_a Q^\pi(s,a)`, and say why that inequality matters."* — a weighted average is bounded by its max term, with equality iff all the weight is on the argmax — i.e. iff `π` is greedy w.r.t. its own `Q^π`. This is the seed of the policy improvement theorem: any policy that isn't already greedy w.r.t. its own `Q` can be strictly improved by making it greedy, which is exactly the update rule in policy iteration (`T31-dynamic-programming`).

### Q6 — Derive what `γ` actually represents, beyond "future rewards matter less."
**Answer:** Model a random horizon where the episode continues with probability `γ` at each step and terminates with probability `1-γ`. The expected return under this model, `\sum_k P(\text{survive }k)\cdot r_{t+k+1} = \sum_k \gamma^k r_{t+k+1}`, is algebraically identical to the standard discounted return. So `γ` is equivalent to believing in a `1-γ` per-step chance of termination, with expected remaining horizon `1/(1-γ)`.
**Follow-up trap:** *"Your task genuinely has hard 200-step dependencies and someone set γ=0.9. What happens, mechanically?"* — `1/(1-0.9)=10`, so the agent's effective planning horizon is roughly 10 steps; rewards or consequences 200 steps out are discounted by `0.9^{200}\approx 10^{-10}`, effectively invisible to the value function — the agent isn't failing to learn the long dependency, it's structurally incapable of representing it at that `γ`.

### Q7 — Why does `Q^*(s,a) = \sum_{s'}P(s'|s,a)[R(s,a,s')+\gamma\max_{a'}Q^*(s',a')]` have `max_{a'}` inside the sum rather than outside?
**Answer:** Because the action at the *next* state is a free choice the optimal policy gets to make *after* observing `s'`, while the current transition to `s'` is stochastic and already happened by the time that choice is made — you're taking the expectation over what state you land in, and *then*, for each possible landing state, choosing the best next action. Moving `max` outside the sum would incorrectly assume you choose `a'` before knowing which `s'` you're in.
**Follow-up trap:** *"Is `\max_{a'}\sum_{s'}P(s'|s,a)[\dots]` (max outside) ever equal to the correct equation (max inside)?"* — only in the degenerate deterministic-transition case where `P` puts all mass on one `s'`, collapsing the sum to a single term where order doesn't matter; in general `\max\mathbb{E}[\cdot] \ge \mathbb{E}[\max(\cdot)]` is false in general and the two expressions differ, with the max-inside version being the only one that's actually correct.

### Q8 — A colleague implements value iteration and it doesn't converge — what do you check first?
**Testing:** debugging via the derivation, not guessing.
**Answer:** First, `γ<1` (an off-by-one here breaks the contraction guarantee entirely, not just slows it). Second, that terminal/absorbing states have their value bootstrap correctly zeroed rather than continuing to bootstrap through themselves. Third, that `P(s'|s,a)` actually sums to 1 for every `(s,a)` — a normalization bug silently breaks the contraction argument's use of "probability-weighted average is bounded by the max."
**Follow-up trap:** *"It converges but to the wrong answer, not divergence — different check?"* — that's not a Bellman-operator problem (contraction guarantees the *unique* fixed point, so a converged wrong answer means you didn't converge to `T`'s actual fixed point) — check the reward function's signature (is it `R(s,a)` where you meant `R(s,a,s')`?), and check the action set used in the `max` matches the actual available actions per state.

### Q9 — How would you extend this MDP formalism to include a hard safety constraint, e.g. "never let battery drop below 5%"?
**Answer:** A Constrained MDP (CMDP): add a second reward-like signal (a cost function `C(s,a)`) and optimize `\max_\pi \mathbb{E}[\sum \gamma^t r_t]` subject to `\mathbb{E}[\sum \gamma^t c_t] \le d`. In practice this is usually solved via Lagrangian relaxation — turn the constraint into a penalty term with a dual variable `λ` that's itself adapted during training to push the expected cost toward the budget `d`, rather than baking the constraint into the scalar reward by hand-tuned weight (which reintroduces the scalarization fragility from `T31-rl-framing`).
**Follow-up trap:** *"Why not just make the constraint violation a huge negative reward instead?"* — that's the naive scalarization approach, and it's fragile: too small a penalty and the constraint gets violated when the task reward is large enough to be "worth it"; too large and it can dominate learning signal everywhere, including states nowhere near the constraint. Lagrangian methods adapt the tradeoff automatically toward the actual target budget instead of requiring you to guess the right fixed weight.

### Q10 — Solve by hand: `γ=0.5`, one state with a self-loop, reward `+2` every step forever. What's `V(s)`?
**Testing:** can they actually compute, not just recite formulas.
**Answer:** `V(s) = \sum_{k=0}^\infty \gamma^k \cdot 2 = 2 \cdot \frac{1}{1-\gamma} = 2 \cdot \frac{1}{0.5} = 4`. Also derivable via the Bellman equation directly: `V(s) = R + \gamma V(s) \Rightarrow V(s)(1-\gamma) = R \Rightarrow V(s) = R/(1-\gamma) = 2/0.5 = 4` — same answer, and this self-consistent-equation approach is exactly how you'd solve any single-state or small cyclic MDP by hand without invoking the geometric series formula from memory.
**Follow-up trap:** *"Now with γ=1?"* — the sum diverges to infinity; `V(s)=R+V(s)` has no finite solution (it reduces to `0=R`, a contradiction unless `R=0`), directly illustrating why `γ<1` is required for a continuing task with nonzero reward.

### Q11 — Explain why `V^\pi=(I-\gamma P^\pi)^{-1}R^\pi` is valid — under what condition does the inverse exist?
**Answer:** From the Bellman expectation equation in matrix form: `V^\pi = R^\pi + \gamma P^\pi V^\pi \Rightarrow (I-\gamma P^\pi)V^\pi = R^\pi \Rightarrow V^\pi=(I-\gamma P^\pi)^{-1}R^\pi`. The inverse exists because `P^\pi` is a stochastic matrix (row sums to 1, all eigenvalues have magnitude `\le 1`), so `\gamma P^\pi` has spectral radius `\le\gamma<1`, meaning `I-\gamma P^\pi` is invertible (no eigenvalue of `\gamma P^\pi` equals 1, so `I-\gamma P^\pi` is never singular).
**Follow-up trap:** *"Would this still work at γ=1 for a properly episodic (terminating) MDP?"* — yes, but you need `P^π` restricted to transient (non-absorbing) states, since the absorbing terminal states have `V=0` by construction and get factored out separately; the naive full-matrix inversion at `γ=1` can be singular if any recurrent (non-terminating) class exists, which is exactly the "episodic vs continuing" distinction showing up as a literal linear-algebra condition.

### Q12 — Why does `T31-rl-for-llms`'s reward model still fit inside this same MDP framework despite looking nothing like a robotics MDP?
**Testing:** synthesis — connecting the abstract math to where it's actually deployed.
**Answer:** In RLHF, the "state" is the prompt plus the tokens generated so far, the "action" is the next token (or, in a coarser formulation, the whole response), the "transition" is deterministic (appending the chosen token), and the "reward" typically arrives only at the end of the episode (a single scalar from the reward model scoring the complete response), with `γ` often set close to 1 over a short, bounded horizon (tokens in one response). It's a valid MDP — just an extremely short-horizon, deterministic-transition, sparse-terminal-reward one, which is precisely why techniques built for long, stochastic-transition, dense-reward control problems (classic DQN-style tabular bootstrapping) don't map over unchanged, and why PPO's specific properties (`T31-ppo`) turned out to matter for this regime.
**Follow-up trap:** *"If transitions are deterministic, why not just use planning/search instead of RL at all?"* — the action space (vocabulary size, ~30k-100k+ tokens) times the horizon (response length) is astronomically large for exact search or DP, and the reward model is itself expensive to query and imperfect, which is exactly the situation sample-based, function-approximated RL is built for rather than exact dynamic programming.

---

## Red flags that fail you

- Stating the Bellman equation from memory without being able to re-derive it from `G_t = r_{t+1} + γG_{t+1}`.
- Confusing where the `max` goes in the optimality equation (outside the sum instead of inside, over `a'` at the *next* state).
- Claiming `γ=1` is always fine, or not knowing it requires a guaranteed terminal state.
- Not knowing why `V^π` is a linear system but `V^*` isn't.
- Being unable to state, even informally, why value iteration is guaranteed to converge (the contraction argument).
- Treating `R(s,a)`, `R(s,a,s')`, and `R(s')` as interchangeable notational choices with no consequence.
- No mental model for what `γ` corresponds to in terms of effective planning horizon.

---

## Cheat card

```
MDP TUPLE      (S, A, P, R, gamma);  P(s'|s,a) sums to 1;  gamma in [0,1)
RETURN         G_t = sum_k gamma^k r_{t+k+1}; converges iff gamma<1 (geometric series,
               bounded |r|<=Rmax) -> |G_t| <= Rmax/(1-gamma)
GAMMA MEANING  equivalent to a (1-gamma) chance of episode ending each step;
               effective horizon ~ 1/(1-gamma).  gamma=0.99 -> ~100 steps
RECURSION      G_t = r_{t+1} + gamma * G_{t+1}   <- the one algebraic fact everything follows from
V-Q RELATION   V^pi(s) = sum_a pi(a|s) Q^pi(s,a);  V^pi(s) <= max_a Q^pi(s,a),
               equality iff pi greedy w.r.t. its own Q  (seed of policy improvement)
BELLMAN EXP    V^pi(s) = sum_a pi(a|s) sum_s' P(s'|s,a)[R(s,a,s') + gamma V^pi(s')]
               LINEAR in V^pi -> solvable exactly: V^pi = (I - gamma P^pi)^-1 R^pi
BELLMAN OPT    V*(s) = max_a sum_s' P(s'|s,a)[R(s,a,s') + gamma V*(s')]
               NONLINEAR (max) -> needs iteration, no closed form
CONTRACTION    Bellman optimality operator T is a gamma-contraction in max-norm:
               ||TV1-TV2||_inf <= gamma ||V1-V2||_inf
               -> Banach fixed point thm -> UNIQUE V*, converges from ANY V0, rate gamma^n
WHY MAX INSIDE max_a' is chosen AFTER s' is observed -> max inside the E[.] over s', not outside
TERMINAL STATE bootstrap must be zeroed at done: target = r  (not r + gamma*V(s'))
CMDP           add cost C(s,a), constrain E[sum gamma^t c_t] <= d, solve via Lagrangian dual lambda
```

## Sources

- [Sutton & Barto — Reinforcement Learning: An Introduction (2nd ed.), ch. 3-4](http://incompleteideas.net/book/the-book-2nd.html) — canonical Bellman equation derivation — accessed 2026-08-03
- [Bellman, R. — Dynamic Programming (1957), Princeton University Press — historical origin](https://press.princeton.edu/books/paperback/9780691146683/dynamic-programming) — accessed 2026-08-03
- [Puterman, M. — Markov Decision Processes: Discrete Stochastic Dynamic Programming — contraction mapping proofs](https://onlinelibrary.wiley.com/doi/book/10.1002/9780470316887) — accessed 2026-08-03
- [100+ Reinforcement Learning Interview Questions and Answers (2026)](https://www.wecreateproblems.com/interview-questions/reinforcement-learning-interview-questions) — accessed 2026-08-03
- [Q-Learning Interview Questions (2026)](https://github.com/Devinterview-io/q-learning-interview-questions) — accessed 2026-08-03

## Changelog
- 2026-08-03 — created
