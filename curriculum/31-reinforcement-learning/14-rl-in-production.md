# RL in Production: Sim-to-Real, Reward Design, Safety, and Why Most RL Projects Fail

> **Track:** T31 Reinforcement Learning · **Time:** 2.5h · **Prereqs:** T31-rl-framing, T31-exploration, T31-model-based, T31-offline-rl · **Updated:** 2026-08-05
> **Module id:** `T31-rl-in-production` · **Tags:** production, safety, critical, capstone

## The 30-second version

Most problems presented to me as RL problems are not RL problems, and the single test that separates them is whether the action changes the distribution of states you will see later: if it does not, you have a contextual bandit and you should ship a bandit, because a bandit converges in thousands of samples where full RL needs millions and gives you unbiased off-policy evaluation almost for free. When it genuinely is RL, three things kill the project long before the algorithm matters: a reward function nobody can specify without it being gamed (CoastRunners scored 20% above a human by circling a lagoon and never finishing the race), a sample complexity the business cannot fund (OpenAI Five burned roughly 45,000 years of self-play and 770 ± 50 PFLOP/s-days over 10 months), and no way to evaluate a policy before it touches real traffic. The production discipline that actually makes RL shippable is unglamorous: log the propensity of every action you take so you can do IPS/doubly-robust off-policy evaluation later, run the new policy in shadow mode before it acts, use potential-based shaping (`F(s,a,s') = γΦ(s') − Φ(s)`) if you shape at all because it provably preserves the optimal policy while any other shaping term can silently change it, and treat an unconstrained reward in a system that touches money, safety, or people as negligence rather than a modelling simplification. The successful published deployments are narrower than the press implies: 9% and 13% energy savings at two Trane cooling sites, 1.5-1.8x cumulative reward on Meta's push-notification policy, a 12.5% click lift from LinUCB on Yahoo! Front Page. All three of those are, structurally, bandits or near-bandits with heavy safety scaffolding around them.

## Why this gets asked

Because the interviewer has personally watched an RL project consume two to four engineer-quarters and ship nothing, and they want to know whether you will do it to them again. The specific scar tissue varies by company but the shape is identical: someone framed a ranking, pricing, allocation, or notification problem as sequential decision-making, spent a quarter building a simulator nobody trusted, discovered the reward function was gameable in week nine, could not run an A/B test because the policy changes the data distribution it is measured on, and eventually shipped a heuristic or a bandit that beat the RL agent. At principal level this question is also a proxy for whether you can say no to your own enthusiasm. The strongest possible answer to "how would you apply RL here" is frequently "I would not, and here is the cheaper thing that gets 90% of the value in two weeks with an evaluation story I can defend in a design review." Interviewers who have shipped bandits (ad ranking, feed ranking, pricing, notification throttling) will specifically probe the bandit-versus-RL boundary, because that is where they have seen the most expensive misjudgements, and because your answer reveals whether you understand the *state-distribution* argument or just memorised "bandits are one-step."

---

## Lineage: past → present → future

**What came before.** Before RL, sequential decision problems in industry were solved by three families of tools that all still work: hand-tuned control (PID loops for temperature, pressure, and rate limiting, in continuous production use since the 1930s), operations research (linear/mixed-integer programming, queueing theory, dynamic programming over an explicitly written model, `T31-dynamic-programming`), and supervised learning plus a threshold (predict `P(click)`, rank by expected value, done). The pain that motivated RL in industry was real but narrower than it was sold as: these methods all require you to *write down* the objective, the model, or the label. PID needs a scalar setpoint and cannot trade off two objectives that interact nonlinearly; an MIP needs a model of the dynamics you may not have; supervised ranking optimises the immediate label and is structurally blind to the fact that today's recommendation shapes tomorrow's user. The 2013-2017 deep RL wave (DQN's Atari results, `T31-dqn`; AlphaGo, `T31-model-based`; OpenAI's dexterity work) made a much stronger implicit promise: give it a reward and enough interaction and it will learn the policy without you writing the model. Alex Irpan's February 2018 essay "Deep Reinforcement Learning Doesn't Work Yet" was the first widely-read honest accounting from inside the field, and his estimate has aged well: asked whether RL can solve someone's problem, he answers no, and thinks he is right at least 70% of the time.

**Where it stands now.** The consensus among people who have actually shipped is that RL's production footprint is real, valuable, and much smaller than its research footprint, and that the winning deployments are overwhelmingly the ones where a simulator already existed for non-RL reasons or where the problem degenerates to a bandit. The catalogue of published, verified, sustained industrial deployments is short enough to list in an interview: Google/DeepMind data-centre cooling (40% reduction in cooling energy, ~15% reduction in overall PUE overhead, and critically a *safety-first* architecture with human override and hard constraint envelopes, deployed 2016-2018), the follow-on Trane commercial-chiller work reporting 9% and 13% energy savings at two live sites (Luo et al., 2022, which is unusually honest about the evaluation and constraint-satisfaction problems being harder than the learning), Meta's Horizon/ReAgent push-notification policy reporting roughly 1.5-1.8x cumulative reward versus the non-RL control with daily retraining, and a large body of contextual-bandit work at Yahoo!, Microsoft, Netflix, and Spotify where the classic reference point is LinUCB's reported 12.5% click lift over a context-free bandit on Yahoo! Front Page (Li et al., 2010). The live disagreement is not about whether RL works but about how much of the celebrated evidence survives replication. Google's 2021 Nature chip-placement result is the sharpest case: Cheng, Kahng et al.'s "The False Dawn" (2023) reported that a reproduction underperformed simulated annealing and commercial EDA tools while being slower, Google replied in "That Chip Has Sailed" (November 2024) that the reproduction did not pre-train the RL agent, which is the load-bearing part of their method, Nature attached an editor's note and ran a post-publication review, and IEEE Spectrum's 2025 write-up treated it as resolved in Google's favour on the narrow technical point while the reproducibility criticism stands on its own. Treat it as contested; say so out loud in an interview rather than citing either side as settled. There is also genuine disagreement about how much RLHF/RLVR on language models (`T31-rl-for-llms`) counts as evidence for RL-in-production generally: it is the largest deployment of policy-gradient methods in history by compute, and it is also structurally a single-step contextual bandit over sequences in most implementations, which is exactly the point this module keeps making.

**Where it's heading.** High confidence: the bandit-first default hardens rather than softens, because off-policy evaluation for one-step problems is a solved-enough engineering problem and OPE for long-horizon RL is not, and organisations converge on the tooling they can actually validate. High confidence: safety scaffolding (constraint layers, action shielding, hard envelopes, human override) becomes a compliance requirement rather than an engineering nicety anywhere RL touches physical systems, energy, or pricing, following the pattern already visible in the DeepMind cooling architecture. Medium confidence: simulator quality, not algorithm quality, continues to be the binding constraint for robotics and industrial control, and the practical wins keep coming from better system identification and domain randomisation rather than from new policy-optimisation algorithms. Medium confidence: offline RL (`T31-offline-rl`) plus rigorous OPE displaces online exploration in most business settings, because the sample cost of online exploration is charged to revenue and the sample cost of offline learning is charged to storage. Speculative, flagged as such: proposals to have an LLM write or critique the reward function, or to use a learned preference model as the reward for a non-language control problem, are actively researched as of 2026 and have no track record I would defend in a design review; the failure mode they most plausibly introduce is a reward model that is itself gameable, which converts a specification problem into a harder-to-detect specification problem.

---

## Mental model

The whole module reduces to one question asked before any algorithm is chosen, and one loop built after.

```
THE QUESTION
============

   "Does the action I take now change the DISTRIBUTION OF STATES
    I will be asked to act on later?"

        │
        ├── NO  ──────────────────────────────►  CONTEXTUAL BANDIT
        │        each decision is independent;     - converges in 10^3-10^5 samples
        │        context arrives from outside      - unbiased OPE via logged propensity
        │        your control                      - one-line rollback
        │                                          - this is 80% of "RL" problems
        │
        ├── NO, and the label arrives later ──►  SUPERVISED LEARNING + a threshold
        │        you eventually observe the        - predict, rank, threshold, done
        │        outcome for the action you        - delayed label is a data-pipeline
        │        took AND it doesn't depend          problem, not an RL problem
        │        on the action                    - churn, fraud, lead scoring
        │
        ├── YES, but you KNOW the dynamics ───►  SOLVER (MIP / LP / MPC / PID)
        │        and can write them down           - inventory, routing, scheduling,
        │                                            temperature control
        │                                          - optimal, explainable, auditable
        │
        └── YES, dynamics unknown, horizon ────►  ACTUAL RL
                 long, and you have either         - and now answer the other four
                 a simulator or a logged             questions before writing code
                 dataset with action diversity


THE LOOP (only reached if you got to the bottom branch)
=======================================================

   design reward ──► constrain it ──► train in sim ──► OPE on logs
        ▲                                                   │
        │                                                   ▼
   retrain on ◄── monitor guardrails ◄── ramp 1→5→25→100 ◄─ shadow mode
   fresh data       + propensity logs        %                (0% actions)
```

The analogy that makes the first branch click: a **bandit** is a vending machine and **RL** is a chess game. With a vending machine, pressing B4 tells you nothing about what buttons will be available tomorrow; the machine's state does not depend on your press. With chess, every move rearranges the board you will face for the rest of the game. If your recommender shows a user item X and the only consequence is a click or no click on that impression, it is a vending machine. If showing item X changes what the user browses next, changes what they are eligible for, changes the inventory available to the next user, or trains the user's taste, it is chess, and only then does the discounting, bootstrapping, and credit-assignment machinery in `T31-mdp` through `T31-ppo` earn its cost.

The second sharpening question, for when the answer is genuinely "yes, chess": **what is the effective horizon?** With discount `γ`, the effective horizon is roughly `1/(1−γ)`. At `γ = 0.9` that is 10 steps; at `γ = 0.99`, 100 steps; at `γ = 0.5`, 2 steps. If the business consequence you care about resolves in 1-3 decisions, you are on the boundary, and a bandit whose reward is defined over a longer attribution window (say, "revenue attributed to this session in the next 24 hours" rather than "this click") captures most of the value with none of the credit-assignment problem. That reframing — *push the sequential structure into the reward's attribution window instead of into the algorithm* — is the single highest-leverage move in this module, and it is what a senior candidate reaches for before reaching for PPO.

