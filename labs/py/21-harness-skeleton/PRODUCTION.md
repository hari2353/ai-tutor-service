# Production notes — harness engineering

## The 15-component model, condensed

Your skeleton implements the load-bearing five. The full production harness
(Claude Code, Devin-style agents, OpenAI Assistants) layers on: streaming,
sandboxed execution, credential brokering, telemetry export, retry policies,
model routing, prompt caching keys, session persistence, multi-agent
delegation, and UI-facing event streams.

## What production adds

| Component | Production version |
|---|---|
| ContextWindow | Real tokenizers, prioritized eviction, prompt-cache-aware ordering |
| ToolRouter | JSON Schema validation, capability tokens, per-tool rate limits, sandboxing (containers, WASM) |
| Budgets | $-denominated cost ceilings, per-turn and per-task; token accounting from the API stream |
| Kill switch | Out-of-band cancellation (control plane), not in-loop flags — a stuck process can't check a flag |
| Event log | OTel spans with GenAI semantic conventions; the log IS the observability story |

## Failure modes

| Symptom | Cause | Fix |
|---|---|---|
| Agent runs forever "thinking" | No stop condition on plain replies / budgets | Every budget, every stop, tested |
| Compaction drops the system prompt | Pinned flag missing | Pin system + invariants; test under load |
| Destructive tool executed in a test | Approver defaulted to yes | Deny-by-default; approver must be explicit |
| Kill switch "didn't work" | Checked inside a long tool call | Check between turns; hard-kill path separately |
