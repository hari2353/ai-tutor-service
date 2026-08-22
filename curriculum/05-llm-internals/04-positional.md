# Positional Encoding: Sinusoidal, RoPE, ALiBi, YaRN

> **Track:** T05 LLM Internals · **Time:** 2h · **Prereqs:** T05-attention
> **Module id:** `T05-positional` · **Tags:** internals

## The 30-second version

Attention itself is permutation-invariant — swap two tokens and the dot products don't change — so position has to be injected some other way. Sinusoidal encoding (2017) added fixed sin/cos vectors so each absolute position gets a unique fingerprint the model could in principle learn to use for relative offsets, but it never extrapolated well past training length. RoPE (2021) fixed the actual problem: instead of adding a position vector, it *rotates* each query/key pair by an angle proportional to its position, which makes the attention score a function of relative position `(m-n)` by construction, not by hoping the model learns it — this is why RoPE displaced sinusoidal and learned embeddings almost everywhere from 2022 onward. ALiBi skips rotation entirely and just subtracts a distance penalty from the attention logits, trading a little quality for near-free length extrapolation. When you need a pretrained RoPE model to go past its trained context, you don't retrain from scratch — you stretch the rotation frequencies with YaRN or NTK-aware interpolation, which is now standard practice for every 2025-2026 long-context release (Llama, Qwen, DeepSeek, gpt-oss).

## Why this gets asked

Because "we use RoPE" is table stakes and doesn't demonstrate anything — the interviewer wants to know if you can derive *why* rotation gives relative position for free while additive encodings don't, since that derivation is the actual reason RoPE won the architecture debate. They've also personally hit the wall where a model trained at 4k context falls apart at 32k, and want to know whether you understand that this is a *frequency* problem (untrained rotation angles at long distances) that YaRN/NTK fixes, not a capacity problem you can just fine-tune away without touching the position math.

## Lineage: past → present → future

**What came before.** Vaswani et al. (2017) used fixed sinusoidal position encodings added to token embeddings at the input, plus a learned absolute-position-embedding variant (BERT, GPT-1/2) that assigns each position index its own trainable vector. Both share the same failure: they encode *absolute* position, and the model has to learn on its own how to derive relative relationships from the difference of two absolute encodings — it usually does, approximately, for positions seen during training, but the learned-embedding variant simply has no vector at all for a position past the training length (there's nothing to look up), and even sinusoidal encodings, though mathematically defined at any position, feed the model activation patterns at long distances that look nothing like anything it saw in training. The pain that killed both: every attempt at longer context meant either retraining from scratch at the new length or watching perplexity explode past the trained window.

**Where it stands now.** RoPE (Su et al., 2021, RoFormer) is the default in essentially every open-weight decoder model shipped 2022-2026 — Llama, Mistral, Qwen, DeepSeek, gpt-oss. It bakes relative position directly into the dot product by rotating Q and K as a function of absolute position, so the score between position `m` and `n` provably depends only on `m-n`. The live disagreement is entirely about *extension*: once you've pretrained at some base context (commonly 4k-32k) and want to serve 128k-2M, do you extend by interpolating the rotation frequencies (Position Interpolation, NTK-aware, YaRN, LongRoPE2), or do you pretrain at long context directly with a large RoPE base `theta` (as Llama 3 and most 2025-2026 frontier models now do, reserving YaRN-style post-hoc extension for pushing further past the pretrained length)? ALiBi remains a minority choice — MosaicML's MPT and BLOOM shipped it — valued for its extrapolation-without-retraining property and slightly cheaper compute, but most labs found RoPE's ceiling on trained-length quality worth the extra extension engineering.

**Where it's heading.** With high confidence: post-hoc frequency-interpolation methods keep improving — LongRoPE2 (2025) reports near-lossless extension to 128k by fixing an evaluation-methodology gap in earlier NTK/YaRN work, and "dropping positional embeddings entirely past a certain layer" (NoPE-style approaches) is an active 2025-2026 research thread showing surprising extrapolation ability in some settings. With lower confidence: whether the field converges on training at native ultra-long context (reducing the need for post-hoc extension altogether, as compute allows) or keeps relying on extension tricks because pretraining at 2M context natively is still compute-prohibitive for most labs. Treat "NoPE will replace RoPE" as speculative — as of mid-2026 it has not displaced RoPE in any frontier general-purpose model.

---

## Mental model

Sinusoidal / learned: position is a *label glued onto* the token, like a sticky note with a timestamp. The model has to read both notes and compute a difference itself.

RoPE: position is a *rotation applied to* the vector itself, like turning a clock hand. Two hands rotated by the same amount relative to each other always show the same angle between them, no matter what absolute time it is — that angle-between-them is exactly what the dot product measures.

```
Sinusoidal (additive):           RoPE (multiplicative / rotational):

token_emb + pos_vector[m]         rotate(q, angle = m * theta)
token_emb + pos_vector[n]         rotate(k, angle = n * theta)

dot product depends on the        dot product of two rotated vectors
sum in a way the model must       depends ONLY on the difference in
learn to disentangle              their rotation angles = (m-n)*theta
                                   -- relative position, by construction
```

ALiBi: no rotation, no added vector — just a fixed penalty subtracted from the raw score proportional to distance, like turning down the volume on anything far away before you even listen to it.

---

## How it actually works

### Sinusoidal, derived from first principles

The requirement: give every position a unique, bounded, deterministic vector such that the *relationship* between two positions is expressible as a simple function (ideally linear) of the vectors themselves, so the model doesn't need a separate lookup table (which wouldn't generalize past training length).

