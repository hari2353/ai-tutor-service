# Model-Based RL, Dyna, MCTS, AlphaZero-Style Planning

> **Track:** T31 Reinforcement Learning · **Time:** 3h · **Prereqs:** T31-mdp, T31-dynamic-programming, T31-dqn · **Updated:** 2026-08-03
> **Module id:** `T31-model-based` · **Tags:** deep-rl, planning, critical
> **Lab:** `labs/py/31-11-model-based/`

## The 30-second version

Everything from `T31-dqn` through `T31-continuous-control` is **model-free**: it learns a value function or policy directly from real environment interaction, with no explicit model of `P(s'|s,a)` ever built. **Model-based RL** learns (or is given) an explicit transition model and uses it to *plan* — either by generating extra simulated experience to train on (Dyna-Q, Sutton 1990) or by searching ahead through the model at decision time (MCTS). Dyna-Q's core move: after every real step, also take `k` simulated steps sampled from a learned model and run ordinary Q-learning updates on them, extracting far more gradient updates per real environment interaction than a purely model-free method could — the direct answer to model-free RL's sample-inefficiency. **Monte Carlo Tree Search** (MCTS) builds a search tree at decision time using four phases — selection (via the UCB1/UCT formula balancing exploitation and exploration), expansion, simulation/rollout, backpropagation — and **AlphaZero** (Silver et al., 2017) replaces MCTS's expensive random rollouts with a learned value/policy network's direct estimate, and replaces UCT's visit-count-only exploration bonus with **PUCT**, weighted by the network's own prior over actions. The whole family's fundamental tradeoff is sample efficiency (a model lets you generate cheap simulated experience or search ahead without touching the real environment) versus **compounding model error**: a learned model's small per-step prediction error compounds multiplicatively over a multi-step rollout, and planning against a systematically wrong model can be worse than not planning at all.

## Why this gets asked

Model-based RL and MCTS/AlphaZero-style planning are asked to test whether a candidate understands sample efficiency as a *design axis*, not just an incidental benefit — and whether they can reason about the specific, real failure mode (compounding model error) that has killed more than one production model-based RL project after early results looked great in the near-term rollout horizon. Interviewers who've built game-playing agents or robotics planners have watched a model-based system's simulated rollouts look internally consistent and confident while being systematically wrong past a few steps, producing a policy that's excellent against the model and mediocre or dangerous against reality — precisely the model-based analogue of DQN's "training loss looks fine, real performance doesn't" failure signature (`T31-dqn`).

---

## Lineage: past → present → future

