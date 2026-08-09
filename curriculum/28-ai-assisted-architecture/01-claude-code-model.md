# The Claude Code Model: What the Agent Actually Sees

> **Track:** T28 AI-Assisted Architecture · **Time:** 2h · **Prereqs:** `T07-harness-engineering`, `T07-context-engineering` · **Updated:** 2026-07-26
> **Module id:** `T28-claude-code-model` · **Tags:** foundations, critical
> **Lab:** none yet — see `labs/py/02-agent-loop/` for the pattern if you want to build one

## The 30-second version

An agentic coding tool is a `while` loop around a stateless model: gather context, take action, verify, repeat, with every tool result appended to a single flat token buffer that is re-sent in full on every turn. The three things that explain almost all surprising behaviour are (a) the terminal and the context window show you different things, so a one-line "Read auth.ts" in your terminal is 2,400 tokens in the model's window and a 4,200-token system prompt you never see is already there, (b) quality degrades with input length well before the window is full, with effective capacity roughly 60-70% of nominal, and (c) compaction is destructive: it replaces verbatim history with a summary, and the things it drops are exactly the things you assumed were remembered. "It forgot my instruction" is almost never a model failure; it is either an instruction that was only ever in conversation history and got summarized away, or an instruction that was present and lost an attention contest against a fresher, more concrete objective. The design consequence: treat the context window as a budget you author, and treat anything you would be upset to see violated as a hook or CI gate rather than a sentence.

## Why this gets asked

Because the interviewer has watched somebody debug a "model regression" for two days that was actually a 400KB test log pushing the session through three compactions. The signal they are hunting for is whether you understand the harness as a system with a resource budget, failure modes, and observable symptoms, or whether you treat it as a magic box that is sometimes in a bad mood. There is also a hard hiring reason: 2026 interview loops now put you in the harness on purpose. Google replaced one coding round with a Code Comprehension round in May 2026, where you get a 200-500 line unfamiliar codebase in CoderPad, 60 minutes, and Gemini as an assistant. Meta rolled out AI-enabled coding interviews from late 2025 and lets candidates pick the model. Canva rewrote its problems specifically so a single prompt cannot solve them. In all three, the thing being scored is your judgment about the tool, and the fastest way to fail is to be surprised by the tool's mechanics on camera.

---

## Lineage: past → present → future

**What came before.** Two dead approaches, both killed by specific pain. The first was inline completion, 2021 through mid-2024: the model saw the current file plus a few heuristically-retrieved neighbours, and produced tokens. The pain that killed it was that it could not act, so it could not verify. Every correctness question came back to the human, and the human was the bottleneck the tool was supposed to relieve. The second was the retrieval-first chatbot era, roughly 2023-2024, where the harness pre-computed an embedding index of the repository and stuffed the top-k chunks into the prompt. That died of two things: index staleness (the embedding was built before your last four commits, so the model reasoned about code that no longer existed) and the fact that chunk-level similarity is a terrible proxy for "which files does this change touch." The replacement is what Anthropic calls agentic search: no index, the model runs `grep`, `glob`, and `read` itself and follows imports the way a human would. It is slower per query and enormously more accurate, because the filesystem is the ground truth and it is never stale. Cursor still runs a codebase index, which is a genuine live disagreement rather than a legacy artifact, and the tradeoff is real: indexing is faster on "where is X" and worse on "what breaks if I change X."

**Where it stands now.** The consensus architecture is a harness of three parts: a tool set, a context manager, and an execution environment, wrapped around a model that is itself stateless. Anthropic's own framing is that the loop has three phases (gather context, take action, verify results) that blend rather than sequence, with the human able to interrupt at any point. Tools cluster into five categories: file operations, search, execution, web, and code intelligence. What is genuinely contested is context management. The Extract pattern (summarize and replace, destructively) is used by six of the seven major agents surveyed in April 2026; OpenHands is the outlier with an append-only event store where compaction marks events suppressed rather than deleted, making it reversible and auditable. Trigger thresholds vary by a factor of two: Gemini CLI compacts at ~50% of the window, Claude Code at ~89% (`contextWindow − min(maxOutput, 20k) − 13k`), Codex CLI at ~90% (`model_auto_compact_token_limit`, 180k-244k depending on model, configurable downward only), OpenCode at 96-99%. That spread is not sloppiness, it is a real disagreement about whether frequent small information losses beat rare catastrophic ones. The second live disagreement is whether long context makes compaction obsolete, and the evidence says no: Chroma's study across 18 frontier models found every one degrades as input length grows, a 200K window shows serious accuracy loss by 50K tokens of input, and effective capacity is commonly 60-70% of nominal. MonitorBench is the sharpest version of this: Opus 4.6, GPT 5.4, and Gemini 3.1 all miss dangerous actions **2× to 30× more often** when 800K tokens of benign activity are prepended to the same transcript. Bigger windows move the cliff; they do not remove it.

**Where it's heading.** **High confidence: compaction becomes a first-class, configurable API surface rather than a client-side hack.** It already has: Anthropic's server-side `compact_20260112` strategy (beta header `compact-2026-01-12`) exposes a trigger threshold, custom summarization `instructions`, and `pause_after_compaction` so you can re-inject preserved messages after the summary, and it reports per-iteration token usage so you can bill it correctly. Expect the same for tool-result eviction. **High confidence: tool schemas stop being loaded eagerly.** Claude Code already defers MCP tool schemas by default, listing names only (~120 tokens) and loading full schemas on demand via tool search; `ENABLE_TOOL_SEARCH=auto` loads upfront only if they fit in 10% of the window. Anything that grows linearly with your integrations will get this treatment. **Medium confidence: cache-preserving compaction.** MIT and Harvard published Fast KV Compaction via Attention Matching in February 2026, constructing a smaller KV set that matches the full set's attention outputs without emitting summary tokens, which would preserve cache continuity and remove the cold-start penalty. That is a research result, not a product. **Speculative: the Extract-versus-event-store split resolves in favour of event stores** once audit requirements arrive in regulated deployments. State that as a guess if you say it.

---

## Mental model

The harness is a token budget with a `while` loop bolted to it. Two diagrams carry the whole module.

**One: the loop, and what is actually re-sent.**

