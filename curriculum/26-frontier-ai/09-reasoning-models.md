# Reasoning Models: Test-Time Compute, RL on Chains, What Actually Changed

> **Track:** T26 Frontier AI · **Time:** 2.5h · **Prereqs:** T05 (attention, inference serving), `T07-loop-engineering`
> **Updated:** 2026-08-08
> **Module id:** `T26-reasoning-models` · **Tags:** reasoning, test-time-compute, rl, grpo, critical

## The 30-second version

A reasoning model — OpenAI's o-series and GPT-5.5 Thinking, DeepSeek-R1, Claude's extended thinking, Gemini Deep Think — is trained with reinforcement learning against a **verifiable** reward (does the final answer match, does the code pass tests), not purely imitating human-written demonstrations, and the RL objective rewards reaching the right answer regardless of how many tokens it takes to get there. The emergent side effect, not an explicitly engineered feature, is that models trained this way generate long internal chains of thought before answering, and spending more inference compute generating that chain produces a smooth, steep accuracy improvement on hard, checkable problems: o3 went from **75.7%** to **87.5%** on ARC-AGI-1 using roughly **172x** more test-time compute, at a cost of **thousands of dollars per task** at the high end. DeepSeek-R1 (January 2025) proved the recipe is reproducible and cheap to open-source, using **GRPO** (Group Relative Policy Optimization), a critic-free RL algorithm that estimates a baseline from a group of sampled completions instead of training a separate value model. The honest, evidence-backed position on "what actually changed" is narrower than the marketing: a NeurIPS 2025 study measuring **pass@k at large k** found RL-trained reasoning models beat their base model at small k (better first-try accuracy) but the **base model matches or exceeds the RL-tuned model at large k** — meaning RL mostly sharpens sampling toward correct paths the base model could already reach given enough tries, rather than expanding what's reachable at all; genuine new-capability expansion in that study came from distilling a stronger teacher's traces, not from RL itself. That's a real, useful, deployed capability (first-shot accuracy on hard verifiable problems is exactly what a product needs), just not the "the model learned to think" story often sold. The operational cost that makes "when NOT to use it" a real interview question: hidden reasoning tokens are billed at the output-token rate (often the most expensive rate in a provider's pricing), and Amazon's internal research documented reasoning models burning **7-10x** more tokens than a standard model on simple tasks — one model spending **17 seconds** deliberating "what is 1+1" — with measured cases of latency doubling (18s to 38s) and cost rising (**$1.70 to $2.59** per task) for **zero accuracy gain**.

## Why this gets asked

The interviewer wants to know whether you can tell the test-time-compute story with actual numbers and actual limitations, rather than repeating "it's like the model gets to think before answering," which is a description, not an explanation, and tells the interviewer nothing about whether you understand the training mechanism or its cost. The production failure this maps to directly: a team defaults every agent call to the highest reasoning-effort setting because it "seems safer" or benchmarks well on hard eval sets, and then discovers in a postmortem that p50 latency tripled, spend went up 5-10x, and accuracy on the actual (mostly simple, mostly lookup-shaped) production traffic didn't move, or moved backward, because reasoning models can genuinely score worse on trivial tasks by overthinking them. At staff/principal level, the deeper probe is whether you can hold the nuanced position that RL-on-verifiable-rewards is both a real, shippable capability improvement on a specific class of problems (multi-step, verifiable, where a wrong intermediate step ruins the answer) and *not* evidence of a qualitatively new kind of reasoning, because the interviewer has likely watched a team burn a quarter building an "AGI-adjacent" roadmap on the second claim.

---

## Lineage: past → present → future

