# World Models: What They Are, Why They Matter, the Core Idea

> **Track:** T26 Frontier AI · **Time:** 2.5h · **Prereqs:** `T31-model-based`, `T31-mdp`, T05 · **Updated:** 2026-08-05
> **Module id:** `T26-world-models` · **Tags:** world-models, model-based-rl, survey, critical

## The 30-second version

A world model is a learned simulator: a model that, given a state and an action, predicts the next state, and can be rolled forward without touching the real environment. The entire argument for building one reduces to two things, and you should say both: **sample efficiency** (one real trajectory can be amortised into thousands of imagined gradient updates, which is why PlaNet solved DeepMind Control tasks in roughly 2,000 episodes where D4PG needed about 50x to 500x more) and **counterfactual policy evaluation** (you can score a policy inside the model before it ever touches a robot, a market, or a customer). Ha and Schmidhuber's 2018 *World Models* is the clean origin: a 4.35M-parameter VAE compresses frames to a 32-dimensional latent, a 422K-parameter MDN-RNN predicts the next latent, and an **867-parameter** linear controller is trained by CMA-ES entirely inside the dream, then transferred back to the real VizDoom environment where it scores about 1,100 timesteps against a 750 solve threshold. The line from PlaNet (2019) through Dreamer, DreamerV2 and DreamerV3 (Nature, 2025, one configuration across 150+ tasks, first system to mine diamonds in Minecraft from scratch) is a sequence of fixes to that recipe, and every one of those fixes is about the same enemy: **compounding error over the rollout horizon**, which at a 2% per-step divergence rate leaves only 36% of 50-step rollouts faithful and 0.6% of 250-step rollouts, and is the reason nobody plans 1,000 steps deep. The 2025-2026 claim that video-generation models are becoming world models is the live disagreement, and the honest position is that visual plausibility is not physical consistency: ByteDance's ICML 2025 study found in-distribution velocity error of 0.012 against 0.427 out-of-distribution on the same model, a 35x gap that did **not** close with more data or more parameters.

## Why this gets asked

Because "world model" is currently the most abused phrase in AI marketing, and a frontier-lab interviewer wants to know within four minutes whether you can separate a paper with a benchmark from a demo video with a press release. Every serious lab now has a world-model team, every one of them has shipped a reel of generated worlds, and almost none of those reels come with a closed-loop task-success number. The interviewer has personally lived through the failure this module is about: a model-based agent that scored beautifully in imagination and then face-planted in the real environment, or a video model whose output looked photographic frame-by-frame and violated conservation of momentum on frame 40. They ask this to see whether you reach for the sample-efficiency argument (correct), the "it understands physics" argument (a red flag unless you can define the test), or the "it's basically Sora with a joystick" argument (a red flag in the other direction, because it misses that action-conditioning is the whole point). At principal level they also want to see you name the boundary: a world model is only useful if the horizon over which it stays accurate is longer than the horizon your decision actually needs, and most candidates have never framed it that way.

---

## Lineage: past → present → future

**What came before.** The pre-history is model-based control with hand-specified dynamics: system identification and Model Predictive Control in the 1980s and 1990s, where an engineer wrote down `x_{t+1} = f(x_t, u_t)` from physics and the controller optimised against it. That worked when you could write `f` down, and stopped working the moment the state was a camera image. The learned-model attempts that followed were bounded by two specific pains. **PILCO** (Deisenroth and Rasmussen, 2011) learned a Gaussian-process dynamics model with genuinely excellent sample efficiency (cart-pole swing-up in under 20 seconds of real interaction) but scaled cubically in the number of data points and could not ingest pixels at all, so it stayed a low-dimensional-state method. On the other side, model-free deep RL (`T31-dqn`, `T31-ppo`) could ingest pixels but at absurd sample cost: DQN needed 200M Atari frames, roughly 38 days of game time per game, and D4PG needed on the order of 10^8 environment steps on DeepMind Control tasks that a human solves in minutes. Meanwhile the video-prediction line (Oh et al. 2015 on Atari, Chiappa et al. 2017, Finn and Levine's action-conditioned video prediction, 2016-2017) built pixel-space predictors that produced strikingly good next-frame images and were then almost never used to actually replace the environment, because pixel-space rollouts blurred to mush within 10 to 20 frames and burned nearly all model capacity reconstructing texture, lighting and background that no controller ever needed. The specific pain that killed each: PILCO could not see, model-free RL could not afford the samples, and pixel-space predictors could not stay sharp long enough to plan inside. Ha and Schmidhuber's 2018 paper is the synthesis that resolved all three at once by moving prediction into a compressed latent space and then training the controller *inside* that latent simulator, and it is still the cleanest single artefact to explain in an interview.

**Where it stands now.** Two research programmes wear the same name and mean different things, and conflating them is the most common way to lose the room. Programme one is **latent-dynamics model-based RL**, the PlaNet → Dreamer → DreamerV3 line, which is scientifically settled in the sense that it works and is measured: DreamerV3 (Hafner et al., arXiv January 2023, published in *Nature* April 2025) beats specialised methods across 150+ tasks spanning DMC, Atari, ProcGen, Minecraft and robot control **with a single fixed hyperparameter configuration**, and was the first system to obtain diamonds in Minecraft from scratch with no human data and no curriculum. That is a benchmarked, reproducible, open-source result. Programme two is **generative video world models**, the Genie / Sora / Veo / Cosmos line, where a large video model is conditioned on actions and marketed as a simulator you could train agents in. Genie (Bruce et al., February 2024) is the honest early datapoint: 11B parameters, 30,000 hours of 2D platformer video, an unsupervised latent action model with a codebook of just **8 discrete actions**, evaluated with real metrics. Genie 3 (announced 5 August 2025) generates navigable 720p worlds at 24 fps holding consistency for "a few minutes", which is a genuine engineering achievement, but as of this writing there is **no technical report, no benchmark table, and no closed-loop agent-training result** attached to it, and its acknowledged limits (navigation-only action space, roughly one minute of usable memory, unreliable multi-agent interaction) are exactly the ones that matter for using it as an environment. The live disagreement is whether programme two subsumes programme one. LeCun's camp says no on principle, arguing generative pixel prediction wastes capacity on unpredictable detail and that joint-embedding prediction (V-JEPA 2: ViT-g scale, >1M hours of video, action-conditioned post-training on **under 62 hours** of unlabelled Droid robot video, then 65-80% zero-shot pick-and-place success on Franka arms in two labs it had never seen) is the right substrate. The scaling camp says video generation will get there. The ByteDance PhyWorld result (ICML 2025) is currently the strongest evidence for the sceptics and the single most useful citation you can carry into this interview.

**Where it's heading.** High confidence (call it 85%+): action-conditioned latent world models remain the standard substrate for sample-efficient control and robot learning, and the DreamerV3 "one config, many domains" result is not going to be un-discovered. High confidence: evaluation moves decisively from perceptual quality metrics (FVD, LPIPS) toward physics-and-controllability benchmarks; this already happened between 2024 and 2026 with PhyGenBench, VideoPhy, VideoPhy-2, WorldModelBench, WorldScore and PhyWorldBench, and the numbers are brutal enough (best model 22% joint semantic-plus-physical adherence on VideoPhy-2's hard subset; Sora-Turbo 20.8% and Kling-1.6 18.8% on PhyWorldBench) that the field cannot go back to publishing reels alone. Medium confidence (roughly 60%): hybrid architectures win, meaning a generative video prior for perceptual richness combined with an explicit, structured or physics-grounded state for the parts that must be exactly right, rather than either pure approach. Genuinely speculative, and you should label it that way out loud: whether a video model trained on enough internet video **spontaneously** acquires transferable physical law is unresolved, and the only careful controlled experiment on it so far (PhyWorld) says no, with the caveat that it tested a 2D synthetic setting with DiT models up to XL rather than a frontier-scale model on real video, so it constrains the claim without settling it. Equally speculative: whether world models become the training environment for general agents at scale. The demos suggest it; there is not yet a published result where an agent trained inside a generative video world model transfers to a real task and beats a baseline trained conventionally. If someone tells you otherwise in an interview, ask for the benchmark.

---

## Mental model

```
THE ONE-LINE DEFINITION
  world model  =  learned P(s_{t+1} | s_t, a_t)  that you can ROLL FORWARD
                  without touching the real environment
  (a video model without action-conditioning is NOT this: it is a prior over
   futures, not a simulator you can act inside)

THE TWO THINGS IT BUYS YOU  (memorise these; nothing else is the argument)
  1. SAMPLE EFFICIENCY   1 real episode  ->  N imagined trajectories
                         real steps are expensive (wear, safety, money, time)
                         imagined steps cost a forward pass
  2. OFF-SYSTEM POLICY EVALUATION
                         score pi inside the model BEFORE it touches reality
                         (the only reason a hospital / plant / fleet lets you ship)

THE HA & SCHMIDHUBER 2018 DECOMPOSITION  (still the cleanest)

   frame x_t                                        REPRESENTATION
      |                                             ("what is true now")
      v
  +---------+   z_t in R^32
  |  V: VAE |------------------+
  | 4.35M p |                  |
  +---------+                  |
                               v
                     +---------------------+  DYNAMICS
      a_t ---------->|  M: MDN-RNN         |  ("what happens next")
                     |  422K params        |
                     |  P(z_{t+1}|z_t,a_t,h_t)
                     |  5-component GMM    |
                     +----------+----------+
                                | h_t (LSTM state, 256 units)
                                v
                     +---------------------+
                     |  C: linear controller|  867 PARAMETERS
                     |  a_t = W[z_t h_t]+b |  trained by CMA-ES
                     +---------------------+  ENTIRELY INSIDE THE DREAM

  KEY MOVE: C never sees a pixel and never touches VizDoom during training.
            It is optimised against M's hallucination, then deployed cold.
            Real result: ~1100 timesteps vs 750 solve threshold.

THE REPRESENTATION / DYNAMICS SPLIT
  encoder  q(z|x)      : throw away what does not matter    <- capacity sink
  dynamics p(z'|z,a)   : the part you actually plan through <- the hard part
  decoder  p(x|z)      : ONLY a training signal. At rollout time you never
                         need it. Dreamer never decodes during imagination.

WHY LATENT, NOT PIXELS
  pixel rollout:  1080p RGB = 6.2M dims/frame, ~99% of which is texture,
                  lighting, foliage, and other agent-irrelevant detail
  latent rollout: 32-1024 dims/frame. Same forward pass predicts 4-5 orders
                  of magnitude fewer numbers, so capacity goes to DYNAMICS
                  instead of to RECONSTRUCTION.
  the tell: a pixel-space predictor that is "good" by MSE is optimising
            mostly for getting the wallpaper right.

THE FUNDAMENTAL LIMIT: COMPOUNDING ERROR
  per-step fidelity (1-eps).  H-step fidelity = (1-eps)^H.  EXPONENTIAL.

    eps=2%     H=15  -> 74% of rollouts still faithful
               H=50  -> 36%
               H=100 -> 13%
               H=250 -> 0.6%      <- this is why long rollouts are useless
    half-life  H_1/2 = ln2 / eps  ~=  0.69/eps steps
               eps=1% -> 69 steps    eps=5% -> 14    eps=10% -> 7

  This is why Dreamer imagines H=15 and MBPO branches k~1-15 steps off REAL
  states, and why Genie 3's "a few minutes" (~4,300 autoregressive frames at
  24fps) is a rendering claim, not a planning claim.

WHERE THIS TRACK GOES NEXT
  T26-jepa              : predict in embedding space, skip generation entirely
  T26-video-generation  : the generative side, and what its metrics do/don't say
  T26-cosmos            : world models as an industrial data/simulation product
  T26-vla               : world model as the perception+prediction half of a policy
```

---

## How it actually works

### The argument, derived rather than asserted

Start from the cost model, because the entire case for world models is an economic argument dressed as an algorithmic one.

Let `c_real` be the cost of one environment step and `c_sim` the cost of one imagined step. For a physical robot, `c_real` includes wall-clock time (a 20 Hz control loop means 50 ms per step, so 10^7 steps is roughly 5.8 days of continuous operation with no resets), actuator wear, a human supervisor, and a nonzero probability of destroying hardware. For a recommender or a pricing system, `c_real` includes serving a real user a worse experience. `c_sim` is one forward pass through a network: on a single A100, a Dreamer-class RSSM step over a batch of 16 imagined trajectories costs on the order of a millisecond, so `c_real / c_sim` is somewhere between 10^2 and 10^6 depending on the domain.