```
  YOU: "fix the 401 after token refresh"
        │
        ▼
  ┌─────────────────────────────────────────────────────────────┐
  │  every turn, the ENTIRE buffer is re-sent to a stateless    │
  │  model. there is no "memory". there is only this array:     │
  │                                                             │
  │  [ system prompt ][ CLAUDE.md ][ MEMORY.md ][ env ]         │
  │  [ your msg ][ tool_use ][ tool_result ] × N ...            │
  └─────────────────────────────────────────────────────────────┘
        │  GATHER          take ACTION           VERIFY
        │  grep/glob/read  edit/write/bash       test/lint/typecheck
        └──────────────────────┬────────────────────┘
                               │ every result APPENDS
                               ▼
                    buffer grows monotonically until
                    something evicts or summarizes it
```

**Two: the visibility asymmetry, which is the single most useful idea here.** What your terminal shows and what the model holds are different sets, and the mismatch runs in *both* directions.

```
                  IN CONTEXT?      ON YOUR SCREEN?
  system prompt      YES (4.2k)        never
  MEMORY.md          YES (~680)        never   (first 200 lines / 25KB)
  env + git state    YES (~280)        never
  MCP tool names     YES (~120)        never   (schemas deferred)
  skill listing      YES (~450)        never   (1% of window budget)
  ~/.claude/CLAUDE.md YES (~320)       never
  project CLAUDE.md  YES (~1.8k)       never
  ──────────────────────────────────────────── ~7.8k before you type
  Read auth.ts       YES (2.4k)        ONE LINE  ← the big one
  grep results       YES (~600)        ONE LINE
  npm test output    YES (1.2k)        pass count only
  hook stdout        NO (debug log)    never   ← unless additionalContext
  hook additionalContext YES           never
  Claude's analysis  YES               YES
  subagent's file reads NO (6.1k in its own window) never
  subagent's summary YES (420)         brief
```

Read that table twice. **Almost everything expensive is invisible, and one thing that looks like it is in context (plain hook stdout on exit 0) is not.** Every "why is it out of context already" question and every "why did it ignore my hook" question is answered by this table.

---

## How it actually works

### The startup budget, in tokens

Claude Code's own interactive context-window simulation gives concrete numbers for a session on a 200,000-token window. Before you type a character:

| Loaded automatically | Tokens | Visible to you |
|---|---|---|
| System prompt (behaviour, tool use, formatting) | 4,200 | no |
| Auto memory `MEMORY.md` (first 200 lines or 25KB) | 680 | no |
| Environment info (cwd, platform, shell, OS, is-git-repo) | 280 | no |
| MCP tool *names* (schemas deferred) | 120 | no |
| Skill listing (names + descriptions) | 450 | no |
| `~/.claude/CLAUDE.md` | 320 | no |
| Project `CLAUDE.md` | 1,800 | no |
| **Total floor** | **~7,850 (≈3.9%)** | |

Then the work. A single realistic bug fix in that simulation: `auth.ts` 2,400 · `tokens.ts` 1,100 · a path-scoped rule that auto-loaded because a matching file was read 380 · `middleware.ts` 1,800 · `auth.test.ts` 1,600 · another path rule 290 · one `grep` 600 · analysis 800 · two edits 1,000 · two prettier hooks 220 · `npm test` output 1,200 · summary 400. Roughly **12,000 tokens for one small fix**, of which **~7,500 is file content.** The operational rule falls straight out: *file reads dominate.* "Fix the bug in `src/api/auth.ts`" is not politeness, it is a 5-10× reduction in context consumed per turn versus "fix the auth bug", because vague prompts make the agent read its way to the file.

### Why "it forgot" is four different bugs

Say "it forgot my instruction" in an interview and you will be asked which mechanism. There are four, and the fixes are different:

| Mechanism | What actually happened | Symptom you would see | Fix |
|---|---|---|---|
| **Never persisted** | You said it in chat on turn 3. Compaction summarized turns 1-40. | Instruction reappears in your `/rewind` transcript but not in behaviour | Put it in `CLAUDE.md` (project-root CLAUDE.md is re-read from disk and re-injected after `/compact`) |
| **Not re-injected** | It was in a nested `subdir/CLAUDE.md`, which is loaded on demand, not at launch, and is **not** re-injected after compaction | Behaves correctly while working in that subdir, drifts after a compaction until it reads a file there again | Hoist to project root, or `.claude/rules/` with `paths:` |
| **Present but outranked** | It is in context and the model chose a different approach. Instruction files are *context, not enforced configuration* | `/context` shows the file loaded under **Memory files**; behaviour still wrong | Make it specific and verifiable, or escalate to a `PreToolUse` hook |
| **Contradicted** | Two `CLAUDE.md` files in the hierarchy disagree; the model picks one arbitrarily | Nondeterministic: correct in some sessions, not others | Audit the hierarchy; `claudeMdExcludes` for other teams' files in a monorepo |

One correction worth carrying, because plenty of blog posts get it wrong: **`CLAUDE.md` content is delivered as a user message after the system prompt, not as part of the system prompt itself.** If you actually need system-prompt-level text, that is `--append-system-prompt`, which must be passed on every invocation and is therefore a scripting tool, not an interactive one.

### Compaction, mechanically

Claude Code runs a tiered defence rather than one big summarizer:

1. **Microcompact.** No model call, no summary. Fires on every turn above a warning threshold and drops stale tool results the model no longer needs. Cheapest possible intervention; you will not notice it.
2. **Tool-output clearing.** Older tool outputs go first, preserving conversation structure. This is why the *shape* of your session survives even when the *evidence* does not.
3. **Full LLM summarization.** The Extract pattern. Triggers around 89% of the window (`contextWindow − min(maxOutput, 20k) − 13k`). Replaces earlier turns with a structured summary.
4. **Thrashing detection.** If a single file or tool output is so large that context refills immediately after each summary, Claude Code stops auto-compacting after a few attempts and errors instead of looping. Observable symptom: repeated "Conversation compacted" messages seconds apart, then a hard error. Cause is almost always one enormous read (a lockfile, a minified bundle, a 400KB test log).

What survives, and what does not, is the part to memorize:

```
SURVIVES compaction
  your requests and intent · key technical concepts · files examined/modified
  with important snippets · errors and how they were fixed · pending tasks
  project-root CLAUDE.md   (re-read from disk and re-injected)
  invoked skills           (most recent invocation of each, first 5,000 tokens
                            each, sharing a 25,000-token budget, filled from
                            the most recent backwards)

LOST
  verbatim tool output · intermediate reasoning · the exact code it read
  the SKILL LISTING itself (not re-injected; only skills you invoked persist)
  nested subdirectory CLAUDE.md (reloads only on next read in that dir)
  anything you only said in conversation
```

