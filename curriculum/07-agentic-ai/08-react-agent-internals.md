# create_react_agent Internals, Line by Line

> **Track:** T07 Agentic AI · **Time:** 1.5h · **Prereqs:** none · **Updated:** 2026-08-01
> **Module id:** `T07-react-agent-internals` · **Tags:** framework,langgraph

## The 30-second version

`create_react_agent` is not a different execution model from the `StateGraph` in `T07-langgraph-core` — it is that same Pregel runtime with the graph already wired for you: an `agent` node that calls the model, a `tools` node that dispatches every `tool_call` in the last message and appends `ToolMessage`s keyed by `add_messages`, and a routing function that loops back to `agent` while tool calls are pending and exits to `END` otherwise. Everything interesting is in five places: the routing check (`tool_calls` present or not), the `remaining_steps` managed value that degrades gracefully instead of raising `GraphRecursionError`, the `pre_model_hook`/`post_model_hook` insertion points that let you trim context or gate on approval without forking the graph, the `response_format` parameter that appends a `generate_structured_response` node after the loop exits, and whatever checkpointer you passed at compile time, which behaves exactly as it does for any other `StateGraph`. What you lose versus hand-rolling the graph is control over exactly those five things — you get one loop shape, one place tools can run, and one exit condition, in exchange for not writing forty lines you've already written twice in this curriculum. And as of LangGraph 1.0 (20 Oct 2025) it is itself deprecated in favor of `create_agent` from the `langchain` package, so know it as the reference shape rather than the thing you should reach for on a new project.

## Why this gets asked

Because "I used `create_react_agent`" and "I understand `create_react_agent`" produce identical demos and different interview answers. The interviewer has debugged a `post_model_hook` that silently broke tool dispatch because state injection differs from the un-hooked path, or watched a team hit `remaining_steps < 2` and get a generic "need more steps" message with no idea why, or tried to add a second tool-execution phase and discovered the prebuilt has exactly one `tools` node and no seam to add another. They want to know whether you can open the box, not just import from it — and, in 2026, whether you know it's the box LangChain itself is walking away from.

---

## Lineage: past → present → future

**What came before.** `create_react_agent` is the direct descendant of `langchain.agents.AgentExecutor`, the pre-2024 loop that ran a ReAct-style agent with no inspectable state: a failure at step 7 meant a full restart with no way to see what had happened. When LangGraph shipped in early 2024, `create_react_agent` was the first prebuilt on top of it — the "give me the loop, I don't want to write a `StateGraph` by hand" convenience wrapper, and for two years it was the default way most people met LangGraph at all, to the point that a lot of "LangGraph experience" on resumes is actually "called this one function." The pain that made it necessary in the first place was the same pain `T07-agent-loop-from-scratch` names for the raw forty-line loop: a working ReAct loop is easy to write once and easy to get subtly wrong on stop conditions, message accounting, and tool dispatch, so a maintained, tested prebuilt was worth adopting even for something conceptually small.

**Where it stands now.** It is a thin, well-tested `StateGraph` with two mandatory nodes and three optional ones, and understanding it is genuinely just understanding `T07-langgraph-core`'s reducer and routing model applied to one specific, small topology. The live fact to know is that LangChain's own v1.0 migration guide (Oct 2025) marks it deprecated in favor of `create_agent` in the `langchain` package, which runs on the same LangGraph runtime but adds a composable middleware system (`before_model`, `wrap_model_call`, `wrap_tool_call`, and friends — see `T07-harness-engineering`) instead of two fixed hook slots. It still works, there is no removal date published, and plenty of production code and tutorials still use it, so you need both: the mechanics of what you're actually running today, and the honest statement that this is the legacy shape.

**Where it's heading.** High confidence: `create_agent` supersedes it as the default entry point, and the middleware model — six composable hooks instead of `pre_model_hook`/`post_model_hook` — is the direction every framework in this space is converging on (LangChain's `AgentMiddleware`, Microsoft's `HarnessAgent` lifecycle hooks). Medium confidence: the underlying graph shape (one model node, one tool node, loop until no tool calls, optional structured-output tail) stays the reference topology even as the ergonomics around it change, because it is the same shape the raw loop and every framework converge on. Flag as unsettled: LangChain's own package layout kept moving after 1.0 — `create_agent` briefly disappeared from `langchain.agents.__init__` in a later point release before landing back — which is itself evidence for this module's closing point: treat any specific prebuilt as disposable and know the graph underneath it.