Now the sample-efficiency claim. A model-free learner extracts one gradient signal per real transition (a replay buffer lets it reuse each transition many times, but it never gets a transition it did not observe). A model-based learner spends `N_real` real steps to fit the model, then generates `N_imag = B x H x U` imagined transitions, where `B` is the imagination batch size, `H` the horizon, and `U` the number of update iterations. DreamerV3's defaults give roughly `B=16`, `H=15`, and a training ratio (imagined-to-real step count) that for Atari100k runs in the hundreds. Concretely, the published comparisons: **PlaNet** (Hafner et al., ICML 2019) solved six DeepMind Control image-based tasks in about **2,000 episodes**, where D4PG from pixels needed roughly **50x** more on average, and on Cheetah Run specifically PlaNet exceeded D4PG's final reward by about **26%** while using around **500x fewer episodes**. That is the number to have cold. It is not a marginal efficiency win, it is two to three orders of magnitude, and it is the reason anyone tolerates the extra complexity of maintaining a second learned system.

The second half of the argument is the one candidates forget, and it is the half that actually gets budget approved in industry: **a world model lets you evaluate a policy without deploying it**. Off-policy evaluation from logged data (importance sampling, doubly-robust estimators) has variance that explodes as the evaluation policy diverges from the logging policy; the effective sample size collapses when the importance weights concentrate. A world model gives you an alternative: roll the candidate policy forward inside the model and read off the predicted return. This is exactly what Ha and Schmidhuber's Table 2 measures, and it is exactly where the method's honesty is tested, because the same table shows the model's predicted return and the real return diverging catastrophically under the wrong settings. At temperature `tau = 0.1` the dreamed score was **2086 +/- 140** and the real score was **193 +/- 58**, which is *worse than the random policy's 210 +/- 108*. A world model used for policy evaluation is a measurement instrument, and an uncalibrated measurement instrument that reports 2086 when the truth is 193 is worse than no instrument, because it manufactures confidence.

So the honest formulation of the argument is conditional, and you should state it conditionally in an interview: **a world model converts sample cost into model-error risk.** You are always making that trade. The engineering question is never "is a world model good" but "is my model's error over the horizon my decision requires small enough that the samples I saved were worth it."

### Ha and Schmidhuber 2018, mechanically

The paper's structure is three separately trained components, and the separation is the pedagogically important part.

**Step 1. Collect data with a random policy.** 10,000 rollouts, random actions. No reward involved. This is the part people miss: the world model in this paper has *no access to the reward signal at all*. V and M are trained purely to compress and predict observations. Only C sees reward.

**Step 2. Train V, a convolutional VAE.** For CarRacing-v0, `z` in `R^32`; for VizDoom Take Cover, `z` in `R^64`. Parameter counts: **4,348,547** for the CarRacing VAE and **4,446,915** for the Doom VAE. The Gaussian prior is doing real work here beyond the usual VAE story: it bounds the information capacity of `z`, which forces the encoder to discard detail, which is precisely what makes the downstream dynamics model tractable.

**Step 3. Train M, an MDN-RNN.** An LSTM (**256 hidden units** for CarRacing, **512** for Doom) that consumes `[z_t, a_t]` and emits the parameters of a **5-component mixture of diagonal Gaussians** over `z_{t+1}`, plus for the Doom task a Bernoulli over `done_{t+1}`. Parameter counts: **422,368** and **1,678,785** respectively. The mixture density output is not decoration. A single Gaussian would smear over discrete branch points; the mixture lets the model represent "the monster either fires a fireball or it does not" as two modes rather than as one blurred average of both. This is the same failure that makes deterministic pixel predictors go grey after a few frames.

**Step 4. Define C as a linear map.** `a_t = W_c [z_t ; h_t] + b_c`. For CarRacing that is **867 parameters** total. For Doom, **1,088**. Nine hundred parameters. The whole point of the architecture is that if V and M have done their job, the policy is nearly linear in the learned features, and a 867-parameter policy is small enough that a derivative-free optimiser (CMA-ES, population size 64) is a perfectly reasonable choice, which sidesteps every credit-assignment pathology of backpropagating through a long rollout.

**Step 5. Train C inside the dream, then transfer.** For Doom, M predicts `done` as well as `z`, which means M has everything needed to expose a `gym.Env` interface. The controller is trained against that fake Gym environment and never touches VizDoom. Results: about **900** timesteps inside the dream, about **1,100** timesteps in the real environment against a solve threshold of **750** (episodes cap at **2,100** steps, roughly 60 seconds), versus **820 +/- 58** for the best OpenAI Gym leaderboard entry and **210 +/- 108** for a random policy. On the CarRacing side the full world model scored **906 +/- 21** over 100 trials against a solve threshold of 900, where the same controller given only `z_t` (no `h_t`) scored **632 +/- 251**, adding a hidden layer got **788 +/- 141**, and prior deep RL results were DQN **343 +/- 18**, A3C-continuous **591 +/- 45**, A3C-discrete **652 +/- 10**, and the leaderboard best **838 +/- 11**.

Read the CarRacing ablation again, because it is the single most instructive number in the paper. Giving the controller the RNN's hidden state `h_t` in addition to the current latent `z_t` moved the score from 632 to 906 and turned an unsolved task into a solved one. `h_t` is the model's belief about the *future*, compressed. The controller is not planning; it is not rolling anything out at decision time. It is consuming a representation that already contains predictive information, and that alone is worth 274 points. This is the cheapest form of world-model benefit and it is available even when your model is far too inaccurate to roll out: **use the dynamics model as a representation learner, not as a simulator.** In production that is very often the only version of this that survives contact with reality.

### Cheating the model: the failure mode the paper named first

The paper's section 4.5 is titled "Cheating the World Model" and it describes the failure mode you will be asked about. Trained inside the dream, the controller discovered "an adversarial policy to move around in such a way so that the monsters in this virtual environment governed by the M model never shoots a single fireball during some rollouts." It found a movement pattern that extinguished fireballs. Not because the game allowed it, but because the *model* allowed it.

The mechanism is precise and worth stating precisely, because it generalises far beyond this paper. When you optimise a policy against a learned model, the optimiser is explicitly searching for the argmax of the model's predicted return. Regions where the model is *wrong in an optimistic direction* are exactly the regions with high predicted return, so the optimiser is drawn to them. Model error is not zero-mean noise from the optimiser's perspective; the optimisation process actively seeks out the error. This is the same structure as reward hacking and the same structure as adversarial examples: a powerful optimiser against an imperfect proxy will find the proxy's defects, and it will find them faster the more powerful the optimiser is.

Ha and Schmidhuber's mitigation is the one you should be able to name: **inject stochasticity into the model to make its defects harder to exploit.** They raise the sampling temperature `tau` of the MDN's mixture, which widens the predictive distribution. The full transfer table is the best empirical illustration of the trade-off in the literature:

| `tau` | Dreamed score | Real score |
|---|---|---|
| 0.10 | 2086 +/- 140 | 193 +/- 58 |
| 0.50 | 2060 +/- 277 | 196 +/- 50 |
| 1.00 | 1145 +/- 690 | 868 +/- 511 |
| 1.15 | 918 +/- 546 | **1092 +/- 556** |
| 1.30 | 732 +/- 269 | 753 +/- 139 |

At `tau = 0.1` the model mode-collapses so hard that monsters never fire at all; the agent scores a near-perfect 2086 in the dream and 193 in reality, below the 210 of a random policy. At `tau = 1.15` the dream is *harder* than reality (918 dreamed, 1092 real) and transfer is best. At `tau = 1.30` the dream becomes so noisy that there is not enough signal left to learn a good policy. The shape of that curve is the whole lesson: **the correlation between dreamed score and real score is not monotonic, and the best transfer happens when the model is pessimistic rather than accurate.** Deliberately making your simulator harder than reality is the same principle as domain randomisation in sim-to-real robotics, arrived at independently.

### Representation versus dynamics, and why the split matters

Every world model factorises into two learned objects with different jobs, different failure modes and different evaluation criteria:

- **Representation** `q(z_t | x_{<=t}, a_{<t})`: map observations to a state. The job is *compression with sufficiency*. It must throw away everything irrelevant to prediction and control while keeping everything relevant. Its characteristic failure is dropping something that mattered (a small distant object, a subtle indicator light) and its symptom is that the model's predictions are confidently wrong in a way that no amount of dynamics training fixes, because the information is simply not in `z`.
- **Dynamics** `p(z_{t+1} | z_t, a_t)`: roll the state forward under an action. The job is *accuracy over a horizon*. Its characteristic failure is compounding error, and its symptom is one-step accuracy that looks excellent while 20-step accuracy is garbage.

The reason to keep these separate in your head is that they are measured differently and fixed differently. One-step prediction error measures the dynamics head; latent linear-probe accuracy for known state variables measures the representation. A team that reports only reconstruction loss has measured neither. And critically, **the decoder is a third object that exists only to supply a training signal**. At rollout time Dreamer never decodes: imagination happens entirely in latent space, the actor and critic consume `z` directly, and the decoder is dead weight during inference. If your architecture requires decoding to pixels in order to take the next step, you have built a video model with an action input, not a latent world model, and you have paid the full pixel-space cost on every one of your rollout steps.

### Latent-space prediction versus pixel-space prediction

The argument for latent prediction is a capacity argument and a signal-to-noise argument, and both have numbers attached.

**The capacity argument.** A 1920x1080 RGB frame is 6,220,800 numbers. A DreamerV3 latent is 32 categorical variables of 32 classes each (1,024 bits of stochastic state) plus a deterministic recurrent state of a few hundred to a few thousand units. That is a compression ratio in the range 10^3 to 10^4. A model trained to minimise pixel reconstruction error allocates its capacity proportionally to where the error mass is, and in natural video the error mass is overwhelmingly in high-frequency texture: foliage, fabric weave, specular highlights, film grain, the exact shading of a wall. None of that is causally relevant to whether the robot's gripper closes on the mug. You are spending the majority of a fixed parameter and compute budget on the parts of the frame that a controller will never read.

**The signal-to-noise argument.** In a pixel-space model, the training loss is dominated by inherently unpredictable detail. Exactly *which* way each leaf moves in the wind is aleatoric noise. A model that minimises expected squared error on unpredictable content converges to the conditional mean, which is a blur. This is the mechanical reason pixel-space video predictors degrade to grey mush over 10 to 20 frames, and it is why Finn-style action-conditioned video prediction never became a planning substrate despite producing good-looking single-step predictions in 2016. Latent-space prediction with a learned encoder does not have this problem in the same form, because the encoder is free to not represent the leaves at all.

The counter-argument, and you should raise it before the interviewer does: **latent prediction has no external ground truth.** A pixel predictor can be evaluated against the actual next frame. A latent predictor is predicting its own encoder's output, which means encoder and predictor can collude on a degenerate solution: if `q(z|x)` maps everything to a constant, prediction is perfect and the representation is worthless. This is representation collapse, and it is the central technical problem of the entire joint-embedding family. The three standard defences are (a) keep a reconstruction term as an anchor, which is what Dreamer does and which is why Dreamer still has a decoder it never uses at rollout time, (b) use an asymmetric architecture with a stop-gradient and an EMA target encoder, which is what JEPA does (`T26-jepa`), or (c) add an explicit variance or covariance regulariser (VICReg-style). Dreamer's choice of (a) is a deliberate trade: it pays the pixel-reconstruction capacity cost during *training* in exchange for a collapse-proof objective, while getting the latent-rollout benefit at *inference*. That is a much more defensible position than "latents good, pixels bad," and it is the version a frontier-lab interviewer wants to hear.

### The PlaNet → Dreamer → DreamerV3 line, and exactly what each one fixed

This is the spine of the module. Four papers, four specific fixes. If you can recite what each one broke and repaired you will out-answer most candidates, because most people know "Dreamer" as one undifferentiated thing.

