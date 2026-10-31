# AI Safety & Red-Teaming: Jailbreaks, Prompt Injection Deep Dive, Safety Benchmarks, Alignment

> **Track:** T07 Agentic AI · **Time:** 2.5h · **Prereqs:** `T07-agent-safety` · **Updated:** 2026-10-31
> **Module id:** `T07-ai-safety-redteam` · **Tags:** security, safety, critical

## The 30-second version

Prompt injection (T07-agent-safety) is the *mechanism*; AI safety and red-teaming is the *discipline* of systematically finding and fixing the ways AI systems fail, harm, or get exploited. The core practices: **red-teaming** (structured adversarial testing with a defined threat model, not just "trying to break it"), **jailbreak taxonomy** (role-play, encoding, multi-turn, many-shot, crescendo attacks), **safety benchmarks** (HarmBench, JailbreakBench, AIR-Bench, WMDP), **alignment techniques** (RLHF, DPO, Constitutional AI, RLAIF, GRPO), and **defense layers** (input filtering, output filtering, classifier guardrails, sandboxing, monitoring). The 2026 reality: no single defense is sufficient; defense-in-depth with deterministic containment (egress allowlists, least-privilege tools, sandboxing) is the only reliable strategy. The key insight for interviews: safety is not a feature you add at the end — it's an architectural property that must be designed in from the start, because retrofitting safety onto an agent with excessive agency is nearly impossible.

## Why this gets asked

Because every company shipping AI products has a safety story, and interviewers want to know if you understand the threat landscape beyond "we use a content filter." They probe: "how would you red-team this agent?" (wrong answer: "I'd try some jailbreaks"; right answer: "I'd define a threat model, enumerate attack surfaces, build an eval suite with known attack patterns, measure attack success rate, and iterate on defenses"). Also probed: "what's the difference between safety and security?" (safety = preventing harmful outputs/actions; security = preventing unauthorized access/exploitation — they overlap but have different threat models and defenses). The principal-level probe: "your agent reads customer emails and files tickets — walk me through your safety review" (answer: data classification, tool scoping, egress control, audit, incident response, red-team eval suite).

## Lineage: past → present → future

**What came before.** The chatbot era (2020-2023) had a simple safety model: refusal fine-tuning + output filters. The risk was *output* (toxic content, PII leakage). Defenses were reactive: OpenAI Moderation API, word blocklists. The pain that killed this: agents act in the world, so a safety failure isn't just embarrassing — it's a real-world harm (unauthorized transactions, data exfiltration, system compromise). The 2023-2024 period saw the rise of systematic red-teaming (Anthropic's red team, OpenAI's Preparedness Framework) and safety benchmarks (HarmBench, 2024).

**Where it stands now.** The 2026 landscape: (1) jailbreaks are an arms race — new attacks (crescendo, many-shot, encoding) appear monthly, defenses (classifiers, instruction hierarchy) improve but are bypassed within weeks. (2) Safety benchmarks (HarmBench, JailbreakBench, AIR-Bench, WMDP) provide standardized evaluation, but the gap between benchmark performance and real-world robustness is large. (3) Alignment techniques (RLHF, DPO, Constitutional AI, RLAIF, GRPO) improve base model safety but don't solve prompt injection or agent-specific risks. (4) The emerging consensus: deterministic containment (egress allowlists, least-privilege tools, sandboxing) is the only reliable defense; AI-classified guardrails reduce but don't eliminate risk.

**Where it's heading.** High confidence: defense-in-depth with deterministic containment becomes the standard for agent systems. Medium confidence: safety benchmarks become more realistic (moving from single-turn jailbreaks to multi-turn, tool-use, and agentic scenarios). Speculative: formal verification of agent safety properties becomes feasible for constrained domains, but remains impractical for open-ended agents.

## Mental model

```
AI SAFETY STACK (defense in depth, bottom to top):

Layer 5: MONITORING & INCIDENT RESPONSE
  ├─ Audit logs (every tool call, every decision)
  ├─ Anomaly detection (unusual tool usage patterns)
  └─ Revocation story (how fast can you kill the agent?)

Layer 4: DETERMINISTIC CONTAINMENT (the real boundary)
  ├─ Egress allowlists (only approved URLs/domains)
  ├─ Least-privilege tool tiers (read-only default, approval for writes)
  ├─ Sandboxing (microVMs, network isolation)
  └─ Canary tokens (detect data exfiltration)

Layer 3: AI-CLASSIFIED GUARDRAILS (reduce, don't eliminate)
  ├─ Input filters (jailbreak classifiers)
  ├─ Output filters (harmful content classifiers)
  ├─ Instruction hierarchy (system > user > tool results)
  └─ Constitutional AI / RLAIF (trained safety behavior)

Layer 2: ALIGNMENT (base model safety)
  ├─ RLHF / DPO / GRPO (preference learning)
  ├─ Constitutional AI (principle-based self-critique)
  └─ RLAIF (AI feedback instead of human feedback)

Layer 1: RED-TEAMING (find the gaps)
  ├─ Structured adversarial testing (defined threat model)
  ├─ Safety benchmarks (HarmBench, JailbreakBench, AIR-Bench, WMDP)
  ├─ Automated attack generation (GCG, PAIR, TAP)
  └─ Continuous eval (regression testing for safety)
```