**What came before.** Classical planning and search (minimax with alpha-beta pruning for perfect-information games, exact dynamic programming for known-model MDPs, `T31-dynamic-programming`) solved decision-making exactly when the model was known, small, and exactly solvable — chess and checkers engines through the 1990s used deep, hand-tuned search plus hand-crafted evaluation functions rather than learning. The pain that killed pure hand-crafted search-plus-evaluation at scale was twofold: hand-designed evaluation functions don't generalize (a chess-tuned evaluation function is useless for Go, whose branching factor and lack of good heuristic evaluation functions made brute-force minimax-style search computationally hopeless — the search tree's branching factor, roughly 250 for Go versus roughly 35 for chess, made even modest-depth exhaustive search infeasible), and model-free RL (`T31-dqn` onward) throws away the sample-efficiency benefit a model provides when one is actually learnable. MCTS (Kocsis & Szepesvári's UCT algorithm, 2006, building on earlier Monte Carlo tree ideas) offered a way to search deep game trees without needing a hand-crafted evaluation function at every leaf — random rollouts to the end of the game supplied a noisy but unbiased value estimate instead.

**Where it stands now.** AlphaGo (2016) and AlphaZero (2017) settled a long-open question by combining MCTS's search structure with a learned value/policy network replacing random rollouts, achieving superhuman play in Go, chess, and shogi from self-play alone, with no hand-crafted evaluation function and no human game data beyond the rules themselves (AlphaZero specifically; AlphaGo used human game data as an initial bootstrap, a distinction still worth naming precisely in an interview). This MCTS-plus-learned-network combination is now the standard architecture for perfect-information, discrete-action game-playing agents at the frontier, and its core idea — use a model (real or learned) to search ahead rather than relying purely on a reactive learned policy — has influenced broader model-based RL research (world models, learned dynamics models for robotics planning) even outside board games. The live, practical disagreement is precisely the tradeoff this module is built around: model-based methods (Dyna-style or MCTS-with-a-learned-model) offer real sample-efficiency gains, but a poorly-calibrated learned model's compounding error can make a model-based agent confidently wrong in ways a model-free agent, which never extrapolates through a learned dynamics model at all, simply cannot be — and for most industrial applications outside games and well-modeled physics/robotics simulators, model-free methods (or even simpler non-RL baselines, `T31-rl-in-production`) remain the safer, more common default specifically to avoid this failure mode.

**Where it's heading.** High confidence: MCTS-plus-learned-network planning remains the standard for perfect-information discrete-game agents — nothing has displaced this architecture since AlphaZero. Medium confidence: learned world models (predicting future observations/latents rather than hand-specified state transitions) for planning in continuous-control and robotics settings continue to be an active, improving research direction, with real but bounded production adoption specifically where the model's error can be kept in check (short planning horizons, frequent replanning against real observations rather than committing to long open-loop plans). Speculative: whether learned-world-model-based planning displaces model-free actor-critic methods (`T31-continuous-control`) as the default for general continuous control is genuinely unsettled — the compounding-error problem this module derives is a structural, not merely an engineering, obstacle, and there's no consensus it's been solved in general, only mitigated in specific, narrower settings.

---

## Mental model

```
MODEL-FREE (T31-dqn, T31-ppo, T31-continuous-control):
    real env --(s,a,r,s')--> learn V/Q/policy directly, no model of P(s'|s,a) ever built

MODEL-BASED, two distinct uses of a model:

  (1) DYNA-Q: use the model to generate MORE (simulated) experience to
      train the SAME model-free update on -- sample efficiency via
      "practice against your own mental model between real interactions"

        real step  -> update model, do 1 real Q-learning update
        simulated steps (k of them) -> sample from LEARNED model,
                                        do k MORE Q-learning updates
                                        (free -- no real env interaction)

  (2) MCTS / SEARCH: use the model to look AHEAD at decision time,
      building a tree of possible futures before committing to an action
      -- "practice against your mental model RIGHT NOW, before acting"

        current state
             │
        ┌────┼────┬────┐   SELECTION: walk down via UCT/PUCT
        ▼    ▼    ▼    ▼   (balance: this looks good vs. haven't tried much)
       ...  ...  ...  ...
        │
        EXPANSION: add a new leaf node
        │
        SIMULATION: random rollout (classic MCTS) OR value-net estimate (AlphaZero)
        │
        BACKPROPAGATION: push the result back up every node on the path,
                          updating visit counts and value estimates

FUNDAMENTAL TRADEOFF:  a model lets you plan/practice CHEAPLY without
  touching the real environment -- but if the model is even slightly
  wrong, errors COMPOUND over a multi-step rollout (wrong -> more wrong
  -> confidently wrong), unlike model-free methods which never extrapolate
  through a learned dynamics model at all.
```

---

## How it actually works

### Dyna-Q: learning a model and using it to manufacture cheap experience

Dyna-Q (Sutton, 1990) augments ordinary tabular Q-learning (`T31-q-learning-sarsa`) with a learned model `\hat{P}(s'|s,a),\hat{R}(s,a)` (for a deterministic or simple stochastic environment, often just a table recording the last-observed `(s',r)` for each `(s,a)` pair encountered) and interleaves real and simulated updates:

```
loop:
  observe real transition (s, a, r, s')
  Q(s,a) <- Q(s,a) + alpha*(r + gamma*max_a' Q(s',a') - Q(s,a))   # ordinary real Q-learning update
  Model[s,a] <- (r, s')                                            # update the learned model

  repeat k times:                          # PLANNING: k simulated updates per real step
      s_sim, a_sim <- sample a previously-visited (s,a) pair
      r_sim, s'_sim <- Model[s_sim, a_sim]                          # query the LEARNED model, no real env
      Q(s_sim,a_sim) <- Q(s_sim,a_sim) + alpha*(r_sim + gamma*max_a' Q(s'_sim,a') - Q(s_sim,a_sim))
```

**Why this is a real sample-efficiency win, not just extra compute.** Every real environment interaction is expensive (time, physical wear, safety risk); every simulated update using the learned model is comparatively free. Dyna-Q gets `k+1` Q-learning updates per real step instead of 1, and because Q-learning's convergence guarantee (`T31-mdp`'s contraction argument) only requires that state-action pairs continue being visited/updated, extra updates from a *reasonably accurate* model genuinely accelerate convergence toward the same fixed point Q-learning would eventually reach from real data alone. The mechanism has an exact analogue to DQN's replay buffer (`T31-dqn`): both extract multiple gradient/update signals from data that's cheaper to reuse/generate than fresh real interaction — the difference is a replay buffer reuses *real* past transitions exactly, while Dyna-Q's planning step generates *new*, model-sampled transitions that were never directly observed, which is where the compounding-error risk this module is about first enters the picture (a replay buffer can't be "wrong" about a transition it actually observed; a learned model absolutely can be wrong about a transition it's extrapolating).

### MCTS: the four phases and the UCB1/UCT formula, derived

MCTS builds a search tree incrementally, one simulation at a time, over four repeated phases:

1. **Selection.** Starting at the root (current state), walk down the tree by repeatedly choosing the child that maximizes the **UCT** (Upper Confidence bound applied to Trees) score, until reaching a node with an unexpanded child:

$$\text{UCT}(s,a) = \underbrace{Q(s,a)}_{\text{exploitation}} + c\sqrt{\frac{\ln N(s)}{N(s,a)}}$$

where `Q(s,a)` is the current average simulated return from taking `a` at `s` (exploitation term — "how good has this looked so far"), `N(s)` is the total visit count of the parent node, `N(s,a)` is the visit count of this specific child, and `c` is an exploration constant. **Where this formula comes from, precisely**: it's a direct instantiation of the UCB1 bandit algorithm (Auer et al., 2002) — the same principle behind optimism-under-uncertainty exploration covered in `T31-exploration` — applied at *every node* of the tree, treating each node's set of children as an independent multi-armed bandit problem. The `\sqrt{\ln N(s)/N(s,a)}` term is UCB1's confidence-interval width: it shrinks as `N(s,a)` grows (more visits to this specific action, more confident the average `Q(s,a)` is accurate) but grows (slowly, logarithmically) with `N(s)` (as the parent gets visited more overall, even a well-explored child's uncertainty bound loosens slightly, preventing the search from *permanently* abandoning an action after an unlucky early run of simulations). This selection rule provably balances exploiting the currently-best-looking action against continuing to explore under-visited ones, with the exploration bonus vanishing (relatively) as evidence accumulates.

