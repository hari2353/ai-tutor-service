# Context Files: CLAUDE.md / AGENTS.md That Actually Change Behaviour

> **Track:** T28 AI-Assisted Architecture · **Time:** 2h · **Prereqs:** `T28-claude-code-model`, `T07-context-engineering` · **Updated:** 2026-07-26
> **Module id:** `T28-context-files` · **Tags:** foundations, critical

## The 30-second version

A context file is a permanent tax on every request in every session, so the only content that earns its place is content the agent cannot derive from the repository itself: exact commands, non-obvious conventions, and pitfalls. That is not a style opinion, it is the finding of the one rigorous study on the question: across four agents and two benchmarks, providing a context file **did not generally improve task success while raising inference cost by over 20% on average**, and the specific thing that failed was the repository-overview section that every tool's template tells you to write, while *instructions* were followed reliably. The failure mode that matters most is aspirational drift: a file describing the architecture you intend rather than the one on disk, which is worse than no file because the agent trusts it and builds on a false premise. Size is the second-order problem, with a documented target of **under 200 lines** and measurable adherence loss beyond it. And the load-bearing distinction: `CLAUDE.md` is delivered as a *user message after the system prompt*, it is context and not enforced configuration, so anything you would be upset to find violated belongs in a hook, a lint rule, or CI, not in a markdown bullet.

## Why this gets asked

Because "write me a CLAUDE.md for a service you own" is a five-minute whiteboard exercise that separates people who have shipped agent workflows from people who have read about them, and it is now a common opener. The interviewer has personally watched two things: an auto-generated `CLAUDE.md` that described a directory layout three refactors out of date and quietly steered every agent in the repo wrong for a month, and a 700-line `CLAUDE.md` that somebody kept adding rules to after each incident until the agent obeyed roughly none of them. Both are cheap to prevent and neither is prevented by enthusiasm. There is also a second-order signal: how you talk about context files reveals whether you think instructions are enforcement, which is the single most common architectural error in this space.

---

## Lineage: past → present → future

**What came before.** First, nothing: 2023-2024, you re-explained your conventions in every chat, and the pain that killed it was that the explanation was the most expensive part of the interaction and you paid for it a dozen times a day. Then per-tool config sprawl, roughly late 2024 through 2025: `.cursorrules`, `CLAUDE.md`, `.github/copilot-instructions.md`, `.windsurfrules`, `.clinerules`, `.devin/rules/`, each with a slightly different format, all containing the same facts, drifting from each other within weeks. The pain that killed *that* was maintenance cost multiplied by tool churn: a team using three agents maintained three copies of the truth and the copies disagreed. `AGENTS.md` emerged as the de facto cross-tool convention in response, adopted by Codex, Cursor, Copilot, Gemini CLI, Aider, Windsurf, Zed and others, stewarded under the Linux Foundation's Agentic AI Foundation, and present in tens of thousands of repositories. It is a convention, not a standard, and worth saying so plainly.