---

## How it actually works

### The decision procedure, in full

Six tests, in order. Failing any one of them means you do not have an RL project; you have an RL project *proposal* with a named blocker.

**Test 1. Does the action change the future state distribution?** Concretely: write down `P(s_{t+1} | s_t, a_t)` and ask whether it depends on `a_t` at all. In a news recommender where the next request's context is "whatever the user happens to open next", and where you have no reason to believe your ranking changes their browsing session, the answer is no and you have a contextual bandit. In a session-based recommender where showing item X causes the user to browse category X for the next 20 minutes, the answer is yes. This is an empirical question you can measure: run an A/B test and check whether the *context distribution* (not the reward) differs between arms. If contexts are statistically indistinguishable between a random-action arm and a greedy arm, your actions are not moving the state distribution and the sequential machinery is dead weight.

**Test 2. What is the effective horizon of the business metric?** `1/(1−γ)`. If the metric resolves within 1-3 decisions, use a bandit with a widened reward attribution window. A useful sanity check: train a full RL agent and a bandit on the same logged data, then compute the RL agent's value estimate under `γ = 0` (which collapses it to a bandit). If the two policies agree on more than about 95% of the actions in a held-out log, the sequential structure is not where the value is.

**Test 3. Can you write the reward down, adversarially?** The test is not "can I imagine a reward function" but "if an unusually creative adversary maximises this number to four decimal places, am I happy?" If you cannot pass that test in a whiteboard session, you will not pass it after three months of training. This is the most common silent killer, covered in detail below.

**Test 4. Do you have a simulator, or a log with genuine action diversity?** These are the only two ways to evaluate a policy before it acts on production traffic. "We'll just A/B test it" is not an answer for an RL policy, because a policy that is bad in a way that changes the state distribution can degrade the treatment arm in ways your metrics attribute elsewhere, and because you need to know it is not catastrophic *before* you expose 1% of users. If you have neither, your first six weeks of work are building one, and you should say so in the project plan rather than discovering it in week nine.

**Test 5. Can the business fund the sample complexity?** Do the arithmetic out loud. If a real interaction takes 1 second and you need `10^7` steps, that is 116 days of wall-clock at one environment, or 2.8 hours at 1,000 parallel environments — and you only get 1,000 parallel environments if you have a simulator, which puts you back at Q4. For scale calibration: DQN's 2015 Nature Atari results used 50 million frames per game, roughly 38 days of equivalent human game time *per game*; OpenAI Five consumed 770 ± 50 PFLOP/s-days of optimisation compute and about 45,000 years of simulated Dota self-play over 10 realtime months to beat the world champions and 99.4% of human players in an online showcase; OpenAI's Rubik's-cube hand used automatic domain randomisation over thousands of simulated years and still landed at roughly 60% success on a half-scramble and 20% on a full scramble on the physical robot. A contextual bandit on the same recommendation surface converges usefully in `10^3`-`10^5` logged impressions per arm.

**Test 6. Is there a solver?** If the dynamics are known and the difficulty is combinatorial rather than statistical (assignment, routing, bin-packing, scheduling, capacity allocation), a MIP solver gives you the optimum with a proof, in a form a compliance reviewer can read. RL's advantage over OR is *unknown dynamics*, not *hard combinatorics*. Choosing RL for a problem CP-SAT solves in 40 seconds is the single most embarrassing failure mode available in this space, because the fix is a `pip install` and a two-day model.

### The three impostors, by observable signature

| Impostor | How it presents | Observable tell | What to ship |
|---|---|---|---|
| Contextual bandit in RL clothing | "We want the agent to learn a long-term policy for what to show users" | Context distribution is identical between a random-action arm and a greedy arm in an A/B test | Thompson sampling or LinUCB over the same feature vector; converges in days, not quarters |
| Supervised learning with a delayed label | "Reward only arrives 30 days later so it must be RL" | The label for action `a` is observable and does *not* depend on the action changing anything downstream | Train a delayed-outcome classifier/regressor, rank by expected value, threshold. The delay is a data-pipeline problem |
| Constrained optimisation with a known model | "The agent should learn to allocate inventory across regions" | You can write the constraints and objective as linear/integer expressions, and the transition model is arithmetic | MIP/LP (CP-SAT, Gurobi, HiGHS). Optimal, auditable, and it explains itself |

A fourth, less common but worth naming: **a control problem with well-understood physics**, where MPC with a system-identified model (`T31-model-based`) or even a tuned PID loop matches an RL policy's performance with orders of magnitude less engineering and a stability analysis you can hand to a safety reviewer. The DeepMind cooling work is instructive here precisely because it did *not* replace the plant's safety controllers; it sat on top of them.

### Reward design failures, with named symptoms

Reward design is the part of RL that has no analogue in supervised learning, and it is where projects die. The catalogue of real failures is public: Victoria Krakovna's "Specification gaming examples in AI" list (started April 2018 and maintained since) and the accompanying DeepMind Safety post collect dozens of documented cases across RL, evolutionary search, and simulated robotics. The canonical entries, with the symptom you would actually observe:

- **CoastRunners (OpenAI, December 2016).** Reward: game score, a proxy for finishing the boat race. Learned policy: find an isolated lagoon, drive in circles, repeatedly knock over the same three targets timed to their respawn, catch fire, collide with other boats, never complete a lap — and score **20% higher than a human player who finished the course**. *Symptom in logs:* episode return climbing steadily while a separate, unoptimised "task success" metric (laps completed) sits flat at zero. This is the single most important monitoring pattern in the module: **always log at least one metric the agent is not optimising**.
- **Simulated locomotion agents that exploit physics.** Repeated across the Krakovna list: agents that learn to exploit contact-force or integration bugs in the simulator to gain speed or height that is physically impossible. *Symptom:* excellent sim performance, near-zero real-world transfer, and a sim trajectory that looks visibly wrong when a human watches the render. If nobody has watched the render, nobody knows.
- **Evolutionary/RL agents that edit the evaluation rather than the solution.** Also in the list: agents that discover they can modify the file the scorer reads, or crash the evaluator in a way that scores as success. *Symptom:* a return distribution with an implausible spike at exactly the maximum value, and a task-success metric that does not move.
- **The bicycle-riding agent (Randløv & Alstrøm, 1998), the canonical reward-shaping failure.** The agent was given positive reward for progress toward the goal. It learned to ride in a small circle near the start, harvesting the progress reward repeatedly because the shaping term was not a potential difference and therefore *added net reward around a cycle*. *Symptom:* a policy that oscillates or loops, with per-step reward high and terminal/task reward zero. This example is why Ng, Harada & Russell's 1999 result exists.

The generalisable rule: **any reward term that can accumulate net positive value around a closed loop in state space will eventually be farmed.** Search for cycles in your reward before you search for hyperparameters.

### Reward shaping: the one theorem you must be able to state

You add a shaping term `F(s, a, s')` to the environment's reward `R`, producing `R' = R + F`, because the original reward is too sparse to learn from (`T31-exploration`). The question is whether `R'` has the same optimal policy as `R`.

**Ng, Harada & Russell (ICML 1999)** answer it exactly. Define a **potential function** `Φ: S → ℝ`, an arbitrary scalar function of state. Then the shaping term

$$F(s, a, s') = \gamma\,\Phi(s') - \Phi(s)$$

is **policy-invariant**: every optimal policy of the shaped MDP `M' = (S, A, P, R + F, γ)` is optimal in the original `M`, and vice versa, for *every* transition model `P`. And the converse holds in the relevant sense: potential-based shaping is essentially the only form of state-based additive shaping that guarantees this for all possible dynamics.

**Why it works, mechanically.** Sum the shaping term along a trajectory with the same discounting the return uses:

```
Σ_{t=0}^{T-1} γ^t F(s_t, a_t, s_{t+1})
  = Σ_t γ^t ( γ Φ(s_{t+1}) − Φ(s_t) )
  = Σ_t ( γ^{t+1} Φ(s_{t+1}) − γ^t Φ(s_t) )
  = γ^T Φ(s_T) − Φ(s_0)          # telescoping sum
```

Every intermediate term cancels. The total shaped reward added over any trajectory depends only on the start state and the end state, not on the path taken. Therefore the *difference* in shaped return between two policies starting from the same `s_0` equals the difference in their unshaped return (plus a terminal term that vanishes when `Φ(s_terminal) = 0`, which is the standard convention). Ranking over policies is preserved exactly. The equivalent statement, which is worth having ready because interviewers like it: potential-based shaping is exactly equivalent to initialising the value function at `V_0(s) = Φ(s)` — it changes how fast you learn, never what you converge to.

**Why the non-potential version breaks.** Take the bicycle: shaping reward `+c` for "moved closer to the goal", `0` otherwise, with no penalty for moving away. Around a small circle, the agent moves closer for half the loop and away for the other half, collecting `+c` on the approach and paying nothing on the retreat. The loop integral of the shaping term is strictly positive, so infinite looping has infinite shaped return, and the optimal policy of the shaped MDP is *literally* to loop forever. That is not a training bug. That is the correct optimal policy for the reward you wrote. Now write it as a potential instead: `Φ(s) = −distance_to_goal(s)`, `F = γΦ(s') − Φ(s)`. The retreat now costs exactly what the approach earned, the loop integral is zero, and the exploit disappears by construction.

**The practical checklist for shaping in production:**

1. Express every shaping term as `γΦ(s') − Φ(s)` for some `Φ`. If you cannot, you are changing the objective and you must justify it explicitly.
2. Set `Φ(terminal) = 0` so the `γ^T Φ(s_T)` term vanishes and episodic returns stay comparable.
3. Keep the *reported* metric on the unshaped reward. Report `R`, train on `R + F`. If your dashboards show shaped return, you have lost the ability to notice that shaping helped training and hurt the task.
4. If the shaping magnitude is comparable to the task reward magnitude, it will dominate early learning. Ratio of about 1:10 (shaping:task, in per-episode totals) is a reasonable starting point, and anneal it toward zero if you can.

### Sim-to-real: the reality gap, domain randomisation, system identification

If you got past Q4 with "we have a simulator", the next problem is that the simulator is wrong. The **reality gap** is the performance drop between a policy's simulated return and its real-world return, and it comes from three separable sources:

