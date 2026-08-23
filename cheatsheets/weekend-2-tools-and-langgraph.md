# Weekend 2 — Tool Engineering and LangGraph

This weekend decides interviews because "your agent has 40 tools and picks the wrong one" and "how does your agent survive a pod eviction at step 7" are the two questions that separate people who've built the harness from people who've only called an SDK.

## Tool Engineering: Schemas, Errors, Idempotency, Sandboxing

**30-sec:** A tool is a contract between a deterministic system and a non-deterministic one — the description field *is* prompt engineering, the JSON Schema is only half the spec. Reliability, in order: consolidate tools to match a human-recognisable task, not a REST endpoint; name/parameterise unambiguously; truncate and shape results **at the tool boundary**; return errors as actionable observations. On top: idempotency keys, explicit risk tiers, real sandboxing (microVM, not container). Selection degrades measurably past ~10–20 tools — Berkeley Function Calling data shows accuracy collapsing from 43% to 2% going from 4 to 51 tools.

**Consolidate:** `list_users+list_events+create_event → schedule_event`. Test: can you name the *human* task? `list_contacts` fails, `search_contacts` passes.

**Description = prompt, not docs:** state what it's for, when NOT to use it, query grammar, "empty result is not an error." Description-only refinements have pushed tools to SOTA on SWE-bench Verified.

**Params:** `user_id` > `user`; enums > free strings; semantic IDs > UUIDs (fewer hallucinations); 1–5 realistic input examples lift complex-param accuracy 72%→90%.

**Errors as observations, never exceptions:** unknown tool → did-you-mean + list. 429 → retry_after + "do something else first." 403 → "do not retry; tell the user what approval is needed." "No results" is success, not an error — otherwise infinite identical retries.

**Idempotency:** the harness supplies the key, never the model (the model regenerates on retry). Server: `INSERT ... ON CONFLICT DO NOTHING` + check rowcount — read-then-write races.

**Risk tiers**, enforced in the dispatcher: read_only · write_reversible · write_external · financial · destructive. Unknown tool name = most dangerous, fail closed. MCP annotations are self-asserted hints, never your security boundary.

**Sandbox:** in-process exec never; container is insufficient (shared kernel); microVM (Firecracker/Kata) is the production answer — ~125ms boot, <5 MiB/VM. Isolation without egress control is an exfiltration channel.

## LangGraph I: StateGraph, Reducers, Conditional Edges, Send

**30-sec:** LangGraph is a Pregel-style bulk-synchronous message-passing runtime wearing a graph API. State is typed channels, each with a reducer for concurrent writes; nodes are functions returning partial updates; edges route statically or dynamically; `Send` fans a routing function out to N dynamic copies of a node with per-copy state. Execution proceeds in super-steps — everything scheduled runs, writes reduce, checkpoint. For a plain `model→tool→model` loop it buys almost nothing — say so.

**Reducers:** no reducer → last-write-wins, and two writes to the same key in one super-step raises `InvalidUpdateError`. `Annotated[list, operator.add]` concatenates — required for any fan-in or `Send`.

**`Send`** requires a reducer on the fan-in channel; it means the *same* node run N times with N different states (different from a conditional edge returning a list, which routes to different nodes with the same state).

**Recursion limit:** default 1000 (was 25 for two years, changed in 1.0.6) — a top-level config key; silently ignored if nested inside `"configurable"`.

**Fault tolerance per node, in order:** timeout → `RetryPolicy` (max_attempts 3, backoff ×2.0, jitter) → `error_handler`. `interrupt()` bypasses both.

## LangGraph II: Checkpointers, interrupt()/HITL, Durable Resume

**30-sec:** A checkpointer writes a snapshot of every channel at every super-step, keyed by `thread_id`. That one mechanism is durable resume, HITL, time travel, and fault tolerance, all the same feature — because at 0.85¹⁰≈20% per-run success, 80% of runs fail somewhere and un-checkpointed retries pay for the whole trajectory again. `interrupt()` pauses a node indefinitely, resumed with `Command(resume=value)`. The interview trap: **resume restarts the node from its first line**, so any side effect before the interrupt re-executes — idempotency keys become a correctness requirement, not a nicety. `InMemorySaver` is a dict in a process; it dies on deploy, eviction, or a second replica.

**Implementations:** `InMemorySaver` (dev only) · `SqliteSaver` (dev/single-node) · `PostgresSaver` (production) · `ShallowPostgres` (latest checkpoint only, no time travel).

**Time travel:** `get_state_history` (reverse chronological). Replay re-executes nodes (LLM calls fire again). Fork writes a new checkpoint via `update_state`, original history intact — values pass through reducers, so `add` accumulates; use `Overwrite` to replace.

**LangGraph = at-least-once.** Exactly-once is the downstream system's property, achieved via idempotency keys, not the checkpointer.

## If you remember nothing else

1. Tool selection accuracy collapses from 43% to 2% between 4 and 51 tools (BFCL) — consolidate before you scale up tool count.
2. The tool description is prompt engineering, not documentation — it's the highest-leverage lever you have.
3. Errors are observations, not exceptions: 403 = don't retry, tell the user; "no results" = success.
4. Idempotency keys are supplied by the harness, never the model, and checked via `INSERT ... ON CONFLICT DO NOTHING`.
5. `interrupt()` re-executes the whole node from the top on resume — every side effect before it must be idempotent.
6. LangGraph buys persistence/checkpointing, HITL, and observability — it does not give you the loop, which is ~40 lines regardless.
7. `InMemorySaver` is a dev-only dict that dies on deploy or a second replica; use `PostgresSaver` in production.
8. LangGraph is at-least-once; exactly-once is a property you build downstream with idempotency keys.

## Numbers table

| Fact | Value |
|---|---|
| Tool selection accuracy collapse (BFCL) | 43% → 2% (4 → 51 tools) |
| Tool description refinement → complex-param accuracy | 72% → 90% (with examples) |
| Claude Code default tool response cap | 25,000 tokens |
| Firecracker microVM boot time | ~125ms, <5 MiB/VM, up to 150 VMs/sec/host |
| LangGraph recursion_limit default | 1000 (was 25 pre-1.0.6) |
| RetryPolicy defaults | max_attempts 3, initial 0.5s, backoff ×2.0, max 128s |
| Reliability at 10 steps, 85%/step | ≈20% (why checkpointing matters) |
| Retry-cost multiplier without checkpointing | ~5× expected cost per success |
| Idempotency key TTL | > max retry window (days, if human approval gate) |
| Tool Search token savings (Anthropic) | ~85% cut vs loading all tool defs upfront |
| Programmatic Tool Calling token savings | 37% general, ~98.7% for code-as-MCP cases |