Vaswani et al. use, for dimension pair `2i, 2i+1` of a `d`-dimensional encoding:

```
PE(pos, 2i)   = sin(pos / 10000^(2i/d))
PE(pos, 2i+1) = cos(pos / 10000^(2i/d))
```

Each dimension pair oscillates at a different frequency — low `i` (early dimensions) oscillates fast (short wavelength), high `i` oscillates slowly (long wavelength), giving a spectrum from fine-grained to coarse-grained position information, analogous to binary encoding where low bits flip fast and high bits flip slow. The key algebraic property: `PE(pos+k)` can be written as a **linear transformation** of `PE(pos)` for fixed offset `k`, because `sin(a+b)` and `cos(a+b)` expand via the angle-addition formulas into linear combinations of `sin(a), cos(a)`. This is the intended mechanism for relative-position generalization — but critically, it requires the model to *learn* to exploit that linear relationship from the additive combination of position and content; nothing in the architecture forces it to. In practice this is why sinusoidal encoding degrades relatively gracefully but doesn't cleanly extrapolate: the linear relationship exists in the position vectors, but it's entangled with content in a way the model only partially learns to exploit, and it was never designed to handle positions with wavelengths the model never saw at training length.

### RoPE, derived

Goal: find a function `f(x, pos)` such that `f(q, m) · f(k, n)` depends only on `q`, `k`, and `(m-n)` — relative position, guaranteed by construction rather than hoped for.

Treat each 2D slice of the head dimension as a complex number (or a 2D coordinate pair). Rotate that pair by an angle proportional to position:

$$f(x, pos) = x \cdot e^{i \cdot pos \cdot \theta}$$

where `theta` is a fixed frequency for that dimension pair (following the same `10000^(-2i/d)` spectrum idea as sinusoidal, so different dimension pairs rotate at different rates). Applying this to both `q` at position `m` and `k` at position `n`, the dot product (equivalent to the real part of the product of one rotated vector with the complex conjugate of the other) becomes:

$$\langle f(q,m), f(k,n) \rangle = \text{Re}\left[ q \bar{k} \cdot e^{i(m-n)\theta} \right]$$

The rotation angles `m*theta` and `n*theta` combine into a single term depending only on `(m-n)*theta` — the individual absolute positions cancel out algebraically, not by training. This is the entire point: shift both `q` and `k` by the same absolute offset (translate the whole sequence) and the score is provably unchanged, because you're rotating both vectors by the same extra amount, which doesn't change the angle *between* them.

In real-valued implementation, for a `d`-dimensional head split into `d/2` pairs `(x_{2i}, x_{2i+1})`, each pair is rotated by angle `m * theta_i` where `theta_i = base^(-2i/d)` (base commonly 10000, sometimes much larger for long-context models):

```python
def rotate(x_pair, angle):
    x0, x1 = x_pair
    cos, sin = np.cos(angle), np.sin(angle)
    return x0 * cos - x1 * sin, x0 * sin + x1 * cos
```