The skill-listing detail catches people: after a compaction, the model may no longer know a skill exists unless it already used it.

**The server-side API version**, if you are building your own harness rather than driving Claude Code:

```python
# runs. requires anthropic>=0.7x and the compaction beta.
import anthropic
client = anthropic.Anthropic()
messages = [{"role": "user", "content": "Help me refactor this service"}]

resp = client.beta.messages.create(
    betas=["compact-2026-01-12"],
    model="claude-opus-5",
    max_tokens=4096,
    messages=messages,
    context_management={"edits": [{
        "type": "compact_20260112",
        "trigger": {"type": "input_tokens", "value": 150_000},  # default; min 50_000
        "pause_after_compaction": True,
        # NOTE: `instructions` REPLACES the default prompt entirely, it does not append
        "instructions": (
            "Summarize the transcript inside <summary></summary> tags. Preserve file "
            "paths modified, architectural decisions, error states, function signatures, "
            "test results, env vars, and pending tasks. Do not call any tools while "
            "writing this summary; respond with text only."
        ),
    }]},
)
if resp.stop_reason == "compaction":
    # resp.content[0] is the compaction block. Append it, optionally splice the last
    # N verbatim messages back in after it, then continue the request.
    ...
# billing: sum usage.iterations[], not usage.input_tokens. The top-level fields
# EXCLUDE the compaction iteration.
```

Three non-obvious things in that snippet, all from the official docs. `instructions` **replaces** the default prompt rather than supplementing it, which is the most common way people accidentally lose the `<summary>` tag contract. The `do not call any tools` clause exists because a documented failure mode is that the model calls a tool during the internal summarization step and you get a compaction block with `content: null`. And billing changed shape: `usage.input_tokens` no longer covers everything, you must aggregate `usage.iterations`.

### The cost of a compaction, in dollars

This is the number that reframes compaction from "housekeeping" to "an expensive event you should schedule."

Prompt caching means a turn that shares its prefix with the previous turn is roughly **92% cheaper** than a cold read: about **$0.019 versus $0.23 for 60,000 tokens**. Compaction produces a brand-new prefix, so it invalidates the KV cache completely. Measured: **one compaction on a 125,000-token context costs about $0.40, equivalent to ~21 follow-up turns at cached rates.**

Two consequences. First, the optimal strategy is not to avoid compaction but to *delay it while the cache is warm and then pay for it deliberately*, which is the argument for large windows even given context rot. Second, if you are going to pay $0.40, buy a better summary: injecting a structured preservation checklist (files modified, architectural decisions, error states, function signatures, test results, env vars, pending tasks) before compaction raised summary length from 1,643 to 2,455 tokens, a **49% improvement, for $0.013.** In Claude Code that is a `Compact Instructions` section in `CLAUDE.md`, or `/compact focus on the API changes`.

### Determinism, and the honest limits of the sandbox

The permission model matters more than people expect because it is the only part of the system that is actually deterministic. Four modes, cycled with `Shift+Tab`: manual (asks before edits and shell), `acceptEdits` (edits and common filesystem commands run freely), `plan` (explores and proposes, source edits blocked), `auto` (a separate classifier model reviews each action, blocking escalation beyond your request, unrecognized infrastructure, and actions that look driven by hostile content it read). Plus two out-of-cycle modes, `dontAsk` and `bypassPermissions`.

Plan mode is the one worth being precise about, because it is the load-bearing control in every spec-driven workflow: edits stay blocked until you approve the plan, enforced by the harness rather than by the model's cooperation. **The honest caveat, straight from the docs: in sessions where bypass permissions are available, Claude Code does not enforce plan mode's blocks.** Claude is still *instructed* to plan without editing, and a file edit it attempts during planning will run without prompting. So "plan mode is a hard sandbox" is true in a normal session and false in a `--dangerously-skip-permissions` session, and knowing that distinction is what separates having read the docs from having read a blog post about the docs.

Separately, checkpoints: before an edit, the file is snapshotted, and `Esc Esc` rewinds. This is independent of git and survives resume. It covers file changes only, skips symlinked and hard-linked paths on restore, and cannot cover anything with an external side effect, which is exactly why the harness asks before commands that touch databases, APIs, or deployments.

---

## Build it from scratch

`labs/py/28-agent-loop-anatomy/` builds the harness in three passes, each one revealing a failure the previous pass hides.

**Pass 1: the loop (about 70 lines).** Three tools (`read_file`, `grep`, `run`), a `while` loop, and an explicit `messages` list you print the token count of on every turn.

```python
# runs. minimal harness; the point is that `messages` is the whole "memory".
import anthropic, subprocess, json, pathlib

client = anthropic.Anthropic()
TOOLS = [
    {"name": "read_file", "description": "Read a UTF-8 file.",
     "input_schema": {"type": "object", "properties": {"path": {"type": "string"}},
                      "required": ["path"]}},
    {"name": "run", "description": "Run a shell command in the repo root.",
     "input_schema": {"type": "object", "properties": {"cmd": {"type": "string"}},
                      "required": ["cmd"]}},
]

def dispatch(name, args):
    if name == "read_file":
        return pathlib.Path(args["path"]).read_text()[:40_000]   # the truncation matters
    if name == "run":
        p = subprocess.run(args["cmd"], shell=True, capture_output=True, text=True,
                           timeout=120)
        return (p.stdout + p.stderr)[-20_000:]                   # tail, not head
    return f"unknown tool {name}"

messages = [{"role": "user", "content": "Find and fix the failing test in tests/."}]
for turn in range(40):
    r = client.messages.create(model="claude-sonnet-5", max_tokens=4096,
                               tools=TOOLS, messages=messages)
    print(f"turn {turn}: in={r.usage.input_tokens} out={r.usage.output_tokens}")
    messages.append({"role": "assistant", "content": r.content})
    calls = [b for b in r.content if b.type == "tool_use"]
    if not calls:
        break
    messages.append({"role": "user", "content": [
        {"type": "tool_result", "tool_use_id": c.id, "content": dispatch(c.name, c.input)}
        for c in calls]})
```

Run it on a repo with a large lockfile and watch `input_tokens` climb superlinearly, because every previous tool result is re-sent every turn. That curve is the entire economics of the field.

