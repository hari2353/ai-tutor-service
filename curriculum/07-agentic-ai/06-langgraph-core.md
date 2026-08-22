# LangGraph I: StateGraph, Reducers, Conditional Edges, Send

> **Track:** T07 Agentic AI · **Time:** 3h · **Prereqs:** `T07-agent-loop-from-scratch` · **Updated:** 2026-07-26
> **Module id:** `T07-langgraph-core` · **Tags:** sprint, framework, langgraph

## The 30-second version

LangGraph is a Pregel-style message-passing runtime wearing a graph API. You declare a typed **state** whose keys are independent channels, each with a **reducer** that says how concurrent writes to that key combine; **nodes** are plain functions that return partial state updates; **edges** decide what runs next, statically or via a routing function; and `Send` lets a routing function fan out to N dynamic copies of a node with per-copy state. Execution proceeds in **super-steps** — every node scheduled for a tick runs, possibly in parallel, all their writes are reduced into the state, and the next tick is scheduled. That structure buys you three things a plain loop doesn't have for free: a checkpoint boundary at every super-step, a declared topology you can inspect and stream, and well-defined merge semantics for parallel branches. For a simple `model → tool → model` agent it buys almost nothing, and you should say so; the abstraction starts paying when you have real branching, real fan-out, or a requirement to resume.

## Why this gets asked

Because LangGraph is on almost every agentic-AI job description in 2026, and the split between people who have shipped it and people who have followed a tutorial is visible within two questions. The tutorial answer is "nodes and edges, you compile it, it's a state machine." The shipped answer is about reducers — specifically, that the *default* reducer is last-write-wins, that two parallel nodes writing the same unannotated key raises `InvalidUpdateError: Can receive only one value per step`, and that `Annotated[list, add]` exists to make fan-in well-defined rather than as decoration. The interviewer has personally debugged a graph where a parallel branch silently clobbered the other branch's output, or one where `add_messages` was replaced with `operator.add` and human-in-the-loop message edits started appending duplicates instead of updating in place. They are also probing whether you'll reach for a graph when an `if` statement would do.

---

## Lineage: past → present → future

**What came before.** The first generation of LLM orchestration was **LangChain chains** (2022–2023): `LLMChain`, `SequentialChain`, and the `AgentExecutor`. Chains were DAGs of Runnables with no cycles, which is fine for retrieve-then-generate and useless for an agent, because an agent is definitionally a loop. `AgentExecutor` bolted a loop on, but the loop was opaque: you could not inspect the intermediate state, could not resume it, could not put a human in the middle of it, and could not branch on anything except the model's own output. The specific pain that killed it was **debuggability under failure**. When an `AgentExecutor` run failed on step 7 of 10, you had no state to inspect and no way to resume; you re-ran from zero and paid for all seven steps again, and the model took a different path so you couldn't reproduce the bug. LangGraph (first release early 2024, `1.0.0` on 20 Oct 2025) is LangChain's answer, and its intellectual ancestor is not LangChain at all — it's **Google's Pregel** (Malewicz et al., 2010), the bulk-synchronous-parallel graph processing model where vertices exchange messages in discrete super-steps and the computation halts when no messages are in flight. LangGraph says this in its own docs. That lineage explains the parts of the API that look strange until you see it: channels, reducers, and super-steps are Pregel concepts, not agent concepts.

**Where it stands now.** LangGraph is the default answer for "durable, inspectable agent orchestration in Python" and has real production adoption, but the consensus is narrower than the marketing. Three things are settled. First, **the graph is a persistence and inspection substrate, not intelligence** — nobody credible claims a hand-drawn graph makes the agent smarter. Second, **the Graph API and the Functional API coexist** and the choice is stylistic: `StateGraph` when the topology is the artifact you want to reason about, `@entrypoint`/`@task` when you'd rather write imperative Python and get durability. Third, **the higher-level factories moved out**: `create_agent` now lives in `langchain` with a middleware system, and LangGraph is positioned as the low-level runtime underneath. The live disagreement is about **how much topology to declare**. Anthropic's own guidance and OpenAI's Agents SDK argue for giving a capable model good tools and a short loop, on the grounds that hand-drawn graphs encode 2024 assumptions about model capability that a 2026 model would have handled better. The LangGraph position is that explicit topology is what makes behaviour auditable and resumable, which matters more than flexibility in regulated or high-cost domains. Both are defensible; the honest framing is that declared structure is worth its cost exactly when your failure modes are known in advance. A second live disagreement is **LangGraph versus a general durable-execution engine** (Temporal, Restate) with LLM calls as activities — the latter has a decade of operational maturity and no opinion about agents, which is either a feature or a missing feature depending on whether you want streaming and HITL primitives handed to you.

**Where it's heading.** Three directions with different confidence. **High confidence: the runtime is getting node-level operational controls that used to be your problem.** `1.2.0` (12 May 2026) added per-node timeouts (`run_timeout` and a progress-resetting `idle_timeout`), node-level `error_handler=` for Saga-style compensation, and cooperative graceful shutdown via `RunControl.request_drain()`. This is LangGraph converging on what a workflow engine looks like, and it is shipping. **Medium confidence: checkpoint storage becomes delta-based by default.** `DeltaChannel` (beta in 1.2, requires `langgraph>=1.2`) stores only the incremental write per step instead of re-serialising the whole accumulated channel, with `snapshot_frequency=K` to bound read latency; this exists because full-value checkpointing on a long message list is quadratic in storage and it is the obvious fix. **Lower confidence, and flagged as speculative: the streaming API keeps churning.** There have been three formats in fifteen months — v1 tuples, `version="v2"` unified `StreamPart` (1.1, Mar 2026), and `version="v3"` typed per-channel projections via `stream_events` (1.2, beta). If you write against the streaming surface, expect to migrate again.

---

## Mental model

Do not picture a flowchart. Picture **a spreadsheet with a scheduler**.

```
  STATE = a set of independent CHANNELS. Each channel owns a reducer.
  ┌───────────────┬──────────────────────────────┬──────────────────────┐
  │ channel       │ reducer                      │ concurrent writes?   │
  ├───────────────┼──────────────────────────────┼──────────────────────┤
  │ messages      │ add_messages (merge by id)   │ safe, merges         │
  │ findings      │ operator.add (concat)        │ safe, concatenates   │
  │ query         │ (none) → LAST WRITE WINS     │ InvalidUpdateError   │
  │ step_count    │ lambda a,b: a+b              │ safe, sums           │
  └───────────────┴──────────────────────────────┴──────────────────────┘

  EXECUTION = discrete SUPER-STEPS (Pregel ticks). One tick:

   tick N        ┌──────────┐
   scheduled:    │  node_b  │──writes {findings:[x]}──┐
                 └──────────┘                         │
                 ┌──────────┐                         ├──▶ REDUCE all writes
                 │  node_c  │──writes {findings:[y]}──┘    into the channels
                 └──────────┘                              │
                    (parallel, same tick)                   ▼
                                                    ★ CHECKPOINT ★
                                                            │
   tick N+1:     schedule every node with an inbound message
                 halt when no node has inbound messages
```

