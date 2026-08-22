# Pre/Post-Norm, RMSNorm, SwiGLU, MoE Routing

> **Track:** T05 LLM Internals · **Time:** 2h · **Prereqs:** T05-attention, T05-positional
> **Module id:** `T05-architecture-blocks` · **Tags:** internals

## The 30-second version

Every production transformer block today is Pre-Norm, RMSNorm, SwiGLU, and — above a certain scale — sparse MoE instead of one dense FFN, and each of those four choices displaced an earlier default for a specific, nameable failure. Post-Norm (the original 2017 design) normalizes *after* the residual add, which means gradients get multiplied through a LayerNorm Jacobian at every layer on the way back to the input, decaying with depth and forcing a careful learning-rate warmup; Pre-Norm normalizes *before* the sublayer, giving the residual stream an unobstructed identity path for gradients and making deep models trainable with little or no warmup. RMSNorm strips out LayerNorm's mean-centering step, keeping only the rescaling that actually mattered, for a 7-64% speedup with no measured quality loss. SwiGLU replaces the plain ReLU/GELU feed-forward block with a gated variant — one projection gates another element-wise — which consistently lowers perplexity at equal parameter count, at the cost of a third weight matrix that the hidden dimension is shrunk to compensate for. MoE routing swaps a single dense FFN for many small expert FFNs plus a learned router that sends each token to a handful of them, and the entire practical difficulty is keeping load balanced across experts without letting the balancing mechanism itself fight the language-modeling objective — which is exactly the problem DeepSeek's auxiliary-loss-free routing was built to solve.

## Why this gets asked

Because these four choices are exactly the difference between a from-scratch nanoGPT-style implementation and what Llama, Qwen, or DeepSeek actually ship, and an interviewer who has trained anything past toy scale has personally watched a Post-Norm model spike or diverge, watched a dense FFN's parameter count balloon past what MoE would cost for the same quality, or watched an MoE run collapse to using 4 of its 64 experts because nobody was watching the load-balancing loss. They want to know you can explain *why* each default changed, not just name the current one.

## Lineage: past → present → future

**What came before.** The original Transformer (Vaswani et al., 2017) used Post-Norm: `LayerNorm(x + Sublayer(x))`. Feed-forward blocks used two dense matrices with a ReLU (later GELU) in between, and there was no sparsity — every token touched every parameter. This worked at the depths people trained in 2017-2018 (6-24 layers), but as models grew deeper (GPT-2/3-scale, 24-96+ layers), Post-Norm's gradient behavior became the actual blocker: Xiong et al. (2020, "On Layer Normalization in the Transformer Architecture") showed analytically that Post-Norm's expected gradient magnitude near the output is large while gradients near the input are comparatively suppressed, because every backward pass through a residual+norm block multiplies by a LayerNorm Jacobian — the pain was concretely a *training instability requiring a fragile, hand-tuned warmup schedule*, and without enough warmup, deep Post-Norm models would diverge early in training.

**Where it stands now.** Pre-Norm (`x + Sublayer(LayerNorm(x))`) is the default in essentially every model trained since GPT-2/GPT-3: it gives the residual stream a clean additive (identity) gradient path, since the norm only touches the branch going into the sublayer, not the skip connection itself — this is why deep Pre-Norm models train with much shorter warmup and higher learning rates than Post-Norm ever tolerated. The known cost, acknowledged but generally accepted, is that Pre-Norm models can suffer a mild "representation collapse" — unnormalized residual-stream variance grows across depth, so later layers contribute proportionally less to the final representation than they would in a well-conditioned Post-Norm model, an effect DeepNorm (Microsoft, 2022) specifically targeted by combining Post-Norm-style placement with a scaled residual and careful initialization to reach 1000+ layers. RMSNorm (Zhang & Sennrich, 2019) is now standard across Llama, Mistral, Gemma, Qwen, and most open weights — the ablation that mean-centering (re-centering invariance) wasn't actually doing the useful work in LayerNorm, only the rescaling was, held up empirically and nobody has walked it back. SwiGLU (Shazeer, "GLU Variants Improve Transformer," 2020) is likewise close to universal in the FFN block of frontier open models (PaLM, LLaMA family). MoE is the one axis still actively contested: DeepSeek-V3, Mixtral, Qwen's MoE variants, and GPT-OSS all ship sparse MoE FFNs at scale, but dense models remain competitive and simpler to serve — the live disagreement is whether MoE's training/serving complexity (routing collapse risk, load imbalance, harder quantization, all-to-all communication cost across devices) is worth its FLOP-per-parameter efficiency for a given deployment's actual traffic pattern.

