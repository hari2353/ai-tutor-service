# Video & Diffusion: DiT, Flow Matching, Consistency Models

> **Track:** T26 Frontier AI · **Time:** 2.5h · **Prereqs:** T05-sampling, T05-quantization · **Updated:** 2026-08-23
> **Module id:** `T26-video-generation` · **Tags:** generative

## The 30-second version

Modern generative media rests on three stacked ideas. First, the **Diffusion Transformer (DiT)** replaced diffusion's traditional convolutional U-Net backbone with a plain transformer over latent patches — and won because transformers scale predictably: more Gflops consistently means lower FID (DiT-XL/2 hit a then-SOTA FID of **2.27** on ImageNet 256×256 while using **119 Gflops** versus ADM-U's 742). Second, **flow matching** reframed training as regressing a velocity field along straight-line interpolation paths from noise to data, turning sampling into an ordinary differential equation solvable in far fewer steps than a stochastic diffusion chain (rectified flow's near-straight paths are why Stable Diffusion 3 and FLUX sample fast). Third, **consistency models/distillation** collapse the trajectory entirely — mapping any point on the generation path straight to its endpoint — cutting video sampling from 50 steps/~60 s to ~4 steps/~10 s, at a real quality cost below ~4 steps. Interviewers care whether you can explain *why* each replaced its predecessor and what each tradeoff buys.

## Why this gets asked

Because "we use a diffusion model" is where most engineers' understanding stops, and hiring loops are full of questions that separate users from understanders: why did every major video/text-to-image system since 2023 (Sora, SD3, FLUX, movie-gen-class models) move off U-Nets onto transformers? What does flow matching actually change mathematically versus DDPM's noise prediction? What do you *lose* when you generate in one step instead of fifty? These are answerable in a whiteboard conversation only if you hold the mechanism — patchification, the velocity regression objective, the consistency boundary condition — not just the vocabulary. There's also a systems dimension interviewers increasingly probe: video generation is compute-bound in a way text generation isn't (a single multi-second clip can cost multiples of a long chat completion), so knowing how step count, resolution, and architecture interact with cost and latency is production knowledge, not trivia.

---

## Lineage: past → present → future

**What came before.** Diffusion models (2020-2022) generated images by learning to reverse a fixed noising process, almost universally with convolutional **U-Net** backbones inherited from PixelCNN++/segmentation practice — ResNet blocks at multiple resolutions with self-attention sprinkled in at low resolutions, down/up sampling paths, skip connections. Sampling meant iterating the learned reversal dozens to hundreds of times (DDPM's original formulation needed **1000** steps; DDIM reduced this but 20-50 remained typical). Latent diffusion (LDM/Stable Diffusion, 2022) made this practical by running the whole process in a VAE's compressed latent space rather than pixel space. The U-Net worked, but it was an architectural accident — nobody had shown convolutions were *necessary* — and its scaling behavior was murky: you couldn't cleanly predict what doubling the compute would buy, and the field had already watched transformers eat language, vision recognition, and audio precisely because their scaling laws were legible.

**Where it stands now.** Three consolidations define the current era. (1) **DiT won the backbone war**: Peebles & Xie (2022) showed a ViT-style transformer operating on latent patches beats U-Nets purely through better scaling — their Gflops-vs-FID curve was monotonic across 12 model configurations, and the headline results (FID 2.27 at 256×256 versus the prior best 3.60; 3.04 at 512×512 versus prior best 3.85) came with *lower* inference flops than predecessors. Every frontier media system since — Sora (spacetime patches), Stable Diffusion 3 ("Scaling Rectified Flow Transformers"), FLUX — is a DiT descendant. (2) **Flow matching became the default training objective**: instead of predicting noise along a stochastic chain, regress the constant velocity `x1 − x0` along linear interpolations; the resulting deterministic ODE samples in fewer steps, gives exact likelihoods via change-of-variables, and rectified-flow variants straighten paths until 1-4 step sampling becomes viable (the engine inside SD3 and FLUX). (3) **Few-step generation went mainstream via consistency distillation**: LCM/Turbo/Lightning-style students learn to jump any point on the trajectory directly to the data endpoint, cutting image sampling from ~30 to ~4 steps and video from 50-step DDIM (~60 s per batch of eight clips on an A100) to 4-step LCM (~10 s) — with perceptual-space supervision advances (PFM, 2026) pushing flow models to 4-8 step native generation without teacher models.

**Where it's heading.** The active fronts, in confidence order. High confidence: few-step/few-second generation keeps collapsing toward interactive latencies (real-time brush-as-you-go editing, on-device generation), because the economics of video make step count the dominant cost dial. Medium-high confidence: architectures diversify beyond dense transformers — sparse MoE DiTs (one 2025 design activates ~458M of ~2B parameters per sample), hourglass/multi-resolution designs recovering conv efficiency inside transformer skeletons, linear-attention/Mamba hybrids chasing video's token-count explosion (a minute of video is vastly more tokens than any text prompt). Contested: whether autoregressive next-scale prediction (VAR-style) or diffusion remains the right paradigm as video length grows, and whether "video generation as world simulation" (see T26-world-models) is a product goal or a research metaphor. The honest read for interviews: the *objectives* (flow matching, consistency) look settled; the *architecture* for long-horizon video does not.

---

## Mental model

```
THREE STACKED REPLACEMENTS:

1. BACKBONE      U-Net (conv, multiscale, murky scaling)
   ───────────►  DiT (transformer over latent patches)
                 WHY: scaling laws are legible — more Gflops => lower FID,
                 monotonically. Same recipe that ate NLP. adaLN injects
                 timestep/class conditioning into every block.
                 EVIDENCE: DiT-XL/2 FID 2.27 @ 256² (prior best 3.60);
                 119 Gflops vs ADM-U's 742.

2. OBJECTIVE     DDPM: predict noise along stochastic chain
   ───────────►  Flow matching: predict velocity v = x1 − x0 along
                 straight lines  x_t = (1−t)x0 + t·x1
                 WHY: sampling = deterministic ODE (Euler), near-straight
                 paths tolerate big steps; exact likelihood possible.
                 Rectified flow re-straightens paths → 1-4 step sampling
                 (engine of SD3 / FLUX).

3. SAMPLING      iterate the ODE/SDE ~20-50 steps
   ───────────►  consistency distillation: map ANY trajectory point
                 straight to the endpoint (few steps: 1-4-8)
                 WHY: video cost ∝ steps × tokens; 50→4 steps ≈ 6x cheaper
                 COST: below ~4 steps quality degrades — blur, lost detail,
                 artifacts. Speed buys quality debt.

GENERATION PATH (all three compose):

 noise z~N(0,I) ──step──► ──step──► ... ──► clean latent ──VAE decode──► pixels
        \_________ fewer steps via straighter paths (flow) ______/
        \___ or skip the middle entirely (consistency: t → 0 jump) ___/
```

The compression to hold: **backbone determines how well you scale, objective determines how straight your path is, distillation determines how few steps you can afford.** Each answers a different interviewer question, and conflating them ("flow matching is faster because it uses a transformer") is the standard tell.

---

## How it actually works

### Diffusion basics, compressed

Diffusion trains a network to reverse a gradual noising process: given a noisy latent `z_t` (noise level indexed by timestep `t`), predict the noise that was added (epsilon-prediction) or equivalently the clean signal, with a squared-error loss against ground truth. Sampling starts from pure Gaussian noise and iterates the learned reversal — originally 1000 DDPM steps, later 20-50 with DDIM-style samplers. Two additions matter for everything downstream: **classifier-free guidance (CFG)** trains the model both conditionally and unconditionally, then extrapolates away from unconditional at sampling time (guidance weight typically 3-9) to sharpen prompt adherence; and **latent diffusion** runs the whole process in a VAE's compressed latent space (e.g., 8x spatial compression), which is what makes the compute tractable at all.

### DiT: replacing the U-Net, and why it won

DiT operates on latent patches exactly like ViT operates on image patches: chop the VAE latent into p×p patches (patch sizes 8, 4, or 2 — smaller patches = more tokens = more compute), embed each as a token, run a plain transformer, project back to latents. DiT models ranged from 33M to 675M parameters and 0.4 to 119 Gflops. Timestep and class/text conditioning enter via **adaLN-Zero**: rather than cross-attention or concatenation, conditioning regresses scale-and-shift parameters (and a gate) applied to every LayerNorm in every block, with gates initialized to zero so each block starts as identity. This conditioning mechanism — not attention itself — was the ablated difference-maker: identical transformers with weaker conditioning (in-context tokens, cross-attention) were dramatically worse in FID.

Why it beat U-Net, precisely:

1. **Legible scaling.** Across 12 configs (DiT-S through XL, patch 8/4/2), forward-pass Gflops correlated monotonically with final FID — the transformer recipe transferred from language/vision-recognition with its scaling behavior intact. U-Nets offered no equivalent predictive knob: their multiscale, asymmetric design resists clean width/depth sweeps, and prior work tuned them by folklore.
2. **Compute efficiency at equal quality.** DiT-XL/2 reached FID 2.27 (256²) at 119 Gflops/sample versus ADM-U's 742 Gflops for worse results; at 512², DiT hit 3.04 FID at 525 Gflops versus ADM-U's 3.85 at 2,813 Gflops — roughly 5x the efficiency.
3. **Model compute beats sampling compute.** The sharpest experimental lesson: DiT-L/2 sampled with 1000 steps (80.7 Tflops/image) produced *worse* FID than DiT-XL/2 with just 128 steps (15.2 Tflops) — 23.7 vs 25.9 FID-10K. Scaling inference steps cannot compensate for a backbone-limited model. Any budget conversation about "more denoising steps for quality" should start here.
4. **Architectural unification.** A transformer over tokens accepts anything expressible as tokens — which is exactly how video entered: Sora's **spacetime patches** treat space-time cubes of latent video as tokens, letting one architecture handle variable resolutions, durations, and aspect ratios without U-Net-style architectural surgery per format. Sora-class models generate up to around a minute of video this way.

The honest counterpoint (interviewers may probe): U-Net's convolutional inductive bias is genuinely more sample-efficient at small scale and lower-latency for high-resolution pixel work — hourglass and U-ViT hybrids exist precisely to recover conv efficiency inside transformer skeletons. DiT won because frontier systems live at scales where scaling-law legibility dominates local inductive-bias efficiency.

### Flow matching: changing the objective

DDPM's forward process is a *stochastic* Markov chain; its learned reversal is naturally sampled as an SDE, and paths from noise to data are highly curved. **Flow matching** replaces all of it with a regression: pick a data point `x1` and a noise point `x0`, form the straight line `x_t = (1−t)x0 + t·x1`, and train `v(x_t, t)` to predict the constant velocity `x1 − x0` with plain MSE (the CFM loss — Lipman et al. showed its gradient equals that of the intractable marginal-flow objective). Sampling integrates the learned ODE `dx/dt = v` with Euler steps.

Three consequences carry the interview weight:

- **Straightness enables few steps.** Linear-interpolation conditional paths are nearly straight, so coarse integration stays close to the data manifold; independent couplings still produce crossing curves, which **rectified flow** fixes by iteratively re-pairing (x0, x1) through the trained model — after roughly two rectifications a single Euler step often suffices. This is explicitly the engine behind Stable Diffusion 3 and FLUX, and the reason modern video generators default to flow objectives.
- **Determinism and exact likelihood.** The ODE is deterministic given the initial noise, and continuous normalizing flows admit exact log-likelihoods via change-of-variables — useful for evaluation and distillation, unavailable under vanilla DDPM's ELBO framing.
- **Same training simplicity.** No score functions, no SDE machinery, no time-dependent loss weighting — bounded-target regression, stable to train, drop-in compatible with DiT backbones (hence "rectified flow transformers").

Rule-of-thumb numbers worth quoting: DDPM needs 50-1000 steps; flow-matching ODEs reach comparable fidelity in ~10; rectified variants push toward 1-4; practical speedups land around 10-100x depending on domain and quality bar. When asked "diffusion or flow matching?", the 2026 answer is that flow matching *is* the mainstream diffusion implementation — the distinction is objective-plus-sampler, with flow winning wherever latency matters.

### Consistency models & few-step distillation

The third axis attacks step count directly. A **consistency model** learns the trajectory-to-endpoint map: enforce the boundary condition that applying the function to *any* point `(x_t, t)` on an ODE trajectory yields the same output as applying it to the trajectory's origin (`f(x_t, t) = f(x0, 0)`), trained either from scratch (consistency training) or by distilling a pretrained diffusion teacher (consistency distillation). At inference you can jump noise → data in one evaluation, or take 2-4 intermediate steps trading a little latency for quality.

The canonical latent-space distillation variant is **LCM**; applied to video, **VideoLCM** distills a text-to-video model while keeping the teacher architecture intact (CFG weight frozen at 9.0 during student training; guidance itself isn't needed at student inference). Measured on an A100, generating eight videos at 16×256×256: **DDIM 50-step = 60 s; VideoLCM 4-step = 10 s** (and 104 s → 16 s at 16×448×256) — about a 6x cut, with 2-4 steps sufficient when structural priors constrain the task (e.g., depth-conditioned synthesis), occasionally even 1. Image-side siblings: SDXL-Turbo (adversarial diffusion distillation — a student plus frozen teacher plus discriminator, three networks total), SDXL-Lightning, LCM-LoRA adapters that bolt few-step sampling onto existing fine-tunes without retraining, and PixArt-delta-class models generating 1024×1024 in roughly half a second. Continuous-time consistency training (sCM) simplified and scaled the from-scratch recipe — worth naming if asked "is consistency only a distillation trick?"

**The few-step tradeoff, stated honestly.** Below roughly four steps: images go blurry or artifact visibly (the classic LCM failure), with fine detail and text rendering degrading first; one-step students are mode-seeking — they snap to plausible modes and lose diversity/tail fidelity relative to the teacher's distribution; adversarial distillation recovers sharpness but imports GAN-flavored training instability and its own artifact signature. The 2026 refinement, **Perceptual Flow Matching (PFM)**, explains *why* the blur happens: regressing velocities in VAE latent space has a mean-seeking minimizer that averages modes under coarse integration; supervising decoded predictions in a pretrained perceptual feature space shifts the minimizer toward mode-seeking, cutting flow-model sampling from 35-50 steps to 4-8 with no teacher model at all (COCO FID 33.93 / CLIP score 31.70 at 8 steps — SOTA among 8-step methods). Its own stated limit: quality again degrades below two steps. Net interview position: few-step generation is production-viable at 4+ steps, contested at 1-2, and the failure mode is a *predictable quality tax*, not randomness.

### Video-specific costs

Video multiplies everything by time. Token counts grow linearly with frames (spacetime patches), so a multi-second clip is orders of magnitude more tokens than an image; cost scales roughly with `steps × tokens`, making both axes — consistency-distilled step counts and VAE compression ratios — economic decisions rather than academic ones. Temporal consistency adds its own failure surface: flicker between frames, object permanence errors, physics violations, prompt drift over long durations. Those failures are why the same DiT backbone gets reframed as a *world model* candidate — that lens is T26-world-models' subject.

---

## Build it from scratch

**Exercise: a minimal flow-matching trainer/sampler on 2-D synthetic data.** Small enough to run anywhere, faithful enough to expose the real mechanics — velocity regression, straight-line coupling, Euler ODE integration, and the step-count/quality relationship:

```python
# untested sketch — minimal flow matching on 2D moons.
# Deliberately tiny: the POINT is watching step count trade against quality.
import torch
import torch.nn as nn
from sklearn.datasets import make_moons

torch.manual_seed(0)

def batch(n=4096):
    x1 = torch.tensor(make_moons(n, noise=0.06)[0], dtype=torch.float32)
    x1 = (x1 - x1.mean(0)) / x1.std(0)          # normalize target data
    x0 = torch.randn_like(x1)                    # source distribution N(0, I)
    t  = torch.rand(n, 1)
    xt = (1 - t) * x0 + t * x1                   # straight-line interpolation
    v  = x1 - x0                                 # constant target velocity
    return xt, t, v

model = nn.Sequential(nn.Linear(3, 128), nn.SiLU(),
                      nn.Linear(128, 128), nn.SiLU(),
                      nn.Linear(128, 2))
opt = torch.optim.Adam(model.parameters(), lr=1e-3)

for step in range(3000):                         # CFM loss = plain MSE
    xt, t, v = batch()
    loss = ((model(torch.cat([xt, t], 1)) - v) ** 2).mean()
    opt.zero_grad(); loss.backward(); opt.step()

@torch.no_grad()
def sample(n=2048, n_steps=10):
    x = torch.randn(n, 2)                        # start at noise, t=0
    dt = 1.0 / n_steps                           # Euler integrate dx/dt = v
    for i in range(n_steps):
        t = torch.full((n, 1), i * dt)
        x = x + model(torch.cat([x, t], 1)) * dt
    return x

for k in (1, 2, 5, 10, 50):                      # watch 1-step smear happen
    pts = sample(n_steps=k)
    print(f"steps={k:>3}  mean_radius={pts.norm(dim=1).mean():.3f}")
```

Read the output like an interviewer would: at 1-2 steps samples smear toward the inter-mode gap (mean-seeking regression showing through coarse integration); by ~10 they're clean — the few-step tradeoff from the text, reproducible on a laptop in minutes. Extensions that make it a real study lab: add a second moon-shaped mode far away and watch one-step mode-collapse; retrain with `t` sampled near {0, 1} only and observe how the consistency-style shortcut degrades mid-trajectory coverage; swap MSE for a perceptual-feature distance (PFM's core move) and compare few-step sharpness.

For a runnable full-scale lab (fine-tune or distill an actual video DiT, measure step/quality/cost curves), no lab exists yet for this module — a reasonable ask is `(lab pending)`.

---

## How it's done in production

| Concern | Typical production choice | Why |
|---|---|---|
| Backbone | DiT-family transformer over latents | Legible scaling; token interface accepts video/audio/modalities uniformly |
| Objective | Flow matching / rectified flow | Fewer sampling steps, deterministic ODE, exact likelihood for distillation |
| Step budget | 20-50 (quality tier), 8-10 (default), ~4 (fast tier via distillation) | Cost ∝ steps × tokens; tiers are explicit product decisions |
| Few-step acceleration | LCM/Turbo/Lightning distillation, LCM-LoRA adapters, PFM-style training | ~6x video latency cut (60s→10s class); adapters retrofit existing fine-tunes |
| Guidance | CFG weight ~3-9 (or distilled/guidance-free few-step models) | Prompt adherence; note CFG doubles forward passes unless baked in |
| Latent compression | Pretrained video VAE (spatial+temporal) before diffusion | Pixel-space video diffusion is unaffordable; compression is the cost lever |
| Serving | Batching, step-caching, resolution/duration ladders, async job queues | Video gen is minutes-of-GPU per clip; queue semantics beat request/response |

**What breaks in production**

| Symptom | Cause | Fix |
|---|---|---|
| Few-step outputs look washed out / blurry | Below ~4 steps, latent-space regression averages modes | Use ≥4-step distilled checkpoints; prefer PFM-style or adversarially-distilled variants; keep 1-step only for previews |
| Quality doesn't improve when raising sampling steps | Model-compute-limited, not sampling-limited (DiT's core lesson) | Move to a larger backbone rather than burning inference flops |
| Cost explosion on longer clips | Token count grows linearly with frames; cost ∝ steps × tokens | Duration/resolution ladders; draft-tier preview then refine; temporal VAE compression |
| Inconsistent characters across shots | No cross-generation conditioning mechanism | Reference/image conditioning, seed control, or post-hoc identity adapters |
| Flicker/temporal artifacts | Weak temporal attention coverage or over-aggressive latent compression | Spacetime-patch architectures, temporal super-resolution pass, higher-quality decoder |
| CFG makes outputs oversaturated/burnt | Guidance weight too high for the checkpoint | Tune guidance per model (typical healthy range ~3-7); use guidance-distilled checkpoints to skip the double forward pass |
| Distilled model can't follow complex prompts | Student lost teacher's CFG behavior during distillation | Freeze guidance properly during distillation; or run teacher path for hard prompts, student for volume |

---

## Tradeoffs & when NOT to use it

- **Don't reach for one-step generation when quality is the product.** The 50→4 step speedup is seductive, but below ~4 steps you pay in blur, detail loss, and mode collapse; use 1-2 steps only for previews, drafts, or interactive canvases where immediacy outranks fidelity.
- **Don't add sampling steps to fix a weak model.** DiT's own data shows a bigger model at fewer steps beats a smaller model at many more steps (15.2 Tflops beating 80.7); if quality plateaus, the backbone/data is the constraint, not the sampler.
- **Don't assume flow matching changes what you can generate.** It changes the path shape, step count, and likelihood machinery — not capacity. Claims like "flow matching fixed artifact X" usually describe a different backbone or data pipeline wearing flow-matching clothes.
- **Don't use pixel-space diffusion for video.** Without latent compression, token counts make training/serving costs absurd; if a proposal bypasses the VAE, it needs a cost model attached.
- **Don't pick U-Net vs DiT by benchmark folklore at small scale.** For small-data, low-latency, high-resolution pixel tasks, conv inductive bias still wins; DiT's advantage is at frontier scale where scaling legibility dominates. Match the claim to the scale.
- **When NOT to use generative video at all:** template-driven motion graphics, deterministic product renders, and anything requiring exact reproducibility are cheaper and safer with classical rendering pipelines; generative video earns its cost only where novel content, style transfer, or natural-language-driven variation is the actual requirement.

---

## Interview questions

### Q1 — Why did Diffusion Transformers replace U-Nets as the standard diffusion backbone?
**Testing:** whether the answer is mechanism (scaling laws) or fashion ("newer papers used them").
**Answer:** Because transformers made the compute-to-quality relationship legible and favorable. Across DiT's 12 configurations, forward-pass Gflops correlated monotonically with FID — you could predict what more compute buys — while U-Net scaling was folklore-governed. Concretely, DiT-XL/2 hit FID 2.27 on ImageNet 256×256 at 119 Gflops versus ADM-U's 742 Gflops for worse results, and at 512² reached 3.04 FID at 525 Gflops versus ADM-U's 3.85 at 2,813. The token interface also unified modalities — Sora's spacetime patches are just video-as-tokens — which U-Nets' format-specific convolutional designs couldn't match.
**Follow-up trap:** *"So U-Net inductive biases were useless?"* — no; they're genuinely more sample-efficient at small scale and better suited to some high-res pixel-space regimes (that's why hourglass/U-ViT hybrids exist). The honest statement: DiT wins at frontier scales where scaling-law predictability dominates, not universally.

