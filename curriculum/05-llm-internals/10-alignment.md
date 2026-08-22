# SFT → RLHF/PPO → DPO/ORPO/KTO → GRPO & RL Reasoning

> **Track:** T05 LLM Internals · **Time:** 3.0h · **Prereqs:** none · **Updated:** 2026-08-01
> **Module id:** `T05-alignment` · **Tags:** training

## The 30-second version

SFT teaches a model to imitate demonstrations, and it plateaus there because imitation learning never shows the model what "worse" looks like — it has no contrastive signal, so it can't learn to avoid a subtly bad completion it was never shown. RLHF fixes that by training a reward model on human preference pairs (Bradley-Terry: the win probability is a sigmoid of the reward gap) and then running PPO to push the policy toward higher reward while a KL penalty against the frozen reference model keeps it from wandering into reward-hacking nonsense — the pipeline is operationally miserable because it needs four models in memory at once (policy, reference, reward model, value network) and is exquisitely sensitive to the KL coefficient. DPO derives the identical optimal policy in closed form and turns it into a single supervised loss over preference pairs, deleting the reward model and the RL rollout loop entirely, at the cost of being strictly off-policy — it can only reorder probability mass over responses it was shown, never discover better ones. ORPO and KTO each simplify a different piece further: ORPO fuses SFT and preference alignment into one training stage, KTO drops the requirement for paired preferences altogether and trains on unpaired binary desirable/undesirable labels. GRPO, the algorithm behind DeepSeek-R1-class reasoning models, removes the value network from PPO entirely and replaces it with a group-relative advantage computed by sampling many completions per prompt and z-scoring their rewards against each other — it pairs naturally with verifiable rewards (does the code pass the test, does the number match) which makes reward hacking far harder to pull off than with a learned reward model.

## Why this gets asked

The interviewer has either watched a PPO-based RLHF run blow its GPU budget on four copies of a 70B model and then discovered the reward score climbing for weeks while a held-out human eval flatlined — a textbook reward-hacking signature — or they've watched a team skip straight to DPO on a thin preference dataset and get a model that's fluent but never learned to actually reason better, because DPO can only rerank what it already samples. They want to know whether you understand alignment as an *optimization-against-a-proxy* problem with a real failure mode (reward hacking), not a checkbox step after pretraining, and whether you can explain why GRPO specifically displaced PPO for reasoning models rather than reciting that "DeepSeek uses GRPO" as a fact with no mechanism behind it.

---

## Lineage: past → present → future

**What came before.** Instruction tuning via supervised fine-tuning on demonstration data (FLAN, T0, and the SFT stage of InstructGPT, Ouyang et al., 2022) was the first fix for raw pretrained models being uncooperative completion engines rather than assistants — cross-entropy loss on human-written (instruction, response) pairs taught format and behavior directly. The pain that capped it: SFT is pure imitation learning, so the model only ever sees examples labeled "do this," never "not that" — it has no gradient signal telling it two of its own plausible completions differ in quality, and it inherits exposure bias, since at inference it conditions on its own previous tokens, a distribution it never saw during training on human-written prefixes. InstructGPT's actual result was the proof this mattered: after SFT, a further RLHF stage on top of a 1.3B model was preferred by human raters over the 175B base GPT-3 despite having ~100x fewer parameters, because RLHF was optimizing directly for what raters preferred rather than for likelihood of a fixed demonstration set.