**Pass 2: eviction and compaction.** Add (a) microcompact: replace tool results older than N turns with `"[evicted: 2,400 tokens of src/api/auth.ts]"`, keeping the *reference* so the model can re-read on demand, and (b) an Extract-pattern compaction at 89% of the window with the preservation checklist above. Measure the two things that matter: input tokens per turn, and *task success* on a fixed 10-task set. The lesson is that eviction is nearly free and compaction is not, and you should exhaust the former before reaching for the latter.

**Pass 3: the visibility split.** Log two separate streams: what a user would see, and what is in `messages`. Diff them. Then intentionally break it: have a tool return 200KB and watch the loop thrash. Implement the thrashing guard (stop compacting after 3 attempts and raise) and you will have re-derived, from first principles, a behaviour that ships in the product.

Deliverable is a one-page table: for each of your 10 tasks, tokens consumed, compactions triggered, pass/fail with and without the preservation checklist.

---

## How it's done in production

The managed harness adds five things over your `while` loop, and each one is there because of a specific failure you will hit in the lab: tiered compaction with thrashing detection, deferred tool schemas, subagent context isolation, filesystem checkpoints, and a permission layer with a classifier. Plus the operational surface: `/context` to see what is using space, `/mcp` for per-server cost, `/doctor` for a setup checkup that (as of v2.1.206) proposes trims to a checked-in `CLAUDE.md`, cutting content the model can derive from the codebase and keeping pitfalls and conventions.

**Failure-mode table**

| Symptom | Cause | Fix |
|---|---|---|
| Repeated "Conversation compacted" seconds apart, then a hard error | Compaction thrashing: one tool output larger than the space a summary frees | Find the read (`/context`), truncate at the tool boundary, delegate the read to a subagent, or `head`/`jq` it in the shell first |
| Instruction obeyed for 30 turns then silently dropped | It lived only in conversation history and was summarized away | Move to project-root `CLAUDE.md` (re-injected after compaction) or a `.claude/rules/` file |
| A skill stops being used mid-session and the model claims not to know it exists | The skill *listing* is not re-injected after compaction; only invoked skills are re-attached | Re-invoke it explicitly with `/name`, or pin critical guidance into `CLAUDE.md` |
| A skill is loaded but no longer influencing behaviour | Content is still present; the model is choosing other tools. Skill content is a message, not a constraint | Strengthen the description and instructions, or enforce via hooks |
| Bill 3× higher than token counts suggest | Compaction iterations are excluded from top-level `usage.input_tokens`; also every compaction invalidates the prompt cache (~$0.40 on a 125k context) | Aggregate `usage.iterations`; reduce compaction frequency rather than reducing per-turn tokens |
| Hook clearly ran, agent behaved as if it did not | Plain stdout on exit 0 goes to the debug log only. Only `hookSpecificOutput.additionalContext` enters context (and `UserPromptSubmit`/`SessionStart` stdout) | Emit JSON with `additionalContext`; use exit 2 + stderr to block and give feedback |
| Quality falls off a cliff at ~60% window utilization, well before compaction | Context rot. Effective capacity is 60-70% of nominal; every one of 18 frontier models tested degrades with input length | Delegate high-volume reads to subagents; start a fresh session with a handoff; do not treat a 1M window as 1M usable |
| Agent "reviews" a long transcript and misses the obvious problem | Monitoring degrades hard with irrelevant prefix: 2-30× more missed dangerous actions with 800K benign tokens prepended | Review in a fresh context, per-artifact, not at the end of a long session |
| Third compaction in one session; answers increasingly generic | Summary-of-a-summary degradation, compounding per round in the Extract pattern | Treat three compactions as a signal to restart with a written handoff, not to keep going |

**Numbers to have cold.** 200K default window · ~7.8K startup floor · ~12K for one small bug fix, 60% of it file content · compaction at ~89% (`ctx − min(maxOut, 20k) − 13k`) · API default trigger 150K input tokens, minimum 50K · `MEMORY.md` loads first 200 lines or 25KB · `CLAUDE.md` target under 200 lines · skill listing budget 1% of the window · invoked skills re-attached at 5K each within a 25K budget · cache reads ~92% cheaper ($0.019 vs $0.23 per 60K) · one compaction on 125K ≈ $0.40 ≈ 21 cached turns · preservation checklist +49% summary content for $0.013 · effective context 60-70% of nominal · 200 subagents per session, 20 concurrent.

---

## Tradeoffs & when NOT to use it

- **Do not use an agentic harness where you cannot supply a verifier.** The loop's entire advantage is that it can check its own work: run the test, read the error, adjust. Strip the verifier and you have an expensive autocomplete with a 15× token bill and no error signal. If there is no command whose exit code decides "done," fix that before you delegate.
- **Do not use a long session where a fresh session would do.** This is the most common self-inflicted wound. Sessions are cheap, compactions are not: three summarization rounds cost you real money, real fidelity, and (per the MonitorBench result) most of the model's ability to notice something wrong in the transcript. Long sessions feel productive because the context "knows the project." Measure it instead: if `/context` shows you past two compactions, restart with a written handoff.
- **Do not treat a bigger window as a fix for context management.** Every frontier model tested degrades with input length, and effective capacity lands around 60-70% of nominal. A 1M-token window buys you headroom before the cliff, not the absence of a cliff. Anyone who tells you long context obsoletes retrieval and subagents has not read the benchmark.
- **Do not use `bypassPermissions` and then describe plan mode as your safety control.** They are mutually exclusive claims: in bypass sessions the harness does not enforce plan mode's blocks. If you need both autonomy and a real gate, the gate has to be a hook or CI, not a mode.
- **Do not use the agentic harness for high-frequency, low-latency edits.** A tight rename-and-retype loop inside one file is autocomplete's home turf. The agent will `read` the file (2,400 tokens), think, and edit, at 5-20 seconds a round trip. Practitioners running both, deliberately, is the correct configuration; harness-for-everything is a fashion.
- **Understand that Extract-pattern compaction is destructive and irreversible, and that this is an audit problem, not just a quality problem.** If you are in a regulated environment and need to show what the agent saw when it made a change, a summarizer that discards the original turns is a compliance gap. The session JSONL under `~/.claude/projects/` is your mitigation and it is machine-local, cleaned up per `cleanupPeriodDays` (default 30). Event-sourced harnesses like OpenHands exist specifically for this and pay for it in storage.
- **The counter-argument you should be able to state:** a real camp argues all of this context engineering is transitional scaffolding that better models and cache-preserving compaction will delete, and that time spent tuning `CLAUDE.md` files is time spent optimizing against a moving target. They have a point about the specific numbers in this module, all of which will move. They are wrong about the shape: as long as inference is priced per token and attention degrades with length, *something* has to decide what is in the window, and deciding that is engineering.

