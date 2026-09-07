# Production notes — the agent loop anatomy

This lab isolates the *decision logic* of one turn. The real Claude Code loop makes the same decisions, but the machinery around them is where the engineering actually lives.

## What the real harness adds over yours

| Your lab | The real Claude Code |
|---|---|
| `build_context`: system + last-N history + user msg | **Context assembly**: system prompt (~4.2k tokens) → `CLAUDE.md` hierarchy (`~/.claude/CLAUDE.md`, project root, nested on demand) as *user* messages → `MEMORY.md` (first 200 lines / 25KB) → env info (cwd, platform, git state) → tool schemas (MCP names only, ~120 tokens, full schemas deferred behind tool search) → conversation history, every tool result appended in full |
| `parse_model_output(raw)` on a string | **Streaming tool-call blocks**: the model streams text and `tool_use` blocks in one response; the harness cannot know whether a turn is "text" or "tool" until the stream ends — which is why your stretch goal 3 exists. Partial JSON accumulates until a block closes |
| `resolve_tools` with a permission set | **Permission modes**: `default` (ask per risky action), `acceptEdits` (auto-approve file edits in the workspace), `plan` (read-only — your read-only rule, made into a whole mode), `bypassPermissions` (danger). Permissions bind to the *session*, tool, and resource, with `PreToolUse` hooks able to veto before execution — your stage 1 is a policy table; theirs is hook-gated and auditable |
| `execute_and_observe` returning a string | **What actually executes**: the model's `Edit` is a *diff*, applied by the harness (never the model) — with fuzzy matching, linter hooks (`PostToolUse` → prettier) rewriting the file after; `Bash` runs in a shell with sandboxing, network controls and output streaming back; big outputs are cleared in microcompaction long before your 10k-char cap would matter |
| `turn_loop` with `max_iterations` | Same idea, plus **compaction** (at ~89% of the window: `contextWindow − min(maxOutput, 20k) − 13k`), microcompact on every turn above the warning threshold, and thrashing detection that errors instead of looping when one giant read refills the window instantly |

## The loop, mechanically, in production

1. **Assemble.** Everything is re-sent every turn. The model is stateless; the flat token buffer *is* the memory. The system prompt never appears on your screen — the visibility asymmetry is the single most useful mental model.
2. **Stream.** The harness parses blocks as they arrive. Text renders live; a `tool_use` block's JSON arguments accumulate until complete. Your `parse_model_output` runs once per turn; theirs runs per *block*.
3. **Gate.** Permission check per call: mode (`default`/`acceptEdits`/`plan`), allow/deny rules, and `PreToolUse` hooks — any of which can deny, or inject `additionalContext` (which *is* visible to the model, unlike plain hook stdout).
4. **Execute.** The tool runs in the sandbox; the result is stringified and appended. **Diff application** is the notable one: the model emits a search/replace block, the harness does the write. Two extra guards yours lacks: timeouts per tool, and idempotency concerns for retried side effects.
5. **Verify.** The model runs tests/lint itself (`gather → act → verify`), which is what makes it an agent rather than a chatbot.
6. **Repeat until** the model emits text with no tool calls — your exact termination condition — or the iteration/token budget ends, or compaction reclaims space.

## What breaks at scale

| Symptom | Cause | Fix |
|---|---|---|
| "It forgot my instruction" | Said in chat, summarized away by compaction | Put durable rules in project-root `CLAUDE.md` (re-injected after compaction), not conversation |
| Quality degrades mid-session | Input length grows; effective capacity is ~60-70% of nominal | Schedule compaction; don't paste 400KB logs; scope file reads |
| Repeated "compacted" seconds apart | One enormous tool output refills the window instantly | Cap output size at the *tool* (your `max_output_chars`, but enforced before it ever enters the buffer); tail logs |
| Loops forever reading files | `max_iterations` too high, no token budget | Iteration cap + token-based stop; your lab caps iterations only — note the gap |
| Model edits the wrong file confidently | Stale tool results in context, no re-verify | The verify phase exists for this; harnesses that skip it are chatbots with extra steps |

## The 3 questions an interviewer asks

1. *"Is CLAUDE.md part of the system prompt?"* — No. It is injected as a *user* message after the system prompt. System-prompt-level text requires `--append-system-prompt` on every invocation. Naming this correctly is a shibboleth.
2. *"What does the model actually see when it reads a file?"* — Not the one line your terminal printed: the full file content as a tool result, in the buffer, re-sent every subsequent turn until compaction clears it. "Read auth.ts" is ~2.4k tokens per turn it survives.
3. *"Why do agent loops break at ~50k input tokens even on 200k windows?"* — Effective capacity is 60-70% of nominal; every model measured degrades with input length (MonitorBench: dangerous-action miss rates 2-30x with 800K of prepended benign activity). The loop must treat context as a budget, not a right.

The lab's five functions are the skeleton; production is the muscle around them. If you can say "here is where permissions gate, here is where the diff is applied, here is where compaction fires — and my lab isolates those decisions from the machinery," you have answered the interview question.