### Q2 — What was adaLN-Zero, and why did it matter more than the attention layers?
**Answer:** The conditioning mechanism: timestep and label/text embeddings regress per-block scale/shift/gate parameters applied at every LayerNorm, with gates zero-initialized so every block starts as identity. DiT's ablations showed this conditioning design — not the presence of attention — drove the FID gains; identical transformers using weaker conditioning (cross-attention, in-context tokens) performed dramatically worse. It matters because it demonstrates that in conditional generation, *how* information enters each block can outweigh the block type itself.
**Follow-up trap:** *"Why initialize gates to zero?"* — so the network begins as the identity function: early training passes activations through unchanged, which stabilizes optimization in deep stacks (each block refines rather than corrupts), analogous in spirit to residual-scaling and zero-init tricks elsewhere. It's a small change with outsized stability effects.

### Q3 — A teammate proposes improving generation quality by doubling denoising steps from 25 to 50. What does the DiT evidence say?
**Answer:** Be skeptical: DiT's sharpest lesson is that model compute beats sampling compute. DiT-L/2 at 1000 sampling steps (80.7 Tflops/image) produced worse FID than DiT-XL/2 at 128 steps (15.2 Tflops) — 23.7 vs 25.9. If the current model is backbone-limited, extra steps buy noise-level polish at best and doubled inference cost always; the fix is a bigger/better-trained backbone, better data, or better conditioning — not more iterations of the same network.
**Follow-up trap:** *"Are there cases where more steps DO help?"* — yes: when moving from very few steps up a sampler's quality curve (e.g., 4→8→16 on a curved-path or distilled model, or when guidance interacts with step count), and for certain ODE solvers whose error shrinks with steps. The claim isn't "steps never matter"; it's that steps can't substitute for model capacity, and past a modest count the returns flatten hard.

