# Video & Diffusion: DiT, Flow Matching, Consistency Models

> **Track:** T26 Frontier AI · **Time:** 2.5h · **Prereqs:** `T26-world-models`, T05 (attention, transformers)
> **Updated:** 2026-08-08
> **Module id:** `T26-video-generation` · **Tags:** generative, diffusion, video, dit, flow-matching, consistency-models

## The 30-second version

Every serious 2026 video generator — Sora 2, Veo 3, Kling, Hailuo, Seedance, WAN, Hunyuan Video, Mochi, CogVideoX, LTX-Video — runs on the same backbone shape: a **diffusion transformer (DiT)**, which replaced diffusion's original U-Net with a ViT-style transformer operating on patches of a compressed latent, because Peebles and Xie (arXiv 2212.09748, ICCV 2023) showed the U-Net's convolutional inductive bias was never necessary and that FID scales predictably with transformer Gflops the same way loss scales with compute for LLMs, letting video-gen ride the same scaling recipe. What changed between 2023 and 2026 is the training objective and the sampler, not the backbone: **flow matching** (Lipman et al., 2022) reframes the problem as regressing a velocity field along a fixed, often straight-line ("rectified") path from noise to data instead of reversing a stochastic denoising process, which is a simpler regression loss and produces trajectories cheap enough to integrate in far fewer steps, and by 2024-25 it displaced classic DDPM-style training as the production default (Stable Diffusion 3, FLUX, Veo, Movie Gen) because a straighter ODE means fewer sampling steps at serving time, and at millions of generations a day a 10x latency cut is the entire business case. **Consistency models** (Song, Dhariwal, Chen, Sutskever, arXiv 2303.01469) push the same idea further, distilling a many-step teacher into a student that can jump from any point on the trajectory straight to the clean sample in 1-4 steps, cutting inference 10-100x at a real, measurable quality cost that production teams partially recover with reward-guided distillation. What has **not** been solved by any of this stack, and this is the honest position to hold in an interview: temporal consistency past 10-20 seconds and physical controllability remain open problems, not engineering details — every DiT pays quadratic attention cost in the number of spacetime tokens, so long, high-resolution video is expensive by construction, and even the strongest 2026 models (Veo 3, Sora 2) show visibly different, still-present failure modes (color jitter and frame freezing versus smoother motion but its own artifacts), while VBench2's physics-and-commonsense dimension shows every model, including the frontier ones, still has real headroom on physical plausibility.

## Why this gets asked

The interviewer wants to know whether you can separate the architecture (DiT: a scaling recipe) from the training objective (flow matching: a loss reformulation) from the inference trick (consistency distillation: a step-count compression), because candidates who have only used a video-gen product tend to describe all three as one undifferentiated "the AI makes video now" black box. The production failure this maps to is concrete and expensive: a team picks a distilled few-step model for cost reasons, ships it, and only discovers the quality gap versus the full multi-step teacher when a client-facing deliverable comes back with visible artifacts a demo clip never showed — because the demo was cherry-picked at 4-6 seconds and the production use case needed 20. The second failure mode, and the one that separates staff-level candidates, is treating a video generator's output as ground truth about physical plausibility: someone proposes using a diffusion video model to synthesize training data for a robotics policy, or as a world model for planning, without knowing that pixel-space video generation optimizes for visual plausibility, not physical consistency, and VBench2's own physics dimension exists specifically because models routinely produce videos that look right at a glance and violate object permanence or basic dynamics on inspection.

---

## Lineage: past → present → future

**What came before.** Image generation before diffusion was dominated by **GANs** (Goodfellow et al., 2014, through StyleGAN2/3), which produced sharp, high-fidelity images fast (a single forward pass) but were notoriously unstable to train — mode collapse, discriminator/generator balance requiring careful tuning, and poor sample diversity that made them hard to condition reliably on open-ended text prompts. **Denoising diffusion probabilistic models** (DDPM, Ho et al., 2020) replaced adversarial training with a much more stable objective: learn to reverse a fixed noising process by predicting the noise added at each step, trained with plain regression, which fixed the instability and diversity problems decisively. **Latent diffusion** (Rombach et al., "High-Resolution Image Synthesis with Latent Diffusion Models," CVPR 2022, the paper behind Stable Diffusion) made this tractable at scale by running the diffusion process in a compressed VAE latent space rather than pixel space, cutting compute by roughly an order of magnitude. The specific pain that pushed the field past this generation was twofold: DDPM sampling required dozens to hundreds of sequential network evaluations to reverse the noising process, making inference slow and expensive at serving scale, and the U-Net backbone underlying nearly every diffusion model carried a convolutional inductive bias that, unlike a transformer, did not scale predictably with added compute — doubling a U-Net's parameters did not reliably buy the same quality improvement doubling a transformer's parameters did for language models, so diffusion could not straightforwardly ride the compute-scaling recipe that had worked everywhere else.

