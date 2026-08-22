# Policy Evaluation, Policy Iteration, Value Iteration — Coded From Scratch

> **Track:** T31 Reinforcement Learning · **Time:** 2.5h · **Prereqs:** T31-mdp · **Updated:** 2026-08-03
> **Module id:** `T31-dynamic-programming` · **Tags:** tabular, critical

## The 30-second version

Dynamic programming solves an MDP exactly when you know `P` and `R` and the state space is small enough to enumerate — no learning, no samples, just iterated application of the Bellman equations from `T31-mdp`. Policy evaluation repeatedly applies the Bellman *expectation* backup to compute `V^π` for a fixed policy; policy improvement makes the policy greedy with respect to that `V^π`, which is provably at least as good by the policy improvement theorem; policy iteration alternates the two until the policy stops changing, which happens in a finite number of iterations because there are only finitely many deterministic policies and each iteration strictly improves or terminates. Value iteration collapses evaluation and improvement into one sweep — apply the Bellman *optimality* backup directly — trading exact per-policy evaluation for more, cheaper sweeps; the contraction argument from `T31-mdp` guarantees both converge to the same `V*`, so the choice between them is a computational tradeoff, not a correctness one. Everything from `T31-monte-carlo-td` onward exists because real problems don't give you `P`, and this module is what you're approximating once you no longer have it.

## Why this gets asked

Because it's the fastest way to check whether "I understand the Bellman equation" (previous module) translates into "I can turn it into working code with a correct termination condition" — a huge number of candidates can recite the equations and cannot implement policy iteration without an off-by-one in the stopping criterion or a bug in how they detect policy convergence. Interviewers who've built simulators, game AI, or operations-research systems where the model genuinely is known (inventory control, network routing with known costs) have hit real cases where DP is the *correct* production choice, not just a teaching toy, and want to know you'd recognize that instead of reflexively reaching for a neural network.

---

## Lineage: past → present → future

**What came before.** Before iterative dynamic programming, small MDPs with known dynamics were sometimes solved as linear programs (the value function as the LP's variables, the Bellman optimality inequalities as constraints) — correct but scaling worse in practice than iteration for the state counts DP methods target, and much harder to warm-start from a previous solution. The pain iterative DP fixed was exactly this: policy iteration and value iteration are simple, matrix-free, warm-startable, and (per the contraction argument) come with a clean convergence guarantee that doesn't depend on LP solver internals.

**Where it stands now.** Exact tabular DP is settled, correct, and rarely the production bottleneck when it applies — its actual constraint is `P` and `R` being known and `|S|` being small enough to enumerate, both of which fail for almost every interesting modern RL problem (continuous states, unknown dynamics, pixels). Where it's still genuinely used unmodified: small, well-specified operations-research-flavored problems (elevator scheduling, small inventory systems, certain classic control problems) where the model really is known and exact optimality is worth the enumeration cost. Its larger legacy is conceptual: every deep RL algorithm in this track is a specific answer to "how do we do policy evaluation and improvement when we can't enumerate states and don't know `P`" — TD learning (`T31-monte-carlo-td`) replaces the expectation-over-`P` in evaluation with a sampled bootstrap; DQN (`T31-dqn`) replaces the table `V(s)` with a neural network; policy gradient methods (`T31-policy-gradient`) replace explicit greedy improvement with gradient ascent on policy parameters. The live disagreement, such as it is, isn't about DP's correctness but about pedagogy: whether teaching DP first (this track's order) or teaching model-free methods first better prepares people for the deep RL they'll actually ship — DP-first is the traditional Sutton & Barto ordering and remains the mainstream choice because the convergence arguments it establishes get reused everywhere downstream.

**Where it's heading.** High confidence: DP stays exactly where it is — a small, well-understood corner used directly on genuinely small/known-model problems, and used pedagogically/conceptually everywhere else. Approximate dynamic programming (function-approximated value iteration, fitted value iteration) is the bridge to deep RL and is stable, established technique, not a moving target. Speculative: some 2025-2026 work on using large models as approximate world models (`T31-model-based`) effectively runs DP-flavored planning (rollouts, tree search) inside a *learned* model instead of a known one — a real and growing pattern, but it inherits all the compounding-error risk of an imperfect model, and treat any claim that this fully replaces model-free learning as unproven.

