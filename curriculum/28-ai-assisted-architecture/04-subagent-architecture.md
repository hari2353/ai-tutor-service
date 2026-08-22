# Subagent Architecture: Context Isolation and What It Costs

> **Track:** T28 AI-Assisted Architecture · **Time:** 2h · **Prereqs:** `T28-claude-code-model`, `T07-multi-agent-topologies` · **Updated:** 2026-07-26
> **Module id:** `T28-subagent-architecture` · **Tags:** architecture, critical

## The 30-second version

A subagent is a fresh context window with its own system prompt, tool scope, and permissions, and the only thing that crosses back is its final text response, which is why the canonical example is a research task that reads 6,100 tokens of files and returns a 420-token summary: a 14× reduction in what your main window pays. That is the whole value proposition, and it comes with a cold start you must price: a non-fork subagent loads its own system prompt plus **its own full copy of every CLAUDE.md in the hierarchy** plus MCP and skill metadata plus the delegation prompt, roughly 3,800 tokens before it does any work, and it sees none of your conversation, so anything it needs you must restate. The decision rule is a ratio: delegate when the work it will read is much larger than the summary it returns *and* much larger than the cold start, which in practice means high-volume reads, verbose command output, and genuinely independent parallel research. Delegate the wrong thing and you pay twice: once for the cold start and again for the handoff loss, where the subagent solved the task and then described the solution badly. Two guardrails that stop this becoming a distributed-systems disaster: one subagent per independently reviewable artifact, and treat the return value as a distilled report with a required shape, not a transcript.

## Why this gets asked

Because "just use subagents" is the current cargo cult, and the interviewer has paid for it. They have seen a session spawn eleven subagents to do work that fit in one context, and they have seen the opposite failure, a 400,000-token main session that should have delegated its log reading on turn three. They also know the load-bearing number: Anthropic's own measurement is that multi-agent systems consume roughly **15× more tokens than chat** while agents generally use about 4×, so this is the most expensive architectural decision available in the harness and it is frequently made by accident. And there is a review-discipline signal underneath: if you fan out generation without fanning out review, you have parallelized the cheap half and serialized the expensive half.

---

## Lineage: past → present → future

**What came before.** First, one long session. The pain that killed it was mechanical: every tool result is re-sent every turn, so a session that reads a large codebase reaches compaction and then the Extract pattern discards the evidence while keeping the narrative, and quality degrades in a way you cannot see. The second approach was manual context management, roughly 2024: you shepherded which files were open, cleared the session by hand, and re-pasted the state you wanted to keep. That died of it being your job, and of you being bad at it, because the token accounting is invisible from the terminal. The third and most instructive predecessor was the multi-agent orchestration framework wave of 2023-2024 (AutoGen-style conversational teams, CrewAI-style role assignment): agents with personas, talking to each other, in a shared message space. The pain that killed *that* pattern for coding specifically was that shared conversation defeats the only benefit worth having. If every agent sees every message, you have paid N× for the model calls and got 1× the context isolation, plus a new class of failure where agents agree with each other into a wrong plan. What survived is the narrow, boring version: isolated context, one-way delegation, structured return.

**Where it stands now.** The consensus is a lead-agent-plus-workers topology with strict context isolation and no peer chatter by default, and the numbers behind it are public. Anthropic's multi-agent research system reports Opus-lead-with-Sonnet-workers outperforming single-agent Opus by **90.2%** on their internal research evaluation, with the sharpest finding being that **token usage alone explains about 80% of performance variance** on BrowseComp, with tool calls and model choice accounting for most of the rest. Read together with the 15× cost multiplier, that is an honest and unusual admission: much of the gain is *buying more tokens*, structured so they do not all land in one window. In Claude Code the shipped shape is: built-in Explore (read-only, Write and Edit denied, inherits the session model capped at Opus on the Claude API), Plan (read-only research during plan mode), general-purpose (all subagent-available tools), plus custom subagents with their own prompts, tool restrictions, permission modes, hooks, and preloaded skills. Notably, **Explore and Plan skip CLAUDE.md and the parent's git status** to keep research cheap, and every other subagent loads both. Defaults have moved toward background execution: as of v2.1.198 subagents run in the background by default and Claude runs one in the foreground only when it needs the result to continue. The live disagreements are real. **Isolation versus inheritance:** forks (`/subtask`) inherit the entire conversation, which drops input isolation but shares the parent's prompt cache and needs no re-explanation, and reasonable people disagree about which should be the default. **Nesting:** off by default, with the `Agent` tool withheld from subagents, because debuggability collapses faster than capability grows. **And whether "agent teams" (independent contexts that can message each other) are a real advance or a reinvention of the 2024 mistake with better plumbing.**

**Where it's heading.** **High confidence: delegation gets priced and budgeted rather than free-form.** The limits are already explicit: 200 subagents per session (`CLAUDE_CODE_MAX_SUBAGENTS_PER_SESSION`), 20 concurrent (`CLAUDE_CODE_MAX_CONCURRENT_SUBAGENTS`), nesting depth capped, and the failure modes are named errors (`Subagent spawn limit reached` tells the model to finish the work itself). Expect token budgets per delegation next, the way `pause_after_compaction` gave compaction a budget hook. **High confidence: the return value becomes a typed contract.** Subagent output is already *scanned* before the main agent reads it, with backslashes inserted into text imitating `<system-reminder>` tags or `Human:`/`Assistant:` lines, and a marker line prepended when a report imitates harness output or mentions `bypassPermissions`. That is the first step from "returns prose" to "returns a validated structure." **Medium confidence: forks become the default and named subagents become the specialization.** Cache sharing is a strong economic argument, and the fork's own tool calls still stay out of your window, so you get most of the context benefit without the re-explanation cost. **Speculative: the industry converges on one-subagent-per-reviewable-artifact as a norm** because review is the actual bottleneck. Flag that as a preference, not a forecast.

---

## Mental model

The economics, drawn as a balance sheet. Every delegation decision is this arithmetic:

```
  DELEGATE                                    DON'T DELEGATE
  ────────────────────────────────────        ─────────────────────────────
  COST (paid every spawn)                     COST
    own system prompt        ~900               everything the task reads
    own copy of CLAUDE.md   ~1,800              lands in YOUR window
      (hierarchy, in full — Explore
       and Plan are the exceptions)
    MCP + skills metadata     ~970
    delegation prompt YOU write ~120
    ────────────────────────────
    ≈3,800 tok COLD START, in the
    subagent's window, before any work
  +
    HANDOFF LOSS: it saw everything,
    you get its summary. if the summary
    is bad you cannot tell.
  +
    LATENCY: it starts from nothing and
    must re-derive context you already had

  BENEFIT
    its reads stay in ITS window
    canonical: reads 6,100 → returns 420
    ⇒ 14× reduction in YOUR window
```

The rule falls out: **delegate when (work it will read) ≫ (summary returned) and (work it will read) ≫ 3,800.** A task that reads 4,000 tokens and returns 800 is roughly break-even and you have added latency and handoff risk for nothing.

Second picture: what crosses the boundary, because every "why didn't it know that" question is here.

```
   MAIN SESSION                          NON-FORK SUBAGENT
   ───────────────────                   ─────────────────────────
   conversation history   ──── ✗ ────►   (never)
   files already read     ──── ✗ ────►   (never; it re-reads)
   skills already invoked ──── ✗ ────►   (only `skills:` preload — FULL content)
   auto memory (MEMORY.md)──── ✗ ────►   (its own `memory:` dir if configured)
   output style           ──── ✗ ────►   (never)
   CLAUDE.md hierarchy    ──── ✓ ────►   full copy, own tokens
                                          (Explore + Plan SKIP it)
   git status snapshot    ──── ✓ ────►   parent-session snapshot
                                          (Explore + Plan SKIP it)
   YOUR delegation prompt ──── ✓ ────►   this is the ONLY task-specific channel
   context window size    ──── ✗ ────►   sized by ITS model, not yours

   ◄─── final text response ONLY (+ token/duration trailer, + output scan)
   ◄─── its tool calls, file reads, errors: NEVER cross back

   FORK (/subtask) inherits: full history, same system prompt, tools, model,
   AND SHARES THE PARENT'S PROMPT CACHE. its tool calls still stay out.
```

The single most consequential line: **your delegation prompt is the only task-specific channel.** The docs say it plainly for rules ("if a rule must reach the subagent, such as 'ignore the `vendor/` directory,' restate it in the prompt you give Claude when delegating"). Everything you know and do not write down, the subagent does not know.

---

## How it actually works

### The cold start, itemized

From Claude Code's own context-window walkthrough, a `general-purpose` subagent spawned for a research task starts with:

| Component | Tokens | Note |
|---|---|---|
| Its own system prompt + env details | ~900 | Shorter than the main session's ~4,200. Custom subagents supply theirs in the markdown body or `prompt` field |
| Project `CLAUDE.md` (own copy) | ~1,800 | The **entire hierarchy**: `~/.claude/CLAUDE.md`, project rules, `CLAUDE.local.md`, managed policy. Explore and Plan skip this |
| MCP tools + skills metadata | ~970 | Most of the parent's tools, minus plan-mode controls, background-task tools, and (by default) `Agent` itself |
| Delegation prompt written by the lead | ~120 | The only task-specific input |
| **Cold start total** | **≈3,800** | in the subagent's window, before it reads a single file |

Then it works: `session.ts` 2,200 · `timeouts.ts` 800 · `config/*.ts` 3,100 = **6,100 tokens of reads**, none of which touch your window. And it returns **420 tokens** plus a small metadata trailer with token counts and duration.

Two things to take from that. First, the savings are real and large when the read volume is large: 6,100 in, 420 out. Second, the cold start is not negligible: if the task only needed to read 2,000 tokens, you spent 3,800 to save 2,000, and you also added a full round of latency because it starts from nothing.

### The limits, and what happens when you hit them

Three separate limits with three separate variables, and knowing they are distinct is a decent proxy for having actually operated this:

| Limit | Default | Variable | Behaviour at the edge |
|---|---|---|---|
| Total spawned per session | **200** | `CLAUDE_CODE_MAX_SUBAGENTS_PER_SESSION` (v2.1.212+, no upper bound, cannot be disabled) | `Agent` fails with `Subagent spawn limit reached`; the error instructs the model to finish the remaining work with its own tools. `/clear` resets |
| Concurrent running | **20** | `CLAUDE_CODE_MAX_CONCURRENT_SUBAGENTS` (v2.1.217+) | `Concurrent subagent limit reached`, with instructions not to retry; succeeds again when the count drops. Ultracode sessions are exempt |
| Nesting depth | 1 (nesting off) | see below | The `Agent` tool is withheld from subagents; a fork keeps it in its list but it errors instead of spawning |

Everything counts toward the session limit: nested subagents, forks, background subagents, and subagents spawned by workflow agents. A `/subtask` fork you start yourself spends the same budget but is never *blocked* by the limits. A finished subagent still counts. Resuming a completed subagent takes a fresh concurrency slot **without checking the limit**, so resumes can push the running count past 20.

### Delegation boundaries: what to send down

The delegation prompt is the interface, and treating it like an interface is the difference between delegation that works and delegation that produces confident nonsense. What belongs in it:

1. **The task, bounded.** Not "look into session timeouts" but "read `src/auth/session.ts` and everything it imports, and tell me every place a timeout value is set, read, or defaulted."
2. **The files or directories in scope, and out of scope.** The subagent has no idea `vendor/` is generated or that `legacy/` is being deleted next sprint. Restate exclusions explicitly; the docs call this out as necessary because most rules do not need to reach the subagent but the ones that do must be in the prompt.
3. **The output shape you require.** This is the highest-value line and the least written. See below.
4. **What it must not do.** Especially for a `general-purpose` subagent, which has every tool available to subagents including write access.
5. **Nothing else.** Do not dump your conversation. If the subagent needs your whole conversation, you wanted a fork.

For the built-in Explore agent, the lead also specifies a thoroughness level: **quick** for targeted lookups, **medium** for balanced exploration, **very thorough** for comprehensive analysis. That is a cost dial and it is worth setting deliberately.

### What comes back: distilled reports, not transcripts

Only the final text response crosses back. That means the *shape* of that response is your only lever on quality, and an unshaped subagent produces the worst possible artifact: a narrative of what it did.

Require a structure. In a custom subagent definition, put it in the system prompt so every invocation obeys it:

```markdown
---
name: codebase-researcher
description: Investigates how a subsystem works and returns a structured findings
  report. Use proactively when a question would require reading more than three files.
tools: Read, Grep, Glob, Bash
model: sonnet
---

You research code and report findings. You do not modify files.

Always end your response with exactly this structure and nothing after it:

## Answer
<2-4 sentences. The direct answer. No preamble.>

## Evidence
<file:line → one-line claim. Every claim needs a citation. Max 8 entries.>

## Uncertain
<What you could not determine and why. An empty list is suspicious;
 if you genuinely have none, say "none, and here is what I checked".>

## Not examined
<What you deliberately did not read, so the caller knows the boundary.>
```

Why each section earns its place. **Answer** first because the caller may only read that. **Evidence with `file:line`** because the caller cannot see what you read, so an uncited claim is unverifiable, and this is where subagent hallucination concentrates: it is the one place in the system where a confident sentence has no provenance. **Uncertain** because the default failure of a summarizer is confident completeness; an explicitly empty uncertainty list is a signal about the task's framing. **Not examined** because the caller needs the boundary to know whether the answer generalizes.

**Anti-pattern:** "summarize what you found." That yields "I explored the session handling and found that timeouts are configured in several places, and the implementation looks reasonable overall," which is 30 tokens of nothing and you cannot tell it apart from a real answer.

There is also a security layer worth knowing about, because it is the kind of detail that signals you have read the docs. Claude Code **scans each subagent's final report before the main agent reads it**, since the subagent may have read files, web pages, or command output nobody reviewed, and text from those sources can carry instructions aimed at the main conversation. The scan never removes or rewords: it inserts a backslash into text imitating harness output (`<system-reminder>` tags, lines starting with `Human:` or `Assistant:`), and prepends a marker line `[harness: subagent output matched instruction-shaped pattern(s):` when a report imitates such a tag or mentions `bypassPermissions` / `--dangerously-skip-permissions`. Crucially, the docs are honest that the scan does not judge maliciousness and does not change what an instruction in a report can do: a tool call the report leads Claude to make still goes through permission checks and sandboxing. **It is not a substitute for restricting what a subagent can reach.** Prompt injection via subagent output is a live attack surface and tool scoping is the actual control.

### Parallel fan-out, and where it goes wrong

Fan-out works when the research paths genuinely do not depend on each other: "research the authentication, database, and API modules in parallel using separate subagents," then the lead synthesizes. It fails in four distinct ways.

**One: return-value bloat.** The docs warn about it directly: running many subagents that each return detailed results can consume significant context. Five subagents returning 2,000 tokens each is 10,000 tokens landing in your window at once, which is worse than one subagent returning 420. Fan-out requires *tighter* output contracts than a single delegation, not looser.

**Two: false independence.** If subagent B needs a conclusion subagent A is still deriving, you have not parallelized, you have duplicated: both will read the shared code and reach possibly different conclusions, and the lead now has to reconcile two accounts of the same thing with no ability to inspect either one's reasoning.

**Three: serialized review.** This is the one that matters at Principal level. If two subagents produce work you can only evaluate together, you have parallelized generation and serialized review, which is exactly backwards given that review is the bottleneck. Hence the rule: **one subagent per independently reviewable artifact.**

**Four: uncoordinated writes.** The documented large-scale case is Scott Chacon's Grit (a Git rewrite in Rust, roughly 45 billion tokens consumed) where a parallel agent broke a fundamental part of the testing harness, and the cause was uncoordinated parallel writes. The mitigation is worktree isolation plus frequent merge checkpoints, which is module 06's subject. For read-only fan-out this does not apply, which is why read-only fan-out is the safe default.

### Forks: the case for inheritance

A fork (`/subtask`, v2.1.212+; `/fork` on v2.1.161-2.1.211) inherits the entire conversation, the same system prompt, tools, and model. It drops input isolation deliberately, and it keeps the part you actually wanted: its own tool calls stay out of your conversation and only the final result comes back.

| | Fork | Named subagent |
|---|---|---|
| Context | full conversation history | fresh, plus your delegation prompt |
| System prompt and tools | same as main | from the definition file, filtered for background runs |
| Model | same as main | from `model:` |
| Prompt cache | **shared with main session** | separate cache |
| Cold start | ~0 (cache hit on the shared prefix) | ~3,800 tokens |
| `Agent` tool | inherited (can it spawn? no, nesting still off) | withheld |

The economic argument is the cache line: because a fork's system prompt and tool definitions are identical to the parent, its first request reuses the parent's prompt cache, making forking cheaper than a fresh subagent for tasks needing the same context. Use a fork when a named subagent would need too much background to be useful, or to try several approaches in parallel from the same starting point. Use a named subagent when you want a *different* tool scope or permission posture, which a fork by definition cannot give you.

One more capability worth knowing: when Claude spawns a fork through the `Agent` tool it can pass `isolation: "worktree"` so the fork's edits land in a separate git worktree rather than your checkout. That is the bridge between this module and large-scale refactoring.

### Resume, and why it is not a workaround for bad delegation

Each invocation creates a new instance with fresh context, but a completed subagent can be resumed via `SendMessage` with its agent ID or name, retaining full conversation history including all previous tool calls and reasoning. Explore and Plan are one-shot and return no agent ID, so they cannot be resumed; use `general-purpose` or a custom subagent when continuation matters. Transcripts live at `~/.claude/projects/{project}/{sessionId}/subagents/agent-{agentId}.jsonl`, persist independently of the main conversation (main-session compaction does not touch them), and are cleaned up per `cleanupPeriodDays`, default 30. Subagents run their own auto-compaction with the same logic as the main conversation, logging `compact_boundary` events with `preTokens`.

Two guardrails in the resume path that read like they were added after an incident. `SendMessage` verifies that a name still refers to the same agent it reached earlier in the conversation, refusing the send if a newer agent took the name and reporting which agent the name now reaches. And, as of v2.1.198, a subagent treats messages from the agent that launched it as normal task direction including mid-task corrections, **but no message from any agent counts as your approval for a pending permission prompt, and no agent message can change a subagent's permission settings, `CLAUDE.md`, or configuration.** Only the permission system or your own messages can grant approval. That is a deliberate confused-deputy defence and it is the correct answer to "can the lead agent authorize the worker."