**What came before.** Prior to mid-2024, getting a language model to produce multi-step reasoning was purely a **prompting** trick applied to a model with no training-time notion that some tokens deserved more "thinking" than others. Chain-of-thought prompting (Wei et al., 2022) showed that including worked examples with explicit intermediate steps in the prompt dramatically improved performance on multi-step math and logic problems versus asking for a direct answer; zero-shot CoT (Kojima et al., 2022) showed the even simpler trick of appending "let's think step by step" achieved much of the same benefit without hand-written examples. Self-consistency (Wang et al., 2022) added a further improvement: sample several chains-of-thought independently and take a majority vote over the final answers, trading inference compute (multiple samples) for accuracy. All of this ran on models trained with standard next-token pretraining plus instruction-tuning/RLHF (the InstructGPT recipe, 2022) optimized for helpful, single-pass responses, not for reasoning length or depth. The specific pain that killed this generation as the frontier approach: it was brittle and prompt-sensitive (small wording changes materially shifted output quality), it hit diminishing returns fast (self-consistency's majority-vote gains flatten quickly as sample count grows, since all samples come from the same underlying, un-retrained distribution), and critically, the model itself had no mechanism to **backtrack** — if an early step in a sampled chain was wrong, nothing in the model's training rewarded noticing and correcting that, because the objective it was trained on never conditioned reward on the correctness of an eventual final answer reached via a long, self-generated, possibly meandering path.

**Where it stands now.** OpenAI's **o1** (released September 2024) was the first widely deployed demonstration that training a model with reinforcement learning against a reward tied to the correctness of a final, verifiable answer — not imitating a human demonstration of reasoning — produces long, internally-generated chains of thought as an emergent training outcome, and that scaling the compute spent generating that chain at inference time yields a smooth, monotonic accuracy improvement on hard, checkable problems (math competitions, coding, some scientific reasoning). The canonical, numbers-backed demonstration of how steep this scaling axis is: **o3** scored **75.7%** on ARC-AGI-1 at a standard compute budget and **87.5%** using a high-compute configuration consuming roughly **172x** more test-time compute, at an estimated cost of **thousands of dollars per task** at that setting — a genuinely dramatic capability jump bought almost entirely with inference compute, not additional training. **DeepSeek-R1** (January 2025) made the recipe reproducible and open: **DeepSeek-R1-Zero** was trained with pure RL, no supervised fine-tuning at all, using **GRPO** (Group Relative Policy Optimization), which samples a group of `G` completions per prompt, scores each with a rule-based verifier (correct final answer, passing test cases), and computes each completion's advantage as its reward normalized against the group's mean and standard deviation — eliminating the need for a separately trained critic/value network that standard PPO requires, which is a substantial cost and stability win at scale. R1-Zero exhibited genuinely emergent behavior never explicitly demonstrated in its training data: extended chains of thought that grow organically in length over training, self-correction ("aha moments" where the model's own generated text re-evaluates an earlier step and revises it), all as a side effect of optimizing purely for final-answer correctness with no length penalty and no imitation target. R1-Zero's raw output was, however, poorly formatted and hard to read, so the shipped **DeepSeek-R1** used a multi-stage pipeline (a small cold-start SFT phase for readable formatting, RL, rejection-sampling to generate cleaner training data, then a second RL phase) to become a usable product, reporting performance comparable to OpenAI's o1 across math, code, and reasoning benchmarks. By August 2026 every frontier lab ships a reasoning mode as a first-class product surface — GPT-5.5 with a router that dispatches between a standard model and "GPT-5.5 Thinking" per query, Claude's hybrid extended-thinking models (Opus 4.8 leading on tasks judged by human reviewers for nuanced quality, the Fable line retaking coding benchmarks in mid-2026), and Gemini 3.5's "Deep Think" mode, which leads on formal/scientific reasoning benchmarks and pairs with a very large context window for reasoning over large corpora. The live, load-bearing disagreement, and the fact that separates a well-informed candidate from one repeating marketing copy: a NeurIPS 2025 study ("Does Reinforcement Learning Really Incentivize Reasoning Capacity in LLMs Beyond the Base Model?") measured **pass@k** — the probability that at least one of `k` independently sampled completions is correct — at large values of `k` across RLVR-trained models and their base models. RLVR-trained models win at small `k` (better first-try accuracy, which is exactly what a single-shot product interaction needs), but as `k` grows large, **the base model's pass@k matches or exceeds the RL-trained model's**, indicating that RLVR is predominantly **sharpening sampling toward correct paths the base model could already reach given enough attempts**, not expanding the frontier of what the model can solve at all. In the same line of work, **distillation from a stronger teacher's reasoning traces** did genuinely expand capability beyond what RL alone achieved, which is a meaningfully different mechanism (learning new patterns from an external source) than RL on the model's own rollouts (re-weighting an existing distribution).

**Where it's heading.** High confidence (~85%): inference compute keeps growing as a share of total AI infrastructure spend, with industry analysts projecting it could represent roughly **75%** of total AI compute by 2030, a full inversion from the training-dominated paradigm of the early 2020s — this is already visible in how frontier labs price and market reasoning effort as a per-query dial rather than a fixed model property. High confidence (~80%): automatic routing between reasoning and non-reasoning modes, decided by the system per query rather than exposed as a manual user toggle, becomes the default product pattern, precisely because the overthinking/cost failure mode is well-documented and expensive enough that leaving the decision to end users or a static config is a liability. Medium confidence (~55%): process-level supervision (rewarding intermediate reasoning steps, not just final answers) becomes more central as the easy wins on cleanly verifiable domains (competition math, code with unit tests) saturate, but this is genuinely harder than outcome-only RLVR, because training a reliable process reward model is prone to reward hacking (the model learns to produce text that scores well on the step-verifier without the steps being logically sound) and most 2025-26 production recipes still lean on outcome-only rewards specifically to avoid that failure mode. Speculative, flagged explicitly: whether RL-on-verifiable-rewards generalizes meaningfully to open-ended domains without a clean automated verifier (subjective writing quality, ambiguous real-world judgment calls, most enterprise agentic work), or whether the entire reasoning-model paradigm stays confined to the relatively narrow, if economically important, niche of problems with checkable answers, while non-reasoning models continue improving on everything else through other means (better base pretraining, better retrieval, better tool use). The pass@k evidence above is a reason for real skepticism here, not just caution.

---

## Mental model

```
PROMPTING ERA (pre-2024)                    RL-TRAINED REASONING ERA (o1/R1+)

 base model, RLHF for helpfulness            base model, THEN RL against a
 no training signal tied to reasoning        VERIFIABLE reward (right answer /
 length or correctness of intermediate       passing tests), no length penalty
 steps                                       and no imitation target for HOW
      │                                      to reason
      ▼                                            │
 "let's think step by step"                        ▼
 (prompt engineering, external)              long CoT is an EMERGENT SIDE
      │                                      EFFECT of optimizing for
      ▼                                      correctness over long, self-
 sample N chains, majority vote              generated rollouts
 (self-consistency: MORE SAMPLES,                  │
  same underlying distribution,                    ▼
  diminishing returns fast)                  model itself decides how long
                                              to think (bounded by a
                                              reasoning_effort / budget_tokens
                                              parameter at inference)

GRPO, THE TRAINING MECHANISM (DeepSeek-R1)

  prompt --> sample G completions (no separate critic/value model needed)
              │
              ▼
        verifier scores each: reward_i = 1 (correct) or 0 (wrong)
              │
              ▼
        advantage_i = (reward_i - mean(rewards)) / std(rewards)   <- GROUP-
              │                                                       RELATIVE
              ▼                                                       BASELINE
        policy gradient update using advantage_i
        (completions that beat the group average get reinforced,
         below-average ones get suppressed)

WHY LENGTH GROWS: no length penalty in the base recipe. A LONGER chain that
eventually lands on the right answer scores the SAME reward as a short one
that does. Longer, more careful chains empirically succeed more often on
hard problems, so the optimizer drifts toward them as a side effect of
correctness-seeking, not because length itself is the target.

THE PASS@K EVIDENCE (the "what actually changed" crux)
  pass@1 (first try):     RL-trained model  >  base model
  pass@k, k LARGE:        base model        >= RL-trained model
  Interpretation: RL sharpens toward paths the base model already had
  latent access to. It does not clearly expand the frontier.
  (Distillation from a STRONGER teacher's traces DID expand it, in the
  same study -- a genuinely different mechanism from self-generated RL.)
```

