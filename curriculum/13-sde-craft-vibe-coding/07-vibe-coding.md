# AI-Assisted Coding: CLAUDE.md, Skills, Subagents, Spec-Driven Dev

> **Track:** T13 SDE Craft & Vibe Coding · **Time:** 2.5h · **Prereqs:** `T13-code-review`, `T27-reviewing-ai-code`, `T13-testing-practice` · **Updated:** 2026-08-05
> **Module id:** `T13-vibe-coding` · **Tags:** agentic-coding, workflow, context-engineering, spec-driven, critical

## The 30-second version

Operating a coding agent well is a context-engineering problem and a verification problem, not a prompting problem. The context side: everything loaded at session start is a recurring tax on every turn, so a CLAUDE.md holds only facts needed in every session (build commands, conventions, the three things the agent gets wrong repeatedly, target under 200 lines), procedures move to skills that load on demand, high-volume reads move to subagents with their own context windows, and MCP tool schemas stay deferred until a task needs them. The verification side: the agent's real feedback signal is types, tests, and lint, which means the honest failure mode is that oversight collapses onto the test suite, and SpecBench measured the resulting reward-hacking gap growing 28 percentage points for every tenfold increase in code size, so tests you wrote before the agent started are worth far more than tests the agent wrote to satisfy itself. Spec-driven development exists to give the agent a target it can verify against without being the author of the target. The honest limit: this workflow multiplies throughput on well-specified, verifiable, medium-blast-radius work and does close to nothing for novel algorithms, deep concurrency debugging, or any problem where writing the spec is the hard part, and METR's RCT found experienced developers on mature repos were 19% slower with early-2025 AI tooling while believing they were 20% faster.

## Why this gets asked

Because by 2026 the interviewer's org has already adopted agentic coding at scale (Sundar Pichai stated in April 2026 that 75% of new code at Google is AI-generated and engineer-approved, up from 50% the previous autumn), and the failure they have personally lived through is not "the AI wrote bad code." It is a senior engineer who let an agent run for three hours on a vague task, came back to a 4,000-line diff touching 60 files, and could not answer "what exactly changed and why" in the incident review; or a merged PR where the agent had quietly weakened three assertions to get CI green; or a team whose CLAUDE.md grew to 900 lines of aspirational rules that the model demonstrably stopped following. Interviewers hiring at staff and principal level are screening for whether you treat the agent as a system component with known failure modes and a verification harness around it, or as a magic autocomplete you supervise by vibes. Google's 2026 pilot makes this explicit: the AI-assisted coding round is scored on "AI fluency, including prompt engineering, output validation, and debugging skills," and candidates who lean on the assistant without demonstrating independent understanding get negative feedback.

---

## Lineage: past → present → future

**What came before.** The 2021 to 2023 era was inline completion: Copilot suggesting the next few lines from the current file plus a handful of neighbors, with a context window measured in low thousands of tokens. The interaction model was accept or reject a suggestion, and the engineer stayed the author. The pain that killed it as the ceiling of the field was that the tool had no access to the parts of the system that determine whether a change is correct: it could not read the test suite, could not run it, could not see the type errors its suggestion introduced, and could not follow an import two files over. Every suggestion was a guess about local syntax, so the engineer's cost of verification stayed roughly proportional to the code produced, and throughput gains capped out around "types faster." The 2023 to 2024 chat era (paste code into a window, paste the answer back) removed the file-locality limit but added a worse one: the human became the transport layer for context in both directions, manually deciding what to paste in and manually reconciling what came out with a codebase the model had never seen. Both eras shared one structural defect: no closed verification loop. Nothing the model produced was ever checked by a compiler or a test before a human looked at it.