**Where it's heading.** With reasonable confidence: fine-grained MoE (many small experts, DeepSeek-style, versus few large experts, Mixtral-style) plus a shared always-on expert is the direction serious labs are converging toward, because it captures both common-knowledge sharing and specialization without needing an auxiliary loss that fights the primary objective. Auxiliary-loss-free load balancing (bias-based, DeepSeek-V3 style) is displacing the classic Switch-Transformer auxiliary loss as of 2024-2026 releases; expect this to keep spreading. More speculative: exactly how normalization placement interacts with extremely deep (hundreds of layers) or extremely wide MoE models is still being worked out — treat claims that any one norm-placement scheme is "solved" for arbitrary depth as unverified until you've seen the specific paper's depth regime.

---

## Mental model

```
POST-NORM (2017)                    PRE-NORM (2019-present)

x ──┬────────────► Sublayer         x ──┬──► LayerNorm ──► Sublayer
    │                  │                │                     │
    └──────(+)◄────────┘                └────────(+)◄─────────┘
          │                                      │
       LayerNorm                                 x_out
          │
        x_out

Backward pass must go THROUGH        Backward pass has an unobstructed
a LayerNorm Jacobian at every        additive identity path straight
layer to reach earlier layers --     through every residual connection
gradient shrinks with depth          -- gradient magnitude preserved
```

FFN gating (SwiGLU): think of it as one projection deciding *how much* of another projection's content to let through, per-dimension — a learned, continuous, per-feature gate rather than a fixed nonlinearity applied uniformly.

MoE: a token arrives at a router (a small linear layer), the router scores every expert, the top-k highest-scoring experts process the token, and everyone else's weights are never touched for that token — capacity, not depth, is being made conditional on the input.

---

## How it actually works

### Post-Norm vs Pre-Norm, mechanically

Post-Norm: `y = LayerNorm(x + Sublayer(x))`. Backpropagating through `L` stacked blocks, the gradient at layer `1` has passed through `L` LayerNorm Jacobians (each one bounded by the normalization's local scaling), and Xiong et al. showed the expected gradient norm at the top of a Post-Norm stack grows large relative to the bottom — practically, the last layers get large, aggressive updates early in training while the first layers barely move, until a warmup schedule (small learning rate ramped up over the first few thousand steps) prevents that imbalance from blowing up the loss.

Pre-Norm: `y = x + Sublayer(LayerNorm(x))`. The residual/skip term `x` is untouched by any normalization on the way through — the gradient of the loss with respect to an early layer's output includes a direct additive term (`dL/dx` flows straight through the `+`) on top of whatever the sublayer branch contributes. This means gradient magnitude doesn't systematically decay with depth, warmup can be shorter (or in some recipes, skipped), and learning rates can be pushed higher — this is the concrete, derivable reason Pre-Norm displaced Post-Norm as models scaled past a few dozen layers.

**The cost nobody skips mentioning at staff level:** because the residual stream in Pre-Norm is never renormalized on the skip path itself, its variance can grow roughly with depth (each sublayer adds its output on top of an ever-growing running sum), and empirically deeper Pre-Norm layers end up contributing proportionally less new information relative to the accumulated residual — sometimes described as "effective depth" being shallower than nominal depth. DeepNorm (Wang et al., 2022) addresses this directly by scaling the residual connection (`x*alpha + Sublayer(x)` with `alpha > 1` computed as a function of total depth) combined with a scaled-down initialization, reporting stable training to 1000 layers — but it's still Post-Norm-*flavored* placement with the scaling fix, not plain Pre-Norm, and it hasn't become the default outside of a few very-deep-model demonstrations.

### RMSNorm, derived

LayerNorm: `LN(x) = g * (x - mean(x)) / sqrt(var(x) + eps) + b` — subtracts the mean (re-centers), divides by standard deviation (re-scales), then applies a learned affine transform.

RMSNorm (Zhang & Sennrich, 2019) keeps only the rescaling:

$$\text{RMSNorm}(x) = g \odot \frac{x}{\sqrt{\frac{1}{d}\sum_{i=1}^d x_i^2 + \epsilon}}$$

The hypothesis the paper tests directly: LayerNorm's benefit comes from **re-scaling invariance** (the output doesn't change if you scale the input by a constant), not from **re-centering invariance** (subtracting the mean). Ablating mean-subtraction and keeping only the RMS-based rescale produced comparable-or-better quality across the tasks tested, while removing an entire reduction (the mean) from both forward and backward passes. Measured savings: **7-64% faster** depending on task/hardware, with roughly 20.5% training-time savings reported on a CIFAR-10 image classification benchmark used in the original paper's ablations ([Root Mean Square Layer Normalization, arXiv:1910.07467](https://arxiv.org/abs/1910.07467), accessed 2026-07-27). No learned bias term `b` either — just the single learned per-feature gain `g`, further cutting parameters (a rounding error at model scale, but one less thing to initialize and store).