---

## Interview questions

### Q1 — Walk me through what happens between me pressing Enter and the file being edited.
**Testing:** whether you can describe the loop mechanically or only narratively.
**Answer:** The harness sends one Messages API request containing the full buffer: system prompt (~4.2K), `CLAUDE.md` files as a user message after it, auto memory (first 200 lines / 25KB of `MEMORY.md`), environment and git state, MCP tool names with schemas deferred, the skill listing, then my prompt. The model returns text plus zero or more `tool_use` blocks. The harness executes them, appends `tool_result` blocks, and re-sends the *entire* buffer. That loop repeats: gather context with grep/glob/read, take action with edit/write/bash, verify with tests, until the model returns no tool calls. The model is stateless; the array is the only memory.
**Follow-up trap:** *"How much of that am I paying for on turn 20?"* All of it, every turn, unless the harness intervenes, which is why prompt caching dominates the cost model: a turn sharing its prefix costs about $0.019 per 60K tokens versus $0.23 cold, roughly 92% cheaper. And it is why compaction is expensive in a non-obvious way: it produces a fresh prefix, so it invalidates the whole cache. Measured, one compaction on a 125K context is about $0.40, equivalent to 21 more cached turns.

### Q2 — I ran `Read auth.ts` and my terminal shows one line. Why did my context jump 2,400 tokens?
**Testing:** the visibility asymmetry, which is the single most load-bearing idea in the module.
**Answer:** Because the terminal and the context window show different sets. Terminal output is a UI summary; the model receives the full file content. In Claude Code's own worked example a single `auth.ts` read is 2,400 tokens shown as one line, and a whole small bug fix is ~12,000 tokens with roughly 7,500 of that being file content. File reads dominate context usage, which is why prompt specificity is an engineering lever and not a manner: naming the file skips the exploratory reads.
**Follow-up trap:** *"Does the asymmetry ever run the other way, where something looks in-context but is not?"* Yes, and it is the classic hook bug. A `PostToolUse` hook's plain stdout on exit 0 goes to the debug log only, not into context. Only `hookSpecificOutput.additionalContext` enters the model's window (plus stdout from `UserPromptSubmit` and `SessionStart`). So a linter hook that prints violations to stdout and exits 0 has effectively printed them to nobody. Exit 2 with a message on stderr blocks and returns the reason as feedback, which is what you actually want for `PreToolUse`.

### Q3 — Why does it "forget" my instructions in long sessions?
**Testing:** whether "forgetting" is one word or four mechanisms to you.
**Answer:** Four distinct bugs. One: the instruction was only ever in conversation history and compaction summarized it away, since compaction keeps requests, key concepts, files touched, errors and fixes, and pending tasks, and drops verbatim tool output and intermediate reasoning. Two: it lived in a nested subdirectory `CLAUDE.md`, which loads on demand and is *not* re-injected after compaction, unlike project-root `CLAUDE.md`, which is re-read from disk and re-injected. Three: it is present and simply outranked, because instruction files are context, not enforced configuration. Four: two files in the `CLAUDE.md` hierarchy contradict each other and the model picks one arbitrarily, which shows up as nondeterminism across sessions. Diagnosis is `/context` to confirm the file is under **Memory files**, then `InstructionsLoaded` hooks to log exactly which instruction files loaded and when.
**Follow-up trap:** *"So put it in the system prompt."* `CLAUDE.md` is not the system prompt; it is delivered as a user message after it. Actual system-prompt injection is `--append-system-prompt`, which must be passed on every invocation, so it is a scripting mechanism rather than an interactive one. And it would not solve the real problem: even at system-prompt level, an instruction is a recommendation. If I would be upset to find the rule violated, it belongs in a `PreToolUse` hook, a lint rule, or a CI gate, where effectiveness does not depend on the model's cooperation.

### Q4 — Explain compaction. What survives and what doesn't?
**Testing:** the mechanism, not the vibe.
**Answer:** Tiered. Microcompact first: no model call, drops stale tool results on turns above a warning threshold. Then tool-output clearing, oldest first, which preserves conversation structure while discarding evidence. Then full LLM summarization, the Extract pattern, at roughly 89% of the window (`contextWindow − min(maxOutput, 20k) − 13k`). Then a thrashing guard that stops after a few attempts and errors rather than looping. Survives: my requests and intent, key technical concepts, files examined and modified with important snippets, errors and how they were fixed, pending tasks, project-root `CLAUDE.md`, and the most recent invocation of each skill at 5,000 tokens each within a shared 25,000-token budget. Lost: verbatim tool output, intermediate reasoning, exact code read, nested `CLAUDE.md`, and the skill *listing* itself.
**Follow-up trap:** *"What's the practical consequence of losing the skill listing?"* After a compaction the model may not know a skill exists unless it already invoked it, so a workflow that depended on the model auto-selecting a skill silently degrades mid-session with no error. Re-invoke it explicitly, or move the genuinely load-bearing part of it into `CLAUDE.md` so it survives. This is also the argument for `disable-model-invocation: true` on side-effecting skills: their descriptions were never in context anyway, so nothing changes at compaction.

### Q5 — A colleague says the 1M-token window means we can stop doing context engineering. Respond.
**Testing:** whether you have read the long-context evidence.
**Answer:** Wrong, and it is measurable. Chroma tested 18 frontier models and every single one degrades as input length increases; a 200K window shows serious accuracy loss by around 50K tokens of input, and effective capacity in practice is roughly 60-70% of nominal. The sharpest version is MonitorBench: Opus 4.6, GPT 5.4, and Gemini 3.1 miss dangerous actions 2× to 30× more often when 800K tokens of benign activity are prepended to the same transcript. So a bigger window moves the cliff further out, it does not flatten the curve. What large windows genuinely buy is fewer compactions, which matters because a compaction costs about $0.40 on a 125K context and destroys the prompt cache. The correct use of a big window is to delay compaction while the cache is warm, not to fill it.
**Follow-up trap:** *"Then why does anyone pay for 1M context?"* Because compaction is destructive and cache invalidation is expensive, so headroom has real value even if the tail of the window is low-quality. The right mental model is a budget with a soft quality ceiling around 60-70%: stay under it deliberately, and use the rest as slack so you compact once instead of three times. Anyone quoting nominal window size as a capability number is quoting a marketing figure.