**Where it stands now.** Two facts are in tension and you should present both. Fact one: every vendor recommends context files, ships a generator for them (`/init`, and Claude Code's `CLAUDE_CODE_NEW_INIT=1` interactive multi-phase flow that explores with a subagent and presents a reviewable proposal), and gives detailed authoring guidance. Fact two: the only rigorous evaluation, Gloaguen, Mündler, Müller, Raychev and Vechev at ETH Zurich (arXiv:2602.11988, February 2026, revised June 2026), tested SWE-bench tasks with LLM-generated context files *and* a novel collection of issues from repositories with developer-committed files, across Claude Code with Sonnet 4.5, Codex with GPT-5.2 and GPT-5.1 Mini, and Qwen Code with Qwen3-30B. The result: **context files did not generally improve task success rates, while increasing inference cost by over 20% on average**, holding across LLMs, agents, and both generated and human-written files. LLM-generated files reduced success in 5 of 8 settings, by about 3 percentage points on average, and added 2-4 reasoning steps. Human-curated files beat LLM-generated ones for all four agents by roughly 4 percentage points. The decisive detail is *which part* failed: instructions in the files were followed well; **repository overviews, "although popular and recommended by model providers, are not helpful."** The authors' ablation nails the mechanism: strip all other documentation from the repo, and LLM-generated files then help by 2.7%. In other words, the overview section is redundant with a README the agent will read anyway, and you are paying tokens to duplicate it. The live disagreement is about scope, not direction: nobody credible now argues for long overview-heavy files, but practitioners disagree about how much *behavioural* instruction is worth its cost, and the study is a benchmark result on issue-resolution tasks rather than a verdict on team-convention enforcement, which is not what SWE-bench measures.

**Where it's heading.** **High confidence: files get smaller and split by scope.** The mechanisms are already shipped: path-scoped rules in `.claude/rules/` with `paths:` frontmatter that load only when the agent touches a matching file, skills for procedures that load on invocation, and `claudeMdExcludes` for ignoring other teams' files in a monorepo. `/doctor` (v2.1.206+) now actively *proposes trims* to a checked-in `CLAUDE.md`, cutting content the model can derive from the codebase (directory layouts, dependency lists, architecture overviews) and keeping pitfalls, rationale, and conventions that differ from tool defaults. That is a vendor shipping the study's conclusion. **High confidence: cross-tool convergence on `AGENTS.md` continues,** with each tool's native file becoming a thin pointer. Claude Code reads `CLAUDE.md`, not `AGENTS.md`, and the documented pattern is a `CLAUDE.md` whose first line is `@AGENTS.md` followed by Claude-specific additions. **Medium confidence: agent-maintained memory eats the descriptive half of context files.** Auto memory already writes its own notes per repository (`~/.claude/projects/<project>/memory/MEMORY.md`, first 200 lines or 25KB loaded, topic files read on demand, with a `modified` ISO-8601 frontmatter timestamp so staleness is visible), and it is enabled by default. If the agent can learn build commands by being corrected once, the hand-written half shrinks to genuinely non-inferable policy. **Speculative: the descriptive content moves into enforcement.** The direction of travel is that anything worth stating is worth checking, so the artifact stops being prose and becomes an import-linter config, a type signature, or a CI rule. Flag that as a bet, not a report.

---

## Mental model

Two pictures. First, the derivability test, which is the only filter you need:

```
  For each candidate line, ask: CAN THE AGENT DERIVE THIS BY LOOKING?
  ┌──────────────────────────────────────────────────────────────┐
  │                                                              │
  │  DERIVABLE (delete it)          NON-INFERABLE (keep it)      │
  │  ────────────────────           ─────────────────────        │
  │  directory layout               `uv sync --all-extras`       │
  │  dependency list                "integration tests need a    │
  │  "this is a FastAPI app"         local Redis on :6380"       │
  │  what each module does          "the retry wrapper in        │
  │  language / framework            adapters/ is load-bearing;  │
  │  README restated                 do not 'simplify' it"       │
  │  architecture overview          "prefer 3 duplicate lines    │
  │                                  over a premature abstraction"│
  │      ↑ THE PART THE STUDY           ↑ the part the study     │
  │        FOUND UNHELPFUL                found IS followed      │
  └──────────────────────────────────────────────────────────────┘
```

Second, the load hierarchy, because scoping is how you get small files without losing coverage:

```
  ALWAYS IN CONTEXT, EVERY REQUEST            LOADS ON DEMAND
  ─────────────────────────────────           ─────────────────────────
  managed policy CLAUDE.md    (IT/MDM)        .claude/rules/*.md WITH paths:
  ~/.claude/CLAUDE.md         (you)             → fires when a matching file is READ
  ~/.claude/rules/*.md        (you)           subdir CLAUDE.md
  ./CLAUDE.md or ./.claude/CLAUDE.md (team)     → fires when a file in that dir is READ
  ./.claude/rules/*.md (no paths:)              → NOT re-injected after /compact
  ./CLAUDE.local.md           (gitignored)    skills   → fire on invocation
  @imports (recursive, max 4 hops)            MEMORY.md topic files → read on demand
  ─────────────────────────────────
  concatenated ROOT → CWD, so the file closest
  to where you launched is read LAST.
  CLAUDE.local.md is appended after CLAUDE.md at each level.
  contradictions are resolved ARBITRARILY.  ← the nondeterminism bug
```

The rule to say out loud: **always-loaded content is a tax on every request; on-demand content is free until relevant. Default to on-demand and promote only what the agent needs on turn one.**

---

## How it actually works

### Loading and precedence, precisely

Claude Code walks *up* the directory tree from the working directory, collecting `CLAUDE.md` and `CLAUDE.local.md` at every level, and concatenates them (they do not override each other) ordered from filesystem root down to your cwd, so instructions closest to launch are read last. Within a level, `CLAUDE.local.md` is appended after `CLAUDE.md`. Subdirectory files *below* cwd are discovered but not loaded at launch; they enter context when the agent reads a file in that directory, and they are **not re-injected after compaction**. Managed policy files (`/Library/Application Support/ClaudeCode/CLAUDE.md`, `/etc/claude-code/CLAUDE.md`, `C:\Program Files\ClaudeCode\CLAUDE.md`, or the `claudeMd` key in `managed-settings.json`) load first and **cannot be excluded by individual settings**. `--add-dir` directories do not contribute memory files unless `CLAUDE_CODE_ADDITIONAL_DIRECTORIES_CLAUDE_MD=1`.

Two mechanical details that come up in interviews. `@path/to/file` imports are expanded **at launch**, recursively to a maximum depth of 4 hops, so splitting a 600-line file into six imported 100-line files is an organizational improvement and **zero** context saving. Import parsing skips code spans and fenced blocks, so `` `@README` `` in backticks stays literal. And block-level HTML comments (`<!-- maintainer note -->`) are stripped before injection, which makes them the correct place for notes to humans that should not cost tokens.

### What the evidence says to write

Combine the ETH result with the vendor guidance and you get four categories, in descending order of value.

**1. Exact commands.** The highest-value content, and the one thing agents cannot reliably guess in a non-standard repo. Copy-pasteable, with the flags.

**2. Non-obvious conventions and pitfalls.** Things that differ from tool defaults, where the codebase's own patterns are ambiguous or where the obvious choice is wrong.

**3. Behavioural policy.** Read before modifying; do not add unrequested features; do not comment code you did not change; do not add error handling the contract does not require; diagnose before retrying; stop and ask above a stated uncertainty threshold. These are *followed* per the study, and they are the closest thing to leverage you have at Level 1.

**4. Pointers.** Where to look next, not what everything is. `docs/adr/` exists; read it before proposing a module-boundary change; stop if your plan contradicts an ADR.

And what to delete: the repository overview, the directory tree, the dependency list, "this project uses FastAPI and Postgres," prose explanations of why the architecture is the way it is (that is an ADR, link to it), anything restating the README, and anything you would be upset to find violated but have not enforced.

A file that survives contact, at roughly 60 lines:

```markdown
# CLAUDE.md

## Commands (exact)
Install:      uv sync --all-extras
Test (fast):  pytest -q -x -m "not integration"
Test (full):  pytest -q          # needs Redis on :6380 — `make redis` first
Lint:         ruff check . && ruff format --check .
Types:        mypy --strict src/
Migrate:      alembic upgrade head
Run lint + types + fast tests before claiming a task is done. Paste the output.

## Non-obvious
- `src/domain/` is pure. No I/O, no framework imports. Enforced by import-linter.
- Public functions return `Result[T, DomainError]`. Never raise across `src/api/`.
- Every migration needs a tested `downgrade`. Enforced by scripts/migration_lint.py.
- The retry wrapper in `src/adapters/clickhouse.py` handles a specific OOM pattern.
  Do not "simplify" it. See docs/adr/0014-clickhouse-retry.md.
- 22 locales. Any string that reaches a user goes through `i18n.t()`, no exceptions.
- New dependency requires an ADR note. Enforced by a CI diff check.

## Behaviour
- Read a file before modifying it.
- Prefer three duplicate lines over a premature abstraction.
- Do not add comments to code you did not change.
- Do not add error handling the contract does not require.
- If a command fails, diagnose before retrying. Do not retry blind.
- Report honestly. Do not claim you ran something you did not run.
- If you are more than ~60% unsure about a module boundary, stop and ask.

## Pointers
- `docs/adr/` — read before proposing a boundary change. If your plan contradicts
  an ADR, stop and say so.
- `docs/runbooks/` — on-call procedures. Not needed for code changes.

## Done means
Lint clean, types clean, tests pass, the spec's verification steps executed with
output pasted, and one paragraph listing anything you changed that the spec did
not ask for (ideally: nothing).

## Compact Instructions
Preserve: files modified, architectural decisions made, error states hit,
function signatures touched, test results, and pending tasks.
```

Notice what is *not* there: no tree, no framework list, no module-by-module description. Notice also that every hard rule is annotated with where it is actually enforced. The prose exists to save the agent a wasted cycle, not to create the constraint, and saying so in the file keeps you honest about which rules are real.

The `## Compact Instructions` section at the bottom is the cheapest win in the file. A structured preservation checklist before compaction raised summary content from 1,643 to 2,455 tokens, a 49% improvement, for about $0.013.

### Scoping: how to get coverage without weight

Three mechanisms, and choosing correctly between them is the actual skill.

| Content | Mechanism | Loads |
|---|---|---|
| Facts needed on turn one, everywhere | `CLAUDE.md` | every request |
| Rules for one area of the tree | `.claude/rules/x.md` with `paths: ["src/api/**/*.py"]` | when a matching file is read |
| Multi-step procedures | a skill | on invocation |
| Package-local rules in a monorepo | nested `.claude/CLAUDE.md` or nested rules | when a file there is read |
| Your machine's quirks | `CLAUDE.local.md` (gitignored) or `~/.claude/rules/` | every request |
| Org-wide policy nobody can opt out of | managed policy `CLAUDE.md` / `claudeMd` setting | every request, unexcludable |

```markdown
---
paths:
  - "src/api/**/*.py"
  - "tests/api/**/*.py"
---

# API layer rules
- Handlers are thin. No business logic, no direct DB access.
- Every endpoint validates input with a Pydantic model. No raw dicts.
- Errors return the standard envelope from `src/api/errors.py::to_response`.
- Never return a domain object directly; map to a response model.
```

That file costs zero tokens until the agent reads something under `src/api/`. Moving four rules out of `CLAUDE.md` into two path-scoped files typically cuts the always-loaded footprint by 30-50% with no loss of coverage, and it removes the contradiction risk between rules that apply to different layers. A budgeting detail if you use brace expansion: a rule's whole `paths` list shares one budget of 1,000 expanded patterns and 4 MiB, and any pattern exceeding it is used unexpanded, where literal braces match nothing, so a clever `{a,b}/{c,d}/*.{ts,tsx}` can silently disable the rule.

### The aspiration failure, which is the one that actually hurts

Every other failure in this module costs you tokens. This one costs you architecture.

The mechanism: somebody writes `CLAUDE.md` while planning a refactor, describing the target structure. The refactor lands 60%. Nobody updates the file. Six weeks later an agent reads "business logic lives in `src/domain/`, adapters are the only I/O," believes it, plans against it, and produces a change that is internally coherent and wrong about the actual dependency graph. The diff looks excellent. It passes review because the reviewer also half-believes the file. Three PRs later, the invented boundary is load-bearing.

Why it is worse than an empty file: with no context file the agent reads the code and derives the real structure, which is what the ETH ablation shows it does anyway. A false context file *replaces* that derivation with a confident wrong prior, and the study's other finding is that **instructions are followed well**, which is exactly the property that makes a wrong instruction dangerous.

Observable symptoms, in rough order of when you notice:

- The agent's plan references a module or interface that does not exist, phrased with total confidence.
- `grep` for a rule the file states as universal returns violations in the current codebase.
- A new hire says "the file says X but the code does Y" in their first week. This is the cheapest detector you have and you should ask explicitly.
- Agents keep "fixing" code toward the file's structure in unrelated PRs (scope leakage with a plausible justification).

Three defences that work, and one that does not:

1. **Assert it in CI.** Anything stated as an invariant gets a check. `import-linter` for layering, a boundary test, a `grep` gate, a type signature. Then the file can only lie until the next build.
2. **Date and own it.** Auto memory does this automatically: files with frontmatter get a `modified` ISO-8601 timestamp on each write (v2.1.214+), which shows both you and the agent how current a fact is. Do the same by hand: a `<!-- reviewed 2026-07-26 by hari -->` HTML comment costs zero tokens because block comments are stripped before injection.
3. **Run `/doctor` and take the trims.** It specifically proposes cutting content derivable from the codebase and keeping pitfalls and conventions, which is the aspiration-prone content versus the durable content.

What does not work: "review the file quarterly." Nobody does, and the file drifts fastest exactly when the codebase is moving fastest.

### Generated files: use the generator, do not ship its output

`/init` reads the codebase and writes a starting file; with `CLAUDE_CODE_NEW_INIT=1` it runs an interactive multi-phase flow, explores with a subagent, asks follow-ups, and presents a reviewable proposal before writing. It also reads `.cursor/rules/`, `.cursorrules`, `.github/copilot-instructions.md`, and (with the new flow) `AGENTS.md`, `.devin/rules/`, `.windsurf/rules/`, `.clinerules`, so it is genuinely useful for consolidating a sprawl.

But ship the output unedited and you have built precisely the artifact the study measured as harmful: an LLM-generated overview of a repository the agent can already read. The numbers again: 5 of 8 settings worse, ~3 points down on average, 2-4 extra reasoning steps, >20% more inference cost, and human-curated files beating generated ones by ~4 points across all four agents. The workflow that follows: generate, then delete every line that is derivable, then add the pitfalls the generator could not know because they live in incident retrospectives and people's heads.

---

## Build it from scratch

No lab folder; this is a 90-minute exercise on a repository you own, and the deliverable is a number.

**Step 1: baseline.** Pick 10 real tasks with machine-checkable outcomes (a failing test to fix, a small feature with an existing acceptance test, a migration). Run each in a fresh session with your context file *disabled* (move it aside). Record pass/fail, turns, input tokens, and wall time. This is the control the ETH authors had and almost no team has.

**Step 2: measure your current file.** Same 10 tasks, file restored. If success is flat or down while token cost is up, you have reproduced the paper on your own repo, and that is the single most persuasive artifact you can bring to an interview or an internal argument.

**Step 3: ablate by section.** Run again with (a) the overview section deleted, (b) commands only, (c) commands plus behavioural policy. Expect (b) and (c) to beat the full file. The published mechanism predicts (a) alone recovers most of the loss.

**Step 4: rewrite by the derivability test.** Delete anything the agent can derive. Move anything area-specific into `.claude/rules/` with `paths:`. Move anything procedural into a skill. Target under 200 lines, and record the before/after startup footprint from `/context`.

**Step 5: find the lies.** For each statement in the file phrased as an invariant, write the check that proves it. `import-linter` contracts, a boundary test, a `grep` in CI. Count how many were false. In a repo older than a year, two or three is typical, and each one was silently steering every agent in the repo.

**Step 6: assert it.** Add a CI job that fails if `CLAUDE.md` exceeds 200 lines, and one that fails if any documented invariant's check fails. Now the file cannot rot silently.

---

## How it's done in production

The mature setup is thin at the top and scoped underneath:

```
repo/
├── AGENTS.md                     # source of truth, cross-tool, ~80 lines
├── CLAUDE.md                     # @AGENTS.md + Claude-specific additions only
├── CLAUDE.local.md               # gitignored: your ports, your test data
└── .claude/
    ├── rules/
    │   ├── api.md                # paths: src/api/**
    │   ├── domain.md             # paths: src/domain/**
    │   ├── migrations.md         # paths: alembic/**
    │   └── testing.md            # paths: tests/**
    ├── skills/
    │   ├── ship-migration/       # procedure, loads on /ship-migration
    │   └── triage-incident/
    └── settings.json             # hooks: where the RULES actually live
```

`CLAUDE.md` is three lines:

```markdown
@AGENTS.md

## Claude Code
Use plan mode for changes under `src/billing/`.
```

On Linux and macOS a symlink (`ln -s AGENTS.md CLAUDE.md`) works if you need no Claude-specific content. On Windows a symlink needs Administrator or Developer Mode, so use the `@AGENTS.md` import.

For monorepos: a root file with only cross-cutting facts, per-package nested `.claude/CLAUDE.md` and rules, and `claudeMdExcludes` in `.claude/settings.local.json` to skip other teams' ancestor files (glob-matched against absolute paths, arrays merge across settings layers, and managed policy files cannot be excluded). Cursor practitioners converge on the same shape from a different direction: keep always-apply context (`AGENTS.md` plus always-apply rules) under ~3,000 tokens and move anything over ~15% of the context budget to conditional activation.

**Failure-mode table**

| Symptom | Cause | Fix |
|---|---|---|
| Agent confidently references a module or interface that does not exist | Aspirational file: it describes the intended architecture, and instructions *are* followed | Assert every stated invariant in CI; delete anything unenforced; date-stamp the file with an HTML comment |
| Task success flat or worse after adding a context file, cost up ~20% | Overview content duplicating a README the agent reads anyway | Delete the overview. Keep commands, pitfalls, behavioural policy. Run the 10-task ablation to prove it |
| Rules obeyed inconsistently across sessions on the same repo | Two files in the hierarchy contradict each other; the model picks arbitrarily | Audit root → cwd concatenation order; `claudeMdExcludes` for other teams' files; remove one of the two rules |
| Rule works while editing `src/api/` then stops after a compaction | Nested subdirectory `CLAUDE.md` is loaded on demand and **not** re-injected after `/compact` | Hoist to project root, or convert to `.claude/rules/` with `paths:` |
| Split a 600-line file into six imports; `/context` shows no savings | `@imports` are expanded at launch, recursively to 4 hops. Organizational only | Use path-scoped rules or skills, which are genuinely lazy |
| Adherence dropped as the file grew past a few hundred lines | Longer files consume more context and reduce adherence; no hard cap, just decay | Target under 200 lines; `/doctor` (v2.1.206+) proposes the trims |
| Path-scoped rule silently never fires | Brace expansion exceeded the 1,000-pattern / 4 MiB budget, so the pattern is used unexpanded and literal braces match nothing; or an invalid `[` bracket expression | Simplify patterns; verify with an `InstructionsLoaded` hook |
| A rule is in the file, `/context` confirms it loaded, behaviour still violates it | Instruction files are context, not enforced configuration | Escalate: `PreToolUse` hook with exit 2, a lint rule, a type that makes it unrepresentable, or a CI gate |
| `MEMORY.md` grew and older entries stopped applying | Only the first 200 lines or 25KB load at session start; content past that is dropped | Claude Code warns and errors on over-limit writes; keep one line per entry and push detail into topic files |
| Auto memory contains a stale fact you cannot find | It is plain markdown you can edit; the `modified` frontmatter timestamp shows currency | `/memory` → open the auto memory folder; edit or delete |

---

## Tradeoffs & when NOT to use it

- **Do not write a context file for a repository the agent can read.** This is the study's actual conclusion and it is uncomfortable: on standard, well-documented projects the marginal value of a context file is around zero and the cost is over 20%. If your repo has a good README, standard tooling, and conventional layout, a context file with only the three commands that differ from the defaults is the *complete* correct answer. A 300-line file on such a repo is a net negative.
- **Do not ship `/init` output.** The generator is a research tool. Its output is the exact artifact measured as harmful: an LLM-written overview of a repo the agent already reads. Generate, then delete the derivable half, then add what the generator could not know.
- **Do not use a context file to enforce anything.** It is delivered as a user message after the system prompt and is explicitly context, not configuration. `permissions.deny` blocks tools; hooks block actions; a `Result` return type makes raising unrepresentable. A bullet point does none of those. The docs are unusually blunt: settings rules are enforced by the client regardless of what Claude decides; `CLAUDE.md` instructions shape behaviour but are not a hard enforcement layer.
- **Do not put secrets, environment values, or permission logic in it.** It is committed, it is loaded into every request, and (for project-level external imports) it is a file other people can commit into your repo, which is why Claude Code shows an approval dialog the first time a project memory file imports something outside the working directory.
- **Do not centralize in a monorepo without exclusions.** Ancestor `CLAUDE.md` files load in full at launch, so a 12-team monorepo can silently load eleven other teams' conventions into your window and generate contradictions the model resolves arbitrarily. `claudeMdExcludes` exists for exactly this.
- **Do not assume the study settles it.** Two honest caveats. It measures issue-resolution success on benchmark-style tasks, which is not the same as *conforming to a team's conventions*, and a file whose value is "the agent stops raising exceptions across the service boundary" would not register as a win on SWE-bench at all. And the tested files were mostly generated or scraped from repos, not carefully curated to the study's own recommendation. The defensible position is the authors' own: context files are useful for specifying non-standard practices, and any attempt to improve performance with them should be *evaluated before deployment* rather than assumed. If you are not measuring, you are guessing, and the guess has been wrong at scale.
- **The counter-argument worth stating:** practitioners who get real value from long context files are usually enforcing *taste* rather than correctness, in codebases with unwritten invariants where benchmark task success is not the metric. That is a legitimate use the study does not cover. It is still cheaper as a path-scoped rule than as always-loaded prose.

---

## Interview questions

### Q1 — Write me a CLAUDE.md for a service you own.
**Testing:** whether you know the difference between agent-operational policy and human documentation.
**Answer:** Four sections and nothing else. Commands, exact and copy-pasteable, with the non-obvious flags and prerequisites ("full tests need Redis on :6380, run `make redis` first"). Non-obvious conventions and pitfalls, each annotated with where it is actually enforced, so the prose saves the agent a cycle rather than pretending to be the constraint. Behavioural policy: read before modifying, prefer three duplicate lines over a premature abstraction, do not comment unchanged code, do not add error handling the contract does not require, diagnose before retrying, report honestly, stop and ask above roughly 60% uncertainty on a boundary. And pointers: `docs/adr/` exists, read it before proposing a boundary change, stop if your plan contradicts one. Plus a `Compact Instructions` block, and a `Done means` block with verifiable criteria. Target under 200 lines; mine is usually 50-70.
**Follow-up trap:** *"You left out the architecture overview. Every template has one."* Deliberately. The ETH Zurich evaluation (arXiv:2602.11988) found context files did not generally improve task success while adding over 20% inference cost, and isolated the culprit: instructions were followed well, but repository overviews, "although popular and recommended by model providers, are not helpful." The mechanism is redundancy, confirmed by their ablation, where removing all other repo documentation made generated files help by 2.7%. The overview duplicates a README the agent reads anyway. Worse, the overview is the section most likely to go stale, and because instructions *are* followed, a stale overview is a confident wrong prior rather than harmless noise.

### Q2 — Is putting "never raise across the service boundary" in CLAUDE.md enough?
**Testing:** the instruction-versus-enforcement distinction, which is the central architectural idea in the whole track.
**Answer:** No. Three levels of control and only the third is real. Instruction: `CLAUDE.md` states it, which is a recommendation delivered as a user message after the system prompt, explicitly context and not enforced configuration. Reminder: a skill or path-scoped rule re-states it at the moment it matters, which raises compliance and is still probabilistic. Enforcement: the public function signature returns `Result[T, DomainError]` so raising is unrepresentable, plus a lint rule, plus a CI gate. Only the third has an effectiveness that does not depend on the model's cooperation. The rule I apply: anything I would be upset to find violated belongs at level three, and if it is only in markdown I have expressed a preference, not a policy.
**Follow-up trap:** *"Then why write it down at all?"* Two reasons and they are both economic. It saves a wasted cycle: the agent writes the raising version, CI rejects it, it rewrites, and I have paid two round trips to communicate something one sentence would have conveyed. And documented instructions *are* followed well, per the same study, so level one buys real compliance, just not guaranteed compliance. The mistake is not writing it down, it is *stopping* there and believing the rule is now enforced.

### Q3 — Our CLAUDE.md is 700 lines and the agent ignores half of it. Diagnose.
**Testing:** whether you fix size or fix structure.
**Answer:** Three separate problems, and size is the least interesting. First, always-loaded weight: longer files consume more context and measurably reduce adherence, with a documented target of under 200 lines. Second, and more likely at 700 lines, contradictions: a file that big has accumulated rules from a dozen incidents and some of them disagree, and when two instructions conflict the model picks one arbitrarily, which presents as "ignores half of it" but is actually nondeterminism. Third, derivable content: probably 200-300 of those lines are a directory tree and architecture overview that the model would derive correctly by reading, and that content is measurably unhelpful. Fix: run `/doctor`, which proposes trims specifically along the derivable-versus-durable line; move area-specific rules into `.claude/rules/` with `paths:` so they cost nothing until relevant; move procedures into skills; and grep for contradictions.
**Follow-up trap:** *"Can I just split it into six files with `@imports`?"* That fixes maintainability and saves exactly zero context. `@path` imports are expanded and loaded at launch, recursively up to 4 hops, so all six files are in every request. The mechanisms that are genuinely lazy are path-scoped rules (load when a matching file is read), skills (load on invocation), and subdirectory `CLAUDE.md` (loads when a file in that directory is read, with the caveat that it is not re-injected after compaction).

### Q4 — What's the worst failure mode of a context file?
**Testing:** whether you have lived with one, and whether you volunteer the architecture-level failure rather than the token-level one.
**Answer:** Aspiration. The file describes the architecture somebody intended rather than the one on disk: the refactor landed 60%, nobody updated the file, and now every agent in the repo starts from a confident false premise. It is worse than having no file, because with no file the agent reads the code and derives the real structure, whereas a wrong file *replaces* that derivation. And the study's finding that instructions are followed well is exactly what makes it dangerous. The output is locally excellent and globally wrong, so it passes review, and by the third PR the invented boundary is load-bearing. Symptoms: plans referencing modules that do not exist, `grep` finding violations of a rule the file states as universal, a new hire saying "the file says X but the code does Y," and agents opportunistically "fixing" unrelated code toward the file's structure.
**Follow-up trap:** *"How do you prevent it, given nobody reviews docs?"* You do not rely on review. Every statement phrased as an invariant gets a machine check: `import-linter` for layering, a boundary test, a `grep` gate in CI. Then the file can only lie until the next build. The corollary is a policy: **if a claim is not worth asserting in CI, it is not worth stating as an invariant in the file** — downgrade it to a preference or delete it. Plus two cheap habits: a `<!-- reviewed YYYY-MM-DD -->` HTML comment (block comments are stripped before injection, so it costs zero tokens) and asking every new hire in week one which lines are wrong.

### Q5 — CLAUDE.md, AGENTS.md, .cursorrules, copilot-instructions.md. How do you organize a polyglot team?
**Testing:** practical multi-tool reality.
**Answer:** `AGENTS.md` as the single source of truth, because it is the de facto cross-tool convention read natively by Codex, Cursor, Copilot, Gemini CLI, Aider, Windsurf and others under Linux Foundation stewardship. Then thin per-tool pointers. Claude Code reads `CLAUDE.md`, not `AGENTS.md`, so `CLAUDE.md` is `@AGENTS.md` followed by Claude-specific additions only, or a symlink if you need nothing Claude-specific (Administrator or Developer Mode required on Windows, so prefer the import there). `/init` reads Cursor and Copilot rule files and consolidates them, and with `CLAUDE_CODE_NEW_INIT=1` it also reads `AGENTS.md`, `.devin/rules/`, `.windsurf/rules/`, `.clinerules`. The thing to avoid is three parallel copies of the truth, because they drift within weeks and then the tools disagree about your conventions.
**Follow-up trap:** *"AGENTS.md is a standard, right?"* It is a convention, not a standard: no ISO, no IETF, no normative spec, stewarded under the Linux Foundation's Agentic AI Foundation, with adoption driven by tool vendors choosing to read the filename. Practically that means the *filename* is portable and the *semantics* are not: tools differ on whether nested files load, whether they are re-injected after compaction, whether path scoping exists, and how precedence resolves. So write content that degrades gracefully, favour plain imperative statements over tool-specific frontmatter in the shared file, and keep anything mechanism-dependent in the per-tool file.

### Q6 — Would you let the agent maintain its own context file?
**Testing:** whether you distinguish learned facts from policy.
**Answer:** For learned facts, yes, and that is what auto memory already is: enabled by default, per-repository at `~/.claude/projects/<project>/memory/`, first 200 lines or 25KB of `MEMORY.md` loaded at session start with topic files read on demand, and files carrying a `modified` ISO-8601 timestamp so staleness is visible to me *and* to the model. Build commands, "the integration tests need Redis," "this codebase uses pnpm" are exactly right for it, because they are facts discovered by being corrected once. For policy, no. The `CLAUDE.md` is a team artifact under review, and a model-written policy file is the generated-overview failure with a longer half-life: LLM-generated context files reduced task success in 5 of 8 settings by about 3 points, and human-curated files beat them by roughly 4 points across all four agents tested.
**Follow-up trap:** *"So `/init` is useless?"* No, it is a good research tool and a good consolidator, since it reads existing Cursor/Copilot/Windsurf rule files and reports what it derived. The mistake is *committing* its output. The workflow is: generate, delete everything derivable (which is most of it), then add the pitfalls it could not know because they live in incident retrospectives and people's heads. `/doctor` (v2.1.206+) even automates the deletion half, proposing trims to a checked-in `CLAUDE.md` that cut derivable content and keep pitfalls, rationale, and conventions differing from defaults.

### Q7 — How would you prove your context file is helping?
**Testing:** whether you measure or believe. This is the question the ETH paper exists to make askable.
**Answer:** A/B on a fixed task set from cold contexts. Ten real tasks with machine-checkable outcomes, each run in a fresh session with the file present and with it moved aside, recording pass/fail, turns, input tokens, wall time. Then ablate by section, because the interesting result is per-section: expect commands-plus-behaviour to beat the full file and the overview to be a net negative. The reason this has to be measured rather than assumed is that the aggregate result went the other way: across four agents and two benchmarks, context files did not generally improve success while costing over 20% more inference, and the authors' explicit conclusion is that any attempt to improve performance this way should be rigorously evaluated before deployment. Self-report is worthless here for the same reason it is worthless for productivity generally.
**Follow-up trap:** *"Ten tasks isn't statistically meaningful."* Correct, and it is still enormously better than the zero measurements almost every team has, and it reliably catches the large effects, which are the ones that matter: a 20% cost increase and a wrong invariant show up immediately. For a real decision I would widen it, stratify by task type (bug fix, feature, migration, refactor), run each three times because agent runs are stochastic, and report the ablation deltas rather than absolute pass rates, since the absolute number is dominated by task difficulty. And I would treat the per-section ablation as the primary output, because "should we have a file" is less useful than "which 30 lines are earning their keep."

### Q8 — Path-scoped rules versus skills versus CLAUDE.md. Pick correctly.
**Testing:** whether you know the loading semantics, which is the whole basis of the choice.
**Answer:** `CLAUDE.md` for facts needed on turn one everywhere, paid on every request. `.claude/rules/*.md` with `paths:` frontmatter for rules about one area, which cost nothing until the agent reads a matching file, making them the right home for layer-specific conventions. Skills for multi-step procedures, which cost only their description line until invoked. The decision rule is a question: does the agent need this before it knows what it is touching? If yes, `CLAUDE.md`. If it depends on which files are in play, a path-scoped rule. If it is a sequence of steps rather than a fact, a skill. And a rule without `paths:` in `.claude/rules/` loads unconditionally at the same priority as `.claude/CLAUDE.md`, which people forget and then wonder why their "modular" rules cost as much as the monolith.
**Follow-up trap:** *"What breaks when you move a rule to a path-scoped file?"* Two things. It fires when a *matching file is read*, not on every tool use, so a rule that needs to be true before the agent decides which file to open (like "never touch `src/legacy/`") is in the wrong mechanism and belongs in `CLAUDE.md` or a `permissions.deny` entry. And glob budgeting bites: a rule's `paths` list shares a budget of 1,000 expanded patterns and 4 MiB, and any pattern that would exceed it is used unexpanded, where literal braces match nothing, so the rule silently never fires. I verify with an `InstructionsLoaded` hook, which logs exactly which instruction files loaded, when, and why.

### Q9 — Managed policy CLAUDE.md versus managed settings. When do you use which?
**Testing:** whether you understand that the enforcement boundary is organizational too.
**Answer:** Split by whether the thing is behavioural or technical. Managed settings for anything you need actually enforced: `permissions.deny` to block tools, commands, or paths; `sandbox.enabled`; `env` for provider routing; `forceLoginMethod` and `forceLoginOrgUUID`. Those are enforced by the client regardless of what the model decides. Managed policy `CLAUDE.md` (`/etc/claude-code/CLAUDE.md`, the macOS Application Support path, `C:\Program Files\ClaudeCode\CLAUDE.md`, or the `claudeMd` key in `managed-settings.json`) for behavioural guidance: code style, data-handling reminders, compliance framing. It loads before user and project files and cannot be excluded by individual settings, which is the point.
**Follow-up trap:** *"Compliance wants 'never send customer data to a third-party API' in the managed CLAUDE.md. Is that sufficient?"* No, and this is the version of the instruction-versus-enforcement error that has legal consequences. A managed `CLAUDE.md` is unexcludable *context*, which makes it a durable recommendation and nothing more. The enforceable version is `permissions.deny` on the relevant tools and hosts, network egress restrictions, sandboxing, and a `PreToolUse` hook that inspects payloads. I would put the sentence in the managed file too, because it saves cycles and documents intent, but I would tell compliance plainly that the control is the deny rule and the file is the reminder.

### Q10 — Your monorepo has 12 teams. Design the context file layout.
**Testing:** scaling behaviour and the specific monorepo failure.
**Answer:** Thin root, scoped everything. Root `AGENTS.md` with only genuinely cross-cutting facts: the build tool, the CI gates, the "never do this" list. Per-package nested `.claude/CLAUDE.md` and `.claude/rules/`, which load when the agent reads a file in that package, and which also lets a package ship its own skills that become available when work touches it. Then `claudeMdExcludes` in `.claude/settings.local.json` with globs against absolute paths so I do not load eleven other teams' conventions into my window, remembering that arrays merge across settings layers and managed policy files cannot be excluded. The failure this prevents is specific: ancestor files load *in full* at launch, so without exclusions every session pays for the whole org's accumulated rules and then resolves contradictions between them arbitrarily.
**Follow-up trap:** *"How do you keep the root file from becoming a dumping ground?"* Make it expensive to add to and cheap to scope. Concretely: a CI check that fails if root `AGENTS.md` exceeds 200 lines, ownership on the file (a CODEOWNERS entry with a small group, not the whole org), and a written rule that any addition must state which package it does *not* apply to, because if the answer is "none" it usually belongs in a package rule. And a quarterly ablation on the 10-task set. Governance without measurement just produces a slower dumping ground.

### Q11 — An agent produced a beautiful PR built on a module that does not exist. Walk me through the postmortem.
**Testing:** whether you trace the failure to the context layer instead of blaming the model.
**Answer:** First question: where did the false premise come from? Check `/context` for which memory files loaded, and diff the file's claims against reality. In my experience it is the context file's overview section describing an intended structure, which is exactly the content the ETH study found unhelpful and which is also the most staleness-prone. Second question: why did review not catch it? Because the reviewer holds the same wrong model, from the same file. Third: how deep is it? If the invented boundary has three PRs on it, the fix is a revert-and-replan, not a patch, because assumption propagation is not fixable at diff-review time. Then the actual remediation: delete the overview, assert the real boundaries with `import-linter` contracts and boundary tests in CI, and add the plan-review gate so premises get checked before code exists.
**Follow-up trap:** *"Isn't the real lesson just 'keep docs updated'?"* No, and that lesson has failed for thirty years. The lesson is that **prose about structure is unverifiable, so it should not be load-bearing.** An `import-linter` contract stating `domain` cannot import `adapters` is the same claim in a form that fails the build when it becomes false. The context file should then point at the contract rather than restate it. That converts a documentation-discipline problem, which humans lose, into a build-failure problem, which humans fix within the hour.

### Q12 — Someone on your team says context files are a waste of tokens and cites the ETH paper. Respond.
**Testing:** whether you can hold a nuanced position on evidence that cuts against the industry consensus.
**Answer:** They are substantially right and slightly overreaching. Right: across four agents and two benchmark settings, context files did not generally improve task success and cost over 20% more inference; generated files were worse than nothing in 5 of 8 settings; and the recommended overview section is specifically unhelpful because it duplicates documentation the agent reads anyway. Overreaching in two ways. The paper measures issue-resolution success, and a rule like "return `Result` instead of raising across the API boundary" would not register as a win on SWE-bench even though it is the whole reason my team has the file. And the paper's own conclusion is not "delete your file," it is that files are useful for specifying **non-standard** practices and that performance claims should be evaluated before deployment. So the correct action is to cut the file to non-inferable content and then measure, which is roughly a 70% deletion in most repos.
**Follow-up trap:** *"So what would change your mind in the other direction?"* A study measuring convention conformance rather than task completion, on a mature codebase with unwritten invariants, using human-curated files written to the paper's own recommendation. That is the gap: the tested files were mostly generated or scraped, and the tasks were benchmark issues on public repos where the agent had good documentation to fall back on. Their ablation actually hints at the answer, since removing other documentation made generated files help by 2.7%, which suggests the value of a context file is inversely proportional to how well-documented your repo already is. That is a testable prediction and it is the one I would run on my own repo first.

---

## Red flags that fail you

- Recommending a repository overview / directory tree section in 2026.
- Committing `/init` output unedited.
- Believing `CLAUDE.md` is part of the system prompt or is enforced.
- Thinking `@imports` reduce context cost.
- No answer for how you detect that the file has drifted from the code.
- Stating invariants in prose that are not asserted anywhere.
- Never having measured whether the file helps.
- Maintaining three parallel per-tool rule files with the same content.
- Putting secrets, permission logic, or environment values in a committed context file.
- Calling `AGENTS.md` a standard.
- Answering "the agent ignores my rules" with "make the file longer."
- Centralizing in a monorepo without `claudeMdExcludes`.

## Cheat card

```
THE EVIDENCE (arXiv:2602.11988, ETH Zurich, Feb→Jun 2026)
  4 agents (Claude Code/Sonnet 4.5, Codex/GPT-5.2 + 5.1-mini, Qwen Code/Qwen3-30B)
  context files DID NOT generally improve task success · cost +20%+ inference
  LLM-generated: worse in 5/8 settings, ≈−3pp, +2-4 reasoning steps
  human-curated BEAT generated for all 4 agents by ≈+4pp
  INSTRUCTIONS were followed well · REPOSITORY OVERVIEWS were NOT helpful
  ablation: delete all other repo docs → generated files then help +2.7%
  authors' conclusion: useful for NON-STANDARD practices; EVALUATE before deploying

THE FILTER   can the agent DERIVE this by looking? → then delete it
  DELETE: tree · deps · "uses FastAPI" · module descriptions · README restated
  KEEP:   exact commands · pitfalls · conventions differing from defaults ·
          behavioural policy · pointers to ADRs

FOUR SECTIONS, ~50-70 LINES
  Commands (exact, with prereqs) | Non-obvious (+ where each is ENFORCED)
  Behaviour (read-before-modify, no premature abstraction, don't comment
    unchanged code, no unrequested error handling, diagnose before retry,
    report honestly, stop above ~60% uncertainty on a boundary)
  Pointers | + Done means | + Compact Instructions

LOADING
  walk UP from cwd; ALL files CONCATENATED root→cwd (no override)
  CLAUDE.local.md appended after CLAUDE.md at each level
  subdir files: on demand, NOT re-injected after /compact
  @imports EXPANDED AT LAUNCH, recursive max 4 hops → ZERO context savings
  managed policy loads FIRST and CANNOT be excluded
  HTML block comments STRIPPED before injection → free notes to humans
  --add-dir needs CLAUDE_CODE_ADDITIONAL_DIRECTORIES_CLAUDE_MD=1

SCOPING
  CLAUDE.md            every request     facts needed on turn one
  .claude/rules + paths: on matching READ  layer/area rules
  skills               on invocation     procedures
  nested CLAUDE.md     on read in dir    package-local (not re-injected)
  CLAUDE.local.md      every request     your machine (gitignore it)
  managed policy       unexcludable      org policy (guidance, NOT enforcement)
  glob budget: 1,000 expanded patterns / 4 MiB per rule; over → used UNEXPANDED
    (literal braces match nothing → rule silently never fires)

SIZE   target <200 lines. longer = more context + LOWER adherence (no hard cap)
  /doctor v2.1.206+ PROPOSES trims: cuts derivable, keeps pitfalls+rationale
  Cursor practice: keep always-apply context under ~3,000 tokens

THREE LEVELS  instruction (CLAUDE.md) → reminder (skill/rule) → ENFORCEMENT
  (hook exit 2 / permissions.deny / lint / type / CI). Only the 3rd is a constraint.
  managed SETTINGS = enforced by the client. managed CLAUDE.md = guidance only.

AUTO MEMORY  ~/.claude/projects/<project>/memory/MEMORY.md
  first 200 lines OR 25KB loaded; topic files on demand; per-git-repo, machine-local
  `modified` ISO-8601 frontmatter (v2.1.214+) makes staleness visible
  NOT loaded into subagents (except forks)

THE ASPIRATION FAILURE (the one that costs architecture)
  file describes intended structure → agent trusts it (instructions ARE followed)
  → plausible+wrong plan → cemented over 3 PRs
  worse than NO file, because no file → agent derives the real structure
  DETECT: plan cites a module that doesn't exist · grep finds violations of a
    "universal" rule · new hire says "file says X, code does Y"
  FIX: assert every invariant in CI. if it's not worth a CI check it's not an invariant.

POLYGLOT   AGENTS.md = source of truth (convention, NOT a standard)
  CLAUDE.md = "@AGENTS.md" + Claude-specific only (symlink needs Admin on Windows)
  /init reads .cursorrules, copilot-instructions; NEW_INIT=1 also AGENTS.md,
    .devin/rules, .windsurf, .clinerules
  monorepo: thin root + per-package nested + claudeMdExcludes (globs, abs paths)

PROVE IT   10 machine-checkable tasks × {file, no file} from COLD contexts
  then ABLATE BY SECTION. expect commands+behaviour > full file > overview-only.
```

## Sources

- [Evaluating AGENTS.md: Are Repository-Level Context Files Helpful for Coding Agents?](https://arxiv.org/abs/2602.11988) — Gloaguen, Mündler, Müller, Raychev, Vechev (ETH Zurich), submitted 2026-02-12, revised 2026-06-23; the >20% cost increase with no general success improvement, instructions followed but repository overviews unhelpful, and the "evaluate before deployment" conclusion; accessed 2026-07-26
- [New Research Reassesses the Value of AGENTS.md Files for AI Coding](https://www.infoq.com/news/2026/03/agents-context-file-value-review/) — InfoQ, March 2026; the per-setting breakdown (5 of 8 settings worse, ≈3pp drop, 2-4 extra reasoning steps, ≈4pp human-curated advantage, 2.7% ablation result) and the four agents tested; accessed 2026-07-26
- [How Claude remembers your project](https://code.claude.com/docs/en/memory) — the full loading and precedence model, the under-200-line target, `@import` expansion at launch with a 4-hop limit, HTML comment stripping, path-scoped rules and their glob budget, `claudeMdExcludes`, managed policy locations and the `claudeMd` setting, the settings-versus-CLAUDE.md enforcement table, auto memory limits and the `modified` timestamp, the `AGENTS.md` import/symlink pattern, `/init` and `CLAUDE_CODE_NEW_INIT=1`, and the "Claude isn't following my CLAUDE.md" troubleshooting path; accessed 2026-07-26
- [Extend Claude Code](https://code.claude.com/docs/en/features-overview) — context cost by feature: CLAUDE.md full content every request versus skills, MCP, subagents, and hooks; accessed 2026-07-26
- [Extend Claude with skills](https://code.claude.com/docs/en/skills) — when a section of CLAUDE.md has become a procedure and should move to a skill, and the on-demand loading contract; accessed 2026-07-26
- [Get started with hooks](https://code.claude.com/docs/en/hooks-guide) — `PreToolUse` blocking with exit 2, the `InstructionsLoaded` event for debugging which instruction files loaded, and `SessionStart` with a `compact` matcher for re-injecting context after compaction; accessed 2026-07-26
- [Writing a Good AGENTS.md](https://www.philschmid.de/writing-good-agents) — practitioner guidance converging on commands-and-pitfalls over overviews; accessed 2026-07-26
- [AGENTS.md: Helpful agent briefing or token hog?](https://www.heise.de/en/background/AGENTS-md-Helpful-agent-briefing-or-token-hog-11245317.html) — heise, 2026; the cost-versus-benefit framing of the ETH result for practitioners; accessed 2026-07-26
- [Cursor Agent Best Practices 2026](https://baeseokjae.github.io/posts/cursor-agent-best-practices-2026/) — the under-3,000-token always-apply budget and the 15%-of-context threshold for moving a rule to conditional activation; accessed 2026-07-26
- [Context Compaction Showdown](https://codex.danielvaughan.com/2026/04/10/context-compaction-showdown-coding-agents/) — Daniel Vaughan, 2026-04-10; the preservation-checklist result (1,643 → 2,455 summary tokens, +49%, for $0.013) that justifies a `Compact Instructions` section; accessed 2026-07-26
- [AGENTS.md Spec (2026): Recommended Sections + AGENTS.md vs CLAUDE.md vs .cursorrules](https://www.morphllm.com/agents-md-guide) — cross-tool adoption and Linux Foundation Agentic AI Foundation stewardship; accessed 2026-07-26

## Changelog
- 2026-07-26 — created
