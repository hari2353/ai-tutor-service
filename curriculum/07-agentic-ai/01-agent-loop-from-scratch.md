# The Agent Loop From Scratch (no framework)

> **Track:** T07 Agentic AI · **Time:** 3h · **Prereqs:** none · **Updated:** 2026-07-26
> **Module id:** `T07-agent-loop-from-scratch` · **Tags:** sprint (W1), core, loop
> **Lab:** labs/py/02-agent-loop/

## The 30-second version

An agent is a loop around a stateless model. Each turn you send the full conversation plus tool schemas, the model returns either a final answer or a tool call, you execute the tool, append the result to the message list, and loop. That's the whole mechanism — perceive, decide, act, observe, repeat. Everything that makes agents *hard* is not the loop, it's the four controls wrapped around it: a **stop condition** so it terminates, a **budget** on steps and tokens and dollars so it can't run away, **context management** so turn 40 still fits in the window, and **error handling** so a failing tool becomes an observation the model can route around instead of an exception that kills the run. Frameworks give you those four things plus persistence. They do not give you the loop; the loop is about forty lines.

## Why this gets asked

Because the single fastest way to tell whether someone has actually shipped an agent or has only used one is to ask them to write the loop. People who have only used LangChain describe an abstraction. People who have shipped talk immediately about step caps, retry semantics, and what happens when the tool result is 200KB of JSON. The interviewer is also probing for the failure they've personally lived through: an agent that looped 400 times overnight and burned a five-figure API bill, or one that silently returned a confident wrong answer because a tool threw and the exception was swallowed.

---

## Lineage: past → present → future

**What came before.** Pre-2022, "agent" meant symbolic planners — STRIPS, PDDL, BDI architectures — where the world was a formal state space and the agent searched it. These worked beautifully in closed domains and fell apart everywhere else, because writing down the state space is the actual problem. The first LLM-era attempt was chain-of-thought prompting: get the model to reason in text before answering. That improved reasoning but the model still couldn't *act* — it had no way to touch the world. **ReAct** (Yao et al., 2022) is the paper that joined the two, interleaving reasoning traces with actions so the model could think, act, observe what happened, and think again. Then AutoGPT (early 2023) demonstrated the autonomous loop to a mass audience and simultaneously demonstrated why it doesn't work unsupervised: no budget, no stop condition, no context management, so it looped forever, rediscovered the same dead end repeatedly, and produced impressive demos that never survived contact with a real task.

**Where it stands now.** Two things settled. First, **native tool calling replaced prompt parsing.** ReAct originally required the model to emit `Action: search[query]` as text that you regex out; every major provider now returns structured tool calls as first-class API objects, which removes an entire category of parsing bugs. If you describe ReAct in an interview as "parse the Thought/Action/Observation text", you're describing 2022. Second, the field converged on **short, supervised, bounded loops over long autonomous ones.** The reliability arithmetic is brutal and worth memorising: at 95% per-step success, a 10-step agent completes ~60% of the time; at 85%, ~20%. Nobody ships a 50-step autonomous agent, because 0.95^50 is 8%. What ships is 3–10 step loops with human approval at the consequential moments, plus checkpointing so a failure resumes rather than restarts. The live disagreement is over **how much structure to impose**: the graph camp (LangGraph) argues you should declare the state machine explicitly so it's inspectable and resumable; the loop camp (Anthropic's own guidance, OpenAI's Agents SDK) argues you should give a capable model good tools and get out of its way, because hand-drawn graphs encode assumptions the model would have handled better. Both are defensible and the honest answer is that it depends on whether your failure modes are known in advance.

