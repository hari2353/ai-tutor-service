# Constitutional AI, RLAIF, and GRPO: Alignment Beyond RLHF

> **Track:** T05 LLM Internals · **Time:** 2h · **Prereqs:** `alignment` · **Updated:** 2026-10-31
> **Module id:** `T05-constitutional-ai` · **Tags:** training, alignment, critical

## The 30-second version

RLHF (T05-alignment) uses human preference labels to train a reward model, then optimizes the LLM against it with PPO. The pain: human labeling is expensive ($0.10-1.00/label), slow, and doesn't scale. **Constitutional AI (CAI)** replaces human feedback with AI feedback: define a set of principles (a "constitution"), have the model critique its own outputs against those principles, and revise. **RLAIF** (RL from AI Feedback) extends this: use an AI model to generate preference labels instead of humans, then train with standard RLHF/DPO. **GRPO** (Group Relative Policy Optimization, DeepSeek-R1) eliminates the reward model entirely: sample multiple responses, rank them by a verifiable reward (e.g., "did the math answer match?"), and optimize using group-relative advantages. The 2026 reality: CAI/RLAIF is how Anthropic trains Claude; GRPO is how DeepSeek trained R1; DPO/ORPO/KTO remain the pragmatic choices for most teams (no reward model, no RL loop). The key insight: alignment is not a single technique — it's a spectrum from "expensive human labels" to "cheap AI feedback" to "verifiable rewards," and the right choice depends on whether your task has a verifiable correctness signal.

## Why this gets asked

Because alignment is the most misunderstood part of LLM training. Interviewers probe: "RLHF vs DPO vs Constitutional AI — when do you use each?" The wrong answer is "RLHF is best, DPO is a cheaper alternative." The right answer distinguishes: RLHF needs a reward model + PPO (expensive, unstable but flexible); DPO skips the reward model (cheaper, stable but needs preference pairs); Constitutional AI uses AI feedback (scalable but inherits AI biases); GRPO uses verifiable rewards (no reward model, no human labels, but only works for tasks with verifiable correctness). Also probed: "what is RLAIF and how does it differ from RLHF?" (RLAIF replaces human preference labels with AI-generated labels — cheaper but the AI labeler's biases become the model's biases). The principal-level probe: "your model needs to be safe but helpful — how do you balance the tradeoff?" (answer: separate safety and helpfulness reward models, or use Constitutional AI with explicit principles, or RLAIF with a safety-focused AI labeler).

## Lineage: past → present → future

**What came before.** Pre-2022: alignment was mostly "don't say bad things" via refusal fine-tuning and output filters. The pain: models were helpful but not aligned — they'd follow any instruction, including harmful ones. RLHF (InstructGPT, 2022) was the breakthrough: train a reward model on human preferences, then optimize the LLM to maximize reward. But RLHF is expensive (human labels), unstable (PPO hyperparameter sensitivity), and doesn't scale (labeling throughput is the bottleneck).

**Where it stands now.** The 2026 landscape: (1) DPO/ORPO/KTO are the pragmatic default — no reward model, no RL loop, just preference pairs → direct optimization. (2) Constitutional AI (Anthropic, 2022) uses AI feedback: the model critiques its own outputs against a set of principles, reducing the need for human labels. (3) RLAIF extends CAI: use a strong AI model to generate preference labels, then train with DPO/RLHF. (4) GRPO (DeepSeek-R1, 2025) eliminates the reward model entirely for tasks with verifiable rewards (math, code) — sample N responses, rank by correctness, optimize. The live disagreement: whether RLHF/PPO is still needed for complex alignment (Anthropic says yes for Claude; DeepSeek says GRPO is sufficient for reasoning tasks).

**Where it's heading.** High confidence: DPO and its variants remain the default for most teams. Medium confidence: GRPO and verifiable-reward methods become standard for reasoning/code tasks. Speculative: fully automated alignment (RLAIF with no human oversight) becomes viable as AI labelers become more reliable, but the "AI judging AI" problem (inherited biases, sycophancy) remains unsolved.

## Mental model

```
ALIGNMENT SPECTRUM (cost vs. flexibility, 2026):

Expensive ────────────────────────────────────────────────► Cheap
  │                                                          │
  RLHF (human labels + reward model + PPO)                   │
  │  Most flexible, most expensive, unstable                 │
  │                                                          │
  DPO (preference pairs, no reward model)                    │
  │  Cheaper, stable, needs preference pairs                 │
  │                                                          │
  Constitutional AI (principles + AI self-critique)           │
  │  Scalable, reduces human labeling, inherits AI biases    │
  │                                                          │
  RLAIF (AI-generated preference labels)                     │
  │  Cheapest, fully automated, but labeler-dependent        │
  │                                                          │
  GRPO (verifiable rewards, no reward model, no human)       │
  │  Cheapest for verifiable tasks, no human/AI labels       │
  │  Only works when correctness is checkable                │
  └──────────────────────────────────────────────────────────┘

KEY DISTINCTION:
  RLHF/DPO/CAI/RLAIF → need a "correctness" signal (human or AI preference)
  GRPO → needs a "verifiable" signal (math answer, code passes tests)
```