### Q6 — How would you reduce token spend on a team where sessions routinely hit three compactions?
**Testing:** whether your optimizations target the right term.
**Answer:** File reads first, because they dominate: name files in prompts, delegate high-volume reads to subagents so the 6,100 tokens of exploration stay in the subagent's window and only a ~420-token summary returns, and truncate tool output at the tool boundary (head/tail/`jq` before it enters context, not after). Then reduce the startup floor: defer MCP schemas (default), trim `CLAUDE.md` toward the 200-line target, and set low-priority skills to `name-only` in `skillOverrides` or `disable-model-invocation: true` so they cost nothing. Then restructure sessions: three compactions is a signal to restart with a written handoff, not to push on. And add compact instructions, because a preservation checklist raised summary content 49% for $0.013.
**Follow-up trap:** *"Which of those actually saves the most money, and how do you know?"* Not the per-turn trimming: caching means a stable prefix is already 92% cheaper, so shaving 500 tokens off `CLAUDE.md` saves almost nothing. The wins are the ones that change *event counts*: fewer compactions (each ~$0.40 plus a cold re-read at $0.23 per 60K) and fewer full-file reads into the main window. I would measure it directly, `/context` plus aggregating `usage.iterations` per session, because the top-level `input_tokens` field excludes compaction iterations and will lie to you about where the money went.

### Q7 — Is plan mode a real sandbox?
**Testing:** whether you know the caveat, which is the difference between reading docs and reading about docs.
**Answer:** In a normal session, yes: Claude explores and proposes, source edits stay blocked until you approve the plan, and the block is enforced by the harness rather than by the model's cooperation. Commands outside the built-in read-only set prompt for approval, or get classified when auto mode is available with `useAutoModeDuringPlan` on. **But in sessions where bypass permissions are available, Claude Code does not enforce plan mode's blocks.** Claude is still instructed to plan without editing, and an edit it attempts during planning will run without prompting. So plan mode is a real control exactly when you have not already opted out of controls.
**Follow-up trap:** *"So how do you get a hard gate in an autonomous session?"* Move it below the mode layer. `PreToolUse` hooks with exit 2 or `permissionDecision: "deny"` fire regardless of mode, and when multiple hooks match, the most restrictive answer wins in the order deny, defer, ask, allow. `permissions.deny` in managed settings cannot be overridden by a user. Protected paths, sandboxing, and CI gates all sit outside the model's decision surface. The general rule: a mode is a *default*, a hook is a *constraint*, and only the second survives someone passing a flag.

### Q8 — What are the built-in tool categories, and why does the set matter more than the model?
**Testing:** harness literacy.
**Answer:** Five: file operations (read, edit, create, move), search (glob by pattern, regex content search), execution (shell, servers, tests, git), web (search and fetch), and code intelligence (type errors and diagnostics after edits, jump-to-definition, find-references, via plugins). Plus orchestration tools: spawning subagents, asking the user questions. The set matters more than the model because it determines what the loop can *verify*. A harness with execution can run the test and read the failure; a harness without it can only assert. That is also why agentic search beat index-based retrieval: `grep` on the live filesystem is never stale, whereas an embedding index built four commits ago describes code that no longer exists.
**Follow-up trap:** *"More tools is better, then?"* No, and the failure is measurable in context. MCP tool schemas are deferred by default precisely because they grow linearly with your integrations; only names load (~120 tokens) with `ENABLE_TOOL_SEARCH=auto` loading schemas upfront only when they fit within 10% of the window. Beyond cost, a large tool surface degrades selection: overlapping tools make the model pick wrong. Vercel deleting 80% of their agent's tools and getting better results is the canonical anecdote. Tool set design is subtractive.

### Q9 — Design compaction for a harness you own. What do you copy and what do you change?
**Testing:** whether you can reason about a design space with real alternatives.
**Answer:** Copy the tiering, because it is the highest-leverage part: evict stale tool results with no model call before you ever pay for a summary, and keep a *reference* in place of the content (`[evicted: src/api/auth.ts, 2,400 tokens]`) so the model can re-read on demand instead of hallucinating. Copy the thrashing guard. Change two things. First, threshold: the industry spread is 50% (Gemini CLI) to 96-99% (OpenCode) and it is a genuine tradeoff, frequent small losses versus rare catastrophic ones, so I would pick based on task shape, late for focused high-context work and early for long exploratory sessions. Second, I would seriously consider the event-store model over Extract: OpenHands keeps an append-only log and marks events suppressed rather than deleting them, so compaction is reversible and auditable, at a storage cost. In a regulated context that is not a nicety.
**Follow-up trap:** *"What breaks in the Extract pattern that the event store fixes?"* Compounding degradation and auditability. Extract feeds a summary of a summary into the next round, so fidelity decays per compaction, which is why three compactions is a restart signal rather than a status. And once the original turns are gone you cannot answer "what did the agent actually see when it made this change," which is a real problem in an incident review or a compliance audit. The mitigation in Claude Code is that the raw session is persisted as JSONL under `~/.claude/projects/`, but that is machine-local and cleaned up on `cleanupPeriodDays`, default 30, so it is a debugging aid rather than an audit trail.

### Q10 — Your agent is thrashing: it compacts, immediately refills, compacts again, then errors. Diagnose it.
**Testing:** whether you can debug the harness rather than blame the model.
**Answer:** Something entered context that is larger than the space a summary can free. Almost always a single read: a lockfile, a minified bundle, a 400KB test log, a `SELECT *` dump. Claude Code detects this and stops auto-compacting after a few attempts rather than looping, which is why you get a hard error instead of an infinite bill. Diagnosis: `/context` to find the biggest contributor, then look at the last few tool results. Fix at the tool boundary, not after: `tail -100`, `jq -r '.failures[]'`, `grep -c`, or delegate the whole read to a subagent so the volume lands in its window and a summary comes back. The general principle is that truncation belongs upstream of context, because once it is in the buffer you are paying to re-send it every turn until it is evicted.
**Follow-up trap:** *"Why not just raise the compaction threshold?"* Because the failure is not that compaction fired too early, it is that a single item exceeds what compaction can reclaim, so a higher threshold gives you a bigger, more expensive version of the same loop. It also runs the wrong direction against context rot: pushing utilization higher lands you deeper into the 60-70%-effective-capacity zone where quality is already falling. The fix has to be on the input side.