**Where it's heading.** Three directions with different confidence levels. **Durable execution is winning** — the insight that agent state belongs in a database rather than a process is now consensus (LangGraph checkpointers, Temporal, Restate), and this is settled enough to build on. **Context engineering is becoming the primary skill** — as loops lengthen, what you keep, compact, and discard between turns dominates quality far more than prompt wording; Anthropic's published evals show context editing alone giving a 29% lift and cutting token use 84% over a 100-turn task. **Multi-agent is unsettled and probably over-applied** — the current enthusiasm for swarms of specialists is running ahead of the evidence, and the honest position is that a single agent with good tools beats a poorly-decomposed multi-agent system almost always. Treat confident claims about agent topologies as fashion until someone shows you an eval.

---

## Mental model

```
   ┌──────────────────────── the loop (yours, ~40 lines) ───────────────────────┐
   │                                                                            │
   │   messages[]  ──────▶  MODEL  ──────▶  response                            │
   │       ▲                (stateless)         │                               │
   │       │                                    ├── text only ──▶ DONE          │
   │       │                                    │                               │
   │       │                                    └── tool_calls ──┐              │
   │       │                                                     ▼              │
   │       │                                          execute each tool         │
   │       │                                                     │              │
   │       └──── append(assistant msg) ──── append(tool results) ─┘              │
   │                                                                            │
   └────────────────────────────────────────────────────────────────────────────┘
              guarded by:  STOP CONDITION · BUDGET · CONTEXT MGMT · ERROR POLICY
```

The one thing to internalise: **the model has no memory.** It is a pure function of the messages you send. There is no session, no state, no "the agent remembers". Every turn you rebuild the entire context and pay for all of it. Once that lands, most agent design questions answer themselves — memory is something *you* implement, context growth is *your* problem, and "the agent forgot" always means you dropped something.

---

## How it actually works

### The minimum viable loop

```python
def run(task: str, tools: dict, max_steps: int = 10) -> str:
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": task},
    ]
    for step in range(max_steps):
        resp = client.messages.create(
            model=MODEL, max_tokens=2048,
            tools=[t.schema for t in tools.values()],
            messages=messages,
        )
        messages.append({"role": "assistant", "content": resp.content})

        calls = [b for b in resp.content if b.type == "tool_use"]
        if not calls:                                  # no tool call = finished
            return text_of(resp)

        results = []
        for c in calls:
            results.append({
                "type": "tool_result",
                "tool_use_id": c.id,
                "content": execute(tools, c.name, c.input),   # never raises
            })
        messages.append({"role": "user", "content": results})

    return "Step budget exhausted without a final answer."
```

That is a working agent. Everything below is the difference between that and something you'd put in front of a customer.

### Control 1 — stop conditions

You need **all** of these, not one:

| Stop | Why | Typical |
|---|---|---|
| Model returns no tool call | The natural exit — the model decided it's done | — |
| Step cap | Hard ceiling on iterations | 10–25 |
| Token budget | Cost ceiling; catches loops that grow context fast | task-dependent |
| Wall-clock deadline | User-facing latency ceiling | 30–120s |
| No-progress detector | Catches the model repeating itself | 3 identical calls |
| Explicit `done` tool | Lets the model signal completion with structured output | optional |

The no-progress detector is the one people miss and it catches the most common real failure: the model calls `search("X")`, gets nothing useful, and calls `search("X")` again. Hash `(tool_name, args)` and abort or intervene after N repeats.

```python
seen = collections.Counter()
key = (c.name, json.dumps(c.input, sort_keys=True))
seen[key] += 1
if seen[key] >= 3:
    result = "You have called this exact tool with these exact arguments 3 times. " \
             "It will not produce a different result. Try a different approach or " \
             "explain why you cannot proceed."
```

Note that the intervention is a *tool result*, not an exception. You're steering the model, not killing the run.

### Control 2 — budgets

Track and enforce three separately, because they fail differently:

```python
@dataclass
class Budget:
    max_steps: int = 10
    max_tokens: int = 100_000
    max_usd: float = 0.50
    deadline: float = field(default_factory=lambda: time.monotonic() + 60)

    steps: int = 0
    tokens: int = 0
    usd: float = 0.0

    def check(self) -> str | None:
        if self.steps >= self.max_steps:          return "step budget"
        if self.tokens >= self.max_tokens:        return "token budget"
        if self.usd >= self.max_usd:              return "cost budget"
        if time.monotonic() >= self.deadline:     return "deadline"
        return None
```