### Q4 — Explain flow matching versus DDPM-style diffusion. What actually changes?
**Testing:** the objective/sampler distinction, not vocabulary swapping.
**Answer:** DDPM learns to reverse a stochastic noising chain (predicting added noise along curved paths, sampled as an SDE/DDIM over dozens of steps). Flow matching regresses the constant velocity `x1 − x0` along straight-line interpolations `x_t = (1−t)x0 + t·x1` with plain MSE (CFM loss), then samples by Euler-integrating the resulting ODE. What changes: path geometry (near-straight tolerates large steps), determinism given initial noise, exact log-likelihood via change-of-variables, and step count (~10 vs 50-1000; rectified variants push to 1-4). What doesn't: it's still iterative refinement from Gaussian noise, still compatible with the same backbones.
**Follow-up trap:** *"If paths are linear interpolations, why isn't one Euler step exact?"* — because the *marginal* velocity field (averaged over all couplings passing through a point) is generally nonlinear even though each conditional path is linear; independent noise-data pairings create crossing curves. Rectified flow reduces this by re-pairing samples through the trained model until trajectories nearly straighten, after which one step often suffices.

### Q5 — What is rectified flow, and why do SD3 and FLUX credit it?
**Answer:** An iterative straightening procedure: train the velocity field, then re-pair (noise, data) samples by running the model to generate new pairs, and retrain on those — each round reduces trajectory curvature. After roughly two rectifications the ODE is close enough to straight that a single Euler step produces usable samples. SD3 ("Scaling Rectified Flow Transformers") and FLUX built on it because it combines the DiT backbone's scaling with genuinely few-step-capable sampling — the practical sweet spot of both prior threads.
**Follow-up trap:** *"Does straightening hurt quality/diversity?"* — there's a real tension: reflow concentrates probability mass along efficient transport paths and can reduce diversity relative to curved multi-modal transport, which is why guidance strength, coupling choices (e.g., minibatch-OT couplings), and evaluation beyond FID all matter. Straightness trades a bit of path diversity for sampling efficiency.

