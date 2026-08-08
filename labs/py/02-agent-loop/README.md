# Lab 02: The Agent Loop From Scratch

**Track:** T07 Agentic AI · **Time:** 3h · **XP:** 50
**Module:** `T07-agent-loop-from-scratch`

**You will build:** a dependency-free agent loop -- message passing, tool dispatch,
six stop conditions, budgets on a fake clock, and provably-safe context compaction --
driven entirely by a scripted fake model, so every test is deterministic and free.

**You will be able to answer:** *"Write the agent loop. What are the six ways it stops,
and how do you test the no-progress detector without burning API credits?"*

## Setup

```bash
cd labs/py/02-agent-loop
python -m venv .venv && . .venv/bin/activate     # or: uv venv && . .venv/bin/activate
pip install pytest                                # only dependency
```

## The spec

1. **`FakeModel`** -- plays back a fixed script of `ModelResponse` objects, one per
   call to `.next()`. No network, no API key, fully deterministic. `Message` carries
   `role`, `content`, and an `obligation` flag (survives compaction verbatim).
2. **`dispatch_tool(tools, call)`** -- validate against `ToolSpec.params`/`required`,
   then execute. **Never raises.** Unknown tool, missing arg, wrong type, and a
   handler exception all become `"ERROR: ..."` observation strings the loop appends
   to the transcript, never a Python exception that kills the run.
3. **Six stop conditions** (`StopReason` enum): `FINAL_ANSWER`, `MAX_STEPS`,
   `MAX_TOKENS`, `MAX_COST`, `DEADLINE`, `NO_PROGRESS`. The last one hashes
   `(tool_name, sorted(args.items()))` per call; on the **3rd** identical call the
   loop *intervenes* -- it does not dispatch that call, it injects a nudge
   observation instead and gives the model one more turn. A 4th identical call is a
   hard stop.
4. **Budgets** -- `Budget(max_steps, max_tokens, max_cost, deadline_seconds)`,
   all checked against `FakeClock`, never `time.sleep()`.
5. **`compact_context(messages, keep_last)`** -- shrinks a long transcript while
   *provably* preserving the original task and every `obligation=True` message:
   their exact text is guaranteed present, verbatim, in the output.

## Run the tests

```bash
pytest tests/ -v          # against starter/ → FAILS. Make them pass.
```

To check the reference: `pytest tests/ -v --solution`

## Stretch goals

1. **Parallel tool calls** -- let one `ModelResponse` carry a *list* of tool calls,
   dispatch them concurrently, and decide how repeats are hashed when calls happen
   in the same turn. *(Interview: "how do side effects interact with parallel tool
   calls?")*
2. **Real no-progress recovery** -- instead of a flat nudge string, feed the model a
   *diff* of what changed since the last identical call, so it has something new to
   reason about.
3. **Token-aware compaction** -- replace the message-count-based `keep_last` with a
   token budget, summarizing just enough of the middle to fit.
4. **Streaming budgets** -- adapt the loop so `max_tokens` can be checked mid-turn
   (partial token counts) rather than only after a full response returns.