Cost is the one that gets skipped and the one that generates the incident. A loop with a 25-step cap and a tool that returns 50KB per call can cost dollars per run, and at production volume that is a budget conversation you have after the fact rather than before.

### Control 3 — context management

Message history grows monotonically and each turn re-sends all of it. Costs are quadratic in turns; quality degrades before you hit the hard context limit, because relevant content gets buried ("lost in the middle").

Three levers, in the order you should reach for them:

1. **Truncate tool results at the boundary.** A tool that returns 200KB should return the useful 2KB, with a pointer. This is the highest-leverage fix and it belongs in the tool, not the loop.
2. **Compact.** When context crosses a threshold (say 70% of the window), summarise the older turns into a dense recap and keep the recent ones verbatim. Preserve: the original task, decisions made, facts discovered, and what's still open. Discard: verbose intermediate tool output, superseded reasoning.
3. **Externalise.** Write findings to a scratchpad file or store and let the model re-read on demand. State that survives compaction is strictly better than state that must fit in the window.

```python
if budget.tokens > 0.7 * CONTEXT_WINDOW:
    keep = messages[-6:]                       # recent turns verbatim
    recap = summarise(messages[1:-6])          # a separate, cheap model call
    messages = [messages[0],
                {"role": "user", "content": f"<progress_so_far>{recap}</progress_so_far>"},
                *keep]
```

The trap: compaction can drop the thing you needed. Never compact the original task, and never compact away a pending obligation. Keeping an explicit "open items" list that you carry across every compaction is the standard mitigation.

### Control 4 — error handling

**A failing tool is data, not an exception.** This is the single most important design decision in the loop.

```python
def execute(tools, name, args) -> str:
    if name not in tools:
        return f"Error: no tool named '{name}'. Available: {', '.join(tools)}"
    try:
        validated = tools[name].validate(args)      # pydantic or jsonschema
    except ValidationError as e:
        return f"Error: invalid arguments — {e}. Expected schema: {tools[name].schema}"
    try:
        return truncate(tools[name].run(**validated), limit=2000)
    except Exception as e:                          # deliberately broad
        return f"Error: tool failed — {type(e).__name__}: {e}"
```

Every path returns a string the model can read and react to. If you let the exception propagate, a transient 503 on a search tool kills a run that had already done nine steps of good work. If you return it as an observation, the model tries a different tool or tells the user honestly.

The counter-consideration: don't swallow *your own* bugs. Distinguish "the tool's dependency failed" (return to model) from "the loop has a programming error" (crash loudly, because a model cannot fix your `KeyError`).

---

## Build it from scratch

The lab at `(lab pending)` builds this incrementally against a fake model, so the tests are deterministic and free:

1. Bare loop with a scripted model — proves the message-passing shape.
2. Add tool dispatch, schema validation, and error-as-observation.
3. Add all six stop conditions, including the no-progress detector.
4. Add the three budgets with a fake clock.
5. Add compaction and prove the original task survives it.
6. Swap the fake model for Ollama and run it for real.

Do it before you touch LangGraph. Once you've built the loop, LangGraph stops looking like magic and starts looking like a persistence layer plus a state machine — which is exactly what it is, and exactly how you should describe it in an interview.

---

## How it's done in production

Nobody hand-rolls the loop at scale, and that's fine — but you should be able to say precisely what the framework buys you:

| Framework gives you | Why it matters |
|---|---|
| **Persistence / checkpointing** | The real reason to adopt one. At 10 steps × 85% reliability, ~80% of runs fail somewhere. Resume-from-checkpoint converts that from "start over" to "continue". |
| Streaming | Token and step streaming to a UI, which you'd otherwise plumb yourself |
| Human-in-the-loop | `interrupt()` and resume — genuinely fiddly to build correctly |
| Observability hooks | Spans per step and per tool call, cost attribution |
| Retry/durability semantics | Per-node retry policies, exactly-once side effects |
| Composition | Subgraphs, fan-out/fan-in, subagents with isolated context |

