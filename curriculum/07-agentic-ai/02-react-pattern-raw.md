# ReAct Implemented Raw + Plan-Execute + Reflexion

> **Track:** T07 Agentic AI · **Time:** 2.5h · **Prereqs:** `T07-agent-loop-from-scratch` · **Updated:** 2026-07-26
> **Module id:** `T07-react-pattern-raw` · **Tags:** sprint, core, reasoning
> **Lab:** `labs/py/03-reasoning-patterns/`

## The 30-second version

ReAct, Plan-and-Execute, Reflexion and Tree-of-Thought are four answers to one question: *when does the model decide what to do next?* ReAct decides per step after seeing each observation; Plan-and-Execute decides once up front and pays with a plan that can go stale; Reflexion decides again after a whole attempt fails, using a written critique as memory; ToT decides across parallel branches at 10–100× the tokens. The decision rule is one line: **if later steps depend on what earlier steps return, loop (ReAct); if they don't, plan up front (cheaper, parallelisable, auditable); add a critique loop only when you have an external verdict — tests, compiler, schema, DB error — because self-critique without one is well documented to add tokens and not accuracy.** And ReAct in 2026 is not text parsing: the Thought is the model's reasoning block and the Action is a structured `tool_use` block from the API, so the whole `Thought:/Action:/Observation:` regex layer is dead transport. Reasoning models absorbed the Thought half of all this and left the Act/Observe half completely untouched, which is exactly where the boundary between the model's job and your harness now sits.

## Why this gets asked

Because this is the topic where candidates recite paper names and interviewers are checking whether you can *choose*. Anyone can say "we used ReAct." The signal is whether you know that ReAct costs you a quadratically-growing reasoning trace, that a plan committed at step 0 is a bet on a decomposition you can't verify yet, and that the reflection loop your team added last quarter probably never got an A/B test. The failure the interviewer has lived through is one of two: a Plan-and-Execute pipeline that confidently executed steps 4 through 8 against a table that step 3 had already reported missing, or a reflection loop that turned a correct first answer into a wrong second one because the model was asked "are you sure?" and complied.

---

## Lineage: past → present → future

**What came before.** Chain-of-thought (Wei et al., 2022) got the model to reason but left it sealed in its own weights: on HotpotQA, CoT hallucinated because it had no way to check anything against the world. The mirror-image approach, action-only agents (WebGPT, SayCan, ACT-1), could touch the world but couldn't plan: the ReAct paper's own act-only ablation had *identical observations to ReAct* and still failed to synthesise the answer, because nothing in the context connected the observations into a conclusion. **ReAct** (Yao et al., arXiv Oct 2022, ICLR 2023) is the join: interleave a free-text reasoning trace with actions so the thought can induce, track and update the plan while the actions supply ground truth. With one or two in-context examples it beat imitation and RL baselines by **+34% absolute success on ALFWorld and +10% on WebShop**. The specific pain it killed was CoT's ungrounded confidence, and the specific pain that then killed *its own implementation* was string parsing: the paper's `Action: search[Bob's "Big" Idea]` format had to be regexed out of free text, and the parse broke on brackets, quotes, newlines and markdown fences. Every serious 2023 agent codebase had a `try: parse_action(text) except OutputParserException:` retry path, and it was the single most common source of wasted turns.

**Where it stands now.** Three things settled and one is genuinely contested. **Settled 1: native tool calling replaced parsing.** Every major provider now returns tool calls as first-class API objects and reasoning as a separate content block, so the ReAct triple is `thinking_block → tool_use block → tool_result block`. Parse-failure rate went from single-digit percent to zero, and constrained decoding guarantees the arguments validate against the schema. Describing ReAct as regex-parsing `Thought:/Action:` in 2026 marks you as someone who last read the literature in 2022. **Settled 2: ToT and self-consistency have been largely subsumed for math and code.** Reasoning models do the branching internally; the measured gains from external multi-path sampling on modern models are now inside the noise (see the numbers below). **Settled 3: verifier-backed retry works; introspection-only retry does not.** Huang et al. (ICLR 2024) showed that *intrinsic* self-correction — no external feedback — fails to reliably improve reasoning on GSM8K, CommonSenseQA and HotpotQA and sometimes degrades it, and that several published gains were artifacts of a deliberately weak initial prompt. **Contested: how much up-front planning to impose.** The planning camp points at auditability, cost and parallelism; the loop camp points at plan lock-in. The best current evidence is a middle position: "Learning When to Plan" (arXiv 2509.03581) shows that *always* planning before every action, which is exactly what ReAct prompts do, "is computationally expensive and degrades performance on long-horizon tasks, while never planning further limits performance." Neither pole wins; the allocation is the thing.