---

## Mental model

```
POLICY ITERATION                          VALUE ITERATION

  π0 ──evaluate──▶ V^π0                     V0
   ▲                  │                      │
   │            improve (greedy)        one optimality
   │                  ▼                  backup sweep
  π1 ◀──────────────  π1                     ▼
   │                  │                     V1
   │            evaluate to V^π1             │
   ▼                  ▼                  (repeat)
  ...  until π stops changing               ▼
                                            V* ──▶ extract greedy π* (once, at the end)

  Policy iteration: full evaluation (many sweeps) then one improvement step, repeat.
  Value iteration:  one sweep of evaluation-and-improvement fused together, repeat.
```

Policy iteration alternates two clean phases — "how good is my current plan, exactly" then "given that, what's a strictly better plan" — like fully solving a math problem, checking the answer, then revising the approach. Value iteration never fully answers "how good is my current plan" for any policy in particular; it directly chases the *optimal* value function by always backing up with the best available action, and only extracts an actual policy at the very end. Both walk toward the same destination (`V*`, proven unique in `T31-mdp`); they just take different-shaped steps.

---

## How it actually works

### Policy evaluation

Given a fixed policy `π`, compute `V^π` by iterating the Bellman *expectation* backup as an update rule rather than solving the linear system directly (which is `O(|S|^3)` and doesn't reuse the previous policy's solution as a warm start):

$$V_{k+1}(s) \leftarrow \sum_a \pi(a|s) \sum_{s'} P(s'|s,a)\left[R(s,a,s') + \gamma V_k(s')\right] \quad \text{for all } s$$

This is the Bellman expectation *operator* `T^π` applied repeatedly. `T^π` is, by the identical argument used for `T` in `T31-mdp` (max replaced by the fixed weighted average `\sum_a\pi(a|s)(\cdot)`, which is also non-expansive), also a `γ`-contraction, so `V_k \to V^π` regardless of initialization. In practice you don't iterate to exact convergence — you stop when `\max_s|V_{k+1}(s)-V_k(s)| < \theta` for a small threshold `θ`, which by the contraction bound guarantees you're within a known, shrinking distance of the true `V^π`.

### Policy improvement, and why it's guaranteed to help

Given `V^π`, define a new policy greedy with respect to it: `π'(s) = \arg\max_a \sum_{s'}P(s'|s,a)[R(s,a,s')+\gamma V^\pi(s')] = \arg\max_a Q^\pi(s,a)`.

