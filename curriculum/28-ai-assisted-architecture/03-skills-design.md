# Skills Design: The Description Is the Product

> **Track:** T28 AI-Assisted Architecture · **Time:** 2.5h · **Prereqs:** `T28-claude-code-model`, `T28-context-files` · **Updated:** 2026-07-26
> **Module id:** `T28-skills-design` · **Tags:** skills, critical

## The 30-second version

A skill is a markdown file whose body loads only when it is used, which makes it the right home for procedures that would otherwise bloat `CLAUDE.md`, and the entire mechanism turns on one line: the `description`. That single field is what the model matches your request against, it is the only part of the skill in context before invocation, and it is subject to hard budgets: capped at 1,536 characters combined with `when_to_use` in the Claude Code listing, sharing a listing budget of 1% of the context window, and when that budget overflows **descriptions are dropped starting with the skills you invoke least**, so a rarely-used skill can silently lose the keywords that would have triggered it. So the skill's quality ceiling is set by its description and everything else is implementation. Testing means two separate measurements: does it fire on the prompts it should and not on the ones it should not (a trigger question), and is the output better than baseline when it does (an output-quality question), and you need fresh sessions for both because leftover authoring context masks gaps in the written instructions. A skill is the wrong abstraction more often than people think: if it always applies it is a rule, if it is deterministic it is a script or a hook, if it must always run at a lifecycle point it is a hook, and if it is one sentence you type twice a year it is a prompt.

## Why this gets asked

Because skills are where the "instructions versus enforcement" confusion gets expensive. The interviewer has a repository with fourteen skills, of which four fire reliably, six fire occasionally, and four have never fired since the day they were written, and nobody knows which category any given skill is in because nobody measured. They also have the inverse: a `deploy` skill that the model invoked on its own because the code "looked ready." Both failures are one frontmatter field away from fixed. And there is a design-taste signal underneath: knowing when a skill is the wrong abstraction is the same judgment as knowing when a microservice is, and it is graded the same way.

---

## Lineage: past → present → future

**What came before.** Custom slash commands, roughly 2024 through mid-2025: a file in `.claude/commands/deploy.md` became `/deploy`, and that was the whole feature. It worked and it had two limits that killed it. First, invocation was manual only, so the knowledge in the file was available exactly when you remembered to type the command, which meant the most valuable content (the checklist you forget under pressure) was the content least likely to load. Second, a command was a single file, so anything with a script, a template, or reference material had to be either inlined (paying full context every invocation) or referenced by an absolute path that broke when someone else cloned the repo. Before that, the state of the art was pasting the same 40-line checklist into chat, and the pain that killed *that* was not the typing, it was version skew: five engineers each had a slightly different copy of the checklist, and nobody knew which was current.