Three consequences fall straight out of this picture and they answer most interview questions:

1. **A node returns a partial update, not a state.** `return {"findings": ["x"]}` means "write `["x"]` to the `findings` channel." What happens to the existing value is the reducer's business, not the node's.
2. **Parallelism is per-tick, so merge semantics must be declared per channel.** That is the entire reason `Annotated[list, add]` exists. It is not syntax sugar.
3. **The checkpoint boundary is the super-step boundary.** That is why you can only time-travel to a super-step, and why "resume" means "re-run the node from its beginning," not "resume from the line that failed."

---

## How it actually works

### 1. State is a set of channels, and the reducer is the interesting part

```python
from typing import Annotated
from typing_extensions import TypedDict
from operator import add
from langchain.messages import AnyMessage
from langgraph.graph.message import add_messages

class ResearchState(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]  # merge-by-id
    subqueries: list[str]                                # LAST WRITE WINS
    findings: Annotated[list[dict], add]                 # concatenate
    budget_spent_usd: Annotated[float, lambda a, b: a + b]
    verdict: str                                         # LAST WRITE WINS
```

`TypedDict` is the documented default. A `dataclass` gets you default values. A Pydantic `BaseModel` gets you recursive validation and is explicitly slower than either, and `create_agent` in `langchain` does not accept Pydantic state at all. Reach for Pydantic only when the state crosses a trust boundary.

**Derive why the reducer is mandatory.** A reducer has signature `(current, update) -> new`. Suppose two nodes run in the same super-step and both write `findings`. Without a declared reducer, the runtime has two candidate values for one channel and no rule to combine them, so it refuses:

```
langgraph.errors.InvalidUpdateError: At key 'findings': Can receive only one
value per step. Use an Annotated key to handle multiple values.
```

That error message is the single most useful thing to be able to quote in an interview, because it proves you've hit it. **The observable symptom in a trace** is a graph that works fine on the sequential path and blows up the first time a conditional edge returns two destinations — which is often the first time you run it against real data rather than your test fixture.

The failure mode one level worse is the *silent* one. Sequential path, no reducer, two nodes write `verdict` on consecutive ticks: no error, second write wins, first write is gone. Nothing in the log says anything happened. That's the bug people actually ship.

**`add_messages` is not `operator.add`.** `operator.add` concatenates. `add_messages` matches on message `id` and *replaces* an existing message when the incoming one has the same id, and additionally coerces `{"type": "human", "content": "..."}` dicts into `HumanMessage` objects on the way in. That id-matching behaviour is the whole reason it exists: human-in-the-loop edits and `update_state` calls need to *correct* a message, not append a near-duplicate. Swap in `operator.add` and your approve-and-edit flow starts producing two copies of every edited tool call. `MessagesState` is the prebuilt one-key version; subclass it when you need more:

```python
from langgraph.graph import MessagesState

class State(MessagesState):
    documents: list[str]
```

**Bypassing a reducer.** `Overwrite` (from `langgraph.types`) sets a channel directly, skipping the reducer — the escape hatch for "compact the message list down to a summary." Constraint worth knowing: only one node may `Overwrite` a given key in a super-step, or you get `InvalidUpdateError` again.

```python
from langgraph.types import Overwrite

def compact(state: State):
    return {"messages": Overwrite([summarise(state["messages"])])}
```

**Multiple schemas.** `StateGraph(OverallState, input_schema=InputState, output_schema=OutputState)` narrows what callers can pass and see, while nodes still write to any channel in the union of declared schemas. A node can even declare a private schema in its signature and the runtime adds those channels. Useful for keeping a 30-key internal state out of your public API surface.

### 2. Nodes

A node is a sync or async function taking `state` and optionally `config: RunnableConfig` and/or `runtime: Runtime[Context]`. Parameters are injected by name and annotation.

```python
from dataclasses import dataclass
from langgraph.runtime import Runtime

@dataclass
class Ctx:
    user_id: str
    llm_provider: str = "anthropic"

def plan(state: ResearchState, runtime: Runtime[Ctx]):
    llm = get_llm(runtime.context.llm_provider)          # runtime context, not state
    store = runtime.store                                 # cross-thread memory
    attempt = runtime.execution_info.node_attempt         # 1-indexed, works w/o retry policy
    ...
    return {"subqueries": [...]}
```

`runtime` carries `context`, `store`, `stream_writer`, `execution_info`, `heartbeat()`, and `control`. **Runtime context is the right home for dependencies** — model name, DB handle, tenant id — because state gets serialised into every checkpoint and a DB connection is not serialisable. Passing `context=Ctx(user_id="1")` to `invoke` keeps it out of the checkpoint entirely.

`builder.add_node(plan)` auto-names the node `"plan"` from the function name. Explicit names (`add_node("plan", plan)`) are worth it because node names end up in checkpoint namespaces, stream metadata, and traces; renaming a node later loses saved state for interrupted threads.

**Node caching** is per-input and off by default:

```python
from langgraph.cache.memory import InMemoryCache
from langgraph.types import CachePolicy

builder.add_node("embed", embed, cache_policy=CachePolicy(ttl=300))
graph = builder.compile(cache=InMemoryCache())
# second identical invoke → {'embed': {...}, '__metadata__': {'cached': True}}
```

Default `key_func` is a pickle hash of the input, which means it is only useful when your state is small and hashable and your node is genuinely pure.

### 3. Edges and routing

```python
from langgraph.graph import StateGraph, START, END

builder.add_edge(START, "plan")           # entry point
builder.add_edge("plan", "search")        # static
builder.add_conditional_edges("search", route)              # dynamic
builder.add_conditional_edges("search", route, {True: "a", False: "b"})  # with mapping
builder.add_conditional_edges(START, route)                 # conditional entry
```

A routing function receives state and returns a node name, a list of node names (all run in parallel next tick), `END`, or a list of `Send` objects. **A node with multiple outgoing static edges fans out in parallel** — that is not opt-in, and it is the most common accidental source of `InvalidUpdateError`.

The rule that catches people: **do not mix static edges and dynamic routing from the same node.** `Command(goto=...)` *adds* a dynamic edge; it does not replace `add_edge("a","b")`. If both exist, both destinations run.

**Loops.** There is no loop construct. A loop is a conditional edge pointing backwards:

```python
def should_continue(state: ResearchState) -> Literal["tools", "__end__"]:
    last = state["messages"][-1]
    return "tools" if getattr(last, "tool_calls", None) else END

builder.add_conditional_edges("model", should_continue, ["tools", END])
builder.add_edge("tools", "model")
```