2. **Expansion.** Once selection reaches a node with at least one unvisited child action, add that child as a new leaf node to the tree.

3. **Simulation (rollout).** Estimate the new leaf's value. Classic MCTS does this via a **random rollout** — play out the rest of the episode (or search to some depth) using a random or simple heuristic policy, and use the resulting terminal outcome (win/loss, or accumulated reward) as a noisy but unbiased value estimate.

4. **Backpropagation.** Propagate the simulation's result back up every node visited during selection, incrementing each node's visit count `N(s,a)` and updating its running average `Q(s,a)` to include the new simulation's outcome.

Repeat these four phases for a fixed simulation budget (thousands to hundreds of thousands of simulations per real decision, depending on the time budget), then commit to the real action with the highest visit count (or highest average value) at the root — visit count is typically used rather than raw value because it's a more robust proxy for "this is the direction search has converged on," less sensitive to a small number of lucky/unlucky individual rollouts.

### AlphaZero: replacing rollouts and reshaping exploration

AlphaZero makes two structural changes to classic MCTS, both aimed at removing the dependence on expensive, high-variance random rollouts:

**Replacing simulation with a learned value/policy network.** Instead of a random rollout to estimate a new leaf's value, AlphaZero queries a neural network `f_\theta(s) = (p(\cdot|s), v(s))` that outputs both a **policy prior** `p(\cdot|s)` (a distribution over actions at this state, used to guide future selection) and a **value estimate** `v(s)` (a direct, learned estimate of the expected outcome from this state, replacing the rollout entirely). This is a large practical win: a random rollout to the end of a long game is slow and extremely high-variance (a single random playout of Go is a very noisy signal), whereas a trained value network gives a much lower-variance point estimate in a single forward pass, at the cost of that estimate only being as good as the network's training.

**PUCT: incorporating the network's prior into selection.** AlphaZero replaces UCT's exploration term with **PUCT** (Predictor + UCT), incorporating the policy network's prior `p(s,a)` directly into the selection formula:

$$\text{PUCT}(s,a) = Q(s,a) + c\cdot p(s,a)\cdot\frac{\sqrt{\sum_b N(s,b)}}{1+N(s,a)}$$

**Why the prior term matters, mechanically.** Pure UCT's exploration bonus treats every unvisited or under-visited action as equally worth exploring, guided only by visit counts. PUCT's `p(s,a)` factor weights the exploration bonus by the network's own belief about which actions are promising *before any simulation has even been run* — an action the policy network considers very unlikely to be good gets a correspondingly smaller exploration bonus even at low visit counts, while an action the network favors gets explored more eagerly even before search has accumulated much direct evidence. This lets the search concentrate its (finite) simulation budget on the region of the tree the learned prior already suggests is promising, rather than spending simulations uniformly across every possible action the way pure UCT effectively does early on — a critical efficiency gain given the astronomically large branching factor of games like Go (roughly `250` legal moves per position, versus chess's roughly `35`) that made pure hand-crafted-evaluation search computationally infeasible in the first place.

**The self-play training loop.** AlphaZero's network is trained entirely from self-play: MCTS (using the current network) is run to select each move in a self-play game, the network's policy head is trained to match the *MCTS-improved* action distribution (the visit-count distribution at the root — MCTS itself, given a much larger effective search budget than a single forward pass, produces a genuinely improved policy relative to the raw network prior, which is what training the network toward it teaches), and the value head is trained toward the actual game outcome. This is a policy-improvement loop directly analogous to policy iteration's improvement step (`T31-mdp`/`T31-dynamic-programming`), except the "improvement operator" here is MCTS itself rather than an explicit greedy-w.r.t.-`Q` operation.

### The fundamental tradeoff: sample efficiency vs. compounding model error, derived

