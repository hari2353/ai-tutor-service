# Production notes -- the agent loop

## What you'd actually use

| Concern | Roll-your-own (this lab) | Production reach-for |
|---|---|---|
| Loop + message passing | ~40 lines | Same shape, but the model client is real (OpenAI/Anthropic SDK) |
| Tool schema validation | `isinstance` checks | JSON Schema / Pydantic, so the model's declared schema and your validator can't drift apart |
| Stop conditions | in-process enum | Same idea, but persisted so a crashed process can resume mid-run |
| Budgets | in-memory counters | Metered against a billing account, enforced server-side too (client-side budgets are advisory) |
| Context compaction | message-count heuristic | Token-aware, usually an LLM call itself ("summarize everything except the last N turns and any open TODOs") |
| Durable state | none -- lost on crash | LangGraph checkpoints / a database row per run, so a restart resumes instead of starting over |

## What the real ones add over yours

- **Real schema validation, not `isinstance`.** Production tool schemas are JSON
  Schema (nested objects, enums, min/max, regex patterns). `isinstance` catches
  "wrong Python type" but not "string doesn't match the enum of valid currency
  codes" -- that gap is exactly where a model hallucinates a plausible-looking but
  invalid argument.
- **Persisted stop state.** If the process crashes at step 30 of 50, you want to
  resume from step 30, not step 0 and not silently lose the budget already spent.
  That means every step (message + budget delta) gets written somewhere durable
  before the next model call, not held only in a Python list.
- **Compaction that's actually a model call.** A message-count heuristic is fine for
  a lab; production compaction almost always calls the model itself to summarize the
  middle, because a hand-written truncation rule cannot know which of 40 tool
  results turned out to matter for the final answer.
- **Cross-run no-progress detection.** This lab detects repeats *within one run*.
  Production agents track it across an entire session, and some escalate to a human
  rather than a canned nudge string after the second intervention fails.
- **Token counting that matches the real tokenizer.** `response.tokens` here is a
  number you hand-wave in a test. Production code counts with the actual model's
  tokenizer (or trusts the API's `usage` field) -- a naive `len(text.split())`
  estimate is routinely 30-50% off and either burns budget headroom you didn't have
  or trips the budget early.

## What breaks at scale

| Symptom | Cause | Fix |
|---|---|---|
| Agent loops for 400 steps overnight, five-figure bill | No step/cost budget, or a budget that's advisory-only client-side | Enforce budgets server-side (API key spend caps), not just in the loop |
| Agent repeats the same failing call forever | No no-progress detector, or one that's too lenient | Hash `(tool, args)`, intervene early (this lab uses 3) |
| Context silently drops the original ask by turn 50 | Naive truncation (drop oldest N messages) | Compaction that provably preserves the task + open obligations, as in this lab |
| A transient tool failure ends the whole run | Tool errors raised as exceptions instead of returned as observations | `dispatch_tool` never raises -- errors become text the model can react to |
| Two tool calls with equivalent-but-differently-ordered kwargs are treated as different | Hashing the raw dict (or its repr) instead of a sorted canonical form | `hash_call` sorts `args.items()` before hashing |
| Budget check happens after the expensive call already ran | Checking budgets only post-hoc | Check step/deadline budgets *before* the model call; check token/cost budgets right after, before doing any more work |

## Cost & latency

A single unnecessary extra tool-call round trip on GPT-4-class pricing is often
$0.01-0.05 and 1-3 seconds of latency -- trivial per call, but a no-progress loop
that runs 20 extra turns before a step-budget catches it is real money on every
single request, multiplied by traffic. The step budget and the no-progress detector
are the two cheapest guardrails you can add and they are the ones most frequently
missing from a first agent implementation.

## The 3 questions an interviewer asks after you describe this

1. *"Your no-progress detector hashes exact argument equality. What if the model
   calls the same tool with semantically-identical but textually different
   arguments (`{"q": "cats"}` vs `{"query": "cats"}`)?"* -- exact-match hashing is a
   floor, not a ceiling; a stronger version needs semantic similarity on args, which
   is itself a model call and a cost/latency trade-off.
2. *"Where do budgets actually get enforced -- client or server?"* -- both. Client-
   side budgets give fast, cheap, in-process stopping; server-side (API rate limits,
   spend caps) are the real backstop because a client budget only helps if the code
   enforcing it is actually running.
3. *"What happens to an open obligation if the run hits MAX_STEPS before it's
   resolved?"* -- this is the difference between a toy and a production agent: the
   obligation needs to surface to whatever consumes the `AgentResult` (a human, a
   retry policy, a ticket), not silently vanish because the loop ended.
