# Vision-Language-Action Models: GR00T, RT-2, π0, and Embodied Agents

> **Track:** T26 Frontier AI · **Time:** 2.5h · **Prereqs:** `T26-world-models`, T05 transformers, T10 LLM serving · **Updated:** 2026-08-05
> **Module id:** `T26-vla-robotics` · **Tags:** vla, robotics, action-tokenisation, action-chunking, flow-matching, control-frequency, open-x-embodiment

## The 30-second version

A vision-language-action model is a VLM with an action head bolted on, and every interesting engineering decision in the field is one of three things: how you represent the action, how fast the policy has to emit it, and where the data came from. RT-2 (2023) proved the first point by literally reusing the 256 least-frequent tokens of a 55B PaLI-X vocabulary as action bins and running the whole thing at 1 to 3 Hz over a cloud TPU pod, which is fine for pick-and-place and useless for anything dynamic; π0 (2024) fixed the representation with a 300M-parameter flow-matching action expert glued to a 3B PaliGemma backbone that emits a 50-step action chunk in about 73 ms, giving 50 Hz effective control from a 3.3B model. The unlock in between is **action chunking**: predict `H` future actions from one observation rather than one, which cuts the compounding-error horizon by a factor of `H` and decouples your control frequency from your inference frequency, and ACT's ablation is the cleanest evidence (1% success at `k=1` versus 44% at `k=100` on their simulated suite). The data is the actual bottleneck and nobody has solved it: Open X-Embodiment pooled 60 datasets from 34 labs into 1M+ trajectories across 22 embodiments, which sounds enormous until you notice it is roughly three orders of magnitude smaller than a language pretraining corpus and was collected by humans teleoperating at real time. Be sceptical of every headline number you are quoted, because real-robot evaluation is expensive, non-reproducible, and reported on author-chosen suites with trial counts in the tens: 90% on 10 trials has a 95% confidence interval running from about 55% to 100%, and held-out-task success is routinely 30 to 50 points below the in-distribution number in the same table.

## Why this gets asked

Because a VLA is the first place where an LLM-serving engineer's instincts and a control engineer's instincts collide head-on, and the interviewer wants to see whether you can hold both. The serving instinct says "batch it, quantise it, add speculative decoding, ship a 7B model." The control instinct says "if the loop period jitters by 8 ms the arm oscillates and the gripper drops the mug." Both are right, and the whole discipline of VLA engineering is the negotiation between them. The interviewer at a robotics lab, a humanoid startup, or an embodied-AI team inside a frontier lab has personally lived a specific failure: a policy that scored beautifully on the demo table, was moved 30 cm to the left or had its camera nudged 5 degrees, and collapsed from 80% to 10% success. Or worse, a policy that was reported at 85% by the research team, then measured by the deployment team on 200 trials and came in at 41%, and the difference was that the researcher reset failed trials and the deployment team did not.

They probe four things in order. First, whether you treat action representation as a *design decision with measurable consequences* rather than an implementation detail. Second, whether you understand the control-frequency constraint quantitatively: a 7B autoregressive model emitting 7 tokens per step cannot run at 50 Hz on any hardware you will be given, and you should say why in numbers. Third, whether you treat data collection as the dominant cost line, because a candidate who has not costed teleoperation has not thought about the business. Fourth, the staff-level filter: whether you will tell them the truth about evaluation. Published success rates are not comparable across papers, and quoting them uncritically says you have never run a real eval.

Lean on your LLM-serving background explicitly. Action chunking is prefill amortisation. The two-system split is a draft-model/target-model decomposition with a hard real-time constraint on the draft. Temporal ensembling is an exponentially-weighted moving average over overlapping predictions. And the p99 discipline you already have matters *more* here than in serving, because a control loop that misses its deadline does not return a slow response, it returns a physically wrong one.

---

## Lineage: past → present → future

**What came before.** Two lineages died into this one. The first is **classical robot manipulation**: perception, then state estimation, then motion planning, then a hand-written controller, each stage a separate research field with its own conference. The pain that killed it was not that any stage was bad; it was that the interfaces between stages threw away information and that the pipeline needed a per-task engineer. To pick up a novel object you needed a pose estimator that knew about that object class, a grasp planner that knew about that geometry, and a task specification written in code. The unit of work was a task, and the marginal cost of task number 101 was the same as task number 1. The second lineage is **deep RL for manipulation**, roughly QT-Opt (Kalashnikov et al., 2018) through the domain-randomisation era of OpenAI's Dactyl (2018), which trained a Shadow Hand to reorient a cube using something on the order of 100 years of simulated experience. The pain there is on the record: QT-Opt used about **580,000 real grasp attempts collected over 800 robot-hours across 7 robots** and produced a policy that grasped well and did nothing else. Real-world RL burns hardware, needs resets, and the reward function is itself a research project. Sim-to-real works for locomotion and for contact-poor manipulation, and degrades badly for anything involving deformables, cloth, liquids, or the precise friction of a real drawer.

The pivot was **behaviour cloning at scale with a transformer**. Robotics Transformer 1 (RT-1, Brohan et al., December 2022) is the hinge: a **35M-parameter** EfficientNet-B3 with FiLM conditioning on a Universal Sentence Encoder embedding, a TokenLearner compressing 81 visual tokens to **8**, then a decoder-only transformer over a history of **6 images**, emitting **11 action dimensions** (7 arm: x, y, z, roll, pitch, yaw, gripper aperture; 3 base: x, y, yaw; 1 mode switch) each discretised into **256 uniform bins**. Trained on **~130,000 episodes covering 700+ tasks**, collected over **17 months** with a fleet of **13 robots**. It ran at **3 Hz** and reported roughly **97% success on seen tasks and 76% on unseen instructions** in the original paper. RT-1 established the recipe (tokenise the action, treat control as sequence modelling, scale the demonstrations) and established the ceiling: it generalised over *phrasings* of tasks it knew, not over the semantics of tasks it did not.

The specific pain RT-1 could not fix, and which motivated everything since: a 35M model trained only on robot data knows nothing about the world. Ask it to "move the apple to the Taylor Swift picture" and it has never seen Taylor Swift. The web-scale semantic prior lives in a VLM, and the entire VLA programme is the attempt to import it without destroying the motor skill on the way in.

**Where it stands now.** The consensus, and it is a real consensus as of 2026, has four load-bearing planks. Plank one: **start from a pretrained VLM, do not train from scratch.** Every serious model since RT-2 does this (RT-2 on PaLI-X 55B and PaLM-E 12B, OpenVLA on Llama-2-7B with a fused DINOv2 plus SigLIP visual encoder, π0 on PaliGemma 3B, GR00T N1 on NVIDIA Eagle-2 with a 1.34B VLM inside a 2.2B total). Plank two: **predict action chunks, not single actions.** ACT (Zhao et al., RSS 2023) made this unavoidable and π0's `H=50` is now typical; GR00T N1 uses an action horizon of **16**. Plank three: **the modern action head is continuous, and specifically it is a diffusion or flow-matching expert**, not a softmax over bins. Plank four: **pool data across embodiments**, which Open X-Embodiment (October 2023) turned from an aspiration into an artefact: **60 datasets, 34 labs, 1M+ trajectories, 22 embodiments, 527 skills, 160,266 tasks**.