---

## Mental model

```
  create_react_agent(model, tools, ...) builds exactly this StateGraph:

  [pre_model_hook]? ──▶ AGENT ──▶ [post_model_hook]? ──▶ route()
        entry point         │                              │
     (else AGENT is entry)  │  calls model with             ├─ tool_calls present
                            │  tools bound, appends          │     ──▶ TOOLS
                            │  AIMessage via add_messages     │           │
                            │                                 │  executes each
                            │                                 │  tool_call, appends
                            │                                 │  ToolMessage(s)
                            │                                 │           │
                            │                                 │           └──▶ back to AGENT
                            │                                 │
                            │                                 ├─ no tool_calls + response_format
                            │                                 │     ──▶ GENERATE_STRUCTURED_RESPONSE ──▶ END
                            │                                 │
                            │                                 └─ no tool_calls, no response_format
                            │                                       ──▶ END

  STATE (AgentState, a TypedDict):
    messages: Annotated[Sequence[BaseMessage], add_messages]   ← merge-by-id reducer
    remaining_steps: NotRequired[RemainingSteps]                ← auto-populated, counts DOWN
    structured_response: NotRequired[StructuredResponse]        ← only if response_format set
```

The one thing to internalize: **this is `T07-langgraph-core`'s reducer-and-routing model with exactly one shape baked in.** There is one place the model gets called, one place tools get dispatched, and one routing function deciding between them. Every question about `create_react_agent` is really a question about what happens at those three points, because there is nothing else in the box.

---

## How it actually works

### 1. State and the reducer — `add_messages`, not `operator.add`

`AgentState` is a two-field `TypedDict` (three with structured output): `messages` with the `add_messages` reducer, and `remaining_steps`, a `RemainingSteps` managed value the runtime populates and decrements for you — you never write to it. `add_messages` merges by message `id` rather than concatenating, which is the same mechanism `T07-langgraph-core` covers in depth: a node returning `{"messages": [resp]}` appends `resp` if its id is new, and *replaces* the existing entry if the id matches, which is what makes `update_state` corrections to an in-flight tool call land as an edit instead of a duplicate. If you swap in a custom `state_schema` and forget the `Annotated[..., add_messages]` annotation on your own `messages`-like key, you get exactly `T07-langgraph-core`'s `InvalidUpdateError` the first time two writers touch it in one super-step — the prebuilt does not protect you from that, it just ships a state schema that already gets it right.

### 2. The `agent` node

A plain node: take `state["messages"]` (or `llm_input_messages` if a `pre_model_hook` set it — see below), apply `prompt` (a string, `SystemMessage`, callable, or `Runnable`), call the model with `tools` bound, and return `{"messages": [response]}`. Nothing here is different from calling `model.bind_tools(tools).invoke(...)` yourself; the value of the node is that it's wired into the graph with retry/checkpoint semantics for free.

### 3. Routing — the internal `should_continue`, and the standalone `tools_condition`

Two different things share a name in casual conversation and interviewers will test whether you keep them apart:

- **`should_continue`** is the private routing function `create_react_agent` wires up internally. It checks the last message for `tool_calls`; if present, route to `tools`; if absent and `response_format` was given, route to `generate_structured_response`; otherwise route to `END`. You never call this yourself.
- **`tools_condition`**, from `langgraph.prebuilt`, is a *public, standalone* utility with the same "tool calls present → route to tools, else → END" logic, meant for people building their own `StateGraph` by hand who want the same one-line routing rule `create_react_agent` uses internally, without reimplementing it. If someone says "I used `tools_condition` in my custom graph," that's a hand-rolled graph borrowing the prebuilt's routing primitive, not the prebuilt agent itself. Conflating the two in an answer is a tell that you've only ever imported the whole factory function and never looked one level down.

### 4. Tool dispatch — `ToolNode`, and the v1/v2 split

The `tools` node is a `ToolNode` instance built from your `tools` list (or passed in directly if you built your own `ToolNode`, e.g. to set `handle_tool_errors`). It reads every `tool_calls` entry off the last `AIMessage` and executes them, returning one `ToolMessage` per call, matched by `tool_call_id` — this is the same 1:1 `tool_use`/`tool_result` pairing invariant `T07-loop-engineering` calls out, and violating it (a `tool_use` with no matching result, usually from a cancelled or partially-failed turn) is the same API-400 failure mode there.