---

## Build it from scratch

No lab folder; this is a measurement exercise, and the deliverable is a table you could put in a design doc.

**Step 1: instrument the ratio.** Take five real tasks. For each, run it inline in the main session and record main-window input tokens at completion. Then run it with delegation and record (a) main-window tokens, (b) the subagent's token count from the metadata trailer, (c) wall time for both, (d) whether the answer was correct. You now have the only numbers that matter: tokens saved in your window, total tokens spent across both windows, and latency delta.

**Step 2: find the break-even.** Vary the task size: a question answerable from one file, three files, ten files, and a whole subsystem. Plot main-window savings against task size. The crossover is where read volume exceeds the roughly 3,800-token cold start plus the returned summary, and finding it on your own repo is worth more than any rule of thumb.

**Step 3: break the handoff on purpose.** Run the ten-file task twice: once with "summarize what you found," once with the structured Answer / Evidence / Uncertain / Not examined contract. Then verify every `file:line` citation. Count the uncited claims in the unstructured run. This is the exercise that changes people's behaviour, because the unstructured summary reads perfectly and typically contains one or two assertions that are simply wrong and unfalsifiable from where you sit.

**Step 4: fan out and count the return.** Three read-only subagents on independent modules, with a strict 300-token output cap in each definition, then the same three with no cap. Measure the total tokens landing back in your main window. The uncapped version routinely returns more than a single unified read would have cost, which is the whole lesson.

**Step 5: fork versus fresh.** Same task, once as `/subtask` and once as a named subagent, comparing first-request cost (the fork should show a large cache read) and answer quality. Then pick a task where the fork is *wrong*: something that needs a restricted tool scope, and observe that a fork cannot give you one.

---

## How it's done in production

A subagent inventory that holds up looks like four or five agents, not fifteen:

```
.claude/agents/
├── codebase-researcher.md    # Read/Grep/Glob only, sonnet, structured report contract
├── test-runner.md            # Bash + Read, returns ONLY failing tests + error lines
├── readonly-db-analyst.md    # PreToolUse hook rejects any non-SELECT (see below)
└── diff-reviewer.md          # Read only, one artifact per invocation
```

Three configuration patterns that matter more than the prompts:

**Tool restriction as the primary control.** A researcher with `tools: Read, Grep, Glob` cannot write, regardless of what its instructions say or what a prompt-injected file tells it to do. This is the Level 3 control applied to delegation, and it is the reason the built-in Explore agent denies Write and Edit rather than merely discouraging them.

**Conditional rules with hooks.** For a read-only database analyst, the real control is a `PreToolUse` hook running a validator script that exits 2 on any SQL write, which the docs demonstrate directly. Instructions say "only run SELECT"; the hook makes it true.

**Model routing as a cost lever.** Subagents can run cheaper models: routing verbose exploration to Haiku or Sonnet while the lead reasons on Opus is the main reason the 15× token multiplier is survivable. Note the Explore default changed as of v2.1.198, inheriting the main conversation's model rather than always running Haiku, capped at Opus on the Claude API; if you want cheap exploration you now define a user or project subagent named `Explore` with `model: haiku`, which overrides the built-in.

**Failure-mode table**

| Symptom | Cause | Fix |
|---|---|---|
| Subagent's answer is confidently wrong and you cannot tell | No output contract, so claims arrive with no provenance and only the summary crossed back | Require `file:line` evidence per claim, plus explicit Uncertain and Not examined sections |
| Subagent ignored a project rule the main session follows | Explore and Plan **skip CLAUDE.md and git status**; and no rule reaches a subagent's *task* framing unless you write it | Use `general-purpose`/custom for rule-sensitive work; restate critical exclusions in the delegation prompt |
| Delegating made the session more expensive, not less | Cold start (~3,800 tokens) exceeded the read volume; or fan-out return values exceeded the inline cost | Apply the ratio test; cap subagent output length in the definition |
| Five parallel subagents blew up the main window | Each returned a detailed report; the docs warn about exactly this | Hard output caps; require the structured contract; synthesize in a second pass |
| Subagent re-derived context you already had, slowly | Non-fork subagents see none of your conversation and start cold | Use a fork (`/subtask`), which inherits history *and* shares the parent's prompt cache |
| Two parallel agents corrupted shared state | Uncoordinated parallel writes (the documented Grit failure) | Read-only fan-out by default; for writes, `isolation: "worktree"` and merge checkpoints |
| `Subagent spawn limit reached` | 200-per-session cap; finished and nested subagents and forks all count | The error already tells the model to finish inline. `/clear` resets. Raise `CLAUDE_CODE_MAX_SUBAGENTS_PER_SESSION` only if the decomposition is genuinely that wide |
| More than 20 running; new spawns fail | Concurrency cap. Note resumes take a slot **without** checking it, so they can push you past | Let the count drain; do not retry (the error says so) |
| Claude reported subagent results that had not happened | Pre-v2.1.211 behaviour with background subagents | Upgrade; background results now arrive as a completion notification in a later turn |
| Subagent returned an API error as if it were findings | Pre-v2.1.199 behaviour | Upgrade: foreground returns partial output with a cut-off note; background marks it failed and includes the last output |
| A weird `[harness: subagent output matched instruction-shaped pattern(s)` line | Output scanning flagged a report imitating harness output or mentioning bypass flags | Investigate the source it read. The scan is a signal, not a defence; restrict tools instead |
| Subagent asked for a permission and the lead "approved" it | It cannot. No agent message counts as your approval; only the permission system or you | Nothing to fix. Know this, because it is the correct answer to a common design question |

---

## Tradeoffs & when NOT to use it

