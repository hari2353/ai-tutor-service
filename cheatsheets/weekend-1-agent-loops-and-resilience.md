# Weekend 1 — The Agent Loop, ReAct Family, and Resilience Patterns

This weekend decides interviews because "write me an agent loop" is the single fastest way an interviewer separates someone who has shipped an agent from someone who has only used one — and the resilience patterns underneath it are what stop that agent (or any service) from taking down production the first time a dependency wobbles.

## The Agent Loop From Scratch

**30-sec:** An agent is a loop around a stateless model: send full history + tool schemas, get back a final answer or a tool call, execute, append result, loop. That's ~40 lines. Everything hard is the four controls wrapped around it — stop condition, budget, context management, error handling. Frameworks give you those plus persistence; they don't give you the loop.

**The loop:** `messages[] → model(+tools) → tool_calls? no→DONE / yes→execute→append→loop`. Model is stateless — full context re-sent every turn, so **cost is quadratic in turns**.

**Stop conditions (need all six):** no tool call · step cap 10–25 · token budget · cost budget · wall-clock deadline · no-progress detector (hash `(tool,args)`, intervene at 3 repeats — this one fires most in production).

**Reliability math (know cold):** 0.95¹⁰≈60%, 0.85¹⁰≈20%, 0.95⁵⁰≈8%. Better models shift the exponent, not the shape — the fix is fewer steps + checkpoints + human-in-the-loop, not a smarter model.

**Error policy:** tool dependency fails → return a string to the model, it routes around it. Harness bug → crash loudly (model can't fix your `KeyError`). Every `execute()` path returns a readable string, never raises.

**Context, in order:** (1) truncate tool results at the tool boundary — highest leverage; (2) compact at ~70% window, recap old + keep recent verbatim, never compact `messages[0]`, the task, or open obligations; (3) externalise to file/store — survives compaction entirely.

**When NOT to use an agent:** steps known in advance → write the pipeline. One prompt suffices → use one prompt. Long-running/multi-party → durable workflow engine (Temporal/Step Functions).

**Idempotency:** every mutating tool takes a client-generated key; server stores `(key→result)`.

## ReAct, Plan-Execute, Reflexion, Tree-of-Thought

**30-sec:** Four answers to "when does the model decide what to do next?" ReAct decides after every observation (adaptive, quadratic context). Plan-and-Execute decides once up front (cheaper, parallelisable, but the plan can go stale). Reflexion decides again after a whole attempt fails, using a critique as memory — but only works with a **real external verdict** (tests, compiler, schema), not self-critique. ToT decides across parallel branches at 10–100× tokens. ReAct in 2026 is a structured `tool_use` API block, not regex on `Thought:/Action:` text.

**Decision rule:** later steps depend on earlier results → ReAct. Decomposition stable up front → Plan-Execute/ReWOO + a gate. Cheap external verdict exists → retry-with-critique, cap 2–3 attempts. No verdict → do **not** add self-critique (Huang, ICLR'24: intrinsic self-correction doesn't reliably help and can hurt).

**Verdict quality, best to worst:** compiler/tests/typecheck/schema/EXPLAIN > invariants + row-count bounds > a *different* model as judge > same-model "are you sure?" (near-worthless, can be harmful).

**Failure symptoms:** plan lock-in (plan_hash constant, replan_count==0) · degeneration (cos(reflect_k, reflect_k-1) > 0.9) · act-only drift (reasoning block dropped from history, repeats prior action) · fabricated observations (no matching tool log).

**Reasoning models** absorbed the "Thought" half of ReAct but not the Act/Observe half — that's still your harness's job (side effects, real verifiers, durable state, budgets).

## Resilience Catalogue: Timeout, Retry, Circuit Breaker, Bulkhead

**30-sec:** Four patterns compose in order: timeout bounds a single call, retry+jitter recovers from transient faults without a thundering herd, circuit breaker stops you hammering something that's actually down, bulkhead confines the blast radius. Retry without a timeout is unbounded latency; retry without a circuit breaker amplifies an outage (3 retries × a struggling service = 4× load exactly when it can least take it). None of it is safe unless the downstream call is idempotent.

**Order (outermost→innermost):** Bulkhead → Circuit Breaker → Retry → Timeout.

**Retryable:** connection errors, timeouts, 429, 502, 503, 504. **Not retryable:** 400, 401, 403, 404, 422.

**Jitter:** full jitter `sleep = rand(0, base·2^n)` is the default; decorrelated jitter `min(cap, rand(base, prev·3))` is best under contention.

**Fallback order:** stale cache > degraded response > default > queue-for-later > fast 503 + Retry-After.

## If you remember nothing else

1. The agent loop is ~40 lines; the four controls (stop, budget, context, errors) are the actual job.
2. Reliability is multiplicative: 0.85¹⁰ ≈ 20%. Fewer steps + checkpoints + HITL beat a better model.
3. A failing tool returns a string to the model; a harness bug crashes loudly. Never let a tool exception kill a 9-step run.
4. Context is re-sent whole every turn — cost is quadratic in turns; truncate at the tool, then compact, then externalise, in that order.
5. Self-critique without a real external verdict (tests/compiler/schema) doesn't reliably improve accuracy and can hurt.
6. Retry without a circuit breaker amplifies an outage; retry only idempotent, retryable errors.
7. Resilience pattern order is fixed: Bulkhead → Circuit Breaker → Retry → Timeout. If you only add one thing, add timeout.
8. Multi-agent/ToT-style branching costs 10–100× tokens — earn it with evidence, not by default.

## Numbers table

| Fact | Value |
|---|---|
| Step cap (typical) | 10–25 |
| No-progress intervention | 3 identical `(tool,args)` repeats |
| 0.95¹⁰ / 0.85¹⁰ / 0.95⁵⁰ | ≈60% / ≈20% / ≈8% |
| ToT/self-consistency token cost | 10–100× a single pass |
| Reflexion cap | 2–3 attempts, needs real verdict |
| Circuit breaker failure threshold | 50% |
| CB sliding window | 100 calls / 60s |
| CB minimum calls before tripping | 20 |
| CB wait duration open | 30s |
| CB permitted calls half-open | 5–10 |
| CB slow-call threshold | 50% over 2s |
| Timeout: connect | 1–3s |
| Timeout: read | ≈ p99 × 1.5 |
| Retry amplification | 3 attempts = 3× load; 2 retry layers = 9× |
| Fleet retry budget | ~10% of total requests |
| Bulkhead sizing | Little's Law: concurrency = throughput × latency, ×2 for burst |