Consider a learned model with per-step prediction error `\epsilon` (some appropriately-defined divergence between the model's predicted next state and the true next state, e.g. total variation distance between `\hat{P}(\cdot|s,a)` and the true `P(\cdot|s,a)`). Planning or rolling out `H` steps into the future using this model compounds that error: informally, the probability the full `H`-step rollout diverges meaningfully from a trajectory the *true* dynamics would have produced grows roughly with `H\epsilon` in the best case (errors accumulating additively under favorable conditions) and can be substantially worse than linear when the dynamics are chaotic or when small early errors push the trajectory into regions of state space the model has seen little training data for (compounding *and* increasingly out-of-distribution for the model itself, a self-reinforcing failure). This is the single most important quantitative intuition in model-based RL: **short-horizon** model-based planning (a few steps, frequently replanned against fresh real observations, exactly as MCTS does — it plans ahead but only commits to *one* real action before re-running search from the new real state) is comparatively safe, because compounding error over a short horizon stays bounded; **long-horizon, open-loop** planning (committing to a long sequence of actions purely from the model with no intermediate real-world correction) is where compounding model error does the most damage, because there's no opportunity for reality to correct the trajectory before the error has already multiplied across many steps.

### Real numbers

- **MCTS simulation budget**: AlphaZero used roughly `800` simulations per move during self-play training in the original paper (varies by compute budget and time control; competitive/tournament settings can use far more).
- **Go's branching factor**: roughly `250` legal moves per position on average, versus chess's roughly `35` — the concrete reason brute-force search was computationally infeasible for Go long after it was tractable (with heuristic pruning) for chess.
- **PUCT exploration constant `c`**: commonly in the range `1`-`5` depending on implementation, tuned per game/domain; AlphaZero's original paper used a value derived to balance exploration against the network's growing confidence as training progresses.
- **UCB1's theoretical regret bound**: `O(\log T)` cumulative regret after `T` pulls in the classic multi-armed bandit setting — the formal justification (`T31-exploration`) for why the `\sqrt{\ln N(s)/N(s,a)}` form specifically, rather than an arbitrary alternative exploration bonus, is used in UCT.
- **Compounding model error**: no single universal number, but the qualitative result reported across model-based RL literature is consistent — model-based methods using a learned dynamics model for multi-step rollouts reliably show accuracy degrading sharply past roughly `5`-`15` steps of open-loop rollout in typical continuous-control benchmarks, which is why practical systems (MBPO and similar) use **short** model rollouts blended with real data rather than long, fully model-generated trajectories.

---

## Build it from scratch

A minimal MCTS implementation with UCT selection, illustrating all four phases on a generic two-player game interface — small enough to trace by hand, structured so swapping the random-rollout `simulate` function for a value-network call is the one-line change that turns this into an AlphaZero-style search:

```python
# untested sketch -- minimal MCTS with UCT selection
import math
import random

class Node:
    def __init__(self, state, parent=None):
        self.state = state
        self.parent = parent
        self.children = {}          # action -> Node
        self.N = 0                  # visit count
        self.W = 0.0                # total accumulated value
        self.untried_actions = state.legal_actions()

    def Q(self):
        return self.W / self.N if self.N > 0 else 0.0

    def uct_score(self, c=1.4):
        if self.N == 0:
            return float("inf")     # force-visit unvisited nodes first
        return self.Q() + c * math.sqrt(math.log(self.parent.N) / self.N)

def select(node):
    """SELECTION: walk down via UCT until an expandable node is found."""
    while not node.untried_actions and node.children:
        node = max(node.children.values(), key=lambda n: n.uct_score())
    return node

def expand(node):
    """EXPANSION: add one new child for an untried action."""
    action = node.untried_actions.pop()
    child_state = node.state.step(action)
    child = Node(child_state, parent=node)
    node.children[action] = child
    return child

def simulate(state, max_depth=100):
    """SIMULATION/ROLLOUT: classic MCTS uses a random policy to the end.
    Swap this function for a value-network call f_theta(state) -> v to get AlphaZero-style search."""
    depth = 0
    while not state.is_terminal() and depth < max_depth:
        action = random.choice(state.legal_actions())
        state = state.step(action)
        depth += 1
    return state.outcome()   # e.g. +1 win, -1 loss, 0 draw/ongoing

def backpropagate(node, value):
    """BACKPROPAGATION: push the result up every node on the path to the root."""
    while node is not None:
        node.N += 1
        node.W += value
        value = -value        # flip perspective each ply for a two-player zero-sum game
        node = node.parent

def mcts_search(root_state, n_simulations=800):
    root = Node(root_state)
    for _ in range(n_simulations):
        node = select(root)
        if not node.state.is_terminal():
            node = expand(node) if node.untried_actions else node
        value = simulate(node.state)
        backpropagate(node, value)
    # commit to the REAL action with the highest visit count, not highest raw value --
    # visit count is the more robust signal against a few lucky/unlucky rollouts
    return max(root.children.items(), key=lambda item: item[1].N)[0]
```

The `simulate` function is the single, deliberate seam this code is structured around: replacing its random-rollout body with `value = value_network(node.state)` (and correspondingly weighting `select`'s scoring by a policy network's prior, turning `uct_score` into a PUCT score) is the entire conceptual difference between classic MCTS and AlphaZero-style search — everything else (the tree structure, the four-phase loop, committing to the highest-visit-count root action) is unchanged.

---

## How it's done in production

| Layer | What you actually use | What it adds |
|---|---|---|
| Game-playing agents (perfect information, discrete action) | AlphaZero-style MCTS + learned value/policy network, or open-source reimplementations (Leela Chess Zero, KataGo) | Superhuman play without hand-crafted evaluation functions; the standard architecture since 2017 for this problem class |
| Robotics/continuous-control planning | Model Predictive Control (MPC) with a learned dynamics model, replanning at every real step (short-horizon, closed-loop) — e.g. PETS, MBPO-style approaches | Sample efficiency from a learned model while deliberately keeping the compounding-error window short via frequent real-world replanning |
| General-purpose sample efficiency in classic RL benchmarks | Dyna-style planning combined with model-free updates, or model-based value-expansion methods | Extracts more gradient signal per real environment interaction than pure model-free methods, when the environment/model is well-behaved enough to learn accurately |
| Anywhere the model is expensive or unreliable to learn well | Pure model-free methods instead (`T31-dqn`, `T31-ppo`, `T31-continuous-control`) | Avoids the compounding-model-error risk entirely at the cost of the sample-efficiency benefit a good model would have provided |

### Failure modes

| Symptom | Cause | Fix |
|---|---|---|
| A model-based agent performs excellently in "imagined" (model-simulated) rollouts but poorly when actually deployed | Compounding model error — the learned model is systematically wrong in ways that accumulate over the rollout horizon used for planning/training, and the agent has effectively overfit to its own model's mistakes | Shorten the planning/rollout horizon; interleave more real data; validate the model's multi-step prediction accuracy directly (not just one-step accuracy) before trusting long rollouts |
| MCTS search wastes simulation budget repeatedly exploring clearly-bad branches | Exploration constant `c` too high relative to the value scale, or (for AlphaZero-style search) a poorly-trained or miscalibrated policy prior giving bad initial guidance | Tune `c` to the actual value/reward scale; verify the prior network's calibration on held-out positions before trusting it to guide search efficiently |
| Dyna-Q's simulated updates make training worse, not better, compared to pure model-free Q-learning | The learned model is a poor approximation of the true dynamics (common early in training, when the model itself has seen little data) — simulated updates are training the value function toward a wrong target | Weight/limit simulated updates more conservatively early in training, or track model accuracy and reduce planning-step count `k` when model error is high |
| A game-playing agent using pure MCTS (no learned network) plays very strong tactically but poorly in tasks requiring deep positional judgment | Random rollouts are extremely high-variance and provide little genuine positional insight — MCTS alone is only as good as the rollout policy's ability to play out realistic games | Replace random rollouts with a learned value network (AlphaZero-style), or at minimum a stronger heuristic rollout policy |
| Model Predictive Control with a learned dynamics model performs well in early testing then degrades over a longer deployment | The model was validated only over short horizons matching training conditions; real-world drift (wear, changing conditions) pushes the model out of its accurate regime over time | Periodically retrain/recalibrate the dynamics model against fresh real data; monitor prediction error online as a trigger for retraining |

---

## Tradeoffs & when NOT to use it

- **Don't use long-horizon, open-loop model-based planning when the learned model's multi-step accuracy hasn't been directly validated.** One-step prediction accuracy looking good is not evidence multi-step rollouts are trustworthy — compounding error is the specific, derivable reason these are different questions.
- **Prefer short-horizon, frequently-replanned model-based control (MPC-style) over long open-loop model-based plans** whenever real observations are available to correct course — this is exactly why MCTS itself only commits to one real action per search before replanning from the new real state, rather than executing a long sequence purely from the tree's deepest simulated line.
- **Don't reach for MCTS/AlphaZero-style planning outside its natural fit (discrete actions, a known or learnable model, enough compute budget for many simulations per real decision).** It's a poor match for continuous action spaces without adaptation, and for problems where a real-time decision budget doesn't allow hundreds or thousands of simulations per move.
- **Model-based methods are the wrong default when the true dynamics are hard to model accurately** (highly stochastic, chaotic, or simply data-scarce for the model itself) — a pure model-free method, while less sample-efficient, never risks the specific compounding-model-error failure mode this module derives, because it never plans through a learned model's extrapolation at all.
- **Weigh the real engineering cost of maintaining a second learned system (the model) alongside the policy/value function** — a model-based system has strictly more moving parts to validate, monitor, and debug than a comparable model-free one, and that added complexity needs to be justified by a real, measured sample-efficiency win, not assumed.

---

## Interview questions

### Q1 — What's the core difference between Dyna-Q's use of a model and MCTS's use of a model?
**Testing:** whether "model-based RL" is understood as a family with genuinely different mechanisms, not one technique.
**Answer:** Dyna-Q uses the model to generate *additional simulated training data* between real interactions — extra Q-learning updates on model-sampled transitions, extracting more learning signal per real environment step, but the model isn't used at actual decision time (action selection is still the ordinary `\arg\max_aQ(s,a)`). MCTS uses the model to *search ahead at decision time* — build a tree of possible futures before committing to the current real action, then discard the search tree and replan from scratch at the next real state. Both exploit a model for sample/decision efficiency, but one manufactures training data and the other performs lookahead planning.
**Follow-up trap:** *"Could you combine both — use a model for both extra training data and decision-time search?"* — yes, and this is common in practice (e.g. AlphaZero-style self-play generates training data for the network from MCTS-improved action distributions, which is simultaneously using the model for planning at decision time *and* producing improved training targets from that planning) — the two uses aren't mutually exclusive, and treating them as alternatives rather than composable is a real gap in understanding.

### Q2 — Derive the UCT selection formula's exploration term. Where does it come from, and what does the `\log N(s)` in the numerator actually control?
**Answer:** UCT applies the UCB1 bandit algorithm at every tree node, treating each node's children as an independent multi-armed bandit. UCB1's confidence bound gives `Q(s,a)+c\sqrt{\ln N(s)/N(s,a)}` — the square-root term is a confidence-interval width that shrinks as `N(s,a)` (visits to this specific child) grows, reflecting more evidence for that child's average value, while growing (slowly, logarithmically) with `N(s)` (total parent visits), which prevents the search from permanently abandoning a child after an unlucky early run — even a well-visited child's exploration bonus keeps loosening slightly as the parent accumulates far more total visits than that child has received.
**Follow-up trap:** *"Why logarithmic in `N(s)` specifically, rather than, say, linear?"* — this comes directly from UCB1's formal regret-bound derivation (a Hoeffding-inequality-based confidence bound), which gives an `O(\log T)` cumulative regret guarantee after `T` pulls in the classic bandit setting (`T31-exploration`) — the logarithmic form isn't an arbitrary design choice, it's the specific rate that this regret bound requires to hold.

### Q3 — Explain precisely how AlphaZero's PUCT differs from classic UCT, and why the prior term matters for a game like Go specifically.
**Answer:** PUCT adds a policy-network prior `p(s,a)` directly into the exploration bonus: `Q(s,a)+c\cdot p(s,a)\cdot\sqrt{\sum_bN(s,b)}/(1+N(s,a))`, versus UCT's prior-free `c\sqrt{\ln N(s)/N(s,a)}`. The prior weights exploration toward actions the network already believes are promising, even before any simulation has run — concentrating the finite simulation budget where it's more likely to matter. This matters especially for Go, whose branching factor (~250 legal moves) is roughly seven times chess's (~35); with that many children per node, uniformly exploring every action a few times before any of them accumulate meaningful statistics (pure UCT's early behavior) wastes an enormous fraction of a realistic simulation budget on the network's own weak initial beliefs, whereas PUCT lets the network's prior immediately focus search on a much smaller, more promising subset.
**Follow-up trap:** *"If the policy network's prior is badly miscalibrated for some position, does PUCT's search eventually recover the correct answer anyway, given enough simulations?"* — yes, eventually — the `1+N(s,a)` denominator means the prior's influence on the exploration bonus *decays* as an action accumulates real visits and its own `Q(s,a)` statistic becomes more trustworthy, so with enough simulation budget the search can still discover a genuinely good action the prior initially underrated, just less efficiently (more wasted simulations) than if the prior had been well-calibrated to begin with.

