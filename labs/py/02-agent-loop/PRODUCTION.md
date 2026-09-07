# Production notes — the agent loop

## What you'd actually use

| Need | Tool | Note |
|---|---|---|
| The loop, hosted | LangGraph / OpenAI Agents SDK | You built the shape; these add checkpointing, tracing, streaming |
| Deterministic testing | `FakeLLM` pattern (kept) | Injection by script — every serious agent test suite is built on one |
| Tracing | LangSmith / OTel | The trace IS the debug surface for loop bugs |

## What production adds over yours

- **Real streaming** — tokens arrive before the turn is complete; dispatch happens on parsed tool-call boundaries, not after a full completion.
- **Checkpointing** — a long-running loop persists state per node so a crash resumes instead of restarting (and `interrupt()` replays the node, not the line).
- **Structured tool args** — model-emitted JSON is validated against the schema before dispatch; malformed args become observations, not exceptions.
- **Budgets everywhere** — step, token, wall-clock, and per-tool budgets, each with its own exhaustion policy.

## What breaks at scale

| Symptom | Cause | Fix |
|---|---|---|
| Loop oscillates between two tools | Observation includes the prior error; model repeats | Cap repeats, salt the prompt with attempt count |
| Works in demo, hangs in prod | No step budget on the model path | Step budget is non-negotiable, even on the "smart" model |
| Tokens vanish between turns | Context trimmed mid-loop | Explicit compaction trigger with a tested summary contract |
| One flaky tool kills the run | Exceptions propagate to the loop | Errors-as-observations (lab 04 builds the ledger version) |

## The one-liner to remember

The loop is `prompt → model → parse → dispatch → observe → repeat` with a
step budget; everything else is an optimization of one of those six verbs.