- **Do not delegate small tasks.** Below roughly 4,000-6,000 tokens of reading, the cold start plus latency plus handoff risk exceeds the benefit. The docs' own guidance for the main conversation is the right default: use it when the task needs frequent back-and-forth, when multiple phases share significant context, for quick targeted changes, and when latency matters because subagents start fresh and need time to gather context.
- **Do not delegate work whose output you cannot verify from the summary.** If correctness depends on details that will not survive a 400-token report, delegation converts a checkable task into an unfalsifiable claim. Either shape the report until it is checkable, or keep it inline.
- **Do not fan out generation without fanning out review.** One subagent per independently reviewable artifact. Two subagents whose outputs only make sense together have parallelized the cheap half of the pipeline and serialized the expensive half, and review is the documented bottleneck across the industry.
- **Do not use subagents as a substitute for decomposition.** A task you cannot state as a bounded prompt with a defined output shape is not a delegation problem, it is a specification problem, and spawning an agent at it produces a plausible report about work that was never scoped.
- **Do not enable nesting because it sounds powerful.** It is off by default for a reason: debuggability collapses. Only the top-level subagent's summary returns to you, so a failure three levels down surfaces as a vague sentence with no trace you can read without digging into per-agent JSONL files. The legitimate case is narrow (a reviewer that dispatches a verifier per finding, keeping intermediate output out of your window) and you should be able to say why yours is that case.
- **Do not treat output scanning as a security boundary.** The docs say it does not judge maliciousness and does not change what an instruction in a report can do. Prompt injection through a file, a web page, or command output that a subagent read is a live path into your main conversation, and the control is `tools:` restriction plus `PreToolUse` hooks plus sandboxing, not the scan.
- **Do not ignore the 15× multiplier.** Anthropic's own reporting is that multi-agent systems consume roughly 15× more tokens than chat while agents generally use about 4×, and that token usage alone explains about 80% of performance variance in their evaluation. Two honest readings follow. The optimistic one: fan-out is a way to spend more tokens without any single window degrading. The uncomfortable one: a large share of the reported gain is *buying tokens*, so before you architect a multi-agent system you should check whether a single agent with a better prompt and more allowed turns gets you the same place cheaper. Their own conclusion is that the economics only work for high-value tasks.
- **The counter-argument to state:** the strongest critique of subagents is that they trade a visible problem (a full context window you can inspect with `/context`) for an invisible one (a handoff you cannot audit). In a single window you can see the wrong file being read; in a delegated run you get a fluent summary and no way to know it dropped the important case. That critique is correct in exact proportion to how weak your output contract is, which is why the contract, not the topology, is the engineering.

---

## Interview questions

### Q1 — When do you reach for a subagent?
**Testing:** whether you have a ratio or a vibe.
**Answer:** When the work it will read is much larger than the summary it returns, and much larger than the cold start. The canonical figure is the docs' own example: a research subagent reads 6,100 tokens of files and returns 420, a 14× reduction in my window. Against that I price roughly 3,800 tokens of cold start (its own system prompt ~900, its own full copy of the CLAUDE.md hierarchy ~1,800, MCP and skill metadata ~970, my delegation prompt ~120) plus a full round of latency because it starts from nothing. So: high-volume reads, verbose command output like a full test run where I only want the failures, and genuinely independent parallel research. Also two non-cost reasons: when I need a different tool scope (a read-only researcher that physically cannot write) or a different permission posture.
**Follow-up trap:** *"Give me a case where delegating is strictly worse."* A three-file question with frequent back-and-forth. I pay 3,800 tokens to save maybe 2,500, add latency, and lose the ability to steer mid-task, since a non-fork subagent cannot see the conversation where I would have clarified. The docs' guidance is the same: use the main conversation when the task needs iterative refinement, when multiple phases share significant context, for quick targeted changes, and when latency matters. The general principle is that delegation converts a steerable interaction into a one-shot RPC, and one-shot RPCs need a spec.

### Q2 — What crosses the boundary in each direction?
**Testing:** the mechanics, which is where most bugs live.
**Answer:** Down: its own system prompt plus env details (not the full Claude Code system prompt), the delegation prompt the lead writes, the entire CLAUDE.md hierarchy including user, project, `CLAUDE.local.md`, and managed policy files, a git-status snapshot from the parent session start, any skills named in its `skills:` field with **full content** injected at startup, and a sibling roster if it has `SendMessage` and other named agents exist. Not down: my conversation history, the files already read, skills already invoked, the main conversation's auto memory, my output style, and the parent's context window size, since a subagent's window is sized by its own model. Up: only the final text response, plus a small metadata trailer with token counts and duration, after an output scan. Its tool calls, file reads, and errors never cross back.
**Follow-up trap:** *"So how do you get a project rule to a subagent?"* Two paths and they solve different problems. Most rules arrive automatically, because every subagent except the built-in Explore and Plan loads the full CLAUDE.md hierarchy. But a rule that shapes the *task framing* rather than the code style has to be in the delegation prompt: the docs' own example is "ignore the `vendor/` directory," which no context file will convey because it is a property of this task. And the reason Explore and Plan are exceptions is deliberate cost control: they skip CLAUDE.md and git status to keep research cheap, on the reasoning that the main conversation reads their results *with* full CLAUDE.md context.

### Q3 — Design the return contract for a research subagent.
**Testing:** whether you know that shaping the return is the actual engineering.
**Answer:** Four sections, enforced in the subagent's system prompt so every invocation obeys it. **Answer**: two to four sentences, the direct answer, no preamble, because the caller may read only this. **Evidence**: `file:line` to one-line claim, capped at about eight entries, because I cannot see what it read and an uncited claim is unverifiable, and this is exactly where subagent hallucination concentrates. **Uncertain**: what it could not determine and why, with an explicit note that an empty list is suspicious. **Not examined**: what it deliberately did not read, so I know the boundary of the answer. What I never ask for is "summarize what you found," which reliably produces "the implementation looks reasonable overall," which is indistinguishable from a real answer and worth nothing.
**Follow-up trap:** *"Why does the 'not examined' section matter?"* Because the most expensive subagent failure is a confident answer with a silent scope gap: it read three of the five places a timeout is set, answered correctly about those three, and I generalized. I cannot detect that from the summary, because the summary is about what it *did* look at. Making the boundary explicit turns an invisible omission into a visible one, and it is the only section that lets me decide whether to spend another delegation. It is the same reason a spec needs an out-of-scope section: the negative space is the part you cannot infer.

