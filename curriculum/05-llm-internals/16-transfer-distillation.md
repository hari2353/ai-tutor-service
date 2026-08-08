# Transfer Learning & Distillation: Feature Extraction, Full FT, Teacher-Student

> **Track:** T05 LLM Internals · **Time:** 2.0h · **Prereqs:** none · **Updated:** 2026-08-01
> **Module id:** `T05-transfer-distillation` · **Tags:** training,critical

## The 30-second version

Transfer learning works because a network trained on a large, diverse task learns hierarchical features — early layers general (edges, syntax, subword co-occurrence), late layers task-specific (this class, this sentiment) — so you can reuse the general layers and only relearn the specific ones on far less data than training from scratch would need. The spectrum from frozen-feature-extraction through partial unfreezing to full fine-tuning to PEFT (LoRA/QLoRA) is a single dial trading adaptation power against overfitting risk and compute cost, and you pick a point on it based on dataset size and domain distance from pretraining, not by default going straight to full fine-tuning. Knowledge distillation is the orthogonal move: instead of adapting one model to a new task, you train a small "student" to match a large "teacher's" output distribution — including its softened, temperature-scaled probabilities over *wrong* answers — because those probabilities carry more information than a one-hot hard label ever could. DistilBERT gets 97% of BERT's GLUE performance at 40% of the size and 60% of the latency; that ratio, not the exact numbers, is what you should be able to reproduce cold. The one thing that actually kills distillation projects in production isn't the math, it's the provider terms of service: several frontier labs' ToS explicitly prohibit using their model's outputs to train a competing model, and that clause has already produced a real, public legal dispute.

## Why this gets asked

The interviewer has been on a team that either fine-tuned a model on too little data and watched it catastrophically forget everything it used to know, or shipped a giant model to production because "fine-tuning our own smaller one seemed like extra work," and paid for that decision every month in inference cost. They want to know if you can pick the right point on the adaptation spectrum given a dataset size and a latency/cost budget, and whether you understand distillation as a genuine training technique with real numbers behind it rather than a buzzword for "make the model smaller somehow."

---

## Lineage: past → present → future

**What came before.** Pre-transfer-learning, every new task meant training a model from random initialization on task-specific labeled data alone. The pain was structural: deep networks need enormous data to learn good low-level features from scratch, and most real tasks don't have enormous labeled data, so models underfit or overfit depending on capacity, and every team re-solved "learn what an edge looks like" or "learn what a common English bigram looks like" independently, wastefully, per project. ImageNet pretraining (2012 onward, AlexNet and successors) was the first widely reproduced proof that features learned on a large, generic task transfer to specific ones — a model trained on 1.2M images could be fine-tuned on a few thousand task-specific images and beat a model trained on those few thousand alone. NLP lagged behind vision by several years because word2vec/GloVe only transferred word-level features, not sentence- or document-level structure; ELMo and then BERT (2018) closed that gap by making the pretrained-then-fine-tuned pattern work for language, and it's been the dominant recipe since.