### Q6 — How do consistency models work, and what exactly is the tradeoff when sampling in one or four steps instead of fifty?
**Answer:** A consistency function enforces `f(x_t, t) = f(x0, 0)` — mapping any point on the probability-flow trajectory to the trajectory's endpoint — trained via consistency distillation from a pretrained teacher (or self-consistency from scratch). Sampling jumps noise→data in one evaluation or a few. The tradeoff: below roughly 4 steps you get blur and detail loss (latent-regression students average across modes — mean-seeking), one-step students lose tail diversity (mode-seeking), and text/fine-structure degrade first. Measured video impact: VideoLCM cut 8-clip generation from 60 s (DDIM-50) to 10 s (4 steps) on an A100 — a ~6x win that remains production-viable precisely at 4+ steps.
**Follow-up trap:** *"Why does the one-step student produce blurrier images rather than noisier ones?"* — because its regression target under coarse integration has a mean-seeking minimizer: predicting the conditional expectation smears probability mass between modes into plausible-but-soft averages. PFM's contribution was showing that supervising in a perceptual feature space flips the minimizer toward mode-seeking, recovering sharp 4-8 step generation without any teacher.

### Q7 — You need to cut video-generation cost by ~5x without changing vendors. Rank your levers.
**Answer:** (1) Steps: switch to a consistency/distilled checkpoint — 50→4-8 steps is the single biggest multiplier (~6x measured on VideoLCM-class setups), accepting the known quality tax above 4 steps. (2) Tokens: drop resolution/duration for drafts and reserve full-res for finals (token count scales with frames × area). (3) Latent compression ratio: a stronger temporal VAE shrinks tokens everywhere. (4) Serving mechanics: batching, caching shared prefixes/conditioning, off-peak scheduling. Notably absent from the top: switching objective (retraining-grade, not a serving lever).
**Follow-up trap:** *"Which lever hurts perceived quality least?"* — usually the draft/refine ladder: users judge the artifact they approve, and a fast low-cost preview with a slower final render reads as responsiveness, not degradation. Pure step-cutting below ~4 steps is where subjective quality visibly collapses; keep the floor.