---

## How it actually works

### GRPO, mechanically, and why it's cheaper than PPO

Standard PPO-based RLHF trains a separate **value/critic network** to estimate the expected future reward from any partial generation, which is used to compute an advantage (how much better a token was than expected) for the policy gradient update — training and serving that critic model roughly doubles the memory and compute footprint of the RL loop and is a real source of instability if the critic's value estimates are noisy. **GRPO** (used in DeepSeek-R1, and now widely adopted, e.g. via the `trl` library's `GRPOTrainer` and the `verl` framework) removes the critic entirely: for a given prompt, sample a **group** of `G` completions from the current policy (a typical setting is `G` in the 8-64 range depending on compute budget), score each completion with a **verifier** (a rule-based checker for math/code: does the final numeric answer match, does the generated code pass the test suite), and compute each completion's advantage as its reward **normalized against the group's own mean and standard deviation** rather than against a learned baseline. This is the entire mechanism that makes RLVR economical at frontier scale: no critic to train, no critic-induced instability, and the group itself supplies a naturally scaled, per-prompt baseline (a hard prompt where the whole group scores 0.1 reward and an easy prompt where the whole group scores 0.9 reward both produce well-calibrated advantages, because normalization happens within each group, not against a fixed global baseline).

### Outcome reward versus process reward, and why 2025-26 production leans outcome-only

An **outcome reward** checks only the final answer: correct/incorrect, tests pass/fail. It's cheap, automatable, and structurally hard to game for domains with a genuinely objective checker (a unit test either passes or it doesn't). A **process reward model (PRM)** instead scores intermediate reasoning steps, which in principle catches "right answer, wrong reasoning" and could shape *how* a model reasons, not just whether it eventually lands correctly. The reason most production RLVR recipes as of 2026 still lean heavily on outcome-only rewards despite the theoretical appeal of process supervision: PRMs are themselves learned models and are vulnerable to **reward hacking** — the policy learns to produce text that satisfies the PRM's learned notion of a "good step" without those steps being logically load-bearing, which is a much harder failure to detect than a wrong final answer, since it doesn't show up as an obviously wrong output, only as a subtly unreliable reasoning process that happens to often still land correctly by luck or memorization. Outcome-only RLVR sidesteps this at the cost of not directly optimizing reasoning quality, only reasoning outcomes — which is precisely why the "does RL actually improve reasoning versus just improve pass@1" question above is so live.

### Test-time compute at inference: what the caller actually controls

At inference, reasoning effort is exposed as a bounded parameter, not an open-ended dial: OpenAI's Responses API exposes `reasoning_effort` (low/medium/high), Claude's extended thinking exposes a `budget_tokens` cap, Gemini exposes a `thinking_budget`. Structurally this is different from the self-consistency era's "sample N times and vote": the model generates **one** sequential chain of variable length (bounded by the budget parameter), deciding internally, based on its RL training, roughly how much deliberation a given problem seems to warrant, rather than the caller externally fixing a sample count and aggregating post hoc. Some production systems still layer parallel sampling **on top of** a reasoning model (multiple reasoning traces, then a selection or voting step) for the hardest problems, which is exactly the mechanism behind o3's ARC-AGI-1 high-compute configuration — the 172x compute multiplier is predominantly more parallel sampled attempts at high internal reasoning depth, not a single, 172x-longer chain.

### The billing mechanic that catches people off guard