The live disagreements are sharper than the consensus. **Disagreement one: discrete versus continuous actions.** The discrete camp points out that FAST (Physical Intelligence's DCT-based action tokeniser, 2025) recovered most of the flow-matching quality with a plain autoregressive head and vastly simpler training, and that discretisation lets you keep the VLM's original loss and vocabulary untouched. The continuous camp points at 50 Hz and at multimodality. Nobody has published a clean apples-to-apples comparison on the same backbone, same data, same eval suite, and until someone does, treat anyone with a strong opinion as underinformed. **Disagreement two: does cross-embodiment transfer actually work?** RT-X reported that RT-1-X beat the original per-dataset state-of-the-art by **50% on average across 5 datasets**, but the same paper reported that on the datasets with the *most* data, RT-1-X was **worse** than the original single-embodiment model. That is the sentence to memorise. Pooling helps low-data embodiments and can hurt high-data ones, which is a negative-transfer result hiding inside a positive-transfer headline. **Disagreement three: how big should the VLM be?** OpenVLA-7B beat RT-2-X-55B by **16.5 percentage points absolute across 29 tasks** with 7x fewer parameters, which either means scale does not help here or means data and recipe dominate scale at these sizes. **Disagreement four, and the loudest: evaluation.** There is no accepted benchmark. SIMPLER is the closest thing to a shared sim eval and multiple 2025-2026 studies found that every VLA scores substantially higher on SIMPLER than on comparable suites, attributed to its small number of environments and biased scenario selection.

What is actually deployed at scale, as opposed to published: much less than the reels suggest. π0 and π0.5 derivatives run in commercial pilots (laundry folding, dish loading, box assembly) under supervision. GR00T is shipped as an open checkpoint plus a post-training pipeline, which is a developer product rather than a deployed policy. Warehouse and logistics manipulation in production is still overwhelmingly classical perception plus planning with a learned grasp scorer, because the reliability bar is 99.9% and no VLA is close. If someone tells you VLAs are deployed at scale, ask for the fleet size and the intervention rate.

**Where it's heading.** High confidence (call it 85%): **the two-system split becomes universal architecture**, with a slow multimodal reasoner running at 1 to 10 Hz emitting a latent plan and a small fast expert running at 50 to 200 Hz consuming it. GR00T N1 already ships this explicitly (System 2 VLM, System 1 DiT at 120 Hz) and π0's backbone/expert split is the same idea with different framing. This is the same architecture as speculative decoding and the same architecture as a cascaded ranker, and it wins for the same reason: the expensive computation is not needed at the rate the cheap one is. High confidence (80%): **continuous action heads win for high-frequency dexterous work, discrete heads persist for low-frequency semantic work**, and the field stops arguing because the answer is "depends on your control rate," which is exactly the boring correct answer.

Medium confidence (60%): **evaluation gets fixed by real-to-sim, not by more real robots.** RobotArena-∞ (2025) and REALM (2025) are the direction, reconstructing real scenes into simulation so you can run thousands of trials reproducibly. Medium confidence (55%): **latent action pretraining from unlabelled human video becomes a standard data source**, because the teleoperation economics are brutal and inferring pseudo-actions from egocentric video is the only route to a genuinely large corpus (Genie's latent action model and LAPA are the templates). Genuinely speculative, and label it that way out loud: whether a single VLA checkpoint ever generalises to a *genuinely* novel embodiment with zero fine-tuning. Everything reported today as cross-embodiment either fine-tunes on the target or evaluates on an embodiment that was in the pooled training set. I know of no result where a policy was deployed on a robot morphology absent from training and worked. Also speculative: whether robot data scaling laws exist in a useful form. Nobody has published a clean loss-versus-data curve that predicts task success, and until they do, "just collect more data" is a strategy, not a plan.

---

## Mental model

```
A VLA IS A VLM WITH AN ACTION HEAD. That's it. Everything else is
consequences of that sentence colliding with a real-time deadline.

  images (1-3 cams)  ─┐
  language instruction ├──► [ VLM BACKBONE ]──► h ──► [ ACTION HEAD ] ──► a_{t:t+H}
  proprioception     ─┘      2B - 55B params            0.3B or a softmax
                             the SEMANTICS               the MOTOR SKILL

THE THREE QUESTIONS THAT DEFINE EVERY VLA
  1. HOW is the action represented?      (discrete bins | continuous | diffusion)
  2. HOW FAST must it come out?          (control frequency, in Hz, non-negotiable)
  3. WHERE did the data come from?       (teleop hours × $/hr, this is the real cost)

────────────────────────────────────────────────────────────────────────
QUESTION 1: ACTION REPRESENTATION

  (a) DISCRETE BINS  — RT-1, RT-2, RT-2-X, OpenVLA
      each of 7 dims ──► 256 uniform bins ──► one token each
      RT-2 trick: OVERWRITE the 256 least-used tokens of PaLI-X's vocab
                  (PaLM-E: overwrite 256 existing tokens instead)
      "1 128 91 241 5 101 127 217"  ← this string IS the action
      + zero architecture change, reuse the LM head and the LM loss
      + co-train on web VQA data for free (the whole point of RT-2)
      - 7 sequential decode steps per action = 7x the latency
      - quantisation floor: 256 bins over a joint range is ~0.4% resolution
      - a softmax over bins CAN be multimodal but only per-dimension
        (independent per-dim argmax on a bimodal task = the AVERAGE of two
         valid actions = a third, invalid action. this is the killer.)

  (b) CONTINUOUS REGRESSION HEAD — an MLP emitting R^{H×d}
      + one forward pass, no decode loop, fastest possible
      - L2 loss on multimodal demonstrations converges to the MEAN
        two humans go left and right around an obstacle -> policy goes through it

  (c) DIFFUSION / FLOW-MATCHING EXPERT — Diffusion Policy, π0, GR00T N1
      iteratively denoise a chunk of noise into an action chunk
      + genuinely multimodal, samples a MODE not a mean
      + continuous, no quantisation floor
      - N denoising steps per chunk (DDPM 100 → DDIM 10 → flow matching 10)
      - the N steps are on the SMALL expert only, not the whole VLM: cheap

────────────────────────────────────────────────────────────────────────
QUESTION 2: THE CONTROL-FREQUENCY CONSTRAINT (the hard part)

  A 7B model does NOT run at 50 Hz. Arithmetic, not opinion:
    50 Hz  =  20 ms budget per action, INCLUDING camera and comms
    OpenVLA-7B measured: 292 ms on an A6000  →  3.4 Hz
                         405 ms on an L4     →  2.5 Hz
                         ~160 ms optimised   →  6 Hz
    RT-2 at 55B: 1-3 Hz, over a multi-TPU CLOUD endpoint

  TWO WAYS OUT, and you need BOTH:

  WAY 1: ACTION CHUNKING — amortise the forward pass over H steps
     one inference emits a_t .. a_{t+H-1}; execute them open-loop
     effective control rate = H / latency
     π0: H=50 chunk in 73 ms  →  685 actions/sec available  →  50 Hz easily
     COST: the last action in the chunk is (H × dt) seconds stale.
           at 50 Hz and H=50 that is 1.0 s of open-loop blindness.

  WAY 2: TWO-SYSTEM SPLIT — decouple the rates
     ┌──────────────────────────────┐
     │ SYSTEM 2  VLM  1-10 Hz       │  "what should I be doing"
     │ 1.3B-55B, sees language+scene│   emits latent plan / embedding
     └───────────┬──────────────────┘
                 │ latent (cached, reused for K fast steps)
     ┌───────────▼──────────────────┐
     │ SYSTEM 1  action expert      │  "what torque, right now"
     │ 0.3B, DiT/flow, 50-120 Hz    │   sees proprio at full rate
     └──────────────────────────────┘
     GR00T N1: System 1 DiT runs at 120 Hz. Same shape as spec decoding.

────────────────────────────────────────────────────────────────────────
QUESTION 3: WHERE THE DATA COMES FROM (the actual bottleneck)

  robot data does NOT exist on the internet. every trajectory was
  produced by a human moving a robot IN REAL TIME. there is no
  Common Crawl for torque.

  scale reality check:
    Llama-3 pretraining      ~15,000,000,000,000 tokens
    Open X-Embodiment        ~1,000,000 trajectories  (60 datasets, 34 labs)
    π0 proprietary corpus    ~903M timesteps ≈ 10,000 hours
    RT-1                     130k episodes over 17 months on 13 robots

  10,000 hours of teleop at ~1 operator-hour per robot-hour is ~5 person-YEARS
  of continuous work, before annotation, resets, or failures. THAT is why
  this field looks the way it does.

────────────────────────────────────────────────────────────────────────
THE LINEAGE IN ONE COLUMN
  RT-1     '22  35M   tokenise actions, 130k eps, 3 Hz     → sequence modelling works
  RT-2     '23  55B   reuse VLM vocab as action bins       → web semantics transfer
  RT-X     '23   —    pool 60 datasets, 22 embodiments     → cross-embodiment data
  OpenVLA  '24  7B    open weights, beat 55B by 16.5pp     → open + smaller wins
  π0       '24  3.3B  flow-matching expert, H=50, 50 Hz    → continuous head, real rate
  π0.5     '25  3.3B  knowledge insulation, new homes      → open-world generalisation
  GR00T N1 '25  2.2B  explicit 2-system, DiT at 120 Hz     → humanoid, open checkpoint
```

---

## How it actually works

### Action tokenisation, derived from the constraint that produced it

Start from the problem RT-2 actually faced, because the solution is only elegant once you see the constraint. You have PaLI-X, a 55B vision-language model that has been trained on web-scale image-text data and knows what a Taylor Swift picture is. You want it to output a robot action. You have roughly 130k robot episodes, which is nothing compared to the pretraining corpus. If you add a new output head and train it, two things go wrong: the new head has no pretraining signal, and the gradient from the robot loss flows back into the backbone and degrades the visual-semantic knowledge you were trying to import (this specific pathology is what π0.5's "knowledge insulation" later attacks directly).

RT-2's move is to change nothing. Represent the action **as text**, in the model's existing vocabulary, and train with the model's existing next-token loss. Mechanically:

1. Take the action vector. For the mobile manipulator it is 8 dimensions: `[terminate, Δx, Δy, Δz, Δroll, Δpitch, Δyaw, gripper]`, where terminate is a discrete episode-end flag and the rest are continuous deltas.
2. Discretise each continuous dimension uniformly into **256 bins** over the range observed in training data (RT-1 used the same 256-bin scheme over 11 dimensions).
3. Map each bin index to a token. In **PaLI-X**, integers up to 1000 already have dedicated tokens, so bin `k` is just the token for the string `k`. In **PaLM-E**, which lacks that property, they **overwrite the 256 least-frequently-used tokens in the existing vocabulary** with action bins.
4. The target string for one timestep is `"terminate Δx Δy Δz Δroll Δpitch Δyaw gripper"`, for example `"1 128 91 241 5 101 127 217"`. Standard cross-entropy over that string. Done.
5. **Co-fine-tune**, do not fine-tune. RT-2 trains on robot data *and* the original web VQA/captioning data simultaneously, with the robot fraction increased over training. Fine-tuning on robot data alone measurably destroys the semantic generalisation that was the entire point.

That last step is the one candidates skip and the one interviewers care about. The generalisation results only exist because of co-training. RT-2 roughly doubled generalisation performance over RT-1 on unseen objects, backgrounds and environments (approximately **62% versus 32%** on the aggregate unseen split), and reported around a **3x** improvement on the "emergent skills" evaluations that require web knowledge (symbol understanding, reasoning, human recognition) where RT-1 was essentially at chance.

Now the costs, which are where the senior conversation lives.

**Cost one: sequential decoding.** An action is 7 to 11 tokens, so one action is 7 to 11 sequential forward passes through a 55B model. This is the decode-bound regime you know from LLM serving, except the "user" is a physical arm with a deadline. RT-2 at 55B ran at **1 to 3 Hz** from a multi-TPU cloud endpoint, meaning the robot had a network round trip inside its control loop; the 5B variant ran around **5 Hz**. The paper's own ablation concludes that at or above 10 Hz you should drop the image history and use single-frame inputs with vectorised action tokens.

**Cost two: the quantisation floor.** 256 bins gives `range/256`, roughly **0.4%** of the range per bin. Irrelevant for coarse pick-and-place. For threading a cable into a connector with a 1 mm tolerance over a ±10 cm action range, one bin is 0.78 mm and you are at the quantisation limit before making a single modelling error. Shrinking the range fixes it and caps your maximum velocity.

**Cost three, the one people get wrong: per-dimension independence.** A softmax over 256 bins *can* be multimodal within a dimension, and greedy decoding picking one of two modes on a single axis is fine. The problem is across axes. Mode A is `(Δy=+0.05, Δz=+0.02)`, mode B is `(Δy=-0.05, Δz=-0.02)`. Autoregressive decoding conditioned on previously emitted dimensions handles this *if* the model learned the conditional. A parallel independent head picks `(+0.05, -0.02)`, which is neither mode and is a collision. That is the concrete reason "just add an MLP head" fails and the reason diffusion heads exist.

**The 2025 improvement worth knowing: FAST.** Physical Intelligence's frequency-space tokeniser applies a discrete cosine transform to the action chunk, quantises the DCT coefficients, and byte-pair-encodes the result. The motivating observation is sharp: at 50 Hz, consecutive actions are nearly identical, so a naively binned chunk is highly redundant and the model spends its capacity predicting that nothing changed. DCT plus BPE compresses a 50-step chunk into a far shorter sequence and reportedly makes autoregressive VLAs competitive with diffusion ones while training substantially faster. Same insight as "do not tokenise audio in the time domain."

### Continuous heads and flow matching, mechanically

The alternative is to stop pretending actions are words.

**The naive continuous head** is an MLP mapping the backbone's hidden state to `R^{H×d}`, trained with L2 or L1 loss. It is one forward pass, no decode loop, and it is the fastest thing you can build. It also fails on any task with genuine demonstration multimodality, because the minimiser of expected squared error is the conditional mean, and the mean of "go left" and "go right" is "go straight into the obstacle." L1 loss gives you the conditional median, which is better (the median of a bimodal distribution is at least sometimes near a mode) and is why several strong policies use L1 rather than L2. This is the identical pathology to blurred video prediction in `T26-world-models`: an averaging loss on multimodal data returns the average.

**Diffusion Policy** (Chi et al., RSS 2023) fixed it by making the action head a conditional denoiser. You sample `A^{(K)} ~ N(0, I)` of shape `H×d` and run `K` denoising steps conditioned on the observation embedding, each step `A^{(k-1)} = α(A^{(k)} - γ ε_θ(A^{(k)}, k, o))+ noise`. Because you are sampling from a learned distribution rather than regressing its mean, you get a mode. The cost is `K` network evaluations per chunk: DDPM at **100 steps** is far too slow, DDIM at **10 steps** is usually acceptable.

**π0's flow matching** is the version to know, because it is what shipped. Instead of a diffusion noise schedule, train a conditional velocity field. Sample `τ ~ Beta(1.5, 1)` biased toward low `τ` (early, noisy timesteps get more weight), form `A^τ = τ A_noise + (1-τ) A_true`, and regress the network's output `v_θ(A^τ, τ, o)` against the target velocity `u = A_noise - A_true`. At inference, integrate from `τ=1` to `τ=0` with forward Euler at a fixed step size; π0 uses **10 integration steps**. The architecture detail that makes it fast is the important one: the denoising network is **not the whole VLM**. π0 is a mixture-of-experts-shaped model where the **3B PaliGemma backbone (2.291B trainable)** processes images and language once, and a separate **300M-parameter (0.315B) action expert** with its own transformer weights processes proprioception and the noisy action tokens. Only the action expert runs the 10 integration steps. The backbone's KV cache is computed once and attended to.

Do that arithmetic, because it is the whole argument: 10 denoising steps on a 300M expert is roughly the cost of 1 forward pass on a 3B model, so the total is roughly 2 backbone-equivalents rather than 10. Measured: π0 emits a **50-action chunk in about 73 ms** on a consumer RTX-class GPU with three camera inputs. At 50 Hz that chunk covers 1.0 second of motion, so you need a new inference every ~1 s while having 73 ms of compute, a **13x** headroom factor. That headroom is what lets you do real-time chunking (start the next inference while executing the current chunk) and hide latency entirely.

**π0.5's two changes**, both small and both instructive. It discretises the robot's proprioceptive state into **256 bins over [-1, 1]** and injects it as discrete tokens in the *language prefix* rather than through a separate encoder, which means the state goes through the pretrained backbone's attention rather than around it. And it replaces MLP-based timestep fusion with **AdaRMSNorm** timestep conditioning, borrowed straight from the DiT literature. The headline capability is that it performs long-horizon mobile manipulation (cleaning kitchens and bedrooms) in **entirely unseen homes**, trained on a corpus where **97.6% of the data came from sources other than mobile manipulators** and only about **400 hours** was actual mobile-manipulator data. That ratio is the interesting number: the mobile-manipulation capability is mostly transferred, not directly demonstrated.

### Action chunking: why predicting a horizon beats predicting a step

This is the single highest-leverage idea in the module and it is underexplained everywhere. There are four independent reasons chunking wins, and a strong answer names at least three.

**Reason 1: it divides the compounding-error horizon by H.** Behaviour cloning suffers covariate shift: a small error puts the policy slightly off the demonstration manifold, where its error is larger, which compounds. The classical result (Ross and Bagnell) is that BC error grows `O(ε T²)` over a `T`-step episode where a non-compounding policy would be `O(ε T)`. If each *decision* commits `H` steps, there are only `T/H` decisions, so the quadratic term shrinks by `H²`; at `T=1000, H=50` that is a 2,500x reduction. This is `T26-world-models`' rollout-horizon arithmetic run in the opposite direction, and the sign flips because the policy is not accumulating its own prediction errors during the chunk, it is executing a plan conditioned on a single real observation.

**Reason 2: it handles non-Markovian demonstrations.** Human teleoperators pause, hesitate mid-reach, adjust their grip. A single-step policy sees the same observation paired with both "move" and "don't move" and predicts the average, giving a slow, hesitant, sometimes stalled policy. This is the direct cause of the "policy stalls mid-trajectory" failure below. Chunking absorbs the pause into the unit: the model predicts "pause then continue" as one object rather than deciding, from a static image, whether this is a pausing moment.

**Reason 3: it amortises inference.** One forward pass buys `H` control steps.

**Reason 4: it produces temporally coherent trajectories,** because the chunk is generated jointly rather than as `H` independent decisions.

The evidence is ACT's ablation (Zhao et al., RSS 2023), and quote it precisely because the magnitude is startling: success on their simulated evaluation went from **1% at k=1 to 44% at k=100**, averaged across settings, tapering slightly for larger `k`. One percent to forty-four from a single architectural change. On real ALOHA hardware ACT reported **80% to 95%** on tasks like slotting a battery, against baselines in the single digits to low tens. Note that the 44% and the 80-95% are different task suites, which is exactly the comparability problem this module keeps returning to. Do not put them on the same axis.

**The tradeoff, stated honestly.** A chunk is open loop. At 50 Hz with `H=50` the final action executes **1.0 second** after the observation that produced it, so a hand entering the workspace 200 ms in is invisible. Larger `H` gives better compounding-error properties and worse reactivity, bounded above by how fast your environment changes. Static tabletop tolerates `H=50`; a handover with a moving human does not. GR00T N1's `H=16` is a different point on that curve.

### Temporal ensembling, and why naive chunk replacement oscillates

Executing chunks back-to-back creates a discontinuity at every boundary. Chunk `i` ends at some predicted state; chunk `i+1` is generated from a fresh observation and may start somewhere slightly different. The commanded trajectory has a step change at each boundary, which the low-level controller sees as a velocity impulse. The observable symptom is a visible jerk every `H` steps, and with a stiff controller, an oscillation.

ACT's fix is **temporal ensembling**. Run inference *every* timestep rather than every `H` timesteps, so that at time `t` you hold `H` overlapping predictions for `a_t`, one from each of the last `H` chunks. Combine them with an exponentially-decaying weighted average, `w_i = exp(-m·i)` where `i` indexes how old the prediction is, normalised. Smaller `m` weights old predictions more (smoother, more lag); larger `m` weights the newest prediction more (more reactive, less smooth). ACT reported temporal ensembling adds about **3.3 percentage points**, which is a modest gain in the success metric and a much larger gain in trajectory smoothness that the success metric does not capture.

The cost is that you have given back the inference amortisation: you are now running the model at the full control rate. This is only viable if a single inference fits inside the control period, which is exactly why ACT (a ~80M-parameter model on ALOHA at 50 Hz) can do it and a 7B VLA cannot.

The practical middle ground, and the one most production stacks land on, is **asynchronous chunk overlap**: execute chunk `i` while computing chunk `i+1`, and blend the overlap region over a short window (typically the first 4 to 10 steps of the new chunk) with a linear or cosine crossfade. You get boundary smoothness without running inference at the control rate. π0's real-time-chunking work formalises this. State it in interviews as "double-buffer the chunk and crossfade the seam" and the analogy to audio buffer underrun will land immediately with anyone who has done streaming.

### The control-frequency constraint, in numbers

This is the section where your serving background is worth the most, and it is where most ML candidates fall apart because they have never had a hard deadline.

**The budget.** A control loop at frequency `f` gives you a period of `1/f`. That period must contain: camera exposure and readout, image transport, preprocessing, model inference, postprocessing, network transport to the robot controller, and the controller's own cycle. Not just inference.

```
CONTROL PERIOD BUDGET

    f        period     realistic non-inference overhead     inference budget
    3 Hz     333 ms     ~40 ms                                ~293 ms
   10 Hz     100 ms     ~30 ms                                 ~70 ms
   30 Hz      33 ms     ~20 ms                                 ~13 ms
   50 Hz      20 ms     ~15 ms                                  ~5 ms
  100 Hz      10 ms     ~8 ms                                   ~2 ms
  200 Hz       5 ms     ~4 ms                                   ~1 ms

camera alone: a 30 fps global-shutter USB3 camera contributes ~33 ms of
sampling latency plus 5-15 ms of transport. At 50 Hz your camera is already
the slowest thing in the loop unless you bought a 120 fps one.
```

**What the models actually measure.** These are the numbers to carry.

| Model | Params | Reported inference | Effective rate | Notes |
|---|---|---|---|---|
| RT-1 | 35M | ~ | **3 Hz** | on-robot, EfficientNet-B3 backbone |
| RT-2 (PaLI-X 55B) | 55B | ~ | **1-3 Hz** | multi-TPU **cloud** endpoint, network in the loop |
| RT-2 (5B variant) | 5B | ~ | **~5 Hz** | still cloud-served |
| OpenVLA-7B | 7B | **292 ms** on A6000 | 3.4 Hz | 7 action tokens, autoregressive |
| OpenVLA-7B | 7B | **405 ms** on L4 24GB | 2.47 Hz | commodity inference GPU |
| OpenVLA-7B optimised | 7B | ~160 ms | ~6 Hz | with batching/compile tricks |
| π0 | 3.3B | **73 ms** for H=50 | **50 Hz** effective | 3 cams, 10 flow steps on 300M expert |
| GR00T N1 System 1 | 2.2B total | ~ | **120 Hz** DiT | System 2 VLM runs far slower |

Three lessons fall straight out of that table.

**Lesson one: single-step autoregressive VLAs are stuck below 10 Hz and always will be.** OpenVLA at 292 ms is not a bad implementation; it is 7 sequential decode steps through a 7B model plus a vision encoder. INT4 plus torch-compile moves 292 ms to maybe 120 ms. It does not move it to 20 ms, because that is a factor of 2 to 3, not 15. Same wall as LLM decode latency, same cause: memory-bandwidth-bound on weight reads with no arithmetic-intensity relief at batch size 1, which is what a single robot is. A 7B model in FP16 is 14 GB; at ~2 TB/s HBM one full weight read is ~7 ms and you need 7 of them, so ~49 ms is the *hardware floor* before any inefficiency. Real numbers land 5x above it.

**Lesson two: chunking is the only thing that breaks the wall for a large model.** π0's 73 ms is not 15x faster per forward pass than OpenVLA's 292 ms; it is roughly 4x faster per pass (smaller model, no decode loop) and then divided by 50 because one pass buys 50 actions. `Effective rate = H / latency`. Write that on the whiteboard.

**Lesson three: for genuine closed-loop reactivity above ~20 Hz you need the two-system split, not a faster big model.** Deciding *what* to do (which drawer, which object, did the instruction change) changes on a timescale of hundreds of milliseconds to seconds. Deciding *torque right now* has to happen at 100 Hz because that is the timescale of contact dynamics and compliance. Running both at the higher rate is waste; running both at the lower rate is physically incorrect.

The engineering pattern, which is worth spelling out because it is exactly your speculative-decoding intuition:

```
ASYNCHRONOUS TWO-SYSTEM CONTROL LOOP  (this is the shape you should draw)

  thread A  (slow, 1-10 Hz, GPU)
     ┌─ grab latest frame set + instruction
     ├─ VLM forward pass  (50-300 ms)
     ├─ write latent plan z into a lock-free double buffer
     └─ loop
                        │
                        │ z  (stale by up to one A-period; that is FINE)
                        ▼
  thread B  (fast, 50-200 Hz, hard real-time)
     ┌─ read proprioception (joint pos/vel/torque) at full rate
     ├─ read latest z from buffer (never blocks, never waits)
     ├─ action expert forward pass  (1-5 ms)
     ├─ send joint command, respect the deadline
     └─ loop

  RULES THAT MAKE THIS WORK
   1. thread B NEVER blocks on thread A. If z is stale, use stale z.
   2. thread B is pinned, isolated core, SCHED_FIFO, no GC, no malloc
      in the hot path, no Python GIL contention.
   3. thread A's output is a LATENT, not a target pose. A stale target
      pose is a wrong command; a stale intent is still roughly right.
   4. measure JITTER (std of period), not just mean latency. A p99 of
      25 ms on a 20 ms budget means 1% of your commands are late, and
      late commands are what causes oscillation.
```

Point 4 deserves emphasis because it is the thing an LLM-serving person underweights. In serving, a p99 spike is a slow response. In control, a late command means the controller either holds the previous command (producing a velocity discontinuity) or extrapolates (producing an overshoot). Do it repeatedly at a rate near the arm's mechanical resonance and you get sustained oscillation. **Jitter is a first-class metric here and mean latency is not sufficient.** Practically: run the fast loop in C++ or Rust, not Python; if it must be Python, pre-allocate every buffer, disable the cyclic GC in the hot loop, and expect to fight the GIL. A 200 Hz loop has a 5 ms period and CPython can lose 5 ms to a GC pass.

### The data problem, which dominates everything

Every architectural argument above is second-order compared to this. There is no internet-scale corpus of robot actions, there never will be one that arrives for free, and every trajectory in every dataset named in this module was produced by a human moving a robot in real time.

**The cost model.** One hour of teleoperation produces one hour of trajectory data, minus resets, minus failures you discard, minus setup. Realistic yields on a well-run bimanual setup are in the range of **30 to 60 demonstrations per operator-hour** for short (10 to 30 second) tasks, dropping to a handful per hour for long-horizon tasks. At a fully loaded operator cost of roughly **$25 to $60 per hour** (this is my estimate from public job postings and lab budgets, not a published figure, so present it as an order-of-magnitude), plus hardware amortisation and a supervising engineer, **usable robot data lands somewhere in the $50 to $200 per hour range**. π0's ~10,000 hours of proprietary data is therefore a **multi-million-dollar** data asset before you count the robots, and roughly **five person-years** of continuous teleoperation. That is the real moat in this field, and it is why Physical Intelligence's valuation is a data valuation rather than a model valuation.

**The scale gap, stated plainly.** Llama-3-class pretraining is on the order of **15 trillion tokens**. Open X-Embodiment is **~1 million trajectories**; at maybe 200 to 500 timesteps each that is on the order of **10^8 to 10^9** timesteps. If you generously call a timestep a token, robot data is **four to five orders of magnitude** smaller than language data. This is why every VLA starts from a pretrained VLM: the robot data is enough to learn a motor mapping and nowhere near enough to learn what a stapler is.

**Open X-Embodiment is the pooled-data answer.** Released October 2023 by a collaboration of **34 labs**, pooling **60 existing datasets** into a single RLDS-format corpus: **1M+ real robot trajectories, 22 embodiments** (single arms, bimanual, quadrupeds), **527 skills**, **160,266 tasks**. The engineering contribution is underrated and worth naming: they standardised heterogeneous action spaces, control frequencies, camera configurations, and gripper conventions into one schema. That normalisation work is most of why the dataset is usable, and it is the part you would actually be hired to do.

**Does cross-embodiment transfer work? Read the RT-X results carefully.** The headline is that **RT-1-X outperformed the original per-dataset state-of-the-art method by about 50% on average across 5 evaluated datasets**, and that **RT-2-X showed roughly 3x improvement on emergent-skill evaluations** over models trained on a single embodiment. Both are real. But the paper is honest about the qualification, and this is the sentence that separates a candidate who read the paper from one who read the abstract: **on the datasets with the most data, RT-1-X performed worse than the original single-embodiment model.** Positive transfer for data-poor embodiments, negative transfer (or at least no benefit) for data-rich ones. The mental model is the multilingual-model one you already have: pooling helps low-resource languages and can cost you on high-resource ones, and the mitigation is the same (upweight the target embodiment during fine-tuning, or accept a per-embodiment head). Also note the capacity dependence: RT-2-X at 55B did not show the same degradation, suggesting the negative transfer is partly a capacity problem rather than a data-conflict problem. That is a testable claim and nobody has cleanly tested it.

The deeper honesty: **no published result shows transfer to an embodiment absent from training.** Every "cross-embodiment" number is either an embodiment that was in the pooled corpus or one that received fine-tuning data. What is demonstrated is *co-training benefit across a fixed set of embodiments*, which is valuable and is not the same claim as morphology-general robotics.

**The escape routes people are betting on**, in order of how much I believe them:

1. **Simulation and synthetic data.** Cheap and infinitely resettable, with a sim-to-real gap for contact-rich manipulation that has resisted a decade of work. This is the sibling module's territory (`T26-nvidia-cosmos`, Isaac Sim, synthetic trajectory generation) and I will not duplicate it. The point *for the policy side*: synthetic data changes the data economics without touching the action-representation or control-frequency constraints at all.
2. **Human video.** Tens of thousands of hours of egocentric manipulation video (Ego4D, EPIC-Kitchens) exist with no action labels. Latent-action pretraining (LAPA, and Genie's latent action model from `T26-world-models`) infers a discrete pseudo-action from consecutive frames via a VQ-VAE, pretrains on that space, then maps to real actions with a little labelled robot data. The mapping step is where it currently loses.
3. **Play data and autonomous collection.** Act semi-randomly or under a weak policy and relabel post-hoc with hindsight. Cheap per hour, low information density.
4. **Cheaper teleoperation hardware.** ALOHA's underrated contribution: a **~$20,000** bimanual rig at **50 Hz** is roughly an order of magnitude cheaper than research-grade alternatives, which changes how many hours a lab can afford. Cost reduction is a real lever and gets no papers.

### Evaluation, which is genuinely unsolved

Be blunt about this in an interview. It is the fastest way to signal that you have actually operated a system rather than read about one.

**Problem one: real-robot evaluation does not reproduce.** A trial depends on lighting, object pose, gripper wear, cable drag, ambient temperature affecting servo torque, and who reset the scene. Two runs of the *same policy* on the *same task* a week apart routinely differ by 10 to 20 percentage points. There is no seed you can set.

**Problem two: trial counts are tiny and confidence intervals are never reported.** A typical VLA paper reports success over **10 to 50 trials per task**. Do the binomial arithmetic once and you will never read a robotics table the same way:

```
95% CONFIDENCE INTERVAL ON A REPORTED SUCCESS RATE (Wilson interval)

  observed    n=10           n=20           n=50          n=200
   90%      [ 60%,  98%]   [70%,  97%]   [79%, 96%]    [85%, 94%]
   80%      [ 49%,  94%]   [58%,  92%]   [67%, 89%]    [74%, 85%]
   50%      [ 24%,  76%]   [30%,  70%]   [36%, 64%]    [43%, 57%]

  → to distinguish an 80% policy from a 70% policy at p<0.05 you need
    roughly n=300 PER ARM. Nobody runs 300 real trials per arm. Nobody.
  → a paper claiming "+8 points over baseline" on n=20 has measured noise.
```

At 30 seconds per trial plus 30 seconds of reset, 300 trials is **5 hours of continuous robot time for one number**. A 10-task suite with 2 policies is 100 hours. That is why nobody does it, and that is why the field's tables are not comparable.

**Problem three: sim benchmarks do not transfer.** SIMPLER is the most-used real-to-sim eval, and multiple 2025-2026 studies found all VLAs score substantially higher on it than on comparable benchmarks, attributed to its small number of test environments, single viewpoint, and biased scenario selection. LIBERO, the other common suite, is fully synthetic. A policy tuned against a sim benchmark is tuned against that benchmark's renderer and physics engine.

**Problem four: every paper picks its own suite.** RT-2's emergent-skills evaluations, OpenVLA's 29-task cross-embodiment set, π0's laundry-folding and box-assembly tasks, and GR00T's humanoid suite share almost no tasks. Cross-paper success-rate comparison is not meaningful; say so rather than reciting a leaderboard.

**Problem five, the one that matters commercially: the held-out number is far below the headline.** In-distribution tasks (same objects, scene and camera pose as training) report 80 to 95%. Swap in an unseen object instance and you typically lose 15 to 30 points; change the scene and you lose more. Novel task plus novel scene routinely lands **30 to 60 points below** the in-distribution number, and the abstract almost always quotes the in-distribution one. RT-2 illustrates the good case at about 62% on the aggregate unseen split versus RT-1's 32%, and note that 62% is the *improved* number: it still fails more than a third of the time on things it has not seen. For a warehouse needing 99.9%, that is not a product.

**What a defensible eval protocol looks like**, and this is strong to propose unprompted in a system-design round:

- **Pre-register the task list, the scene randomisation procedure, and `n`** before running anything, or you are selecting tasks post-hoc.
- **Report Wilson confidence intervals, always.** If the interval overlaps the baseline's, the result is not significant.
- **Randomise object and initial robot pose from a scripted distribution**, executed by a script, not by a human's idea of "roughly here."
- **Stratify into in-distribution, novel-object, and novel-scene**, and report all three. A single aggregate hides everything that matters.
- **Report interventions per hour and MTBF**, not just binary success. A policy that succeeds 80% of the time but needs a human to untangle it on 5% of trials has a very different operational cost from one that just drops the object.
- **Log and version everything**: camera intrinsics and extrinsics, gripper serial, firmware, ambient lux. That is how you explain a 15-point move next month.

---

## Build it from scratch

The smallest thing that is genuinely a VLA and not a toy: a frozen vision-language backbone, a flow-matching action expert, action chunking, and an async two-rate control loop. Everything here is deliberately stripped so the moving parts are visible. Matching lab folder: `(lab pending)`.

```python
# untested sketch -- minimal flow-matching VLA with action chunking.
# Deliberately omits: real vision encoder, proper attention masking between
# backbone and expert, EMA, and the discrete-token baseline.
import torch
import torch.nn as nn
import torch.nn.functional as F

H = 50          # action chunk horizon (pi0 uses 50; GR00T N1 uses 16)
ACT_DIM = 7     # 6-DoF delta pose + gripper
STATE_DIM = 14  # bimanual joint positions
D = 512         # expert width
FLOW_STEPS = 10 # Euler integration steps at inference (pi0 uses 10)


class ActionExpert(nn.Module):
    """The SMALL fast head. ~0.3B in pi0; ~5M here so it is readable.
    It cross-attends to the backbone's cached prefix and self-attends
    over [state, noisy_action_chunk]."""

    def __init__(self, ctx_dim):
        super().__init__()
        self.state_in = nn.Linear(STATE_DIM, D)
        self.act_in = nn.Linear(ACT_DIM, D)
        self.tau_in = nn.Linear(1, D)                       # timestep conditioning
        self.ctx_proj = nn.Linear(ctx_dim, D)
        layer = nn.TransformerDecoderLayer(D, 8, 4 * D, batch_first=True)
        self.blocks = nn.TransformerDecoder(layer, num_layers=6)
        self.out = nn.Linear(D, ACT_DIM)

    def forward(self, ctx, state, a_noisy, tau):
        """ctx (B,L,ctx_dim) frozen backbone prefix. a_noisy (B,H,ACT_DIM).
        tau (B,1) in [0,1]. Returns predicted velocity field (B,H,ACT_DIM)."""
        mem = self.ctx_proj(ctx)
        tok = self.act_in(a_noisy) + self.tau_in(tau).unsqueeze(1)
        tok = torch.cat([self.state_in(state).unsqueeze(1), tok], dim=1)
        h = self.blocks(tgt=tok, memory=mem)
        return self.out(h[:, 1:])                            # drop the state slot


def flow_loss(expert, ctx, state, a_true):
    """Conditional flow matching. a_true (B,H,ACT_DIM), already normalised
    per-dimension to roughly unit scale -- skip that and training diverges."""
    B = a_true.shape[0]
    # pi0 samples tau from a Beta biased toward LOW tau (noisy end) because
    # that is where the integration error concentrates.
    tau = torch.distributions.Beta(1.5, 1.0).sample((B, 1)).to(a_true.device)
    noise = torch.randn_like(a_true)
    t = tau.view(B, 1, 1)
    a_tau = t * noise + (1.0 - t) * a_true                   # linear path
    target_v = noise - a_true                                # constant velocity
    return F.mse_loss(expert(ctx, state, a_tau, tau), target_v)


@torch.no_grad()
def sample_chunk(expert, ctx, state, steps=FLOW_STEPS):
    """Integrate tau: 1 -> 0 with forward Euler. THIS is the inference-time
    cost, and it runs on the EXPERT ONLY -- ctx was computed once."""
    B = state.shape[0]
    a = torch.randn(B, H, ACT_DIM, device=state.device)
    dt = 1.0 / steps
    for i in range(steps):
        tau = torch.full((B, 1), 1.0 - i * dt, device=state.device)
        a = a - dt * expert(ctx, state, a, tau)
    return a                                                 # (B,H,ACT_DIM)
```

The control loop is where the module's real content lives, and it is the part nobody writes down.

```python
# untested sketch -- async two-rate loop. Thread B must NEVER block on A.
import threading, time, collections

class ChunkBuffer:
    """Lock-free-ish double buffer. Thread A writes, thread B reads.
    A stale chunk is always better than a blocked control loop."""
    def __init__(self):
        self._cur = None          # (chunk_tensor, t0_monotonic)
        self._lock = threading.Lock()

    def publish(self, chunk, t0):
        with self._lock:          # held for ~microseconds, never over I/O
            self._cur = (chunk, t0)

    def read(self):
        with self._lock:
            return self._cur


def slow_thread(vlm, expert, cams, robot, buf, hz=5):
    period = 1.0 / hz
    while True:
        start = time.monotonic()
        ctx = vlm.encode(cams.latest(), robot.instruction)   # 50-300 ms
        chunk = sample_chunk(expert, ctx, robot.state())     # 5-70 ms
        buf.publish(chunk.cpu().numpy(), time.monotonic())
        time.sleep(max(0.0, period - (time.monotonic() - start)))


def fast_thread(robot, buf, hz=50, blend=6):
    """Executes the chunk. Crossfades the seam when a new chunk lands."""
    period = 1.0 / hz
    prev_cmd, prev_chunk_id, blend_left = None, None, 0
    deadline = time.monotonic()
    while True:
        deadline += period
        item = buf.read()
        if item is None:
            robot.hold(); _sleep_until(deadline); continue
        chunk, t0 = item
        idx = int((time.monotonic() - t0) * hz)
        if idx >= len(chunk):
            # chunk EXHAUSTED and no new one arrived. This is the stall.
            robot.hold()                                     # do NOT extrapolate
            _sleep_until(deadline); continue
        cmd = chunk[idx]
        if id(chunk) != prev_chunk_id:
            prev_chunk_id, blend_left = id(chunk), blend
        if blend_left > 0 and prev_cmd is not None:
            w = blend_left / blend                           # linear crossfade
            cmd = w * prev_cmd + (1.0 - w) * cmd
            blend_left -= 1
        robot.send(cmd)
        prev_cmd = cmd
        late = time.monotonic() - deadline
        if late > 0.2 * period:
            LATE_COUNTER.inc()        # export this. jitter is a real metric.
        _sleep_until(deadline)
```

Four things in that loop are load-bearing and are exactly what an interviewer probes.

**Step 1. Indexing the chunk by wall-clock, not by loop iteration.** `idx = (now - t0) * hz`. If the fast thread skips a cycle, the chunk index still advances correctly and the arm ends up where it should be in time, rather than lagging by however many cycles were dropped. Indexing by a counter accumulates drift.

**Step 2. Holding, not extrapolating, on chunk exhaustion.** When the slow thread is late and the chunk runs out, the physically safe behaviour is to hold the last commanded position. Extrapolating the trajectory forward is the tempting choice and it is how you drive an arm into a table.

**Step 3. Crossfading the seam.** Six steps of linear blend at 50 Hz is 120 ms, which is enough to absorb a discontinuity without meaningfully delaying a new intent.

**Step 4. Exporting a late-command counter.** You will not debug oscillation without it. The symptom (arm buzzes) and the cause (2% of commands arrive after their deadline) are not connected by intuition.

---

## How it's done in production

**The open stack.** `openpi` (Physical Intelligence, Apache-2.0) ships π0, π0-FAST and π0.5 checkpoints with JAX training and PyTorch inference, plus a client/server split where the policy runs on a GPU box and the robot talks to it over a websocket. That split is the honest admission that the policy does not fit on the robot. `Isaac GR00T N1.5-3B` (NVIDIA, Hugging Face) ships a checkpoint, a post-training recipe, and the `EmbodimentTag` mechanism for adding a new robot's state and action dimensions without touching the backbone. `LeRobot` (Hugging Face) is the glue: the de-facto `LeRobotDataset` schema, ACT/Diffusion-Policy/π0 implementations, and teleoperation and recording scripts. `OpenVLA` gives you the discrete-token baseline plus a LoRA path that fine-tunes a 7B VLA on a single 24 GB consumer GPU.

**What the frameworks add over your own loop:** an embodiment adapter layer so a new robot is a config change; per-embodiment normalisation statistics computed and versioned (get these wrong and the policy is silently broken, see the failure table); a batching inference server and websocket protocol so the GPU is off the robot; and eval harnesses. What they do *not* give you is the hard-real-time fast loop, which every serious deployment writes itself in C++ or Rust.

**The fine-tuning recipe people actually run**, because "train a VLA" almost never means pretraining:

1. Collect **50 to 200 demonstrations** of your target task on your target robot. This is the number that surprises people: post-training a pretrained VLA on a new task genuinely works in the low hundreds of demos, which is 2 to 6 operator-hours, not 6 months.
2. Compute per-dimension normalisation statistics (usually 1st and 99th percentile, not min/max, so one bad demo does not squash the range) and store them *with the checkpoint*.
3. LoRA on the backbone (rank 16 to 32 is typical), full fine-tune on the action expert. Freezing the backbone entirely costs you accuracy; full fine-tuning it costs you the semantic generalisation, which is the pathology π0.5's knowledge insulation targets.
4. Evaluate against the pre-registered protocol above. Expect the first honest number to be roughly half what the demo video suggested.

### Failure-mode table

| Symptom | Cause | Fix |
|---|---|---|
| **Policy stalls mid-trajectory.** Arm freezes partway to the object, gripper open, and never recovers. Commanded deltas are near zero for hundreds of consecutive steps. | Demonstration data contains operator pauses. A single-step (or short-chunk) policy sees near-identical observations paired with both "move" and "don't move" actions; the regression head converges to the mean, which near a pause is approximately zero. Absorbing states are self-reinforcing: predicting zero keeps the observation identical, so it predicts zero again. | Increase the action chunk (`H=1` to `H=50` is the single biggest lever; ACT measured 1% to 44%). Filter near-zero-motion segments out of training data, or subsample them. Switch from an L2 regression head to a flow-matching/diffusion head so you sample a mode rather than a mean. As a last-resort runtime guard, detect `N` consecutive sub-threshold commands and inject a small exploration nudge or trigger a re-plan. |
| **Compounding error over a long horizon.** Success is 85% on a 10-second task and 15% on the same skill chained into a 60-second task. Failures cluster near the end. | Covariate shift. BC error grows `O(ε T²)`: small deviations put the robot in states absent from the demonstration manifold, where error is larger. Long-horizon tasks also have no intermediate reward or reset. | Chunk (divides the compounding term by `H²`). Decompose the task into sub-goals and re-condition the VLM on a language sub-instruction per segment (the RT-H / hierarchical approach), which resets the effective horizon. Collect *recovery* data: deliberately perturb the robot mid-task and demonstrate the recovery, which is the DAgger insight applied by hand. Add a high-level monitor that detects "not making progress" and re-plans rather than pushing through. |
| **Policy only works from the training camera pose.** 80% success on the rig as built; move the wrist camera 2 cm or rotate the third-person camera 5 degrees and it drops to 10 to 20%. Predicted actions are systematically offset in one axis. | The policy learned a mapping from *image pixels* to *actions in the robot's frame* and absorbed the camera extrinsics into its weights as a constant. Nothing forced it to learn a 3D-consistent representation, and the training data had exactly one camera pose. This is the single most common real-world VLA failure. | Randomise camera extrinsics during data collection (this is the real fix and it is a data-collection decision, not a modelling one). Use a wrist-mounted camera as the primary view, since it is rigidly attached and its extrinsics never drift. Apply strong photometric plus random-crop/resize augmentation at train time. Add proprioception to the input so the policy is not purely visual. Version and check camera extrinsics at policy load and refuse to run if they differ from the recorded values by more than a threshold. Verify normalisation statistics match the checkpoint, since a stats mismatch produces the same systematic-offset symptom and is far easier to fix. |
| **Control-loop jitter causing oscillation.** Arm buzzes or visibly vibrates, especially when holding position or near contact. Audible whine from the servos. Command timestamps show a p99 period well above the mean. | Late commands. The controller either holds (velocity discontinuity) or extrapolates (overshoot), and if the resulting excitation is near the arm's mechanical resonance the error is reinforced each cycle. Root causes in order of likelihood: Python GC pause in the hot loop, GIL contention with the inference thread, non-isolated CPU core, chunk-boundary discontinuity with no crossfade, and temporal-ensembling gain `m` set too high. | Move the fast loop out of Python, or pre-allocate all buffers, `gc.freeze()` and `gc.disable()` in the hot path. Pin the loop to an isolated core with `SCHED_FIFO` and `isolcpus`. Crossfade chunk boundaries over 4 to 10 steps. Add first-order low-pass filtering or explicit velocity/acceleration limits on the commanded trajectory. Export period jitter (std and p99) as a metric and alert on it. If oscillation persists at a fixed frequency, that frequency is the mechanical resonance: notch-filter it or lower the controller gains. |
| **Policy succeeds in sim, fails on hardware.** 90%+ on LIBERO or SIMPLER, 20 to 30% on the real robot doing the "same" task. | Sim-to-real gap in contact dynamics, friction and rendering, plus benchmark inflation: multiple studies found all VLAs score substantially higher on SIMPLER than on comparable suites due to limited environments and biased scenarios. | Treat sim numbers as a regression gate (did I break something?), never as a performance estimate. Real-to-sim reconstruction of your actual scenes (RobotArena-∞, REALM) is closer to honest. Always co-report a small real-robot number. |
| **New embodiment performs worse after adding pooled data.** Fine-tuning on OXE plus your data underperforms training on your data alone. | Negative transfer, exactly as RT-X measured on their most data-rich datasets. Action-space and control-frequency conventions differ across pooled sources and conflict. | Upweight your target embodiment in the sampling mix; verify action normalisation and control-frequency resampling are consistent across sources; consider a per-embodiment head over a shared trunk. Run the your-data-only versus pooled ablation before assuming pooling helps. |
| **Gripper misses by 1 to 3 cm or drops the object on lift.** | Two causes you must separate. Systematic miss in one direction is calibration or normalisation. Random miss is depth ambiguity: a single RGB camera at a shallow angle underdetermines distance. | Systematic: recheck extrinsics and normalisation stats. Random: add a wrist camera (resolves depth by proximity), a second viewpoint, or force/torque sensing so the policy closes on contact rather than at a predicted position. |

---

## Tradeoffs & when NOT to use it

**Do not use a VLA when a classical pipeline meets the spec.** Known objects, estimable poses, fixed task set: perception plus motion planning gives **99%+ reliability with a deterministic, debuggable failure mode**, against a VLA's 60 to 90% and an opaque one. Bin picking of known SKUs is a solved classical problem and replacing it with a VLA is a downgrade dressed as innovation. The VLA buys *breadth over unstructured tasks*, and if you do not need breadth you are paying for it in reliability.

**Do not use a large VLA above ~20 Hz when you cannot chunk.** Force-controlled insertion, in-hand manipulation, dynamic catching and legged locomotion need 100 to 1000 Hz closed loops with genuine contact reactivity. A chunked policy is open loop within the chunk, which is precisely wrong when the interesting information arrives mid-chunk. Locomotion remains owned by sim-trained RL policies running small MLPs at 50 to 200 Hz on-board, and that is correct. The VLA's role in a humanoid is manipulation and task-level reasoning, not the balance controller.

**Do not use a VLA when the safety case requires verifiable behaviour.** You cannot write a proof about a 3B transformer. Where failure means injury or expensive damage, the VLA sits *inside* an envelope enforced classically: joint limits, velocity and force caps, workspace geometry checks, and a control-loop watchdog, all outside the model and all able to veto its command. Present it as an architecture, not a caveat.

**Do not fine-tune on 20 demonstrations and expect generalisation.** You get a policy that works on that exact table with that exact object under that exact lighting. The realistic floor for surviving an object swap is 100 to 200 demonstrations *with deliberate variation*, and variation matters more than count: 50 demos across 10 object instances and 5 lighting conditions beats 200 of the identical setup.

**Do not assume a bigger backbone is better.** OpenVLA-7B beat RT-2-X-55B by 16.5 points absolute across 29 tasks. Data quality, recipe and action representation dominate parameter count at these scales, and every extra billion parameters is directly a control-frequency tax. Default to the smallest backbone that carries the semantics you need.

**Do not build a teleoperation stack before checking the economics.** 500 hours of demonstration is roughly 3 person-months and, at $50 to $200 per usable hour, $25k to $100k of data. For a single task, classical engineering usually wins on cost. VLAs amortise across tasks, and one task has no amortisation.

**Where the honest counter-argument sits.** The classical argument weakens fast as task count grows and specifiability falls. Across 500 loosely-specified household tasks no amount of classical engineering scales, and a 70% VLA that improves with data beats a 99% pipeline covering 12 of the 500. The right framing is not "VLA versus classical" but "what is the marginal cost of task N+1 in each approach," with the crossover somewhere in the tens of tasks. Say it that way.

---

## Interview questions

### Q1 — What is a vision-language-action model, and what makes it different from a VLM?
**Testing:** Whether you can state the thing in one sentence without hand-waving.
**Answer:** A VLA is a vision-language model whose output space is robot actions instead of text. Same backbone, same multimodal input (images plus a natural-language instruction, usually plus proprioception), different head. The reason to start from a VLM rather than train from scratch is that robot data is four to five orders of magnitude smaller than language data (Open X-Embodiment is ~1M trajectories against Llama-3's ~15T tokens), so the semantic knowledge has to be imported. RT-2 made the strongest version of this argument by encoding actions in the VLM's own token vocabulary so the pretrained weights and loss function are literally unchanged, and it roughly doubled generalisation on unseen objects and backgrounds over RT-1 (about 62% versus 32%).
**Follow-up trap:** *"If it's just a VLM with a different head, why can't I take GPT-4 class model, add a head, and be done?"* Because of the deadline. A VLM answers when it answers; a policy must answer inside the control period. A 55B RT-2 ran at 1 to 3 Hz over a cloud TPU endpoint, which is fine for pick-and-place and useless for anything reactive. The action head is not the hard part; the latency budget and the action *representation* are. Say that and then pivot into chunking.

### Q2 — Walk me through RT-2's action tokenisation. Why reuse existing tokens?
**Testing:** Do you know the actual mechanism, or just the headline.
**Answer:** Each continuous action dimension is discretised into 256 uniform bins over its training-data range. RT-1 did this over 11 dimensions; RT-2's mobile manipulator uses 8 (terminate flag, 6-DoF delta pose, gripper). Each bin index becomes a token, and the action for one timestep is a string like `"1 128 91 241 5 101 127 217"`. In PaLI-X, integers up to 1000 already have dedicated tokens, so no vocabulary change is needed at all. PaLM-E lacks that property, so they overwrite the 256 least-frequently-used tokens in the existing vocabulary. The point of reusing tokens is that nothing about the architecture, the output head, or the loss function changes, which means you can **co-fine-tune** on web VQA data and robot data simultaneously with one loss.
**Follow-up trap:** *"Why does co-fine-tuning matter? Why not just fine-tune on robot data?"* Because fine-tuning on robot data alone measurably destroys the semantic generalisation that was the entire reason to start from a VLM. The emergent-skill results (roughly 3x over RT-1 on symbol understanding and reasoning tasks) exist because of co-training. This is catastrophic forgetting, and π0.5's "knowledge insulation" is a later, more principled attack on the same problem.

### Q3 — Give me three concrete downsides of discrete action tokens.
**Testing:** Whether you can criticise the approach you just explained.
**Answer:** One, sequential decoding: 7 to 11 tokens per action means 7 to 11 forward passes, which is the single largest latency multiplier in the stack. Two, quantisation floor: 256 bins is roughly 0.4% of the range per bin, so on a ±10 cm range a bin is 0.78 mm, and precision insertion tasks are at the quantisation limit before any modelling error. Three, and the subtle one, per-dimension independence: a softmax per dimension can be multimodal within a dimension, but if you decode dimensions in parallel (or the model has not learned the cross-dimension conditional) you can pick mode A's `Δy` and mode B's `Δz`, producing an action that is in neither mode. Half the demos go left, half go right, and you emit "straight into the obstacle."
**Follow-up trap:** *"Doesn't autoregressive decoding over dimensions fix the third problem?"* In principle yes, and that is one of the reasons RT-2 decodes autoregressively rather than with parallel heads. In practice it fixes it only if the model has actually learned the conditional, and it costs you exactly the latency from problem one. So the two problems trade against each other, which is why the field moved to diffusion and flow-matching heads that get joint multimodality in a fixed small number of steps.

### Q4 — Explain action chunking. Why does it help so much?
**Testing:** The central concept. Expect this in every VLA interview.
**Answer:** Predict a horizon of `H` future actions from one observation and execute them, rather than one action per observation. Four independent reasons it helps. First, compounding error: behaviour cloning error grows `O(ε T²)`, and committing `H` steps per decision cuts the number of decisions to `T/H`, shrinking the quadratic term by `H²`. Second, non-Markovian demonstrations: human teleoperators pause, so the same observation maps to both "move" and "don't move," and a single-step policy learns the average, which is a stall. Chunking absorbs the pause into the unit. Third, inference amortisation: effective control rate is `H / latency`, which is the only way a 3B model reaches 50 Hz. Fourth, temporal coherence, because the chunk is generated jointly. ACT's ablation is the number: **1% success at `k=1`, 44% at `k=100`**, averaged across settings.
**Follow-up trap:** *"So use a huge H?"* No. A chunk is open loop. At 50 Hz with `H=50` the last action executes 1.0 second after the observation that produced it, so anything that changes in that second is invisible to the robot. `H` is bounded above by how fast your environment changes. Static tabletop work tolerates `H=50`; a handover with a moving human does not. GR00T N1 uses `H=16`. The honest answer is that `H` is a reactivity-versus-stability dial, not a free win.

### Q5 — What is temporal ensembling and what does it cost?
**Testing:** Depth on chunking, and whether you notice the cost.
**Answer:** Run inference every timestep instead of every `H` timesteps. At time `t` you then hold `H` overlapping predictions for `a_t`, one from each of the last `H` chunks, and you combine them with an exponentially-decaying weighted average `w_i ∝ exp(-m·i)` over prediction age. Smaller `m` is smoother with more lag; larger `m` is more reactive and less smooth. ACT measured about **+3.3 percentage points** in success, and a much larger improvement in trajectory smoothness that the success metric does not capture. The cost is that you have thrown away the entire inference-amortisation benefit: you are now running the model at the full control rate. ACT can afford that because it is a small model on 50 Hz hardware. A 7B VLA cannot.
**Follow-up trap:** *"What do you do instead for a big model?"* Asynchronous chunk overlap. Double-buffer: execute chunk `i` while computing chunk `i+1`, and crossfade the first 4 to 10 steps of the new chunk against the tail of the old one. You get the boundary smoothness without inference at the control rate. If you skip the crossfade you get a velocity discontinuity at every chunk boundary, which is a visible jerk every `H` steps and, with a stiff controller, an oscillation.

### Q6 — I want a 7B VLA running at 50 Hz. How do you do it?
**Testing:** The core systems question. This is where your serving background pays.
**Answer:** You do not, not directly. 50 Hz is a 20 ms period, and after camera and transport overhead you have maybe 5 ms of inference budget. A 7B model in FP16 is 14 GB of weights; at ~2 TB/s of HBM bandwidth a single full weight read is ~7 ms, and if you decode 7 action tokens that is a ~49 ms hardware floor before any inefficiency. Measured reality is worse: OpenVLA-7B is 292 ms on an A6000 and 405 ms on an L4, giving 2.5 to 3.4 Hz. Quantisation and compilation buy a factor of 2 to 3, not 15. Two things actually work, and you need both. Chunking: one forward pass buys `H` control steps, so the effective rate is `H / latency`; π0 emits a 50-action chunk in 73 ms, which is 685 actions per second of capacity. And the two-system split: a slow VLM at 1 to 10 Hz emitting a latent plan, and a small action expert at 50 to 200 Hz consuming it plus full-rate proprioception. GR00T N1 ships this explicitly with the System 1 DiT at 120 Hz.
**Follow-up trap:** *"Isn't the stale latent from the slow system a correctness problem?"* Only if you make the slow system emit a *target pose*, in which case a stale target is a wrong command. Make it emit an *intent or latent plan*, and a 200 ms stale intent is still roughly right, because intent changes on a timescale of hundreds of milliseconds while torque changes on a timescale of milliseconds. The architectural rule is: the fast loop consumes proprioception at full rate and the slow loop's output at whatever rate it arrives, and it never blocks waiting for it.

### Q7 — π0 uses flow matching. What is it doing, and why not just regress the action?
**Testing:** Whether you understand the multimodality argument.
**Answer:** Regression with an L2 loss converges to the conditional mean of the demonstrations. If half the demonstrations go left around an obstacle and half go right, the mean goes through the obstacle. This is the identical failure as blurred video prediction: an averaging loss on multimodal data returns the average, and the average is not a valid sample. Flow matching instead learns a conditional velocity field. Training: sample `τ ~ Beta(1.5, 1)` biased toward the noisy end, form `A^τ = τ·noise + (1-τ)·A_true`, regress the network output against `noise - A_true`. Inference: integrate `τ` from 1 to 0 with forward Euler, **10 steps** in π0. Because you are sampling from a learned distribution you get a mode, not a mean.
**Follow-up trap:** *"Ten denoising steps sounds slow. How is that faster than 7 autoregressive tokens?"* Because the 10 steps run on the **action expert only**, which is 300M parameters (0.315B) out of π0's 3.3B, while the 3B PaliGemma backbone runs once and its KV cache is reused across all 10 steps. Ten passes over 300M is roughly one pass over 3B, so the total is about 2 backbone-equivalents, not 10. That architectural separation, not the loss function, is what makes it fast. Measured: 73 ms for a 50-action chunk.

### Q8 — Open X-Embodiment pooled 60 datasets. Does cross-embodiment transfer actually work?
**Testing:** Whether you read past the abstract. This is a strong differentiator.
**Answer:** Partially, and the paper is honest about the limit. The dataset is 60 datasets from 34 labs, 1M+ trajectories, 22 embodiments, 527 skills, 160,266 tasks. RT-1-X beat the original per-dataset state-of-the-art by about **50% on average across 5 evaluated datasets**, and RT-2-X showed roughly **3x** improvement on emergent-skill evaluations over single-embodiment training. But on the datasets with the **most** data, RT-1-X was **worse** than the original single-embodiment model. So: positive transfer for data-poor embodiments, negative transfer for data-rich ones. It is the multilingual-model pattern exactly, and the mitigations are the same, namely upweight the target embodiment or use a per-embodiment head over a shared trunk.
**Follow-up trap:** *"Would it transfer to a robot morphology that was not in the training set at all?"* No published result shows that. Every reported cross-embodiment number is either on an embodiment present in the pooled corpus or one that received fine-tuning data. What is demonstrated is co-training benefit across a fixed embodiment set, which is genuinely useful and is a different claim from morphology-general robotics. If a candidate claims otherwise, ask for the citation.

### Q9 — A team reports 90% success on their new policy. What do you ask?
**Testing:** Evaluation rigour. The staff-level filter.
**Answer:** Five questions, in order. How many trials? At `n=10`, a 90% observation has a 95% Wilson interval of roughly [60%, 98%], so it is compatible with a 65% policy. What was the task suite, and was it fixed before you ran? Author-chosen suites post-hoc are selection. Is that in-distribution, novel-object, or novel-scene? The gap is routinely 30 to 60 points and the headline is almost always in-distribution. How were failed trials handled, were they reset and retried, and does the denominator include them? And what is the intervention rate and MTBF, because a policy that succeeds 80% of the time but needs a human to untangle it on 5% of trials has a very different operational cost from one that just drops the object.
**Follow-up trap:** *"Fine, they ran 50 trials. Now is +8 points over baseline significant?"* No. To separate an 80% policy from a 72% one at p<0.05 you need on the order of 300 trials per arm. At 30 seconds per trial plus 30 seconds of reset, 300 trials is 5 hours of continuous robot time for one number, and a 10-task two-policy comparison is 100 hours. Nobody runs that, which is precisely why the field's tables are not comparable and why "we beat X by 8 points" is usually a measurement of noise.

### Q10 — Your policy stalls halfway to the object and never recovers. Debug it.
**Testing:** The named failure mode. Can you go from symptom to mechanism.
**Answer:** First confirm the symptom in the logs: commanded deltas near zero for hundreds of consecutive steps while the observation is essentially static. That signature means an absorbing state, not a hardware fault. The dominant cause is operator pauses in the demonstration data. The teleoperator hesitated, so the same observation appears paired with both "move" and "don't move," and a regression head predicts the average, which near a pause is approximately zero. It is self-reinforcing: predicting zero keeps the observation identical, so the next prediction is also zero. Fixes in order of leverage: increase the action chunk (`H=1 → 50` is the biggest single lever; ACT saw 1% to 44%), filter or subsample near-zero-motion segments out of training, and switch from an L2 head to flow matching so you sample a mode rather than a mean. A runtime guard that detects `N` consecutive sub-threshold commands and triggers a re-plan is a mitigation, not a fix.
**Follow-up trap:** *"You added chunking and it still stalls at exactly the same point in the trajectory."* Then it is not a data-averaging problem, it is a visual one: something at that point in the trajectory is out of distribution, most likely occlusion of the target by the gripper as it approaches. Check whether the wrist camera view at the stall point resembles anything in training. The fix is a viewpoint or a proprioception input, not more chunking.

### Q11 — The policy works at 80% on our rig and 15% after we moved the camera 2 cm. Why?
**Testing:** The most common real deployment failure.
**Answer:** The policy learned a mapping from image pixels to actions in the robot's frame and absorbed the camera extrinsics into its weights as a constant. Nothing in behaviour cloning forces a 3D-consistent representation, and if the training data had exactly one camera pose there was no pressure to learn one. The symptom confirms it: predicted actions are systematically offset in one axis rather than randomly wrong. The real fix is a data-collection decision, namely randomise camera extrinsics during collection. Secondary fixes: prefer a wrist-mounted camera whose extrinsics are rigidly fixed and cannot drift, apply aggressive random-crop and photometric augmentation, and feed proprioception so the policy is not purely visual. Operationally, version the camera calibration with the checkpoint and refuse to load the policy if the live extrinsics differ beyond a threshold.
**Follow-up trap:** *"We didn't move the camera and it still dropped."* Then check the normalisation statistics first, because a mismatch between the per-dimension action normalisation used at training and at inference produces the identical systematic-offset symptom and is a five-minute fix. After that, check for anything else that changed the image statistics: lighting, a new table surface, a firmware update to the camera's auto-exposure. Auto-exposure and auto-white-balance are a genuinely underrated source of silent distribution shift; lock them.

### Q12 — Design the serving architecture for a fleet of 50 robots running a 3B VLA.
**Testing:** Systems design where your serving experience is directly transferable.
**Answer:** Do not put a GPU on every robot. Split by rate: the fast loop on every robot, the slow loop in a shared pool. On-robot, a hard-real-time process (C++ or Rust, `SCHED_FIFO`, isolated core) runs the action expert at 50 to 100 Hz against a locally cached latent, reads proprioception at full rate, enforces joint/velocity/force limits outside the model, and holds on chunk exhaustion rather than extrapolating. Off-robot, a GPU pool serves the VLM backbone at 1 to 10 Hz per robot, which is 50 to 500 aggregate RPS of independent requests, so continuous batching is a straight win here in a way it is not for a single robot at batch size 1. Autoscale on queue depth and target p99 rather than mean, because a p99 miss is one stale intent (survivable) while a systematic miss is a fleet-wide slowdown.
**Follow-up trap:** *"What happens when the network drops for 500 ms?"* The fast loop keeps running on the last latent, and the current chunk covers `H·dt` seconds, so `H=50` at 50 Hz gives 1.0 second of buffer. Beyond that the robot transitions to a safe hold: it must not extrapolate and must not replay the last chunk. The design rule is that every layer degrades to a *safe* state rather than a *plausible* one, and the fast loop needs its own watchdog on latent staleness that trips independently of what the network stack reports.

### Q13 — GR00T N1 versus π0. What is actually different?
**Testing:** Whether you can compare architectures rather than recite marketing.
**Answer:** Same family, different emphases. π0 is 3.3B: a 3B PaliGemma backbone (2.291B trainable) plus a 300M flow-matching action expert, `H=50`, 10 integration steps, ~73 ms per chunk, trained on ~10,000 hours (~903M timesteps) of mostly proprietary data with roughly 9.1% from open sources including OXE, Bridge and DROID. GR00T N1 is 2.2B total with a 1.34B Eagle-2 VLM as System 2 and a flow-matching diffusion transformer as System 1, action horizon 16, System 1 at 120 Hz, plus an `EmbodimentTag` mechanism with per-embodiment encoders and decoders so variable state and action dimensions are a config change; N1.5 is the 3B successor. Substantive differences: GR00T makes the two-system split architectural where π0 makes it a weight partition; GR00T is open-weights with a post-training recipe where π0's data is proprietary; GR00T targets humanoids and π0 targets tabletop and mobile manipulation.
**Follow-up trap:** *"Which one would you pick?"* It is determined by the embodiment, so do not answer without asking what robot they have. Humanoid with many DoF and an Isaac-based simulation pipeline: GR00T, for the embodiment adapters and the synthetic-trajectory tooling. Bimanual tabletop arm with real teleoperation data: π0/π0.5 through `openpi`, for the stronger demonstrated open-world results and the simpler serving path.

### Q14 — When would you tell a team not to use a VLA at all?
**Testing:** Judgement. The senior signal.
**Answer:** When a classical pipeline meets the spec. If the objects are known, the poses are estimable, and the task set is fixed, perception plus motion planning gives 99%+ reliability with a debuggable failure mode, against a VLA's 60 to 90% and an opaque one. Bin picking of known SKUs is a solved classical problem and replacing it with a VLA is a downgrade. Also: when the control requirement is above ~20 Hz with genuine mid-loop reactivity (force-controlled insertion, in-hand manipulation, locomotion), because a chunk is open loop precisely when the interesting information arrives. Also: when the safety case requires verifiable behaviour, in which case the VLA must sit inside an envelope enforced by classical limit checks that can veto its command. And when you have one task, because a VLA's whole economic argument is amortisation across tasks and one task has no amortisation.
**Follow-up trap:** *"So VLAs are a research toy?"* No, and do not overcorrect. The classical argument collapses as task count grows and specifiability falls. At 500 loosely-specified household tasks, no amount of classical engineering scales, and a 70% policy that improves with data beats a 99% pipeline covering 12 of the 500. The right framing is the marginal cost of task N+1 in each approach, and the crossover is somewhere in the tens of tasks. Give the number and the framing, not a verdict.

### Q15 — What is the single biggest constraint on this field, and what would you do about it?
**Testing:** Whether you identify data rather than architecture. Almost everyone says architecture.
**Answer:** Data, by a wide margin. There is no internet-scale corpus of robot actions, because every trajectory in every dataset named here was produced by a human moving a robot in real time. One operator-hour yields roughly 30 to 60 short demonstrations; at $50 to $200 per usable hour including hardware and supervision, π0's ~10,000 hours is a multi-million-dollar asset and about five person-years of teleoperation. The scale gap against language pretraining is four to five orders of magnitude, which is why every VLA starts from a pretrained VLM. In expected-value order I would: invest in data *variation* over *volume* (50 demos across 10 object instances beats 200 of one setup); randomise camera extrinsics and lighting at collection, since that is where the most common deployment failure originates; pursue latent-action pretraining from unlabelled human video (LAPA, Genie-style latent action models) as the only route to genuinely large corpora; and drive teleoperation hardware cost down, because ALOHA's ~$20,000 bimanual rig at 50 Hz changed what a lab could afford more than most modelling papers did.
**Follow-up trap:** *"Won't simulation solve this?"* It changes the economics without touching the other two constraints, and the sim-to-real gap for contact-rich manipulation is the problem it has been for a decade. Synthetic data is strong for scene and object diversity and anything geometric, and weakest exactly where manipulation is hardest: friction, deformables, contact transitions. A multiplier on real data, not a replacement, and always co-report a real-hardware number.

---

## Red flags that fail you

- "We'll just run the 7B model at 50 Hz on the robot." You have not done the arithmetic. State the 20 ms budget out loud.
- Quoting a success rate without the trial count, the task suite, or whether it is in-distribution. At `n=10`, 90% and 65% are statistically indistinguishable.
- "Action representation is an implementation detail." It determines your latency, your precision floor, and whether you can represent multimodal behaviour at all.
- Claiming cross-embodiment transfer works, full stop. It works for data-poor embodiments in the pooled set and can be *negative* for data-rich ones; RT-X measured exactly that.
- Proposing an MLP regression head on multimodal demonstration data without mentioning mode averaging.
- Treating sim benchmark numbers as performance estimates. They are regression gates. Every VLA scores materially higher on SIMPLER than on comparable suites.
- Not mentioning proprioception. A purely visual policy is why the camera-pose failure exists.
- Optimising mean latency and never measuring jitter. In control, p99 misses cause oscillation, not just slowness.
- "More parameters will fix it." OpenVLA-7B beat RT-2-X-55B by 16.5 points absolute across 29 tasks.
- Proposing a VLA for a fixed, known, specifiable task where a classical pipeline hits 99%.
- Extrapolating the trajectory when the chunk runs out. That is how you drive an arm into a table. Hold.
- Saying "we'll collect more data" without costing it. 500 hours is roughly 3 person-months and $25k to $100k.

## Cheat card

```
VLA = VLM + action head. Three questions: representation, rate, data.

ACTION REPRESENTATION
  discrete bins   256 bins/dim, RT-1 (11 dims), RT-2 (8 dims)
                  RT-2: reuse 256 rarest tokens (PaLI-X) / overwrite (PaLM-E)
                  cost: 7-11 sequential decodes; 0.4%/bin quantisation floor
  continuous MLP  1 pass, but L2 loss -> conditional MEAN -> mode averaging
  flow/diffusion  pi0: 10 Euler steps on a 300M expert, 3B backbone cached
                  Diffusion Policy: DDPM 100 steps -> DDIM 10
  FAST (2025)     DCT + BPE on the chunk; makes autoregressive competitive

ACTION CHUNKING     effective control rate = H / latency
  ACT ablation      1% @ k=1  ->  44% @ k=100 ; temporal ensembling +3.3pp
  BC error O(eps*T^2) -> chunking cuts the quadratic term by H^2
  cost: last action is H*dt stale. H=50 @ 50Hz = 1.0 s open loop.
  pi0 H=50 | GR00T N1 H=16
  temporal ensembling: w_i ~ exp(-m*i) over prediction age; needs inference
                       at the CONTROL rate -> only for small models

CONTROL FREQUENCY   50 Hz = 20 ms period; ~5 ms inference budget after overhead
  RT-1 35M              3 Hz
  RT-2 PaLI-X 55B       1-3 Hz   (cloud multi-TPU, network in the loop)
  RT-2 5B               ~5 Hz
  OpenVLA-7B            292 ms A6000 (3.4 Hz) | 405 ms L4 (2.47 Hz)
  pi0 3.3B              73 ms for a 50-chunk -> 50 Hz effective
  GR00T N1 System 1     120 Hz DiT
  7B FP16 = 14 GB; 2 TB/s HBM -> ~7 ms/pass floor; x7 tokens = ~49 ms floor

TWO-SYSTEM SPLIT    S2 VLM 1-10 Hz emits LATENT (not a pose) ; S1 expert 50-200 Hz
  fast loop NEVER blocks on slow loop. stale intent > blocked loop.
  hold on chunk exhaustion, never extrapolate. measure JITTER not just mean.

DATA (the real bottleneck)
  Open X-Embodiment  60 datasets, 34 labs, 1M+ traj, 22 embodiments,
                     527 skills, 160,266 tasks
  RT-1               130k episodes, 700+ tasks, 13 robots, 17 months
  pi0                ~903M timesteps ~= 10,000 h ; 9.1% open / 90.9% proprietary
  pi0.5              ~400 h mobile-manip; 97.6% of data from OTHER sources
  OpenVLA            970k episodes, 7B, beat RT-2-X-55B by +16.5 pp on 29 tasks
  teleop yield ~30-60 demos/operator-hour ; ~$50-200 per usable hour (estimate)
  fine-tune a pretrained VLA: 50-200 demos is genuinely enough for a new task
  RT-X CAVEAT: RT-1-X beat SOTA by ~50% avg, but was WORSE on the
               most-data-rich datasets. negative transfer is real.

EVALUATION (unsolved)
  Wilson 95% CI at 90% observed:  n=10 [60,98] | n=50 [79,96] | n=200 [85,94]
  distinguishing 80% from 70% at p<0.05 needs ~n=300 PER ARM. nobody does it.
  held-out task success is typically 30-60 pp BELOW the headline
  SIMPLER inflates all VLAs (few envs, one viewpoint, biased scenarios)
  report: in-dist / novel-object / novel-scene, + interventions per hour

FAILURE SIGNATURES
  stall            near-zero deltas for 100s of steps -> operator pauses, mean
                   averaging -> chunk it, filter pauses, use flow matching
  long-horizon     85% @ 10 s, 15% @ 60 s -> covariate shift -> subgoals+chunk
  camera pose      systematic one-axis offset -> extrinsics baked in -> randomise
                   (check normalisation stats FIRST, same symptom, 5-min fix)
  oscillation      p99 period >> mean -> late commands -> C++ loop, isolcpus,
                   SCHED_FIFO, crossfade 4-10 steps at chunk seams
```

## Sources

- [RT-1: Robotics Transformer for Real-World Control at Scale](https://arxiv.org/abs/2212.06817) — accessed 2026-08-05
- [RT-2: Vision-Language-Action Models Transfer Web Knowledge to Robotic Control (CoRL 2023 proceedings PDF)](https://proceedings.mlr.press/v229/zitkovich23a/zitkovich23a.pdf) — accessed 2026-08-05
- [RT-2 project page](https://robotics-transformer2.github.io/) — accessed 2026-08-05
- [Open X-Embodiment: Robotic Learning Datasets and RT-X Models (arXiv 2310.08864)](https://arxiv.org/abs/2310.08864) — accessed 2026-08-05
- [Open X-Embodiment project page](https://robotics-transformer-x.github.io/) — accessed 2026-08-05
- [Scaling up learning across many different robot types (DeepMind blog)](https://deepmind.google/blog/scaling-up-learning-across-many-different-robot-types/) — accessed 2026-08-05
- [OpenVLA: An Open-Source Vision-Language-Action Model (arXiv 2406.09246)](https://arxiv.org/abs/2406.09246) — accessed 2026-08-05
- [OpenVLA project page](https://openvla.github.io/) — accessed 2026-08-05
- [openvla/openvla GitHub repository](https://github.com/openvla/openvla) — accessed 2026-08-05
- [π0: A Vision-Language-Action Flow Model for General Robot Control (arXiv 2410.24164)](https://arxiv.org/abs/2410.24164) — accessed 2026-08-05
- [Physical-Intelligence/openpi GitHub repository (π0, π0-FAST, π0.5)](https://github.com/Physical-Intelligence/openpi) — accessed 2026-08-05
- [GR00T N1: An Open Foundation Model for Generalist Humanoid Robots (arXiv 2503.14734)](https://arxiv.org/abs/2503.14734) — accessed 2026-08-05
- [nvidia/GR00T-N1.5-3B model card](https://huggingface.co/nvidia/GR00T-N1.5-3B) — accessed 2026-08-05
- [nvidia/GR00T-N1-2B model card](https://huggingface.co/nvidia/GR00T-N1-2B) — accessed 2026-08-05
- [Accelerate Generalist Humanoid Robot Development with NVIDIA Isaac GR00T N1 (NVIDIA developer blog)](https://developer.nvidia.com/blog/accelerate-generalist-humanoid-robot-development-with-nvidia-isaac-gr00t-n1/) — accessed 2026-08-05
- [Learning Fine-Grained Bimanual Manipulation with Low-Cost Hardware (ACT / ALOHA, arXiv 2304.13705)](https://arxiv.org/pdf/2304.13705) — accessed 2026-08-05
- [tonyzhaozh/act GitHub repository](https://github.com/tonyzhaozh/act) — accessed 2026-08-05
- [Diffusion Policy: Visuomotor Policy Learning via Action Diffusion (arXiv 2303.04137)](https://arxiv.org/abs/2303.04137) — accessed 2026-08-05
- [FAST: Efficient Action Tokenization for Vision-Language-Action Models (arXiv 2501.09747)](https://arxiv.org/abs/2501.09747) — accessed 2026-08-05
- [RobotArena ∞: Scalable Robot Benchmarking via Real-to-Sim Translation (arXiv 2510.23571)](https://arxiv.org/abs/2510.23571) — accessed 2026-08-05
- [Fine-Tuning Vision-Language-Action Models: Optimizing Speed and Success (arXiv 2502.19645)](https://arxiv.org/pdf/2502.19645) — accessed 2026-08-05
- [RT-H: Action Hierarchies Using Language (arXiv 2403.01823)](https://arxiv.org/pdf/2403.01823) — accessed 2026-08-05

## Changelog

- 2026-08-05 — created