**Policy improvement theorem, the argument.** If `π'` is greedy w.r.t. `V^π`, then by construction `Q^\pi(s,\pi'(s)) \ge Q^\pi(s,\pi(s)) = V^\pi(s)` for every `s` (greedy action can't be worse than whatever `π` happened to pick, by definition of argmax). The nontrivial step is showing this *pointwise* one-step improvement implies `V^{\pi'}(s) \ge V^\pi(s)` for *all* `s`, i.e. that it's not just better for one step and then possibly worse later. Expand by repeatedly substituting the inequality into itself:

$$V^\pi(s) \le Q^\pi(s,\pi'(s)) = \mathbb{E}[r_{t+1}+\gamma V^\pi(s_{t+1}) \mid s_t=s, a_t=\pi'(s)]$$
$$\le \mathbb{E}[r_{t+1}+\gamma Q^\pi(s_{t+1},\pi'(s_{t+1})) \mid \dots] \le \mathbb{E}[r_{t+1}+\gamma r_{t+2}+\gamma^2 V^\pi(s_{t+2})\mid\dots] \le \cdots \le V^{\pi'}(s)$$

Each step substitutes `V^\pi(s_{t+k})\le Q^\pi(s_{t+k},\pi'(s_{t+k}))` again at the next timestep — chaining the one-step guarantee out to infinity, which is valid because the inequality direction never flips. The result: greedy improvement w.r.t. `V^π` never makes any state worse, and strictly improves any state where `π` wasn't already greedy. If improvement produces no change anywhere, `π` already satisfies the Bellman *optimality* equation (greedy w.r.t. its own value function, with equality everywhere), which by uniqueness of the fixed point (`T31-mdp`) means `π = π^*`.

### Policy iteration: the algorithm

```
1. Initialize π arbitrarily (e.g. random or all-same-action)
2. repeat:
     a. POLICY EVALUATION: iterate V ← T^π V until ||V_{k+1}-V_k||_∞ < θ
     b. POLICY IMPROVEMENT: π'(s) ← argmax_a Σ_s' P(s'|s,a)[R(s,a,s') + γV(s')]  for all s
     c. if π' == π: return π (this is π*)
        else: π ← π', go to (a)
```

**Why it terminates in finitely many outer iterations.** There are exactly `|A|^{|S|}` deterministic policies — finite. By the policy improvement theorem, each outer iteration either strictly improves `V^π(s)` for at least one `s` (with no state getting worse), or the policy is unchanged and we've already reached `π*`. A strictly-improving sequence over a finite set of policies cannot repeat a policy and cannot continue forever, so it must terminate — this is a genuinely different convergence argument from value iteration's contraction argument, and interviewers who ask "why does policy iteration converge" specifically want this finite-policy-set argument, not the contraction argument that applies to value iteration.

### Value iteration: the algorithm

```
1. Initialize V arbitrarily (commonly all zeros)
2. repeat:
     V_{k+1}(s) ← max_a Σ_s' P(s'|s,a)[R(s,a,s') + γV_k(s')]   for all s
     until ||V_{k+1} - V_k||_∞ < θ
3. extract π*(s) ← argmax_a Σ_s' P(s'|s,a)[R(s,a,s') + γV*(s')]   (once, at the end)
```

Convergence: exactly the contraction argument proven in `T31-mdp` — `T` is a `γ`-contraction in max-norm, unique fixed point `V^*`, geometric convergence rate `γ^n` from any starting point. Note the practical consequence of the rate: to halve the error you need roughly `\log(2)/\log(1/\gamma)` more sweeps, so `γ` close to 1 (long horizons) means slow convergence in wall-clock sweeps even though each sweep is cheap — a real, measurable tradeoff, not just theory.

**Policy iteration vs value iteration — the actual tradeoff.** Policy iteration does more work per outer iteration (a full inner evaluation loop to convergence) but typically needs far fewer outer iterations (often single digits in practice) because policy improvement makes large, discrete jumps. Value iteration does less work per sweep (a single backup) but needs more sweeps, especially as `γ→1`. **Modified/generalized policy iteration** — the practical default — truncates the inner evaluation loop to a fixed small number of sweeps (even just one) instead of running it to convergence, which turns out empirically to converge in comparable or fewer total backups than either pure extreme; value iteration is the special case of generalized policy iteration where the inner loop is exactly one sweep.

---

## Build it from scratch

FrozenLake-style gridworld, both algorithms, with the convergence checks made explicit and inspectable:

```python
import numpy as np

class GridWorld:
    """4x4 grid. Actions: 0=up 1=right 2=down 3=left. Terminal at (3,3), reward +1.
    Step reward -0.04 elsewhere (encourages shortest path). Slips 10% sideways."""
    def __init__(self, n=4, slip=0.1):
        self.n = n
        self.slip = slip
        self.states = [(r, c) for r in range(n) for c in range(n)]
        self.terminal = (n - 1, n - 1)
        self.actions = [0, 1, 2, 3]
        self.deltas = {0: (-1, 0), 1: (0, 1), 2: (1, 0), 3: (0, -1)}

    def _move(self, s, a):
        if s == self.terminal:
            return s, 0.0
        dr, dc = self.deltas[a]
        r, c = s
        r2, c2 = min(max(r + dr, 0), self.n - 1), min(max(c + dc, 0), self.n - 1)
        s2 = (r2, c2)
        reward = 1.0 if s2 == self.terminal else -0.04
        return s2, reward

    def transitions(self, s, a):
        """Returns list of (prob, s', reward). Slips to the two perpendicular directions."""
        if s == self.terminal:
            return [(1.0, s, 0.0)]
        perp = {0: [1, 3], 1: [0, 2], 2: [1, 3], 3: [0, 2]}[a]
        outcomes = [(1 - self.slip, a)] + [(self.slip / 2, pa) for pa in perp]
        result = []
        for prob, act in outcomes:
            s2, r = self._move(s, act)
            result.append((prob, s2, r))
        return result

def policy_evaluation(env, policy, gamma=0.99, theta=1e-8, max_sweeps=10_000):
    V = {s: 0.0 for s in env.states}
    for sweep in range(max_sweeps):
        delta = 0.0
        for s in env.states:
            a = policy[s]
            v_new = sum(p * (r + gamma * V[s2]) for p, s2, r in env.transitions(s, a))
            delta = max(delta, abs(v_new - V[s]))
            V[s] = v_new
        if delta < theta:
            break
    return V, sweep + 1

def policy_improvement(env, V, gamma=0.99):
    policy, stable_input_unused = {}, None
    for s in env.states:
        q_values = {
            a: sum(p * (r + gamma * V[s2]) for p, s2, r in env.transitions(s, a))
            for a in env.actions
        }
        policy[s] = max(q_values, key=q_values.get)
    return policy

def policy_iteration(env, gamma=0.99, theta=1e-8):
    policy = {s: 0 for s in env.states}   # arbitrary start: always 'up'
    for outer_iter in range(1000):
        V, _ = policy_evaluation(env, policy, gamma, theta)
        new_policy = policy_improvement(env, V, gamma)
        if new_policy == policy:            # exact equality check -> finite termination
            return new_policy, V, outer_iter + 1
        policy = new_policy
    raise RuntimeError("policy iteration did not converge -- check gamma < 1, P sums to 1")

def value_iteration(env, gamma=0.99, theta=1e-8, max_sweeps=10_000):
    V = {s: 0.0 for s in env.states}
    for sweep in range(max_sweeps):
        delta = 0.0
        for s in env.states:
            v_new = max(
                sum(p * (r + gamma * V[s2]) for p, s2, r in env.transitions(s, a))
                for a in env.actions
            )
            delta = max(delta, abs(v_new - V[s]))
            V[s] = v_new
        if delta < theta:
            break
    policy = policy_improvement(env, V, gamma)   # extract policy once, at the end
    return policy, V, sweep + 1

if __name__ == "__main__":
    env = GridWorld()
    pi_policy, pi_V, pi_iters = policy_iteration(env)
    vi_policy, vi_V, vi_sweeps = value_iteration(env)

    print(f"policy iteration: {pi_iters} outer iterations")
    print(f"value iteration:  {vi_sweeps} sweeps")
    max_diff = max(abs(pi_V[s] - vi_V[s]) for s in env.states)
    print(f"max |V_PI - V_VI| = {max_diff:.6f}  (should be ~0: both converge to the same V*)")
    assert pi_policy == vi_policy, "policies should agree at the optimum"
```

Run this and log `pi_iters` vs `vi_sweeps`: policy iteration typically finishes in under 10 outer iterations (each doing many inner evaluation sweeps), while value iteration needs hundreds of sweeps at `γ=0.99` — a direct, measured illustration of the tradeoff described above. The `assert` at the end is the empirical version of "both converge to the unique `V*`," proven exactly, not approximately, in `T31-mdp`.

---

## How it's done in production

| Layer | What you actually use | What it adds |
|---|---|---|
| When the model truly is known | Direct policy/value iteration on the enumerated state space | Exact optimum, no sampling noise, no function-approximation error |
| Larger but still enumerable state spaces | Sparse/structured transition matrices, asynchronous DP (update states in any order, not full sweeps), prioritized sweeping (update states with the largest pending Bellman error first) | Same guarantees, much less wasted computation on states far from converging |
| State space too large to enumerate | Fitted value iteration / approximate DP: replace the table `V(s)` with a function approximator, backup targets computed via sampled or simulated transitions | Bridges to deep RL; loses the exact convergence guarantee, since function approximation plus bootstrapping reintroduces two legs of the deadly triad from `T31-rl-framing` |
| `P`/`R` unknown | Not DP anymore — model-free methods (`T31-monte-carlo-td` onward) or model-based RL that first learns an approximate `P̂` (`T31-model-based`) | Removes the "known model" requirement DP can't do without |

### Failure modes

| Symptom | Cause | Fix |
|---|---|---|
| Policy iteration loops seemingly forever, never reports convergence | Policy equality check compares object identity or uses float tolerance instead of an exact discrete action match | Compare action *choices* per state exactly (`new_policy == policy` on the dict, as above); ties in the argmax should be broken deterministically or the comparison will flicker |
| Value iteration "converges" but the extracted policy is clearly wrong | Policy extracted using a *stale* `V` (extracted mid-loop, or before the final backup) | Extract the policy only after the value loop's stopping condition is met, using the final `V` |
| Evaluation or value iteration diverges numerically | `γ ≥ 1`, or `P(s'|s,a)` doesn't sum to 1 for some `(s,a)` (breaks the contraction proof's key step) | Assert `sum(P(s'|s,a) for s') == 1` for every `(s,a)` in tests; assert `γ<1` |
| DP is "too slow" and someone reaches straight for deep RL | State space is enumerable but large; full sweeps waste time on states far from their converged value | Try asynchronous DP / prioritized sweeping before abandoning exact methods — often solves the actual bottleneck without giving up exactness |

