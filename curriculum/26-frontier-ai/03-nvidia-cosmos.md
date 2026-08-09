# NVIDIA Cosmos & Physical AI: World Foundation Models, Isaac Sim

> **Track:** T26 Frontier AI · **Time:** 2.5h · **Prereqs:** `T26-world-models`, `T26-video-generation`, T05 · **Updated:** 2026-08-05
> **Module id:** `T26-nvidia-cosmos` · **Tags:** cosmos, world-foundation-models, isaac-sim, sim-to-real, synthetic-data, vendor-analysis, critical
> **Lab:** none yet — see `labs/py/02-agent-loop/` for the pattern if you want to build one

## The 30-second version

Cosmos is not one thing, it is three things sold as one: a family of open-weight video world models (Predict for generation, Transfer for controlled style/domain translation, Reason for a physical-commonsense VLM), a set of video tokenizers, and a GPU-accelerated data-curation pipeline that turned 20 million hours of raw video into roughly 100 million training clips. The honest read is that **the curation pipeline and the Transfer model are the parts with defensible engineering value, and the "learned simulator" framing is the part that is ahead of its evidence**: nobody, NVIDIA included, has published a controlled study showing that pretraining a robot policy on generatively synthesised video beats the same budget spent on real data, at a fixed real-data budget, on a benchmark someone else chose. The best evidence that exists is the DreamGen/GR00T line, where neural trajectories co-trained **1:1** with real trajectories lifted a 12-task DreamGen suite from **13.1% to 38.3%** success, and gave up to **+8.8%** even when real demonstrations were already available; that is a real, measured, useful result, and it is an *augmentation* result, not a replacement result. Underneath the WFMs the substrate that actually ships robots is boring and old: Isaac Sim on OpenUSD with PhysX, Isaac Lab running thousands of parallel environments on one GPU, and domain randomisation, which is a 2017 idea. Your interview position should be: the sim-to-real gap is a *physics and contact* problem, generative video mostly fixes the *appearance* half, and if you cannot say which half your gap is in you have no business buying either.

## Why this gets asked

Because "physical AI" is the single most heavily marketed category in the industry right now and an interviewer wants to know whether you can read a model card. The specific failure they have lived through is this: someone on their team spent a quarter and a six-figure GPU bill generating synthetic training data, the policy's validation numbers went up, and the robot performed exactly as badly on hardware as it did before, because the gap was never in the pixels. Or the autonomous-driving variant: the perception model got better at the rare-scenario videos it was fine-tuned on and got worse on the common case, because the synthetic distribution collapsed diversity in a way the eval set did not measure.

At principal level they are also probing three things that have nothing to do with robotics and are the reason this module is worth your time even if you never touch a robot. First, **can you evaluate a vendor stack sceptically under time pressure** - which claims are attached to a paper with a table, which to a blog post, which to a keynote. Second, **do you understand licensing and lock-in as engineering constraints** rather than legal trivia; the NVIDIA Open Model License is revocable and terminates automatically if you weaken the guardrails, which is a real constraint on a data pipeline. Third, **can you reason about synthetic-data mixing ratios** - a problem that is identical whether you are mixing generated video into a robot policy or generated text into an LLM SFT set, and the failure mode (diversity collapse, model-generated data reinforcing model priors) is the same failure mode in both.

If you are interviewing for a non-robotics AI role, the correct posture is: you know what this stack is, you know exactly which of its claims are load-bearing, and you know that the transferable lesson is about synthetic-data economics, not about robots.

---

## Lineage: past → present → future