**Termination.** The graph halts when no node has inbound messages, or when the recursion limit trips. **Know this number and know it changed:** `recursion_limit` is a cap on super-steps and its default is **1000 as of `langgraph` 1.0.6**; for the framework's first two years it was **25**. Anyone quoting 25 is quoting 2024. It is a standalone config key and a classic bug is nesting it wrongly:

```python
graph.invoke(inp, config={"recursion_limit": 25})                    # correct
graph.invoke(inp, config={"configurable": {"recursion_limit": 25}})  # silently ignored
```

Exceeding it raises `GraphRecursionError`. A default of 1000 super-steps means the framework will no longer stop a runaway agent before it costs you real money, so **set it explicitly per graph.** For graceful degradation instead of an exception, use the `RemainingSteps` managed value:

```python
from langgraph.managed import RemainingSteps

class State(TypedDict):
    messages: Annotated[list, add]
    remaining_steps: RemainingSteps      # auto-populated by the runtime

def route(state) -> Literal["model", "wrap_up"]:
    return "wrap_up" if state["remaining_steps"] <= 2 else "model"
```

Proactive beats reactive here: the graph completes normally, the partial result is checkpointed, and the user gets a best-effort answer instead of a 500.

### 4. `Send` — dynamic fan-out

`Send(node_name, state_for_that_node)` is how you get map-reduce when N isn't known until runtime. It is returned *from a conditional edge*, and the second argument is a **different state object** for that one invocation, not the graph state.

```python
from langgraph.types import Send

class OverallState(TypedDict):
    subqueries: list[str]
    findings: Annotated[list[dict], add]      # ← the fan-in reducer. mandatory.

class SearchState(TypedDict):                  # per-Send state
    subquery: str

def fan_out(state: OverallState):
    return [Send("search_one", {"subquery": q}) for q in state["subqueries"]]

def search_one(state: SearchState):
    return {"findings": [do_search(state["subquery"])]}   # writes to the SHARED channel

builder.add_conditional_edges("plan", fan_out, ["search_one"])
builder.add_edge("search_one", "synthesise")
```

Three things to get right:

- **`Send` without a reducer on the fan-in channel is broken by construction.** Ten parallel `search_one` nodes writing an unannotated `findings` is exactly the two-writes-one-channel case, ten times over. This is the question behind the question when an interviewer asks about `Send`.
- **Conditional-edge-returns-a-list vs `Send`:** returning `["a","b"]` runs two *different* nodes on the *same* state. `Send` runs the *same* node N times on N *different* states. Different tools.
- **Concurrency is unbounded unless you bound it.** `graph.invoke(inp, {"max_concurrency": 10})` caps in-flight tasks. Fanning out 500 `Send`s at a rate-limited provider without this is how you generate a 429 storm. As of 1.2 you can also pass a per-`Send` timeout: `Send("search_one", {...}, timeout=TimeoutPolicy(idle_timeout=15))`.

**Unequal branch lengths.** If one branch is one node and another is three, the fan-in node runs as soon as *its* inbound edges are satisfied, which may be before the long branch finishes. `add_node("synthesise", synthesise, defer=True)` delays it until all pending tasks are done. This is the correct answer to "your reducer output is missing half the branches."

### 5. `Command` — update and route in one move

```python
from langgraph.types import Command

def triage(state: State) -> Command[Literal["refund", "escalate"]]:
    if state["amount"] > 1000:
        return Command(update={"tier": "manual"}, goto="escalate")
    return Command(update={"tier": "auto"}, goto="refund")
```

