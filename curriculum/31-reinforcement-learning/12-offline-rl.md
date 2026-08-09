# Offline RL, Distribution Shift, Conservative Q-Learning, Imitation & Inverse RL

> **Track:** T31 Reinforcement Learning · **Time:** 2.5h · **Prereqs:** T31-dqn, T31-continuous-control, T31-model-based, T31-exploration · **Updated:** 2026-08-05
> **Module id:** `T31-offline-rl` · **Tags:** deep-rl, offline-rl, ope, imitation-learning, critical
> **Lab:** none yet — see `labs/py/02-agent-loop/` for the pattern if you want to build one

## The 30-second version

Offline RL learns a policy from a fixed logged dataset `D` collected by some behaviour policy `\pi_\beta`, with zero further environment interaction, and it fails for one specific mechanical reason: the Bellman target `r + \gamma\max_{a'}\hat{Q}(s',a')` evaluates the Q-network at actions `a'` that `\pi_\beta` never took, where `\hat{Q}` is pure function-approximator extrapolation constrained by no data point, and the `\max` is a selection operator that deliberately picks the largest extrapolation error, so the bias is injected on every backup and amplified by `1/(1-\gamma)` — with `\gamma=0.99` that is a factor of `100`, which is how a Q-function with true values bounded by `\pm 100` ends up printing `10^7`. This is Sutton & Barto's deadly triad (function approximation + bootstrapping + off-policy) in its worst corner: online off-policy methods self-correct because the agent executes the overestimated action and gets contradicted by reality, and offline that correction channel does not exist. Every offline RL algorithm is the same move under different clothes — keep the policy inside the region where the critic was actually trained — and they differ only in *what* they constrain: BCQ constrains the action set fed to the `\max`, CQL constrains the Q-values themselves via a `\log\sum\exp` pessimism penalty, TD3+BC constrains the policy with a behaviour-cloning term (`\alpha=2.5`), and IQL constrains nothing because it never queries an out-of-distribution action at all, fitting an in-sample upper expectile (`\tau=0.7` locomotion, `\tau=0.9` AntMaze) instead. Behaviour cloning and its filtered variant (`10\%`BC) are genuine, frequently-winning baselines rather than strawmen — on near-expert narrow data no algorithm can beat BC, and offline RL earns its complexity only on suboptimal, broad-coverage data that requires trajectory stitching (AntMaze: BC scores roughly `0`, IQL roughly `40`-`50`). The part that has no good answer is off-policy evaluation: importance sampling's variance grows exponentially in horizon (`2^{100}\approx 1.3\times10^{30}` for a deterministic target against a uniform binary-action logger at `H=100`), weighted IS and doubly-robust and FQE each trade a specific bias for that variance, and the resulting confidence intervals on real logs are routinely wide enough to contain both "this policy doubles revenue" and "this policy is catastrophic," which is why the honest production architecture is offline RL to *shortlist* candidates and a guarded online test to *decide*.

## Why this gets asked

Offline RL is the only version of RL most companies can legally or physically run — you have five years of logged clicks, prescriptions, trades, or route choices, and no ability to let a randomly-initialised policy explore against real users. So the interviewer is checking whether you know the difference between "off-policy" (DQN with a replay buffer, mildly off-policy, self-correcting) and "offline" (fixed dataset, unboundedly off-policy, no correction channel), because engineers who don't know that difference confidently point `d3rlpy` or a stock SAC implementation at a logged dataset and produce a policy whose Q-values are `10^8` and whose real-world performance is worse than the logging policy. The production failure the interviewer has personally lived through is almost always one of two shapes: a Q-function that diverged silently while the TD loss curve looked perfectly healthy (prediction and target inflating together), or — far more expensive — a policy that scored beautifully under their own off-policy evaluation, shipped, and lost money, because the OPE estimate was a weighted average of three trajectories out of fifty thousand. For someone who has shipped contextual bandits on PySpark/EMR, this is the exact question of what changes when the horizon goes from `H=1` to `H>1`: at `H=1` the importance weight is `1/\pi_\beta(a|x)` and off-policy evaluation genuinely works in production; at `H=100` the weight is a product of `100` such terms and the whole edifice collapses. Interviewers use this topic to separate people who have read the CQL paper from people who have tried to tune `\alpha` with no online signal to tune it against.

---

## Lineage: past → present → future

**What came before.** Two lines converged. From the RL side, batch/fitted-value methods — Ernst, Geurts & Wehenkel's Fitted Q Iteration (2005) and Riedmiller's Neural Fitted Q Iteration (2005) — already framed "learn from a fixed batch" as a regression problem, and Lagoudakis & Parr's LSPI (2003) did the linear version; they worked acceptably with linear or tree-based approximators and small, well-covered state spaces, and mostly fell apart when the approximator became a deep network with enough capacity to extrapolate confidently into regions with no data. From the control-and-robotics side, behaviour cloning (ALVINN, Pomerleau 1988) was the default way to turn demonstrations into a policy, and its killer pain was named precisely by Ross, Gordon & Bagnell in 2011: BC is trained on the expert's state distribution and deployed on its own, so a per-step error rate of `\epsilon` compounds to a regret of `O(T^2\epsilon)` over a horizon `T`, quadratic rather than linear, because one mistake puts the learner in a state where it has no guarantee at all and can lose the remaining `T` steps of reward. DAgger fixed that with an interactive expert; the reason offline RL exists is that in the settings that matter — clinical logs, five years of recommender impressions, historical trading fills — there is no interactive expert to query and no simulator to roll out in. The moment that crystallised the modern field was Fujimoto, Meger & Precup's 2018 result (ICML 2019) that this is not a data-quantity problem: they showed DDPG trained on the *complete* replay buffer of a concurrently-running, successful DDPG agent — data whose coverage is by construction excellent — still fails to learn, and named the cause **extrapolation error**. That single experiment killed the assumption that "off-policy algorithms are off-policy, so of course they work on logs."

**Where it stands now.** The taxonomy is settled and the rankings are not. Policy-constraint methods (BCQ 2019, BEAR 2019, BRAC 2019, TD3+BC 2021), value-regularisation methods (CQL 2020), in-sample methods that never query an out-of-distribution action (IQL 2021, one-step RL 2021), model-based pessimism (MOReL and MOPO, both 2020), and sequence-model conditional BC (Decision Transformer 2021, RvS 2021) all coexist, and on D4RL the gaps between the good ones are frequently smaller than the reproduction variance — the CORL project (Tarasov et al., 2022) re-implemented these algorithms under a uniform protocol and reported numbers that differ from the originals by several normalised points in both directions, which is a live embarrassment for the field's benchmark culture. Three disagreements are genuinely open and you should be able to state them. First, **is offline RL beating a well-tuned baseline at all?** Emmons et al.'s RvS (2021) showed a plain 2-layer conditional-BC MLP with the right width and dropout matches CQL and IQL on most D4RL gym tasks, and filtered `10\%`BC beats CQL on several — versus Kumar et al. (2022), who identify the conditions where offline RL genuinely dominates (noisy or highly suboptimal data, sparse reward requiring stitching, long horizons with high initial-state variability) and concede that with sufficiently expert, narrow data *no algorithm can beat BC*. Second, **is D4RL measuring the right thing?** NeoRL (Qin et al., 2021) argues D4RL's datasets are far more exploratory and broad than any real deployed logging policy, which is typically narrow and near-deterministic, and that on realistic conservative data the D4RL ranking does not transfer and BC-like methods win — this matters more than any leaderboard delta if you are actually shipping. Third, **is pessimism the right primitive at all**, given that CQL's `\alpha` sits in a narrow band between "so pessimistic the policy collapses back to `\pi_\beta`" and "diverges," with no offline signal to tune it against, while IQL sidesteps the tuning problem and pays with structurally limited improvement over the data. What is actually deployed at scale, as opposed to published: offline pretraining followed by online finetuning in robotics (Cal-QL 2023, Q-Transformer 2023), conservative offline policies in recommendation as *candidate generators* validated by online A/B, and — the honest majority — not offline RL at all, but supervised or bandit approaches with a real online test, because the OPE story is not good enough to justify shipping a value-based policy on offline evidence alone.

**Where it's heading.** High confidence: in-sample methods (IQL and its descendants) and "simple thing plus a constraint" (TD3+BC-shaped) remain the default first attempts, because the field has repeatedly rediscovered that algorithmic complexity in offline RL buys less than data curation and a stronger baseline. High confidence: offline-pretrain-then-online-finetune is the dominant real-world pattern wherever any online interaction is permitted at all, precisely because it converts the unsolvable offline-evaluation problem into a bounded online one; Cal-QL's calibration fix (making the conservative Q-function's pessimism consistent enough that the initial online steps don't crater) exists specifically because naive CQL initialisation degrades before it improves. Medium confidence: the LLM world's near-total abandonment of value-based offline RL for preference-optimisation methods (DPO and relatives, `T31-rl-for-llms`) continues, since a sequence model's offline "policy improvement" problem is better posed as a supervised contrast than as a Bellman backup — though offline value estimation is quietly returning as process/outcome reward models for reasoning, which is the same extrapolation problem in new clothes. Speculative, and I would bet against it: that general-purpose OPE with decision-useful confidence intervals becomes possible at long horizons. Marginalised-IS methods (DualDICE 2019 and relatives) break the exponential-in-horizon dependence in theory by estimating the stationary density ratio directly rather than as a product over time, but they replace it with a saddle-point estimation problem whose own error you cannot bound tightly from data, and the exponential lower bounds for the general case are information-theoretic, not artifacts of bad estimators. Assume for planning purposes that you will need an online test.

---

## Mental model

```
ONLINE OFF-POLICY (DQN, T31-dqn):                OFFLINE (this module):

  replay buffer <--- current-ish policy            fixed dataset D <--- pi_beta
        |                    ^                           |            (frozen, gone)
        v                    |                           v
   Q-learning update         |                    Q-learning update
        |                    |                           |
        v                    |                           v
  policy takes an OVER-      |                    policy takes an OVER-
  ESTIMATED action --------->+                    ESTIMATED action ---> ???
        |                                                 |
   reality answers:                                  NOTHING ANSWERS.
   "that action gave r=-1"                           No contradiction ever
   -> target corrected                               arrives. The error is
   -> error SHRINKS                                  never corrected and gets
                                                     re-amplified every backup.

THE KILLER, precisely:

   target(s,a) = r + gamma * max_{a'} Qhat(s', a')
                                ^^^^^^^^^^^^^^^^^^
                                 a' ranges over ALL actions, including
                                 ones pi_beta NEVER took at s'. There,
                                 Qhat is pure extrapolation -- no data
                                 point constrains it -- and max() is a
                                 SELECTION operator: it hunts for the
                                 largest error, it does not average it away.

   error injected per backup:  b ~ sigma * sqrt(2 ln |A|)   (max of |A| noisy values)
   error at the fixed point:   b / (1 - gamma)  = 100b at gamma=0.99
                                                = 1000b at gamma=0.999

   AND the policy is trained to argmax Qhat, so it actively SEEKS the
   states/actions with the largest positive error. Adversarial, not random.

WHAT EVERY OFFLINE ALGORITHM DOES (same move, four places to apply it):

   D ---> [ Q-function ] ---> [ policy ]
           ^          ^            ^
           |          |            |
        CQL: push    IQL: never   TD3+BC / BCQ: keep the
        Qhat DOWN    query an     policy's actions near the
        at OOD       OOD action   data's actions
        actions      (in-sample
                     expectile)

   ...and RLHF's KL-penalty-to-reference (T31-ppo) is the SAME mechanism
   applied to a reward model instead of a critic. Reward hacking is
   OOD extrapolation of a learned reward. Identical failure, different noun.

THE HARDER HALF -- did it work?

   H=1  (contextual bandits, what you shipped on EMR):
        weight = 1 / pi_beta(a|x).   Variance ~ 1/pi_beta. FINE.
   H=100 (RL):
        weight = PRODUCT of 100 such terms.
        deterministic target vs uniform binary logger: weight = 2^100
        with prob 2^-100, else 0.   2^100 ~ 1.3e30.  NOT FINE.
```

---

## How it actually works

### The setting, stated precisely

You are given `\mathcal{D}=\{(s_i,a_i,r_i,s'_i)\}_{i=1}^{N}` generated by an unknown (or partially known) behaviour policy `\pi_\beta`, and you may not interact with the environment. Define the empirical state-action distribution `d^{\pi_\beta}(s,a)`. The goal is a policy `\pi` maximising `J(\pi)=\mathbb{E}[\sum_t\gamma^tr_t]`. Nothing about the *algorithm* has to change from `T31-dqn` — you can literally run DQN or SAC on `\mathcal{D}` — which is exactly why this fails so often: the code runs, the loss goes down, and the output is garbage.

Two distribution shifts are in play and conflating them is the single most common interview error:

1. **State shift at deployment.** The learned `\pi` visits states `\pi_\beta` never visited. This hurts you *after* you ship. It is real, and it is what behaviour cloning's `O(T^2\epsilon)` bound (below) is about.
2. **Action shift inside the Bellman target, during training.** The `\max_{a'}` (or `\mathbb{E}_{a'\sim\pi}`) in the target evaluates `\hat{Q}` at actions with zero support under `\pi_\beta`. This corrupts you *before* you ship, during training, on data you already have.