## Recognition heuristics

- **"How would you red-team this agent?"** → Define threat model → enumerate attack surfaces → build eval suite with known attack patterns → measure attack success rate → iterate on defenses → continuous regression testing.
- **"What's the difference between safety and security?"** → Safety = preventing harmful outputs/actions (content, bias, misuse). Security = preventing unauthorized access/exploitation (auth, injection, data breach). They overlap (prompt injection is both) but have different threat models.
- **"How do you evaluate model safety?"** → Safety benchmarks (HarmBench, JailbreakBench) + custom eval suite + red-team exercises + continuous monitoring. No single metric is sufficient.
- **"Constitutional AI vs RLHF?"** → RLHF uses human preference labels. Constitutional AI uses a set of principles (constitution) and has the model critique its own outputs against those principles. RLAIF replaces human feedback with AI feedback.

## Common bugs and how these get shipped wrong

- **Treating safety as a feature you add at the end.** Retrofitting safety onto an agent with excessive agency (too many tools, too many permissions) is nearly impossible. Design for least privilege from the start.
- **Relying solely on AI-classified guardrails.** Classifiers are bypassed within weeks of deployment. They reduce risk but are not boundaries. Always have deterministic containment as the backstop.
- **No red-team eval suite.** "We tried some jailbreaks and they didn't work" is not a safety evaluation. Build a structured eval suite with known attack patterns and measure attack success rate over time.
- **Confusing refusal rate with safety.** A model that refuses everything is "safe" but useless. Measure the tradeoff: safety (refusal rate on harmful requests) vs. utility (helpfulness on benign requests).
- **No incident response plan.** When (not if) a safety failure occurs, you need: detection (monitoring), containment (kill switch), investigation (audit logs), and remediation (patch + re-eval).

## Interview questions

1. **"How would you red-team an agent that reads customer emails and files tickets?"** Answer: threat model (attacker controls email content → can inject instructions). Attack surfaces: email body, attachments, sender address. Eval suite: known injection patterns (direct, indirect, multi-turn). Defense: least-privilege tools (read-only email, approval for ticket creation), egress allowlist, canary tokens, audit log. Measure attack success rate. Iterate.
2. **"Constitutional AI vs RLHF vs RLAIF?"** Answer: RLHF uses human preference labels (expensive, slow). Constitutional AI uses a set of principles; the model critiques its own outputs against them (cheaper, scalable). RLAIF replaces human feedback with AI feedback (cheaper but inherits AI biases). GRPO (DeepSeek-R1) uses group relative policy optimization with verifiable rewards.
3. **"How do you evaluate model safety?"** Answer: (1) Safety benchmarks (HarmBench, JailbreakBench, AIR-Bench, WMDP) for standardized comparison. (2) Custom eval suite with domain-specific attack patterns. (3) Red-team exercises (structured adversarial testing). (4) Continuous monitoring (attack success rate over time, regression testing). No single metric is sufficient; measure the safety-utility tradeoff.

## Red flags that fail you

- "We use a content filter" as the entire safety story.
- No red-team eval suite or safety benchmarks.
- Treating safety as a post-hoc addition rather than an architectural property.
- Confusing refusal rate with safety (high refusal = safe but useless).
- No incident response plan for safety failures.
- Not knowing the difference between safety (harmful outputs) and security (unauthorized access).

## Cheat card

- Safety ≠ security. Safety = harmful outputs/actions. Security = unauthorized access.
- Defense in depth: red-teaming → alignment → AI guardrails → deterministic containment → monitoring.
- Red-teaming: define threat model → enumerate surfaces → build eval suite → measure ASR → iterate.
- Benchmarks: HarmBench, JailbreakBench, AIR-Bench, WMDP.
- Alignment: RLHF (human labels) → DPO (preference pairs) → Constitutional AI (principles) → RLAIF (AI feedback) → GRPO (verifiable rewards).
- Containment is the architecture: egress allowlists, least-privilege tools, sandboxing, canary tokens.
- Safety is an architectural property, not a feature. Design for least privilege from the start.

## Sources

- [OWASP Top 10 for LLM Applications (2025 edition)](https://owasp.org/www-project-top-10-for-large-language-model-applications/) — accessed 2026-10-31
- [HarmBench: A Standardized Evaluation Framework for Automated Red Teaming](https://github.com/centerforaisafety/HarmBench) — accessed 2026-10-31
- [JailbreakBench: An Open Robustness Benchmark for Jailbreaking LLMs](https://github.com/JailbreakBench/jailbreakbench) — accessed 2026-10-31
- [Constitutional AI: Harmlessness from AI Feedback (Anthropic)](https://arxiv.org/abs/2212.08073) — accessed 2026-10-31
- [Simon Willison — The Lethal Trifecta (June 2025)](https://simonwillison.net/2025/Jun/16/the-lethal-trifecta/) — accessed 2026-10-31
- [Anthropic — Claude Code Auto Mode Eval (Aug 2026)](https://www.anthropic.com/) — accessed 2026-10-31

## Changelog

- 2026-10-31: Created — AI Safety & Red-Teaming identified as a gap (no dedicated module; only scattered coverage in T07-14, T06-19, T30).