### Q4 — Derive, at least informally, why compounding model error is a genuinely different problem from one-step model prediction error, and why that distinction matters for deciding planning horizon.
**Answer:** A model with per-step error `\epsilon` produces a rollout whose divergence from the true trajectory grows with the number of steps compounded through — informally on the order of `H\epsilon` in a favorable (additive-error) case, and potentially much worse when small errors push the simulated trajectory into regions of state space the model has little accurate data for, which is itself a *further* source of error (increasingly out-of-distribution for the model, not just accumulating a fixed per-step error rate). One-step accuracy being high says nothing directly about `H`-step accuracy for `H>1`, because it doesn't measure whether the errors compound benignly or catastrophically. This is why practical model-based systems bound the planning horizon short and replan frequently against real observations, rather than trusting a long, open-loop rollout purely from the model.
**Follow-up trap:** *"Given this, is there ever a legitimate reason to trust a very long model-based rollout?"* — only when the model's accuracy has been *directly validated* at the relevant multi-step horizon (not just one-step), typically in settings with very well-characterized, close-to-deterministic dynamics (some physics simulators, certain robotics settings with precise system identification) — the default assumption for a learned, imperfect model should be that long open-loop trust is unjustified until specifically demonstrated otherwise.

### Q5 — Why does AlphaZero replace random rollouts with a learned value network, beyond just "it's faster"?
**Answer:** Speed is real (a single forward pass versus playing out a full random game), but the more important reason is variance: a random rollout to a game's terminal outcome is an extremely high-variance, weakly-informative signal (a single random playout of Go bears little resemblance to how the game would actually be played by two skilled agents from that position), whereas a trained value network provides a much lower-variance point estimate that has learned to correlate with actual outcomes across many training games. Lower-variance value estimates mean each individual MCTS simulation contributes a more reliable signal to backpropagation, so the search converges toward an accurate assessment with fewer total simulations than pure random-rollout MCTS would need for comparable reliability.
**Follow-up trap:** *"Does this mean AlphaZero-style search is strictly better than classic random-rollout MCTS in every setting?"* — no — it requires a domain where a value/policy network *can* actually be trained to meaningful accuracy (enough self-play data, enough training compute, a learnable enough game/environment); classic random-rollout MCTS remains a reasonable, much-simpler-to-implement choice in settings without the infrastructure or training budget to develop a good network, or where a cheap, decent heuristic rollout policy already exists and a full learned network isn't worth the added system complexity.