---

## Tradeoffs & when NOT to use it

- **Don't use DP if `P` and `R` are unknown.** This is the hard requirement, not a soft preference — DP needs the actual transition probabilities to compute an expectation over successor states; if you don't have them (almost every real-world control problem), you need model-free methods (`T31-monte-carlo-td` onward) or first learn a model (`T31-model-based`).
- **Don't use DP on large or continuous state spaces without function approximation, and know you lose the exact convergence guarantee when you do.** Tabular DP's `O(|S|^2|A|)` per sweep is fine for thousands of states, hopeless for millions or continuous spaces; fitted value iteration bridges the gap but the contraction argument no longer strictly applies once `V` is a parameterized function rather than an exact table (this is exactly the deadly triad risk flagged in `T31-rl-framing`).
- **Prefer policy iteration when policy evaluation is cheap relative to how many outer iterations you'd otherwise need**, and prefer value iteration (or truncated/generalized policy iteration) when you want a simpler loop and don't mind more, cheaper sweeps — in practice, truncated generalized policy iteration usually wins on wall-clock time over either textbook extreme.
- **When the model is known and the state space is genuinely small, DP is the right answer, not a stepping stone.** Don't reach for a neural network or sampling-based method "because that's what RL is" on a problem where exact tabular DP finishes in milliseconds with a provably optimal answer.

