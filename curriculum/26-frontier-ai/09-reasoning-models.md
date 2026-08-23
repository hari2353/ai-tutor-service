# Reasoning Models: Test-Time Compute, RL on Chains, What Actually Changed

> **Track:** T26 Frontier AI · **Time:** 2.5h · **Prereqs:** T05-pretraining, T31-rl-for-llms · **Updated:** 2026-08-23
> **Module id:** `T26-reasoning-models` · **Tags:** reasoning, critical

## The 30-second version

A reasoning model is an LLM trained (mostly via reinforcement learning) to spend *variable* inference-time compute generating long internal chains of thought before answering — turning a fixed-cost text generator into a system whose accuracy scales with how long you let it think. This opened a third scaling axis beyond parameters and training data: test-time compute, which improves performance roughly logarithmically with thinking tokens and let OpenAI's o-series post results like **~96% on AIME math** and **87.7% on GPQA-Diamond**, while DeepSeek's R1 reproduced the recipe openly (MIT license, reasoning emerging from pure RL) at roughly **5% of o1's API price**. The economics inverted too: a normal LLM's bill is input-dominated, but a reasoning query might carry 500 input tokens against 5,000 billed output tokens of hidden thinking — one hard problem can burn 50,000 reasoning tokens (~$0.40 at o3-class pricing) and minutes of latency. Which is exactly when they *lose*: conversation, content generation, simple lookups, and orchestration-bound agent loops, where a fast model matches quality at 1/10th the cost and latency. Production reality is hybrid routing, not model loyalty.

## Why this gets asked

Because "should this request use a reasoning model?" is now a genuine production design decision with a wrong-answer cost attached in both directions: route everything to a reasoner and your p99 latency triples while your bill multiplies for zero quality gain; route everything to a fast model and hard queries fail confidently. Interviewers probe three layers. Mechanism: do you know what RL-on-chains actually trains (not prompted chain-of-thought, but learned exploration, backtracking, self-verification)? Economics: can you reason about why *output* tokens dominate cost and why thinking time is billed even when hidden? Judgment: do you know the failure modes — overthinking simple tasks, degraded instruction-following on trivial prompts, latency blowouts — well enough to design a routing layer rather than pick a favorite model? There's also a skepticism check embedded: candidates who repeat "reasoning models are just smarter" without engaging the log-scaling curves, the benchmark-vs-real-task gaps, or chain-of-thought faithfulness concerns read as trend-followers, not engineers.

---

## Lineage: past → present → future

**What came before.** Prompted chain-of-thought (2022) showed that asking a model to "think step by step" improved arithmetic and logic — but it was a prompting trick over a frozen policy: the model had no training signal rewarding good reasoning, chains were short, errors compounded uncorrected, and there was no way to buy more reliability with more compute. Self-consistency (sample k chains, majority-vote) was the first crude test-time-compute dial — accuracy did rise with k, revealing the seam the later models would mine — but it multiplied costs linearly and capped out quickly. Meanwhile pretraining scaling (bigger models, more data) delivered most 2020-2024 gains, and the field treated inference cost as roughly constant-per-query. The core limitation: a standard transformer spends the same fixed compute per token regardless of problem difficulty, so its only lever was being a bigger fixed thing.

**Where it stands now.** The o1→o3 line (OpenAI, 2024-2025) established that reinforcement learning on chain-of-thought produces models whose accuracy climbs with allocated thinking time on genuinely hard tasks — o3-class results include ~96% on AIME 2024 mathematics, 87.7% on GPQA-Diamond graduate science, ~71.7% on SWE-bench Verified, and Codeforces ratings around 2727 (top-percentile competitive programming), plus the striking high-compute ARC-AGI results on a benchmark designed to resist memorization. DeepSeek-R1 (January 2025) then reproduced the behavior openly — MIT license, published training recipe, with the headline finding that strong reasoning emerged from large-scale pure RL (GRPO-style) without supervised fine-tuning — scoring 79.8% on AIME 2024, 71.5% GPQA-Diamond, 49.2% SWE-bench at a small fraction of frontier API prices, with visible `<think>` traces. By 2026 every major lab ships a variant of the same idea (GPT-5-class extended thinking, Claude extended thinking with developer-set budgets, Gemini reasoning tracks), reasoning-effort tiers (minimal/low/medium/high) became a first-class API parameter, and the deployment consensus is two product modes: synchronous reasoning (seconds-to-minutes per answer) and agentic reasoning (chains spanning many tool calls over hours).

