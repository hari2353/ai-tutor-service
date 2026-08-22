# LoRA/QLoRA/DoRA + the RAG-vs-FT-vs-Prompt Decision Tree

> **Track:** T05 LLM Internals · **Time:** 3.0h · **Prereqs:** none · **Updated:** 2026-08-01
> **Module id:** `T05-finetuning` · **Tags:** training,critical

## The 30-second version

Full fine-tuning updates every parameter and needs roughly 16-18 bytes of GPU memory per parameter with Adam (weights, gradients, and two optimizer moments, mostly in fp32) — about 112-140 GB for a 7B model before you've loaded a single activation, which is why nobody does it on a single GPU. LoRA freezes the base weights and learns a low-rank update `ΔW = BA` where `B` is `d×r` and `A` is `r×k` with `r` far smaller than `d` or `k`, cutting trainable parameters by two to three orders of magnitude and the optimizer-state memory with them; QLoRA quantizes the frozen base to 4-bit NF4, adds double quantization of the quantization constants themselves, and pages the optimizer to CPU on memory spikes, which is what gets 70B fine-tuning onto a single 80 GB GPU. DoRA decomposes each weight into a magnitude scalar and a unit-norm direction, applies LoRA only to the direction, and closes most of the remaining quality gap to full fine-tuning at the same rank with zero added inference cost. None of this answers the question that actually matters in an interview: fine-tuning teaches a model *form and behavior* — output schema, tone, a reasoning style, an unusual tool-calling convention — it does not reliably teach it *facts*, because knowledge injected via gradient updates is stored diffusely across weights, degrades as training continues on other data, and has to be fully retrained every time the underlying facts change. If the failure looks like "the model doesn't know something" reach for retrieval; if it looks like "the model knows it but won't do what I told it in the format I need," reach for fine-tuning; and try a better prompt before either, because it costs nothing to test.

## Why this gets asked

The interviewer has watched a team spend a month and five figures of compute fine-tuning a model on their internal wiki to "give it knowledge," ship it, and then discover it still hallucinates internal policy the same way it did before, except now it also can't follow the output format it used to get right, because the training set skewed the model's general instruction-following in the process. They want to know if you understand fine-tuning as a tool with a specific job — reshaping behavior on a fixed skill, not injecting facts — and whether you can do the actual memory arithmetic that decides whether an approach is even feasible on the hardware you have, rather than reciting "use LoRA, it's more efficient" with no numbers behind it.

---

## Lineage: past → present → future