### Q6 — A colleague claims Dyna-Q's simulated updates are "free" sample-efficiency gains with no real downside compared to pure model-free Q-learning. Is this accurate?
**Testing:** whether the compounding-error risk is understood as applying to Dyna-Q too, not just long-horizon MCTS/MPC settings.
**Answer:** Not accurate. Simulated updates are only as good as the learned model's accuracy at the `(s,a)` pairs being sampled for planning. Early in training (or in regions of state space the agent has visited rarely), the model itself is likely to be inaccurate, and simulated Q-learning updates against a wrong model can train the value function toward a systematically wrong target — the same "training loss looks fine but targets are wrong" failure signature as DQN (`T31-dqn`), just introduced via the model instead of via a stale target network. It's a real efficiency gain *conditional on* reasonable model accuracy, not an unconditionally free lunch.
**Follow-up trap:** *"How would you concretely detect that Dyna-Q's planning step is hurting rather than helping?"* — track real (not simulated) episode return over training with and without the planning step as an ablation, and separately monitor the model's own prediction accuracy on held-out real transitions — if planning-enabled training underperforms model-free-only training, or if model accuracy is measurably poor in the regions being sampled for planning, that's direct evidence the "free" simulated updates are net-negative in the current regime.

### Q7 — Why does MCTS commit to only one real action per search, rather than executing the full sequence of moves along its most-visited simulated line?
**Testing:** the closed-loop replanning discipline that keeps compounding error bounded.
**Answer:** The tree built during one search is itself built partly from the model's own uncertainty (or, in the real-environment two-player-game case, from an opponent whose actual move might not match what MCTS explored most) — committing only to the immediate next action and then replanning fresh from the new, actually-observed real state means any error in the deeper, less-explored parts of the tree never gets executed blindly; it's discarded and re-derived from real information at every step. Executing a long simulated line open-loop would forgo this correction opportunity entirely, exposing the agent to however much the deeper tree diverges from what actually happens.
**Follow-up trap:** *"Does this discipline fully eliminate the compounding-error risk, or just bound it?"* — just bounds it, to roughly one search's worth of lookahead depth rather than an unboundedly long open-loop plan — a badly miscalibrated model or value network can still produce a poor immediate action choice even with this replanning discipline; the discipline limits *how far* any single planning error can propagate before reality has a chance to correct it, it doesn't make any individual search's conclusions perfectly reliable.

