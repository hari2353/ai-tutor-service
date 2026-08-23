# The Agent Loop From Scratch (no framework)

> Sprint weekend 1 · source: `curriculum/07-agentic-ai/01-agent-loop-from-scratch.md`

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
