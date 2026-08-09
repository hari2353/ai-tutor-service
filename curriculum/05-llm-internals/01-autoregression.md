# Autoregression: Next-Token Prediction, Teacher Forcing, Exposure Bias

> **Track:** T05 LLM Internals · **Time:** 2h · **Prereqs:** none
> **Module id:** `T05-autoregression` · **Tags:** internals, critical
> **Lab:** none yet — see `labs/py/02-agent-loop/` for the pattern if you want to build one (create if not present — not yet in this repo)

## The 30-second version

An autoregressive LLM factorizes the joint probability of a token sequence into a product of conditionals: `p(x_1..x_n) = Π p(x_t | x_<t)`, and it is trained to maximize the log-likelihood of every token given everything before it, in parallel, in one forward pass, using teacher forcing — the ground-truth prefix, not the model's own prediction, is what conditions each position during training. That single design choice is also the source of the model's biggest structural weakness: at inference time there is no ground truth, so the model conditions on its *own* generated tokens, and any early mistake becomes part of the context for every token that follows. This training/inference mismatch is called exposure bias, and it's why errors compound over long generations even though the per-token loss during training looked fine. Nothing about this is a bug to be patched — it's the tradeoff that buys full parallelization of training over a sequence-length-dependent bottleneck, and every mitigation (scheduled sampling, RL fine-tuning, self-correction training) is a patch on top of that tradeoff, not a replacement for it.

## Why this gets asked

Because "the model predicts the next token" is the one-sentence version everyone gives, and it's not wrong, but it hides the actual training mechanics that make LLM pretraining computationally tractable at all, and it hides the specific failure mode — compounding error, not just "sometimes wrong" — that shows up in production as a model that answers a short prompt fine but degrades, repeats, or drifts off-topic over a long generation. The interviewer has watched a model produce a perfectly reasonable first paragraph and then unravel by paragraph four, and wants to know if you understand *why* that specific shape of failure happens rather than treating it as generic "hallucination."

## Lineage: past → present → future

**What came before.** Statistical n-gram language models (Markov chain word models, pre-2000s through the 2000s) were autoregressive too, but they estimated `p(x_t | x_{t-k}..x_{t-1})` from raw counts over a fixed, short context window, and the pain was sparsity: most n-grams of length 4+ never appear in any training corpus, so the model backs off to shorter contexts and loses exactly the long-range dependency that makes language coherent. RNN/LSTM language models (Bengio et al. 2003 neural LM; Mikolov 2010 RNNLM; Hochreiter & Schmidhuber's LSTM applied to language modeling through the 2010s) fixed the fixed-window problem by carrying a hidden state forward indefinitely, but paid for it with an inherently sequential training process — you cannot compute the hidden state at position `t` without first computing it at `t-1`, so training throughput was bounded by sequence length no matter how much parallel hardware you had. That sequential-training bottleneck, not model quality, is the specific pain that the Transformer killed.

**Where it stands now.** Every frontier general-purpose LLM (GPT, Llama, Claude, Gemini, Qwen, DeepSeek families) is trained with teacher-forced next-token prediction over a Transformer, computed in one masked, fully parallel forward pass per training step — this part is completely settled and has been since 2018-2019. The live disagreement is entirely about what to do about exposure bias and how much it actually matters in practice. One camp (empirically dominant in production through 2024-2025) argues that at current model and data scale, teacher forcing plus a large enough pretraining corpus plus RLHF/DPO alignment on generated (not teacher-forced) rollouts is sufficient — the model implicitly learns to be robust to its own small errors because human-preference fine-tuning is scored on actual autoregressive rollouts, not on teacher-forced likelihood. The other camp points to reasoning tasks specifically: chain-of-thought generations are long, and a single early logical slip compounds, which is a big part of why RL-for-reasoning (GRPO, RLVR — covered in `T05-alignment`) trains directly against full autoregressive rollouts with verifiable rewards rather than against teacher-forced likelihood, precisely because likelihood-based training doesn't penalize compounding error the way rollout-based reward does.

**Where it's heading.** With reasonable confidence: RL-style post-training that scores whole autoregressive rollouts (not per-token teacher-forced loss) is becoming a larger fraction of total training compute for reasoning-focused models, because it directly optimizes the thing exposure bias breaks. More speculatively, and worth flagging explicitly as such: multi-token prediction objectives (predicting several future tokens per position during pretraining, as explored by DeepSeek-V3 and Meta's 2024 multi-token-prediction work) are being investigated as a way to give the model implicit lookahead and reduce reliance on single-step teacher forcing, but as of mid-2026 this augments rather than replaces standard next-token teacher forcing in any shipped frontier model — treat "teacher forcing is going away" as false, and "it's being supplemented" as the accurate, cautious claim.