**What came before.** Before parameter-efficient fine-tuning existed as a category, adapting a pretrained model meant either full fine-tuning (updating every weight, requiring the full optimizer-state memory budget and a copy of the entire model per task if you wanted to serve multiple specializations) or feature extraction (freezing the backbone and training only a small task head on top, which works for classification but can't reshape how a generative model reasons or responds). Houlsby et al. (2019) introduced bottleneck adapters — small trainable modules inserted between frozen transformer layers — which cut trainable parameters dramatically but added inference latency because every forward pass now runs through the extra adapter layers sequentially. The pain that killed full fine-tuning as a default: a 70B model needs on the order of a terabyte of GPU memory to fine-tune with Adam, which puts it out of reach of anyone without a multi-node cluster, and serving a different fully-fine-tuned checkpoint per customer or task multiplies storage and deployment cost linearly with the number of specializations.

**Where it stands now.** Hu et al.'s LoRA (2021) reframed the adapter idea: instead of adding new layers, learn a low-rank *update* to existing weight matrices, which can be merged back into the original weights at inference time with zero added latency — this is the detail that made it the default over bottleneck adapters. QLoRA (Dettmers et al., 2023) extended this by quantizing the frozen base model to 4-bit NF4 and introducing paged optimizers, which is what took 65B/70B fine-tuning from "needs a multi-GPU node" to "runs on a single 48-80 GB GPU." DoRA (Liu et al., 2024, ICML oral) is the current refinement: standard LoRA, because it's a single low-rank additive update, tends to change a weight's magnitude and direction in a way that's structurally different from how full fine-tuning changes weights — DoRA decomposes the weight into magnitude and direction explicitly and applies LoRA only to direction, which empirically tracks full-FT's update pattern more closely and closes most of the remaining gap. As of 2025-2026, the live disagreement has moved from "LoRA vs full FT" (settled — LoRA/QLoRA is the default for anyone without a training cluster) to rank selection: earlier guidance favored small ranks (r=8-16) for cost, but 2025 research found intermediate ranks (32-64) give a better capacity/stability tradeoff for complex, multi-turn, or code-heavy tasks, and current practical guidance (2026) defaults to `r=16` with DoRA enabled and `target_modules="all-linear"` rather than the original paper's query/value-only targeting [How Does LoRA Fine-Tuning Work? — Mixpeek](https://mixpeek.com/guides/fine-tuning-with-lora-adapters) — accessed 2026-08-01. The RAG-vs-fine-tuning question is also largely settled in the literature and still routinely gotten wrong in practice: RAG outperforms fine-tuning alone for injecting new or long-tail knowledge, and a hybrid (RAG for facts, fine-tuning for behavior/format) beats either alone [Fine-Tuning vs. RAG for Multi-Hop QA with Novel Knowledge (arXiv:2601.07054)](https://arxiv.org/pdf/2601.07054) — accessed 2026-08-01.

**Where it's heading.** High confidence: multi-adapter serving (many LoRA adapters sharing one base model in memory, batched at inference time) is now standard in production serving stacks (vLLM, S-LoRA-style designs) and will keep displacing "one fine-tuned checkpoint per customer" as an operational pattern, because storage and swap cost scale with adapter size (megabytes) instead of model size (tens of gigabytes). Moderate confidence: DoRA-style decomposition and its successors (weight decomposition variants published through 2026, e.g. activation-space or eigenvector-based low-rank methods) will keep narrowing the LoRA-to-full-FT quality gap without giving back LoRA's memory savings — this is an active research area with new variants appearing every few months, so treat any specific successor as provisional rather than settled. Speculative: sub-4-bit base quantization combined with adapter training (2-bit QLoRA variants) is being published but is not yet a reliable production default — expect real quality regressions on anything beyond simple tasks until calibration methods mature further, and treat vendor claims of "full LoRA quality at 2-bit" with skepticism until you've measured it on your own eval set.

---

## Mental model

```
FULL FINE-TUNING                      LoRA / QLoRA / DoRA

  W (d x k, ALL trainable)              W (d x k, FROZEN, often quantized)
  every element updated                        +
  grad + 2 Adam moments                 ΔW = B (d x r) . A (r x k)
  per element                           only B, A trainable
                                         r << min(d, k)

  memory ~ 16-18 bytes/param            memory ~ 2-4 bytes/param (frozen W)
  (weights+grad+optimizer)              + tiny optimizer state for B,A only

DoRA additionally splits W into magnitude * direction, LoRA only touches direction:
  W = m * (V / ||V||_c)     m: learned per-column scalar magnitude
                            V: LoRA-adapted direction, columns normalized
```

Think of `W` as a fixed lookup table you're not allowed to rewrite wholesale. LoRA writes a small correction note (`BA`) on a sticky pad next to it, sized to be cheap to store and cheap to erase, and at inference time you can staple the note directly onto the table (merge) so reading it costs nothing extra. QLoRA just shrinks the table itself (4-bit) before you staple notes onto a *copy* you compute against. DoRA writes the correction as "make this row louder/quieter" (magnitude) versus "point this row a bit differently" (direction) instead of one blended correction, which turns out to match how full retraining actually changes the table more closely.

---

## How it actually works

### Full fine-tuning memory arithmetic, derived

Training with Adam requires, per trainable parameter: the parameter itself, its gradient, and Adam's two running moments (momentum, variance). In mixed precision, a common accounting is 2 bytes (bf16 param) + 2 bytes (bf16 grad) + 4 bytes (fp32 master-weight copy) + 4+4 bytes (fp32 Adam momentum + variance) ≈ **16-18 bytes/parameter**, before activations. Concretely, ignoring activation memory:

| Model | Params | Full FT (Adam, mixed precision) | LoRA (fp16 base + adapter) | QLoRA (4-bit NF4 base + adapter) |
|---|---|---|---|---|
| 7B | 7×10⁹ | ~112-140 GB | ~28 GB | ~12 GB |
| 13B | 13×10⁹ | ~210-235 GB | ~40-45 GB | ~16-20 GB |
| 70B | 70×10⁹ | ~1.1-1.4 TB | ~150 GB | ~35-48 GB |

[GPU VRAM Requirements to Fine-Tune LLMs in 2026 — Spheron](https://www.spheron.network/blog/gpu-vram-requirements-fine-tune-llm-2026/) — accessed 2026-08-01. Full fine-tuning of the 70B row needs a multi-node cluster; QLoRA's ~35-48 GB fits comfortably on a single 80 GB A100/H100. This table is the actual argument for LoRA/QLoRA — it isn't "more efficient" as an adjective, it's the difference between one consumer-adjacent GPU and a cluster.

### LoRA, derived

Instead of learning a full update `ΔW ∈ ℝ^{d×k}`, LoRA constrains it to rank `r`: `ΔW = BA`, with `B ∈ ℝ^{d×r}`, `A ∈ ℝ^{r×k}`, `r ≪ min(d,k)`. The forward pass becomes `h = Wx + \frac{α}{r} BAx`, where `α` is a scaling hyperparameter. `A` is initialized with small random values (Gaussian) and `B` is initialized to zero, so `ΔW = 0` at the start of training — the model starts out numerically identical to the frozen base and only diverges as training proceeds, which is why LoRA training is stable even with a "large" learning rate relative to full fine-tuning.

**Parameter reduction, worked example.** For a `4096×4096` attention projection matrix, full fine-tuning has `4096×4096 ≈ 16.8M` trainable parameters. At `r=8`, LoRA has `4096×8 + 8×4096 = 65,536` parameters — a **~256x reduction** for that matrix. Applied across all four attention projections and the MLP's linear layers ("all-linear" targeting), the aggregate trainable-parameter count for a 7B model at `r=16` typically lands around 0.1-0.5% of total parameters, which is what makes the Adam optimizer-state overhead (the 8 bytes/param that dominates full-FT memory) nearly disappear.

**Rank and alpha.** `α/r` is the effective scale applied to the low-rank update; keeping `α = r` (a scale of 1.0) is the simple, stable default. 2026 practical guidance: `r=16, α=16` with DoRA enabled and `target_modules="all-linear"` as a starting configuration, moving to `r=32-64` for complex multi-turn or code tasks where 2025 research found intermediate ranks give a better capacity/stability tradeoff than the smaller ranks the original 2021 guidance favored [Master LoRA and QLoRA — Let's Data Science](https://letsdatascience.com/blog/fine-tuning-llms-with-lora-and-qlora-complete-guide) — accessed 2026-08-01. **Target modules matter more than rank in practice**: the original LoRA paper only adapted the query and value attention projections; adapting all linear layers (attention *and* MLP up/down/gate projections) closes noticeably more of the gap to full fine-tuning, especially on tasks that stress the MLP's capacity (code, math, multi-step reasoning).

### QLoRA: NF4, double quantization, paged optimizers

QLoRA keeps the base model frozen and quantized, and trains only bf16 LoRA adapters on top — three specific tricks make this work without destroying quality:

1. **NF4 (4-bit NormalFloat).** A quantization data type whose quantization bins are placed at the quantiles of a standard normal distribution rather than linearly spaced, because pretrained weights are empirically close to zero-centered and normally distributed — this is information-theoretically better than a linear 4-bit grid for weights that actually follow that distribution, and is the core reason naive linear INT4 loses more quality than NF4 at the same bit width.
2. **Double quantization.** Quantizing to 4-bit still needs a per-block scaling constant (typically one 32-bit float per 64-weight block) to map the quantized values back to real numbers, and those scaling constants themselves take non-trivial memory at scale. Double quantization quantizes *those constants* to 8-bit, saving roughly **0.37 bits per parameter — about 3 GB on a 65B model** — a genuinely free reduction with negligible quality cost, because you're compressing metadata, not the weights themselves.
3. **Paged optimizers.** Built on NVIDIA unified memory, this automatically pages optimizer states out to CPU RAM when a GPU memory spike would otherwise OOM (these spikes happen with gradient checkpointing, where activation recomputation briefly needs extra memory), and pages them back when the spike passes. This trades a latency hit during paging events for the ability to fine-tune at all on hardware that would otherwise OOM on a rare spike rather than steady-state usage.

The result: a 65B model that needed >780 GB for full 16-bit fine-tuning fits on a single 48 GB GPU with QLoRA at effectively no measured quality regression versus full 16-bit fine-tuning on the benchmarks in the original paper.

### DoRA: decomposing magnitude from direction

DoRA rewrites a weight matrix as `W = m \cdot \frac{V}{\lVert V \rVert_c}`, where `m` is a learned per-column magnitude vector and `V/\lVert V\rVert_c` is the column-normalized direction. Full fine-tuning is free to change both magnitude and direction independently and does so in a characteristic pattern; a single additive low-rank update (plain LoRA) tends to change magnitude and direction together in a way that doesn't match that pattern as closely. DoRA freezes nothing conceptually different from LoRA in terms of trainable parameter count — it applies LoRA only to the direction component `V` while separately learning the magnitude vector `m` — and because both pieces are still simple linear compositions of the frozen base, the whole thing merges back into a single weight matrix at inference time exactly like plain LoRA, at **zero added inference latency**. Reported result: DoRA consistently outperforms LoRA at matched rank across LLaMA (commonsense reasoning), LLaVA, and VL-BART benchmarks [DoRA (arXiv:2402.09353)](https://arxiv.org/abs/2402.09353) — accessed 2026-08-01, and it's now integrated into Hugging Face PEFT as a flag on standard LoRA config rather than a separate library.

### Serving many adapters

Because a merged LoRA/DoRA adapter is just a small delta on top of a shared frozen base, you don't need a full model copy per fine-tuned task or customer. Modern serving stacks (vLLM's multi-LoRA support, and the S-LoRA design it draws from) keep one copy of the base model resident and dynamically apply different adapters per request via batched matrix operations, so a single GPU can serve **hundreds to thousands of distinct LoRA adapters** with throughput close to serving the base model alone, because the adapter matmuls are tiny relative to the base forward pass. This only works because the adapters stay unmerged and are applied at batch-time; a naive design that reloads or re-merges the model per adapter switch reintroduces exactly the deployment cost multi-adapter serving is meant to eliminate.

### Catastrophic forgetting

Fine-tuning on a narrow distribution shifts the model toward that distribution's style and content, and the further and longer training pushes in that direction, the more it degrades on capabilities the training data didn't reinforce — a model heavily fine-tuned on customer-support transcripts can measurably regress on general instruction-following or unrelated reasoning benchmarks it handled fine before. LoRA and other PEFT methods forget measurably less than full fine-tuning at matched task performance, because the frozen base weights (where most general capability lives) are untouched and the low-rank update has less capacity to overwrite them broadly [LoRA Learns Less and Forgets Less (arXiv:2405.09673)](https://arxiv.org/pdf/2405.09673) — accessed 2026-08-01. This cuts both ways: "learns less" means LoRA at low rank can genuinely underperform full FT on tasks that need real new capability (heavy code or math skill acquisition), which is part of why 2025-2026 guidance shifted toward higher ranks (32-64) for exactly those task types.

### The RAG-vs-fine-tuning-vs-prompt decision tree

This is the question that actually separates a senior engineer from someone who fine-tunes reflexively.

```
Is the failure "the model doesn't know a fact / info is out of date / needs a citation"?
  │
  ├─ YES ──▶ RETRIEVAL (RAG). Facts belong in a retrievable store you can update
  │          without retraining, and retrieval gives you provenance fine-tuning
  │          cannot: you can point to the source chunk that produced the answer.
  │
  └─ NO — the model "knows" the domain but does the wrong THING with it
     (wrong format, wrong tone, ignores an instruction pattern, wrong reasoning
      style, wrong tool-call convention, too verbose for a cost-sensitive path)
       │
       ├─ Can a better prompt / few-shot examples fix it within your latency
       │  and context budget? ──▶ TRY THIS FIRST. Zero training cost, reversible
       │  in one deploy, and most "we need to fine-tune" tickets die here.
       │
       └─ Prompting hits a ceiling (indefinitely repeated behavior, output-
          schema compliance that must be load-bearing, or per-call prompt/
          token cost at volume makes a long system prompt genuinely expensive)?
            │
            ├─ Do you have 1,000+ high-quality, diverse, curated examples of
            │  the desired behavior, with a held-out eval set?
            │    ├─ NO  ──▶ Don't fine-tune yet. Collect data, or fall back to
            │    │          prompting/RAG while you do.
            │    └─ YES ──▶ FINE-TUNE (LoRA/QLoRA by default; full FT only if
            │               you have the cluster and a proven need for it).
```

The classic mistake this tree exists to prevent: fine-tuning to inject knowledge. It fails in a specific, observable way — the model can recite training-set facts verbatim right after training, then confidently states a stale or fabricated version of the same fact a few months later once the underlying reality has moved on, because the "knowledge" was baked into weights at a point in time and every update requires a full retrain. Retrieval doesn't have this failure mode: update the index, and the next query sees the new fact immediately.

### Data requirements and quality thresholds

Rule of thumb repeatedly confirmed in practice: **1,000 hand-curated, diverse examples routinely beat 100,000 noisy or repetitive ones.** Quality signals that matter more than raw count: coverage of edge cases and failure modes you've actually observed (not just the happy path), consistent labeling/formatting across examples (inconsistency in the training signal directly becomes inconsistency in model behavior), and a held-out eval set drawn from the same distribution *plus* a genuinely out-of-domain probe set to catch overfitting the in-distribution set won't reveal. A model that scores well on a held-out split from the same narrow source but regresses on general capability probes is overfit to the training distribution's superficial patterns, not the underlying task.

---

## Build it from scratch

Minimal LoRA linear layer — the mechanism underlying every LoRA/QLoRA/DoRA library:

```python
import torch
import torch.nn as nn

class LoRALinear(nn.Module):
    """Wraps a frozen linear layer with a trainable low-rank update."""
    def __init__(self, base: nn.Linear, r: int = 16, alpha: int = 16):
        super().__init__()
        self.base = base
        for p in self.base.parameters():
            p.requires_grad = False          # freeze the base weight

        d_out, d_in = base.weight.shape
        self.A = nn.Parameter(torch.randn(r, d_in) * 0.01)   # small random init
        self.B = nn.Parameter(torch.zeros(d_out, r))          # zero init -> delta W = 0 at start
        self.scale = alpha / r

    def forward(self, x):
        base_out = self.base(x)
        lora_out = (x @ self.A.T) @ self.B.T * self.scale
        return base_out + lora_out

    def merge(self):
        """Fold the adapter into the base weight for zero-overhead inference."""
        with torch.no_grad():
            self.base.weight += (self.B @ self.A) * self.scale
        return self.base   # now a plain nn.Linear, adapter gone, output identical
```

A minimal DoRA sketch layered on the same idea:

```python
# untested sketch -- illustrates magnitude/direction decomposition, not a full training loop
class DoRALinear(nn.Module):
    def __init__(self, base: nn.Linear, r: int = 16, alpha: int = 16):
        super().__init__()
        self.base = base
        for p in self.base.parameters():
            p.requires_grad = False
        d_out, d_in = base.weight.shape
        self.A = nn.Parameter(torch.randn(r, d_in) * 0.01)
        self.B = nn.Parameter(torch.zeros(d_out, r))
        self.scale = alpha / r
        # learned magnitude, initialized to match the frozen base's column norms
        self.m = nn.Parameter(base.weight.norm(dim=1, keepdim=True).clone())

    def forward(self, x):
        delta = (self.B @ self.A) * self.scale
        direction = self.base.weight + delta
        direction = direction / direction.norm(dim=1, keepdim=True)  # unit-norm direction
        w_eff = self.m * direction
        return x @ w_eff.T
```

Full training loop with 4-bit NF4 quantization of the base and a paged-AdamW optimizer is what `bitsandbytes` + Hugging Face `peft` provide; the mechanism above is what they're doing under the hood.

---

## How it's done in production

| Layer | What you actually use | What it adds |
|---|---|---|
| Adapter library | Hugging Face `peft` (LoRA, QLoRA, DoRA, AdaLoRA config flags) | Standardized config, merge/unmerge, checkpoint format |
| Base quantization | `bitsandbytes` (NF4, double quant) | The 4-bit frozen base QLoRA depends on |
| Training orchestration | Axolotl, TRL (`SFTTrainer`), LLaMA-Factory | Dataset formatting, multi-GPU/DeepSpeed/FSDP config, packing |
| Multi-adapter serving | vLLM (`--enable-lora`), S-LoRA-style designs | One resident base model, many adapters batched per request |

### Failure modes

| Symptom | Cause | Fix |
|---|---|---|
| Fine-tuned model recites training-set facts correctly at launch, then gives stale or fabricated answers to the same questions months later | Facts injected via fine-tuning instead of retrieval; knowledge is frozen at training time | Move factual grounding to RAG; keep fine-tuning for format/behavior only |
| General instruction-following or unrelated-domain quality visibly regresses after a task-specific fine-tune | Catastrophic forgetting from full FT (or LoRA at too-high rank/too-long training) on a narrow distribution | Prefer LoRA at a moderate rank, cap training epochs, mix in a slice of general instruction data, eval on an out-of-domain probe set before shipping |
| LoRA adapter plateaus well below full-FT quality on a code or math task | Rank too low for the task's actual capacity needs, or adapter only targets attention Q/V, not MLP layers | Raise rank to 32-64, set `target_modules` to all linear layers, not just attention |
| Training OOMs intermittently, not at a fixed step | Gradient-checkpointing activation-recompute spikes exceed available GPU memory | Enable paged optimizer (QLoRA/bitsandbytes paged AdamW) so spikes page to CPU instead of OOMing |
| Merged adapter has almost no effect on outputs | `alpha/r` scaling wrong (e.g., merged with a different alpha than trained with) or `B` never diverged from its zero init because learning rate was too low for the adapter parameters specifically | Verify the same `alpha/r` used at train and merge time; confirm adapter-specific learning rate isn't drowned out by a schedule tuned for full-FT magnitudes |
| Serving latency spikes badly when switching between customer-specific fine-tunes | Naive per-adapter serving reloads or re-merges the full model on each switch | Use a multi-LoRA-aware server (vLLM `--enable-lora` or equivalent) that keeps one base resident and batches adapter application |

---

## Tradeoffs & when NOT to use it

- **Never fine-tune to inject knowledge that changes on any cadence shorter than your retraining cycle.** Prices, policies, personalized user data, anything with a "last updated" date — put it in a retrieval store, not in weights.
- **Don't fine-tune before trying a better prompt.** A large fraction of "the model won't follow our format" tickets are solved by a clearer system prompt and two or three good few-shot examples, at zero training cost and same-day iteration speed; fine-tuning locks in a specific behavior and every future tweak requires a new training run.
- **Don't fine-tune on fewer than a few hundred genuinely high-quality, diverse examples.** You'll overfit to the training distribution's incidental patterns (a repeated phrase, a narrow topic slice) rather than learning the intended general behavior, and it won't show up until you test out-of-domain.
- **Don't reach for full fine-tuning by default.** Unless you specifically need every parameter free to move (rare — usually only justified by a very large, very diverse dataset and a proven LoRA quality ceiling on your task), LoRA/QLoRA gets most of the benefit at a fraction of the memory and with measurably less catastrophic forgetting.
- **Fine-tuning is the wrong lever if your actual problem is retrieval quality.** If the model is getting facts wrong because the retriever surfaced the wrong chunk, no amount of fine-tuning the generator fixes a retrieval-side failure; you'll spend a training budget "fixing" a symptom while the retriever keeps returning the wrong evidence.
- **When you do need to inject a large body of stable, rarely-changing domain knowledge that's too big for any practical context window** (e.g., an entire internal codebase's idioms, not individual current facts) — that's the genuinely gray zone where continued pretraining or heavy fine-tuning on domain text can pay off, but validate it against a strong RAG baseline first; RAG plus a good retriever frequently wins on cost and freshness even here.

---

## Interview questions

### Q1 — Walk through the memory arithmetic for full fine-tuning a 7B model with Adam, and why LoRA changes that number.
**Testing:** whether the candidate can derive the number, not just quote "LoRA is more efficient."
**Answer:** Full fine-tuning with Adam needs roughly 16-18 bytes per trainable parameter (bf16 weight + bf16 grad + fp32 master weight + fp32 Adam momentum + fp32 Adam variance), so a 7B model needs on the order of 112-140 GB before activations — out of reach for a single GPU. LoRA freezes the base weights (2 bytes/param, no gradient or optimizer state needed for them) and only allocates optimizer state for the tiny adapter matrices, dropping total memory to roughly 28 GB for the same model.
**Follow-up trap:** *"Where did the activation memory go in this calculation?"* — it's separate and additive; the 16-18 bytes/param figure is weights+gradients+optimizer state only, and activation memory scales with batch size and sequence length independently, which is why gradient checkpointing (trading recompute for activation memory) matters on top of any of these approaches.

### Q2 — Derive the parameter count for a LoRA adapter on a 4096x4096 weight matrix at rank 8, and compare to full fine-tuning of that matrix.
**Answer:** Full fine-tuning: 4096×4096 ≈ 16.8M parameters. LoRA at r=8: `B` is 4096×8, `A` is 8×4096, total `4096×8 + 8×4096 = 65,536` parameters — about a 256x reduction for that single matrix.
**Follow-up trap:** *"Does that reduction hold if you apply LoRA to every linear layer instead of just attention Q/V?"* — the per-matrix ratio holds, but 2026 practical guidance targets all linear layers (`target_modules="all-linear"`) rather than only Q/V, because closing the gap to full FT on complex tasks needs the MLP's capacity too — so total trainable parameters go up from the original paper's Q/V-only setup, while still remaining well under 1% of the model.

### Q3 — What does QLoRA add beyond plain LoRA, mechanically?
**Answer:** Three things: NF4 quantization of the frozen base (4-bit bins placed at quantiles of a standard normal, which fits pretrained weight distributions better than a linear 4-bit grid), double quantization (quantizing the per-block scaling constants themselves to 8-bit, saving ~0.37 bits/parameter, ~3 GB on a 65B model), and paged optimizers (NVIDIA unified memory pages optimizer state to CPU RAM during gradient-checkpointing memory spikes instead of OOMing).
**Follow-up trap:** *"Does NF4 quantization affect the LoRA adapter itself?"* — no, only the frozen base is quantized to 4-bit; the LoRA adapter matrices (`A`, `B`) are trained and stored in bf16/fp16, which is why QLoRA can match near-full-precision fine-tuning quality despite the base being 4-bit.

### Q4 — What is DoRA and why doesn't it add inference latency?
**Answer:** DoRA decomposes a weight into a learned magnitude vector and a unit-norm direction, and applies LoRA only to the direction component while separately learning the magnitude. It doesn't add inference latency because, like plain LoRA, the whole decomposition is a composition of linear operations on the frozen base that can be algebraically merged back into a single weight matrix before serving — there's no extra runtime computation once merged.
**Follow-up trap:** *"If it merges the same way as LoRA, why does it perform better?"* — the *training dynamics* differ, not the inference cost: full fine-tuning changes magnitude and direction somewhat independently, and DoRA's explicit decomposition lets the low-rank update track that pattern more closely than a single blended additive update can, which is a training-time quality effect, not a serving-time one.

### Q5 — A team fine-tuned a model on customer support transcripts and now it performs worse on general coding questions it used to handle fine. What happened and how do you prevent it?
**Testing:** naming catastrophic forgetting with a concrete mechanism, not just the term.
**Answer:** Catastrophic forgetting — training pushed the weights toward the narrow support-transcript distribution and, in the process, degraded capability the training data never reinforced. Prevent it by preferring LoRA/QLoRA over full fine-tuning (frozen base weights preserve more general capability), capping training epochs, mixing a slice of general instruction data into the fine-tuning set, and evaluating on an out-of-domain probe set before shipping, not just a held-out split of the support transcripts.
**Follow-up trap:** *"Does using LoRA guarantee you won't see this?"* — no, it reduces the risk but doesn't eliminate it, especially at high rank or long training; "LoRA learns less and forgets less" is an empirical tendency, not a guarantee, so you still need the out-of-domain eval.

### Q6 — Your manager says "let's fine-tune the model on our product documentation so it knows our product." What's your response?
**Testing:** the central decision-tree question — do they reach for RAG or FT correctly.
**Answer:** Push back toward retrieval. Fine-tuning on documentation to inject facts is the classic mistake this decision tree exists to prevent: the model will recite the docs reasonably well right after training, then give stale or fabricated answers as the docs change, because the "knowledge" is frozen in weights at training time. Put the documentation in a retrieval index instead, so updates take effect immediately with no retraining, and you get citations/provenance for free. Fine-tuning stays on the table if the actual problem is that the model, given the right retrieved context, still answers in the wrong format or tone.
**Follow-up trap:** *"What if the documentation almost never changes?"* — even then, RAG usually still wins on cost (no training run) and provenance (you can point to the source paragraph); fine-tuning-for-static-knowledge is only worth considering when the corpus is too large to ever fit in any practical retrieval-augmented context and you've already validated a strong RAG baseline underperforms it on your actual eval.

### Q7 — How much training data do you actually need before fine-tuning is worth attempting?
**Answer:** Rule of thumb: 1,000 hand-curated, diverse examples routinely outperform 100,000 noisy ones. Below a few hundred genuinely high-quality examples, you're at real risk of overfitting to incidental patterns in the small set rather than learning the intended general behavior, and it often won't show up until you test out-of-domain.
**Follow-up trap:** *"What if you have 100,000 examples but they're all near-duplicates of a handful of patterns?"* — that's effectively a small dataset with padding; diversity of the underlying patterns matters more than raw row count, and a held-out split from the same source won't catch this — you need an out-of-domain or deliberately varied eval set to detect it.

### Q8 — Explain how vLLM (or a similar server) serves thousands of LoRA adapters on one GPU without loading a full model copy per adapter.
**Answer:** The base model stays resident once; each adapter is a small pair of low-rank matrices applied per-request via batched matrix operations rather than merged into a separate full copy of the weights. Because the adapter matmuls are tiny relative to the base model's forward pass, the server can batch requests targeting different adapters together and pay almost no throughput penalty versus serving the base model alone.
**Follow-up trap:** *"What breaks this if you naively merge each adapter into the base weights before serving?"* — merging produces a full-size model copy per adapter, which reintroduces the exact per-tenant storage and swap cost multi-adapter serving exists to avoid; keep adapters unmerged and applied at batch time for multi-tenant serving specifically.

### Q9 — When is full fine-tuning actually the right call over LoRA/QLoRA?
**Answer:** When you have a very large, diverse, high-quality dataset, a proven quality ceiling with LoRA even at higher rank on your specific task (usually something requiring deep capability acquisition like a new skill far from pretraining data, not just style adaptation), and the compute budget/cluster to support it. It's rare in practice — most production fine-tuning needs are style, format, or narrow-task specialization, which LoRA/QLoRA handles at a fraction of the cost.
**Follow-up trap:** *"How would you actually prove LoRA has hit a ceiling before committing to a full-FT run?"* — sweep rank upward (e.g., 16 → 32 → 64) and target more modules (all-linear, not just Q/V); if quality keeps improving with more LoRA capacity, you haven't hit LoRA's ceiling, you've just been under-provisioning it — only escalate to full FT once increasing LoRA capacity stops helping.

### Q10 — What's the risk of picking too high a LoRA rank versus too low?
**Answer:** Too low: the adapter lacks capacity for the task, and you see a quality plateau below full-FT performance, especially on tasks needing real new capability (code, math, multi-step reasoning) — 2025 research favors intermediate ranks (32-64) over the smaller 8-16 range for exactly these cases. Too high: you approach full-fine-tuning's parameter count and its forgetting/overfitting risk without the corresponding memory savings that make LoRA attractive in the first place, and training becomes less stable.
**Follow-up trap:** *"Is there a clean rule for picking rank, or do you have to sweep it?"* — no clean rule; the 2026 default of r=16 with DoRA is a reasonable starting point, but the right rank is task-dependent, and the honest answer is you sweep a small range and check both held-out task performance and an out-of-domain forgetting probe, not just training loss.

### Q11 — A colleague proposes fine-tuning a model to shorten your production system prompt and few-shot examples, purely for cost. Is that a legitimate use of fine-tuning?
**Testing:** whether the candidate over-generalizes "don't fine-tune for knowledge" into "never fine-tune."
**Answer:** Yes — this is a legitimate and common use case, because it's not knowledge injection, it's distilling a *behavior pattern* (the instruction-following and formatting that the long prompt was inducing) into weights so every production call pays for fewer tokens. This is squarely "teaching form and behavior," which is exactly what fine-tuning is good at, as long as the underlying facts the prompt/examples referenced aren't themselves the thing being memorized.
**Follow-up trap:** *"What would make this go wrong?"* — if the few-shot examples embedded specific facts (prices, current policies) rather than pure format/behavior patterns, fine-tuning on them re-introduces the knowledge-injection failure mode by the back door; audit what's actually in the examples before assuming it's pure behavior.

### Q12 — Design the fine-tuning approach for a support-ticket triage model: classify ticket urgency and route to the right team, using a company's historical ticket data.
**Testing:** synthesis — applying the decision tree, data thresholds, and rank/target-module choices together.
**Answer:** This is squarely a fine-tuning use case, not RAG: it's a stable, well-defined classification/routing behavior, not a knowledge-lookup task. Start by checking whether a strong prompt with a handful of labeled examples (few-shot) already hits the required accuracy — if it does, ship that and skip training entirely. If not, and there are at least ~1,000 diverse, correctly-labeled historical tickets covering the actual urgency/routing edge cases (not just the common case), fine-tune with QLoRA at r=16-32, targeting all linear layers, holding out a genuinely time-later slice of tickets (not a random split) as eval to catch temporal drift in ticket patterns. Re-validate periodically since routing categories and team structures change over time — this is itself a "knowledge that changes" risk, just on the label space rather than the input facts.
**Follow-up trap:** *"Your holdout accuracy is 95% but production routing complaints haven't dropped. What do you check first?"* — check whether the holdout set's label distribution matches current production ticket patterns; a randomly-split eval set drawn from the same historical window as training data can look great while missing a shift in ticket types or team structure that happened after that window — this is the same "eval set went stale" failure that shows up in any offline eval, and it's exactly why a temporally-held-out eval set matters more than a random split for this task.

---

## Red flags that fail you

- Proposing fine-tuning to fix "the model doesn't know X" without mentioning retrieval as the default alternative.
- Not being able to produce the full-FT memory arithmetic (16-18 bytes/param) or explain why LoRA reduces it.
- Calling QLoRA "just quantized LoRA" without naming double quantization or paged optimizers specifically.
- Believing DoRA adds inference latency because it's "doing more."
- Recommending full fine-tuning by default without checking whether LoRA at higher rank/broader target modules already closes the gap.
- Not knowing that a merged LoRA/DoRA adapter costs zero extra inference latency.
- Treating "we have lots of data" as sufficient justification without checking data quality/diversity.

---

## Cheat card

```
FULL FT MEMORY   ~16-18 bytes/param (Adam, mixed precision): bf16 w + bf16 grad
                 + fp32 master + fp32 momentum + fp32 variance
                 7B ~112-140GB | 13B ~210-235GB | 70B ~1.1-1.4TB (no activations)

LoRA / QLoRA     7B: LoRA ~28GB, QLoRA ~12GB | 70B: LoRA ~150GB, QLoRA ~35-48GB
                 (fits 70B QLoRA on a single 80GB GPU)

LORA FORMULA     h = Wx + (alpha/r) * B A x ; B init 0, A init small random
                 -> delta W = 0 at step 0, stable start
PARAM REDUCTION  4096x4096 full FT = 16.8M params; LoRA r=8 = 65,536 (~256x fewer)

QLORA TRICKS     NF4: 4-bit bins at normal-distribution quantiles (fits weight stats)
                 double quant: quantizes the scaling constants -> ~0.37 bit/param,
                   ~3GB saved on 65B
                 paged optimizer: pages Adam state to CPU RAM on GC memory spikes

DORA             W = m * (V / ||V||); LoRA applied to direction V only, m learned
                 separately -> merges like LoRA -> ZERO added inference latency

RANK/TARGET      2026 default: r=16, alpha=16, DoRA on, target_modules=all-linear
                 r=32-64 for code/math/multi-turn (2025 research: mid-rank wins)

FORGETTING       LoRA forgets less than full FT (arXiv:2405.09673) but "learns less"
                 too -> low rank underfits hard tasks, raise rank before blaming LoRA

MULTI-ADAPTER    vLLM --enable-lora / S-LoRA: 1 resident base, 100s-1000s adapters
                 batched per request, ~base-model throughput

DATA THRESHOLD   1,000 curated examples > 100,000 noisy ones (rule of thumb)
                 eval on OUT-OF-DOMAIN probe, not just held-out same-source split

DECISION TREE    doesn't know a fact -> RAG
                 knows it, wrong form/tone/format -> prompt first, then fine-tune
                 classic mistake: fine-tuning to inject knowledge -> stale, no
                   provenance, needs full retrain per fact change
```

## Sources

- [How Does LoRA Fine-Tuning Work? (Adapters, QLoRA, DoRA) — Mixpeek](https://mixpeek.com/guides/fine-tuning-with-lora-adapters) — accessed 2026-08-01
- [Master LoRA and QLoRA: Fine-Tuning LLMs on Consumer GPUs — Let's Data Science](https://letsdatascience.com/blog/fine-tuning-llms-with-lora-and-qlora-complete-guide) — accessed 2026-08-01
- [GPU VRAM Requirements to Fine-Tune LLMs in 2026 — Spheron](https://www.spheron.network/blog/gpu-vram-requirements-fine-tune-llm-2026/) — accessed 2026-08-01
- [DoRA: Weight-Decomposed Low-Rank Adaptation (arXiv:2402.09353)](https://arxiv.org/abs/2402.09353) — accessed 2026-08-01
- [LoRA Learns Less and Forgets Less (arXiv:2405.09673)](https://arxiv.org/pdf/2405.09673) — accessed 2026-08-01
- [Fine-Tuning vs. RAG for Multi-Hop Question Answering with Novel Knowledge (arXiv:2601.07054)](https://arxiv.org/pdf/2601.07054) — accessed 2026-08-01
- [RAG vs Fine Tuning: Enterprise Decisions for AI Models and AI Systems — Databricks](https://www.databricks.com/blog/rag-vs-fine-tuning) — accessed 2026-08-01

## Changelog
- 2026-08-01 — created