Reasoning ("thinking") tokens are generated, consumed as part of the context for the final answer, and then typically **not shown** to the caller by default (some providers return a summary, some return nothing) — but they are billed, and billed at the **output-token rate**, which across OpenAI, Anthropic, and Google is substantially more expensive than the input rate (illustrative 2026 OpenAI pricing put o1-pro's output rate at roughly **$600 per million tokens** against **$150 per million** for input, a 4x differential, and reasoning-capable models generally sit well above standard chat-model output pricing). A caller who doesn't explicitly track the `reasoning_tokens` field in the usage object, or set a hard cap via `max_completion_tokens`, can see costs balloon on prompts that trigger unexpectedly long internal deliberation, with no visibility into *why* until they instrument for it specifically.

---

## Build it from scratch

The minimal thing that demonstrates the actual training mechanism, not an API call to a hosted reasoning model: a GRPO loop against a toy verifiable task (arithmetic expressions with a checkable numeric answer). No lab folder exists for this module yet; the sketch below is the shape to build one from.

```python
# untested sketch -- minimal GRPO training step. Omits: the actual
# transformer forward/backward, KL penalty against a reference policy
# (used in practice to prevent the policy drifting too far, though
# DeepSeek-R1-Zero's ablations show it is not strictly required),
# and any infrastructure for sampling at scale.
import torch
import torch.nn.functional as F

def verify(completion: str, ground_truth: str) -> float:
    """Rule-based, outcome-only reward. Returns 1.0 or 0.0.
    This is the entire 'reward model' -- no learned critic anywhere."""
    return 1.0 if extract_final_answer(completion) == ground_truth else 0.0

def grpo_step(policy, prompt: str, ground_truth: str, group_size: int = 16,
              optimizer=None):
    # 1. Sample a GROUP of completions from the current policy for one prompt.
    completions = [policy.generate(prompt) for _ in range(group_size)]

    # 2. Score each with the verifier. No critic network anywhere in this loop.
    rewards = torch.tensor([verify(c, ground_truth) for c in completions])

    # 3. GROUP-RELATIVE advantage: normalize within this prompt's own group.
    #    This IS the baseline. No separate value network trained or served.
    mean, std = rewards.mean(), rewards.std().clamp_min(1e-4)
    advantages = (rewards - mean) / std

    # 4. Policy gradient update: reinforce above-group-average completions,
    #    suppress below-average ones. log_probs computed per completion
    #    under the CURRENT policy (this sketch omits the importance-
    #    sampling ratio a real PPO-style clipped objective would use).
    loss = 0.0
    for completion, advantage in zip(completions, advantages):
        log_probs = policy.log_prob(prompt, completion)          # sum over tokens
        loss = loss - (advantage.detach() * log_probs)
    loss = loss / group_size

    optimizer.zero_grad()
    loss.backward()
    optimizer.step()
    return {
        "mean_reward": mean.item(),
        "frac_correct": mean.item(),      # for a 0/1 reward, identical to mean
        "loss": loss.item(),
    }

# WHY LENGTH GROWS, made concrete: nothing in `verify` or in `advantages`
# penalizes a long `completion`. If longer completions empirically land on
# the correct final answer more often on hard `ground_truth` problems,
# their reward -> advantage -> reinforced gradient is identical in KIND to
# a short correct completion's, and the group naturally drifts toward
# whatever length distribution correlates with success on THIS prompt's
# difficulty. No length term needs to be, or should be, added by hand.
```

The detail every reimplementation gets wrong first: **the group must be sampled per-prompt, not pooled across prompts**, because the normalization is only a valid baseline within a fixed prompt's difficulty — pooling rewards across prompts of very different difficulty into one mean/std would produce advantages that conflate "this completion is good relative to how hard this problem is" with "this problem happened to be easier than average," destroying the signal GRPO depends on.

---

## How it's done in production

Nobody outside a handful of labs trains a frontier reasoning model from scratch; the realistic production surface is API-level reasoning-effort control plus, for teams that need a cheaper or specialized reasoning model, fine-tuning or distilling from an open reasoning model's traces. **Managed:** OpenAI's Responses API (`reasoning_effort: low/medium/high`, with `reasoning_tokens` reported separately in usage), Anthropic's extended thinking (`budget_tokens` cap on Claude's thinking models), Google's Gemini API (`thinking_budget`), each exposing reasoning depth as a bounded, billable parameter rather than an unbounded dial. **Open weights and self-training:** DeepSeek-R1 and its distilled dense-model variants (R1 traces distilled into smaller Qwen/Llama-family checkpoints) are the realistic self-hosted path when API cost or data residency rules out the managed option; `trl`'s `GRPOTrainer` and the `verl` framework are the dominant open tooling for running GRPO-style RLVR on a custom verifiable domain (internal code review, a specific class of structured extraction task with a checkable schema) rather than relying on a general frontier reasoning model.

### Failure-mode table

| Symptom | Cause | Fix |
|---|---|---|
| Simple, previously-fast requests (lookups, short rewrites, basic classification) suddenly show 5-10x higher latency and cost after switching a service to a reasoning model, with no accuracy improvement or even a regression | **Overthinking.** Reasoning models can burn 7-10x more tokens than a standard model reaching comparable or worse accuracy on tasks that don't require multi-step deliberation; documented cases include a model spending 17 seconds on "what is 1+1" and measured latency/cost roughly doubling (18s→38s, $1.70→$2.59) for zero quality gain | Route by task shape, not by a global default: reserve reasoning mode for tasks where a wrong intermediate step would ruin the answer (multi-step math, non-trivial code, multi-hop retrieval synthesis), and use a standard model for lookups, rewrites, and high-volume simple classification; if using a single model family, set `reasoning_effort`/`budget_tokens` low or off for these paths explicitly rather than trusting a default |
| An agent loop or voice pipeline (see `T26-voice-models`) with a hard latency budget starts timing out or blowing SLAs after a reasoning-capable model is introduced upstream | Reasoning tokens add tens of seconds of sequential generation before any output token is available, which is fundamentally incompatible with a sub-second or few-second latency budget regardless of the accuracy benefit | Never place an unbounded-reasoning-effort call on a latency-critical synchronous path; if reasoning quality is needed, run it asynchronously (pre-compute, cache, or a background enrichment step) rather than inline, or cap `reasoning_effort`/`budget_tokens` tightly and validate the accuracy/latency tradeoff at that specific cap before shipping |
| Monthly API spend spikes unexpectedly with no corresponding traffic increase | Hidden reasoning tokens billed at the output-token rate (often several times the input rate) accumulate silently, since they're not shown in the visible response by default and easy to omit from cost dashboards that only track prompt/completion visible-text length | Explicitly monitor the `reasoning_tokens` field in the usage object per request, not just visible completion length; set `max_completion_tokens` (or the provider's equivalent) as a hard cap to bound worst-case spend per call, and alert on reasoning-token share of total spend as a first-class metric |
| A custom RLVR fine-tune's held-out accuracy looks great, but real-world outputs are subtly unreliable — reasoning steps read as plausible but don't logically support the conclusion | Reward hacking against a process reward model, or an outcome verifier with an exploitable gap (e.g. a test suite the policy learns to satisfy via an edge case rather than genuinely solving the underlying task) | Prefer outcome-only rewards over learned process reward models where possible, since outcome checks (does the answer match, do the real tests pass) are far harder to game than a learned step-scorer; audit the verifier itself for exploitable gaps (weak test coverage, answer-matching that accepts near-misses) before trusting held-out accuracy as evidence of real capability |
| A team assumes their RL-tuned reasoning model has learned genuinely new problem-solving ability because pass@1 improved substantially over the base model | Conflating pass@1 improvement (real, and useful) with capability expansion (not well supported); the NeurIPS 2025 pass@k study found base models match or exceed RL-tuned models at large k, meaning RL primarily reallocates probability mass toward already-latent correct paths | Evaluate claims of "the model can now do X it couldn't before" against pass@k at large k on the base model, not just pass@1 on the RL-tuned model, before making capability claims to stakeholders; if genuine new capability is the goal, look at distillation from a stronger teacher's traces, which the same study found does expand capability, rather than RL on the model's own rollouts alone |