**What came before.** Robot learning from simulation is old and its history is a list of things that did not work. The first generation was **hand-built simulators with hand-tuned dynamics**: Gazebo (2004), MuJoCo (Todorov et al., 2012), Bullet, ODE. These worked for locomotion research and failed for contact-rich manipulation, and the reason is precise and worth naming: rigid-body contact is stiff, non-smooth, and its parameters (friction coefficients, restitution, compliance, actuator backlash, sensor latency) are not identifiable from the observations a robot actually has. A policy optimised against a specific friction coefficient learns to exploit it, and the same policy on hardware with a 15% different friction coefficient falls over. That is the sim-to-real gap in its original form: **it was a dynamics-identification problem, not a rendering problem.** The second generation was **domain randomisation** (Tobin et al., "Domain Randomization for Transferring Deep Neural Networks from Simulation to the Real World", 2017; Sadeghi and Levine's CAD2RL, 2016), whose insight was to stop trying to identify the true parameters and instead train across a distribution wide enough that reality is one sample from it. This works, it is still the backbone of every deployed sim-to-real pipeline in 2026, and its pain is cost: OpenAI's Dactyl in-hand manipulation work consumed on the order of 100 years of simulated experience for the 2018 block-reorientation result, and the 2019 Rubik's-cube result with Automatic Domain Randomisation used something on the order of 13,000 simulated years. Randomising harder buys robustness by making the task harder, so you pay for it in sample count, and the sample count grows roughly with the volume of the randomisation space. The third pain was **visual realism**: a randomised simulator produces cartoon-looking scenes, and while randomisation over textures and lighting produces a policy that ignores appearance, it produces a *perception* model that is measurably worse than one trained on real images. That is the specific gap NVIDIA's WFM pitch targets.

The generative-video precursor dates the idea. GAN-based sim-to-real image translation (CycleGAN, 2017; RetinaGAN and RL-CycleGAN from Google Robotics, 2020-2021) already did "make my simulated frames look real" and already reported robot-task improvements. Cosmos Transfer is the same idea at diffusion-transformer scale with better control conditioning. It is an evolution, not an invention, and saying so out loud is a good signal.

**Where it stands now.** NVIDIA announced Cosmos at CES on 6 January 2025 and posted the platform paper (arXiv:2501.03575) the next day, with v2 on 18 March 2025 and v3 on 9 July 2025. Cosmos 1.0 shipped two WFM families under the NVIDIA Open Model License: **diffusion** at 7B and 14B in Text2World and Video2World variants, and **autoregressive** at 4B and 12B base plus 5B and 13B Video2World, alongside a tokenizer family (CI8x8, CV4x8x8, CV8x8x8, DI8x8, DV8x16x16) and a four-component guardrail. Cosmos-Predict2.5 (October 2025) collapsed Text2World, Image2World and Video2World into one model at **2B and 14B**, trained on **200 million curated clips**, using Cosmos Reason 1 as the text encoder and extending output to **30 seconds**. Cosmos-Transfer2.5 shipped at **2B**, **3.5x smaller** than Transfer1-7B with better control adherence. Cosmos 3 (arXiv:2606.02800, June 2026) is an omnimodal Mixture-of-Transformers family jointly modelling language, image, video, audio and action, subsuming the VLM, the video generator and the world-action model into one backbone.

Deployed versus merely published is the important split. **Deployed:** the curation pipeline, Transfer-style domain augmentation for AV perception, and Isaac Sim as an industrial simulation product with real customers doing warehouse and factory digital twins. **Published with evaluation:** DreamGen's neural-trajectory co-training result and GR00T N1/N1.5, and Transfer 2.5's reported up-to-**60%** improvement on 3D lane and cuboid detection over Transfer1-7B-Sample-AV with real-world control inputs (LATR for lanes, BEVFormer for cuboids). **Claimed but not benchmarked in any way you can check:** that Cosmos is a simulator you can train a policy *inside*. The live disagreement sits exactly there. The generative camp says a WFM will eventually replace the physics engine; the roboticists point out that a video model has no notion of a contact constraint, cannot be queried for a force, cannot be stepped at a fixed timestep with reproducible state, and cannot be reset, all of which a physics engine gives you for free and all of which an RL loop requires. As of August 2026 there is no published result where an RL policy trained entirely inside a Cosmos-class video model transfers to hardware and beats a policy trained in Isaac Sim. If that result existed, NVIDIA would lead every keynote with it.

**Where it's heading.** High confidence (85%+): the **augmentation** use case consolidates and becomes standard practice. Generating photometric and semantic variations of real logged data via a Transfer-style controlled translation, conditioned on segmentation or depth so the geometry is preserved, is cheap, evaluable, and already works; it will be as normal by 2028 as image augmentation is now. High confidence: the **curation pipeline is the durable product**. Cosmos Curator and Cosmos Dataset Search are the pieces that would still be valuable if every WFM were replaced tomorrow, because the bottleneck in physical AI is finding the 0.1% of your fleet's logged video that contains the scenario you need, not rendering more of it. Medium confidence (roughly 60%): **hybrid stacks win** - a physics engine for state, contact and reset semantics, with a generative model layered on top for appearance and for long-tail scenario synthesis, rather than either alone. That is what the Isaac Sim + Cosmos Transfer pairing already is, and it is architecturally honest in a way the "learned simulator" pitch is not. Speculative, and label it that way: whether an omnimodal action-conditioned model like Cosmos 3 becomes a genuine closed-loop training environment. The Mixture-of-Transformers design that jointly generates action and next observation is the right structural bet if it is going to happen, but the evaluation problem (below) is unsolved and no amount of architecture fixes it. Also speculative and more commercially interesting: whether the NVIDIA Open Model License stays permissive. It is **revocable**, it terminates automatically if you circumvent a safety guardrail, and NVIDIA reserves the right to update it unilaterally to comply with regulation. A company building a data pipeline on it in 2026 is taking a risk that a company building on Apache-2.0 weights is not.

---

## Mental model

```
THE STACK, BOTTOM TO TOP  (and where the value actually is)

  +--------------------------------------------------------------+
  |  POLICY            GR00T N1 / N1.5  (VLA)      -> T26-vla     |
  |                    diffusion action head, cross-embodiment    |
  +--------------------------------------------------------------+
             ^ trains on                    ^ trains on
             |                              |
  +----------------------+     +---------------------------------+
  | REAL ROBOT DATA      |     | SYNTHETIC DATA                  |
  | teleop demos         |     |  (a) sim rollouts   Isaac Lab   |
  | expensive:           |     |  (b) neural traj.   DreamGen    |
  |  ~1 demo / 30-60s    |     |  (c) augmented real Transfer    |
  |  of human time       |     +---------------------------------+
  +----------------------+                  ^
             |                              |
             |         +--------------------+--------------------+
             |         |                                         |
  +----------v---------+---------+     +-------------------------v-+
  | SIMULATION SUBSTRATE         |     | WORLD FOUNDATION MODELS    |
  |  Omniverse / OpenUSD         |     |  Cosmos-Predict  (2B,14B)  |
  |  PhysX  (rigid body, GPU)    |     |  Cosmos-Transfer (2B)      |
  |  Isaac Sim 5.x  (RTX render) |     |  Cosmos-Reason   (7B..32B) |
  |  Isaac Lab 2.x/3.x  (RL API) |     |  Cosmos Tokenizer          |
  |  DETERMINISTIC. RESETTABLE.  |     |  NOT resettable, NOT       |
  |  Gives you STATE and FORCE.  |     |  steppable, gives PIXELS.  |
  +------------------------------+     +----------------------------+
             ^                                        ^
             |                                        |
  +----------+----------------------------------------+-----------+
  |  DATA CURATION: Cosmos Curator / NeMo Curator                 |
  |  20M hours raw  ->  ~100M clips                               |
  |  split -> filter -> dedup -> annotate -> re-encode -> shard   |
  |  <<< THIS IS ARGUABLY THE REAL PRODUCT >>>                    |
  +---------------------------------------------------------------+
             ^
  +----------+----------------------------------------------------+
  |  NVIDIA HARDWARE. Every box above assumes it. This is the     |
  |  business model, and it is the thing to price in a design doc.|
  +---------------------------------------------------------------+


THE ONE DISTINCTION THAT DECIDES EVERYTHING

   SIMULATOR                          VIDEO WORLD MODEL
   ---------                          -----------------
   step(dt) -> state                  sample() -> pixels
   reset(seed) -> exact state         no reset, no seed->state map
   query contact force                no forces exist
   deterministic replay               stochastic sampler
   physics is WRONG BUT KNOWN         physics is PLAUSIBLE BUT UNKNOWN
   ~1e3-1e5 steps/s/GPU               ~380 s for 5 s of video (7B, H100)

   => an RL loop needs the LEFT column. Full stop.
   => a perception/imitation dataset can be built from the RIGHT column.

   Cosmos is sold with language from the left column and ships the right.


THE SIM-TO-REAL GAP HAS TWO HALVES. NAME YOURS BEFORE YOU BUY.

   APPEARANCE GAP                     DYNAMICS GAP
   textures, lighting, sensor         friction, compliance, mass,
   noise, lens, exposure, weather     backlash, latency, contact
   ---------------------------        ---------------------------
   FIXED BY: domain randomisation,    FIXED BY: system id, actuator
   Transfer-style translation,        nets, better contact solver,
   real-image co-training             randomised dynamics, real data
   ---------------------------        ---------------------------
   Cosmos Transfer helps HERE.        Cosmos helps here: NOT MUCH.

   The expensive failure is spending the appearance budget on a
   dynamics gap. Photorealism does not fix a friction coefficient.


WHERE THE HOURS GO IN A REAL PROGRAMME (order of magnitude, not gospel)
   asset + USD scene authoring .......... 40-60%
   reward / task definition .............. 10-20%
   randomisation range tuning ............ 10-20%
   the actual RL training run ............  5-10%
   generative augmentation ...............  5-10%
   Nobody's keynote mentions the first line.
```

---

## How it actually works

### What Cosmos actually ships, item by item

Start with the inventory, because half of assessing this stack is knowing that "Cosmos" names about seven different artefacts and an interviewer will let you conflate them if you want to.

**The diffusion WFM family (Cosmos-Predict1, January 2025).** Four checkpoints: `Cosmos-1.0-Diffusion-7B-Text2World`, `-14B-Text2World`, `-7B-Video2World`, `-14B-Video2World`. Architecturally these are diffusion transformers denoising in the tokenizer's latent space, with interleaved self-attention, cross-attention and feedforward blocks; the cross-attention layers carry the text conditioning throughout denoising, and adaptive layer normalisation injects the diffusion timestep. For the Video2World variants the conditioning frames' latents are concatenated along the temporal axis and **augment noise is added to the conditioning latents specifically to close the train/inference gap** - which is the kind of detail worth having, because it is the mitigation for the classic autoregressive-video failure where a model conditioned only on clean ground-truth frames during training falls apart when conditioned on its own noisy outputs at inference.

The output spec is the thing to memorise, because it is what makes the economics real. Text2World emits **121 frames**, which at the default 24 fps is a **5-second** clip at **1280x704**. Video2World predicts the **next 120 frames** given a text prompt and one image as the first frame. Configurable aspect ratios are 1:1 at 960x960, 4:3 at 960x704, 3:4 at 704x960, 16:9 at 1280x704, and 9:16 at 704x1280. Frame rate is adjustable between **12 and 40 fps**. Prompts are capped at **fewer than 300 words**. Inference has only been tested at **BF16**, only on **Linux**, on Ampere, Hopper or Blackwell.

**The autoregressive WFM family.** `Cosmos-1.0-Autoregressive-4B` and `-12B` as base future-frame predictors, plus `-5B-Video2World` and `-13B-Video2World` which add text conditioning via cross-attention. These consume the *discrete* tokenizer (DV8x16x16) and predict the next visual token, GPT-style. Both families exist because of a genuine tradeoff: autoregressive models stream naturally frame-by-frame, which matters for interactive use, while diffusion models produce higher fidelity per unit compute at these scales. Predict2.5 and Cosmos 3 both continued the diffusion/flow lineage, which tells you how that bet resolved internally.

**The tokenizers.** Naming is `{C|D}{I|V}<temporal>x<spatial>x<spatial>`: C for continuous latents, D for discrete (FSQ-quantised) codes, I for image, V for video. `CV8x8x8` is continuous video at 8x temporal and 8x8 spatial; `DV8x16x16` is discrete at 8x temporal and 16x16 spatial. Spatial rates are **8x8 or 16x16**, temporal factors **4x or 8x**, maximum total compression **2048x** (8 x 16 x 16). NVIDIA reports the tokenizer as **2x to 12x faster** than prior art at comparable reconstruction quality with a smaller parameter count; that is a vendor comparison in their own paper, so treat it as a claim with a table behind it rather than an independent benchmark.

The arithmetic on what that compression buys is the number that makes the platform tractable. One 121-frame 1280x704 clip is 121 x 1280 x 704 x 3 = **327 million** raw RGB values. Through CV8x8x8 the token grid is roughly (121/8) x (704/8) x (1280/8) ≈ 15 x 88 x 160 ≈ **211,200 latent tokens**, a compression of about **1,550x** in element count before channel depth. Without something in that range a video sequence does not fit in a transformer context at all, which is why "tokenizer" is a first-class deliverable rather than an implementation detail.

**The guardrail.** `Cosmos-Guardrail1` has four components and they run at both ends of the pipe. On input: a **blocklist** of human-curated keywords, and **Aegis**, which is `Aegis-AI-Content-Safety-LlamaGuard-LLM-Defensive-1.0`, a parameter-efficient instruction-tuned Llama-Guard variant built on Llama2-7B and trained on NVIDIA's Aegis Content Safety Dataset over a taxonomy of **13 critical safety risk categories**. On output: a **video content safety filter**, a multi-class classifier over **SigLIP** embeddings that scores frames as safe or unsafe, and a **face blur filter** using **RetinaFace** that pixelates any detected facial region larger than **20x20 pixels**. That last threshold is the one that bites in practice and you should remember it: if your downstream task involves people at any reasonable distance, faces are being pixelated in your training data by default, which is fine for a warehouse-navigation policy and quietly fatal for anything doing human pose, gaze or intent.

**The licence.** NVIDIA Open Model License, version release date **6 January 2025**. It is commercially usable, permits derivative models, and NVIDIA disclaims ownership of outputs. It also: (a) is explicitly **revocable**, (b) **terminates automatically** if you "bypass, disable, reduce the efficacy of, or circumvent any technical limitation, safety guardrail or associated safety guardrail hyperparameter", (c) terminates if you file patent or copyright litigation against anyone alleging the model infringes, (d) requires the string **"Built on NVIDIA Cosmos"** on a related website, UI, blog post or product documentation if you distribute a Cosmos model, a product containing one, a derivative, or **any AI model you trained or fine-tuned using Cosmos outputs**, and (e) is governed by Delaware law with exclusive jurisdiction in Santa Clara County. Clause (d) is the one to raise in a design review: **synthetic data generated by Cosmos carries an attribution obligation into every model trained on it.** Clause (b) means "we disabled the face blur because our use case is legitimate human-robot interaction research" is a licence termination, not a config change. This is not Apache 2.0 and calling it "open source" without that caveat is a small but real credibility hit.

### The curation pipeline, which is arguably the actual product

The headline training-scale numbers are **20 million hours** of video reduced to about **100 million clips**. The stages, in order, are: shot-boundary detection to split long videos into single-shot clips; filtering for motion (static clips and pure camera-pan clips are removed because they teach nothing about dynamics), for quality, and for text overlays; deduplication against the rest of the corpus; annotation with a VLM to produce captions; and re-encoding into a uniform mp4 profile so downstream loaders are homogeneous.

The interesting engineering is the throughput claim, and it is the most credible number NVIDIA publishes. Processing 20 million hours takes roughly **40 days on Hopper** or **14 days on Blackwell**, against a stated **3.4 years** on a CPU-only pipeline - about an **89x** speedup Blackwell-versus-CPU. The mechanism is not mysterious: video decode and encode are the bottleneck, not the model inference, and the GPUs have fixed-function hardware for it. NVDEC handles decode, NVENC handles encode, and a detail that matters if you are actually sizing this is that **L40S has both NVDEC and NVENC while H100 has only NVDEC** - so the "obvious" choice of your most expensive training GPU is the wrong choice for the re-encode stage. That is the kind of observation that plays well in an interview because it is a systems answer, not a model answer.

Now the number the last module already flagged and which you should be prepared to take apart: the vendor-stated **"9,000 trillion tokens"** (9 x 10^15). Work it: 20 million hours is 7.2 x 10^10 seconds; at 24 fps that is about **1.73 x 10^12 frames**. Divide 9 x 10^15 by 1.73 x 10^12 and you need about **5,200 tokens per frame**, which is in the right ballpark for a 1280x704 frame at 8x8 spatial compression with 8x temporal pooling (88 x 160 / 8 ≈ 1,760, or 14,080 without temporal pooling). So the figure is *arithmetically reachable* - but only by tokenising the entire **uncurated 20-million-hour** corpus, not the curated set. The curated set is about **100 million clips**; at roughly 211,200 tokens per 5-second clip that is about **2.1 x 10^13 tokens**, roughly **21 trillion**. The gap between the marketing number and the plausible trained-on number is about **430x**. The correct interview formulation: "9,000 trillion is a *corpus tokenisation* figure over data that was mostly filtered out, not a training-token figure; the defensible number is order 10^13, which is roughly Llama-3-scale in tokens but each token is far lower-information than a text token." Nobody expects you to have done that arithmetic, which is exactly why it lands.

### Isaac Sim, Isaac Lab, Omniverse, USD, PhysX

This is the substrate that actually produces working robots today, and candidates blur the layers, so be precise.

**OpenUSD** is the scene format, originally Pixar's Universal Scene Description. It is not a file format so much as a composition system: scenes are layered, referenced and *composed* from sublayers with an explicit strength ordering, which is what makes procedural scene generation viable. The relevant extension is the **UsdPhysics** schema, standardising rigid bodies, colliders, joints and physical materials inside USD so mass, friction and articulation travel with the asset rather than living in an engine-specific sidecar. That is the strongest technical argument for the Omniverse stack: your scene is data with a schema, not an engine project file.

**PhysX** is the GPU-accelerated physics engine, rigid-body-first with articulation via a reduced-coordinate (Featherstone-style) solver. Its constraint solver is iterative, which is the origin of most sim-to-real dynamics discrepancy: contact is resolved approximately, penetration corrected with a positional bias, and the resulting effective compliance is a function of solver iteration count and timestep rather than of any physical property. **Change the substep count and your policy's learned behaviour changes.** Isaac Lab 3.0 introduces a multi-backend abstraction over PhysX, **Newton** and OVPhysX, so a single-backend assumption is no longer safe.

**Isaac Sim** is the application: PhysX plus RTX ray-traced rendering plus sensor models (cameras, beam-level lidar, IMU, contact sensors) plus ROS bridges, on Omniverse Kit. **Isaac Lab** is the RL/IL layer: a vectorised environment API over `torch` tensors, randomisation as a declarative event/manager system, task suites, and integrations with rl_games, RSL-RL, SKRL and Stable-Baselines3. Isaac Sim 5.0 and Isaac Lab 2.2 hit general availability on GitHub at SIGGRAPH in August 2025.

Hardware floor: Isaac Sim 5.1's stated minimum is an **RTX 4080 with 16 GB VRAM** and **32 GB system RAM**. The Isaac Lab benchmarking paper (arXiv:2511.04831) runs headless on **L40 (48 GB)**, **RTX Pro 6000 (96 GB)** and **GeForce RTX 5090 (32 GB)**. Not on that list: any non-NVIDIA GPU, any Mac, any CPU-only CI runner. So "let's just try it" costs a workstation purchase or a GPU cloud instance, and your CI cannot run the simulator.

Throughput is the whole reason this layer exists. Isaac Lab's design point is thousands of environments stepping in lockstep on one GPU with observations that never leave device memory. Typical published locomotion configurations use **2,048 to 4,096** parallel environments, and the headline result of the GPU-simulation generation (Isaac Gym, Makoviychuk et al., 2021) was training ANYmal locomotion in **minutes on a single GPU** against hours to days on a CPU cluster. It is fast not because PhysX is a better solver but because the physics step, observation assembly and policy forward/backward share device memory with no serialisation boundary. That is also why the "generative model as environment" pitch is structurally awkward: a 7B diffusion model takes about **380 seconds on an H100** for 5 seconds of video, roughly **76x slower than real time for a single environment**, against a physics engine doing thousands of environments faster than real time each.

### Domain randomisation, and how synthetic data is actually mixed

Domain randomisation is the operative technique. You define a distribution over simulator parameters and sample a fresh draw per episode or per reset. The categories:

- **Visual:** textures, materials, lighting position/colour/intensity, camera intrinsics and extrinsics, exposure, motion blur, sensor noise.
- **Dynamics:** link masses (commonly +/- 10-30%), friction coefficients (often 0.5x to 2.0x nominal), joint damping and stiffness, actuator gains, restitution.
- **Latency and control:** action delay of 1-3 control steps, observation noise, dropped frames.
- **Scene:** object poses, distractor objects, clutter density, layout.

The theory is a robustness argument, not a realism argument: you train a policy optimal under the *expectation* over the parameter distribution, so if the true parameters lie inside the support the policy is at worst suboptimal rather than catastrophically wrong. The cost is that the task gets harder as the support widens, so sample complexity rises and asymptotic performance on any single environment drops. **Automatic Domain Randomisation** (OpenAI, 2019) is the standard fix: start narrow, widen each range whenever performance crosses a threshold, so the curriculum expands only as fast as the policy can absorb it.

Now the part everyone gets vague about: **what ratio of synthetic to real?** The findable numbers all come from the DreamGen/GR00T line, which is NVIDIA's own work and the most honest evaluation the ecosystem has published.

- **Co-training sampling ratio: 1:1** neural trajectories to real trajectories. That is the number to quote.
- **Volume per task:** 3,000 neural trajectories per task for the RoboCasa simulation benchmark; **100 neural trajectories per task** for real-world tasks. Note the two-orders-of-magnitude drop for real tasks - the real-world regime is not "generate a million videos", it is "generate a hundred good ones".
- **Effect size:** GR00T N1.5 scored **38.3%** on the 12-task DreamGen suite versus **13.1%** for GR00T N1. Synthetic data improved results consistently across 30-, 100- and 300-demonstration regimes in simulation, and in a real-world regime using **10%** of the real data. Where real demonstrations were already plentiful, dreamed data still added **up to 8.8%**.
- The GR00T N1 pretraining mixture combined internal GR-1 humanoid data, **Open X-Embodiment**, simulated GR-1 trajectories from DexMimicGen, DreamGen neural trajectories, and AgiBot-Beta. Note that this is a mixture with *four or five distinct data sources*, so attributing the model's capability to any single one, including the synthetic component, is not possible from the released numbers.

The VLA policy architecture that consumes this data belongs to the sibling module; see `T26-vla` for GR00T N1's dual-system design, the diffusion action head, and cross-embodiment action tokenisation. Do not re-derive it here. What you need from that module for *this* one is only the interface: it eats (image, language instruction, proprioception) tuples and emits action chunks, and that is the shape any synthetic-data pipeline must produce.

The general rule the field has converged on, which is also true for synthetic text in LLM SFT and is the transferable lesson: **synthetic data works as a diversity amplifier over a real seed and fails as a real-data replacement.** Every result above has real data in the mixture. Nobody publishes a zero-real-data result on hardware, and the reason is that the synthetic generator was itself trained on real data and cannot add information that was not in its training set; it can only redistribute it into combinations the policy has not seen. That is genuinely valuable - combinatorial coverage is what generalisation needs - but it is a bounded kind of valuable.

### The honest evaluation problem

This section separates a credible assessment from a summary of a press release. Be explicit about levels of evidence.

**Measured with a number you can check.** Video-generation perceptual quality (FVD, human preference), tokenizer reconstruction (PSNR/SSIM at a given compression rate), Cosmos Reason's physical-reasoning benchmark scores, Transfer 2.5's downstream detection metrics (3D lanes with LATR, cuboids with BEVFormer, up to 60% better than the previous Transfer model), and the DreamGen/GR00T policy success rates. These are real evaluations.

**Measured but weakly.** The "physics-aware" claim. No accepted benchmark certifies a video model as physically consistent, and the ones that exist (VideoPhy, VideoPhy-2, PhyWorldBench, PhyWorld; see `T26-world-models`) put frontier video models in the **19% to 22%** range for joint semantic-plus-physical adherence. Cosmos is not exempt from that regime, and NVIDIA's own 3D-consistency and physics-alignment evaluations are internally defined metrics on internally chosen prompt sets: a legitimate thing to publish, not a legitimate thing to treat as external validation.

**Asserted.** That synthetic data from a WFM makes robot policies better *in general*. The missing experiment is easy to state, and stating it demonstrates you know what a controlled study looks like:

> Fix a real-data budget of N demonstrations and a total training-compute budget C. Train policy A on N real demos plus M synthetic trajectories. Train policy B on N real demos plus the same compute C spent on more training epochs, stronger classical augmentation, or on collecting additional real demos worth the *dollar cost* of generating M synthetic ones. Evaluate both on a held-out task suite chosen by someone who is not selling either. Report success rate with confidence intervals over at least 20 trials per task.

Nobody has published that. The DreamGen ablations are the closest and they hold the real budget fixed while adding synthetic data for free, which answers "does adding synthetic data help?" (yes, measurably) but not "is synthetic data the best use of this budget?" (unknown). Both questions matter; only the first has an answer.

**The cost side that turns the second question into arithmetic.** At **~380 seconds per 5-second clip** on one H100 for the 7B diffusion model, one H100-hour yields about **9.5 clips**, or **47 seconds** of generated video. Generating 100 hours of synthetic video therefore costs about **7,600 H100-hours**; at a rough cloud rate of $3 to $4 per H100-hour that is **$23,000 to $30,000**, before curation, before filtering out the bad generations (and a meaningful fraction will be bad), and before the guardrail rejects some of them. Compare that to a teleoperator producing one 30-second demonstration per minute of wall-clock at a fully loaded cost of $40 to $80 per hour: **$30,000 buys roughly 400 to 750 operator-hours**, which at 60 demos per hour is **24,000 to 45,000 real demonstrations**. That comparison is not decisive - the synthetic data covers scenarios you cannot stage safely, and the real demos come from one lab with one lighting setup - but a principal engineer who walks into a design review without having done it is not doing the job. The numbers above are my arithmetic from published unit figures, not a published cost study; present them as an order-of-magnitude framing, not a quote.

---

## Build it from scratch

Not a 14B diffusion transformer. The smallest artefact that answers the question the module is about: **does synthetic data help, and how would I know?** That artefact is a mixing-and-evaluation harness, and it is what you would actually own as a Principal engineer on such a programme. Matching lab folder: `labs/py/26-03-nvidia-cosmos/`.

### Part 1: a synthetic-data mixer that cannot lie to you

These programmes usually fail because the eval set is contaminated by the same generator that produced the training data, or because the "improvement" is an artefact of more samples rather than better ones. This harness makes both impossible by construction.

```python
# untested sketch -- synthetic/real mixing harness with contamination guards.
# Design constraints, in priority order:
#   1. eval set contains ZERO generated frames and ZERO scenes whose seed
#      appeared in any generation prompt.
#   2. the real-data budget is FIXED across arms. Only the synthetic arm varies.
#   3. every arm gets identical optimiser steps, so "more data" is not the
#      confound.
from dataclasses import dataclass
from typing import Sequence
import hashlib
import random

import torch
from torch.utils.data import Dataset


@dataclass(frozen=True)
class Sample:
    obs: torch.Tensor            # (T, 3, H, W)
    instruction: str
    action_chunk: torch.Tensor   # (T, action_dim)
    origin: str                  # "real" | "sim" | "neural"
    scene_id: str                # provenance key, survives generation
    seed_episode_id: str | None  # for neural: which REAL episode seeded it


class MixedDataset(Dataset):
    """Interleaves real and synthetic at a FIXED ratio, deterministically.

    ratio=1.0 reproduces the DreamGen/GR00T co-training setting (1:1).
    The interleave is deterministic per seed so two arms see the same real
    samples in the same order. Otherwise you are measuring data-order noise,
    which on small robot datasets is worth several points of success rate
    on its own.
    """

    def __init__(self, real: Sequence[Sample], synth: Sequence[Sample],
                 ratio: float, seed: int = 0):
        if not real:
            raise ValueError("zero-real-data arms are not a valid experiment")
        self.real, self.synth, self.ratio = list(real), list(synth), ratio
        n_synth = min(len(self.synth), int(round(ratio * len(self.real))))
        rng = random.Random(seed)
        self.items = self.real + rng.sample(self.synth, n_synth)
        rng.shuffle(self.items)

    def __len__(self) -> int:
        return len(self.items)

    def __getitem__(self, i: int) -> Sample:
        return self.items[i]


def assert_no_contamination(train: Sequence[Sample],
                            eval_: Sequence[Sample]) -> None:
    """Fail loudly rather than publish a number you cannot defend."""
    eval_scenes = {s.scene_id for s in eval_}

    leaked_scene = eval_scenes & {s.scene_id for s in train}
    if leaked_scene:
        raise AssertionError(f"scene leak: {sorted(leaked_scene)[:5]}")

    # The subtle one: a neural trajectory seeded by a real episode inherits
    # that episode's scene. If the seed episode's scene is in eval, the
    # generated data is a paraphrase of the test set.
    leaked_seed = {s.seed_episode_id for s in train
                   if s.origin == "neural" and s.seed_episode_id is not None
                   and _scene_of(s.seed_episode_id) in eval_scenes}
    if leaked_seed:
        raise AssertionError(f"generator seed leak: {sorted(leaked_seed)[:5]}")

    if any(s.origin != "real" for s in eval_):
        raise AssertionError("eval set contains generated samples")


def _scene_of(episode_id: str) -> str:
    """Replace with a real provenance lookup. Stub for the sketch."""
    return hashlib.sha1(episode_id.encode()).hexdigest()[:8]
```

The seed-leak check is the part worth internalising. Neural trajectories are generated *from* real episodes; if you generate from an episode whose scene later lands in your eval split, your synthetic training data is a paraphrase of your test set and your improvement is memorisation. This is the synthetic-data version of a train/test leak and it is invisible to every metric you would normally look at.

### Part 2: the diversity metric that catches collapse

The second failure is that generated data looks varied to a human and is not varied in the space the policy consumes. Measure it, do not eyeball it.

```python
# untested sketch -- effective diversity of a generated corpus.
import torch
import torch.nn.functional as F


@torch.no_grad()
def effective_rank(embeddings: torch.Tensor, eps: float = 1e-12) -> float:
    """Roy & Vetterli effective rank: exp(entropy of the normalised singular
    value spectrum). A corpus of N distinct-looking clips whose embeddings
    lie in a 12-dimensional subspace has effective rank ~12, not N.

    Compare synth vs real on the SAME frozen encoder. A synth/real
    effective-rank ratio below ~0.6 is the observable symptom of collapse.
    """
    x = embeddings - embeddings.mean(0, keepdim=True)
    sv = torch.linalg.svdvals(x.float())
    p = sv / (sv.sum() + eps)
    entropy = -(p * (p + eps).log()).sum()
    return float(entropy.exp())


@torch.no_grad()
def coverage(real_emb: torch.Tensor, synth_emb: torch.Tensor,
             k: int = 5) -> float:
    """Fraction of REAL samples with at least one synthetic neighbour inside
    their own k-NN radius. Low coverage means the generator produced a dense
    blob somewhere the real data is not. This catches 'photorealistic and
    useless'."""
    r = F.normalize(real_emb.float(), dim=-1)
    s = F.normalize(synth_emb.float(), dim=-1)
    d_rr = torch.cdist(r, r)
    d_rr.fill_diagonal_(float("inf"))
    radius = d_rr.topk(k, largest=False).values[:, -1]   # (N_real,)
    d_rs = torch.cdist(r, s).min(dim=1).values           # (N_real,)
    return float((d_rs <= radius).float().mean())
```

Run both on a frozen encoder that neither model was trained on (a DINOv2 or SigLIP checkpoint is the standard choice) so the metric is not measuring the generator's own representation.

### Part 3: the sim-to-real gap decomposition

Before you spend a dollar on generation, find out which half of the gap you have. This is a two-day experiment and it decides the entire programme.

**Step 1. Establish the ceiling.** Train and evaluate the policy entirely in simulation. Call this `S_sim`. If `S_sim` is not high, your problem is the task, the reward or the policy, and nothing about domain transfer is relevant yet.

**Step 2. Isolate the appearance gap.** Keep the simulated dynamics and replace only the renderer output with real camera images of the identical physical scene (or the closest achievable). Evaluate the sim-trained policy. Call this `S_realvision`. The drop `S_sim - S_realvision` is your **appearance gap**.

**Step 3. Isolate the dynamics gap.** Run the sim-trained policy on hardware with vision out of the loop: use a state-based policy consuming proprioception and a motion-capture or fiducial-derived object pose. Call this `S_realdyn`. The drop `S_sim - S_realdyn` is your **dynamics gap**.

**Step 4. Read the verdict.** If the appearance gap dominates, Cosmos Transfer, stronger visual randomisation, or real-image co-training will help, and the expected gain is bounded above by the size of that gap. If the dynamics gap dominates, generative video will not help you at all, and your budget belongs in system identification, actuator modelling, contact-solver tuning, or real-data collection. In most contact-rich manipulation programmes the dynamics gap is the larger one, which is precisely why the marketing emphasis on photorealism should make you suspicious.

**Step 5. Only now, price the options.** Compute the dollar cost per point of expected success-rate gain for each intervention, using the arithmetic in the previous section. Present it as a table. That table is the artefact that gets a decision made.

---

## How it's done in production

### The three workflows actually running in 2026

**Workflow 1: controlled augmentation of logged real data (the one that works).** Run Cosmos Transfer on fleet data, conditioned on a structural control signal extracted from the real clip (segmentation, depth, edges or blur), regenerating appearance under different weather, time of day or scene style. Because the control signal derives from real geometry, **layout and dynamics are real and only appearance is synthetic**, which is exactly the half of the gap a generative model is qualified to fix. Transfer 2.5 supports all four control modalities, reports reduced error accumulation on each versus Transfer1-7B, and reports up to 60% better downstream 3D lane and cuboid detection. Multi-view consistency across synchronised camera rigs is the AV-specific feature. Most credible evidence, propose this first.

**Workflow 2: sim-first policy training with generative appearance augmentation.** Author the scene in USD, train in Isaac Lab with heavy dynamics randomisation across thousands of parallel environments, then use Transfer to diversify observations so the perception front-end does not overfit the RTX renderer's look. This is domain randomisation with a learned randomiser. Honest framing: it *competes with* rather than replaces classical texture and lighting randomisation, and I am not aware of a published head-to-head isolating the two.

**Workflow 3: neural trajectory generation for imitation data (DreamGen).** Post-train a Cosmos-class model on a target robot's data, prompt it with a new instruction and a starting frame to generate video of a task the robot was never taught, then recover pseudo-actions with an inverse dynamics model or latent action model, yielding a (video, action) trajectory. Co-train **1:1** with real trajectories, at roughly **3,000** neural trajectories per task in simulation and about **100** per task for real-world tasks. The subtlety that decides whether it works: pseudo-action labels come from an IDM, so **your synthetic action labels are only as good as your IDM**, and an IDM trained on the same narrow real data has the same blind spots. That is the load-bearing weakness and interviewers who have done this will ask about it.

### Serving and infrastructure realities

- Cosmos WFMs are distributed on Hugging Face under `nvidia/` and on NGC; you must accept the licence in the UI before the weights download, which means **your CI cannot pull them without a stored HF token whose account has accepted the gate**, and that token is a credential to manage and rotate.
- Offloading strategy is a real config decision, not a nicety. For 7B Text2World, peak GPU memory ranges from **74.0 GB** (offloading only the prompt upsampler) through **57.1 GB** (plus guardrails), **38.5 GB** (plus T5 encoder), **38.3 GB** (plus tokenizer), down to **24.4 GB** (plus the diffusion model itself). For 14B the same ladder runs **>80 GB / 70.5 GB / 51.9 GB / 51.7 GB / 39.0 GB**. The 24.4 GB figure is what makes a 24 GB RTX 4090 marginally viable, and it costs throughput on every denoising step.
- The guardrail is not free and is not optional under the licence. Offloading it saves about 17 GB on the 7B; the memory is swapped, not eliminated, and the compute still runs.
- Cosmos Reason 1 (7B) doubles as the text encoder in Predict 2.5, so a "single model" deployment is in practice at least two models resident or swapped.
- NIM microservices exist for Cosmos Reason, which is the managed path. It moves the ops burden to NVIDIA and moves your inference spend onto NVIDIA-hosted or NVIDIA-licensed infrastructure. That is the lock-in trade, stated plainly.
- Cosmos Curator and Cosmos Dataset Search (vector search over clip embeddings via Cosmos Embed NIM) are the pieces you would keep even if you dropped the WFMs. NVIDIA's claim that it searches "billions of clips in seconds" and cuts post-training "from years to days" is a blog claim with no published benchmark; treat the capability as real and the magnitudes as marketing.

### Failure-mode table

| Symptom | Cause | Fix |
|---|---|---|
| Policy hits 95%+ in Isaac Lab, 10-30% on hardware; failures cluster at the moment of contact (grasp slip, object squirts out, overshoot on insertion) | **Dynamics gap.** PhysX resolves contact iteratively with a positional bias, so effective compliance is a function of substep count rather than of any physical property. Friction, mass and actuator gains were never identified against the real robot. | Run the Step 2 / Step 3 decomposition to confirm it is dynamics. Then: system identification on the real actuators, randomise link mass +/- 20-30% and friction 0.5x-2.0x, add 1-3 step action latency, train an actuator network on real torque/position traces. Change solver substeps and verify the policy survives before shipping. Photorealism will not touch this. |
| Same sim-to-real drop, but failures cluster on *perception* (grasps empty space, misidentifies the object, fails only under new lighting) | **Appearance gap.** Renderer-specific texture and lighting statistics; the vision front-end latched onto them. | Visual domain randomisation first, because it is nearly free. Then real-image co-training. Then Transfer-style translation conditioned on segmentation or depth so geometry is preserved. Expected gain is bounded above by the measured appearance gap, so measure it first. |
| Adding 10x more generated clips stops improving the policy and then makes it worse, while validation loss keeps dropping | **Diversity collapse.** The generator samples from a narrow mode; the extra clips are near-duplicates in embedding space, and model-generated data reinforces the generator's own priors. | Measure `effective_rank(synth)/effective_rank(real)` on a frozen third-party encoder; below ~0.6 is collapse. Measure `coverage` against real. Fix by raising sampler diversity, prompting from a **stratified scenario taxonomy** rather than free text, deduplicating generated clips at the embedding level, and capping the synthetic:real ratio at 1:1. Do not fix it by generating more. |
| Generated video is beautiful; the policy trained on it is no better, sometimes worse | **Optimising the wrong axis.** Perceptual metrics (FVD, LPIPS, human preference) are close to uncorrelated with physical correctness; frontier video models sit at 19-22% joint semantic-plus-physical adherence on the public physics benchmarks. The model got the wallpaper right. | Stop reporting FVD to stakeholders. Report downstream task metrics only: detection mAP, or policy success rate on real hardware with confidence intervals over at least 20 trials per task. If you must gate generation quality, gate on extracted physical quantities (object permanence, trajectory smoothness, contact plausibility), not on pixels. |
| Generation jobs return blank or refused outputs at a nonzero rate; faces in your training corpus come back pixelated | **Guardrails.** Aegis blocks prompts against 13 risk categories, a curated keyword blocklist catches corner cases, a SigLIP-based multi-class filter rejects unsafe frames post-hoc, and RetinaFace pixelates any face detection larger than **20x20 pixels**. | Log every guardrail rejection with the triggering prompt and treat rejection rate as a pipeline SLI. Rewrite prompts away from trigger vocabulary; surgical, medical, weapon-adjacent and human-injury language are common false positives for legitimate industrial and healthcare scenarios. **You may not disable them:** the licence terminates automatically on circumvention. If face fidelity is essential to the task, seek a custom licence via `cosmos-license@nvidia.com` or use a different model. |
| Two runs of the same simulation config produce different training curves | Nondeterminism in GPU physics (contact ordering, atomic accumulation) compounded by a randomisation manager reseeded on every reset. | Pin the physics seed and the randomisation seed separately and log both. Report results over at least 3 seeds. Never report a single-seed sim-to-real number; the seed variance on small robot benchmarks is frequently larger than the effect being claimed. |
| Simulation throughput collapses as soon as cameras are added | Rendering, not physics, is now the bottleneck, and RTX rendering per environment does not amortise the way the batched physics step does. | Train state-based first and add vision late. Use tiled/batched rendering, drop render resolution, render at a lower frequency than the control loop, or substitute a fixed set of viewpoint-randomised offline renders for live rendering. |
| Fine-tuned Cosmos checkpoint cannot be shipped to a customer's air-gapped site | Licence, attribution and gate-acceptance obligations follow the derivative. **"Built on NVIDIA Cosmos"** attribution is required, and it attaches to any AI model trained or fine-tuned on Cosmos *outputs*, not just to the weights. | Resolve at design time, not ship time. Have legal read the NVIDIA Open Model License before the first generation job runs, and record the attribution obligation in the model card of every downstream artefact so it is not rediscovered during a customer security review. |
| Team proposes running an RL loop "inside Cosmos" | Category error. The WFM has no reset, no deterministic state, no forces, and produces 5 seconds of video in about 380 s on an H100 at 7B. | Use the physics engine for the loop and the WFM offline to produce a dataset. If a learned environment is genuinely wanted, the relevant literature is latent-dynamics model-based RL (`T26-world-models`), not video generation. |

---

## Tradeoffs & when NOT to use it

**Do not use a WFM when your gap is dynamics.** This is the headline. If your policy fails at contact, on force-controlled tasks, on deformables, or on anything where the outcome depends on a friction coefficient or a compliance, a generative video model is the wrong tool by construction. It does not represent forces, it was never trained on a force signal, and its objective contains no term penalising a violated contact constraint. Spend the money on system identification and real data.

**Do not use it when you need a closed loop.** RL requires `reset()` and `step()` with reproducible state; a diffusion video model has neither. At roughly 380 seconds per 5 seconds of 7B output on an H100 it is about **76x slower than real time for one environment**, against a GPU physics engine running 2,048 to 4,096 environments each faster than real time. No amount of engineering closes that.

**Do not use it if you have no real data.** Every published win is a co-training win with real data in the mixture at ratios like 1:1. The generator cannot manufacture information about your robot, objects or workspace that was not in its training distribution; it can only recombine what it saw. A zero-real-data pitch is a red flag about the person making it.

**Do not use it for safety-critical validation.** Certifying an autonomous system against generated scenarios means certifying against a distribution whose relationship to reality is unmeasured. Generated data is for *training*. Validation belongs on real logged data and physically-grounded simulation with documented parameter provenance. Getting this backwards is a regulatory problem, not merely an engineering one.

**Be careful when the licence conflicts with your product.** Revocable, guardrail-tamper-terminating, patent-litigation-terminating, attribution-propagating into downstream models, Delaware law and Santa Clara County jurisdiction. A startup whose entire training corpus is Cosmos-generated has a single-vendor dependency with a unilateral update clause under its core asset. Compare against genuinely permissive alternatives before committing.

**Be careful about the hardware assumption.** Isaac Sim 5.1's floor is an RTX 4080 with 16 GB VRAM and 32 GB system RAM; Isaac Lab benchmarks run on L40 (48 GB), RTX Pro 6000 (96 GB) and RTX 5090 (32 GB). No AMD path, no Apple path, no CPU-only CI path. Every engineer needs an NVIDIA GPU, CI needs GPU runners, and cloud spend is denominated in NVIDIA instance types. That is the business model working as intended; price it rather than be annoyed by it.

**When it genuinely is the right tool.** Appearance-gap-dominated perception problems with large volumes of logged real data and a long tail of conditions you cannot safely stage: night, fog, snow, rare vehicle types, uncommon road furniture. Autonomous driving is the canonical fit and it is no coincidence that the strongest published Transfer numbers are AV detection metrics. Also: scenario amplification where you have the geometry and need appearance variety, and post-hoc augmentation of a fixed logged corpus. In each of those the generative model does the one job it is qualified for, and does it well.

**The counter-argument, which you should state before the interviewer does.** A defender can legitimately say: the evidence is thin because the field is 18 months old, the DreamGen results are real and directionally positive, collecting robot data at teleoperation rates does not scale to the diversity a generalist policy needs, and every scaling story looked underevidenced at this stage. That is fair. The reason to stay sceptical is not that the idea is bad; it is that the *specific* marketed claim, that generated video substitutes for real interaction data, is stronger than any published experiment supports, and the experiment that would settle it is cheap and has not been run.

---

## Interview questions

### Q1 — What is NVIDIA Cosmos, in one minute?

**Testing:** whether you can describe a vendor stack precisely instead of repeating its tagline.
**Answer:** A platform with three separable parts. One, a data-curation pipeline that turned 20 million hours of raw video into roughly 100 million training clips, GPU-accelerated end to end (about 40 days on Hopper, 14 on Blackwell, against a stated 3.4 years CPU-only). Two, open-weight world foundation models under the NVIDIA Open Model License: Predict for video generation (7B/14B diffusion and 4B/12B autoregressive in 1.0; 2B/14B unified in Predict 2.5), Transfer for spatially-controlled domain translation (2B in 2.5, 3.5x smaller than the 7B Transfer 1), and Reason, a physical-commonsense VLM from 2B to 32B. Three, a tokenizer family, continuous and discrete, at up to 2048x total compression. It sits above Omniverse/OpenUSD/PhysX and Isaac Sim/Isaac Lab, and feeds policies like GR00T.
**Follow-up trap:** *"So it's a simulator?"* No, and this is where most candidates lose the room. A simulator gives you `step(dt)`, `reset(seed)`, deterministic replay, and queryable contact forces. Cosmos gives you sampled pixels. You can build a dataset from it; you cannot run an RL loop inside it. Isaac Sim is the simulator; Cosmos is a generative data source that sits beside it.

### Q2 — Which parts of Cosmos have evidence behind them and which do not?

**Testing:** whether you distinguish a paper with a table from a keynote slide.
**Answer:** Sort into three bins out loud. Benchmarked: Transfer 2.5's up-to-60% improvement in 3D lane and cuboid detection over Transfer1-7B-Sample-AV (measured with LATR and BEVFormer); the DreamGen/GR00T policy numbers, where GR00T N1.5 hit 38.3% on a 12-task DreamGen suite against 13.1% for N1; tokenizer reconstruction at stated compression rates. Demonstrated but internally evaluated: the "physics-aware" claim, which rests on NVIDIA-defined metrics over NVIDIA-chosen prompts. Asserted: that WFM-generated data improves robot policies in general, and the 9,000-trillion-token training figure.
**Follow-up trap:** *"Isn't NVIDIA-published evaluation still evaluation?"* Yes, and you should not dismiss it. The distinction is not honesty, it is *comparability*: an internally defined metric on an internally chosen prompt set cannot be used to compare against a competitor or to detect the metric being gamed. Ask for the specific benchmark, the specific baseline, and whether the baseline was tuned by the same team. Say that, and you have made the point without accusing anyone of lying.

### Q3 — NVIDIA says Cosmos was trained on 9,000 trillion tokens. React.

**Testing:** numerical scepticism under pressure. This is the single highest-signal question in the module.
**Answer:** Work it live. 20 million hours is 7.2e10 seconds, about 1.73e12 frames at 24 fps. To reach 9e15 you need roughly 5,200 tokens per frame, which is the right order for 1280x704 at 8x8 spatial compression. So the number is arithmetically reachable, but only by tokenising the entire *uncurated* 20-million-hour corpus. The curated set is about 100 million clips; at roughly 211,200 latent tokens per 121-frame clip that is about 2.1e13, so **~21 trillion tokens**, roughly 430x below the headline. Conclusion: 9,000 trillion is a corpus-tokenisation figure over data that was mostly filtered out, not a training-token figure.
**Follow-up trap:** *"Doesn't 21 trillion still make it comparable to a frontier LLM?"* In token count, yes, roughly. In information content, no, and saying so is the mature answer. A video latent token is enormously more redundant than a text token: adjacent frames are near-copies, and the tokenizer's job is to preserve appearance, not semantics. Token count is not a comparable unit across modalities, and anyone who compares them directly is doing marketing arithmetic.

### Q4 — Where does the sim-to-real gap actually come from, and which half does Cosmos address?

**Testing:** the central technical judgement of the module.
**Answer:** Two halves. The appearance gap is textures, lighting, lens and sensor characteristics; the dynamics gap is friction, mass, compliance, actuator backlash, control latency and contact resolution. Cosmos Transfer addresses the appearance half well, because a controlled translation conditioned on segmentation or depth preserves real geometry and changes only the look. It addresses the dynamics half essentially not at all, because a video model has no representation of force and its training objective contains no penalty for a violated contact constraint. In contact-rich manipulation the dynamics gap usually dominates, which is why photorealism is oversold.
**Follow-up trap:** *"How would you actually measure which half you have?"* Decompose it: train and evaluate in sim for the ceiling; hold dynamics simulated and swap in real imagery to isolate the appearance drop; take vision out of the loop with a state-based policy on hardware to isolate the dynamics drop. Two numbers, and they tell you where the budget goes. If you cannot answer this you are guessing, and every candidate who says "you just try it and see" has admitted to guessing.

### Q5 — What ratio of synthetic to real data would you use, and why?

**Testing:** whether you have numbers or vibes.
**Answer:** Start at **1:1**, because that is the sampling ratio DreamGen and GR00T used for co-training neural trajectories with real ones, and it is the only publicly documented number in this space. Volume per task in that work was about 3,000 neural trajectories for RoboCasa simulation tasks and about 100 per task for real-world tasks. Then treat the ratio as a hyperparameter you sweep with a fixed real budget, and stop increasing it the moment the effective-rank ratio of the synthetic corpus falls below about 0.6 of real, because past that point you are adding duplicates.
**Follow-up trap:** *"Why not 10:1 if the synthetic data is free?"* Because it is not free in the way that matters. Three costs: dollars (at ~380 s per 5-second clip on an H100, 100 hours of generated video is roughly 7,600 H100-hours, order $25k), diversity collapse as the ratio rises and the generator's modes dominate the gradient, and label quality, since neural trajectories carry pseudo-actions from an inverse dynamics model whose errors are systematic rather than random. Systematic label noise at 10:1 will move the policy toward the IDM's biases.

### Q6 — What is the Cosmos tokenizer for, and what do the names mean?

**Testing:** whether you read past the model list.
**Answer:** The naming is `{C|D}{I|V}<temporal>x<spatial>x<spatial>`: C continuous, D discrete, I image, V video. So CV8x8x8 is continuous video at 8x temporal and 8x8 spatial compression; DV8x16x16 is discrete at 8x temporal and 16x16 spatial. Spatial options are 8x8 or 16x16, temporal 4x or 8x, maximum total 2048x. Its job is to make video fit in a transformer context at all: a 121-frame 1280x704 clip is 327 million raw RGB values and about 211,200 latent tokens through CV8x8x8, roughly 1,550x fewer elements. Continuous latents feed the diffusion models; discrete codes feed the autoregressive ones.
**Follow-up trap:** *"What breaks if you push compression higher?"* You lose exactly the high-frequency detail a downstream perception model may need, and worse, the loss is not uniform: small distant objects, thin structures and fast motion degrade first, which are disproportionately the safety-relevant content in a driving or manipulation scene. The right test is not reconstruction PSNR, it is downstream task metric as a function of compression rate, because PSNR is dominated by the large smooth regions you do not care about.

### Q7 — Walk me through the Cosmos guardrail and what it costs you.

**Testing:** operational awareness, and whether you have actually run this.
**Answer:** Four components. Pre-generation: a human-curated keyword blocklist, and Aegis, a Llama-Guard variant fine-tuned from Llama2-7B on NVIDIA's Aegis Content Safety Dataset across 13 risk categories. Post-generation: a multi-class video content safety filter over SigLIP embeddings, and a RetinaFace-based face blur that pixelates any detection larger than 20x20 pixels. Costs: memory (offloading guardrails saves about 17 GB on the 7B path, 74.0 GB down to 57.1 GB), latency on every generation, a nonzero refusal rate that should be tracked as a pipeline SLI, and irreversible face pixelation in your training corpus.
**Follow-up trap:** *"Our use case is legitimate, so can we just turn the face blur off?"* No, and this is the trap. The NVIDIA Open Model License terminates automatically if you "bypass, disable, reduce the efficacy of, or circumvent any technical limitation, safety guardrail or associated safety guardrail hyperparameter". Disabling it is a licence termination, not a config change. The legitimate routes are a custom licence via `cosmos-license@nvidia.com` or a different model. Any candidate who answers "just comment out the filter" has failed the question.

### Q8 — What does the NVIDIA Open Model License actually oblige you to do?

**Testing:** whether "open" is a word you interrogate.
**Answer:** Version dated 6 January 2025. It permits commercial use and derivative models and disclaims NVIDIA ownership of outputs, which is genuinely permissive. It also: is explicitly revocable; terminates on guardrail circumvention; terminates if you bring patent or copyright litigation alleging the model infringes; requires **"Built on NVIDIA Cosmos"** attribution on a website, UI, blog post or product documentation if you distribute a Cosmos model, a product containing one, a derivative, **or any AI model you trained or fine-tuned using Cosmos outputs**; and is governed by Delaware law with exclusive jurisdiction in Santa Clara County. NVIDIA may update it unilaterally to comply with regulation.
**Follow-up trap:** *"Which clause matters most to an engineer, not a lawyer?"* The attribution-propagation clause. It means synthetic data generated by Cosmos carries an obligation into every downstream model trained on it, so your data lineage has to be tracked well enough to know which models are affected. That is a metadata and provenance requirement on your training pipeline, decided by a licence, and it is much cheaper to build in on day one than to reconstruct during a customer security review.

### Q9 — Why do the diffusion and autoregressive WFM families both exist?

**Testing:** whether you can articulate a real engineering tradeoff rather than list models.
**Answer:** They optimise different things. Autoregressive models over discrete tokens (DV8x16x16) generate frame-by-frame and stream naturally, so they suit interactive or lower-latency use and inherit the LLM serving toolchain (KV cache, speculative decoding). Diffusion models over continuous latents denoise the whole clip jointly, giving better spatial-temporal coherence and higher fidelity per unit compute at these scales, at the cost of no natural streaming and a fixed clip length (121 frames in Cosmos 1.0). NVIDIA's own comparisons favoured diffusion on quality, and the fact that Predict 2.5 and Cosmos 3 both continued the diffusion/flow lineage tells you how the internal bet resolved.
**Follow-up trap:** *"If diffusion won, why keep the autoregressive line?"* Because the failure modes differ. Autoregressive models accumulate error frame by frame in a way you can detect and truncate mid-generation; diffusion models produce a whole clip that is globally plausible and can be globally wrong. Also, the autoregressive family is the natural substrate for anything interleaving with language tokens, which is exactly where Cosmos 3's omnimodal Mixture-of-Transformers went.

### Q10 — Design the experiment that would prove synthetic data is worth the money.

**Testing:** experimental design at staff/principal level. This is the question that separates the top candidate.
**Answer:** Fix a real-data budget of N demonstrations and a total compute budget C. Arm A: N real plus M synthetic. Arm B: N real plus the same compute C spent on longer training and stronger classical augmentation. Arm C: the *dollar* cost of generating M synthetic trajectories spent on collecting additional real demonstrations instead, so the comparison is budget-matched rather than data-matched. Evaluate all three on a held-out task suite chosen by someone with no stake, with at least 20 trials per task and confidence intervals, over at least 3 seeds. Guard against contamination: no generated frames in eval, and no eval scene that seeded any generation prompt.
**Follow-up trap:** *"The DreamGen ablations already did this, didn't they?"* No, and knowing why is the point. DreamGen holds the real budget fixed and adds synthetic data for free, which answers "does adding synthetic data help?" (yes, measurably, up to +8.8% even with real demos available). It does not answer "is synthetic data the best use of this budget?", because there is no budget-matched Arm C. Both questions matter; only the first currently has an answer, and conflating them is exactly the move the marketing makes.

### Q11 — Your policy is 95% in Isaac Lab and 20% on hardware. Debug it.

**Testing:** systematic debugging rather than a list of things to try.
**Answer:** Do not change anything yet. First, classify the failures by *where in the episode* they occur. Approach-phase failures point at perception; contact-phase failures point at dynamics; post-contact failures point at control. Second, run the two-number decomposition: hold dynamics simulated and feed real imagery to get the appearance drop; take vision out of the loop with a state-based policy on hardware to get the dynamics drop. Third, check the boring things that account for a surprising share of these: control frequency mismatch between sim and the real controller, action-space mismatch (position targets versus torques), unit and coordinate-frame errors, and observation latency. Fourth, check seed variance in sim, because a 95% single-seed number is often 80% +/- 12% across seeds.
**Follow-up trap:** *"You've confirmed it's the dynamics gap. Now what, and how much will each fix buy?"* Ranked by expected value per unit effort: (1) system identification on actuators, which is days of work and often the single largest win; (2) an actuator network trained on real torque/position traces, which is the standard fix for the servo-model gap in legged robots; (3) randomise mass 20-30% and friction 0.5x-2.0x and retrain, which costs GPU time and buys robustness at the price of asymptotic performance; (4) add 1-3 steps of action latency, which is nearly free and frequently matters more than it should. Note what is not on the list: generating photorealistic video.

### Q12 — How does Isaac Lab get thousands of environments on one GPU, and what does that cost you?

**Testing:** systems understanding of the simulation substrate.
**Answer:** The win is not a better solver, it is the elimination of the serialisation boundary. Physics stepping, observation assembly, and the policy forward and backward pass all live in the same device memory as torch tensors, so nothing is copied to host and nothing is pickled across a process boundary. That is why the Isaac Gym generation trained ANYmal locomotion in minutes on one GPU where CPU clusters took hours to days, and why typical locomotion configs run 2,048 to 4,096 parallel environments. The costs: all environments must step in lockstep with the same timestep, so heterogeneous or variable-rate environments are awkward; environments cannot easily have different asset topologies; and rendering does not amortise the way physics does, so adding cameras collapses throughput.
**Follow-up trap:** *"So why not just run 4,096 environments with cameras?"* Because you will be GPU-memory-bound and render-bound long before you are physics-bound, and the render cost is roughly linear in environment count where the physics step is heavily batched. The standard mitigations are training state-based first and adding vision late, tiled/batched rendering, rendering at lower resolution or lower frequency than the control loop, or replacing live rendering with offline viewpoint-randomised renders. Also note that Isaac Sim 5.1's stated floor is a 16 GB RTX 4080; that is a floor for the simulator, not for a 4,096-environment vision job.

### Q13 — What is the role of OpenUSD and PhysX here, and why should anyone outside robotics care?

**Testing:** whether you understand the substrate or just the models.
**Answer:** OpenUSD is a composition system, not merely a file format: scenes are layered and referenced with an explicit strength ordering, which is what makes procedural scene generation tractable. The UsdPhysics schema standardises rigid bodies, colliders, joints and physical materials inside USD so that mass, friction and articulation travel with the asset rather than living in an engine-specific project file. PhysX is the GPU rigid-body engine with a reduced-coordinate articulation solver. The reason anyone outside robotics should care is the interoperability argument: your scene is data with a schema, so it survives an engine change. Isaac Lab 3.0's multi-backend physics abstraction over PhysX, Newton and OVPhysX is that bet being cashed.
**Follow-up trap:** *"If the scene is portable, is the trained policy portable?"* No, and the gap between those two statements is the interesting part. USD portability guarantees geometry and declared physical properties transfer. It does not guarantee the *solver behaviour* transfers, and a policy trained against PhysX has absorbed PhysX's specific contact resolution, penetration bias and effective compliance at your substep count. Swapping to Newton is a distribution shift for the policy even when the USD file is byte-identical. That is why solver settings belong in your randomisation ranges, not in a config file nobody varies.

### Q14 — You are a Principal engineer at a non-robotics company. When is any of this relevant to you?

**Testing:** judgement about scope, and honesty about relevance. Interviewers respect a candidate who says "mostly not".
**Answer:** Mostly it is not, and say so. Three transferable pieces. First, **synthetic-data economics**: the mixing-ratio question, the diversity-collapse failure mode, and the contamination guards are identical whether you are mixing generated video into a robot policy or generated text into an LLM SFT set, and the 1:1 co-training ratio is the same order as what works for synthetic text. Second, **evaluating a vendor stack**: the three-bin sort (benchmarked / internally evaluated / asserted) is a reusable habit and it is what a design review actually needs. Third, **licence-as-architecture**: the attribution-propagation clause is a data-provenance requirement imposed by a contract, and that pattern recurs across every open-weight model you might build on. The domain-specific parts, PhysX solver behaviour and USD authoring, are genuinely not your problem.
**Follow-up trap:** *"Then why should we hire someone who spent time learning this?"* Because the failure mode it teaches is the most expensive one in applied AI: optimising a proxy metric that is uncorrelated with the outcome. Video models at 19-22% physical adherence with excellent FVD scores are the cleanest available illustration that a good number on the wrong axis is worse than no number, because it manufactures confidence. If you can carry that lesson from robots to your recommender's offline NDCG or your RAG system's retrieval recall, the time was well spent. Do not oversell it beyond that.

### Q15 — What would change your mind about the strong "learned simulator" claim?

**Testing:** intellectual honesty and falsifiability.
**Answer:** A published result with all four of these properties: a policy trained predominantly or entirely inside a generative WFM; deployed on real hardware; in an environment with no data in the model's training set; beating a matched-budget baseline trained in a physics simulator, on a benchmark the authors did not design. V-JEPA 2's zero-shot Franka pick-and-place is the closest structural analogue in the literature and it is a joint-embedding model, not a video generator. Absent that, the defensible claim is augmentation, not replacement.
**Follow-up trap:** *"Isn't that an unfairly high bar for an 18-month-old field?"* It is a high bar and it is exactly the bar the marketing claims to have cleared, which is the whole point. Lower the bar and the claim gets weaker with it: "generated video is useful training data" is well supported and worth building on. The bar is only unfair if you insist on the strong framing, and the honest move is to accept the weaker claim rather than to argue the bar down.

## Red flags that fail you

- Calling Cosmos "a simulator" or proposing to run an RL loop inside it. This is the single fastest way to reveal you have not thought about `reset()` and `step()`.
- Describing the NVIDIA Open Model License as "open source" without mentioning that it is revocable, guardrail-conditional and attribution-propagating.
- Quoting "9,000 trillion tokens" or "20 million hours" approvingly as evidence of quality. Scale figures are inputs, not results.
- Proposing to disable the guardrails because your use case is legitimate. It is an automatic licence termination.
- Reporting FVD, LPIPS or human-preference scores as evidence that synthetic data will improve a policy. The correlation with physical correctness is close to zero.
- Suggesting photorealism as the fix for a policy that fails at the moment of contact.
- Claiming synthetic data can replace real data, or citing DreamGen as evidence for it. Every published win is a co-training win with real data in the mixture.
- Reporting a sim-to-real number from a single seed, or a policy success rate without a trial count.
- Not knowing that Cosmos and GR00T are different layers, or attributing GR00T's capability to Cosmos when its pretraining mixture contains four or five distinct data sources.
- Being unable to name a single case where this stack is the wrong choice. Every technology has one; a candidate who cannot find it has not evaluated it.
- Ignoring the hardware assumption. "We'll just run it in CI" when Isaac Sim's floor is a 16 GB RTX 4080 and there is no CPU path.

## Cheat card

```
COSMOS 1.0 (arXiv 2501.03575, 7 Jan 2025; v3 9 Jul 2025)
  diffusion WFM : 7B / 14B, Text2World + Video2World
  autoregressive: 4B / 12B base, 5B / 13B Video2World
  output        : 121 frames = 5 s @ 24 fps @ 1280x704 (Video2World: next 120)
  ratios        : 960x960 / 960x704 / 704x960 / 1280x704 / 704x1280; fps 12-40
  prompt cap    : <300 words. BF16 only. Linux only. Ampere/Hopper/Blackwell.
  inference     : 7B ~380 s, 14B ~590 s per clip on ONE H100
  peak VRAM 7B  : 74.0 -> 57.1 -> 38.5 -> 38.3 -> 24.4 GB by offload tier
  peak VRAM 14B : >80 -> 70.5 -> 51.9 -> 51.7 -> 39.0 GB

COSMOS 2.5 / 3
  Predict2.5    : 2B + 14B, unified T2W/I2W/V2W, 200M clips, up to 30 s output,
                  Cosmos Reason 1 (7B) as text encoder
  Transfer2.5   : 2B, 3.5x smaller than Transfer1-7B, control = edge/blur/
                  depth/segmentation, up to +60% 3D lane & cuboid detection
                  vs Transfer1-7B-Sample-AV (LATR / BEVFormer)
  Reason        : Reason1 7B; Reason2 at 2B / 8B / 32B
  Cosmos 3      : arXiv 2606.02800, Jun 2026, omnimodal Mixture-of-Transformers

TOKENIZER  {C|D}{I|V}<t>x<s>x<s>
  spatial 8x8 or 16x16 | temporal 4x or 8x | max total 2048x (8*16*16)
  CV8x8x8 continuous video; DV8x16x16 discrete video
  121x1280x704x3 = 327M raw values -> ~211,200 tokens (~1,550x fewer elements)

DATA PIPELINE  (arguably the real product)
  20M hours raw -> ~100M clips
  40 days Hopper | 14 days Blackwell | 3.4 years CPU  (~89x)
  L40S has NVDEC+NVENC; H100 has NVDEC only -> H100 is wrong for re-encode
  "9,000 trillion tokens" = whole UNCURATED corpus tokenised.
  Curated training set is order 2.1e13 (~21T). Headline is ~430x higher.

GUARDRAIL (4 parts, licence-mandatory)
  in : keyword blocklist + Aegis (LlamaGuard on Llama2-7B, 13 risk categories)
  out: SigLIP multi-class video safety filter + RetinaFace blur, faces >20x20 px

LICENCE  NVIDIA Open Model License, dated 2025-01-06
  commercial OK, derivatives OK, NVIDIA disclaims output ownership
  REVOCABLE | auto-terminates on guardrail circumvention | auto-terminates on
  patent/copyright suit | "Built on NVIDIA Cosmos" attribution propagates to
  models trained on OUTPUTS | Delaware law, Santa Clara County

SIM SUBSTRATE
  OpenUSD scene format + UsdPhysics schema | PhysX GPU rigid body
  Isaac Sim 5.0 + Isaac Lab 2.2 GA at SIGGRAPH, Aug 2025
  Isaac Sim 5.1 floor: RTX 4080, 16 GB VRAM, 32 GB RAM. No AMD/Apple/CPU path.
  Isaac Lab bench GPUs: L40 48GB, RTX Pro 6000 96GB, RTX 5090 32GB
  Isaac Lab 3.0: multi-backend physics (PhysX / Newton / OVPhysX)
  typical locomotion: 2,048-4,096 parallel envs, one GPU

SYNTHETIC-DATA NUMBERS THAT MATTER
  co-training ratio          1:1 neural : real  (DreamGen / GR00T)
  volume                     3,000 neural traj/task sim; ~100/task real
  GR00T N1.5 vs N1           38.3% vs 13.1% on 12 DreamGen tasks
  gain with real data present up to +8.8%
  diversity-collapse alarm   eff_rank(synth)/eff_rank(real) < ~0.6
  physics-adherence regime   19-22% for frontier video models

COST ARITHMETIC (my derivation, not a published study)
  1 H100-hour ~= 9.5 clips ~= 47 s of generated video (7B)
  100 h synthetic video ~= 7,600 H100-hours ~= $23k-30k @ $3-4/hr
  same $30k ~= 400-750 teleop hours ~= 24k-45k real demos @ 60/hr

THE TWO-HALF RULE
  appearance gap -> Transfer / randomisation / real-image co-training HELP
  dynamics gap   -> sys-id, actuator nets, randomised dynamics, real data
  photorealism does not fix a friction coefficient
```

## Sources

- [Cosmos World Foundation Model Platform for Physical AI (arXiv:2501.03575)](https://arxiv.org/abs/2501.03575) — accessed 2026-08-05
- [Cosmos 3: Omnimodal World Models for Physical AI (arXiv:2606.02800)](https://arxiv.org/abs/2606.02800) — accessed 2026-08-05
- [nvidia/Cosmos-1.0-Diffusion-7B-Text2World model card (model versions, frame counts, resolutions, inference time, VRAM table)](https://huggingface.co/nvidia/Cosmos-1.0-Diffusion-7B-Text2World) — accessed 2026-08-05
- [NVIDIA Open Model License Agreement, version dated 6 January 2025](https://www.nvidia.com/en-us/agreements/enterprise-software/nvidia-open-model-license) — accessed 2026-08-05
- [Cosmos Guardrail documentation (Aegis, blocklist, SigLIP filter, RetinaFace 20x20 threshold)](https://docs.nvidia.com/cosmos/latest/guardrail.html) — accessed 2026-08-05
- [nvidia/Cosmos-1.0-Guardrail model card](https://huggingface.co/nvidia/Cosmos-1.0-Guardrail) — accessed 2026-08-05
- [Cosmos Tokenizer research page (compression rates, PSNR comparisons)](https://research.nvidia.com/labs/cosmos-lab/cosmos-tokenizer/) — accessed 2026-08-05
- [Cosmos Predict 2.5 & Transfer 2.5 announcement, Hugging Face blog (200M clips, 30 s horizon, 3.5x smaller, 60% detection gain) — VENDOR BLOG, treat as claim](https://huggingface.co/blog/nvidia/cosmos-predict-and-transfer2-5) — accessed 2026-08-05
- [nvidia/Cosmos-Transfer2.5-2B model card](https://huggingface.co/nvidia/Cosmos-Transfer2.5-2B) — accessed 2026-08-05
- [nvidia/Cosmos-Predict2.5-2B model card](https://huggingface.co/nvidia/Cosmos-Predict2.5-2B) — accessed 2026-08-05
- [NVIDIA Cosmos Reason 2 announcement (2B / 8B / 32B) — VENDOR BLOG](https://huggingface.co/blog/nvidia/nvidia-cosmos-reason-2-brings-advanced-reasoning) — accessed 2026-08-05
- [NVIDIA Makes Cosmos World Foundation Models Openly Available (CES announcement, 20M hours, curation timings) — VENDOR BLOG](https://blogs.nvidia.com/blog/cosmos-world-foundation-models/) — accessed 2026-08-05
- [Accelerate Custom Video Foundation Model Pipelines with NeMo Framework (curation stages, NVDEC/NVENC, Hopper vs Blackwell timings) — VENDOR BLOG](https://developer.nvidia.com/blog/accelerate-custom-video-foundation-model-pipelines-with-new-nvidia-nemo-framework-capabilities/) — accessed 2026-08-05
- [nvidia-cosmos/cosmos-curate (Cosmos Curator and Dataset Search)](https://github.com/nvidia-cosmos/cosmos-curate) — accessed 2026-08-05
- [DreamGen: Unlocking Generalization in Robot Learning through Neural Trajectories (arXiv:2505.12705)](https://arxiv.org/abs/2505.12705) — accessed 2026-08-05
- [GR00T N1: An Open Foundation Model for Generalist Humanoid Robots (arXiv:2503.14734)](https://arxiv.org/abs/2503.14734) — accessed 2026-08-05
- [GR00T N1.5 research page (38.3% vs 13.1% on DreamGen suite, 1:1 co-training ratio)](https://research.nvidia.com/labs/gear/gr00t-n1_5/) — accessed 2026-08-05
- [Isaac Lab: A GPU-Accelerated Simulation Framework for Multi-Modal Robot Learning (arXiv:2511.04831)](https://arxiv.org/abs/2511.04831) — accessed 2026-08-05
- [General Availability for NVIDIA Isaac Sim 5.0 and Isaac Lab 2.2 — VENDOR BLOG](https://developer.nvidia.com/blog/isaac-sim-and-isaac-lab-are-now-available-for-early-developer-preview/) — accessed 2026-08-05
- [Domain Randomization for Transferring Deep Neural Networks from Simulation to the Real World (Tobin et al., arXiv:1703.06907)](https://arxiv.org/abs/1703.06907) — accessed 2026-08-05
- [Isaac Gym: High Performance GPU-Based Physics Simulation For Robot Learning (arXiv:2108.10470)](https://arxiv.org/abs/2108.10470) — accessed 2026-08-05

## Changelog

- 2026-08-05 — created