---

## Interview questions

### Q1 — What's the difference between policy evaluation and policy iteration? People conflate these.
**Answer:** Policy evaluation computes `V^π` for one *fixed* policy `π` — it's a subroutine, not a full algorithm for finding the optimal policy. Policy iteration is the outer loop: evaluate the current policy, then improve it by acting greedily w.r.t. that evaluation, repeat until the policy stops changing. Evaluation alone never changes the policy; iteration is evaluation plus improvement, repeated.
**Follow-up trap:** *"Can you skip evaluation and go straight to improvement using an arbitrary V, not V^π?"* — that's exactly what value iteration does (one backup, not full evaluation, then implicitly "improve" by using the max in the same step) — it's a valid algorithm, just a different point on the evaluation-thoroughness spectrum, not a mistake.

### Q2 — Prove that greedy policy improvement never makes any state worse.
**Answer:** By construction, `Q^\pi(s,\pi'(s)) \ge Q^\pi(s,\pi(s)) = V^\pi(s)` for the greedy `π'`. Chain this one-step inequality forward by repeatedly substituting it at each future timestep: `V^\pi(s) \le \mathbb{E}[r_{t+1}+\gamma V^\pi(s_{t+1})|a_t=\pi'(s)] \le \mathbb{E}[r_{t+1}+\gamma Q^\pi(s_{t+1},\pi'(s_{t+1}))|\dots] \le \cdots \le V^{\pi'}(s)`. The inequality direction is preserved at every substitution, so it holds in the limit.
**Follow-up trap:** *"What if the improvement produces exactly the same policy — what does that tell you?"* — the policy is already greedy w.r.t. its own value function everywhere, which is precisely the Bellman optimality equation; by uniqueness of the fixed point, that policy's value function is `V^*` and the policy is optimal.