Number 2 is the killer, and it is the one that surprises people, because it means the algorithm can destroy itself without ever touching the environment.

### Deriving extrapolation error

Let `\hat{Q}_k` be the current estimate and write `\hat{Q}_k(s,a)=Q^*(s,a)+\varepsilon_k(s,a)` where `\varepsilon_k` is approximation error. On in-distribution `(s,a)` pairs, `\varepsilon_k` is bounded by the regression fit — every gradient step pins `\hat{Q}` to an observed target there. On out-of-distribution actions there is no such pin: `\varepsilon_k(s,a_{\text{OOD}})` is whatever the network's inductive bias produces when asked about a point it has never been penalised for, and for a ReLU MLP that is an unbounded linear extrapolation, not a shrink-to-mean.

Now apply the backup. Suppose at state `s'` the errors `\varepsilon(s',a')` across the `|A|` actions behave like zero-mean noise of scale `\sigma`. Standard extreme-value arithmetic for the maximum of `|A|` roughly-independent Gaussians gives

$$\mathbb{E}\left[\max_{a'}\varepsilon(s',a')\right]\;\approx\;\sigma\sqrt{2\ln|A|}$$

so the target is biased **upward** by `b\approx\sigma\sqrt{2\ln|A|}` even though the errors were mean-zero. This is exactly Thrun & Schwartz's 1993 overestimation argument and the reason Double DQN exists (`T31-dqn`), and the `\sqrt{2\ln|A|}` scaling tells you something useful: for Atari's `|A|=18`, `\sqrt{2\ln 18}\approx 2.4`, so a per-action error scale of `\sigma=1` becomes a `+2.4` bias per backup. In a continuous action space the effective `|A|` is the number of actions the actor can search over, which is unbounded, and the bias is correspondingly worse — which is why the first published demonstrations of this failure (BCQ, on DDPG) were in continuous control.

Propagate it. Ignoring generalisation shrinkage, the error recursion is `e_{k+1}\le\gamma\,e_k+b`, whose fixed point is

$$e_\infty\;=\;\frac{b}{1-\gamma}$$

At `\gamma=0.99` that is `100b`; at `\gamma=0.999` (common in long-horizon recsys and clinical settings) it is `1000b`. So a per-backup bias of `+2.4` lands you at `\hat{Q}\approx240` above truth — and true returns in a `\gamma=0.99` MDP with `|r|\le1` are bounded by `1/(1-\gamma)=100`, so the *error* is already `2.4\times` the entire legal range of the value function. Reported divergences of `10^5` to `10^8` in the offline RL literature are not exotic; they are this recursion running for `10^6` gradient steps.

Three amplifiers make it worse than that clean recursion suggests:

- **The `\max` is adversarial, not random.** The policy is `\arg\max_a\hat{Q}(s,a)`, so it does not sample the error distribution — it selects its upper tail, at every state, every step.
- **The error compounds through the policy's own state visitation.** Once `\pi` prefers an OOD action at `s'`, the next backup queries `\hat{Q}` at `s''` reached by that action, which is itself further from the data, where extrapolation is worse. Positive feedback.
- **No contradiction ever arrives.** Online, the agent executes the overestimated action, observes `r`, and the next backup pulls the estimate down: overestimation is *self-limiting* because reality is in the loop. That is the entire structural difference between "off-policy" and "offline," and it is the sentence to say in an interview.

**The observable symptom, so you can recognise it in a log.** Mean `|\hat{Q}|` over a training batch climbs monotonically across `10^5`-`10^6` gradient steps, blowing past `R_{\max}/(1-\gamma)` by orders of magnitude, *while the TD loss stays flat or small*, because prediction and target are inflating in lockstep — the residual `\hat{Q}-(r+\gamma\max\hat{Q}')` can remain tiny while both terms run to `10^7`. If you only monitor the loss, you see nothing. Log `mean(Q)`, `max(Q)`, and the ratio `\text{mean}(Q)\cdot(1-\gamma)/R_{\max}` (which should sit near `1`) on every offline run; it is a two-line addition that catches this on the first `50{,}000` steps.

### The deadly triad, restated for the offline setting

Sutton & Barto's triad: **function approximation**, **bootstrapping**, and **off-policy training**. Any two are safe; all three can diverge. Offline RL is not a new failure mode, it is the triad's extreme corner, and the useful reformulation is *how far off-policy, and can the mismatch shrink?*

| Setting | Function approx | Bootstrapping | Off-policy-ness | Self-correcting? |
|---|---|---|---|---|
| Tabular Q-learning | no | yes | yes | n/a, converges |
| Linear TD, on-policy (SARSA) | yes | yes | no | yes |
| DQN with replay (`T31-dqn`) | yes | yes | **mild and shrinking** — the buffer is refilled by policies close to the current one | **yes** — bad actions get executed and contradicted |
| Offline RL | yes | yes | **unbounded and growing** — `\pi_\beta` is frozen while `\pi` drifts away over `10^6` steps | **no** |
| Offline BC / conditional BC | yes | **no** | n/a — it is supervised learning | n/a, cannot diverge |

Two readings drop straight out. First, **removing bootstrapping removes the triad entirely** — that is why behaviour cloning, filtered BC, and Decision Transformer cannot diverge, and it is a large part of why they are competitive: they trade the ability to stitch trajectories for the guarantee that the pathology in this section is structurally impossible. Second, van Hasselt et al. (2018) studied the triad empirically in deep RL and found divergence is much rarer online than theory allows, precisely because of that correction channel; removing it is what makes offline RL brittle rather than merely theoretically risky.

### Why coverage, not sample size, is the binding constraint

The formal version. Approximate dynamic programming error bounds have the shape

$$J(\pi^*)-J(\hat{\pi})\;\le\;\frac{2\gamma}{(1-\gamma)^2}\,C\,\epsilon,\qquad C\;=\;\max_{s,a}\frac{d^{\pi}(s,a)}{d^{\pi_\beta}(s,a)}$$

where `\epsilon` is the Bellman error measured *on the data distribution* and `C` is the concentrability coefficient. Read it carefully: `\epsilon` is the thing you can see and drive down with more gradient steps; `C` is the thing you cannot see and that no amount of training touches. If `\pi` puts any probability mass where `\pi_\beta` put exactly zero, `C=\infty` and the bound is vacuous — you have a policy with arbitrarily small measured Bellman error and no guarantee whatsoever about its return. The `(1-\gamma)^{-2}` prefactor is `10{,}000` at `\gamma=0.99`, so even a finite `C` of, say, `10` and a Bellman error of `0.01` gives a bound of `\approx 2000` on a value scale of `100`; these bounds are loose. Their value is qualitative and it is decisive: **more data from the same narrow behaviour policy does not reduce `C`.** Ten billion rows of a deployed recommender's logs, all generated by one near-deterministic ranker, have essentially the coverage of ten million rows. This is the correct answer to "can we just collect more data?" and the correct argument for spending the effort on *randomised exploration budget in production logging* (even 1-5% epsilon-greedy traffic) rather than on a better algorithm.

Fujimoto et al.'s 2018 experiment is the empirical version and is worth memorising as a story: they trained a DDPG agent online, recorded its *entire* replay buffer, and then trained a second DDPG from scratch on exactly that buffer with no interaction. Coverage is by construction as good as the online agent's own experience. The offline agent still failed — and failed worse as the batch became more "final-policy-like." That result is what makes "our logs are big and diverse" an inadequate defence.

### The algorithms: what each one actually constrains, and the bill

Every method below is an answer to "how do I make `C` finite?" They differ in where they intervene, and each intervention has a price you should be able to name.

**BCQ — constrain the action set fed to the `\max` (Fujimoto, Meger & Precup, 2018/ICML 2019).** Train a conditional VAE `G_\omega(s)` on the dataset so it generates actions resembling `\pi_\beta(\cdot|s)`. At target-computation time, sample `n=10` candidate actions from the VAE, pass each through a learned perturbation network `\xi_\phi(s,a,\Phi)` bounded to `[-\Phi,\Phi]` with `\Phi=0.05` (in normalised action units), and take the max over *those* `10` perturbed candidates rather than over the whole action space. The target also uses a soft-minimum of twin critics, `\lambda\min(Q_1,Q_2)+(1-\lambda)\max(Q_1,Q_2)` with `\lambda=0.75`, a softened version of TD3's clipped double-Q. **What it costs:** the policy class is now bounded by whatever the VAE can generate, so BCQ cannot discover an action the generative model does not cover; VAE quality becomes a silent failure point (a mode-collapsed VAE on multimodal `\pi_\beta` quietly restricts you to one mode); and `\Phi` is a new hyperparameter with no offline tuning signal — too small and BCQ is BC, too large and extrapolation error returns.

**BEAR (2019) and BRAC (2019) — constrain the divergence.** BEAR replaces BCQ's explicit generative sampling with a **support** constraint via a sample-based MMD penalty `\mathrm{MMD}(\pi,\pi_\beta)\le\epsilon`, arguing correctly that matching the *support* is what bounds extrapolation while matching the *distribution* needlessly forbids improvement. BRAC systematised the family (value penalty vs policy regularisation, KL vs MMD vs Wasserstein) and reported the field's most useful negative result: once each variant was tuned properly, the choice of divergence mattered far less than the tuning, and a well-tuned simple baseline matched the elaborate ones. **What it costs:** MMD needs a kernel and bandwidth, and the estimate is sample-based over typically `4`-`10` action samples per state, which is noisy exactly where it matters.

**CQL — constrain the Q-values (Kumar, Zhou, Tucker & Levine, NeurIPS 2020).** Do not restrict the policy at all; instead make `\hat{Q}` a provable lower bound. Add to the usual Bellman regression a penalty that pushes Q *down* at actions sampled from a distribution `\mu` and *up* at actions actually in the data:

$$\min_Q\;\alpha\Big(\mathbb{E}_{s\sim\mathcal{D},a\sim\mu(\cdot|s)}[Q(s,a)]-\mathbb{E}_{(s,a)\sim\mathcal{D}}[Q(s,a)]\Big)+\tfrac{1}{2}\mathbb{E}_{\mathcal{D}}\big[(Q-\mathcal{B}^\pi\hat{Q})^2\big]$$

Choosing `\mu` adversarially (the `\mu` that maximises the penalty, subject to an entropy regulariser) gives the practical **CQL(H)** variant in which the first term becomes `\log\sum_a\exp Q(s,a)` — evaluated by sampling, typically `10` actions from the current policy plus `10` uniform actions per state in continuous control. The theorem: for `\alpha` above a computable threshold, `\hat{Q}\le Q^\pi` pointwise (the tighter variant bounds only `\mathbb{E}_{a\sim\pi}[\hat{Q}(s,a)]\le V^\pi(s)`, which is what you actually need). **Why a lower bound is the right thing:** a policy maximising an underestimate cannot be seduced by a phantom high-value action, because phantom actions are exactly the ones the penalty crushes; you convert an unbounded, adversarially-selected *over*estimate into a bounded *under*estimate, and underestimates cost you performance rather than safety. **What it costs, honestly:** (a) `\alpha` is brutal. Typical values run `0.5`-`10`, with `5.0` common for D4RL locomotion and `10.0` for AntMaze; too large and `\hat{Q}` is so flat that `\arg\max_a\hat{Q}` collapses back to `\pi_\beta` — you have paid for CQL and received behaviour cloning — and too small and the divergence in the previous section returns. The Lagrange variant auto-tunes `\alpha` against a target "action gap" threshold (`\tau=5.0` or `10.0`), which trades one un-tunable hyperparameter for another. (b) Compute: the extra `10`-`20` sampled actions per state per batch make CQL roughly `2`-`4×` slower per gradient step than TD3+BC, and `10^6` gradient steps that take under an hour for TD3+BC take several hours for CQL on a single modern GPU (rough, hardware-dependent). (c) The `2`-`5×` return improvement over prior methods that CQL reports is real on multimodal, suboptimal data and much smaller-to-absent on near-expert data.

**TD3+BC — constrain the policy, and nothing else (Fujimoto & Gu, NeurIPS 2021 spotlight).** Take TD3 (`T31-continuous-control`) unchanged and add one behaviour-cloning term to the actor loss:

$$\pi=\arg\max_\pi\;\mathbb{E}_{(s,a)\sim\mathcal{D}}\big[\lambda\,Q(s,\pi(s))-(\pi(s)-a)^2\big],\qquad \lambda=\frac{\alpha}{\frac{1}{N}\sum_{(s_i,a_i)}|Q(s_i,a_i)|}$$

with `\alpha=2.5`, plus per-dimension state normalisation. The `\lambda` normalisation is the load-bearing trick and is worth explaining in an interview: `Q` has an arbitrary scale that differs by orders of magnitude across tasks and drifts during training, so a fixed trade-off weight between `Q` and the squared BC term would need retuning per dataset; dividing by the batch mean `|Q|` makes the ratio scale-free, so a single `\alpha=2.5` transfers across all of D4RL. **What it costs:** the constraint is a *distribution* match (squared error to the logged action), not a support match, so TD3+BC genuinely cannot deviate far from `\pi_\beta` even when it should; it needs the state normalisation to work; and it is weakest on the multimodal-behaviour case where the squared error pulls the policy toward the mean of two good modes, which can be a terrible action (drive left or right around the tree; the mean is the tree). Its selling point is the bill it does *not* send: no VAE, no MMD kernel, no extra sampled actions, and the paper reports more than halving total runtime relative to prior methods.

**IQL — never query an out-of-distribution action at all (Kostrikov, Nair & Levine, 2021).** The most elegant answer, because it removes the problem instead of regularising it. Fit a state-value function `V_\psi` by **expectile regression** against the Q-values of *in-sample* actions:

$$L_V=\mathbb{E}_{(s,a)\sim\mathcal{D}}\big[L_2^\tau\big(Q_{\bar\theta}(s,a)-V_\psi(s)\big)\big],\qquad L_2^\tau(u)=\big|\tau-\mathbf{1}(u<0)\big|\,u^2$$

The `\tau`-expectile is the asymmetric-least-squares analogue of the quantile: `\tau=0.5` recovers the mean, and `\tau\to1` penalises negative residuals `\tau/(1-\tau)` times harder than positive ones, so the minimiser is pushed toward the *maximum* of the residual distribution. Concretely at `\tau=0.9` the asymmetry ratio is `9:1`; at `\tau=0.7` it is `2.33:1`. Since the residual distribution here is `Q(s,a)` over `a\sim\pi_\beta(\cdot|s)`, a high expectile approximates `\max_{a\in\text{support}(\pi_\beta)}Q(s,a)` **using only actions that appear in the dataset**. Then the critic backs that up with no max anywhere:

$$L_Q=\mathbb{E}_{(s,a,r,s')\sim\mathcal{D}}\big[(r+\gamma V_\psi(s')-Q_\theta(s,a))^2\big]$$

and the policy is extracted afterwards by advantage-weighted regression, `L_\pi=\mathbb{E}[\exp(\beta(Q(s,a)-V(s)))\log\pi(a|s)]`, which is a weighted behaviour cloning — again, only on dataset actions. Published defaults: `\tau=0.7` and `\beta=3.0` for D4RL MuJoCo locomotion, `\tau=0.9` and `\beta=10.0` for AntMaze, exponential weights clipped at `100`, `2`-layer `256`-unit MLPs, Adam at `3\times10^{-4}`, batch `256`, `\gamma=0.99`, target Polyak `0.005`, `10^6` gradient steps. **What it costs, and this is the subtle one:** the expectile is taken over the joint randomness of *action and dynamics*, so a large `\tau` is optimistic about lucky transitions too, not just about good actions — in a genuinely stochastic environment IQL's `V` inherits an optimism bias that has nothing to do with policy improvement. And because everything is in-sample, IQL's improvement over `\pi_\beta` is bounded by what stitching within the support can achieve; it will not invent a good action nobody ever took.

**One-step RL (Brandfonbrener et al., 2021) — forbid iterated bootstrapping.** Fit `Q^{\pi_\beta}` once by SARSA-style on-policy evaluation on the data (no max, no OOD query, no iteration toward a different policy), then take a *single* improvement step (advantage-weighted or greedy-with-constraint) and stop. The insight: the pathology needs *iteration* — one backup injects `b`, the geometric series turns it into `b/(1-\gamma)`. Cut the iteration and you cut the amplification. It is remarkably competitive on narrow, near-expert data and structurally incapable of the stitching that AntMaze requires (the IQL paper reports one-step methods totalling roughly `125` across AntMaze versus IQL's `378`, on the `-v0` datasets), which is a clean demonstration of exactly what multi-step bootstrapping buys and what it costs.

**Model-based offline (MOReL and MOPO, both 2020).** Learn dynamics, then plan or train inside the model with a **pessimism** penalty proportional to model uncertainty — MOReL constructs a pessimistic MDP with an absorbing low-reward state outside the model's known region, MOPO subtracts an uncertainty penalty from the reward. Same pessimism principle, applied to the dynamics rather than the values. **What it costs:** you now own both this module's extrapolation error *and* `T31-model-based`'s compounding model error, and the uncertainty estimate (typically ensemble disagreement over `5`-`7` dynamics models) is itself unreliable exactly in the regions where it matters most, because ensembles are known to be confidently wrong together off-distribution.

**Conditional / sequence-model BC (Decision Transformer 2021, RvS 2021).** No Bellman backup at all: condition a sequence model on a target return-to-go (or goal) and train it to predict the demonstrated action, then at test time condition on a high return. No bootstrapping means no triad, no divergence, no `\alpha` to tune. **What it costs:** it cannot stitch, and it is provably confounded in stochastic environments — conditioning on a high return-to-go selects trajectories that got *lucky*, so the model learns to imitate actions whose observed return came from environment noise rather than from the action being good (the "dichotomy of control" problem, Yang et al. 2022). On AntMaze, where the whole task is stitching sub-trajectories, this family scores near the floor.

### Behaviour cloning is a real baseline and it frequently wins

BC is `\pi=\arg\max_\pi\mathbb{E}_{(s,a)\sim\mathcal{D}}[\log\pi(a|s)]`. That is it — maximum likelihood on logged actions, no reward used at all. It deserves respect for four concrete reasons.

1. **No bootstrapping, so no deadly triad.** The pathology derived above is not mitigated, it is structurally impossible. The training loss you watch is the loss you get.
2. **It is the only method in this module whose hyperparameters you can tune offline honestly.** Held-out negative log-likelihood is a real validation metric computed on the same distribution you trained on. Every value-based method's key hyperparameter (`\alpha`, `\Phi`, `\tau`, `\beta`) needs a signal about *policy return* that offline data cannot give you without OPE — and OPE, as the next section argues, cannot give it to you either. This is the most under-appreciated practical argument in the whole area.
3. **On near-expert data it is optimal and no algorithm can beat it.** If `\pi_\beta` is expert, the best policy in the data is the data, and any deviation is error. Kumar et al. (2022) state this explicitly.
4. **`10\%`BC is stronger than plain BC and is usually forgotten.** Sort trajectories by return, keep the top `10\%` (or top `25\%`), and clone those. This is a one-line change that converts BC from "imitate the average logger" to "imitate the logger's best days," and it beats CQL on several D4RL locomotion datasets. If you present offline RL results without this baseline, a good interviewer will ask for it.

The published numbers, from the IQL paper's D4RL `-v2` locomotion table (normalised score, `0=` random policy, `100=` expert):

| Dataset | BC | `10\%`BC | CQL | TD3+BC | IQL |
|---|---|---|---|---|---|
| halfcheetah-medium | `42.6` | `42.5` | `44.0` | `48.3` | `47.4` |
| hopper-medium | `52.9` | `56.9` | `58.5` | `59.3` | `66.3` |
| walker2d-medium | `75.3` | `75.0` | `72.5` | `83.7` | `78.3` |
| AntMaze total (`-v0`, 6 tasks) | `\approx0` | `\approx0` | `303.6` | — | `378.0` |

Two readings. On locomotion the entire spread between the worst and best method is roughly `5`-`14` normalised points, which is the same order as the reproduction variance CORL reported across seeds and implementations — treat those gaps as noise unless you have run `\ge5` seeds yourself. On AntMaze the spread is not noise: BC scores essentially zero and IQL scores `378` total, because the task requires composing sub-trajectories from a dataset in which *no single trajectory* solves the maze. That contrast is the answer to "when is offline RL worth it," and it is worth memorising as a pair.

**The decision rule, compressed:**

| Dataset property | Use |
|---|---|
| Near-expert, narrow, dense reward | BC, or `10\%`BC. Stop here. |
| Mixed quality, dense reward, short horizon | `10\%`BC first; offline RL must beat it to justify itself |
| Highly suboptimal, broad coverage | Offline RL (IQL or TD3+BC first, CQL if multimodal) |
| Sparse reward, solution requires stitching sub-trajectories | Offline RL, and nothing else will work |
| Expert data but long horizon and high initial-state variability | Offline RL can still win (Kumar et al. 2022) — BC's `T^2` compounding bites |
| Heteroskedastic — expert in some states, random in others | Neither cleanly; support-constrained methods, and expect trouble |
| Narrow near-deterministic production logger, no exploration | Nothing works. Buy coverage with `1`-`5\%` randomised traffic first. |

### Off-policy evaluation: the genuinely hard part

Training a policy offline is the easy half. The question that decides whether you can ship — *is this policy better than the one currently running?* — has no clean offline answer, and pretending otherwise is how offline RL projects fail expensively.

**Ordinary importance sampling.** With trajectories `\tau_i` logged under `\pi_\beta` and known behaviour probabilities,

$$\hat{V}_{\text{IS}}=\frac{1}{n}\sum_{i=1}^{n}\left(\prod_{t=0}^{H-1}\frac{\pi(a_t^i|s_t^i)}{\pi_\beta(a_t^i|s_t^i)}\right)G_i,\qquad G_i=\sum_{t}\gamma^tr_t^i$$

Unbiased, given known `\pi_\beta` and full support. Now compute the variance in the simplest non-trivial case: binary actions, `\pi_\beta` uniform (`0.5` each), `\pi` deterministic. The per-step ratio `\rho_t\in\{0,2\}`. A trajectory survives only if `\pi` agrees with the log at every one of `H` steps, probability `2^{-H}`, and its weight is then `2^H`. So:

- `H=10`: weight `1024`, survival probability `\approx10^{-3}`. With `n=10^4` trajectories you get `\approx10` non-zero terms. Painful but not hopeless.
- `H=20`: weight `\approx1.05\times10^6`, survival `\approx10^{-6}`. With `n=10^6` you expect **one** non-zero term.
- `H=100`: weight `\approx1.27\times10^{30}`. There is no dataset.

Variance grows as `2^H/n` — **exponentially in horizon**, and this is an information-theoretic limit in the general case (Jiang & Li 2016 give matching lower bounds), not an artifact of a lazy estimator. This is exactly what changes between contextual bandits and RL: at `H=1` the weight is `1/\pi_\beta(a|x)`, so a logger with a `1\%` floor on action probabilities gives weights bounded by `100` and everything works, which is why bandit off-policy evaluation is a solved, shipped, production-grade technique and full-horizon OPE is not.

**Per-decision IS (PDIS)** (Precup, Sutton & Singh, 2000). The reward at time `t` cannot depend on actions taken after `t`, and the future ratios have expectation `1`, so you only need the product up to `t`:

$$\hat{V}_{\text{PDIS}}=\frac{1}{n}\sum_i\sum_{t=0}^{H-1}\gamma^t\left(\prod_{k=0}^{t}\rho_k^i\right)r_t^i$$

Still unbiased, strictly lower variance, because early rewards carry short products. It converts the exponent from the full horizon to the *effective* horizon `\approx1/(1-\gamma)`, which at `\gamma=0.99` is `100` — an improvement only if your true horizon was much longer than that. Use it always; do not expect it to save you.

**Weighted IS (WIS).** Self-normalise: divide by `\sum_iw_i` rather than by `n`. This makes the estimator a convex combination of observed returns, so it is **bounded** by `[\min_iG_i,\max_iG_i]` no matter how extreme the weights are. It is biased (consistent, bias `O(1/n)`) and it is almost always the right default over ordinary IS in practice, because an unbiased estimator with variance `10^{30}` is worse than useless — it is actively misleading, since any finite sample of it looks confidently wrong.

**Effective sample size — the diagnostic that should gate every OPE result.**

$$\mathrm{ESS}=\frac{\left(\sum_iw_i\right)^2}{\sum_iw_i^2}$$

ESS is how many trajectories your weighted estimate is *really* averaging. If `n=50{,}000` and `\mathrm{ESS}=3`, your point estimate is a weighted average of three episodes and its bootstrap confidence interval is a fiction — the bootstrap resamples the same three dominant trajectories. Rules of thumb I would defend in an interview: refuse to act on an OPE number with `\mathrm{ESS}<100`, treat `\mathrm{ESS}/n<0.01` as "the target policy is out of the log's support, go get exploration data," and always report ESS next to the estimate. Related, cheaper red flag: `\max_iw_i/\sum_iw_i`. If one trajectory holds more than `10\%` of the total weight, you are estimating that trajectory, not the policy.

**Doubly robust (Jiang & Li, 2016; Thomas & Brunskill, 2016).** Use a learned model `\hat{Q},\hat{V}` as a control variate, recursively:

$$\hat{V}_{\text{DR}}^{(t)}=\hat{V}(s_t)+\rho_t\Big(r_t+\gamma\hat{V}_{\text{DR}}^{(t+1)}-\hat{Q}(s_t,a_t)\Big)$$

The name is the guarantee: the estimator is unbiased if **either** the model is correct **or** the behaviour probabilities are correct — you get two chances. Mechanically, the huge weight `\rho_t` now multiplies a *residual* `(r_t+\gamma\hat{V}'-\hat{Q})` rather than a raw return, and if the model is even roughly right that residual is near zero, so the variance contribution collapses. Variance reductions of one to two orders of magnitude over PDIS are typical when the model is decent. **The catch nobody mentions:** where the model is *bad*, DR is worse than WIS, because it multiplies unbounded weights by a large residual and, unlike WIS, has no self-normalisation to bound it. MAGIC (Thomas & Brunskill, 2016) addresses this by blending the `j`-step partial-DR estimators with weights chosen to minimise an estimate of MSE, which is the right shape of fix and adds its own estimation error.

**FQE (fitted Q evaluation)** (Le, Voloshin & Yue, 2019; Paine et al., 2020). Drop importance weights entirely. Iterate regression:

$$\hat{Q}_{k+1}=\arg\min_Q\ \mathbb{E}_{\mathcal{D}}\Big[\big(Q(s,a)-(r+\gamma\hat{Q}_k(s',\pi(s')))\big)^2\Big],\qquad \hat{V}^\pi=\mathbb{E}_{s_0\sim d_0}\big[\hat{Q}(s_0,\pi(s_0))\big]$$

Low variance — it is just regression. But look at `\hat{Q}_k(s',\pi(s'))`: FQE bootstraps off the *target policy's* actions at `s'`, which are precisely the out-of-distribution actions this entire module says you cannot trust. **FQE inherits the exact extrapolation error it is being used to measure**, which is the deepest and most quotable irony in offline RL: your evaluator overestimates optimistically for the same structural reason your learner did, and the two errors are correlated because they share a data distribution and often an architecture. In the DOPE benchmark (Fu et al., 2021), which evaluated OPE methods across D4RL-style tasks with ground-truth online returns, FQE was among the better performers on average, no estimator dominated across task families, and rank correlation with true return was far from perfect even for the winners — meaning OPE frequently gets the *ordering* of candidate policies wrong, which is the only thing you actually needed it for.

**Marginalised IS / density-ratio methods (DualDICE, Nachum et al. 2019; GenDICE).** Estimate the stationary state-action density ratio `w(s,a)=d^\pi(s,a)/d^{\pi_\beta}(s,a)` directly by solving a convex-dual optimisation, rather than building it as a product of `H` per-step ratios. This genuinely breaks the exponential-in-horizon dependence, which is the main theoretical advance of the last several years. It replaces it with a saddle-point problem whose own estimation error is hard to bound from data, and adoption outside benchmarks remains thin.

**Why the confidence intervals are too wide to decide with.** High-confidence OPE (Thomas, Theocharous & Ghavamzadeh, 2015) gives *valid* lower bounds by applying concentration inequalities to the IS weights. But Hoeffding-style bounds scale with the *range* of the random variable, and the weights range up to `\prod_t1/\pi_\beta` — a bound of width `O(w_{\max}\sqrt{\ln(1/\delta)/n})` with `w_{\max}=2^{20}` is not a confidence interval, it is a statement that the value is somewhere on the real line. Empirical-Bernstein and bootstrap variants tighten this materially and still, on realistic logs, deliver intervals like `[0.4\times,\,2.5\times]` the behaviour policy's value. That interval contains "meaningfully better," "no change," and "disaster." Gottesman et al.'s *Guidelines for Reinforcement Learning in Healthcare* (Nature Medicine, 2019) makes the operational version of this point about the AI Clinician sepsis work (roughly `17{,}000` ICU patient trajectories from MIMIC-III): with noise, limited data, and unobserved confounding, the standard confidence measures are insufficient to support a clinical claim, and OPE should be used to **reject** policies rather than to certify them. That is the correct posture in industry too.

**The production architecture that follows.** Offline RL to generate a *shortlist* of `3`-`5` candidate policies; OPE (WIS + DR + FQE, and disagreement between them treated as a red flag) purely as a **filter** that eliminates obviously-broken candidates; then a small, guarded online test — `1`-`5\%` of traffic, hard safety constraints, automatic rollback on a guardrail metric — to make the actual decision. If you cannot run any online test at all, the honest statement in the interview is "then I would not ship a learned policy; I would ship a constrained one whose worst case I can bound by construction, and spend the quarter buying exploration data instead."

### Imitation learning and DAgger's covariate-shift fix

Behaviour cloning is supervised learning on `(s,a)` pairs, and its failure is purely distributional. Train on `d^{\pi^*}` (the expert's state distribution), deploy on `d^{\hat\pi}` (your own). Ross & Bagnell's bound: if the learner's expected `0`-`1` action error under the *expert's* distribution is `\epsilon`, then

$$J(\hat\pi)\;\le\;J(\pi^*)+O(T^2\epsilon)$$

**Where the `T^2` comes from, since asserting it is not enough.** At each of `T` steps there is probability up to `\epsilon` of taking a wrong action. A wrong action puts you in a state off the expert's distribution, where you have *no guarantee at all* — worst case you never recover and forfeit the remaining reward, up to `T` more steps of cost. So the expected cost is `T` opportunities `\times\ \epsilon` probability `\times\ T` remaining cost `=T^2\epsilon`. Put numbers on it: `\epsilon=0.01` on a `T=1000`-step driving episode gives a bound of `10^4` in units of per-step cost, versus `10^2` for the linear-in-`T` ideal. That factor of `T` is why a `99\%`-accurate driving policy drifts off the road.

**DAgger** (Ross, Gordon & Bagnell, AISTATS 2011) fixes it by making the training distribution match the deployment distribution through iteration:

```
D <- expert demonstrations
pi_1 <- train(D)
for i = 1..N:
    beta_i = decay schedule, e.g. p^i with p=0.5, or beta_1=1 then 0
    pi_mix = beta_i * expert + (1 - beta_i) * pi_i     # roll out MIXTURE
    visit states with pi_mix, and at EVERY visited state
        query the EXPERT for the action it would have taken
    D <- D  U  {(s, expert(s)) for those states}       # AGGREGATE, never discard
    pi_{i+1} <- train(D)                                # retrain on ALL data
return best pi_i by validation
```

The key move is that labels come from the **expert** but states come from the **learner**. Formally it is a reduction to no-regret online learning (Follow-the-Leader over the sequence of per-iteration losses), and the guarantee improves to `J(\hat\pi)\le J(\pi^*)+O(T\epsilon)` — **linear** in horizon, matching the best achievable. Typical practice: `N=10`-`20` iterations, `\beta_1=1` (pure expert on the first pass, so the first dataset is clean) and `\beta_i=0` thereafter, which the paper shows is sufficient for the no-regret guarantee.

**When NOT to use DAgger, which is most of the time in the settings this module cares about.** DAgger requires an *interactive* expert who can be queried at arbitrary states the learner reaches. Your five years of logged clinical decisions are not an expert you can ask new questions of; neither is a historical recommender log. That absence is the entire reason offline RL exists. Second, DAgger's early iterations deliberately drive the system with a bad policy to generate informative states, which is unacceptable in any safety-critical setting — hence HG-DAgger and EnsembleDAgger, which hand control back to the human when the learner's ensemble disagrees. Third, expert labelling cost is linear in states visited, which for a human expert is the binding constraint. The cheap alternative when you have no interactive expert is *manufactured* covariate shift: NVIDIA's PilotNet (Bojarski et al., 2016) mounted left and right cameras alongside the centre one and labelled those shifted views with a corrected steering command, synthesising recovery data from off-distribution states without ever querying a human again — and DART (Laskey et al., 2017) injects noise into the expert during collection so the demonstrations themselves cover the neighbourhood of the expert's trajectory.

### Inverse RL and the identifiability problem

IRL inverts the usual direction: given demonstrations, infer the reward `R` that makes the demonstrator optimal, then optimise it (possibly in a new environment). The motivation is that in most real problems **reward specification is the bottleneck** — nobody can write down the reward function for "drive like a competent human" or "treat this patient well," but everyone can produce demonstrations.

**The problem is ill-posed, and precisely so.** Ng & Russell (2000) characterised the set of rewards consistent with an observed optimal policy by linear constraints and immediately noted the degeneracy: `R\equiv0` makes *every* policy optimal, so it satisfies the constraints for any demonstration set. There are four distinct sources of non-identifiability and naming them separately is a strong interview signal.

1. **Constant/zero rewards.** `R=c` for any constant explains all behaviour.
2. **Potential-based shaping.** By Ng, Harada & Russell (1999), `R'(s,a,s')=R(s,a,s')+\gamma\Phi(s')-\Phi(s)` leaves the optimal policy invariant for *every* potential function `\Phi`. So the reward is recoverable at best up to an equivalence class defined by shaping plus positive affine scaling, and the class is infinite-dimensional. Cao, Cohen & Szpruch (NeurIPS 2021) give the exact characterisation of these classes.
3. **Support.** Demonstrations constrain `R` only where the demonstrator went. Off the demonstrated support, `R` is unconstrained — which is *the same distribution-shift problem as the rest of this module*, relocated into reward space.
4. **Reward-dynamics entanglement.** A reward fitted to behaviour in environment `M` may encode facts about `M`'s dynamics rather than the agent's preferences, so it does not transfer to `M'`. AIRL (Fu, Luo & Levine, 2017) makes disentangling this its explicit objective and demonstrates that naively learned rewards routinely fail to transfer.

**MaxEnt IRL** (Ziebart et al., AAAI 2008) resolves ambiguity 1 by a modelling commitment rather than by more data: among all trajectory distributions matching the demonstrated feature expectations, pick the maximum-entropy one, which gives `p(\tau)\propto\exp\big(\sum_tR_\theta(s_t,a_t)\big)`. That is a unique solution, and it buys uniqueness with an assumption — the demonstrator is Boltzmann-rational, exponentially more likely to pick higher-reward trajectories rather than exactly optimal. That assumption is a choice, not a fact, and Ziebart's original driver-route data notwithstanding, it is wrong in most settings involving humans under time pressure. The descendants: Deep MaxEnt (Wulfmeier et al., 2015) replaces linear reward features with a network; GCL (Finn et al., 2016) makes it sample-based for continuous control; **GAIL** (Ho & Ermon, 2016) skips the reward entirely and matches occupancy measures with a GAN discriminator — excellent imitation, but it deliberately gives up the reward, so it transfers nothing; AIRL recovers a transferable reward by restricting the discriminator's functional form.

**Why this matters in 2026 even if you never write `irl.py`.** An RLHF reward model is an IRL-adjacent object trained from pairwise preferences under Bradley-Terry rather than from demonstrations, and it inherits every problem above: it is identifiable only up to a monotone transform on the comparison distribution, it is unconstrained off the support of the preference data, and **reward hacking is exactly the policy exploiting the region where the reward model was never constrained by data**. That is the identical mechanism as the `\max_{a'}\hat{Q}(s',a')` failure derived at the top of this module, with a reward model in place of a critic. Which is why the fix is also identical: RLHF's explicit KL penalty to the reference policy (`T31-ppo`, `T31-rl-for-llms`) is a policy constraint, structurally the same object as TD3+BC's behaviour-cloning term. Saying that sentence out loud in an interview is worth more than reciting any three algorithms.

---

## Build it from scratch

Two pieces, both small enough to hold in your head. First, the core of IQL — chosen over CQL because the entire mechanism is three loss functions and no sampled actions, which makes it the thing to write on a whiteboard. Lab: `labs/py/31-12-offline-rl/`.

```python
# untested sketch -- IQL core: expectile V, in-sample Q backup, AWR policy.
# Defaults from Kostrikov, Nair & Levine (2021): tau=0.7 / beta=3.0 for D4RL
# locomotion; tau=0.9 / beta=10.0 for AntMaze; 2x256 MLPs; Adam 3e-4; batch 256.
import torch, torch.nn.functional as F

TAU, BETA, GAMMA, POLYAK, EXP_CLIP = 0.7, 3.0, 0.99, 0.005, 100.0

def expectile_loss(diff, tau=TAU):
    # asymmetric squared error: negative residuals weighted tau/(1-tau) more,
    # so the minimiser is pushed toward the MAX of the residual distribution.
    # tau=0.5 -> mean; tau=0.9 -> 9:1 asymmetry; tau->1 -> in-sample max.
    w = torch.where(diff > 0, tau, 1.0 - tau)
    return (w * diff.pow(2)).mean()

def iql_step(batch, q_net, q_target, v_net, policy, opts):
    s, a, r, s2, done = batch

    # 1) V: expectile regression toward Q(s, a) for a ACTUALLY IN THE DATA.
    #    No max, no sampled action -- this is the whole trick.
    with torch.no_grad():
        q_sa = torch.min(*q_target(s, a))          # twin critics, take min
    v = v_net(s)
    loss_v = expectile_loss(q_sa - v)

    # 2) Q: back up the expectile value. Still no OOD query anywhere.
    with torch.no_grad():
        target = r + GAMMA * (1.0 - done) * v_net(s2)
    q1, q2 = q_net(s, a)
    loss_q = F.mse_loss(q1, target) + F.mse_loss(q2, target)

    # 3) Policy: advantage-weighted behaviour cloning on dataset actions only.
    with torch.no_grad():
        adv = q_sa - v_net(s)
        w = torch.exp(BETA * adv).clamp(max=EXP_CLIP)   # clip or this explodes
    loss_pi = -(w * policy.log_prob(a, s)).mean()

    for name, loss in (("v", loss_v), ("q", loss_q), ("pi", loss_pi)):
        opts[name].zero_grad(); loss.backward(); opts[name].step()

    with torch.no_grad():                                # Polyak target update
        for p, tp in zip(q_net.parameters(), q_target.parameters()):
            tp.mul_(1 - POLYAK).add_(POLYAK * p)

    return {"loss_v": loss_v.item(), "loss_q": loss_q.item(),
            "mean_q": q1.mean().item(), "max_q": q1.max().item()}
```

Log `mean_q` and `max_q` on every step, not just the losses. The divergence signature derived above is invisible in `loss_q` and unmissable in `mean_q`.

Second, the WIS + ESS evaluator, which is the piece people skip and then regret. This is `~25` lines and it is the thing that stops you shipping a policy on three trajectories:

```python
# untested sketch -- weighted per-decision IS with the diagnostics that matter.
import numpy as np

def wis_evaluate(trajectories, target_probs, behav_probs, gamma=0.99):
    """trajectories: list of reward arrays. target_probs/behav_probs: list of
    per-step action probabilities under pi and pi_beta. Returns estimate + the
    diagnostics that decide whether the estimate means anything."""
    weights, returns = [], []
    for rew, p_pi, p_b in zip(trajectories, target_probs, behav_probs):
        p_b = np.clip(p_b, 1e-6, None)             # guard: logger with 0 prob
        logw = np.cumsum(np.log(p_pi) - np.log(p_b))   # per-DECISION products
        disc = gamma ** np.arange(len(rew))
        # per-decision IS return for this trajectory
        returns.append(float(np.sum(disc * np.exp(logw) * rew)))
        weights.append(float(np.exp(logw[-1])))        # full-trajectory weight

    w = np.asarray(weights); g = np.asarray(returns)
    ess = w.sum() ** 2 / np.sum(w ** 2)                # effective sample size
    wis = float(np.sum(w * g) / max(w.sum(), 1e-12))   # self-normalised
    return {
        "wis": wis,
        "ordinary_is": float(g.mean()),
        "n": len(w),
        "ess": float(ess),
        "ess_frac": float(ess / len(w)),
        "max_weight_share": float(w.max() / max(w.sum(), 1e-12)),
        "trustworthy": bool(ess >= 100 and w.max() / max(w.sum(), 1e-12) < 0.10),
    }
```

Run this before you run anything else. If `ess_frac < 0.01`, no algorithm choice in the previous section is going to save the project, and the correct next action is to negotiate for randomised exploration traffic.

---

## How it's done in production

| Layer | What you actually use | What it adds |
|---|---|---|
| Algorithms | `d3rlpy` (CQL, IQL, BCQ, TD3+BC, AWAC, plus a `d3rlpy.ope` module with FQE) or CORL's single-file reference implementations | Tested implementations with the published hyperparameters already baked in; CORL specifically exists so you can diff your numbers against a uniform-protocol reproduction rather than against a paper table |
| Datasets | Minari (Farama Foundation), the maintained successor to D4RL, with reproductions of the D4RL suites; RL Unplugged for Atari/DM-control scale | Versioned, checksummed episode storage with a standard `(s,a,r,s')` iteration API, so your dataset is not a pickled numpy blob nobody can reproduce |
| Evaluation | FQE from `d3rlpy.ope`, plus your own WIS/DR with ESS reporting; DOPE-style protocol if you have any ground truth | Turns "the policy looks good" into a number with a stated diagnostic; the ESS gate is the part you have to add yourself |
| Logging infrastructure | Propensity logging: store `\pi_\beta(a|s)` **at decision time**, alongside the action | Without logged propensities, every IS-family estimator is unavailable and you are down to FQE and hope. This is a one-line change in the serving path that is impossible to retrofit. |
| Exploration budget | `1`-`5\%` randomised or epsilon-greedy traffic, or Thompson sampling on the deployed policy | Buys the support coverage that bounds `C`. This is the highest-leverage engineering action in the entire topic and it is an infrastructure decision, not a modelling one. |
| Deployment | Offline pretrain → guarded online finetune (Cal-QL 2023) where any interaction is allowed | Converts an unsolvable offline evaluation problem into a bounded online one; Cal-QL specifically calibrates the conservative Q-function so the first online steps do not degrade before improving |
| Safety | Action masking / hard constraints applied *outside* the policy, plus automatic rollback on guardrail metrics | The learned policy's worst case is unbounded; the constrained wrapper's is not. Never rely on the reward function to encode a hard safety constraint. |

### Failure modes

| Symptom | Cause | Fix |
|---|---|---|
| `mean(Q)` on the training batch climbs monotonically past `10^5`, `10^7`, `10^9` while `loss_q` stays flat and small | Extrapolation error at OOD actions in the Bellman target, amplified by `1/(1-\gamma)`; prediction and target inflate in lockstep so the residual stays small | Add a constraint: switch to IQL (no OOD query at all) or add CQL's penalty / TD3+BC's BC term. Assert `mean(Q)*(1-gamma) < 5*R_max` and kill the run when it trips |
| Policy scores excellently under your own FQE/OPE, then loses money or degrades in the online A/B | The evaluator shares the learner's blind spot — FQE bootstraps off the same OOD actions the policy prefers, so learner and evaluator err in the same direction; or the OPE estimate had a tiny ESS | Report ESS with every estimate; require agreement between WIS, DR, and FQE; treat disagreement as a hard block. Use OPE only to reject, never to certify |
| OPE point estimate looks plausible but `ESS = 3` out of `n = 50{,}000` trajectories | Target policy is nearly deterministic and far from the near-deterministic logger, so almost all trajectory weights are `0` and a handful are astronomically large | Stop. No estimator fixes missing support. Either constrain the target policy closer to `\pi_\beta` (raising ESS) or acquire randomised-traffic data |
| CQL run produces a policy whose actions are indistinguishable from `\pi_\beta`, and returns match the logger exactly | `\alpha` too large — the pessimism penalty flattened `\hat{Q}` so much that `\arg\max_a\hat{Q}(s,a)` is just the data's action; you bought CQL and received behaviour cloning | Reduce `\alpha` (try the `0.5`-`5` range) or switch to the Lagrange variant with a target action gap. Then check whether plain `10\%`BC would have done the same for `1/50` the compute |
| Training is stable, offline metrics fine, but the agent fails catastrophically on `~2\%` of episodes in production | State-distribution shift at deployment: the policy reaches states absent from `\mathcal{D}`, where both the policy and the critic are extrapolating | Add an out-of-support detector (VAE reconstruction error or ensemble disagreement on `s`) and fall back to the logging policy above a threshold; this is the runtime analogue of a support constraint |
| BC policy trained to `98\%` action accuracy drifts off course after `50`-`100` steps and never recovers | Covariate shift: `O(T^2\epsilon)` compounding, one mistake puts the learner in states the expert never demonstrated | DAgger if an interactive expert exists; otherwise synthesise recovery data (PilotNet's shifted cameras) or inject noise during collection (DART) |
| Learned IRL/RLHF reward gives implausibly high scores to a policy that a human immediately calls bad | Reward hacking — the policy found the region where the learned reward was never constrained by preference/demonstration data. Same OOD extrapolation as the critic failure, different noun | KL penalty to the reference policy, reward-model ensembling with pessimistic aggregation, and periodic fresh preference collection *on the new policy's own outputs* |
| Offline agent beats the logger on D4RL-style benchmarks but loses on your production log | Benchmark mismatch: D4RL datasets are far broader/more exploratory than a deployed near-deterministic logger (the NeoRL critique). Your `C` is much larger than the benchmark's | Re-rank candidate methods on a held-out slice of your *own* log with your own logger's narrowness; expect BC-family methods to move up the ranking |
| Decision Transformer conditioned on a high return-to-go performs well in a deterministic sim and poorly in a stochastic one | Conditioning on high return selects lucky trajectories, so the model imitates actions whose returns came from environment noise rather than from merit | Use a value-based method, or a variant that conditions on something the policy controls rather than on realised return |

---

## Tradeoffs & when NOT to use it

- **Do not use offline RL when your logging policy is narrow and near-deterministic, which describes most production systems.** A deployed ranker or a clinical protocol produces logs with essentially no action diversity at any given state, so `C` is effectively infinite regardless of row count. Ten billion rows from one policy have roughly the coverage of ten million. Spend the quarter negotiating a `1`-`5\%` randomised exploration slice instead; that changes the problem, whereas a better algorithm does not.
- **Do not use offline RL when the data is near-expert.** No algorithm can beat behaviour cloning on expert data, and you will spend weeks tuning `\alpha` to arrive back at the demonstration policy. Run BC and `10\%`BC first, always, and make offline RL beat them before it earns a line in the design doc.
- **Do not use offline RL when you cannot run any online test, and the decision is consequential.** The honest position is that OPE confidence intervals on realistic logs routinely span "clearly better" to "clearly harmful," so there is no evidence standard you can meet. Ship a constrained or rule-based policy whose worst case you can bound by construction, and use offline RL only to generate hypotheses.
- **Do not use offline RL when the horizon is `1`.** If your problem is contextual bandits — one decision, immediate reward, which is where a large fraction of "RL" business problems actually live — use contextual bandits. The importance weight is `1/\pi_\beta(a|x)` rather than a product of `100` of them, off-policy evaluation genuinely works, the theory is tight, and the operational story is mature. Reaching for full RL when `H=1` imports every problem in this module for no benefit.
- **Do not use CQL as your first attempt.** It is the most cited and the most annoying to tune: `\alpha` sits in a narrow band between "collapses to BC" and "diverges," it is `2`-`4×` slower per step than TD3+BC, and you have no offline signal to tune it against. Start with IQL or TD3+BC, both of which have hyperparameters that transferred across all of D4RL unchanged, and escalate to CQL only if multimodal behaviour data specifically demands value-side pessimism.
- **Do not treat DAgger as available.** It needs an interactive expert queryable at states the learner reaches. If you had that, you would not be doing offline RL. Reach for synthesised recovery data or noise-injected collection instead.
- **Do not treat a learned reward (IRL or RLHF) as a specification.** It is identifiable only up to potential shaping and positive scaling, unconstrained off the demonstration support, and entangled with the dynamics it was fitted in. It is a useful training signal inside a KL ball around the data and an actively dangerous one outside it.
- **Weigh the operational cost honestly.** An offline RL system carries a policy, a critic, an OPE stack, a propensity-logging dependency in the serving path, a support-detection fallback, and a set of hyperparameters you cannot validate offline. A supervised ranker plus a bandit carries one model and a working evaluation story. The offline RL version needs to be *substantially* better, not marginally better, to be worth that surface area — and on most datasets the measured gap over `10\%`BC is smaller than the seed variance.

---

## Interview questions

### Q1 — What is the difference between off-policy RL and offline RL? DQN is off-policy, so why can't I just run it on a logged dataset?
**Testing:** whether you know the one distinction that the entire field rests on. This is the screening question.
**Answer:** DQN is off-policy in the sense that it learns from data generated by earlier versions of itself, but the replay buffer is continuously refilled by policies *close to the current one*, so the distribution mismatch is bounded and, crucially, **self-correcting**: when the Q-function overestimates an action, the agent executes it, observes the real reward, and the next backup pulls the estimate down. Offline RL removes that correction channel entirely — `\pi_\beta` is frozen and `\pi` drifts arbitrarily far from it over `10^6` gradient steps, so the mismatch grows monotonically and nothing ever contradicts an overestimate. Mechanically, the Bellman target `r+\gamma\max_{a'}\hat{Q}(s',a')` evaluates `\hat{Q}` at actions `\pi_\beta` never took, where `\hat{Q}` is unconstrained extrapolation, and `\max` is a selection operator that picks the largest extrapolation error rather than averaging it away. That bias compounds through the backup to `b/(1-\gamma)`, which is `100b` at `\gamma=0.99`.
**Follow-up trap:** *"So it's a data-quantity problem — collect more logs and it goes away?"* No, and there is a specific experiment that settles it: Fujimoto et al. (2018) trained DDPG online, saved its entire replay buffer, and trained a fresh DDPG on exactly that buffer. Coverage is by construction as good as the successful online agent's own experience, and the offline agent still failed. The binding constraint is the concentrability coefficient `C=\max_{s,a}d^\pi(s,a)/d^{\pi_\beta}(s,a)`, which is a property of the *support* of your logging policy, not of the row count — more rows from the same narrow policy leave `C` unchanged.

### Q2 — Restate the deadly triad for the offline setting. Which leg is doing the damage?
**Testing:** whether you can connect a textbook fact to the specific mechanism, rather than reciting three words.
**Answer:** The triad is function approximation, bootstrapping, and off-policy training; any two are safe, all three can diverge. Offline RL is the triad's extreme corner because the off-policy leg is *unbounded and growing* rather than mild and shrinking. But the leg you can actually remove is **bootstrapping** — and removing it removes the pathology completely, which is why behaviour cloning, filtered BC, and Decision Transformer cannot diverge and are competitive baselines rather than strawmen. It is also why one-step RL works: the amplification `b/(1-\gamma)` is a geometric series over *iterated* backups, so a single non-iterated evaluation step gets you `b` instead of `100b`.
**Follow-up trap:** *"If bootstrapping is the problem, why use it at all?"* Because it is what buys **stitching** — combining sub-trajectories from different episodes into a better trajectory than any single logged one. The cleanest demonstration is D4RL AntMaze, where no single trajectory in the dataset solves the maze: BC scores essentially `0` and IQL scores `378` total across the six `-v0` tasks. On locomotion datasets where the whole spread between BC and the best method is `5`-`14` normalised points, bootstrapping is barely earning its risk; on AntMaze it is the entire task.

### Q3 — Derive why overestimation is worse offline than online. Put numbers on it.
**Testing:** derivation over assertion; this is the module's central argument.
**Answer:** Write `\hat{Q}=Q^*+\varepsilon` with `\varepsilon` mean-zero of scale `\sigma`. For `|A|` roughly-independent errors, `\mathbb{E}[\max_{a'}\varepsilon]\approx\sigma\sqrt{2\ln|A|}` — Atari's `|A|=18` gives `\sqrt{2\ln18}\approx2.4`, so a per-action error scale of `\sigma=1` injects `+2.4` bias per backup even though the errors averaged to zero. The error recursion `e_{k+1}\le\gamma e_k+b` has fixed point `b/(1-\gamma)`, so at `\gamma=0.99` that `+2.4` becomes `+240`, on a value function whose entire legal range with `|r|\le1` is `\pm100`. Three amplifiers make reality worse: the policy is `\arg\max\hat{Q}`, so it selects the upper tail rather than sampling it; each preferred OOD action leads to states further from the data where extrapolation is worse; and no observation ever contradicts it. Online, all three are cut by the same fact — you execute the action and reality answers.
**Follow-up trap:** *"Double Q-learning fixes overestimation online. Why doesn't it fix it offline?"* Double/clipped double Q reduces the *maximisation bias* from using the same values to select and evaluate, which is a bias about which of several **estimated** values is largest. Offline, the problem is not that the estimate is noisy — it is that at an OOD action there is *no estimate*, only extrapolation, and two independently-trained networks extrapolate in a correlated way because they share architecture, data, and inductive bias. Twin critics with a min help at the margin (every algorithm in the module uses them) and do not touch the structural problem, which is missing support.

### Q4 — CQL, BCQ, IQL, TD3+BC. For each, say precisely what is being constrained and what it costs.
**Testing:** whether the taxonomy is understood as one idea in four places, or memorised as four names.
**Answer:** All four keep the policy inside the region where the critic was trained; they differ in where they intervene. **BCQ** constrains the *action set* fed to the max: a conditional VAE generates `n=10` candidate actions, a perturbation network moves each by at most `\Phi=0.05`, and the max is over those `10` only — cost is that a mode-collapsed VAE silently restricts the policy class, and `\Phi` is untunable offline. **CQL** constrains the *Q-values*: add `\alpha(\mathbb{E}_{a\sim\mu}[Q]-\mathbb{E}_{a\sim\mathcal{D}}[Q])` to the loss, with `\mu` chosen adversarially so the term becomes `\log\sum_a\exp Q`, yielding a provable lower bound on `Q^\pi` — cost is that `\alpha` (typically `0.5`-`10`, `5.0` for locomotion, `10.0` for AntMaze) sits between "collapses to BC" and "diverges," plus `2`-`4×` the per-step compute for the sampled actions. **TD3+BC** constrains the *policy*: add `-(\pi(s)-a)^2` to the actor loss with weight `\lambda=\alpha/\overline{|Q|}` and `\alpha=2.5` — cost is that it is a distribution match rather than a support match, so it cannot deviate when it should, and it averages multimodal behaviour into the middle. **IQL** constrains nothing because it never queries an OOD action: expectile regression at `\tau=0.7` (locomotion) or `0.9` (AntMaze) fits `V` to the in-sample max of `Q`, `Q` backs up `r+\gamma V(s')` with no max anywhere, and the policy is extracted by advantage-weighted BC — cost is that improvement is bounded by what in-support stitching allows.
**Follow-up trap:** *"Which would you reach for first, and why not CQL given it's the most cited?"* IQL or TD3+BC, because both shipped hyperparameters that transferred across all of D4RL unchanged, whereas CQL's `\alpha` needs per-dataset tuning against a return signal you do not have offline. That is not a small point — it is the practical difference between a method you can deploy and a method you can publish.

### Q5 — Walk me through expectile regression. Why does a high `\tau` approximate a maximum, and what does IQL's version get wrong?
**Testing:** depth on the one genuinely non-obvious piece of machinery in modern offline RL.
**Answer:** The `\tau`-expectile minimises `\mathbb{E}[L_2^\tau(x-m)]` with `L_2^\tau(u)=|\tau-\mathbf{1}(u<0)|u^2`, an asymmetric squared error weighting positive residuals `\tau` and negative ones `1-\tau`. At `\tau=0.5` the weights are equal and you recover the mean; at `\tau=0.9` the asymmetry is `9:1`, so undershooting is punished nine times harder than overshooting and the minimiser is dragged toward the top of the distribution; as `\tau\to1` it converges to the maximum. IQL applies this with `x=Q(s,a)` for `a` drawn from the dataset at `s`, so a high `\tau` gives `\approx\max_{a\in\mathrm{supp}(\pi_\beta)}Q(s,a)` — the in-sample max — using only actions that actually appear. That is the whole trick: you get the maximisation that policy improvement needs without ever evaluating an action nobody took.
**Follow-up trap:** *"What does the expectile take the max over, exactly?"* Over the joint randomness of action *and* dynamics, which is the known flaw. `Q(s,a)` varies across dataset samples both because different actions were taken and because the same action landed in different next states. A high `\tau` is therefore optimistic about **lucky transitions** too, not just about good actions — in a genuinely stochastic environment IQL's `V` inherits a bias that has nothing to do with policy improvement, and it is the same structural error as Decision Transformer conditioning on a high realised return. IQL's paper mitigates by integrating over dynamics in the Q-backup rather than the V-fit, which reduces but does not remove it.

### Q6 — Behaviour cloning is a supervised baseline with no reward signal at all. Why would it ever beat CQL or IQL?
**Testing:** whether you have the intellectual honesty the whole field had to learn the hard way.
**Answer:** Four reasons, all concrete. First, no bootstrapping means the deadly triad is structurally absent, so BC cannot diverge — the loss you watch is the loss you get. Second, and most under-appreciated, BC is the only method here whose hyperparameters you can tune honestly offline: held-out negative log-likelihood is a real validation metric on the same distribution, whereas `\alpha`, `\Phi`, `\tau`, and `\beta` all need a *return* signal that offline data cannot give you and OPE cannot reliably supply. Third, on near-expert data BC is optimal by construction — the best policy in the data is the data. Fourth, `10\%`BC (sort trajectories by return, clone the top decile) is a one-line upgrade that beats CQL on several D4RL locomotion datasets. Emmons et al.'s RvS showed a plain conditional-BC MLP with the right width and dropout matching CQL and IQL across most D4RL gym tasks, which strongly suggests some published offline RL gains were tuning and capacity rather than algorithm.
**Follow-up trap:** *"Then when is offline RL actually worth the complexity?"* Kumar et al. (2022) give the conditions: highly suboptimal or noisy data, sparse reward requiring the stitching of sub-trajectories, and — the counterintuitive one — long horizons with high initial-state variability *even with expert demonstrations*, because BC's `O(T^2\epsilon)` compounding grows faster than the value-based error there. The canonical demonstration is AntMaze: BC `\approx0`, IQL `378`. Outside those conditions, the measured gap is often smaller than the seed variance, and CORL's uniform-protocol reproduction showed published numbers moving by several normalised points in both directions.

### Q7 — Derive why importance-sampling OPE breaks down as the horizon grows. Be quantitative.
**Testing:** whether you understand that OPE is the hard part, with the arithmetic to prove it.
**Answer:** `\hat{V}_{\text{IS}}=\frac{1}{n}\sum_i(\prod_{t=0}^{H-1}\rho_t^i)G_i` with `\rho_t=\pi(a_t|s_t)/\pi_\beta(a_t|s_t)`. Take the simplest non-trivial case: binary actions, `\pi_\beta` uniform, `\pi` deterministic. Then `\rho_t\in\{0,2\}`, a trajectory survives only if `\pi` agrees at every step (probability `2^{-H}`), and its weight is `2^H`. At `H=10` that is a weight of `1024` and about `10` surviving trajectories out of `10^4`; at `H=20`, a weight of `1.05\times10^6` and one survivor in `10^6`; at `H=100`, `2^{100}\approx1.27\times10^{30}` and there is no dataset large enough. Variance scales as `2^H/n`, and Jiang & Li's lower bounds show this is information-theoretic in the general case, not an artifact of a naive estimator.
**Follow-up trap:** *"You shipped contextual bandits in production with importance-weighted evaluation and it worked. Why?"* Because `H=1`. The weight is `1/\pi_\beta(a|x)` rather than a product of `100` such terms, so a logger with a `1\%` probability floor gives weights bounded by `100` and the variance is `O(1/\pi_{\min})`, not `O(2^H)`. That is the entire reason bandit off-policy evaluation is mature production technology and full-horizon OPE is not — and it is also the argument for modelling a business problem as a bandit whenever the credit assignment genuinely is one-step, rather than importing an RL framing and its evaluation problem for free.

### Q8 — I have `50{,}000` logged trajectories and my WIS estimate says the new policy is `30\%` better. What do you check before believing it?
**Testing:** production judgement; the single most useful diagnostic habit in the topic.
**Answer:** Effective sample size, `\mathrm{ESS}=(\sum_iw_i)^2/\sum_iw_i^2`, and the maximum weight share `\max_iw_i/\sum_iw_i`. With `50{,}000` trajectories and `\mathrm{ESS}=3`, the estimate is a weighted average of three episodes; the bootstrap interval around it is a fiction, because the bootstrap resamples those same three dominant trajectories. My gates: refuse to act below `\mathrm{ESS}=100`; treat `\mathrm{ESS}/n<0.01` as "the target policy is outside the log's support, stop and get exploration data"; and block if any single trajectory holds more than `10\%` of total weight. I would also require agreement between WIS, doubly-robust, and FQE — three estimators with different failure modes agreeing is weak evidence, and any two disagreeing is a hard stop.
**Follow-up trap:** *"WIS is biased. Shouldn't you prefer the unbiased ordinary IS estimate?"* No. Ordinary IS is unbiased with variance up to `2^H`, and an unbiased estimator whose variance is `10^{30}` is worse than useless — any finite sample of it is confidently wrong in an unpredictable direction. WIS self-normalises, so the estimate is a convex combination of observed returns and is bounded by `[\min_iG_i,\max_iG_i]`; its bias vanishes at `O(1/n)`. Unbiasedness is a property of an estimator averaged over datasets you will never collect; you have one dataset.

### Q9 — Explain doubly robust OPE. What does "doubly" buy you, and when is it worse than plain weighted IS?
**Testing:** whether you can state a guarantee and its failure case, not just the name.
**Answer:** DR uses a learned model as a control variate inside the IS recursion: `\hat{V}^{(t)}_{\text{DR}}=\hat{V}(s_t)+\rho_t(r_t+\gamma\hat{V}^{(t+1)}_{\text{DR}}-\hat{Q}(s_t,a_t))`. It is unbiased if *either* the model `\hat{Q}` is correct *or* the behaviour probabilities `\pi_\beta` are correct — two chances, hence "doubly robust." The variance win is mechanical: the large weight `\rho_t` now multiplies a **residual** rather than a raw return, and if the model is roughly right that residual is near zero, giving one to two orders of magnitude variance reduction over per-decision IS.
**Follow-up trap:** *"So DR strictly dominates WIS?"* No. Where the model is bad, DR is *worse* than WIS, because it multiplies unbounded importance weights by a large residual and, unlike WIS, has no self-normalisation to bound the result — you get IS's variance back with an extra bias term on top. That is exactly why MAGIC (Thomas & Brunskill, 2016) blends the `j`-step partial-DR estimators with weights chosen to minimise an *estimated* MSE, trading a clean guarantee for empirical robustness and introducing its own model-selection error. In practice I report WIS and DR side by side; their disagreement is a better signal than either number.

### Q10 — FQE is the standard offline evaluator and it uses no importance weights. Why isn't that the answer to everything?
**Testing:** the deepest structural point in the module; strong candidates get here on their own.
**Answer:** FQE iterates `\hat{Q}_{k+1}=\arg\min_Q\mathbb{E}_\mathcal{D}[(Q(s,a)-(r+\gamma\hat{Q}_k(s',\pi(s'))))^2]` and reports `\mathbb{E}_{s_0}[\hat{Q}(s_0,\pi(s_0))]`. Variance is low because it is regression. But `\hat{Q}_k(s',\pi(s'))` evaluates the network at the **target policy's** actions at `s'` — precisely the out-of-distribution actions the entire module says are untrustworthy. So FQE inherits exactly the extrapolation error it is supposed to be measuring, and worse, the errors are *correlated* with the learner's: learner and evaluator share the data distribution, usually the architecture, and therefore the direction of extrapolation. Your evaluator is optimistic about the same phantom actions your policy learned to prefer. In the DOPE benchmark (Fu et al., 2021), FQE was among the better estimators on average, no method dominated across task families, and rank correlation with true return was well short of perfect — meaning OPE regularly gets the *ordering* of candidates wrong, which was the only thing you needed it for.
**Follow-up trap:** *"Given that, how do you actually select a policy offline?"* You do not, as a final decision. The defensible architecture is: offline RL to produce a shortlist of `3`-`5` candidates, OPE (WIS + DR + FQE with ESS reported) purely as a **filter** that eliminates broken candidates, and a guarded online test on `1`-`5\%` of traffic with automatic rollback to make the choice. Gottesman et al.'s Nature Medicine 2019 guidelines reach the same conclusion for clinical RL: OPE is for rejecting policies, not for certifying them. If no online test is possible at all, the correct answer is that you should not ship a learned policy.

### Q11 — Derive behaviour cloning's `O(T^2\epsilon)` bound and explain how DAgger gets to `O(T\epsilon)`.
**Testing:** covariate shift understood as a mechanism with a rate, not a slogan.
**Answer:** BC minimises action error under the *expert's* state distribution `d^{\pi^*}` but is deployed under its own `d^{\hat\pi}`. If the per-state error is `\epsilon`, then at each of `T` steps you have probability up to `\epsilon` of a wrong action; a wrong action puts you off the expert's distribution, where you have no guarantee at all and can forfeit the remaining up-to-`T` steps of reward. So `T` opportunities `\times\ \epsilon\ \times\ T` remaining cost `=O(T^2\epsilon)` (Ross, Gordon & Bagnell, 2011). Concretely, `\epsilon=0.01` over a `T=1000`-step driving episode bounds the regret at `10^4` per-step-cost units instead of `10^2` — that factor of `T` is why a `99\%`-accurate driving policy leaves the road. DAgger closes the gap by making the training distribution match the deployment distribution: roll out the **learner** to collect states, query the **expert** for the correct action at those states, aggregate into the dataset (never discard), and retrain on everything. It is formally a reduction to no-regret online learning, giving `O(T\epsilon)` — linear, and optimal.
**Follow-up trap:** *"Great, use DAgger then."* DAgger requires an interactive expert queryable at arbitrary states the learner reaches. Logged clinical decisions, historical trades, and recommender impressions are not experts you can ask new questions of — that absence is precisely why offline RL exists as a field. Two further costs: DAgger's early iterations deliberately drive the system with a bad policy to generate informative states, unacceptable in safety-critical deployment (hence HG-DAgger and EnsembleDAgger handing control back on ensemble disagreement), and expert labelling cost is linear in states visited. When there is no interactive expert, you manufacture the covariate shift instead: PilotNet's left/right cameras labelled with corrected steering (Bojarski et al., 2016) synthesise recovery data from off-distribution states, and DART injects noise into the expert during collection so the demonstrations themselves cover the neighbourhood of the expert trajectory.

### Q12 — What is the identifiability problem in inverse RL? Name the distinct sources.
**Testing:** whether "IRL is ill-posed" is a memorised phrase or a decomposable fact.
**Answer:** Four separable sources. (1) **Degenerate rewards** — `R\equiv0` (and any constant) makes every policy optimal, so it satisfies the constraints for any demonstration set; Ng & Russell noted this in 2000 as they introduced the linear-constraint formulation. (2) **Potential-based shaping** — by Ng, Harada & Russell (1999), `R'=R+\gamma\Phi(s')-\Phi(s)` preserves the optimal policy for *every* `\Phi`, so the reward is recoverable at best up to an infinite-dimensional equivalence class plus positive affine scaling; Cao, Cohen & Szpruch (2021) characterise these classes exactly. (3) **Support** — demonstrations constrain `R` only where the demonstrator went; off-support the reward is free, which is this module's distribution-shift problem relocated into reward space. (4) **Reward-dynamics entanglement** — a reward fitted in environment `M` can encode facts about `M`'s dynamics rather than the agent's preferences and therefore fails to transfer to `M'`, which is the problem AIRL (2017) exists to attack. MaxEnt IRL (Ziebart et al., 2008) removes ambiguity (1) by picking the maximum-entropy trajectory distribution matching demonstrated feature expectations, giving `p(\tau)\propto\exp(\sum_tR_\theta)` — a unique solution purchased with an assumption, namely that the demonstrator is Boltzmann-rational rather than optimal.
**Follow-up trap:** *"Where does this bite you in 2026, if you never write an IRL algorithm?"* RLHF. A reward model trained from pairwise preferences under Bradley-Terry is an IRL-adjacent object and inherits all four problems: identifiable only up to a monotone transform on the comparison distribution, unconstrained off the support of the preference data, and entangled with the setting it was collected in. **Reward hacking is the policy exploiting the region where the reward model was never constrained by data** — structurally the identical failure to `\max_{a'}\hat{Q}(s',a')` at an unseen action, with a reward model substituted for a critic. Which is why the fix is also identical: the explicit KL penalty to the reference policy in RLHF is a policy constraint, the same object as TD3+BC's behaviour-cloning term.

### Q13 — Design an offline RL system for a production recommender with five years of logs from a deployed ranker. Walk me through it.
**Testing:** staff-level judgement — whether you can say "this will not work as posed" and redirect.
**Answer:** First I would establish whether the problem is real RL. If reward is a click on the recommended item with no meaningful downstream effect, this is contextual bandits at `H=1`, importance weighting works with bounded weights, and I would not import full-horizon RL. Assume it is genuinely sequential (session-level engagement, multi-step funnels). Then: (a) **Audit coverage before anything else** — compute per-context action entropy under the deployed ranker and the ESS of a proposed target policy against the log. A deployed near-deterministic ranker gives essentially no action diversity per context, so `C` is effectively infinite and five years of logs have roughly the coverage of five weeks. (b) **Check for propensity logging.** If `\pi_\beta(a|s)` was not recorded at decision time, every IS-family estimator is unavailable and cannot be retrofitted; adding it is a one-line change in the serving path and the highest-value thing I can ask for. (c) **Negotiate a `1`-`5\%` randomised exploration slice.** This changes the problem; a better algorithm does not. (d) **Baselines first**: BC and `10\%`BC on the logs, evaluated the same way as anything fancier. (e) **Then IQL or TD3+BC**, not CQL, because their hyperparameters transfer. (f) **Evaluation**: WIS + DR + FQE with ESS reported, used only to shortlist. (g) **Ship** the shortlist into a guarded `1\%` A/B with automatic rollback on guardrails, and a runtime out-of-support detector that falls back to the incumbent ranker.
**Follow-up trap:** *"The exploration slice costs revenue and product will refuse. What now?"* Then I would say plainly that offline RL is not fundable here and I would not spend a quarter on it, because with no coverage and no online test there is no evidence standard I can meet — the OPE interval will span "clearly better" to "clearly harmful" and the decision will end up being made on vibes with a model attached. The alternative that does work: keep the incumbent ranker, add a small bandit layer on a decision that genuinely is one-step, and log propensities so that in twelve months the sequential question becomes answerable. Being able to decline the project for a stated reason is more senior than delivering a policy nobody can validate.

### Q14 — Your offline agent's D4RL numbers look great but it underperforms on your company's logs. What is going on?
**Testing:** benchmark scepticism; the NeoRL critique is the kind of thing that separates readers from practitioners.
**Answer:** Benchmark mismatch in the *behaviour policy*, not the task. D4RL's datasets are generated by deliberately diverse sources — random policies, partially-trained policies, mixtures of medium and expert, replay buffers — which gives them far broader action coverage than any deployed system produces. A production logger is a single near-deterministic policy, so your `C` is orders of magnitude larger than the benchmark's, and the methods that win in that regime are different. NeoRL (Qin et al., 2021) constructed near-real-world datasets with narrow, conservative behaviour policies and found that the D4RL ranking does not transfer and that BC-like and heavily-constrained methods move up. Practical consequence: re-rank candidate algorithms on a held-out slice of your own log rather than trusting any published table, and expect the ordering to change.
**Follow-up trap:** *"But CQL reports `2`-`5×` higher returns than prior methods — surely that survives?"* That figure is from the settings CQL was designed for: complex, multimodal, suboptimal data. On near-expert or narrow data the gap shrinks to nothing or inverts, and CORL's uniform-protocol reproductions moved published D4RL numbers by several normalised points in both directions, which is the same order as the gaps being claimed. Treat any single-paper delta smaller than the seed spread as unproven until you have run `\ge5` seeds on your own data.

### Q15 — When would you deliberately choose *not* to use offline RL, and what would you build instead?
**Testing:** the senior signal; every technology has a wrong context and this one has several large ones.
**Answer:** Five cases with the substitute named. (1) **Horizon is `1`** — use contextual bandits; the importance weight is `1/\pi_\beta` rather than a product of `100` of them, evaluation actually works, and the operational story is mature. (2) **Data is near-expert** — use BC or `10\%`BC; no algorithm beats BC on expert data and you will spend weeks tuning `\alpha` to reproduce the demonstrations. (3) **Logger is narrow and near-deterministic** — nothing works; spend the effort acquiring a randomised traffic slice, because `C` is a property of support and no algorithm reduces it. (4) **No online test is possible and the decision is consequential** — ship a constrained or rule-based policy whose worst case is bounded by construction, and use offline RL only to generate hypotheses; the OPE evidence standard cannot be met. (5) **The gain over `10\%`BC is within seed variance** — the offline RL system carries a policy, a critic, an OPE stack, a propensity dependency in the serving path, a support-detection fallback, and hyperparameters you cannot validate offline; that surface area needs a large win, not a marginal one.
**Follow-up trap:** *"Isn't that just an argument against RL in general?"* No, it is an argument for matching the method to the evaluation you can actually run. Offline RL is genuinely the right tool in three places: when data is broad but suboptimal and the reward is sparse enough that stitching is required (AntMaze-shaped problems, and real robotics datasets that look like it), when offline pretraining precedes permitted online finetuning — which is the dominant real deployment pattern and the reason Cal-QL exists — and when the alternative is no learned policy at all in a domain where the incumbent is provably poor. What I am arguing against is running offline RL in the fourth case, which is where most people encounter it: narrow logs, no exploration budget, no online test, and a leaderboard delta mistaken for a business case.

---

## Red flags that fail you

- Saying "DQN is off-policy so it works on logged data." This is the screening question and this answer ends the interview.
- Describing offline RL's problem as "the policy sees states it hasn't seen at deployment" and stopping there. That is deployment-time state shift; the killer is *training-time action shift inside the Bellman target*, and conflating them means you have not understood the mechanism.
- Claiming more data fixes it. The binding constraint is the support of `\pi_\beta`, not `N`; Fujimoto's full-replay-buffer experiment settles this.
- Reciting CQL's objective without being able to say what `\alpha` too large does (collapses to behaviour cloning) and what `\alpha` too small does (diverges), or without admitting you have no offline signal to tune it against.
- Treating behaviour cloning as a strawman. Not knowing about `10\%`BC, or presenting offline RL results without a BC baseline, reads as never having run these methods.
- Saying "we'll validate with off-policy evaluation" as if that closes the loop, with no mention of effective sample size, horizon-exponential variance, or the fact that FQE bootstraps off the same OOD actions it is meant to audit.
- Preferring ordinary IS to WIS because "it's unbiased," without noting that its variance can be `2^{100}`.
- Not knowing that behaviour cloning's error compounds as `O(T^2\epsilon)` and that DAgger's contribution is reducing it to `O(T\epsilon)` — or proposing DAgger in a setting with no interactive expert.
- Saying inverse RL "recovers the reward function" without naming the identifiability problem, or naming it without being able to give at least potential-based shaping as a concrete source.
- Missing that RLHF's KL-to-reference penalty and TD3+BC's behaviour-cloning term are the same mechanism, and that reward hacking is OOD extrapolation of a learned reward.
- Quoting D4RL leaderboard deltas of `2`-`5` normalised points as meaningful without mentioning seed variance or reproduction discrepancies.

## Cheat card

```
OFFLINE vs OFF-POLICY  DQN's buffer is refilled by NEARBY policies and reality
  CONTRADICTS overestimates -> self-correcting. Offline: pi_beta FROZEN, pi
  drifts unboundedly over 1e6 steps, NOTHING ever contradicts. That is all.
THE KILLER  target = r + gamma*max_{a'} Qhat(s',a').  a' ranges over actions
  pi_beta NEVER took -> pure extrapolation, and max() SELECTS the largest error.
  bias/backup b ~ sigma*sqrt(2 ln|A|)  (|A|=18 -> 2.4x sigma)
  fixed point  b/(1-gamma) = 100b @ .99, 1000b @ .999.  Policy = argmax Qhat
  -> ADVERSARIAL selection of the error, not random.
SYMPTOM  mean(Q) climbs to 1e5..1e9 while loss_q STAYS SMALL (pred+target
  inflate together). Log mean(Q), max(Q), mean(Q)*(1-gamma)/R_max (~1 is sane).
DEADLY TRIAD  fn-approx + bootstrapping + off-policy. Offline = worst corner.
  Kill BOOTSTRAPPING -> BC / DT cannot diverge. Kill ITERATION -> one-step RL
  gets b not b/(1-gamma). Bootstrapping's payoff = STITCHING (AntMaze).
COVERAGE  C = max d^pi(s,a)/d^pi_beta(s,a); bound ~ 2*gamma*C*eps/(1-gamma)^2.
  C=inf if pi acts where pi_beta had ZERO prob. MORE ROWS DO NOT REDUCE C.
  Fujimoto 2018: full replay buffer of a SUCCESSFUL DDPG -> offline DDPG fails.
BCQ    constrain ACTION SET: VAE gen n=10 cands, perturb <= Phi=0.05,
       twin-Q soft-min lambda=0.75. Cost: VAE mode collapse, Phi untunable.
CQL    constrain Q-VALUES: + alpha(E_mu[Q] - E_D[Q]); adversarial mu -> logsumexp.
       Provable LOWER BOUND on Q^pi. alpha 0.5-10 (5 locomotion / 10 antmaze).
       TOO BIG -> collapses to BC.  TOO SMALL -> diverges.  2-4x slower.
TD3+BC constrain POLICY: max lambda*Q(s,pi(s)) - (pi(s)-a)^2, lambda=alpha/mean|Q|,
       alpha=2.5 + state normalisation. lambda's /mean|Q| = scale-free, one
       alpha for ALL of D4RL. Cost: distribution (not support) match; averages
       multimodal behaviour into the middle. >2x faster than prior methods.
IQL    NEVER queries an OOD action. Expectile L2^tau(u)=|tau-1(u<0)|u^2,
       tau=0.5 mean, tau=0.9 -> 9:1 asymmetry -> IN-SAMPLE max.
       V <- expectile(Q(s,a_data)); Q <- r + gamma*V(s'); pi <- AWR exp(beta*A).
       tau .7/beta 3 locomotion; tau .9/beta 10 antmaze; clip exp at 100;
       2x256 MLP, Adam 3e-4, batch 256, polyak .005, 1e6 steps.
       Flaw: expectile is over ACTION *and* DYNAMICS -> optimistic about LUCK.
BC IS A REAL BASELINE  no bootstrap -> no triad; the ONLY method whose
  hyperparams tune honestly offline (held-out NLL). 10%BC (top decile by
  return) beats CQL on several D4RL sets. Expert data -> nothing beats BC.
  D4RL -v2: halfcheetah-med BC 42.6 / CQL 44.0 / TD3+BC 48.3 / IQL 47.4
            hopper-med     BC 52.9 / CQL 58.5 / TD3+BC 59.3 / IQL 66.3
  AntMaze total (-v0):     BC ~0   / CQL 303.6 / one-step 125.3 / IQL 378.0
OFFLINE RL WINS WHEN  suboptimal+broad data, SPARSE reward needing STITCHING,
  or long horizon + high initial-state variability (BC's T^2 bites).
OPE IS THE HARD PART  IS weight = PRODUCT_t pi/pi_beta. Binary acts, uniform
  logger, deterministic pi: weight 2^H w.p. 2^-H. H=20 -> 1.05e6 (1 survivor
  in 1e6). H=100 -> 1.27e30. EXPONENTIAL, information-theoretic.
  H=1 (bandits) -> weight 1/pi_beta, BOUNDED. That's why bandit OPE ships.
  PDIS   reward_t needs product only up to t -> exponent ~ 1/(1-gamma)=100
  WIS    self-normalise -> convex combo of returns, BOUNDED, bias O(1/n).
         Default over ordinary IS. Unbiased@var 1e30 is worse than useless.
  ESS    (sum w)^2 / sum w^2.  n=50k, ESS=3 -> you estimated 3 episodes.
         GATES: ESS>=100, ESS/n>=0.01, max_w share < 10%.
  DR     Vhat(s) + rho*(r + gamma*V_DR' - Qhat). Unbiased if EITHER model OR
         propensities correct. Weight hits a RESIDUAL -> 10-100x var cut.
         WORSE than WIS when the model is bad (unbounded w * big residual).
  FQE    no weights, low var -- but bootstraps off pi's OOD actions, i.e. it
         INHERITS THE ERROR IT MEASURES, correlated with the learner's.
  VERDICT  use OPE to REJECT, never to certify (Gottesman, Nat Med 2019).
BC -> DAgger  BC regret O(T^2 eps): T chances * eps * T remaining cost.
  eps=.01, T=1000 -> 1e4 vs 1e2. DAgger: roll out LEARNER, label with EXPERT,
  AGGREGATE, retrain on ALL -> no-regret -> O(T eps). NEEDS INTERACTIVE EXPERT
  (which is why offline RL exists). No expert -> PilotNet shifted cameras,
  DART noise injection.
IRL UNIDENTIFIABLE  (1) R=0 explains everything (Ng&Russell 2000)
  (2) potential shaping R+gamma*Phi(s')-Phi(s) preserves pi* for ANY Phi
  (3) constrained only on demo SUPPORT  (4) entangled with dynamics (AIRL).
  MaxEnt (Ziebart 2008) p(tau) ~ exp(sum R) -> unique, buys it with the
  Boltzmann-rationality ASSUMPTION. GAIL matches occupancy, recovers NO reward.
  RLHF reward model = same object; REWARD HACKING = OOD extrapolation of R.
  RLHF's KL-to-ref == TD3+BC's BC term. Same mechanism, different noun.
WHEN NOT TO  H=1 (use bandits) | expert data (use 10%BC) | narrow deterministic
  logger (buy 1-5% randomised traffic, no algorithm fixes support) | no online
  test possible (ship a bounded-worst-case policy) | gain < seed variance.
FIRST MOVES  log propensities at decision time (cannot retrofit); run BC and
  10%BC; try IQL/TD3+BC before CQL; report ESS with every OPE number.
```

## Sources

- [Levine, Kumar, Tucker & Fu — Offline Reinforcement Learning: Tutorial, Review, and Perspectives on Open Problems (2020)](https://arxiv.org/abs/2005.01643) — accessed 2026-08-05
- [Fujimoto, Meger & Precup — Off-Policy Deep Reinforcement Learning without Exploration (BCQ, 2018/ICML 2019)](https://arxiv.org/abs/1812.02900) — accessed 2026-08-05
- [Kumar, Zhou, Tucker & Levine — Conservative Q-Learning for Offline Reinforcement Learning (CQL, NeurIPS 2020)](https://arxiv.org/abs/2006.04779) — accessed 2026-08-05
- [Kostrikov, Nair & Levine — Offline Reinforcement Learning with Implicit Q-Learning (IQL, 2021)](https://arxiv.org/abs/2110.06169) — accessed 2026-08-05
- [Fujimoto & Gu — A Minimalist Approach to Offline Reinforcement Learning (TD3+BC, NeurIPS 2021)](https://arxiv.org/abs/2106.06860) — accessed 2026-08-05
- [Kumar, Hong, Singh & Levine — When Should We Prefer Offline Reinforcement Learning Over Behavioral Cloning? (2022)](https://arxiv.org/abs/2204.05618) — accessed 2026-08-05
- [BAIR Blog — Should I Use Offline RL or Imitation Learning? (2022)](https://bair.berkeley.edu/blog/2022/04/25/rl-or-bc/) — accessed 2026-08-05
- [Fu, Kumar, Nachum, Tucker & Levine — D4RL: Datasets for Deep Data-Driven Reinforcement Learning (2020)](https://arxiv.org/abs/2004.07219) — accessed 2026-08-05
- [Farama Foundation — Minari, the maintained successor to D4RL](https://minari.farama.org/datasets/D4RL/index.html) — accessed 2026-08-05
- [Gulcehre et al. — RL Unplugged: A Suite of Benchmarks for Offline Reinforcement Learning (2020)](https://arxiv.org/abs/2006.13888) — accessed 2026-08-05
- [Qin et al. — NeoRL: A Near Real-World Benchmark for Offline Reinforcement Learning (2021)](https://arxiv.org/abs/2102.00714) — accessed 2026-08-05
- [Tarasov et al. — CORL: Research-oriented Deep Offline RL Library (2022)](https://arxiv.org/abs/2210.07105) — accessed 2026-08-05
- [Kumar, Fu, Tucker & Levine — Stabilizing Off-Policy Q-Learning via Bootstrapping Error Reduction (BEAR, 2019)](https://arxiv.org/abs/1906.00949) — accessed 2026-08-05
- [Wu, Tucker & Nachum — Behavior Regularized Offline Reinforcement Learning (BRAC, 2019)](https://arxiv.org/abs/1911.11361) — accessed 2026-08-05
- [Brandfonbrener et al. — Offline RL Without Off-Policy Evaluation (one-step RL, 2021)](https://arxiv.org/abs/2106.08909) — accessed 2026-08-05
- [Emmons, Eysenbach, Kostrikov & Levine — RvS: What is Essential for Offline RL via Supervised Learning? (2021)](https://arxiv.org/abs/2112.10751) — accessed 2026-08-05
- [Chen et al. — Decision Transformer: Reinforcement Learning via Sequence Modeling (2021)](https://arxiv.org/abs/2106.01345) — accessed 2026-08-05
- [Yu et al. — MOPO: Model-based Offline Policy Optimization (2020)](https://arxiv.org/abs/2005.13239) — accessed 2026-08-05
- [Nakamoto et al. — Cal-QL: Calibrated Offline RL Pre-Training for Efficient Online Fine-Tuning (2023)](https://arxiv.org/abs/2303.05479) — accessed 2026-08-05
- [van Hasselt et al. — Deep Reinforcement Learning and the Deadly Triad (2018)](https://arxiv.org/abs/1812.02648) — accessed 2026-08-05
- [Precup, Sutton & Singh — Eligibility Traces for Off-Policy Policy Evaluation (2000)](https://scholarworks.umass.edu/cs_faculty_pubs/80/) — accessed 2026-08-05
- [Jiang & Li — Doubly Robust Off-policy Value Evaluation for Reinforcement Learning (2015/ICML 2016)](https://arxiv.org/abs/1511.03722) — accessed 2026-08-05
- [Thomas & Brunskill — Data-Efficient Off-Policy Policy Evaluation for Reinforcement Learning (MAGIC, ICML 2016)](https://arxiv.org/abs/1604.00923) — accessed 2026-08-05
- [Le, Voloshin & Yue — Batch Policy Learning under Constraints (FQE, ICML 2019)](https://arxiv.org/abs/1903.08738) — accessed 2026-08-05
- [Fu et al. — Benchmarks for Deep Off-Policy Evaluation (DOPE, ICLR 2021)](https://arxiv.org/abs/2103.16596) — accessed 2026-08-05
- [Nachum et al. — DualDICE: Behavior-Agnostic Estimation of Discounted Stationary Distribution Corrections (2019)](https://arxiv.org/abs/1906.04733) — accessed 2026-08-05
- [Gottesman et al. — Guidelines for reinforcement learning in healthcare, Nature Medicine (2019)](https://www.nature.com/articles/s41591-018-0310-5) — accessed 2026-08-05
- [Ross, Gordon & Bagnell — A Reduction of Imitation Learning and Structured Prediction to No-Regret Online Learning (DAgger, AISTATS 2011)](https://arxiv.org/abs/1011.0686) — accessed 2026-08-05
- [Bojarski et al. — End to End Learning for Self-Driving Cars (PilotNet, 2016)](https://arxiv.org/abs/1604.07316) — accessed 2026-08-05
- [Ng & Russell — Algorithms for Inverse Reinforcement Learning (ICML 2000)](https://ai.stanford.edu/~ang/papers/icml00-irl.pdf) — accessed 2026-08-05
- [Ziebart, Maas, Bagnell & Dey — Maximum Entropy Inverse Reinforcement Learning (AAAI 2008)](https://cdn.aaai.org/AAAI/2008/AAAI08-227.pdf) — accessed 2026-08-05
- [Ho & Ermon — Generative Adversarial Imitation Learning (GAIL, 2016)](https://arxiv.org/abs/1606.03476) — accessed 2026-08-05
- [Fu, Luo & Levine — Learning Robust Rewards with Adversarial Inverse RL (AIRL, 2017)](https://arxiv.org/abs/1710.11248) — accessed 2026-08-05
- [Cao, Cohen & Szpruch — Identifiability in inverse reinforcement learning (NeurIPS 2021)](https://arxiv.org/abs/2106.03498) — accessed 2026-08-05
- [d3rlpy — offline deep RL library with an OPE (FQE) module](https://d3rlpy.readthedocs.io/) — accessed 2026-08-05

## Changelog
- 2026-08-05 — created