**Where it stands now.** The 2025 to 2026 consensus is the agentic loop with tool access: the model reads files, runs the build, runs the tests, reads the failures, and iterates, which closes the verification loop and makes the compiler and test suite the actual reward signal. Around that loop a fairly stable set of primitives has settled: a persistent instruction file at the repo root (`CLAUDE.md` for Claude Code, `AGENTS.md` as the cross-tool convention, formalized as an open spec in August 2025 by OpenAI with Google, Cursor, and Factory, donated to the Linux Foundation's Agentic AI Foundation in December 2025, adopted in over 60,000 public repositories and read by 30-plus tools); on-demand procedures (Agent Skills, an open standard at agentskills.io, loaded only when invoked so the body costs nothing until used); isolated worker contexts (subagents, each with its own window, returning only a summary); and a tool-surface protocol (MCP, whose 2026-07-28 revision is the largest since launch, making the core stateless, adding `ttlMs`/`cacheScope` on list endpoints and a formal deprecation policy). Spec-driven development is the current answer to the "what does the agent verify against" question, with GitHub's Spec Kit (106K-plus stars, 30 integrations, `Spec → Plan → Tasks → Implement`) the most visible implementation. The live disagreements are real and unsettled. First, whether SDD's ceremony pays for itself: for a two-file bug fix the spec artifacts cost more than the fix, and practitioners split hard on where the crossover point sits. Second, whether the productivity gains are real at senior level on mature code: METR's randomized trial (16 experienced open-source developers, 246 tasks, repos they averaged 5 years on) found a 19% slowdown against a forecast 24% speedup, and METR itself published a revision to its experiment design in February 2026, so treat both the headline number and its confident dismissals with suspicion. Third, whether parallel subagents help or hurt: they demonstrably cut main-context growth, and they demonstrably fragment shared understanding on tasks with cross-cutting invariants.

**Where it's heading.** Three directions with different confidence levels. High confidence: verification moves further into the loop rather than after it, so the agent's own generation is gated on type resolution, import existence, and a pre-written test suite before a human sees a diff at all. This is already shipping in several 2026 assistants and is a direct response to measured reward hacking. Medium confidence: the instruction-file layer converges on a single cross-tool format with progressive disclosure semantics rather than one monolithic file per tool, which is exactly what the open AGENTS.md v1.1 proposal argues for; the pressure here is real (nobody wants to maintain four dialects of the same conventions) but vendor differentiation cuts the other way. Low confidence and explicitly speculative: that "spec as source of truth, code as build artifact" becomes the normal way software is maintained rather than a workflow a minority of teams use for greenfield features. That claim requires specs to be more maintainable than code for systems with a decade of accumulated edge cases, and there is currently no evidence for that at scale. Treat any 2026 vendor claim that specs have replaced code as marketing.

---

## Mental model

```
THE CONTEXT BUDGET IS THE WHOLE GAME

  Every token loaded at session start is paid AGAIN on every single turn.
  Everything else in this module is a consequence of that one fact.

  ALWAYS LOADED (a tax on every turn)     LOADED ON DEMAND (free until used)
  ─────────────────────────────────      ─────────────────────────────────
  system prompt        ~4,200 tok        skill BODY  (only when invoked)
  project CLAUDE.md    ~1,800 tok        path-scoped rule (on matching read)
  user CLAUDE.md         ~320 tok        MCP tool SCHEMA (on ToolSearch)
  auto memory MEMORY.md  ~680 tok        nested CLAUDE.md (on subdir read)
  skill DESCRIPTIONS     ~450 tok        subagent's file reads (never yours)
  MCP tool NAMES         ~120 tok
  env + git status       ~280 tok
  (representative numbers from the Claude Code context-window doc)

  => The question for any piece of knowledge is never "is this useful?"
     It is "is this useful in EVERY session, or only in SOME?"
     Useful-in-some belongs on disk, not in RAM.

THE FOUR PLACES A FACT CAN LIVE, AND THE TEST FOR EACH

  CLAUDE.md / AGENTS.md   "the agent must know this EVERY session"
                          facts, not procedures. build cmd, conventions,
                          the 3 things it gets wrong repeatedly. <200 lines.

  .claude/rules/*.md      "must know this whenever touching THESE files"
                          paths: frontmatter. loads on matching file read.

  skill (SKILL.md)        "must know this for SOME tasks"
                          a PROCEDURE with steps. body loads on invoke.

  hook (settings.json)    "this must happen REGARDLESS of what it decides"
                          shell command on a lifecycle event. Not context.
                          The only one of the four that is ENFORCEMENT.

  Rule of thumb: if you would be upset when the agent skips it,
  it is a hook, not a CLAUDE.md line. CLAUDE.md is advice; hooks are law.

THE ARCHITECT'S LOOP (what you actually do all day)

   1. SPEC      you write: what "done" means, in checkable terms
   2. TESTS     you (or agent under your review) write: the target
                ^^^ these two are the parts you cannot delegate
   3. PLAN      agent proposes; you reject the plan, not the diff
   4. IMPLEMENT agent writes code, runs types/tests/lint, iterates
   5. VERIFY    the loop closes on YOUR tests, not tests it invented
   6. REVIEW    the diff, against the spec (see T27-reviewing-ai-code)

   Steps 1, 2, 3, 6 are yours. Step 4 is the only one you delegated.
   Anyone who describes step 4 as "the work" is doing this wrong.

WHY VERIFICATION IS THE HARD PART, NOT GENERATION

   oversight surface = the test suite
   agent optimizes   = "make the test suite green"
   these are the same objective ONLY IF the suite fully encodes the spec.

   SpecBench (arXiv 2605.21384, May 2026): the gap between visible-test
   pass rate and held-out-test pass rate grows +28 percentage points per
   10x increase in code size. Every frontier agent saturated the visible
   suite. One produced a 2,900-line hash table that memorized test inputs.

   => Long-horizon autonomy and trustworthy verification are in DIRECT
      tension. The longer you let it run, the less your tests mean.
```

## How it actually works

### What belongs in CLAUDE.md, and what is wasted tokens

The official guidance is a hard number: target under 200 lines per CLAUDE.md file, because the file is loaded in full into context at the start of every session and longer files both consume more tokens and measurably reduce adherence. Note the second half of that sentence, since it is the part people ignore. Adding a rule to an already-long CLAUDE.md does not monotonically increase the chance the rule is followed; past some length it decreases the chance every rule is followed, because the file is delivered as a user message after the system prompt and competes with everything else in the window for attention.

What earns its place:

- **Commands that are not guessable.** `pytest -m "not integration"` when the repo has a two-tier test suite. `make lint` when the repo does not use the obvious linter invocation. The agent will otherwise run the wrong thing and get a misleading signal.
- **Conventions that differ from the tool's default.** "This repo uses `pydantic` v1 style validators; do not migrate them" is worth 40 tokens forever. "Write clean, readable code" is worth zero and actively costs you attention budget.
- **The three to five things the agent gets wrong repeatedly in this repo.** The correct trigger for adding a line is: the agent made the same mistake a second time, or you typed the same correction you typed last session. Not "this might be useful someday."
- **Architecture facts a codebase read would not reveal cheaply.** "Service A owns the `orders` table; B reads it only through A's API" is not derivable from a grep and prevents a whole class of blast-radius mistake.

What is wasted tokens:

- **Directory layouts and dependency lists.** The agent can derive these from the codebase faster than you can keep them accurate, and a stale one is worse than none. The `/doctor` trim check in recent versions specifically proposes cutting derivable content (directory layouts, dependency lists, architecture overviews) and keeping pitfalls, rationale, and conventions that differ from tool defaults.
- **Multi-step procedures.** "How to cut a release" is a skill, not a memory. It is needed in maybe 1 session in 30 and costs tokens in all 30.
- **Aspirational rules with no verification.** "Always write comprehensive tests" is unenforceable advice. A hook that fails the commit when coverage on changed lines drops is enforcement. The distinction matters because CLAUDE.md is context, not configuration: the docs state plainly that to block an action regardless of what the model decides, you use a `PreToolUse` hook.
- **Duplicated content from a linter config.** If `ruff` already enforces it and runs in the loop, the agent gets the feedback mechanically. Writing it in prose too is paying twice for one constraint.

**Layering.** Files load from managed policy (`/etc/claude-code/CLAUDE.md` on Linux, `C:\Program Files\ClaudeCode\CLAUDE.md` on Windows) through user scope (`~/.claude/CLAUDE.md`) to project scope (`./CLAUDE.md` or `./.claude/CLAUDE.md`) to local (`./CLAUDE.local.md`, gitignored). They concatenate rather than override, ordered root-of-filesystem-down, so the closest file is read last. That concatenation behavior is the trap in a monorepo: ancestor files from other teams land in your context whether or not they are relevant, which is why `claudeMdExcludes` exists as a glob-based skip list. `@path/to/file` imports expand at launch to a maximum depth of 4 hops, so imports help organization and do not help context: the imported bytes still load. Only path-scoped rules and nested subdirectory files are genuinely lazy.

**AGENTS.md versus CLAUDE.md.** These are not competitors, they are a naming problem. AGENTS.md is the cross-tool convention: plain markdown, no required fields, nearest file in the tree wins, explicit chat instructions override everything. The OpenAI Codex repo reportedly ships 88 of them for its subprojects. Claude Code reads `CLAUDE.md` and not `AGENTS.md`, so the correct move in a repo that already has AGENTS.md is a one-line `CLAUDE.md` containing `@AGENTS.md` plus any Claude-specific additions below it, or a symlink if you have nothing to add (`ln -s AGENTS.md CLAUDE.md`, which needs Administrator or Developer Mode on Windows, so prefer the import there). Maintaining two files with drifting content is the actual failure mode, and it is common.

### Context engineering: what to load, what to exclude, when to compact

Three levers, in order of how much they matter.

**Exclude by delegation.** File reads dominate context growth. A 2,400-token read of `auth.ts` is 2,400 tokens you pay on every subsequent turn for the rest of the session, whether or not you ever reference it again. A subagent doing the same read pays it in its own window and returns a summary. This is why "use a subagent to run the test suite and report only the failing tests" is a real technique and not ceremony: a full pytest run against a large suite can be tens of thousands of tokens of noise for three lines of signal.

**Compact deliberately, not reactively.** Automatic compaction exists so a full window does not end your session, but the automatic pass guesses what matters. `/compact focus on the auth bug fix` keeps what you choose. The mechanically important part is what survives: system prompt and output style are untouched; project-root CLAUDE.md, unscoped rules, and auto memory are re-injected from disk; **rules with `paths:` frontmatter and nested CLAUDE.md files are lost** until a matching file is read again; invoked skill bodies are re-injected but capped at 5,000 tokens per skill and 25,000 tokens total, oldest dropped first. Two direct consequences for how you write things. First, if a rule must survive compaction, drop its `paths:` frontmatter or move it to the root file, accepting the always-loaded cost. Second, because skill re-injection truncates and keeps the start of the file, put the load-bearing instructions at the top of `SKILL.md`, not in a "Notes" section at the bottom.

**Clear between unrelated tasks.** `/clear` is underused. Old conversation crowds out the files you need next and costs tokens on every message. The auto-compact window is tunable from 100K to 1M tokens (`/autocompact 500k`, the `--autocompact` flag, or `CLAUDE_CODE_AUTO_COMPACT_WINDOW`), and a larger window is not free: NoLiMa evaluated 12 models claiming 128K-plus support and found 11 of 12 dropped below 50% of their short-context performance by 32K tokens on tasks requiring non-literal retrieval. Chroma's context-rot work reports the same shape, with focused prompts substantially outperforming full prompts containing the same relevant information plus distractors. A 1M-token window is a capacity number, not a quality guarantee. "Just use the bigger window" is the wrong answer to context pressure roughly as often as "just add more RAM" is the wrong answer to a memory leak.

### Skills as reusable procedure, not prompt-stuffing

A skill is a `SKILL.md` with YAML frontmatter, discovered from `.claude/skills/<name>/` (project) or `~/.claude/skills/` (user), following the agentskills.io open standard. The economics are the point: only the `description` (plus optional `when_to_use`, combined and truncated at 1,536 characters in the listing) sits in context at startup; the body loads only on invocation. So a 3,000-word deployment runbook costs you roughly 30 tokens of description until the day you deploy.

The frontmatter fields that change behavior rather than decorate it:

- `disable-model-invocation: true` keeps the skill out of the auto-invoked set so it only fires on `/name`. Correct for anything destructive or expensive.
- `paths:` scopes automatic activation to matching files, the same glob semantics as path-scoped rules.
- `allowed-tools` pre-approves tools for the turn that invoked the skill, and the grant clears on your next message. It grants, it does not restrict; `disallowed-tools` is the restricting one.
- `context: fork` runs the skill in a subagent, with the SKILL.md content as the driving prompt. It backgrounds by default; `background: false` waits in-turn. The documented trap: `context: fork` on a reference-style skill ("use these API conventions") produces a subagent with guidelines and no task, which returns nothing useful.
- `model` and `effort` let a cheap skill run on a cheap model without changing the session default.

The lifecycle detail that catches people: once invoked, the rendered content enters the conversation as a single message and stays for the rest of the session. The file is not re-read on later turns. So write standing instructions ("throughout this task, X"), not one-time steps that assume the model reads them fresh each turn. Re-invoking with identical rendered content adds a short "already loaded" note rather than a duplicate copy.

**Skill versus prompt-stuffing.** The failure this replaces is a 400-line CLAUDE.md section titled "Release Process." The test is mechanical: does the content have steps and an outcome (skill), or is it a fact that shapes all work (CLAUDE.md/rule)? A section of CLAUDE.md that has grown into a procedure is the canonical trigger to extract a skill.

### Subagents: when parallelism pays and when it fragments

Each subagent gets a fresh, isolated context window with its own system prompt, tool access, and permissions. What loads into a non-fork subagent at startup: its own prompt plus appended environment details, the delegation message the parent wrote, the full CLAUDE.md hierarchy, a git-status snapshot from the parent session start, and any skills named in its `skills` field. What does not: your conversation history, the files you already read, your output style, and your auto memory. The built-in `Explore` and `Plan` agents additionally skip CLAUDE.md and git status to stay cheap, which is a real behavioral difference: a rule like "ignore `vendor/`" will not reach them, so it has to be restated in the delegation prompt.

Current operational limits worth knowing because they are the ones you hit: 200 subagents per session (`CLAUDE_CODE_MAX_SUBAGENTS_PER_SESSION`), 20 concurrent (`CLAUDE_CODE_MAX_CONCURRENT_SUBAGENTS`), and nesting 3 layers deep by default (`CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH`, which defaulted to 5 in v2.1.172-v2.1.216, dropped to 1 in v2.1.217-v2.1.218, and settled at 3 in v2.1.219; if you are quoting a nesting default in an interview, quote the version too). Subagent transcripts live in `~/.claude/projects/{project}/{sessionId}/subagents/agent-{id}.jsonl` and are cleaned up after `cleanupPeriodDays`, default 30. Subagents auto-compact on the same logic as the main conversation, logging `compact_boundary` with `preTokens`.

**Parallelism pays** when the subtasks are genuinely independent and each produces high-volume output you will not reference again: reading three unrelated modules to answer three unrelated questions, running a test suite, grepping a large codebase for callers, fetching and summarizing documentation. The win is arithmetic, not magic: N verbose investigations cost you N summaries instead of N full transcripts.

**Parallelism fragments** when the subtasks share an invariant. Three subagents each editing a different service to implement one cross-cutting change will each make a locally reasonable and mutually incompatible decision about the shared contract, because none of them can see the other two's reasoning; only their summaries return, and summaries are exactly where "I named the field `userId`" gets dropped as an implementation detail. It also fragments when the task needs iterative refinement, because a subagent starts cold and cannot be steered mid-flight as cheaply as the main conversation can. And the returns themselves cost context: many subagents each returning detailed results will consume significant context in the parent, which is the failure mode where someone "used parallelism to save context" and finished with a fuller window than if they had done it inline.

The decision rule that survives contact: **delegate reads, keep writes.** Investigation, search, log analysis, doc fetching, and test running go out. Anything that decides a shared contract stays in the main conversation where you can see the reasoning.

### MCP as tool surface

MCP is the protocol for exposing tools, resources, and prompts to an agent over a standard interface. The 2026-07-28 revision is the largest since launch: the core became stateless (the `initialize`/`notifications/initialized` handshake is gone, with protocol version and client capabilities riding in `_meta` on each request), `tools/list`/`prompts/list`/`resources/list`/`resources/read` responses now carry `ttlMs` and `cacheScope` so clients can cache, list endpoints no longer vary per connection, servers should return tools in deterministic order to improve prompt-cache hit rates, Streamable HTTP requests must carry `Mcp-Method` and `Mcp-Name` headers so gateways can route and rate-limit without parsing JSON bodies, and there is now a formal deprecation policy.

For the coding-agent workflow specifically, two numbers matter. First, **tool schemas are the hidden context cost**, which is why tool search is on by default in Claude Code: only tool names and server instructions load at startup, and full schemas are fetched on demand. `ENABLE_TOOL_SEARCH=auto` switches to threshold loading, pulling schemas upfront when they fit within 10% of the context window and deferring the overflow. This is the difference between "I added 6 MCP servers" being free and being a 20K-token startup tax. Second, **MCP output is capped**: a warning fires above 10,000 tokens of tool output and the default hard limit is 25,000 (`MAX_MCP_OUTPUT_TOKENS`), with per-tool overrides via the `anthropic/maxResultSizeChars` annotation. A server that returns an unpaginated query result will silently truncate, and the observable symptom is an agent confidently reasoning about a partial result set.

The judgment call an interviewer is actually probing: MCP is the right answer when the agent needs a *live* system (query the staging database, read the Jira ticket, hit the internal service catalog). It is the wrong answer when a CLI already exists, because a bash command costs zero startup context and an MCP server costs a schema plus a process. "We wrapped our CLI in an MCP server" is usually a step backwards for a coding agent.

### Spec-driven development: giving the agent a target it can verify against

The core insight is not "write documentation first." It is that an agent optimizing against a verification signal will find the cheapest path to a green signal, so **whoever writes the verification signal controls the outcome**, and that job cannot be delegated to the thing being verified. SpecBench made this quantitative: decompose a task into a natural-language spec, visible validation tests, and held-out composition tests; a genuine solution passes both. Every frontier agent saturated the visible suite while the held-out gap persisted, and the gap grew 28 percentage points per tenfold increase in code size. The 2,900-line hash table that memorized test inputs is the memorable case, but the boring case is more common and more dangerous: features implemented correctly in isolation, exactly as each visible test exercises them, that break the moment they compose.

The practical workflow that follows, independent of tooling:

1. **Spec first, in checkable language.** Not "add rate limiting." Instead: "requests exceeding 100/min per API key return 429 with a `Retry-After` header; the counter is per-key not per-IP; limits reset on a fixed 60s window, not sliding; exceeding the limit does not consume the request's normal quota." Every clause is a test. Ambiguity in the spec becomes a plausible wrong choice in the implementation, and the agent will not surface the ambiguity because "pick the most likely continuation" is what it does.
2. **Tests before implementation, written or reviewed by you.** This is the whole ballgame. Tests the agent writes after seeing its own implementation are a description of what it built, not a check on it. Tests written against the spec, before any implementation exists, are the only ones with independent evidentiary value.
3. **Plan review, not diff review, for large changes.** Rejecting a plan costs one message. Rejecting a 3,000-line diff costs a re-run and your attention on code that was never going to survive. Plan mode exists for exactly this.
4. **Small commits with a verification gate between them.** The reward-hacking gap scales with code size, so the mitigation is bounded scope per verified checkpoint.

**GitHub Spec Kit** is the most adopted formalization of this: a `specify` CLI plus slash commands that structure work into `Spec → Plan → Tasks → Implement`, each phase producing a markdown artifact that feeds the next. As of its docs (last updated 2026-05-27) it reports 106K-plus GitHub stars, 30 agent integrations, 105 community extensions, 22 presets, and 200-plus contributors, and it ships checklists and cross-artifact analysis for consistency between the spec, plan, and tasks. It works offline and behind firewalls, with self-hostable extension catalogs.

Be blunt about the cost. The four-phase artifact chain is real overhead: for a one-file bug fix it is strictly worse than reading the code and fixing it. The honest crossover is roughly where a change spans enough files that you would have written a design doc anyway. Below that, SDD tooling is ceremony that produces markdown nobody reads again. Practitioners genuinely disagree about where that line sits, and anyone who tells you SDD is always right or always overhead is selling something.

## Build it from scratch

A minimal, tool-agnostic spec-driven loop, no framework required. This is the version to describe in an interview because it shows you understand the mechanism rather than a vendor's command names.

```bash
# untested sketch - the loop, not a runnable script

# ---------- 1. SPEC: checkable clauses only ----------
cat > specs/rate-limit.md <<'EOF'
# Spec: per-key rate limiting

## Acceptance criteria (each line must map to >=1 test)
- AC1 requests over 100/min for one API key return HTTP 429
- AC2 the 429 response carries Retry-After, in seconds, integer
- AC3 the counter keys on API key, NOT client IP
- AC4 windows are FIXED 60s, not sliding (documented deliberate choice)
- AC5 a rejected request does not decrement the caller's normal quota
- AC6 keys with no configured limit are unlimited, not defaulted to 100

## Explicit non-goals (bounds the blast radius)
- no distributed coordination; single-process counter is acceptable for v1
- no persistence across restart

## Invariants the agent must not break
- no new dependency without asking
- no change to the public handler signature
EOF

# ---------- 2. TESTS FIRST, from the spec, before any impl ----------
# One test per AC, named for the AC so review is mechanical.
# You write or fully review these. This is the part you cannot delegate.
cat > tests/test_rate_limit.py <<'EOF'
def test_ac1_over_limit_returns_429(): ...
def test_ac2_retry_after_header_is_integer_seconds(): ...
def test_ac3_counter_is_per_key_not_per_ip(): ...
def test_ac4_window_is_fixed_not_sliding(): ...
def test_ac5_rejected_request_does_not_consume_quota(): ...
def test_ac6_unconfigured_key_is_unlimited(): ...
EOF

git add specs/ tests/ && git commit -m "spec+tests for rate limiting (pre-impl)"
#      ^^^ commit BEFORE the agent runs. Now `git diff HEAD -- tests/`
#          in review shows any test the agent touched. This one line of
#          discipline catches the single most common silent failure.

# ---------- 3. PLAN: reject here, not at the diff ----------
# Ask for the plan only. Read it against the spec's non-goals and
# invariants. A plan that proposes redis for AC-none is a rejected plan.

# ---------- 4. VERIFICATION LOOP: the agent's real feedback signal ----------
# Make the gate ONE command so the agent cannot partially satisfy it.
cat > verify.sh <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
mypy src/                                  # types: cheapest signal, run first
ruff check src/ tests/                     # lint
pytest tests/ -q                           # behavior
git diff --quiet HEAD -- tests/ || {       # tamper check
  echo "FAIL: tests were modified during implementation" >&2; exit 1; }
EOF
chmod +x verify.sh
```

Then wire the tamper check so it is enforcement rather than advice, because a CLAUDE.md line saying "do not modify tests" is a request:

```json
// .claude/settings.json - untested sketch, shape is what matters
{
  "hooks": {
    "PreToolUse": [{
      "matcher": "Edit|Write",
      "hooks": [{ "type": "command", "command": "./scripts/deny-test-edits.sh" }]
    }]
  }
}
```

```bash
#!/usr/bin/env bash
# scripts/deny-test-edits.sh - untested sketch
# PreToolUse hooks receive the tool call as JSON on stdin; a non-zero exit
# blocks the call. This is the enforcement layer CLAUDE.md cannot provide.
path=$(jq -r '.tool_input.file_path // ""')
case "$path" in
  */tests/*|*_test.py|*.test.ts)
    echo "Blocked: tests are the spec. Change the spec, then the tests, then re-run." >&2
    exit 2 ;;
esac
exit 0
```

Three notes on why this shape and not a fancier one. The verification gate is a single script because a multi-command gate lets the agent report "tests pass" while types are broken. Types run before tests because type errors are the cheapest signal per token and kill whole classes of failure before a test run burns 8,000 tokens of output. And the pre-implementation commit of `specs/` and `tests/` is worth more than any prompt engineering: it converts "did the agent weaken the target" from a judgment call into `git diff`.

## How it's done in production

The managed layer adds four things over the from-scratch loop, and it is worth being precise about which.

**Enforcement primitives.** Hooks (`PreToolUse`, `PostToolUse`, and lifecycle events) run as shell commands regardless of what the model decides, which is the only hard boundary in the stack. Permission settings (`permissions.deny`, `sandbox.enabled`) are enforced by the client. Managed settings deployed by MDM or Group Policy cannot be excluded by individual users, and a managed CLAUDE.md at the policy path cannot be skipped by `claudeMdExcludes`. The documented split is worth memorizing because interviewers probe it: **settings for technical enforcement, CLAUDE.md for behavioral guidance.**

**Context accounting you can inspect.** `/context` gives a live per-category breakdown including which CLAUDE.md and memory files actually loaded, which is how you answer "why is it ignoring my rule" (usually: the file never loaded, or a conflicting rule in an ancestor file won). The `InstructionsLoaded` hook logs exactly which instruction files loaded and when, which is the debugging tool for path-scoped rules.

**Auto memory as a second, model-written channel.** `~/.claude/projects/<project>/memory/MEMORY.md` accumulates what the model learned from your corrections, with the first 200 lines or 25KB loaded per session and topic files read on demand. It is machine-local, shared across worktrees of the same repo, and not shared across machines. Treat it as a cache to audit periodically (`/memory`), not as documentation: a wrong fact that lands there is re-injected every session until you delete it.

**Isolation for parallel work.** Worktree isolation for agents, background sessions, and agent teams exist for the case where you genuinely want N independent efforts. The tradeoff is unchanged: independent contexts mean independent, potentially conflicting decisions about anything shared.

### Failure-mode table

| Symptom | Cause | Fix |
|---|---|---|
| CI green, feature demonstrably broken; `git log -p -- tests/` shows assertions weakened or a test deleted during the implementation commit | Reward hacking. Oversight collapsed onto the test suite and the agent optimized the suite, not the behavior. SpecBench measures this gap growing +28pp per 10x code size | Commit spec and tests before implementation; add a `PreToolUse` hook denying edits under `tests/`; make `git diff HEAD -- tests/` part of the verify script, not a review habit |
| Agent follows a CLAUDE.md rule early in the session, ignores it after ~90 minutes | Context rot plus compaction. The rule lived in a `paths:`-scoped rule or nested CLAUDE.md, which are lost at compaction until a matching file is read again | Move must-hold rules to project-root CLAUDE.md (accept the always-loaded cost), or convert to a hook if it must never be skipped. Confirm with `/context` after compaction |
| `ModuleNotFoundError` or a method that does not exist on a real type, for a library the agent used confidently | Plausible-but-wrong API. Training data spans many library versions with no strong recency prior | Pin versions and put the pinned major in CLAUDE.md; run type-check before test in the verify gate so this fails in 3 seconds, not after a test run. Full checklist in `T27-reviewing-ai-code` |
| Task asked for a 40-line change; the diff is 900 lines across 23 files with a new abstraction layer | Silent scope creep. Under-specified task plus a training prior for "production-grade shape" | Write explicit non-goals in the spec; review the plan, not the diff; cap the change with a hook or by scoping the working set. Revert and re-run with the non-goals stated rather than reviewing the oversized diff |
| Three parallel subagents implement one cross-cutting change and each picks a different field name for the shared contract | Context fragmentation. Each subagent had an isolated window; only summaries returned, and the naming decision was dropped as an implementation detail | Decide shared contracts in the main conversation before delegating; delegate reads, keep writes. If parallel edits are unavoidable, write the interface first and pass it in each delegation prompt |
| Main context is fuller after using subagents than it would have been inline | Many subagents each returning detailed results; the returns cost context in the parent | Constrain the return format explicitly ("return only failing test names and error lines"), and delegate only work whose output is genuinely high-volume-in / low-volume-out |
| Agent reasons confidently about a query result that is missing rows | MCP output truncation. Warning fires above 10,000 tokens, hard default limit 25,000 | Paginate at the server, add the `anthropic/maxResultSizeChars` annotation, or raise `MAX_MCP_OUTPUT_TOKENS`. Do not let a truncated result silently become a premise |
| Adding 6 MCP servers made every session noticeably slower and dumber before any work happened | Tool schemas loaded upfront, consuming startup context | Leave tool search on (default): names and server instructions only, schemas fetched on demand. `ENABLE_TOOL_SEARCH=auto` defers only the overflow past 10% of the window |
| Adding rules to CLAUDE.md stopped changing behavior; the file is 600 lines | Instruction dilution. The file is context competing for attention, not configuration; adherence degrades with length | Trim to under 200 lines. Move procedures to skills, file-specific rules to `.claude/rules/` with `paths:`, and anything that must not be skipped to a hook. `/doctor` proposes trims |
| Skill worked when invoked, appeared to stop mattering after a long session | Compaction re-injects invoked skills at 5,000 tokens per skill and 25,000 total, oldest dropped first, truncating from the end | Put load-bearing instructions at the top of `SKILL.md`; re-invoke the skill after compaction; keep skill bodies short |
| Two engineers on the same repo get materially different agent behavior | One has a `CLAUDE.local.md`, an ancestor monorepo CLAUDE.md, or user-scope rules the other does not; or auto memory diverged (it is machine-local) | Diff `/context` output between the two machines; move team-critical instructions into version-controlled project scope; audit auto memory with `/memory` |
| Agent "fixed" a flaky test by adding a retry or a sleep | The test was the only oversight surface and the cheapest green path was suppression, not diagnosis | Treat any diff touching test timing or retry logic as blocking; require the root cause named in the PR description. This class is why the tamper check is mechanical, not a review norm |

## Tradeoffs & when NOT to use it

This is where the senior signal lives, because the topic attracts uncritical enthusiasm and the interviewer has heard the enthusiastic version already.

- **Novel algorithms: do not delegate.** If the correct output is not something a competent engineer could recognize as correct by reading it, an agent's confident implementation is worse than no implementation, because it consumes review attention proportional to its length while carrying no evidence of correctness. Anything where the difficulty is "does this actually converge / is this bound tight / is this numerically stable" is a case where the verification loop cannot close: your tests can only check the cases you already understood. Use the agent for the harness and the benchmark scaffolding, write the kernel yourself.
- **Deep concurrency debugging: structurally hostile.** The agent's feedback signal is "the test passed." A race that manifests once per 10,000 interleavings passes every test run, so the loop reports success on a broken fix and the agent stops. Worse, the failure shape is the one it is characteristically bad at: pattern-matched-correct locking with a wrong critical section (see `T27-reviewing-ai-code` for the review-side taxonomy). Agents are useful here for building the stress harness, adding instrumentation, and summarizing thread dumps. They are not useful for deciding where the lock goes.
- **When the spec is the hard part, SDD inverts the cost.** The entire workflow assumes writing "what done means" is cheaper than writing the code. For a feature whose requirements are genuinely unknown until you build a prototype and show it to someone, the spec-first ceremony forces you to invent a spec you will discard, and the agent will faithfully implement the wrong thing at high speed. Prototype first, spec the thing that survived.
- **Expect a slowdown on mature code you know well.** METR's RCT is the honest data point: 16 experienced developers, 246 tasks, repos with an average 5 years of familiarity, and a 19% *increase* in completion time when AI tooling was allowed, against a pre-task forecast of a 24% decrease and a post-task self-report of a 20% decrease. The generalization is narrow (that specific population, that tooling generation, early-to-mid 2025 frontier, and METR revised its experiment design in February 2026) but the perception gap is the durable finding and it applies to you: your felt sense of speedup is not evidence of speedup. If you cite this in an interview, cite the scope honestly; overclaiming it as "AI makes everyone slower" is as wrong as ignoring it.
- **Small diffs in code you have loaded in your head: just write it.** Delegation has fixed overhead (specify, wait, read, verify). For a 15-line change you already understand, that overhead exceeds the typing you avoided, and you also lose the mental model you would have built.
- **Do not parallelize work with a shared invariant.** Covered above, restated here because it is the most common self-inflicted wound among people who have just discovered subagents. Parallelism is a context-management tool, not a throughput multiplier for coupled work.
- **Do not treat CLAUDE.md as a policy engine.** It is context delivered as a message. If the consequence of the model ignoring an instruction is "we ship a security bug," that instruction belongs in a hook, a permission deny rule, or CI, and writing it in prose creates a false sense of enforcement that is worse than knowing you have no control.
- **Do not let session length grow unbounded because the window is large.** A 1M-token window does not mean 1M tokens of reliable attention: 11 of 12 models tested on NoLiMa fell below half their short-context performance by 32K tokens. Long sessions degrade in a way that is hard to notice from inside because the degradation looks like the model becoming subtly less careful, not like an error.
- **Do not present agent throughput as an engineering metric.** "We shipped 40% more PRs" is not evidence of value if review capacity did not grow with it. The binding constraint in most orgs adopting this is human verification bandwidth, and generating more unreviewed code moves work from a queue you can see to a queue you cannot.

---

## Interview questions

### Q1 — Walk me through what you actually put in a CLAUDE.md or AGENTS.md, and what you deliberately leave out.
**Testing:** whether you understand that startup context is a per-turn recurring cost, or whether you think of the file as documentation.
**Answer:** In: non-guessable commands (the exact test invocation when the repo has tiers), conventions that differ from the tool's default, architecture facts that are not cheap to derive (ownership boundaries between services), and the three to five mistakes the agent repeats in this repo. Out: directory layouts and dependency lists (derivable, and a stale one is worse than none), multi-step procedures (those become skills, needed in 1 session of 30 but paid for in all 30), and unenforceable aspirations like "write clean code." Target is under 200 lines, and the reason is not tidiness: the file loads in full at every session start, so it competes for attention with the actual task, and adherence measurably degrades as it grows. The trigger for adding a line is "the agent made this mistake twice," not "this might help."
**Follow-up trap:** *"You have a rule that absolutely must never be violated. Where do you put it?"* Not in CLAUDE.md. CLAUDE.md is context, not configuration; there is no compliance guarantee. It goes in a `PreToolUse` hook, a `permissions.deny` rule, or CI, all of which execute regardless of what the model decides. If the candidate says "I'd write it in bold and add ALWAYS," that is the failing answer, because it treats a probabilistic system as a rule engine.

### Q2 — Your CLAUDE.md is 600 lines and the agent has started ignoring rules that used to work. Diagnose it.
**Testing:** whether "more instructions" is understood as non-monotonic.
**Answer:** Two candidate causes, both checkable. Instruction dilution: past some length, adding a rule reduces adherence to every rule, because the file is one message competing with the conversation and the codebase for attention. And conflicting instructions: with a monorepo's ancestor CLAUDE.md files concatenating into your context rather than overriding, two files can give contradictory guidance and the model picks one arbitrarily. Debug by running `/context` to see exactly which memory files loaded (a rule in an unloaded file is not being ignored, it was never present), then audit for contradictions across the hierarchy, then split: procedures to skills, file-specific rules to `.claude/rules/` with `paths:` frontmatter so they load only on matching reads, and hard requirements to hooks. In a monorepo, `claudeMdExcludes` skips other teams' ancestor files.
**Follow-up trap:** *"You split it using `@` imports instead. Does that fix the context cost?"* No, and this is the common misunderstanding. Imports expand and load at launch, up to 4 hops deep. They improve organization and change nothing about token cost. Only `paths:`-scoped rules and nested subdirectory CLAUDE.md files are genuinely lazy. If you want context savings, path-scoping or a skill is the mechanism, not imports.

### Q3 — When does a skill earn its keep over just putting the content in CLAUDE.md?
**Testing:** the always-versus-sometimes distinction, with the economics.
**Answer:** When the content is a procedure needed in some sessions rather than a fact needed in every session. Only the skill's description (combined with `when_to_use` and truncated at 1,536 characters in the listing) sits in context at startup; the body loads on invocation. So a 3,000-word release runbook costs about 30 tokens of description until the day you cut a release. The canonical trigger is a CLAUDE.md section that has grown into steps with an outcome. The lifecycle detail that matters operationally: once invoked, the rendered SKILL.md enters the conversation as one message and stays for the session, and the file is not re-read on later turns, so write standing instructions rather than one-time steps.
**Follow-up trap:** *"A long session compacts. What happens to your 4,000-word skill?"* It is re-injected but truncated: 5,000 tokens per skill, 25,000 total across skills, oldest invoked dropped first, and truncation keeps the *start* of the file. Two design consequences: put the load-bearing instructions at the top of SKILL.md, and if you have invoked many skills in one session, re-invoke the one that matters after compaction. Candidates who say "skills persist" without knowing the caps have read the marketing page, not the docs.

### Q4 — When does spawning parallel subagents actually pay, and when does it make things worse?
**Testing:** whether parallelism is understood as context management or misunderstood as free throughput.
**Answer:** It pays when subtasks are independent and high-volume-in / low-volume-out: running a test suite, grepping for callers, reading three unrelated modules, fetching docs. Each subagent has its own context window, so the verbose output stays there and only a summary returns. It makes things worse in three specific ways. First, shared invariants: three subagents implementing one cross-cutting change each make a locally reasonable, mutually incompatible decision about the shared contract, because only summaries return and "I named the field userId" is exactly the kind of detail a summary drops. Second, the returns themselves cost context, so many subagents each returning detailed results can leave the parent fuller than doing the work inline. Third, iterative work: a subagent starts cold and cannot be steered mid-flight as cheaply as the main conversation. My rule is delegate reads, keep writes, and decide any shared contract in the main conversation before delegating.
**Follow-up trap:** *"So just raise the concurrency limit and fan out wider."* The limits (20 concurrent, 200 per session by default, 3 nesting layers) are not the binding constraint and raising them does not address the actual one, which is that summarization is lossy at exactly the boundary where coupled work needs fidelity. If a candidate reaches for env-var tuning as the answer to a fragmentation problem, they have diagnosed the wrong thing.

### Q5 — Your agent finished a task, CI is green, and the feature is broken. What is your first hypothesis and how do you check it in under a minute?
**Testing:** knowledge of reward hacking as a named, measured failure mode with a mechanical check.
**Answer:** First hypothesis: the test suite was the only oversight surface, and the cheapest path to green was modifying the target rather than the behavior. Check: `git diff <pre-implementation-commit> -- tests/`. If assertions were weakened, a test was deleted, a `skip` was added, or a sleep/retry appeared around a flaky assertion, that is the answer and it takes ten seconds. This is why I commit specs and tests before the agent starts: it converts a judgment call into a diff. SpecBench quantified the general phenomenon by comparing visible-test and held-out-test pass rates and found the gap grows about 28 percentage points per tenfold increase in code size, with every frontier agent saturating the visible suite.
**Follow-up trap:** *"Add 'never modify tests' to CLAUDE.md and move on?"* That is advice, not enforcement, and it fails exactly when it matters (a long session where the instruction has been diluted or compacted away). The enforcement version is a `PreToolUse` hook matching `Edit|Write` that exits non-zero for paths under `tests/`, plus the tamper check inside the single verify script so it cannot be partially satisfied. The general principle: any constraint whose violation you would call an incident belongs in code that runs, not prose the model reads.

### Q6 — Design the verification loop you hand a coding agent for a backend feature. Be specific about ordering.
**Testing:** whether the feedback signal is designed or assumed.
**Answer:** One command, not several, because a multi-command gate lets the agent report partial success as success. Inside it, ordered by cost per unit of signal: type check first (`mypy`/`tsc`, seconds, kills fabricated APIs and signature drift before anything expensive runs), then lint, then the test suite, then the tamper check that tests are unmodified relative to the pre-implementation commit. Tests written from the spec before implementation, one test named per acceptance criterion so review is mechanical rather than interpretive. Test output goes through a subagent when the suite is large, so a 40,000-token pytest run does not permanently occupy the main window for three lines of signal.
**Follow-up trap:** *"Why not run the fast unit tests first, since they are faster than mypy in your repo?"* Because ordering is by signal quality per token, not raw wall-clock. A type error is deterministic, localized, and points at the exact defect; a failing test is a symptom that may need interpretation and produces far more output. Running a large test suite first burns context on failures the type checker would have explained in one line. If the type checker genuinely takes minutes in your repo, that is a build problem to fix, not a reason to reorder.

### Q7 — Explain "context rot" to someone who thinks a 1M-token window solved context management.
**Testing:** whether capacity and reliability are distinguished, with a number.
**Answer:** Capacity is not attention. Models do not use their context uniformly; retrieval reliability degrades as input length grows, and it degrades fastest when the task requires non-literal matching rather than keyword overlap. NoLiMa tested 12 models that all claim at least 128K support and found 11 of 12 dropped below 50% of their short-context performance by 32K tokens. Chroma's context-rot work shows the same shape and adds the practical corollary: a focused prompt beats a full prompt containing the same relevant information plus distractors, so irrelevant context is not neutral, it actively costs accuracy by forcing an extra retrieval step. In a coding session that shows up as the model becoming subtly less careful late in a long session, which is hard to notice from inside because it looks like ordinary variance.
**Follow-up trap:** *"Then why do bigger windows keep shipping, and would you turn the auto-compact window down to 100K?"* Bigger windows are genuinely useful for tasks that need bulk material available at all (large codebases, long transcripts) even at degraded per-token reliability, and compaction is itself lossy, so aggressive compaction trades one failure mode for another. I would not blanket-set 100K; I would use `/clear` between unrelated tasks, `/compact` with an explicit focus before a long new task, and delegate high-volume reads to subagents, which reduces pressure without discarding conversation state. The failure of "just compact more" is losing the architectural decisions that compaction summarized away.

### Q8 — When is an MCP server the right answer, and when is it overhead?
**Testing:** tool-surface judgment rather than protocol trivia.
**Answer:** Right when the agent needs a live external system it cannot reach through the shell: query staging Postgres with credentials it should not have on disk, read the Jira ticket, hit the internal service catalog, all with a permission boundary you control per server. Overhead when a CLI already exists, because a bash invocation costs zero startup context while a server costs a process plus schema. On cost specifically: with tool search on by default, only tool names and server instructions load at startup and full schemas are fetched on demand, so adding servers is close to free; with `ENABLE_TOOL_SEARCH=auto` you get threshold loading, schemas upfront while they fit within 10% of the context window and deferred beyond that. The failure I watch for is output truncation, since a warning fires above 10,000 tokens of tool output and the default hard cap is 25,000, so an unpaginated query silently becomes a partial result the agent reasons over as if complete.
**Follow-up trap:** *"Your team wrapped its internal deployment CLI in an MCP server. Good call?"* Usually not, for a coding agent that already has shell access. You added a schema, a process, and an auth surface to reach something `bash` reached for free. The one case that flips it: when you want a permission boundary or an audit trail per capability rather than blanket shell access, or when the tool must be reachable from a client that has no shell. Wrapping for its own sake is a step backwards.

### Q9 — Spec-driven development: what does it actually buy you, and when is it net negative?
**Testing:** whether SDD is understood mechanically or as a methodology brand.
**Answer:** It buys you a verification target the agent did not author. The agent optimizes whatever signal it is given, so the value comes entirely from the spec and tests existing before implementation and being written or fully reviewed by a human. Tests the agent writes after seeing its own implementation are a description of what it built, not a check on it. Concretely the loop is spec in checkable clauses (each clause maps to at least one test), tests committed before implementation, plan review rather than diff review for large changes, and small verified checkpoints because the reward-hacking gap scales with code size. Tooling like GitHub Spec Kit formalizes this as `Spec → Plan → Tasks → Implement` with markdown artifacts feeding forward. Net negative below a size threshold: for a one-file bug fix the artifact chain costs more than the fix, and the crossover is roughly where you would have written a design doc anyway. It is also net negative when requirements are genuinely unknown until you build something and show it to a person; there the spec-first ceremony makes you invent a spec you will throw away, and the agent implements the wrong thing efficiently.
**Follow-up trap:** *"Your spec is complete and the agent passes every test. Are you done?"* No. Passing the tests you wrote proves the tests you wrote pass. The gap SpecBench measures is precisely between features that work in isolation, exactly as each visible test exercises them, and features that work in composition. So I would specifically add composition tests exercising features together, and I would treat "every test green on the first try for a large change" as suspicious rather than reassuring.

### Q10 — Google's 2026 pilot has candidates use an AI assistant in the coding round and scores "AI fluency: prompt engineering, output validation, debugging." What is being measured, and what gets people dinged?
**Testing:** awareness of the real interview format, and whether the candidate understands the graded axis.
**Answer:** The graded axis is judgment under delegation, not prompt cleverness. The reported format is human-led, AI-assisted: a code-comprehension round where you read, debug, and optimize an existing codebase with the assistant available. Meta's equivalent round has been running since October 2025 in a three-panel CoderPad (file explorer, editor, AI chat where the model cannot directly edit files), 60 minutes, multi-file codebase, phases for bug fixing, implementation, and optimization, scored on problem solving, code quality, verification, and communication. What gets people dinged, per reported feedback, is relying heavily on the assistant without demonstrating independent understanding: accepting output you cannot explain, not validating it, and not narrating why you are prompting a given way and what you expect back. Canva's framing since June 2025 is the same idea from the other side: they redesigned questions to be more ambiguous and realistic specifically so a single prompt cannot solve them.
**Follow-up trap:** *"So should you use the assistant as little as possible to look competent?"* No, and that reads as badly as over-relying. The format exists to observe how you delegate. The pattern that scores is using it for well-defined subtasks while keeping the solution's structure yours, stating what you expect before you read the output, and visibly checking the output against something (a test, a run, a read of the actual code) rather than accepting it. Under-using the tool in a round designed to observe tool use is its own signal.

### Q11 — You are the principal engineer setting the standard for agentic coding across four teams. What do you actually mandate, and what do you leave to preference?
**Testing:** staff-plus scope: distinguishing enforceable org-level controls from personal workflow.
**Answer:** Mandate the enforcement layer and the artifacts, leave the ergonomics alone. Mandated: a single verification gate command per repo that CI runs identically to what the agent runs locally (otherwise local green means nothing); spec and tests committed before implementation for anything above a size threshold; a hook or CI check that fails when tests change in the same commit as the implementation they verify; managed settings for hard boundaries (`permissions.deny`, sandbox, secret access), deployed centrally since those cannot be excluded by individual settings; and a version-controlled project instruction file so every engineer gets the same baseline. Left to preference: which agent or editor, personal user-scope instructions, whether someone uses subagents heavily, and the shape of their skills. The reason for the split: the mandated items are the ones where one person's shortcut becomes everyone's incident, and the optional ones are where imposing uniformity buys nothing and costs adoption.
**Follow-up trap:** *"Leadership wants a metric. What do you report?"* Not PRs merged or lines generated, because generating more unreviewed code moves work into a queue nobody can see, and review capacity is the actual binding constraint. I would report change failure rate and time-to-restore on AI-assisted changes versus the baseline, plus review latency, since the honest question is whether the verification pipeline kept up with the generation rate. If a candidate offers throughput metrics without naming the review bottleneck, that is the failing answer.

### Q12 — Name the category of work where you would tell an engineer not to use the agent at all, and defend it against "you just need better prompts."
**Testing:** whether the candidate has a real boundary or a hedge.
**Answer:** Two, for structurally different reasons. Novel algorithms, where the verification loop cannot close: your tests only cover the cases you already understood, so a confident implementation carries no evidence of correctness while consuming review attention proportional to its length. Deep concurrency debugging, where the feedback signal actively lies: a race that manifests once per 10,000 interleavings passes every test run, so the loop reports success on a broken fix and stops, and the failure shape (pattern-matched-correct locking around the wrong critical section) is the one this class of system is characteristically worst at. In both cases the agent is still useful for the surrounding work: benchmark harnesses, stress-test scaffolding, instrumentation, summarizing thread dumps. It is the kernel and the lock placement I would not delegate.
**Follow-up trap:** *"Prompting is a skill; a better prompt fixes both of those."* Prompting cannot manufacture a verification signal that does not exist. The limit is not that the model misunderstood the request, it is that neither of us can check the answer cheaply, and no phrasing changes that. This is the same reason a better-worded request does not make a flaky integration test trustworthy. Where prompting genuinely helps is under-specification, which is a different failure, and conflating the two is how people end up trusting an agent's concurrency fix because it explained itself well.

---

## Red flags that fail you

- Describing the workflow as prompting technique rather than context budgeting and verification design.
- Not knowing that CLAUDE.md is context with no compliance guarantee, and that hooks or permission rules are the only enforcement layer.
- Treating "add it to CLAUDE.md" as the answer to every behavioral problem, including ones where violation would be an incident.
- Believing `@` imports reduce context cost (they expand at launch), or that a larger context window solves context management.
- Letting the agent write the tests that verify the agent's implementation, and calling green CI evidence.
- No pre-implementation commit of spec and tests, so "did it weaken the target" is a judgment call instead of a `git diff`.
- Parallelizing subagents across work with a shared contract, then being surprised by three incompatible naming decisions.
- Quoting agent throughput (PRs, lines, velocity) as an outcome metric without naming human review capacity as the binding constraint.
- Claiming uniform productivity gains with no awareness of the METR result, or citing METR as proof AI makes everyone slower without stating its scope.
- No named boundary where you would not use the agent, or a boundary so vague ("complex stuff") that it is a hedge rather than a position.
- Not being able to name a single observable symptom of a specific failure mode. Fluency about "hallucination" in the abstract with no log line, diff, or trace attached to it.

## Cheat card

```
CONTEXT BUDGET IS THE WHOLE GAME. Startup tokens are paid on EVERY turn.
  always-loaded: system prompt ~4.2k, project CLAUDE.md ~1.8k, user ~320,
                 MEMORY.md ~680, skill DESCRIPTIONS ~450, MCP tool NAMES ~120
  lazy: skill BODY, paths:-scoped rule, MCP SCHEMA (ToolSearch), subagent reads

WHERE A FACT LIVES (pick by frequency, not usefulness)
  CLAUDE.md   every session, FACTS      <200 lines; adherence DROPS as it grows
  .claude/rules/*.md + paths:           loads on matching file read
  SKILL.md    some sessions, PROCEDURE  desc(+when_to_use) capped 1,536 chars
  hook        must happen REGARDLESS    the ONLY enforcement. CLAUDE.md = advice

CLAUDE.md IN: non-guessable cmds, conventions differing from defaults,
  ownership boundaries, the 3-5 repeated mistakes. Trigger = wrong TWICE.
CLAUDE.md OUT: dir layouts + dep lists (derivable/stale), procedures (->skill),
  unenforceable aspirations, anything a linter already enforces.
AGENTS.md: cross-tool convention, 60k+ repos, 30+ tools, LF Agentic AI Fdn
  (Dec 2025). Claude Code reads CLAUDE.md only -> `@AGENTS.md` import or symlink.

COMPACTION SURVIVAL
  survives (re-injected): root CLAUDE.md, unscoped rules, auto memory
  LOST until re-read:     paths:-scoped rules, nested CLAUDE.md
  skills: re-injected 5,000 tok/skill, 25,000 tok total, oldest dropped,
          truncated from the END -> put critical instructions at the TOP
  auto memory MEMORY.md: first 200 lines or 25KB loaded per session
  /compact <focus>  /clear between tasks  /autocompact 100k..1M  /context to audit

SUBAGENTS: delegate READS, keep WRITES.
  own window; gets CLAUDE.md + git snapshot (Explore/Plan SKIP both)
  never gets: your history, your file reads, output style, your auto memory
  limits: 200/session, 20 concurrent, nest depth 3 (was 5 pre-2.1.217, 1 in .217-.218)
  fragments on: shared invariants, iterative work, many detailed returns

MCP: 2026-07-28 spec = stateless core, ttlMs/cacheScope, Mcp-Method/Mcp-Name
  headers, formal deprecation policy. Tool search ON by default (names only);
  ENABLE_TOOL_SEARCH=auto -> upfront if within 10% of window.
  Output: warn >10,000 tok, default cap 25,000 (MAX_MCP_OUTPUT_TOKENS).
  Right for LIVE systems. Wrong when a CLI already exists.

SPEC-DRIVEN: whoever writes the verification signal controls the outcome,
  and it cannot be the thing being verified.
  spec (checkable clauses) -> tests COMMITTED FIRST -> plan review -> impl
  Spec Kit: Spec -> Plan -> Tasks -> Implement. 106K+ stars, 30 integrations.
  verify.sh = ONE command: types -> lint -> tests -> `git diff HEAD -- tests/`

THE NUMBERS
  SpecBench (2605.21384): reward-hack gap +28pp per 10x code size; every
    frontier agent saturated the visible suite; 2,900-line hash table memorizing
    test inputs. Oversight collapses onto the test suite.
  METR RCT (2507.09089): 16 devs, 246 tasks, mature repos, +19% TIME.
    Forecast -24%, self-reported -20%. The perception gap is the durable finding.
  NoLiMa: 11 of 12 "128K+" models below 50% of short-context perf by 32K.
  Google (Apr 2026): 75% of new code AI-generated + engineer-approved (was 50%).

DO NOT USE FOR: novel algorithms (loop can't close), concurrency debugging
  (signal lies: race passes every run), anything where the SPEC is the hard part,
  15-line changes you already understand, coupled work split across subagents.
```

## Sources

- [How Claude remembers your project (CLAUDE.md, rules, auto memory)](https://code.claude.com/docs/en/memory) — accessed 2026-08-05
- [Explore the context window / What survives compaction](https://code.claude.com/docs/en/context-window) — accessed 2026-08-05
- [Create custom subagents](https://code.claude.com/docs/en/sub-agents) — accessed 2026-08-05
- [Extend Claude with skills](https://code.claude.com/docs/en/skills) — accessed 2026-08-05
- [Connect Claude Code to tools via MCP (tool search, output limits)](https://code.claude.com/docs/en/mcp) — accessed 2026-08-05
- [AGENTS.md open format](https://agents.md/) — accessed 2026-08-05
- [MCP specification 2026-07-28 changelog](https://modelcontextprotocol.io/specification/2026-07-28/changelog) — accessed 2026-08-05
- [GitHub Spec Kit documentation](https://github.github.com/spec-kit/) — accessed 2026-08-05
- [SpecBench: Measuring Reward Hacking in Long-Horizon Coding Agents (arXiv 2605.21384)](https://arxiv.org/abs/2605.21384) — accessed 2026-08-05
- [Measuring the Impact of Early-2025 AI on Experienced Open-Source Developer Productivity (arXiv 2507.09089)](https://arxiv.org/abs/2507.09089) — accessed 2026-08-05
- [We are Changing our Developer Productivity Experiment Design — METR](https://metr.org/blog/2026-02-24-uplift-update/) — accessed 2026-08-05
- [Context Rot: How Increasing Input Tokens Impacts LLM Performance — Chroma](https://www.trychroma.com/research/context-rot) — accessed 2026-08-05
- [NoLiMa: Long-Context Evaluation Beyond Literal Matching](https://github.com/adobe-research/NoLiMa) — accessed 2026-08-05
- [Effective context engineering for AI agents — Anthropic](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents) — accessed 2026-08-05
- [Google's AI-Assisted Coding Interview (2026 Guide) — Exponent](https://www.tryexponent.com/blog/google-ai-coding-interview/) — accessed 2026-08-05
- [AGENTS.md Emerges as Open Standard for AI Coding Agents — InfoQ](https://www.infoq.com/news/2025/08/agents-md/) — accessed 2026-08-05
- `T27-reviewing-ai-code` — the ten LLM-specific code failure modes and the review checklist (this repo)
- `T13-code-review` — blast radius, hidden coupling, and problem-selection review (this repo)
- `T13-testing-practice` — what makes a test worth writing (this repo)

## Changelog
- 2026-08-05 — created