**Framework map** (see `T07-framework-matrix` for the full comparison): LangGraph when you need durable, inspectable, resumable state machines; OpenAI Agents SDK or Claude Agent SDK when you want a good loop with minimal ceremony; CrewAI/AutoGen for role-play-style multi-agent prototyping; raw when the loop is simple and you'd rather own it.

**What breaks at scale**

| Symptom | Cause | Fix |
|---|---|---|
| Runs cost 10× the estimate | Context growth — every turn resends everything | Truncate tool results at source; compact |
| Agent "forgets" the task at turn 30 | Compaction dropped the original instruction | Never compact `messages[0]` or the task statement |
| Same tool called repeatedly | No no-progress detector | Hash `(name, args)`, intervene at N |
| Overnight run, five-figure bill | No cost budget or deadline | Enforce all four budgets; alert on p99 steps |
| One transient 503 kills a 9-step run | Exception propagated instead of becoming an observation | Return errors as tool results |
| Duplicate side effects after a retry | Non-idempotent tool retried | Idempotency keys on every mutating tool |
| Works in dev, wanders in prod | Dev tasks were short; prod tasks are long | Test at realistic step counts, not 3-step demos |

**Observability is not optional.** Emit one span per step and per tool call, with tokens, cost, latency, and outcome. Without it, "the agent gave a bad answer" is unfalsifiable. With it, you can see that step 4's search returned nothing and everything after was confabulation.

---

## Tradeoffs & when NOT to use an agent loop

- **If the workflow is deterministic, write the workflow.** A fixed pipeline of "extract → classify → route" does not need an agent. You're paying latency, cost, and nondeterminism for flexibility you don't need. The most common architectural mistake in this space is using an agent where a chain — or an `if` statement — would do.
- **If one prompt does it, use one prompt.** Agents earn their cost only when the number and order of steps genuinely can't be known in advance.
- **If the task is long-running or multi-party, use a durable workflow engine.** Temporal or Step Functions with LLM calls as activities beats an in-process loop once you need retries across hours, human approval over days, or exactly-once side effects.
- **The autonomy dial has a cost curve.** More steps means more capability and worse reliability, monotonically. Choose the point deliberately, and be able to justify it with the 0.95^n arithmetic.

---

## Interview questions

### Q1 — Write me an agent loop.
**Testing:** whether you've built one or only used one.
**Answer:** The forty lines above. Narrate as you go: messages list, model call with tool schemas, append the assistant message, check for tool calls, no tool call means done, execute tools, append results as a user message, loop with a step cap.
**Follow-up trap:** *"What's missing?"* — say it before they ask: budgets, no-progress detection, context compaction, errors-as-observations, and persistence. Volunteering the gaps is the strongest move available in this question.

### Q2 — The model has no memory. What follows from that?
**Answer:** Everything. Each turn is a pure function of the messages you send, so memory is something you implement, context growth is your cost problem, and cost is quadratic in turns because you re-send the whole history every time. "The agent forgot" always means the harness dropped something.
**Follow-up trap:** *"So how does a multi-turn chat product work then?"* — the server stores the transcript and replays it. The statelessness is at the model boundary, not the product boundary. People who miss this build "memory" features that are really just transcript storage, and then can't explain why cost grows the way it does.

### Q3 — How do you stop an agent looping forever?
**Answer:** Six mechanisms, not one: natural termination when the model returns no tool call; a step cap; a token budget; a cost budget; a wall-clock deadline; and a no-progress detector that hashes `(tool, args)` and intervenes after three repeats.
**Follow-up trap:** *"Which one actually fires most often in production?"* — the no-progress detector, because the common failure isn't infinite exploration, it's the model retrying an identical call that will never succeed. And the intervention should be a tool *result* that tells it to change approach, not an exception.