### Q8 — Compare the role of a value function/critic in AlphaZero's MCTS versus in PPO's actor-critic (`T31-ppo`). Are they serving the same purpose?
**Testing:** synthesis across the track, distinguishing genuinely similar-sounding but structurally different uses of "value function."
**Answer:** Structurally related but used differently. PPO's critic `V_\phi(s)` is used to compute a bootstrapped advantage estimate for training the *actor's parameters* via gradient ascent — it never directly influences which action gets executed at decision time beyond shaping the training signal. AlphaZero's value network `v(s)` is used *inside the search itself*, at decision time, to estimate leaf-node values during MCTS's simulation phase, directly influencing which branches of the tree get explored and ultimately which real action is selected — the value network's role is a component of an explicit search procedure, not (only) a training-time gradient-shaping signal. Both are learned value estimators trained toward observed outcomes, but one feeds a gradient computation and the other feeds a lookahead search algorithm.
**Follow-up trap:** *"Could you use MCTS's search procedure to select actions for a policy being trained by PPO instead of by self-play imitation of MCTS's output?"* — this is roughly the idea behind some hybrid model-based-plus-policy-gradient approaches — using search to produce better action choices (and possibly better training targets) than the raw policy network alone would choose, then training the policy toward the search-improved choices — genuinely related to AlphaZero's core loop, but requires the search to be computationally affordable at whatever frequency training updates are needed, a real cost PPO's simpler forward-pass-only action selection doesn't have.

### Q9 — Design a model-based RL system for a warehouse robot's path planning, where the environment is mostly deterministic (known map) but has some genuinely unpredictable elements (other moving robots/workers). What planning horizon and replanning frequency would you choose, and why?
**Testing:** applying the compounding-error tradeoff to a realistic, mixed-determinism setting.
**Answer:** Use a short-horizon, frequently-replanned approach (MPC-style, or MCTS with a limited simulation depth per real decision) rather than a long open-loop plan — the map's deterministic parts are safe to model and plan through accurately, but the unpredictable elements (other agents) are exactly where a model's predictions will be least reliable, and any error there compounds fastest precisely in the parts of the plan furthest from the current, actually-observed real state. Replan frequently enough (ideally every real step, or every few steps) that the unpredictable elements' actual observed positions correct the plan before compounding error in that portion of the model has a chance to matter.
**Follow-up trap:** *"Would you model the other robots/workers explicitly, or treat their movement as part of the environment's stochastic transition function?"* — either is defensible depending on available information: if you can observe or communicate with the other agents' own planned paths, explicitly modeling them (even a simple predictive model of their likely next moves) gives a better-informed model than treating them as generic environmental stochasticity; if no such information is available, folding their unpredictability into the transition model's stochasticity is the more honest framing — but either way, the short-horizon-plus-frequent-replanning discipline is what actually protects against the resulting model error, not which framing is chosen.

### Q10 — Why did Go resist strong AI play for decades longer than chess, and what does that history tell you about when hand-crafted search-plus-evaluation approaches break down?
**Testing:** whether the lineage's "what came before" pain is genuinely understood, not just recited.
**Answer:** Chess has a moderate branching factor (~35) and reasonably effective hand-crafted evaluation functions (material count, positional heuristics) that let alpha-beta search reach competitive strength with a tractable search depth. Go's branching factor (~250) makes brute-force or lightly-pruned search computationally far more expensive at comparable depth, and — the more fundamental problem — no one found a good hand-crafted evaluation function for Go positions; the game's strategic complexity resisted the kind of material/positional heuristics that worked for chess, meaning even an affordable search had nothing reliable to evaluate leaf positions with. This combination (larger search space, no usable hand-crafted evaluation function) is exactly what MCTS's random-rollout evaluation and, later, AlphaZero's learned value network were built to solve — a leaf's value no longer needs a human-designed heuristic at all.
**Follow-up trap:** *"Does this history generalize into a rule for when to expect hand-crafted evaluation-plus-search to fail more broadly, beyond games?"* — yes, informally: expect hand-crafted evaluation-plus-search approaches to struggle whenever (a) the branching factor or horizon makes exhaustive or lightly-pruned search computationally infeasible, and (b) domain experts can't articulate a reliable, generalizable heuristic for "how good is this partial state" — both conditions together are the signature that a learned value/policy network (trained from outcomes rather than hand-specified) is likely to outperform a hand-crafted alternative, which is the broader lesson AlphaZero's success generalized beyond board games specifically.