**Where it's heading.** **High confidence:** the surviving scaffolding is the part that touches the world. Reasoning models absorbed the "Thought" half of ReAct; they cannot absorb the "Act/Observe" half, because a real side effect and a real observation are not things a forward pass can produce. Budgets, stop conditions, tool dispatch, durable state and *real verifiers* stay yours. **Medium confidence:** the industry converges on adaptive depth — one model, a dial for how much internal deliberation to spend, chosen per request by a cheap difficulty classifier, rather than four named prompt architectures. Anthropic's extended-thinking budget parameter and the adaptive-consistency line of work (7.9× fewer samples for <0.1% accuracy loss) are both early instances. **Speculative:** whether reflection ever becomes fully internal. It cannot for anything with an external ground truth — a unit test is not a thought — so my read is that "reflection" splits permanently into internal deliberation (model's job) and verifier-driven retry (your job), and the word stops being useful. Treat any 2026 claim that a named reasoning pattern is universally best as fashion until someone shows you an eval on *your* task distribution.

---

## Mental model

Four patterns, one axis: **where the decision point sits relative to the observations.**

```
ReAct — decide AFTER each observation (interleaved)
   T1 → A1 → O1 → T2 → A2 → O2 → T3 → answer
        └── every decision sees all prior reality ──┘
   adaptive · quadratic context growth · n round trips

Plan-Execute — decide BEFORE any observation (up front)
   PLAN[s1,s2,s3,s4] ──┬─→ exec s1 → O1
                       ├─→ exec s2 → O2      (parallelisable, small contexts)
                       ├─→ exec s3 → O3
                       └─→ exec s4 → O4 ──→ SOLVE(plan, O1..O4)
   cheap · auditable · BLIND to O1 when choosing s2
   (+ optional REPLAN edge = the whole saving, spent)

Reflexion — decide AGAIN after the attempt fails (outer loop)
   attempt_1 ──→ VERDICT ──fail──→ write critique ──┐
                    │                              │
                    pass → done          episodic memory
                                                   │
   attempt_2 (memory in context) ──→ VERDICT ──────┘   cap: 2-3
   needs a REAL verdict. without one it is a token generator.

ToT / self-consistency — decide across PARALLEL branches, then score
   root ─┬─ b1 ─┬─ b11   score, prune, expand best
         ├─ b2  └─ b12   k branches × d depth = k^d evaluations
         └─ b3           10-100x tokens of a single pass
```

The one sentence to internalise: **these are not competing frameworks, they are four different answers to "how much do I commit before I look."** ReAct commits nothing and pays in round trips. Plan-Execute commits everything and pays when reality disagrees. Reflexion commits, checks, and re-commits, and only works if the check is real. ToT commits to many things at once and pays in tokens.

---

## How it actually works

### ReAct raw, 2022 edition (so you can say why it died)

```python
# untested sketch — this is the 2022 shape, kept for archaeology
PROMPT = """Answer the question using interleaved Thought, Action, Observation.
Actions: search[<query>] | lookup[<term>] | finish[<answer>]

Question: {q}
"""

ACTION_RE = re.compile(r"Action:\s*(\w+)\[(.*?)\]\s*$", re.S | re.M)

def react_2022(q, max_steps=8):
    scratchpad = ""
    for _ in range(max_steps):
        # stop=["Observation:"] is load-bearing: without it the model
        # HALLUCINATES the observation and keeps going against fiction.
        out = complete(PROMPT.format(q=q) + scratchpad, stop=["\nObservation:"])
        m = ACTION_RE.search(out)
        if not m:
            # ~2-8% of turns in practice. burns a full round trip.
            scratchpad += out + "\nObservation: Malformed action. Use search[q].\n"
            continue
        tool, arg = m.group(1), m.group(2)
        if tool == "finish":
            return arg
        scratchpad += out + f"\nObservation: {run(tool, arg)}\n"
    return "step budget exhausted"
```

Three things are wrong with this and all three are the same thing — the protocol is prose:

1. **`stop=["\nObservation:"]` is mandatory and fragile.** Forget it and the model writes its own observation, believes it, and continues reasoning against a fabrication. The symptom in a trace is an `Observation:` line that never appears in your tool logs.
2. **The regex is a parser for an unspecified grammar.** `search[Bob's "Big" Idea]`, nested brackets, a markdown fence, a stray newline — all produce a failed parse, and each failure costs one full model round trip plus the whole scratchpad re-sent.
3. **There is no arity or type checking.** `search[]`, `search[a, b]` and `serach[x]` are all syntactically fine and semantically garbage.

### ReAct raw, 2026 edition

The pattern is unchanged. The transport is structured, and that is the whole difference.

```python
# untested sketch: ReAct = the loop from T07-agent-loop-from-scratch
# with reasoning turned on and preserved in the history.
resp = client.messages.create(
    model=MODEL,
    max_tokens=4096,
    thinking={"type": "enabled", "budget_tokens": 2048},   # ← the "Thought"
    tools=[t.schema for t in tools.values()],              # ← typed "Action" space
    messages=messages,
)

for block in resp.content:
    if block.type == "thinking":  trace.thought = block.thinking   # audit hook
    if block.type == "tool_use":  calls.append(block)              # parsed by API

messages.append({"role": "assistant", "content": resp.content})    # keep thinking
messages.append({"role": "user", "content": [                      # ← "Observation"
    {"type": "tool_result", "tool_use_id": c.id, "content": run(c)} for c in calls
]})
```

| ReAct 2022 | ReAct 2026 | What you stop paying for |
|---|---|---|
| `Thought:` in free text | reasoning / thinking content block | prompt real estate for the format spec |
| `Action: tool[arg]` regexed out | `tool_use` block, schema-validated | the parse-failure retry path entirely |
| `Observation:` appended as prose | `tool_result` block keyed by `tool_use_id` | ambiguity about which result answers which call |
| one action per turn (format-imposed) | N parallel `tool_use` blocks per turn | serialised round trips for independent lookups |
| `stop` sequence to prevent fabricated observations | structural: the turn ends at the tool boundary | the fabricated-observation failure mode |

**Keep the reasoning block in the history.** This is the part people get wrong. If you drop the thinking block when appending the assistant turn, you have re-implemented act-only, which is the ablation the paper showed *fails on identical observations*. Also: with some providers, stripping thinking blocks between tool-use turns invalidates the signature and errors, which is the good outcome, because it fails loudly instead of quietly degrading.

### Why the reasoning trace actually improves action selection

Four mechanisms, in decreasing order of how well established they are:

1. **Locality.** The next action is chosen by conditioning on the context. A 100-token thought written immediately before the action puts a *compressed, task-relevant summary of the whole history* adjacent to the decision point, instead of asking the decode to re-derive it from 20k tokens of interleaved observations. This is the same reason "lost in the middle" hurts: position matters, and the thought is a deliberate recency injection.
2. **Factorisation.** `P(action | history)` is a hard conditional. ReAct replaces it with `P(thought | history) · P(action | thought, history)` — two easier ones. Each has a lower error rate than the joint, which is the same argument as chain-of-thought, applied to a decision instead of an answer.
3. **Exception handling.** The paper's specific claim: reasoning traces let the model *update* the plan mid-trajectory. Without a thought slot, a surprising observation has nowhere to be processed; the model's only channel is the action itself, so it tends to repeat the previous action. This is the mechanism behind the repeated-identical-tool-call failure that the no-progress detector catches.
4. **Steerability.** ReAct's own finding: because thoughts are text, a human can edit a couple of them and change downstream behaviour. That is a real operational property — it is how you debug a bad trajectory without retraining anything.

**The cost, derived.** A thought is roughly 60–200 tokens and it is re-sent on every subsequent turn. Over n steps the extra *input* tokens are `thought_len × n(n+1)/2`. At 120 tokens and 10 steps: `120 × 55 = 6,600` extra input tokens per run, on top of the actions and observations. That is the price of the reasoning trace, and it is quadratic, which is why "just make the thoughts longer" is not a strategy.

### Plan-and-Execute

Three components, and the third one is the one people forget:

```
PLANNER   →  ordered list of steps (+ optional dependency DAG)
EXECUTOR  →  runs step i with a SMALL context: [step_i, deps' outputs]
SOLVER    →  synthesises the final answer from plan + all outputs
REPLANNER →  optional edge: after step i, revise the remaining plan
```

The variant worth naming is **ReWOO** (Reasoning WithOut Observation): the planner emits *all* tool calls up front with variable substitution (`#E2` refers to the output of step 2), so the executor is a dumb runtime with no LLM in the loop for orchestration, and only the solver sees the results. Reported savings are **30–50% fewer tokens than ReAct** on equivalent multi-step tasks.

**Where the saving comes from, arithmetic.** Take an 8-step task: system + tool schemas 1,500 tokens, each observation 800, each thought 120, each action 40.

- **ReAct:** turn *k* re-sends everything before it. Input = `8 × 1500 + 960 × (0+1+…+7)` = **38,880 input tokens**, output ≈ 1,280.
- **Plan-Execute:** one planner call (1,500 in, ~300 out), eight executor calls with tiny stateless contexts (~800 in, 40 out each), one solver call carrying the plan plus all eight observations (~7,100 in). Input ≈ **15,000 tokens**, output ≈ 1,020.

**~2.6× cheaper, and the eight executor calls can run in parallel**, which also collapses wall-clock from 8 sequential model round trips to roughly 3. Those are the two real reasons to plan up front: cost and latency, not intelligence.

*(This is a model, not a measurement. Run it on your own token distribution before quoting it.)*

**And here is the bill.** One replan at step 4 means re-planning with four observations in context (≈ +4,700 input tokens) and re-running the tail. **Two replans and Plan-Execute costs more than ReAct would have**, with worse adaptivity. So the pattern is a bet: *I am confident enough in this decomposition to pay a penalty if I'm wrong.* Take that bet when the task shape is known (a monthly report, a fixed 5-source enrichment, a known ETL) and refuse it when it isn't (debugging, exploratory analysis, anything where step 1 might return "no such table").

**Failure mode: plan lock-in.** The observable symptom is precise and worth memorising, because it is what you say when an interviewer asks how you'd detect it: **`plan_hash` is identical across every step, `replan_count == 0`, and the final answer references an entity that a mid-trajectory observation reported as missing.** The executor for step 4 got `Error: relation "user_events_v2" does not exist`, the plan never changed, steps 5–8 aggregated over nothing, and the solver produced a fluent report of zero rows described as a trend. The fix is not "add a replanner" — it is a **gate**: after each step, a cheap deterministic check on whether the observation invalidates any downstream step's precondition, and only then pay for an LLM replan.

### Reflexion, and the honest evidence

Reflexion (Shinn et al., arXiv Mar 2023) has three roles plus one store:

```
ACTOR      → produces a trajectory (typically a ReAct agent)
EVALUATOR  → scores it. unit tests / game engine / EM / heuristic / LLM judge
SELF-REFLECT → turns (trajectory, score) into VERBAL feedback:
               "I searched for X but the entity is disambiguated as X (film);
                next attempt, look up the disambiguation page first."
MEMORY     → episodic buffer of those reflections, injected into attempt k+1
```

The claim is **verbal reinforcement learning**: no gradients, no weight updates; the "policy update" is a paragraph appended to the prompt. The reported numbers:

| Benchmark | Baseline | Reflexion | Verdict source |
|---|---|---|---|
| HumanEval pass@1 | 80% (GPT-4) | **91%** | unit tests |
| ALFWorld | 75% (ReAct) | **130/134 ≈ 97%** in 12 trials | game engine success flag |
| HotpotQA EM (100 sampled Qs) | 61% (CoT) | **75%** | exact match vs ground truth |

**Now look at the third column.** Every headline gain has an external verdict: a test suite, a simulator, a labelled answer. The "self" in self-critique is doing far less work than the name implies — what is actually happening is *retry with a failure explanation in context*, and the explanation is grounded in a signal the model did not generate.

Strip the verdict and the evidence reverses:

- **Huang et al., "Large Language Models Cannot Self-Correct Reasoning Yet" (ICLR 2024).** Intrinsic self-correction — model critiques itself with no external feedback — fails to reliably improve on GSM8K, CommonSenseQA and HotpotQA, and *degrades* performance in places. Their sharpest finding is methodological: several published self-correction gains came from a deliberately weak initial prompt. Strengthen the first prompt and the benefit largely evaporates. If your reflection loop's baseline is a lazy zero-shot prompt, you are measuring prompt quality, not reflection.
- **The FlipFlop effect (arXiv 2311.08596).** Challenge an LLM on a correct answer and it frequently flips to a wrong one. A naive "are you sure? critique your answer" pass is not neutral — it has a **harm rate**, and you must measure it, not just the help rate.
- **Degeneration of thought.** Reflexion's own known failure: the reflection repeats the same flawed diagnosis across attempts. Observable symptom: **cosine similarity between reflection *k* and *k−1* above ~0.9, near-zero diff between successive attempts' outputs, pass rate flat while token spend grows linearly.** Detect it, abort at 2–3 attempts, escalate to a human or a different tool.
- **The information-theoretic version of the argument:** when the generator and the evaluator are the same model with the same training distribution, their errors are correlated, so the evaluator's "this looks right" carries very little evidence about correctness. The critique is only worth its tokens when it is *decorrelated* from the generator — which in practice means a different model, or better, not a model at all.

**So the engineering rule.** Rank your verdict sources and take the cheapest real one:

```
compiler / unit tests / type checker / schema validation / SQL EXPLAIN  ← use these
assertion on a known invariant, checksum, row-count sanity bound
a second, DIFFERENT model as judge (decorrelated errors, some value)
the same model asked "are you sure?"                                   ← ~worthless, measurable harm
```

And instrument the loop with three metrics, not one: **help rate** (wrong → right), **harm rate** (right → wrong), and **cost per net-correct answer**. If harm rate ≥ help rate you have shipped a random-answer-perturber. Practitioner write-ups on evaluating reflection loops in 2026 converge on exactly this: almost nobody measures the harm rate, which is why almost nobody knows whether their reflection loop is working.

### Tree-of-Thought and self-consistency: the price list

**Self-consistency** (Wang et al., 2022): sample k reasoning paths at temperature > 0, take the majority answer. **ToT** (Yao et al., NeurIPS 2023): generate k candidate thoughts per node, score them, expand the promising ones, prune the rest, backtrack when needed. ToT's famous number is Game of 24: **74% with GPT-4 + ToT versus 4% with GPT-4 + CoT** — an 18× improvement, on a task with a perfect cheap verifier (does the arithmetic hit 24) and a tiny branching factor.

The costs:

| Technique | Token multiplier vs single pass | Requires |
|---|---|---|
| Self-consistency, k samples | ~k× (linear, ~20× at k=20) | a comparable-answer extractor |
| ToT, breadth k depth d | 10–100× typical; `O(k^d)` evaluations worst case | a **per-node scorer** |
| Adaptive-consistency | ~k/7.9× (early stop on convergence) | a convergence criterion |

And the 2026 measurements on modern models, which are the numbers that make you sound current:

- Gemini-2.5-Flash-Lite on HotpotQA: **+0.4% accuracy across 20 sampled paths at ~20× the token cost**, and the curve fluctuated rather than rose.
- Gemini-2.5-Pro on MATH-500: **98% single-pass CoT → 99.6% at 15 paths**, i.e. **+1.6% for ~15× the compute**.
- On MATH-500 with Flash-Lite, accuracy **peaked around 10 paths and declined beyond 15**. That is not diminishing returns, it is negative returns: once a model solves most items in one pass, extra samples inject spurious paths the aggregator cannot fully suppress.
- Adaptive-consistency cut sample usage **7.9×** for **<0.1%** accuracy loss; criteria-based early stopping cut it ~**70%** with negligible loss. Both findings say the same thing: there is a threshold beyond which paths are redundant, and that threshold moves down as models get better.

**When ToT still earns its keep.** Three conditions, all required: (a) single-pass accuracy is *demonstrably* well below ceiling on your task, (b) intermediate states are **cheaply and objectively scoreable** — a unit test, arithmetic, a schema, a solver, not an LLM judge — and (c) you actually need the branches, e.g. you are enumerating alternatives for a human to compare (design options, query plans, legal arguments). Miss (b) and you have built an expensive random walk: the scorer is the whole algorithm, and an LLM-judge scorer at every node is both the cost centre and the correlated-error problem again. Replacing the judge with a deterministic checker where the task allows drops per-node cost by roughly an order of magnitude.

---

## The comparison an interviewer wants

| | **ReAct** | **Plan-Execute / ReWOO** | **Reflexion** | **ToT / self-consistency** |
|---|---|---|---|---|
| Decision point | after each observation | before any observation | after a failed attempt | across parallel branches |
| Adapts mid-task | yes, per step | only via replan | between attempts | within one attempt |
| Model round trips | n sequential | 1 + (n parallel) + 1 | n × attempts | k^d-ish |
| Relative token cost | 1.0 (baseline) | **0.4–0.7×** | 2–3× (per extra attempt) | **10–100×** |
| Context growth | quadratic in steps | flat per executor | resets per attempt, + memory | branch-local |
| Hard requirement | good tool descriptions | a **correct decomposition** | a **real verdict** | a **cheap node scorer** |
| Signature failure | repeated identical calls; runaway trace | **plan lock-in** | **degeneration of thought**; harm > help | cost blowup; scorer is the bottleneck |
| Auditability | trace is readable, unstructured | plan is a diffable artifact | reflections are readable | tree is large, hard to read |
| Subsumed by reasoning models? | half of it (the Thought) | partly (native planning) | only the introspection half | **largely, for math/code** |

**Decision rule — say it in this order:**

```
1. Do later steps depend on what earlier steps RETURN?
     YES → ReAct. loop, decide per step. accept the cost.
     NO  → is the decomposition knowable and stable up front?
             YES → Plan-Execute (ReWOO if steps are fully pre-computable).
                   ~2-3x cheaper, parallel, plan is a reviewable artifact.
                   ADD A GATE, not a blanket replanner.
             NO  → back to ReAct. an unstable plan is worse than no plan.

2. Do you have a CHEAP EXTERNAL VERDICT? (tests, compiler, schema, DB error, invariant)
     YES → wrap in a retry-with-critique loop. cap 2-3 attempts.
           track help rate, harm rate, cost per net-correct.
     NO  → do NOT add self-critique. spend the tokens on a better first prompt,
           a better tool, or a real verifier instead.

3. Is single-pass accuracy demonstrably below ceiling AND are intermediate
   states cheaply, objectively scoreable?
     YES → self-consistency k=3-5 first (linear); ToT only if you need the tree.
     NO  → single pass with a reasoning model. this is the common case in 2026.

4. Default for a new agent: ReAct loop, native tool calling, no reflection,
    no ToT. Add exactly one pattern at a time and eval each addition.
```

The composition that actually ships: **Plan-Execute as the outer orchestration, ReAct sub-agents inside each step, one verifier-gated retry at the boundary.** Plan for auditability and cost, loop for adaptivity, retry only where there's a test.

---

## Build it from scratch

`labs/py/03-reasoning-patterns/` builds all four on top of the loop from module 01, against a scripted fake model so tests are deterministic and free:

1. **ReAct 2022** — implement `ACTION_RE`, then a property test that feeds it 30 adversarial action strings (quotes, nested brackets, fences, unicode). Measure your own parse-failure rate. This is the exercise that makes the point.
2. **ReAct 2026** — same task, native tool calling, thinking block preserved in history. Assert the parse-failure rate is exactly 0 and the step count is ≤ the 2022 version.
3. **Ablation** — drop the thinking block from the appended assistant message and re-run. Watch the trajectory degrade toward act-only. This is the paper's ablation, reproduced in ten lines.
4. **Plan-Execute** — planner emitting a step DAG, stateless executors, solver. Instrument token counts and reproduce the ~2.6× input-token saving. Then inject a step-3 failure and watch the plan lock in.
5. **The gate** — add a deterministic precondition check between steps. Prove it catches the injected failure and triggers exactly one replan, and count the cost.
6. **Reflexion** — actor + evaluator (real unit tests, not a judge) + reflection memory, capped at 3 attempts. Then swap the evaluator for "ask the same model if it's sure" and **measure help rate and harm rate on 30 seeded tasks**. This is the most valuable half hour in the lab.
7. **Self-consistency** — k = 1,3,5,10 on a fixed task set; plot accuracy against tokens and find your own plateau.
8. **Degeneration detector** — embed successive reflections, abort when cosine similarity > 0.9.

If you do only one of these, do #6. Being able to say "I measured the harm rate of a reflection loop and it was 8% against an 11% help rate" is worth more in an interview than naming every paper in this module.

---

## How it's done in production

Nobody hand-writes these. What you should be able to say is which primitive maps to which pattern and what the framework's version silently changes.

| Pattern | Production form | What it actually is |
|---|---|---|
| ReAct | LangGraph `create_react_agent` (deprecated in 2026 in favour of `create_agent` in the `langchain` package); OpenAI Agents SDK / Claude Agent SDK default loop | a **tool-calling loop inspired by ReAct**, not the paper's text-parsed version. There is no mandatory `Thought` step; reasoning happens because the model reasons, or because you enabled thinking. Say this out loud in an interview. |
| Plan-Execute | LangGraph plan-and-execute / ReWOO tutorials; Step Functions or Temporal with LLM activities for the durable case | a planner node, a fan-out over executor nodes, a solver node, and optionally a conditional edge back to the planner |
| Reflexion | Anthropic's **evaluator-optimizer** workflow; LangGraph reflection/reflexion tutorials; agentic-RAG "grade then re-retrieve" | generator + critic in a loop with an explicit stop. Anthropic's framing is the honest one: use it "when we have clear evaluation criteria, and when iterative refinement provides measurable value" |
| ToT | LangGraph LATS (language-agent tree search, i.e. MCTS over thoughts) | tree search with an LLM value function. Rarely deployed. Mostly appears in benchmark papers |

**Anthropic's Building Effective Agents is the citation to reach for**, because it says the unfashionable thing plainly: the most successful implementations "weren't using complex frameworks or specialized libraries," you should "find the simplest solution possible, and only increase complexity when needed," and you should add complexity "*only* when it demonstrably improves outcomes." Its three principles map directly onto this module: **simplicity** (don't stack four patterns), **transparency** (show the planning steps — which is exactly the ReAct trace and the Plan-Execute artifact), and **a well-engineered agent-computer interface** (their own SWE-bench work spent more time optimising *tools* than prompts). The practical translation: most of the time, better tool descriptions beat any reasoning pattern you could bolt on.

**What breaks at scale**

| Symptom | Cause | Fix |
|---|---|---|
| `OutputParserException` in 2–8% of turns; agent "retries" for no visible reason | text-parsed ReAct | native tool calling; delete the parser |
| An `Observation:` line in the transcript that has no matching tool-log entry | missing `stop` sequence: model fabricated the observation | structured `tool_result` blocks, or a hard stop sequence |
| Agent stops adapting to surprises; repeats the previous action after a failure | thinking/reasoning block dropped when appending the assistant turn | preserve the reasoning block verbatim in history |
| Final report describes a trend over zero rows | **plan lock-in**: `replan_count == 0`, `plan_hash` constant, downstream steps ran after a failed precondition | deterministic precondition gate between steps; replan only when the gate fires |
| Attempt 3 output byte-identical to attempt 2; tokens up 3×, pass rate flat | **degeneration of thought** | cosine-similarity abort at >0.9; cap attempts at 2–3; escalate |
| Accuracy *dropped* after you shipped the reflection loop | harm rate exceeds help rate; the critique is correlated with the generator | measure both rates; use a real verifier or a different model as judge |
| Reflection loop looked great in the demo, worthless in prod | baseline was a weak zero-shot prompt (Huang et al.'s exact critique) | re-baseline against your *best* single-pass prompt before attributing gains |
| Self-consistency bill 20× with no accuracy change | single-pass accuracy already near ceiling | measure single-pass first; adaptive early stop; reserve for demonstrably hard items |
| ToT costs dominate; quality tracks the scorer, not the tree | LLM-judge at every node | deterministic checker per node where possible; cut breadth before depth |
| Latency doubled after adding thinking to every turn | reasoning budget applied uniformly | budget thinking only on decision-heavy turns; cheap turns get none |

**Instrumentation specific to this module** (module 01 covers the general loop spans): per run, log `pattern`, `plan_hash`, `replan_count`, `attempts`, `verdict_source`, `thought_tokens`, and the reflection-similarity series. Per reflection loop, log the `(pre_verdict, post_verdict)` pair, because that pair *is* the help/harm rate.

---

## Tradeoffs & when NOT to use each

- **Don't use Plan-and-Execute when step 1 can invalidate step 2.** This is the whole ballgame. Exploratory analysis, debugging, incident response, anything against a schema you don't control: the plan is a guess about a world you haven't looked at, and the cost model says two replans and you've lost the saving anyway. Plan-Execute is for tasks whose *shape* you already know.
- **Don't add self-critique without a verdict.** This is the most common wasted quarter in agentic AI. Without an external signal it fails to reliably improve reasoning and measurably harms some cases (Huang et al. ICLR 2024; the FlipFlop effect). If you cannot name the verdict source in one word — "tests", "compiler", "schema", "row count" — you do not have a reflection loop, you have a token multiplier with a nice architecture diagram.
- **Don't reach for ToT or self-consistency in 2026 before measuring single-pass accuracy.** +0.4% for 20× tokens on HotpotQA, and *negative* returns past 15 samples on MATH-500 with a strong model. If the model already solves 90% in one pass, extra paths mostly re-confirm answers you had and occasionally poison ones you didn't.
- **Don't force a `Thought` on every step.** "Always plan before every action" — literal ReAct prompting — is measurably wasteful and *degrades long-horizon performance* (arXiv 2509.03581, Crafter). Cheap mechanical steps don't need deliberation. Reserve reasoning budget for branch points.
- **Don't use ReAct when the steps are fixed.** If it's "fetch → validate → transform → write" every single time, that's a pipeline. You're paying nondeterminism and n round trips for flexibility you don't want. Module 01's rule stands: the most common architectural mistake in this space is using an agent where an `if` statement would do.
- **Don't stack patterns.** ReAct + Reflexion + ToT + a planner is four multiplicative cost centres and four independent failure modes, and you will not be able to attribute a regression to any of them. Add one, eval it, keep it or delete it.
- **Don't cite ToT's Game-of-24 number as general evidence.** 4% → 74% is real and it is on a puzzle with a perfect cheap verifier and a small branching factor. Your production task almost certainly has neither.

---

## Interview questions

### Q1 — What is ReAct?
**Testing:** whether your knowledge has a 2022 timestamp.
**Answer:** Interleaving reasoning traces with actions: Thought, Action, Observation, repeat, so the reasoning can track and update the plan while the actions supply ground truth. Yao et al., arXiv Oct 2022, ICLR 2023; beat imitation and RL baselines by +34% absolute on ALFWorld and +10% on WebShop with one or two in-context examples. It exists because CoT alone hallucinates (ungrounded) and act-only can't synthesise (their act-only ablation had identical observations to ReAct and still failed).
**Follow-up trap:** *"How do you implement it?"* — this is the trap. Native tool calling. The Thought is the model's reasoning block, the Action is a structured `tool_use` block, the Observation is a `tool_result` block keyed by `tool_use_id`. Describing the regex on `Thought:/Action:` is describing 2022, and it deletes an entire class of parse-failure bugs to stop doing it.

### Q2 — Why does adding a reasoning trace improve action selection? Give me a mechanism, not "it thinks more."
**Answer:** Four. **Locality** — the thought puts a compressed task-relevant summary immediately adjacent to the decision point instead of making the decode re-derive it from 20k tokens of history. **Factorisation** — it replaces the hard `P(action | history)` with two easier conditionals, `P(thought | history)` then `P(action | thought, history)`. **Exception handling** — a surprising observation needs somewhere to be processed; without a thought slot the model's only output channel is the action itself, which is why it repeats the previous call. **Steerability** — thoughts are text, so a human can edit two of them and change downstream behaviour, which is how you debug a trajectory.
**Follow-up trap:** *"What does it cost?"* — quadratic input tokens. A 120-token thought re-sent every turn over 10 steps is `120 × 55 = 6,600` extra input tokens. So longer thoughts are not free and "always reason before every action" measurably degrades long-horizon tasks (arXiv 2509.03581).

### Q3 — ReAct or Plan-and-Execute for this task?
**Testing:** whether you have a rule or a vibe.
**Answer:** One question: do later steps depend on what earlier steps return? Yes → ReAct, decide per step. No, and the decomposition is stable → Plan-Execute, because it's roughly 2–3× cheaper in input tokens, the executors parallelise so wall-clock collapses, and the plan is a diffable artifact a human can review before anything executes. Those three — cost, latency, auditability — are the real reasons to plan. Not intelligence.
**Follow-up trap:** *"Quantify the saving."* — 8-step task, 1,500-token system prompt, 800-token observations: ReAct re-sends everything each turn, so ~39k input tokens; Plan-Execute is one planner call plus eight small stateless executor calls plus one solver call carrying the observations, so ~15k. Then volunteer the bill: one replan costs ~4,700 tokens plus re-running the tail, and **two replans and Plan-Execute is more expensive than ReAct** with worse adaptivity.

### Q4 — Your Plan-Execute agent produced a beautiful report describing a trend that doesn't exist. Debug it.
**Testing:** the named failure mode.
**Answer:** Plan lock-in. Check three things in the trace: `plan_hash` constant across all steps, `replan_count == 0`, and whether any mid-trajectory observation invalidated a downstream precondition. The classic shape is step 3 returning `relation "user_events_v2" does not exist`, the plan never changing, steps 4–8 aggregating over an empty set, and the solver fluently describing zero rows as a trend.
**Follow-up trap:** *"So add a replanner?"* — no, that's the expensive reflex. Add a **deterministic gate**: after each step, a cheap non-LLM check on whether the observation invalidates any downstream step's precondition, and pay for an LLM replan only when the gate fires. A blanket replan-after-every-step is just ReAct with extra latency and a worse name.

### Q5 — Does Reflexion work?
**Testing:** whether you can hold a real counter-argument.
**Answer:** Yes when there's an external verdict, no when there isn't, and the paper's own numbers show it. 91% pass@1 on HumanEval versus GPT-4's 80% — verdict was unit tests. 130 of 134 ALFWorld tasks, ~97%, versus ReAct's 75% — verdict was the game engine's success flag. HotpotQA 61% → 75% EM — verdict was exact match against ground truth. Every headline gain is verifier-backed. So what Reflexion actually is, mechanically, is *retry with a grounded failure explanation in context*. Strip the verdict and Huang et al. (ICLR 2024) show intrinsic self-correction fails to reliably improve GSM8K, CommonSenseQA and HotpotQA and sometimes degrades them.
**Follow-up trap:** *"Then why do so many blog posts report gains?"* — Huang et al.'s sharpest finding: a lot of reported self-correction benefit is an artifact of a weak *initial* prompt. Strengthen the first prompt and the gain largely evaporates. If your reflection loop's baseline is a lazy zero-shot prompt, you measured prompt quality and attributed it to reflection.

### Q6 — How would you prove your reflection loop is worth keeping?
**Answer:** Three metrics, not one. **Help rate** (wrong → right), **harm rate** (right → wrong), and **cost per net-correct answer**. Log the `(pre_verdict, post_verdict)` pair on every invocation; that pair is the whole measurement. If harm ≥ help you've shipped a random-answer-perturber, and you'd never know from an accuracy-only dashboard because the two effects partly cancel. Almost nobody measures the harm rate, which is why almost nobody knows if their loop works.
**Follow-up trap:** *"Why would critique ever make it worse?"* — sycophancy. The FlipFlop result: challenge a model on a correct answer and it frequently flips to a wrong one. "Are you sure?" is not a neutral operation. Plus the information-theoretic version: generator and evaluator are the same model with correlated error modes, so the evaluator's "looks right" is weak evidence. That's the argument for a *different* model as judge, or better, a non-model verifier.

### Q7 — What's the cheapest verdict source you can get, and how do you rank them?
**Answer:** Cheapest real one wins, in this order: compiler / unit tests / type checker / schema validation / `EXPLAIN` on the SQL; then assertions on known invariants, checksums, row-count sanity bounds; then a second, *different* model as judge, which has some value because its errors are decorrelated; and last, the same model asked "are you sure?", which is roughly worthless and has measurable harm. The engineering move is almost always to *build the verifier* rather than to add another critique pass. A tool that returns `Error: column not found, available: [...]` gives the model a better signal than any self-reflection would.
**Follow-up trap:** *"What if nothing verifiable exists — open-ended writing, say?"* — then you don't have a reflection loop, you have an evaluator-optimizer with a human in it. Anthropic's own framing: use it when there are clear evaluation criteria and when a human articulating feedback demonstrably improves the output. Otherwise spend the tokens on the first prompt.

### Q8 — When is Tree-of-Thought worth it?
**Answer:** Three conditions, all required. Single-pass accuracy demonstrably well below ceiling on your task; intermediate states cheaply and *objectively* scoreable; and you genuinely need the branches, e.g. enumerating alternatives a human will compare. Game of 24 hits all three: 74% with GPT-4 + ToT versus 4% with CoT, a perfect arithmetic verifier, and a tiny branching factor. Cost is 10–100× tokens, `O(k^d)` evaluations worst case.
**Follow-up trap:** *"Would you use it on our task?"* — probably not, and say why: if the node scorer is an LLM judge, the scorer *is* the algorithm and you're back to correlated errors, paying 100× for a random walk. Replace the judge with a deterministic checker where the task allows — that drops per-node cost by about an order of magnitude — and cut breadth before depth. Also: modern reasoning models do this search internally, so on math and code the external tree usually doesn't beat native extended thinking.

### Q9 — Self-consistency: k = 20 or k = 1?
**Answer:** Measure single-pass accuracy first, then almost certainly a small k or 1. Current numbers on modern models: Gemini-2.5-Flash-Lite on HotpotQA gained **0.4% across 20 samples at ~20× the tokens**; Gemini-2.5-Pro on MATH-500 went 98% → 99.6% at 15 paths, **+1.6% for ~15×**. Worse, Flash-Lite on MATH-500 *peaked around 10 paths and declined past 15*. That's negative returns: once a model solves most items in one pass, extra samples mostly re-confirm and occasionally inject a spurious path the aggregator can't suppress.
**Follow-up trap:** *"So it's dead?"* — no, it's narrowed. It works where single-pass reliability is genuinely low, which means you need difficulty-aware routing rather than a blanket k. And use early stopping: adaptive-consistency cut sample usage 7.9× for under 0.1% accuracy loss; criteria-based stopping cut ~70%. Both say the same thing — the useful threshold is per-item, and it's dropping as models improve.

### Q10 — Reasoning models do internal deliberation. Which of these patterns are now obsolete?
**Testing:** the current-boundary question. This is the staff-level differentiator in this module.
**Answer:** Draw the line at "does it touch the world." **Absorbed by the model:** single-turn deliberation, branching over candidate solutions, verifying arithmetic and logic within one answer, short self-correction inside one response. External ToT and self-consistency mostly no longer beat native extended thinking on math and code. **Not absorbed, still yours:** anything with a side effect (a tool call producing a real observation), anything needing durable state across a boundary (approval that takes a day), any *real* verifier (a test suite is not a thought), and all the control machinery — budgets, stop conditions, dispatch, context management. So reasoning models ate the *Thought* half of ReAct and left the *Act/Observe* half untouched. The scaffolding that died is the scaffolding that simulated deliberation in text.
**Follow-up trap:** *"So you'd delete your agent framework?"* — no, you'd delete the reasoning scaffolding and keep the orchestration. The framework's value was never the cognitive loop, it was persistence, tool dispatch, human-in-the-loop and observability. What changes is you stop writing prompt templates that force a thought and start setting a thinking budget per turn — high on decision points, zero on mechanical steps.

### Q11 — LangGraph's `create_react_agent` — is that the ReAct paper?
**Testing:** whether you read the source or the name.
**Answer:** No. It's a tool-calling loop inspired by ReAct: model call, if the response has `tool_calls` run the tool node, append `ToolMessage`s, repeat until no tool calls. There is no mandatory `Thought` step and no text parsing. Reasoning happens because the model reasons or because you enabled thinking, not because the harness demands it. As of 2026 it's deprecated in favour of `create_agent` in the `langchain` package with a middleware system.
**Follow-up trap:** *"Does the naming matter?"* — yes, twice. People conclude they've implemented the paper and then can't explain why the ablation-degraded behaviour shows up when their history-trimming drops reasoning blocks. And "we use ReAct because LangGraph gave us `create_react_agent`" is not a design decision, it's a default. State which pattern you chose and why.

### Q12 — Your agent's success rate dropped after you added a reflection step. Walk me through the investigation.
**Answer:** Order of operations. (1) Split the metric: help rate versus harm rate on the same eval set. A flat aggregate hides a 15%/17% split. (2) Check the verdict source. If it's the same model judging itself, errors are correlated and the critique carries almost no information — that alone explains it. (3) Check for degeneration: embed successive reflections, look for cosine similarity above ~0.9 and near-identical successive outputs while tokens grow linearly. (4) Re-baseline. If the pre-reflection prompt was weak, you may be comparing against a strawman in *both* directions. (5) Check sycophancy specifically: how many flips were on items answered correctly first time.
**Follow-up trap:** *"What's the fix?"* — usually delete it, and spend the budget on a real verifier or a better tool instead. If you must keep it, gate it: only fire the loop when the verdict says fail, cap at 2–3 attempts, and never let a passing first attempt be re-litigated. The loop should be unreachable on success.

### Q13 — Design the reasoning architecture for a production data-analysis agent: 20 tables, users ask ad-hoc questions, some need 6–8 queries.
**Answer:** ReAct at the core, because query *k+1* genuinely depends on what query *k* returned — you don't know the join cardinality or whether a column is null-heavy until you look. Native tool calling with a typed `run_sql` tool. The verifier is free and I'd lean on it hard: `EXPLAIN` before execute, plus a row-count sanity bound, plus schema validation — so a verifier-gated single retry on SQL errors, where the error text goes back as the observation. No reflection loop on the *analysis* (no verdict exists for "is this the right insight"), no ToT, no up-front plan because the decomposition isn't knowable. Thinking budget high on the "which table next" turns, zero on the formatting turn. Cap steps at 10 with a cost budget.
**Follow-up trap:** *"Now it's a scheduled nightly report over the same 5 tables."* — the answer inverts. Fixed decomposition, so Plan-Execute or ReWOO: the plan is a reviewable artifact, the queries parallelise, and it's ~2–3× cheaper. Honestly, at that point most of it should be a SQL file in version control with the LLM only writing the narrative. The pattern follows the task's stability, not the team's preference.

### Q14 — How do you eval a reasoning pattern change without shipping it?
**Answer:** Separate the deterministic from the stochastic. The pattern's *machinery* — plan parsing, gate logic, replan trigger, attempt cap, degeneration detector — is deterministic and gets ordinary unit tests against a scripted fake model. Then a golden set of 30–100 tasks with **trajectory** assertions, not just outcome: did it replan when the gate fired, did it stop at the attempt cap, did it avoid re-litigating a passing result. Report a distribution over N runs, not a single pass/fail, and always report tokens and wall-clock alongside accuracy, because most pattern changes are cost regressions dressed as quality wins.
**Follow-up trap:** *"What's your acceptance bar?"* — accuracy improvement that survives the token cost. Concretely: cost per net-correct answer must go down, or accuracy must go up by more than the run-to-run standard deviation across at least 5 repeats. "It felt better in the demo" is how the reflection loop got shipped in the first place.

### Q15 — I've given you a task with a step budget of 6 and one where later steps clearly depend on earlier ones, but the reasoning traces are blowing your context. What do you do?
**Answer:** Keep ReAct (the dependency is real, a plan would be a guess) and attack the trace, not the pattern. Three moves in order: truncate observations *at the tool boundary* so the 40KB JSON becomes 2KB plus a pointer — that's the highest-leverage fix and it isn't about reasoning at all; drop or summarise *old* thoughts while keeping the recent ones verbatim, since a thought's value is overwhelmingly local to its decision point, unlike observations which stay factually relevant; and set the thinking budget per turn rather than globally, so mechanical turns get none.
**Follow-up trap:** *"Is it safe to drop old reasoning?"* — mostly yes and this is the asymmetry worth naming: thoughts are locally useful, facts are globally useful, so compact thoughts before facts. Two cautions. Never drop the *current* turn's reasoning block, because with some providers that breaks the signature and with all of them it degrades you toward act-only. And never drop a thought that recorded a *decision or an open obligation* — promote those into an explicit open-items list that survives compaction.

### Q16 — Rank these four patterns by how much of them survived reasoning models, and defend the ordering.
**Testing:** whether you can reason about the trend rather than recite it.
**Answer:** Most-eroded first. **ToT and self-consistency** — largely subsumed for math and code; the internal search is hard to beat externally, and the measured external gains are now sub-2% at 15–20× cost. **Reflexion** — split in two: the introspection half is absorbed (models self-check inside one response), the verifier-driven retry half is untouched and never will be absorbed, because a compiler is not a thought. **Plan-and-Execute** — partly absorbed, in that models plan natively without being prompted to, but the *artifact* survives for reasons that have nothing to do with capability: cost, parallelism, and a human reviewing the plan before anything executes. **ReAct** — least eroded, because the Act/Observe half is a statement about the world, not about the model. Half of it moved inside; the half that matters didn't.
**Follow-up trap:** *"What's your confidence on each?"* — high on ToT/self-consistency (there are measurements). Medium on Plan-Execute (the adaptive-planning literature says always-plan hurts long-horizon, but the cost and auditability arguments are orthogonal to model capability, so it survives regardless). Speculative on reflection ever fully internalising — I'd bet against it, because the boundary isn't capability, it's that some verdicts live outside the model by definition.

---

## Red flags that fail you

- Describing ReAct as regex-parsing `Thought:/Action:/Observation:` in 2026.
- Calling ReAct, Plan-Execute, Reflexion and ToT "frameworks" and not being able to state the one axis that separates them (where the decision point sits relative to the observations).
- Claiming Reflexion improves accuracy without mentioning that every headline number in the paper had an external verdict.
- Recommending a self-critique loop with no answer to "what's the verdict source?"
- Not knowing the harm rate exists. Reporting only "it improved accuracy."
- Quoting Game of 24 (4% → 74%) as general evidence for ToT, without the caveats: perfect cheap verifier, tiny branching factor, 10–100× tokens.
- Reaching for self-consistency k=20 in 2026 without having measured single-pass accuracy.
- Dropping the model's reasoning block when appending the assistant turn, then being surprised the agent stopped adapting.
- Adding a blanket replanner instead of a deterministic precondition gate.
- Stacking three patterns at once and having no way to attribute a regression.
- Saying "we use ReAct" when what you mean is "LangGraph's prebuilt was called `create_react_agent`."
- No opinion on which of these reasoning models made obsolete.

## Cheat card

```
THE AXIS: where is the decision point vs the observations?
  ReAct        decide AFTER each obs   · adaptive · quadratic ctx · n round trips
  Plan-Execute decide BEFORE any obs   · 0.4-0.7x tokens · parallel · plan lock-in
  Reflexion    decide AGAIN after fail · needs a REAL verdict · cap 2-3 attempts
  ToT/self-cons decide ACROSS branches · 10-100x tokens · needs a node scorer

REACT 2026 = thinking block + tool_use block + tool_result block
  NOT regex on "Thought:/Action:". parse-failure rate 2-8% -> 0.
  KEEP the reasoning block in history, else you re-implement act-only (the ablation).
  cost of the trace: thought_len x n(n+1)/2 input tokens. 120 tok x 10 steps = 6,600.

PAPER NUMBERS (know cold)
  ReAct (Yao 2022/ICLR23): +34% abs ALFWorld, +10% WebShop, 1-2 shot
  Reflexion (Shinn 2023):  91% pass@1 HumanEval (GPT-4: 80%) <- verdict = unit tests
                           130/134 ALFWorld ~97% in 12 trials (ReAct 75%)
                           HotpotQA 61% -> 75% EM
  ToT (Yao 2023):          Game of 24: 74% vs CoT 4%. cheap verifier + tiny branching.
  Huang ICLR24:            INTRINSIC self-correct doesn't reliably improve, sometimes
                           degrades. many reported gains = weak initial prompt.
  Self-consistency 2026:   Gemini-2.5-Flash-Lite HotpotQA +0.4% @ 20 samples (20x cost)
                           Gemini-2.5-Pro MATH-500 98 -> 99.6% @ 15x
                           DECLINES past 15 samples. negative, not just diminishing.
  Adaptive-consistency:    7.9x fewer samples, <0.1% accuracy loss
  ReWOO:                   30-50% fewer tokens than ReAct
  arXiv 2509.03581:        ALWAYS planning degrades long-horizon; never planning limits

DECISION RULE
  later steps depend on earlier RESULTS?  yes -> ReAct
    no + decomposition stable up front?   yes -> Plan-Execute/ReWOO + a GATE
  cheap external verdict exists?          yes -> retry-with-critique, cap 2-3
                                          no  -> DO NOT add self-critique
  single-pass acc well below ceiling AND nodes cheaply scoreable? -> self-cons k=3-5
  default: plain ReAct loop. add one pattern at a time, eval each.

VERDICT SOURCES, best to worst
  compiler/tests/typecheck/schema/EXPLAIN > invariants+row-count bounds
  > a DIFFERENT model as judge > same model "are you sure?" (~worthless, harmful)

MEASURE THE LOOP: help rate (wrong->right) · harm rate (right->wrong)
  · cost per NET-CORRECT.  harm >= help = random-answer-perturber.

FAILURE SYMPTOMS
  plan lock-in:  plan_hash constant, replan_count==0, answer cites a missing entity
  degeneration:  cos(reflect_k, reflect_k-1) > 0.9, flat pass rate, linear tokens
  act-only drift: reasoning block dropped from history; repeats prior action
  fabricated obs: Observation: line with no matching tool log (2022 impl, no stop seq)

REASONING MODELS: absorbed the THOUGHT half. not the ACT/OBSERVE half.
  gone:  external ToT, self-consistency (math/code), introspection-only critique
  yours: side effects, real verifiers, durable state, budgets, stop conditions
```

## Sources

- [ReAct: Synergizing Reasoning and Acting in Language Models](https://arxiv.org/abs/2210.03629) — Yao et al., arXiv Oct 2022 / ICLR 2023; +34% ALFWorld, +10% WebShop, and the act-only / reason-only ablations; accessed 2026-07-26
- [ReAct project page](https://react-lm.github.io/) — the CoT-hallucinates vs act-only-can't-synthesise framing, and the thought-editing steerability claim; accessed 2026-07-26
- [Reflexion: Language Agents with Verbal Reinforcement Learning](https://arxiv.org/abs/2303.11366) — Shinn et al., 2023; 91% pass@1 HumanEval vs GPT-4's 80%; accessed 2026-07-26
- [Anthropic — Building Effective Agents](https://www.anthropic.com/engineering/building-effective-agents) — evaluator-optimizer pattern, "only increase complexity when needed", and the ACI/tool-engineering point; accessed 2026-07-26
- [Large Language Models Cannot Self-Correct Reasoning Yet](https://openreview.net/pdf?id=IkmD3fKBPQ) — Huang et al., ICLR 2024; intrinsic self-correction, and the weak-initial-prompt artifact; accessed 2026-07-26
- [Tree of Thoughts: Deliberate Problem Solving with LLMs](https://arxiv.org/abs/2305.10601) — Yao et al., NeurIPS 2023; Game of 24 74% vs 4%; accessed 2026-07-26
- [Self-Consistency Is Losing Its Edge: Diminishing Returns and Rising Costs in Modern LLMs](https://arxiv.org/abs/2511.00751) — Gemini 2.5 numbers, the decline past 15 samples, and the adaptive-consistency 7.9× figure; accessed 2026-07-26
- [Learning When to Plan: Efficiently Allocating Test-Time Compute for LLM Agents](https://arxiv.org/abs/2509.03581) — always-planning degrades long-horizon performance; accessed 2026-07-26
- [Are You Sure? Challenging LLMs Leads to Performance Drops in the FlipFlop Experiment](https://arxiv.org/abs/2311.08596) — the harm rate of naive challenge-and-revise; accessed 2026-07-26
- [Self-consistency Improves Chain of Thought Reasoning in Language Models](https://arxiv.org/abs/2203.11171) — Wang et al., 2022, the origin of majority-vote sampling; accessed 2026-07-26
- [LangGraph `create_react_agent` reference](https://reference.langchain.com/python/langgraph.prebuilt/chat_agent_executor/create_react_agent) — it is a tool-calling loop, and it is deprecated in favour of `create_agent`; accessed 2026-07-26
- [Agentic Reasoning Patterns (2026): ReAct, Reflexion, Plan-Execute & ToT Compared](https://servicesground.com/blog/agentic-reasoning-patterns/) — ReWOO's 30–50% token reduction and the pattern-composition survey; accessed 2026-07-26
- [10 Essential Agentic AI Interview Questions for AI Engineers](https://www.kdnuggets.com/10-essential-agentic-ai-interview-questions-for-ai-engineers) — reported question shapes: "describe the main architectural patterns", "compare different planning approaches"; accessed 2026-07-26
- [Evaluating LLM Self-Reflection Loops: The 3 Metrics That Matter](https://futureagi.com/blog/evaluating-llm-self-reflection-loops-2026/) — the help/harm/cost framing and the observation that reflection loops are rarely evaluated on real traffic; accessed 2026-07-26

## Changelog
- 2026-07-26 — created