**Where it stands now.** The adaptation spectrum is well understood and the consensus is to pick based on two variables: dataset size and domain distance from pretraining. Small dataset + close domain → freeze the base, train only a new head (feature extraction). Small dataset + far domain → this is the hard case, usually solved by partial unfreezing of late layers plus heavy regularization, or by not fine-tuning at all and using in-context learning instead. Large dataset + either domain → full fine-tuning becomes viable and often best. The genuinely new development since ~2021 is **PEFT (Parameter-Efficient Fine-Tuning)** — LoRA, QLoRA, adapters — which inserts small trainable matrices into a frozen base and full-fine-tunes only those, closing most of the gap to full fine-tuning's quality at a fraction of the trainable-parameter count and memory footprint (`T05-finetuning` covers LoRA/QLoRA mechanics and the RAG-vs-FT-vs-prompt decision tree in depth; this module doesn't re-derive that). On distillation, the live disagreement isn't whether it works — DistilBERT and TinyBERT settled that with published, reproducible numbers years ago — it's about **licensing**. OpenAI's terms of service explicitly prohibit using its models' outputs to develop a competing model [OpenAI-US House Select Committee memo](https://cdn.openai.com/pdf/045aa967-ee96-4a09-94ee-3098ddf6db2c/OpenAI-US-House-Select-Cmte-Update-%5B021226%5D.pdf) — accessed 2026-08-01, and OpenAI has alleged DeepSeek violated exactly this clause using obfuscated third-party routers to extract outputs for distillation at scale [Berkeley Law — The Innovation Dilemma](https://sites.law.berkeley.edu/thenetwork/2025/03/30/the-innovation-dilemma-ai-distillation-in-openai-v-deepseek/) — accessed 2026-08-01. Anthropic, Mistral, and xAI carry similar anti-competitive-distillation clauses in their terms of use [law.asia — dispute over distillation tech](https://law.asia/openai-deepseek-ai-distillation/) — accessed 2026-08-01. This is now a live commercial and legal risk, not a theoretical footnote.

**Where it's heading.** High confidence: PEFT methods keep displacing full fine-tuning as the default for adapting large models, because the memory and cost savings are too large to ignore for anything short of fundamentally changing a model's capabilities. Moderate confidence: distillation from your own fine-tuned large model into a small deployed model (self-distillation, no third-party ToS issue) becomes a standard step in the model-deployment pipeline rather than a research technique, precisely because the licensing risk of distilling *someone else's* frontier model is now well-publicized and legally contested. Speculative: whether labs move toward technical hardening against distillation (output watermarking, rate-limiting patterns consistent with training-data extraction) as a durable countermeasure, or whether this remains primarily a contractual/legal deterrent rather than a technical one — OpenAI has stated it's taken steps to harden against distillation, but the effectiveness of purely technical countermeasures against a determined extractor is unproven.

---

## Mental model

```
THE ADAPTATION SPECTRUM (one dial, more freedom -> right)

 FROZEN FEATURES        PARTIAL UNFREEZE       FULL FINE-TUNE         PEFT (LoRA/QLoRA)
 freeze all base        freeze early layers,    train every            freeze base entirely,
 layers, train only     unfreeze + train        parameter              inject small trainable
 a new head             late layers + head                             low-rank matrices,
                                                                        train only those
 -----------------------------------------------------------------------------------------
 least compute,         middle ground           most adaptation        near-full-FT quality,
 least data needed,     -                       power, most data       far less memory/compute
 least adaptation                                needed, highest       than full FT
 power                                           catastrophic-
                                                  forgetting risk

 PICK BY: dataset size (small -> left, large -> right)
          domain distance from pretraining (close -> left, far -> right,
                                             but far+small is the hard unsolved corner)

DISTILLATION (orthogonal axis — not "where on the spectrum," but "copy a different model")

  TEACHER (large, frozen)  ──produces──►  soft targets (full probability distribution)
         │                                        │
         │ same input                             ▼
         ▼                                STUDENT (small, training)
  hard label (ground truth) ──┐                    │
                               ├──► loss = α·KL(teacher_soft, student_soft) + (1-α)·CE(hard, student)
                               ┘
  soft targets carry MORE information than the hard label: teacher's probability that a
  "2" looks a little like a "7" IS the useful signal a one-hot label discards entirely.
```

---

## How it actually works

### Why transfer learning works: hierarchical feature reuse

A deep network trained on a broad task organizes computation hierarchically because that's the cheapest way to solve the task: early layers learn generic, reusable patterns (in vision: edges, textures; in language: subword co-occurrence, local syntax), and later layers compose those into increasingly task-specific representations (in vision: "this is a dog's face"; in language: "this sentence expresses frustration"). This is empirically demonstrated, not just intuited — freezing early layers and only fine-tuning late layers consistently recovers most of full fine-tuning's performance when the target task is reasonably close to the pretraining distribution, which wouldn't be true if early layers encoded task-specific rather than general information. The practical consequence: you need far less labeled data to relearn the task-specific late-layer mapping than you'd need to learn the entire hierarchy from scratch, because the expensive, data-hungry part (general feature learning) was already paid for during pretraining on a much larger corpus.

### Picking a point on the spectrum

| Dataset size | Domain distance from pretraining | Recommendation |
|---|---|---|
| Small (hundreds-low thousands of examples) | Close (e.g., fine-tuning a general sentiment model on a specific product review style) | Freeze the base, train only a new head. Full fine-tuning on this little data will overfit or catastrophically forget. |
| Small | Far (e.g., a general LLM on a narrow legal-clause extraction task with 500 labeled examples) | The hard corner. Partial unfreeze of the last few layers with strong regularization, or skip fine-tuning entirely and use RAG/few-shot prompting instead — see `T05-finetuning`'s RAG-vs-FT-vs-prompt decision tree, which exists specifically because this case has no clean fine-tuning answer. |
| Large (tens of thousands+) | Close | Full fine-tuning or LoRA both work well; LoRA usually wins on cost with comparable quality. |
| Large | Far | Full fine-tuning becomes justified — there's enough data to genuinely shift the model's representations without overfitting, though PEFT methods have closed most of this gap too as rank and target-module choices have matured. |

### Catastrophic forgetting: the observable symptom

Catastrophic forgetting is what happens when fine-tuning on a narrow task overwrites the general capabilities the base model had — the network's weights shift too far in the direction the new gradient signal points, and capabilities that weren't represented in the fine-tuning data degrade even though nothing about the fine-tuning objective explicitly asked for that. **The observable symptom**: a model fine-tuned on customer-support-ticket classification suddenly can't answer a general knowledge question it handled fine before fine-tuning, or a model fine-tuned to output terse JSON starts producing terse, degraded prose on unrelated general chat turns it's asked afterward. You'd see this in an eval as a regression on a held-out general-capability benchmark that has nothing to do with the fine-tuning task, run *before and after* fine-tuning as a diff. Mitigations: freeze more of the base (less capacity to forget with), use a much lower learning rate, mix a small amount of general-capability data back into the fine-tuning set (rehearsal), or use PEFT, which structurally can't overwrite base weights since they stay frozen — the adapter can be removed and the original capabilities return exactly.

### Discriminative (layer-wise) learning rates

When you do fine-tune more than just the head, using one learning rate for the whole network is usually wrong: early layers hold general features you want to disturb minimally, late layers need larger updates to actually adapt. Discriminative learning rates assign a smaller LR to early layers and a larger LR to late layers, typically via a multiplicative decay per layer group (e.g., `lr_layer_i = base_lr * decay^(n_layers - i)`, decay ~0.9-0.95). This reduces catastrophic forgetting in the early layers while still letting the late, task-specific layers move enough to actually fit the task.

```python
# untested sketch
def discriminative_lrs(model, base_lr=2e-5, decay=0.95):
    groups = []
    layers = list(model.encoder.layer)          # e.g. 12 BERT layers
    n = len(layers)
    for i, layer in enumerate(layers):
        lr = base_lr * (decay ** (n - i - 1))    # later layers -> lr closer to base_lr
        groups.append({"params": layer.parameters(), "lr": lr})
    groups.append({"params": model.head.parameters(), "lr": base_lr})  # head: full LR
    return torch.optim.AdamW(groups)
```

### Knowledge distillation, derived

The standard cross-entropy loss against a hard label only tells the student "this example is class 2, everything else is wrong, equally." A teacher model's full output distribution over classes carries more information: for a handwritten "2" that looks a bit like a "7", a well-trained teacher might output `P(2)=0.7, P(7)=0.25, P(others)=0.05` — this is real signal about which classes are visually/semantically similar, and it's completely discarded by a hard label. This extra signal is Hinton et al.'s "dark knowledge" argument (2015): the *relative* probabilities the teacher assigns to wrong answers encode a similarity structure over the output space that hard labels can never express.

**Temperature softening.** Raw teacher logits, softmaxed normally, are often too peaked (near one-hot) to expose this structure — a confident teacher gives the "2" example `P(2)=0.999`, hiding the useful `P(7)` signal in the remaining 0.001. Temperature `T` softens the distribution:

```
softmax_T(z_i) = exp(z_i / T) / Σ_j exp(z_j / T)
```

Higher `T` (typically 2-10) flattens the distribution, exposing more of the inter-class similarity structure the teacher has learned. Both teacher and student use the *same* T when computing the distillation loss.

**The loss, in full:**

```
L = α · T² · KL(softmax_T(teacher_logits) || softmax_T(student_logits))
  + (1 - α) · CE(hard_label, softmax(student_logits))
```

The `T²` factor corrects for the gradient magnitude shrinking as T grows (since softmax_T's gradient scales roughly as `1/T²`), so the soft-target term doesn't get numerically drowned out. `α` balances between matching the teacher (soft-target term) and getting the ground truth right directly (hard-label term); typical values sit around 0.5-0.9 favoring the soft-target term, since that's where the extra information lives.

### Response, feature, and relation distillation

| Type | What's matched | Example |
|---|---|---|
| Response distillation | Final output logits/probabilities only | The classic Hinton et al. setup above |
| Feature distillation | Intermediate hidden-layer activations | TinyBERT matches transformer layer outputs and attention matrices, not just final logits, giving the student a richer training signal per layer |
| Relation distillation | Relationships *between* examples (e.g., pairwise similarity structure) rather than any single example's output | Useful when the absolute output scale matters less than preserving which examples the teacher considers similar to which |

TinyBERT's two-stage approach (general-domain distillation on a large unlabeled corpus, then task-specific distillation on the fine-tuning data) using feature-level matching is a large part of why it beats DistilBERT's compression ratio while retaining comparable accuracy.

### Real compression and retention numbers

| Model | Compression | Retention |
|---|---|---|
| DistilBERT | 40% smaller (66M vs 110M params), 60% faster inference on CPU | ~97% of BERT-base's GLUE average (77.0 vs 79.5) |
| TinyBERT-4 | 7.5x smaller (14.5M params), 9.4x faster | ~96.8% of BERT-base's GLUE average |
| TinyBERT-6 | ~1.6x smaller (67M params), 2x faster | Matches BERT-base closely (e.g., 87.5 vs 88.5 F1 on SQuAD v1.1) |

[TinyBERT: Distilling BERT for Natural Language Understanding](https://aclanthology.org/2020.findings-emnlp.372.pdf) — accessed 2026-08-01; [Model Distillation for LLMs guide](https://redis.io/blog/model-distillation-llm-guide/) — accessed 2026-08-01. The pattern to internalize: bigger compression ratios cost more retention, but the curve is favorable — TinyBERT-4 gives up roughly 3 points of GLUE average for 7.5x smaller and 9.4x faster, which is usually a good trade for a high-QPS production endpoint.

### Distilling a large LLM into a small one for a narrow task

The generative-LLM version of this is the same idea at a different scale: generate a large volume of (input, teacher-output) pairs from a frontier model on your specific narrow task, then fine-tune a small open-weight model (student) on those pairs — often with the teacher's full generation as the target rather than a distribution over tokens, since token-level logit access to a hosted frontier model is frequently unavailable via API. This is "distillation" in the loose industry sense even when it's really supervised fine-tuning on teacher-generated data rather than the formal soft-target KL-divergence setup above. **The constraint that actually bites**: if the teacher is a hosted frontier model (OpenAI, Anthropic, several others), their terms of service typically prohibit using outputs to train a competing model — this isn't a hypothetical, it's the substance of the OpenAI-DeepSeek dispute. Before building a pipeline that generates training data from a frontier API for a student you plan to deploy, read the ToS, not just the pricing page.

---

## Build it from scratch

```python
# untested sketch — response-distillation training step
import torch, torch.nn.functional as F

def distillation_loss(student_logits, teacher_logits, hard_labels, T=4.0, alpha=0.7):
    soft_teacher = F.log_softmax(teacher_logits / T, dim=-1).detach()   # teacher frozen, no grad
    soft_student = F.log_softmax(student_logits / T, dim=-1)
    kd_loss = F.kl_div(soft_student, soft_teacher, log_target=True, reduction="batchmean") * (T ** 2)
    ce_loss = F.cross_entropy(student_logits, hard_labels)
    return alpha * kd_loss + (1 - alpha) * ce_loss

def train_step(student, teacher, batch, optimizer, T=4.0, alpha=0.7):
    teacher.eval()
    with torch.no_grad():
        teacher_logits = teacher(batch["input_ids"], batch["attention_mask"]).logits
    student_logits = student(batch["input_ids"], batch["attention_mask"]).logits
    loss = distillation_loss(student_logits, teacher_logits, batch["labels"], T, alpha)
    optimizer.zero_grad(); loss.backward(); optimizer.step()
    return loss.item()
```

Feature-distillation extension (TinyBERT-style): add an MSE term between a chosen student layer's hidden state and the corresponding teacher layer's hidden state (usually with a learned linear projection to match dimensions if the student is narrower than the teacher), summed across matched layer pairs, added to the response-distillation loss above.

---

## How it's done in production

| Approach | What it adds |
|---|---|
| Hugging Face `Trainer` + `transformers` distillation scripts | Standard response-distillation loop, easy to extend with feature-matching hooks |
| DistilBERT / TinyBERT / MobileBERT checkpoints | Pre-distilled general-purpose students you can fine-tune directly, skipping the distillation step entirely if a general-domain student already exists for your architecture |
| Self-distillation pipelines (large fine-tuned model → small deployed model, same org) | No third-party ToS risk since you own both models; increasingly the default pattern for "we fine-tuned a big model to validate the approach, now shrink it for production" |
| `T04-export-optimize` | Covers distillation from the deployment/serving angle — quantization, ONNX export, and how distillation composes with those (distill first, then quantize, typically) |

**Failure modes**

| Symptom | Cause | Fix |
|---|---|---|
| Fine-tuned model aces the target task but fails basic general questions it used to answer | Catastrophic forgetting — fine-tuning shifted weights too far from the base | Lower LR, freeze more layers, add rehearsal data, or switch to PEFT so base weights never change |
| Student model matches teacher accuracy on training distribution but degrades badly on edge cases | Response-only distillation with too little training data diversity; student memorized teacher's common-case behavior without learning the underlying decision boundary | Add feature-level distillation, increase training data diversity, or use a higher temperature to expose more of the teacher's uncertainty structure |
| Distillation loss won't converge / KL term dominates and ignores ground truth | `α` too high relative to the hard-label term, or T too extreme | Tune α down, sweep T in the 2-10 range rather than picking an extreme value |
| Legal/compliance flags a distillation pipeline built on a hosted frontier model's outputs | ToS violation risk — using outputs to train a competing or substitute model | Check the provider's terms before building the pipeline; prefer open-weight teachers or your own fine-tuned model as the teacher |
| Small model trained "from scratch" on a narrow domain underperforms a distilled model of the same size | Distillation transfers the teacher's learned inductive biases and generalization patterns that a from-scratch student of the same capacity can't discover on its own from limited data | Prefer distillation over from-scratch training whenever a suitable teacher and enough distillation data exist |

---

## Tradeoffs & when NOT to use it

- **Don't jump to full fine-tuning by default.** If the dataset is small and the domain is close to pretraining, full fine-tuning is more compute for a worse overfitting/forgetting risk profile than frozen-feature extraction or PEFT would give you.
- **Don't distill when you can fine-tune the small model directly on labeled data instead.** Distillation earns its cost when the teacher captures decision-boundary nuance you can't get from your labeled set alone, or when you don't have enough labeled data but can generate large volumes of teacher outputs cheaply. If you have ample labeled data already, direct fine-tuning of the small model is simpler and skips the ToS/teacher-management overhead entirely.
- **Don't distill a hosted frontier model's outputs into a competing product without reading the ToS.** This is not a hypothetical risk; it is the subject of an active, public legal dispute between two major labs. If a third-party model's ToS bars this, use an open-weight teacher or your own model.
- **When distillation is the wrong call entirely**: the task is too complex for the target student capacity regardless of teacher quality (compression has a floor — you cannot distill genuinely emergent capability into a model too small to represent it), or the deployment target doesn't actually have the latency/cost pressure that justifies the engineering investment in the first place (a low-QPS internal tool rarely needs a distilled student; ship the big model and revisit if traffic grows).
- **PEFT vs full fine-tuning vs distillation are not interchangeable** — PEFT and full fine-tuning adapt one model to a new task; distillation compresses a model's *capability* into a smaller architecture. You may need both in sequence: fine-tune a large model to validate an approach works at all, then distill into a small model for production serving.

---

## Interview questions

### Q1 — Why does transfer learning work at all?
**Answer:** Hierarchical feature reuse. Deep networks trained on large, diverse tasks organize computation so early layers learn general, broadly reusable patterns and later layers compose those into task-specific representations. Reusing the general layers means the target task only needs enough data to relearn the specific mapping, not the entire hierarchy from scratch.
**Follow-up trap:** *"How would you verify this empirically rather than just asserting it?"* — freeze early layers and fine-tune only late layers; if performance on a target task reasonably close to pretraining stays near full-fine-tuning levels, that's direct evidence the early layers already encode transferable, not task-specific, information.

### Q2 — You have 800 labeled examples for a task close to your base model's pretraining domain. What do you do?
**Answer:** Freeze the base, train only a new head (feature extraction), or use PEFT with a small rank. Full fine-tuning on 800 examples risks overfitting and catastrophic forgetting; there isn't enough data to safely move the whole network's weights.
**Follow-up trap:** *"What if accuracy with a frozen base isn't good enough?"* — try partial unfreezing (last 1-2 layers) with a low learning rate before reaching for full fine-tuning; jumping straight to full FT on 800 examples is the more common mistake than under-unfreezing.

### Q3 — What is catastrophic forgetting and what does it look like in a log or eval, concretely?
**Answer:** Fine-tuning on a narrow task shifts weights enough to degrade capabilities the base model had that weren't represented in the fine-tuning data. Concretely: a model fine-tuned for terse structured-JSON output starts producing degraded, terse prose on unrelated general chat turns afterward, or a support-ticket classifier suddenly fails general-knowledge questions it handled correctly pre-fine-tuning. You'd catch this as a regression on a held-out general-capability eval run before and after fine-tuning.
**Follow-up trap:** *"How do you fix it without giving up the target-task gains?"* — lower the learning rate, freeze more of the base, mix a small amount of general-capability data back into training (rehearsal), or switch to PEFT, which structurally can't overwrite base weights since they're frozen and the adapter is separable.

### Q4 — Derive why soft targets carry more information than hard labels.
**Answer:** A hard label says "this is class 2, everything else is equally wrong." A well-trained teacher's full probability distribution over classes for the same input encodes real structure — e.g. `P(2)=0.7, P(7)=0.25` for an ambiguous handwritten digit — which is a measured similarity relationship between classes that the ground truth alone can never express. Training a student against that full distribution (Hinton et al.'s "dark knowledge") transfers that similarity structure, which is strictly more supervisory signal per example than a one-hot label.
**Follow-up trap:** *"Why not just use the teacher's raw softmax output directly, without temperature?"* — a confident teacher's raw softmax is often too peaked (near one-hot) to expose the inter-class structure; temperature scaling flattens it so the useful signal in the small probabilities isn't numerically invisible.

### Q5 — Walk through the distillation loss term by term.
**Answer:** `L = α·T²·KL(softmax_T(teacher) || softmax_T(student)) + (1-α)·CE(hard_label, student)`. The KL term matches the student's softened distribution to the teacher's, transferring dark knowledge; the CE term anchors the student to ground truth directly. `T²` corrects for the gradient shrinking as temperature rises (softmax_T's gradient scales roughly as 1/T²), so the KL term's contribution doesn't get numerically drowned out at high T. `α` balances the two terms, typically weighted 0.5-0.9 toward the soft-target term.
**Follow-up trap:** *"What happens if you set T=1?"* — you're just using the raw softmax, which for a confident teacher is close to one-hot and loses most of the dark-knowledge signal; T=1 makes distillation degenerate toward plain supervised learning on the teacher's argmax prediction.

### Q6 — Give real numbers: how much does DistilBERT give up, and for what?
**Answer:** ~97% of BERT-base's GLUE average (77.0 vs 79.5) at 40% smaller (66M vs 110M params) and roughly 60% faster inference on CPU. That's the ratio to know cold: a small accuracy cost for a large size/latency win.
**Follow-up trap:** *"TinyBERT compresses harder — how does it do it and what's the tradeoff?"* — TinyBERT-4 is 7.5x smaller and 9.4x faster at ~96.8% of BERT-base's GLUE average, achieved via a two-stage distillation (general-domain then task-specific) using feature-level matching (hidden states and attention matrices), not just final-logit matching — the richer per-layer signal is what lets it compress harder without retention collapsing.

### Q7 — What's the difference between response, feature, and relation distillation?
**Answer:** Response distillation matches only the final output distribution (the classic Hinton et al. setup). Feature distillation matches intermediate hidden-layer activations or attention matrices, giving a much richer per-layer training signal — this is most of what makes TinyBERT beat DistilBERT's compression-to-retention ratio. Relation distillation matches relationships between examples (e.g., pairwise similarity) rather than any single example's absolute output.
**Follow-up trap:** *"When would feature distillation actively hurt?"* — when the student's architecture is different enough from the teacher's (different hidden dimension, different layer count) that forcing intermediate representations to match requires an extra learned projection whose own errors add noise; if the architectures are very different, response-only distillation can be more robust despite carrying less signal per example.

### Q8 — Your legal team flags a plan to distill a competitor's hosted API into your product's small model. What's the actual risk?
**Testing:** whether you know this is a live legal issue, not a theoretical one.
**Answer:** Most frontier-model providers (OpenAI, Anthropic, Mistral, xAI) have anti-competitive-distillation clauses in their terms of service that explicitly prohibit using model outputs to train a competing model. This isn't hypothetical — it's the substance of a real, public 2025-2026 dispute between OpenAI and DeepSeek, where OpenAI alleged DeepSeek used obfuscated third-party routers to extract outputs at scale for distillation, in violation of ToS.
**Follow-up trap:** *"So is distillation itself illegal?"* — no, distillation as a technique is legal and widely practiced; the issue is specifically contractual — using a *particular provider's* outputs in violation of *that provider's* terms. Distilling your own fine-tuned model, or a properly licensed open-weight model, carries none of this risk.

### Q9 — When is distillation the wrong call?
**Testing:** the senior "when NOT to" signal.
**Answer:** When you already have enough labeled data to fine-tune the small student directly — distillation's value is transferring a teacher's decision-boundary nuance when your own labeled set is thin, so if it isn't, direct fine-tuning is simpler and skips teacher-management and licensing overhead. Also wrong when the target task requires capability the student's capacity genuinely can't represent regardless of teacher quality (compression has a floor), or when the deployment doesn't have latency/cost pressure that justifies the engineering investment at all.
**Follow-up trap:** *"Isn't a smaller model always cheaper to run, so why not distill anyway?"* — the cost isn't just training compute, it's building and maintaining a teacher-student pipeline, sourcing distillation data, and revalidating whenever the teacher updates; for a low-QPS internal tool that overhead outweighs the marginal inference savings, so "ship the big model, revisit if traffic grows" is often the right call.

### Q10 — What's the difference between PEFT (LoRA) and distillation? Could you use both?
**Answer:** PEFT adapts one existing model to a new task by training a small set of additional parameters while freezing the base — it's a fine-tuning technique. Distillation transfers capability from one model into a *different, smaller* architecture — it's a compression technique. They solve different problems and compose naturally: fine-tune (possibly with LoRA) a large model to validate an approach and get strong task performance, then distill that fine-tuned model's behavior into a small architecture for cheap production serving.
**Follow-up trap:** *"Could you LoRA-fine-tune the student during distillation instead of full-fine-tuning it?"* — yes, and it's a reasonable combination when the student itself is still large enough that full fine-tuning is expensive; you'd apply the distillation loss (KD + CE) while only updating LoRA adapter weights on the student, freezing the student's own base.

### Q11 — Discriminative learning rates: what problem do they solve and how would you set them up?
**Answer:** Using one learning rate across the whole network during fine-tuning risks disturbing general early-layer features too much (increasing forgetting risk) while under-adapting the task-specific late layers. Discriminative learning rates assign smaller LRs to early layers and progressively larger LRs to later layers, typically via a multiplicative decay per layer group, so early general features move minimally while late task-specific layers adapt fully.
**Follow-up trap:** *"How do you pick the decay factor?"* — there's no universal number; a common starting point is decay ≈0.9-0.95 per layer group, then validate against a held-out general-capability eval to check forgetting hasn't crept in, adjusting the decay (steeper for more preservation) if it has.

### Q12 — A frontier LLM is your teacher via API, so you don't have logit access. How do you distill without soft targets?
**Answer:** Generate a large volume of (input, teacher-generation) pairs from the API and supervised-fine-tune the student directly on the teacher's generated text as the target — this is "distillation" in the loose industry sense (sequence-level knowledge distillation), not the formal soft-target KL setup, since you don't have access to the teacher's token-level probability distribution through most hosted APIs.
**Follow-up trap:** *"Does that lose the dark-knowledge benefit?"* — largely yes; sequence-level distillation on generated text transfers the teacher's *choices* but not its uncertainty structure over alternatives. Some providers expose token-level logprobs for a subset of tokens, which can partially recover soft-target information, but full-distribution access is rare and this remains a real limitation versus classic response distillation with an open-weight teacher.

---

## Red flags that fail you

- Reaching for full fine-tuning by default regardless of dataset size.
- Describing catastrophic forgetting vaguely ("the model gets worse") without naming the observable symptom or an eval-based way to detect it.
- Explaining distillation as "just making the model smaller" without mentioning soft targets, temperature, or the dark-knowledge argument.
- Not knowing that provider ToS can prohibit distillation from a hosted frontier model, or treating it as a purely technical, licensing-free decision.
- Confusing PEFT (adapt one model to a task) with distillation (compress capability into a different, smaller architecture).
- Citing DistilBERT/TinyBERT numbers with no idea what the compression-vs-retention tradeoff actually looks like.

---

## Cheat card

```
TRANSFER LEARNING WORKS BECAUSE: hierarchical feature reuse
  early layers = general (edges, subword co-occurrence)
  late layers  = task-specific
  -> reuse general layers, relearn only the specific mapping, need far less data

ADAPTATION SPECTRUM (pick by dataset size x domain distance)
  frozen features -> partial unfreeze -> full fine-tune -> PEFT (LoRA/QLoRA, near-full-FT
                                                             quality, tiny memory footprint)
  small+close: freeze base, new head only
  small+far:   hard corner -> partial unfreeze + heavy reg, or RAG/few-shot instead
  large+either: full FT or LoRA both viable; LoRA usually wins on cost

CATASTROPHIC FORGETTING
  symptom: fine-tuned model fails general capability it had pre-fine-tune
  fix: lower LR, freeze more, rehearsal data, or PEFT (base weights never move)

DISCRIMINATIVE LR: smaller LR early layers, larger LR late layers (decay ~0.9-0.95/layer)

DISTILLATION LOSS
  L = alpha * T^2 * KL(softmax_T(teacher) || softmax_T(student)) + (1-alpha) * CE(hard, student)
  T=2-10 typical; T^2 corrects gradient shrinkage; alpha ~0.5-0.9 toward KD term
  T=1 -> degenerates toward plain supervised learning on teacher's argmax

DARK KNOWLEDGE: teacher's soft probs over WRONG answers carry similarity structure
  a hard label discards entirely (Hinton et al. 2015)

TYPES: response (final logits only) / feature (hidden states, attn) / relation (pairwise sim)

REAL NUMBERS
  DistilBERT: 97% GLUE retention, 40% smaller, 60% faster (CPU)
  TinyBERT-4: 96.8% GLUE retention, 7.5x smaller, 9.4x faster (feature-level distillation)

LICENSING — THE THING THAT ACTUALLY BITES
  OpenAI/Anthropic/Mistral/xAI ToS: prohibit training a competing model on their outputs
  real dispute: OpenAI alleges DeepSeek violated this at scale (2025-2026)
  own model or open-weight teacher = no such risk

WHEN NOT TO DISTILL
  enough labeled data to fine-tune student directly -> skip distillation entirely
  task exceeds student capacity regardless of teacher -> compression has a floor
  low QPS / no latency pressure -> ship the big model
```

## Sources
- [TinyBERT: Distilling BERT for Natural Language Understanding](https://aclanthology.org/2020.findings-emnlp.372.pdf) — accessed 2026-08-01
- [Model Distillation for LLMs: Cut Costs & Boost Speed in 2026 — Redis](https://redis.io/blog/model-distillation-llm-guide/) — accessed 2026-08-01
- [The Innovation Dilemma: AI Distillation in OpenAI v. DeepSeek](https://sites.law.berkeley.edu/thenetwork/2025/03/30/the-innovation-dilemma-ai-distillation-in-openai-v-deepseek/) — accessed 2026-08-01
- [Dispute over AI model distillation tech in OpenAI-DeepSeek case](https://law.asia/openai-deepseek-ai-distillation/) — accessed 2026-08-01
- [OpenAI — US House Select Committee update on distillation/ToS](https://cdn.openai.com/pdf/045aa967-ee96-4a09-94ee-3098ddf6db2c/OpenAI-US-House-Select-Cmte-Update-%5B021226%5D.pdf) — accessed 2026-08-01

## Changelog
- 2026-08-01 — created
