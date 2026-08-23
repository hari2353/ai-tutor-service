# Loop Engineering: The Canonical Loop, Budgets, Compaction Triggers, Stop Conditions

> Sprint weekend 10 · source: `curriculum/07-agentic-ai/26-loop-engineering.md`

```
TWO TOKEN COUNTS (get this wrong and every budget bug follows)
  context_tokens  per-agent, in the window now  → drives COMPACTION, shrinks
  billed_tokens   per-RUN, everything ever paid → drives COST, only grows
  compaction lowers the 1st and RAISES the 2nd (summarizer call costs money)

BUDGET COMPOSITION ACROSS SUBAGENTS
  cost/tokens  additive + RESERVE before dispatch (check-then-spend = TOCTOU;
               N parallel children overshoot by up to N×)
  steps        TWO counters: local_steps (this loop) + tree_steps (whole run)
  deadline     ABSOLUTE monotonic timestamp, inherited. duration ⇒ 3 levels × 600s

9 STOP CONDITIONS
  verified natural term · local step cap · TREE step cap · billed-token budget
  cost budget · absolute deadline · no-progress · compaction circuit breaker
  external interrupt (cooperative, at a tool boundary)
  stop_reason distribution = your best dashboard
  cost_budget top reason ⇒ agent is broken, do NOT raise the cap

COMPACTION CASCADE (cheapest first; 4 of 5 cost zero API calls)
  1 tool-result budget  >50K chars → disk + 2KB preview + path      zero
  2 snip                stale scaffolding; MUST report tokens_freed  zero
  3 microcompact        cold: rewrite msgs (cache dead ~5min TTL)
                        hot:  cache_edits API-side, saves 100K+ prefix  zero
  4 context collapse    ~90% util, projection, REVERSIBLE            zero
  5 autocompact         ~87% util, fork summarizer, IRREVERSIBLE     1 call
  collapse ACTIVE ⇒ autocompact SUPPRESSED (they compete)
  freed tokens not credited to threshold ⇒ level 5 fires on stale usage
  post-compact recovery: last 5 files (≤5K ea) · skills (≤25K) · re-announce tools
  circuit breaker = 3   (1,279 sessions hit 50+ fails, worst 3,272, ~250K calls/day)
  token count: anchor on server `usage` + estimate delta → <5% err (vs 30%+ client)

PROGRESS = STATE DELTA, not arg hashes
  sig = (dirty_file_hashes, tests_passing, todos_closed, artifacts)
  K=4 nudge (name the absence) → K=7 shrink tool set → K=10 stop, escalate
  inject remaining {steps, seconds, usd} INTO context: temporal awareness is
    orthogonal to reasoning; it lets the model triage

INVARIANTS TO ASSERT
  messages[0] byte-stable      → else cache_read≈0, cost 5-10×
  1:1 tool_use ↔ tool_result   → else API 400 after partial failure/cancel
  thinking blocks preserved    → else silent reasoning degradation, no error
  task + open_items + persisted paths survive compaction
  context_tokens strictly ↓ after successful compaction
  replay(events[:k]) byte-identical  ← build this FIRST; precondition for resume
  no tool executes after stop_reason() is non-null

RESUMABLE
  typed append-only event log (not a message array) → derive messages from events
  deterministic rehydrate: logical clock, sorted everything, versioned templates,
    store RESOLVED file contents not paths
  checkpoint AFTER tool_result; idempotency key makes the gap safe
  HIBERNATE-AND-WAKE (task > 1 context window): handoff artifact must be
    sufficient alone. Test: kill process, fresh start, does it progress?

RELIABILITY MATH, 12 steps
  bare 0.90^12 = 28%  →  +errors-as-obs 0.94^12 = 48%  →  +no-progress ≈55%
  −compaction 0.94^8×0.85^4 = 32%   (compaction removes a FLOOR, no ceiling gain)
  +resume ≤2 retries, transient→0.036³: 0.976^12 = 75%   ← biggest single win
  +verifier: reported 75%→72% but TRUE-correct 67%→72%
  better model helps (0.98^12=79%) but does NOT remove 503s, turn-40 overflow,
    or false success claims

CLAUDE CODE REFERENCE NUMBERS
  1,729-line generator · 1,421-line while body · 9 named continue points
  budget checked TWICE per iteration (pre-call + post-call)
  streaming tool exec: 5 calls 30s → 18s (40%)
  stop_reason==='tool_use' is UNRELIABLE; watch for tool_use blocks

LOG PER ITERATION (top 2 fields: prompt_prefix_hash, transition_reason)
  alert on p99 steps + p99 cost (mean hides runaways), stop_reason shift,
  compaction cost as % of run cost, denied-call rate by tool

WHEN NOT TO
  short read-only task → step cap + deadline, done
  steps known → write the pipeline
  hours/days + exactly-once + day-long approvals → Temporal/Step Functions;
    keep loop POLICY, buy loop DURABILITY
```