### Q4 — A tool throws an exception mid-run. What happens?
**Answer:** It gets caught and returned to the model as a tool result string describing the failure, so the model can try another tool or report honestly. Propagating it discards all prior work in the run.
**Follow-up trap:** *"Always?"* — no. Distinguish the tool's dependency failing (return to the model) from a bug in your harness (crash loudly). A model cannot fix your `KeyError`, and swallowing it means you ship a broken agent that appears merely stupid.

### Q5 — Turn 40, context is full. What do you do?
**Answer:** Three levers in order. Truncate tool results at the tool boundary — highest leverage and belongs in the tool. Compact older turns into a dense recap while keeping recent turns verbatim, preserving the task, decisions, facts, and open items. Externalise state to a file or store the model re-reads on demand, so it survives compaction entirely.
**Follow-up trap:** *"What can compaction break?"* — it can drop a pending obligation or the original instruction. Never compact `messages[0]`, and carry an explicit open-items list through every compaction.

### Q6 — When is an agent the wrong choice?
**Testing:** the senior signal in this whole topic.
**Answer:** When the steps are known in advance. A deterministic pipeline, a chain, or an `if` statement is cheaper, faster, testable, and doesn't hallucinate. Agents earn their cost only when the number and order of steps genuinely can't be predicted. Also wrong for long-running or multi-party work, where a durable workflow engine with LLM activities is the better abstraction.
**Follow-up trap:** *"Your team already built it as an agent. Do you rip it out?"* — usually no, and saying yes is a red flag. Measure first: if step count is consistently 1-2 and the tool sequence never varies, collapse it to a chain and keep the agent path as a fallback for the long tail. Rewrites justified by taste rather than data are how you lose credibility as a Principal.

### Q7 — Why not just run 50 steps and let it figure things out?
**Answer:** Compounding failure. At 95% per-step reliability, 50 steps completes 8% of the time; at 85% it's 0.03%. Reliability is multiplicative, so autonomy trades capability against completion rate. The fix isn't a better model — it's fewer steps, checkpointing so failures resume, and human approval at the consequential points.
**Follow-up trap:** *"Doesn't a smarter model fix this?"* — it moves the per-step number, not the shape of the curve. Going from 85% to 95% per step takes a 10-step task from 20% to 60%, which is better and still not shippable unattended. The structural fixes are fewer steps, checkpointing, and approval gates.

### Q8 — What does LangGraph give you that your loop doesn't?
**Answer:** Persistence, primarily — checkpointers that let a failed run resume instead of restart, which matters because most multi-step runs fail somewhere. Then streaming, `interrupt()`-based human-in-the-loop, per-node retry semantics, observability hooks, and composition via subgraphs. It does not give you the loop; the loop is forty lines. Framing it as "a persistence layer and a state machine around a loop I could write myself" is the answer that signals you understand the boundary.
**Follow-up trap:** *"Then why not always use it?"* — because the graph is a schema, and schemas cost you when requirements are still moving. For a 3-step tool loop, LangGraph adds concepts, a dependency, and a state definition to maintain for persistence you may not need yet. Adopt it when you need durability, HITL, or inspectability, not by default.

### Q9 — How do you make tool calls safe to retry?
**Answer:** Idempotency keys. Any mutating tool takes a client-generated key, and the server stores `(key → result)` so a repeat returns the stored result rather than acting twice. Without this, a retried `send_email` or `create_ticket` duplicates. Read-only tools are naturally safe; classify your tools and only auto-retry the safe ones.
**Follow-up trap:** *"Where do you store the keys, and for how long?"* — a dedup store (Redis or a unique constraint) with a TTL longer than your maximum retry window, including manual replays. Too short and a next-day retry double-charges; unbounded and you're paying to remember 2023. And the check must be atomic: `INSERT ... ON CONFLICT DO NOTHING` with an affected-row count, never read-then-write.