### Q4 — Fork versus named subagent.
**Testing:** whether you know forks exist and what they trade.
**Answer:** A fork (`/subtask`) inherits the entire conversation, the same system prompt, tools, and model, so it drops input isolation deliberately and keeps the part that matters: its tool calls stay out of my window and only the final result returns. The decisive economics are the prompt cache: because its system prompt and tool definitions are identical to the parent, the first request reuses the parent's cache, making it materially cheaper than a fresh subagent for tasks needing the same context. So: fork when a named subagent would need too much background to be useful, or to try several approaches in parallel from the same starting point. Named subagent when I want a *different* tool scope, a different model, or a different permission posture, which a fork cannot give me by definition.
**Follow-up trap:** *"If forks are cheaper, why is the named subagent the default?"* Because input isolation is a feature, not just a cost. A fork carries all my accumulated assumptions, including the wrong ones, so it is the worst choice for anything I want an independent read on, most obviously reviewing my own work: fresh-context self-review works precisely because the errors are mostly context artifacts, and a fork inherits the context that produced them. It also cannot be restricted: a read-only researcher is a tool-scope decision, and a fork gets the parent's tools. So the split is by intent, isolation for independence and forking for continuity, not by price.

### Q5 — Multi-agent systems use 15× the tokens of chat. Justify that.
**Testing:** whether you have read the unfavourable half of Anthropic's own reporting.
**Answer:** Sometimes I cannot, and saying so is the point. Anthropic's own numbers: agents generally use about 4× the tokens of chat, multi-agent about 15×, their multi-agent research system outperformed single-agent Opus by 90.2% on their internal research eval, and **token usage alone explains about 80% of performance variance** on BrowseComp with tool calls and model choice covering most of the rest. Read honestly, that last figure says a large share of the gain is buying more tokens, arranged so no single window degrades. So the justification has to be task-specific: fan-out earns its cost when the work is genuinely parallel, read-heavy, and high-value, which is Anthropic's own conclusion, that the economics work for legal due diligence, competitive intelligence, literature review. For a bounded coding task, checking whether one agent with a better prompt and more turns gets there is the cheaper experiment and it frequently wins.
**Follow-up trap:** *"So how do you make it affordable?"* Model routing is the main lever: run verbose exploration on a cheaper model and reason on the expensive one, which is the lead-Opus-with-Sonnet-workers shape. Note the default moved: as of v2.1.198 the built-in Explore inherits the session model (capped at Opus on the Claude API) rather than always running Haiku, so cheap exploration is now something you configure by defining your own `Explore` subagent with `model: haiku`, which overrides the built-in. After that: hard output caps so returns do not undo the savings, read-only tool scopes so failures are cheap, and the ratio test so I stop delegating things that fit inline.

### Q6 — Five subagents in parallel made your session worse. Why?
**Testing:** the fan-out failure modes, which are non-obvious.
**Answer:** Most likely return-value bloat, which the docs warn about directly: many subagents each returning detailed results consumes significant context, so five reports at 2,000 tokens each is 10,000 tokens landing in my window at once, potentially more than reading the files inline would have cost. Second candidate is false independence: if B needed a conclusion A was still deriving, both read the shared code and reached possibly different conclusions, and now I am reconciling two accounts of the same thing with no ability to inspect either one's reasoning. Third, and the one that actually matters at my level, is serialized review: if the five outputs only make sense together, I parallelized generation and serialized review, which is backwards because review is the bottleneck.
**Follow-up trap:** *"What's your rule for fan-out width?"* One subagent per independently reviewable artifact, with a hard output cap in each definition, and read-only unless I have worktree isolation. Width is then set by how many artifacts I can actually review, not by how many I can spawn, and the platform limits (200 per session, 20 concurrent) are nowhere near the binding constraint. If I find myself wanting eight, the real question is whether the decomposition produces eight things I can evaluate separately, and usually it does not.

### Q7 — A subagent read a malicious file. What's the exposure?
**Testing:** whether you have thought about prompt injection across the delegation boundary.
**Answer:** Real, and the mitigation is not the one people name. A subagent may read files, web pages, or command output nobody reviewed, and text from those sources can carry instructions aimed at the main conversation, so its report is untrusted input. Claude Code scans each report before the main agent reads it, inserting a backslash into text imitating harness output like `<system-reminder>` tags or `Human:`/`Assistant:` lines, and prepending a `[harness: subagent output matched instruction-shaped pattern(s):` marker when a report imitates such a tag or mentions `bypassPermissions` or `--dangerously-skip-permissions`. But the docs are explicit that the scan does not judge maliciousness and does not change what an instruction in a report can do: a tool call the report leads Claude to make still goes through permission checks and sandboxing. **It is not a substitute for restricting what a subagent can reach.**
**Follow-up trap:** *"Then what is the control?"* Tool scoping first: a researcher with `tools: Read, Grep, Glob` cannot write no matter what a file tells it, which is why the built-in Explore *denies* Write and Edit rather than discouraging them. Then `PreToolUse` hooks for semantic restrictions the tool list cannot express, which is exactly the docs' read-only-database-analyst example where a validator script exits 2 on any non-SELECT. Then MCP server scoping per subagent, sandboxing, and `permissions.deny` in managed settings. And one structural fact that is a genuine defence: no message from any agent counts as my approval for a pending permission prompt, and no agent message can change a subagent's permission settings, `CLAUDE.md`, or configuration. Only the permission system or I can grant that, which closes the obvious confused-deputy path.

### Q8 — Should subagents spawn subagents?
**Testing:** judgment about a feature that is off by default.
**Answer:** Usually no, and the default is correct. Nesting is disabled, with the `Agent` tool withheld from every subagent except a fork, which keeps it in its tool list but gets an error instead of a spawn. The reason is debuggability: only the top-level subagent's summary returns to me, so a failure three levels down surfaces as one vague sentence, and reconstructing what happened means digging through per-agent JSONL transcripts. The legitimate case is narrow and specific: a reviewer subagent that dispatches a verifier per finding, so the intermediate verification output never reaches my main conversation. If that is genuinely the shape, nesting earns its keep, and I should be able to say why the intermediate output is worth hiding.
**Follow-up trap:** *"How would you debug a three-level failure?"* Transcripts, and I should know where they are before I need them: `~/.claude/projects/{project}/{sessionId}/subagents/agent-{agentId}.jsonl`, one per agent, persisting independently of the main conversation so main-session compaction does not touch them, retained per `cleanupPeriodDays` (default 30). Subagents run their own auto-compaction and log `compact_boundary` events with `preTokens`, so I can see whether a worker compacted mid-task, which is a strong explanation for a degraded report. And the honest answer to the follow-up is that this is exactly the argument against nesting: if my debugging story is "read the JSONL," I should flatten the topology instead.