### Q3 — Why does policy iteration terminate in a finite number of outer iterations, and is that argument different from value iteration's convergence proof?
**Answer:** There are finitely many deterministic policies (`|A|^{|S|}`). Each outer iteration either strictly improves the value at some state (with no state getting worse, by Q2) or leaves the policy unchanged, at which point it's already optimal and the loop returns. A sequence that strictly improves over a finite set without repeating must terminate. This is a *combinatorial* argument (finite set, monotonic strict improvement), distinct from value iteration's *analytic* contraction-mapping argument (Banach fixed point on a continuous space of value functions) — they're proving convergence of genuinely different objects (a sequence of discrete policies vs. a sequence of real-valued functions).
**Follow-up trap:** *"Does the policy-iteration argument tell you anything about the convergence *rate*, the way the contraction argument gives you γ^n for value iteration?"* — no, and this is a real asymmetry: the finite-policy-set argument only guarantees termination, not a rate; in practice policy iteration converges in very few outer iterations (often single digits) but this is an empirical observation, not something the termination proof itself bounds.

### Q4 — When would you choose value iteration over policy iteration, and vice versa?
**Answer:** Value iteration when you want a simpler loop and per-sweep cost matters more than iteration count, or when policy evaluation to convergence would be expensive relative to the gain. Policy iteration when outer iterations are expensive to trigger (e.g. some real-world cost to changing the deployed policy) and you'd rather pay for thorough evaluation between infrequent policy changes. In practice neither pure extreme usually wins — truncated/generalized policy iteration (evaluate a few sweeps, not to convergence, then improve) tends to converge in fewer total backup operations than either textbook version.
**Follow-up trap:** *"Is value iteration a special case of policy iteration, or a fundamentally different algorithm?"* — it's the special case of generalized policy iteration where the inner evaluation loop is truncated to exactly one sweep before every improvement step; recognizing this unifies both algorithms as points on one spectrum rather than two unrelated methods.

### Q5 — Your policy iteration implementation runs forever without converging. What are the top three things you check?
**Testing:** debugging via the actual convergence argument, not guessing.
**Answer:** (1) The policy-equality check — comparing dicts/arrays for exact match per state, not floating-point value comparison, and handling argmax ties deterministically so the "same" policy doesn't get represented two different ways across iterations. (2) `γ<1` — the evaluation step's contraction guarantee requires it. (3) That `P(s'|s,a)` sums to 1 for every `(s,a)` used in the backup — a normalization bug breaks the proof that improvement is monotonic.
**Follow-up trap:** *"It converges, but slower than a colleague's implementation on the same problem. Why might that be, given both are theoretically guaranteed to converge?"* — the *evaluation* step's inner tolerance `θ` is likely too tight relative to how much precision is actually needed before the next improvement step would change anything — running evaluation to near machine-precision every outer iteration when a much looser tolerance would already yield the same greedy policy wastes enormous computation for no benefit.

### Q6 — What's the per-sweep computational complexity of value iteration, and how does it scale as the problem grows?
**Answer:** `O(|S|^2|A|)` per sweep for a dense transition model (for each of `|S|` states, for each of `|A|` actions, sum over up to `|S|` possible next states); with sparse transitions (each `(s,a)` reaches only a few `s'`) this drops close to `O(|S| \cdot |A| \cdot b)` where `b` is the branching factor. This is exactly why tabular DP is limited to state spaces in the thousands-to-low-millions, not why it's "slow" in some vague sense — the quadratic-in-`|S|` term from dense transitions is the concrete bottleneck.
**Follow-up trap:** *"Your state space is a 10^9-cell grid but transitions are local (each cell reaches ~4 neighbors). Does tabular DP still work?"* — the per-sweep cost with sparse transitions is roughly `O(|S| \cdot |A| \cdot 4)`, linear in `|S|`, so a single sweep is plausible, but you still need to *store* `V` over `10^9` states and the number of sweeps to converge doesn't shrink — this is exactly the regime where asynchronous DP / prioritized sweeping (update states with large pending Bellman error first, skip near-converged ones) becomes necessary rather than optional.

