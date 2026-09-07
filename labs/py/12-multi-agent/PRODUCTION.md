# Production notes — multi-agent topologies

## What you'd actually use

| Topology | Framework | Notes |
|---|---|---|
| Supervisor | `langgraph-supervisor` | structured routing via `Command(goto=...)`; one routing node, one trace |
| Swarm / handoff | `langgraph-swarm`, OpenAI Agents SDK | `Command(goto=..., graph=Command.PARENT)`; SDK handoffs transfer **full history** |
| Orchestrator + subagents | Anthropic multi-agent Research | lead agent + `search`/`codex` subagents; checker validates, executor runs code |

## How the real ones do it

- **LangGraph supervisor.** Workers are nodes in an explicit `StateGraph`; the supervisor returns `Command(goto="worker", update={...})`. Routing is *structured output* (`with_structured_output(Route)`), never prose parsed with a regex. A hop budget (`MAX_HOPS`) terminates the router — without it you have an infinite loop with extra steps. What you built as `dispatch` is one hop; production's supervisor loops and synthesises.
- **Anthropic's multi-agent research system** (the "How we built our multi-agent research system" post): a lead agent decomposes the task, spawns parallel subagents, and — the key mechanism — each subagent works in an **isolated context** and returns a compressed summary, not its history. A checker-then-executor split: one agent verifies the other's plan/output before anything runs. They report beating single-agent Opus 4 by 90.2% on research tasks at ~15x token usage. That 15x is the honest price and the reason this is not the default.
- **Router.** Production routing is usually a *cheap classifier* (small model or fine-tuned) rather than a frontier-model prompt, because routing errors are a top failure mode and a classifier is measurable, cheap and fast.

## When NOT to — the honest table

| Condition | Use a topology? | Why |
|---|---|---|
| Parallel, read-heavy subtasks, small distilled returns | Yes | Anthropic's case: total info exceeds one window; branches independent |
| Mandatory context isolation (50k tokens must not pollute the main window) | Yes | the subagent is a token-spending device, nothing more |
| Different permission / trust tiers | Yes | split on blast radius, not cardinality — a tool that can spend money needs different guardrails |
| "The agent has too many tools" | No | fix descriptions, remove overlap, group, add tool search — splitting swaps a selection problem for a routing problem *plus* a handoff problem |
| "The org chart has four teams" | No | Conway's law is not an architecture; split on context/permission boundaries |
| Sequential task, shared evolving context | No | every handoff is lossy or expensive; one agent keeps the whole thread |
| Chasing "emergent" quality from debate | No | see below |

**Debate, honestly:** controlled follow-ups to the 2023 multiagent-debate papers find sycophantic conformity, contextual fragility and consensus collapse; 2-3x token cost for accuracy comparable to or worse than plain self-consistency (N independent samples + a vote). Your `Debate` class exists so you can *measure* that, not so you ship it. The variant that earns its keep is **asymmetric verification**: one checker with a different prompt and a checklist, run once — which is exactly Anthropic's checker/executor shape.

## What production adds over your classes

- **Durable state.** LangGraph checkpoints every step (`checkpointer=`): a run dies mid-pipeline, you resume from the last checkpoint instead of replaying 15x tokens. Your `Pipeline` trace is the data such a checkpointer would persist.
- **Retries.** Per-node retry policies with backoff, plus per-worker circuit breakers so one dead subagent doesn't burn the budget of every run. Your `Failure` per-worker containment is the shape of this; a real one adds tenacity-style `retry_on` and a breaker registry.
- **Subagent context isolation.** The whole point in production: a worker/subagent gets a fresh context window, a compressed task, and a return contract `{answer, evidence, confidence, tokens}`. The parent never sees the worker's tool spam; the worker never sees the parent's history. Your injected-callable design is the honest version of that boundary — `fn(task) -> result` *is* the seam, and the seam is where failures live.
- **Observability.** One trace id across every agent; route distribution and route-accuracy metrics; handoff count per run (rising handoffs = ping-pong). MAST (arXiv:2503.13657) annotates 1,600+ traces across 7 frameworks; the dominant failures are **system design** and **inter-agent misalignment** — the seams you just built, not the models.

## The 3 questions an interviewer asks after this lab

1. *"Your supervisor's broadcast caught the exception. What did you lose?"* — the worker's side effects may have half-applied; catching the exception is not rolling back the world. Production wraps workers in transactions or makes them idempotent.
2. *"Why is the blackboard round-capped at 3?"* — non-convergence. Agents that keep proposing updates forever are the conversational equivalent of a group chat that never terminates; the cap turns a hang into a bounded, observable result.
3. *"A single agent with all five workers as tools would also pass these tests. Why build the topologies at all?"* — because the topologies exist for the cases where they're the only shape that works: context isolation, permission tiers, parallel breadth. When none of those apply, the single agent wins, and your stretch goal 4 is the eval that proves it.