---

## Mental model

```
TRAINING (teacher forcing) — ground truth feeds every position, computed in parallel

  input:   <BOS> the  cat  sat  on
  target:       the  cat  sat  on  the

  position 1: sees "<BOS>"              -> must predict "the"
  position 2: sees "<BOS> the"          -> must predict "cat"   (real "the", not model's guess)
  position 3: sees "<BOS> the cat"      -> must predict "sat"   (real "cat", not model's guess)
  position 4: sees "<BOS> the cat sat" -> must predict "on"    (real "sat", not model's guess)

  all 4 positions computed in ONE forward pass, using a causal mask so position i
  can't see positions > i. loss = sum of per-position cross-entropy.

INFERENCE (autoregressive generation) — the model's own output feeds the next step

  step 1: sees "<BOS>"                       -> generates "the"     (correct, say)
  step 2: sees "<BOS> the"                   -> generates "dog"     (WRONG — should be "cat")
  step 3: sees "<BOS> the dog"               -> generates "barked"  (fluent, but now off-script,
                                                                       and conditioned on its own error)
  step 4: sees "<BOS> the dog barked"        -> generates "loudly"  (compounding: every future token
                                                                       is now conditioned on "dog barked")
```

The training loop never lets a wrong token propagate — every position always sees the *true* prefix. The inference loop has no true prefix to fall back on; whatever the model said becomes ground truth for everything after it. That gap between the two loops is exposure bias in one picture.

---

## How it actually works

### The factorization and the loss

An autoregressive model defines the probability of an entire sequence as a product of per-token conditionals:

$$p_\theta(x_1, \dots, x_n) = \prod_{t=1}^{n} p_\theta(x_t \mid x_1, \dots, x_{t-1})$$

Training maximizes this likelihood, equivalently minimizes the sum of per-token cross-entropy losses:

$$\mathcal{L}(\theta) = -\sum_{t=1}^{n} \log p_\theta(x_t \mid x_{<t})$$

Each term only needs the *true* prefix `x_<t`, which is exactly what makes parallel computation possible: you don't need the model's own prediction at position `t-1` to compute the loss at position `t`, because the loss at position `t` conditions on the ground-truth `x_{t-1}`, not on whatever the model happened to predict there. This is teacher forcing — the "teacher" (the real next token from the training corpus) is forced into the context regardless of what the model itself would have generated.

### Why one forward pass computes all positions at once