```python
import numpy as np

def rmsnorm(x, gain, eps=1e-6):
    """x: (..., d). gain: (d,) learned scale, no bias, no mean subtraction."""
    rms = np.sqrt(np.mean(x ** 2, axis=-1, keepdims=True) + eps)
    return gain * (x / rms)
```

### SwiGLU, derived

A standard transformer FFN: `FFN(x) = W2 * activation(W1 * x)`, historically ReLU or GELU, with hidden dimension `d_ff` conventionally `4 * d_model`.

Gated Linear Units replace a single activated projection with **two** projections, one of which gates the other element-wise: `GLU(x) = activation(xW) ⊙ (xV)`. Shazeer's 2020 sweep tried several activation choices in this gated form — ReGLU (ReLU), GEGLU (GELU), SwiGLU (Swish/SiLU) — and found GEGLU and SwiGLU gave the best perplexity at equal parameter count against a plain (ungated) FFN baseline ([GLU Variants Improve Transformer, arXiv:2002.05202](https://arxiv.org/pdf/2002.05202), accessed 2026-07-27).

$$\text{SwiGLU}(x) = \big(\text{Swish}_\beta(xW_1) \odot (xW_3)\big) W_2, \quad \text{Swish}_\beta(z) = z \cdot \sigma(\beta z)$$

(`beta=1` recovers SiLU exactly; most implementations fix `beta=1` and just call it SiLU-gated.)

**Why the hidden dimension shrinks.** A gated FFN needs *three* weight matrices (`W1`, `W2`, `W3`) instead of a plain FFN's two, so at the same `d_ff = 4*d_model` a gated FFN would have 50% more FFN parameters than the ungated baseline — an unfair comparison for any ablation claiming "better at equal parameter count." The fix, used by essentially every production implementation (Llama et al.), is to shrink `d_ff` to roughly `(2/3) * 4 * d_model = 8/3 * d_model`, then round to a hardware-friendly multiple (commonly a multiple of 256 or matched to tensor-parallel shard size). This keeps total FFN parameter count roughly matched to the ungated-4d baseline while switching to the gated formulation — the parameter-matched comparison is exactly what makes SwiGLU's quality gain a real gain and not just "more parameters."

```python
def swiglu_ffn(x, W1, W3, W2):
    """x: (n, d_model). W1,W3: (d_model, d_ff). W2: (d_ff, d_model). d_ff ~ 8/3 * d_model."""
    gate = x @ W1
    swish = gate * (1.0 / (1.0 + np.exp(-gate)))   # beta=1 Swish == SiLU
    value = x @ W3
    return (swish * value) @ W2
```

### MoE routing, load balancing, and capacity factor

A dense FFN activates all its parameters for every token. Sparse MoE replaces the single FFN with `N` expert FFNs (each usually smaller than the dense equivalent) plus a router: a small linear layer producing a score per expert, top-`k` of which are selected per token (`k=1`: Switch Transformer; `k=2`: Mixtral/GShard-style; `k=8` across many small fine-grained experts: DeepSeek-V3).

**Why load balancing is the whole problem.** Nothing in a naive top-k router prevents it from collapsing onto a handful of favorite experts early in training — once an expert gets slightly more traffic, it gets more gradient signal, gets better at whatever it's seeing, and attracts even more traffic, a rich-get-richer dynamic. Left unchecked this wastes most of the model's parameter budget (unused experts never improve) and overloads the popular ones past their capacity.

**Capacity factor.** Each expert is given a fixed processing capacity per batch: `capacity = capacity_factor * (tokens_per_batch / num_experts)`. A `capacity_factor` of 1.0 means an expert can hold exactly its "fair share" if routing were perfectly uniform; values of 1.25-2.0 are typical in GShard/Switch-style setups to leave slack for imperfect balance. Tokens routed to an expert that's already at capacity are **dropped** — in Switch Transformer, a dropped token is passed through via the residual connection with no expert computation applied (effectively an identity/no-op for that token at that layer), which is a real, measurable quality cost, not a rare edge case at high load imbalance.

**Auxiliary load-balancing loss (Switch Transformer / GShard formulation):**

$$L_{\text{aux}} = \alpha \cdot N \cdot \sum_{i=1}^{N} f_i \cdot P_i$$

