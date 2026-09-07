# Production notes — loop engineering

## The canonical loop's control plane

Every production agent loop (Claude Code, LangGraph's executor, OpenAI's
Assistants run loop) separates the *mechanism* of iteration from the *policy*
that ends it. Budgets are quantitative ceilings; stop conditions are semantic
detectors; compaction is a context-management strategy with a trigger. Mixing
them (an agent that "decides" when to stop inside its own prompt) is the
classic unbounded-loop incident.

## What production adds

| Component | Production version |
|---|---|
| Budgets | Real token accounting from API usage fields; $-cost ceilings; wallclock via monotonic + out-of-band kill |
| Compaction | Tokenizer-accurate; summarizer is itself an LLM call with its own budget; prompt-cache-aligned to avoid re-encoding |
| Stuck detection | Trajectory similarity (embedding of last-k tool calls), not just exact-match |
| Resume | Durable checkpointer (LangGraph) — your snapshot/restore is its toy form |
| Metrics | OTel spans per turn; cost/step and tools/turn are the two charts that matter |

## Failure modes

| Symptom | Cause | Fix |
|---|---|---|
| Agent loops forever, politely | No stuck detector; goal never trips | Exact-match stuck-k + trajectory divergence |
| Context "forgets" the task after compaction | Summary dropped the task statement | Pin task + invariants; test compaction preserves them |
| Budget trips silently mid-tool | Budget checked only between turns | Check before expensive ops too |
| Resume behaves differently | Snapshot missed a counter | Golden-trace test: resumed run must reproduce the trace |