**Where it stands now.** DiT (Peebles and Xie, arXiv 2212.09748, ICCV 2023) settled the architecture question by patchifying a latent-diffusion model's VAE latent into tokens and processing them with a standard transformer instead of a U-Net, using **AdaLN-Zero** conditioning (timestep and class/text embeddings modulate each block via scale, shift, and a gate initialized to zero, so every block starts as an identity function and training is stable from step one) — DiT-XL/2 reached a state-of-the-art **FID of 2.27** on class-conditional ImageNet 256×256, and the paper's core empirical claim, that FID improves predictably as a function of transformer Gflops (depth, width, and token count), is the reason nearly every serious video model since has been built on this backbone rather than a U-Net. Sora's technical report (OpenAI, February 2024) extended the recipe to video by first compressing raw video both spatially and temporally through a VAE-style network, then decomposing the compressed latent into **spacetime patches** that act as transformer tokens exactly the way image patches do for a 2D DiT, which is also what lets these models train on and generate variable resolutions, durations, and aspect ratios from one architecture. On the objective side, **flow matching** (Lipman et al., "Flow Matching for Generative Modeling," 2022) reframes training as directly regressing a velocity field along an arbitrary, chosen probability path connecting noise and data, rather than reversing a specific stochastic differential equation the way diffusion does — the loss is simulation-free plain regression, simpler to implement and reason about than diffusion's score-matching formulation. **Rectified flow** (Liu et al., "Flow Straight and Fast," 2022-23) is the specific, dominant instance: prescribe a straight-line path between the noise and data samples, which minimizes the curvature the sampler has to integrate through and, combined with an iterative "reflow" procedure, allows high-quality generation in very few steps, in the limit one. By 2024-25 flow matching had become the production default rather than a research curiosity: Stable Diffusion 3.5, FLUX (Black Forest Labs; FLUX.2, a 32B-parameter rectified-flow transformer, shipped November 2025), Veo, and Meta's Movie Gen all train with a flow-matching objective, and the shift was driven almost entirely by economics — at the scale of serving millions of generations a day, cutting required sampling steps by an order of magnitude is not a nice-to-have, it is most of the unit-economics story. **Consistency models** (Song et al., arXiv 2303.01469, ICML 2023) sit one layer further downstream, targeting inference cost directly: a model trained (via distillation from a pretrained teacher, or from scratch via "consistency training") to satisfy self-consistency along a trajectory — any point on the same noise-to-data path maps to the same clean output — can generate a sample in a single forward pass instead of an iterative loop. **Latent Consistency Models** (Luo et al., arXiv 2310.04378) brought this to Stable Diffusion specifically: a 768×768 2-4-step distilled model trains in roughly **32 A100-GPU-hours**, cuts inference **10-100x**, and matches 25-50-step DDIM sampling on FID and text-image alignment at moderate step counts, though the efficiency is bought with a real, measurable quality cost at the most aggressive (1-step) settings, which reward-guided distillation variants (RG-LCD) partially claw back. The live disagreement in 2026 is not architecture (DiT has won) but where the field's actual bottleneck sits: temporal consistency at duration beyond roughly 10-20 seconds is unsolved industry-wide, not vendor-specific — independent comparisons in 2026 report Veo 3 producing sharper, more temporally stable motion while Sora 2 shows visible color jittering, brightness shifts, and frame freezing with static optical flow on longer generations, which means the top labs are still failing in different, visible ways rather than having converged on a solved problem.

**Where it's heading.** High confidence (~85%): video DiTs keep scaling and keep getting cheaper per generated second through inference-side tricks that don't require new architecture — block-wise caching of repeated DiT computations across denoising steps (the BWCache line of work), and consistency-style few-step distillation becoming closer to a default training recipe rather than a bolt-on afterthought (MeanFlow-style approaches that target few-step generation in a single training stage rather than distilling a separately-trained multi-step teacher). Medium confidence (~65%): controllability — separating camera trajectory from subject motion, maintaining a specific character's identity across shots, accepting reference images or motion signals as first-class conditioning rather than text-prompt-only — becomes the primary competitive axis among vendors rather than raw visual fidelity, which is already visible in 2026 product differentiation (Kling 3.0's Motion Control and Omni Video separating camera and character motion, Runway Gen-4.5's motion brush and reference-driven character consistency, Veo 3.1 adding reference images), because fidelity has become good enough across the top few vendors that repeatability and directability are what make a workflow usable for real production rather than one-off generation. Genuinely speculative, flagged as such: whether video diffusion models ever become reliable enough on physical consistency to serve as world models for planning or robotics training data, as opposed to remaining tools for visually plausible but physically approximate content generation — VBench2's physics-and-commonsense dimension is explicitly built because this gap is still wide in 2026, and the skepticism `T26-jepa` raises about generative pixel-space prediction as a world-model substrate (spending capacity modeling aleatorically unpredictable detail) applies with full force to video DiTs; my read, offered as a read and not a fact, is that the honest gap between "looks physically right" and "is physically right" narrows slowly and is still open past 2027.

---

## Mental model

```
IMAGE/VIDEO DiT PIPELINE

  raw video/image
        │
        ▼
  ┌──────────────┐
  │  VAE ENCODER  │   compress spatially (and temporally, for video)
  └──────┬───────┘    e.g. 8x spatial downsample
         ▼
  latent tensor  ──patchify──>  SPACETIME PATCHES (= transformer tokens)
                                  video: tokens grow with frames x space,
                                  so attention cost is O((T*H*W)^2)
         │
         ▼
  ┌───────────────────────────────────────────┐
  │  DiT BLOCKS (repeated N times)             │
  │   self-attention over all spacetime tokens │
  │   cross-attention to text/condition embed  │
  │   AdaLN-Zero: (scale, shift, gate) from    │
  │     [timestep + condition] modulate each   │
  │     block; gate init = 0 => block starts   │
  │     as IDENTITY, training stable from t=0  │
  └──────────────────┬──────────────────────────┘
                      ▼
              predict velocity (flow matching)
                 or noise (classic diffusion)
                      │
                      ▼
        INTEGRATE across denoising/flow steps
          diffusion (curved path): 25-1000 steps
          rectified flow (straight path): fewer steps,
             1 step in the reflow limit
          consistency model: JUMP directly, 1-4 steps
                      │
                      ▼
              ┌──────────────┐
              │ VAE DECODER   │ -> pixels
              └──────────────┘

THREE PATHS FROM NOISE TO DATA, SAME ENDPOINTS, DIFFERENT ROUTE
  diffusion (DDPM/score-based): curved, stochastic-ish path,
     many small steps needed to track the curvature accurately
  flow matching / rectified flow: CHOSEN, often straight-line path,
     fewer steps needed because there's less curvature to integrate
  consistency model: doesn't walk the path step by step at all,
     learns to jump from ANY point on it straight to the endpoint
```