### Q9 — Design the subagent layer for a team of 15 on a large monorepo.
**Testing:** whether you can restrain yourself.
**Answer:** Four or five agents, not fifteen, each defined by its *tool scope* rather than its persona. A `codebase-researcher` with `tools: Read, Grep, Glob` on a cheaper model with the structured report contract. A `test-runner` with Bash and Read that returns only failing tests and their error lines, which is the highest-value delegation in most repos because test output is the worst context-to-signal ratio in the system. A `readonly-analyst` for data questions with a `PreToolUse` hook rejecting non-SELECT statements, because instructions saying "only SELECT" are a recommendation and the hook is a constraint. And a `diff-reviewer` invoked once per reviewable artifact. Then a written norm: read-only by default, output capped, one per reviewable artifact, and the ratio test before delegating.
**Follow-up trap:** *"Why so few, when the mechanism is cheap to add?"* Because the cost is not in the definition, it is in the selection. Automatic delegation is driven by the `description` field, so overlapping subagent descriptions produce wrong-agent selection the same way overlapping skill descriptions do, and nobody measures it. Fifteen agents also means fifteen tool scopes and fifteen prompts to keep true as the repo changes, and stale agent definitions fail the same aspirational way stale context files do. My rule is that a new subagent has to justify itself by tool scope or by a measured token ratio, not by "we also do X."

### Q10 — Your main session is at 180K tokens and you have not delegated anything. What went wrong?
**Testing:** whether you can diagnose backwards from the symptom.
**Answer:** Something high-volume went into the main window that had no business being there, and the usual suspects are ordered: a full test-suite run, a log file, a wide `grep`, a schema dump, or exploratory reading of a subsystem. The tell is `/context` showing file and tool output dominating rather than conversation. The fix is not "compact," because compaction costs about $0.40 on a 125K context, destroys the prompt cache, and discards the evidence while keeping the narrative. The fix is to restructure: start a fresh session, delegate the high-volume reads to a subagent with a capped structured return, and keep the main window for reasoning and decisions. Then prevent recurrence: delegate verbose command output by default, and bound output at the tool boundary rather than after it lands.
**Follow-up trap:** *"Can you fix it without restarting?"* Partially and not well. I can delegate from here, which helps future turns but does nothing about the 180K already in the buffer. `/compact` with a focus and a good `Compact Instructions` block is the least-bad in-place option and it still loses the verbatim evidence. Honestly, the cheapest thing is a fresh session with a written handoff, because I am already at the point where the model's ability to notice a problem in the transcript is degraded, which is the MonitorBench effect: 2× to 30× more missed dangerous actions with a long benign prefix. That is precisely when I least want to be doing careful review, so I would restart.

### Q11 — What's the strongest argument against subagents?
**Testing:** the closing question, where genuine criticism outperforms advocacy.
**Answer:** They trade a visible problem for an invisible one. A full context window is inspectable: `/context` tells me what is in it, and I can watch the wrong file being read and correct it mid-turn. A delegated run gives me a fluent 420-token summary and no way to know it dropped the important case, and the errors that survive are precisely the confident ones. Add the 15× token multiplier and the finding that token usage alone explains about 80% of performance variance, and a sceptic can reasonably say multi-agent architecture is an expensive way to buy tokens while making failures harder to see. That critique is correct in exact proportion to how weak the output contract is, which is why I treat the contract as the engineering and the topology as an implementation detail.
**Follow-up trap:** *"Given that, would you use fewer subagents?"* Fewer and more sharply defined, yes. The two delegations I would keep unconditionally are verbose-output isolation (test runs, log analysis) where the ratio is overwhelming and the return is trivially verifiable because it is a list of failures, and fresh-context self-review where isolation is the *point* rather than a cost. The ones I would cut are the speculative research fan-outs, where five plausible reports arrive and I have neither the provenance to check them nor the budget to re-derive them. The general principle: delegate where the return value is mechanically checkable, keep inline where it is a judgment I have to make anyway.

---

## Red flags that fail you

- Delegating without a token ratio in mind.
- Not knowing a subagent loads its own full copy of the CLAUDE.md hierarchy.
- Not knowing Explore and Plan skip CLAUDE.md and git status.
- Asking a subagent to "summarize what you found."
- No provenance requirement on returned claims.
- Fan-out with no output cap.
- Parallelizing generation while serializing review.
- Treating output scanning as a security boundary.
- Enabling nesting without a specific reason.
- Assuming the lead agent can approve a worker's permission prompt.
- Quoting the 90.2% improvement without the 15× cost.
- Using a subagent when the real problem is that the task is not specified.

## Cheat card