### Q8 — Where do spacetime patches come from, and why did they matter for video?
**Answer:** Sora's reformulation of video as tokens: pack the compressed spatiotemporal latent volume into patches spanning space AND time, embed them as a token sequence, and feed a standard DiT. This gave one architecture over variable resolutions, durations, aspect ratios — no per-format architectural surgery — and let scaling behavior carry over from images. It mattered because it turned "video generation" from a bespoke architecture problem into a token-scaling problem, the same transition that took transformers from text to images.
**Follow-up trap:** *"What breaks first as videos get longer?"* — attention cost and memory grow quadratically with token count while temporal-consistency demands grow with duration; hence the research front of linear/sparse attention, MoE DiTs, and hierarchical/next-scale approaches for long horizons. Also physics: longer horizons expose world-model failures (object permanence) that short clips hide.

### Q9 — When would you still choose a U-Net-based or conv-heavy design today?
**Answer:** Narrow but real niches: small datasets where conv sample-efficiency beats transformer scaling headroom; ultra-low-latency high-res pixel manipulation where per-token transformer overhead dominates; edge devices with tight memory where multiscale conv designs fit better; and editing tasks needing precise local spatial control where conv locality helps. The modern pattern is hybridization (conv frontend/backends around transformer middles) rather than pure either/or.
**Follow-up trap:** *"Your team wants to fine-tune a generator on 5k domain images — DiT or U-Net?"* — at 5k images, scaling-law advantages are irrelevant and transfer-from-pretrained-checkpoints decides it: fine-tune whichever pretrained family matches your domain and license, since both ecosystems have mature checkpoints. The architecture war matters at pretraining scale, not fine-tuning scale.