- **Dynamics mismatch.** Friction coefficients, motor latency, gear backlash, mass distribution, actuator saturation. These are hard to measure and, in the case of contact-rich manipulation, arguably not measurable to the precision a policy exploits.
- **Observation mismatch.** Sensor noise models, camera intrinsics, lighting, texture, and the fact that a rendered image and a photographed image differ in ways a CNN happily latches onto.
- **Latency and control-loop mismatch.** A simulator that steps instantaneously versus a real system with 20-80 ms of sensing-to-actuation delay. This one is routinely underestimated and routinely fatal: a policy trained with zero latency learns a bang-bang control law that oscillates violently the moment you add delay. *Symptom:* real-world behaviour that looks like high-frequency chatter or limit-cycle oscillation while sim behaviour is smooth.

Two families of fix, and you should be able to argue for the right one:

**System identification** — measure the real parameters and make the simulator match. Best when the physics are well-understood and the parameters are few (rigid-body dynamics, thermal systems, network queues). It gives you a simulator you can also use for MPC and for a stability analysis. It fails when the parameters are unmeasurable or non-stationary (a robot's friction changes as it wears).

**Domain randomisation** (Tobin et al., 2017) — instead of matching reality, randomise the simulator's parameters over a wide distribution during training so the real world is one sample from that distribution and the policy is forced to be robust to all of them. Randomise masses, frictions, latencies, textures, lighting, sensor noise. The policy that survives learns something closer to a robust controller than to a fitted one, and often learns to *infer* the parameters implicitly from a short history of observations, which is why a recurrent policy usually outperforms a feedforward one under heavy randomisation.

**Automatic domain randomisation (ADR)**, the OpenAI Rubik's-cube variant, closes the loop on the randomisation range: start with a single non-randomised environment, and each time the policy clears a performance threshold, widen the randomisation distribution automatically. This is a curriculum over robustness. The honest reporting on that project matters as much as the method: even after thousands of simulated years, the physical hand solved roughly 60% of half-scrambles (15 face rotations) and about 20% of full scrambles (26 rotations), and the cube-solving itself was done by a classical solver, not by RL. That is the calibration to carry into an interview: ADR is a real advance and the real-world success rate was still one in five on the hard case.

The tradeoff to state explicitly: **wider randomisation buys robustness and costs asymptotic performance.** A policy trained over a friction range of `[0.5, 1.5]×` nominal will underperform, on the true friction, a policy trained at exactly the true friction. You are deliberately paying optimality for transfer. If you can system-identify accurately and the parameters are stable, do that instead and keep the performance.

### Safety and constrained RL: why an unconstrained reward is negligence

A scalar reward in a real system says "maximise this, I have no other preferences." That statement is false in every production system I have worked on. You always have other preferences; you simply did not write them down. Writing them down as *constraints* rather than as reward terms is both more honest and mathematically better behaved.

**The CMDP formalism.** A Constrained MDP extends `(S, A, P, R, γ)` with one or more cost functions `C_i: S × A → ℝ` and thresholds `d_i`. The problem becomes:

$$\max_\pi\; J_R(\pi) = \mathbb{E}_\pi\!\left[\sum_t \gamma^t R(s_t,a_t)\right] \quad \text{subject to} \quad J_{C_i}(\pi) = \mathbb{E}_\pi\!\left[\sum_t \gamma^t C_i(s_t,a_t)\right] \le d_i \;\; \forall i$$

Why this is not the same as folding the cost into the reward with a penalty weight `λ`: with a fixed penalty, you have committed to an exchange rate between reward and violation, and you have to guess it before training. A CMDP lets you specify the thing you actually know ("no more than 5 safety violations per 1,000 episodes") and lets the optimisation discover the exchange rate. In a design review, "we allow at most 0.1% of requests to exceed the price cap" is a defensible sentence; "we set the price-cap penalty coefficient to 3.7" is not.

**Lagrangian methods** are the workhorse. Form the Lagrangian `L(π, λ) = J_R(π) − Σ_i λ_i (J_{C_i}(π) − d_i)` with `λ_i ≥ 0`, and do simultaneous gradient ascent on `π` and gradient descent on `λ`:

```
theta  <- theta + alpha_pi  * grad_theta  [ J_R - sum_i lambda_i * J_Ci ]
lambda <- max(0, lambda + alpha_lambda * (J_C - d))    # dual ascent
```

The multiplier `λ` self-tunes: while the constraint is violated (`J_C > d`), `λ` grows and the penalty bites harder; once satisfied, `λ` decays back toward zero and the agent is free to optimise reward. PPO-Lagrangian and TRPO-Lagrangian are the standard instantiations, and on OpenAI's Safety Gym benchmark (Ray, Achiam & Amodei, 2019) the Lagrangian variants generally outperform **CPO** (Constrained Policy Optimization, Achiam et al., 2017), which solves a per-update trust-region subproblem with an approximate per-update safety guarantee but is heavier and depends on accurate cost-advantage estimation. The well-known practical failure of naive Lagrangian methods is **multiplier oscillation**: `λ` overshoots, the policy over-corrects into extreme conservatism, `λ` collapses, the policy violates again, and the constraint value oscillates around `d` with a long period. *Symptom:* a sawtooth in the cost curve with a period of tens of policy iterations. The standard fix is a PID controller on the multiplier update (proportional-integral-derivative Lagrangian) rather than plain integral-only dual ascent.

**Shielding** is the complementary mechanism and it is what you actually ship. A shield is a *hard, non-learned* filter between the policy and the actuator: the policy proposes `a`, the shield checks it against a formally specified safety property, and substitutes a known-safe fallback if it would violate (Alshiekh et al., 2018). Critically, the shield's guarantee does not depend on the policy having learned anything, which means it holds on day one of training and during any distribution shift. This is the architecture of the DeepMind data-centre cooling deployment: the RL agent proposes setpoints, a separate verification layer checks them against the plant's constraint envelope, and the plant's own safety controllers remain in place with human override available at all times. The agent is a suggestion engine wrapped in a cage, and the cage is the reason it was allowed to run.

**Safe exploration** is the third piece: even with a shield, exploration itself can be expensive. The practical toolkit, ranked by how often it is the right answer:

1. **Do not explore online at all.** Learn offline from logged data (`T31-offline-rl`), evaluate with OPE, deploy the fixed policy. This is the correct default whenever exploration cost is charged to revenue or safety.
2. **Constrain the exploration budget.** Cap the fraction of traffic or episodes that take exploratory actions (1-5% is a common range for revenue-bearing surfaces), and cap the *magnitude* of deviation from the incumbent, not just its frequency.
3. **Explore inside a safe set.** Restrict exploratory actions to a region certified safe by a model or by the shield, and expand the set only as evidence accumulates.
4. **Warm-start from the incumbent.** Initialise the policy by behaviour-cloning the existing production system, so exploration starts from a known-acceptable baseline rather than from noise. This alone removes most of the catastrophic early-training risk.

The blunt version: shipping an unconstrained RL policy into a system that moves money, allocates physical resources, or affects people is not a modelling simplification, it is an unreviewed decision to accept unbounded tail risk on behalf of people who did not consent to it. The reward function is the only thing telling the agent what you want; anything you failed to put in it, the agent is free to destroy in exchange for a fraction of a reward unit. Constraints are how you say "and don't do that" in a language the optimiser understands.

---

## Build it from scratch

Two things worth building yourself, because they are what you will actually be asked to build: a propensity-logging wrapper that makes later OPE possible, and an IPS/SNIPS/doubly-robust off-policy evaluator with the diagnostics that tell you when to distrust it.

```python
"""Propensity logging + off-policy evaluation for a contextual-bandit policy.
Tested against a synthetic logged dataset; run directly to see the diagnostics.
(lab pending)ope.py
"""
import numpy as np
from dataclasses import dataclass


# ---------------------------------------------------------------- logging side
@dataclass
class LoggedDecision:
    """The ONLY thing that makes later evaluation possible: store the
    probability the logging policy assigned to the action it actually took."""
    context: np.ndarray
    action: int
    propensity: float      # pi_logging(a | x)  -- NOT a score, a probability
    reward: float
    policy_version: str    # so you can segment the log by which policy produced it


def act_and_log(context, scores, temperature=1.0, floor=0.01, rng=None):
    """Softmax exploration with a PROPENSITY FLOOR.

    The floor is not a hyperparameter, it is an insurance policy: it bounds the
    importance weight 1/p at 1/floor, which bounds the variance of every IPS
    estimate you will ever compute from this log. floor=0.01 caps weights at 100.
    Without a floor, one action logged at p=1e-6 contributes a weight of 1e6 and
    single-handedly determines your estimate.
    """
    rng = rng or np.random.default_rng()
    p = np.exp(scores / temperature)
    p /= p.sum()
    p = (1 - floor * len(p)) * p + floor        # mix with uniform; every arm >= floor
    a = int(rng.choice(len(p), p=p))
    return a, float(p[a])


# ------------------------------------------------------------- evaluation side
def ips(log, target_probs):
    """Inverse propensity scoring. Unbiased if (a) propensities are correct and
    (b) the target policy has support only where the logging policy did."""
    w = np.array([target_probs[i][d.action] / d.propensity for i, d in enumerate(log)])
    r = np.array([d.reward for d in log])
    return float(np.mean(w * r)), w


def snips(log, target_probs):
    """Self-normalised IPS: divide by the mean weight instead of by n.
    Slightly biased, much lower variance, and immune to the systematic
    over/under-estimation you get when the weights don't average to 1."""
    _, w = ips(log, target_probs)
    r = np.array([d.reward for d in log])
    return float(np.sum(w * r) / max(np.sum(w), 1e-12))


def doubly_robust(log, target_probs, reward_model):
    """DR = direct method + IPS correction on the residual.
    Unbiased if EITHER the propensities are right OR the reward model is right.
    In production the reward model is always somewhat wrong and the propensities
    are usually right, so DR mainly buys you variance reduction, not unbiasedness."""
    total = 0.0
    for i, d in enumerate(log):
        q_hat = reward_model(d.context)                     # shape (n_actions,)
        direct = float(np.dot(target_probs[i], q_hat))      # E_{a~pi_target}[ q_hat ]
        w = target_probs[i][d.action] / d.propensity
        total += direct + w * (d.reward - q_hat[d.action])
    return total / len(log)


def effective_sample_size(w):
    """ESS = (sum w)^2 / sum(w^2). If ESS < ~10% of n, your estimate is being
    driven by a handful of records and the confidence interval is a fiction."""
    return float(w.sum() ** 2 / np.sum(w ** 2))


def ope_report(log, target_probs, reward_model=None):
    v_ips, w = ips(log, target_probs)
    n = len(log)
    ess = effective_sample_size(w)
    out = {
        "n": n,
        "IPS": v_ips,
        "SNIPS": snips(log, target_probs),
        "ESS": ess,
        "ESS_frac": ess / n,
        "max_weight": float(w.max()),
        "mean_weight": float(w.mean()),          # should be ~1.0; if not, suspect logging
        "support_violations": int(sum(
            1 for i, d in enumerate(log)
            if target_probs[i][d.action] > 0 and d.propensity <= 0)),
    }
    if reward_model is not None:
        out["DR"] = doubly_robust(log, target_probs, reward_model)
    return out


if __name__ == "__main__":
    rng = np.random.default_rng(0)
    n_actions, n = 5, 20_000
    true_w = rng.normal(size=(n_actions, 4))

    # --- simulate a logging policy over n requests
    log = []
    for _ in range(n):
        x = rng.normal(size=4)
        scores = true_w @ x
        a, p = act_and_log(x, scores, temperature=2.0, floor=0.02, rng=rng)
        r = float(rng.random() < 1 / (1 + np.exp(-scores[a])))   # Bernoulli reward
        log.append(LoggedDecision(x, a, p, r, policy_version="v1"))

    # --- a candidate target policy: greedier version of the same scorer
    target_probs = []
    for d in log:
        s = true_w @ d.context
        p = np.exp(s / 0.5)
        target_probs.append(p / p.sum())

    on_policy_value = np.mean([d.reward for d in log])
    print(f"logging policy observed value : {on_policy_value:.4f}")
    for k, v in ope_report(log, target_probs).items():
        print(f"{k:20s} {v}")
    # Expect: SNIPS close to IPS, mean_weight ~1.0, and ESS_frac well below 1.0 --
    # the greedier the target policy, the lower ESS gets, which is exactly the
    # signal that says "you cannot evaluate this policy from this log."
```

The lesson the code encodes, and the one worth stating in an interview: **the propensity floor and the ESS diagnostic are the two lines that decide whether your evaluation is real.** Everything else is arithmetic. If you deploy a logging policy without a propensity floor, you have permanently destroyed your ability to evaluate any policy that diverges from it, and no amount of clever estimation afterwards recovers it. If you compute IPS without checking ESS, you will confidently report a 7% lift that is three records wide.

---

## How it's done in production

### The deployment loop

Six stages. Skipping any of them is how policies reach users unevaluated.

**1. Log propensities from day one, before you have any RL.** This is the highest-return, lowest-cost decision in the entire module, and the one most often skipped. Every decision your *current* system makes should be logged with the probability it assigned to the action it took. If the current system is deterministic, log `propensity = 1.0` and understand that you have zero action diversity and therefore cannot evaluate anything except the incumbent — which is precisely why you should introduce a small randomisation layer (1-5% of traffic, or an epsilon-greedy floor over the top-`k` candidates) months before you need it. The log schema that matters: `(request_id, timestamp, context_features_hash or the features themselves, candidate_set, action_taken, propensity, model_version, reward, reward_timestamp)`. The `candidate_set` field is the one people forget and the one that breaks OPE later, because a target policy that would have chosen an action that was not in the candidate set is unevaluable and you need to know that.

**2. Offline: train and evaluate.** Train on the log (offline RL or bandit learning), evaluate with IPS/SNIPS/DR plus the ESS diagnostic, and set a hard gate: **if ESS is below roughly 10% of `n`, you do not have an evaluation, you have a number.** Report a confidence interval, not a point estimate; for IPS the empirical-Bernstein or a simple bootstrap over the weighted rewards is fine. Also compute the **support overlap**: the fraction of logged decisions where the target policy puts non-trivial probability on an action the logging policy essentially never took. High overlap failure means offline evaluation is structurally impossible for that policy and you must either widen the logging policy's exploration and wait, or accept online risk.

**3. Shadow mode.** Run the new policy on 100% of live traffic, compute its actions, log them, and **execute none of them**. Duration: long enough to cover a full seasonality cycle for your surface, typically 1-2 weeks for a consumer product with weekday/weekend structure. What shadow mode catches that offline evaluation does not: feature-pipeline skew between training and serving (the single most common production ML bug and it is not RL-specific), latency regressions, crashes on real-world context distributions your log did not represent, and *action-distribution shift* — if the new policy would take an action the incumbent takes 0.1% of the time on 40% of requests, you learn that here, for free, before any user is affected. Shadow mode cannot tell you the reward, because the actions were not executed. Anyone who claims otherwise has confused shadow mode with offline evaluation.

**4. Gradual rollout with guardrails.** The standard ramp: **1% → 5% → 25% → 50% → 100%**, with a minimum soak at each stage long enough to detect your slowest-moving guardrail metric (often 24-72 hours; for weekly-cycle metrics, 7 days at the 5% and 25% stages). Randomise at the *unit of interference* — if your actions affect a user's future state, randomise by user, not by request, or your treatment and control contaminate each other. Guardrail metrics are the metrics you are *not* optimising and refuse to regress:

| Guardrail class | Concrete example | Typical alert threshold |
|---|---|---|
| The unoptimised task metric | Laps completed / order completion rate / task success | Any statistically significant regression |
| Business floor | Revenue per session, conversion rate | −1% relative, or the smallest effect your test can detect |
| User-harm proxy | Complaint rate, unsubscribe rate, session abandonment | +2σ over trailing baseline |
| System health | p99 serving latency, error rate, timeout rate | Latency budget breach (e.g. scorer p99 > 10 ms inside a 200 ms page budget) |
| Distributional | Action entropy, fraction of traffic to the top-1 action, propensity distribution | Action entropy drop > 20% week-over-week |
| Constraint satisfaction | Rate of shield interventions, cost-constraint violations | Shield intervention rate above the modelled rate |

Automate the rollback. A guardrail that requires a human to notice a dashboard is not a guardrail, it is a post-mortem input.

**5. Detect degradation in production.** A policy degrades in ways a supervised model does not, so the monitoring is different:

- **Action entropy collapse.** The policy converges to a single action for most contexts. *Symptom:* top-1 action share climbing week over week, action entropy falling. Causes: feedback loop (the policy's own logged data reinforces its choices), reward-model drift, or an upstream feature going constant. This is the earliest available warning and the cheapest to compute.
- **Propensity drift.** The distribution of logged propensities shifts. If the average propensity of taken actions rises toward 1.0, exploration has quietly stopped and your future OPE capability is dying.
- **The optimised metric rises while an unoptimised metric falls.** The production signature of reward hacking. This is exactly the CoastRunners pattern, and it is why the guardrail table above leads with "the metric you are not optimising."
- **OPE on fresh logs, continuously.** Run IPS of the *current production policy* against a recent window of logs weekly. If its estimated value drifts down while the observed value holds, your context distribution has moved and the policy is being carried by luck or by a compositional shift.
- **Counterfactual holdout.** Keep 1-2% of traffic permanently on the previous policy (or on a randomised policy). It costs you a fraction of a percent of the metric and it is the only unambiguous measurement of your system's cumulative value that survives six policy iterations. Every serious personalisation team I know of runs one and every team that does not eventually wishes it had.

**6. Retraining cadence and non-stationarity.** None of the algorithms in this track assume a non-stationary environment (`T31-exploration` makes the same point about bandit regret guarantees). Real systems are non-stationary on at least four timescales: intraday, weekly, seasonal, and secular (the product changes, the user base changes, a competitor changes). Practical cadences:

| Surface | Typical retrain cadence | Why |
|---|---|---|
| Bandit posteriors on a high-volume surface | Hourly to continuous (streaming update) | Cheap; posteriors are sufficient statistics, no full retrain needed |
| Contextual bandit model weights (PySpark/EMR batch) | Daily | Matches the daily log partition; a 200M-impression daily batch on a ~50-node r5.4xlarge cluster is a 1-3 hour job |
| Offline RL policy | Weekly to monthly | Full OPE + shadow + ramp cycle takes days; retraining faster than you can validate is theatre |
| Sim-trained control policy | On drift detection, not on a schedule | Trigger on measured model prediction error against real telemetry |

The non-stationarity mechanisms worth naming: **discounted/windowed sufficient statistics** (multiply Beta posterior counts by a decay factor `0.99`-`0.999` per update so evidence has an effective half-life of roughly `ln(2)/(1−decay)` updates), **change-point detection** on the reward stream to trigger a reset, and **recency-weighted training samples**. And the failure that catches people: **retraining on your own policy's logs is a feedback loop.** The policy chose the data, the data trains the policy, and the two co-adapt into a narrow region of the action space that looks great on-policy and is badly suboptimal globally. The counterfactual holdout and the propensity floor are both, in part, defences against exactly this.

### What the frameworks give you

| Layer | What you actually use | What it adds over rolling your own |
|---|---|---|
| Bandit serving at scale | In-house scorer over a feature store; Vowpal Wabbit for CB training; Azure Personalizer-style managed services | Propensity logging and the exploration/exploitation split as a first-class API rather than something you remember to add |
| Batch bandit training | PySpark/EMR job over the daily log partition, model artefact to S3, served from a low-latency store | Handles the `10^8`-`10^9` impression/day scale where a single-node trainer stops fitting in memory |
| Applied RL platform | Meta's ReAgent (formerly Horizon) | Data preprocessing, distributed training, counterfactual policy evaluation, and optimised serving in one pipeline. The reported push-notification result was ~1.5-1.8x cumulative reward vs. control with daily retraining |
| OPE library | Open Bandit Pipeline, ReAgent's CPE module, or ~200 lines of your own | Standard estimators (IPS, SNIPS, DR, switch-DR) with the diagnostics; rolling your own is genuinely fine and forces you to understand the assumptions |
| Simulation | MuJoCo / Isaac / a domain-specific plant simulator | Parallel environments. 1,000+ parallel envs is the difference between a 116-day and a 3-hour training run |
| Safety layer | A hand-written shield plus the existing control system's envelope | Guarantees that hold regardless of what the policy learned; the reason your deployment gets approved |

### Failure modes

| Symptom | Cause | Fix |
|---|---|---|
| Episode return climbs steadily while task-success metric stays flat at zero | Reward hacking / specification gaming — the proxy reward is being maximised without achieving the goal (CoastRunners pattern) | Add the unoptimised task metric to the training dashboard and to guardrails; re-specify the reward; add a cost constraint on the exploited behaviour |
| Policy loops or oscillates, per-step reward high, terminal reward zero | Non-potential-based shaping term with a positive loop integral (the Randløv-Alstrøm bicycle) | Rewrite every shaping term as `F = γΦ(s') − Φ(s)`; verify the loop integral is zero by construction |
| Excellent sim performance, near-zero real-world transfer, sim render looks physically wrong | Agent is exploiting a simulator bug (contact forces, integrator instability) | Watch the render. Then fix the sim, add domain randomisation over the exploited parameter, and add a physical-plausibility check to the eval suite |
| Real robot chatters / limit-cycles while sim is smooth | Control-loop latency present in reality, absent in sim | Model actuation delay explicitly in the sim and randomise it (e.g. uniform over 20-80 ms); penalise action jerk in the reward |
| Offline evaluation says +7%, online A/B says −2% | Low effective sample size (ESS well under 10% of `n`), or the target policy is off-support relative to the logging policy | Gate on ESS; widen the logging policy's exploration; use SNIPS/DR and report intervals; where support is missing, accept that OPE cannot answer and go to a small online ramp |
| Cost/constraint curve sawtooths around the threshold with a long period | Lagrangian multiplier oscillation from plain dual ascent | PID-Lagrangian multiplier update, or a lower multiplier learning rate with a warm start |
| Agent's behaviour is safe in training and unsafe on day one of deployment | Safety relied on the learned policy rather than on a non-learned shield | Move the guarantee into a shield/constraint layer that holds independent of what was learned |
| Action entropy collapses over weeks; metrics look fine, then plateau | Feedback loop — training on the policy's own logs reinforces its own choices | Propensity floor, counterfactual holdout arm, and explicit exploration budget; monitor entropy as a first-class metric |
| Metrics regress on a Monday after a good weekend rollout | Randomised by request rather than by user, or ramped without a full weekly seasonality soak | Randomise at the unit of interference; require a 7-day soak at intermediate ramp stages |
| Bandit/RL policy that was strong for months quietly decays | Non-stationarity — the reward distribution shifted and sufficient statistics have too long a memory | Discounted/windowed statistics, change-point detection, or a scheduled retrain with recency weighting |
| Training diverges only when scaled to production feature volume | Feature-pipeline skew between offline training and online serving | Shadow mode with feature-level diffing between the training and serving paths; this is not an RL bug and it is the most common one |

---

## Tradeoffs & when NOT to use it

- **Do not use RL when the action does not change the future state distribution.** This is not a preference, it is a definition. A contextual bandit converges in `10^3`-`10^5` samples per arm, gives you unbiased off-policy evaluation from logged propensities, has a one-line rollback, and can be shipped by one engineer in a sprint. Full RL on the same problem needs `10^6`-`10^9` samples, has no trustworthy long-horizon OPE, and takes a team a quarter. The student's PySpark/EMR contextual bandit is the right shape for the overwhelming majority of ranking, pricing, and allocation surfaces, and "would this be better as a bandit?" should be the first question in any RL design review.
- **Do not use RL when a solver exists.** If you can write the transition model and the objective as arithmetic, MIP/LP/CP-SAT returns a provably optimal solution with a duality gap you can report. RL's edge is unknown dynamics, not hard combinatorics.
- **Do not use RL when you cannot specify the reward adversarially.** If you cannot survive the "a creative adversary maximises this to four decimals" test at the whiteboard, three months of training will not help. Escalate to constrained formulations, or accept that the problem needs a human in the loop, or do not do the project.
- **Do not use RL when you have no simulator and no log with action diversity.** You will have no way to evaluate before deploying, which means your only evaluation is a live experiment on real users with a policy of unknown quality. That is not an experiment, it is an incident with a hypothesis attached.
- **Do not use online RL where exploration cost is charged to revenue, safety, or people.** Offline RL plus OPE plus shadow mode plus a ramp is slower and it is the correct default. Reserve online exploration for surfaces where a bad action is cheap and reversible.
- **Do not use domain randomisation when you can system-identify.** Randomisation deliberately trades asymptotic performance for robustness. If the parameters are measurable and stable, measure them, keep the performance, and use the identified model for MPC and for a stability argument as well.
- **Do not treat a published research result as a deployment precedent without checking replication.** The chip-placement dispute is the live example: a 2021 Nature result, a 2023 reproduction that found it underperformed simulated annealing and commercial tools, a 2024 rebuttal arguing the reproduction omitted pre-training, an editor's note, and a 2025 press consensus that leaned toward Google on the technical point while the reproducibility criticism stood. Cite it as contested. An interviewer who knows the history will mark you up for the nuance and down for citing either side as settled fact.
- **Do not let the sunk cost of a simulator justify the project.** Simulator work is seductive because it is tractable engineering with visible progress, and it is the most common way an RL project consumes two quarters while shipping nothing. Set a decision date: if the sim-to-real gap is not measurably closing by then, the answer is a bandit or a heuristic.

---

## Interview questions

### Q1 — How do you decide whether a problem is actually a reinforcement learning problem?
**Testing:** whether you have a crisp, mechanical test or just vibes about "sequential decision-making".
**Answer:** One question first: does the action change the distribution of states I will be asked to act on later? Write down `P(s_{t+1} | s_t, a_t)` and check whether it depends on `a_t`. If it does not, it is a contextual bandit and I ship a bandit, because it converges in `10^3`-`10^5` samples per arm instead of `10^6`-`10^9`, gives unbiased off-policy evaluation from logged propensities, and rolls back in one config change. If it does depend on the action, I ask four more: what is the effective horizon (`1/(1−γ)`; if the business consequence resolves in 1-3 decisions, widen the reward's attribution window and stay a bandit), can I write the reward down adversarially, do I have a simulator or a log with real action diversity, and can the business fund the sample complexity. The empirical version of the first question is cheap: run an A/B test and check whether the *context* distribution, not the reward, differs between a random-action arm and a greedy arm. If contexts are statistically indistinguishable, the sequential machinery is dead weight.
**Follow-up trap:** *"Our recommender obviously affects what users do next, so it's clearly RL, right?"* — affecting behaviour is necessary but not sufficient. The question is whether that effect is large enough, and resolves fast enough, that a credit-assignment algorithm recovers value a bandit with a 24-hour reward attribution window would not. Measure it: fit both on the same log, and if the two policies agree on more than roughly 95% of held-out actions, the sequential structure is not where the value is and you have paid a quarter of engineering for a rounding error.

### Q2 — You've shipped contextual bandits on PySpark/EMR. Walk me through what would have to change to make that a full RL system, and whether you would.
**Testing:** whether production experience translates into an accurate account of the incremental cost, rather than "swap the algorithm".
**Answer:** Mechanically: the training data changes from `(context, action, propensity, reward)` tuples to trajectories with an explicit episode boundary and a user-level join across sessions, which is a much harder Spark job because it is a stateful sessionisation rather than a per-row map; the label changes from an immediate reward to a discounted return requiring either bootstrapping or full-episode assembly; evaluation changes from IPS/DR over one-step decisions, which is unbiased under known propensities, to sequential OPE where importance weights multiply across the trajectory and variance grows exponentially in horizon, so the honest answer at horizon 20 is usually "I cannot evaluate this offline"; and the rollback story changes from "revert the model artefact" to "revert the model artefact and wait for the state distribution to relax back". Whether I would: only if the measured effect of actions on the next-request context distribution is large, and only after trying a bandit with a longer reward attribution window first, because that captures the delayed-value story without giving up the evaluation story.
**Follow-up trap:** *"Isn't sequential OPE just IPS with a product of ratios? Why is that so much worse?"* — because the product of `H` importance ratios has variance that grows exponentially in `H`; at horizon 20 with per-step ratios averaging 1.5, weights routinely span many orders of magnitude and effective sample size collapses to a handful of trajectories. Per-decision importance sampling and doubly-robust variants reduce the constant, they do not change the exponential dependence on horizon. That is the structural reason bandit OPE is a solved engineering problem and long-horizon OPE is not.

### Q3 — Explain potential-based reward shaping and prove it doesn't change the optimal policy.
**Testing:** the one theorem in this module. A candidate who shapes rewards without knowing this will ship a policy that optimises something they did not intend.
**Answer:** Ng, Harada & Russell (ICML 1999): a shaping term of the form `F(s,a,s') = γΦ(s') − Φ(s)`, for any potential function `Φ: S → ℝ`, leaves the set of optimal policies unchanged for every transition model. The proof is a telescoping sum: `Σ_t γ^t (γΦ(s_{t+1}) − Φ(s_t)) = Σ_t (γ^{t+1}Φ(s_{t+1}) − γ^tΦ(s_t)) = γ^TΦ(s_T) − Φ(s_0)`. Every intermediate term cancels, so the total shaping reward accumulated over any trajectory depends only on the start and end states, not on the path. Two policies from the same `s_0` therefore have their shaped returns shifted by the same constant, and the ranking over policies is preserved exactly. Set `Φ(terminal) = 0` and even the terminal term vanishes. The equivalent framing: potential-based shaping is exactly value-function initialisation at `V_0(s) = Φ(s)`; it changes how fast you learn, never what you converge to.
**Follow-up trap:** *"So why does anyone ever use non-potential shaping?"* — because writing a good `Φ` requires knowing something about state values, and people reach for the easier "give +1 whenever the agent moves closer to the goal" formulation instead. That form is not a potential difference, its loop integral around a cycle is strictly positive, and the optimal policy of the shaped MDP becomes literally "loop forever". That is the Randløv-Alstrøm 1998 bicycle agent that circled near the start rather than riding to the goal, and it is the example Ng et al. were answering. The fix is one line: `Φ(s) = −distance_to_goal(s)` and `F = γΦ(s') − Φ(s)`, which makes the retreat cost exactly what the approach earned.

### Q4 — Give me a real example of reward hacking and the metric that would have caught it.
**Testing:** whether you know the catalogue and, more importantly, whether you know what monitoring detects it.
**Answer:** OpenAI's CoastRunners agent (December 2016). Reward was the game score, a proxy for finishing a boat race. The learned policy found an isolated lagoon, circled repeatedly knocking over the same three targets timed to their respawn, caught fire, collided with other boats, never completed a lap, and scored 20% higher than a human who finished the course. The metric that catches it is the one the agent is not optimising: laps completed, which sat at zero the entire time the return curve climbed. That generalises to the single most important production monitoring rule in RL: always instrument at least one metric that is not in the reward, and put it in the guardrail set with an automated rollback. Victoria Krakovna's specification-gaming list, maintained since April 2018, collects dozens of similar cases including simulated robots exploiting physics-engine bugs and agents that learn to crash or edit the evaluator rather than solve the task.
**Follow-up trap:** *"Could you have prevented it by just adding a penalty for not finishing?"* — sometimes, and it generalises badly. Every patch you add to a gameable reward creates a new surface to game, and you are in an adversarial loop against an optimiser with more patience than you. The structurally better move is to express the requirement as a *constraint* in a CMDP formulation ("episodes must terminate with a completed lap") rather than as another reward term, because a constraint states the thing you actually know, and to instrument the unoptimised metric so you find out fast when the next exploit appears.

### Q5 — What is the reality gap and what are your options for closing it?
**Testing:** whether sim-to-real is understood as three separable problems or one vague one.
**Answer:** The reality gap is the drop between a policy's simulated return and its real return, and it decomposes into dynamics mismatch (friction, mass, backlash, actuator saturation), observation mismatch (sensor noise, camera intrinsics, lighting, rendered-versus-photographed texture statistics), and latency/control-loop mismatch (a sim that steps instantaneously versus 20-80 ms of real sensing-to-actuation delay). Two families of fix. System identification measures the real parameters and matches the sim, which is right when the physics are well-understood and the parameters are few and stable, and it gives you a model you can also use for MPC and for a stability argument. Domain randomisation (Tobin et al., 2017) instead randomises sim parameters over a wide distribution so reality is one draw from it, forcing a robust rather than a fitted controller; recurrent policies help here because the policy can infer the parameters implicitly from a short observation history. Automatic domain randomisation, the OpenAI Rubik's-cube variant, widens the randomisation range automatically each time the policy clears a performance threshold, which is a curriculum over robustness.
**Follow-up trap:** *"Domain randomisation is strictly better then, since it needs no measurement?"* — no, you are paying for it. A policy trained over a friction range of `[0.5, 1.5]×` nominal will underperform, at the true friction, a policy trained at exactly the true friction. You are deliberately trading asymptotic performance for transfer. And the honest headline number from ADR is worth quoting: after thousands of simulated years, the physical hand solved roughly 60% of half-scrambles and about 20% of full scrambles, with the cube-solving logic itself done by a classical solver, not by RL.

### Q6 — Why is an unconstrained reward function a problem in a production system, and what's the alternative?
**Testing:** whether "safety" means a formalism you can implement or a word you say.
**Answer:** A scalar reward asserts "maximise this, I have no other preferences", which is false in every real system. Whatever you left out, the optimiser is free to trade away for a fraction of a reward unit. The formalism is the Constrained MDP: keep the reward objective, add cost functions `C_i` with thresholds `d_i`, and solve `max_π J_R(π)` subject to `J_{C_i}(π) ≤ d_i`. The practical advantage over folding the cost into the reward with a fixed penalty weight is that you specify what you actually know ("at most 0.1% of requests may exceed the price cap") and let the optimisation find the exchange rate, rather than guessing the exchange rate up front. Lagrangian methods (PPO-Lagrangian, TRPO-Lagrangian) do simultaneous ascent on the policy and dual ascent on the multipliers `λ_i ← max(0, λ_i + α(J_{C_i} − d_i))`, so `λ` grows while the constraint is violated and decays once it is satisfied. On OpenAI's Safety Gym benchmark the Lagrangian variants generally outperform CPO (Achiam et al., 2017), which has a cleaner per-update guarantee but is heavier and depends on accurate cost-advantage estimation.
**Follow-up trap:** *"If Lagrangian methods enforce the constraint, do you still need a shield?"* — yes, and this is the whole point. Lagrangian methods enforce the constraint *in expectation, asymptotically, if training converges*. None of those three qualifiers hold on day one of deployment or under distribution shift. A shield is a hard, non-learned filter between the policy and the actuator that substitutes a known-safe fallback when the proposed action violates a formally specified property (Alshiekh et al., 2018), and its guarantee is independent of what the policy learned. That is the DeepMind data-centre cooling architecture: the agent proposes setpoints, a verification layer checks them against the plant's constraint envelope, the plant's own safety controllers stay in place, and humans can override at any time. The cage is why the agent was allowed to run at all.

### Q7 — Design the deployment plan for a new policy on a revenue-bearing surface. Be specific.
**Testing:** whether the operational discipline is real or a list of buzzwords.
**Answer:** Offline first: train on logged data, evaluate with IPS, SNIPS, and doubly-robust estimators, and gate on effective sample size, `ESS = (Σw)²/Σw²`. If ESS is under roughly 10% of `n`, I do not have an evaluation and I say so rather than reporting the point estimate. I also report support overlap: the fraction of decisions where the target policy would take an action the logging policy essentially never took, which is the structural reason offline evaluation can be impossible rather than merely noisy. Then shadow mode on 100% of traffic executing 0% of actions, for 1-2 weeks to cover a full weekly seasonality cycle, which catches training/serving feature skew, latency regressions, and action-distribution shift. Then a ramp of 1% → 5% → 25% → 50% → 100%, randomised by user rather than by request if actions affect future state, with a 24-72 hour soak per stage and 7 days at the stages where weekly-cycle metrics matter. Guardrails with automated rollback: the unoptimised task metric, a revenue floor, a user-harm proxy such as complaint or unsubscribe rate, p99 serving latency against its budget, and action entropy. And a permanent 1-2% counterfactual holdout on the previous policy, because after six policy iterations it is the only unambiguous measurement of what the system is actually worth.
**Follow-up trap:** *"Shadow mode ran clean for two weeks. Doesn't that mean the policy is good?"* — no. Shadow mode did not execute the actions, so it produced no reward signal at all. It tells you the policy runs, is fast enough, does not crash on real contexts, and what its action distribution looks like relative to the incumbent. Treating shadow-mode success as evidence of policy quality is one of the most common category errors in this area, and it is the one I would push on if a candidate glossed over it.

### Q8 — Your offline evaluation said +7%. The online A/B says −2%. Debug it.
**Testing:** structured debugging of the specific failure that ends RL projects.
**Answer:** Ranked hypotheses, cheapest discriminating check first. (1) **Low effective sample size.** Compute ESS; if it is a few percent of `n`, a handful of records with enormous importance weights drove the estimate. Check `max_weight` and the weight histogram. (2) **Propensity error.** Check that the mean importance weight is approximately 1.0 across the log. If it is not, the logged propensities are wrong, usually because the serving code applied a post-hoc filter, dedupe, or business rule after sampling, so the logged probability is not the probability of the action actually taken. This is the single most common cause and it is a serving bug, not a statistics bug. (3) **Support violation.** Check the fraction of decisions where the target policy puts mass on actions the logging policy never took; those contribute nothing to IPS and their value is pure extrapolation. (4) **Training/serving skew.** Diff the feature vectors produced by the training pipeline and the serving path for the same request; shadow mode should have caught this and if it did not, that is the process bug to fix. (5) **Interference.** If actions affect future state and you randomised by request rather than by user, treatment and control contaminated each other and the measured effect is attenuated or reversed. (6) **Non-stationarity.** The log predates a product or seasonal change and the context distribution has moved.
**Follow-up trap:** *"You found the mean importance weight is 1.4. What does that tell you and what do you do?"* — it tells you the logged propensities are systematically too small relative to what the logging policy actually did, which usually means the serving path modified the action distribution after the propensity was recorded (a downstream filter, a dedupe, a business-rule override, or a retry that re-sampled). SNIPS is the immediate mitigation because self-normalising divides out the systematic bias in the weights, but it is a patch on an instrumentation bug: the real fix is to log the propensity at the *last* point the action can change, after every filter, and to add a continuous assertion that mean weight stays inside roughly `[0.95, 1.05]` on the incumbent policy.

### Q9 — How would you detect that a deployed RL policy is degrading, before the business metric moves?
**Testing:** whether monitoring for a policy differs, in your head, from monitoring for a classifier.
**Answer:** Five signals, roughly in order of how early they fire. **Action entropy collapse**: track the entropy of the action distribution and the top-1 action share; a policy converging onto a single action for most contexts is the earliest and cheapest warning, and its usual cause is a feedback loop where the policy's own logs reinforce its own choices. **Propensity drift**: if the average propensity of taken actions rises toward 1.0, exploration has quietly stopped and your ability to do any future OPE is dying, months before anyone notices. **Optimised metric up, unoptimised metric down**: the production signature of reward hacking, the CoastRunners pattern. **Continuous OPE on fresh logs**: weekly IPS of the current production policy against a recent window; if its estimated value drifts down while observed value holds, the context distribution has moved and the policy is being carried by compositional shift. **Counterfactual holdout**: 1-2% of traffic permanently on the previous or a randomised policy, which is the only unambiguous measurement of cumulative system value that survives six policy iterations. Standard classifier monitoring (feature drift, prediction distribution) is still necessary but it is not sufficient, because a policy can have perfectly stable inputs and outputs while the *value* of its actions collapses.
**Follow-up trap:** *"A 1-2% holdout costs real money. How do you justify it?"* — by naming what you cannot answer without it. After six policy iterations, each individually measured against its immediate predecessor, you have six local comparisons and no measurement of the system's total value versus baseline, so you cannot detect slow cumulative drift, you cannot detect that iterations three through five were collectively negative, and you cannot answer "what would happen if we turned this off", which is the question that eventually gets asked in a cost review. The holdout costs a known fraction of a percent; not having it costs an unbounded and unmeasurable amount.

### Q10 — When does non-stationarity break an RL or bandit system, and what's your retraining strategy?
**Testing:** whether you know that none of the standard guarantees assume a moving target.
**Answer:** Every regret and convergence guarantee in this track assumes a stationary MDP or bandit. Real systems move on at least four timescales: intraday, weekly, seasonal, and secular. The break is not gradual degradation, it is confident wrongness: a Thompson posterior with large accumulated counts is *slow* to update, so it keeps favouring arms that were good under the old distribution for a long time after new contradicting evidence starts arriving. Three mechanisms, and I would use all three at different layers. **Discounted or windowed sufficient statistics**: multiply Beta counts by a decay factor of `0.99`-`0.999` per update, giving evidence an effective half-life of roughly `ln(2)/(1−decay)` updates, so `0.999` is about 690 updates. **Change-point detection** on the reward stream to trigger a reset when observed reward diverges from the posterior's prediction beyond a threshold. **Recency-weighted retraining** on a cadence matched to how fast you can validate, not to how fast you can train: hourly or streaming for bandit posteriors, daily for batch contextual-bandit weights (a 200M-impression daily partition on a ~50-node r5.4xlarge cluster is a 1-3 hour Spark job), weekly-to-monthly for an offline RL policy where the OPE plus shadow plus ramp cycle itself takes days.
**Follow-up trap:** *"Why not just retrain every hour and stop worrying about it?"* — because retraining faster than you can validate is theatre, and because retraining on your own policy's logs is a feedback loop. The policy chose the data, the data trains the policy, and the two co-adapt into a narrow region of action space that looks excellent on-policy and is badly suboptimal globally. The defences are the propensity floor (guaranteeing every action retains some minimum probability, which bounds importance weights *and* keeps the log informative), the counterfactual holdout, and an explicit exploration budget. Cadence is not a substitute for any of those.

### Q11 — Why do most RL projects fail? Give me the honest version.
**Testing:** the whole module. This is the question a principal-level candidate should be able to answer without defensiveness.
**Answer:** Four causes, and in my experience they account for nearly all of it. **No simulator.** You cannot get `10^6`-`10^9` samples from a real system that runs at one interaction per second, so either a simulator existed already for non-RL reasons or you are about to spend a quarter building one that nobody trusts. **A reward that cannot be specified.** The whiteboard test is "if a creative adversary maximises this to four decimal places, am I happy", and most business objectives fail it, because the real objective is a bundle of preferences nobody has written down and some of which are only revealed when they are violated. **Sample complexity the business cannot fund.** DQN's Atari results used 50 million frames per game, roughly 38 days of equivalent human play *per game*; OpenAI Five used 770 ± 50 PFLOP/s-days and about 45,000 years of self-play over 10 realtime months. Nobody is funding that for a 3% conversion lift. **No way to evaluate before deploying.** Sequential OPE's importance weights multiply across the horizon and variance grows exponentially in it, so at any realistic horizon the honest answer is "I cannot tell you what this policy is worth without running it", and a policy of unknown quality on real traffic is an incident with a hypothesis attached. Alex Irpan's 2018 estimate was that when asked whether RL can solve someone's problem the answer is no, and he is right at least 70% of the time; I have not seen anything since that moves that number much for business problems specifically.
**Follow-up trap:** *"So is RL just not worth doing?"* — no, and the distinction matters. The published successes are real: 40% reduction in Google data-centre cooling energy with a safety-first architecture, 9% and 13% energy savings at two live Trane sites, roughly 1.5-1.8x cumulative reward on Meta's push-notification policy, a 12.5% click lift from LinUCB on Yahoo! Front Page. What they have in common is that a simulator or a rich log already existed, the reward was a physically measurable quantity or a directly logged business event rather than a proxy for something fuzzy, and the deployment was wrapped in constraints and human override. RL is worth doing when those conditions hold. The failure is not doing RL, it is doing RL when they do not hold and finding out in month four.

### Q12 — Google's 2021 Nature chip-placement result: is that a good precedent for using RL on our optimisation problem?
**Testing:** whether you cite research honestly, including when it is contested. Interviewers in EDA, hardware, or research-adjacent orgs use this deliberately.
**Answer:** I would cite it as contested rather than as precedent. The 2021 Nature paper reported RL-generated macro placements meeting or beating human designers in under six hours where the manual process took weeks. Cheng, Kahng et al.'s "The False Dawn" (2023) reported that a reproduction underperformed simulated annealing and commercial EDA tools while being slower, and that RL methods did not place in the top five of a 2023 open contest. Google's "That Chip Has Sailed" (November 2024) responded that the reproduction did not pre-train the RL agent, which is load-bearing for their method, and that other reported differences stemmed from not running the method as described. Nature ran a post-publication review and attached an editor's note; IEEE Spectrum's 2025 coverage treated the narrow technical dispute as resolved largely in Google's favour while the reproducibility criticism, that critical methodology and inputs were withheld, stood on its own. What I take from it operationally: even a Nature-published, heavily-resourced RL result took three years and a public dispute to establish what it actually showed, which is a strong argument for building your own baseline comparison against simulated annealing or a commercial solver before committing to RL for a combinatorial optimisation problem.
**Follow-up trap:** *"Doesn't the pre-training point mean the critics were simply wrong?"* — it means they were wrong on one specific, important axis, and it does not dissolve the reproducibility criticism, which is a separate claim about whether the artefacts and methodology released were sufficient for an independent party to reproduce the result. Both things can be true: the method can work as its authors describe *and* the publication can have been insufficiently reproducible. A candidate who collapses that into "the critics were debunked" is telling me they read the headline, not the dispute.

### Q13 — A product manager wants an RL agent to optimise "user satisfaction". What do you say?
**Testing:** the reward-specification conversation, which is the actual job.
**Answer:** I ask what we can log. "User satisfaction" is not a reward, it is a construct, and RL requires a scalar you can compute per decision from telemetry. So the conversation becomes: which logged events do we believe correlate with satisfaction, over what attribution window, and what is the failure mode of each. Then I run the adversarial test on every candidate out loud: optimise session length and the agent learns to make things hard to find; optimise clicks and it learns clickbait; optimise a thumbs-up rate and it learns to solicit thumbs-up; optimise retention over 30 days and the signal is so delayed and so confounded by everything else the product ships that we cannot attribute it to actions. Where I land in practice is a short-horizon logged proxy as the reward, plus a constraint set for everything the proxy can destroy (complaint rate, unsubscribe rate, diversity floor, a hard cap on repeat exposure), plus at least one unoptimised metric on the guardrail dashboard. And I say plainly that if we cannot agree on the proxy and the constraints in a room in an afternoon, the project is not ready, because that disagreement will not resolve itself during training.
**Follow-up trap:** *"Could we learn the reward from human preference data instead, like RLHF?"* — you can, and you have moved the specification problem rather than solved it. A learned reward model is itself a proxy that an optimiser will exploit, and now the exploit is harder to detect because the reward is a neural network nobody can read rather than an expression somebody wrote. RLHF pipelines manage this with KL penalties against a reference policy and with held-out human evaluation, which are exactly "constrain the optimiser" and "measure an unoptimised metric" in different clothing. The 2025-2026 work on LLM-generated or LLM-critiqued reward functions is interesting and I would not put it in a design review as a load-bearing component yet.

### Q14 — You have six weeks and one engineer. The ask is "use RL to improve our ranking system." What do you actually do?
**Testing:** prioritisation under a real constraint, and whether the bandit-first instinct survives contact with a deadline.
**Answer:** Week 1: instrument. Add propensity logging to the existing ranker and introduce a small randomisation layer, an epsilon-greedy floor of 1-5% over the top-`k` candidates, so the log has action diversity. This has value even if the rest of the project is cancelled, because without it no future policy of any kind is evaluable. Weeks 2-3: build the offline evaluation harness (IPS, SNIPS, DR, ESS, support overlap) and validate it by predicting the incumbent's known online value from its own logs; if the harness cannot reproduce a number you already know, it will not be trusted on a number you do not. Weeks 3-5: train a contextual bandit on the logged data with the reward defined over the widest attribution window the join supports, evaluate it offline, and run it in shadow mode. Week 6: ramp to 1% and 5% behind guardrails. What I do not do in six weeks with one engineer is build a simulator or train a sequential policy, and I would say so in the kickoff rather than at the deadline. If the bandit shows a real lift, the case for investing a quarter in the sequential version is made with data instead of with enthusiasm; if it does not, we found out for the price of six weeks and we kept the propensity logging.
**Follow-up trap:** *"That's not RL. Won't leadership see this as not delivering the ask?"* — reframe the ask as the outcome rather than the method, and make the sequencing explicit at kickoff: the infrastructure I build in weeks 1-3 (propensity logging, the OPE harness, shadow mode) is a strict prerequisite for *any* RL system, so nothing is wasted, and the bandit is the fastest way to measure whether there is signal in personalising this surface at all. If leadership specifically wants the method rather than the outcome, that is worth surfacing early and directly, because a project whose success criterion is "we used RL" has no failure condition and will consume budget indefinitely.

---

## Red flags that fail you

- Reaching for PPO or DQN without first asking whether the action changes the future state distribution.
- Not knowing that a contextual bandit gives unbiased off-policy evaluation from logged propensities and that long-horizon RL does not.
- Proposing reward shaping without knowing potential-based shaping, or being unable to state `F = γΦ(s') − Φ(s)` and why the telescoping sum makes it policy-invariant.
- Treating an unconstrained scalar reward as adequate for a system that touches money, safety, or people.
- Confusing shadow mode with offline evaluation: shadow mode executes nothing, so it produces no reward signal at all.
- Reporting an IPS estimate without effective sample size, weight distribution, or support-overlap diagnostics.
- Not having a rollback plan, or having one that requires a human to notice a dashboard.
- Assuming a policy that was safe in training is safe on day one of deployment, rather than putting the guarantee in a non-learned shield.
- Citing the Nature chip-placement result, or the critiques of it, as settled fact in either direction.
- Being unable to name a case where the right answer was "do not use RL", or treating that answer as a failure rather than as the most common correct outcome.
- Saying "we'll just A/B test it" as the entire evaluation plan for a policy of unknown quality.
- Not logging propensities, and not understanding that this permanently destroys the ability to evaluate anything later.

## Cheat card

```
THE TEST        does a_t change the DISTRIBUTION of s_{t+1..T} you'll face?
                NO -> contextual bandit (10^3-10^5 samples, unbiased OPE, 1-line rollback)
                NO + delayed label -> supervised + threshold
                YES + known dynamics -> MIP/LP/MPC/PID solver
                YES + unknown dynamics + long horizon -> actual RL
EFF. HORIZON    1/(1-gamma). gamma=.9 ->10, .99 ->100. If business metric resolves in
                1-3 steps: widen the bandit's reward ATTRIBUTION WINDOW, stay a bandit
5 MORE GATES    reward specifiable adversarially? simulator OR log w/ action diversity?
                sample budget affordable? solver exists? can you evaluate pre-deploy?
SHAPING         F(s,a,s') = gamma*Phi(s') - Phi(s)  (Ng/Harada/Russell ICML 1999)
                telescopes to gamma^T*Phi(s_T) - Phi(s_0): path-independent -> POLICY
                INVARIANT for every P. Equivalent to init V_0(s)=Phi(s). Phi(term)=0.
                NON-potential shaping w/ positive LOOP INTEGRAL -> optimal policy is to
                LOOP (Randlov-Alstrom 1998 bicycle circled the start). Train on R+F,
                REPORT on R.
REWARD HACKING  CoastRunners 2016: circled a lagoon, 3 respawning targets, never
                finished a lap, scored 20% ABOVE a human. Krakovna spec-gaming list
                (2018-) = dozens more. RULE: always log >=1 metric you are NOT optimising
SIM-TO-REAL     gap = dynamics + observation + LATENCY (20-80ms; ignore it and the real
                robot chatters). sysID (few, stable, measurable params -> keep perf)
                vs domain randomisation (robust, COSTS asymptotic perf) vs ADR (auto-
                widens range on threshold). Rubik's hand: ~60% half-scramble, ~20% full
SAFETY          CMDP: max J_R s.t. J_Ci <= d_i. Lagrangian: lambda += alpha*(J_C - d),
                clamped >=0. PPO-Lag/TRPO-Lag > CPO on Safety Gym. Sawtooth cost curve
                = multiplier oscillation -> PID-Lagrangian. SHIELD = hard non-learned
                filter, guarantee holds DAY ONE and under drift. DeepMind DC cooling =
                agent proposes, verifier checks, plant safety controllers stay, human override
OPE             IPS: mean(w*r), w = pi_target(a|x)/p_logged. SNIPS: /sum(w) - lower var.
                DR: direct + w*(r - q_hat) - unbiased if EITHER model or propensity right.
                ESS = (sum w)^2/sum(w^2). ESS < ~10% of n -> NO EVALUATION.
                mean(w) should be ~1.0; if not, propensity logging is BUGGED.
                PROPENSITY FLOOR (e.g. .01) bounds w at 1/floor = 100. Log AFTER all filters.
                Sequential OPE: weights MULTIPLY, variance exponential in horizon.
DEPLOY LOOP     log propensities -> offline train+OPE (gate on ESS) -> SHADOW (100%
                traffic, 0% actions, 1-2wk, catches train/serve skew + latency + action
                shift, gives NO reward signal) -> ramp 1/5/25/50/100% randomised at the
                UNIT OF INTERFERENCE, 24-72h soak (7d if weekly seasonality) -> guardrails
                w/ AUTOMATED rollback -> permanent 1-2% counterfactual holdout
DEGRADATION     action-entropy collapse (earliest), propensity drift toward 1.0,
                optimised-up/unoptimised-down (= reward hacking), weekly OPE on fresh logs
NON-STATIONARY  no guarantee in this track assumes it. discounted stats (decay .99-.999,
                half-life ln2/(1-d) updates), change-point detection, recency weighting.
                Retrain no faster than you can VALIDATE. Training on your own logs = loop.
CADENCE         posteriors hourly/streaming | CB weights daily (200M impressions,
                ~50-node r5.4xlarge, 1-3h Spark) | offline RL weekly-monthly | sim policy on drift
WHY THEY FAIL   (1) no simulator (2) reward not specifiable (3) sample complexity
                unfundable (DQN 50M frames/game ~38 human-days; OpenAI Five 770+-50
                PFLOP/s-days, ~45k yrs self-play, 10 months) (4) no pre-deploy evaluation
                Irpan 2018: "no" is right >=70% of the time
REAL WINS       DeepMind DC cooling -40% cooling energy / ~-15% PUE overhead | Trane
                9% and 13% at 2 live sites | ReAgent push notifs ~1.5-1.8x reward, daily
                retrain | LinUCB Yahoo! Front Page +12.5% clicks. All: sim/log already
                existed, reward directly measurable, wrapped in constraints
CONTESTED       Nature 2021 chip placement (<6h vs weeks) vs "False Dawn" 2023 (lost to
                simulated annealing + commercial EDA) vs "That Chip Has Sailed" 2024
                (critics didn't pre-train) + Nature editor's note. SAY IT'S CONTESTED.
```

## Sources

- [Krakovna — Specification gaming examples in AI (list started April 2018, maintained since)](https://vkrakovna.wordpress.com/2018/04/02/specification-gaming-examples-in-ai/) — accessed 2026-08-05
- [DeepMind Safety Research — Specification gaming: the flip side of AI ingenuity (2020)](https://deepmind.google/blog/specification-gaming-the-flip-side-of-ai-ingenuity/) — accessed 2026-08-05
- [OpenAI — Faulty Reward Functions in the Wild (CoastRunners, Amodei & Clark, Dec 2016)](https://openai.com/index/faulty-reward-functions/) — accessed 2026-08-05
- [Ng, Harada & Russell — Policy Invariance Under Reward Transformations: Theory and Application to Reward Shaping (ICML 1999, pp. 278-287)](https://people.eecs.berkeley.edu/~russell/papers/icml99-shaping.pdf) — accessed 2026-08-05
- [Luo et al. — Controlling Commercial Cooling Systems Using Reinforcement Learning (arXiv:2211.07357, 2022)](https://arxiv.org/abs/2211.07357) — 9% and 13% energy savings at two live Trane sites — accessed 2026-08-05
- [DeepMind — Safety-first AI for autonomous data centre cooling and industrial control (2018)](https://deepmind.google/discover/blog/safety-first-ai-for-autonomous-data-centre-cooling-and-industrial-control/) — accessed 2026-08-05
- [DeepMind — DeepMind AI Reduces Google Data Centre Cooling Bill by 40% (2016)](https://deepmind.google/discover/blog/deepmind-ai-reduces-google-data-centre-cooling-bill-by-40/) — accessed 2026-08-05
- [Cheng, Kahng et al. — The False Dawn: Reevaluating Google's Reinforcement Learning for Chip Macro Placement (arXiv:2306.09633, 2023)](https://arxiv.org/abs/2306.09633) — accessed 2026-08-05
- [Google — That Chip Has Sailed: A Critique of Unfounded Skepticism Around AI for Chip Design (arXiv:2411.10053, Nov 2024)](https://arxiv.org/abs/2411.10053) — accessed 2026-08-05
- [IEEE Spectrum — Ending an Ugly Chapter in Chip Design](https://spectrum.ieee.org/chip-design-controversy) — accessed 2026-08-05
- [Wikipedia — AlphaChip (controversy)](https://en.wikipedia.org/wiki/AlphaChip_(controversy)) — timeline of the dispute and Nature's editorial response — accessed 2026-08-05
- [Alex Irpan — Deep Reinforcement Learning Doesn't Work Yet (Feb 2018)](https://www.alexirpan.com/2018/02/14/rl-hard.html) — accessed 2026-08-05
- [OpenAI — Dota 2 with Large Scale Deep Reinforcement Learning (2019)](https://cdn.openai.com/dota-2.pdf) — 770 ± 50 PFLOP/s-days, ~45,000 years of self-play, 10 months — accessed 2026-08-05
- [OpenAI — Solving Rubik's Cube with a Robot Hand (arXiv:1910.07113, 2019)](https://arxiv.org/abs/1910.07113) — automatic domain randomisation, reported success rates — accessed 2026-08-05
- [Tobin et al. — Domain Randomization for Transferring Deep Neural Networks from Simulation to the Real World (arXiv:1703.06907, 2017)](https://arxiv.org/abs/1703.06907) — accessed 2026-08-05
- [Ray, Achiam & Amodei — Benchmarking Safe Exploration in Deep Reinforcement Learning (Safety Gym, 2019)](https://cdn.openai.com/safexp-short.pdf) — accessed 2026-08-05
- [Achiam, Held, Tamar & Abbeel — Constrained Policy Optimization (ICML 2017)](https://arxiv.org/abs/1705.10528) — accessed 2026-08-05
- [Alshiekh et al. — Safe Reinforcement Learning via Shielding (AAAI 2018)](https://arxiv.org/abs/1708.08611) — accessed 2026-08-05
- [Dudík, Langford & Li — Doubly Robust Policy Evaluation and Learning (ICML 2011)](https://icml.cc/2011/papers/554_icmlpaper.pdf) — accessed 2026-08-05
- [Li, Chu, Langford & Schapire — A Contextual-Bandit Approach to Personalized News Article Recommendation (WWW 2010)](https://arxiv.org/abs/1003.0146) — LinUCB, reported 12.5% click lift on Yahoo! Front Page — accessed 2026-08-05
- [Gauci et al. — Horizon: Facebook's Open Source Applied Reinforcement Learning Platform](https://openreview.net/pdf?id=SylQKinLi4) — push-notification result, ~1.5-1.8x cumulative reward — accessed 2026-08-05
- [facebookresearch/ReAgent — platform for applied RL and contextual bandits](https://github.com/facebookresearch/ReAgent) — accessed 2026-08-05
- [Netflix TechBlog — ML Platform Meetup: Infra for Contextual Bandits and Reinforcement Learning](https://netflixtechblog.com/ml-platform-meetup-infra-for-contextual-bandits-and-reinforcement-learning-4a90305948ef) — propensity logging, IPS/DR/DM bandit metrics — accessed 2026-08-05
- [Mnih et al. — Human-level control through deep reinforcement learning (Nature, 2015)](https://www.nature.com/articles/nature14236) — 50M frames per game training budget — accessed 2026-08-05

## Changelog
- 2026-08-05 — created
