# Build & Train a nanoGPT-Class Model From Scratch

> **Track:** T05 LLM Internals · **Time:** 4h · **Prereqs:** T05-autoregression, T05-tokenization, T05-attention, T05-positional, T05-architecture-blocks · **Updated:** 2026-07-28
> **Module id:** `T05-build-nanogpt` · **Tags:** lab, critical
> **Lab:** none yet — see `labs/py/02-agent-loop/` for the pattern if you want to build one

## The 30-second version

A GPT is roughly 300 lines of PyTorch: token + positional embeddings feeding a stack of pre-norm transformer blocks (causal self-attention + MLP, residual around each), ending in a final norm and a tied output projection back to vocabulary logits, trained with plain cross-entropy against the next token. Karpathy's `build-nanogpt` reproduces GPT-2 (124M) on an 8xA100 node in about 90 minutes for roughly $20-30 of compute, hitting GPT-2's original validation loss of ~3.12 on OpenWebText; a single consumer GPU or a free Colab T4 can't reproduce that in reasonable time, but it can train a character-level Shakespeare model to a sensible loss (~1.4-1.5) in minutes and a small subword model on a few million tokens in under an hour. The actual engineering is in getting the details right that don't show up in a diagram: weight tying, correct initialization scaling by depth, fused/flash attention kernels, mixed precision, gradient clipping, and a cosine LR schedule with warmup — get any of these wrong and the loss curve looks fine on log scale while the model is actually much worse than it should be. The single most common failure for a from-scratch build is a silent bug that still trains (data leakage between train/val, wrong causal mask, forgetting to shift targets) — the loss goes down, so it looks correct, and it takes a held-out eval or a generation sample to catch it.

## Why this gets asked