### Q10 — Design the observability for this loop.
**Answer:** One span per step, one child span per tool call, following the OpenTelemetry GenAI semantic conventions so it's portable. Attributes: model, tokens in/out, cost, latency, tool name, outcome, and stop reason for the run. Metrics: steps per run (watch p99, not mean — the mean hides runaways), cost per run, tool error rate by tool, and completion rate. Without per-step traces, "it gave a bad answer" is unfalsifiable; with them you can see step 4 returned nothing and everything after was confabulation.
**Follow-up trap:** *"You have the traces and the answer is still wrong. Now what?"* — you've moved from an observability problem to an eval problem. Traces tell you what happened on one run; they can't tell you whether it's systematically bad. That needs a golden set and trajectory scoring, which is why observability and eval are separate investments and you need both.

### Q11 — How do you test an agent when the model is nondeterministic?
**Answer:** Separate the layers. The harness — stop conditions, budgets, dispatch, compaction — is deterministic and gets ordinary unit tests against a scripted fake model; that's most of the code and most of the bugs. Tools get tested independently. Only end-to-end behaviour needs eval-style testing: a golden set of tasks with trajectory assertions (did it call the right tools in a reasonable order) and outcome assertions, run at temperature 0, tracked as a distribution over runs rather than pass/fail on one.
**Follow-up trap:** *"Your golden set passes and production still degrades. Why?"* — the model changed under you, or your traffic drifted away from the golden set. Both are real. The mitigations are pinning model versions, re-running evals on every model upgrade as a release gate, and sampling live traffic into the golden set so it tracks reality instead of your original assumptions.

### Q12 — Walk me through adding human approval to a step.
**Answer:** You need durable state, because a human might take a day. Persist the loop state before the consequential action, emit a request for approval, and return. On approval, rehydrate from the checkpoint and continue; on rejection, append the rejection as an observation so the model can adapt. This is precisely why in-process loops don't survive the requirement — an approval gate forces you into durable execution, whether you adopt a framework or build it.
**Follow-up trap:** *"The human approves 48 hours later and the underlying data has changed. What happens?"* — you have a stale-approval problem, and this is where naive HITL breaks. Either re-validate preconditions before executing and re-prompt if they moved, or attach an expiry to the approval. Silently executing against changed state is how approval gates become theatre.

### Q13 — Your agent is slow. Where does the time go, and what do you do?
**Answer:** Measure before guessing, but the usual distribution is: model latency dominated by output tokens, then tool latency, then context growth inflating time-to-first-token as the prompt gets longer. Fixes in order: cut output tokens (structured output rather than prose), parallelise independent tool calls in the same turn, cache aggressively (prompt caching on the stable prefix, semantic caching on repeated queries), reduce steps by giving better tools, and route simple turns to a smaller model.
**Follow-up trap:** *"You cached aggressively and quality dropped. Explain."* — almost certainly a semantic cache with a similarity threshold set too loose, returning an answer to a *nearby* question rather than the one asked. Exact-match and prefix caching are safe; semantic caching trades correctness for cost and needs a measured threshold plus a hit-quality audit, not a default.

### Q14 — What's the difference between this loop and ReAct?
**Answer:** ReAct is the *prompting pattern* — interleave explicit reasoning with actions so the model can think, act, observe, and re-think. The loop is the *harness* that executes it. And ReAct as published required parsing `Thought:/Action:/Observation:` out of text; native tool calling replaced that, so a modern implementation gets the structure from the API rather than a regex. If someone describes ReAct as text parsing today, they're describing 2022.
**Follow-up trap:** *"Is explicit reasoning still worth the tokens with a reasoning model?"* — less than it was. Models that reason internally at test time already do much of what ReAct scaffolding forced externally, so prompting for visible Thought steps can add cost without adding accuracy. The judgement is empirical per task, and the honest answer names it as a live question rather than settled.