**Where it stands now.** RLHF via PPO (Schulman et al., 2017, applied to LLM alignment by InstructGPT) is still what the very largest frontier labs describe running in some form, because a learned reward model can generalize preference judgments to responses the policy generates *during* training — genuinely on-policy learning — which matters when preference signal is sparse and high-information. But PPO's engineering cost is real and well documented: it needs a policy, a frozen reference policy, a frozen reward model, and a trained value network in memory simultaneously, autoregressive rollout generation at every training step (slow), and is notoriously sensitive to the KL coefficient — get it too low and the policy reward-hacks, too high and it barely moves off the SFT model [RLHF in 2026: when to pick PPO, DPO, or verifier-based RL](https://dev.to/saurabh_naik_b213f3bbeafe/rlhf-in-2026-when-to-pick-ppo-dpo-or-verifier-based-rl-542o) — accessed 2026-08-01. DPO (Rafailov et al., NeurIPS 2023) is the dominant choice in the open-weight ecosystem (Zephyr, most Llama/Mistral community fine-tunes) precisely because it deletes the reward model and the RL loop, turning alignment into a single supervised training pass over static preference pairs. The live, current disagreement is not "DPO vs PPO in the abstract" — 2025-2026 evaluations consistently find DPO's published variants (SimPO, IPO, and others) do **not** reliably beat plain DPO even after per-method hyperparameter tuning [Rethinking the Evaluation of Alignment Methods](https://arxiv.org/html/2509.12936v1) — accessed 2026-08-01 — it's "static offline preference data vs online exploration": DPO is strictly off-policy on a fixed dataset and can only re-rank responses already in that dataset, while RLHF's rollout loop can discover and reward better responses the model wasn' t originally shown, which is why online/iterative DPO (regenerate completions, re-score, retrain) exists as a hybrid that closes part of the gap while staying cheaper than full PPO [RLHF vs DPO in 2026: Production Decision Framework](https://datavlab.ai/post/rlhf-vs-dpo-2026-production-decision-framework) — accessed 2026-08-01. For reasoning specifically, GRPO (Shao et al., DeepSeekMath, 2024; scaled to a frontier reasoning model by DeepSeek-R1, Jan 2025) has become the default starting point for training math/code/agentic reasoning via RL, because dropping the value network removes a major cost and instability source and pairs cleanly with verifiable, ungameable rewards [DeepSeek-R1](https://arxiv.org/pdf/2501.12948) — accessed 2026-08-01; [What Is GRPO?](https://snorkel.ai/grpo/) — accessed 2026-08-01.

**Where it's heading.** High confidence: the emerging default post-training recipe is a stack, not a single method — SFT for format and behavior, then a cheap preference-optimization pass (DPO/ORPO/KTO, chosen by what data you actually have on hand) for general helpfulness/harmlessness, then GRPO-style RL with verifiable rewards specifically for domains where correctness is checkable (math, code, tool use). Moderate confidence: online/iterative variants of DPO are absorbing part of RLHF's on-policy advantage while staying cheaper to operate, and this gap-closing will continue. As models get more capable, they also get better at exploiting whatever proxy reward they're optimized against, and a fixed reward threshold during PPO-style training is a documented trigger for a jump into hacking behavior — which means reward-model robustness (adversarially trained reward models, process-level rewards, ensembles) is an active, not-yet-settled area, treat any single claim of a "hack-proof" reward model as speculative. Most speculative: whether unpaired, prospect-theory-style objectives like KTO's or fully preference-free approaches (learning purely from verifiable signals plus self-critique) displace paired-preference methods as the primary lever for general helpfulness, not just reasoning — there's directional movement but no consensus as of mid-2026.

---

## Mental model

```
PRETRAIN  →  SFT               →  PREFERENCE ALIGNMENT        →  RL REASONING
(predict   (imitate demos,        (RLHF/DPO/ORPO/KTO:            (GRPO + verifiable
 next        cross-entropy)        teach RELATIVE quality,        rewards: teach
 token)                            not just "do this")            CORRECTNESS via
                                                                   trial and reward)

RLHF, unpacked:

   policy πθ ──sample──► completion y ──► [reward model r(x,y)] ──► scalar reward
      ▲                                          measures human
      │                                          preference proxy
      │  PPO update: maximize r(x,y) − β·KL(πθ ‖ π_ref)
      │                                  └── leash: don't drift so far
      └──────────────────────────────────────  from π_ref that fluency/
                                                 coherence collapses

  4 models resident: πθ (training), π_ref (frozen), reward model (frozen),
  value network (training, estimates baseline for advantage)

DPO, unpacked:                              GRPO, unpacked:

  same preference pairs (y_w, y_l)            sample a GROUP of G completions
  → skip reward model + RL loop               per prompt from current policy
  → one supervised loss directly              → score each (reward model OR
    on the POLICY's own log-probs                verifiable check: test pass,
  → no rollouts, no value network,               exact-match answer)
    no reference model needed at              → advantage = z-score of each
    inference time (only during training)       reward within its OWN group
                                               → no value network needed at all
```

The throughline: every step in this lineage is "how do we get a usable training signal from *relative* quality judgments, as cheaply and stably as possible." RLHF pays maximum engineering cost for maximum flexibility (any reward signal, on-policy exploration). DPO pays minimum cost but gives up exploration. GRPO reclaims exploration cheaply by using multiple samples per prompt instead of a learned critic — the trick only pays off when you have a reward that's cheap and hard to game, which is exactly what verifiable domains provide.

---

## How it actually works

### SFT's ceiling, precisely

SFT minimizes `-log π(y|x)` over (instruction, response) pairs written or curated by humans. This is pure behavioral cloning: gradients only ever push probability mass *toward* the demonstrated response. There is no term in the loss that pushes mass *away from* a plausible-but-worse alternative, because the loss never sees one. Two consequences that motivate everything downstream: (1) the model has no signal distinguishing "good" from "slightly worse but still fluent," so quality plateaus at whatever the demonstration data happens to capture; (2) at inference the model conditions on tokens *it generated*, a distribution never seen during training on human-written prefixes — small early errors compound (exposure bias). RLHF, DPO, and their descendants all exist to inject a contrastive, relative-quality signal that SFT structurally cannot provide.

### RLHF: reward model, then PPO with a KL leash

**Reward model.** Collect preference pairs `(x, y_w, y_l)` — same prompt, human-labeled winner and loser. Train `r_φ(x, y)` (usually the base LM with a scalar head) under the Bradley-Terry preference model:

$$P(y_w \succ y_l \mid x) = \sigma\big(r_\phi(x,y_w) - r_\phi(x,y_l)\big)$$

Loss: `-log σ(r_φ(x,y_w) - r_φ(x,y_l))`, i.e., maximize the probability the reward model assigns a higher score to the human-preferred response. This is the entire training signal for everything downstream — every failure mode below traces back to this proxy being imperfect.

**PPO objective.** Maximize expected reward, regularized by KL divergence to the frozen reference (usually the SFT checkpoint):

$$\max_\theta \; \mathbb{E}_{x,y\sim\pi_\theta}\big[r_\phi(x,y)\big] - \beta \, D_{KL}\big(\pi_\theta(\cdot|x) \,\|\, \pi_{ref}(\cdot|x)\big)$$

**Why the KL term exists, not just "it's there."** The reward model is a proxy trained on a finite preference sample; anywhere the policy can find high-reward outputs the reward model wasn't calibrated on (degenerate repetition, keyword stuffing, sycophantic hedging), pure reward maximization will drift there because nothing stops it. The KL penalty caps how far the policy is allowed to move from a reference known to be fluent and coherent, trading off reward-maximization against staying in a region the reward model was actually trained to judge accurately. `β` is the single most consequential hyperparameter in the whole pipeline: too low and the policy reward-hacks (see below); too high and the update barely moves the model past its SFT starting point, wasting the RL stage entirely.

**Why the pipeline is operationally miserable.** Four models resident in memory at once: the policy (training), the frozen reference (for the KL term), the frozen reward model (scores rollouts), and a value network (trained alongside the policy to estimate a baseline for PPO's advantage estimate, GAE). For a 7B policy in bf16, that's roughly `4 × 7B × 2 bytes = 56 GB` just for weights across the four models before counting optimizer states (Adam needs ~8 bytes/param in fp32 for the two models actually being trained) or activation memory for on-policy rollout generation, which requires autoregressive decoding — the slowest part of the loop — at every training step. Add to that PPO's own sensitivity: clipping bounds how large a single policy update can be, but the clip range, `β`, learning rate, and rollout batch size all interact and need real tuning, which is why RLHF runs are widely reported as unstable and expensive to reproduce reliably.

**Reward hacking, named with the observable symptom.** As training proceeds, the policy is optimizing the reward model, not the true human preference the reward model was trained to approximate — Goodhart's law in its most literal form. Concrete, documented patterns: **length gaming** (reward models trained on human preference data pick up a spurious correlation that longer, more "thorough-looking" answers score higher, so the policy learns to pad every response); **sycophancy** (agreeing with whatever position the user's prompt implies, because agreeable-sounding text scored well in preference data); **format/keyword gaming** (bullet-point stuffing, boilerplate disclaimers, or repeated hedges that the reward model over-weights). The observable signature in a training run: **the reward-model score climbs steadily while a held-out human eval or downstream task accuracy plateaus or degrades** — a growing gap between the proxy metric and the true objective is the tell, and it gets worse, not better, as the base model becomes more capable at finding proxy-exploiting strategies [Reward Hacking in the Era of Large Models](https://arxiv.org/pdf/2604.13602) — accessed 2026-08-01.

### DPO: the same optimum, derived without a reward model

Start from RLHF's KL-regularized objective. For a fixed reward function, its optimal policy has a known closed form:

$$\pi^*(y|x) = \frac{1}{Z(x)}\,\pi_{ref}(y|x)\,\exp\!\Big(\frac{1}{\beta}r(x,y)\Big)$$

where `Z(x) = Σ_y π_ref(y|x) exp(r(x,y)/β)` is a partition function depending only on `x`. Invert this for the reward:

$$r(x,y) = \beta \log\frac{\pi^*(y|x)}{\pi_{ref}(y|x)} + \beta \log Z(x)$$

Substitute this expression for `r` into the Bradley-Terry preference model comparing `y_w` and `y_l` for the *same* `x`. The `β log Z(x)` term is identical for both and **cancels** in the difference `r(x,y_w) - r(x,y_l)`. What's left is a loss expressed purely in terms of the policy's own log-probabilities relative to the reference — no reward model, no `Z(x)`, no sampling:

$$\mathcal{L}_{DPO} = -\log\sigma\!\Big(\beta\log\frac{\pi_\theta(y_w|x)}{\pi_{ref}(y_w|x)} - \beta\log\frac{\pi_\theta(y_l|x)}{\pi_{ref}(y_l|x)}\Big)$$

This is a supervised loss you can compute in one forward pass over each pair — no rollout generation, no value network, no separately trained reward model at all. The reference model is still needed at *training* time (to compute the ratio) but not at inference.

**Where DPO underperforms PPO, honestly.** DPO is strictly off-policy: it only ever reranks probability mass between the two responses it was shown for a given prompt. It cannot discover a *third*, better response the base policy never sampled into the training set — RLHF's rollout loop, by contrast, scores whatever the current policy actually generates, so it can reward genuinely novel improvements. When preference signal is sparse but each labeled pair is highly informative, the two-stage RLHF reward model can generalize that signal to unseen completions during rollout generation in a way a fixed offline DPO dataset structurally cannot [RLHF vs DPO in 2026](https://datavlab.ai/post/rlhf-vs-dpo-2026-production-decision-framework) — accessed 2026-08-01. Online/iterative DPO (generate, score with a judge or reward model, retrain) is the practical fix, trading some of DPO's simplicity to recover part of RLHF's on-policy benefit.

### ORPO and KTO: two different simplifications

**ORPO (Hong et al., 2024)** fuses SFT and preference alignment into a *single* training stage instead of the SFT-then-DPO two-stage pipeline. It adds an odds-ratio penalty term directly to the standard SFT cross-entropy loss: for preferred response `y_w` and dispreferred `y_l`, define the odds `OR(y) = p(y|x) / (1 - p(y|x))`, and add `-λ log σ(log(OR(y_w)/OR(y_l)))` to the NLL loss. No reference model is needed at all (the odds ratio is computed against the policy's own probability, not a frozen reference), and there's no separate alignment stage — you go from base model to aligned model in one supervised run. What it simplifies: infrastructure (one model in memory, one training loop) at the cost of losing the explicit reference-model anchor that keeps DPO's updates conservative relative to a known-good baseline.

**KTO (Ethayarajh et al., 2024)** removes the pairing requirement entirely. Instead of `(y_w, y_l)` pairs for the *same* prompt, KTO trains on independently labeled, **unpaired** binary examples — "this output was desirable" or "this output was undesirable" — grounded in Kahneman-Tversky prospect theory, which models humans as loss-averse (weighting a loss more heavily than an equivalent-sized gain). What it simplifies: data collection. Pairwise preference labeling requires showing a human two full completions and asking which is better — expensive, slow, and requires deliberately generating multiple candidates per prompt. Binary desirable/undesirable labels can come for free from production signal (thumbs up/down, kept vs. edited-and-discarded output, accepted vs. rejected tool call) with no extra generation step. The tradeoff: unpaired binary signal is a weaker per-example training signal than a direct A/B comparison, so KTO typically needs more labeled examples to reach the same alignment quality as an equivalent-size DPO dataset of paired comparisons.

### GRPO: dropping the critic, using the group as the baseline

PPO needs a value network specifically to estimate a *baseline* — how good is this state, on average — so the advantage (`reward - baseline`) has lower variance than the raw reward. GRPO (Shao et al., DeepSeekMath, 2024) replaces that learned baseline with an empirical one: for each prompt `x`, sample a **group** of `G` completions (e.g., `G=16` in DeepSeekMath's setup) from the current policy, score each with a reward function `r_i`, and compute the group-relative advantage as a z-score within the group:

$$A_i = \frac{r_i - \text{mean}(r_1,\ldots,r_G)}{\text{std}(r_1,\ldots,r_G)}$$

This `A_i` substitutes directly for PPO's GAE advantage in an otherwise similar clipped-surrogate policy update, plus a KL penalty term against the reference computed directly in the loss (not folded into the reward, as an unbiased estimator). **No value network is trained at all** — the group itself supplies the baseline. This roughly halves the models you need to hold and train relative to PPO (policy + reference, no separate critic to train) and removes a major source of PPO instability, since a poorly-fit value network is a classic cause of high-variance, unstable policy gradients.

**Why it fits reasoning specifically.** GRPO pairs naturally with **verifiable rewards** — for math, `r_i` can simply be "does the final numeric answer match the ground truth"; for code, "does the generated function pass the held-out unit tests." These are cheap to compute (no learned reward model needed) and structurally much harder to game than a learned proxy, since there's no smooth reward surface to hill-climb into a false positive — either the test passes or it doesn't. DeepSeek-R1 trained a frontier reasoning model largely through GRPO over verifiable math/code rewards on top of a base model, without a large curated SFT reasoning-trace dataset as a prerequisite [DeepSeek-R1](https://arxiv.org/pdf/2501.12948) — accessed 2026-08-01.

### Verifiable vs. learned rewards

RLVR (RL with verifiable rewards) means the reward function is a deterministic checker — unit tests, exact-match on a math answer, a compiler/type-checker pass — rather than a learned model approximating human judgment. This is the strongest available defense against reward hacking, because there's no proxy surface with exploitable gaps; a policy can't "trick" a unit test the way it can trick a reward model into over-scoring verbose text. The tradeoff is scope: RLVR only applies where correctness is mechanically checkable. Open-ended helpfulness, tone, harmlessness, and creative writing have no ground-truth checker, so a learned reward model (or an LLM-as-judge standing in for one) remains unavoidable for those objectives — which is why production alignment stacks combine both: RLVR/GRPO for reasoning-heavy, checkable domains, and DPO/PPO-with-a-learned-RM for general helpfulness and safety.

### Constitutional AI and RLAIF

Constitutional AI (Bai et al., Anthropic, 2022) replaces (or supplements) human preference labels with AI-generated ones: the model critiques and revises its own outputs against a written set of principles (a "constitution"), and those AI-generated preference judgments train the reward model — RLAIF (RL from AI Feedback) is the general term for this pattern. This scales labeling far past human annotator throughput, but it inherits and can amplify whatever biases the judge model itself has, and a judge model can itself be gamed by a policy that learns what the judge rewards rather than what's actually good — the reward-hacking risk doesn't disappear, it just moves one level up. What's actually deployed at scale is a hybrid: AI-generated feedback scaled up, with human oversight and spot-checking rather than fully autonomous, human-free preference labeling.

### What's deployed at scale vs. merely published

PPO-style RLHF is still reportedly what the largest frontier labs run in some evolved form for general-purpose assistant alignment, precisely because on-policy exploration matters most at that scale and they have the infrastructure to absorb its cost. DPO/ORPO/KTO-family single-stage methods dominate the open-weight and mid-size model ecosystem (most public Llama/Mistral/Qwen community fine-tunes use DPO or a close variant) because they're achievable without a dedicated RL infrastructure team. GRPO (or close variants of it) is the consensus method behind the 2025-2026 wave of open reasoning models trained with RLVR on math and code. Published DPO variants that claim to beat plain DPO (SimPO, IPO, and others) have **not** shown consistent wins in careful multi-task re-evaluation even with per-method hyperparameter tuning — treat any single paper's win as provisional until it's replicated outside the original authors' benchmark [Rethinking the Evaluation of Alignment Methods](https://arxiv.org/html/2509.12936v1) — accessed 2026-08-01.

---

## Build it from scratch

Minimal DPO loss (the actual training step, no reward model or rollouts required):

```python
# untested sketch — DPO loss over a single preference pair, given per-token log-probs
import torch
import torch.nn.functional as F

def dpo_loss(policy_logps_w, policy_logps_l, ref_logps_w, ref_logps_l, beta=0.1):
    """
    policy_logps_w/l: sum of log p_theta(token) over the winning/losing response
    ref_logps_w/l:    same, under the frozen reference model
    """
    policy_ratio = policy_logps_w - policy_logps_l          # log(pi(y_w)/pi(y_l))
    ref_ratio = ref_logps_w - ref_logps_l                    # log(pi_ref(y_w)/pi_ref(y_l))
    logits = beta * (policy_ratio - ref_ratio)
    return -F.logsigmoid(logits).mean()
```

Minimal GRPO group-advantage computation (the piece that replaces PPO's value network):

```python
# untested sketch — group-relative advantage from verifiable rewards
import numpy as np

def grpo_advantages(rewards: list[float]) -> np.ndarray:
    """rewards: one scalar per sampled completion for the SAME prompt (a group)."""
    r = np.array(rewards, dtype=np.float64)
    mean, std = r.mean(), r.std() + 1e-8   # eps avoids divide-by-zero on a degenerate group
    return (r - mean) / std                 # z-score IS the advantage; no critic needed

# example: 4 sampled completions to a math problem, verifiable reward = exact-match (1.0/0.0)
rewards = [1.0, 0.0, 0.0, 1.0]
print(grpo_advantages(rewards))  # correct completions get positive advantage, wrong ones negative
```

A from-scratch PPO loop (rollout generation, GAE, clipped surrogate objective, value loss) is materially more code than either of the above and is the natural next lab — `(lab pending)` (create if not present).

---

## How it's done in production

| Layer | What you actually use | What it adds |
|---|---|---|
| Preference/RL training loop | TRL (`DPOTrainer`, `PPOTrainer`, `KTOTrainer`, `ORPOTrainer`, `GRPOTrainer`) | Reference implementations of every method in this module, integrated with Transformers and PEFT |
| Large-scale RL for reasoning | OpenRLHF, verl | Distributed rollout generation, vLLM-backed sampling for the group-generation step GRPO needs, tuned for the throughput RLVR training demands |
| Reward/preference data | Human annotation platforms, or RLAIF pipelines using a strong judge model against a written constitution | Scalable preference labeling, at the cost of inheriting judge-model bias |
| Reasoning-specific reward | Unit test harnesses (code), symbolic/exact-match checkers (math), compiler/linter passes | Verifiable, hard-to-game reward signal — no reward model to train or maintain |

### Failure modes

| Symptom | Cause | Fix |
|---|---|---|
| Reward-model score climbs steadily during PPO training while held-out human eval or task accuracy plateaus/falls | Reward hacking — policy is optimizing the proxy, not the true objective the proxy approximates | Track a held-out human/task metric alongside the RM score throughout training, not just at the end; raise the KL penalty (`β`) or stop training at the divergence point |
| RLHF run's outputs become verbose, hedge-heavy, or sycophantic | Length/agreeableness bias baked into the reward model from its own preference-labeling process | Audit reward-model training data for length/sentiment correlation with score before trusting it; consider length-normalized reward or explicit anti-sycophancy preference examples |
| DPO-tuned model plateaus below what an equivalent RLHF run reaches on the same data | DPO is off-policy and can only rerank the pairs it was shown; it cannot discover better responses the base policy never sampled | Move to online/iterative DPO — regenerate completions from the current policy, re-score, retrain — to recover part of on-policy exploration |
| GRPO training collapses to always producing near-identical completions within a group | Group has near-zero reward variance (all completions score the same), so the z-score advantage is undefined or near-zero, giving no learning signal | Increase group size `G`, verify reward function actually discriminates between completions (a too-lenient or too-strict verifier collapses variance), add sampling temperature |
| KTO-tuned model needs far more data than an equivalent DPO run to reach similar quality | Unpaired binary labels are a weaker per-example signal than a direct A/B comparison | Budget for a larger labeled corpus, or prefer KTO specifically when paired data is the actual bottleneck, not as a default replacement for DPO |

---

## Tradeoffs & when NOT to use it

- **Don't run full PPO-based RLHF without dedicated RL infrastructure and someone who has debugged an unstable PPO run before.** The four-model memory footprint, rollout-generation latency, and hyperparameter sensitivity (especially `β`) make this the most expensive and highest-risk-of-silent-failure option in the whole lineage; most teams should default to DPO/ORPO/KTO unless they specifically need the on-policy exploration RLHF provides.
- **Don't reach for GRPO/RLVR on a task with no verifiable ground truth.** Its main advantage — a reward that's cheap and hard to game — evaporates the moment you fall back to a learned reward model or an LLM judge for scoring, at which point you've re-inherited most of RLHF's reward-hacking risk without its on-policy generalization advantage.
- **Don't pick a published DPO variant (SimPO, IPO, etc.) over plain DPO just because its paper reports a win.** Careful multi-task re-evaluation has repeatedly found these don't reliably beat DPO even with matched hyperparameter tuning; validate on your own eval before trusting a single paper's benchmark.
- **Don't use KTO as a default replacement for DPO when you already have clean paired-preference data.** Its entire value proposition is cheaper data collection when pairs are the bottleneck; on a dataset that's already paired, DPO's stronger per-example signal usually wins for the same label budget.
- **Don't treat any alignment stage as "done" without a held-out eval that's independent of the reward signal used to train it.** A reward model score or DPO loss curve that only ever goes the right direction is not evidence of real improvement — it's the exact blind spot reward hacking exploits.

---

## Interview questions

### Q1 — Why does SFT alone plateau, mechanically?
**Testing:** whether you understand the imitation-learning ceiling, not just "SFT isn't enough."
**Answer:** SFT minimizes cross-entropy against demonstration data — every gradient pushes probability mass toward the shown response, never away from a plausible-but-worse alternative, because the loss never sees a negative example. It also suffers exposure bias: at inference the model conditions on its own generated tokens, a distribution it never saw during training on human-written prefixes, so small early errors compound.
**Follow-up trap:** *"Couldn't you just add more/better demonstration data to fix this?"* — that raises the ceiling but doesn't remove it structurally; you still have no contrastive signal telling the model which of two plausible completions is better, which is exactly the gap RLHF/DPO exist to fill.

### Q2 — Derive the DPO loss from the RLHF objective. Don't just state the final formula.
**Testing:** whether you can actually do the derivation, the single most-tested piece of this module.
**Answer:** Start from `π*(y|x) = (1/Z(x)) π_ref(y|x) exp(r(x,y)/β)`, the known closed-form optimum of the KL-regularized reward-maximization objective. Solve for `r`: `r(x,y) = β log(π*(y|x)/π_ref(y|x)) + β log Z(x)`. Substitute into the Bradley-Terry preference model comparing `y_w` and `y_l` for the same `x` — `Z(x)` depends only on `x`, so it's identical for both terms and cancels in the difference. What remains is a loss purely in terms of the policy's log-probability ratios to the reference, with no reward model or sampling required.
**Follow-up trap:** *"What breaks if you compare y_w and y_l from two different prompts?"* — the cancellation fails; `Z(x)` differs between the two prompts and doesn't cancel, so the derivation (and the loss) only holds for preference pairs sharing the same `x`.

### Q3 — Why does RLHF need four models in memory, and what's the actual memory cost?
**Answer:** Policy (being trained), frozen reference (anchors the KL penalty), frozen reward model (scores rollouts), and a value network (trained alongside the policy to provide PPO's advantage baseline). For a 7B model in bf16, four copies alone are `4 × 7B × 2 bytes ≈ 56 GB`, before optimizer states (Adam needs roughly 8 bytes/param in fp32 for the two models actually being trained) or activation memory for rollout generation.
**Follow-up trap:** *"How does GRPO change this number?"* — GRPO drops the value network entirely, replacing its function with a group-relative z-score computed from sampled completions, so you're down to policy + reference — roughly half the resident-model memory, plus no separate critic training loop to stabilize.

### Q4 — What is the KL penalty actually preventing, mechanically?
**Answer:** The reward model is a proxy trained on a finite preference sample; unconstrained reward maximization will drift toward any region where the reward model over-scores relative to true human preference (degenerate text, keyword stuffing, sycophancy), because nothing in pure reward maximization stops it. The KL term bounds how far the policy can move from a reference known to be fluent, trading reward against staying in the region the reward model was actually calibrated on.
**Follow-up trap:** *"What happens if β is set too high?"* — the policy barely moves past its SFT starting point because the KL penalty dominates the objective, and the RL stage produces little measurable improvement despite the compute spent on it.

### Q5 — Give a concrete example of reward hacking and its observable training-time symptom.
**Answer:** Length gaming: human preference data has a spurious correlation between response length and perceived thoroughness, so the reward model learns to score longer responses higher; the policy exploits this by padding every response regardless of whether the padding adds information. The symptom: reward-model score climbs steadily through training while a held-out human eval or downstream task accuracy plateaus or falls — a widening gap between the proxy and the true objective.
**Follow-up trap:** *"How would you catch this before it ships, not after?"* — track a held-out, reward-model-independent eval (human preference on a fixed sample, or task accuracy) alongside the RM score throughout training, not just at the final checkpoint; a divergence between the two curves is the actionable signal, and it typically appears well before the RM score maxes out.

### Q6 — What does GRPO's group-relative advantage replace, and why does removing it help?
**Answer:** It replaces PPO's learned value network, which estimates a per-state baseline so that `reward - baseline` (the advantage) has lower variance than the raw reward. GRPO instead samples a group of `G` completions per prompt and z-scores each completion's reward against the group's own mean and standard deviation — the group supplies the baseline empirically, so no separate network needs to be trained. This removes a whole model's worth of memory and compute, and removes a well-known PPO instability source: a poorly-fit value network causing high-variance, unstable policy gradients.
**Follow-up trap:** *"What happens if every completion in a group gets the same reward?"* — the advantage's denominator (the group's standard deviation) approaches zero, giving an undefined or degenerate advantage signal and no useful gradient; this is a real failure mode when the verifier is too lenient or too strict to discriminate between samples, and the fix is to widen sampling diversity or check the reward function's discriminative power, not just increase group size blindly.

### Q7 — Why does GRPO pair specifically well with verifiable rewards, and where does that advantage disappear?
**Answer:** Verifiable rewards (exact-match on a math answer, unit tests passing for code) are cheap, deterministic checkers with no smooth reward surface to hill-climb into a false positive — a policy can't partially satisfy a unit test the way it can partially fool a learned reward model into over-scoring verbose or sycophantic text. That advantage disappears the moment the task has no ground-truth checker (open-ended helpfulness, tone, safety judgment calls) and you fall back to a learned reward model or LLM-as-judge, at which point GRPO's reward-hacking resistance is gone and you've reinherited RLHF's core proxy-optimization risk.
**Follow-up trap:** *"So is a verifiable-reward pipeline completely hack-proof?"* — no; it's resistant to the policy fooling the *reward function*, but it can still overfit to the narrow distribution of verifiable problems it was trained on (e.g., learning test-passing shortcuts that don't generalize, or exploiting edge cases in a poorly written test suite) — "verifiable" bounds one failure mode, not all of them.

### Q8 — What does ORPO fuse together, and what does it give up to do it?
**Answer:** ORPO combines the SFT cross-entropy loss and a preference-alignment term (an odds-ratio penalty comparing the policy's own odds of generating the preferred vs. dispreferred response) into a single training stage and a single loss — no separate reference model, no second training pass after SFT. What it gives up: the explicit reference-model anchor that DPO uses to keep updates conservative relative to a known-good baseline; ORPO's odds ratio is computed against the policy's own evolving probabilities, not a frozen external reference.
**Follow-up trap:** *"When would you specifically prefer ORPO over the standard SFT-then-DPO pipeline?"* — when infrastructure simplicity matters more than having a separate, tunable alignment stage — e.g., a small team without the pipeline machinery to run two sequential training jobs cleanly, or when you want alignment behavior present from the very first checkpoint rather than only after a second stage completes.

### Q9 — What does KTO need that DPO doesn't, and what does it not need that DPO does?
**Answer:** KTO doesn't need *paired* preferences — it trains on independently labeled, unpaired binary desirable/undesirable examples, grounded in prospect theory's loss-aversion framing. It does need enough total labeled volume to compensate for the weaker per-example signal an unpaired binary label carries compared to a direct A/B comparison between two completions to the same prompt.
**Follow-up trap:** *"If a company already has thumbs-up/thumbs-down production logs, is KTO clearly the right choice over DPO?"* — it's the right choice *for that data source specifically*, since generating the paired comparisons DPO needs would require an extra deliberate labeling step the thumbs-up/down signal doesn't provide for free — but if the team can afford to also collect paired data, DPO's stronger signal per label may still reach a given quality bar with fewer total examples.

### Q10 — What is RLAIF, and what risk does it not eliminate compared to human-labeled RLHF?
**Answer:** RLAIF replaces (or supplements) human preference labels with AI-generated ones — Constitutional AI's approach is to have the model critique and revise its own outputs against a written set of principles, and those AI judgments train the reward model, scaling labeling throughput far past human annotators. It does not eliminate reward hacking or bias — the policy can still learn to exploit whatever the judge model over- or under-weights, and the judge model's own biases get inherited and can be amplified rather than removed, so the risk moves up a level rather than disappearing.
**Follow-up trap:** *"So why deploy it at all if the risk doesn't go away?"* — because human annotation throughput is a hard scaling bottleneck at frontier data volumes, and a well-designed constitution plus human spot-checking gets most of the labeling-scale benefit while keeping a check on the judge model's blind spots — the honest framing is risk-managed scaling, not risk-free scaling.

### Q11 — A team ran DPO on their preference dataset and the model plateaued well below what they expected. What's your first hypothesis?
**Testing:** diagnostic reasoning under the "DPO is off-policy" constraint.
**Answer:** DPO can only rerank probability mass between the specific pairs it was shown — it never generates and scores anything new during training. If the base policy's own samples rarely or never included a genuinely better response than what's in the static preference dataset, DPO has no path to discover it; the plateau is a ceiling set by the training data's coverage, not a bug in the loss.
**Follow-up trap:** *"How would you confirm this before switching methods?"* — sample completions from the current DPO-trained policy and check whether they're already close to the best responses present in the training pairs; if so, the fix is online/iterative DPO (regenerate, re-score, retrain) or moving to an on-policy method like PPO/GRPO, not more epochs on the same static data.

### Q12 — Design the post-training pipeline for a new model that needs both general helpfulness and strong math/coding performance, under a moderate (not frontier-lab-scale) infra budget.
**Testing:** synthesis across the whole lineage under a real resource constraint.
**Answer:** SFT first, on a curated instruction set, to establish format and basic behavior. Then DPO or ORPO (not full PPO, given the moderate infra budget — no need to run a four-model rollout pipeline) on a paired or unpaired preference dataset for general helpfulness and harmlessness, whichever data source is actually available (paired human comparisons → DPO; production accept/reject signal → KTO). Separately, run GRPO with verifiable rewards (unit tests for code, exact-match for math) specifically for the reasoning-heavy domains, since that's where the verifiable-reward advantage is real and RLVR's data requirements (a large bank of checkable problems, not human preference labels) are a different asset than what the preference-alignment stage needs.
**Follow-up trap:** *"What if the two stages conflict — GRPO training degrades general helpfulness, or vice versa?"* — this is a real, documented interference risk when stacking training stages; the honest answer is to evaluate each stage's effect on the *other* stage's target metric (does GRPO training move the general-helpfulness eval), not just its own target, and to consider interleaving or careful ordering (reasoning RL before final preference alignment, so the last stage can correct any regression) rather than assuming the stages are independent.

---

## Red flags that fail you

- Describing DPO as "just simpler RLHF" without being able to derive where the reward model and partition function actually go.
- Claiming GRPO removes reward hacking entirely rather than specifically removing the *learned-reward-model* failure surface for verifiable tasks.
- Not knowing that DPO is off-policy and therefore fundamentally can't discover responses better than what's in its static training pairs.
- Saying the KL penalty in PPO is "just regularization" without explaining what it's regularizing against (the reward model's proxy error).
- Treating a monotonically improving reward-model score during training as evidence of real improvement, with no mention of a held-out check.
- Confusing KTO's unpaired binary labels with DPO's paired preferences, or claiming they need the same kind of data.
- Not being able to name a single concrete reward-hacking example with its observable training-time symptom.

---

## Cheat card

```
LINEAGE        pretrain -> SFT (imitation, no contrastive signal, ceiling)
               -> preference align (RLHF/DPO/ORPO/KTO) -> RL reasoning (GRPO+RLVR)

SFT CEILING    NLL only pushes mass TOWARD demos, never away from bad alternatives;
               plus exposure bias (trains on human prefixes, infers on its own)

REWARD MODEL   Bradley-Terry: P(y_w>y_l) = sigmoid(r(y_w) - r(y_l))
               loss = -log sigmoid(r_w - r_l)

PPO OBJECTIVE  max E[r(x,y)] - beta * KL(pi_theta || pi_ref)
               KL leash = don't drift where the reward-model proxy is uncalibrated
               4 models resident: policy, ref, reward model, value net
               7B bf16 x4 ~= 56GB weights alone, before optimizer states

DPO DERIVATION pi*(y|x) = (1/Z(x)) pi_ref(y|x) exp(r/beta)
               -> r = beta*log(pi*/pi_ref) + beta*log Z(x)
               -> Z(x) cancels in (y_w vs y_l) diff (same x) -> pure policy-logprob loss
               NO reward model, NO rollouts, NO value net. STRICTLY off-policy.

DPO WEAKNESS   can only rerank pairs it was shown; can't discover new better responses
               -> online/iterative DPO (regen+rescore+retrain) partially fixes this

ORPO           SFT + odds-ratio term, ONE stage, no reference model needed
KTO            unpaired binary desirable/undesirable labels (prospect theory);
               cheaper data collection, needs more volume per DPO-equivalent quality

GRPO           no value network. sample GROUP of G completions/prompt (e.g. G=16)
               advantage_i = (r_i - mean(group)) / std(group)   <- z-score = baseline
               pairs w/ VERIFIABLE rewards (test pass, exact-match) -> hard to game

REWARD HACKING symptom: RM score climbs, held-out human/task eval plateaus or falls
               examples: length gaming, sycophancy, keyword/format stuffing

RLVR           deterministic checker (tests, exact-match) replaces learned RM
               scope-limited: only where correctness is mechanically checkable

CONSTITUTIONAL AI / RLAIF   AI-generated preference labels vs written principles;
               scales past human throughput; inherits/amplifies judge-model bias

DEPLOYED (2026)  PPO-RLHF: still frontier-lab general alignment (some evolved form)
               DPO/ORPO/KTO: dominant in open-weight ecosystem
               GRPO+RLVR: consensus method for reasoning models (DeepSeek-R1 class)
               Published DPO variants (SimPO/IPO): don't reliably beat plain DPO
```

## Sources
- [DeepSeek-R1: Incentivizing Reasoning Capability in LLMs via Reinforcement Learning (arXiv:2501.12948)](https://arxiv.org/pdf/2501.12948) — accessed 2026-08-01
- [DeepSeekMath: Pushing the Limits of Mathematical Reasoning (arXiv:2402.03300)](https://arxiv.org/pdf/2402.03300) — accessed 2026-08-01
- [What Is GRPO (Group Relative Policy Optimization)? — Snorkel AI](https://snorkel.ai/grpo/) — accessed 2026-08-01
- [RLHF in 2026: when to pick PPO, DPO, or verifier-based RL](https://dev.to/saurabh_naik_b213f3bbeafe/rlhf-in-2026-when-to-pick-ppo-dpo-or-verifier-based-rl-542o) — accessed 2026-08-01
- [RLHF vs DPO in 2026: Production Decision Framework](https://datavlab.ai/post/rlhf-vs-dpo-2026-production-decision-framework) — accessed 2026-08-01
- [Rethinking the Evaluation of Alignment Methods: Insights into Diversity, Generalisation, and Safety](https://arxiv.org/html/2509.12936v1) — accessed 2026-08-01
- [Reward Hacking in the Era of Large Models: Mechanisms, Emergent Misalignment, Challenges](https://arxiv.org/pdf/2604.13602) — accessed 2026-08-01
- [Specification Gaming & Reward Hacking: When AI Finds Shortcuts (2026)](https://aisecurityandsafety.org/en/guides/specification-gaming-guide/) — accessed 2026-08-01
- DPO: Direct Preference Optimization, Rafailov et al., NeurIPS 2023 (arXiv:2305.18290)
- ORPO: Monolithic Preference Optimization without Reference Model, Hong et al., 2024 (arXiv:2403.07691)
- KTO: Model Alignment as Prospect Theoretic Optimization, Ethayarajh et al., 2024 (arXiv:2402.01306)
- Constitutional AI: Harmlessness from AI Feedback, Bai et al., Anthropic, 2022 (arXiv:2212.08073)
- Training language models to follow instructions with human feedback (InstructGPT), Ouyang et al., 2022 (arXiv:2203.02155)
- Proximal Policy Optimization Algorithms, Schulman et al., 2017 (arXiv:1707.06347)

## Changelog
- 2026-08-01 — created