Applied per-pair across all `d/2` frequencies at each position, this is the RoPE transform. It's applied to `Q` and `K` only — never to `V` — because the relative-position property comes specifically from the `Q·K` dot product structure; rotating `V` would just rotate the output representation for no benefit.

**Why "relative position for free" matters concretely:** a sinusoidal or learned-embedding model sees position `50000` at inference and has either no learned vector for it (learned embeddings) or a vector combination the training data never produced (sinusoidal beyond trained length). A RoPE model instead only ever needs the *rotation angle*, `(m-n)*theta`, to have been seen in a similar range during training — which is a much weaker requirement, and is exactly the lever that context-extension methods (below) pull.

### ALiBi: skip rotation, penalize distance directly

ALiBi (Press, Smith & Lewis, 2021) doesn't touch `Q` or `K` at all. It adds a static, non-learned bias to the raw attention scores before softmax:

$$\text{score}_{ij} = q_i \cdot k_j - m_h \cdot |i - j|$$

where `m_h` is a head-specific slope. The slopes follow a fixed geometric sequence: for `H` heads, `m_h = 2^{-8h/H}` (e.g. for `H=8`: `1/2, 1/4, 1/8, ..., 1/256`) — different heads penalize distance at wildly different rates, so some heads stay almost purely local while others retain long-range sensitivity, giving the model a spread of effective receptive fields without any of it being learned. Because the penalty is linear in distance and never depends on the absolute position index, a sequence of length 100k looks structurally identical to the model as one of length 100 — just with bigger numbers subtracted, which is why ALiBi extrapolates to unseen lengths without retraining. Reported result: a 1.3B model trained at sequence length 1024 with ALiBi matches the perplexity of a sinusoidal model trained directly at length 2048, while training 11% faster and using 11% less memory ([Press et al., 2021, arXiv:2108.12409](https://arxiv.org/abs/2108.12409), accessed 2026-07-26). The cost: ALiBi's inductive bias (recency dominates) is a worse fit for tasks needing precise long-range retrieval than RoPE at its trained length, which is why most 2024-2026 frontier labs chose RoPE-plus-extension over ALiBi despite ALiBi's simpler extrapolation story.

### Context extension: Position Interpolation, NTK-aware, YaRN

A pretrained RoPE model has only ever seen rotation angles `pos * theta_i` for `pos` up to its trained context length `L`. Push `pos` past `L` at inference and the model is evaluating rotation angles it never trained on — this is the actual mechanism behind long-context degradation, not a vague "attention gets diluted" story.

**Position Interpolation (PI, 2023).** The blunt fix: instead of extrapolating positions past `L`, compress them — scale every position index by `L/L'` (where `L'` is the new target length) so the *maximum angle ever seen* stays within the trained range. This works but degrades short-range resolution uniformly across all frequency bands, including the high-frequency (fine-grained, local) ones that didn't need compressing at all.

**NTK-aware interpolation.** The insight PI misses: low-frequency dimension pairs (large `theta_i`, slow rotation) need almost no adjustment to reach a new max length, while high-frequency pairs (small `theta_i`, fast rotation) already wrap around many times within the *original* context and don't need compression — compressing them anyway (as plain PI does) throws away resolution the model actually relies on for local/fine-grained attention. NTK-aware scaling instead stretches the RoPE *base* (`theta` = 10000 becomes larger) so that high-frequency dimensions are barely touched while low-frequency dimensions absorb most of the extension.

**YaRN (Peng et al., 2023).** Combines the frequency-aware idea with a per-dimension ramp instead of a single global choice. Define the wavelength ratio `r_d = L / lambda_d` for each dimension `d` (how many original-context-lengths fit in that dimension's rotation wavelength), and a ramp function:

$$\gamma(r) = \begin{cases} 0 & r < \alpha \\ 1 & r > \beta \\ \frac{r - \alpha}{\beta - \alpha} & \text{otherwise} \end{cases}$$

with `alpha=1, beta=32` as the values tuned for the Llama family. Each dimension's frequency is interpolated as `h(theta_d) = (1 - gamma(r_d)) * theta_d / s + gamma(r_d) * theta_d` — low-wavelength (high-frequency) dimensions where `r_d` is large get left alone (`gamma=1`, no scaling), high-wavelength (low-frequency) dimensions get fully compressed by factor `s` (`gamma=0`), and dimensions in between get a smooth blend. On top of this, YaRN adds an **attention temperature** adjustment: since interpolating frequencies flattens the score distribution slightly, YaRN scales attention logits by `1/sqrt(t)` where `sqrt(1/t) = 0.1 * ln(s) + 1`, a formula obtained by curve-fitting the temperature that minimizes perplexity across scale factors `s`, not derived from first principles ([YaRN paper, arXiv:2309.00071](https://arxiv.org/pdf/2309.00071), accessed 2026-07-26). Combined, YaRN reaches 128k+ context from a much shorter pretrained base with far less perplexity degradation than plain PI or plain NTK-aware scaling, and requires only a short fine-tuning phase (hundreds of steps, not a pretraining run) — this cost profile is why it became the default 2024-2026 extension recipe: Qwen, DeepSeek, Llama, and gpt-oss family releases all use YaRN-style scaling for their extended-context variants ([RoPE context extension deep dive](https://amaarora.github.io/posts/2025-09-21-rope-context-extension.html), accessed 2026-07-26).

**LongRoPE2 (2025)** reports near-lossless extension to 128k, arguing that earlier NTK/YaRN evaluations understated degradation due to an evaluation-methodology gap, and pushes the per-dimension search further; it and successor methods are the live frontier of this specific sub-problem as of mid-2026 rather than settled practice yet.

---

## Build it from scratch

```python
import numpy as np

def rope_frequencies(dim, base=10000.0):
    """theta_i for i in [0, dim/2) -- one frequency per rotated pair."""
    i = np.arange(0, dim, 2)
    return 1.0 / (base ** (i / dim))            # shape (dim/2,)

def rope_rotate(x, positions, base=10000.0):
    """x: (seq_len, dim). Applies RoPE rotation per position, per frequency pair."""
    seq_len, dim = x.shape
    theta = rope_frequencies(dim, base)                    # (dim/2,)
    angles = positions[:, None] * theta[None, :]            # (seq_len, dim/2)
    cos, sin = np.cos(angles), np.sin(angles)
    x1, x2 = x[:, 0::2], x[:, 1::2]                          # even/odd dims = pairs
    rotated = np.empty_like(x)
    rotated[:, 0::2] = x1 * cos - x2 * sin
    rotated[:, 1::2] = x1 * sin + x2 * cos
    return rotated

def rope_attention_scores(Q, K, base=10000.0):
    """Verifies the relative-position property: score depends only on (m - n)."""
    n, d = Q.shape
    positions = np.arange(n)
    Qr = rope_rotate(Q, positions, base)
    Kr = rope_rotate(K, positions, base)
    return Qr @ Kr.T / np.sqrt(d)

def alibi_bias(n_positions, n_heads):
    """Returns (n_heads, n, n) bias matrix to add to raw attention scores."""
    slopes = 2.0 ** (-8.0 * (np.arange(1, n_heads + 1)) / n_heads)
    dist = np.abs(np.arange(n_positions)[:, None] - np.arange(n_positions)[None, :])
    return -slopes[:, None, None] * dist[None, :, :]   # (H, n, n), negative = penalty

def yarn_ramp(dim, base, orig_len, scale, alpha=1, beta=32):
    """Per-dimension interpolation factor gamma in [0, 1]. untested sketch."""
    theta = rope_frequencies(dim, base)                 # (dim/2,)
    wavelength = 2 * np.pi / theta
    r = orig_len / wavelength
    gamma = np.clip((r - alpha) / (beta - alpha), 0.0, 1.0)
    new_theta = (1 - gamma) * theta / scale + gamma * theta
    return new_theta
```

A quick sanity check that RoPE gives relative position (run this, don't just believe it): compute `rope_attention_scores` for `Q, K` at positions `[5, 6, 7]` versus the same `Q, K` at positions `[105, 106, 107]` — the resulting score matrices are numerically identical, because only the pairwise differences `(m-n)` ever appear in the final angle.

Full sinusoidal / RoPE / ALiBi comparison harness with perplexity-vs-length extrapolation curves: **`(lab pending)`** (create if not present).

---

## How it's done in production

| Layer | What you actually use | What it adds |
|---|---|---|
| Base model | RoPE with a large base `theta` (100k-1M range for native long-context models, e.g. Llama 3's 500k) | Pushes the "wraps around" point of high-frequency dimensions further out, buying native context length without post-hoc scaling |
| Context extension | YaRN (via `transformers` `rope_scaling={"type": "yarn", ...}` config, or vLLM's `--rope-scaling`) | Extends a pretrained model past its base context with a short fine-tune, not a full pretraining run |
| Extrapolation without extension | ALiBi (rare in 2025-2026 frontier models; still used in some encoder/embedding models) | No fine-tuning needed to go past trained length, at a quality cost on long-range precision tasks |

### Failure modes

| Symptom | Cause | Fix |
|---|---|---|
| Perplexity fine at trained context, degrades sharply past it | RoPE rotation angles at those positions were never seen in training (out-of-distribution frequencies) | Apply NTK-aware/YaRN scaling matched to the target length, with the short fine-tune YaRN specifies, rather than raw extrapolation |
| Model retrieves near context fine, fails on far-back facts specifically at extended lengths | PI-style uniform compression flattened high-frequency (local-detail) resolution it didn't need to touch | Switch to a frequency-aware method (NTK-aware or YaRN's ramp) instead of plain linear position interpolation |
| Long-context fine-tune improves perplexity but not downstream task accuracy | Scaling done without the accompanying attention-temperature adjustment YaRN specifies, or applied to a base model with too small a native `theta` for the target scale factor | Use the full YaRN recipe (frequency ramp + temperature term), and check the scale factor `s` isn't pushing far outside the range the temperature formula was fit on |
| bf16 training silently breaks RoPE at long context | Rotation angle precision loss in bf16 accumulates over many positions, corrupting relative-position fidelity at long distances | Compute RoPE angles/sin/cos in fp32 even inside a bf16 training run ([BFloat16 Breaks Down RoPE, arXiv:2411.13476](https://arxiv.org/pdf/2411.13476), accessed 2026-07-26) |

---

## Tradeoffs & when NOT to use it

- **ALiBi is the wrong choice when precise long-range retrieval matters more than cheap extrapolation.** Its recency-biased inductive bias trades away exactly the long-distance precision that RAG-style needle-in-haystack retrieval needs; that's why almost no frontier 2025-2026 general-purpose LLM ships it as the primary scheme.
- **Plain Position Interpolation is rarely the right extension method anymore.** It's simple but wastes model capacity by compressing high-frequency dimensions that didn't need it; NTK-aware or YaRN dominate it at equivalent fine-tuning cost.
- **Extending context via RoPE scaling is not free capacity.** The model can now *attend* over more tokens without garbage perplexity, but if it was never trained on tasks requiring reasoning over that much context, scaling the position math alone won't produce good long-context task performance — that requires long-context data in the fine-tune, not just angle math.
- **A large native RoPE base (pretraining at long context directly) is not obviously better than pretrain-short-then-extend.** It costs more compute during pretraining for context length you may rarely use in practice; extend-on-demand is often the more compute-efficient choice unless long context is a near-universal serving requirement.
- **Sinusoidal/learned absolute embeddings are a legitimate choice only when context length is fixed and short and you have no extrapolation requirement at all** (e.g. small encoder models with a hard length cap) — anywhere extrapolation or extension matters, they're strictly dominated by RoPE-based approaches today.

---

## Interview questions

### Q1 — Why does attention need explicit positional information at all?
**Testing:** baseline understanding of what problem this even solves.
**Answer:** Self-attention computes `QK^T` as a set of pairwise dot products; permuting the input tokens permutes the rows/columns of that matrix identically but doesn't change any individual dot product's value — attention alone is permutation-equivariant with no notion of order. Positional encoding is what breaks that symmetry and gives the model access to sequence order.
**Follow-up trap:** *"Doesn't the causal mask already give it some notion of order?"* — the causal mask restricts *which* positions can be attended to (only earlier ones), but it doesn't tell the model *how far apart* two positions are, which is the actual information positional encoding supplies.

### Q2 — Derive why sinusoidal encoding was designed to support relative position, and why it under-delivers in practice.
**Answer:** `sin`/`cos` angle-addition formulas mean `PE(pos+k)` is expressible as a linear transformation of `PE(pos)` for any fixed offset `k` — the design intent was that the model could learn a fixed linear operation representing "shift by k" and apply it uniformly. In practice, position vectors are *added* to content embeddings, so the model has to learn to disentangle the linear relative-position structure from content-dependent noise in the same additive slot, and nothing in training length forces this to generalize to unseen positions.
**Follow-up trap:** *"So is sinusoidal encoding 'wrong'?"* — no, it's a legitimate, learnable-in-principle design; it's just weaker than RoPE's guarantee, which makes relative position an algebraic property of the dot product itself rather than something the model must learn from additive vectors.

### Q3 — Derive RoPE's core property: why does rotating Q and K make the dot product depend only on relative position?
**Testing:** the actual derivation, not "it uses rotation matrices."
**Answer:** Represent a 2D slice of `q` at position `m` as `q * e^{i*m*theta}` and `k` at position `n` as `k * e^{i*n*theta}`. Their inner product (real part of one times the conjugate of the other) is `Re[q * conj(k) * e^{i*(m-n)*theta}]` — the `m` and `n` terms combine additively in the exponent and the result only depends on `(m-n)`. This holds because rotating both vectors by the same extra angle (shifting both `m` and `n` by the same constant) doesn't change the angle *between* them, which is exactly what a dot product of unit-scaled vectors measures.
**Follow-up trap:** *"Why apply RoPE to Q and K but never to V?"* — the relative-position guarantee comes specifically from the structure of the `Q·K` dot product; `V` is just the content being aggregated, rotating it would only rotate the output representation for no positional benefit and would need to be un-rotated somewhere to keep the residual stream consistent.

### Q4 — What is the RoPE "base" (theta, commonly 10000) actually controlling, and why do long-context models use a much larger value?
**Answer:** Base sets the frequency spectrum: dimension pair `i` rotates at rate `base^(-2i/d)`, so a larger base slows down every frequency, especially the low-frequency (large-`i`) dimensions, meaning the rotation angle takes longer (more positions) to wrap around. Long-context models (Llama 3 at 500k base, for example) use a larger base specifically so that the trained context length doesn't push any dimension's rotation angle into territory it hasn't seen, without needing post-hoc frequency scaling.
**Follow-up trap:** *"If a bigger base is better for long context, why not always use the biggest possible base?"* — an excessively large base flattens the frequency spectrum too much at short distances, reducing the model's ability to distinguish nearby positions sharply, which hurts fine-grained local attention; the base has to be tuned relative to the target training context length, not maximized blindly.

### Q5 — A model trained at 8k context degrades sharply past it. Is this an attention problem or a positional encoding problem, and how do you tell?
**Answer:** With RoPE, it's almost always positional: attention's mechanism (`softmax(QK^T/sqrt(d))V`) is unchanged past 8k, but the rotation angles at positions beyond 8k are out-of-distribution relative to what the model saw in training. Diagnose by checking whether perplexity degradation tracks *position index* (positional) versus something that would degrade regardless of absolute position, like a KV-cache eviction bug (serving-layer, not architectural).
**Follow-up trap:** *"Give me the concrete fix without retraining from scratch."* — apply YaRN or NTK-aware scaling to remap the rotation frequencies to the target length, then do a short fine-tune (hundreds to low-thousands of steps, not a full pretraining run) so the model adapts to the rescaled angles.

### Q6 — Walk through YaRN's per-dimension ramp function and why it treats high- and low-frequency dimensions differently.
**Answer:** For each RoPE dimension, compute the wavelength ratio `r_d = L / lambda_d` (original context length over that dimension's rotation wavelength). High-frequency dimensions (short wavelength, large `r_d`) already cycle many times within the original context and don't need adjustment (ramp value 1, meaning "keep as-is" in YaRN's convention -- no compression). Low-frequency dimensions (long wavelength, small `r_d`) barely rotate within the original context and need most of the compression to reach the new length (ramp value 0, full interpolation by scale factor `s`). A smooth blend (`alpha=1, beta=32` for Llama) interpolates between the two regimes.
**Follow-up trap:** *"Why not just compress every dimension uniformly like plain Position Interpolation?"* — that wastes resolution on high-frequency dimensions that already had headroom, degrading short-range/local attention precision unnecessarily; YaRN's whole improvement over PI is recognizing frequencies need different treatment.

### Q7 — What does YaRN's attention temperature term do, and is it derived or empirical?
**Answer:** It's empirical: `sqrt(1/t) = 0.1*ln(s) + 1` was obtained by curve-fitting the temperature value that minimized perplexity across tested scale factors `s`, not derived from first principles. It scales attention logits (equivalent to a mild extra softening or sharpening of the softmax) to compensate for the slight distributional shift the frequency interpolation introduces.
**Follow-up trap:** *"What breaks if you skip the temperature term and just do the frequency ramp?"* — YaRN's reported perplexity numbers assume both pieces together; skipping the temperature adjustment leaves measurable perplexity on the table at the tested scale factors, since the two were tuned jointly.

### Q8 — Explain ALiBi's slope assignment across heads and why different heads get very different slopes.
**Answer:** For `H` heads, head `h`'s slope is `m_h = 2^{-8h/H}`, a geometric sequence — e.g. at `H=8`: `1/2, 1/4, ..., 1/256`. Steeper slopes (larger penalty per unit distance) make that head almost purely local; shallow slopes let a head retain influence from far-away tokens. Spreading slopes geometrically across heads gives the model a range of effective "receptive fields" without learning any of it — it's a fixed inductive bias, not a trained parameter.
**Follow-up trap:** *"Since the slopes aren't learned, doesn't that limit what the model can express?"* — yes, that's the acknowledged tradeoff: ALiBi trades some representational flexibility (which RoPE preserves, since rotation frequencies are fixed but the interaction with learned Q/K projections is fully expressive) for extrapolation robustness and reduced compute, which is why it isn't the default at the highest end of retrieval-heavy frontier models.

### Q9 — Compare RoPE and ALiBi on extrapolation past trained context length, mechanically, not just by benchmark number.
**Answer:** RoPE's score at distance `(m-n)` depends on rotation angles the model has seen during training up to its max trained length; past that, the angles are out-of-distribution and quality degrades until you intervene with frequency scaling. ALiBi's score is a *linear* penalty in raw distance with no notion of "trained range" baked into the math itself — a distance of 200000 is treated exactly the same functional way as a distance of 200, just with a bigger subtracted number, so there's no out-of-distribution regime to hit, which is the entire mechanism behind ALiBi's extrapolation claim.
**Follow-up trap:** *"So is ALiBi strictly more robust?"* — robust to length extrapolation specifically, yes; but its fixed recency bias means it's structurally worse than RoPE at giving equal, precise attention weight to a far-away but highly relevant token, which is a different (and for many production use cases more important) failure mode.

### Q10 — Design the positional strategy for a new 13B model you're pretraining, expecting to serve at both 8k (chat) and 1M (document analysis) context.
**Testing:** synthesis under a real constraint, staff-level.
**Answer:** Pretrain with RoPE at a moderate native context (e.g. 8k-32k) using a base `theta` already somewhat larger than the classic 10000 (headroom for later extension without stressing high-frequency dimensions too early), validate quality at the native length, then apply YaRN-style extension with a short continued-pretraining/fine-tune phase specifically targeting 1M, verifying with long-context retrieval evals (not just perplexity, which can look fine while retrieval degrades). Budget for the fact that extension is not free lunch: expect measurable continued-training compute and a validation pass at the target length before shipping, not a config flag flipped at serving time.
**Follow-up trap:** *"What if you skip pretraining at native long context entirely and just YaRN-scale from a much shorter base, say 4k to 1M?"* — technically possible but the quality gap grows with how extreme the scale factor `s` is; YaRN's own temperature formula was fit on a bounded range of scale factors, and pushing far outside that range without re-validating is exactly the kind of unverified extrapolation that produces silent quality regressions in production.

### Q11 — A user says "the model seems to have amnesia after about 50 pages of the document, even though it's within our stated context window." What do you check first?
**Answer:** First confirm it's actually a positional-encoding effect and not truncation or KV-cache eviction upstream (check the raw prompt length reaching the model and whether the serving stack does any windowing). If length is confirmed within the stated window, check whether that window was reached via YaRN/NTK extension and whether the scale factor used in production matches what was validated — a common real-world bug is a mismatch between the `rope_scaling` config used at serving time and the one used during the extension fine-tune.
**Follow-up trap:** *"The config matches exactly. What next?"* — check if the "stated context window" in marketing/docs is the *architectural* max (what RoPE scaling nominally supports) versus the *effectively validated* max (what retrieval evals actually confirmed good quality at) — these are often different numbers, and shipping the architectural max without task-level validation is a common cause of exactly this complaint.

---

## Red flags that fail you

- Saying RoPE "adds" positional information — it rotates, it doesn't add; conflating the two erases the entire reason RoPE gives relative position for free.
- Claiming sinusoidal encoding "extrapolates fine" past trained length — it's bounded and well-defined at any position, but the model still hasn't seen those position combinations in training, so quality degrades.
- Describing context extension (YaRN/NTK) as a free inference-time flag with no fine-tuning implications.
- Not being able to state that RoPE is applied to Q and K only, never V.
- Confusing Position Interpolation (uniform compression) with NTK-aware/YaRN (frequency-selective compression) — these are not the same mechanism.
- Claiming ALiBi is strictly better than RoPE because it extrapolates — ignoring the recency-bias quality tradeoff.

---

## Cheat card

```
WHY NEEDED       attention is permutation-equivariant; position must be injected explicitly
SINUSOIDAL       PE(pos,2i)=sin(pos/10000^(2i/d)), PE(pos,2i+1)=cos(...) -- additive, absolute
                 relative-position support relies on model LEARNING angle-addition structure
ROPE CORE        rotate Q,K by angle m*theta_i per dim-pair i; dot product depends only on (m-n)*theta_i
                 theta_i = base^(-2i/d), base commonly 10000 (short ctx) to 500k+ (native long ctx)
                 applied to Q,K only -- never V
ALIBI            score -= m_h*|i-j|; slope m_h = 2^(-8h/H) geometric across H heads
                 no learned params; extrapolates natively; trades away long-range precision
CONTEXT EXT      PI: uniform position compression by L/L' -- wastes high-freq resolution
                 NTK-aware: stretch base theta, low-freq dims absorb most scaling
                 YaRN: per-dim ramp gamma(r), r=L/wavelength, alpha=1 beta=32 (Llama) + temp scaling
                 YaRN temp: sqrt(1/t) = 0.1*ln(s)+1 (curve-fit, not derived)
FAILURE MODE     bf16 angle precision loss corrupts RoPE at long distance -- compute angles in fp32
PRODUCTION       transformers/vLLM rope_scaling={"type":"yarn",...}; short fine-tune required, not free
NEVER            claim context extension needs zero fine-tuning or validation past the tuned scale range
```

## Sources

- [RoFormer: Enhanced Transformer with Rotary Position Embedding (arXiv:2104.09864)](https://arxiv.org/abs/2104.09864) — accessed 2026-07-26
- [Rotary Embeddings: A Relative Revolution — EleutherAI Blog](https://blog.eleuther.ai/rotary-embeddings/) — accessed 2026-07-26
- [Train Short, Test Long: Attention with Linear Biases (ALiBi) (arXiv:2108.12409)](https://arxiv.org/abs/2108.12409) — accessed 2026-07-26
- [YaRN: Efficient Context Window Extension of Large Language Models (arXiv:2309.00071)](https://arxiv.org/pdf/2309.00071) — accessed 2026-07-26
- [Extending the RoPE — EleutherAI Blog](https://blog.eleuther.ai/yarn/) — accessed 2026-07-26
- [How LLMs Scaled from 512 to 2M Context: A Technical Deep Dive](https://amaarora.github.io/posts/2025-09-21-rope-context-extension.html) — accessed 2026-07-26
- [LongRoPE2: Near-Lossless LLM Context Window Scaling (arXiv:2502.20082)](https://arxiv.org/pdf/2502.20082) — accessed 2026-07-26
- [When Precision Meets Position: BFloat16 Breaks Down RoPE in Long-Context Training (arXiv:2411.13476)](https://arxiv.org/pdf/2411.13476) — accessed 2026-07-26

## Changelog
- 2026-07-27 — created