Everyone who's used an LLM API can describe attention in the abstract; very few candidates have actually watched a transformer's loss curve from a cold random initialization to something that generates coherent text, which is the difference between reciting an architecture diagram and having debugged one. The interviewer has spent real time watching a training run diverge or stall and wants to know if you understand *why* — an unstable loss spike at step 4,000 is diagnosable (usually a bad batch, an LR that's too high, or unscaled attention logits), but only if you know what to look at. This module is also the natural home for "have you actually trained a model, or only fine-tuned/called one," which becomes an increasingly sharp filter as more candidates skip straight to API usage.

## Lineage: past → present → future

**What came before.** Before nanoGPT (2022), reproducing GPT-2 meant either using OpenAI's original TensorFlow 1.x code (undocumented, awkward, effectively unmaintainable by 2020) or wading into HuggingFace's `transformers` library, which is comprehensive but deliberately general-purpose — a single `GPT2Model` class supports dozens of variants, config options, and backward-compatibility shims, which makes it a poor teaching tool even though it's the right tool for production. Karpathy's original `minGPT` (2020) stripped this down to roughly 300 lines for pedagogy, then `nanoGPT` (Jan 2023) rebuilt it as something that is *also* fast enough to actually reproduce GPT-2 on real hardware in hours rather than being purely illustrative — the pain it fixed was the false choice between "readable" and "actually trains a real model at real scale."

**Where it stands now.** `nanoGPT` and its 2024 successor `build-nanogpt` (the from-scratch lecture-and-code version, walked through token by token) are the standard reference implementation used across the field for teaching and for research ablations — most scaling-law and optimizer papers in 2024-2026 still cite or fork it as a clean baseline. A parallel and very active thread is Keller Jordan's `modded-nanogpt` speedrun, a public leaderboard for "fastest wall-clock time to a fixed validation loss (3.28) on FineWeb with the 124M architecture on 8xH100" — the record dropped from a ~45-minute baseline to under 2 minutes through a long sequence of concrete, individually-small wins: a Muon optimizer replacing AdamW for the hidden matrices, better learning-rate schedules, architecture tweaks (untied embeddings, QK-norm, value residuals), and reduced vocabulary size ([modded-nanogpt](https://github.com/kellerjordan/modded-nanogpt), accessed 2026-07-28; [NanoGPT speedrun history](https://www.lesswrong.com/posts/j3gp8tebQiFJqzBgg/how-the-nanogpt-speedrun-wr-dropped-by-20-in-3-months), accessed 2026-07-28). The live disagreement in the speedrun community, and increasingly in production pretraining, is how much of that stack (Muon in particular) transfers to genuinely large-scale runs versus being an artifact tuned specifically for the 124M/FineWeb regime.
The practical consensus for someone learning this today: build the naive version yourself once, understand every line, then read (don't necessarily reproduce) the speedrun diffs to see which "obvious" choices in the naive version turn out to be leaving real performance on the table.

**Where it's heading.** With reasonable confidence: the reference-implementation role of nanoGPT-style codebases is stable — they keep getting re-forked as the "known good baseline" for new optimizer and architecture ideas because they are small enough to audit end to end, which matters more as papers proliferate. Muon and Muon-derived optimizers (Shampoo-family, orthogonalized updates) are trending from "speedrun curiosity" toward genuine adoption in larger pretraining runs through 2025-2026, though whether they hold their advantage past the 1B-10B parameter range the community has tested is still being established. More speculatively: as reasoning-model post-training (RL on verifiable rewards) becomes the dominant cost center for frontier labs, expect "build it from scratch" educational content to extend past pretraining into a minimal GRPO-on-a-toy-model lab — treat that as a direction of travel, not something settled or widely available yet.

---

## Mental model

```
tokens ──▶ [token embed] ──┐
                            ├─▶ + ──▶ [ Block ] × N ──▶ [ final LayerNorm ] ──▶ [ LM head ] ──▶ logits
positions ──▶ [pos embed] ─┘              │
                                    (weight-tied to token embed)

  one Block, pre-norm residual:
  x ──▶ [LayerNorm] ──▶ [Causal Self-Attention] ──▶ (+) ──▶ [LayerNorm] ──▶ [MLP] ──▶ (+) ──▶ out
  │_______________________________________________↑        │______________________________↑
                    residual add                                    residual add
```

Think of the whole network as a residual stream: each block *reads* from the stream (via LayerNorm), computes something (attention or MLP), and *adds* its result back in. Nothing overwrites the stream — everything the network has learned so far is still there for the next block to build on, which is exactly why residual connections are what makes 12+ layer networks trainable at all (without them, gradients through 12 sequential nonlinear transforms vanish or explode).

---

## How it actually works

### The GPT block, with real shapes

For GPT-2 (124M): `n_layer=12`, `n_head=12`, `n_embd=768`, `block_size=1024`, `vocab_size=50257`.

```python
import torch, torch.nn as nn, torch.nn.functional as F, math

class CausalSelfAttention(nn.Module):
    def __init__(self, n_embd, n_head, block_size):
        super().__init__()
        self.n_head, self.n_embd = n_head, n_embd
        self.qkv = nn.Linear(n_embd, 3 * n_embd)
        self.proj = nn.Linear(n_embd, n_embd)
        self.proj.NANOGPT_SCALE_INIT = 1   # marks this for the 1/sqrt(2*n_layer) init below

    def forward(self, x):
        B, T, C = x.shape
        qkv = self.qkv(x)
        q, k, v = qkv.split(self.n_embd, dim=2)
        q = q.view(B, T, self.n_head, C // self.n_head).transpose(1, 2)  # (B, nh, T, hd)
        k = k.view(B, T, self.n_head, C // self.n_head).transpose(1, 2)
        v = v.view(B, T, self.n_head, C // self.n_head).transpose(1, 2)
        # scaled_dot_product_attention dispatches to FlashAttention when available
        y = F.scaled_dot_product_attention(q, k, v, is_causal=True)
        y = y.transpose(1, 2).contiguous().view(B, T, C)
        return self.proj(y)

class MLP(nn.Module):
    def __init__(self, n_embd):
        super().__init__()
        self.fc = nn.Linear(n_embd, 4 * n_embd)
        self.gelu = nn.GELU(approximate="tanh")  # matches GPT-2's original approximation
        self.proj = nn.Linear(4 * n_embd, n_embd)
        self.proj.NANOGPT_SCALE_INIT = 1

    def forward(self, x):
        return self.proj(self.gelu(self.fc(x)))

class Block(nn.Module):
    def __init__(self, n_embd, n_head, block_size):
        super().__init__()
        self.ln1 = nn.LayerNorm(n_embd)
        self.attn = CausalSelfAttention(n_embd, n_head, block_size)
        self.ln2 = nn.LayerNorm(n_embd)
        self.mlp = MLP(n_embd)

    def forward(self, x):
        x = x + self.attn(self.ln1(x))   # pre-norm: normalize BEFORE the sublayer, not after
        x = x + self.mlp(self.ln2(x))
        return x
```

**Why pre-norm, not post-norm.** The original Transformer (2017) applied LayerNorm *after* the residual add (post-norm). Post-norm trains fine at shallow depth but becomes unstable as layers stack, because gradients have to flow back through the norm at every layer; pre-norm keeps an unnormalized residual path all the way from input to output, which is why every GPT-style model since GPT-2 uses it. This is covered in depth in `T05-architecture-blocks`; the point here is that getting this backwards is a real and easy-to-make bug that trains but converges to a visibly worse loss.

**Weight tying.** The input token embedding (`vocab_size × n_embd`) and the output LM head (`n_embd × vocab_size`) are set to literally the same tensor (`self.lm_head.weight = self.wte.weight`). This is not a minor optimization: for GPT-2 (124M), the embedding matrix is `50257 × 768 ≈ 38.6M` parameters — roughly 31% of the entire model. Untying it doesn't just waste parameters, it also tends to slightly hurt quality (the original GPT-2 and the "Using the Output Embedding to Improve Language Models" paper both tie for this reason).

**Depth-scaled initialization.** Standard practice (GPT-2's own code, and every faithful reproduction) scales the *output* projection of each attention and MLP block (the layers marked `NANOGPT_SCALE_INIT` above) by `1/√(2 · n_layer)` in addition to the usual `std=0.02` initialization. Why: with `N` residual blocks each adding their own output into the stream, the *variance* of the residual stream grows roughly linearly with `N` if every block's contribution has unit variance — by block 12, the stream's scale has grown enough to make training less stable. Scaling each block's contribution down by `1/√(2N)` (the `2` accounts for attention and MLP both contributing per block) keeps the stream's variance roughly constant regardless of depth. Skipping this is a genuine, measurable difference in loss curves at 12+ layers, not a cosmetic detail.

### The training loop, with real numbers

```python
# untested sketch -- illustrates the real loop; see labs/py/06-build-nanogpt/train.py for a runnable version
import torch, time

model = GPT(config).to(device)
model = torch.compile(model)  # ~2x throughput on A100/H100, from kernel fusion

optimizer = torch.optim.AdamW(
    model.parameters(), lr=6e-4, betas=(0.9, 0.95), weight_decay=0.1, fused=True
)

def get_lr(step, warmup_steps=715, max_steps=19073, max_lr=6e-4, min_lr=6e-5):
    if step < warmup_steps:
        return max_lr * (step + 1) / warmup_steps          # linear warmup
    if step > max_steps:
        return min_lr
    decay_ratio = (step - warmup_steps) / (max_steps - warmup_steps)
    coeff = 0.5 * (1.0 + math.cos(math.pi * decay_ratio))    # cosine decay
    return min_lr + coeff * (max_lr - min_lr)

for step in range(max_steps):
    t0 = time.time()
    x, y = train_loader.next_batch()
    x, y = x.to(device), y.to(device)
    optimizer.zero_grad()
    with torch.autocast(device_type="cuda", dtype=torch.bfloat16):
        logits = model(x)
        loss = F.cross_entropy(logits.view(-1, logits.size(-1)), y.view(-1))
    loss.backward()
    norm = torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)  # cap gradient norm
    lr = get_lr(step)
    for g in optimizer.param_groups:
        g["lr"] = lr
    optimizer.step()
    torch.cuda.synchronize()
    dt = time.time() - t0
    tokens_per_sec = (x.numel()) / dt
```

Each line here fixes a real, specific instability if removed:

- **`betas=(0.9, 0.95)`** (not Adam's default `0.999`) — a shorter second-moment memory tracks the noisier gradients of language-model training better; using the default makes convergence visibly slower in the first few thousand steps.
- **Gradient clipping at norm 1.0** — without it, a single anomalous batch (a long repeated sequence, a tokenization edge case) can produce a gradient spike that the optimizer's momentum then propagates for hundreds of steps afterward — the classic "loss spike that never fully recovers" pattern.
- **Warmup (715 steps)** — starting at full LR before Adam's second-moment estimate has stabilized causes an early, sometimes fatal instability; this is why every serious LLM training run warms up, typically over 0.1-1% of total steps.
- **`torch.compile`** — roughly 2x wall-clock throughput on A100 via kernel fusion and reduced Python overhead; the first step is much slower (compilation), which is a genuine gotcha if you're timing per-step throughput naively.

### Reading the loss curve

Expected shape training GPT-2 (124M) on OpenWebText/FineWeb: loss starts near `ln(vocab_size) ≈ ln(50257) ≈ 10.8` (a uniform random guess), drops steeply in the first few hundred steps as the model learns basic token frequencies and short-range structure, then descends smoothly and slowly, following an approximate power law in steps, converging toward GPT-2's reported validation loss of about **3.12** on the small (124M) config after roughly 10B tokens seen (repeated passes acceptable at this compute budget), or the modern nanoGPT-style single-epoch run over ~10B FineWeb tokens landing in a similar range ([nanoGPT reproduction notes](https://github.com/karpathy/build-nanogpt), accessed 2026-07-28). What "wrong" looks like:

| Symptom | Likely cause |
|---|---|
| Loss stuck near `ln(vocab_size)` past the first few hundred steps | Learning rate far too low, or a bug zeroing gradients |
| Loss goes to `NaN` | LR too high, missing gradient clipping, or fp16 (not bf16) overflow in attention |
| Loss decreases smoothly but generation is garbage | Train/val split leakage, or targets not shifted by one position (model is trivially copying input) |
| Loss looks great in log-plot but validation loss is far worse than train | Overfitting on a too-small dataset relative to model size, or actual data duplication inflating apparent train performance |
| Sudden spike at some step, partial recovery | One bad batch (e.g., non-UTF8 bytes, an extremely long document) hit the optimizer's momentum; add grad clipping if missing, consider skipping the batch |

---

## Build it from scratch

Two realistic tiers, both runnable on hardware a candidate actually has access to.

**Tier 1 — laptop CPU or free Colab T4, minutes: character-level Shakespeare.** `vocab_size≈65` (raw characters), `n_layer=4-6`, `n_embd=128-384`, `block_size=256`. This trains to a validation loss around **1.4-1.5** (much lower than word/subword loss because the vocabulary is tiny) in a few minutes on a T4, and a few tens of minutes on CPU. This is the right first target: it proves the whole pipeline (data loading, forward, loss, backward, sampling) works before spending any real compute.

```python
# untested sketch -- minimal end-to-end skeleton, character-level
with open("shakespeare.txt") as f:
    text = f.read()
chars = sorted(set(text))
stoi = {c: i for i, c in enumerate(chars)}
data = torch.tensor([stoi[c] for c in text], dtype=torch.long)
n = int(0.9 * len(data))
train_data, val_data = data[:n], data[n:]

def get_batch(split, block_size=256, batch_size=64):
    d = train_data if split == "train" else val_data
    ix = torch.randint(len(d) - block_size, (batch_size,))
    x = torch.stack([d[i:i+block_size] for i in ix])
    y = torch.stack([d[i+1:i+block_size+1] for i in ix])   # targets = inputs shifted by 1
    return x, y
```

**Tier 2 — single A100/H100 or Colab Pro, a few hours: GPT-2 (124M)-class on a FineWeb subset.** This is where the numbers above (6e-4 peak LR, bf16 autocast, `torch.compile`, gradient clipping) matter and where you actually reproduce something comparable to a real released checkpoint. Realistic budget: **10B tokens, batch size ~0.5M tokens via gradient accumulation, ~19,000 optimizer steps** — Karpathy's original reproduction took about 4 days on an 8xA100 node in the pre-`torch.compile`/pre-bf16-default era; with modern kernels and `torch.compile`, a single 8xH100 node reproduces it in **under 2 hours**, and a single consumer GPU (RTX 4090) can get a smaller (e.g., 6-layer, ~30M param) model to a sensible loss on a few hundred million tokens overnight.

Full training script, data loader (FineWeb shard downloader), and evaluation harness (HellaSwag accuracy as a sanity check beyond loss): **`labs/py/06-build-nanogpt/`**.

---

## How it's done in production

| Layer | What you actually use | What it adds |
|---|---|---|
| Reference/teaching | `nanoGPT` / `build-nanogpt` | Minimal, auditable, single-file-ish; not built for multi-node scale |
| Real pretraining | Megatron-LM, torchtitan, DeepSpeed | Tensor/pipeline/data parallelism, ZeRO sharding, activation checkpointing for models that don't fit on one GPU |
| Data pipeline | datatrove, NeMo Curator | Streaming shard loading, tokenization at scale, dedup — covered in `T05-pretraining` |
| Optimizer | AdamW (standard) or Muon (2024-2026, speedrun-derived) | Muon claims faster convergence per step on hidden-layer matrices via orthogonalized updates; adoption in genuinely large runs is still being validated as of mid-2026 |

### Failure modes

| Symptom | Cause | Fix |
|---|---|---|
| Loss is `NaN` within the first 100 steps | fp16 autocast overflow (fp16 has a much narrower exponent range than bf16) | Use `bfloat16` autocast on Ampere+ GPUs; fp16 needs a loss-scaler and is more fragile |
| Throughput far below expected TFLOPs | `torch.compile` recompiling every step (dynamic shapes), or DataLoader is the bottleneck, not the GPU | Pad/bucket to fixed shapes; profile with `torch.profiler` before assuming it's the model |
| Model trains but validation loss barely beats a bigram baseline | Positions or targets not aligned (off-by-one), or attention mask not actually causal | Sanity-check: overfit a tiny model on 10 examples to near-zero loss; if it can't, the pipeline has a correctness bug, not a scale problem |
| Perfect train loss, terrible generation | Train/val split leaked (same document split across both, or dedup missed near-duplicates) | Deduplicate before splitting, split by document not by line |
| OOM only when increasing `block_size` | Activation memory for attention scales with sequence length; naive attention is O(n²) | Use `F.scaled_dot_product_attention` (dispatches FlashAttention), enable gradient checkpointing |

---

## Tradeoffs & when NOT to use it

- **Don't reproduce GPT-2 from scratch to get a production model.** Every open-weight checkpoint from GPT-2 onward is better, cheaper, and faster to obtain than retraining it; the value of this exercise is entirely diagnostic fluency, not model production.
- **Don't skip the character-level tier to go straight to a "real" run.** If your pipeline has a subtle bug (off-by-one targets, wrong mask), it is far cheaper to discover that at Tier 1 in two minutes than at Tier 2 after burning GPU-hours.
- **`torch.compile` isn't free.** First-step compilation overhead is real (tens of seconds to minutes), and dynamic input shapes (variable sequence lengths per batch) can trigger repeated recompilation that silently tanks throughput; for short experimental runs the overhead may not pay for itself.
- **Single-GPU training is the wrong tool once the model doesn't fit in one GPU's memory** (roughly >1-2B parameters at fp32 gradients/optimizer state on a single 80GB card) — that's when you need Megatron/DeepSpeed-style sharding, which is a materially different engineering problem (communication topology, not just a bigger loop).
- **Muon/exotic optimizers are a bet, not a default**, as of 2026 — they show real speedrun gains at the 124M/FineWeb scale the community has heavily tuned for; use AdamW as your default unless you have a specific, validated reason and the budget to re-tune around a new optimizer.

---

## Interview questions

### Q1 — Walk me through a forward pass of a GPT block, tensor shapes included.
**Testing:** whether you've actually implemented this, not just read about it.
**Answer:** Input `x: (B, T, C)`. LayerNorm normalizes over the last dim, shape unchanged. QKV projection: `(B, T, C) → (B, T, 3C)`, split into `q, k, v: (B, T, C)` each, reshaped to `(B, n_head, T, head_dim)`. Scaled dot-product attention returns `(B, n_head, T, head_dim)`, reshaped back to `(B, T, C)`, projected once more, then added back to the residual stream. MLP: `(B, T, C) → (B, T, 4C) → GELU → (B, T, C)`, added back again.
**Follow-up trap:** *"Why 4C for the MLP hidden dimension specifically?"* — it's the original Transformer/GPT convention, not a mathematical necessity; it gives the MLP roughly 8x the parameters of a single attention projection (since MLP has two `C×4C` matrices vs attention's four `C×C` matrices), which empirically works well but is a design choice, not a derived constant — some newer architectures (SwiGLU-based) use a different multiplier to keep parameter count matched.

### Q2 — Why is weight tying between the embedding and the LM head not just a parameter-saving trick?
**Answer:** For GPT-2 (124M), the tied matrix is `50257 × 768 ≈ 38.6M` params, about 31% of the model — untying doubles that cost. Beyond the savings, the original "Using the Output Embedding to Improve Language Models" (Press & Wolf, 2017) result and GPT-2's own ablations found tied weights slightly improve quality, likely because it forces the input and output representations of a token to live in a compatible space.
**Follow-up trap:** *"Does tying ever hurt?"* — in very large-vocabulary or highly multilingual settings, some newer architectures untie deliberately, arguing the optimal input embedding (frequency-sensitive) and output embedding (calibration-sensitive) objectives diverge at scale; this is a live, model-specific design choice, not settled either way.

### Q3 — Derive why gradients vanish or explode in a deep post-norm transformer but not (as badly) in pre-norm.
**Answer:** Post-norm applies LayerNorm after the residual add: `x_{l+1} = LN(x_l + f(x_l))`. Backpropagating through `L` such layers means the gradient passes through `L` LayerNorm Jacobians in sequence, each of which can attenuate or amplify depending on the input's variance at that point — compounding over depth. Pre-norm computes `x_{l+1} = x_l + f(LN(x_l))`: the residual path `x_l` reaches `x_{l+1}` completely unmodified by any normalization, so gradients have a direct, un-attenuated path all the way back to the input regardless of depth; only the branch through `f` sees the normalization's Jacobian.
**Follow-up trap:** *"So is post-norm just strictly worse?"* — no; post-norm's stronger normalization pressure can produce better-calibrated activations at *shallow* depth and some 2023-2025 architectures (DeepNet-style) reintroduce carefully-scaled post-norm variants specifically to get that benefit back at extreme depth. It's a real, current design tradeoff, not settled history.

### Q4 — What's the compute budget arithmetic for training GPT-2 (124M) on 10B tokens? Use the standard `6ND` approximation.
**Answer:** `FLOPs ≈ 6 × N × D` where `N` is non-embedding parameters and `D` is tokens. `N ≈ 124M`, `D = 10B`: `6 × 1.24×10^8 × 10^10 ≈ 7.4×10^18` FLOPs (~7.4 exaFLOPs). An A100 delivers roughly 150-200 TFLOP/s of achievable (not theoretical peak) bf16 throughput in practice with good kernels; on 8 A100s that's roughly `1.2-1.6 × 10^15` FLOP/s, so wall-clock time is `7.4×10^18 / 1.4×10^15 ≈ 5,300s ≈ 90 minutes` — consistent with reported modern reproductions.
**Follow-up trap:** *"Why 6ND and not something else?"* — the factor of 6 comes from 2 FLOPs per parameter per token for the forward pass (one multiply, one add per weight) times roughly 3x for forward+backward (backward costs about 2x forward) — `2 × 3 = 6`. It's an approximation that ignores attention's own `O(n²d)` term, which is usually small relative to the parameter term at typical context lengths but stops being negligible at very long context.

### Q5 — Your loss goes to NaN at step 340. Debug it live.
**Answer:** First check precision: fp16 autocast has a narrow exponent range and overflows silently unless a loss scaler is active — switch to bf16 on Ampere+ hardware, which has fp32's exponent range. Second, check whether gradient clipping is actually being applied (a common bug: computing the clip but not using the returned/clipped gradients, or clipping after the optimizer step). Third, inspect the batch at that step for a pathological input — an extremely long repeated token run can produce anomalously large attention logits before scaling is applied correctly.
**Follow-up trap:** *"You switch to bf16 and it still happens at a later step."* — check the learning rate schedule: if warmup is too short or peak LR too high for your batch size, instability can resurface later once the model reaches a region of loss landscape with sharper curvature; the standard fix is more warmup steps or a lower peak LR relative to batch size (larger batch generally tolerates higher LR, per the "linear scaling rule," but only up to a point).

### Q6 — What does `torch.compile` actually buy you, and what's the catch?
**Answer:** It traces the model into a graph, fuses elementwise operations, and generates specialized kernels (via Triton), cutting Python dispatch overhead and memory traffic between fused ops — roughly 2x throughput on A100/H100 for typical transformer training. The catch: the first call triggers compilation (can take tens of seconds to minutes depending on model size), and any change in input shape triggers *recompilation*, so variable-length batches without padding/bucketing can silently make training much slower than eager mode by recompiling every step.
**Follow-up trap:** *"How would you notice recompilation was happening in production?"* — per-step wall-clock time that doesn't stabilize after the first few steps, or `torch._dynamo` recompilation counters/logs; profiling tools like `torch.profiler` will show compilation frames repeating rather than one-time overhead at the start.

### Q7 — Why does the loss curve start near `ln(vocab_size)` and what does that number actually mean?
**Answer:** At initialization the model's output distribution over the vocabulary is close to uniform, so cross-entropy loss equals `-log(1/vocab_size) = log(vocab_size)`. For GPT-2's 50,257-token vocabulary, `ln(50257) ≈ 10.8`. Watching the very first loss value confirms the loss function, data pipeline, and label shifting are wired correctly before anything else is debugged.
**Follow-up trap:** *"Your loss starts at 14, way above 10.8. What's wrong?"* — the model is doing *worse* than uniform, which typically means a label/index bug — e.g., targets not properly shifted, or an off-by-one that has the model predicting a token far from its actual context, producing systematically overconfident wrong answers rather than the calibrated uncertainty a fresh random init should show.

### Q8 — Explain the depth-scaled initialization (`1/√(2·n_layer)`) and what breaks without it.
**Answer:** Each residual block adds its sublayer's output into the stream; if every block's output has roughly unit variance and nothing counteracts it, the stream's variance grows roughly linearly with depth (`N` blocks → variance ≈ `N`), pushing later layers' LayerNorm inputs into a regime that's harder to train through. Scaling the *output* projection of each attention and MLP sublayer by `1/√(2N)` keeps each block's marginal contribution small enough that the cumulative stream variance stays roughly constant regardless of `N`.
**Follow-up trap:** *"Would you notice this bug from the loss curve alone?"* — often not immediately; it typically shows up as slower convergence and a worse asymptotic loss at a given token budget rather than an outright NaN, which is exactly what makes it a dangerous silent bug — you need a paired ablation (same everything, with/without the scaling) to actually see the effect cleanly.

### Q9 — When would 8xH100 training actually be *slower* per-token than expected, despite correct code?
**Answer:** Communication overhead between GPUs (gradient all-reduce in data-parallel training) can bottleneck if the model is small relative to interconnect bandwidth — for a 124M model, gradients are small enough that all-reduce is cheap relative to compute, but as you scale batch size or GPU count without proportionally more compute per GPU, communication-to-compute ratio rises. Also: if the dataloader can't keep up (tokenization or disk I/O bound), GPUs sit idle waiting for the next batch — visible as GPU utilization well below 100% in `nvidia-smi` despite "the code being right."
**Follow-up trap:** *"How do you tell communication-bound from I/O-bound from actually-compute-bound?"* — profile with `torch.profiler` and look at the timeline: gaps between backward-finish and optimizer-step suggest all-reduce wait; gaps between step-finish and next-forward-start with GPU idle suggest dataloader starvation; neither gap present but throughput still below theoretical peak suggests kernel-level inefficiency (worth checking `torch.compile` is actually engaged and FlashAttention kernel is dispatching).

### Q10 — A colleague says "just double the model size, double the tokens, and it'll be strictly better." Is that always true within a fixed compute budget?
**Testing:** whether nanoGPT-scale intuition connects to `T05-pretraining`'s scaling laws.
**Answer:** Not for a *fixed* compute budget — the `6ND` relationship means doubling both `N` and `D` roughly quadruples compute, not doubles it, so within a fixed budget you're choosing a point on the Chinchilla-style tradeoff curve between "bigger model, less data" and "smaller model, more data," and the loss-optimal point for a given compute budget is a specific ratio, not "more of everything." Beyond a fixed budget, yes, more of both eventually helps, but training dynamics (LR schedule needs adjusting for a different token count, batch size scaling) don't come for free just from changing the config numbers.
**Follow-up trap:** *"So is the Chinchilla ratio still the right one to target in 2026?"* — no, and this is exactly the connection to `T05-pretraining`: production models in 2025-2026 are routinely trained far past the original Chinchilla-optimal ratio (deliberately "overtrained" relative to loss-per-FLOP optimality) because inference cost, not just training-loss-per-FLOP, is part of the real objective — a smaller, more-overtrained model that's cheaper to serve at scale can beat a "compute-optimal" one on total cost of ownership.

### Q11 — Your validation loss looks great, but a human reviewing samples says the outputs are repetitive and low quality. What's going on?
**Answer:** Loss and sample quality are correlated but not identical — a model can achieve low cross-entropy by learning strong local statistics (n-gram-level patterns, common phrase completions) without the outputs being coherent over longer spans, especially early in training or with a small/undertrained model. Also check the decoding strategy used to generate the samples: greedy decoding on an undertrained model tends to fall into repetition loops even when the underlying distribution (and hence loss) is reasonable — that's a sampling problem (see `T05-sampling`), not necessarily a training problem.
**Follow-up trap:** *"How do you separate a training problem from a sampling problem here?"* — compute the model's loss/perplexity on genuinely held-out text and compare against expected values for its scale (per scaling laws); if perplexity is in the expected range for its parameter/token budget, the repetition is a decoding artifact — try nucleus/top-p sampling with modest temperature before concluding the training run itself failed.

### Q12 — Design the from-scratch build for a candidate with only a single consumer GPU and two evenings. What do you actually have them build, and why?
**Testing:** synthesis and calibrated scope — this is what the lab in this module is designed to teach.
**Answer:** Start with the character-level Shakespeare model (minutes on CPU, faster on any GPU) to validate the entire pipeline correctness — data loading, causal masking, target shifting, loss computation, sampling — before spending any meaningful compute. Then scale to a small subword-tokenized model (a few million to low tens of millions of parameters) on a few hundred million tokens of a public corpus subset, targeting an overnight run, with `torch.compile`, bf16 autocast, gradient clipping, and a cosine schedule with warmup all present from the start rather than added later, because retrofitting them after a "does it train at all" pass means re-diagnosing which change fixed what. The learning objective is the debugging loop itself — reading a loss curve, catching a shape bug, verifying with a tiny-scale overfit test — not the final model's quality, which will not be competitive with any released checkpoint regardless.
**Follow-up trap:** *"They report the loss curve looks perfect but ask why the model can't hold a coherent conversation past two sentences."* — at this parameter count and token budget, that's expected, not a bug: coherence over long spans is one of the last capabilities to emerge with scale, and a candidate should be able to say confidently "this is a scale limitation, here's the loss/perplexity number that confirms the model trained correctly for its size" rather than assuming something is broken.

---

## Red flags that fail you

- Confusing training loss going down with the model being correct — never mentioning a held-out validation check or a generation sanity-check.
- Not knowing why weight tying exists, or dismissing it as "just saves memory."
- Claiming fp16 and bf16 are interchangeable for training stability.
- Unable to explain why gradient clipping and warmup exist, beyond "it's standard practice."
- Saying pre-norm vs post-norm is a stylistic choice with no stability implication.
- Not knowing the rough order of magnitude for GPT-2 (124M) reproduction cost/time in 2026.
- Treating `torch.compile` as strictly free with no compilation or shape-stability caveat.

---

## Cheat card

```
BLOCK           x = x + Attn(LN(x)); x = x + MLP(LN(x))          -- pre-norm, residual stream never overwritten
WEIGHT TYE      wte.weight == lm_head.weight  -- ~31% of GPT-2(124M) params, also improves quality
DEPTH INIT      scale attn/mlp output proj by 1/sqrt(2*n_layer)  -- keeps residual stream variance ~constant with depth
LOSS AT INIT    ~= ln(vocab_size)  (GPT-2: ln(50257) ~= 10.8)    -- sanity check #1, always verify this first
GPT-2 REPRO     124M, ~10B tokens, 6ND FLOPs ~= 7.4 EFLOPs, ~90min on 8xH100 (2026 kernels), ~$20-30
6ND RULE        FLOPs ~= 6 * N_params * D_tokens (2 fwd + ~4 bwd/misc)
PRECISION       bf16 autocast >> fp16 (narrow exponent range, silent NaN) on Ampere+
STABILITY       grad clip norm=1.0, warmup ~0.5-1% of steps, cosine decay, AdamW betas=(0.9,0.95)
COMPILE         torch.compile ~2x throughput; first call compiles; dynamic shapes = repeated recompile
TIER 1 LAB      char-level Shakespeare: minutes on CPU/T4, val loss ~1.4-1.5, proves pipeline correctness
TIER 2 LAB      small subword model, few hundred M tokens, overnight on one consumer GPU
SPEEDRUN        modded-nanogpt: 45min -> <2min via Muon optimizer, QK-norm, untied embed, smaller vocab
COMMON BUG      loss trends down but generation is garbage -> check target shift, causal mask, train/val leak
```

## Sources

- [karpathy/build-nanogpt](https://github.com/karpathy/build-nanogpt) — accessed 2026-07-28
- [karpathy/nanoGPT](https://github.com/karpathy/nanogpt) — accessed 2026-07-28
- [KellerJordan/modded-nanogpt](https://github.com/kellerjordan/modded-nanogpt) — accessed 2026-07-28
- [How the NanoGPT Speedrun WR dropped by 20% in 3 months](https://www.lesswrong.com/posts/j3gp8tebQiFJqzBgg/how-the-nanogpt-speedrun-wr-dropped-by-20-in-3-months) — accessed 2026-07-28
- [NanoGPT Speedrun — Prime Intellect](https://app.primeintellect.ai/speedrun/nanogpt) — accessed 2026-07-28

## Changelog
- 2026-07-28 — created