The one sentence that separates the three: **DiT is what predicts (a transformer over spacetime patches), flow matching is what it's trained to predict (a velocity field along a chosen path, not a score along an implicit one), and a consistency model is a further distillation that skips walking the path at inference time entirely.**

---

## How it actually works

### DiT: patchify, AdaLN-Zero, and why Gflops predicts FID

A DiT takes a VAE-compressed latent (for a 256×256 image with an 8x spatial downsample, a 32×32×4 latent), divides it into patches the way a ViT divides an image (patch size **2** or **4**, i.e. `2x2` or `4x4` in latent space), flattens each patch to a token, and adds positional embeddings. Each transformer block conditions on the diffusion timestep and any class/text embedding not by prepending a token (as a plain ViT would) but via **adaptive layer norm (AdaLN-Zero)**: the timestep-and-condition embedding is passed through an MLP that regresses a per-block scale, shift, and **gate**, and the gate is initialized so each residual block contributes exactly zero at initialization — every block starts as an identity function, which is what lets DiT-XL-scale models train stably without the careful warmup schedules earlier diffusion transformers needed. The paper's central, load-bearing empirical result is that measured forward-pass Gflops (from depth, width, or token count, i.e. patch size) correlates predictably and monotonically with lower FID, the same scaling-law shape LLM pretraining loss shows against compute — DiT-XL/2 reaches **FID 2.27** on ImageNet 256×256, state of the art at publication, and the practical consequence is that "which config gets the best quality per training FLOP" becomes an answerable scaling question rather than a matter of architecture folklore.

### Extending to video: spacetime patches and the quadratic-cost wall

Sora's approach (OpenAI technical report, February 2024) is the reference shape nearly every 2026 video model follows: compress raw video both spatially and temporally through a VAE-style network into a latent, then decompose that latent into **spacetime patches** — small spatiotemporal chunks that each become one transformer token, encoding both appearance and short-range motion. This is what lets a single architecture train on and generate variable resolution, duration, and aspect ratio without redesign: everything reduces to "how many spacetime patches." The direct consequence, and the number that explains most of video-gen's cost structure, is that self-attention cost is quadratic in **token count**, and token count for video scales with `frames × spatial_patches`, not just spatial resolution the way it does for a single image. Doubling video duration at fixed resolution and frame rate roughly doubles token count and roughly **quadruples** attention cost; doubling both duration and resolution multiplies cost by roughly 16x. This is the structural reason long, high-resolution video generation is expensive by construction, not an implementation detail any one vendor has been sloppy about, and it's why most production video models cap default generation length in the single-digit-to-low-teens seconds and treat longer output as an extrapolation or a stitched-together sequence of shorter generations rather than one native forward pass.

### Flow matching, derived