```
WHAT A SUBAGENT IS   fresh context window + own system prompt + own tool scope
  + independent permissions. only the FINAL TEXT crosses back.

THE CANONICAL NUMBERS
  cold start ≈3,800 tok: own sys prompt ~900 · OWN COPY of the whole CLAUDE.md
    hierarchy ~1,800 · MCP+skills ~970 · your delegation prompt ~120
  then reads 6,100 tok of files → returns 420 → 14× reduction in YOUR window
  DELEGATE WHEN: reads ≫ summary AND reads ≫ 3,800

CROSSES DOWN   own sys prompt+env · your delegation prompt · FULL CLAUDE.md
  hierarchy (user+project+local+managed) · parent git-status snapshot ·
  `skills:` preload (FULL content) · sibling roster (if SendMessage + named peers)
NEVER DOWN     your conversation · files already read · skills already invoked ·
  main auto memory · output style · parent's window size (sized by ITS model)
CROSSES UP     final text ONLY + token/duration trailer + output scan
EXCEPTIONS     Explore and Plan SKIP CLAUDE.md AND git status (cost control).
               no frontmatter field changes that.

BUILT-INS  Explore: read-only, Write/Edit DENIED, inherits session model (capped at
    Opus on Claude API since v2.1.198; define your own Explore with model:haiku for
    cheap). thoroughness: quick | medium | very thorough.
  Plan: read-only research during plan mode.  general-purpose: all subagent tools.

LIMITS (three separate ones)
  200 spawned/session  CLAUDE_CODE_MAX_SUBAGENTS_PER_SESSION → "Subagent spawn
    limit reached", model told to finish inline. /clear resets. forks+nested count.
  20 concurrent        CLAUDE_CODE_MAX_CONCURRENT_SUBAGENTS → "do not retry".
    RESUMES take a slot WITHOUT checking → can push past the limit.
  nesting DEPTH 1      Agent tool withheld (fork keeps it but it errors)

RETURN CONTRACT (the actual engineering)
  ## Answer      2-4 sentences, no preamble
  ## Evidence    file:line → claim. EVERY claim cited. cap ~8.
  ## Uncertain   what it could not determine. EMPTY LIST IS SUSPICIOUS.
  ## Not examined  the boundary of the answer
  NEVER "summarize what you found" → "looks reasonable overall" = worthless

FORK (/subtask) vs NAMED SUBAGENT
  fork: full history · same prompt/tools/model · SHARES PARENT PROMPT CACHE
        (≈0 cold start) · cannot restrict tools · inherits your wrong assumptions
  named: fresh + your prompt · own tools/model/permissions · ~3,800 cold start
  fork for CONTINUITY · named for INDEPENDENCE or a different tool scope
  Agent tool can pass isolation:"worktree" so a fork's edits land outside your checkout

FAN-OUT FAILURES  1 return-value bloat (5×2,000 > inline cost)
  2 false independence (both read shared code, disagree, you can't inspect either)
  3 SERIALIZED REVIEW ← the one that matters: one subagent per INDEPENDENTLY
    REVIEWABLE ARTIFACT
  4 uncoordinated writes (Grit, ~45B tokens, a parallel agent broke the test harness)

COST  agents ≈4× chat tokens · MULTI-AGENT ≈15× · Opus-lead+Sonnet-workers beat
  single Opus by 90.2% on Anthropic's research eval · TOKEN USAGE ALONE EXPLAINS
  ≈80% OF PERFORMANCE VARIANCE (BrowseComp) → much of the gain is buying tokens.
  levers: model routing · output caps · read-only scopes · the ratio test

SECURITY  subagent reports are UNTRUSTED INPUT (it read files/web/output you didn't)
  output scan: backslash-escapes fake <system-reminder>/Human:/Assistant:, prepends
    "[harness: subagent output matched instruction-shaped pattern(s):" for those and
    for bypassPermissions mentions. NEVER removes/rewords.
  DOCS ARE EXPLICIT: not a judgment of maliciousness, NOT a substitute for
    restricting what a subagent can reach.
  REAL controls: tools: allowlist · PreToolUse hook exit 2 (e.g. reject non-SELECT) ·
    per-subagent MCP scoping · sandboxing · permissions.deny (managed)
  NO agent message = your approval; NO agent message can change a subagent's
    permissions/CLAUDE.md/config. only the permission system or you.

TRANSCRIPTS  ~/.claude/projects/{project}/{sessionId}/subagents/agent-{id}.jsonl
  survive main-session compaction · cleanupPeriodDays default 30
  subagents auto-compact too → compact_boundary events with preTokens
  Explore/Plan are ONE-SHOT: no agent ID, cannot be resumed. use general-purpose.
  resume via SendMessage(to=id|name); name-reuse check refuses misdelivery
```

## Sources

- [Create custom subagents](https://code.claude.com/docs/en/sub-agents) — the built-in agents and their tool restrictions; Explore and Plan skipping CLAUDE.md and git status; what loads at startup and what never reaches a non-fork subagent; the 200-per-session and 20-concurrent limits with their env vars and error strings; resume via `SendMessage` and the name-reuse check; the confused-deputy rules (no agent message is your approval, none can change permissions/CLAUDE.md/config); output scanning and its explicit limits; nesting defaults; foreground versus background; fork semantics including shared prompt cache and `isolation: "worktree"`; the read-only-database-analyst `PreToolUse` hook pattern; transcript paths and `cleanupPeriodDays`; and subagent auto-compaction with `compact_boundary`/`preTokens`; accessed 2026-07-26
- [Explore the context window](https://code.claude.com/docs/en/context-window) — the itemized subagent cold start (~900 system prompt, ~1,800 own CLAUDE.md copy, ~970 MCP + skills, ~120 task prompt) and the 6,100-tokens-read / 420-tokens-returned example; accessed 2026-07-26
- [How Claude Code works](https://code.claude.com/docs/en/how-claude-code-works) — subagents as the mechanism for managing context beyond compaction, and the main-conversation-versus-subagent guidance; accessed 2026-07-26
- [How we built our multi-agent research system](https://www.anthropic.com/engineering/built-multi-agent-research-system) — Anthropic Engineering; the ~4× (agents) and ~15× (multi-agent) token multipliers versus chat, the 90.2% improvement of Opus-lead-with-Sonnet-workers over single-agent Opus, and the finding that token usage alone explains about 80% of performance variance on BrowseComp; accessed 2026-07-26
- [Extend Claude with skills](https://code.claude.com/docs/en/skills) — the `context: fork`, `agent:`, and `background:` frontmatter that runs a skill in a forked subagent, and the note that preloaded subagent skills inject full content at startup; accessed 2026-07-26
- [Extend Claude Code](https://code.claude.com/docs/en/features-overview) — the context-cost table showing subagents as isolated from the main session; accessed 2026-07-26
- [Multi-Agent AI Coding Workflow: Git Worktrees That Scale](https://blog.appxlab.io/2026/03/31/multi-agent-ai-coding-workflow-git-worktrees/) — the Grit case (a Git rewrite in Rust, roughly 45 billion tokens) where a parallel agent broke the test harness through uncoordinated writes; accessed 2026-07-26
- [Agent Harnesses — Microsoft Learn](https://learn.microsoft.com/en-us/agent-framework/agents/harness) — the optional background-agents capability for delegating parallel work, as independent convergence on the same topology; page updated 2026-07-08, accessed 2026-07-26
- [Classifier Context Rot: Monitor Performance Degrades with Context Length](https://arxiv.org/html/2605.12366v1) — the 2×-to-30× degradation in noticing dangerous actions with a long benign prefix, which is the argument for isolating high-volume reads; accessed 2026-07-26

## Changelog
- 2026-07-26 — created