### Q15 — Single agent with 20 tools, or five specialists with four each?
**Testing:** whether you'll reach for multi-agent reflexively.
**Answer:** Start with one agent and good tools. Multi-agent adds real cost — routing errors, context handoff loss, harder debugging, more latency — and pays off only under specific conditions: genuinely parallelisable subtasks, context isolation needed to stop one workstream polluting another, or different tools requiring different permissions. Twenty tools is not by itself a reason to split; tool *selection* degrading is, and the first fix for that is better tool descriptions and grouping, not another agent.
**Follow-up trap:** *"How would you know selection is degrading rather than the task just being hard?"* — measure it directly, don't infer it. Log the chosen tool against the tool a human would have chosen on a labelled sample, and watch accuracy as you add tools. Reported benchmarks show sharp degradation well before 50 tools, but the number is model- and description-dependent, so yours has to be measured. If accuracy is flat and outcomes are still bad, the problem is the tools or the task, and splitting into sub-agents will make it worse rather than better.

---

## Red flags that fail you

- Describing an agent as "the LLM remembers the conversation".
- Letting a tool exception propagate and kill the run.
- Only having a step cap, with no cost or time budget.
- Not knowing that context is re-sent every turn (and so not knowing why cost is quadratic).
- Calling LangGraph "the agent" rather than the harness around one.
- Reaching for multi-agent before demonstrating a single agent is insufficient.
- Describing ReAct as regex-parsing `Thought:/Action:` in 2026.
- No answer for how you'd test it.

---

## Cheat card

```
THE LOOP
  messages[] → model(+tools) → tool_calls?
     no  → DONE (natural termination)
     yes → execute → append tool_results → loop
  MODEL IS STATELESS. Full context re-sent every turn → cost is QUADRATIC in turns.

STOP CONDITIONS (need all six)
  no tool call · step cap 10-25 · token budget · cost budget · wall-clock deadline
  no-progress: hash (tool,args), intervene at 3 repeats  ← fires most in prod

RELIABILITY MATH (know cold)
  0.95^10 ≈ 60%    0.85^10 ≈ 20%    0.95^50 ≈ 8%
  → better models don't fix this; fewer steps + checkpoints + HITL do

ERROR POLICY
  tool dependency fails  → return string to model (it routes around)
  harness bug            → crash loudly (model can't fix your KeyError)
  every execute() path returns a readable string, never raises

CONTEXT (in this order)
  1. truncate tool results AT THE TOOL (highest leverage)
  2. compact at ~70% window: recap old + keep recent verbatim
     NEVER compact messages[0], the task, or open obligations
  3. externalise to file/store — survives compaction entirely

FRAMEWORK BUYS YOU
  persistence/checkpointing ← the real reason · streaming · interrupt()/HITL
  retry semantics · observability hooks · subgraphs
  NOT the loop. The loop is ~40 lines.

WHEN NOT TO USE AN AGENT
  steps known in advance → write the pipeline
  one prompt suffices → use one prompt
  long-running/multi-party → durable workflow engine (Temporal/Step Functions)

IDEMPOTENCY
  every mutating tool takes a client-generated key; server stores (key→result)
```

## Sources

- [ReAct: Synergizing Reasoning and Acting in Language Models](https://arxiv.org/abs/2210.03629) — the origin paper; accessed 2026-07-26
- [Anthropic — Building Effective Agents](https://www.anthropic.com/engineering/building-effective-agents) — accessed 2026-07-26
- [Anthropic — Effective context engineering for AI agents](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents) — compaction and subagent figures; accessed 2026-07-26
- [Lost in the Middle: How Language Models Use Long Contexts](https://arxiv.org/abs/2307.03172) — accessed 2026-07-26
- [LangChain — production deployment patterns](https://octopusbuilds.com/blog/langchain-production-deployment-patterns) — checkpointer reliability arithmetic; accessed 2026-07-26

## Changelog
- 2026-07-26 — created