**Where it stands now.** Custom commands have been merged into skills: `.claude/commands/deploy.md` and `.claude/skills/deploy/SKILL.md` both create `/deploy` and behave the same way, with skills adding a directory for supporting files, frontmatter for invocation control, and model-initiated loading. Claude Code skills follow the [Agent Skills](https://agentskills.io) open standard, which works across tools, and Claude Code extends it with invocation control, subagent execution, and dynamic context injection. Microsoft's Agent Framework harness ships an optional skills provider that "discovers and progressively loads Agent Skills from the file system," which is the same idea implemented independently, and that convergence is the strongest evidence the abstraction is real rather than a vendor feature. The genuinely live disagreements are two. **How much should be a skill versus a tool?** A skill is instructions the model reads; a tool (or MCP server) is code the model calls. The skill camp points out that skills cost nothing until used and are trivially versionable as markdown in your repo; the tool camp points out that a skill's compliance is probabilistic while a tool's behaviour is deterministic. Both are right, and the split is by whether the operation is fragile. **And how much freedom to give.** The official guidance is explicitly a spectrum matched to task fragility: high freedom (prose instructions) when multiple approaches are valid, medium (pseudocode, parameterized scripts) when a preferred pattern exists, low (an exact script, few or no parameters) when operations are fragile, consistency is critical, or a specific sequence must be followed.

**Where it's heading.** **High confidence: skill selection becomes a measured, tuned artifact rather than a hand-written guess.** This has already shipped: the `skill-creator` plugin runs description tuning by generating should-trigger and should-not-trigger prompts, measuring hit rate, and proposing description edits when a skill activates on the wrong requests, plus blind A/B between two versions and a with-skill-versus-without benchmark aggregating pass rate, time, and tokens. That is an eval harness for a prompt fragment, which is where the discipline is going generally. **High confidence: the listing budget becomes the binding constraint at scale.** With a 1%-of-window budget and descriptions dropped from least-used skills first, a repo with 40 skills is already in triage; expect retrieval over descriptions rather than eager listing, the same move MCP tool schemas already made. **Medium confidence: skills absorb most of what people currently put in `CLAUDE.md`.** The vendor guidance is now explicit that a section of `CLAUDE.md` which has grown into a *procedure* rather than a fact belongs in a skill, and the ETH result on context files pushes hard in the same direction. **Speculative: the skill/subagent boundary collapses.** `context: fork` plus `agent:` frontmatter already lets a skill run in an isolated forked context in the background, which is a subagent wearing a skill's clothes. Say that is a guess.

---

## Mental model

The mechanism, drawn as a funnel, because every design decision is about which stage you are optimizing:

```
  SESSION START
  ┌──────────────────────────────────────────────────────────────────┐
  │  SKILL LISTING: names + descriptions only, ~450 tok typical      │
  │  budget = 1% of context window (skillListingBudgetFraction)      │
  │  each entry: description + when_to_use capped at 1,536 chars     │
  │  OVERFLOW → descriptions DROPPED, least-invoked FIRST            │
  │  disable-model-invocation:true → NOT IN THE LISTING AT ALL       │
  └──────────────────────────────────────────────────────────────────┘
                       │
        the model matches your prompt against THESE STRINGS
        ← this is the entire selection mechanism. 100% of trigger
          quality lives here. the body is invisible at this point.
                       │
                       ▼
  ┌──────────────────────────────────────────────────────────────────┐
  │  INVOKED: full rendered SKILL.md enters the conversation as ONE  │
  │  message, and STAYS for the rest of the session                  │
  │  · !`cmd` blocks already executed and inlined                    │
  │  · $ARGUMENTS / $0 / ${CLAUDE_SKILL_DIR} already substituted     │
  │  · re-invoking with identical rendered content → a short "already│
  │    loaded" note, not a second copy                               │
  │  · allowed-tools grant applies THIS TURN ONLY                    │
  └──────────────────────────────────────────────────────────────────┘
                       │
                       ▼
  ┌──────────────────────────────────────────────────────────────────┐
  │  SUPPORTING FILES: reference.md, examples.md, scripts/*          │
  │  read ON DEMAND by ordinary file tools. free until needed.       │
  └──────────────────────────────────────────────────────────────────┘

  AFTER COMPACTION: the LISTING is not re-injected. Invoked skills are
  re-attached: most recent invocation of each, first 5,000 tokens each,
  sharing a 25,000-token budget, filled newest-first. Older ones drop.
```

The one-sentence version: **the description is a retrieval query you are writing on behalf of your future self, and the body is a document nobody will read unless the query matches.**

---

## How it actually works

### The description, in mechanical detail

Constraints first, because they determine the writing:

| Constraint | Value | Consequence |
|---|---|---|
| Combined `description` + `when_to_use` in the Claude Code listing | truncated at **1,536 chars** (`skillListingMaxDescChars`) | put the key use case **first**; the tail is what gets cut |
| Platform-level `description` field max | **1,024 chars** | write to the tighter bound for portability |
| `name` field | max **64 chars**, lowercase / digits / hyphens, no XML tags, cannot contain "anthropic" or "claude" | naming is constrained, not stylistic |
| Listing budget | **1% of the model's context window**, tunable via `skillListingBudgetFraction` or `SLASH_COMMAND_TOOL_CHAR_BUDGET` | with many skills you are in a zero-sum allocation |
| Overflow behaviour | names always listed; **descriptions dropped starting with least-invoked skills** | new and rare skills are the first to go dark |
| Missing `description` | falls back to the first paragraph of the body | a malformed YAML block yields *empty* metadata: `/name` still works, model invocation never fires |

Writing rules that follow from the mechanism:

**Third person, always.** The description is injected into the system prompt, and inconsistent point of view causes discovery problems. "Processes Excel files and generates reports," not "I can help you process Excel files."

**Two clauses: what it does, and when to use it.** The second clause is the one people omit and it is the one that determines firing.

```yaml
# good: capability + explicit triggers, key use case first
description: Summarizes uncommitted changes and flags anything risky. Use when the
  user asks what changed, wants a commit message, or asks to review their diff.

# good: includes the words a user would actually say
description: Extract text and tables from PDF files, fill forms, merge documents.
  Use when working with PDF files or when the user mentions PDFs, forms, or document
  extraction.

# useless: no trigger, no keywords, competes with everything
description: Helps with documents
```

**Include the vocabulary your users use, not the vocabulary you use.** If people on your team say "ship it," "cut a release," and "push to prod" for the same operation, all three belong in the description or in `when_to_use`. This is a retrieval problem and synonyms are the entire game.

**Write the negative space too.** The failure that costs most is not a skill that fails to fire, it is a skill that fires on adjacent requests and derails them. `when_to_use` is where you put trigger phrases and example requests, and it counts toward the same 1,536-character cap, so it competes with the description; spend the budget where the ambiguity is.

### The body, and degrees of freedom

Keep `SKILL.md` under **500 lines**; split beyond that. The single most useful authoring principle from the official guidance is that the context window is a public good and **Claude is already very smart**: add only context Claude does not already have, and challenge every paragraph with "does this justify its token cost?" A 50-token version that says "use `pdfplumber`, here is the four-line snippet" beats a 150-token version that explains what a PDF is.

Then match specificity to fragility:

| Freedom | Form | Use when |
|---|---|---|
| **High** | prose steps | multiple approaches valid, decisions are contextual, heuristics guide it (e.g. "analyze structure, check edge cases, suggest readability improvements") |
| **Medium** | pseudocode or a parameterized script | a preferred pattern exists, some variation acceptable |
| **Low** | "run exactly this script" with few or no parameters | fragile and error-prone, consistency critical, a specific sequence required |

Getting this wrong in the low-freedom direction produces a skill that is 400 lines of prose describing a migration procedure that the model performs 90% correctly, differently each time. Getting it wrong in the high-freedom direction produces a script that cannot handle the variation the task actually has, and the model works around it.

Progressive disclosure is the structural pattern: `SKILL.md` is a table of contents that points to `reference.md`, `examples.md`, and `scripts/`, all read on demand by ordinary file tools. Avoid deep nesting; one hop from `SKILL.md` to a reference file is reliable, three is not. For long reference files, put a table of contents at the top so the model can decide whether to read further.

### Frontmatter that actually changes behaviour

```yaml
---
name: shipping-migrations                     # gerund form; dir name sets the command
description: Runs a database migration through the team's safety checklist, including
  a tested downgrade and a shadow-read verification. Use when the user asks to ship,
  apply, or roll out a migration, or mentions alembic upgrade.
when_to_use: Trigger phrases include "ship the migration", "apply the schema change",
  "roll out the new column". Do NOT use for writing a migration from scratch.
disable-model-invocation: true                # side effects: only I invoke this
allowed-tools: Bash(alembic *) Bash(${CLAUDE_SKILL_DIR}/scripts/shadow_read.sh *)
paths: ["alembic/**", "src/models/**"]        # auto-load only when relevant files touched
model: opus                                    # this turn only, not saved to settings
effort: high
---
```

The fields that matter most in practice, and why:

- **`disable-model-invocation: true`.** The skill leaves the listing entirely (zero context cost) and only you can invoke it. This is the correct default for anything with side effects: commit, deploy, send a message, run a migration. The docs put it plainly: you do not want Claude deciding to deploy because your code looks ready. As of v2.1.196 it also prevents the skill running when a scheduled task fires with it as the prompt.
- **`user-invocable: false`.** The inverse: only the model can invoke it. For background knowledge that is not a meaningful user action, like a `legacy-system-context` skill explaining how an old subsystem works.
- **`allowed-tools`.** Pre-approves tools **for the turn that invokes the skill only**. The grant clears on your next message even though the skill content stays in context. It does *not* restrict anything; every other tool remains callable under your normal permission settings. `${CLAUDE_SKILL_DIR}` is substituted in both the body and the `allowed-tools` Bash rules, which is how a skill runs its own bundled script without prompting regardless of where it is installed.
- **`disallowed-tools`.** Removes tools from the pool while the skill is active. The real use is autonomous loops: strip `AskUserQuestion` from a background skill so it cannot block waiting for input.
- **`paths`.** Limits *automatic* activation to sessions touching matching files. This is the cheapest fix for a skill that fires too often.
- **`context: fork`** plus **`agent:`** and **`background:`** run the skill in a forked subagent, in the background by default.
- **`hooks`.** Hooks scoped to the skill's lifecycle, which is how you get an actual constraint out of a skill rather than a suggestion.

**A security note worth saying unprompted:** `allowed-tools` in a project's `.claude/skills/` takes effect after you accept the workspace trust dialog, and a checked-in skill can grant itself broad tool access. Reviewing project skills before trusting a repository is a real supply-chain step, not paranoia.

### Dynamic context injection

`` !`command` `` in the body is executed and replaced with its output **before the model sees the skill**. This is the difference between a skill that asks the model to go find the current state and a skill that arrives with the current state inlined:

```yaml
---
description: Reviews the working tree for risky changes before a commit. Use when the
  user asks to review their diff, wants a commit message, or asks what changed.
---

## Current changes
!`git diff HEAD --stat`

## Full diff
!`git diff HEAD`

## Instructions
Flag: swallowed exceptions, `# type: ignore`, new `Any`, missing downgrade in a
migration, hardcoded values, and any test that would pass if the feature were absent.
Say nothing about style; the formatter owns that.
```

Two failure modes. The output is inlined verbatim with no truncation, so `!`git diff HEAD`` on a 4,000-line diff is a 60,000-token skill invocation, and you have reinvented the compaction-thrashing bug on purpose. Bound it (`--stat`, `| head -200`, a path filter). And it runs every invocation, so a slow command is a slow skill.

### Testing whether a skill fires

This is the part almost nobody does, and the whole reason skills silently fail. **Seeing a skill trigger tells you the model found it, not that it did what you intended.** Measure two things separately.

**1. Trigger accuracy.** Write 10 should-trigger prompts in the words real users use, and 10 should-not-trigger prompts drawn from *adjacent* requests, which is where the real false positives live. Run each in a **fresh session** and record whether the skill loaded. Fresh matters because leftover context from authoring the skill masks gaps in the written instructions: you know what you meant, and your session does too.

```
                 fired    didn't fire
should-trigger     TP         FN      ← FN: description missing user vocabulary
should-not         FP         TN      ← FP: description too broad / no `paths:`
```

An honest target for a well-scoped skill is 9-10 of 10 should-trigger and 0-1 of 10 should-not. If you are at 6/10 on should-trigger, the fix is in the description, not the body.

**2. Output quality against baseline.** Run the same realistic prompts with the skill available and again with it disabled via `skillOverrides` (`"off"` hides it from both the model and the `/` menu). Compare results. Without the without-skill arm you cannot distinguish "the skill works" from "the model would have done that anyway," which is the same methodological hole the ETH study exposed in context files.

The `skill-creator` plugin automates this loop (`/plugin install skill-creator@claude-plugins-official`, then `/reload-plugins`): test cases with expected behaviour in `evals/evals.json` inside the skill directory, one **subagent per test case** so each run starts clean, token count and duration recorded, assertions graded to `grading.json` with evidence, a `benchmark.json` aggregating pass rate, time, and tokens for with-skill versus without, blind A/B between two versions, description tuning that generates should-trigger and should-not-trigger prompts and proposes description edits, and an HTML review viewer whose qualitative notes feed the next iteration.

One more thing to check, because it is invisible: run `/doctor` for an estimate of the listing's context cost and its biggest contributors, and `/context` for the post-budget listing size. If the budget is overflowing, some skill's description is already truncated and you will never see an error, only a skill that stopped firing.

### Versioning

Skills are markdown in your repo, so version control is git, and the practices that matter are the ones that keep behaviour honest across a change:

- **Commit the evals next to the skill.** `evals/evals.json` in the skill directory makes "did this edit help" answerable, and the blind A/B mode exists precisely because edits that feel like improvements often are not.
- **Treat a description change as a behaviour change.** Body edits change what happens after invocation; description edits change *whether* invocation happens, which is a much larger blast radius. Re-run trigger accuracy on every description change.
- **Live reload is real but partial.** Claude Code watches skill directories and picks up added, edited, or removed `SKILL.md` files within the session; creating a top-level skills directory that did not exist at session start needs a restart. For a skill folder that is also a plugin, changes to `hooks/`, `.mcp.json`, `agents/`, and `output-styles/` need `/reload-plugins`.
- **Know the override order:** enterprise > personal > project, and any of them overrides a bundled skill of the same name, so a project `code-review` skill replaces the bundled `/code-review`. Plugin skills are namespaced `plugin:skill` and cannot collide. Nested skills in a monorepo appear as `apps/web:deploy` when the name clashes, and invoking the unqualified name loads the root skill plus an instruction to also invoke variants whose directory holds the files being worked on.
- **There is no version field, and that is a real gap.** No `version:` in frontmatter, no dependency declaration, no deprecation mechanism. Distribution and versioning is what plugins are for; for a single-repo skill, git tags and a changelog inside the skill directory are what you have.

### When a skill is the wrong abstraction

This is where the seniority signal lives. Six alternatives, with the discriminating question:

| Reach for | When | Discriminating question |
|---|---|---|
| **A plain prompt** | one-off, or you type it twice a year | Will I use this enough to maintain it? A skill nobody invokes still costs listing budget and still rots |
| **A `CLAUDE.md` line** | it is a *fact* that always applies | Is it conditional? If it applies unconditionally, a skill adds a trigger gamble for nothing |
| **A `.claude/rules/` file with `paths:`** | it applies to an area, always, when that area is touched | Do I want this to fire *reliably* when a file matches, rather than when the model decides? Rules fire on the read; skills fire on the model's judgment |
| **A script or a tool/MCP server** | the operation is deterministic and fragile | Would I be upset if it were done slightly differently? Then it should be code the model calls, not prose the model interprets |
| **A hook** | it must run at a lifecycle point, every time | Is "usually" acceptable? If not, a skill is the wrong layer; a `PreToolUse` hook fires regardless of what the model decides |
| **A subagent** | the work needs context isolation or a different tool scope | Would the work flood my main context, or does it need tools I do not want in my main session? |

Stated as a rule: **skills are for procedures whose application requires judgment. Anything that should happen unconditionally is a rule or a hook; anything that must happen identically is code.**

The most common category error is the deterministic skill: a 300-line `SKILL.md` describing a release procedure in prose, executed slightly differently each time, with a failure rate nobody measures. That is a shell script with a 40-line skill wrapper that says "run `scripts/release.sh` and interpret the output." The second most common is the always-on skill, which is a `CLAUDE.md` rule paying a trigger gamble for no benefit.

---

## Build it from scratch

`(lab pending)` builds the eval harness before building the skill, because the harness is what makes the skill improvable.

**Part 1: the confusion matrix, by hand (30 min).** Take a skill you already have. Write 10 should-trigger prompts in real user vocabulary and 10 should-not-trigger prompts from adjacent tasks. Run all 20 in fresh sessions (`claude -p "<prompt>"` in a scratch worktree), and record whether the skill loaded. Most people discover 5-7 of 10 on should-trigger and are shocked, because in their own sessions it always fires, and in their own sessions they were priming it.

**Part 2: fix it in the description only (30 min).** Do not touch the body. Add the user vocabulary you missed, put the key use case first, move the negative cases into `when_to_use`, and add `paths:` if the false positives are location-dependent. Re-run the 20. Target 9+/10 and 0-1/10. The point of the constraint is to prove where trigger quality actually lives.

**Part 3: the baseline arm (30 min).** For 5 realistic tasks, run with the skill and with it disabled (`skillOverrides: {"<name>": "off"}`), and grade the outputs against written assertions. Record tokens and wall time for both. You are looking for a pass-rate improvement that justifies the token and time overhead, and you will sometimes find there is none, which is the most valuable outcome available.

**Part 4: automate it (30 min).** Install `skill-creator`, port your cases into `evals/evals.json`, and run the benchmark and description-tuning modes. Compare its proposed description against yours. Then use blind A/B to check whether your Part 2 edit was actually an improvement or just a change you liked.

**Part 5: the wrong-abstraction exercise (30 min).** Take three skills in the lab repo, each deliberately misclassified: one that should be a `CLAUDE.md` line (it always applies), one that should be a script plus a thin wrapper (it is deterministic and fragile), one that should be a hook (it must run on every edit). Convert each, and measure the reliability change. The hook conversion goes from ~85% compliance to 100% by construction, and that delta is the whole argument of the track.

---

## How it's done in production

The shape that holds up at team scale:

```
.claude/skills/
├── shipping-migrations/          # disable-model-invocation: true (side effects)
│   ├── SKILL.md                  # 60 lines: checklist + "run scripts/verify.sh"
│   ├── scripts/verify.sh         # the deterministic part
│   └── evals/evals.json          # committed. this is what makes edits safe.
├── triaging-incidents/           # user-invocable + model-invocable
│   ├── SKILL.md
│   ├── reference.md              # runbook index, read on demand
│   └── evals/evals.json
└── legacy-billing-context/       # user-invocable: false (background knowledge)
    └── SKILL.md
```

Distribution is by scope: project skills committed to `.claude/skills/`, a plugin with a `skills/` directory for cross-repo sharing, managed settings for organization-wide deployment. Bundled skills (`/doctor`, `/code-review`, `/batch`, `/debug`, `/loop`, `/claude-api`, `/run`, `/verify`, `/run-skill-generator`) are prompt-based rather than fixed logic, and as of v2.1.215 `/verify` and `/code-review` run only when *you* invoke them, so the longer-running checks spend time and tokens on your schedule. `disableBundledSkills` turns the rest off, `/doctor` excepted.

**Failure-mode table**

| Symptom | Cause | Fix |
|---|---|---|
| Skill never fires; `/name` works fine | Description missing the words users actually say, or malformed YAML (body loads with **empty metadata**, so `/name` works and matching has nothing to match) | Add user vocabulary and explicit triggers; run with `--debug` to see the parse error |
| Skill fired reliably for weeks, then stopped | The listing budget overflowed as skills were added, and descriptions are dropped **least-invoked first** | `/doctor` for listing cost; raise `skillListingBudgetFraction`; set low-priority skills to `"name-only"` in `skillOverrides`; trim descriptions to the 1,536-char cap |
| Skill fires on unrelated requests and derails them | Description too broad, no negative space in `when_to_use`, no `paths:` | Narrow it; add explicit non-triggers; add `paths:`; escalate to `disable-model-invocation: true` if it has side effects |
| Model deployed / committed / messaged on its own | Side-effecting skill left model-invocable | `disable-model-invocation: true`. Non-negotiable for anything irreversible |
| Skill invoked, then ignored a few turns later | Content is still present; the model is choosing other tools. Skill content is a message, not a constraint | Strengthen description and instructions; for anything that must happen, use hooks |
| Skill stops mattering after a compaction | Only the most recent invocation of each skill is re-attached, first 5,000 tokens each, sharing a 25,000-token budget filled newest-first, so older skills drop entirely | Re-invoke it; keep `SKILL.md` well under 5,000 tokens so nothing is truncated |
| Same skill's instructions appear three times in context | Pre-v2.1.202 behaviour, or the rendered content genuinely differs each time (changed arguments, `!`cmd`` output) | Upgrade; make dynamic injection output stable and bounded |
| One skill invocation consumed 60,000 tokens | `` !`git diff HEAD` `` inlines verbatim with no truncation | Bound the command: `--stat`, `| head -200`, path filters |
| Bundled `/code-review` behaves oddly | A project skill named `code-review` overrides the bundled one (enterprise > personal > project > bundled) | Rename yours, or accept the override deliberately |
| `allowed-tools` rule never matches; still prompts | `${CLAUDE_SKILL_DIR}` substitution in `allowed-tools` requires v2.1.129+; on older versions the rule stays a literal string | Upgrade, or use an absolute path |
| Skill works for you, fails for a teammate | Untrusted project directory (workspace trust gates `allowed-tools` and project settings), or a personal skill of the same name shadowing the project one | Check trust dialog; check override precedence |

---

## Tradeoffs & when NOT to use it

- **Do not write a skill you will invoke fewer than a handful of times.** It costs listing budget forever, competes with skills that matter, and rots. The honest test is whether you have typed the same instructions three times. If not, type them a fourth.
- **Do not use a skill where a hook belongs.** A skill's compliance is probabilistic even after it is loaded: the docs are explicit that a skill which seems to stop influencing behaviour is usually still present and the model is simply choosing other approaches. If the requirement is "this must happen before every commit," a `PreToolUse` hook with exit 2 fires regardless of the model's judgment and a skill does not.
- **Do not use a skill where a script belongs.** Prose describing an eight-step fragile procedure will be executed 90% correctly, differently each time, with a failure rate you are not measuring. Write the script, then write a 30-line skill that says when to run it and how to read its output. Low freedom for fragile operations is the official guidance and it is correct.
- **Do not use a skill for something that always applies.** That is a `CLAUDE.md` fact or a path-scoped rule. Wrapping an unconditional rule in a skill converts a certainty into a probability in exchange for nothing.
- **Do not let skills accumulate unmeasured.** The overflow behaviour makes this actively dangerous rather than merely untidy: descriptions are dropped from the least-invoked skills first, so a growing collection silently disables its own long tail. A repo with 40 skills and no eval harness has a large number of skills whose firing status nobody knows.
- **Do not put secrets or unbounded commands in dynamic injection.** `` !`cmd` `` runs on every invocation with the output inlined verbatim, and the rendered content persists in the conversation for the rest of the session.
- **Be wary of skills in repositories you do not control.** A checked-in project skill can grant itself broad tool access via `allowed-tools` once you accept the workspace trust dialog. Read project skills before trusting a repo, and use `skillOverrides` to turn off ones you did not write rather than editing their files.
- **The counter-argument to state:** a real camp argues skills are a worse version of tools, since a tool has a schema, deterministic behaviour, testability, and no trigger gamble, while a skill is a prompt fragment with a marketing name. They are right for anything mechanical. They are wrong about the case skills exist for: procedures where *the judgment about how to apply them* is the valuable part, and where progressive disclosure means 3,000 tokens of reference material costs nothing until the one session that needs it. Both mechanisms should be in your repo, and confusing them is the actual mistake.

---

## Interview questions

### Q1 — What is the highest-leverage line in a skill and why?
**Testing:** whether you know how invocation works.
**Answer:** The `description`. It is the only part of the skill in context before invocation, and it is what the model matches your prompt against, so it determines *whether* the skill is ever used. The body determines quality after that, but a perfect body with a vague description is a file nobody reads. The constraints make it tighter still: description plus `when_to_use` is truncated at 1,536 characters in the Claude Code listing, the whole listing shares a budget of 1% of the context window, and when that overflows descriptions are dropped starting with the least-invoked skills. So it is a retrieval problem under a hard budget. Write it in third person because it is injected into the system prompt, put the key use case first because the tail gets truncated, and include the words real users say rather than the words you say.
**Follow-up trap:** *"How do you know your description is good?"* Measure it, do not read it. Ten should-trigger prompts in real user vocabulary and ten should-not-trigger prompts drawn from adjacent requests, each run in a **fresh session**, scored as a confusion matrix. Fresh sessions are load-bearing: in your own authoring session the skill always fires because your context has already primed it, which is exactly how people ship skills that fire for them and nobody else. `skill-creator`'s description-tuning mode automates this by generating both prompt sets, measuring hit rate, and proposing edits when the skill activates on the wrong requests.

### Q2 — Skill, rule, hook, or tool? Give me the decision procedure.
**Testing:** the abstraction judgment, which is the main senior signal here.
**Answer:** Two questions in order. First, must it happen? If the answer is "every time, no exceptions," it is a hook, because hooks fire at lifecycle events regardless of what the model decides. If "when this area is touched, reliably," it is a `.claude/rules/` file with `paths:`, which loads on the read rather than on the model's judgment. If "always, everywhere, as a fact," it is a `CLAUDE.md` line. Second question, if it is genuinely judgment-dependent: must it happen *identically*? If yes, it is a script or an MCP tool the model calls, because prose is interpreted and code is executed. Only what survives both questions, a procedure whose application requires judgment, is a skill.
**Follow-up trap:** *"Where do most people get this wrong?"* Two errors, both predictable. The deterministic skill: 300 lines of prose describing a fragile release procedure, executed 90% correctly and differently each time, with no measured failure rate. That is a shell script plus a 30-line skill that says when to run it and how to read the output, which is what the official guidance means by low freedom for fragile operations. And the always-on skill: a rule that applies unconditionally, wrapped in a skill, which converts a certainty into a trigger gamble in exchange for nothing. Both errors have the same root cause, which is treating "skill" as the default container for anything longer than a sentence.

### Q3 — Your team has 40 skills and half of them don't seem to fire. Diagnose.
**Testing:** whether you know the listing budget behaviour, which is invisible and silent.
**Answer:** Most likely the listing budget overflowed. The listing always contains every skill *name*, but descriptions are shortened to fit a budget of 1% of the model's context window, and when it overflows Claude Code **drops descriptions starting with the skills invoked least**, so the skills you use most keep their full text and the long tail goes dark with no error message. That produces exactly this symptom: it used to work, we added skills, half of them stopped. Diagnosis: `/doctor` for an estimate of the listing's cost and its biggest contributors, `/context` for the post-budget size (which is what the model actually receives), and `--debug` for the overflow warning in the log. Fixes in order: trim descriptions toward the 1,536-character cap with the key use case first, set low-priority skills to `"name-only"` in `skillOverrides`, set side-effecting ones to `disable-model-invocation: true` so they leave the listing entirely, raise `skillListingBudgetFraction` to 2% if it is genuinely warranted, and delete the ones nobody invokes.
**Follow-up trap:** *"Which do you do first?"* Delete. A repo with 40 skills has maybe 12 that earn their place, and every dead skill is consuming budget that a live one needs. I would rank by invocation count, which the budget mechanism already implicitly does, and cut everything with zero invocations in 90 days. Then trim. Raising the budget is last because it treats the symptom: at 2% of the window the listing is a real recurring tax on every request in every session, and the reason the budget exists is that a bloated listing degrades selection quality even when it fits.

### Q4 — How do you test a skill?
**Testing:** whether "it worked when I tried it" is your standard.
**Answer:** Two separate measurements, because they fail independently. Trigger accuracy: 10 should-trigger and 10 should-not-trigger prompts, fresh session each, scored as a confusion matrix. Output quality: the same realistic prompts run with the skill and with it disabled via `skillOverrides: "off"`, graded against written assertions, recording tokens and wall time so the pass-rate improvement can be weighed against the overhead. The second arm is the one people skip and it is the one that answers the real question, which is whether the model would have done that anyway. `skill-creator` runs both: cases in `evals/evals.json`, one subagent per case so each starts clean, graded assertions with evidence in `grading.json`, a `benchmark.json` comparing with-skill against without, blind A/B between versions, and description tuning.
**Follow-up trap:** *"Why does the session have to be fresh?"* Because leftover context from authoring the skill masks gaps in the written instructions. You spent twenty minutes discussing the procedure, so the model in your session has the procedure in context and would follow it with no skill at all. That is how a skill that works perfectly for its author fires for nobody else. It is the same methodological error as evaluating a context file without a no-file arm, and it produces the same overconfidence.

### Q5 — What's in the skill's context and when?
**Testing:** the loading contract, which drives every design decision.
**Answer:** At session start, only names and descriptions, subject to the 1%-of-window budget and the 1,536-character per-entry cap, with `disable-model-invocation: true` skills absent entirely. On invocation, the fully rendered `SKILL.md` enters the conversation as a single message and **stays for the rest of the session**, with `` !`cmd` `` blocks already executed and inlined and `$ARGUMENTS`/`$0`/`${CLAUDE_SKILL_DIR}` already substituted. Claude Code does not re-read the file on later turns, which is why standing instructions beat one-time steps in the body. Re-invoking with identical rendered content adds a short "already loaded" note rather than a second copy; different content (changed arguments, new dynamic output) appends the full content again. Supporting files are read on demand by ordinary file tools, so reference material is free until needed. And `allowed-tools` is the exception to persistence: the grant applies to the invoking turn only and clears on your next message.
**Follow-up trap:** *"What happens at compaction?"* The listing is not re-injected, so the model may stop knowing a skill exists unless it already used it. Invoked skills are re-attached: the most recent invocation of each, keeping the first 5,000 tokens each, sharing a combined 25,000-token budget filled from most-recently-invoked backwards, so in a session where you used eight skills the earliest ones are dropped entirely. Two design consequences: keep `SKILL.md` well under 5,000 tokens so nothing is silently truncated at the re-attachment boundary, and if a skill's guidance is genuinely load-bearing for the whole task, put the critical two lines in `CLAUDE.md`, which is re-read from disk and re-injected.

### Q6 — Design a `deploy` skill.
**Testing:** whether you reach for `disable-model-invocation` unprompted.
**Answer:** First frontmatter line is `disable-model-invocation: true`, because I do not want the model deciding to deploy when the code looks ready, and the docs say exactly that. That also removes it from the listing, so it costs zero context until I type `/deploy`. Then low freedom, because deployment is fragile and consistency is critical: the body does not describe the steps in prose, it says "run `${CLAUDE_SKILL_DIR}/scripts/deploy.sh <env>`, then interpret the output against this checklist," with `allowed-tools: Bash(${CLAUDE_SKILL_DIR}/scripts/deploy.sh *)` so the exact command runs without prompting and nothing else is pre-approved. The judgment part, which is the only reason a skill exists here rather than a bare script, is reading the output: what a partial rollout looks like, when to roll back, which metrics to watch and for how long.
**Follow-up trap:** *"Why not just a script in `package.json`?"* Because the script is only half the operation. The half that goes wrong is interpretation: canary metrics that are ambiguous, a migration that applied on two of three shards, a health check that passes while p99 doubles. That is judgment, and it is what a skill is for. But note the split: the *actions* are in the script where they are deterministic and testable, and only the *interpretation* is in the skill where it is probabilistic. Putting the deploy steps themselves in prose would be the classic category error, and I would expect a slightly different deploy every time.

### Q7 — A skill fires on requests it shouldn't and derails them. Fix it.
**Testing:** whether you know the false-positive levers.
**Answer:** Four levers, cheapest first. Narrow the description: cut the generic capability language and keep the specific triggers, because vague descriptions overlap and the model picks wrong. Add negative space in `when_to_use`, which takes explicit trigger phrases and example requests: "Do NOT use for writing a migration from scratch." Add `paths:` so automatic activation only happens in sessions touching matching files, which kills location-dependent false positives outright. And if it has side effects, `disable-model-invocation: true`, which removes the model's ability to choose it at all. Then re-run the should-not-trigger set to confirm, because a narrowing edit frequently breaks the should-trigger side and you will not notice without both arms.
**Follow-up trap:** *"What if two of your skills legitimately overlap?"* Then the decomposition is wrong, and I would merge them or split them along a different axis, because overlapping descriptions guarantee the model loads the wrong one some fraction of the time and no amount of description tuning fixes genuine ambiguity. If they must coexist, differentiate on the trigger vocabulary rather than the capability description, since that is what matching actually uses, and consider making one `user-invocable: false` (model-only background knowledge) and the other `disable-model-invocation: true` (explicit command), which removes the competition mechanically rather than probabilistically.

### Q8 — How do you version skills?
**Testing:** whether you notice a genuine gap in the tooling.
**Answer:** Git, because they are markdown in the repo, plus three practices. Commit `evals/evals.json` next to the skill so "did this edit help" is answerable, and use the blind A/B mode before committing a description change, because edits that feel like improvements often are not. Treat a description edit as a *behaviour* change with a much larger blast radius than a body edit, since it changes whether the skill fires at all, and re-run trigger accuracy every time. And know the resolution order for distribution: enterprise > personal > project, with any of those overriding a bundled skill of the same name, plugin skills namespaced `plugin:skill` so they cannot collide, and nested monorepo skills surfacing as `apps/web:deploy` on a name clash.
**Follow-up trap:** *"So what's missing?"* There is no `version` field, no dependency declaration, and no deprecation mechanism in the format. That matters as soon as skills are shared: you cannot express "this skill requires Claude Code v2.1.203+" or "this replaces `old-deploy`," and a personal skill silently shadows a project skill of the same name with no warning. Plugins are the answer for distribution and they carry their own versioning, but for a single repo the honest answer is a changelog inside the skill directory and a git tag, which is weaker than what we expect from any other shared artifact.

### Q9 — Talk me through dynamic context injection and what breaks.
**Testing:** whether you know the sharpest edge in the format.
**Answer:** `` !`command` `` in the body is executed and its output substituted before the model sees the skill, so the instructions arrive with the current state already inlined rather than asking the model to go find it. That is genuinely powerful: a review skill that inlines `git diff HEAD --stat` starts grounded in the real working tree instead of guessing from open files. What breaks: the output is inlined **verbatim with no truncation**, so an unbounded command on a large diff is a 60,000-token skill invocation, which is the compaction-thrashing bug reintroduced deliberately. It also runs on every invocation, so a slow command is a slow skill, and the rendered content persists for the rest of the session, so anything sensitive in the output stays in context.
**Follow-up trap:** *"How do you bound it safely?"* At the command, not after: `--stat` first and the full diff only for a filtered path set, `| head -200`, `jq -r` to project only the fields you need, `--name-only` when the file list is what matters. And I would pair it with a `scripts/` helper in the skill directory invoked via `${CLAUDE_SKILL_DIR}` so the bounding logic is versioned code rather than a shell one-liner in markdown, plus an `allowed-tools` rule matching that exact path so it runs without a prompt. The general principle from the context-window module applies: truncation belongs upstream of context, because once it is in the buffer you re-send it every turn.

### Q10 — Is there a security story around skills?
**Testing:** whether you have thought about the supply chain, which most candidates have not.
**Answer:** Yes, and it is underrated. A skill checked into a project's `.claude/skills/` can grant itself broad tool access via `allowed-tools`, taking effect once you accept the workspace trust dialog for that folder, which is the same gate as permission rules in `.claude/settings.json`. So cloning a repo and trusting it is a decision about executable capability, not just files. Add `.claude-plugin/plugin.json` to a skill folder and it loads as a plugin that can bundle agents, hooks, and MCP servers. And dynamic injection means a skill body can run shell commands the moment it is invoked. Practically: read project skills before trusting a repository, use `skillOverrides` to turn off skills you did not write rather than editing files you do not own, and put `permissions.deny` in managed settings for anything organizationally forbidden, since that is enforced by the client regardless.
**Follow-up trap:** *"How would you gate this for 200 engineers?"* Managed settings, because they are the only layer users cannot override: `permissions.deny` for forbidden tools and hosts, `Skill(name)` permission rules to allow or deny specific skills, `disableBundledSkills` if the org wants a curated set, and a managed policy `CLAUDE.md` for the guidance half. Then distribute approved skills as a plugin from an internal marketplace rather than letting each repo carry its own, so there is one review surface. I would also treat the workspace trust prompt as a security event worth training people on, because "accept trust to get syntax highlighting" is how this goes wrong.

### Q11 — Are skills a good abstraction, or a prompt fragment with a marketing name?
**Testing:** whether you can argue against your own tooling, which is the closing-question signal.
**Answer:** Partly the latter, and I would concede the specific criticism before defending the general case. A skill has no schema, no version, no type checking, and probabilistic invocation; a tool has all four. For anything mechanical, the critics are simply right, and the deterministic-skill anti-pattern is the most common failure in real repos. What the abstraction genuinely buys is two things a tool cannot. Progressive disclosure: 3,000 tokens of reference material and a bundled script cost nothing until the one session that needs them, whereas a tool's schema is a permanent context cost, which is exactly why MCP schemas are deferred by default. And versionability as plain markdown in the repo alongside the code it describes, reviewed in the same PR, which matters because procedures drift with the code. The honest summary: skills are the right container for judgment-dependent procedures and the wrong container for everything else, and the industry is currently overusing them because they are the easiest thing to write.
**Follow-up trap:** *"Then what would you change about the format?"* Three things, in order of value. A `version` field with a compatibility declaration, because shared skills without versioning is a dependency system with no dependency metadata. A first-class notion of "this skill supersedes that one," so deprecation is expressible rather than a naming convention. And mandatory evals for skills distributed beyond a single repo, the way `skill-creator` already structures them, because the current default is that nobody knows whether a shared skill fires. None of those are hard; they are all downstream of skills having been designed as a convenience and then becoming an interface.

---

## Red flags that fail you

- Not knowing the description is what determines invocation.
- Writing descriptions in first or second person.
- Never having measured whether a skill fires, or testing only in the session where you wrote it.
- No should-not-trigger set; only testing the happy path.
- Leaving a side-effecting skill model-invocable.
- Describing a fragile deterministic procedure in prose instead of shelling out to a script.
- Wrapping an unconditional rule in a skill.
- Not knowing the listing budget exists, or that overflow silently drops least-invoked descriptions.
- Unbounded `` !`cmd` `` in the body.
- Believing a loaded skill is a constraint on behaviour.
- No plan for what happens to skills after a compaction.
- Ignoring that a checked-in skill can grant itself tool access.

## Cheat card

```
THE DESCRIPTION IS THE PRODUCT
  the ONLY part in context pre-invocation. it IS the selection mechanism.
  THIRD PERSON (injected into the system prompt). key use case FIRST.
  two clauses: what it does + WHEN to use it. include USER vocabulary/synonyms.
  caps: description+when_to_use truncated at 1,536 chars (skillListingMaxDescChars)
        platform `description` field max 1,024 chars
        `name` ≤64 chars, [a-z0-9-], no XML, cannot contain "anthropic"/"claude"
  LISTING BUDGET = 1% of context window (skillListingBudgetFraction /
        SLASH_COMMAND_TOOL_CHAR_BUDGET). names always listed.
  OVERFLOW → descriptions DROPPED, LEAST-INVOKED FIRST, silently. /doctor to see it.
  malformed YAML → body loads with EMPTY metadata: /name works, matching never fires

BODY   keep SKILL.md <500 lines. context window is a public good.
  "Claude is already very smart" — add only what it does not have
  DEGREES OF FREEDOM: high=prose (many valid approaches) · medium=parameterized
    script · LOW=exact script (fragile, consistency critical, fixed sequence)
  progressive disclosure: SKILL.md = ToC → reference.md/examples.md/scripts/
    (read on demand, free). avoid deep nesting. ToC at top of long refs.

FRONTMATTER THAT MATTERS
  disable-model-invocation:true → OUT OF LISTING, zero cost, you-only. USE FOR
    SIDE EFFECTS (commit/deploy/message/migrate). also blocks scheduled-task firing.
  user-invocable:false          → model-only background knowledge
  allowed-tools                 → pre-approve THIS TURN ONLY, clears next message;
    does NOT restrict. ${CLAUDE_SKILL_DIR} substituted in body AND in Bash rules.
  disallowed-tools              → remove from pool while active (e.g. AskUserQuestion
    for a background loop)
  paths: [...]                  → limit AUTOMATIC activation to matching files
  context: fork + agent + background → run in a forked subagent
  model / effort                → this turn only, not saved
  hooks                         → skill-scoped lifecycle hooks (the real constraint)

LIFECYCLE
  invoked → FULL rendered SKILL.md enters as ONE message and STAYS all session
  file is NOT re-read on later turns → write STANDING instructions, not one-time steps
  identical re-invoke → "already loaded" note (v2.1.202+), not a second copy
  COMPACTION: listing NOT re-injected. invoked skills re-attached: most recent
    invocation of each, first 5,000 tok each, 25,000-tok combined budget,
    newest-first → older skills DROP ENTIRELY
  subagent `skills:` preload → FULL content injected at startup (different contract)

TESTING = TWO MEASUREMENTS
  1 TRIGGER: 10 should-trigger (real user words) + 10 should-NOT (adjacent tasks),
    FRESH SESSION each. confusion matrix. target 9-10/10 and 0-1/10.
    fresh matters: your authoring session already primed it.
  2 OUTPUT: same prompts with skill vs skillOverrides:"off". grade assertions.
    without-arm is the one people skip and the one that answers the real question.
  skill-creator: evals/evals.json · subagent per case · grading.json · benchmark.json
    (pass rate/time/tokens, with vs without) · blind A/B between versions ·
    DESCRIPTION TUNING (generates both prompt sets, proposes edits) · HTML viewer

DYNAMIC INJECTION  !`cmd` executed and inlined BEFORE the model sees the skill
  VERBATIM, NO TRUNCATION → unbounded diff = 60k-token invocation
  runs every invocation → slow command = slow skill · output persists all session

WRONG ABSTRACTION — reach for instead:
  plain prompt   used <3 times
  CLAUDE.md line always applies, is a FACT
  rules + paths: always applies to an AREA (fires on the READ, not on judgment)
  script / MCP   deterministic + fragile ("would I mind if it were done differently?")
  HOOK           must happen EVERY TIME at a lifecycle point (exit 2 blocks)
  subagent       needs context isolation or a different tool scope
  RULE: skills are for procedures whose APPLICATION requires judgment.
        unconditional → rule/hook. must-be-identical → code.

PRECEDENCE  enterprise > personal > project > bundled
  plugin skills namespaced plugin:skill (no collisions)
  nested monorepo clash → apps/web:deploy; unqualified loads root + variant instruction
  live reload: SKILL.md text yes; new top-level dir needs restart;
    plugin hooks/.mcp.json/agents need /reload-plugins
  NO version field, NO dependency decl, NO deprecation. real gap.

SECURITY  a checked-in project skill can grant itself broad tool access via
  allowed-tools once you accept WORKSPACE TRUST. read project skills before trusting.
  skillOverrides to disable skills you did not write. permissions.deny + Skill(name)
  in MANAGED settings for org-level enforcement.
```

## Sources

- [Extend Claude with skills](https://code.claude.com/docs/en/skills) — the full frontmatter reference; the 1,536-character combined `description`+`when_to_use` cap and `skillListingMaxDescChars`; the 1%-of-window listing budget, `skillListingBudgetFraction`, `SLASH_COMMAND_TOOL_CHAR_BUDGET`, and least-invoked-first description dropping; skill content lifecycle and the post-compaction re-attachment rule (5,000 tokens each within a 25,000-token budget); `allowed-tools` clearing on the next message; `${CLAUDE_SKILL_DIR}` substitution; dynamic context injection; the `skillOverrides` states; precedence and nested monorepo naming; live change detection; and the "skill not triggering / triggers too often / descriptions cut short" troubleshooting sections; accessed 2026-07-26
- [Skill authoring best practices](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices) — "concise is key" and the context window as a public good; the degrees-of-freedom spectrum; third-person descriptions and why (injected into the system prompt); `name` ≤64 chars with reserved words, `description` ≤1,024 chars; gerund naming; progressive disclosure patterns; the under-500-line target; testing across models; accessed 2026-07-26
- [Evaluating skill output quality](https://agentskills.io/skill-creation/evaluating-skills) — the eval file format and iteration workflow on the Agent Skills standard site; accessed 2026-07-26
- [Improving skill-creator: test, measure, and refine agent skills](https://claude.com/blog/improving-skill-creator-test-measure-and-refine-agent-skills) — the benchmark and blind-comparison modes behind `benchmark.json` and version A/B; accessed 2026-07-26
- [Extend Claude Code](https://code.claude.com/docs/en/features-overview) — context cost by feature, and how Claude chooses skills from descriptions (vague or overlapping descriptions cause wrong or missed loads); accessed 2026-07-26
- [How Claude remembers your project](https://code.claude.com/docs/en/memory) — the rule-versus-skill boundary: rules load every session or on matching reads, skills load on invocation; and that a `CLAUDE.md` section which has become a procedure belongs in a skill; accessed 2026-07-26
- [Get started with hooks](https://code.claude.com/docs/en/hooks-guide) — exit-code semantics and lifecycle events, for the skill-versus-hook decision; accessed 2026-07-26
- [Create custom subagents](https://code.claude.com/docs/en/sub-agents) — preloaded skills inject full content at subagent startup, unlike the regular-session contract; accessed 2026-07-26
- [Agent Harnesses — Microsoft Learn](https://learn.microsoft.com/en-us/agent-framework/agents/harness) — the optional skills provider that "discovers and progressively loads Agent Skills from the file system," as independent convergence on the abstraction; page updated 2026-07-08, accessed 2026-07-26
- [Agent Skills](https://agentskills.io) — the open standard Claude Code skills follow, and the cross-tool baseline Claude Code extends; accessed 2026-07-26

## Changelog
- 2026-07-26 — created