**Where it's heading.** High confidence: efficiency compression — the 2026 mantra is delivering what took $1M-class compute at a dollar-class price, via redundant-step reduction, trace compression, distilled reasoners (R1-distill-style small models retaining much of the teacher's reasoning), and hybrid architectures that toggle between fast and deep modes per query. Medium confidence: adaptive allocation — models that learn *when to stop*, spending 100 tokens on easy queries and 10,000 on hard ones instead of a user-set budget. Contested: how far the test-time curve extends (the pretraining laws gave a decade-long roadmap; inference-time scaling laws are still being mapped — nobody knows what 30 hours of thinking buys over 30 seconds), whether chain-of-thought remains faithful enough to monitor for alignment purposes, and whether RL-on-chains converges toward verifiable domains (math/code, where reward is checkable) or generalizes to fuzzy ones. Watch item: benchmark saturation is forcing evaluation migration toward private held-out sets and agentic task suites, because public benchmarks leak into training data fast.

---

## Mental model

```
THREE SCALING AXES (what got added in 2024):

  1. PRETRAINING      more data + params → smarter base   (saturating-ish)
  2. POST-TRAINING    RLHF/fine-tune → aligned base       (established)
  3. TEST-TIME        think longer per query → better     (NEW, 2024+)
                      answer ≈ f(thinking tokens),
                      improving ~logarithmically

THE MECHANISM:

  standard LLM:   prompt ──► token token token ──► answer     (fixed compute/token)
  reasoning LLM:  prompt ──► [think think think ... verify ...
                             backtrack ... think] ──► answer
                              \____ variable, BILLED ____/
                              trained via RL with rewards on FINAL answers,
                              so the chain itself evolves to be useful —
                              exploration, backtracking, self-correction emerge

ECONOMICS FLIP:

  base LLM bill:   ████████████ input tokens ████ few output   (input-dominated)
  reasoner bill:   ██ input ████ output(= mostly HIDDEN THINKING) ████
                   e.g. 500 in / 5,000 out where 4,500 are thinking
                   hard case: ~50,000 thinking tokens ≈ $0.40 + minutes

WHEN IT WINS vs LOSES:

  WINS:  math · competitive code · refactors · scientific derivation ·
         planning · verification-heavy agentic steps
  LOSES: chat latency · content generation · lookups ·
         orchestration-bound loops · subjective/style tasks
         (overthinking: thousands of tokens on a one-pass question)

PRODUCTION PATTERN: hybrid routing —
  fast model handles ~90% of traffic; router escalates on low confidence /
  hard task class; reasoner used as critic on drafts for critical paths.
```

The one-sentence compression: **reasoning models trade latency and dollars for accuracy along a new scaling axis — and the entire production discipline is deciding, per query, whether that trade is worth it.**

---

## How it actually works

### What RL on chains actually trains

Pretraining yields a next-token simulator. Reinforcement learning on chains of thought wraps generation in a reward loop: sample a problem, let the model generate a full (possibly thousands-of-token) chain ending in an answer, score the *final answer* against a verifier (unit tests for code, exact-match for math, rubric models elsewhere), and update the policy toward chains that produced correct answers. Because the reward lands only on outcomes, the chain content itself isn't dictated — and that's where the interesting behaviors emerged: R1's training showed models spontaneously developing longer chains on harder problems, backtracking ("wait, that's wrong..."), re-deriving from earlier steps, and exploring alternative approaches — behaviors that increased because they correlated with reward, not because anyone scripted them. Two technical anchors worth naming: **GRPO** (group relative policy optimization — sample a group of responses per problem and advantage-rank within the group, avoiding a separate value network), and the R1 finding that pure RL at scale sufficed, contrary to expectations that heavy SFT bootstrapping was required (R1-Zero); the shipped R1 added a small amount of cold-start SFT for readability. Distillation then compresses the capability: fine-tuning smaller models on the big reasoner's traces transfers substantial reasoning skill cheaply — the R1-distill line proved a small model with great traces beats a bigger model without them.

### The test-time compute curve