### Q7 — Derive why value iteration's convergence rate is `γ^n` and what that implies practically for `γ` close to 1.
**Answer:** From the contraction proof in `T31-mdp`, `\|V_n - V^*\|_\infty \le \gamma^n \|V_0-V^*\|_\infty`. To reduce the error by half, you need `\gamma^n = 0.5 \Rightarrow n = \log(0.5)/\log(\gamma)`. At `γ=0.9`, that's about 6.6 sweeps; at `γ=0.99`, about 69 sweeps; at `γ=0.999`, about 693 sweeps. So long-horizon tasks (`γ` near 1) — exactly the tasks where you need the discount to be near 1 to represent the horizon at all (`T31-mdp`) — are also the tasks where value iteration converges slowest in sweep count. This tension (need `γ` near 1 for horizon, pay for it in convergence speed) is real and doesn't have a free fix within exact DP.
**Follow-up trap:** *"Does policy iteration avoid this tradeoff?"* — not entirely: the inner evaluation loop has the identical `γ^n` rate (it's the same contraction argument applied to `T^π` instead of `T`), but policy iteration usually needs many fewer *outer* iterations, so the total sweep count can still come out lower — but this isn't guaranteed in general, it's an empirical tendency.

### Q8 — What breaks if you extract the policy from `V` *before* value iteration has actually converged?
**Answer:** You get a policy that's greedy w.r.t. an intermediate, still-wrong value estimate — not necessarily terrible (early sweeps of value iteration often already identify locally-good actions), but not guaranteed optimal, and with no principled bound on how far from optimal it is without knowing how far `V_k` is from `V^*`. The correct procedure extracts the policy once, after the stopping criterion (`\|V_{k+1}-V_k\|_\infty<\theta`) is met, using the final `V`.
**Follow-up trap:** *"Is there a formal bound relating the value-function error to the resulting policy's suboptimality?"* — yes: if `\|V-V^*\|_\infty \le \epsilon`, the policy greedy w.r.t. `V` has value within `\frac{2\gamma\epsilon}{1-\gamma}` of optimal — meaning near-`γ=1` problems amplify a given value-function error into much larger policy suboptimality, another reason tight tolerances matter more as `γ→1`.

### Q9 — A production team has a genuinely small, fully-known MDP (order of a few thousand states) and is defaulting to training a deep Q-network on it anyway. Is that the right call?
**Testing:** the "don't reach for deep RL by default" senior signal.
**Answer:** No, usually not — with a known model and enumerable states, tabular value or policy iteration gives the exact optimum in milliseconds to seconds with zero sampling noise, zero function-approximation error, and zero training instability, while DQN adds all three of those risks (deadly-triad territory) to solve a problem that doesn't need them. The only reasons to prefer a learned approach here would be if the model is expected to change frequently in ways that make re-deriving `P` expensive, or if this is explicitly a stepping stone toward a version of the problem that won't stay small.
**Follow-up trap:** *"The state space is 3 thousand states today but the team says it'll likely grow to millions next year. Does that change your answer?"* — it's a real consideration, but "might grow" isn't "has grown" — building for a hypothetical future scale at the cost of today's simplicity and exactness is a premature-generalization trap; better to solve today's problem exactly and re-evaluate the algorithm choice when the state space actually grows past what tabular DP (possibly with sparsity/asynchronous updates) can handle.

### Q10 — Explain prioritized sweeping and why it can dramatically speed up value iteration on large, sparse state spaces without giving up exactness.
**Answer:** Standard value iteration updates every state every sweep, wasting computation on states whose value is already near-converged (their most recent Bellman update produced a tiny delta) while under-serving states with a large pending error. Prioritized sweeping maintains a priority queue keyed by each state's most recent Bellman error magnitude, always updating the highest-priority (largest-error) state next, and — critically — after updating a state, pushes its *predecessors* (states that can transition into it) back onto the queue with an updated priority, since their value now depends on a changed number. This focuses computation where it actually reduces error fastest, while still converging to the exact same `V*` (it's still applying the same Bellman backup, just in a smarter order).
**Follow-up trap:** *"Why push predecessors specifically, rather than just re-checking all states periodically?"* — because a state's Bellman backup depends only on its successors' current values; if a successor `s'` just changed significantly, only states that transition *into* `s'` are affected and need re-evaluating — re-checking all states wastes exactly the computation prioritized sweeping exists to avoid, and requires precomputing/maintaining the predecessor graph as the actual mechanism that makes this efficient.

