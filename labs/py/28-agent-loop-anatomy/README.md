# Lab 28: Agent Loop Anatomy — One User Turn, Dissected

**Track:** T28 AI-Assisted Architecture (Claude) · **Time:** 2h · **XP:** 50
**Module:** `T28-claude-code-model`

**You will build:** one file (`anatomy.py`) that dissects a Claude-Code-style agent turn as five pure functions — tool resolution by permission, context assembly with history trimming, model-output parsing, tool execution with truncation and error observations, and the full turn loop with an iteration cap — simulated end to end with a scripted fake model, no LLM.

**You will be able to answer:** *"Walk me through what actually happens between my prompt and Claude's reply in an agentic tool — every stage, and what the harness adds around the model."*

## Setup

```bash
cd labs/py/28-agent-loop-anatomy
python -m venv .venv && . .venv/bin/activate     # or: uv venv && . .venv/bin/activate
pip install pytest                                # only dependency
```

## The spec

1. **`resolve_tools(user_msg, available_tools, permissions)`** — the subset of tools allowed for this message, order preserved. A tool is **read-only** (name contains `read`, `search`, `glob`, `list`, `grep`, or `find`) → always allowed. **Execute** (name exactly `bash` or `execute`) → needs `"execute"` in `permissions`. **Write** (name exactly one of `write`, `edit`, `delete`, `save`, `create`, `mkdir`, `apply_patch`, `patch`, `move`, `rename`) → needs `"write"` in `permissions`. Anything else is **unknown** → excluded, whatever the permissions.
2. **`build_context(user_msg, system_prompt, history, max_history)`** — the message list sent to the model: system prompt first, then the *last* `max_history` history messages (older ones trimmed), then the user message last. Ordering is the contract.
3. **`parse_model_output(raw)`** — a dict. `"TOOL: name {json}"` → `{"type": "tool_use", "tool": name, "args": <parsed dict>}`; any non-empty plain string → `{"type": "text", "text": raw}`; unparseable JSON after `TOOL:` or an empty/whitespace string → `{"type": "invalid"}`.
4. **`execute_and_observe(tool_call, tool_fns, limits)`** — run the tool, return a string observation. Enforcement: output longer than `limits["max_output_chars"]` is truncated to the limit with a marker `" [truncated N chars]"` where N is the chars dropped; a tool that raises returns `"error: ..."` instead of crashing; a tool not in `tool_fns` returns `"error: unknown tool"`.
5. **`turn_loop(user_msg, fake_model, tool_fns, config)`** — the full turn. Builds context (system prompt from `config["system_prompt"]`, history from `config["history"]`, trimmed to `config["max_history"]`), calls `fake_model(context)` → raw string, parses it. `tool_use` → execute, append the observation to history, loop. `text` → done, that's the final answer. Caps at `config["max_iterations"]` model calls. `invalid` output → treat like a parse failure the loop survives: append an observation, keep going. Returns `{"final_text": str, "iterations": int, "history": list}` — history includes the user message, every observation, and the final text.

## Run the tests

```bash
pytest tests/ -q          # against starter/ → FAILS. Make them pass.
```

To check the reference: `pytest tests/ -q --solution`

## Stretch goals

1. **Resolve per-iteration, not per-turn** — re-resolve the tool list between model calls using the observation history, so a read-then-write workflow can *earn* write permission mid-turn. *(Interview: "when should permissions be evaluated — session start or per call?")*
2. **Token-budget context** — estimate tokens (chars/4) and trim oldest history under a budget rather than a message count; note the difference from Claude Code's 89%-window compaction trigger. *(Interview: "why is trimming by count wrong at scale?")*
3. **Streaming parse** — feed `parse_model_output` a list of chunks and assemble before parsing; observe why the decision can't be made until the stream ends. *(Interview: "what changes in the loop when the model streams?")*
4. **Stop conditions** — a callable `(observation) -> bool` that halts on a dangerous pattern (e.g. `rm -rf`) before the next iteration. *(Interview: "where do safety hooks sit in the loop?")*