### Q10 — What does classifier-free guidance do, and how does it interact with few-step distilled models?
**Answer:** CFG trains the model conditionally and unconditionally, then extrapolates the difference at sampling time (`v = v_uncond + w·(v_cond − v_uncond)`), sharpening prompt adherence at guidance weights typically 3-9 — at the cost of two forward passes per step. Interaction with distillation: students are usually distilled with guidance baked in (LCM froze the teacher's CFG weight, e.g., 9.0, during student training), so the student needs neither double evaluations nor a guidance dial at inference — changing effective guidance post-hoc is limited or impossible, which is a real operational constraint.
**Follow-up trap:** *"Users complain outputs look 'burnt' and oversaturated — diagnosis?"* — classic excessive-guidance signature: guidance weight too high for the checkpoint pushes samples off-manifold. Lower `w`; or if the model is guidance-distilled, switch checkpoints/tiers rather than hunting for a knob that doesn't exist anymore.

### Q11 — Compare the three axes — backbone, objective, distillation — as an interviewer might force you to.
**Testing:** whether the three-layer mental model survives direct decomposition pressure.
**Answer:** Backbone (U-Net → DiT) determines scaling behavior and modality flexibility — a training-time architecture decision. Objective (epsilon-prediction/SDE → flow matching/ODE) determines path geometry, step requirements, determinism, and likelihood availability — also training-time but cheaper to change than architecture. Distillation (teacher → consistency/LCM/PFM students) is an inference-time transformation of an existing model determining achievable step counts and their quality tax. They compose independently: a DiT can run DDPM or FM objectives; either can be consistency-distilled. Interview questions usually target one axis while assuming the others.
**Follow-up trap:** *"Which axis could you change on a deployed system without retraining?"* — only distillation-flavored ones: sampler swaps, step-count schedules, LoRA-bolted LCM adapters. Objective changes require retraining; backbone changes require new pretraining. Answering "we'd just switch to flow matching" for a deployed system reveals confusion about where each lever lives.

### Q12 — Is one-step generation the end state, in your assessment?
**Answer:** Arguably for interactive/preview contexts yes — the economics demand it, and PFM-class training improvements plus adversarial distillation keep closing the gap (sharp 4-8 step now; 1-2 steps still degraded by the practitioners' own admission). But for premium content generation the multi-step regime persists because the quality ceiling of iterative refinement hasn't been matched at one step, and the mode-seeking/diversity losses are structural, not incidental. The likely equilibrium is tiered: 1-4 steps interactive, 8+ steps finals — mirroring how voice systems tier latency budgets rather than converging on one number.
**Follow-up trap:** *"What evidence would change your mind?"* — a training method achieving one-step generation matching teacher distributions on diversity-sensitive metrics (not just FID), demonstrated at video scale where temporal coherence compounds any per-frame averaging. Watch for perceptual/adversarial hybrids reporting tail-fidelity metrics, not headline benchmarks alone.

---

## Red flags that fail you

- Describing DiT as "diffusion but with attention" without the scaling-law story or adaLN-Zero conditioning.
- Claiming flow matching is "faster diffusion" without stating the mechanism (straight-line velocity regression, deterministic ODE, path curvature).
- Confusing the three axes — proposing to "switch to a transformer" to reduce sampling steps.
- Not knowing what consistency distillation gives up (sub-4-step blur, mode-seeking diversity loss).
- Quoting FIDs/steps without units or context (FID-50K vs FID-10K, image vs video settings).
- Recommending pixel-space video diffusion or ignoring latent compression in cost discussions.
- Treating "more denoising steps" as a generic quality knob despite the model-compute-beats-sampling-compute evidence.
- No awareness of the U-Net's remaining legitimate niches at small scale/high resolution.

---

## Cheat card

```
DiT (2022)      ViT over VAE-latent patches replaces U-Net backbone.
                WINNER BECAUSE: Gflops↔FID monotonic across 12 configs
                (legible scaling) + adaLN-Zero conditioning (gates zero-
                init; ablated difference-maker).
                NUMBERS: XL/2 = 675M params · FID 2.27 @256² @119 Gflops
                (ADM-U: 742) · 3.04 @512² @525 (ADM-U 2813 ≈ 5x worse eff.)
                KEY LESSON: model compute > sampling compute
                  (L/2 @1000 steps = 80.7 Tflops LOSES to XL/2 @128 = 15.2;
                   FID 23.7 vs 25.9)
                VIDEO ENTRY: spacetime patches (Sora) = video as tokens

FLOW MATCHING   CFM loss: MSE(v_θ(x_t,t), x1−x0), x_t=(1−t)x0+t·x1.
                Sample = Euler-integrate ODE dx/dt=v. Deterministic,
                exact likelihood (change of variables).
                STEPS: DDPM 50-1000 → FM ~10 → rectified (reflow re-pairs
                x0/x1, ~2 rounds) 1-4. Engine of SD3 + FLUX. 10-100x speedup.

CONSISTENCY     Boundary cond: f(x_t,t)=f(x0,0) — jump any point→endpoint.
/LCM           VideoLCM: 8 clips 16×256×256 on A100: DDIM-50 = 60s,
                LCM-4 = 10s (~6x). CFG frozen w=9.0 in student.
                TRADEOFF <4 steps: blur/detail loss (mean-seeking),
                1-step = mode-seeking diversity loss; ADD adds a
                discriminator (3 nets) for sharpness + instability.
                PFM (2026): supervise in PERCEPTUAL space → 35-50 steps
                → 4-8, NO teacher. COCO 8-step: FID 33.93, CLIP 31.70.

COST MODEL      video cost ∝ steps × tokens(frames × area ÷ VAE compression).
                Levers ranked: distilled steps → res/duration ladder →
                stronger temporal VAE → batching/caching.

WHEN NOT        don't buy quality with sampling steps (backbone-limited);
                don't 1-step premium content; small-data/high-res/local-
                edit niches still favor conv/hybrids.
```

## Sources

- [Scalable Diffusion Models with Transformers (DiT) — Peebles & Xie, arXiv 2212.09748](https://arxiv.org/abs/2212.09748) — accessed 2026-08-23
- [facebookresearch/DiT — GitHub](https://github.com/facebookresearch/DiT) — accessed 2026-08-23
- [Diffusion Transformer (DiT) Models: A Beginner's Guide — Encord](https://encord.com/blog/diffusion-models-with-transformers) — accessed 2026-08-23
- [VideoLCM: Video Latent Consistency Model — arXiv 2312.09109](https://arxiv.org/abs/2312.09109) — accessed 2026-08-23
- [Perceptual Flow Matching for Few-Step Generative Modeling — arXiv 2607.03524](https://arxiv.org/html/2607.03524v1) — accessed 2026-08-23
- [Flow Matching vs Diffusion Models — MetricGate](https://metricgate.com/blogs/flow-matching-vs-diffusion-models) — accessed 2026-08-23
- [Comparing few-step image generation models — Baseten](https://www.baseten.co/blog/comparing-few-step-image-generation-models) — accessed 2026-08-23
- [Latent Consistency Models Guide — AI Understanding](https://aiunderstanding.org/learn/latent-consistency-models) — accessed 2026-08-23
- [Flow Matching and Diffusion Models — MIT 2026 course](https://diffusion.csail.mit.edu/2026/index.html) — accessed 2026-08-23

## Changelog
- 2026-08-23 — created