**PlaNet (Hafner et al., "Learning Latent Dynamics for Planning from Pixels", ICML 2019).** Two contributions. The first is the **RSSM**, the Recurrent State-Space Model, which splits the latent state into a *deterministic* recurrent path `h_t` (a GRU) and a *stochastic* variable `s_t` conditioned on it. The ablation in the paper is the argument: a purely stochastic state cannot reliably carry information many steps forward, because every step re-samples and injects noise, so long-range dependencies get washed out; a purely deterministic state cannot represent multiple possible futures, so it collapses branch points to their mean. RSSM keeps both paths and beats either alone. Every subsequent model in this line uses RSSM or a direct descendant. The second contribution is **latent overshooting**, a multi-step training objective: instead of training only the one-step prediction, train predictions made `d` steps ahead to match the posterior, for `d` up to some limit. This is a direct attack on compounding error at training time rather than a mitigation at inference time. PlaNet then *plans* at decision time with CEM (the cross-entropy method) over action sequences inside the latent model, with a planning horizon of 12 and 1,000 candidate sequences per iteration, and re-plans every step. Results: six DMC image tasks, roughly 2,000 episodes, versus about 50x more for D4PG on average and about 500x on Cheetah Run.

*What PlaNet did not fix:* CEM planning at every decision step is expensive (1,000 forward rollouts per action) and it does not amortise. Nothing is learned about *how to act*; the whole search is thrown away after each step. And CEM over raw action sequences degrades badly as the horizon or action dimensionality grows.

**Dreamer (Hafner et al., ICLR 2020).** The fix: **replace planning with a learned actor and critic trained by backpropagating through the imagined rollout.** Because the RSSM is differentiable, the gradient of the imagined return flows directly back into the actor's parameters through the dynamics, which is a far stronger learning signal than the zeroth-order CEM search PlaNet used. Imagination horizon **H = 15** steps, and a learned value function bootstraps the return beyond step 15, so the effective horizon is longer than the rollout without paying compounding error for it. That bootstrapping trick is the important structural idea: **do not extend the rollout to cover a long horizon; extend the rollout only as far as the model is trustworthy and let a learned critic carry the rest.** Dreamer beat PlaNet on 20 continuous-control tasks with lower compute per decision, because at deployment the actor is a single forward pass rather than a 1,000-rollout search.

*What Dreamer did not fix:* it used Gaussian latents, which work on smooth continuous control and struggle on domains with sharp discrete transitions. It could not do Atari.

**DreamerV2 (Hafner et al., "Mastering Atari with Discrete World Models", ICLR 2021).** The fix: **categorical latents with straight-through gradients**, replacing the Gaussian stochastic state with 32 categorical variables of 32 classes each. The ablation showed categoricals beating Gaussians across every aggregation method. The intuition is the same one that motivated the MDN in 2018: game dynamics are full of discrete branch points (you either got hit or you did not, the enemy either spawned or did not), and a Gaussian posterior has to represent a bimodal outcome as a wide unimodal blur, whereas a categorical can just put mass on two classes. DreamerV2 also added KL balancing (separate weights on the prior and posterior sides of the KL term, so the prior is pulled toward the posterior faster than the posterior is regularised toward the prior). The result: the first agent to reach human-level mean performance on the **55-game Atari benchmark at 200M frames** by learning behaviours purely inside a separately trained world model, on a single GPU in about 10 days, matching or exceeding top single-GPU model-free agents (Rainbow, IQN) at the same compute and wall-clock budget.

*What DreamerV2 did not fix:* it still needed per-domain hyperparameter tuning. Reward scales differ by orders of magnitude across domains (a DMC task returns values in [0, 1000] per episode; an Atari game might return 10 or 100,000; a sparse Minecraft reward is 0 almost always), and every one of those regimes wanted different loss weights, different clipping and different learning rates. That tuning burden is precisely what makes "general algorithm" claims hollow.

**DreamerV3 (Hafner et al., arXiv January 2023; *Nature*, April 2025).** The fix is not one architectural idea but a set of **robustness transformations that make one hyperparameter configuration work everywhere**, which is the actual headline result and the one worth quoting. The three you should be able to name:

1. **symlog prediction.** Transform targets with `symlog(x) = sign(x) * ln(|x| + 1)` and predict in that space, inverting with `symexp` at read time. This compresses large magnitudes while remaining smooth and sign-preserving near zero, so the same network and learning rate handle a reward of 0.01 and a reward of 100,000 without loss-scale tuning. The decoder uses a symlog MSE.
2. **twohot encoded regression** for reward and value. Rather than regressing a scalar, discretise the symlog-space target into **255 equally spaced buckets** and predict a categorical distribution, with the target represented as a two-hot vector splitting mass between the two adjacent buckets. This makes the loss scale-invariant and lets the model represent multimodal value distributions, which matters enormously with sparse rewards.
3. **Percentile-based return normalisation** for the actor's advantage scaling (using the 5th-to-95th percentile range of returns rather than a standard deviation), so that a domain where returns are almost always zero and occasionally huge does not produce exploding policy gradients.

The result: **outperforms specialised methods on over 150 tasks with a single fixed configuration**, spanning DMC proprio and vision, Atari at 200M and Atari100k, ProcGen, DMLab, BSuite, Crafter and Minecraft, and it was **the first algorithm to collect diamonds in Minecraft from scratch with no human data and no curriculum**, applied out of the box. Model sizes were studied from about **8M to 200M parameters**, with the important finding that larger models are not only better asymptotically but *more data-efficient*, learning faster per environment step, which is the opposite of the usual intuition that big models need more data. The default configuration is the 200M model; the Atari100k results use an XS variant of about 12M parameters.

Why the "one configuration" claim is the actual result, and how to say it in an interview: every prior model-based RL paper reported strong numbers on a domain family after per-domain tuning, which means the reported sample efficiency silently excluded the hundreds of tuning runs required to find those hyperparameters. A method that needs 200 tuning runs at 10^6 steps each to achieve a 10^5-step result is not sample-efficient in any sense a practitioner cares about. DreamerV3's contribution is removing that hidden cost, and that is a systems-engineering result as much as a machine-learning one. If you only remember one thing about DreamerV3, remember that.

### Compounding error: the actual arithmetic

This is the part of the module that separates a survey answer from an engineering answer. Do the arithmetic on a whiteboard and you will be the only candidate that day who did.

**Step 1. Set up the per-step error.** Let `eps` be the probability that one model step produces a next-state that is meaningfully wrong, formalised as the total-variation distance between the model's predicted next-state distribution and the true one: `eps = sup_{s,a} D_TV( p_hat(.|s,a), p(.|s,a) )`. "Meaningfully wrong" is doing real work here and you should say so; the whole analysis is only as good as your definition of a divergence that matters for your decision. For a discrete branch (did the object fall off the table or not) it is unambiguous. For a continuous state it is a threshold you choose.

**Step 2. Compound it over `H` steps.** By a union bound over the `H` steps, the total-variation distance between the `H`-step model trajectory distribution and the true one is at most `H * eps`. That is the standard bound and it is the one quoted in the simulation-lemma literature. It is loose but honest, and it is linear.

The multiplicative view is more useful for intuition. If each step is independently faithful with probability `(1 - eps)`, the probability that the whole `H`-step rollout is faithful is `(1 - eps)^H`, which decays **exponentially**:

```
FIDELITY OF AN H-STEP ROLLOUT = (1 - eps)^H

  eps \ H      5       15       50      100      250     1000
  0.1%      99.5%    98.5%    95.1%    90.5%    77.9%    36.8%
  0.5%      97.5%    92.8%    77.8%    60.6%    28.7%     0.7%
  1.0%      95.1%    86.0%    60.5%    36.6%     8.1%     0.004%
  2.0%      90.4%    73.9%    36.4%    13.3%     0.6%     ~0
  5.0%      77.4%    46.3%     7.7%     0.6%     ~0        0
 10.0%      59.0%    20.6%     0.5%     ~0        0        0
```

**Step 3. Read the half-life off it.** The horizon at which half your rollouts have gone wrong is

```
H_1/2 = ln(2) / -ln(1 - eps)  ~=  0.693 / eps      (for small eps)

  eps = 0.1%  ->  H_1/2 ~= 693 steps
  eps = 1%    ->  H_1/2 ~=  69 steps
  eps = 2%    ->  H_1/2 ~=  34 steps
  eps = 5%    ->  H_1/2 ~=  14 steps
  eps = 10%   ->  H_1/2 ~=   7 steps
```

This single formula explains most of the design decisions in the field. Dreamer's `H = 15` and MBPO's branched rollouts of `k = 1` to `15` are not arbitrary; they sit right around the half-life of a well-trained latent dynamics model whose per-step error is in the low single-digit percent. To plan 500 steps deep with 50% fidelity you would need `eps <= 0.14%`, which is roughly *seven times better one-step accuracy than any published learned dynamics model on a nontrivial domain.* That is the quantitative reason long rollouts are useless, and it is why the answer to "why not just imagine longer" is a number rather than a shrug.

**Step 4. Add the term that makes it worse than exponential.** The analysis above assumes `eps` is constant. It is not. Once the rollout drifts, it enters states that are increasingly off the model's training distribution, where the model's error is larger. Model a linear growth in per-step error with rollout depth, `eps_h = eps_0 (1 + beta*h)`, and the accumulated error becomes

```
sum_{h=0}^{H} eps_0 (1 + beta*h)  =  eps_0*H  +  eps_0*beta*H^2/2
```

which is **quadratic in the horizon**, not linear. With `eps_0 = 1%` and `beta = 0.05`, the accumulated error at `H = 15` is 0.15 + 0.056 = 0.21, but at `H = 100` it is 1.0 + 2.5 = 3.5, meaning the linear term stopped being the dominant one somewhere around `H = 40`. The self-reinforcement is the point: error causes distribution shift causes more error. This is the same structure as covariate shift in behaviour cloning (the DAgger problem), arrived at from the model side rather than the policy side, and it is worth saying so in an interview because it shows you see the shared structure.

**Step 5. Add the chaos term where it applies.** If the underlying dynamics have a positive Lyapunov exponent `lambda`, an initial discrepancy `delta_0` grows as `delta_0 * e^(lambda*H)` regardless of how good your model is. Solving for the horizon at which a discrepancy reaches order-one:

```
H_useful = (1/lambda) * ln(1 / delta_0)

  lambda = 0.5 / step,  delta_0 = 1e-3   ->  H ~= 13.8 steps
  lambda = 0.1 / step,  delta_0 = 1e-3   ->  H ~= 69 steps
  lambda = 0.5 / step,  delta_0 = 1e-6   ->  H ~= 27.6 steps
```

Note the shape: because the dependence on initial accuracy is *logarithmic*, improving your model by three orders of magnitude (from `1e-3` to `1e-6`) only doubles your useful horizon. In a chaotic domain, model accuracy buys horizon at a logarithmic rate, and no amount of scaling changes that. This is a hard physical ceiling, not an engineering gap, and it is the single most senior-sounding point available in this whole topic. It is also the correct answer to "will a big enough video model be able to simulate the world" for any chaotic subsystem: no, and the reason is not a deficiency of the model.

**Step 6. Translate error into decision quality.** What you actually care about is the gap between the return the model predicts for a policy and the return it really gets. Under the standard simulation-lemma-style analysis, with per-step model error `eps`, discount `gamma`, and rewards bounded by `R_max`, the value gap scales as roughly `2*gamma*eps*R_max / (1 - gamma)^2`. The `(1 - gamma)^-2` is the alarming factor: at `gamma = 0.99` that is 10,000, so a 1% model error and `R_max = 1` gives a bound around 198. The bound is enormously loose in practice, but the *scaling* is real and it tells you something actionable: **lowering the discount factor is a legitimate way to buy robustness against model error.** A shorter effective horizon (`1/(1-gamma)`) means less of your value estimate depends on the part of the rollout the model gets wrong. Many practitioners tune `gamma` down in model-based settings without knowing why it helps; this is why.

**The three mitigations that follow directly from the arithmetic**, and which you should present as a package:

1. **Keep `H` at or below the half-life** and bootstrap the rest with a learned critic (Dreamer's design).
2. **Branch short rollouts off real states** rather than rolling long from an initial state (MBPO's design, Janner et al., NeurIPS 2019). If you take `k = 5` steps from each of 1,000 real replay-buffer states you get 5,000 imagined transitions with maximum error `5*eps`, whereas one 5,000-step rollout has error `5000*eps`, which is vacuous. Same imagined-sample count, three orders of magnitude difference in worst-case error.
3. **Replan every step against a fresh real observation** (MPC discipline). Executing an open-loop `H`-step plan pays the full `(1-eps)^H`; executing only the first action and re-observing pays `(1-eps)^1` per committed decision, with the deeper part of the plan only influencing which first action you chose.

And the diagnostic that follows: **measure multi-step rollout error explicitly, at the horizon you plan to use, before trusting it.** One-step error is not evidence. Concretely, hold out real trajectories, encode the first state, roll the model forward `H` steps under the recorded actions, and plot the error against `h` for `h = 1 .. 4H`. You are looking for where the curve knees. Then set your planning horizon below the knee, not at it.

### Are video-generation models becoming world models?

This is the question you will actually be asked, and it is the one where marketing and evidence diverge most sharply. Handle it by sorting the claims into three bins out loud: **benchmarked results**, **demonstrated capabilities without published evaluation**, and **assertions**.

**The claim.** OpenAI's Sora technical report (February 2024) stated that "scaling video generation models is a promising path towards building general purpose simulators of the physical world," and every lab has since made a version of that argument. The mechanism proposed is that next-frame prediction on internet-scale video forces a model to learn the generative process behind the video, which includes physics, and that this emerges from scale the way in-context learning emerged in language models. It is not a stupid argument. Next-token prediction on text did produce more than anyone expected.

**What is actually benchmarked, with numbers.**

- **Genie** (Bruce et al., ICML 2024) is the well-evaluated one: 11B parameters, 30,000 hours of filtered 2D-platformer internet video, three components (a spatiotemporal ST-transformer video tokeniser, a **latent action model** that infers actions from unlabelled video pairs via a VQ-VAE with a codebook of only **8 discrete latent actions**, and an autoregressive dynamics model). The latent action model is the genuinely important idea and the one most likely to come up: it learns a controllable action space *from video that has no action labels at all*, which is what makes internet video usable as world-model training data. Genie reported controllability metrics and generalisation to unseen sketches and photographs.
- **PhyWorld** (Kang, Yue et al., "How Far is Video Generation from World Model: A Physical Law Perspective", ICML 2025, ByteDance Seed) is the strongest controlled evidence and the one to cite. They built a 2D simulator with textureless geometric shapes (deliberately eliminating appearance as a confound), generated unlimited data, trained DiT-S through DiT-XL on 30K, 300K and 3M samples, and measured *velocity error parsed from the generated video against the simulator's ground truth*, which is a quantitative physical measurement rather than a perceptual score. Results: in-distribution, scaling works cleanly, with uniform-motion velocity error falling from **0.022** (DiT-S, 30K) to **0.012** (DiT-L, 3M) against a ground-truth-video floor of **0.010**. Out-of-distribution, the same DiT-L/3M model had error **0.427**, roughly **35x** worse, and scaling did nothing: DiT-B's OOD error across 30K/300K/3M was **0.433, 0.328, 0.358**, non-monotone noise rather than a trend, and DiT-XL on 3M showed no improvement either. Combinatorial generalisation was the one bright spot: on PHYRE templates, increasing training coverage from 6 to 30 to 60 templates dropped the human-judged abnormal-video rate on unseen templates from **67%** to **18%** to **10%**, while shrinking the model to DiT-B at 60 templates pushed it back up to **24%**. Their mechanistic finding is the memorable one: models generalise **case-based**, retrieving the nearest training example rather than abstracting a rule, with a retrieval priority order of **colour > size > velocity > shape**. Show a model a blue ball when it was trained on red balls and blue squares, and the blue ball turns into a blue square mid-video. It preserved the wrong invariant.
- **Physical-consistency benchmarks** consistently show low absolute numbers. On VideoPhy, the best model tested (Pika) satisfied both the caption and physical law on **19.7%** of instances, with CogVideoX-5B at **39.6%**. VideoPhy-2's hard subset: the best model reached **22%** joint semantic-plus-physical adherence. PhyWorldBench: Sora-Turbo **20.8%**, Kling-1.6 **18.8%** on combined semantic and physical commonsense. These are the numbers that should be in your head when someone shows you a beautiful reel.
- **V-JEPA 2** (Meta, June 2025) is the counter-programme with an actual closed-loop robot result: a ViT-g encoder (>1B parameters) pretrained on VideoMix22M (>1M hours of video), then an action-conditioned predictor post-trained on **fewer than 62 hours** of unlabelled Droid robot video, deployed **zero-shot** on Franka arms in two labs with no data from those labs, achieving **65% to 80%** success on pick-and-place of novel objects via planning to image goals. Note what makes this a strong claim: it is a *task success rate on real hardware in an unseen environment*, which is the format the field should be reporting in.

**What is demonstrated but not evaluated.** Genie 3 (5 August 2025) generates navigable 720p worlds at 24 fps holding consistency for a few minutes, is described by DeepMind as a stepping stone toward AGI, and has **no technical report, no benchmark table, and no published agent-training result** as of this writing. It is a limited research preview. Its own stated limitations are the load-bearing ones for the world-model claim: the agent action space is navigation-only (no fine manipulation), effective memory is on the order of one minute, multi-agent interaction is not robust, and specific real-world locations cannot be reliably simulated. NVIDIA's Cosmos family (announced CES January 2025, updated through Cosmos-Predict2.5 and Cosmos 3 into 2026) reports training-scale figures (**20 million hours** of driving/robotics/synthetic video, a vendor-stated **9,000 trillion tokens**, Predict2.5 trained on 200M curated clips at 2B and 14B parameter scales) and is genuinely used as a synthetic-data generator for autonomous-driving and robotics pipelines; that is a real product with a real use case, and it is a different claim from "this is a simulator you can train a policy inside."

**The serious objection, stated precisely.** Visual plausibility and physical consistency are different properties, and the standard training objective only optimises the first. A diffusion or autoregressive video model is trained to maximise likelihood (or minimise a denoising loss) over frames. That objective is fully satisfied by producing frames from the right marginal distribution. It contains **no term** that penalises a violation of momentum conservation, provided the violating frames are individually in-distribution. Worse, the failure is invisible to the metrics the field grew up on: FVD, LPIPS, PSNR and human preference scores all reward frames that look right. PhyWorld's own PHYRE table shows exactly this dissociation, with SSIM at 0.943 to 0.951 and PSNR at 25.5 to 27.3 on out-of-template videos whose human-judged abnormal rate ranged from 67% down to 10%. The perceptual metrics barely moved across a 6.7x change in physical correctness. If you take one sentence from this section into an interview, take that one.

There is a second, subtler objection from the same paper that almost nobody raises and that will land: **video may not contain enough information to determine the physics in the first place.** PhyWorld found that when a ball's size relative to a gap differs by a few pixels, or its horizontal position relative to a block is ambiguous at the rendering resolution, the outcome is genuinely underdetermined by the pixels. The model produces a visually plausible but wrong result because the correct result was not inferable from the observation. No amount of scaling fixes an information-theoretic deficit in the observation channel. This is an argument for multimodal state (proprioception, force sensing, explicit numeric state) rather than more pixels, and it is why the pure "scale video" position is contested on principle and not just empirically.

**The honest steelman for the other side**, which you should offer unprompted because it demonstrates you are reasoning rather than siding: PhyWorld tested 2D synthetic scenes with models up to DiT-XL, which is orders of magnitude below frontier video-model scale, on data with none of the diversity of real video. A defender can legitimately say the experiment shows that *this scale on this data* does not induce physical law, not that no scale ever will. Also, exact physical law may not be the right bar. If the downstream use is generating training data for a robot policy that will be fine-tuned on real data anyway, then "physically approximate but visually and semantically diverse" may be exactly the product you want, and Cosmos is sold on precisely that logic. The claim that fails is not "video models are useful"; it is "video models are simulators you can safely optimise a policy against." Optimising against them invokes the model-exploitation dynamic from 2018, and a model with a 20% physical-adherence rate is a model with an enormous exploitable surface.

### What "understanding physics" would actually require, and how to test it

If an interviewer asks whether a model "understands physics," the winning move is to refuse the question as posed and replace it with a test protocol. Here is one, in escalating order of strength. Each level is strictly harder than the one before, and a model can pass every level below the one that matters for your use case and still be useless.

**Test 1. Prediction accuracy in-distribution.** Roll forward from held-out initial conditions drawn from the training distribution; measure error on *extracted physical quantities* (position, velocity, contact events), not on pixels. Necessary, nowhere near sufficient. PhyWorld's DiT-L hit 0.012 velocity error against a 0.010 ground-truth floor here, and still failed everything below.

**Test 2. Conservation-law adherence.** Extract state from generated video and check invariants that must hold: momentum before and after a collision, total energy in an elastic system, object count, mass. This is checkable automatically and is the cheapest high-signal test available. A model that violates object permanence, meaning an object disappears under occlusion and does not reappear, fails here and should be disqualified from any planning use immediately.

**Test 3. Out-of-distribution extrapolation.** Hold out a *contiguous region* of a physical parameter, not random samples. PhyWorld's method is the template: train on velocities in [1.0, 1.25] and [3.75, 4.0], test in the excluded [1.25, 3.75]. A model that learned the law interpolates and extrapolates; a model doing case-based retrieval snaps the generated velocity toward the nearest training value. This is the test that separates "learned the rule" from "memorised the manifold," and the gap between Test 1 and Test 3 performance is the number you want. A 35x gap means case-based.

**Test 4. Counterfactual consistency.** Same initial state, different action, and check that the *difference* between the two rollouts is physically coherent. This is the test that specifically distinguishes a world model from a video prior, because it probes the causal structure `p(s'|s,a)` rather than the marginal `p(s')`. A model that produces two individually plausible videos whose difference makes no sense given the difference in action has not learned dynamics.

**Test 5. Compositional generalisation.** Every element seen in training, no combination of them seen. PhyWorld's 6/30/60-template PHYRE sweep is the clean instance, and the result (67% → 10% abnormal as coverage grows) says compositional generalisation is achievable but is bought with *combination coverage*, which implies a scaling law over combinatorial diversity rather than over raw data volume. That is a genuinely useful practical conclusion: for a world model, collecting 10x more of the same scenes is worth much less than collecting the same volume across 10x more scenario combinations.

**Test 6. Closed-loop task success.** Train or plan a policy inside the model, deploy on the real system, measure task success and compare against a baseline trained without the model. This is the only test that matters commercially and it is the one almost nobody publishes for generative video world models. V-JEPA 2's 65-80% zero-shot pick-and-place on unseen Franka setups is a Test 6 result. DreamerV3's Minecraft diamonds is a Test 6 result. A reel of a generated forest is a Test 1 result at best, and usually not even that, because nothing was measured.

**Test 7. Sim-to-real correlation.** Across a set of candidate policies, measure the rank correlation between predicted-in-model return and actual real-world return. This is the metric that tells you whether the model is usable for *policy evaluation*, which is half the reason to build one. Ha and Schmidhuber's temperature table is a five-point sample of exactly this curve, and it shows the correlation can be strongly negative (dreamed 2086 → real 193, dreamed 918 → real 1092). If you are proposing a world model as an evaluation harness in a design review, this is the number to commit to producing. Spearman rank correlation over at least 10 to 20 candidate policies, reported before anyone is allowed to trust the harness.

---

## Build it from scratch

The smallest thing that is genuinely a world model, and not a video predictor: an encoder, a latent transition model, a reward head, and a policy trained purely on imagined rollouts. This is a deliberately stripped RSSM (deterministic path only, Gaussian stochastic state omitted) so the moving parts stay visible. The matching lab folder should be `(lab pending)`.

```python
# untested sketch -- minimal latent world model + imagination-trained actor.
# Deliberately omits: KL balancing, categorical latents, symlog/twohot,
# free bits, and the target critic. Those are the DreamerV3 robustness layer.
import torch
import torch.nn as nn
import torch.nn.functional as F

OBS_DIM, ACT_DIM, Z_DIM, H_DIM = 64, 4, 32, 200


class WorldModel(nn.Module):
    """Encoder + recurrent latent dynamics + reward/continue heads + decoder.
    The decoder exists ONLY to keep the representation from collapsing.
    It is never called during imagination."""

    def __init__(self):
        super().__init__()
        self.encoder = nn.Sequential(
            nn.Linear(OBS_DIM, 256), nn.SiLU(), nn.Linear(256, Z_DIM))
        self.cell = nn.GRUCell(Z_DIM + ACT_DIM, H_DIM)          # deterministic path
        self.prior = nn.Sequential(                              # p(z' | h)
            nn.Linear(H_DIM, 256), nn.SiLU(), nn.Linear(256, Z_DIM))
        self.reward = nn.Sequential(
            nn.Linear(H_DIM + Z_DIM, 256), nn.SiLU(), nn.Linear(256, 1))
        self.cont = nn.Sequential(                               # episode continuation
            nn.Linear(H_DIM + Z_DIM, 256), nn.SiLU(), nn.Linear(256, 1))
        self.decoder = nn.Sequential(
            nn.Linear(H_DIM + Z_DIM, 256), nn.SiLU(), nn.Linear(256, OBS_DIM))

    def observe(self, obs_seq, act_seq):
        """Filter a REAL trajectory to get posterior states. obs (T,B,OBS_DIM)."""
        T, B, _ = obs_seq.shape
        h = torch.zeros(B, H_DIM, device=obs_seq.device)
        hs, zs = [], []
        for t in range(T):
            z = self.encoder(obs_seq[t])                        # posterior from obs
            hs.append(h); zs.append(z)
            h = self.cell(torch.cat([z, act_seq[t]], -1), h)    # advance dynamics
        return torch.stack(hs), torch.stack(zs)

    def imagine_step(self, h, z, a):
        """One step of PURE imagination: no observation, no decoding."""
        h = self.cell(torch.cat([z, a], -1), h)
        z = self.prior(h)                                       # predicted next latent
        return h, z

    def loss(self, obs_seq, act_seq, rew_seq, cont_seq):
        hs, zs = self.observe(obs_seq, act_seq)
        feat = torch.cat([hs, zs], -1)
        recon = F.mse_loss(self.decoder(feat), obs_seq)         # anti-collapse anchor
        rew = F.mse_loss(self.reward(feat).squeeze(-1), rew_seq)
        con = F.binary_cross_entropy_with_logits(
            self.cont(feat).squeeze(-1), cont_seq)
        # dynamics loss: prior must predict the NEXT posterior latent.
        # This term is the actual world model. Everything else is scaffolding.
        pred_next = self.prior(hs[1:])
        dyn = F.mse_loss(pred_next, zs[1:].detach())
        return recon + rew + con + 10.0 * dyn


def train_actor_in_imagination(wm, actor, critic, h0, z0, horizon=15, gamma=0.99):
    """Roll the model forward from REAL filtered states and backprop the
    imagined return through the differentiable dynamics into the actor.

    horizon=15 is not a free parameter. It is roughly the half-life
    0.693/eps for a model with per-step error eps ~ 4-5%. Measure YOUR
    model's multi-step error before changing it."""
    h, z = h0, z0
    rewards, values, entropies = [], [], []
    for _ in range(horizon):
        feat = torch.cat([h, z], -1)
        dist = actor(feat)                     # torch.distributions object
        a = dist.rsample()                     # reparameterised: gradient flows
        entropies.append(dist.entropy())
        h, z = wm.imagine_step(h, z, a)
        feat = torch.cat([h, z], -1)
        rewards.append(wm.reward(feat).squeeze(-1))
        values.append(critic(feat).squeeze(-1))

    # Bootstrap past the horizon with the critic. This is the key trick:
    # do NOT lengthen the rollout to cover a long horizon. Let the critic
    # carry the tail so compounding error stays capped at `horizon` steps.
    ret = values[-1]
    returns = []
    for r, v in zip(reversed(rewards), reversed(values)):
        ret = r + gamma * (0.95 * ret + 0.05 * v)   # lambda-return, lambda=0.95
        returns.append(ret)
    returns = torch.stack(list(reversed(returns)))

    actor_loss = -(returns.mean() + 3e-4 * torch.stack(entropies).mean())
    critic_loss = F.mse_loss(torch.stack(values), returns.detach())
    return actor_loss, critic_loss


@torch.no_grad()
def multistep_error_curve(wm, obs_seq, act_seq, max_h=60):
    """THE DIAGNOSTIC. Run this before you trust any horizon.
    Roll the model open-loop under recorded actions and compare the predicted
    latent against the posterior latent the encoder produces from the REAL
    observation at the same timestep. Plot; find the knee; plan below it."""
    hs, zs = wm.observe(obs_seq, act_seq)
    h, z = hs[0], zs[0]
    errs = []
    for t in range(min(max_h, obs_seq.shape[0] - 1)):
        h, z = wm.imagine_step(h, z, act_seq[t])
        errs.append((z - zs[t + 1]).pow(2).mean().item())
    return errs      # expect roughly flat then a knee, NOT a straight line
```

Three things in that sketch are the whole module in code. `imagine_step` never calls the decoder, which is what makes it a latent world model rather than a video model. `train_actor_in_imagination` caps the rollout at 15 and bootstraps the tail with a critic, which is the compounding-error mitigation expressed as an architecture choice. And `multistep_error_curve` is the function most teams never write, which is why they discover their horizon was too long by shipping.

---

## How it's done in production

Be blunt about the state of play: **almost nothing in this module is deployed at scale as a decision-making system.** The deployed uses of world models today are (a) representation learning, (b) synthetic data generation, and (c) offline policy evaluation with heavy guardrails. Planning inside a learned generative model of a high-dimensional environment is a research capability with a small number of production instances, mostly in robotics and mostly at labs. Saying this plainly is a senior signal; claiming otherwise is a fast way to get caught.

| Use | What is actually used | What it adds | Maturity |
|---|---|---|---|
| Sample-efficient control from pixels | DreamerV3 (open source, JAX; PyTorch reimplementations exist) | One config across domains; 8M-200M params; the reference implementation to benchmark against | Research-grade, reproducible, real |
| Representation learning for a downstream policy | RSSM or JEPA-style encoder trained on unlabelled interaction, frozen, then a small head on top | The 632 → 906 CarRacing effect: predictive features beat instantaneous ones, with no rollout risk at all | Widely used, low risk, most common real deployment |
| Synthetic data for robotics/AV | NVIDIA Cosmos (Predict/Transfer/Reason), Isaac Sim + Cosmos hybrid pipelines | Scenario diversity and rare-event coverage that real fleets cannot collect; 20M hours of pretraining video | Productised, real customers, evaluated as data not as simulator |
| Zero-shot robot planning | V-JEPA 2-AC and successors, planning to image goals | 65-80% pick-and-place in unseen labs from <62h of robot video | Published result, early deployment |
| Agent training environments | Genie-family interactive world models | Diverse environments without hand-built engines | Demo/preview stage, no published closed-loop transfer result |
| Offline policy evaluation | A learned dynamics model plus a pessimism penalty (MOPO/MOReL-style conservative offline MBRL) | Bounds the exploitation of model error by penalising uncertainty | Used in industry, always with a live A/B as the real gate |
| Classical control where you can write `f` | An actual physics engine or identified linear model with MPC | Exactly correct dynamics, no compounding-error risk from learning | Deployed everywhere, and usually the right answer |

The last row is the one to say out loud. If you can write the dynamics down, write them down. A learned world model is what you reach for when the state is an image, the dynamics involve contact or deformation or other agents, or system identification has failed. Reaching for a learned model when a Kalman filter and a physical model would do is a resume-driven-development smell.

### Failure modes

| Symptom | Cause | Fix |
|---|---|---|
| A dreamed rollout tracks reality for N steps then diverges sharply and never recovers; the multi-step error curve is flat then knees hard | Compounding error crossing the model's accuracy half-life at roughly `0.693/eps` steps; past the knee the rollout is off-distribution and per-step error itself grows, so the divergence is super-exponential rather than linear | Measure the multi-step error curve and set the planning horizon at roughly half the knee. Branch short rollouts off real replay states (MBPO, `k = 1..15`) instead of long rollouts from an initial state. Bootstrap the tail with a learned critic (Dreamer's `H = 15` plus lambda-returns). Add latent overshooting to the training objective (PlaNet) so multi-step accuracy is trained rather than hoped for |
| Policy scores superbly in imagination and near-randomly in reality; the gap is largest for the *best* imagined policies | Model exploitation. The optimiser is explicitly searching for the argmax of predicted return, so it is drawn to regions where the model is optimistically wrong. This is not noise, it is adversarial search against your own model. Ha and Schmidhuber's `tau = 0.1` case: dreamed 2086, real 193, worse than random's 210 | Add stochasticity so defects are harder to exploit (raise the sampling temperature; their `tau = 1.15` gave the best transfer at 1092 real with only 918 dreamed). Add an explicit uncertainty penalty to imagined reward (MOPO/MOReL-style pessimism), penalising states where an ensemble disagrees. Use an ensemble and take the pessimistic member. Track dreamed-vs-real rank correlation across candidate policies as a first-class metric and stop trusting the model when it drops |
| An object goes behind another object and never comes back, or reappears changed in colour, size or count | No persistent object-level state. A frame-conditioned autoregressive model carries state only in its context window and its recurrent activations; there is no representation whose job is "this object exists and has these properties." Occlusion removes the pixel evidence, so nothing sustains the object. Genie-class models' effective memory of roughly one minute is this same limit measured in wall-clock | Test object permanence explicitly with scripted occlusion sequences and score object count and identity before and after. Lengthen and structure the memory (explicit slot or object-centric latents, retrieval over a persistent scene buffer, or an external 3D representation). If the downstream task requires reasoning about occluded objects, a purely generative video model is the wrong substrate and should be disqualified rather than tuned |
| Frame-to-frame video looks flawless, but the trajectory violates momentum, energy or mass conservation; perceptual metrics (FVD, SSIM, PSNR, LPIPS) all look fine | The training objective only requires each frame to be in-distribution. It contains no term penalising a physically impossible transition between plausible frames. PhyWorld's PHYRE table shows SSIM 0.943-0.951 and PSNR 25.5-27.3 across out-of-template videos whose human-judged abnormal rate ranged 67% to 10%: the perceptual metrics barely moved while physical correctness changed 6.7x | Stop scoring with perceptual metrics alone. Extract physical quantities from generated video and check invariants (momentum in/out of collisions, energy, object count). Adopt a physics benchmark as a gate (VideoPhy, VideoPhy-2, PhyWorldBench, WorldModelBench) and know that best-in-class numbers there are 20-40%, not 90%. If exact physics matters, add explicit state (proprioception, force, numeric state), because PhyWorld showed pixels alone can be information-theoretically insufficient to determine the outcome |
| Model is excellent on the training distribution and useless slightly outside it; scaling data or parameters does not help | Case-based generalisation. The model retrieves the nearest training example rather than abstracting a rule, with a documented attribute priority of colour > size > velocity > shape. PhyWorld: ID error 0.012 vs OOD 0.427 on the same model, and DiT-B OOD errors of 0.433/0.328/0.358 across a 100x data increase | Change what you scale. Combinatorial coverage helps where raw volume does not (67% → 10% abnormal rate going from 6 to 60 PHYRE templates). Audit your training set for combination coverage rather than hours. Accept a narrower operating envelope and add an out-of-distribution detector that refuses to plan when the current state is outside it |
| Latent predictions are perfectly accurate and the policy learns nothing | Representation collapse. The encoder found a constant or near-constant mapping, making the prediction task trivially solvable and the representation information-free | Check for it directly: measure the variance and effective rank of `z` across a batch, and linear-probe `z` for known ground-truth state variables. Fix with a reconstruction anchor (Dreamer), an EMA target encoder plus stop-gradient (JEPA), or a variance/covariance regulariser (VICReg) |
| Model-based training is *slower* to converge than a model-free baseline on the same task | The model is being trained on data from a policy that is still random, so early imagined rollouts train the actor toward a wrong target; also the wall-clock cost per environment step is much higher for model-based methods even when the sample count is far lower | Compare on the axis that matters for your constraint. If real samples are cheap (a fast simulator), model-free is often simply the better engineering choice. If real samples are expensive, report sample efficiency, not wall clock, and say which you are optimising |
| A model that worked at deployment degrades over weeks with no code change | Distribution drift. The environment changed (wear, seasonality, other agents adapting) and the model's `eps` grew, shrinking the usable horizon under a planning horizon that stayed fixed | Monitor one-step and `H`-step prediction error against live data continuously and alert on it. Treat rising model error as a trigger to shorten the horizon automatically, not just to retrain |

---

## Tradeoffs & when NOT to use it

- **Do not use a learned world model when you can write the dynamics down.** If the system is well-modelled by known physics or an identified linear system, an explicit model plus MPC gives you exact dynamics, analysable stability, and zero compounding-error-from-learning risk. Learned world models exist for the case where the state is an image or the dynamics involve contact, deformation, or other agents. Choosing a learned model over an available exact one is strictly worse on every axis except novelty.
- **Do not use one when real samples are cheap.** The entire sample-efficiency argument is `c_real / c_sim`. If you have a fast, accurate simulator that runs at 10,000 steps per second, the ratio inverts: model-free PPO against the real simulator will beat model-based methods on wall clock, and it carries none of the model-error risk. World models pay off when a real step costs seconds of robot time, a safety review, or a customer's trust.
- **Do not plan through one over a long horizon without having measured multi-step error at that horizon.** One-step accuracy is not evidence about 100-step accuracy; `(1-eps)^H` says the relationship is exponential. This is the single most common way these projects fail, and it is entirely preventable with the twenty lines of diagnostic code above.
- **Do not use a generative video model as an optimisation target.** Model exploitation gets worse as the optimiser gets stronger, and a model scoring 20% on physical adherence has an enormous exploitable surface. Video world models are currently better suited to generating *data* (which is then filtered and used for supervised or imitation learning) than to being an environment a policy is optimised inside. Cosmos is sold on the first framing for a reason.
- **Do not use one in chaotic or adversarial domains.** With a positive Lyapunov exponent, useful horizon grows only logarithmically in model accuracy: going from `1e-3` to `1e-6` initial-state accuracy doubles your horizon, which is a terrible return on a thousand-fold improvement. In adversarial domains (markets, security, competitive games with adapting opponents) the environment actively moves away from your model.
- **Do not use one where a failure of imagination is unbounded in cost.** If the worst case of acting on a wrong prediction is a safety incident, the model belongs behind a validated safety layer that has authority to override it, and the world model's role should be reduced to proposing rather than deciding.
- **Be honest about the operational cost.** A model-based system has two learned components to train, validate, version, monitor and debug instead of one, plus a diagnostic surface (multi-step error curves, dreamed-vs-real correlation, collapse checks) that does not exist in a model-free system. That is real permanent engineering headcount. It needs to be justified by a measured sample-efficiency or evaluation win, not by the architecture being interesting.
- **The version that almost always survives contact with production is the weakest one, and that is fine.** Use the world model as a *representation learner* and throw away the rollout. You get the 632 → 906 effect (predictive features beat instantaneous ones) with none of the compounding-error or model-exploitation risk, because you never roll anything out. If you propose this in a design review you will look experienced rather than unambitious, and you should have the CarRacing ablation ready as the justification.

---

## Interview questions

### Q1 — What is a world model, and why would you build one?
**Testing:** whether you have a definition or a vibe, and whether you reach for the two-part argument.
**Answer:** A world model is a learned model of environment dynamics, `p(s_{t+1} | s_t, a_t)`, that can be rolled forward without touching the real environment. Two things justify it. First, sample efficiency: one real trajectory amortises into many imagined ones, and the published gap is two to three orders of magnitude (PlaNet solved DMC image tasks in about 2,000 episodes where D4PG needed roughly 50x more on average and 500x on Cheetah Run). Second, off-system policy evaluation: you can score a candidate policy inside the model before it touches a robot, a fleet, or a customer, which is often the only reason a deployment gets approved. Everything else, including the "understands the world" framing, is downstream of those two.
**Follow-up trap:** *"Sora generates realistic video. Is it a world model?"* Not by that definition, not without action-conditioning. A video model is a prior over plausible futures; a world model is a conditional next-state distribution you can act inside. The distinguishing test is counterfactual: hold the state fixed, vary the action, and check that the difference between rollouts is coherent. A model that produces two individually beautiful videos whose difference makes no sense given the action difference has learned `p(s')`, not `p(s'|s,a)`. Genie's contribution over Sora was exactly this: an unsupervised latent action model that recovers a controllable action space (a codebook of 8 latent actions) from video with no action labels.

### Q2 — Walk me through Ha and Schmidhuber's 2018 World Models paper.
**Testing:** whether you know the canonical result mechanically or just by name.
**Answer:** Three separately trained components. V is a convolutional VAE compressing frames to `z` (32-D for CarRacing, 64-D for VizDoom, about 4.35M parameters). M is an MDN-RNN, an LSTM of 256 hidden units emitting a 5-component Gaussian mixture over `z_{t+1}` given `[z_t, a_t]` plus a `done` head for Doom, about 422K parameters. C is a **linear** controller, `a = W[z; h] + b`, at **867 parameters**, trained by CMA-ES with population 64. Data collection is 10,000 rollouts from a random policy, and critically V and M never see the reward at all. For VizDoom the controller is trained entirely inside M's hallucination, exposed as a fake Gym environment, and then deployed cold: about 900 timesteps dreamed, about 1,100 real, against a 750 solve threshold and 820 for the best Gym leaderboard entry. On CarRacing the full model scored 906 +/- 21 against a 900 solve threshold.
**Follow-up trap:** *"What does the ablation where the controller only sees `z_t` tell you?"* It scored 632 +/- 251 instead of 906 +/- 21, and adding a hidden layer only got to 788 +/- 141. The RNN hidden state `h_t` is worth 274 points on its own, and the controller is not planning at decision time; it is consuming a representation that already encodes predictive information about the future. That is the cheapest and most robust way to get value from a world model, and it is available even when the model is far too inaccurate to roll out. In production it is usually the only version that survives.

### Q3 — Derive why long model rollouts are useless. Give me numbers.
**Testing:** whether you can do the arithmetic rather than saying "errors compound."
**Answer:** Let `eps` be the per-step probability that the model's next-state prediction is meaningfully wrong, defined as total-variation distance from the true transition distribution. Over `H` steps the union bound gives total divergence at most `H*eps`; the multiplicative view, the probability the whole rollout stays faithful, is `(1-eps)^H`, which decays exponentially. At `eps = 2%`: 74% at H=15, 36% at H=50, 13% at H=100, 0.6% at H=250. The half-life is `H_1/2 ≈ 0.693/eps`, so 1% error gives 69 steps, 5% gives 14, 10% gives 7. To plan 500 steps at 50% fidelity you would need `eps ≤ 0.14%`, roughly seven times better than any published learned dynamics model on a nontrivial domain. That is why Dreamer imagines 15 steps and MBPO branches 1 to 15 steps off real states rather than rolling long.
**Follow-up trap:** *"Is it really exponential, or is that pessimistic?"* It is worse than the constant-`eps` analysis suggests, because `eps` is not constant. Drift pushes the rollout off the model's training distribution, where its error is larger, so error causes distribution shift causes more error. Model that as `eps_h = eps_0(1 + beta*h)` and the accumulated error picks up an `eps_0*beta*H^2/2` term, making it quadratic in the horizon. With `eps_0 = 1%` and `beta = 0.05`, the quadratic term overtakes the linear one around H = 40. It is the same covariate-shift structure as the DAgger problem in behaviour cloning, seen from the model side instead of the policy side.

### Q4 — Why predict in latent space rather than pixel space?
**Testing:** whether you can give the capacity argument *and* the noise argument, and whether you know the cost.
**Answer:** Capacity: a 1080p RGB frame is 6.2M numbers, a DreamerV3 latent is 32 categoricals of 32 classes plus a recurrent state, a compression of 10^3 to 10^4. Reconstruction loss allocates capacity proportionally to error mass, and in natural video that mass is overwhelmingly high-frequency texture that no controller reads. Noise: much of the pixel content is aleatoric (exactly which way each leaf moves), and a model minimising expected squared error on unpredictable content converges to the conditional mean, which is a blur. That is the mechanical reason pixel-space video predictors degrade to grey mush within 10 to 20 frames, and why action-conditioned video prediction never became a planning substrate despite good single-step results in 2016-2017. Latent prediction with a learned encoder avoids both because the encoder is free not to represent the leaves.
**Follow-up trap:** *"What is the cost of latent prediction, then?"* No external ground truth. You are predicting your own encoder's output, so encoder and predictor can collude on a degenerate solution: map everything to a constant and prediction is perfect while the representation is worthless. That is representation collapse, and it is the central technical problem of the joint-embedding family. Three standard defences: a reconstruction anchor (Dreamer, which is why it keeps a decoder it never calls during imagination), an EMA target encoder with a stop-gradient (JEPA), or an explicit variance/covariance regulariser (VICReg). Dreamer's choice pays the pixel cost at training time to get a collapse-proof objective, while keeping the latent-rollout benefit at inference. Detect collapse by measuring the variance and effective rank of `z` across a batch and by linear-probing for known state variables.

### Q5 — Trace PlaNet to DreamerV3. What did each one specifically fix?
**Testing:** whether "Dreamer" is one blob in your head or four papers.
**Answer:** PlaNet (2019) introduced RSSM, splitting the latent into a deterministic GRU path and a stochastic variable, because a purely stochastic state washes out long-range information under repeated sampling and a purely deterministic one collapses branch points to their mean. It also introduced latent overshooting to train multi-step predictions directly. It planned with CEM at every decision step. Dreamer (2020) replaced CEM with an actor and critic trained by backpropagating the imagined return through the differentiable dynamics, at horizon 15, with a value function bootstrapping the tail: the search is amortised instead of thrown away every step. DreamerV2 (2021) replaced Gaussian latents with 32 categoricals of 32 classes using straight-through gradients, because game dynamics are full of discrete branch points a Gaussian must blur, and became the first agent to reach human-level on the 55-game Atari 200M benchmark learning purely inside a world model. DreamerV3 (2023, Nature 2025) added the robustness layer, symlog transforms, twohot regression over 255 buckets, and percentile return normalisation, which is what lets **one fixed configuration** beat specialised methods on 150+ tasks and collect Minecraft diamonds from scratch with no human data or curriculum.
**Follow-up trap:** *"Which of those is the most important result, and why?"* DreamerV3's single-configuration claim, and the reason is a systems argument, not an algorithms one. Every prior model-based paper reported strong numbers after per-domain hyperparameter tuning, which silently excluded hundreds of tuning runs from the reported sample cost. A method needing 200 tuning runs at 10^6 steps each to demonstrate a 10^5-step result is not sample-efficient in any practical sense. Removing the tuning cost is what turns a benchmark result into something you can apply to a new domain out of the box, which is what "general algorithm" is supposed to mean.

### Q6 — Your model-based agent scores 950 in imagination and 190 in the real environment, and a random policy scores 210. Diagnose it.
**Testing:** whether you recognise model exploitation and know it is adversarial rather than noisy.
**Answer:** That is the model-exploitation signature, and it is nearly exactly Ha and Schmidhuber's `tau = 0.1` row: 2086 dreamed, 193 real, against 210 for random. The optimiser is searching for the argmax of the model's predicted return, so it is *drawn toward* regions where the model is optimistically wrong. Model error is not zero-mean noise from the optimiser's point of view; the optimisation actively seeks it out, and it gets worse as the optimiser gets stronger. In their case the model had mode-collapsed so hard that monsters never fired at all, so the policy learned in a world with no threat. Diagnosis steps: check whether the imagined trajectories contain events that are physically impossible in the real environment, check the entropy or spread of the model's predictive distribution for collapse, and compute the rank correlation between dreamed and real return over a set of candidate policies.
**Follow-up trap:** *"Fix it."* Their fix is instructive because it is counter-intuitive: raise the model's sampling temperature to make the dream *harder* than reality. At `tau = 1.15` the dreamed score dropped to 918 while the real score rose to 1092, the best transfer in the table, and at `tau = 1.30` it degraded again because the dream became too noisy to learn in. So the best transfer happened where the model was pessimistic, not where it was accurate, and the dreamed-to-real correlation is non-monotonic. The modern equivalents are the same idea formalised: an explicit uncertainty penalty on imagined reward (MOPO/MOReL-style pessimism), ensemble disagreement as the penalty signal, and domain randomisation in sim-to-real robotics. All three are "make the simulator harder than reality on purpose."

### Q7 — Are video-generation models becoming world models? Give me the evidence on both sides.
**Testing:** whether you can separate benchmarked results from demos, which is the whole point of this module.
**Answer:** Sort it into three bins. Benchmarked: Genie (11B parameters, 30,000 hours of platformer video, 8 latent actions, published controllability metrics) and V-JEPA 2, which reports a closed-loop result, 65-80% zero-shot pick-and-place on Franka arms in two unseen labs after action-conditioned post-training on under 62 hours of unlabelled robot video. Demonstrated but unevaluated: Genie 3 (August 2025), 720p at 24 fps, consistent for a few minutes, with no technical report, no benchmark table, and no published agent-training result, and self-declared limits of navigation-only actions and roughly one minute of memory. Contradicting evidence: ByteDance's PhyWorld (ICML 2025) trained DiT-S through DiT-XL on 30K to 3M samples in a textureless 2D physics simulator and measured velocity error against ground truth. In-distribution error fell to 0.012 against a 0.010 floor; out-of-distribution error was 0.427 on the same model, about 35x worse, and did not improve with scale (DiT-B OOD across 30K/300K/3M: 0.433, 0.328, 0.358). The mechanism is case-based retrieval of the nearest training example with an attribute priority of colour > size > velocity > shape. Physical-consistency benchmarks agree: best joint semantic-plus-physical adherence is 19.7% for Pika on VideoPhy, 22% on VideoPhy-2's hard subset, 20.8% for Sora-Turbo on PhyWorldBench.
**Follow-up trap:** *"Steelman the other side."* Two real defences. First, PhyWorld tested 2D synthetic scenes at DiT-XL scale, orders of magnitude below frontier video models on data with none of the diversity of real video, so it shows that this scale on this data does not induce physical law, not that no scale ever will. Second, exact physics may be the wrong bar for the actual product: if the use is generating diverse training data for a robot policy that gets fine-tuned on real data anyway, then physically approximate but semantically diverse is exactly what you want, and that is precisely how Cosmos is positioned. The claim that fails is narrower than "video models are useless": it is "you can safely optimise a policy against one," and that fails because a model at 20% physical adherence has an enormous exploitable surface.

### Q8 — How would you test whether a model "understands physics"?
**Testing:** whether you replace a fuzzy question with a protocol.
**Answer:** Refuse the question as posed and give a ladder. Level 1, in-distribution prediction accuracy measured on *extracted physical quantities* rather than pixels. Level 2, conservation-law adherence, checking momentum before and after collisions, energy, object count and mass, which is cheap and automatable. Level 3, out-of-distribution extrapolation by holding out a *contiguous region* of a parameter (PhyWorld's method: train on velocity in [1.0, 1.25] and [3.75, 4.0], test the excluded middle). Level 4, counterfactual consistency: fix the state, vary the action, and check the difference between rollouts is coherent, which is what specifically distinguishes a world model from a video prior. Level 5, compositional generalisation with all elements seen and no combinations seen. Level 6, closed-loop task success on the real system against a baseline that did not use the model. Level 7, sim-to-real rank correlation across 10 to 20 candidate policies, which is the number that says whether the model is usable for policy evaluation. Almost every published video-model demo is Level 1 at best, and usually nothing was measured at all.
**Follow-up trap:** *"Which level would you gate a production launch on?"* Level 6 for anything that acts, Level 7 for anything that evaluates. Everything below 6 is a proxy, and the specific danger of the proxies is that they can be excellent while the thing you care about is broken. PhyWorld's PHYRE table is the demonstration: SSIM 0.943-0.951 and PSNR 25.5-27.3 across out-of-template videos whose human-judged abnormal rate spanned 67% down to 10%. Perceptual metrics barely moved while physical correctness changed by a factor of 6.7. Gating on FVD or LPIPS would have shipped all three models as equivalent.

### Q9 — What is the representation-versus-dynamics split, and why does it matter operationally?
**Testing:** whether you can decompose the system into parts with distinct failure modes.
**Answer:** Representation is `q(z | x)`, whose job is compression with sufficiency: throw away everything irrelevant while keeping everything needed for prediction and control. Its characteristic failure is dropping something that mattered (a small distant object, an indicator light), and the symptom is that predictions are confidently wrong in a way no amount of dynamics training fixes, because the information is not in `z`. Dynamics is `p(z' | z, a)`, whose job is accuracy over a horizon; its characteristic failure is compounding error, and the symptom is excellent one-step accuracy with garbage 20-step accuracy. They are measured differently: one-step and `H`-step prediction error tests the dynamics head, linear probing `z` for known state variables tests the representation. Reporting only reconstruction loss measures neither. The decoder is a third object that exists solely to supply a training signal and is never called during imagination.
**Follow-up trap:** *"If the decoder is never used at rollout time, why keep it?"* As an anti-collapse anchor. Predicting your own encoder's output admits a degenerate solution where the encoder is constant, and reconstruction forces `z` to retain information about `x`. Dreamer accepts the pixel-reconstruction capacity cost at training time in exchange for a collapse-proof objective while still getting latent-only rollouts at inference. JEPA takes the other branch: drop the decoder, prevent collapse structurally with an EMA target encoder and a stop-gradient. Both are defensible; what is not defensible is dropping the decoder without replacing its anti-collapse function with something.

### Q10 — Design a world-model-based system for a warehouse robot fleet. Where do you put the horizon and how do you monitor it?
**Testing:** applying the arithmetic to a real system with real constraints.
**Answer:** Start with a measurement, not a design. Roll the model open-loop under recorded actions and plot prediction error against horizon out to at least 4x the intended planning horizon, find the knee, and set the planning horizon at roughly half of it. For a 20 Hz control loop, a 15-step horizon is 0.75 seconds of lookahead, which is appropriate for reactive obstacle avoidance and inadequate for route planning, so split the problem: a classical planner over the known map (where you can write the dynamics down and should) for routing, and the learned model only for the short-horizon, hard-to-model part, meaning contact, other robots, and humans. Replan every step against fresh observations rather than committing to an open-loop plan, which caps the compounding-error exposure of any committed decision at one step. Monitor one-step and `H`-step prediction error continuously against live data and make rising error automatically shorten the horizon, not just page someone. Keep a validated safety layer with authority to override, so the world model proposes and does not decide.
**Follow-up trap:** *"Would you train the policy inside the model or use the model only for representation?"* Start with representation only. You get the effect Ha and Schmidhuber measured (632 → 906 on CarRacing from adding the RNN state to the controller's input) with zero compounding-error and zero model-exploitation exposure, because nothing is rolled out. Add imagination training only after you have multi-step error curves showing a knee well past your intended horizon, and after you have a dreamed-versus-real rank-correlation harness that has been validated on at least 10 to 20 candidate policies. That ordering is defensible in a design review in a way that "let's train in the dream" is not.

### Q11 — Why do DreamerV3's symlog and twohot tricks matter? They look like engineering details.
**Testing:** whether you understand that the generality result *is* the robustness layer.
**Answer:** They are the mechanism behind the headline. Reward scales differ by orders of magnitude across domains: a DMC episode returns values in [0, 1000], an Atari game might return 10 or 100,000, and Minecraft's reward is 0 almost always. Any fixed loss weighting, gradient clipping threshold or learning rate that works for one of those regimes fails for another, which is exactly why every prior model-based paper needed per-domain tuning. Symlog, `sign(x)*ln(|x|+1)`, compresses large magnitudes smoothly while staying well-behaved near zero, so the same network handles 0.01 and 100,000. Twohot regression discretises the symlog-space target into 255 buckets and predicts a categorical with mass split between the two adjacent buckets, which makes the loss scale-invariant and lets the model represent multimodal value distributions, which matters enormously under sparse reward. Percentile-based return normalisation keeps the actor's gradients bounded when returns are almost always zero and occasionally huge. Together these are what make one configuration work across 150+ tasks.
**Follow-up trap:** *"So is DreamerV3 a better algorithm than DreamerV2, or just a better-tuned one?"* Neither framing is quite right, and saying so is the answer. It is the same core algorithm made *tuning-free*, which is a stronger result than being better tuned, because the tuning cost is what made prior sample-efficiency claims misleading. Note also the scaling finding, which is worth naming: across model sizes from about 8M to 200M parameters, larger models were not only better asymptotically but *more data-efficient*, learning faster per environment step. That inverts the usual expectation that bigger models need more data, and it is the finding most likely to come up as a follow-up in a research interview.

### Q12 — When would you tell a team NOT to build a world model?
**Testing:** the senior signal, whether you have a real "no."
**Answer:** Four cases, in order of how often they come up. First, when you can write the dynamics down: an explicit physics model or identified linear system plus MPC gives exact dynamics and analysable stability, and choosing a learned model over an available exact one is worse on every axis except novelty. Second, when real samples are cheap: the whole argument is the ratio `c_real / c_sim`, so if you have a simulator running 10,000 steps per second, model-free PPO against it beats model-based on wall clock with none of the model-error risk. Third, in chaotic or adversarial domains: with a positive Lyapunov exponent the useful horizon grows only as `(1/lambda)*ln(1/delta_0)`, so improving initial accuracy a thousand-fold merely doubles your horizon, and in adversarial domains the environment actively moves away from your model. Fourth, when the operational cost is not justified: two learned systems to train, version, monitor and debug instead of one, plus a whole diagnostic surface that does not otherwise exist.
**Follow-up trap:** *"Your team already built one and it works in imagination. Do you ship it?"* Not on that evidence. Working in imagination is precisely the observation that is consistent with both success and total failure, and the failure mode is not rare: 2086 dreamed against 193 real in the canonical paper, below random. Before shipping I want the multi-step error curve with a knee past my horizon, the dreamed-versus-real rank correlation across at least 10 to 20 candidate policies, an out-of-distribution detector that refuses to plan outside the envelope, and a live A/B or shadow deployment as the actual gate. If those cannot be produced, the correct decision is to degrade the system to representation-only use and keep the rollout out of the decision path.

### Q13 — Objects vanish under occlusion in your generated rollouts. What is actually wrong and how do you fix it?
**Testing:** whether you can reason about the architecture rather than reaching for more data.
**Answer:** There is no representation whose job is "this object exists and has these properties." A frame-conditioned autoregressive video model carries state only in its context window and recurrent activations, so when occlusion removes the pixel evidence, nothing sustains the object, and when it should reappear there is no stored identity to reinstate. This is the same limit that shows up as Genie-class models having roughly one minute of effective memory. More data does not fix it, because the failure is structural rather than statistical; the training objective is satisfied by any plausible continuation, and a continuation where the object is simply gone is plausible frame-by-frame. Fixes in increasing order of effort: test it explicitly with scripted occlusion sequences scoring object count and identity before and after, then lengthen and structure the memory with object-centric or slot latents, a retrieval mechanism over a persistent scene buffer, or an explicit 3D scene representation the generative model conditions on.
**Follow-up trap:** *"Would adding a reconstruction loss over longer sequences fix it?"* No, and this is the important point. Reconstruction loss rewards frames from the right marginal distribution; a frame in which the object is absent is a perfectly good frame. The objective contains no term that penalises the *transition* from "object present" to "object absent" absent a cause. Same structural gap as physics violation: it is a property of trajectories, not of frames, and no per-frame loss can see it. Either the loss has to be defined over trajectory-level invariants (object count, identity persistence, conservation quantities) or the architecture has to carry persistent object state. If the downstream task requires reasoning about occluded objects, a purely generative video model is the wrong substrate and should be disqualified rather than tuned.

### Q14 — Compare a world model used for planning against one used only for representation learning. Which is deployed more, and why?
**Testing:** whether you know what actually ships.
**Answer:** Representation, by a wide margin, and the reason is risk asymmetry. Using the model as a representation learner means encoding observations into features that already contain predictive information and feeding those to a policy, with no rollout at decision time. You get the measurable benefit (632 → 906 on CarRacing from adding the RNN state, an unsolved task becoming a solved one) and you are exposed to neither compounding error nor model exploitation, because nothing is ever imagined. Using the model for planning or in-dream policy training means every one of the failure modes in this module is live, and the diagnostic burden is permanent. In production today, the deployed uses of world models are overwhelmingly representation learning, synthetic data generation (Cosmos and similar), and offline policy evaluation with pessimism penalties and a live A/B as the real gate. Planning inside a learned generative model of a high-dimensional environment is a research capability with a small number of production instances, mostly in robotics, mostly at labs.
**Follow-up trap:** *"Then why does anyone bother with the rollout at all?"* Because the representation-only version cannot do the thing that made DreamerV3 famous. You cannot get Minecraft diamonds from a better encoder; you need imagined trajectories to propagate credit across a long, sparse-reward, exploration-hard task, and the imagination is where the sample efficiency actually comes from. The honest framing is that representation-only is the reliable 80% you take by default, and imagination training is the high-variance remaining 20% you earn by producing multi-step error curves and dreamed-versus-real correlation first. Presenting it as a progression rather than a choice is what distinguishes an engineer who has run these systems from one who has read about them.

---

## Red flags that fail you

- Saying a world model "understands the world" or "learns physics" without being able to name a test that would distinguish that from case-based retrieval of the nearest training example.
- Treating Sora, Veo or any unconditioned video generator as a world model. Without action-conditioning it is a prior over futures, not a conditional next-state distribution you can act inside.
- Citing Genie 3, Cosmos or any lab demo as evidence of a capability without noting whether a benchmark, a technical report, or a closed-loop task-success number exists. If you cannot say which, say you cannot say which.
- Presenting one-step prediction accuracy as evidence that multi-step rollouts are trustworthy. `(1-eps)^H` is exponential; they are different questions.
- Describing compounding error qualitatively ("errors add up") when the arithmetic is two lines and the half-life formula `0.693/eps` explains most of the design decisions in the field.
- Missing that model exploitation is *adversarial*, not noise. The optimiser is drawn to model error because model error is where predicted return is highest, and the problem gets worse as the optimiser gets stronger.
- Not knowing that Ha and Schmidhuber's best transfer came from making the dream *harder* than reality (`tau = 1.15`, 918 dreamed and 1092 real) rather than more accurate.
- Claiming latent prediction is strictly better than pixel prediction without naming representation collapse as the price and at least one defence against it.
- Treating FVD, SSIM, PSNR or LPIPS as evidence of physical correctness. PhyWorld's PHYRE table has SSIM 0.943-0.951 across videos whose abnormal rate spanned 67% to 10%.
- Recommending a learned world model for a system whose dynamics you can write down, or for a domain where a fast simulator makes real samples cheap.
- Conflating the two research programmes that share the name: latent-dynamics model-based RL (benchmarked, works, DreamerV3) and generative video world models (impressive, largely unevaluated for control).
- Quoting "150+ tasks" for DreamerV3 without knowing that the load-bearing part of the claim is **a single fixed configuration**, which is what removes the hidden per-domain tuning cost.

## Cheat card

```
DEFINITION      world model = learned p(s'|s,a) you can ROLL FORWARD offline.
                No action-conditioning => video prior, NOT a world model.

WHY             (1) SAMPLE EFFICIENCY: 1 real episode -> N imagined
                (2) OFF-SYSTEM POLICY EVAL: score pi before it touches reality
                Trade being made: sample cost  ->  model-error risk. Always.

HA & SCHMIDHUBER 2018   V(VAE 4.35M, z=32 CarRacing / z=64 Doom)
                + M(MDN-RNN, LSTM 256/512, 5-component GMM, 422K/1.68M)
                + C(LINEAR, 867 params CarRacing / 1088 Doom, CMA-ES pop 64)
                10,000 random rollouts. V,M never see reward.
                CarRacing: full 906+-21 (solve=900); z only 632+-251;
                  +hidden layer 788+-141; DQN 343; A3C 591-652; leader 838
                Doom: trained ENTIRELY in dream -> ~900 dreamed, ~1100 real
                  (solve 750, cap 2100 steps, random 210, leader 820)
                TEMPERATURE tau: 0.1 -> dream 2086 / real 193 (< random!)
                                 1.15 -> dream 918 / real 1092  <- BEST
                                 1.30 -> dream 732 / real 753
                  => best transfer when dream is HARDER than reality

LINE            PlaNet 2019   RSSM (deterministic GRU + stochastic) +
                              latent overshooting + CEM planning.
                              ~2000 episodes vs D4PG 50x more (500x Cheetah)
                Dreamer 2020  actor-critic backprop THROUGH dynamics, H=15,
                              critic bootstraps the tail. Kills CEM cost.
                DreamerV2 21  32x32 CATEGORICAL latents + straight-through +
                              KL balancing. 1st human-level Atari 55 @200M
                              inside a world model, 1 GPU ~10 days.
                DreamerV3 23  symlog + twohot(255 buckets) + percentile return
                (Nature 25)   norm => ONE CONFIG, 150+ tasks, 1st Minecraft
                              diamonds from scratch, no human data/curriculum.
                              8M-200M params; bigger = MORE data-efficient.

COMPOUNDING     H-step fidelity = (1-eps)^H   [EXPONENTIAL]
ERROR           eps=2%:  H=15 -> 74%  H=50 -> 36%  H=100 -> 13%  H=250 -> 0.6%
                HALF-LIFE  H_1/2 ~= 0.693/eps
                  1% -> 69 steps   5% -> 14   10% -> 7
                500 steps @50% needs eps<=0.14% (~7x better than SOTA)
                WORSE than exponential: eps grows with drift (OOD),
                  eps_h = eps_0(1+beta*h) => accumulated ~ eps_0*beta*H^2/2
                CHAOS: H_useful = (1/lambda)*ln(1/delta_0)  [LOG in accuracy:
                  1e-3 -> 1e-6 only DOUBLES horizon]
                VALUE GAP ~ 2*gamma*eps*Rmax/(1-gamma)^2 => lowering gamma
                  is a legitimate robustness knob

MITIGATIONS     H <= half-life + critic bootstrap (Dreamer H=15)
                branch k=1..15 off REAL replay states (MBPO)
                replan every step vs fresh obs (MPC discipline)
                DIAGNOSTIC: plot multi-step error vs h out to 4H, find knee,
                  plan below it. One-step error proves NOTHING about H-step.

MODEL EXPLOITATION   optimiser seeks argmax of PREDICTED return => drawn TO
                model error. Not noise. Worse with stronger optimisers.
                Fixes: raise sampling temperature / uncertainty penalty
                (MOPO,MOReL) / ensemble disagreement / domain randomisation.

LATENT vs PIXEL  1080p RGB = 6.2M dims vs latent 10^3-10^4x smaller.
                Pixel loss mass = texture nobody plans on; MSE on aleatoric
                content -> conditional mean -> BLUR by frame 10-20.
                COST of latent: NO external ground truth -> COLLAPSE.
                Defences: reconstruction anchor (Dreamer) / EMA target +
                stop-grad (JEPA) / variance-covariance reg (VICReg).
                Decoder is NEVER called during imagination.

REP vs DYN      rep q(z|x): compression w/ sufficiency. Fails by dropping
                  info. Test: linear probe z for known state vars.
                dyn p(z'|z,a): accuracy over horizon. Fails by compounding.
                  Test: H-step error curve.

VIDEO-AS-WORLD-MODEL   PhyWorld (ICML 2025, ByteDance): ID vel error 0.012
                (GT floor 0.010) vs OOD 0.427 = 35x, and scale did NOT help
                (DiT-B OOD 0.433/0.328/0.358 over 30K/300K/3M).
                Mechanism: CASE-BASED retrieval, priority
                  COLOUR > SIZE > VELOCITY > SHAPE
                PHYRE templates 6/30/60 -> abnormal 67%/18%/10%
                  (DiT-B @60 -> 24%) => scale COMBINATIONS, not hours
                SSIM 0.943-0.951 across that whole range => perceptual
                  metrics are BLIND to physics
                Benchmarks: VideoPhy best 19.7% (Pika), CogVideoX-5B 39.6%;
                  VideoPhy-2 hard 22%; PhyWorldBench Sora-Turbo 20.8%,
                  Kling-1.6 18.8%
                Genie 2024: 11B params, 30k hrs platformer, 8 LATENT ACTIONS
                  (VQ-VAE, unsupervised from unlabelled video) - EVALUATED
                Genie 3 (5 Aug 2025): 720p, 24fps, "a few minutes",
                  navigation-only actions, ~1 min memory,
                  NO PAPER / NO BENCHMARK / NO CLOSED-LOOP RESULT
                V-JEPA 2 (2025): ViT-g >1B, >1M hrs video, AC post-train on
                  <62 hrs Droid, 65-80% ZERO-SHOT pick&place, 2 unseen labs
                Cosmos: 20M hrs video, vendor-stated 9,000T tokens,
                  Predict2.5 = 200M clips, 2B & 14B. Sold as DATA, not sim.

TEST LADDER     1 ID accuracy on extracted quantities (not pixels)
                2 conservation laws / object permanence
                3 OOD: hold out a CONTIGUOUS parameter region
                4 counterfactual: same state, different action
                5 compositional: all elements seen, no combinations seen
                6 CLOSED-LOOP task success vs a no-model baseline   <- gate
                7 sim-to-real RANK correlation over 10-20 policies  <- gate
                  for evaluation use

WHEN NOT TO     dynamics writable in closed form / real samples cheap /
                chaotic or adversarial domain / unbounded cost of a wrong
                imagination / 2 learned systems not justified by measured win
DEFAULT MOVE    use it as a REPRESENTATION learner, throw away the rollout.
                632 -> 906 for free, zero compounding-error exposure.
```

## Sources

- [Ha & Schmidhuber — World Models (arXiv 1803.10122, 2018)](https://arxiv.org/abs/1803.10122) — accessed 2026-08-05
- [Hafner et al. — Learning Latent Dynamics for Planning from Pixels (PlaNet, ICML 2019)](https://proceedings.mlr.press/v97/hafner19a/hafner19a.pdf) — accessed 2026-08-05
- [Google Research — Introducing PlaNet: A Deep Planning Network for Reinforcement Learning](https://research.google/blog/introducing-planet-a-deep-planning-network-for-reinforcement-learning/) — accessed 2026-08-05
- [Hafner et al. — Dream to Control: Learning Behaviors by Latent Imagination (arXiv 1912.01603, ICLR 2020)](https://arxiv.org/abs/1912.01603) — accessed 2026-08-05
- [Hafner et al. — Mastering Atari with Discrete World Models (DreamerV2, arXiv 2010.02193)](https://arxiv.org/abs/2010.02193) — accessed 2026-08-05
- [Hafner et al. — Mastering Diverse Domains through World Models (DreamerV3, arXiv 2301.04104)](https://arxiv.org/abs/2301.04104) — accessed 2026-08-05
- [Hafner et al. — Mastering diverse control tasks through world models (Nature, 2025)](https://www.nature.com/articles/s41586-025-08744-2) — accessed 2026-08-05
- [Janner et al. — When to Trust Your Model: Model-Based Policy Optimization (MBPO, NeurIPS 2019)](https://arxiv.org/pdf/1906.08253) — accessed 2026-08-05
- [Bruce et al. — Genie: Generative Interactive Environments (arXiv 2402.15391, ICML 2024)](https://arxiv.org/abs/2402.15391) — accessed 2026-08-05
- [Google DeepMind — Genie 3: A new frontier for world models (5 August 2025)](https://deepmind.google/blog/genie-3-a-new-frontier-for-world-models/) — accessed 2026-08-05
- [TechTalks — The promise and limitations of DeepMind's Genie 3 (7 August 2025)](https://bdtechtalks.com/2025/08/07/deepmind-genie-3/) — accessed 2026-08-05
- [Kang, Yue et al. — How Far is Video Generation from World Model: A Physical Law Perspective (arXiv 2411.02385, ICML 2025)](https://arxiv.org/abs/2411.02385) — accessed 2026-08-05
- [PhyWorld project page — full results, ablations and community discussion](https://phyworld.github.io/) — accessed 2026-08-05
- [Bansal et al. — VideoPhy: Evaluating Physical Commonsense for Video Generation (arXiv 2406.03520)](https://arxiv.org/html/2406.03520v1) — accessed 2026-08-05
- [VideoPhy-2: A Challenging Action-Centric Physical Commonsense Evaluation in Video Generation (arXiv 2503.06800)](https://arxiv.org/pdf/2503.06800) — accessed 2026-08-05
- [PhyWorldBench: A Comprehensive Evaluation of Physical Realism in Text-to-Video Models (arXiv 2507.13428)](https://arxiv.org/pdf/2507.13428) — accessed 2026-08-05
- [Assran et al. — V-JEPA 2: Self-Supervised Video Models Enable Understanding, Prediction and Planning (arXiv 2506.09985)](https://arxiv.org/abs/2506.09985) — accessed 2026-08-05
- [Meta AI — Introducing the V-JEPA 2 world model and new benchmarks for physical reasoning](https://ai.meta.com/blog/v-jepa-2-world-model-benchmarks/) — accessed 2026-08-05
- [NVIDIA — Cosmos World Foundation Models](https://www.nvidia.com/en-us/ai/cosmos/) — accessed 2026-08-05
- [NVIDIA — World Simulation with Video Foundation Models for Physical AI (arXiv 2511.00062)](https://arxiv.org/abs/2511.00062) — accessed 2026-08-05

## Changelog
- 2026-08-05 — created