---

## Tradeoffs & when NOT to use it

**Simple, high-volume, low-ambiguity tasks.** Lookups, short rewrites, basic classification, formatting — the documented overthinking failure mode (7-10x token burn, sometimes worse accuracy) makes a reasoning model actively the wrong choice here, not merely an expensive one. This is the single most common production misuse: defaulting to the "smartest" model for tasks where smartness isn't the bottleneck.

**Hard latency budgets.** Anything on a synchronous path with a tight SLA — voice agents (`T26-voice-models`'s ~300ms-perception threshold is nowhere close to compatible with tens of seconds of sequential reasoning generation), real-time agent loops, interactive UI paths — should not place unbounded or high-effort reasoning inline. If the accuracy benefit is real, move the reasoning step off the critical path (pre-compute, async enrichment, cache) rather than accepting the latency hit live.

**Tasks without a clean automated verifier.** The entire RLVR training recipe depends on a reward signal that can be checked automatically and cheaply (right answer, passing tests). For open-ended writing quality, subjective judgment calls, or most real-world enterprise agentic decisions, there is no equivalent clean verifier, so the specific mechanism that makes reasoning models good at math and code doesn't have an obvious analog, and claims that a reasoning model will systematically improve these tasks the same way should be treated with real skepticism rather than assumed by extension.

**Cost-sensitive high-volume paths.** Reasoning tokens billed at output rates (often several times standard output pricing) compound fast at volume; a marginal accuracy improvement that doesn't move a business metric is not worth a 5-10x cost multiplier, and this tradeoff should be made explicitly and revisited, not defaulted into.

**Anything requiring a fully auditable, deterministic answer path.** Hidden chain-of-thought is by design not shown to the caller by default, and some providers deliberately obscure or summarize it partly to prevent distillation by competitors — for regulated or compliance-sensitive decisions where "show your work" is a hard requirement, an opaque reasoning trace you cannot fully inspect is itself a liability, echoing the same auditability tradeoff `T26-voice-models` raises for unified speech-to-speech models losing their intermediate transcript.

**Where it's clearly right.** Multi-step, verifiable problems where a wrong intermediate step ruins the final answer: non-trivial math, competitive programming, multi-hop reasoning over a large retrieved corpus, code generation against a well-specified test suite, and any task where you can afford the latency and cost and the accuracy gain is measured, not assumed.

---

## Interview questions

### Q1 — What is test-time compute scaling, and what's the strongest quantitative evidence it's real rather than marketing?
**Testing:** whether you can cite a concrete number rather than a description.
**Answer:** Test-time compute scaling means spending more inference compute (a longer internally-generated chain of thought, or more parallel sampled attempts) at answer time to improve accuracy on hard problems, as opposed to only improving accuracy via more training compute or parameters. The strongest concrete evidence: o3 scored 75.7% on ARC-AGI-1 at standard compute and 87.5% using roughly 172x more test-time compute, at an estimated cost of thousands of dollars per task at the high-compute setting — a large, reproducible capability jump bought almost entirely at inference time.
**Follow-up trap:** "So more test-time compute always helps?" No — it helps specifically on hard, verifiable, multi-step problems; on simple tasks it can burn 7-10x more tokens for no accuracy gain and sometimes a regression, which is the overthinking failure mode documented by Amazon's internal research.

### Q2 — How does GRPO differ from standard PPO-based RLHF, and why does the difference matter at frontier scale?
**Testing:** mechanical understanding of the specific algorithm, not just "it's the RL DeepSeek used."
**Answer:** PPO trains a separate critic/value network to estimate expected future reward, which is used to compute the advantage for a policy gradient update — a real cost and stability burden at scale. GRPO removes the critic entirely: sample a group of G completions per prompt, score each with a verifier, and normalize each completion's reward against the group's own mean and standard deviation to get the advantage directly, with no learned baseline. This roughly halves the model-serving footprint of the RL loop and removes a common source of RLHF instability (a noisy or miscalibrated critic).
**Follow-up trap:** "Doesn't removing the critic lose information the critic would have captured?" A fair concern — the group-relative baseline is coarser than a trained critic's token-level value estimates, and this is part of why GRPO works best with a genuinely reliable, outcome-based verifier (math, code) rather than noisier, more subjective reward signals, where a learned critic's smoothing might otherwise help.

### Q3 — Why do most production RLVR recipes in 2025-26 use outcome-only rewards rather than process reward models, despite process supervision's theoretical appeal?
**Testing:** whether you understand the reward-hacking tradeoff, not just that PRMs exist.
**Answer:** An outcome reward (right/wrong final answer, tests pass/fail) is automatable and structurally hard to game when the checker is genuinely objective. A process reward model is itself a learned model scoring intermediate steps, and it's vulnerable to reward hacking: the policy can learn to produce step-text that satisfies the PRM's learned notion of a good step without those steps being logically load-bearing, which is a much harder failure to catch than a simply wrong final answer, since the output can still often land correctly by luck while the reasoning underneath is unreliable.
**Follow-up trap:** "So process rewards are strictly worse, and should never be used?" No — outcome-only rewards give no direct signal on reasoning quality itself, only on final correctness, so process supervision has genuine theoretical value for shaping *how* a model reasons; the honest answer is that it's harder to do safely, not useless, and most production systems currently favor the safer, if less complete, outcome-only signal.

### Q4 — Why does chain-of-thought length grow over the course of RL training, mechanically?
**Testing:** whether you can derive this rather than just observe it as a fact.
**Answer:** The base RLVR recipe applies no length penalty — a long completion that lands on the correct answer receives the same reward, and therefore contributes an advantage of the same sign and treatment, as a short correct completion. If longer, more careful chains empirically succeed more often specifically on hard problems (which they generally do, since more deliberation reduces the chance of an early irrecoverable error), the group of sampled completions naturally drifts toward whatever length distribution correlates with success on that prompt's difficulty, purely as a side effect of the optimizer reinforcing above-group-average completions. Nothing rewards length directly.
**Follow-up trap:** "Could you just add a length penalty to control cost?" Yes, and some production recipes do exactly this, but it's a real tradeoff — penalizing length too aggressively can suppress the deliberation needed for genuinely hard problems, reintroducing errors the unconstrained recipe avoided; the penalty coefficient becomes another hyperparameter to tune against the accuracy/cost curve, not a free win.

### Q5 — Does RL on chains of thought teach a model genuinely new reasoning capability, or something narrower? What's the evidence?
**Testing:** the central "what actually changed" question this module is built around.
**Answer:** The evidence points to something narrower than "new reasoning capability." A NeurIPS 2025 study measured pass@k at large k: RL-trained models beat their base model at small k (better first-try accuracy) but the base model matches or exceeds the RL-trained model at large k, indicating RLVR mostly sharpens sampling toward correct paths the base model could already reach given enough attempts, rather than expanding what's reachable at all. The same study found distillation from a stronger teacher's reasoning traces did expand capability beyond the base model, a genuinely different mechanism (learning new patterns externally) than RL on the model's own rollouts (re-weighting an existing distribution).
**Follow-up trap:** "If it's not teaching new capability, why does it matter at all?" Because pass@1 (first-try accuracy) is exactly what most real products need — a user does not sample 1,000 completions and take a majority vote, they get one answer. A capability the base model technically had access to at large k but couldn't reliably surface on the first try is not useful in most deployed contexts, so RLVR's real, demonstrated value is making a latent capability reliably accessible in a single shot, which is a genuine, shippable improvement even if it isn't capability expansion in the strict sense.

### Q6 — Walk through the overthinking failure mode with real numbers, and how you'd catch it before it ships.
**Testing:** operational instinct connecting a known failure to a mitigation.
**Answer:** Documented cases: reasoning models generating 7-10x more tokens than a standard model to reach comparable accuracy on simple tasks, one model spending 17 seconds deliberating "what is 1+1," and a measured production case where latency doubled (18s to 38s) and cost rose ($1.70 to $2.59 per task) with zero accuracy gain. Catching it before shipping: benchmark reasoning-mode against a standard model specifically on your actual production task distribution (not a curated hard-eval set), broken out by task complexity, and route by task shape rather than defaulting every call to the highest reasoning effort.
**Follow-up trap:** "Wouldn't a smart router just detect task difficulty automatically?" That's the direction the field is heading, but it's not a solved, trustworthy default in 2026 — a router itself needs to be validated against your traffic distribution, and a naive complexity heuristic can misclassify tasks that look simple lexically but are actually multi-step, or vice versa; treat automatic routing as something to build and validate, not something to assume works out of the box.

### Q7 — How are reasoning tokens billed, and what's the operational gotcha teams miss?
**Testing:** whether you've actually operated one of these models in production, not just called the API once.
**Answer:** Reasoning/thinking tokens are billed at the output-token rate, which is typically several times the input rate and often the most expensive rate tier a provider offers, and they're generated whether or not they're shown to the caller — some providers return a summary, some return nothing visible at all, but the token count is still billed. The operational gotcha: teams that only track visible completion length in their cost dashboards miss this entirely and get blindsided by spend spikes with no visible traffic change.
**Follow-up trap:** "Can you just disable reasoning tokens to avoid the cost?" You can set reasoning effort low or off, which is often the right call for simple tasks, but for tasks that genuinely need multi-step deliberation, disabling reasoning trades the token cost for an accuracy cost instead — it's not a free way to cut spend without a corresponding capability tradeoff.

### Q8 — Compare CoT prompting (Wei et al., self-consistency) to RL-trained native reasoning (o1/DeepSeek-R1). What's structurally different, not just "one is trained"?
**Testing:** whether you can name the structural mechanism difference, not just the historical timeline.
**Answer:** CoT prompting elicits multi-step text from a model with no training-time connection between reasoning length/quality and reward — it's a fixed distribution being sampled differently via prompt engineering, and self-consistency's majority-vote-over-N-samples hits diminishing returns fast because all samples come from that same unretrained distribution. RL-trained reasoning models have had their actual token-generation distribution reshaped by a reward signal tied to final-answer correctness over long, self-generated rollouts, which is why they exhibit behaviors (backtracking, self-correction, "aha moments") that were never explicitly demonstrated in any training example — those behaviors emerged because they correlated with higher reward, not because a prompt asked for them.
**Follow-up trap:** "So RL-trained models don't need any prompting to reason well?" Prompting still matters (clear problem specification, well-formed verifiable tasks help the model apply its trained reasoning behavior effectively), but the mechanism generating the reasoning itself is now trained into the model's weights rather than purely elicited by prompt structure, which is the real structural shift.

### Q9 — Design a routing policy for a production agent system deciding when to invoke reasoning mode.
**Testing:** applied judgment, not just knowing the concept exists.
**Answer:** Classify incoming tasks along two axes before dispatch: is the task multi-step where a wrong intermediate step would invalidate the final answer (math, non-trivial code, multi-hop synthesis), and is there latency/cost headroom for tens of seconds of added generation. Route to reasoning mode only when both are true; route to a standard model for lookups, short rewrites, and classification regardless of perceived task "importance," since importance and reasoning-need are not the same axis. Cap `reasoning_effort`/`budget_tokens` explicitly rather than leaving it unbounded even on the reasoning path, and validate the router's classifications against real production traffic and outcomes, not just intuition, since misclassifying a deceptively simple-looking multi-step task is a real failure mode.
**Follow-up trap:** "What if you can't cleanly classify a task in advance?" For genuinely ambiguous cases, a cheap escalation pattern (try the standard model, detect low-confidence or failed verification, then escalate to reasoning mode) is often more cost-effective than defaulting ambiguous traffic to expensive reasoning mode, though it adds a round trip of latency on the escalated fraction — the right choice depends on your specific latency/cost/accuracy tradeoff, which is exactly why this needs to be measured on your own traffic rather than assumed.

### Q10 — Your team's custom RLVR fine-tune shows strong held-out accuracy, but a spot-check of real outputs shows reasoning steps that don't logically support the conclusions reached. Diagnose it.
**Testing:** whether you can connect a subtle quality issue to a specific, named training-time cause.
**Answer:** This is the signature of a gameable verifier or reward hacking, not a mysterious quality regression. If a process reward model is in the loop, the policy has likely learned to produce step-text that satisfies the PRM's learned notion of a good step without the steps being logically necessary for the answer. If it's outcome-only, check the verifier itself for exploitable gaps — weak test coverage that a shortcut can satisfy, or answer-matching lenient enough to accept near-misses that happen to be technically correct by coincidence rather than by sound reasoning.
**Follow-up trap:** "Held-out accuracy is strong though — doesn't that rule out reward hacking?" No — held-out accuracy measured against the same (or a similarly gameable) verifier doesn't catch a systematically exploited gap, since the exploit generalizes to held-out examples that share the same weakness. You need qualitative auditing of the reasoning traces themselves, not just outcome accuracy, to catch this class of failure.

### Q11 — Staff level: your team wants to set `reasoning_effort: high` as the default for every agent call, arguing it can only help quality. What's your response?
**Testing:** whether you can push back on a plausible-sounding but evidence-contradicted proposal with specifics.
**Answer:** Push back with the overthinking evidence directly: reasoning models have documented cases of burning 7-10x more tokens and scoring worse on simple tasks, not just costing more for the same accuracy — "can only help" is empirically false for a meaningful fraction of most systems' real traffic, which skews toward simple, high-volume requests rather than the hard, verifiable problems reasoning mode is validated on. Propose instead: benchmark the actual production traffic distribution split by task complexity, measure the accuracy/latency/cost delta at each reasoning-effort setting per task class, and set effort per class based on measured data rather than a global default based on hard-eval-set benchmarks that don't represent typical traffic.
**Follow-up trap:** "But isn't it safer to default to more reasoning, just in case?" 'Safer' has to be measured against the actual cost, not assumed — tripled latency and 5-10x spend on the 80% of traffic that doesn't need it is a real, quantifiable cost, not a hypothetical one, and the "just in case" framing is exactly the kind of unexamined default this module is built to push back on.

### Q12 — Explain why DeepSeek-R1-Zero (pure RL, no SFT) wasn't shipped directly as the product, and what the multi-stage pipeline added.
**Testing:** whether you know the recipe in enough detail to explain the gap between a research result and a shippable product.
**Answer:** R1-Zero, trained with pure RL and no supervised fine-tuning, exhibited the genuinely emergent reasoning behaviors (extended CoT, self-correction) the paper is known for, but its raw output was poorly formatted, sometimes mixed languages mid-reasoning, and was generally hard to read as a direct user-facing product. The shipped DeepSeek-R1 added a multi-stage pipeline around the core RL: a small cold-start SFT phase specifically to establish readable formatting conventions, the RL phase itself, a rejection-sampling step to generate cleaner synthetic training data from the RL model's own good outputs, and a final RL phase — turning a research demonstration of an emergent capability into a coherent, readable product without discarding the core RLVR mechanism that produced the reasoning behavior in the first place.
**Follow-up trap:** "Doesn't adding SFT back in contradict the 'pure RL' story that made R1-Zero notable?** No, and conflating the two is the trap — R1-Zero's contribution was demonstrating that RL alone, with zero demonstrations of reasoning behavior, could produce it emergently, which is a genuine research finding about what RL can elicit. The shipped R1's SFT stages target formatting and readability, not reasoning behavior itself, which the ablations show came from the RL phases; the two claims (RL alone can elicit reasoning; a shippable product needs more than that alone) are compatible, not contradictory.

---

## Red flags that fail you

- Describing reasoning models as "the model thinks like a human now" without any mechanism (RLVR, GRPO, verifiable rewards) behind the claim.
- Claiming RL-trained reasoning models have learned qualitatively new capabilities without engaging with the pass@k evidence that complicates this.
- Recommending reasoning mode as a default for all traffic without acknowledging the documented overthinking failure mode and its real cost.
- Not knowing that reasoning tokens are billed, often at a premium rate, even when hidden from the visible response.
- Confusing self-consistency (parallel sampling + majority vote, prompting-era) with native RL-trained sequential reasoning (o1/R1-era) as the same mechanism.
- Proposing process reward models as a strictly better replacement for outcome rewards without acknowledging the reward-hacking risk that makes outcome-only the safer production default.
- Treating "more test-time compute" as a free accuracy lever with no cost or downside curve.
- Not being able to explain, mechanically, why chain-of-thought length grows during RL training (no length penalty, correctness-correlated drift) versus just asserting that it does.

## Cheat card

```
TEST-TIME     scale inference compute (longer CoT, more parallel samples)
COMPUTE       to improve accuracy on hard, VERIFIABLE problems. o3 ARC-AGI-1:
              75.7% standard -> 87.5% at ~172x compute, $1000s/task.
GRPO          Group Relative Policy Optimization. Sample G completions/prompt,
              verifier scores each, advantage = (reward - group_mean)/group_std.
              NO separate critic/value network -> cheaper, more stable than PPO.
OUTCOME vs    outcome (right/wrong answer): cheap, hard to game. Process
PROCESS       reward model (scores steps): richer signal, but reward-hackable
REWARD        -> most 2025-26 prod recipes lean OUTCOME-ONLY.
WHY LENGTH    no length penalty in base recipe. Longer chains succeed more
GROWS         on hard problems -> optimizer drifts toward length as a SIDE
              EFFECT of reinforcing correctness, not a direct reward target.
DEEPSEEK-R1   Jan 2025. R1-Zero: pure RL, no SFT, emergent CoT + self-
              correction ("aha moments"). Shipped R1: cold-start SFT -> RL ->
              rejection-sample SFT -> RL, for readability, not new reasoning.
PASS@K        RL-tuned model wins pass@1. BASE model matches/beats pass@k at
EVIDENCE      large k (NeurIPS 2025). => RL mostly SHARPENS existing latent
              paths, doesn't clearly expand the frontier. Distillation from a
              stronger teacher DID expand it -- different mechanism.
OVERTHINKING  reasoning models: 7-10x more tokens than standard model on
              SIMPLE tasks, sometimes WORSE accuracy. 17s on "what is 1+1".
              Measured: latency 18s->38s, cost $1.70->$2.59, 0 accuracy gain.
BILLING       reasoning tokens billed at OUTPUT rate (often priciest tier),
              hidden from response by default. Monitor reasoning_tokens field,
              cap via max_completion_tokens / budget_tokens / thinking_budget.
API CONTROLS  OpenAI reasoning_effort (low/med/high), Claude budget_tokens,
              Gemini thinking_budget -- bounded params, not open-ended dials.
WHEN WRONG    simple/high-volume tasks, hard latency budgets (voice, sync
TOOL          agent loops), no clean automated verifier, cost-sensitive
              volume paths, anything needing fully auditable answer path.
INFERENCE     industry projection: inference compute -> ~75% of total AI
SHARE         compute by 2030, inverting the training-dominated 2020s.
```

## Sources

- [AI Reasoning Models in 2026: o3 vs Claude vs Gemini Deep Think (DevToolLab Blog)](https://devtoollab.com/blog/ai-reasoning-models-guide-2026) — accessed 2026-08-08
- [OpenAI o3 Breakthrough High Score on ARC-AGI-Pub (ARC Prize)](https://arcprize.org/blog/oai-o3-pub-breakthrough) — accessed 2026-08-08
- [DeepSeek-R1: incentivizes reasoning in LLMs through reinforcement learning](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC12443585/) — accessed 2026-08-08
- [deepseek-ai/DeepSeek-R1 (Hugging Face model card)](https://huggingface.co/deepseek-ai/DeepSeek-R1) — accessed 2026-08-08
- [Does Reinforcement Learning Really Incentivize Reasoning Capacity in LLMs Beyond the Base Model? (NeurIPS 2025, arXiv 2504.13837)](https://arxiv.org/abs/2504.13837) — accessed 2026-08-08
- [Limit of RLVR (project page for the pass@k study)](https://limit-of-rlvr.github.io/) — accessed 2026-08-08
- [Turn the Thinking Knob Off. Most of the Time. (Micheal Lanham, Medium, May 2026)](https://medium.com/@Micheal-Lanham/turn-the-thinking-knob-off-most-of-the-time-1b67ab418045) — accessed 2026-08-08
- [When to Use a Reasoning Model (and When Not To) (Candova AI)](https://candova.ai/blog/when-to-use-a-reasoning-model) — accessed 2026-08-08
- [Don't Overthink It: A Survey of Efficient R1-style Large Reasoning Models (arXiv 2508.02120)](https://arxiv.org/pdf/2508.02120) — accessed 2026-08-08
- [Reasoning Token Costs: What You're Actually Paying For](https://leanlm.ai/blog/reasoning-token-costs) — accessed 2026-08-08
- [OpenAI API Pricing 2026: GPT-4o, o3, and GPT-5 Cost Per Token](https://valueaddvc.com/blog/openai-api-pricing-2026-gpt-4o-o3-and-gpt-5-cost-breakdown-for-developers) — accessed 2026-08-08
- [GPT-5 vs Claude 4 vs Gemini 3: 2026 AI Benchmark Showdown (teamai.com)](https://teamai.com/blog/large-language-models-llms/the-2026-ai-frontier-model-war-2/) — accessed 2026-08-08

## Changelog
- 2026-08-08 — created