A Transformer decoder computes hidden states for all `n` positions of a sequence in a single pass by using a causal (lower-triangular) attention mask: position `t` can attend to positions `1..t`, but the mask sets attention scores for positions `> t` to `-∞` before softmax, so those contributions vanish. Because there's no recurrence — no hidden state at position `t` depends on having *finished computing* the hidden state at `t-1` — all `n` positions can be computed as one batched matrix multiply. This is precisely the property RNNs didn't have (their hidden state literally is a function of the previous step's hidden state, computed in sequence), and it's the mechanical reason Transformer pretraining scales far better with parallel hardware than RNN pretraining ever could, independent of anything about attention's representational power.

Concretely: for a batch of sequences each of length `n`, one forward pass produces logits of shape `(batch, n, vocab_size)` and the loss is the mean cross-entropy over all `batch × n` positions simultaneously — you get `n` training signals (one per position) per sequence per step, not one.

### Exposure bias, mechanically

At inference, there is no teacher, so the "prefix" fed into the next step is `x̂_<t` — the model's own previous outputs — not the ground truth `x_<t`. The model was never trained on distributions of prefixes that include *its own mistakes*, because during training it never sees its own mistakes; it only ever sees the true prefix. If the model assigns a small probability `ε` to an error at some step, that error becomes part of the conditioning context for every subsequent step, and the model has to generate coherent continuations from an out-of-training-distribution prefix it has literally never encountered during training. This is why the failure mode has a specific shape: it's not "wrong token here, wrong token there, uniformly" — it's "fine, fine, fine, one mistake, then a qualitatively different kind of drift," because everything after the mistake is conditioned on a prefix the model's training distribution didn't cover.

**Where this shows up as a measurable production symptom:** repetition loops (the model gets stuck regenerating the same few tokens because the current context, corrupted by an earlier error, is a low-density region of the training distribution where the highest-probability continuation is "repeat what's already there"), topic drift in long-form generation, and degrading quality specifically as generation length grows even when per-token perplexity on held-out *teacher-forced* data looks fine — that disconnect (good teacher-forced perplexity, bad long free-running generation quality) is the diagnostic signature of exposure bias specifically, as opposed to a model that's simply undertrained or has a bad prompt.

### Mitigations, and their actual limits

- **Scheduled sampling** (Bengio et al., 2015): during training, occasionally feed the model its own sampled prediction instead of the ground-truth token, with the probability of doing so annealed upward over training. It narrows the train/inference gap but breaks the parallelizability that teacher forcing buys — you can't compute position `t`'s input without first sampling from position `t-1`'s output, reintroducing a sequential dependency during training. It's rarely used at LLM pretraining scale for exactly this reason; it's a training-time cost nobody wants to pay when data and compute are the constraint, not exposure bias.
- **RL / preference fine-tuning on actual rollouts** (RLHF/PPO, DPO, GRPO — `T05-alignment`): the model is scored on sequences it actually generated autoregressively, not on teacher-forced likelihood, so the training signal directly reflects rollout-time quality, including whatever the model's own compounding errors look like. This is the dominant production mitigation today, not because it "solves" exposure bias in some formal sense, but because it's the stage where the objective finally matches the deployment distribution.
- **Self-correction / process supervision**: training the model on data or rewards that explicitly reward catching and correcting an earlier mistake mid-generation. Effective for reasoning chains specifically, but it's a targeted patch for a targeted failure mode (bad intermediate reasoning steps), not a general fix for exposure bias across all generation.

None of these replace teacher-forced pretraining; they all sit on top of it, because teacher forcing is what makes pretraining computationally affordable at trillion-token scale in the first place.

---

## Build it from scratch

Minimal teacher-forced training step versus autoregressive (free-running) generation, to make the training/inference asymmetry concrete:

```python
import torch
import torch.nn.functional as F

def teacher_forced_loss(model, input_ids):
    """input_ids: (batch, seq_len) of token ids, already including BOS.
    Predicts token t from the TRUE prefix x_<t for every position in one pass."""
    logits = model(input_ids[:, :-1])          # (batch, seq_len-1, vocab) -- one forward pass
    targets = input_ids[:, 1:]                  # shift by one: predict the next real token
    # cross-entropy over every position at once -- this is the parallelism teacher forcing buys
    loss = F.cross_entropy(
        logits.reshape(-1, logits.size(-1)),
        targets.reshape(-1),
    )
    return loss

@torch.no_grad()
def autoregressive_generate(model, prompt_ids, max_new_tokens, eos_id):
    """Free-running generation: every new token is conditioned on the model's
    OWN previous outputs, not on any ground truth. This is where exposure bias lives."""
    ids = prompt_ids.clone()
    for _ in range(max_new_tokens):
        logits = model(ids)                      # recompute over the whole growing sequence
        next_logits = logits[:, -1, :]           # only the last position's prediction matters
        next_id = torch.argmax(next_logits, dim=-1, keepdim=True)  # greedy for clarity
        ids = torch.cat([ids, next_id], dim=1)   # append OUR OWN prediction, not a true token
        if (next_id == eos_id).all():
            break
    return ids
```

The asymmetry is entirely in what feeds the next position: `targets` in the training function come from the dataset; `next_id` fed back into `ids` in generation comes from the model itself. A from-scratch demonstration that deliberately injects errors into a teacher-forced prefix and shows perplexity blow up on the corrupted continuation, versus the same measurement on a clean prefix, lives in **`labs/py/01-autoregression/`**.

---

## How it's done in production

| Layer | What you actually use | What it adds |
|---|---|---|
| Pretraining | Teacher-forced cross-entropy over the full corpus, causal-masked Transformer, one pass per batch | Makes trillion-token pretraining computationally tractable at all |
| Alignment | RLHF/PPO, DPO, GRPO scored on real autoregressive rollouts | Directly optimizes the distribution the model is actually deployed under, closing part of the train/inference gap |
| Serving | KV-cache incremental decoding (`T05-inference-serving`) | Not a fix for exposure bias — it's a *speed* optimization for the same free-running loop; it reuses cached K/V from prior real steps but doesn't change what's fed back in |
| Eval | Held-out teacher-forced perplexity **and** separately, free-running generation quality (human eval, LLM-as-judge on full outputs) | Perplexity alone hides exposure bias; you need to evaluate model behavior under its own generated prefixes, not just under ground-truth prefixes |

### Failure modes

| Symptom | Cause | Fix |
|---|---|---|
| Model repeats the same phrase or sentence in a loop during long generations | An early low-probability error pushed the running context into a low-density region where "keep repeating" is locally highest-probability | Repetition penalties / no-repeat-n-gram at decode time (`T05-sampling`) as a serving-layer patch; better long-form RL fine-tuning as the real fix |
| Held-out teacher-forced perplexity looks great, but real free-running outputs degrade past a few hundred tokens | Classic exposure-bias signature — the eval never measured the model conditioned on its own mistakes | Add free-running generation quality to the eval suite; don't rely on teacher-forced perplexity alone to sign off long-context or long-generation behavior |
| Chain-of-thought answers start reasonable and then produce a wrong final answer after a subtly wrong intermediate step | One bad token in a multi-hundred-token reasoning chain compounds; teacher-forced pretraining never penalized that specific chain of dependent errors | RL-with-verifiable-rewards trained directly on full rollouts (GRPO/RLVR) so the compounding effect is part of the actual training signal |
| Fine-tuning on a narrow, short-sequence dataset produces a model that degrades specifically on long generations it wasn't fine-tuned on | Teacher forcing during fine-tuning never exposed the model to its own long free-running outputs in that domain | Include long-sequence, self-generated (or rollout-sampled) examples in the fine-tuning mix, not just short ground-truth-only sequences |

---

## Tradeoffs & when NOT to use it

- **Teacher forcing is not "cheating" you should try to avoid at pretraining time** — abandoning it (full scheduled sampling, fully free-running pretraining) reintroduces the sequential bottleneck that killed RNN-scale training; at trillion-token pretraining budgets this tradeoff is not close, and nobody does it.
- **Don't diagnose every long-generation quality problem as exposure bias.** Truncated context, positional-encoding extrapolation failure (`T05-positional`), and plain undertraining all produce superficially similar "gets worse over a long output" symptoms; the specific tell for exposure bias is good teacher-forced perplexity paired with bad free-running quality — if teacher-forced perplexity is *also* bad, look elsewhere first.
- **Scheduled sampling is usually the wrong call at LLM scale.** It's a legitimate technique from the RNN/seq2seq era and still appears in some structured-prediction and non-LLM sequence tasks, but paying the parallelism cost to marginally reduce exposure bias, when RLHF/DPO/GRPO post-training already targets the same gap using rollout-based signal, is rarely worth it for general-purpose LLM pretraining.
- **If your task genuinely doesn't involve long free-running generation** (e.g., single-token classification framed as next-token prediction, short-answer extraction), exposure bias is close to irrelevant — don't over-invest alignment budget defending against a failure mode your deployment surface doesn't expose.

---

## Interview questions

### Q1 — What does "autoregressive" mean for a language model, precisely?
**Testing:** baseline fluency beyond the buzzword.
**Answer:** The model factorizes the joint probability of a sequence as a product of conditionals, each token conditioned only on the tokens before it: `p(x_1..x_n) = Π p(x_t | x_<t)`. It's trained to maximize this likelihood and, at inference, samples tokens one at a time from left to right, each new token conditioned on everything generated so far.
**Follow-up trap:** *"Is that different from a causal language model?"* — no, "causal LM" and "autoregressive LM" describe the same factorization; "causal" specifically emphasizes the masking mechanism (each position can only attend to earlier positions) that implements the autoregressive constraint inside a Transformer.

### Q2 — What is teacher forcing, and why is it used instead of feeding the model's own predictions during training?
**Testing:** whether you understand the parallelism argument, not just the definition.
**Answer:** Teacher forcing conditions the prediction at position `t` on the true prefix `x_<t` from the dataset, not on what the model itself predicted at `t-1`. This means every position's loss can be computed independently within a single forward pass — no position has to wait for another position's output — which is what lets a whole batch of full-length sequences train in one parallel step instead of a sequential loop over positions.
**Follow-up trap:** *"So teacher forcing makes training faster. Does it cost anything?"* — yes: it creates a distribution mismatch, because the model is only ever trained on true prefixes and never learns to condition on prefixes containing its own errors, which is exactly what it has to do at inference time. That mismatch is exposure bias.

### Q3 — Define exposure bias and describe its observable symptom.
**Answer:** Exposure bias is the mismatch between training (conditioned on ground-truth prefixes) and inference (conditioned on the model's own generated prefixes). The observable symptom is compounding degradation over long free-running generations — quality holds up early, then a small error shifts the context into a region the model wasn't trained to condition on, and everything after that point is affected — while the same model's teacher-forced perplexity on held-out data can look completely normal.
**Follow-up trap:** *"How would you empirically confirm a quality regression is exposure bias and not just a bad model?"* — check teacher-forced perplexity on held-out data first; if that's fine but long free-running generation quality is bad specifically as length grows, that dissociation is the exposure-bias signature. If teacher-forced perplexity is also bad, the problem is upstream (undertraining, data quality, or something in the architecture), not exposure bias specifically.

### Q4 — Why can't you compute a causal Transformer's forward pass at inference time the same way you compute it at training time?
**Answer:** At training time the entire sequence (including everything after position `t`) is already known and fixed from the dataset, so a single masked forward pass computes all positions' hidden states and losses at once. At inference time, position `t+1`'s input token doesn't exist yet — it *is* the thing being generated — so you can't run one pass over the "whole" sequence; you must generate token `t`, append it, then recompute (or incrementally update via KV cache) to generate token `t+1`. This is why generation is fundamentally sequential even though training was parallel.
**Follow-up trap:** *"Doesn't the KV cache make generation parallel too?"* — no, the KV cache makes each generation step *cheaper* (you don't recompute K/V for already-generated positions), but the loop is still sequential — you still can't compute token `t+1` without knowing token `t`, cache or no cache. That's a distinct topic from exposure bias; see `T05-inference-serving`.

### Q5 — A model produces a great first paragraph and then drifts into repetitive, off-topic text by the fourth paragraph. Walk me through your diagnosis.
**Testing:** applying the concept to a realistic production symptom instead of reciting the definition.
**Answer:** First check whether this is length-dependent specifically (does a shorter target length avoid it, does re-prompting with the same content but demanding a shorter answer produce clean output) — if yes, that's consistent with exposure bias: an early low-probability token compounds. Also check positional encoding extrapolation (is total length approaching or exceeding the trained context length) and check for repetition-penalty/sampling misconfiguration (greedy or low-temperature decoding is far more prone to repetition loops once conditioned on a slightly-off context) before concluding it's fundamentally an exposure-bias problem versus a decoding-parameter problem.
**Follow-up trap:** *"If it's exposure bias, what's the actual production fix, not just the diagnosis?"* — decode-time mitigations (repetition penalty, no-repeat-n-gram, better sampling — `T05-sampling`) reduce the symptom without touching the cause; the actual fix is post-training on rollout-based objectives (RLHF/DPO/GRPO) so the model is directly optimized on sequences it generates itself, which is the only stage where the training distribution matches the deployment distribution.

### Q6 — Derive the training loss for a sequence and explain what "the loss decomposes over positions" buys you operationally.
**Answer:** `L(θ) = -Σ_t log p_θ(x_t | x_<t)`. Because each term only depends on the *true* prefix (never on another term's output), all `n` terms for a sequence can be computed from a single forward pass through a causally-masked network, and the total loss is just their sum (or mean). Operationally this means one GPU forward/backward pass produces `n` supervised training signals per sequence, not one — the effective number of "training examples" per step scales with sequence length practically for free.
**Follow-up trap:** *"Does this mean doubling sequence length doubles your effective batch size for free?"* — not for free: attention cost grows quadratically in sequence length (`T05-attention`), so you get more supervision signal per sequence but at superlinear compute cost, not a free lunch; the actual production tradeoff is total tokens processed per step, not "number of loss terms," since a longer sequence with the same batch size costs more FLOPs and memory per step.

### Q7 — What's multi-token prediction and how does it relate to teacher forcing and exposure bias?
**Answer:** Instead of predicting only the single next token at each position, the model is trained with auxiliary heads to predict several future tokens (`t+1, t+2, t+3, ...`) from the same hidden state, still under teacher forcing (all targets come from the true sequence). DeepSeek-V3 and Meta's 2024 work use this to give the model a denser training signal and some implicit "lookahead" pressure during pretraining.
**Follow-up trap:** *"Does multi-token prediction eliminate exposure bias?"* — no. It's still fully teacher-forced at training time (every future-token target is the true one, not a self-generated one), and generation is still one token at a time at inference (the extra heads are typically discarded or used only for draft tokens in speculative decoding). It's a pretraining signal-density improvement, not a fix for the train/inference conditioning mismatch.

### Q8 — Explain scheduled sampling and why it's rarely used at LLM pretraining scale today.
**Answer:** Scheduled sampling (Bengio et al., 2015) occasionally feeds the model its own sampled prediction, instead of the ground-truth token, as the conditioning input during training, with the substitution probability annealed up over training to gradually expose the model to its own error distribution. It directly targets exposure bias, but it reintroduces a sequential dependency at training time — computing the model's input at position `t` may require having already sampled position `t-1`'s output — which breaks the single-parallel-pass property that makes trillion-token teacher-forced pretraining computationally affordable.
**Follow-up trap:** *"If it targets exposure bias directly, why do we use RLHF/DPO/GRPO instead?"* — those methods achieve the same "train on the model's own outputs" property but as a separate, much smaller post-training stage on top of a fully parallel-trained base model, rather than paying the parallelism cost across the entire (vastly larger) pretraining run.

### Q9 — Why does RL-based post-training (GRPO/RLVR) matter specifically for reasoning models in the context of exposure bias?
**Testing:** connecting this module to `T05-alignment` correctly.
**Answer:** Chain-of-thought reasoning traces are long, and a single wrong intermediate step compounds into a wrong final answer — precisely the exposure-bias failure shape. Teacher-forced pretraining never penalizes a chain of compounding errors specifically, because it only ever sees true prefixes. GRPO/RLVR trains directly on full autoregressive rollouts (the actual reasoning chains the model generates) scored against a verifiable outcome (a unit test passing, a math answer matching), so the reward signal directly reflects whether the model's own compounding behavior, errors included, produces a correct result.
**Follow-up trap:** *"Doesn't RLVR just reward the final answer — how does that fix intermediate compounding errors specifically?"* — it doesn't directly localize the error to a specific token, but because the reward is computed over the model's actual sampled rollout (not a teacher-forced one), gradient signal from correct vs. incorrect final outcomes propagates back through whatever intermediate steps the policy actually took, which is qualitatively different supervision than never having seen a self-generated chain at all during pretraining.

### Q10 — Design an evaluation protocol that would actually catch an exposure-bias regression before it ships, for a model fine-tuned for long-form report generation.
**Testing:** staff-level synthesis — turning the concept into an actual eval plan.
**Answer:** Don't rely solely on held-out teacher-forced perplexity/loss, since it structurally can't see this failure mode. Add: (1) free-running generation at production-representative lengths (not short smoke-test lengths), scored by both automated repetition/coherence metrics and human or LLM-judge review specifically for late-generation quality; (2) a length-stratified eval — quality score as a function of position within the generation, watching for a cliff rather than a smooth decline; (3) self-consistency checks — regenerate from the same prompt multiple times and check variance in late-generation quality, since exposure-bias-driven drift tends to be sensitive to small early sampling differences.
**Follow-up trap:** *"What's the concrete threshold that would block a release?"* — a staff-level answer states one: e.g., "quality score at the last quartile of generation length must not drop more than X% relative to the first quartile, measured on N held-out long-form prompts" — a vague "check if it seems worse at the end" isn't a shippable eval gate.

---

## Red flags that fail you

- Saying "the model predicts the next word" and stopping there, with no mention of teacher forcing or the train/inference gap.
- Calling any long-generation quality problem "hallucination" without distinguishing exposure bias, context truncation, and positional-encoding extrapolation failure — they have different fixes.
- Claiming teacher forcing is a flaw that should be removed from pretraining, with no acknowledgment of the parallelism it buys.
- Not knowing that RLHF/DPO/GRPO post-training scores real autoregressive rollouts, which is precisely why it partially closes the exposure-bias gap that pretraining cannot.
- Confusing multi-token prediction (a pretraining auxiliary objective, still teacher-forced) with a fix for exposure bias.

---

## Cheat card

```
FACTORIZATION   p(x_1..x_n) = prod_t p(x_t | x_<t)          -- autoregressive / causal LM
LOSS            L = -sum_t log p_theta(x_t | x_<t)          -- teacher forcing: x_<t is TRUE prefix
WHY TF          all positions' loss computed in ONE parallel forward pass (causal mask)
                -- this is what RNNs (sequential hidden state) could NOT do
EXPOSURE BIAS   train: conditions on true prefix. infer: conditions on OWN generated prefix.
                model never trained to handle a prefix containing its own errors
SYMPTOM         good teacher-forced perplexity + degrading free-running generation over length
                = exposure-bias signature (dissociation is the diagnostic)
COMPOUNDING     one low-prob error -> context shifts out-of-distribution -> every later token
                conditioned on that corrupted context -> repetition loops, topic drift
SCHEDULED SAMP  (Bengio 2015) feed model's own sample sometimes during training -- breaks
                parallelism, rarely used at LLM pretraining scale
REAL FIX        RLHF/PPO, DPO, GRPO -- score MODEL'S OWN rollouts, not teacher-forced likelihood
                -- closes train/inference gap because eval distribution = deployment distribution
GRPO/RLVR LINK  reasoning chains are long -> one bad step compounds -> RL-on-rollouts trains
                directly against the compounding failure mode, unlike teacher-forced pretraining
MULTI-TOKEN     DeepSeek-V3/Meta 2024: predict several future tokens per position, STILL
                teacher-forced -- denser pretraining signal, NOT a fix for exposure bias
NOT A FIX       KV-cache decoding = speed optimization for the same sequential loop, unrelated
                to exposure bias
```

## Sources

- [Next-Token Prediction in AI Models](https://www.emergentmind.com/topics/next-token-prediction-ntp) — accessed 2026-07-27
- [Beyond Multi-Token Prediction: Pretraining LLMs with Future Summaries](https://arxiv.org/html/2510.14751) — accessed 2026-07-27
- [Mitigating Exposure Bias in Risk-Aware Time Series Forecasting with Soft Tokens](https://arxiv.org/html/2512.10056v1) — accessed 2026-07-27
- [4. From Teacher Forcing to Self-Forcing++: A Tutorial on Autoregressive Video Generation](https://medium.com/@aminfadaeinejad.edu/from-teacher-forcing-to-self-forcing-a-tutorial-on-autoregressive-video-generation-fb20b1ac72ad) — accessed 2026-07-27
- [Post-Training in 2026: GRPO, DAPO, RLVR & Beyond](https://llm-stats.com/blog/research/post-training-techniques-2026) — accessed 2026-07-27

## Changelog
- 2026-07-27 — created