The empirical law: accuracy rises approximately logarithmically with thinking-token budget — big early gains, diminishing returns, eventual plateau (and occasionally degradation from overthinking loops on problems the model can't solve regardless of budget). o1's published curves first demonstrated this across math/science/code; o3's high-compute settings pushed it further (its ARC-AGI high-compute runs averaged tens of millions of tokens per problem — RAND cited the extreme configuration as requiring on the order of 10,000 H100-hours-equivalent infrastructure for ten-minute single-task responses). Three practical corollaries: (1) the curve's *shape* differs per task — easy tasks saturate almost immediately (all the gain happens in the first few hundred tokens), hard-but-solvable tasks have long useful tails, unsolvable tasks never rise; (2) sampling-based test-time scaling (best-of-k, self-consistency) and chain-length scaling compose but multiply costs; (3) because gains are log-shaped, a 2x budget rarely buys 2x accuracy — budget-setting is a marginal-return optimization, which is precisely why APIs expose coarse effort tiers (minimal/low/medium/high) rather than raw token counts.

### What actually changed (and what didn't)

Changed: reliability on multi-step verifiable tasks (the jump from GPT-4o-class 13% to o3-class ~96% on AIME is the cleanest demonstration); the existence of a per-query intelligence dial; the cost structure (output/thinking-dominated bills); agent design space (models that can chain 10+ tool calls inside one deliberation, catch their own intermediate errors, and persist intent across long horizons). Didn't change: hallucination on factual recall (a reasoner can construct a flawless logical argument to a fabricated premise — longer thinking does not fix missing knowledge, and retrieval still matters); style/creative quality (unaffected or slightly harmed); instruction-following on simple prompts (sometimes degraded — overthinking introduces ignored constraints); and knowledge cutoffs. The honest summary interviewers want: reasoning models changed *how hard* the average frontier model can think, not *what it knows*, and the failure modes moved rather than vanished.

### The economics, concretely

Base-model bills are input-dominated: pay for context, get a short answer. Reasoning models invert this: a representative frontier-reasoner query is maybe 500 input tokens and 5,000 output tokens where ~4,500 are hidden thinking you're billed for anyway. Hard-problem examples scale up brutally — one query burning ~50,000 reasoning tokens before a 200-token answer runs ~$0.40 at o3-class pricing, and o3's hardest-tier runs averaged ~57 million tokens per question at ~14 minutes each. Latency compounds the bill: 30-second answers reshape UX and force async patterns. This birthed "reasoning budget" engineering: per-task-type budget tables, effort tiers mapped to expected difficulty, and the routing layer as standard architecture — classify complexity, send ~90% of traffic to fast models, escalate on low confidence or hard task classes, use the reasoner as a critic reviewing drafts on critical paths. Cost prediction is also genuinely harder: variable thinking time means per-query cost is a distribution, not a number, and capacity planning inherits that variance (sporadic production traffic prevents the batching efficiencies that make big-model serving economical).

### Failure modes specific to reasoning models

Overthinking (thousands of tokens spent on questions a fast model answers correctly in one pass — measurable as accuracy-flat-or-down versus budget curves); overcomplication (introducing elaborate solutions where simple ones suffice, occasionally degrading instruction-following); runaway loops (chains that circle without converging, burning budget until limits); language mixing and readability drift in long chains (R1 documented this, motivating its SFT stage); and the faithfulness problem — the visible chain is not guaranteed to be the actual causal computation, which matters if you're auditing chains for safety monitoring rather than using them as explanations. Each maps to a mitigation: routers, budgets/tiers, loop detectors with forced termination, distillation for consistency, and treating chains as telemetry-not-testimony.

---

## Build it from scratch

**Exercise: a logprob-based reasoning-trace evaluator sketch.** The realistic version of "evaluate a reasoning trace" without a second LLM call: score a chain mechanically — answer correctness, calibration (does token-level confidence track correctness?), efficiency (tokens per correct answer), and loop/repetition detection:

```python
# untested sketch — mechanical reasoning-trace evaluator.
# Uses logprobs + surface stats; deliberately no LLM-judge. Real systems
# combine this with sampled-consistency checks and rubric models.
import re
from dataclasses import dataclass

@dataclass
class Trace:
    prompt: str
    thinking: str          # the chain-of-thought text
    answer: str
    answer_logprobs: list[float]   # per-token logprobs of the answer span
    gold: str | None = None        # if a reference exists

def norm(s): return re.sub(r"[^a-z0-9]", "", s.lower())

def is_correct(t: Trace) -> bool:
    return t.gold is not None and norm(t.gold) in norm(t.answer)

def avg_logprob(lps): 
    import math
    return sum(lps)/len(lps) if lps else float("-inf")

def repetition_score(text: str, n: int = 8) -> float:
    """Fraction of n-grams that are repeats — proxy for circling loops."""
    words = text.split()
    grams = [tuple(words[i:i+n]) for i in range(len(words)-n+1)]
    return 0.0 if not grams else 1 - len(set(grams))/len(grams)

def evaluate(t: Trace) -> dict:
    lp = avg_logprob(t.answer_logprobs)          # confidence proxy
    conf = 1 / (1 + 2.718281828 ** (-lp))        # squashed to [0,1]
    correct = is_correct(t)
    n_think = len(t.thinking.split())
    rep = repetition_score(t.thinking)
    return {
        "correct":            correct,
        "confidence":         round(conf, 3),
        # miscalibration flag: confident AND wrong, or shy AND right
        "miscalibrated":      (conf > 0.85 and not correct)
                              or (conf < 0.35 and correct),
        "thinking_tokens":    n_think,
        "efficiency":         round(n_think / max(1, len(t.answer.split())), 1),
        "loop_risk":          round(rep, 3),   # >0.25 usually = circling
        "overthink_suspect":  n_think > 4000 and rep < 0.1,
    }

def route_decision(scores: dict, budget_tokens: int = 8000) -> str:
    """Tiny router: the production pattern in five lines."""
    if scores["loop_risk"] > 0.25:
        return "retry_with_fast_model"          # stuck circling — don't pay more
    if scores["correct"] and scores["efficiency"] < 20:
        return "keep_fast_path"
    return "escalate_to_reasoner" if not scores["correct"] else "accept"

# demo shape:
# t = Trace(prompt="...", thinking="...long cot...", answer="42",
#           answer_logprobs=[-0.11,-0.03,-0.22], gold="42")
# print(evaluate(t)); print(route_decision(evaluate(t)))
```

What this teaches: confidence-from-logprobs gives a free calibration signal; the confident-and-wrong quadrant is the expensive failure in production; efficiency ratios expose overthinking; n-gram repetition catches runaway loops cheaper than any judge model; and the router function is where all the module's economics collapse into code. Extensions: add best-of-k selection by mean logprob, compare against sampled self-consistency (same question, temperature 1, k=5, vote), and plot accuracy-versus-thinking-budget from logged traffic to draw your own test-time curve.

For a runnable full lab (RL-finetune a tiny model on verifiable rewards, measure the curve), no lab exists yet for this module — a reasonable ask is `(lab pending)`.

---

## How it's done in production

| Concern | Typical production choice | Why |
|---|---|---|
| Default traffic | Fast/non-reasoning model serves ~90% of requests | Reasoning adds latency/cost with no quality gain on easy queries |
| Escalation | Router classifies difficulty/confidence → reasoning model | Hybrid routing is the consensus 2026 deployment pattern |
| Budget control | Effort tiers (minimal/low/medium/high) or explicit thinking budgets (e.g., 1,024-token minimums) | Marginal returns are log-shaped; coarse dials match the curve |
| Critical paths | Reasoning-as-critic: fast draft, reasoner reviews/corrects | Cheaper than full delegation; catches fast-model errors where it matters |
| Agents | Reasoning backbone + orchestration; deep tool-chaining (10+ calls/deliberation) | Verification-heavy long-horizon work is where the premium pays off |
| Cost control | Per-task-type budget tables; trace-length alerts; loop detectors | Output-dominated bills make variance management a first-class duty |
| Open-weight option | R1-family/distills for self-hosting, transparent `<think>` traces | Cost floor, data residency, auditability of visible reasoning |
| Evaluation | Private held-out sets + task-specific suites, not public benchmarks | Public benchmarks saturate/leak; task fidelity beats leaderboard rank |

**What breaks in production**

| Symptom | Cause | Fix |
|---|---|---|
| Bill doubled, quality unchanged | Easy traffic routed to reasoner (overthinking) | Router with confidence gate; effort tier downgraded for easy classes |
| Chat feels sluggish, users complain | 30s+ thinking time on conversational turns | Async/streamed status, reserve reasoners for analysis paths |
| Confident wrong answers on hard queries | Miscalibration under distribution shift | Sample-k self-consistency; logprob gates; human review on confident-and-wrong quadrants |
| Occasional 15-minute responses, timeouts | Runaway chains on unsolvable-for-this-model inputs | Token/time ceilings, loop detectors, fallback to fast model with honest "couldn't solve" |
| Answers ignore simple instructions | Overthinking degrades constraint-following | Keep simple prompts on fast models; re-state constraints post-thinking |
| Costs unpredictable month-to-month | Variable thinking time → per-query cost is a distribution | Budget tables per task type; p95 cost alerting; effort caps by endpoint |
| Benchmark score doesn't transfer to your tasks | Public-benchmark contamination/saturation | Evaluate on private held-out sets; measure task completion, not leaderboards |

---

## Tradeoffs & when NOT to use it

- **Don't route conversational/chat traffic to reasoners.** Latency destroys UX and quality gain is nil; this is the clearest-cut anti-pattern.
- **Don't use reasoners for content generation, copy, or style-led writing.** Fast-model output is hard to distinguish; the bottleneck is taste, not logic.
- **Don't reason over simple lookups.** "Capital of Bolivia"-class questions gain nothing from extended thought; you're buying overthinking.
- **Don't drop a reasoner into an orchestration-bound agent loop** where most wall-clock is tool calls and parsing — the thinking premium is wasted on coordination overhead unless individual steps need verification depth.
- **Don't treat chains of thought as ground truth.** Faithfulness is imperfect; audit decisions with outcome-level checks and telemetry, not because-the-chain-said-so.
- **Don't plan product economics on current per-token prices.** Inference pricing is moving targets; a reasoner costing $X/query today may cost X/10 in two years — build routing/budgets as configurable policy, not hardcoded assumptions.
- **When NOT to use reasoning models at all:** high-throughput pipelines with tight latency SLOs, cost-sensitive bulk classification, and any workload where a competent first-pass answer is the requirement. Reach for them when being right matters more than being fast: derivations, complex refactors, multi-factor analysis, verification-critical agent steps.

---

## Interview questions

### Q1 — What is test-time compute, and why is it called a 'third scaling axis'?
**Testing:** conceptual clarity beyond buzzwords.
**Answer:** Allocating more inference-time compute per query to improve accuracy — letting the model generate long internal chains of thought, explore alternatives, and self-verify before answering. Third axis because the field previously scaled capabilities along parameters and training data (pretraining) and then post-training alignment; reasoning models made per-query compute a productive axis, with accuracy climbing roughly logarithmically with thinking tokens. Its practical meaning: the same model performs at different capability levels depending on per-query budget — intelligence became a dial, not just a property.
**Follow-up trap:** *"Is prompted chain-of-thought the same thing?"* — no. Prompted CoT elicits whatever behavior pretraining left in a frozen policy, with short chains and no reward signal shaping the reasoning itself. RL-on-chains changes the policy: the model is *trained* with outcome rewards, so exploration/backtracking/self-correction emerge because they correlate with correct final answers. The distinction is training-loop presence, not formatting.

### Q2 — Walk through what RL on chains of thought actually trains, including why backtracking behavior emerges.
**Answer:** Generate a full chain ending in an answer for a training problem; score the final answer with a verifier (tests, exact-match, rubric); update the policy toward chains that led to correct outcomes (R1 used GRPO-style group-relative advantages — ranking a group of samples per problem, no separate value network). Because reward lands only on outcomes, chain structure is free to evolve; behaviors that raise success probability get reinforced, so backtracking ("wait, that's wrong"), re-derivation, and approach-switching emerge spontaneously — R1-Zero demonstrated this from pure RL without SFT. Shipped R1 added light cold-start SFT for readability/language consistency.
**Follow-up trap:** *"If reward is only on final answers, why doesn't the model learn degenerate chains?"* — sometimes it does: R1-Zero showed readability degradation and language mixing, which is exactly why production versions add SFT stages and why faithfulness remains an open concern. Outcome-only reward shapes chains statistically, not semantically — a key caveat when you treat traces as explanations.

### Q3 — Quote the headline evidence that reasoning models changed capability, with numbers.
**Answer:** The AIME gap is the cleanest single number: GPT-4o-class ~13% versus o3-class ~96% on AIME 2024 mathematics. Supporting: o3 ~87.7% GPQA-Diamond (graduate science), ~71.7% SWE-bench Verified, Codeforces ~2727; DeepSeek-R1 open reproduction at 79.8% AIME / 71.5% GPQA-D / 49.2% SWE-bench, MIT-licensed, at roughly 5% of o1's API price. Plus o3's high-compute ARC-AGI runs on a benchmark built to resist memorization — averaging tens of millions of tokens per problem.
**Follow-up trap:** *"Why hedge those numbers in a real answer?"* — because public benchmarks saturate and contaminate quickly; scores move between report generations, configurations (compute tiers) change outcomes materially, and vendor-reported numbers aren't independently audited. Citing them with source-and-date, and immediately noting private-evaluation caveats, signals maturity rather than marketing.

### Q4 — Why did DeepSeek-R1 matter so much beyond its benchmark scores?
**Answer:** It falsified the assumption that frontier reasoning required frontier-lab resources: MIT-licensed weights, a published recipe, and the R1-Zero finding that strong reasoning emerges from large-scale pure RL without supervised fine-tuning. It reset pricing expectations (~5% of o1's API price), gave everyone transparent `<think>` traces for inspection/distillation, seeded an open ecosystem (distilled variants proving small models trained on great traces beat bigger models without them), and turned reasoning-model access into a strategic/commoditization debate overnight.
**Follow-up trap:** *"Does R1 prove RL-on-chains is cheap?"* — no; it proves the *recipe* is replicable and the resulting product is cheap to serve. Training still consumed serious compute; the disruption was transparency and price pressure, not free intelligence. Conflating serving cost with training cost is the trap.

### Q5 — Explain the economics inversion: why do reasoning models flip bills from input-dominated to output-dominated?
**Answer:** Base-model usage: large context in, short answer out — input dominates. Reasoning models insert thousands of billed hidden-thinking tokens before the answer: a representative query is ~500 input tokens against ~5,000 output tokens of which ~4,500 are thinking. Scale example: one hard problem burning ~50,000 reasoning tokens before a 200-token answer ≈ $0.40 at o3-class pricing; hardest-tier configurations averaged ~57M tokens and ~14 minutes per question. Consequences: per-query cost becomes a distribution (variable thinking time), capacity planning gets spikier, and budget/effort controls become first-class API surfaces.
**Follow-up trap:** *"So per-token pricing is what matters?"* — no; per-*task* economics matter. A reasoner at higher per-token rates can be cheaper per resolved task if it eliminates retries, or dearer if it overthinks trivial queries. Teams that optimize per-token rates instead of per-task success rates systematically misroute traffic.

### Q6 — Describe the test-time compute curve's shape and its three practical corollaries.
**Answer:** Approximately logarithmic: steep early gains, diminishing returns, plateau — occasionally degradation via overthinking loops. Corollaries: (1) task-dependence — easy tasks saturate within hundreds of tokens, hard-but-solvable tasks have long tails, unsolvable ones never rise; (2) it composes with sampling-based scaling (best-of-k, self-consistency) at multiplicative cost; (3) log-shape makes budget-setting a marginal-returns problem — hence coarse effort tiers (minimal/low/medium/high) rather than raw token counts as the exposed interface.
**Follow-up trap:** *"Then why does anyone use high tiers?"* — because some production tasks live on the long tail: competition-grade derivations, gnarly debugging, high-stakes analysis where the last few points of accuracy are the product. The error is applying tail-tier budgets to head-of-curve tasks, not having tiers at all.

### Q7 — Name the situations where reasoning models LOSE to fast models, and why.
**Testing:** the anti-hype side; many candidates can only argue the positive case.
**Answer:** Conversational interactions (latency kills UX, zero accuracy gain); content generation (style bottleneck — outputs indistinguishable at 10x cost); simple lookups (no benefit from extended thought); orchestration-bound agent loops (wall-clock is tools/parsing; thinking premium wasted on coordination); subjective/creative work (logic depth irrelevant); and high-throughput latency-SLO pipelines. Plus the subtle one: overthinking — measurably spending thousands of tokens where a fast model answers correctly in one pass, sometimes *degrading* instruction-following by over-complicating.
**Follow-up trap:** *"Give a quantitative routing rule you'd defend."* — escalate only when (expected error cost × error probability reduction) exceeds (token delta cost + latency penalty), estimated per task class from logged data; in practice most teams find a confidence-gated router sending ~90% to fast models captures nearly all available value. Any rule you can't tie to logged accuracy-vs-budget data is vibes.

### Q8 — How would you set up hybrid routing in production? Include the failure handling.
**Answer:** Classify incoming queries (task class, complexity estimate, fast-model confidence via logprobs/self-consistency); route ~90% to the fast default; escalate on low confidence, hard task classes, or explicit user demand; optionally run reasoning-as-critic (fast draft, reasoner review on critical paths). Set per-task-class thinking budgets/effort tiers from logged accuracy-vs-budget curves. Failure handling: token/time ceilings with loop detection (repetition scores), fallback to fast model with honest uncertainty signaling, and p95 cost alerting since per-query cost is a distribution.
**Follow-up trap:** *"Who decides the thresholds, and how do they drift?"* — they must be owned as configuration with periodic recalibration against fresh eval sets; models change monthly, so static thresholds rot silently. The mature answer treats the router as a monitored ML component with its own dashboards, not a constants file.

### Q9 — What is the chain-of-thought faithfulness problem, and when should it change your architecture?
**Answer:** The visible chain is not guaranteed to be the model's actual causal computation — RL shapes chains statistically toward rewarded outcomes, so traces can rationalize rather than explain (and can be influenced toward stated-but-unused premises). Implication: chains are excellent telemetry and weak testimony. Architecture impact: compliance/safety-critical flows shouldn't certify decisions via chain-inspection alone; they need outcome-level verification, independent checks, and monitoring research (whether CoT can reliably expose deception remains an open question labs actively study).
**Follow-up trap:** *"R1 exposes its `<think>` tags — doesn't openness solve this?"* — visibility shows you *a* process, not *the* process; a readable trace can still omit the decisive factors. Transparency helps debugging and distillation enormously, but treating displayed reasoning as an auditable causal record confuses legibility with faithfulness.

### Q10 — Your team's agent uses a reasoner for every step and burns 30-60 s per action. Restructure it.
**Answer:** Profile first: separate thinking-bound steps from orchestration-bound ones. Then: fast model plans/executes routine steps; reasoner reserved for (a) initial planning on complex goals, (b) verification of consequential actions (critic pattern), (c) recovery when fast-path confidence drops. Add streaming/status UX so perceived latency shrinks, parallelize independent tool calls, cache stable context, and cap thinking budgets per step type. Typical result: reasoner touches ~10-20% of steps while total-task success holds — the win comes from matching compute to step difficulty, not global escalation.
**Follow-up trap:** *"Doesn't mixing models break context/state continuity?"* — it's a real cost: state must be serialized across models with consistent formats, and critic/handler disagreements need resolution policy. But that plumbing is bounded engineering; uniform-escalation cost curves are unbounded. The trade favors routing once task volume is nontrivial.

### Q11 — Why might reasoning models NOT fix hallucination, and what actually helps?
**Answer:** Hallucination is largely a knowledge/retrieval problem; reasoning supplies computation over available representations. A reasoner can construct internally-consistent, logically-flawless arguments to false premises — longer thinking amplifies fluency, not truth. What helps: retrieval grounding, citation requirements, outcome verification against external checkers, calibrated abstention (rewarding "I don't know" in training), and sampling-consistency checks. Reasoning does help where errors arise from faulty *manipulation* (multi-step arithmetic, logic) rather than missing facts — knowing which error regime you're in determines whether the reasoner is medicine or placebo.
**Follow-up trap:** *"But benchmarks show reasoning models hallucinating less..."* — partially true via self-check effects and better calibration on reasoning-adjacent queries, yet measured on knowledge-heavy tasks the gap narrows dramatically. The defensible claim: fewer manipulation-errors, similar fabrication-tendency — design accordingly.

### Q12 — Where does test-time scaling go from here, and what would falsify the paradigm?
**Answer:** Consensus directions: efficiency compression (dollar-class cost for what took million-class compute — trace compression, redundancy pruning, distills), adaptive stopping (models learning when to stop thinking per query), hybrid fast/deep toggling in one system, and agentic reasoning spanning hours of tool interaction. Open questions: how far the curve extends (nobody has mapped 30-minute-plus thinking at scale), generalization beyond verifiable domains, and monitorability. Falsification would look like: accuracy curves flattening universally at modest budgets, or discovering the gains were mostly benchmark-specific search rather than transferable deliberation — current evidence supports real but domain-skewed (verifiable-task) scaling.
**Follow-up trap:** *"If efficiency improves 100x, does routing still matter?"* — yes, because routing optimizes the ratio of value to cost at the margin, and cheap reasoning invites broader deployment where the easy-query waste multiplies too; Jevons-style dynamics apply. Absolute cost falling doesn't make allocating zero compute to trivial queries irrational.

---

## Red flags that fail you

- Treating "reasoning model" and "prompted chain-of-thought" as interchangeable (training-loop absence/presence is the distinction).
- No numbers: unable to quote the AIME-class gap or the thinking-tokens-dominate-billing structure.
- Recommending reasoners for chat/content/lookups — the canonical routing anti-pattern.
- Ignoring that hidden thinking tokens are billed; surprise at output-dominated invoices.
- Believing more thinking always helps; unaware of overthinking, loops, and plateau shapes.
- Treating visible chains of thought as faithful causal records for audits.
- Claiming reasoning models solved hallucination.
- Building products on current per-token economics as if static.

---

## Cheat card

```
WHAT CHANGED    3rd scaling axis: accuracy ≈ f(test-time compute),
                ~logarithmic in thinking tokens. RL on chains (outcome
                rewards, GRPO group-relative, no value net) trains
                explore/backtrack/self-verify. R1-Zero: pure RL sufficed;
                R1 added light SFT for readability. Distills: small model
                + great traces > big model without.

HEADLINE NUMBERS
  AIME 2024:   GPT-4o ~13% → o3 ~96% · R1 79.8%
  GPQA-D:      o3 87.7% · R1 71.5%
  SWE-bench V: o3 ~71.7% · R1 49.2%
  Codeforces:  o3 ~2727 · R1 2029
  R1 price ≈ 5% of o1 API · MIT license · visible <think>
  o3 hard tier: ~57M tokens/question · ~14 min
  extreme ARC-AGI config: ~10k H100-class for 10-min single task

ECONOMICS FLIP  base bill: input-dominated (context >> answer)
                reasoner bill: OUTPUT-dominated — e.g., 500 in / 5,000 out
                (4,500 hidden thinking, billed). Hard query: ~50k think
                tokens ≈ $0.40. Per-query cost = distribution → budget
                tables + p95 alerting. Think per-TASK cost, not per-token.

CURVE SHAPE     log gains; easy tasks saturate fast; hard-solvable have
                long tails; unsolvable never rise. Tiers: minimal/low/
                medium/high. Composes with best-of-k/self-consistency
                (costs multiply).

WHEN THEY LOSE  chat (latency) · content gen (style bottleneck) ·
                lookups (zero gain) · orchestration-bound loops ·
                creative/subjective · high-throughput SLOs.
                OVERTHINKING: thousands of tokens where fast model nails
                it in one pass; can degrade instruction-following.

PRODUCTION      hybrid routing: ~90% fast; escalate on confidence/task
                class · reasoning-as-critic on critical paths · effort/
                budget dials per task class · loop detectors + ceilings ·
                eval on PRIVATE held-out sets (public benchmarks leak).

CAVEATS         chains = telemetry, not testimony (faithfulness open).
                Hallucination ≠ fixed (knowledge problem, not compute).
                Prices move: build routing as configurable policy.
```

## Sources

- [Reasoning Models in 2026: o3, R2, and the Compute-at-Inference Shift — jamesm.blog](https://jamesm.blog/ai/reasoning-models-2026/) — accessed 2026-08-23
- [DeepSeek-R1 incentivizes reasoning in RL LLMs via RL — arXiv 2501.12948](https://arxiv.org/abs/2501.12948) — accessed 2026-08-23
- [Learning to Reason with LLMs (o1) — OpenAI](https://openai.com/index/learning-to-reason-with-llms/) — accessed 2026-08-23
- [When AI Takes Time to Think: Implications of Test-Time Compute — RAND](https://www.rand.org/pubs/commentary/2025/03/when-ai-takes-time-to-think-implications-of-test-time.html) — accessed 2026-08-23
- [Reasoning Models in 2026: o3, DeepSeek R1, and Claude Extended Thinking — aitraining2u](https://www.aitraining2u.com/blog/reasoning-models-o3-r1-claude-2026.html) — accessed 2026-08-23
- [AI Reasoning Models 2026: From OpenAI o3 to DeepSeek-R1 — Zylos Research](https://zylos.ai/en/research/2026-01-24-ai-reasoning-models) — accessed 2026-08-23
- [Test-Time Compute and Reasoning Models — Benchmark Reasoning Project](https://brpreiss.com/reasoning/test-time-compute) — accessed 2026-08-23
- [Reasoning Models: o1, o3, and Test-Time Compute — kindatechnical.com](https://kindatechnical.com/generative-ai-llm/reasoning-models-o1-o3-test-time-compute.html) — accessed 2026-08-23
- [Test-Time Compute: How Reasoning Models Are Changing AI Agents — SkillGen](https://skillgen.io/test-time-compute-ai-agents-2026) — accessed 2026-08-23

## Changelog
- 2026-08-23 — created