There is a real version split, controlled by `version="v1"` vs `"v2"` (v2 is current default):

- **v1**: all tool calls in the message dispatch inside a single `ToolNode` invocation, concurrently, as one graph step.
- **v2**: each tool call becomes its own `Send` (see `T07-langgraph-core`'s `Send` mechanics) targeting its own `ToolNode` instance, so tool calls are independent tasks in the Pregel sense rather than one node handling a batch internally.

The practical difference shows up in per-node policies: under v2 you can attach a `RetryPolicy` or timeout that applies per individual tool call, because each is its own scheduled task; under v1 a policy on the `tools` node applies to the whole batch. If a candidate answers "tool calls run in parallel" without knowing which version and why it matters for retry granularity, that's the shallow version of this answer.

By default, `ToolNode` catches exceptions raised inside a tool and returns them as a `ToolMessage` containing the error text rather than propagating — the framework-level version of `T07-agent-loop-from-scratch`'s "errors are observations, not exceptions" rule. Know that this is happening, because a test that expects a raised exception from a failing tool will not see one; you get a `ToolMessage` and the loop continues.

### 5. Recursion limit and `remaining_steps` — the graceful-degradation path

Two independent mechanisms, and this is the section most people get wrong by conflating them.

**`recursion_limit`** is the `T07-langgraph-core` mechanism: a hard cap on super-steps for the whole graph, defaulting to **1000 as of `langgraph` 1.0.6** (was 25 for the framework's first two years), set as a top-level `config` key, and it raises `GraphRecursionError` when exceeded. `create_react_agent` does not change this default or this behavior; it's the same backstop any `StateGraph` has.

**`remaining_steps`** is `create_react_agent`'s own, softer mechanism, and it is the thing people mean when they ask "what happens when a ReAct agent runs out of steps" without realizing they mean something different from the recursion limit. It's a `RemainingSteps` managed value auto-populated into state and decremented each time through the loop. The check, in `_are_more_steps_needed`, fires in two cases:

- `remaining_steps < 1` and every bound tool has `return_direct=True` — a tool result that would otherwise be returned straight to the user has nowhere to go.
- `remaining_steps < 2` **and** the model's response has tool calls — there isn't enough budget left to dispatch the tool and still get a final model turn afterward.

When either fires, the graph does not raise. It short-circuits with a synthetic final `AIMessage`: *"Sorry, need more steps to process this request."* That is a **named, observable failure mode**: if you see that exact string in production output, the fix is not a bug hunt, it's that your step budget is too tight for the task, and the symptom in a trace is the loop terminating cleanly at `END` with a suspiciously generic apology instead of a real answer or a `GraphRecursionError`. This is proactive degradation exactly like `T07-langgraph-core`'s `RemainingSteps`-based routing pattern — `create_react_agent` just has it built in rather than requiring you to wire it into a router yourself.

### 6. `pre_model_hook` and `post_model_hook`

These are the only two extension seams in the prebuilt, and they are inserted as ordinary nodes, not callback functions:

- **`pre_model_hook`**, if given, becomes the graph's entry point (instead of `agent`) and runs before every call to the model. Its return dict must contain **at least one of** `messages` or `llm_input_messages`. Returning `messages` writes through the `add_messages` reducer into permanent state — use this for a real edit, like a compaction that should stick. Returning `llm_input_messages` instead feeds the model a *different* message list for this one call without touching persisted state — use this for a summarization or trimming pass you don't want to make permanent. Conflating the two is the most common mistake: return `messages` when you meant a transient trim, and you've permanently rewritten history; return `llm_input_messages` when you meant a permanent compaction, and every subsequent turn re-does the same trim on the un-shrunk history.
- **`post_model_hook`** (v2 graphs only) inserts after `agent` and before routing, and it's the seam for human-in-the-loop approval or output validation — return an updated state, or call `interrupt()` inside it to pause for approval before tool dispatch, which composes with the checkpointer exactly as `T07-langgraph-durable`/`T07-human-oversight` describe for any interrupt. **The documented gotcha**: with a `post_model_hook` present, routing goes through a `post_model_hook_router` that determines whether tool calls are still pending by diffing tool-call ids on the last `AIMessage` against existing `ToolMessage`s in state, rather than the plain "does the last message have tool calls" check `should_continue` uses without a hook. A hook that mutates or drops messages without preserving that invariant can make the router think tool calls are already satisfied when they aren't, silently skipping dispatch — a real, reported issue, not a hypothetical.

### 7. Structured output — the extra node at the end

`response_format` doesn't change how the model is prompted mid-loop; it appends `generate_structured_response` as a **terminal node**, reached only when the loop would otherwise go to `END` (no pending tool calls). That node makes **one additional model call** constrained to your schema and writes the result to `state["structured_response"]` — it does not touch `messages`. Two consequences worth stating unprompted: this is strictly one extra LLM call per run, not per turn, so it's cheap; and if your task schema requires an `AgentStateWithStructuredResponse`-shaped state (the `structured_response` key must exist), passing a bare custom `state_schema` without it is a startup-time failure, not a runtime surprise.

### 8. Checkpointer integration

Nothing special here beyond `T07-langgraph-core`: `create_react_agent(..., checkpointer=...)` compiles the same way any `StateGraph.compile(checkpointer=...)` does, so `interrupt_before=["tools"]` / `interrupt_after=["agent"]` are static breakpoints on the two real nodes, `graph.get_state(config)` and `Command(resume=...)` work identically, and multi-turn memory is `thread_id`-scoped exactly as it is for a hand-rolled graph. The only prebuilt-specific detail is that `interrupt_before`/`interrupt_after` can only name nodes that exist in this specific topology — `"agent"`, `"tools"`, and (if configured) the hook or structured-response nodes — because you didn't build the graph, so you can't set a breakpoint on a node you didn't ask for.

---

## Build it from scratch

You already have the forty-line loop in `T07-agent-loop-from-scratch` and the full `StateGraph` mechanics in `T07-langgraph-core`. The exercise that actually teaches this module is reimplementing `create_react_agent` on top of `StateGraph` yourself and diffing it against the real one:

```python
# untested sketch - minimal reimplementation of create_react_agent's default shape
from typing import Annotated, Sequence
from typing_extensions import TypedDict
from langchain.messages import AnyMessage
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode, tools_condition

class AgentState(TypedDict):
    messages: Annotated[Sequence[AnyMessage], add_messages]

def make_agent(model, tools):
    model_with_tools = model.bind_tools(tools)

    def agent(state: AgentState):
        return {"messages": [model_with_tools.invoke(state["messages"])]}

    builder = StateGraph(AgentState)
    builder.add_node("agent", agent)
    builder.add_node("tools", ToolNode(tools))
    builder.add_edge(START, "agent")
    builder.add_conditional_edges("agent", tools_condition)   # the SAME primitive
    builder.add_edge("tools", "agent")
    return builder.compile()
```

This is, deliberately, most of what `create_react_agent` actually is: two nodes, `tools_condition` for routing, a loop-back edge. What it's missing — and what you should add one piece at a time to see exactly where the complexity in the real prebuilt lives — is `remaining_steps`-based graceful degradation, the `pre_model_hook`/`post_model_hook` seams, and the `generate_structured_response` tail. Build each, then compare against reading the real `chat_agent_executor.py` source; the gap between your version and theirs is the whole content of this module.

---

## How it's done in production

The prebuilt is a fine choice for exactly the case it was built for — a single model, a flat tool list, a loop, optionally one approval point — and a poor one the moment you need branching, fan-out, or more than one tool-execution phase, because there is exactly one `tools` node and no seam to add a second.

| Symptom | Cause | Fix |
|---|---|---|
| `"Sorry, need more steps to process this request."` in output | `remaining_steps` graceful-degradation path fired, not a crash | raise the step budget for this task class, or shrink the task; this is a budget problem, not a bug |
| `post_model_hook` seems to skip tool execution | hook mutated/dropped messages, breaking the tool-call-id diff `post_model_hook_router` relies on | preserve tool-call ids exactly through the hook; don't reshape `messages` there, use `llm_input_messages`-style transient state elsewhere |
| Permanent history got trimmed when you only wanted a one-off summarized call | `pre_model_hook` returned `messages` instead of `llm_input_messages` | return `llm_input_messages` for transient, `messages` only for edits you want to persist |
| Per-tool retry policy doesn't apply per call | on `version="v1"`, the whole batch is one node invocation | use `version="v2"` if you need per-call `RetryPolicy`/timeout via `Send` |
| `interrupt_before=["my_node"]` fails at compile | node isn't part of this fixed topology | breakpoints can only target `"agent"`/`"tools"`/hook nodes that actually exist in this graph |
| Structured output silently absent | custom `state_schema` doesn't declare `structured_response` | use `AgentStateWithStructuredResponse` or add the key yourself |
| Team can't add a second tool phase (e.g. a validation pass between two tool calls) | the prebuilt has exactly one `tools` node, no seam for more | this is the sign to drop to a hand-rolled `StateGraph` |

---

## Tradeoffs & when NOT to use it

- **When you need more than one tool-execution phase, or branching routing, use a hand-rolled `StateGraph`.** `create_react_agent` gives you exactly one loop shape. A workflow that needs "search, then validate the search results with a different tool set, then answer" doesn't fit two hook slots; it needs real nodes and edges, which is `T07-langgraph-core`'s territory, not this one's.
- **When you need fan-out or `Send`-based map-reduce inside the loop itself** (not just per-tool-call dispatch), you're past what the prebuilt exposes. The `v2` `Send`-per-tool-call mechanism is an implementation detail of dispatch, not a general fan-out primitive you control.
- **It is a deprecated API as of LangGraph 1.0.** For new work, `create_agent` from `langchain` runs on the same graph shape with a real middleware system (six composable hooks instead of two fixed slots) and is the maintained path. Reaching for `create_react_agent` on a greenfield project in 2026 without saying so is a signal you learned LangGraph from an old tutorial rather than current docs.
- **For a genuinely simple loop, skip both and hand-write the forty lines.** `T07-agent-loop-from-scratch`'s point stands here too: if you don't need checkpointing, HITL, or a declared topology, `create_react_agent` buys you two node names and a routing function you could write in five minutes, at the cost of a framework dependency and two fixed extension seams whose exact semantics (the `messages`/`llm_input_messages` split, the hook-router tool-call diff) you now have to know precisely to avoid the bugs this module names.

---

## Interview questions

### Q1 — What graph does `create_react_agent` actually build?
**Testing:** whether you've looked past the function signature.
**Answer:** A `StateGraph` with an `agent` node (calls the model with tools bound), a `tools` node (a `ToolNode` dispatching every `tool_call` on the last message and returning matched `ToolMessage`s), and a routing function checking for pending tool calls: present → loop to `tools` then back to `agent`; absent and `response_format` set → `generate_structured_response` → `END`; absent otherwise → `END`. `pre_model_hook` and `post_model_hook`, if given, insert as additional nodes before and after `agent`.
**Follow-up trap:** *"So it's just `StateGraph` with training wheels?"* — yes, and say so plainly. It's `T07-langgraph-core`'s reducer-and-routing model with one topology baked in. The value is the tested wiring, not a different execution model.

### Q2 — What's the state schema, and what would break if you forgot the reducer annotation on your own custom state?
**Answer:** `AgentState`: `messages: Annotated[Sequence[BaseMessage], add_messages]` plus `remaining_steps: NotRequired[RemainingSteps]`, and `structured_response` if `response_format` is set. If you swap in your own `state_schema` and add a list-typed key without an `Annotated` reducer, you get the same `InvalidUpdateError: Can receive only one value per step` `T07-langgraph-core` names, the moment two writers touch it in one super-step — the prebuilt's own `messages` key is safe because it ships with `add_messages` already attached, but that protection doesn't extend to keys you add yourself.
**Follow-up trap:** *"Why `add_messages` and not `operator.add`?"* — because it merges by message id rather than blindly concatenating, which is what makes `update_state` corrections land as edits instead of duplicates. Same answer as in `T07-langgraph-core`; this module doesn't change that mechanism, it just uses it.

### Q3 — Distinguish `should_continue` from `tools_condition`.
**Testing:** whether "tools condition" is one concept to you or two.
**Answer:** `should_continue` is the private routing function `create_react_agent` wires internally, with three-way logic (tools / structured response / end). `tools_condition` is the public standalone utility in `langgraph.prebuilt` with the simpler two-way version of the same check, meant for people building their own `StateGraph` who want the same one-line rule without reimplementing it.
**Follow-up trap:** *"If I use `tools_condition` in my own graph, am I using `create_react_agent`?"* — no. You're borrowing one routing primitive from the prebuilt library into a hand-rolled graph. That's a completely different thing from calling the factory function, and conflating them is a tell.

### Q4 — Your agent returns "Sorry, need more steps to process this request." What happened, and is this a bug?
**Testing:** the named failure mode.
**Answer:** Not a bug — the `remaining_steps` graceful-degradation path fired. It's checked in `_are_more_steps_needed`: `remaining_steps < 1` with every tool `return_direct=True`, or `remaining_steps < 2` with tool calls still pending, meaning there isn't enough budget for a dispatch-then-respond round trip. Rather than raising, the graph short-circuits to a synthetic final message. This is distinct from `GraphRecursionError`, which is a hard raise at the `recursion_limit` (1000 by default since `langgraph` 1.0.6).
**Follow-up trap:** *"How do you fix it?"* — raise the step budget for that task class, or shrink the task; the message is telling you your budget and your task length don't match, and the fix is a budget decision, not a debugging session.

### Q5 — `pre_model_hook` returns `{"messages": [...]}` versus `{"llm_input_messages": [...]}`. What's the difference, and what breaks if you pick wrong?
**Answer:** `messages` writes through the `add_messages` reducer into permanent graph state — a real, persisted edit. `llm_input_messages` feeds a different list to this one model call without touching persisted state — a transient view. Pick `messages` when you meant a permanent compaction; pick `llm_input_messages` when you meant a one-off trim. Get it backwards and either your compaction never sticks (you re-trim the same growing history every turn) or your transient summarization becomes permanent (you've silently rewritten history you meant to keep).
**Follow-up trap:** *"Which would Claude Code's snip/microcompact levels (see `T07-loop-engineering`) map to?"* — the reversible, cheap levels (snip, microcompact when hot) look more like `llm_input_messages` in spirit (non-destructive, transient shaping); a true compaction that permanently discards old turns is a `messages` write. The prebuilt gives you the primitive; the cascade design is yours.

### Q6 — What breaks with `post_model_hook`, specifically?
**Answer:** With a `post_model_hook` present, routing goes through `post_model_hook_router`, which determines whether tool calls are still outstanding by diffing tool-call ids on the last `AIMessage` against existing `ToolMessage`s in state — not the plain "does the last message have tool calls" check used without a hook. A hook that mutates or drops messages without preserving that id relationship can make the router conclude tool calls are already satisfied when they aren't, silently skipping dispatch. This is a real reported bug pattern, not a hypothetical edge case.
**Follow-up trap:** *"How would you catch this in testing?"* — a test asserting that a scripted response with N tool calls results in exactly N `ToolMessage`s reaching state when a `post_model_hook` is attached, mirroring `T07-agent-testing`'s "assert invariants, not outputs" principle — specifically the tool_use/tool_result 1:1 pairing invariant from `T07-loop-engineering`.

### Q7 — v1 vs v2 tool dispatch: what's the actual behavioral difference?
**Answer:** v1 executes all tool calls from one `AIMessage` inside a single `ToolNode` invocation, concurrently, as one graph step — any per-node policy on `tools` applies to the whole batch. v2 (current default) turns each tool call into its own `Send`, so each is an independent scheduled task; a `RetryPolicy` or timeout attaches per individual tool call rather than to the batch.
**Follow-up trap:** *"Does this affect the fan-in reducer requirements from `T07-langgraph-core`?"* — yes, structurally: v2's per-call `Send` dispatch is the same map-reduce shape as any other `Send` fan-out, which means the channel each `ToolMessage` writes into needs a reducer that tolerates concurrent writes — `add_messages` already provides that, which is why it's safe by default here even though you didn't have to think about it.

### Q8 — How does `response_format` actually change the graph?
**Answer:** It appends a terminal `generate_structured_response` node, reached only from the point the loop would otherwise exit to `END` — i.e., no pending tool calls. That node makes one additional, schema-constrained model call and writes to `state["structured_response"]`, leaving `messages` untouched. It is one extra call per run, not per turn.
**Follow-up trap:** *"Does structured output change how the model behaves mid-loop?"* — no, and that's the point worth volunteering. The model reasons and calls tools completely normally through the whole loop; structuring only happens once, at the very end, against the final unstructured answer. If you need structure enforced at every intermediate step, `response_format` on `create_react_agent` is the wrong tool.

### Q9 — Checkpointer and `interrupt_before`/`interrupt_after` on `create_react_agent` — anything different from a hand-rolled graph?
**Answer:** No, mechanically — same `compile(checkpointer=...)`, same `Command(resume=...)`, same thread-scoped multi-turn memory as any `StateGraph` (`T07-langgraph-core`, `T07-langgraph-durable`). The only prebuilt-specific constraint is that breakpoints can only target nodes that exist in this fixed topology — `"agent"`, `"tools"`, and whichever hook/structured-response nodes you configured — because you didn't build the graph and can't put a breakpoint on a node that isn't there.
**Follow-up trap:** *"Where would you put a human approval gate before a destructive tool call?"* — `interrupt_before=["tools"]` is the coarse version (pauses before *any* tool call); for per-tool gating (only pause for the destructive one), you need `post_model_hook` calling `interrupt()` conditionally, or you've outgrown the prebuilt and should hand-roll the graph per `T07-human-oversight`'s gate-placement model.

### Q10 — When do you drop `create_react_agent` for a hand-rolled `StateGraph`?
**Testing:** the senior signal.
**Answer:** The moment you need more than the fixed shape supports: a second tool-execution phase, branching that depends on which tool was called, fan-out beyond per-call `Send` dispatch, or extension points beyond the two hook slots. Two hooks is enough for "trim context" plus "gate on approval"; it is not enough for "validate tool results with a different tool set before continuing," which needs a real node graph. The tell in an interview is reaching for `pre_model_hook`/`post_model_hook` to force a multi-phase workflow into two slots instead of just writing the `StateGraph`.
**Follow-up trap:** *"Isn't rewriting as a full `StateGraph` more work for no benefit?"* — it's a few more lines, and the benefit is that the topology is now something you can diagram, extend, and reason about, rather than being creative with two fixed seams. `T07-langgraph-core`'s own framing applies here at one level up: don't pay ceremony for nothing, but don't force a shape that doesn't fit either.

### Q11 — Is `create_react_agent` still a reasonable thing to use in 2026?
**Testing:** currency, and honesty about deprecated tools.
**Answer:** It still works — LangChain's v1.0 migration guide (Oct 2025) deprecates it in favor of `create_agent` from the `langchain` package but publishes no removal date, and it remains widely used in existing code and tutorials. `create_agent` runs on the same LangGraph runtime and graph shape but replaces the two fixed hook slots with a composable middleware system (`before_model`, `wrap_model_call`, `wrap_tool_call`, and others — see `T07-harness-engineering`), which is strictly more extensible for the same underlying mechanics.
**Follow-up trap:** *"Then why does this module exist instead of just teaching `create_agent`?"* — because the graph shape underneath both is identical, and `create_react_agent`'s source is small enough to read end to end in one sitting, which makes it the better teaching vehicle for the mechanics. Knowing `create_react_agent` cold and knowing it's legacy are not in tension; the second fact is itself part of a complete answer.

---

## Red flags that fail you

- Describing `create_react_agent` as a different runtime from `StateGraph` rather than a pre-wired instance of it.
- Confusing `should_continue` (internal, three-way) with `tools_condition` (public, two-way utility).
- Not knowing the difference between `recursion_limit` (hard raise, 1000 default) and `remaining_steps` (soft, graceful degradation to a canned message).
- Returning `messages` from a `pre_model_hook` when you meant a transient trim, or vice versa.
- Claiming `response_format` changes model behavior mid-loop rather than adding one terminal call.
- Not knowing it's deprecated in LangGraph 1.0, or overclaiming it's "removed."
- Trying to force a multi-phase tool workflow into two hook slots instead of dropping to a hand-rolled graph.

## Cheat card

```
GRAPH:  [pre_hook]? -> agent -> [post_hook]? -> route()
          entry pt        │                        │
                      model+tools              tool_calls? -> tools -> (back to agent)
                      bound, invoke()           no calls + response_format? -> generate_structured_response -> END
                                                 no calls, no format? -> END

STATE (AgentState): messages: Annotated[Seq[BaseMessage], add_messages]
                     remaining_steps: NotRequired[RemainingSteps]   (auto, counts down)
                     structured_response: NotRequired[...]           (only if response_format)

ROUTING: should_continue (internal, 3-way) != tools_condition (public util, 2-way, same core check)

TOOL DISPATCH (ToolNode): matches ToolMessage.tool_call_id 1:1 to AIMessage.tool_calls
  v1: all calls, ONE ToolNode invocation, batch retry/timeout policy
  v2 (default): each call its OWN Send -> own ToolNode task, PER-CALL retry/timeout
  exceptions inside a tool -> caught, returned as ToolMessage text (NOT raised)

STEP LIMITS (two different mechanisms)
  recursion_limit: hard cap, top-level config key, default 1000 (langgraph >=1.0.6)
                   -> raises GraphRecursionError
  remaining_steps: soft, RemainingSteps managed value, auto-decremented
    fires: remaining<1 & all tools return_direct=True
        or remaining<2 & tool_calls pending
    -> returns "Sorry, need more steps to process this request." (no raise)

HOOKS
  pre_model_hook: entry point if set. return {"messages":[...]}  -> PERMANENT edit (add_messages)
                                    or {"llm_input_messages":[...]} -> THIS CALL ONLY, no persist
                  at least one of the two keys REQUIRED
  post_model_hook: v2 graphs only. routes via post_model_hook_router, which diffs
                   tool_call ids vs existing ToolMessages -- NOT the plain last-message check
                   BUG: hook that drops/reshapes messages can break that diff, skip dispatch

STRUCTURED OUTPUT: response_format -> appends generate_structured_response, TERMINAL node
  only reached when loop would exit to END. ONE extra model call, writes
  state["structured_response"]. messages untouched. custom state_schema needs the key.

CHECKPOINTER: identical to any StateGraph.compile(checkpointer=...)
  interrupt_before/after only on nodes that EXIST in this fixed topology: agent, tools, hooks

DEPRECATED as of langgraph 1.0 (2025-10-20) -> use langchain.agents.create_agent
  (same graph shape, 6-hook AgentMiddleware instead of 2 fixed slots). No removal date set.

DROP TO HAND-ROLLED StateGraph WHEN: 2nd tool-execution phase needed, branching beyond
  tool-calls-yes/no, fan-out beyond per-call dispatch, per-tool (not global) approval gating
```

## Sources

- [create_react_agent | langgraph.prebuilt | LangChain Reference](https://reference.langchain.com/python/langgraph.prebuilt/chat_agent_executor/create_react_agent) — full parameter list, deprecation notice, `remaining_steps` behavior; accessed 2026-08-01
- [langgraph/libs/prebuilt/langgraph/prebuilt/chat_agent_executor.py](https://github.com/langchain-ai/langgraph/blob/main/libs/prebuilt/langgraph/prebuilt/chat_agent_executor.py) — `AgentState` definition, `_are_more_steps_needed`, `_get_model_input_state`, hook merging logic; accessed 2026-08-01
- [tools_condition | langgraph.prebuilt | LangChain Reference](https://reference.langchain.com/python/langgraph.prebuilt/tool_node/tools_condition) — standalone routing utility, distinct from internal `should_continue`; accessed 2026-08-01
- [ReAct Agent (create_react_agent) — DeepWiki](https://deepwiki.com/langchain-ai/langgraph/8.1-react-agent-(create_react_agent)) — graph topology, v1/v2 dispatch split, `post_model_hook_router` mechanics; accessed 2026-08-01
- [LangGraph v1 migration guide](https://docs.langchain.com/oss/python/migrate/langgraph-v1) — deprecation status, `create_agent` replacement and middleware framing, migration example; accessed 2026-08-01
- `create_react_agent with post_model_hook will not inject state/store to tool calls` — langchain-ai/langgraph issue #4841 — the documented hook/routing interaction bug; accessed 2026-08-01
- `curriculum/07-agentic-ai/06-langgraph-core.md` (`T07-langgraph-core`) — the `StateGraph`/reducer/`Send`/checkpointer mechanics this module builds on directly
- `curriculum/07-agentic-ai/01-agent-loop-from-scratch.md` (`T07-agent-loop-from-scratch`) — the raw loop this prebuilt wraps

## Changelog
- 2026-08-01 — created