Diffusion trains a model to predict the score (or equivalently the noise) of a specific, implicitly-defined stochastic process connecting data to a Gaussian prior, and the loss derivation involves the machinery of the reverse-time SDE. Flow matching sidesteps that: pick **any** probability path `p_t(x)` interpolating a simple prior `p_0` (noise) at `t=0` and the data distribution `p_1` at `t=1` — for rectified flow the simplest possible choice, a straight line, `x_t = (1-t) x_0 + t x_1` for a noise sample `x_0` and data sample `x_1` — and train a network `v_theta(x_t, t)` to regress the (in the straight-line case, constant) velocity `x_1 - x_0` along that path via plain L2 regression. This is **simulation-free**: you don't need to run any part of the generative process during training, just sample a noise point, a data point, interpolate, and regress the velocity, which is a substantially simpler loss to implement and reason about than diffusion's noise-prediction-plus-reweighting formulation, and it generalizes diffusion (DDPM's objective is recoverable as one specific choice of path). The practical payoff is at sampling time: because the chosen path can be made close to straight, the ODE the sampler integrates to go from noise to data has much less curvature than a typical diffusion trajectory, so a low-order numerical integrator (even a single Euler step, in the limit) tracks it accurately, which is why models trained this way need far fewer sampling steps for comparable quality. **Reflow** (Liu et al.) pushes this further: after training an initial rectified-flow model, generate synthetic (noise, data) pairs by running the model itself, then retrain on those straighter empirical trajectories, iterating to progressively straighten the learned path and reduce the sampling steps required, in the extreme case to one.

### Consistency models: jump instead of walk

A consistency model exploits a different structural property: along any single deterministic trajectory (probability-flow ODE) connecting a noise sample to its corresponding clean data sample, **every intermediate point should map to the same clean output** if you had a perfect model of that trajectory. Formally, a consistency function `f(x_t, t)` is trained so `f(x_t, t) = f(x_{t'}, t')` for any `t, t'` on the same trajectory, with the boundary condition `f(x_0, 0) = x_0` (identity at the data endpoint). Once trained, generation is a single evaluation: sample noise, evaluate `f`, done — or, for a small quality boost, a handful of alternating noise-injection-and-evaluation steps (2-4 total) rather than the 25-1000 sequential steps a full diffusion or flow-matching sampler needs. Training happens two ways: **consistency distillation**, starting from a pretrained multi-step teacher and training the student to match the teacher's trajectory endpoints, or **consistency training**, learning the property from scratch without a teacher, which is harder to stabilize but avoids the two-stage pipeline. **Latent Consistency Models** (Luo et al., 2023) distill Stable Diffusion specifically, and the production numbers are concrete: a **768×768, 2-4-step** LCM trains in roughly **32 A100-GPU-hours** starting from a pretrained SD checkpoint, delivers a **10-100x** inference speedup, and matches 25-50-step DDIM sampling on FID and text-alignment metrics at 2-4 steps — but the efficiency is bought with a real, measurable quality cost that grows sharply as you push toward true 1-step generation, which is why most production deployments settle on 4 steps rather than 1, and why reward-guided consistency distillation variants exist specifically to recover some of that lost quality by optimizing the single-step (or few-step) output against a learned reward model rather than pure trajectory matching.

---

## Build it from scratch

The minimal thing that demonstrates the actual mechanism, not a toy autoencoder: a tiny DiT block with AdaLN-Zero conditioning, trained with a rectified-flow objective, sampled with a plain Euler integrator. No lab folder exists for this module yet; this sketch is the shape to build one from.

```python
# untested sketch -- minimal DiT block + rectified flow training/sampling.
# Omits: the VAE, patch embedding from real images/video, multi-node
# training, and any conditioning beyond a scalar class label.
import torch
import torch.nn as nn
import torch.nn.functional as F

D, HEADS, N_TOKENS = 384, 6, 64          # toy sizes


class AdaLNZeroBlock(nn.Module):
    """One DiT block. Gate is zero-initialized: block starts as identity."""

    def __init__(self, dim=D, heads=HEADS):
        super().__init__()
        self.norm1 = nn.LayerNorm(dim, elementwise_affine=False)
        self.attn = nn.MultiheadAttention(dim, heads, batch_first=True)
        self.norm2 = nn.LayerNorm(dim, elementwise_affine=False)
        self.mlp = nn.Sequential(nn.Linear(dim, 4 * dim), nn.GELU(), nn.Linear(4 * dim, dim))
        # regress 6 modulation params per block: scale/shift/gate x2 (attn, mlp)
        self.ada = nn.Sequential(nn.SiLU(), nn.Linear(dim, 6 * dim))
        nn.init.zeros_(self.ada[-1].weight)
        nn.init.zeros_(self.ada[-1].bias)          # <-- the "Zero" in AdaLN-Zero

    def forward(self, x, cond):
        s1, b1, g1, s2, b2, g2 = self.ada(cond).chunk(6, dim=-1)   # (B, D) each
        h = self.norm1(x) * (1 + s1.unsqueeze(1)) + b1.unsqueeze(1)
        h, _ = self.attn(h, h, h, need_weights=False)
        x = x + g1.unsqueeze(1) * h                                 # gate starts at 0
        h = self.norm2(x) * (1 + s2.unsqueeze(1)) + b2.unsqueeze(1)
        x = x + g2.unsqueeze(1) * self.mlp(h)
        return x


class ToyDiT(nn.Module):
    def __init__(self, dim=D, depth=6, n_classes=10):
        super().__init__()
        self.time_embed = nn.Sequential(nn.Linear(1, dim), nn.SiLU(), nn.Linear(dim, dim))
        self.class_embed = nn.Embedding(n_classes, dim)
        self.pos = nn.Parameter(torch.zeros(1, N_TOKENS, dim))
        self.blocks = nn.ModuleList([AdaLNZeroBlock(dim) for _ in range(depth)])
        self.out = nn.Linear(dim, dim)

    def forward(self, x_t, t, y):
        """x_t (B, N_TOKENS, D): noisy latent tokens. t (B,1). y (B,) class label.
        Returns predicted VELOCITY (flow matching), not noise."""
        cond = self.time_embed(t) + self.class_embed(y)
        h = x_t + self.pos
        for blk in self.blocks:
            h = blk(h, cond)
        return self.out(h)


def rectified_flow_loss(model, x1, y):
    """x1 (B, N_TOKENS, D): clean data tokens. Straight-line path, simulation-free."""
    B = x1.shape[0]
    x0 = torch.randn_like(x1)                         # noise endpoint
    t = torch.rand(B, 1, device=x1.device)             # uniform t in [0,1]
    x_t = (1 - t).unsqueeze(1) * x0 + t.unsqueeze(1) * x1   # straight-line interpolation
    v_target = x1 - x0                                  # CONSTANT velocity for a straight path
    v_pred = model(x_t, t, y)
    return F.mse_loss(v_pred, v_target)


@torch.no_grad()
def euler_sample(model, y, n_steps=4, dim=D, device="cpu"):
    """Fewer steps than a diffusion sampler because the path is straight.
    n_steps=1 recovers (approximately) a consistency-model-style single jump."""
    x = torch.randn(y.shape[0], N_TOKENS, dim, device=device)
    dt = 1.0 / n_steps
    for i in range(n_steps):
        t = torch.full((y.shape[0], 1), i * dt, device=device)
        v = model(x, t, y)
        x = x + dt * v                                  # first-order Euler step
    return x
```

Two things this sketch makes concrete that are easy to miss reading the papers. First, the rectified-flow **target is constant along a straight path** (`x1 - x0`, independent of `t`), which is exactly why the ODE has low curvature and a coarse integrator tracks it well — a curved diffusion path has a `t`-dependent target and needs finer steps to avoid discretization error. Second, dropping `n_steps` to 1 in `euler_sample` is *not* a consistency model — it's just a single, large, inaccurate Euler step through a network never trained for that regime, and the visible artifact is a blurry, low-detail sample; a real 1-4-step model requires the actual consistency (or reflow) training objective, not merely fewer integration steps applied to a model trained for many.

---

## How it's done in production

Nobody outside a handful of labs trains a frontier video DiT from scratch. The realistic production landscape splits into managed APIs and open weights. **Managed:** Sora 2 (OpenAI, though the standalone Sora app was discontinued April 2026 in favor of API/product integration), Veo 3.1 (Google, via the Gemini API and Vertex AI), Kling 3.0 (Kuaishou), Runway Gen-4.5, Hailuo, Seedance — all closed-weight, billed per generated second, with per-vendor differentiation increasingly centered on controllability (Kling's Motion Control and Omni Video separate camera trajectory from character motion; Runway's motion brush and reference-driven character consistency; Veo 3.1's reference images) rather than raw fidelity, which has converged across the top vendors. **Open weights:** HunyuanVideo, Wan (2.x), Mochi-1, CogVideoX, and LTX-Video, the last explicitly optimized for low-latency, near-real-time generation rather than maximum fidelity, are the realistic self-hosted path, typically requiring multi-H100 serving for anything beyond short, low-resolution clips, with inference-side acceleration (block-wise caching of repeated DiT activations across denoising steps, few-step consistency/LCM-style distillation) doing most of the work to make self-hosting economical.

### Failure-mode table

| Symptom | Cause | Fix |
|---|---|---|
| Object identity drifts or morphs over the course of a generation (a character's face or a product's shape gradually changes) | No native long-range identity anchor in the spacetime-patch attention window; the model has no persistent object representation, only local spatiotemporal coherence within its trained context length | Use reference-image conditioning where the model supports it (Veo 3.1, Runway Gen-4.5) rather than text-only prompting for anything requiring consistent identity across a shot; keep generations within the duration the model was primarily trained/evaluated at, and stitch shorter clips with human-in-the-loop continuity checks rather than trusting a single long native generation |
| Color jittering, brightness shifts, or visible frame freezing with static optical flow on longer clips | Reported specifically in independent 2026 comparisons for Sora 2 on longer generations; the underlying cause is the same quadratic-attention-cost pressure that caps practical native duration, showing up as degraded temporal modeling once a generation pushes past the length/resolution regime the model handles best | Prefer the vendor whose published and independently-verified temporal-stability benchmarks (e.g. VBench2 total score) are strongest for your target duration and resolution; do not assume a vendor's short-demo quality generalizes to your production duration without testing at that duration specifically |
| Video "looks physically right" at a glance but violates object permanence, basic dynamics, or plausible physics on frame-by-frame inspection | Pixel-space (or latent-space) video diffusion optimizes for visual plausibility under the training distribution, not an explicit physical model; nothing in the DiT/flow-matching/consistency-model stack enforces physical consistency as a constraint | Do not use video-gen output as ground truth for anything requiring physical accuracy (robotics training data, engineering visualization); evaluate specifically against a physics/commonsense benchmark dimension (VBench2) rather than only aesthetic-quality metrics, and treat any "looks right" visual inspection as necessary but not sufficient |
| Aggressively distilled few-step (1-2 step) model produces visibly lower detail/quality than the same architecture at 25-50 steps, discovered only after shipping | Few-step consistency/LCM distillation trades quality for latency, and the quality gap widens sharply as step count drops toward 1; a demo evaluated at a comfortable step count (4+) does not represent the 1-2-step regime the team may switch to under cost pressure | Benchmark the exact step count you intend to ship at, not a more conservative one, before committing; consider reward-guided distillation variants if the aggressive step count is a hard requirement, and budget for a visible quality delta versus the full multi-step teacher rather than assuming distillation is free |
| Video generation job runs out of memory or times out only at higher resolution/duration combinations that worked fine individually | Attention cost is quadratic in total spacetime-token count (`frames × spatial patches`), so resolution and duration multiply rather than add in their effect on cost; a config that's fine at each dimension alone can exceed budget at both increased together | Budget compute against total token count, not resolution or duration independently; test the actual combination you intend to serve, and consider whether the increase is better served by post-hoc upscaling/frame-interpolation of a lower-token-count native generation rather than a larger native generation |

---

## Tradeoffs & when NOT to use it

**When you need frame-accurate determinism or guaranteed brand/character consistency across many shots.** Diffusion-based video generation remains fundamentally stochastic; even with reference-image conditioning, exact pixel-level consistency of a product or character across a multi-shot campaign is not reliably guaranteed the way a traditional 3D/CGI pipeline with an explicit asset provides it. For hero brand assets where consistency is contractually or legally load-bearing, a traditional rendering pipeline, or heavy human review of generated output, is the safer default.

**When you need long-form (multi-minute), narratively coherent output.** The quadratic attention cost and the empirically observed degradation past roughly 10-20 seconds mean native long-form generation is not where the field is in 2026. The realistic production pattern is generating short clips and stitching them with human editorial oversight for continuity, not trusting a single long native generation.

**When physical accuracy is the requirement, not visual plausibility.** Training data for robotics policies, engineering visualization, or anything where "looks right" must also "is right" should use an actual physics simulator (see `T26-nvidia-cosmos`, Isaac Sim) rather than a video diffusion model, because nothing in the DiT/flow-matching stack constrains output to obey physics, only to look statistically consistent with training footage, and VBench2's physics-and-commonsense scores show every current model has a real, measured gap here.

**When you're cost-sensitive and the use case tolerates a real quality hit.** Aggressive few-step consistency distillation is the right call for high-volume, lower-stakes generation (social content variants, rapid prototyping, storyboard drafts) where a visible quality delta against a 50-step reference is an acceptable trade for a 10-100x cost and latency cut — but say so explicitly to stakeholders rather than letting the tradeoff surface as a surprise after launch.

**Where it's clearly right.** Rapid creative iteration, storyboarding, short-form social and marketing content, pre-visualization for film/advertising where a human reviews and often re-shoots the final asset, and any workflow where the generated video is a draft or reference rather than the final deliverable — the genuinely large and growing space where current temporal-consistency and physical-accuracy limitations don't block the use case.

---

## Interview questions

### Q1 — What did DiT actually change versus U-Net-based diffusion, and why does it matter beyond "transformers are trendy"?
**Testing:** whether you know the specific architectural and empirical claim, not just that DiT exists.
**Answer:** DiT (Peebles and Xie, arXiv 2212.09748) replaces the U-Net backbone in latent diffusion with a ViT-style transformer operating on patchified latent tokens, using AdaLN-Zero for timestep/condition modulation. The result that matters isn't aesthetic, it's a scaling law: FID improves predictably as a function of transformer Gflops (depth, width, token count), the same shape as LLM pretraining scaling curves, which the convolutional U-Net didn't offer as cleanly. DiT-XL/2 hit a state-of-the-art FID of 2.27 on ImageNet 256×256.
**Follow-up trap:** "So U-Nets are obsolete?" Overstated — U-Nets remain competitive and cheaper at smaller scale, and the claim is specifically that the U-Net's inductive bias isn't *necessary* for quality at scale, not that it's harmful at any scale. The honest framing is DiT wins when you have the compute to exploit the scaling curve; at small scale the difference is much less decisive.

### Q2 — Explain AdaLN-Zero and why the gate is initialized to zero specifically.
**Testing:** mechanical understanding of a detail that's easy to hand-wave.
**Answer:** Each DiT block's timestep-and-condition embedding regresses a scale, shift, and gate per block via an MLP; the gate multiplies the block's residual contribution. Zero-initializing that gate's final linear layer means every block starts training as an exact identity function — the network begins as a no-op and gradually learns to use each block, which is what gives DiT-scale training stability from the first step without a careful warmup schedule that earlier diffusion-transformer variants needed.
**Follow-up trap:** "Isn't zero-init just standard residual-network practice?" Not quite the same thing — a standard residual zero-init typically zeros a final conv/linear layer's weights so the residual branch starts near-zero; AdaLN-Zero specifically routes that zero-init through a *conditioning-dependent gate*, so the block's contribution is zero at init regardless of the timestep/condition input, which is a stronger and more specific guarantee than generic residual zero-init.

### Q3 — What is flow matching, and how does its training objective differ from classic diffusion's?
**Testing:** the actual mathematical distinction, not a vague "it's faster."
**Answer:** Diffusion trains a network to predict the score (or noise) of a specific, implicitly defined reverse-time SDE. Flow matching instead picks an explicit probability path connecting a noise prior to the data distribution — for rectified flow, a straight line `x_t = (1-t)x_0 + t x_1` — and regresses the velocity along that path (`x1 - x0` for the straight-line case) via plain, simulation-free L2 loss. It's a more general framework (diffusion is recoverable as one specific path choice) with a simpler loss to implement.
**Follow-up trap:** "If it's just a different path choice, why does it sample faster?" Because the *chosen* path can be made close to straight, which has low curvature, so a coarse (even single-step, in the reflow limit) numerical integrator tracks it accurately; a typical diffusion path is curved by construction and needs finer steps to avoid discretization error. The speed gain comes from the geometry of the chosen path, not from the loss formulation alone.

### Q4 — What is "reflow" and what problem does it solve?
**Testing:** whether you understand rectified flow beyond the initial straight-line training.
**Answer:** After training an initial rectified-flow model, you generate synthetic (noise, data) pairs by actually running the trained model's sampler, then retrain on those empirical trajectories. Because the model's own generated pairs trace straighter effective paths than the original random pairing of noise and data samples, iterating this process progressively straightens the learned flow, further reducing the number of sampling steps needed for a given quality bar, in the limit approaching one-step generation.
**Follow-up trap:** "Doesn't retraining on the model's own outputs risk compounding its own errors?" A fair concern and a real limitation — reflow is a form of self-distillation, and quality can degrade if iterated too aggressively without validation; production use typically limits reflow to one or two rounds and validates against held-out quality metrics rather than iterating blindly.

### Q5 — What is a consistency model, and how is it different from just running fewer diffusion sampling steps?
**Testing:** the distinction between "trained for few-step generation" and "diffusion model run with a truncated schedule."
**Answer:** A consistency model is explicitly trained so that any point along a deterministic noise-to-data trajectory maps to the same clean output — the self-consistency property `f(x_t, t) = f(x_{t'}, t')` for points on the same trajectory. This lets it generate in one evaluation (or a handful, 2-4, for a quality boost), trained via distillation from a multi-step teacher or from scratch. Simply running a standard diffusion or flow-matching model with fewer integration steps than it was designed for produces a blurry, degraded sample, because the network was never trained to be accurate at that coarse a step size.
**Follow-up trap:** "So a consistency model is always the right choice for low latency?" No — LCM-style distillation trades real, measurable quality for the speedup, worse as you push toward 1 step, and reward-guided variants only partially recover it. It's the right choice when the use case tolerates that quality delta, not a strictly-better replacement for multi-step sampling.

### Q6 — Why is video generation dramatically more expensive than image generation on the same DiT architecture?
**Testing:** whether you can quantify the cost driver rather than just say "video has more data."
**Answer:** Self-attention cost in a DiT is quadratic in token count, and video token count scales with `frames × spatial_patches`, not spatial resolution alone. Doubling duration at fixed resolution and frame rate roughly doubles token count and roughly quadruples attention cost; doubling both duration and resolution together multiplies cost by roughly 16x. This is a structural property of the architecture, not an implementation inefficiency any one vendor has failed to fix.
**Follow-up trap:** "Couldn't you just use a longer, more efficient attention mechanism, like linear or sparse attention?" Some production systems do use factorized or windowed spacetime attention to reduce this cost, but it's a real quality/efficiency tradeoff, not a free lunch — restricting attention's receptive field is part of why long-duration temporal consistency (the model losing track of an object's identity or motion over time) is a live, unsolved problem rather than a solved one with a known fix.

### Q7 — A client complains that a video model's demo looked flawless but their production 30-second generations show color jitter and frame freezing. What's going on and how do you respond?
**Testing:** operational judgment connecting a known, named failure mode to a debugging/communication response.
**Answer:** This matches a documented, vendor-specific failure mode (reported for Sora 2 specifically in independent 2026 comparisons) tied to the same quadratic-attention-cost pressure that caps practical native generation length — quality and temporal stability degrade once a generation pushes past the duration/resolution regime a model was primarily trained and evaluated at. The response: test the exact target duration and resolution before committing to a vendor rather than trusting a short demo, and check independently-verified temporal-stability benchmarks (VBench2 total score, not just marketing claims) for that specific regime, since different vendors show measurably different degradation curves at the same duration.
**Follow-up trap:** "Isn't this just a quality bug the vendor will fix?" Treat it as a structural limitation of the current generation of models until proven otherwise, not a bug — the underlying cause (attention cost scaling with total token count) is shared across the entire DiT-based industry, so switching vendors may shift where the degradation shows up but is unlikely to eliminate it at your target duration in 2026.

### Q8 — Someone proposes using a video diffusion model to generate synthetic training data for a robot manipulation policy. What's your position?
**Testing:** whether you understand the gap between visual plausibility and physical accuracy, connecting to the world-models material.
**Answer:** Push back specifically, not generally — video diffusion models optimize for visual plausibility under the training distribution, not an explicit physical constraint, and VBench2's physics-and-commonsense dimension exists precisely because current models, including frontier ones, routinely produce output that looks right but violates object permanence or basic dynamics on inspection. For robot training data specifically, an actual physics simulator (Isaac Sim, MuJoCo) with domain randomization is the safer default; a generative video model is appropriate for pre-visualization or human-reviewed reference, not as a silent source of physically-grounded training signal.
**Follow-up trap:** "But V-JEPA 2-AC uses learned representations for robot control successfully — why is this different?" V-JEPA 2-AC (see `T26-jepa`) is explicitly action-conditioned and predicts in a learned *embedding* space trained against real robot trajectories with a specific downstream control objective, not pixel-space video generation optimized for visual appeal; conflating "a learned model helped a robot" with "any generative video model is a valid physics source" is exactly the category error this question is testing for.

### Q9 — How would you evaluate a new video generation model release without being fooled by a cherry-picked demo reel?
**Testing:** practical evaluation methodology, staff-level skepticism.
**Answer:** Run your own prompts at your actual target duration and resolution rather than trusting vendor-selected examples, since demo reels are near-universally cherry-picked at short, favorable durations. Use a structured benchmark with named sub-dimensions rather than a single aggregate score — VBench2 decomposes into consistency (subject/background), physics-and-commonsense, human motion, and creative composition, which lets you see specifically where a model is strong or weak rather than trusting one number. Cross-check against independent third-party comparisons (not just the vendor's own reported numbers) since self-reported benchmark selection is exactly the failure mode this question is probing for.
**Follow-up trap:** "Is a high VBench2 total score sufficient to greenlight a model for production?" No — VBench2 measures relative model quality on its own prompt/task distribution, which may not match your production use case's specific duration, resolution, or subject matter; a strong aggregate score is a reason to shortlist a model for your own targeted testing, not a substitute for it.

### Q10 — Staff level: you're deciding between a full multi-step flow-matching model and an aggressively-distilled few-step consistency model for a production video feature. Walk through the decision.
**Testing:** ability to frame a genuine cost/quality tradeoff as an explicit decision rather than defaulting to either the newest technique or the highest-fidelity one.
**Answer:** Start from the actual product requirement: what's the acceptable latency and cost per generation, and how visible would the quality delta be to the end user at that step count. Benchmark the exact step count you intend to ship at (not a more conservative one) against the full multi-step teacher on your own content distribution, since published FID/alignment numbers are measured on the benchmark's distribution, not necessarily yours. If the use case is high-volume and lower-stakes (draft variants, rapid iteration), the 10-100x cost cut from few-step distillation is usually the right call even with a visible quality delta; if the use case is a final, client-facing deliverable, the quality delta is often not acceptable and the full multi-step (or moderate 4-8-step) model is the safer default, with reward-guided distillation considered as a middle ground if latency is still a hard constraint.
**Follow-up trap:** "Why not just always use the highest step count for best quality, since compute is cheap?" At production scale, "compute is cheap" stops being true — a 10x-100x cost multiplier across millions of generations is the actual unit-economics story that drove the entire industry's 2024-25 shift toward flow matching and few-step distillation in the first place; treating step count as a free quality knob ignores the reason this whole subfield exists.

### Q11 — Why did the industry shift from classic DDPM-style diffusion training to flow matching between 2024 and 2025, specifically?
**Testing:** whether you understand this as an economic decision with a technical mechanism, not just "flow matching is newer."
**Answer:** Flow matching's chosen, often-straight probability paths produce ODEs with lower curvature than a typical diffusion trajectory, so far fewer sampling steps are needed for comparable quality — and at the scale of serving millions of image/video generations a day, a 10x reduction in required sampling steps is a direct, large cut to serving cost and latency, which is most of the business case. Stable Diffusion 3.5, FLUX, Veo, and Movie Gen all adopted flow-matching objectives specifically for this reason by 2024-25.
**Follow-up trap:** "Does flow matching also improve sample quality, or just speed?" The primary, unambiguous win is sampling efficiency; quality claims are more mixed and depend heavily on model scale and training data, so the honest answer leads with the efficiency case rather than overselling a quality advantage that isn't the main documented driver of adoption.

### Q12 — What's the single biggest open problem in video generation as of August 2026, and what would change your mind about its status?
**Testing:** whether you can name a genuinely unsolved problem with evidence, and state what would update the assessment, rather than picking a safe non-answer.
**Answer:** Temporal consistency and physical plausibility at duration beyond roughly 10-20 seconds, driven structurally by quadratic attention cost over spacetime tokens. Evidence: independent 2026 comparisons show top models (Sora 2, Veo 3) both degrading in different, visible ways past short durations, and VBench2's physics-and-commonsense dimension shows a persistent gap across the field, not just weaker vendors. What would change my mind: a model demonstrating VBench2-comparable or better physics/consistency scores at native generation lengths of a minute or more, verified independently rather than on vendor-selected clips, or an architectural change (sub-quadratic spacetime attention with no measured quality regression) that removes the cost pressure driving the current duration cap.
**Follow-up trap:** "Isn't this just a compute-scaling problem that bigger models and more GPUs eventually solve?" Partially, but not obviously entirely — the quadratic cost means brute-force scaling hits diminishing returns fast for duration specifically (doubling duration alone roughly quadruples cost at fixed resolution), so the more likely path is architectural (sub-quadratic attention variants, hierarchical/factorized spacetime attention) rather than pure scale, and claiming "just scale it" without naming the specific mechanism is a weaker answer than naming the cost structure directly.

---

## Red flags that fail you

- Describing DiT, flow matching, and consistency models as interchangeable synonyms for "fast diffusion." They are three separable layers: backbone architecture, training objective, and inference-time distillation.
- Claiming video generation has "solved" temporal consistency because a short demo clip looked good. VBench2 and independent 2026 comparisons show every frontier model still has visible, distinct failure modes past short durations.
- Proposing to use a video diffusion model as a source of physically-accurate training data or a world model without qualification. Pixel-space video generation optimizes for visual plausibility, not physical constraint satisfaction.
- Not knowing that attention cost in a video DiT is quadratic in total spacetime-token count, meaning duration and resolution multiply their cost impact together, not additively.
- Assuming a distilled few-step (1-2 step) model is quality-equivalent to its multi-step teacher. The quality gap is real and grows sharply as step count drops.
- Claiming U-Nets are obsolete or "wrong" for diffusion. DiT's advantage is a scaling-law argument at sufficient compute, not evidence U-Nets are broken at smaller scale.
- Not being able to explain why AdaLN-Zero's gate is zero-initialized specifically (training stability from step one via identity-function blocks), versus vaguely citing "good practice."

## Cheat card

```
DiT          Peebles & Xie, arXiv 2212.09748, ICCV 2023. Replaces U-Net with
             ViT-style transformer on patchified VAE latent. FID scales
             predictably with Gflops. DiT-XL/2: FID 2.27, ImageNet 256x256.
ADALN-ZERO   timestep+cond -> MLP -> per-block scale/shift/GATE. Gate init=0
             => every block starts as IDENTITY. Training-stability trick.
SPACETIME    video VAE compresses space+time -> patches = tokens. Attention
PATCHES      cost O((frames x spatial_patches)^2). Duration x2 => ~4x cost.
FLOW MATCH   Lipman et al 2022. Regress VELOCITY along a CHOSEN path (not an
             implicit SDE score). Simulation-free L2 regression.
RECTIFIED    straight-line path x_t=(1-t)x0+t*x1, target=(x1-x0) CONSTANT.
FLOW         Low curvature -> fewer sampler steps. "Reflow": retrain on the
             model's own generated pairs to straighten further.
PRODUCTION   SD3.5, FLUX(.2, 32B, Nov 2025), Veo, Movie Gen all flow-matching
ADOPTION     by 2024-25. Driver: 10x fewer steps = 10x cheaper at scale.
CONSISTENCY  Song/Dhariwal/Chen/Sutskever, arXiv 2303.01469, 2023. f(x_t,t)=
MODELS       f(x_t',t') on same trajectory. 1 eval (or 2-4) instead of 25-1000.
LCM          768x768, 2-4 step, ~32 A100-hrs to distill from SD. 10-100x
             faster. Matches 25-50 step DDIM at 2-4 steps; degrades near 1.
VBENCH2      2026 benchmark: consistency, PHYSICS/commonsense, human motion,
             creative composition. Physics dim: every model still has gap.
2026 STATE   Veo3: sharper, more temporally stable. Sora2: color jitter,
             frame freezing on longer clips. Both fail, differently.
NOT SOLVED   temporal consistency >10-20s, physical accuracy (not just
             plausibility), long-form narrative coherence, frame-exact
             brand/character determinism across many shots.
CONTROL      2026 differentiator, not fidelity: Kling3 Motion Control/Omni,
             Runway Gen-4.5 motion brush+ref chars, Veo3.1 reference images.
```

## Sources

- [Scalable Diffusion Models with Transformers (Peebles and Xie, arXiv 2212.09748, ICCV 2023)](https://arxiv.org/abs/2212.09748) — accessed 2026-08-08
- [Video generation models as world simulators (Sora technical report, OpenAI, February 2024)](https://openai.com/index/video-generation-models-as-world-simulators/) — accessed 2026-08-08
- [Consistency Models (Song, Dhariwal, Chen, Sutskever, arXiv 2303.01469, ICML 2023)](https://arxiv.org/abs/2303.01469) — accessed 2026-08-08
- [Latent Consistency Models: Synthesizing High-Resolution Images with Few-Step Inference (Luo et al., arXiv 2310.04378)](https://arxiv.org/abs/2310.04378) — accessed 2026-08-08
- [Flow Matching vs Diffusion: How AI Models in 2025 Achieve Faster Sampling at Lower Costs](https://blog.stackademic.com/flow-matching-vs-diffusion-in-2025-faster-sampling-lower-costs-same-quality-ac8f3584ebcb?gi=6f3d6b7689b8) — accessed 2026-08-08
- [AI Video Generation Models: 2026 Complete Guide (WaveSpeed Blog)](https://wavespeed.ai/blog/posts/ai-video-generation-models-2026/) — accessed 2026-08-08
- [Sora 2 vs Veo 3.1 vs Kling Full AI Video Test (Blog Picasso IA)](https://blog.picassoia.com/sora-2-vs-veo-3-1-vs-kling-full-test) — accessed 2026-08-08
- [How to Choose the Best AI Video Generator in 2026 (Kling AI blog)](https://kling.ai/blog/best-ai-video-generator-2026-kling-ai) — accessed 2026-08-08
- [GitHub - Vchitect/VBench: VBench - We Evaluate Video Generation](https://github.com/Vchitect/VBench) — accessed 2026-08-08
- [Survey of Video Diffusion Models: Foundations, Implementations, and Applications (arXiv 2504.16081)](https://arxiv.org/pdf/2504.16081) — accessed 2026-08-08

## Changelog
- 2026-08-08 — created
