# LeCun's JEPA & V-JEPA 2: Prediction in Latent Space, Not Pixels

> **Track:** T26 Frontier AI · **Time:** 2.5h · **Prereqs:** `T26-world-models`, T05 (representation learning), T31 (model-based RL) · **Updated:** 2026-08-05
> **Module id:** `T26-jepa` · **Tags:** jepa, i-jepa, v-jepa, ssl, world-models, energy-based, collapse, critical
> **Lab:** `labs/py/26-02-jepa/`

## The 30-second version

JEPA is the family of self-supervised architectures that predict the *embedding* of a masked target from the *embedding* of a visible context, never reconstructing a pixel, and the entire design follows from one observation: a pixel reconstruction loss forces the model to spend capacity on detail that is aleatorically unpredictable (which leaf moves, which grain of film), while an embedding-space loss lets the encoder simply refuse to represent it. The price of that freedom is that the target is *learned*, so a degenerate solution exists (map everything to a constant, prediction error zero, representation worthless), and every engineering decision in I-JEPA and V-JEPA is an anti-collapse decision: a **stop-gradient** on the target branch, an **EMA target encoder** with momentum ramped 0.996 → 1.0, and a **narrow predictor** (embedding dim 384 against a ViT-H encoder's 1280) that is too weak to learn the identity map cheaply. The results are real and cheap: I-JEPA pretrains a ViT-H/14 on ImageNet in **under 1,200 GPU-hours** (16 A100s, under 72 hours), roughly **10x more compute-efficient than MAE** at equal architecture, and V-JEPA 2 (**1.2B** ViT-g, **>1M hours** of internet video) hits **77.3%** on Something-Something-v2 and **39.7** recall-at-5 on Epic-Kitchens-100 anticipation, then post-trains an action-conditioned head on **fewer than 62 hours** of unlabelled Droid robot video and plans zero-shot on Franka arms in two labs it never saw, at roughly **65-80%** pick-and-place success. The honest position to hold in an interview is the narrow one: **JEPA is a demonstrably more compute-efficient way to learn motion-and-dynamics representations, and it is the only line with a published closed-loop zero-shot robot result off web video, but it has not beaten the best curated-data generative or distillation pipelines on general vision benchmarks** (I-JEPA's ~79% ImageNet linear probe against DINOv2 ViT-g/14's ~86.5%), and "predicting in latent space is fundamentally the right path" remains a *bet*, not a measured result.

## Why this gets asked

Because the interviewer wants to know whether you can hold a technical position under pressure when the loudest voice in the room is a Turing laureate and the second loudest is a scaling maximalist who thinks he is wrong. LeCun's claim is architectural and normative ("generative pixel prediction is a dead end for world modelling"), the counter-claim is empirical and dismissive ("nice SSL method, hasn't beaten anything that matters"), and the candidate who parrots either one has told the interviewer nothing except which podcast they listen to. What the interviewer actually wants is the derivation: *why* would predicting in representation space differ from predicting in pixel space, what does that buy you in units of compute and capacity, what does it cost you, and what specific failure does the cost show up as.

The production failure that makes this a real question rather than a philosophy quiz is representation collapse, and it is not exotic. Anyone who has trained a joint-embedding model has watched a run where the loss curve looks *beautiful*, dropping two orders of magnitude in 400 steps and flatlining near zero, and then discovered that every image in the validation set maps to embeddings with cosine similarity 0.9997 to each other. Nothing crashed. No NaN. No alert fired. The linear probe on a downstream head even trains, because a linear probe on a 1024-dim near-constant vector can still fit the training split. The signal only appears when someone finally looks at the covariance spectrum and sees rank 3 out of 1024. An interviewer who has lived that will ask you what you would measure, and "I'd check the loss" is a failing answer, because the loss is the thing that lied.

At principal level there is a third layer: this is a bet-sizing question. If the interviewer's lab is deciding whether to fund a JEPA-style programme, they want someone who can say what evidence would change their mind and by when. That is what the last third of this module is for.

---

## Lineage: past → present → future

**What came before.** Three lines converged and each died of a specific, nameable pain. The first is **pixel-reconstruction self-supervision**: denoising autoencoders (Vincent et al., 2008), Context Encoders (Pathak et al., CVPR 2016), and the line culminating in **MAE** (He et al., arXiv 2111.06377, CVPR 2022), which masks **75%** of patches and reconstructs raw pixels with an asymmetric encoder-decoder. MAE fine-tunes superbly (ViT-H about **87.8%** ImageNet top-1) but its *frozen* representations are markedly weaker (ViT-L linear probe about **75.8%** against **85.9%** fine-tuned, a roughly 10-point gap), and the reason is structural: a pixel objective forces the last layer to retain low-level appearance because the decoder needs it, so the representation mixes semantic and photometric content and a linear head must disentangle them. The pain that killed pixel reconstruction as a *representation* method: **capacity spent on reconstructable-but-irrelevant detail is capacity not spent on semantics**, and it shows up as a ten-point probe gap. The second line is **contrastive / invariance-based SSL**: SimCLR (Chen et al., ICML 2020, batch **4096**, temperature **0.1**, 128-dim projection head, ResNet-50 linear **69.3%**), MoCo (a **65,536**-entry negative queue), BYOL (Grill et al., NeurIPS 2020, no negatives at all, ResNet-50 **74.3%**), SimSiam (Chen and He, CVPR 2021, stop-gradient alone prevents collapse), DINO (Caron et al., ICCV 2021, ViT-B/8 **80.1%** linear, **77.4%** k-NN). Excellent semantic representations, but invariance is bought with **hand-designed augmentations**: random resized crop, colour jitter, grayscale, solarization, blur. Two pains, both load-bearing. Augmentations encode a human's guess about what should be invariant, which is domain-specific and does not transfer (colour jitter is fine for ImageNet, catastrophic for medical stain normalisation or a traffic-light detector), and invariance is the *wrong objective for a world model*, which must predict change rather than be invariant to it. The third line is **action-conditioned pixel video prediction** (Oh et al. 2015, Finn and Levine 2016-2017), which died of blur: minimising squared error over multimodal futures converges to the conditional mean and rollouts go grey in 10 to 20 frames. LeCun's synthesis, **"A Path Towards Autonomous Machine Intelligence" (version 0.9.2, OpenReview, 27 June 2022)**, claims all three failures share one cause: each demands prediction in a space whose irreducible entropy is enormous, and the fix is to predict in a space the model itself chooses, with a latent variable absorbing what is genuinely unpredictable.

**Where it stands now.** Validated as an SSL method, contested as a *path*. Validated side: I-JEPA (Assran et al., arXiv 2301.08243, CVPR 2023) demonstrated the recipe on images with no augmentations at all, headlining efficiency rather than accuracy (**under 1,200 GPU-hours** for a ViT-H/14 on ImageNet, over **2.5x faster than a ViT-S/16 with iBOT**, over **10x more compute-efficient than a ViT-H/14 with MAE**). V-JEPA (Bardes et al., arXiv 2404.08471, February 2024) took it to video on **2 million** videos (VideoMix2M), its ViT-H/16 reporting **81.9%** Kinetics-400, **72.2%** Something-Something-v2 and **77.9%** ImageNet-1K with a **frozen backbone** (no parameter adaptation, attentive probe only). V-JEPA 2 (Assran et al., arXiv 2506.09985, 11 June 2025, 48 pages) scaled to a **1.2B-parameter ViT-g** on **VideoMix22M (>1 million hours)** and delivered the result the programme is judged on: **V-JEPA 2-AC**, an action-conditioned predictor post-trained on **fewer than 62 hours** of unlabelled Droid robot video, deployed **zero-shot** on Franka arms in two labs with **no data from those labs, no task-specific training and no reward**, planning to image goals at roughly **65-80%** pick-and-place success on novel objects. That is a closed-loop task-success number on real hardware in an unseen environment, a format almost nobody else in the world-model conversation reports. The contested side is equally concrete. I-JEPA's ImageNet linear probe (about **79%** for ViT-H/14 at 224, around **81%** at 448) sits *below* DINOv2 (Oquab et al., 2023, ViT-g/14, **1.1B** params, LVD-142M, about **86.5%**), an augmentation-and-distillation method on heavily curated data, i.e. exactly the paradigm JEPA was meant to supersede, and as of 2026 the default frozen vision backbone in most production stacks is DINO-family or CLIP-family, not JEPA. The anti-collapse machinery is acknowledged inside the camp as unprincipled: LeCun's own follow-up with Balestriero, **LeJEPA (arXiv 2511.08544, 11 November 2025)**, calls the EMA-and-stop-gradient stack "heuristics", proves an **isotropic Gaussian** embedding distribution uniquely minimises worst-case downstream prediction risk, and replaces the heuristics with **SIGReg** at **linear time and memory**. Publishing a paper whose thesis is "our previous collapse prevention was a pile of tricks" is the strongest available evidence the criticism was right on that point. Note neutrally if it comes up that LeCun's departure from Meta to found a world-model company was reported in November 2025; treat the org chart as gossip and argue the architecture.

**Where it's heading.** High confidence (~85%): latent-space prediction stays a *component* of frontier robot and video systems regardless of who wins the philosophical argument, because the compute economics are not in dispute and V-JEPA 2-AC's "<62 hours of robot data" is the kind of number that funds a programme even for people who think LeCun is wrong about everything else. High confidence (~80%): the anti-collapse layer moves from heuristics to explicit distributional regularisation (LeJEPA/SIGReg or a VICReg-style variance-covariance term) as the default over EMA momentum schedules; the field has been burned enough by irreproducible momentum tuning that a single-knob replacement wins on ergonomics even at parity. Medium confidence (~60%): hybrids dominate, a JEPA-style latent predictor for the planning loop paired with a generative decoder used only for human inspection and as an anti-collapse anchor, which is architecturally what Dreamer already does (`T26-world-models`). Genuinely speculative, and label it out loud: **whether hierarchical JEPA (H-JEPA), the multi-timescale stack that is the actual proposal in the 2022 paper, ever gets built and works.** As of August 2026 there is no I-JEPA-or-V-JEPA-scale demonstration of a working hierarchy, so the most load-bearing claim in the position paper has the least evidence behind it. Equally speculative: whether a JEPA-family model ever beats a scaled generative model on a *general* capability benchmark rather than motion-specific ones. My read, offered as a read and not a fact, is roughly 35% by 2028, and the reason it is not lower is V-JEPA 2's LLM-aligned results (**84.0** PerceptionTest, **76.9** TempCompass at the **8B** scale), which show the representations survive contact with a language model rather than being a self-supervised curiosity.

---

## Mental model

```
THE ONE SENTENCE
  JEPA = predict the EMBEDDING of the masked part from the EMBEDDING of the
         visible part.  Never decode.  The target is LEARNED, which is both
         the whole point and the whole problem.

THREE ARCHITECTURE FAMILIES  (LeCun's taxonomy, 2022)

  1. GENERATIVE / RECONSTRUCTIVE          (MAE, VAE, diffusion, next-frame)
       x --[enc]--> z --[dec]--> x_hat        loss in PIXEL space
       must model p(every pixel). Pays for texture, grain, foliage.

  2. JOINT-EMBEDDING, INVARIANCE-BASED    (SimCLR, BYOL, DINO)
       x --[enc]--> s_x ; x'=AUG(x) --[enc]--> s_x' ; PULL TOGETHER
       needs hand-designed augmentations to say what to be invariant TO.
       Objective is INVARIANCE. A world model needs the opposite.

  3. JOINT-EMBEDDING PREDICTIVE (JEPA)    (I-JEPA, V-JEPA, V-JEPA 2)
       x --[ctx enc]--> s_x --[predictor(z)]--> s_y_hat  --L2--> s_y
       y --[tgt enc]--> s_y
       y is a DIFFERENT PART of the same signal (masked patch, future frame),
       NOT an augmented copy. Objective is PREDICTION, not invariance.
       z = optional latent absorbing what is genuinely unpredictable.

THE DIAGRAM YOU DRAW ON THE WHITEBOARD

                      +-----------------------+
   context patches -->|  CONTEXT ENCODER      |--- s_x (N_ctx x D)
   (visible, ~85%     |  ViT, TRAINED by SGD  |        |
    of image minus    +-----------------------+        |
    target regions)                                    v
                                            +---------------------+
        mask tokens + positional  --------->|  PREDICTOR          |
        embeddings of TARGET locations      |  NARROW ViT         |
                                            |  dim 384 (not 1280) |
                                            +----------+----------+
                                                       | s_y_hat
                                                       v
                      +-----------------------+     [ L2 / smooth-L1 ]
   target patches --->|  TARGET ENCODER       |--- s_y     ^
   (the FULL image,   |  EMA COPY of context  |            |
    same weights      |  NO GRADIENT EVER     |------------+
    architecture)     +-----------------------+
                          ^        stop-grad
                          |
                theta_tgt <- m * theta_tgt + (1-m) * theta_ctx
                m: 0.996 -> 1.0, LINEAR over training

THE THREE ANTI-COLLAPSE DEVICES AND WHAT EACH ONE BLOCKS
  stop-grad on target  : blocks the gradient path that would shrink s_y
  EMA (m < 1)          : target moves SLOWER than context -> the context
                         encoder is chasing a lagging target, so a
                         "shrink both together" solution is not reachable
                         by gradient descent in one step
  narrow predictor     : an under-parameterised predictor cannot cheaply
                         learn identity or a constant map; it is forced to
                         use the context

THE DEGENERATE SOLUTION YOU ARE DEFENDING AGAINST
   enc(anything) = c   ==>  predictor(c) = c  ==>  loss = 0 EXACTLY
   The global minimum of the naive objective IS collapse.
   You do not fix this with a better loss. You fix it by making collapse
   UNREACHABLE BY THE OPTIMISER, or by adding an explicit anti-collapse term.

ENERGY-BASED FRAMING (LeCun's language, and it is not decoration)
   E(x, y) = || Pred(Enc_ctx(x), z) - Enc_tgt(y) ||^2
   low E   = compatible (x, y)      high E = incompatible
   "energy = prediction error IN REPRESENTATION SPACE"
   Collapse = the energy surface goes FLAT: E(x,y) low for ALL y.
   The engineering problem is stated exactly: SHAPE the energy surface so
   it is low on the data manifold and high off it, WITHOUT normalising
   over y (which is what makes it non-probabilistic and tractable).

WHY LATENT BEATS PIXELS, IN ONE INEQUALITY
   H(y | x)  =  H(y_predictable | x)  +  H(y_noise | x)
   pixel loss pays for BOTH terms.
   embedding loss can drive H(s_y_noise | x) -> 0 by simply NOT ENCODING it.
   Measured consequence: I-JEPA ViT-H/14 pretrain < 1200 GPU-hours,
   ~10x cheaper than MAE ViT-H/14 for BETTER frozen-probe accuracy.

WHERE THE COST SHOWS UP
   no decoder  ->  no external ground truth  ->  no way to look at a sample
   and see it is wrong. MAE fails visibly (blurry reconstruction).
   JEPA fails INVISIBLY (loss 0.0003, rank 3, everything "works").
```

---

## How it actually works

### Deriving why representation-space prediction differs from pixel-space prediction

Do not assert this. Derive it, because the derivation is short and it is the thing that separates you from a candidate who read a blog post.

Fix an observation `x` (visible context) and a target `y` (masked region, or a future frame). Decompose the conditional entropy of the target given the context:

```
H(y | x)  =  H(y_pred | x)  +  H(y_noise | x, y_pred)
             \___________/     \____________________/
             epistemic:         aleatoric: genuinely
             inferable from x   NOT inferable from x
```

A generative objective (MAE, next-frame prediction, a diffusion denoiser) minimises a loss whose optimum requires modelling the *full* conditional `p(y|x)`, aleatoric term included. Under squared error the optimum on that term is the conditional mean, which is a blur; under a proper likelihood objective with enough capacity it is a calibrated distribution over noise, which is worse, because you spent parameters and FLOPs *accurately modelling noise*.

Quantify it. A `224x224` RGB image is `150,528` numbers, and MAE at a **75%** mask ratio reconstructs three quarters of them, on the order of `10^5` scalar predictions per image, where the loss mass in natural images is dominated by high-frequency content: texture, grain, compression artefacts, micro-shading. I-JEPA instead predicts the embeddings of **4** target blocks at **15-20%** image area each, in a `D = 1280` space. The decisive difference is not the scalar count, it is that **the target values themselves are chosen by the model**, so if the grain is unpredictable the cheapest route to lower loss is to stop encoding it. Pixel space offers no such escape: the ground truth is fixed externally and the grain is in it. One sentence for the interview: **a pixel objective has an externally fixed target so the model must model the noise; an embedding objective has a learned target so the model can decline to.** Everything else in JEPA follows from the fact that "can decline to represent things" also means "can decline to represent *everything*."

The measured consequence, and the strongest empirical claim the line makes: I-JEPA pretrains a **ViT-H/14 in under 1,200 GPU-hours** (16 A100s, under 72 hours wall-clock), reported as **over 10x more compute-efficient than MAE at the same ViT-H/14** and **over 2.5x faster than iBOT on a much smaller ViT-S/16**, while producing better frozen-probe representations than MAE. Efficiency at equal or better quality is a hard number and is not seriously contested. Note what it is not: a claim about final accuracy at unlimited compute. I-JEPA does not make one.

### The energy-based framing, and what LeCun's position paper actually claims

An energy-based model defines a scalar `E(x, y)` that is low for compatible pairs and high for incompatible ones, and crucially **does not normalise over `y`**. No partition function, no `Z`, so `E` is not a log-probability and you cannot sample from it directly. That is the point: normalising over the space of all images is intractable and the EBM framing skips it.

For JEPA the energy is defined explicitly, and this is the line to memorise:

```
E(x, y)  =  D( Pred( Enc_ctx(x), z ),  Enc_tgt(y) )
```

with `D` an L2 or smooth-L1 distance and `z` a latent variable capturing the information about `y` that is genuinely not inferable from `x`. **The energy is the prediction error in representation space.** Once you write it that way, the central problem states itself: an EBM is only useful if the energy surface is *shaped*, meaning low on the data manifold and high off it. Training only on positive pairs pushes energy down on the manifold and does nothing to push it up elsewhere. The pathological solution is a **flat energy surface**, where `E` is low everywhere, and a flat energy surface in this parameterisation is exactly representation collapse. LeCun's taxonomy of energy-shaping methods is worth carrying: **contrastive methods** push energy up at explicitly sampled negative points (SimCLR's in-batch negatives, MoCo's queue), and **regularised methods** limit the *volume* of low-energy space by constraining the representation's information content (VICReg's variance and covariance terms, a VAE's KL to a prior, or an architectural bottleneck). LeCun's stated preference for regularised over contrastive is a scaling argument: contrastive methods need negatives whose count must grow to cover a high-dimensional space, which is why SimCLR needs a **4,096** batch and MoCo maintains a **65,536**-entry queue, and that becomes untenable in video.

Now what "A Path Towards Autonomous Machine Intelligence" (version 0.9.2, 27 June 2022, OpenReview) *actually claims*, because candidates routinely inflate it. It is a **position paper**, explicitly labelled as such, with **no experiments**. It proposes six modules: a **configurator** that sets up the others per task, **perception**, a **world model**, a **cost** module (immutable intrinsic cost plus trainable critic), **short-term memory**, and an **actor** performing inference-time optimisation of an action sequence against predicted cost. JEPA is the proposed *implementation of the world model*; **H-JEPA**, the hierarchical stack predicting at multiple time scales, is the proposal for making long-horizon planning tractable, with higher levels predicting coarser abstractions where prediction is actually possible. The claims are (a) autoregressive generative models of raw sensory data are the wrong substrate for a world model, (b) hierarchical latent prediction plus inference-time action optimisation is the right one, (c) this is trainable mostly by observation. What it does *not* claim is that any of this was demonstrated. I-JEPA, V-JEPA and V-JEPA 2 validate a slice: single-level JEPA as a representation learner, and single-level action-conditioned JEPA for short-horizon planning. **The hierarchy, the configurator and the intrinsic cost module remain unimplemented at scale as of August 2026.**

### The architecture, mechanically

Four objects. Get the asymmetry right, because the asymmetry is the design.

**The context encoder** `f_theta`. A standard ViT. Takes only the *visible* patches (mask tokens are not fed to it; this is the same efficiency trick MAE uses, and it is why the encoder's cost scales with the visible fraction, not the full image). Trained by ordinary backpropagation from the loss. This is the network you keep at the end.

**The target encoder** `f_theta_bar`. Architecturally identical, parameters updated *only* by an exponential moving average of the context encoder:

```
theta_bar  <-  m * theta_bar  +  (1 - m) * theta
```

with `m` scheduled linearly from **0.996 to 1.0** over training in I-JEPA (the same schedule family DINO and BYOL use, and the numerical similarity is not a coincidence: this is a self-distillation family). It takes the **full, unmasked** input and produces target embeddings; the targets for the loss are then *sliced out* of that full-image output at the masked block locations. That detail is easy to miss and it matters enormously: the target representation for a masked block is computed with **global context available**, which is what makes it a semantically rich target rather than a patch-level appearance descriptor. **A `stop_gradient` sits on this branch. No gradient ever flows through it.**

**The predictor** `g_phi`. Also a ViT, but deliberately **narrow**: embedding dimension **384** against the ViT-H encoder's **1280**, with shallow depth (6 or 12 blocks depending on config). It receives the context encoder's output tokens plus **mask tokens** carrying the positional embeddings of the target locations, and outputs one predicted embedding per target patch. The mask token is a single shared learned vector; the *only* thing distinguishing one predicted position from another is its positional embedding, which forces the predictor to be a genuine spatially-conditional model rather than a lookup.

**The loss.** Average L2 (I-JEPA) or smooth-L1 / L1 (V-JEPA) between predicted and target embeddings, over target patches. In V-JEPA the target embeddings are additionally normalised with a LayerNorm before the loss, which removes the trivial "shrink the target norms" gradient direction.

Two structural notes that come up in follow-ups. First, **there is no projection head and no contrastive term**, unlike SimCLR/BYOL/DINO. The loss is computed directly on encoder outputs. Second, **there are no hand-designed data augmentations at all** in I-JEPA beyond the cropping implicit in masking: no colour jitter, no blur, no solarization. That is the headline architectural claim (invariances are learned from the prediction task rather than hand-specified) and it is also what makes the recipe plausibly domain-agnostic, which is why it has been ported to tabular data (T-JEPA), audio, and geospatial data with minimal changes.

### Why the EMA target actually prevents collapse, honestly

This is where you get a chance to be more precise than the literature usually is, so be precise.

The naive objective has collapse as a **global minimum**: set `f_theta(x) = c` for all `x`, let the predictor learn the constant map, and the loss is exactly zero. No loss engineering removes that minimum. So the anti-collapse story cannot be "the objective prefers non-collapse"; it has to be **"gradient descent from a reasonable initialisation does not reach it."** Three mechanisms, in decreasing order of how well they are understood.

**Mechanism 1: the stop-gradient removes the collapse-directed gradient.** With `L = ||g(f(x)) - sg[f_bar(y)]||^2`, the gradient with respect to `theta` contains no term that pushes `f_bar(y)` toward `g(f(x))`. The system can only move the prediction toward the target, never the target toward the prediction. SimSiam (Chen and He, CVPR 2021) is the cleanest evidence: it removed negatives, removed the momentum encoder entirely, kept only the stop-gradient and the predictor, and still did not collapse. That result is why you should *not* claim the EMA is the sole mechanism.

**Mechanism 2: the EMA makes the target a lagging, hence effectively different, function.** With `m = 0.996`, the target encoder's effective averaging window is about `1/(1 - m) = 250` steps. The context encoder is optimising against a target computed by a version of itself from roughly 250 optimisation steps ago. A collapse trajectory requires *both* encoders to shrink simultaneously, but the target's motion is a low-pass-filtered copy of the context's, so at any instant a context encoder that "tries" to shrink is scored against a target that has not shrunk yet, producing a nonzero loss that opposes the move. This is a dynamics argument, not an optimality argument, and it is the honest framing. The momentum ramp toward **1.0** late in training freezes the target completely, which is an endgame stability measure.

**Mechanism 3: the predictor's limited capacity.** If the predictor could represent an arbitrary function it could absorb any degenerate encoder. A **384**-dimensional, 6-to-12-block ViT predicting into a **1280**-dimensional target space is under-parameterised for that job, and the cheapest route to low loss is to actually use the context. This is the least rigorous of the three and the easiest to break in practice: widen the predictor to match the encoder and collapse risk rises measurably.

The honest summary: **none of this is a proof.** There is theoretical work on why BYOL-style asymmetry avoids collapse (eigenspace-alignment arguments about the predictor's linear approximation) but no guarantee, and the tuning is brittle, with momentum, predictor width, warmup length and mask ratio all interacting. **LeJEPA** (Balestriero and LeCun, arXiv 2511.08544, 11 November 2025) exists precisely because of this, and it is a rare case of a programme's founder publishing the strongest critique of his own method's engineering. It proves the **isotropic Gaussian** uniquely minimises worst-case downstream prediction risk among embedding distributions, then enforces it with **SIGReg**: rather than matching a `D x D` covariance (`O(D^2)` memory, unstable at `D = 1280`), project embeddings onto a few **random 1D directions**, apply a univariate distribution-matching test (characteristic-function / Epps-Pulley style) per direction, and resample directions each iteration so isotropy holds in expectation. Cost is **linear** in dimension and training reduces to roughly **one** trade-off hyperparameter. In August 2026 this is the paper to name.

### I-JEPA: the masking strategy is the method

I-JEPA (Assran et al., arXiv 2301.08243, submitted 19 January 2023, CVPR 2023) is where the abstraction became a working system, and the load-bearing contribution is not the architecture (which is BYOL-shaped) but the **multi-block masking strategy**. These are the most commonly asked concrete details on this topic.

```
MULTI-BLOCK MASKING  (per image, resampled every step)

  TARGET BLOCKS   M = 4 blocks
                  scale        ~ U(0.15, 0.20)   of image area
                  aspect ratio ~ U(0.75, 1.50)
                  blocks MAY overlap each other
                  targets are SLICED from the target encoder's output
                  over the FULL image (global context available)

  CONTEXT BLOCK   1 block
                  scale        ~ U(0.85, 1.00)   of image area
                  aspect ratio = 1.0  (square)
                  THEN: every patch overlapping ANY target block is
                        REMOVED from the context

  RESULT: context is a large, spatially contiguous, semantically
          informative region with 4 holes punched in it.
```

Two design decisions carry the whole result and both are ablated in the paper. **Targets must be large and semantic:** if you mask individual random patches (the MAE / BEiT default), the target embedding is dominated by local appearance and the task is solvable by texture continuation, so the encoder never learns object-level structure; at **15-20%** of image area a target contains parts of objects, and the ablations show accuracy degrading sharply as target scale falls toward patch level. **The context must be large but non-overlapping:** at **85-100%** scale the predictor gets rich global information, and removing the overlap is what people forget when reimplementing, because if any target patch remains visible the prediction is partly a copy. **Overlap leakage is the single most common reimplementation bug in this architecture, and its signature is a loss curve dropping much faster than the reference run while the linear probe stays flat.**

Reported results: I-JEPA with a ViT-H/14 reaches roughly **79%** ImageNet-1K linear-probe top-1 at 224 resolution, around **81%** for the 448 variant, and it beats MAE on both linear probing and low-shot (1% labels) semi-supervised evaluation at an order of magnitude less compute. It is *also* strong on low-level tasks, which answers the obvious objection: I-JEPA reports better object-counting and depth-prediction probes than view-invariant methods like DINO and iBOT, because invariance-based methods deliberately destroy exactly that information. That asymmetry (JEPA better on *low-level spatial* tasks, contrastive better on *high-level semantic* ones) is the most useful summary of the two families and a far better interview answer than "JEPA is better."

Volunteer the counterweight: **DINOv2** (Oquab et al., 2023, ViT-g/14, **1.1B** parameters, curated **LVD-142M**) reports around **86.5%** ImageNet linear probe, comfortably above I-JEPA. The comparison is not apples-to-apples (data scale, curation, distillation from a large teacher, augmentations) but that cuts both ways: a practitioner choosing a frozen backbone in 2026 does not get to demand a clean comparison, they get to pick the better number.

### V-JEPA and V-JEPA 2: video, then actions

**V-JEPA** (Bardes et al., "Revisiting Feature Prediction for Learning Visual Representations from Video", arXiv 2404.08471, February 2024) is the direct port: 3D tubelet patches instead of 2D patches, masking extended along time so a masked region covers the **same spatial region across all frames of the clip** (masking a random subset of patches per frame is trivially solvable by copying from adjacent frames, which is the video analogue of the overlap-leakage bug), and no image encoder, no text, no negatives, no reconstruction. Trained on **VideoMix2M** (2 million videos assembled from public sets), the ViT-H/16 reports **81.9%** on Kinetics-400, **72.2%** on Something-Something-v2 and **77.9%** on ImageNet-1K, all with a **frozen backbone** and an attentive probe. The frozen-backbone qualifier is what makes the numbers meaningful: they measure the representation, not a fine-tuning budget.

**V-JEPA 2** (Assran et al., arXiv 2506.09985, 11 June 2025, 48 pages, 19 figures) is the one to know in detail, because it is where the argument stops being about ImageNet and starts being about a robot. It is explicitly a **two-stage** design.

**Stage 1, action-free pretraining.** A **ViT-g** encoder at roughly **1.2B** parameters, trained with the standard V-JEPA masked-latent-prediction objective on **VideoMix22M**, described as over **1 million hours** of internet video plus images. No actions, no rewards, no labels. Reported results: **77.3%** top-1 on Something-Something-v2 (a motion-understanding benchmark that is specifically hard for appearance-biased models, because the classes are things like "pushing something from left to right" where a single frame tells you nothing), and **39.7** recall-at-5 on Epic-Kitchens-100 action anticipation, described as state of the art and surpassing prior task-specific models. Aligned with an LLM at the **8B** scale, the same encoder yields **84.0** on PerceptionTest and **76.9** on TempCompass.

**Stage 2, action-conditioned post-training.** Freeze the stage-1 encoder. Train a *new* predictor, **V-JEPA 2-AC**, that consumes the frozen representation of the current observation plus an **action** (end-effector state and gripper command) and predicts the representation of the next observation. Training data: **fewer than 62 hours** of unlabelled robot video from the open **Droid** dataset. Note precisely what "unlabelled" means here and be ready to defend it: the videos come with robot proprioception and action logs, so there are actions, but there are **no task labels, no rewards, no teleoperated demonstrations curated for a target task, and no data from the deployment environments.**

**Deployment.** Zero-shot on Franka arms **in two different labs**, with a goal specified as an **image**. At each control step the system runs inference-time planning: sample candidate action sequences, roll them forward through the action-conditioned predictor **in latent space only**, score each by the distance between the predicted future representation and the goal image's representation, take the best first action, execute, re-observe, replan. That is model-predictive control with a learned latent model and, structurally, it is exactly the "actor performs inference-time optimisation against the cost module" proposal from the 2022 position paper. Reported success on pick-and-place of novel objects is in the **65-80%** range depending on task and object, with **no data collected from those robots or those rooms, no task-specific training and no reward function**.

Separate the tiers explicitly, because this is where interviews are won. **Benchmarked:** the SSv2, EK100, PerceptionTest and TempCompass numbers, and the zero-shot Franka success rates, all published with a 48-page paper and open-sourced code and weights at `facebookresearch/vjepa2`. **Demo-adjacent:** the framing of V-JEPA 2 as "a world model that understands physics," which is a press-release gloss on a representation-quality result. **Follow-on:** V-JEPA 2.1 (arXiv 2603.14482, March 2026) reports that unlocking dense features improves real-robot grasping success by about **+20 percentage points** over V-JEPA 2-AC in zero-shot deployment, which is both good news for the line and a quiet admission that the original dense features were weak, since a +20-point headroom means the stage-1 representation was leaving a lot on the table for control.

### Collapse detection: what you would actually measure

The whole reason this matters is that **the training loss cannot tell you.** Collapse *lowers* the loss. Here is the instrumentation to add before you launch a run, not after.

**Test 1. Per-dimension std of L2-normalised embeddings.** The BYOL/SimSiam standard diagnostic and the cheapest. Normalise each embedding, take the std of each coordinate across the batch. For a healthy representation spread roughly uniformly on the unit sphere each coordinate has std about `1/sqrt(D)`: **0.031** at `D = 1024`, **0.028** at `D = 1280`. **A collapsed run reads near 0.** Log the mean across dimensions every 100 steps; alert below `0.3/sqrt(D)` sustained for 500 steps.

**Test 2. Effective rank of the embedding covariance.** Take at least `4 x D` embeddings, centre, compute singular values, normalise `p_i = sigma_i / sum(sigma)`, report `RankMe = exp(-sum p_i log p_i)`. Healthy vision backbones land in the **0.2 to 0.8 x D** band (roughly 250-1000 at `D = 1280`). Full collapse gives **1**. Partial or *dimensional* collapse, far more common and far more dangerous, gives **20 to 60** while the loss and an easy linear probe both still look fine. RankMe needs no labels and correlates with downstream transfer, which makes it the right model-selection signal for SSL runs.

**Test 3. Pairwise cosine similarity distribution on a held-out batch.** 1,000 distinct images, full pairwise cosine matrix, look at the **distribution**, not the mean. Healthy: broad, centred around **0.0 to 0.3**. Collapsed: a spike above **0.95**. The distribution matters because a mean of 0.4 can be a healthy spread or a bimodal disaster.

**Test 4. The predictor-identity check.** Ask the predictor for a target position *already visible in the context* and for one far away, and compare. Near-identical outputs mean the predictor has degenerated toward identity or a constant. Complementarily, correlate `pred(ctx, pos)` against the *mean* training embedding: a predictor emitting the dataset mean for everything is a partial collapse that Test 1 misses when the encoder itself is still healthy.

**Test 5. A probe on a task requiring spatial detail, not just classification.** A linear probe on ImageNet or CIFAR is a weak instrument, since coarse classification survives a lot of information loss and a representation collapsed to a few dozen semantic clusters still scores respectably. Probe **depth estimation, object counting, keypoint localisation, or segmentation mIoU**. I-JEPA reports the low-level probes for exactly this reason. ImageNet probe fine plus counting probe at chance means partial collapse, not a good representation.

**Test 6. Kill the anti-collapse device on purpose, once.** Run 2,000 steps with `m = 0` (no lag) or with the stop-gradient removed. It should collapse hard and fast, loss under `1e-3` within a few hundred steps. If it does *not*, your monitoring is broken or your loss is not measuring what you think it is. A two-hour experiment that saves a two-week debugging cycle, and raising it unprompted is a strong senior signal.

### The two alternatives, compared honestly

| | **JEPA (I-JEPA / V-JEPA)** | **Generative (MAE)** | **Contrastive / invariance (SimCLR, DINO)** |
|---|---|---|---|
| Prediction target | learned embedding of masked region | raw pixels of masked region | embedding of an augmented view |
| Loss space | representation | pixel | representation |
| Collapse possible? | **yes, it is the central risk** | no (target is external) | yes (contrastive negatives or centring prevent it) |
| Needs augmentations? | no | no | **yes, hand-designed and domain-specific** |
| Needs negatives / large batch? | no | no | SimCLR yes (**4,096**), DINO no (centring + sharpening) |
| Compute to pretrain ViT-H/14 on IN-1k | **<1,200 GPU-hours** | ~10x more | iBOT ViT-S/16 already 2.5x slower than I-JEPA ViT-H/14 |
| ImageNet linear probe (best reported) | ~**79%** (ViT-H/14), ~**81%** @448 | ~**75.8%** (ViT-L) | DINO ViT-B/8 **80.1%**, **DINOv2 ViT-g/14 ~86.5%** |
| ImageNet fine-tuned | strong | **~87.8%** (ViT-H) | strong |
| Low-level spatial probes (depth, counting) | **best of the three** | good (pixel objective preserves detail) | **worst** (invariance destroys it) |
| Interpretable failure? | **no**, fails silently | **yes**, reconstructions visibly blur | partially (loss plateaus, uniformity metric drops) |
| Can you inspect a sample? | no decoder, so no | yes | no |
| Motion / temporal tasks | **best** (V-JEPA 2 SSv2 77.3) | weak | weak |

Read the table out loud like this: **MAE buys an inspectable, collapse-proof objective at roughly 10x the compute and a representation contaminated with photometric detail. Contrastive buys the best semantic representation on curated image data at the cost of hand-designed invariances you must redesign per domain and that actively destroy spatial information. JEPA buys compute efficiency, no augmentation design, and the best motion and spatial representations, at the cost of an objective whose global minimum is degenerate and whose failure is invisible.** Three different trades, none dominant. Say that, then say which you would pick for the job on the table.

---

## Build it from scratch

The smallest thing that is genuinely a JEPA and not a masked autoencoder: two encoders where one is an EMA copy with a stop-gradient, a narrow predictor, multi-block masking with overlap removal, and collapse instrumentation wired in from step zero. The instrumentation is not optional garnish here; it is the only thing that tells you the run is real. Matching lab folder: `labs/py/26-02-jepa/`.

```python
# untested sketch -- minimal I-JEPA. Deliberately omits: mixed precision,
# multi-node, cosine LR/WD schedules, the ViT itself (use timm), and the
# latent variable z. Those are orthogonal to the idea being demonstrated.
import math
import torch
import torch.nn as nn
import torch.nn.functional as F

D_ENC, D_PRED, N_PATCH = 1280, 384, 256      # ViT-H/14 @ 224 -> 16x16 patches


class Predictor(nn.Module):
    """Narrow ViT. Narrowness is an ANTI-COLLAPSE device, not an economy."""

    def __init__(self, depth=6, heads=6):
        super().__init__()
        self.proj_in = nn.Linear(D_ENC, D_PRED)
        self.mask_token = nn.Parameter(torch.zeros(1, 1, D_PRED))
        self.pos = nn.Parameter(torch.zeros(1, N_PATCH, D_PRED))
        layer = nn.TransformerEncoderLayer(
            D_PRED, heads, dim_feedforward=4 * D_PRED,
            batch_first=True, norm_first=True)
        self.blocks = nn.TransformerEncoder(layer, depth)
        self.proj_out = nn.Linear(D_PRED, D_ENC)
        nn.init.trunc_normal_(self.mask_token, std=0.02)
        nn.init.trunc_normal_(self.pos, std=0.02)

    def forward(self, ctx_tokens, ctx_idx, tgt_idx):
        """ctx_tokens (B,Nc,D_ENC); ctx_idx (B,Nc); tgt_idx (B,Nt) -> (B,Nt,D_ENC)"""
        B, Nt = tgt_idx.shape
        x = self.proj_in(ctx_tokens) + self.pos.expand(B, -1, -1).gather(
            1, ctx_idx.unsqueeze(-1).expand(-1, -1, D_PRED))
        # mask tokens carry ONLY the positional embedding of where to predict.
        m = self.mask_token.expand(B, Nt, -1) + self.pos.expand(B, -1, -1).gather(
            1, tgt_idx.unsqueeze(-1).expand(-1, -1, D_PRED))
        h = self.blocks(torch.cat([x, m], dim=1))
        return self.proj_out(h[:, -Nt:])


def multiblock_mask(grid=16, n_tgt=4, tgt_scale=(0.15, 0.20),
                    tgt_ar=(0.75, 1.5), ctx_scale=(0.85, 1.0)):
    """Returns (context_indices, list_of_target_index_tensors).
    THE OVERLAP REMOVAL IS THE BUG-PRONE LINE. Without it the task is
    partly a copy and the representation learns nothing."""
    def sample_block(scale, ar_range):
        s = torch.empty(1).uniform_(*scale).item() * grid * grid
        ar = math.exp(torch.empty(1).uniform_(
            math.log(ar_range[0]), math.log(ar_range[1])).item())
        h = max(1, min(grid, int(round(math.sqrt(s / ar)))))
        w = max(1, min(grid, int(round(math.sqrt(s * ar)))))
        top = torch.randint(0, grid - h + 1, (1,)).item()
        left = torch.randint(0, grid - w + 1, (1,)).item()
        idx = [(top + i) * grid + (left + j) for i in range(h) for j in range(w)]
        return set(idx)

    targets = [sample_block(tgt_scale, tgt_ar) for _ in range(n_tgt)]
    ctx = sample_block(ctx_scale, (1.0, 1.0))
    union = set().union(*targets)
    ctx = ctx - union                                   # <-- overlap removal
    if not ctx:                                          # degenerate draw
        return multiblock_mask(grid, n_tgt, tgt_scale, tgt_ar, ctx_scale)
    return (torch.tensor(sorted(ctx)),
            [torch.tensor(sorted(t)) for t in targets])


class IJEPA(nn.Module):
    def __init__(self, encoder_fn):
        super().__init__()
        self.ctx_enc = encoder_fn()                      # e.g. timm ViT-H/14
        self.tgt_enc = encoder_fn()
        self.tgt_enc.load_state_dict(self.ctx_enc.state_dict())
        for p in self.tgt_enc.parameters():
            p.requires_grad = False                      # EMA-only, never SGD
        self.predictor = Predictor()

    @torch.no_grad()
    def ema_update(self, m: float):
        for pt, pc in zip(self.tgt_enc.parameters(), self.ctx_enc.parameters()):
            pt.mul_(m).add_(pc.detach(), alpha=1.0 - m)
        for bt, bc in zip(self.tgt_enc.buffers(), self.ctx_enc.buffers()):
            bt.copy_(bc)                                 # BN/LN buffers: copy

    def forward(self, imgs, ctx_idx, tgt_idx):
        with torch.no_grad():                            # <-- the stop-gradient
            self.tgt_enc.eval()
            full = self.tgt_enc(imgs)                    # FULL image, (B,N,D_ENC)
            full = F.layer_norm(full, (D_ENC,))          # kills "shrink target norms"
            tgt = full.gather(1, tgt_idx.unsqueeze(-1).expand(-1, -1, D_ENC))
        ctx = self.ctx_enc(imgs, keep_idx=ctx_idx)       # VISIBLE patches only
        pred = self.predictor(ctx, ctx_idx, tgt_idx)
        return F.smooth_l1_loss(pred, tgt), tgt


def ema_momentum(step, total, m0=0.996, m1=1.0):
    """I-JEPA: LINEAR 0.996 -> 1.0. Freezing the target at the end is
    an endgame stability measure, not an accident."""
    return m0 + (m1 - m0) * step / total


# ---------------------------------------------------------------- diagnostics
@torch.no_grad()
def collapse_report(emb: torch.Tensor) -> dict:
    """emb (B, D). Run every 100 steps. THE LOSS WILL NOT TELL YOU."""
    B, D = emb.shape
    z = F.normalize(emb.float(), dim=-1)
    per_dim_std = z.std(dim=0).mean().item()             # healthy ~ 1/sqrt(D)
    c = emb.float() - emb.float().mean(0, keepdim=True)
    sv = torch.linalg.svdvals(c)
    p = sv / sv.sum().clamp_min(1e-12)
    rankme = torch.exp(-(p * (p + 1e-12).log()).sum()).item()
    sim = (z @ z.T)
    off = sim[~torch.eye(B, dtype=torch.bool, device=z.device)]
    return {
        "per_dim_std": per_dim_std,
        "healthy_std": 1.0 / math.sqrt(D),               # D=1280 -> 0.0280
        "rankme": rankme,                                # healthy 0.2-0.8 x D
        "cos_mean": off.mean().item(),                   # healthy 0.0-0.3
        "cos_p95": off.quantile(0.95).item(),            # collapsed -> >0.95
        "COLLAPSED": per_dim_std < 0.3 / math.sqrt(D) or rankme < 0.05 * D,
    }
```

Three things reimplementations get wrong. **Step 1.** The target encoder runs on the **full** image and targets are gathered afterwards; running it on target patches alone destroys the global-context property that makes targets semantic, and you get a weaker representation with no error message. **Step 2.** `ctx = ctx - union` is the overlap removal. Delete that one line and the run still trains, the loss drops *faster*, and the representation is worthless. No assertion fires. **Step 3.** `collapse_report` runs from step 0, not from the first checkpoint, because a run that collapses does so early and the cheapest outcome is discovering it at step 800 rather than hour 60.

For the action-conditioned extension (V-JEPA 2-AC in miniature): freeze `ctx_enc`, add a predictor taking `[repr(o_t), a_t]` to `repr(o_{t+1})`, train on trajectory pairs with the same smooth-L1 objective, and plan with the cross-entropy method at inference (sample `K` action sequences of length `H`, roll each forward in latent space only, score by `||repr_pred(o_{t+H}) - repr(goal_image)||`, refit to the top-`k`, iterate two or three rounds, execute the first action, replan). `H` is bounded by compounding error exactly as derived in `T26-world-models`: at 2% per-step divergence a 15-step horizon retains about **74%** fidelity and a 50-step horizon about **36%**, which is why these systems replan every step instead of executing open-loop plans.

---

## How it's done in production

Be blunt about the state of play: **there is no managed JEPA service.** No SageMaker built-in, no Vertex recipe, no `transformers` one-liner that handles pretraining. What exists is research code and released weights, and the realistic production path is "download the weights, freeze the encoder, train a head."

**What is available.** `facebookresearch/vjepa2` (PyTorch code and weights, June 2025), plus `facebookresearch/jepa` (V-JEPA v1) and `facebookresearch/ijepa`; V-JEPA 2 encoder weights are also on Hugging Face, so the realistic integration for most teams is the same shape as any frozen vision backbone (`encoder.eval()`, `torch.no_grad()`, extract features, train a head). `rbalestr-lab/lejepa` supplies SIGReg if you are pretraining on your own domain. Meta also released three physical-reasoning benchmarks alongside V-JEPA 2 (IntPhys 2, MVPBench, CausalVQA), which are the right harness if you are making claims about physical understanding rather than classification.

**The realistic decision tree.** Frozen general-purpose *image* backbone for classification, retrieval or a VLM adapter: use DINOv2/v3 or CLIP, better numbers and a deeper ecosystem. **Motion or temporal** understanding (action recognition, anticipation, video QA): V-JEPA 2 is genuinely competitive and the SSv2 and EK100 numbers are why. **Latent world model for robot control off cheap data:** V-JEPA 2-AC is the only published option with a zero-shot cross-lab result off under 62 hours of robot video. **A domain with no sensible augmentations** (industrial sensor imagery, medical volumes, radar, seismic, telemetry): the underrated case, where augmentation-freedom is worth more than the benchmark gap, because designing augmentations for a domain you lack intuition about is a multi-month project with no guarantee of success.

**Serving cost.** A **1.2B** ViT-g in fp16 is about **2.4 GB** of weights, and video cost scales with tubelet count: a 16-frame 224 clip at `2x16x16` tubelets is roughly `8 x 14 x 14 = 1,568` tokens, about 6x a single 224 image through a ViT/14. This is not a 20 ms model. In the robot loop the encoder runs once per observation while the predictor runs `K x H` times per planning step, so predictor narrowness is a serving win as well as an anti-collapse device.

### Failure-mode table

| Symptom | Cause | Fix |
|---|---|---|
| Training loss drops 2+ orders of magnitude in the first few hundred steps and flatlines near zero; per-dimension std of L2-normalised embeddings below `0.3/sqrt(D)` (under **0.008** at `D=1280`); pairwise cosine similarity p95 above **0.95**; covariance effective rank (RankMe) in the single digits out of 1280 | **Full representation collapse.** The degenerate constant map is a global minimum of the objective and the optimiser found it. Usually caused by EMA momentum too low (target tracks context too fast), stop-gradient accidentally removed (e.g. `requires_grad=True` on the target encoder, or forgetting `torch.no_grad()`), learning rate too high during warmup, or a predictor wide enough to absorb a degenerate encoder | Verify the stop-gradient first with an assertion that target-encoder grads are `None` after `backward()`. Raise EMA momentum to **0.996+** with a linear ramp to 1.0. Extend LR warmup to **~40** epochs at ImageNet scale. Add an explicit anti-collapse term: VICReg-style variance (hinge each dimension's std at 1.0) plus covariance off-diagonal penalty, or SIGReg. Log `RankMe` and per-dim std every 100 steps and hard-fail the job on the threshold rather than discovering it at hour 60 |
| Loss is very low but downstream probes are at or near chance; predictor output is nearly identical for target positions that are far apart; predictor output correlates >0.9 with the dataset-mean embedding; ablating the context (feeding zeros) barely changes the prediction | **Predictor learned the identity or the mean.** Either the context leaks the target (target patches not removed from the context region, or in video the mask does not extend across time so adjacent frames give it away), or the predictor is over-parameterised relative to the task, or targets are too small/local so patch-level texture continuation solves the task | Assert `set(ctx_idx) & set(tgt_idx) == empty` in the data loader, as a test, not a comment. In video, mask the **same spatial region across all frames** of the clip. Shrink the predictor (dim **384** against encoder **1280** is the reference ratio; do not widen it "for capacity"). Raise target block scale to the **0.15-0.20** area range so targets contain object parts rather than texture. Run the context-ablation test as a scheduled eval: if zeroing the context does not raise the loss substantially, the predictor is not using it |
| Run is stable but final probe accuracy is several points below the reference, or training is unstable early with loss spikes and occasional divergence | **EMA momentum set wrong.** Too low (`m < 0.99`, window under 100 steps) makes the target chase the context, shrinking the effective asymmetry toward zero and drifting the run toward collapse. Too high (`m = 0.9999`, window 10,000 steps) makes the target so stale that the context encoder optimises against a nearly-random early-training target, wasting most of the budget and slowing convergence badly. A **constant** momentum with no ramp leaves the target moving at the end of training, which adds noise exactly when you want convergence | Use the published schedule, do not invent one: linear **0.996 → 1.0** over the full run. Sanity-check the implied window as `1/(1-m)` steps and confirm it is a small fraction of total steps at the start (250 of, say, 500k) and effectively infinite at the end. If you shorten the schedule for a small-data run, scale the *ramp*, not the endpoints. Ablate at **0.99 / 0.996 / 0.999** on a 10%-budget run before committing to a full one; the probe gap will be visible at 10% budget |
| Linear probe on ImageNet or your classification set looks fine (within 1-2 points of reference) but the model fails on anything requiring spatial or temporal detail: depth probe near a constant-predictor baseline, object counting at chance, keypoint localisation poor, segmentation mIoU collapses, action-recognition classes that differ only by direction of motion are confused | **Partial / dimensional collapse, masked by a weak evaluation.** A coarse classification probe survives enormous information loss because the representation only needs a few dozen well-separated clusters. The representation has collapsed onto a low-dimensional semantic subspace and discarded the spatial and temporal structure, and RankMe would read ~20-60 out of 1280 while every headline metric looks healthy. This is also the exact failure induced by borrowing invariance-based augmentations into a JEPA recipe | Never accept a linear probe alone as evidence. Add at least one **detail-sensitive** probe to the eval suite: monocular depth, object counting, keypoint or segmentation, and for video a motion-sensitive benchmark such as Something-Something-v2 where single-frame appearance is uninformative. Track RankMe as a first-class metric alongside probe accuracy. Report probe results at multiple layers, since partial collapse often shows as the last block being much worse than the second-to-last, which is also a hint to probe an intermediate layer in production |

---

## Tradeoffs & when NOT to use it

The senior signal is knowing where reaching for JEPA is the wrong call, and there are several real ones.

**When you need to inspect or generate the output.** There is no decoder. You cannot look at a sample and see it is wrong, cannot show a stakeholder what the model "thinks will happen," and cannot synthesise training data. For generating synthetic driving scenes, or where a human must review predicted futures before a robot acts, you want a generative model (or a JEPA plus a separately trained decoder, which reintroduces the pixel cost you were avoiding). In regulated and safety-critical settings, "the model cannot show its work" is sometimes a blocking requirement rather than an inconvenience.

**When a strong curated-data backbone already exists for your modality.** For general image tasks in 2026, DINOv2/v3 and CLIP-family models are better on the benchmarks that matter with a far deeper ecosystem of adapters, quantised variants and deployment recipes. Choosing I-JEPA over DINOv2 for ImageNet-style classification because it is "more principled" is a research preference imposed on a product decision, and an interviewer will read it as exactly that.

**Training from scratch on a small dataset.** The anti-collapse machinery is a dynamics argument depending on a long optimisation trajectory. On tens of thousands of images with a short schedule you are in the regime where collapse is most likely and you have the least budget to detect it. Below roughly 100k samples, fine-tune an existing backbone. If you must pretrain on a small domain set, use an explicitly regularised variant (SIGReg or VICReg terms) rather than the pure EMA recipe, because an explicit regulariser degrades gracefully where a dynamics argument does not.

**When the task is genuinely invariance-shaped.** If two photographs of the same product under different lighting must embed near-identically, a contrastive objective with lighting augmentations gives you that directly. JEPA will learn a representation that *distinguishes* the lighting, because distinguishing it helps prediction, and you would have to train invariance back in.

**Do not call it a world model when you have only trained stage 1.** An action-free V-JEPA encoder is a representation learner with no `p(s'|s,a)`, so it cannot be rolled forward under a candidate action and cannot support planning or counterfactual evaluation. Only the action-conditioned predictor (V-JEPA 2-AC) qualifies in the sense used in `T26-world-models`. Candidates conflate these constantly and it is a high-value correction to make.

**Be honest about the horizon limit.** The action-conditioned predictor faces the same compounding-error arithmetic as any learned dynamics model, and the published results are short-horizon pick-and-place with per-step replanning, not long-horizon multi-stage manipulation. Against a proposal to plan 200 steps deep in latent space, the answer is the half-life formula from `T26-world-models` (`H_1/2 ≈ 0.693/eps`, so 2% per-step error gives about **34** steps before half your rollouts have gone wrong), not enthusiasm.

**Where it is clearly right.** Abundant unlabelled temporal data, no sensible augmentation design, and a downstream task needing motion or spatial structure: industrial video, robotics, surveillance analytics, sports analysis, medical ultrasound and endoscopy, sensor time series. A genuinely large space, and where augmentation-freedom earns its keep independent of who is right about AGI.

---

## Interview questions

### Q1 — What is a JEPA and how is it different from a masked autoencoder?
**Testing:** whether you can state the one structural difference without hand-waving about "understanding."
**Answer:** Both mask part of the input and predict the missing part. The difference is the space the loss lives in. MAE predicts **raw pixels** of the masked patches (75% mask ratio, asymmetric encoder-decoder, ViT-H fine-tunes to about **87.8%** ImageNet top-1) against an externally fixed ground truth. A JEPA predicts the **embedding** of the masked region, produced by a target encoder that is an EMA copy of the context encoder, and there is no decoder at all. Two consequences follow directly: the JEPA encoder is free to discard unpredictable detail (which is why I-JEPA pretrains a ViT-H/14 in **under 1,200 GPU-hours**, roughly **10x cheaper** than MAE at the same architecture, with better frozen-probe accuracy), and the JEPA objective has a degenerate global minimum (constant encoder, zero loss) that MAE structurally cannot have.
**Follow-up trap:** "So MAE is strictly worse?" No, and saying yes fails. MAE's fixed external target makes it **collapse-proof** and its failures are **visible**: a bad MAE produces blurry reconstructions you can look at. A bad JEPA produces a loss of 0.0003 and a rank-3 covariance with no error message. MAE also fine-tunes extremely well and preserves low-level detail because the decoder demands it. The right framing is a trade of compute efficiency and representation cleanliness against objective safety and inspectability.

### Q2 — Why would predicting in representation space be better than predicting in pixel space? Derive it.
**Testing:** can you produce the information-theoretic argument rather than repeating "pixels are wasteful."
**Answer:** Decompose `H(y|x) = H(y_predictable|x) + H(y_noise|x)`. A pixel objective has an externally fixed target, so minimising it requires modelling both terms; under squared error the optimum on the aleatoric part is the conditional mean, which is a blur, and under a likelihood objective it is an accurate model of noise, which is worse because you paid parameters for it. An embedding objective has a **learned** target, so the joint system can reduce loss by simply not encoding the unpredictable part. Concretely: a 224x224 RGB image is **150,528** numbers of which the loss mass is dominated by texture and grain; I-JEPA instead predicts embeddings of **4** blocks at **15-20%** area each in a **1280**-dim space, and the encoder chooses what those numbers mean.
**Follow-up trap:** "If the encoder can choose not to represent things, what stops it from representing nothing?" Nothing in the loss. That is the entire point: collapse is the **global minimum** of the naive objective, so the defence has to be that gradient descent cannot reach it (stop-gradient plus EMA lag plus a narrow predictor), not that the objective disfavours it. Candidates who cannot make that distinction have not understood the architecture.

### Q3 — Walk me through the I-JEPA masking strategy, with numbers.
**Testing:** whether you have read the paper or a summary of it.
**Answer:** Per image, resampled each step: **4 target blocks**, each with area scale sampled uniformly from **(0.15, 0.20)** of the image and aspect ratio from **(0.75, 1.5)**, allowed to overlap each other. **1 context block** at scale **(0.85, 1.0)** and aspect ratio **1.0**, from which **every patch overlapping any target block is removed**. Targets are computed by running the target encoder over the **full unmasked image** and slicing out the target positions, so target representations carry global context. The context encoder sees only the visible patches.
**Follow-up trap:** "Why not just mask random individual patches, like BEiT?" Because a patch-sized target is solvable by texture continuation from its neighbours, so the encoder never has to learn object-level structure, and the paper's ablations show accuracy degrading sharply as target scale shrinks toward patch level. The second half of the trap is the overlap removal: if you leave target patches visible in the context, the prediction becomes partly a copy, the loss falls **faster** than the reference run, and the representation is worthless. That is the most common reimplementation bug in this architecture and its signature is exactly "loss better than the paper, probe much worse."

### Q4 — What is representation collapse and how would you detect it in a running job?
**Testing:** the core operational question. This is the one that separates people who have trained one from people who have read about one.
**Answer:** Collapse is the encoder mapping all inputs to (nearly) the same embedding, which drives the prediction loss to zero while destroying all information. **The training loss cannot detect it, because collapse lowers the loss.** Four instruments, logged every 100 steps from step zero: (1) **per-dimension std of L2-normalised embeddings**, which should be near `1/sqrt(D)` (**0.028** at `D=1280`) and reads near 0 when collapsed; alert below `0.3/sqrt(D)`. (2) **Effective rank of the embedding covariance**, `RankMe = exp(entropy of normalised singular values)`, healthy in the **0.2-0.8 x D** band (roughly 250-1000 at D=1280), **1** when fully collapsed and **20-60** in the far more common partial-collapse case. (3) **Pairwise cosine similarity distribution** across a held-out batch: healthy is a broad spread centred **0.0-0.3**, collapsed is a spike above **0.95**. (4) A **detail-sensitive probe** (depth, counting, keypoints) rather than only a classification probe.
**Follow-up trap:** "Your linear probe is within a point of the reference. Is the run healthy?" No, that is insufficient evidence. Coarse classification survives enormous information loss, so a representation that has partially collapsed onto a few dozen semantic clusters still probes well on ImageNet while scoring at chance on object counting. That is **dimensional collapse** and it is the failure mode a classification-only eval is structurally blind to. Answer with RankMe plus a spatial probe, or you have not answered.

### Q5 — Why does the EMA target encoder prevent collapse? Is that a proof?
**Testing:** intellectual honesty. There is a wrong confident answer here and most candidates give it.
**Answer:** It is not a proof and you should say so. Three mechanisms, none sufficient alone. The **stop-gradient** removes the gradient path that would pull the target toward the prediction, so the system can only move one side; SimSiam showed that stop-gradient alone, with no momentum encoder and no negatives, already avoids collapse, which means EMA is not the sole mechanism. The **EMA lag** at `m = 0.996` gives the target an effective window of `1/(1-m) = 250` steps, so a context encoder attempting to shrink is scored against a target that has not shrunk yet, producing an opposing loss; this is a claim about the optimisation *trajectory*, not about the objective's minima. The **narrow predictor** (dim **384** against a **1280** encoder) is too weak to absorb a degenerate encoder cheaply. The collapse solution remains a global minimum of the objective throughout.
**Follow-up trap:** "If it is just heuristics, has anyone fixed it properly?" Yes, and naming it is the win: **LeJEPA** (Balestriero and LeCun, arXiv 2511.08544, November 2025) proves the **isotropic Gaussian** is the unique embedding distribution minimising worst-case downstream prediction risk, and enforces it with **SIGReg**, which projects embeddings onto random 1D directions and matches characteristic functions per projection, at **linear** time and memory, collapsing the recipe to about **one** trade-off hyperparameter. The rhetorical point worth making: LeCun co-authoring a paper that calls his own prior anti-collapse stack "heuristics" is the strongest available confirmation that this criticism was correct.

### Q6 — Explain V-JEPA 2's two-stage training and exactly how much robot data it used.
**Testing:** whether you can separate the web-scale pretraining claim from the robot claim, which is where press coverage blurs.
**Answer:** **Stage 1, action-free:** a **1.2B**-parameter ViT-g trained with masked latent prediction on **VideoMix22M**, over **1 million hours** of internet video plus images, no actions, no rewards, no labels. Benchmarked outputs: **77.3%** top-1 on Something-Something-v2, **39.7** recall-at-5 on Epic-Kitchens-100 anticipation (reported SOTA, surpassing prior task-specific models), and with an LLM alignment at the **8B** scale, **84.0** on PerceptionTest and **76.9** on TempCompass. **Stage 2, action-conditioned:** freeze the encoder, train a *new* predictor (**V-JEPA 2-AC**) that maps `[repr(o_t), a_t] -> repr(o_{t+1})`, on **fewer than 62 hours** of unlabelled robot video from the open **Droid** dataset. Deployment: **zero-shot** on Franka arms in **two different labs**, goal given as an image, planning by rolling candidate action sequences forward in latent space and scoring against the goal representation, replanning every step. Roughly **65-80%** pick-and-place success on novel objects with **no data from those robots, no task-specific training and no reward**.
**Follow-up trap:** "62 hours of *unlabelled* data, really?" Be precise or lose the point. Droid trajectories carry robot proprioception and action logs, so actions are present; what is absent is **task labels, rewards, curated demonstrations for the target task, and any data from the deployment environment.** "Unlabelled" here means no task supervision, not no actions. A candidate who overstates this to "it learned to manipulate from 62 hours of raw video" has just failed the honesty check, and a candidate who understates it to "so it's just imitation learning" has missed that there were no demonstrations of the deployment tasks at all.

### Q7 — How is a JEPA different from a contrastive method like SimCLR or DINO?
**Testing:** the taxonomy, and whether you understand that invariance and prediction are opposite objectives.
**Answer:** Contrastive and self-distillation methods are **invariance-based joint-embedding**: they take two *augmented views of the same image* and pull their embeddings together, with negatives (SimCLR, batch **4,096**, temperature **0.1**, ResNet-50 linear **69.3%**) or with centring-and-sharpening instead of negatives (DINO, ViT-B/8 linear **80.1%**, k-NN **77.4%**). A JEPA takes **two different parts of the same signal** and predicts one embedding from the other. The objective is *prediction*, not invariance, and no hand-designed augmentations are used. That matters for two reasons: augmentations encode a human's guess about what should be invariant, which does not transfer across domains, and **a world model must model change, not be invariant to it**, so an invariance objective is structurally the wrong tool for the downstream goal.
**Follow-up trap:** "Then why does DINOv2 beat I-JEPA on ImageNet?" Concede it cleanly: DINOv2 (ViT-g/14, **1.1B** params, curated **LVD-142M**) reports about **86.5%** linear probe against I-JEPA's roughly **79%**. The comparison confounds data scale, curation and distillation, but the honest answer is that curated data plus augmentations plus distillation currently wins on **semantic classification**, while JEPA wins on **low-level spatial** probes (depth, counting) where invariance-based training deliberately destroys the information, and on **motion** benchmarks. Two different strengths, not one method dominating.

### Q8 — Your JEPA loss drops to 1e-4 in 300 steps. What do you do?
**Testing:** debugging instinct under a symptom that looks like success.
**Answer:** Treat it as collapse until proven otherwise, because a healthy run does not do that. Ordered checks, cheapest discriminating first: (1) assert the target encoder's parameters have `grad is None` after `backward()`, which catches a missing `torch.no_grad()` or `requires_grad=False`; (2) run `collapse_report` on a held-out batch and read per-dim std against `1/sqrt(D)` and RankMe against `D`; if std is under **0.008** at D=1280 and RankMe is single-digit, it is full collapse; (3) check the data loader with `assert set(ctx_idx) & set(tgt_idx) == set()`, since overlap leakage produces exactly this "too good" loss curve; (4) check the EMA momentum actually applied, not just configured, since `m` defaulting to 0 in a config merge is a classic; (5) check LR warmup length, since too-high early LR is a common trigger.
**Follow-up trap:** "The stop-gradient is there and RankMe is 900 out of 1280. Now what?" Then it is not collapse and you have the more interesting bug: the predictor is solving a task that is too easy. Run the **context-ablation test**, feeding zeros instead of the context embedding. If the loss barely rises, the predictor is not using the context, which means either leakage (in video, a mask that does not extend across time, so the answer is visible in the adjacent frame) or targets too small to require real inference. Fix by masking the same spatial region across all frames of the clip and raising target block scale.

### Q9 — Is JEPA a fundamentally better path than generative modelling, or an elegant SSL method that has not beaten scaled generative models downstream?
**Testing:** the whole point of the module. They want a position with evidence on both sides, not a side.
**Answer:** Split the claim in two and answer each. **The narrow claim is supported:** predicting in representation space is more compute-efficient (ViT-H/14 in **under 1,200 GPU-hours**, roughly **10x** MAE), needs no augmentation design, produces the best-reported low-level spatial and motion representations, and has produced the **only published zero-shot cross-lab robot planning result off under 62 hours of robot data**. That last item is a closed-loop task-success number on real hardware, which is a strictly stronger evidence class than any perceptual metric. **The broad claim is not supported:** "latent prediction is the path to machine intelligence" rests on H-JEPA, the hierarchical multi-timescale stack that is the actual proposal in the 2022 position paper, and as of August 2026 there is **no scaled demonstration of a working hierarchy**. Meanwhile a JEPA model is not the default frozen backbone in production stacks (DINO-family and CLIP-family are), I-JEPA sits about 7 points below DINOv2 on ImageNet linear probe, and no JEPA system has displaced a scaled generative model on a general capability benchmark. So: **validated as an efficient representation-and-dynamics learner, unvalidated as an architecture thesis.** State what would change your mind: an H-JEPA at V-JEPA-2 scale showing planning horizons that a flat model cannot reach, or a JEPA-based system beating a comparably-scaled generative model on a general benchmark suite.
**Follow-up trap:** "But V-JEPA 2's robot result proves the generative people are wrong, doesn't it?" No, and this is where candidates overreach. It proves *a* latent world model works for short-horizon goal-reaching. It does not compare against an equally-resourced generative baseline on the same task, it is short-horizon pick-and-place with per-step replanning rather than long-horizon manipulation, and the follow-up V-JEPA 2.1 (arXiv 2603.14482, March 2026) reporting a **+20 point** grasping improvement from unlocking dense features is itself evidence that the stage-1 representation was leaving substantial performance on the table. A result that a successor improves by 20 points is a promising result, not a settled one.

### Q10 — What does LeCun's "A Path Towards Autonomous Machine Intelligence" actually claim, and what has been demonstrated?
**Testing:** whether you read the primary source or a summary of the discourse.
**Answer:** It is a **position paper** (version 0.9.2, 27 June 2022, OpenReview), explicitly labelled as such, with **no experiments**. It proposes a modular cognitive architecture: a **configurator** that parameterises the other modules per task, **perception**, a **world model**, a **cost** module (immutable intrinsic cost plus trainable critic), **short-term memory**, and an **actor** that optimises an action sequence at inference time against predicted cost. JEPA is proposed as the world model's implementation; **H-JEPA** is proposed as the mechanism for long-horizon planning via prediction at multiple time scales and abstraction levels. Demonstrated since: single-level JEPA works as a representation learner (I-JEPA 2023, V-JEPA 2024), and a single-level action-conditioned JEPA supports short-horizon planning with inference-time action optimisation (V-JEPA 2-AC 2025), which does validate the "actor optimises actions against a latent world model" piece. **Not demonstrated at scale: the hierarchy, the configurator, and the intrinsic cost module.**
**Follow-up trap:** "So the paper has been validated?" Roughly one component of six, plus a partial validation of the inference-time-planning loop. The most load-bearing claim (that hierarchy makes long-horizon prediction tractable, which is what would answer the compounding-error problem) has the **least** evidence behind it. Being able to say which parts are unvalidated is the difference between having read the paper and having read about it.

### Q11 — You are choosing a frozen backbone for a production video-understanding service. Talk me through it.
**Testing:** engineering judgement, not architecture love.
**Answer:** Start from the task. If the discriminative signal is **appearance** (which objects, scene class, retrieval), a DINOv2/v3 or CLIP backbone applied per-frame with temporal pooling is the better first move: stronger semantic numbers, deeper ecosystem, cheaper inference. If the signal is **motion** (action classes differing by direction, anticipation, activity segmentation), V-JEPA 2 is the right first try, because SSv2 at **77.3%** and EK100 anticipation at **39.7** recall-at-5 are exactly the benchmarks built so single-frame appearance does not solve them. Budget: a **1.2B** ViT-g in fp16 is about **2.4 GB**, and a 16-frame 224 clip is roughly **1,568** tokens, about 6x a single-image ViT/14 forward.
**Follow-up trap:** "Why not fine-tune the backbone for more accuracy?" You then own the collapse and drift risk, lose encoder sharing across services, and multiply the eval burden. More importantly the published V-JEPA numbers are **frozen-backbone** numbers, so the comparison you used to pick it is only valid frozen. Re-run it if you fine-tune, because MAE-style models close much of their gap under fine-tuning (ViT-L: **75.8%** linear against **85.9%** fine-tuned) and the ranking can invert.

### Q12 — Design the evaluation you would demand before letting a JEPA-based world model into a robot control loop.
**Testing:** whether you can specify a gate rather than admire a demo.
**Answer:** Five gates, escalating, each with a number attached before anyone runs it. **One:** representation health, RankMe above `0.2 x D` and per-dimension normalised std within 30% of `1/sqrt(D)` on held-out data, plus a depth or keypoint probe above a stated floor, to rule out partial collapse. **Two:** one-step latent prediction error against held-out real transitions, reported per action type, since the aggregate hides the manipulation-contact cases that matter. **Three:** multi-step rollout error against horizon, encoding a real initial state, rolling `H` steps under recorded actions and plotting error for `h = 1..4H`, then setting the planning horizon **below** the knee of that curve rather than at it. **Four:** closed-loop task success on real hardware in an environment not present in training, which is the V-JEPA 2-AC result format (**65-80%** zero-shot on Franka arms in two unseen labs), with the baseline stated. **Five:** rank correlation between predicted-in-model score and real outcome across at least 10-20 candidate policies or action sequences, because if you are using the model to *choose* actions, monotonicity is the property you actually depend on and it is not implied by low prediction error.
**Follow-up trap:** "Gate four passed at 78%. Ship it?" Not without gate five and not without an off-distribution trigger. A 78% success rate means a 22% failure rate whose *modes* you have not characterised, and planning against a learned model invites the model-exploitation dynamic (`T26-world-models`): the optimiser actively searches for regions where the model is optimistically wrong, so your realised failure rate under an optimising controller is worse than your measured failure rate under a fixed policy. You need a runtime guard on the prediction residual (if the observed next representation deviates from the predicted one beyond a calibrated threshold, stop and replan or hand back to a safe controller) before anything touches production hardware.

### Q13 — Would you use JEPA on non-visual data, say industrial sensor time series with no augmentation intuition?
**Testing:** whether you understand which property of JEPA is actually transferable.
**Answer:** This is the underrated strong case, yes. The transferable property is **augmentation-freedom**. Contrastive SSL requires you to specify what should be invariant, and for a domain where you have no perceptual intuition (vibration spectra, radar returns, seismic traces, plant telemetry) designing those augmentations is a multi-month research project with no guarantee of success, and a wrong choice silently destroys the information the downstream task needs. A JEPA needs only a masking scheme, which is a much weaker and more auditable design commitment: mask a contiguous span, predict its embedding from the surrounding context. The recipe has already been ported this way (T-JEPA for tabular data, plus audio and geospatial variants) with the architecture essentially unchanged.
**Follow-up trap:** "What is different about the masking design in a non-visual domain?" The leakage question changes shape and is easy to get wrong. In a smooth time series, a masked span of a few samples is trivially interpolable from its neighbours, which is exactly the identity-function failure mode: low loss, useless representation. You need spans long enough that interpolation is insufficient, which means the span length has to be set relative to the **autocorrelation length** of the signal, not picked by analogy to a 15-20% image area. Measure the autocorrelation first, then mask well beyond it, then run the context-ablation test to confirm the predictor is actually using context.

### Q14 — Reconcile this: JEPA discards unpredictable detail on purpose, yet I-JEPA reports better depth and counting probes than DINO. Isn't that a contradiction?
**Testing:** whether you understand what "discard" means precisely. This is a genuinely hard question and it separates the top of the pool.
**Answer:** No, because the two methods discard **different** things for **different** reasons. A JEPA discards what is *not predictable from context*: film grain, the exact micro-texture of a surface, the specific realisation of aleatoric noise. It has every incentive to **keep** spatial layout, object extent, depth ordering and motion, because those are exactly what make the masked region predictable. An invariance-based method discards what its **augmentations declare irrelevant**, and random resized crop plus colour jitter explicitly tell the model that position, scale and colour do not matter, which is precisely the information a depth or counting probe needs. So the two are discarding along orthogonal axes: JEPA drops unpredictable *detail*, contrastive drops augmentation-covered *structure*. That is why I-JEPA reports stronger low-level spatial probes while DINO-family methods report stronger semantic classification.
**Follow-up trap:** "Then why not add augmentations to a JEPA to get both?" Because you would be reintroducing exactly the invariance pressure that destroys the spatial information, and you would also be weakening one of the anti-collapse conditions: augmentation-induced invariance makes the target embeddings of different views *more similar*, which moves the system toward the degenerate region. Empirically the JEPA line deliberately uses no colour jitter, blur or solarization. If you need both properties, the right move is two backbones or a multi-task head, not a hybrid objective you have not ablated.

---

## Red flags that fail you

- "JEPA understands the world / has common sense." Undefined and unmeasurable as stated. Replace it with a test protocol or do not say it.
- Claiming the EMA target **provably** prevents collapse. It does not. SimSiam showed stop-gradient alone suffices without a momentum encoder, and LeJEPA (November 2025) exists specifically because the EMA stack is a heuristic.
- Calling an action-free V-JEPA encoder a "world model." Without an action-conditioned predictor there is no `p(s'|s,a)`, so it cannot be rolled forward and cannot support planning. Only V-JEPA 2-AC qualifies.
- Saying "V-JEPA 2 learned to control robots from 62 hours of raw video." The Droid data includes actions and proprioception. It lacks task labels, rewards, and deployment-environment data. Overstating this is a credibility loss you do not recover from.
- Reporting a linear probe as sufficient evidence that a representation is healthy. Partial collapse hides behind classification accuracy.
- Claiming JEPA beats generative models downstream without qualification. I-JEPA is roughly 7 points below DINOv2 on ImageNet linear probe and no JEPA system has displaced a scaled generative model on a general benchmark.
- Dismissing JEPA as "just BYOL with masking." Architecturally adjacent, but the target is a *different part of the signal* rather than an augmented view, which flips the objective from invariance to prediction, and that flip is why it works on motion tasks where BYOL-style methods do not.
- Proposing to widen the predictor "for more capacity." The narrowness is load-bearing.
- Proposing long-horizon open-loop planning in latent space. Compounding error caps this; at 2% per-step divergence the half-life is about 34 steps.
- Confusing I-JEPA's masking with MAE's. Random per-patch masking makes the task solvable by texture continuation.
- Not knowing that the target encoder runs on the **full** image and the targets are sliced out afterwards.
- Treating LeCun's position paper as a validated research programme rather than an explicitly experiment-free proposal with roughly one of six modules demonstrated.

## Cheat card

```
JEPA          predict EMBEDDING of masked target from EMBEDDING of context.
              NO DECODER. Target is LEARNED -> collapse is a global minimum.
ENERGY        E(x,y) = D( Pred(Enc_ctx(x), z), Enc_tgt(y) )  = pred error in
              representation space. Collapse == FLAT energy surface.
4 PARTS       context encoder (SGD) | target encoder (EMA, stop-grad, sees
              FULL image) | narrow predictor (dim 384 vs enc 1280) | L2 loss
EMA           m: 0.996 -> 1.0 LINEAR. window = 1/(1-m) = 250 steps at 0.996.
I-JEPA MASK   4 targets, scale (0.15,0.20), AR (0.75,1.5);
              1 context, scale (0.85,1.00), AR 1.0, MINUS target overlap.
I-JEPA COST   ViT-H/14 < 1200 GPU-h (16 A100 < 72h). 10x cheaper than MAE,
              2.5x faster than iBOT ViT-S/16. IN1k linear ~79% (~81% @448).
V-JEPA (2024) VideoMix2M (2M vids). ViT-H/16 FROZEN: K400 81.9 / SSv2 72.2
              / IN1K 77.9. Mask same spatial region ACROSS ALL FRAMES.
V-JEPA 2      ViT-g 1.2B, VideoMix22M >1M HOURS. SSv2 77.3 top-1,
 (Jun 2025)   EK100 39.7 R@5. +LLM @8B: PerceptionTest 84.0, TempCompass 76.9.
V-JEPA 2-AC   frozen enc + action-cond predictor on <62h unlabelled Droid.
              ZERO-SHOT Franka, 2 unseen labs, image goals, ~65-80% pick&place.
              No reward, no task training, no deployment-env data.
V-JEPA 2.1    Mar 2026, dense features, ~+20pt grasping over V-JEPA 2-AC.
COLLAPSE      per-dim std of L2-normed emb ~ 1/sqrt(D). D=1280 -> 0.028.
 DETECTION    ALERT < 0.3/sqrt(D). RankMe healthy 0.2-0.8 x D; full collapse=1;
              PARTIAL collapse 20-60 (loss + linear probe still look FINE).
              cos-sim p95 > 0.95 = collapsed. ALWAYS add a DETAIL probe.
RIVALS        MAE: 75% mask, pixels, ViT-H FT 87.8, ViT-L linear 75.8.
              SimCLR: batch 4096, T=0.1, RN50 69.3. DINO ViT-B/8 80.1 linear.
              DINOv2 ViT-g/14 1.1B, LVD-142M, ~86.5 linear  <- BEATS I-JEPA.
JEPA WINS     motion (SSv2), low-level spatial (depth/counting), compute,
              no augmentations. LOSES: semantic classification, inspectability.
LeJEPA        arXiv 2511.08544, Nov 2025, Balestriero+LeCun. Isotropic Gaussian
              provably optimal. SIGReg: random 1D projections + char.-function
              matching, LINEAR cost, ~1 hyperparameter. Calls EMA "heuristics".
POSITION PAPR "A Path Towards AMI" v0.9.2, 27 Jun 2022. NO experiments.
              6 modules: configurator/perception/world model/cost/memory/actor.
              H-JEPA (hierarchy) = the key claim, STILL UNDEMONSTRATED at scale.
HORIZON CAP   H_1/2 ~ 0.693/eps. eps=2% -> ~34 steps. Replan every step.
```

## Sources

- [A Path Towards Autonomous Machine Intelligence, version 0.9.2 (LeCun, 27 June 2022)](https://openreview.net/pdf?id=BZ5a1r-kVsf) — accessed 2026-08-05
- [Self-Supervised Learning from Images with a Joint-Embedding Predictive Architecture (I-JEPA, Assran et al., arXiv 2301.08243, CVPR 2023)](https://arxiv.org/abs/2301.08243) — accessed 2026-08-05
- [I-JEPA: The first AI model based on Yann LeCun's vision for more human-like AI (Meta AI blog)](https://ai.meta.com/blog/yann-lecun-ai-model-i-jepa/) — accessed 2026-08-05
- [Revisiting Feature Prediction for Learning Visual Representations from Video (V-JEPA, Bardes et al., arXiv 2404.08471, February 2024)](https://arxiv.org/abs/2404.08471) — accessed 2026-08-05
- [V-JEPA 2: Self-Supervised Video Models Enable Understanding, Prediction and Planning (Assran et al., arXiv 2506.09985, 11 June 2025)](https://arxiv.org/abs/2506.09985) — accessed 2026-08-05
- [Introducing the V-JEPA 2 world model and new benchmarks for physical reasoning (Meta AI blog, June 2025)](https://ai.meta.com/blog/v-jepa-2-world-model-benchmarks/) — accessed 2026-08-05
- [facebookresearch/vjepa2 — PyTorch code and model weights](https://github.com/facebookresearch/vjepa2) — accessed 2026-08-05
- [V-JEPA 2.1: Unlocking Dense Features in Video Self-Supervised Learning (arXiv 2603.14482, March 2026)](https://arxiv.org/html/2603.14482v1) — accessed 2026-08-05
- [LeJEPA: Provable and Scalable Self-Supervised Learning Without the Heuristics (Balestriero and LeCun, arXiv 2511.08544, 11 November 2025)](https://huggingface.co/papers/2511.08544) — accessed 2026-08-05
- [rbalestr-lab/lejepa — reference implementation of SIGReg](https://github.com/rbalestr-lab/lejepa) — accessed 2026-08-05
- [Masked Autoencoders Are Scalable Vision Learners (He et al., arXiv 2111.06377, CVPR 2022)](https://arxiv.org/abs/2111.06377) — accessed 2026-08-05
- [Emerging Properties in Self-Supervised Vision Transformers (DINO, Caron et al., arXiv 2104.14294, ICCV 2021)](https://arxiv.org/abs/2104.14294) — accessed 2026-08-05
- [DINOv2: Learning Robust Visual Features without Supervision (Oquab et al., arXiv 2304.07193, 2023)](https://arxiv.org/abs/2304.07193) — accessed 2026-08-05
- [Exploring Simple Siamese Representation Learning (SimSiam, Chen and He, arXiv 2011.10566, CVPR 2021)](https://arxiv.org/abs/2011.10566) — accessed 2026-08-05
- [Bootstrap Your Own Latent (BYOL, Grill et al., arXiv 2006.07733, NeurIPS 2020)](https://arxiv.org/abs/2006.07733) — accessed 2026-08-05
- [RankMe: Assessing the Downstream Performance of Pretrained Self-Supervised Representations by Their Rank (Garrido et al., arXiv 2210.02885)](https://arxiv.org/abs/2210.02885) — accessed 2026-08-05
- [Introduction to Latent Variable Energy-Based Models: A Path Towards Autonomous Machine Intelligence (arXiv 2306.02572)](https://arxiv.org/abs/2306.02572) — accessed 2026-08-05

## Changelog
- 2026-08-05 — created


---