---

## Red flags that fail you

- Conflating Dyna-Q's use of a model (extra training data) with MCTS's use of a model (decision-time search) as if they were the same mechanism.
- Reciting the UCT/UCB1 formula without being able to explain what the exploration term is actually balancing or where the `\log` comes from.
- Describing AlphaZero as "just MCTS" without naming the two specific structural changes (learned value/policy replacing rollouts, PUCT's prior term replacing plain UCT).
- Treating a learned model's one-step prediction accuracy as sufficient evidence that multi-step rollouts through it are trustworthy.
- Not knowing why MCTS replans from scratch after every real action rather than executing its full simulated line.
- Assuming model-based methods are strictly more sample-efficient with no accompanying risk, missing the compounding-model-error tradeoff entirely.
- Confusing Go's and chess's relative difficulty for AI as being purely about compute, missing the "no good hand-crafted evaluation function" half of the explanation.

---

## Cheat card

```
MODEL-FREE vs MODEL-BASED: model-free learns V/Q/policy directly from real data,
  no explicit P(s'|s,a) ever built. Model-based learns/uses a model for either
  (1) manufacturing simulated training data (Dyna-Q) or (2) decision-time
  lookahead search (MCTS) -- two DISTINCT uses, composable, not the same thing.
DYNA-Q         real step -> 1 real Q-learning update + update model
               THEN k simulated steps sampled from LEARNED model -> k more
               Q-learning updates, free (no real env interaction)
               RISK: simulated updates only as good as model accuracy --
               poor model = training toward a wrong target, same failure
               signature as DQN's "loss looks fine, targets are wrong"
MCTS 4 PHASES  Selection (UCT) -> Expansion (add leaf) -> Simulation/rollout
               (estimate leaf value) -> Backpropagation (push result up path)
UCT FORMULA    UCT(s,a) = Q(s,a) + c*sqrt(ln N(s) / N(s,a))
               = UCB1 bandit algo applied at every tree node (T31-exploration)
               sqrt term SHRINKS as N(s,a) grows (more evidence), grows
               (slowly, log) with N(s) -- prevents PERMANENT abandonment
               of a child after unlucky early rollouts. UCB1 regret: O(log T)
ALPHAZERO      replaces RANDOM ROLLOUT with learned value net v(s) (lower
               variance, single forward pass, not a full random playout)
PUCT           PUCT(s,a) = Q(s,a) + c*p(s,a)*sqrt(sum_b N(s,b))/(1+N(s,a))
               p(s,a) = policy network's PRIOR -- concentrates simulation
               budget on promising branches instead of uniform exploration
               (critical given Go's ~250 branching factor vs chess's ~35)
SELF-PLAY LOOP MCTS's visit-count distribution at root = IMPROVED policy
               target (policy iteration's improvement step, MCTS-as-operator)
               value head trained toward actual game outcome
COMPOUNDING    rollout divergence grows ~H*epsilon (favorable case) or worse
ERROR          if errors push trajectory OUT OF DISTRIBUTION for the model
               -> SHORT horizon + FREQUENT replanning against real obs is
               the standard mitigation (MCTS commits to 1 real action, replans)
NUMBERS        AlphaZero ~800 simulations/move (self-play); Go ~250 vs chess
               ~35 branching factor; UCB1 regret O(log T); model-based
               rollout accuracy typically degrades sharply past ~5-15 steps
WHEN NOT TO USE model-based: dynamics hard to model accurately (chaotic,
  stochastic, data-scarce) -- pure model-free avoids compounding-error risk
  entirely at the cost of sample efficiency. MCTS: continuous actions
  (poor native fit), or real-time budgets too tight for many simulations/move.
```

## Sources

- [Sutton — Integrated Architectures for Learning, Planning, and Reacting Based on Approximating Dynamic Programming (Dyna, 1990)](https://dl.acm.org/doi/10.1016/B978-1-55860-141-3.50030-4) — accessed 2026-08-03
- [Kocsis & Szepesvári — Bandit Based Monte-Carlo Planning (UCT, 2006)](https://link.springer.com/chapter/10.1007/11871842_29) — accessed 2026-08-03
- [Auer, Cesa-Bianchi & Fischer — Finite-time Analysis of the Multiarmed Bandit Problem (UCB1, 2002)](https://link.springer.com/article/10.1023/A:1013689704352) — accessed 2026-08-03
- [Silver et al. — Mastering the game of Go without human knowledge (AlphaGo Zero, 2017), Nature](https://www.nature.com/articles/nature24270) — accessed 2026-08-03
- [Silver et al. — A general reinforcement learning algorithm that masters chess, shogi, and Go through self-play (AlphaZero, 2018), Science](https://www.science.org/doi/10.1126/science.aar6404) — accessed 2026-08-03
- [Chessprogramming Wiki — UCT](https://www.chessprogramming.org/UCT) — accessed 2026-08-03
- [Monte-Carlo Graph Search for AlphaZero (2020)](https://arxiv.org/pdf/2012.11045) — accessed 2026-08-03

## Changelog
- 2026-08-03 — created