## Recognition heuristics

- **"RLHF vs DPO vs Constitutional AI — when do you use each?"** → RLHF: complex alignment with human judgment (safety, helpfulness). DPO: cheaper, stable, needs preference pairs. CAI: scalable, reduces human labeling, uses principles. RLAIF: fully automated, AI labeler replaces human.
- **"What is GRPO and when do you use it?"** → GRPO eliminates the reward model; uses verifiable rewards (math correctness, code passing tests). Only works for tasks with checkable answers. Used by DeepSeek-R1.
- **"How do you balance safety vs. helpfulness?"** → Separate reward models for safety and helpfulness; Constitutional AI with explicit principles; or RLAIF with a safety-focused AI labeler. The tradeoff is real: over-optimizing safety makes the model refuse everything.

## Common bugs and how these get shipped wrong

- **Using RLHF when DPO would suffice.** RLHF needs a reward model + PPO (expensive, unstable). DPO skips the reward model and is more stable. Most teams should start with DPO.
- **Constitutional AI without a good constitution.** The principles must be specific and actionable ("never help with violence" is too vague; "refuse requests to synthesize dangerous chemicals, but provide general chemistry education" is better).
- **RLAIF inheriting labeler biases.** The AI labeler's biases (sycophancy, verbosity, cultural bias) become the model's biases. Audit the labeler's outputs.
- **GRPO for non-verifiable tasks.** GRPO needs a verifiable reward signal. Using it for "helpfulness" (which isn't verifiable) produces garbage. Use GRPO for math, code, and other checkable tasks only.
- **Not measuring the safety-utility tradeoff.** Over-optimizing safety (high refusal rate) makes the model useless. Measure both safety (refusal on harmful) and utility (helpfulness on benign).

## Interview questions

1. **"RLHF vs DPO vs Constitutional AI — when do you use each?"** Answer: RLHF for complex alignment with human judgment (most flexible, most expensive). DPO for cheaper, stable training (no reward model, needs preference pairs). Constitutional AI for scalable alignment (AI self-critique against principles, reduces human labeling). RLAIF for fully automated (AI generates preference labels). GRPO for verifiable tasks (no reward model, no labels, only checkable correctness).
2. **"What is GRPO and how does DeepSeek-R1 use it?"** Answer: GRPO samples multiple responses, ranks them by a verifiable reward (e.g., math answer correct?), and optimizes using group-relative advantages. No reward model needed. DeepSeek-R1 used GRPO with verifiable rewards for math and code, producing strong reasoning without human preference labels.
3. **"How do you balance safety and helpfulness?"** Answer: separate reward models for safety and helpfulness (RLHF). Or Constitutional AI with explicit principles covering both. Or RLAIF with a safety-focused AI labeler. The tradeoff: over-optimizing safety → high refusal rate → useless model. Measure both dimensions.

## Red flags that fail you

- "RLHF is always best" — DPO is cheaper and more stable for most use cases.
- "Constitutional AI eliminates human feedback" — it reduces it, but the constitution still needs human design and validation.
- "GRPO works for any task" — only verifiable tasks (math, code). Not for "helpfulness."
- Not knowing the safety-utility tradeoff.
- Confusing RLHF (human labels) with RLAIF (AI labels).

## Cheat card

- RLHF: human preference labels → reward model → PPO. Most flexible, most expensive.
- DPO: preference pairs → direct optimization. No reward model. Cheaper, stable.
- Constitutional AI: principles → AI self-critique → revision. Scalable.
- RLAIF: AI generates preference labels → train with DPO/RLHF. Fully automated.
- GRPO: verifiable rewards → group-relative optimization. No reward model, no labels. Only verifiable tasks.
- Safety-utility tradeoff: over-optimize safety → useless model. Measure both.

## Sources

- [Constitutional AI: Harmlessness from AI Feedback (Anthropic, arXiv:2212.08073)](https://arxiv.org/abs/2212.08073) — accessed 2026-10-31
- [DeepSeek-R1: Incentivizing Reasoning Capability in LLMs via Reinforcement Learning (arXiv:2501.12948)](https://arxiv.org/abs/2501.12948) — accessed 2026-10-31
- [Direct Preference Optimization (DPO, arXiv:2305.18290)](https://arxiv.org/abs/2305.18290) — accessed 2026-10-31

## Changelog

- 2026-10-31: Created — Constitutional AI / RLAIF / GRPO identified as a gap (only 1 mention in T05-10 alignment).