---

## Red flags that fail you

- Confusing policy evaluation (a subroutine) with policy iteration (the full algorithm).
- Reciting "policy iteration converges" without the finite-policy-set argument, or "value iteration converges" without the contraction argument — and not knowing these are *different* proofs for *different* objects.
- Extracting a policy mid-loop from an unconverged `V`.
- Not knowing DP requires a known `P` and `R` — attempting to describe it as usable on an unknown-dynamics problem.
- Comparing policies for convergence using float tolerance instead of exact action equality.
- Reaching for deep RL by default on a small, fully-known MDP where exact DP is strictly better.
- No answer for why `γ` near 1 makes value iteration converge slower in sweep count.

---

## Cheat card

```
POLICY EVALUATION   V_{k+1}(s) = sum_a pi(a|s) sum_s' P(s'|s,a)[R+gamma V_k(s')]  (all s)
                     iterate to ||V_{k+1}-V_k||_inf < theta;  T^pi is a gamma-contraction too
POLICY IMPROVEMENT  pi'(s) = argmax_a sum_s' P(s'|s,a)[R + gamma V^pi(s')] = argmax_a Q^pi(s,a)
IMPROVEMENT THM     Q^pi(s,pi'(s)) >= V^pi(s) pointwise  =>  chain forward  =>  V^pi'(s) >= V^pi(s) ALL s
                     no improvement anywhere => pi already satisfies Bellman optimality => pi = pi*
POLICY ITERATION    loop: full evaluate -> greedy improve -> if policy unchanged, done
                     TERMINATES: finite # of deterministic policies (|A|^|S|), strictly improves
                     or stops -- COMBINATORIAL argument, not a rate guarantee
VALUE ITERATION     V_{k+1}(s) = max_a sum_s' P(s'|s,a)[R + gamma V_k(s')]  (all s)
                     extract pi* ONCE, after convergence, not mid-loop
                     CONTRACTION argument (Banach fixed pt) -> converges at rate gamma^n
RATE                halving error takes ~log(0.5)/log(gamma) sweeps:
                     gamma=0.9 -> ~7 sweeps;  0.99 -> ~69;  0.999 -> ~693
COMPLEXITY/SWEEP    O(|S|^2 |A|) dense transitions; ~O(|S| |A| b) sparse, branching factor b
GENERALIZED PI      value iteration = PI with inner eval truncated to 1 sweep; truncated PI
                     usually beats both pure extremes on total backups
VALUE-ERROR BOUND   ||V-V*||_inf <= eps  =>  greedy(V) policy within 2*gamma*eps/(1-gamma) of optimal
PRIORITIZED SWEEP   update largest-Bellman-error state first; push its PREDECESSORS back onto
                     queue after each update -- same V*, far less wasted computation
REQUIRES KNOWN P,R  hard requirement -- unknown model => not DP, use T31-monte-carlo-td onward
```

## Sources

- [Sutton & Barto — Reinforcement Learning: An Introduction (2nd ed.), ch. 4](http://incompleteideas.net/book/the-book-2nd.html) — canonical DP treatment and policy improvement theorem — accessed 2026-08-03
- [Puterman, M. — Markov Decision Processes: Discrete Stochastic Dynamic Programming](https://onlinelibrary.wiley.com/doi/book/10.1002/9780470316887) — prioritized sweeping and generalized policy iteration formalism — accessed 2026-08-03
- [Moore & Atkeson — Prioritized Sweeping: Reinforcement Learning with Less Data and Less Time (1993)](https://link.springer.com/article/10.1007/BF00993104) — accessed 2026-08-03
- [100+ Reinforcement Learning Interview Questions and Answers (2026)](https://www.wecreateproblems.com/interview-questions/reinforcement-learning-interview-questions) — accessed 2026-08-03

## Changelog
- 2026-08-03 — created