### Q11 — What is the observable difference between "the model is worse today" and "my context is polluted"?
**Testing:** whether you can distinguish a capability change from a harness state, which is where most wasted debugging time goes.
**Answer:** Pollution has a signature and a capability change does not. Pollution: quality degrades *within* a session and recovers in a fresh one with the same prompt; `/context` shows high utilization or a compaction count above one; the model repeats work it already did (a sign the evidence was evicted but the reference was not preserved); it references a file version that no longer exists (post-compaction summary, not current disk state); it misses things it caught earlier in the same session, which is exactly the MonitorBench effect. A genuine model change reproduces from a clean context on a fixed prompt set. So the test is cheap: rerun the same task in a new session, and if it passes, the model is fine and your harness is not.
**Follow-up trap:** *"How would you catch it before a human notices?"* Instrument the harness rather than the model: log per-turn input tokens, compaction count, and evicted-token count per session, and alert on compactions-per-session above one. Keep a small fixed regression set, ten tasks with machine-checkable outcomes, and run it from a cold context on a schedule. That set is also the only honest way to evaluate a model upgrade, because self-reported productivity is not evidence, which METR demonstrated by finding a 19% slowdown that participants experienced as a 20% speedup.

### Q12 — You get a 300-line unfamiliar codebase, 60 minutes, and an AI assistant. What is your process?
**Testing:** the Google Code Comprehension round format, near-verbatim.
**Answer:** Budget it explicitly and do not start by prompting. First 10 minutes, unaided: read the entry point and the data structures, and write down the invariants I *think* hold. That gives me a hypothesis the assistant cannot hand me and cannot contaminate. Next 15: use the assistant as a search engine and a second reader, asking narrow questions ("where is this mutated," "what calls this with a null") rather than "find the bugs," because a broad ask returns a plausible list I then have to verify from scratch. Next 20: confirm each candidate bug by tracing it myself and stating the failing input. Last 15: narrate the design decisions I would change, what I would test first, and what I deliberately did not touch. Throughout, narrate the AI use out loud, because how I use it is what is being scored.
**Follow-up trap:** *"The assistant flags a bug you don't believe is real. What now?"* Say so, and resolve it by construction: write the input that would trigger it and show it does not. That is the highest-value 60 seconds in the round, because the failure mode the interviewer is watching for is accepting a confident wrong answer, and the documented pattern is that candidates leaning on AI in live rounds often do *worse* because follow-ups expose that they cannot explain the model's mistake. Disagreeing with the tool correctly, with evidence, is the single strongest signal available in that format.

### Q13 — What would you instrument if you owned agent tooling for 200 engineers?
**Testing:** whether you think in observability terms about a probabilistic system.
**Answer:** Per session: input tokens per turn, compaction count with `preTokens` at each boundary, evicted tokens, tool-call histogram, cache hit rate, and total cost aggregated across `usage.iterations` rather than the top-level fields, which exclude compaction. Per repo: `CLAUDE.md` size against the 200-line target, skill listing size after the 1%-of-window budget is applied, and how often instruction files are loaded but overridden. Per outcome: a fixed cold-context task set with machine-checkable pass/fail, PR cycle time end to end, change failure rate, and defect escape rate. And the one that catches real problems: an `InstructionsLoaded` hook logging which instruction files loaded, when, and why, because "the rule was in the file" and "the rule was in the window" are different facts.
**Follow-up trap:** *"Which single metric would you put on the dashboard?"* Compactions per session, because it is a leading indicator that correlates with everything else that goes wrong: cost (each is roughly $0.40 on a 125K context plus a cold re-read), fidelity (summary-of-summary decay), and the reviewer-blindness effect where a long benign prefix makes the model miss dangerous actions 2-30× more often. It is also actionable in a way that "quality" is not: the fixes are all concrete, delegate the reads, truncate at the tool, restart with a handoff.

---

## Red flags that fail you

- Saying "it has memory" or "it remembers the codebase." It has an array you re-send.
- Not knowing that the terminal view and the context window are different sets.
- Believing `CLAUDE.md` is part of the system prompt.
- Treating the nominal context window as usable capacity.
- Claiming plan mode is a hard sandbox without the bypass-permissions caveat.
- No idea what compaction discards, or thinking it is lossless.
- Debugging a "model regression" without first rerunning the task from a cold context.
- Answering a thrashing loop with "raise the threshold."
- Quoting `usage.input_tokens` as total spend with compaction enabled.
- Optimizing per-turn tokens while ignoring compaction event count and cache invalidation.
- Thinking more MCP tools is strictly better.
- Recommending an index-based retrieval layer without acknowledging staleness.

## Cheat card

