# LangGraph I: StateGraph, Reducers, Conditional Edges, Send

> Sprint weekend 2 · source: `curriculum/07-agentic-ai/06-langgraph-core.md`

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