The `-> Command[Literal[...]]` annotation is not decorative: the runtime reads it to draw the graph and to know the node can reach those destinations. `Command` also carries `graph=Command.PARENT` to route from a subgraph node into the parent (which requires the shared key to have a reducer *in the parent's* schema), and `resume=` for interrupts — covered in `T07-langgraph-durable`. It can be returned from a **tool** as well as a node, which is how tool-driven handoffs work.

Use a conditional edge when you only route. Use `Command` when you route *and* write.

### 6. Compilation

```python
graph = builder.compile(
    checkpointer=checkpointer,          # persistence; see T07-langgraph-durable
    cache=InMemoryCache(),
    interrupt_before=["charge_card"],   # static debug breakpoints
)
```

`compile()` is cheap: structural validation (no orphaned nodes, no edges to nonexistent nodes) plus runtime wiring. It does not typecheck your reducers or your state shape. You **must** compile before invoking. `graph.get_graph().draw_mermaid_png()` renders the topology, which is genuinely the best argument for the Graph API: the picture is generated from the code, so it can't drift.

### 7. Streaming

Seven modes, and knowing which one answers which question is the practical skill:

| Mode | Yields | Use for |
|---|---|---|
| `values` | full state after each step | UI that renders whole state |
| `updates` | only changed keys, per node | progress logs, debugging |
| `messages` | `(token_chunk, metadata)` from LLM calls | token-by-token UI |
| `custom` | whatever you pass to `get_stream_writer()` | tool progress, non-LangChain LLMs |
| `checkpoints` | checkpoint events (same shape as `get_state()`) | audit |
| `tasks` | task start/finish with results and errors | per-node timing |
| `debug` | `checkpoints` + `tasks` + metadata | everything |

`checkpoints` and `tasks` require a checkpointer. Filter `messages` by `metadata["langgraph_node"]` to stream only one node's tokens, or by `metadata["tags"]` if you tagged the model; tag a model `nostream` to keep an internal structured-output call out of the user-facing stream entirely.

Three formats exist and you should know which you're on. v1 (still the default) changes shape depending on your options — raw dict for one mode, `(mode, data)` tuples for several, `(namespace, data)` for subgraphs, triples for both. `version="v2"` (needs `>=1.1`) makes every chunk a uniform `StreamPart` — `{"type", "ns", "data"}` — which is the one to write new code against today. `version="v3"` on `stream_events` (1.2, beta) gives typed per-channel projections (`stream.messages`, `stream.values`, `stream.interrupts`, `stream.output`) so you iterate channels instead of branching on a discriminator. Under v2, `invoke()` returns a `GraphOutput` with `.value` and `.interrupts`; dict-style access still works but is deprecated.

### 8. Subgraphs

A subgraph is a compiled graph used as a node. Two wiring patterns:

- **Shared state keys** → pass the compiled graph straight to `add_node`. It reads and writes the parent's channels.
- **Different schemas** → call `subgraph.invoke(...)` inside a wrapper node and translate both directions.

The `checkpointer=` argument on the subgraph's own `.compile()` controls persistence and this table is the interview answer:

| `checkpointer=` | Interrupts | Multi-turn memory | Same subgraph called twice in one node |
|---|---|---|---|
| `None` (default, per-invocation) | yes | no | yes |
| `True` (per-thread) | yes | yes | **no — namespace conflict** |
| `False` (stateless) | no | no | yes |

Default (`None`) is right for most things: the subgraph inherits the parent's checkpointer for the duration of one call, so `interrupt()` works, but state doesn't leak between calls. `checkpointer=True` gives a subagent conversational memory across calls and immediately breaks if the model issues two parallel calls to it, because both writes land in the same checkpoint namespace.

Subgraphs also change checkpoint granularity: with an inherited checkpointer the parent treats the whole subgraph as **one super-step**, so you cannot time-travel to a point inside it. `checkpointer=True` gives it its own checkpoint history and that becomes possible.

---

## Build it from scratch

The point of building a mini-Pregel is that once you have written the reducer loop, LangGraph stops being magic. This is the core, in about forty lines:

```python
# untested sketch — illustrative reimplementation, not LangGraph internals
from collections import defaultdict

END = "__end__"

class MiniGraph:
    def __init__(self, reducers: dict):
        self.reducers = reducers          # channel -> (cur, upd) -> new  (None = overwrite)
        self.nodes, self.edges, self.cond = {}, defaultdict(list), {}

    def add_node(self, name, fn):     self.nodes[name] = fn
    def add_edge(self, a, b):         self.edges[a].append(b)
    def add_conditional(self, a, fn): self.cond[a] = fn

    def _reduce(self, state, writes):
        """writes: list of (channel, value). THIS is the whole abstraction."""
        by_channel = defaultdict(list)
        for ch, val in writes:
            by_channel[ch].append(val)
        for ch, vals in by_channel.items():
            red = self.reducers.get(ch)
            if red is None:
                if len(vals) > 1:
                    raise ValueError(
                        f"At key '{ch}': Can receive only one value per step. "
                        f"Declare a reducer to handle multiple values.")
                state[ch] = vals[0]
            else:
                for v in vals:
                    state[ch] = red(state.get(ch), v)
        return state

    def invoke(self, state, entry, recursion_limit=25):
        frontier = [(entry, state)]                       # (node, node_input)
        for _ in range(recursion_limit):
            if not frontier:
                return state
            writes, next_frontier = [], []
            for name, node_input in frontier:             # ← one SUPER-STEP
                upd = self.nodes[name](node_input) or {}
                writes += list(upd.items())
            state = self._reduce(state, writes)           # ← reduce, then checkpoint
            # checkpoint(state) would go here — this is why the boundary is the tick
            for name, _ in frontier:
                dests = self.cond[name](state) if name in self.cond else self.edges[name]
                for d in (dests if isinstance(dests, list) else [dests]):
                    if isinstance(d, tuple):              # our stand-in for Send(node, st)
                        next_frontier.append(d)
                    elif d != END:
                        next_frontier.append((d, state))
            frontier = next_frontier
        raise RecursionError("recursion limit reached without a stop condition")
```

Everything real LangGraph adds on top of this is worth having, and none of it is conceptually deep: durable checkpoints instead of `checkpoint(state)`, per-node retry and timeout policies, seven stream modes, subgraph namespacing, `interrupt()`, and a Pydantic/TypedDict-aware serialiser. The lab at `(lab pending)` builds this up in six steps and then ports the same agent to real LangGraph so you can diff them.

---

## How it's done in production

A working ReAct-style research graph with routing, `Send` fan-out, and a bounded loop:

```python
# untested sketch — API verified against docs.langchain.com, accessed 2026-07-26
# pip install -U "langgraph>=1.2" langchain langchain-anthropic
import operator
from typing import Annotated, Literal
from typing_extensions import TypedDict

from langchain.chat_models import init_chat_model
from langchain.messages import AnyMessage, ToolMessage
from langchain.tools import tool
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.types import Send, RetryPolicy


class State(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]
    subqueries: list[str]                                  # overwritten each plan
    findings: Annotated[list[str], operator.add]           # FAN-IN CHANNEL
    remaining: int


class SearchTask(TypedDict):
    subquery: str


@tool
def search(query: str) -> str:
    """Search the corpus. Returns at most 2000 characters of the best matches."""
    return do_search(query)[:2000]


model = init_chat_model("claude-sonnet-4-6").bind_tools([search])
tools_by_name = {"search": search}


def plan(state: State):
    resp = model.invoke(
        [{"role": "system", "content": "Decompose the task into 2-5 independent subqueries."}]
        + state["messages"]
    )
    return {"messages": [resp], "subqueries": parse_subqueries(resp), "remaining": 6}


def fan_out(state: State):
    # dynamic map: one search_one per subquery, each with its OWN state
    return [Send("search_one", {"subquery": q}) for q in state["subqueries"]]


def search_one(state: SearchTask):
    return {"findings": [search.invoke({"query": state["subquery"]})]}


def reason(state: State):
    resp = model.invoke(state["messages"] + [
        {"role": "user", "content": "Findings:\n" + "\n---\n".join(state["findings"])}
    ])
    return {"messages": [resp], "remaining": state["remaining"] - 1}


def run_tools(state: State):
    out = []
    for call in state["messages"][-1].tool_calls:
        try:
            obs = tools_by_name[call["name"]].invoke(call["args"])
        except Exception as e:                      # errors are observations
            obs = f"Error: {type(e).__name__}: {e}"
        out.append(ToolMessage(content=str(obs)[:2000], tool_call_id=call["id"]))
    return {"messages": out}


def should_continue(state: State) -> Literal["run_tools", "__end__"]:
    if state["remaining"] <= 0:
        return END                                   # our budget, not the recursion limit
    return "run_tools" if state["messages"][-1].tool_calls else END


builder = StateGraph(State)
builder.add_node("plan", plan)
builder.add_node("search_one", search_one,
                 retry_policy=RetryPolicy(max_attempts=3))     # per-node retry
builder.add_node("reason", reason, defer=True)                 # wait for ALL fan-out
builder.add_node("run_tools", run_tools)

builder.add_edge(START, "plan")
builder.add_conditional_edges("plan", fan_out, ["search_one"])
builder.add_edge("search_one", "reason")
builder.add_conditional_edges("reason", should_continue, ["run_tools", END])
builder.add_edge("run_tools", "reason")

graph = builder.compile()

for part in graph.stream(
    {"messages": [{"role": "user", "content": "Compare Weaviate and pgvector for 50M vectors"}],
     "findings": [], "subqueries": [], "remaining": 6},
    stream_mode=["updates", "messages"],
    version="v2",
    config={"recursion_limit": 40, "max_concurrency": 8},     # set BOTH explicitly
):
    if part["type"] == "updates":
        for node, upd in part["data"].items():
            print(f"[{node}] {list(upd)}")
```

Note what's load-bearing: `operator.add` on `findings` (without it the fan-out raises), `defer=True` on `reason` (without it `reason` may run before all searches land), an explicit `remaining` budget separate from `recursion_limit` (the framework default of 1000 will not save you), an explicit `max_concurrency`, and truncation inside the tool rather than in the graph.

**Per-node fault tolerance** (`RetryPolicy` in all versions; `timeout=` and `error_handler=` require `>=1.2`, currently alpha):

```python
from langgraph.types import RetryPolicy, TimeoutPolicy, default_retry_on
from langgraph.errors import NodeError

builder.add_node(
    "charge_card", charge_card,
    retry_policy=RetryPolicy(max_attempts=3),       # 3 attempts, 0.5s initial,
                                                    # ×2.0 backoff, 128s cap, jitter on
    timeout=TimeoutPolicy(run_timeout=120, idle_timeout=30),   # async nodes only
    error_handler=lambda s, error: Command(update={"status": f"compensated: {error.error}"},
                                          goto="refund"),
)
```

`RetryPolicy`'s default `retry_on` retries **any** exception *except* `ValueError`, `TypeError`, `ArithmeticError`, `ImportError`, `LookupError`, `NameError`, `SyntaxError`, `RuntimeError`, `ReferenceError`, `StopIteration`, `StopAsyncIteration`, `OSError` — i.e. it assumes programmer errors aren't worth retrying, which is right. For `requests`/`httpx` it retries only 5xx. Composition order is fixed: timeout raises `NodeTimeoutError` → retry policy decides → only after retries are exhausted does `error_handler` run. `interrupt()` bypasses both.

### What breaks at scale

| Symptom | Cause | Fix |
|---|---|---|
| `InvalidUpdateError: Can receive only one value per step` | two nodes wrote one unannotated channel in one super-step | add a reducer: `Annotated[list, operator.add]` |
| Branch output silently missing, no error | no reducer, sequential writes, last one won | declare the reducer; grep state for unannotated non-scalar keys |
| Fan-in node sees only some fan-out results | branch lengths unequal, fan-in fired early | `add_node(..., defer=True)` |
| Duplicate near-identical messages after a human edit | `operator.add` used instead of `add_messages` | `add_messages` merges by message `id` |
| Both the intended and an unintended node ran | `Command(goto=...)` plus a static `add_edge` from the same node | pick one routing mechanism per node |
| 429 storm from the model provider | unbounded `Send` fan-out | `config={"max_concurrency": N}` |
| Agent burns 900 super-steps before failing | relying on default `recursion_limit` (1000 since 1.0.6) | set `recursion_limit` explicitly; add `RemainingSteps` routing |
| `recursion_limit` change has no effect | nested under `configurable` | it is a **top-level** config key |
| `GraphRecursionError` on a healthy graph | genuine loop with no terminating condition | conditional edge to `END`; own step budget in state |
| Checkpoint writes dominate latency on long threads | full channel value re-serialised per super-step | `durability="async"`; `DeltaChannel` (beta, ≥1.2) |
| Subgraph state "resets" between calls | default per-invocation persistence | `compile(checkpointer=True)` — and prevent parallel calls to it |
| Can't time-travel into a subgraph | inherited checkpointer treats it as one super-step | give the subgraph `checkpointer=True` |
| Streaming code broke after upgrade | v1 → v2 → v3 format churn | pin `version="v2"` explicitly rather than relying on the default |

**Observability.** LangGraph traces natively into LangSmith; if you're already on OpenTelemetry, `stream_mode="tasks"` gives you node start/finish with results and errors, which is the raw material for your own spans. The metric that actually catches regressions is **super-steps per run at p99**, not the mean — the mean hides the run that looped 400 times.

---

## Tradeoffs & when NOT to use it

- **For a plain `model → tool → model` loop, LangGraph is negative value.** You get a `StateGraph`, a reducer, two edges and a compile step in exchange for something that was twenty lines. Worse, you now have a framework in the stack trace and a state schema to keep in sync. Say this out loud in an interview; it is a stronger signal than enthusiasm. Reach for it when there is *branching you need to audit*, *fan-out you need to merge correctly*, or *a resume requirement*.
- **If the workflow is deterministic, write the function.** A declared graph with no conditional edges and no cycles is a function call with extra ceremony and a serialisation step.
- **If you need durability across hours/days with cross-service compensation, consider Temporal or Restate instead.** They have a decade of operational maturity in exactly this problem, better visibility into in-flight workflows, and no opinions about agents. LangGraph's counter-argument is real (streaming, `interrupt()`, and time travel come free), but "we use a durable execution engine and LLM calls are activities" is a legitimate architecture, not a failure to adopt LangGraph. The 1.2 additions — timeouts, error handlers, graceful drain — are LangGraph moving toward Temporal, which tells you where the gap was.
- **Pydantic state costs real throughput.** Validation runs on updates on every node. For a hot graph, `TypedDict` or `dataclass`.
- **Large blobs in state are a checkpoint tax, not a convenience.** Every super-step re-serialises the full channel value by default. Put document text in a store or object storage and keep an id in state. This is the mistake with the largest cost multiplier in the whole module.
- **The API surface moves fast and it will cost you migrations.** Three streaming formats in fifteen months; `create_agent` relocated to `langchain`; `1.2` features shipped in alpha. If your team cannot absorb a breaking-ish upgrade every two quarters, pin hard and budget the migration.
- **Graph topology can encode staleness.** A carefully hand-drawn router built against a 2024-era model may be actively worse than handing a 2026 model the tools and a short loop. Revisit your topology when you upgrade models; don't assume the graph is the invariant.

---

## Interview questions

### Q1 — What is LangGraph, in one sentence, and how is it different from LangChain?
**Testing:** whether you can locate it in the stack without marketing language.
**Answer:** LangChain gives you the components — chat models, tools, retrievers, message types. LangGraph is a low-level orchestration runtime underneath: typed state with per-channel merge semantics, explicit control flow including cycles, checkpointed persistence, and human-in-the-loop primitives. You use LangChain components *inside* LangGraph nodes. Its execution model is Pregel's bulk-synchronous message passing, not a DAG executor.
**Follow-up trap:** *"Why couldn't you just use a LangChain chain?"* — chains are acyclic, so they can't express a loop, and an agent is definitionally a loop. And the old `AgentExecutor` had a loop but no inspectable state, so a failure at step 7 meant re-running from zero with no reproducibility.

### Q2 — What are the three things you define to build a graph?
**Answer:** State (a schema plus a reducer per key), nodes (functions returning partial state updates), edges (what runs next — static, conditional, or via `Command`/`Send`). Then compile. Nodes do the work; edges decide what's next.
**Follow-up trap:** *"What does compiling actually do?"* — structural validation (orphaned nodes, edges to nonexistent nodes) and runtime wiring, plus it's where you attach the checkpointer, cache, and static breakpoints. It does **not** validate your reducers or state shapes. It's cheap; you just can't invoke without it.

### Q3 — What happens if two nodes in the same super-step write the same state key with no reducer?
**Testing:** the single highest-signal question in this topic.
**Answer:** `InvalidUpdateError: At key '<k>': Can receive only one value per step. Use an Annotated key to handle multiple values.` The runtime has two candidate values for one channel and no rule to combine them, so it refuses rather than guessing. Fix is `Annotated[list, operator.add]` or a custom reducer.
**Follow-up trap:** *"And if they write on consecutive super-steps instead?"* — **no error at all.** The default reducer is last-write-wins, so the second write silently discards the first. That's the worse bug, because nothing appears in the log, and it's why you audit every non-scalar state key for a declared reducer rather than waiting for the exception.

### Q4 — Why does `Annotated[list, add]` exist? What breaks without it?
**Answer:** A reducer is `(current, update) -> new`. Absent one, a channel can accept exactly one write per super-step. Any parallel fan-out or `Send` map-reduce writing a shared channel therefore breaks. `Annotated[list, operator.add]` declares "concatenate," which makes N concurrent writers well-defined. It is the mechanism that makes fan-in safe, not a typing nicety.
**Follow-up trap:** *"What's the risk of `operator.add` on a list?"* — it only appends, so it cannot express correction or dedup. `update_state` and human edits get appended as new entries rather than modifying existing ones, ordering across parallel branches is nondeterministic, and the list grows without bound so every checkpoint gets bigger. Use `Overwrite` to reset it, `add_messages` when identity matters, and consider `DeltaChannel` (beta, ≥1.2) for growth.

### Q5 — `add_messages` vs `operator.add`. Why does LangGraph ship a special one?
**Answer:** `operator.add` concatenates blindly. `add_messages` matches on message `id` and *replaces* an existing message when the incoming one has the same id, and it coerces `{"role": ..., "content": ...}` dicts into LangChain message objects. The id-matching is the point: HITL flows and `update_state` need to correct a message, not duplicate it.
**Follow-up trap:** *"Show me the bug from getting this wrong."* — an approve-and-edit flow where a human edits a draft tool call. With `operator.add` you get the original *and* the edited version in history, the model sees two conflicting instructions, and it often executes the pre-edit version. The observable symptom is a message list that grows by two per human interaction instead of one.

### Q6 — Walk me through `Send`. What problem does it solve that a conditional edge doesn't?
**Answer:** `Send(node, state)` fans out to N *dynamic* invocations of the same node, each with its own input state, returned as a list from a conditional edge. The number of destinations isn't known at build time and each copy needs different input. A conditional edge returning `["a","b"]` runs two *different* nodes on the *same* state; `Send` runs one node N times on N different states. Canonical use is map-reduce: plan produces subqueries, `Send` fans out one worker per subquery, they all write a reduced channel, a synthesise node reads the merged result.
**Follow-up trap:** *"What's the first thing that breaks in your `Send` example?"* — the fan-in channel with no reducer. Ten workers writing an unannotated key is the one-value-per-step error ten times over. Second thing: unbounded concurrency — 500 `Send`s against a rate-limited provider needs `config={"max_concurrency": N}`. Third: if branch lengths differ, the fan-in node fires early and sees partial results; `add_node(..., defer=True)` fixes it.

### Q7 — When do you use `Command` instead of a conditional edge?
**Answer:** When you need to update state *and* route in one atomic decision. `Command(update=..., goto=...)` does both; a conditional edge only routes. It also carries `graph=Command.PARENT` for subgraph-to-parent navigation and `resume=` for interrupts, and it can be returned from a tool as well as a node.
**Follow-up trap:** *"Any gotchas?"* — two. You must annotate the return type `-> Command[Literal["a","b"]]` or the runtime can't render the graph or know the node's destinations. And `Command(goto=...)` *adds* a dynamic edge — it doesn't override a static `add_edge` from that node, so if both exist both destinations execute. Pick one routing mechanism per node.

### Q8 — What is a super-step and why should I care?
**Answer:** One Pregel tick. Every node scheduled for that tick runs, possibly in parallel; all their writes are reduced into the channels; a checkpoint is written; then the next tick is scheduled from whichever nodes have inbound messages. Halt when none do. You care because it defines three things: what "parallel" means (same tick), where reducers apply (across writes within a tick), and where checkpoints exist.
**Follow-up trap:** *"What follows for resuming a failed run?"* — you resume from a super-step boundary, which means the whole node re-runs from its first line, not from the line that failed. Anything non-idempotent before the failure point runs twice. LangGraph does persist per-node *pending writes* within a super-step, so nodes that already succeeded in the failed tick aren't re-executed — but the failing node is.

### Q9 — How do you stop a LangGraph agent looping forever?
**Answer:** Four layers. A conditional edge that can reach `END`. An explicit step or cost budget carried in state, decremented per loop and checked in the router. `recursion_limit` as a backstop — and note the default is **1000 super-steps as of 1.0.6**, up from 25, so it is no longer a meaningful safety net and must be set per graph. And `RemainingSteps` for graceful degradation: route to a wrap-up node at `remaining <= 2` so you checkpoint a partial answer instead of raising.
**Follow-up trap:** *"Where do you put `recursion_limit`?"* — top level of `config`, **not** inside `configurable`. Nesting it silently does nothing, and the resulting bug looks like "my limit is being ignored." Also: proactive (`RemainingSteps` + routing) beats reactive (`try/except GraphRecursionError`) because the graph completes normally and the partial state is checkpointed.

### Q10 — Your fan-in node is seeing incomplete results from the fan-out. Diagnose.
**Answer:** Two candidates, in order. (1) Missing reducer — but that raises `InvalidUpdateError` on the parallel path, so if you're seeing silence it's (2) unequal branch lengths: the fan-in node's inbound edges were satisfied before the longer branch finished, so it ran on a partial channel. Fix is `add_node("synthesise", fn, defer=True)`, which delays execution until all pending tasks complete.
**Follow-up trap:** *"How would you have caught this in a test?"* — a test where one branch is deliberately slower and longer than the others, asserting the fan-in node observes exactly N results. Symmetric fixtures never trigger it, which is why it reaches production.

### Q11 — What belongs in graph state and what doesn't?
**Answer:** State goes in a checkpoint at every super-step, so it must be serialisable and small. In state: ids, decisions, small structured results, message history, counters. Not in state: DB connections and clients (not serialisable), full document text or 200KB tool payloads (checkpoint tax on every tick), secrets (checkpoints are plaintext unless you supply an `EncryptedSerializer`). Dependencies belong in **runtime context** (`context_schema` plus `Runtime[Ctx]`), which is not checkpointed; cross-thread facts belong in the `Store`.
**Follow-up trap:** *"What if you must hold a big object?"* — store it externally and keep the key in state. Failing that, `pickle_fallback=True` on `JsonPlusSerializer` handles types msgpack can't (pandas frames), but that's a smell. And note the security guidance: set `LANGGRAPH_STRICT_MSGPACK=true` or an explicit `allowed_msgpack_modules` list so a compromised checkpoint store can't achieve code execution through deserialisation.

### Q12 — Graph API or Functional API? TypedDict, dataclass, or Pydantic?
**Answer:** Graph API when the topology is the artifact — you want the generated diagram, static inspection, per-node policies, and streamable structure. Functional API (`@entrypoint`, `@task`) when you'd rather write imperative Python and just want durability; same runtime and checkpointer underneath, same `timeout=`/`retry_policy=` parameters. For state: `TypedDict` is the documented default; `dataclass` when you want defaults; Pydantic only when you need recursive validation, because it's explicitly slower and `create_agent` won't take it.
**Follow-up trap:** *"Which would you pick for a five-node linear pipeline?"* — neither. That's a function. Reaching for the Graph API for something with no branching, no cycles, and no resume requirement is the most common over-engineering in this space.

### Q13 — Design the streaming for a chat UI on top of this graph.
**Answer:** `stream_mode=["messages","updates","custom"]` with `version="v2"` so every chunk is a uniform `StreamPart` with `type`/`ns`/`data`. `messages` for token-by-token, filtered by `metadata["langgraph_node"]` so only the user-facing node streams; tag internal structured-output calls `nostream` so they run but don't emit. `updates` for a step-progress rail. `custom` via `get_stream_writer()` for tool progress ("retrieved 100/100 records"), which is also how you stream an LLM that isn't a LangChain integration. `subgraphs=True` and read `chunk["ns"]` to attribute nested output. On `>=1.2`, `stream_events(..., version="v3")` gives typed per-channel projections instead of discriminator branching.
**Follow-up trap:** *"What about Python 3.10 and async?"* — two real constraints. `get_stream_writer()` does not work in async nodes on Python < 3.11 (no `context` on asyncio tasks); take a `writer: StreamWriter` parameter instead. And you must pass `RunnableConfig` explicitly into `await model.ainvoke(msgs, config)` or callbacks don't propagate and token streaming silently produces nothing.

### Q14 — When would you use a subgraph instead of just more nodes?
**Answer:** Three reasons: reuse across graphs, independent team ownership behind a stable input/output schema, and context isolation for a subagent that shouldn't see the parent's whole message history. Wiring: pass the compiled graph to `add_node` if it shares state keys; wrap it in a node and translate both ways if the schemas differ.
**Follow-up trap:** *"What does the subgraph's `checkpointer` argument do?"* — three modes. `None` (default, per-invocation): inherits the parent's checkpointer for one call, supports `interrupt()`, no memory across calls, safe under parallel calls. `True` (per-thread): accumulates state across calls, gives it its own checkpoint history so you can time-travel inside it, and **breaks under parallel calls to the same subgraph** because both writes hit the same namespace. `False`: plain function call, no interrupts, no durable execution. Also: with an inherited checkpointer the parent sees the whole subgraph as one super-step, so you can't time-travel into it.

### Q15 — What does the graph abstraction actually buy you over the forty-line loop, honestly?
**Testing:** the senior signal. Enthusiasm loses here.
**Answer:** Three things, and only three. A checkpoint boundary at every super-step, which converts "restart" into "resume" — the arithmetic is that at 85% per-step reliability a 10-step run completes about 20% of the time, so resume is not a nicety. Declared merge semantics for parallel writes, which is genuinely hard to get right by hand and which the reducer model solves cleanly. And a topology that can be inspected, diagrammed from source, streamed, and given per-node retry/timeout/cache policies. For a simple loop it buys none of that meaningfully and costs you a framework in your stack trace, a state schema to maintain, and a migration every couple of quarters. The right framing is "a Pregel runtime plus a persistence layer around a loop I could write myself" — and knowing when not to pay for it.
**Follow-up trap:** *"So when would you pick Temporal instead?"* — when durability spans hours to days across multiple services, when you need cross-service compensation and mature in-flight workflow visibility, or when the org already runs it. LangGraph's advantage is that streaming, `interrupt()`, and time travel are built for this domain; Temporal's is a decade of operational maturity. Note that 1.2 added per-node timeouts, error handlers, and graceful drain — LangGraph moving toward Temporal, which tells you where the gap has been.

### Q16 — A node needs a database connection and the tenant id. Where do they go?
**Answer:** Runtime context. `StateGraph(State, context_schema=Ctx)`, then `graph.invoke(inp, context=Ctx(user_id=..., db=...))`, read via `runtime.context` in the node. Not state: state is serialised into a checkpoint at every super-step, a connection object isn't serialisable, and the tenant id shouldn't be duplicated into every checkpoint. Cross-thread durable facts (user preferences) go in the `Store`, namespaced by tenant, accessed via `runtime.store`.
**Follow-up trap:** *"What's the difference between the checkpointer and the store?"* — the checkpointer persists *this thread's* state, keyed by `thread_id`. The store persists arbitrary data *across* threads, namespaced by a tuple like `(user_id, "memories")`, with optional embedding-based semantic search. They're deliberately separate systems: thread state has different lifecycle, access pattern, and retention needs from long-term memory.

### Q17 — Your graph worked in dev and raises `InvalidUpdateError` in prod. What changed?
**Answer:** A path that never ran in dev ran in prod. Almost always one of: a conditional edge returned a list of two destinations for the first time; a node acquired a second outgoing static edge (which fans out in parallel, not sequentially); or a `Send` fan-out produced more than one item where the fixture produced one. The fix is the reducer, but the *lesson* is that the safe state schema is the one where every non-scalar channel has a declared reducer whether or not you currently write it in parallel.
**Follow-up trap:** *"How do you prevent the class of bug rather than this instance?"* — a startup assertion or unit test that walks the state schema and fails on any `list`/`dict`-typed key without an `Annotated` reducer. Plus a test that exercises every conditional edge's multi-destination return. Cheap, and it turns a production exception into a CI failure.

---

## Red flags that fail you

- Saying the default reducer "merges" or "appends." It overwrites.
- Not knowing what happens when two parallel nodes write the same unannotated key.
- Describing `Annotated[list, add]` as a typing detail rather than the fan-in contract.
- Using `operator.add` for messages and not knowing why `add_messages` exists.
- Quoting a default `recursion_limit` of 25 in 2026 (it's 1000 since 1.0.6).
- Putting `recursion_limit` inside `configurable` and not knowing it's ignored there.
- Mixing `Command(goto=...)` with static edges from the same node.
- Confusing "conditional edge returns a list" with `Send`.
- Fanning out with `Send` and no `max_concurrency`.
- Putting a DB connection or 200KB of document text in graph state.
- Calling LangGraph "the agent" rather than the runtime the agent runs on.
- Recommending LangGraph for a linear five-step pipeline.

---

## Cheat card

```
EXECUTION MODEL  Pregel (Google, 2010) bulk-synchronous message passing
  SUPER-STEP = one tick: all scheduled nodes run (parallel) → writes REDUCED → CHECKPOINT
  halt when no node has inbound messages, or recursion_limit trips

STATE = independent CHANNELS, one reducer each. reducer sig: (current, update) -> new
  no reducer         → LAST WRITE WINS; 2 writes in ONE super-step → InvalidUpdateError:
                       "Can receive only one value per step. Use an Annotated key..."
  Annotated[list, operator.add]        → concatenate (needed for ANY fan-in / Send)
  Annotated[list[AnyMessage], add_messages] → merge by message id + coerce dicts
  Overwrite(v)  (langgraph.types)      → bypass reducer; only ONE per key per super-step
  schema: TypedDict (default) > dataclass (defaults) > Pydantic (validates, SLOWER)

NODES  fn(state[, config][, runtime: Runtime[Ctx]]) -> partial update
  runtime: .context .store .stream_writer .execution_info.node_attempt .heartbeat()
  deps/connections → context_schema (NOT checkpointed).  big blobs → Store, keep id in state
  cache: CachePolicy(ttl=s) + compile(cache=InMemoryCache())

EDGES  add_edge · add_conditional_edges(node, fn[, mapping]) · START / END
  MULTIPLE static out-edges = PARALLEL fan-out (not sequential)
  Command(update=, goto=, graph=Command.PARENT, resume=) → must annotate Command[Literal[...]]
  Command ADDS a dynamic edge; static edges still fire. ONE mechanism per node.

Send("node", per_call_state[, timeout=])  ← return LIST from a conditional edge
  vs conditional edge returning ["a","b"] = different nodes, SAME state
  Send = SAME node N times, N DIFFERENT states
  REQUIRES a reducer on the fan-in channel · bound with config max_concurrency
  unequal branch lengths → add_node(..., defer=True) or fan-in fires early

LIMITS  recursion_limit default 1000 since langgraph 1.0.6 (was 25 for 2 years)
  TOP-LEVEL config key — inside "configurable" it is SILENTLY IGNORED
  → GraphRecursionError.  Prefer RemainingSteps managed value + route to wrap-up at <=2
  keep your OWN step/cost budget in state; 1000 super-steps is not a safety net

FAULT TOLERANCE (per node)  timeout → RetryPolicy → error_handler (in that order)
  RetryPolicy: max_attempts 3 · initial 0.5s · backoff ×2.0 · max 128s · jitter True
    default retry_on = any exc EXCEPT ValueError/TypeError/RuntimeError/OSError/...; httpx 5xx only
  timeout=TimeoutPolicy(run_timeout=, idle_timeout=) — ASYNC nodes only, >=1.2 alpha
  error_handler=(state, error: NodeError) -> Command  — Saga compensation, >=1.2 alpha
  interrupt() BYPASSES both

STREAM MODES  values · updates · messages · custom · checkpoints* · tasks* · debug*
  (*need a checkpointer)   version="v2" (>=1.1) = uniform StreamPart{type,ns,data}
  version="v3" on stream_events (1.2 beta) = typed projections .messages .values .interrupts
  filter tokens by metadata["langgraph_node"] / ["tags"]; tag "nostream" to suppress
  py<3.11 async: pass RunnableConfig to ainvoke; take writer: StreamWriter param

SUBGRAPHS  shared keys → add_node(compiled)  ·  different schemas → invoke() inside a node
  compile(checkpointer=None) per-invocation: interrupts YES, memory NO, parallel-safe YES
  compile(checkpointer=True) per-thread:     memory YES, parallel calls to SAME subgraph NO
  compile(checkpointer=False) stateless:     no interrupts, no durable execution
  inherited checkpointer → parent sees whole subgraph as ONE super-step (no inner time travel)

VERSIONS  1.0.0 2025-10-20 · 1.1.0 2026-03-10 (stream v2) · 1.2.0 2026-05-12
  1.2: per-node timeouts · error_handler · graceful drain (RunControl) · DeltaChannel beta · v3 events

WHEN NOT TO USE IT
  simple model→tool→model loop → 40 lines beats a framework. Say so.
  deterministic pipeline → write the function
  hours/days + cross-service compensation → Temporal / Restate, LLM calls as activities
```

## Sources

- [LangGraph — Graph API overview](https://docs.langchain.com/oss/python/langgraph/graph-api) — state, reducers, `Overwrite`, nodes, edges, `Send`, `Command`, recursion limit default 1000 since 1.0.6, `RemainingSteps`; accessed 2026-07-26
- [LangGraph — Use the graph API](https://docs.langchain.com/oss/python/langgraph/use-graph-api) — map-reduce with `Send`, `defer=True`, `max_concurrency`, conditional branching; accessed 2026-07-26
- [LangGraph — Persistence](https://docs.langchain.com/oss/python/langgraph/persistence) — super-steps, checkpoint counts, durability modes, `DeltaChannel`, serializer and `LANGGRAPH_STRICT_MSGPACK` guidance; accessed 2026-07-26
- [LangGraph — Streaming](https://docs.langchain.com/oss/python/langgraph/streaming) — seven stream modes, v1/v2/v3 formats, `GraphOutput`, Python <3.11 async constraints; accessed 2026-07-26
- [LangGraph — Fault tolerance](https://docs.langchain.com/oss/python/langgraph/fault-tolerance) — `RetryPolicy` defaults and `default_retry_on` exclusion list, `TimeoutPolicy`, `error_handler`, `NodeError`; accessed 2026-07-26
- [LangGraph — Subgraphs](https://docs.langchain.com/oss/python/langgraph/use-subgraphs) — persistence modes table, namespace isolation; accessed 2026-07-26
- [LangChain Python changelog](https://docs.langchain.com/oss/python/releases/changelog) — `langgraph` 1.0.0 (2025-10-20), 1.1.0 (2026-03-10), 1.2.0 (2026-05-12) contents; accessed 2026-07-26
- [Pregel: A System for Large-Scale Graph Processing](https://research.google/pubs/pregel-a-system-for-large-scale-graph-processing/) — the super-step model LangGraph cites; accessed 2026-07-26
- [langchain-ai/langgraph #2336 — "Can receive only one value per step"](https://github.com/langchain-ai/langgraph/issues/2336) — the error in the wild, on parallel branches; accessed 2026-07-26
- [250 LangGraph Interview Questions & Answers (2026)](https://rpabotsworld.com/langgraph-interview-questions/) — question phrasings actually used in screens; accessed 2026-07-26

## Changelog
- 2026-07-26 — created