```
HARNESS = tool set + context manager + execution env, wrapped round a STATELESS model
LOOP    gather context → take action → verify → repeat (phases blend; you can interrupt)
         the whole message array is RE-SENT every turn. that is the entire cost model.

STARTUP FLOOR (200k window)  ≈7.8k tok = 3.9%
  sys prompt 4.2k · MEMORY.md 680 (first 200 lines/25KB) · env 280
  MCP names 120 (schemas DEFERRED) · skill listing 450 (1% of window budget)
  ~/.claude/CLAUDE.md 320 · project CLAUDE.md 1.8k (target <200 lines)
ONE SMALL BUG FIX ≈12k tok, ~7.5k of it FILE CONTENT → file reads dominate

VISIBILITY ASYMMETRY (the key idea)
  terminal one-liner "Read auth.ts"      = 2,400 tok in context
  hook stdout, exit 0                    = debug log ONLY, not context
  hookSpecificOutput.additionalContext   = enters context
  subagent's 6.1k of reads               = its window; you get a 420-tok summary

COMPACTION, TIERED
  1 microcompact  no LLM call, drops stale tool results
  2 tool-output clearing, oldest first
  3 full LLM summarize (Extract) at ~89% = ctx − min(maxOut,20k) − 13k
  4 thrashing guard: stop after a few attempts, ERROR not loop
  SURVIVES: intent · concepts · files+snippets · errors&fixes · pending tasks
            project-root CLAUDE.md (re-read from disk) · invoked skills (5k ea /25k)
  LOST:     verbatim tool output · reasoning · exact code · SKILL LISTING
            nested subdir CLAUDE.md · anything said only in chat

API   betas=["compact-2026-01-12"], edits=[{type:"compact_20260112"}]
  trigger default 150k input tok, min 50k · pause_after_compaction to splice msgs back
  `instructions` REPLACES the default prompt · add "do not call tools" or you get
   content:null · BILL from usage.iterations[], top-level EXCLUDES compaction

MONEY
  cache read ≈92% cheaper: $0.019 vs $0.23 per 60k
  one compaction on 125k ctx ≈ $0.40 ≈ 21 cached turns
  preservation checklist: 1,643 → 2,455 summary tok (+49%) for $0.013

CONTEXT ROT   effective capacity ≈60-70% of nominal; all 18 models tested degrade
  200k window: serious loss by ~50k input · MonitorBench: 2-30× more missed
  dangerous actions with 800k benign prefix prepended

THRESHOLDS ACROSS AGENTS  Gemini CLI ~50% · Roo 86-92% · Claude Code ~89%
  Codex CLI ~90% (180k-244k, configurable DOWN only) · Pi ~92% · OpenCode 96-99%
  OpenHands: event store, 100 events, compaction REVERSIBLE

"IT FORGOT" = 4 BUGS   never persisted · nested CLAUDE.md not re-injected ·
  present but outranked (instructions are CONTEXT not CONFIG) · two files contradict
  CLAUDE.md is a USER MESSAGE after the system prompt, not the system prompt

MODES  manual · acceptEdits · plan · auto(classifier) · dontAsk · bypassPermissions
  plan mode blocks edits AT THE HARNESS — except in bypass-permissions sessions
  hooks/permissions.deny fire regardless of mode; deny > defer > ask > allow

LIMITS  200 subagents/session · 20 concurrent · checkpoints = file snapshots,
  Esc Esc, not git, skip symlinks, cannot cover external side effects
```

## Sources

- [How Claude Code works](https://code.claude.com/docs/en/how-claude-code-works) — the agentic loop (gather context / take action / verify), the five tool categories, sessions as JSONL under `~/.claude/projects/`, checkpoints, permission modes, and the "when context fills up" behaviour; accessed 2026-07-26
- [Explore the context window](https://code.claude.com/docs/en/context-window) — the per-item token figures used throughout: 4,200 system prompt, 680 auto memory, 280 env, 120 MCP names, 450 skill listing, 320 user CLAUDE.md, 1,800 project CLAUDE.md, 2,400 for one file read, and the subagent 6,100-in / 420-out example; accessed 2026-07-26
- [How Claude remembers your project](https://code.claude.com/docs/en/memory) — CLAUDE.md delivered as a user message after the system prompt; the 200-line target; project-root CLAUDE.md re-injected after `/compact` while nested files are not; `--append-system-prompt`; the `InstructionsLoaded` hook; accessed 2026-07-26
- [Compaction — Claude Platform Docs](https://platform.claude.com/docs/en/build-with-claude/compaction) — `compact_20260112`, beta header `compact-2026-01-12`, default 150,000-token trigger and 50,000 minimum, `pause_after_compaction`, `instructions` replacing the default prompt, the `content: null` tool-call failure mode, and `usage.iterations` billing; accessed 2026-07-26
- [Permission modes](https://code.claude.com/docs/en/permission-modes) — the mode cycle, plan mode's approval gate, and the explicit statement that bypass-permissions sessions do not enforce plan mode's blocks; accessed 2026-07-26
- [Get started with hooks](https://code.claude.com/docs/en/hooks-guide) — event list including `PreToolUse`, `PostToolUse`, `PreCompact`, `InstructionsLoaded`; exit-code semantics; and that only `additionalContext` (plus `UserPromptSubmit`/`SessionStart` stdout) reaches the model; accessed 2026-07-26
- [Extend Claude Code](https://code.claude.com/docs/en/features-overview) — the context-cost-by-feature table (what loads when, and what it costs every request); accessed 2026-07-26
- [Extend Claude with skills](https://code.claude.com/docs/en/skills) — skill listing budget at 1% of the context window, the 1,536-character description cap, and the post-compaction re-attachment rule (5,000 tokens per skill within a 25,000-token budget); accessed 2026-07-26
- [Create custom subagents](https://code.claude.com/docs/en/sub-agents) — fresh isolated context per subagent, what loads at startup, the 200-per-session and 20-concurrent limits, and `compact_boundary` / `preTokens` in subagent transcripts; accessed 2026-07-26
- [Context Compaction Showdown: How Codex CLI, Claude Code, and 5 Other Agents Handle Full Context Windows](https://codex.danielvaughan.com/2026/04/10/context-compaction-showdown-coding-agents/) — Daniel Vaughan, 2026-04-10, updated 2026-07-15; the cross-agent threshold table, the Extract-versus-event-store framing, the KV-cache economics ($0.019 vs $0.23 per 60K, $0.40 per compaction on 125K ≈ 21 cached turns), and the 49% pre-compaction-checklist result; accessed 2026-07-26
- [How AI Coding Agents Handle a Full Context Window](https://wasnotwas.com/writing/context-compaction/) — the underlying measurements behind the threshold formulas and the cache-cost figures; accessed 2026-07-26
- [Effective context engineering for AI agents](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents) — Anthropic Engineering, 2025-09-29; context as a finite resource, compaction, structured note-taking outside the window, concise tool returns, just-in-time retrieval; accessed 2026-07-26
- [Context Rot: Why LLMs Degrade as Context Grows](https://www.morphllm.com/context-rot) — summary of the Chroma study across 18 frontier models, the ~60-70% effective-capacity figure, and the 200K-window loss by ~50K input; accessed 2026-07-26
- [Classifier Context Rot: Monitor Performance Degrades with Context Length](https://arxiv.org/html/2605.12366v1) — the MonitorBench result: 2× to 30× more missed dangerous actions with 800K tokens of benign activity prepended; accessed 2026-07-26
- [Google's AI-Assisted Coding Interview (2026 Guide)](https://www.tryexponent.com/blog/google-ai-coding-interview) — the Code Comprehension round: 200-500 line unfamiliar codebase, CoderPad, 60 minutes, Gemini available; accessed 2026-07-26
- [Meta's AI-Enabled Interview](https://nerddesignlab.substack.com/p/metas-ai-enabled-interview-everything) — AI-enabled coding rounds from late 2025 with candidate model choice; accessed 2026-07-26

## Changelog
- 2026-07-26 — created