where `f_i` is the fraction of tokens actually routed to expert `i` in the batch and `P_i` is the router's average softmax probability assigned to expert `i` — this loss is minimized when routing is uniform across experts (both `f_i` and `P_i` near `1/N` for all `i`), and it's added to the language-modeling loss with a small weight `alpha` (commonly ~0.01). The practical failure mode: set `alpha` too high and the model spends capacity chasing artificial uniformity instead of language modeling quality; set it too low and routing collapses anyway.

**DeepSeek-V3's auxiliary-loss-free alternative.** Rather than fighting the primary loss with an auxiliary term, DeepSeek-V3 adds a per-expert **bias** to the routing score used for top-k selection (not to the probability used for weighting, just for the selection decision), and after each training step nudges that bias up for underloaded experts and down for overloaded ones by a small fixed step `gamma` — a direct, loss-free control loop rather than a competing gradient signal ([DeepSeek-V3 Technical Report analysis](https://vitalab.github.io/article/2025/02/11/DeepSeekV3.html), accessed 2026-07-27; [A Theoretical Framework for Auxiliary-Loss-Free Load Balancing, arXiv:2512.03915](https://arxiv.org/abs/2512.03915), accessed 2026-07-27). DeepSeek-V3 ships this alongside **256 fine-grained routed experts plus 1 always-on shared expert**, selecting top-8 routed experts per token — the shared expert absorbs common cross-token knowledge so the routed experts don't each have to re-learn it, reducing redundancy across the routed pool ([Beyond Vanilla MoE, Chris Hughes](https://medium.com/@chris.p.hughes10/beyond-vanilla-moe-fine-grained-experts-shared-experts-and-modern-architectural-innovations-f89dd62e433b), accessed 2026-07-27).

```python
# untested sketch -- illustrates top-k routing + capacity-based token dropping
def moe_forward(x, router_W, expert_fns, k, capacity_factor):
    n_tokens, n_experts = x.shape[0], router_W.shape[1]
    logits = x @ router_W                                  # (n_tokens, n_experts)
    topk_idx = np.argsort(-logits, axis=-1)[:, :k]           # top-k expert indices per token
    topk_w = softmax_over_selected(logits, topk_idx)         # normalize weights over the k chosen

    capacity = int(capacity_factor * n_tokens / n_experts)
    expert_load = np.zeros(n_experts, dtype=int)
    out = np.zeros_like(x)
    for t in range(n_tokens):
        for e, w in zip(topk_idx[t], topk_w[t]):
            if expert_load[e] >= capacity:
                continue   # token dropped for this expert -- no contribution, quality cost
            expert_load[e] += 1
            out[t] += w * expert_fns[e](x[t])
    return out
```

---

## Build it from scratch

A minimal transformer block showing the Pre-Norm + RMSNorm + SwiGLU combination end to end (attention omitted, assume `attn_fn` from `T05-attention`):

```python
def transformer_block(x, attn_fn, ffn_W1, ffn_W3, ffn_W2, norm1_gain, norm2_gain):
    """Pre-Norm block: normalize INTO each sublayer, add the raw (un-normalized) result back."""
    x = x + attn_fn(rmsnorm(x, norm1_gain))       # attention sublayer, pre-normed
    x = x + swiglu_ffn(rmsnorm(x, norm2_gain), ffn_W1, ffn_W3, ffn_W2)   # FFN sublayer, pre-normed
    return x
```

Full from-scratch Pre-Norm-vs-Post-Norm training-stability comparison (loss curves at increasing depth, with and without warmup) plus a toy 4-expert MoE layer with visualized routing collapse: **`labs/py/05-architecture-blocks/`** (create if not present).

---

## How it's done in production

| Layer | What you actually use | What it adds |
|---|---|---|
| Norm placement | Pre-Norm in essentially every model trained since GPT-2/GPT-3; some labs add a final extra norm before the output head (final LayerNorm/RMSNorm) | Stable deep training with short/no warmup; the final norm keeps the ever-growing residual stream bounded before the unembedding |
| Norm type | RMSNorm (Llama, Mistral, Gemma, Qwen, DeepSeek) | 7-64% faster than LayerNorm, no measured quality cost |
| FFN | SwiGLU with `d_ff ~ 8/3 * d_model`, rounded to a hardware-friendly multiple | Lower perplexity at matched parameter count vs plain ReLU/GELU FFN |
| Sparse scaling | MoE (Mixtral, DeepSeek-V3, Qwen-MoE, GPT-OSS) with a shared expert + fine-grained routed experts, auxiliary-loss-free balancing (DeepSeek-style) or auxiliary loss (Switch/GShard-style) | Far more total parameters than active-per-token compute, at the cost of routing complexity and harder distributed serving |

### Failure modes

| Symptom | Cause | Fix |
|---|---|---|
| Loss spikes or diverges early in training, especially at higher learning rates or greater depth | Post-Norm gradient decay/instability without sufficient warmup | Switch to Pre-Norm, or if Post-Norm is required for a specific reason, lengthen warmup and lower peak LR substantially |
| Deeper layers appear to contribute little (ablating them barely changes output; representation similarity across late layers is high) | Pre-Norm residual-stream variance growth ("effective depth" collapse) | Consider DeepNorm-style residual scaling for very deep models, or accept the tradeoff and add depth-appropriate final normalization |
| MoE training shows most tokens routed to a small subset of experts within the first few thousand steps | Router collapse from rich-get-richer dynamics, no or too-weak load balancing | Add/strengthen the auxiliary load-balancing loss, or switch to bias-based auxiliary-loss-free balancing; check expert utilization histograms during training, not just after |
| MoE inference quality degrades under bursty/skewed traffic despite fine during training | Capacity factor sized for training-time batch statistics, tokens dropped at serving-time load spikes | Size capacity factor (or remove hard capacity at serving time if infra allows) against real production traffic distribution, not just training batch shape |
| Auxiliary load-balancing loss weight tuned too high | Model chases uniform routing at the expense of language-modeling quality, visible as high `L_aux` improvement but stalled/worse primary loss | Lower `alpha`, or move to auxiliary-loss-free (bias-based) balancing so the LM objective isn't directly fighting a balancing term |

---

## Tradeoffs & when NOT to use it

- **Post-Norm is not simply obsolete.** For shallow models (a handful of layers) or specific regimes where its slightly better final-layer conditioning matters and warmup cost is a non-issue, it remains a legitimate choice — the tradeoff is training fragility at depth, not universal inferiority.
- **RMSNorm's dropped re-centering invariance is a real, if usually harmless, simplification.** In architectures or data regimes where input mean shift genuinely carries signal (uncommon in standard token-embedding-based LLMs, but worth checking for unusual modalities), skipping mean subtraction could matter — validate rather than assume for anything outside the standard text-LLM setting.
- **SwiGLU is not free — it costs a third weight matrix.** The parameter-matching trick (shrinking `d_ff` to `8/3 * d_model`) compensates on paper, but at very small model scales the extra matrix multiply and non-power-of-2 hidden dimension can be a real implementation/kernel-efficiency annoyance not worth the perplexity gain.
- **MoE is the wrong choice below a certain scale or traffic pattern.** It buys more total capacity per unit of active compute, but costs router complexity, load-balancing tuning, harder quantization (per-expert calibration), and expensive all-to-all communication in distributed training/serving. For a workload that doesn't need frontier-scale capacity, a dense model is simpler to train, serve, and debug — MoE's win is specifically at the scale where dense parameter growth becomes compute-prohibitive, not a universal efficiency upgrade.
- **Auxiliary-loss-free balancing is not obviously superior in every regime.** It removes the "fighting the LM loss" problem but introduces its own hyperparameter (the bias step size `gamma`) and is newer with less multi-year production track record than the Switch-style auxiliary loss; teams without DeepSeek's specific validation should treat it as a serious option, not an unconditional default, until they've measured it on their own setup.

---

## Interview questions

### Q1 — Write out Post-Norm and Pre-Norm block equations and explain the gradient-flow difference.
**Testing:** baseline fluency plus whether you actually understand *why*, not just which is "modern."
**Answer:** Post-Norm: `y = LayerNorm(x + Sublayer(x))`. Pre-Norm: `y = x + Sublayer(LayerNorm(x))`. In Post-Norm, the gradient flowing back to `x` must pass through the LayerNorm applied to the *sum*, meaning every layer's backward pass includes a LayerNorm Jacobian multiplication; stacked over many layers this compounds and, per Xiong et al.'s analysis, produces large gradients near the output and comparatively suppressed ones near the input. In Pre-Norm, the skip connection `x` is added *after* the sublayer, untouched by any normalization on that path, giving an unobstructed additive gradient route straight back through every layer.
**Follow-up trap:** *"If Pre-Norm's gradient flow is strictly better, why does anyone still use Post-Norm?"* — it isn't strictly better in every respect: Pre-Norm's unbounded residual-stream growth across depth causes a different, real problem (representation/effective-depth collapse) that Post-Norm doesn't have in the same way; Post-Norm is simply harder to train stably at depth without careful warmup, which is the specific pain that made Pre-Norm the practical default.

### Q2 — Derive, don't just assert, why Post-Norm needs a longer/more careful warmup than Pre-Norm.
**Answer:** In Post-Norm, backpropagating through `L` residual+norm blocks means the gradient at the bottom layer has been multiplied by `L` LayerNorm Jacobians on the way down; the expected magnitude of that product is not depth-invariant, and empirically grows large near the output while remaining comparatively small near input layers early in training, before the norm statistics have stabilized. A large learning rate applied to that unevenly-scaled gradient at the start of training causes the top layers to take oversized steps, destabilizing training; warmup avoids this by keeping the learning rate small until the norm statistics and gradient scales settle into a more even, trainable regime.
**Follow-up trap:** *"Does Pre-Norm need zero warmup then?"* — no, some warmup is still commonly used for optimizer stability reasons unrelated to the norm-placement gradient issue (e.g. Adam's second-moment estimate needs a few steps to become reliable); the *specific* norm-placement-driven instability that forced long, carefully-tuned Post-Norm warmup schedules is what Pre-Norm removes, not the general practice of warmup itself.

### Q3 — What does RMSNorm give up relative to LayerNorm, and why doesn't it matter in practice?
**Answer:** It gives up re-centering invariance — RMSNorm doesn't subtract the mean, so its output changes if you add a constant shift to the input, whereas LayerNorm's output is invariant to that shift. Zhang & Sennrich's ablation showed empirically that re-scaling invariance (the property RMSNorm keeps) was doing the useful work, not re-centering, so dropping mean-subtraction cost no measured quality while removing a full reduction operation from forward and backward passes, for a 7-64% speedup.
**Follow-up trap:** *"Is there any regime where dropping re-centering invariance would actually hurt?"* — plausibly, if a model's activations have a meaningful, information-carrying mean shift that the mean-subtraction step was actively using — this hasn't been shown to matter for standard text-LLM token embeddings, but it's a real, not-fully-closed question for architectures/modalities where activation statistics look different.

### Q4 — Derive why SwiGLU's hidden dimension is shrunk to roughly 8/3 * d_model instead of the standard 4 * d_model.
**Answer:** A gated FFN needs three weight matrices (gate projection, value projection, output projection) versus a plain FFN's two (up-projection, output projection). At the same hidden width, that's 50% more FFN parameters, which would make any "SwiGLU is better" comparison confounded by extra capacity rather than a genuine gain from gating. Shrinking `d_ff` from `4*d_model` to `(2/3)*4*d_model = 8/3*d_model` keeps total FFN parameter count roughly matched to the ungated baseline while switching to the gated form, isolating the actual effect of gating.
**Follow-up trap:** *"Why not just keep d_ff at 4x and accept the extra 50% parameters if it's better anyway?"* — that's a legitimate design choice too (more parameters, if you can afford them, often just help), but then you can't attribute the quality gain to gating specifically versus simply having more capacity — the parameter-matched comparison is what makes SwiGLU's reported gain scientifically meaningful, and it's also what most production implementations do since parameter budget is usually the actual constraint.

### Q5 — Explain top-k MoE routing and the capacity factor, with the specific failure mode when capacity is exceeded.
**Answer:** A router (small linear layer) scores every expert per token; the top-`k` highest-scoring experts process that token, weighted by (normalized) router scores. Each expert has a fixed capacity per batch: `capacity_factor * tokens_per_batch / num_experts`. When an expert already at capacity receives another routed token, that token is dropped for that expert — in the Switch Transformer formulation, the dropped token passes through via the residual connection with no expert computation applied, a real quality loss for that token at that layer, not a benign no-op.
**Follow-up trap:** *"How would you detect this happening in a live training run without staring at every token?"* — track the token-drop rate (fraction of routed-but-not-processed tokens) per layer as a training metric alongside the loss; a rising drop rate is a direct, cheap-to-log signal of load imbalance getting worse, well before it shows up as a perplexity regression.

### Q6 — Compare the Switch Transformer/GShard auxiliary loss with DeepSeek-V3's auxiliary-loss-free balancing.
**Answer:** The classic auxiliary loss `L_aux = alpha * N * sum_i(f_i * P_i)` is added directly to the LM loss and is minimized at uniform routing, meaning it's a competing gradient signal — a poorly tuned `alpha` trades LM quality for balance or vice versa. DeepSeek-V3 instead adds a per-expert bias term to the routing *selection* score (not the weighting probability), adjusting it up for underloaded and down for overloaded experts by a fixed step each training step — a control-loop mechanism that never enters the loss the model is trained on, so it doesn't compete with the LM objective at all.
**Follow-up trap:** *"So is auxiliary-loss-free strictly better?"* — it removes one failure mode (a mistuned alpha hurting LM quality) but introduces its own hyperparameter (the bias step size) and has a shorter production track record than the auxiliary-loss approach; treat it as a strong, newer option to validate on your own setup rather than an unconditionally superior default.

### Q7 — What does DeepSeek-V3's shared expert do, and why have it alongside 256 routed experts?
**Answer:** The shared expert processes every token regardless of routing decisions, absorbing knowledge that's broadly useful across most inputs so the 256 routed, fine-grained experts don't each have to redundantly re-learn common patterns — this reduces knowledge duplication across the routed pool and lets routed experts specialize more cleanly on what's actually input-dependent.
**Follow-up trap:** *"Doesn't an always-on shared expert defeat some of the point of sparsity?"* — it adds a small, fixed amount of always-active compute (one expert's worth) in exchange for removing redundancy from a much larger routed pool (256 experts); the net active-parameter count is still far below the model's total parameter count, so sparsity's compute benefit is preserved at the aggregate level even though it's no longer 100% conditional.

### Q8 — A team observes their MoE model has "dead experts" that never get selected. Diagnose and fix.
**Answer:** Classic router collapse — early random advantage compounds because a slightly-favored expert gets more gradient signal, becomes marginally better, and attracts even more routing, starving the rest. Diagnose via per-expert utilization histograms logged from early training, not just final checkpoints. Fix by adding or strengthening load-balancing (auxiliary loss with an appropriately tuned `alpha`, or switching to bias-based auxiliary-loss-free balancing), and check that the router's initialization isn't itself skewed.
**Follow-up trap:** *"Would simply increasing the capacity factor fix dead experts?"* — no, capacity factor controls how many tokens an *already-selected* expert can process before dropping overflow; it does nothing to fix a router that isn't selecting an expert in the first place. That's purely a load-balancing-mechanism problem, not a capacity problem.

### Q9 — Why is Pre-Norm's residual-stream variance growth actually a problem, mechanically, and what does DeepNorm do about it?
**Answer:** In Pre-Norm, the skip path accumulates each sublayer's raw (un-normalized) output on top of the running residual stream; since nothing renormalizes that running sum, its variance tends to grow with depth, and later layers' relative contribution (their output divided by the accumulated stream magnitude) shrinks — this is the mechanism behind the observed "later layers behave like near-identity functions" effect in very deep Pre-Norm stacks. DeepNorm addresses it by scaling the residual branch by a depth-dependent factor `alpha > 1` and using a correspondingly scaled-down initialization, reporting stable training to 1000+ layers.
**Follow-up trap:** *"If DeepNorm solves this, why isn't it the universal default?"* — most production models don't operate anywhere near the depth regime (hundreds to a thousand layers) where this effect is severe enough to matter more than the simplicity of plain Pre-Norm plus a final norm; DeepNorm is a targeted fix for a specific, extreme-depth problem, not a strictly-dominant general replacement.

### Q10 — Design the block architecture for a new 40B-parameter model where compute budget is your primary constraint. Dense or MoE, and what norm/FFN choices?
**Testing:** synthesis, staff/principal level.
**Answer:** If the constraint is active compute per forward pass rather than total parameter count, MoE is likely the right call: a sparse model can pack far more total capacity into the same active-FLOP budget (e.g. a 40B-active/200B+-total MoE can outperform a 40B dense model at the same inference compute). Use fine-grained routed experts plus one shared expert (DeepSeek-style) with auxiliary-loss-free bias-based balancing to avoid tuning an auxiliary-loss weight that fights the LM objective, Pre-Norm with RMSNorm for training stability at whatever depth you're targeting, and SwiGLU FFNs (parameter-matched hidden dim) inside each expert. The real cost you're accepting is routing/serving complexity — all-to-all communication for distributed MoE training, harder per-expert quantization — which has to be weighed against your actual serving infrastructure's ability to handle it.
**Follow-up trap:** *"What if your serving infrastructure can't efficiently do distributed MoE inference?"* — then the "compute-optimal" architecture on paper isn't the right choice in practice; a dense model sized to your actual serving constraints, even if less FLOP-efficient in the abstract, may ship a better real product than an MoE model your infrastructure can't serve efficiently — architecture decisions are constrained by the whole system, not just the training-compute tradeoff curve.

### Q11 — Someone claims "RMSNorm is just a faster LayerNorm with no tradeoffs, always use it." Push back.
**Answer:** The speed claim is well-supported (7-64% faster, no measured quality regression in the original ablations across the tasks tested). But "no tradeoffs" overstates it: RMSNorm gives up re-centering invariance, and while that hasn't mattered in the standard text-LLM setting it's been validated in, "always" is a claim about every architecture and modality, which hasn't been separately verified for every case — a careful engineer states the empirical result's actual scope rather than generalizing it unconditionally.
**Follow-up trap:** *"Give a concrete case where you'd want to re-verify rather than assume RMSNorm is fine."* — any architecture where activation mean carries meaningful signal that re-centering was actively using — plausible in some non-standard modalities or heavily quantized regimes where mean shift interacts with quantization error — worth a quick ablation before assuming the standard-LLM result transfers.

---

## Red flags that fail you

- Saying "Pre-Norm is strictly better than Post-Norm" without naming the residual-variance-growth tradeoff Pre-Norm accepts.
- Describing RMSNorm as "LayerNorm without the bias term" — the actual change is dropping mean-centering, not the affine bias.
- Explaining SwiGLU without mentioning the third weight matrix or the hidden-dimension shrink needed for a fair parameter-matched comparison.
- Confusing capacity factor (a per-expert token-processing budget) with top-k (how many experts a token is routed to) — these are independent knobs.
- Claiming MoE is "always" more efficient than dense — ignoring the routing/serving complexity cost that makes it the wrong choice below a certain scale.
- Not knowing that dropped MoE tokens (over capacity) get a real quality cost (identity/no-op treatment in Switch-style setups), not silent lossless handling.

---

## Cheat card

```
POST-NORM        LN(x + Sublayer(x)) -- grad passes through LN Jacobian every layer, needs warmup
PRE-NORM         x + Sublayer(LN(x)) -- skip path untouched by norm, unobstructed grad flow, less warmup
PRE-NORM COST    residual-stream variance grows w/ depth -> later layers contribute less (DeepNorm fixes)
RMSNORM          x / sqrt(mean(x^2)+eps) * g -- no mean subtraction, no bias; 7-64% faster than LayerNorm
                 gives up re-centering invariance, keeps re-scaling invariance (the part that mattered)
SWIGLU           (Swish_beta(xW1) [dot] xV) W2 -- Swish_beta(z)=z*sigmoid(beta*z), beta=1 = SiLU
                 3 matrices vs FFN's 2 -> shrink d_ff to ~8/3*d_model to param-match plain 4d FFN
MOE ROUTING      router scores N experts, top-k selected per token (k=1 Switch, k=2 Mixtral, k=8 DeepSeek)
CAPACITY FACTOR  capacity = capacity_factor * tokens_per_batch / N; overflow tokens DROPPED (real cost)
AUX LOSS         L_aux = alpha * N * sum_i(f_i * P_i) -- minimized at uniform routing, competes w/ LM loss
LOSS-FREE (DS3)  per-expert bias added to routing SCORE (not weight), nudged +/- gamma per step by load
DEEPSEEK-V3      256 fine-grained routed experts + 1 shared (always-on) expert, top-8 routed per token
NEVER            claim MoE is free efficiency -- routing collapse, capacity drops, all-to-all cost are real
```

## Sources

- [On Layer Normalization in the Transformer Architecture (arXiv:2002.04745)](https://arxiv.org/pdf/2002.04745) — accessed 2026-07-27
- [Why Pre-Norm Became the Default in Transformers](https://medium.com/@ashutoshs81127/why-pre-norm-became-the-default-in-transformers-4229047e2620) — accessed 2026-07-27
- [Root Mean Square Layer Normalization (arXiv:1910.07467)](https://arxiv.org/abs/1910.07467) — accessed 2026-07-27
- [GLU Variants Improve Transformer (arXiv:2002.05202)](https://arxiv.org/pdf/2002.05202) — accessed 2026-07-27
- [DeepSeek-V3 Technical Report analysis](https://vitalab.github.io/article/2025/02/11/DeepSeekV3.html) — accessed 2026-07-27
- [A Theoretical Framework for Auxiliary-Loss-Free Load Balancing (arXiv:2512.03915)](https://arxiv.org/abs/2512.03915) — accessed 2026-07-27
- [Beyond Vanilla MoE: Fine-Grained Experts, Shared Experts, and Modern Architectural Innovations](https://medium.com/@chris.p.hughes10/beyond-vanilla-moe-fine-grained-experts-shared-experts-and-modern-architectural-innovations-f89dd62e433b) — accessed 2026-07-27
- [Demons in the Detail: On Implementing Load Balancing Loss for Training Specialized MoE Models (arXiv:2501.11873)](https://arxiv.org/pdf/2501.11873) — accessed 2026-07-27

## Changelog
- 2026-07-27 — created
