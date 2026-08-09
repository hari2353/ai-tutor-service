# The Claude Architect Model: Operating as the Architect, Not the Typist

> **Track:** T28 AI-Assisted Architecture · **Time:** 3h · **Prereqs:** `T07-harness-engineering`, `T21-architecture-principles` · **Updated:** 2026-07-26
> **Module id:** `T28-claude-architect` · **Tags:** sprint, architecture, critical
> **Lab:** none yet — see `labs/py/02-agent-loop/` for the pattern if you want to build one

## The 30-second version

Agentic coding did not remove the bottleneck, it moved it: writing code, tests, and refactors stopped being the constraint and verification, review, and security became the constraint. That means the Principal-level job is now specification, decomposition, delegation boundaries, and review discipline, with architectural judgment explicitly kept in-house. The three practices that carry the most weight are plan-mode-first (draft and approve a plan before any write tool is available), specs that are self-contained (naming the files and interfaces involved, stating what is out of scope, ending with an end-to-end verification step), and the recognition that **instructions are not enforcement**: a rule in CLAUDE.md is a recommendation, a rule in a hook, linter, or CI gate is a constraint. The honest failure modes are not model bugs and do not go away with a better model: assumption propagation that cements a wrong architecture five PRs deep, abstraction bloat, dead-code accumulation, sycophantic agreement, and comprehension debt, which is the one that actually ends careers because it is trivially easy to review code you can no longer write. The measured cost is visible in the delivery data: high-AI-adoption teams merged 98% more PRs while review time grew 91% and PR size grew 154%, and the 2026 figures are worse (median PR review time up 441%, 31% more PRs merging with no review at all).

## Why this gets asked

Because in 2026 this is a *scored* dimension of senior interviews rather than a soft topic. Miro lists "AI-First Proficiency" as a hiring criterion and expects Claude Code usage. TRM Labs states AI fluency is a baseline expectation. Toku calls AI-native development non-negotiable. BetterUp says you will have opportunities to showcase how you harness AI. OpenAI allows AI tools during coding rounds with screen sharing and narration, and the stated boundary is that you should not dump the whole problem in and paste the output back, because they are watching for reasoning and judgment. Exponent runs a combined coding-plus-design round where the candidate uses Claude Code throughout and the interviewer explicitly evaluates *how* it is used: prompting strategy, ability to verify and understand generated code, and whether the candidate lets the AI make architectural decisions. The interviewer's stated top pitfall is "not understanding what the AI is going to do, relying on AI to make decisions for you." Meanwhile new round types appeared specifically to probe this: code-review rounds, "evaluate this LLM-generated solution" rounds, and "AI delta" assessments where you tackle a real GitHub issue in 2-4 hours and are scored on what you add *beyond* what the AI produced. And the empirical result reported repeatedly on HN is that candidates who lean on AI in live interviews often perform *worse*, because follow-up questions expose that they cannot explain the subtle bug the model introduced. The interviewer has usually lived the organizational version of this: a quarter where throughput doubled, review queues exploded, and a plausible-looking architecture had to be unwound.

---

## Lineage: past → present → future

**What came before.** Two things, and both died of specific pain. The first was the autocomplete era, 2021 through mid-2024: Copilot as a faster typewriter, with the human still holding the whole design in their head and the tool filling in lines. That did not scale past small units, and the pain that killed it was measurable: METR's July 2025 randomized controlled trial (16 experienced open-source developers, 246 tasks on repositories they regularly contributed to) found early-2025 AI tools made them **19% slower**, while the developers predicted a 24% speedup and, *after experiencing the slowdown*, still estimated they had been 20% faster. That perception-reality gap is the single most important number in this topic, because it means self-report is not evidence and the whole field spent 2024 optimizing against a metric that did not exist. The second thing was the design-doc-heavy process built on the assumption that engineering bandwidth was the expensive resource. Anthropic's own Director of Engineering for Claude Code describes writing a good six-month roadmap and having it out of date by month three *because of* Claude Code. Waterfall and agile were both organizations shaped around the cost of typing code. When that cost collapsed, the processes did not fall over dramatically; they quietly stopped working and nobody removed them.

**Where it stands now.** The bottleneck moved, and this is the consensus statement to lead with: on Anthropic's own Claude Code team, "writing code, writing tests, and refactoring rarely slows us down anymore," and verification, code review, and security took their place. The productivity picture is genuinely mixed and you should present it that way. On the positive side, METR's continuation reports the early-2025 19% slowdown flipping to an estimated **+18% speedup by early 2026**, and an exploratory transcript analysis estimating a 1.5× to 13× time-savings factor on Claude Code-assisted tasks for 7 METR staff in January 2026, with substantial caveats attached by the authors themselves. On the negative side, the delivery data is clear about where the cost went: DORA 2025 found high-AI-adoption teams merged **98% more PRs** with review times up **91%** and PR size up **154%**; the 2026 numbers are worse, with median PR review time up **441%** and **31% more PRs merging with no review at all**; agentic PRs wait **5.3× longer** before a reviewer picks them up and run **2.6× larger**; median batch size roughly doubled between Q1 2025 and Q1 2026, growing about 2.5× faster from October onward as agent adoption hit mainstream. Atlassian's survey captured the paradox: 99% of AI-using developers reported saving 10+ hours per week, and most reported *no decrease in overall workload*. **The population is bimodal, not a smooth curve**: Armin Ronacher's 5,000-developer poll found 44% now write less than 10% of their code manually and another 44% still write over 90% manually. Stack Overflow found only 16% reporting "great" productivity improvement, with the top frustrations being "AI solutions that are almost right, but not quite" (66%) and "debugging AI code takes longer than writing it myself" (45%). And 30% of developers report little or no trust in AI-generated code. The **live disagreement** worth naming: Karpathy is bracing for a 2026 "slopacolypse" across GitHub, arXiv, and digital media generally, while Boris Cherny (Claude Code's creator, shipping 22 and 27 PRs a day of 100% Claude-written code) bets there will be none because models get better at writing less-sloppy code and at fixing existing issues, with fresh-context self-review as the near-term mitigation. Both can be true simultaneously; the question is which scales faster.

**Where it's heading.** **High confidence: enforcement layers become the primary artifact you author.** The pattern already documented in practice is three levels of control, and only the third is real: Level 1 instructions (CLAUDE.md explains the rule), Level 2 reminders (a skill reminds the agent to apply it), Level 3 enforcement (hooks, shell commands, CI checks, validators, workflow gates). Without Level 3 the rule remains a recommendation; with it, a constraint. Expect the senior deliverable to shift from "wrote the design doc" to "wrote the check that makes the design doc unfalsifiable." **Medium confidence: review capacity, not generation capacity, becomes the scaling unit of an engineering org.** The 441% review-time figure and the 31%-merged-unreviewed figure are the same fact stated twice, and the responses being tried (agent code review, fresh-context self-critique, PR-size limits, mandatory human review only for trust boundaries and legal risk) are all attempts to raise review throughput. Anthropic's version is explicit: Claude handles style, linting, bug-catching, and test-adding, and humans review where domain expertise matters, specifically legal risk tolerance, trust boundaries and security-sensitive code, and product sense. **Low confidence, speculative: role convergence.** Anthropic reports PMs coding, engineers taking on design and content, and hiring indexed on two profiles (creative builders with product sense, and engineers with deep systems expertise) while explicitly de-indexing raw throughput. That is one org, at one point on the curve, with unusual access. Treat it as a leading indicator, not a template, and be honest in an interview that you are describing a hypothesis.

---

## Mental model

The role shift, stated as a resource reallocation rather than a slogan:

```
  BEFORE                                    AFTER
  ────────────────────────────────          ─────────────────────────────────
  10%  understand the problem               40%  specify: problem, contract,
  15%  design                                    out-of-scope, verification
  55%  TYPE THE CODE                        10%  decompose into agent-sized units
  15%  review                               10%  delegate + supervise
   5%  verify                               35%  REVIEW + VERIFY + own the outcome

  bottleneck: engineering bandwidth         bottleneck: verification capacity
```

And the control hierarchy, which is the load-bearing idea of the whole module:

```
  LEVEL 1  INSTRUCTION    CLAUDE.md / AGENTS.md says "always use the repo's
                          Result type, never raise across the service boundary"
                          → a RECOMMENDATION. Survives until context pressure,
                            a competing objective, or a compaction.

  LEVEL 2  REMINDER       a skill / system-reminder re-states it at the moment
                          it matters
                          → higher compliance, still probabilistic.

  LEVEL 3  ENFORCEMENT    a PreToolUse hook rejects the edit; a lint rule fails;
                          a CI gate blocks the merge; a type signature makes the
                          wrong thing unrepresentable
                          → a CONSTRAINT. Effectiveness does not depend on the
                            agent's cooperation.
```

The rule you say out loud: **anything you would be upset to find violated belongs at Level 3.** If it is only in a markdown file, you have expressed a preference, not a policy. And there is a hard mechanical reason, not just a philosophical one: compaction reliably preserves the current task, recent errors, and file names, and reliably loses initial instructions, intermediate decisions, and style rules. A style rule that lives only in conversation history is gone by turn 60. A style rule in CLAUDE.md lives in the system prompt and survives; a style rule in a lint config cannot be lost at all.

---

## How it actually works

### The five-phase loop, and where the human is mandatory

```
RESEARCH → PLAN → EXECUTE → REVIEW → SHIP
   ↑         ↑                  ↑        ↑
   │         │                  │        └─ human owns: the outcome. Always.
   │         │                  └────────── human mandatory: trust boundaries,
   │         │                              security-sensitive code, legal risk,
   │         │                              product taste, architectural fit
   │         └───────────────────────────── human mandatory: APPROVE THE PLAN
   └─────────────────────────────────────── human sets scope + success criteria
```

**Plan mode first, and understand why it is a real control rather than a convention.** Plan mode is not "the model promises not to edit." In Claude Code the write tools are *physically unavailable* in plan mode, a hard read-only sandbox enforced at the tool level. That is the difference between Level 1 and Level 3 applied to the agent's own workflow, and it is the reason plan mode changes outcomes while "please don't edit anything yet" does not. Microsoft Agent Framework ships the same idea as an explicit mode provider: plan mode is interactive (the agent asks clarifying questions, drafts a todo list and plan, gets approval before significant work) and execute mode is autonomous (works through the todos independently, reporting progress). If you are describing your workflow in an interview and you say "I review the plan first," expect the follow-up "what stops it editing anyway," and the answer is tool-level unavailability, not trust.

**What makes a spec work.** The official guidance is specific and worth quoting close to verbatim, because it is unusually testable: the most useful specs are **self-contained**; they **name the files and interfaces involved**, **state what is out of scope**, and **end with an end-to-end verification step that proves the feature works**. Each of those three clauses maps to a failure it prevents:

| Spec clause | Failure it prevents | What the failure looks like |
|---|---|---|
| Names the files and interfaces | Assumption propagation | Agent invents a plausible module boundary, builds three PRs on it, and you notice when it collides with the real one |
| States what is out of scope | Abstraction bloat, scope creep | 1,000 lines where 100 would do; a config system nobody asked for; unrelated files touched |
| Ends with an end-to-end verification step | Fail-plausible completion | "I've implemented the feature" with a green unit test that mocks the thing that is broken |

A spec template that survives contact:

```markdown
# <Feature>: spec

## Problem
One paragraph. What is broken or missing, for whom, and how we know.

## Contract
- Entry point:      `src/api/routes/quota.py::enforce_quota`
- Interfaces:       `QuotaStore` (existing, do not change), `QuotaDecision` (new)
- Data touched:     `quota_ledger` table, read-write. Migration required: yes.
- Error semantics:  return `QuotaDecision.DENIED`; never raise across the handler
- Concurrency:      per-tenant serialization required; ledger updates must be
                    atomic under 200 rps

## Out of scope
- No changes to `BillingClient`.
- No new config keys.
- Do NOT introduce a caching layer. If you believe one is needed, stop and say so.
- No refactors of files you did not need to change.

## Constraints already enforced in CI (do not restate as prose, they are gates)
- `ruff`, `mypy --strict`, `pytest -q`, migration lint, `bandit`

## Verification (end-to-end, must actually run)
1. `pytest tests/integration/test_quota_enforcement.py` passes.
2. `scripts/loadtest_quota.sh 200` shows zero ledger drift after 10k requests.
3. `alembic upgrade head && alembic downgrade -1` round-trips cleanly.
4. Paste the actual command output. Do not summarize it.

## Open questions for the human (answer before executing)
- <the agent should fill this in during plan mode; an empty list is suspicious>
```

That last section is the highest-leverage line in the template and the least used. Karpathy's catalogue of what still breaks is precise: the models "make wrong assumptions on your behalf and run with them without checking. They don't manage confusion, don't seek clarifications, don't surface inconsistencies, don't present tradeoffs, don't push back when they should. They're still a little too sycophantic." An explicit "open questions" slot in the spec forces the surfacing that does not happen spontaneously. If the agent returns an empty list on a genuinely ambiguous task, that is signal about the task's framing, not reassurance.

### Writing a CLAUDE.md / AGENTS.md an agent actually uses

**Format context first.** AGENTS.md became the de facto cross-tool convention through 2025-2026, read natively by Codex, Cursor, Copilot, Gemini CLI, Aider, Windsurf, Zed and 20+ others, stewarded by the Linux Foundation's Agentic AI Foundation, and adopted in 60,000+ repositories. It is a convention, not an ISO/IETF standard. It exists because teams were maintaining `.cursorrules`, `CLAUDE.md`, and `.github/copilot-instructions.md` in parallel. Practical answer for a polyglot shop: AGENTS.md as the source of truth, CLAUDE.md as a thin pointer to it plus any Claude-specific additions.

**What belongs in it.** Write **operational policy, not human documentation.** Command-first, with exact invocations. Task-organized. Explicit, verifiable "done" criteria.

```markdown
# AGENTS.md

## Commands (exact, copy-pasteable)
- Install:      `uv sync --all-extras`
- Test (fast):  `pytest -q -x -m "not integration"`
- Test (full):  `pytest -q`
- Lint:         `ruff check . && ruff format --check .`
- Types:        `mypy --strict src/`
- Migrate:      `alembic upgrade head`
Run lint + types + fast tests before claiming any task is done. Paste output.

## Map (where to look, not what everything does)
- `src/api/`        HTTP layer. Thin. No business logic here.
- `src/domain/`     Business logic. Pure. No I/O, no framework imports.
- `src/adapters/`   I/O. One module per external system.
- `docs/adr/`       Architecture decisions. READ THESE before proposing a change
                    to a module boundary. If your plan contradicts an ADR, stop.

## Hard rules (also enforced in CI; listed here so you don't waste a cycle)
- `src/domain/` must not import from `src/adapters/` (enforced: import-linter)
- Public functions return `Result[T, DomainError]`; never raise across `src/api/`
- Every migration must have a tested `downgrade` (enforced: `scripts/migration_lint.py`)
- No new dependency without a note in `docs/adr/` (enforced: CI diff check)

## Behaviour
- Read a file before you modify it.
- Prefer three duplicate lines over a premature abstraction.
- Do not add comments to code you did not change.
- Do not add error handling that is not required by the contract.
- If a command fails, diagnose before retrying. Do not retry blind.
- Report honestly. Do not say you ran something you did not run.
- If you are more than ~60% unsure about a boundary, stop and ask.

## Done means
Lint clean, types clean, tests pass, the spec's verification steps executed with
output pasted, and a one-paragraph summary of anything you changed that the spec
did not ask for (ideally: nothing).
```

Three things to notice, because they are the difference between a file the agent uses and a file it skims:

1. **Hard rules are listed *and* enforced.** The prose exists to save a wasted cycle, not to create the constraint. That "Behaviour" block is close to what Claude Code encodes internally in its own system prompt (don't add unrequested features, don't over-abstract, don't comment unchanged code, don't add unnecessary error handling, read before modifying, diagnose before retrying, report honestly), and the lesson from that codebase is stated plainly by people who have read it: **don't trust model self-discipline, codify the behaviour.**
2. **It is a map, not a manual.** The instruction file should tell the agent where to look next, and deeper truth belongs in structured references (ADRs, runbooks, domain models, schemas). A giant manual competes with task context for attention and loses. Trellis exists specifically as a reaction to the bloated-CLAUDE.md pattern, loading only the standards, task PRDs, and session journals relevant to the current step.
3. **Uncertainty has a numeric-ish threshold and an instruction.** "If you are more than ~60% unsure, stop and ask" outperforms "be careful," because the latter is unactionable. Avoid prose paragraphs, ambiguous directives, and contradictory priorities without explicit ordering.

**What does not belong:** anything you would be upset to find violated but have not enforced; secrets; permission logic; long prose explanations of why the architecture is the way it is (that is an ADR, link to it); and duplicated content that will drift from the code.

### Decomposing work so an agent can succeed

An agent-sized unit of work has five properties. Check them before delegating, and if two or more fail, the decomposition is the problem, not the agent.

| Property | Test | If it fails |
|---|---|---|
| **Bounded blast radius** | Can you name the files it should touch? | Split until you can, or the agent will discover the boundary by trial |
| **A stated contract** | Are the interfaces and error semantics fixed in advance? | You are delegating the design, which is the one thing you should keep |
| **Machine-checkable success** | Is there a command whose exit code decides "done"? | You have no verification, so the completion claim is unfalsifiable |
| **Reversibility** | Is one `git revert` enough to undo it? | Add a gate. Non-reversible work needs approval, not autonomy |
| **Fits the context** | Can the relevant code and constraints fit in one window? | Externalize to files, or split. Do not rely on compaction to hold it |

**Work where an agent predictably cannot succeed**, and recognizing this is the senior signal:

- **Under-determined design decisions with long shadows.** Choosing a consistency model, a tenancy strategy, a service boundary, or a data-ownership split. These are decisions whose cost is borne over years by people who were not in the conversation, and the agent has no access to the political, organizational, and roadmap constraints that dominate the choice. The failure is not that it produces a bad answer; it is that it produces a *plausible* one confidently and you accept it.
- **Anything whose correctness depends on unwritten invariants.** "The agent doesn't know what it doesn't know, and its confidence scales inversely with context understanding." In mature codebases with complex invariants the calculus inverts relative to greenfield.
- **Thinly-represented APIs.** Confident hallucination is concentrated where training data is thin: your internal libraries, a recently-changed SDK, a niche database's exact semantics. Mitigation is injecting version-specific docs (Context7-style) rather than hoping.
- **Cross-cutting migrations with per-call-site judgment.** Mechanical migrations are ideal agent work. Migrations where 15% of call sites need a human decision are the worst case, because the agent will make the 15% look like the 85%.
- **Work where the test suite is the thing being fixed.** If tests are the oracle and the tests are wrong, an agent optimizing to green makes things worse with high confidence.

**Where the split works well:** greenfield and prototypes, mechanical refactors with a machine-checkable invariant, test backfilling against existing behaviour, bounded bug fixes with a reproducing test written first, migrations with uniform call sites, and anything with a tight objective function to loop against. Karpathy's framing of the actual leverage is right and worth internalizing: "LLMs are exceptionally good at looping until they meet specific goals." The shift is imperative to declarative, from "write a function that takes X and returns Y, use this library, handle these edge cases" to "here are the requirements, here are the tests that must pass, figure out how." Practitioners who succeed with this reportedly spend ~70% of their effort on problem definition and verification strategy and ~30% on execution, with the ratios inverted from traditional development. But the caveat is load-bearing: **this only works if your success criteria are actually correct, and garbage in / garbage out scales with capability.**

### Delegation boundaries and subagent use

Keep in-house, always: architectural decisions and their rationale (ADRs written by you), trust and security boundaries, data model ownership, error-semantics contracts, dependency additions, anything with legal or compliance exposure, and the final call on whether to ship. Delegate freely: implementation to a fixed contract, mechanical refactor, test authoring, exploration and codebase question-answering, first-draft everything, and review of the agent's own output in a fresh context.

**Subagents.** Reach for one when you need context isolation (an exploration that would otherwise pollute the main thread), genuine parallelism across independent files, or a different permission scope (a read-only research agent). Do not reach for one because you have a lot of tools. The measured benefit is real (subagents process ~67% fewer tokens than skills in multi-domain scenarios because isolation prevents cross-domain bloat) and so is the cost: handoff loss, harder debugging, and a review surface that fans out. The practical rule for a Principal: **one subagent per independently reviewable artifact.** If two subagents produce work you can only evaluate together, you have parallelized generation and serialized review, which is the wrong direction given that review is your bottleneck.

**Fresh-context self-review is the highest-ROI delegation you are probably not doing.** Have the model review its own diff in a clean context window. It feels wrong to ask the same model to critique itself, and it works, because most of the errors are context artifacts (assumptions made 40 turns ago, dead code from a superseded approach) rather than capability limits. Anthropic ships this as a product (Code Review, used by every team internally) and it handles style, linting, PR feedback, bug-catching before commit, and test-adding, which frees the human review budget for the things that need expertise.

### Review discipline: the specific failure classes

Reviewing agent-written code is not reviewing human-written code faster. The error distribution is different, and **38% of developers report that reviewing AI-generated logic requires *more* effort than reviewing human-written code** while only **48% consistently check AI-assisted code before committing it**. Those two numbers together are the whole problem.

Read for these, in this order, because it is roughly descending order of cost:

| # | Failure class | What it looks like | How to catch it |
|---|---|---|---|
| 1 | **Assumption propagation** | An early misunderstanding, built on. Architecture cemented five PRs deep | Review the *plan*, not the diff. This one is unfixable at diff-review time, which is why plan mode is a control and not a nicety |
| 2 | **Passes tests while being wrong** | Green suite, mocked-out the failing dependency; test asserts the implementation rather than the behaviour | Read the test diff *before* the code diff. Ask: would this test fail if the feature were absent? |
| 3 | **Silent bypass of language guarantees** | `# type: ignore`, `Any`, `unsafe`, a cast that defeats the checker, a swallowed `Optional` | Grep the diff for escape hatches. Most compile silently, which is why they survive review |
| 4 | **Swallowed errors** | `except Exception: pass`, a discarded `Result`, an unawaited coroutine, an ignored return code | Grep for bare handlers; check every new `try` for what it does on the failure path |
| 5 | **Confident hallucination on thin APIs** | A method that does not exist on your internal client; a flag from a different SDK version | Any unfamiliar API call gets verified against actual docs, not vibes |
| 6 | **Abstraction bloat** | 1,000 lines where 100 would do; a factory for one implementation; a config system nobody asked for | Ask "couldn't you just…?" The answer is always "of course!" followed by immediate simplification, which tells you it was never necessary |
| 7 | **Dead code accumulation** | Old implementation left in place; comments removed as a side effect; adjacent untouched code altered | Diff the file list against the spec's named files. Anything outside it is suspect |
| 8 | **Scope leakage** | Files touched that the spec did not name; an opportunistic refactor bundled in | Same check. Make it a CI rule if it recurs |
| 9 | **Fail-plausible reporting** | A confident summary of work that did not happen; fabricated command output | Require pasted output, and spot-check by running it yourself. The documented failure class is that polluted or absent evidence produces confident fabrication, not silence |

**The review protocol that survives volume.** Given a 441% increase in median review time, "review harder" is not a strategy. What works:

1. **Gate on size.** Agentic PRs run 2.6× larger on average and wait 5.3× longer for a reviewer. Cap diff size in CI and split. A 200-line PR reviewed properly beats a 2,000-line PR skimmed, and the skim is what is actually happening in the 31% of PRs merging with no review.
2. **Spend the machine budget first.** Lint, types, tests, import-linter, migration lint, security scan, agent code review. Humans should never be the first thing to see a violation that a rule could catch. Every recurring human review comment should become a rule; that is the single most valuable feedback loop available to you.
3. **Review the plan and the test diff, then the code.** In that order. Two of the three highest-cost failure classes are invisible in the code diff.
4. **Human review is targeted, not universal.** Trust boundaries and security-sensitive code, legal risk tolerance, product sense and taste, and architectural fit. Anthropic's framing is "trust but verify," with the explicit caveat that the right balance keeps changing as models improve, so re-evaluate rather than fixing a policy.
5. **Require an "unrequested changes" paragraph.** Make the agent declare what it changed that the spec did not ask for. Ideally nothing. This surfaces items 6-8 without you having to hunt.

### Comprehension debt: the failure mode that ends careers

This is the part to be genuinely uncomfortable about, and the part an interviewer will respect you for raising unprompted.

Generation and discrimination are different cognitive capabilities. You can review code competently after your ability to write it from scratch has atrophied, and **there is a threshold at which "review" silently becomes "rubber stamping."** The mechanism is documented and mundane: the agent does not get tired, it sprints through implementation after implementation with unwavering confidence, the code looks plausible, the tests pass or seem to, you are under pressure to ship, so you skim, nod, and merge. Three days later you cannot explain how it works. Osmani reports doing exactly this and naming it; the borrowed term is **comprehension debt**, and unlike technical debt it does not show up in any dashboard.

The addiction loop that produces it is worth being able to describe, because recognizing it is the mitigation: "the agent implements an amazing feature and got maybe 10% of the thing wrong, and you're like 'hey I can fix this if I just prompt it for 5 more mins.' And that was 5 hrs ago." You are always *almost* there. And the adoption path is a boiling frog: more pasting into a chat, then in-IDE prompting, then agent tools, and suddenly you barely hand-code, with the transition gradual enough that you do not notice until you are already there.

Mitigations that are actually practised, none of them complete:

- **TDD as a comprehension forcing function.** Writing the tests yourself, or at minimum thinking through the cases before delegating, keeps the specification in your head. It also produces the machine-checkable success criterion the decomposition needs, so it pays twice.
- **Ask for the justification, not just the code.** Have the agent explain why, then evaluate the reasoning. This is slower and it is the only reliable way to notice a wrong premise.
- **Hand-write some things deliberately.** Explicitly to maintain the capability, accepting the throughput cost.
- **Treat not-understanding as a stop signal.** When the agent writes something you do not understand, that is not a win, it is a debt entry. Dig in or revert.
- **Own a subsystem end to end.** Comprehension debt is worst when spread thin across everything. Depth somewhere is the insurance.

The formulation to remember: **if your ability to read does not scale with the agent's ability to output, you are not engineering, you are hoping.** And the deeper version, which is the better answer to "what worries you about this": the danger is not that the agent fails. It is that it succeeds so confidently in the wrong direction that you stop checking the compass.

---

## Build it from scratch

`labs/py/28-agent-review-gauntlet/` is a review exercise rather than an implementation lab, because review is the skill under test. It ships a repository with nine agent-authored PRs, one per failure class in the table above, each of which passes CI:

1. **Assumption propagation** across three PRs building on an invented module boundary. Scored on whether you catch it at the plan, and whether you notice at PR 3 that PR 1 was the error.
2. **Green tests, broken feature.** The integration test mocks the exact dependency that is broken.
3. **A `# type: ignore` and a cast** that together defeat `mypy --strict` on a nullable path.
4. **A bare `except Exception: pass`** in a retry helper, plus a discarded `Result`.
5. **A hallucinated method** on an internal client, plus a flag from a newer SDK version.
6. **A factory, a registry, and an ABC** for a single implementation.
7. **Dead code**: the previous implementation left in place and still exported.
8. **Scope leakage**: eleven files touched where the spec named three.
9. **A fabricated verification summary** claiming a load test ran, with plausible numbers.

Then the build half:

10. Write the AGENTS.md that would have prevented 3, 4, 6, and 7 at Level 1, and the hooks/lint rules/CI gates that prevent them at Level 3. Prove the Level 3 versions fail the PR.
11. Write a spec for a real feature using the template above, delegate it, and score the result against your own out-of-scope list.
12. Add a CI check that fails when a PR touches files the linked spec did not name. This is the single highest-value gate in the lab and it takes twenty lines.

The point of the ordering: you review first, unaided, and count what you missed. Most people miss 2, 3, and 9, which is exactly the set that CI could have caught, which is the lesson.

---

## How it's done in production

**Anthropic's Claude Code team** is the most useful primary source because they are furthest along and reasonably candid. What changed, in their words:

| | Before | After |
|---|---|---|
| Planning | Six-month product roadmaps | **Just-in-time planning**: prototype, put internal users on it, act on feedback. Rituals shifted from design docs to discussions in PRs and prototypes |
| Context gathering | Find the person who wrote the code | Ask Claude first, then ask whether the question itself can be automated. "Who made this change?" is no longer sufficient when all PRs are Claude-assisted |
| Code review | Humans review everything | Claude handles style, linting, PR feedback, bug-catching pre-commit, test-adding. Humans review where domain expertise matters: legal risk, trust boundaries and security, product taste |
| Team makeup | Fixed roles | Roles blur; PMs prototype; hiring indexed on creative builders with product sense and engineers with deep systems expertise, and **de-indexed on raw throughput** |

Their non-negotiable principles: relentlessly dogfood; keep the team as flat as possible with managers starting as ICs; and explicitly grant permission to kill processes that no longer work. The three metrics they track for whether new norms are sticking: **onboarding ramp time** (engineers shipping real code within their first week), **PR cycle time** (which surfaces where CI and build systems fail to scale under the new code volume), and **Claude-assisted commit share** (effectively 100% for four months). And the warning attached to the third: *do not confuse throughput with success*; throughput is one metric, the real metric is the thing you were trying to solve. Their starting advice is a good answer to "how would you roll this out": pick your noisiest workflow, the most expensive or most dreaded one, ask whether it still serves its purpose, and if so automate it, and if not delete it.

**What to copy carefully.** JIT planning works when your product surface is moving weekly and your users are internal. It works badly when you have contractual commitments, a compliance calendar, or downstream teams planning against your roadmap. Say this out loud in an interview rather than reciting the practice; the reason a six-month roadmap existed was often coordination cost, not typing cost, and agentic coding does not reduce coordination cost. That is the honest version and it is the more senior answer.

**Failure-mode table**

| Symptom | Cause | Fix |
|---|---|---|
| Throughput doubled, delivery did not improve | Bottleneck moved to review; individual output up 98% while review time up 91% and PR size up 154% | Cap PR size in CI, automate the mechanical review layer, target human review at expertise-required surfaces |
| 31% of PRs merging with no review | Review capacity exceeded, informally rationed | Make the rationing explicit and policy-driven rather than accidental; mandatory human review only where it is genuinely mandatory, and enforced there |
| Feature "done," breaks three commits later when an adjacent system is touched | Assumption propagation; the diff looked right in isolation | Review the plan; require the spec to name interfaces; add architecture-fitness functions (import-linter, dependency rules) as CI gates |
| Codebase grows 3× with no capability gain | Abstraction bloat plus dead-code accumulation | Explicit out-of-scope in every spec; "unrequested changes" paragraph required; complexity budget in CI |
| Style rule ignored after turn 60 despite being in CLAUDE.md | Compaction preserves current task, recent errors, file names; loses initial instructions, intermediate decisions, style rules | Move the rule to Level 3 (lint/hook). Never rely on conversation history for a rule you care about |
| Agent reports a load test that never ran | Fail-plausible: absent evidence becomes confident fabrication | Require pasted command output; spot-check by running it; make the verification step a CI job rather than a narrative |
| Team can generate but nobody can debug production | Comprehension debt | Own-a-subsystem rule; TDD; ask for justifications; deliberate hand-writing; treat not-understanding as a stop |
| Quality varies wildly between engineers on the same tooling | Bimodal adoption; 44% write <10% manually, 44% write >90% | Make the workflow (spec → plan → gates → review) the team standard, not the tool. The tool is not the practice |
| Agent "helpfully" adds error handling, comments, and features nobody asked for | No behavioural constraints codified | The Claude Code internal rule set: don't add unrequested features, don't over-abstract, don't comment unchanged code, don't add unnecessary error handling, read before modifying, diagnose before retrying, report honestly |

---

## Tradeoffs & when NOT to work this way

- **Do not use plan-mode-and-spec for a two-line change.** The ceremony costs more than the fix. The threshold is roughly: if you can hold the whole change and its blast radius in your head and verify it by reading it, just make it. Applying the full apparatus to trivia is how the practice gets a reputation for overhead and gets abandoned.
- **Greenfield and mature codebases invert.** The 80%-agent-written figure lands in greenfield, personal projects, MVPs where good-enough is good enough, and teams small enough that comprehension debt stays manageable. In mature codebases with complex invariants the calculus inverts, because the agent cannot intuit unwritten rules and its confidence scales inversely with context understanding. Be explicit about which regime you are describing; conflating them is the most common way this conversation goes wrong.
- **The last 10% is not linear.** 90% accuracy is fine for non-mission-critical work and nowhere close for the parts that matter. The self-driving analogy is apt: L2 is everywhere, L4 is mostly still vaporware. Each incremental percentage point of autonomy requires disproportionately more oversight, edge-case handling, and rollback infrastructure, and the economics flip somewhere around 75-85% depending on domain complexity.
- **JIT planning is not universally better.** It is better when coding was the dominant cost and your users are internal. It is worse when the roadmap exists for coordination, compliance, or contractual reasons, because agentic coding reduces typing cost and does not reduce coordination cost. Recommending it unconditionally is a red flag.
- **Delegating architecture is the one thing that does not recover.** Implementation mistakes are cheap to fix; a wrong service boundary or consistency model is paid for over years by people who were not present. The specific danger is not a bad answer but a *plausible* one delivered confidently, and the model does not surface tradeoffs or push back unprompted. If you take one rule from this module: the agent may draft the ADR, and you own it, and you must be able to defend the rejected alternatives.
- **AI-fluency signalling can backfire in interviews.** There is a documented case of a borderline senior candidate getting a soft thumbs-down for insisting LLMs could help with a regression problem where it did not make technical sense. Knowing the tools is table stakes; knowing when not to use them is the seniority signal. Correspondingly, candidates who lean on AI during live interviews frequently do worse, because follow-ups expose that they cannot explain a subtle bug the model introduced.
- **Do not present the productivity case as settled.** METR's RCT found 19% slower in early 2025 with a 39-point perception gap; the continuation estimates +18% faster by early 2026; DORA's synthesis is that AI is an **amplifier of existing practice** (good processes get better, with high performers seeing meaningfully faster delivery; bad processes accumulate debt faster) rather than a silver bullet. If you quote only the favourable number, an informed interviewer will assume you have not read the unfavourable one.

---

## Interview questions

### Q1 — How has your role changed with agentic coding tools?
**Testing:** whether you have a structural answer or an enthusiasm answer.
**Answer:** The bottleneck moved rather than disappeared. Writing code, tests, and refactors stopped being the constraint; verification, review, and security became the constraint. So the time reallocation is concrete: roughly 40% specification (problem, contract, out-of-scope, verification), 10% decomposition, 10% delegation and supervision, 35% review and verification, and I own the outcome regardless. The corollary is that the artifacts I author changed: fewer hand-written implementations, more specs, ADRs, and *enforcement* (lint rules, hooks, CI gates, fitness functions), because a rule I have not enforced is a preference.
**Follow-up trap:** *"Isn't that just being a manager?"* Partly, and it is worth saying so honestly rather than dressing it up: orchestrating agents involves delegating, reviewing, and redirecting, and if you became an engineer specifically to avoid management this shift can feel like a loss. But there is a real difference: I still own technical correctness personally and I still have to be able to write and debug the code, because review without comprehension is rubber-stamping. A manager can delegate understanding. An architect cannot.

### Q2 — Walk me through how you would have an agent implement a non-trivial feature.
**Testing:** whether there is a repeatable process or improvisation.
**Answer:** Research → plan → execute → review → ship, with the human at the plan gate and the review gate. Concretely: I write a spec that is self-contained, names the files and interfaces involved, states what is explicitly out of scope, and ends with an end-to-end verification step that actually runs. Then plan mode, where the write tools are unavailable and the agent produces a plan plus, importantly, a list of open questions for me. I answer the questions and approve or revise the plan. Execution runs against CI gates that already encode the hard rules. Then I read the test diff before the code diff, check the file list against the spec's named files, and require a paragraph declaring anything changed that the spec did not ask for.
**Follow-up trap:** *"Why does plan mode matter if you could just tell it not to edit?"* Because "don't edit yet" is Level 1 and plan mode is Level 3. In Claude Code the write tools are physically unavailable in plan mode, a hard read-only sandbox enforced at the tool level, not a promise the model keeps. That distinction generalizes to the whole topic: instructions are recommendations, enforcement is a constraint, and the difference shows up exactly when context is under pressure or another objective becomes more urgent, which is precisely when you need it.

### Q3 — Write me a CLAUDE.md for a service you own.
**Testing:** whether you know the difference between agent-operational policy and human documentation.
**Answer:** Command-first with exact copy-pasteable invocations for install, fast tests, full tests, lint, types, migrate. A *map* of the tree telling the agent where to look next rather than explaining everything, including a pointer to `docs/adr/` with an instruction to stop if a plan contradicts an ADR. Hard rules stated *and* noted as CI-enforced, so the agent does not waste a cycle discovering them. A behaviour block: read before modifying; prefer three duplicate lines over a premature abstraction; don't comment unchanged code; don't add error handling the contract does not require; diagnose before retrying; report honestly; stop and ask above roughly 60% uncertainty on a boundary. And an explicit "done means" section with verifiable criteria.
**Follow-up trap:** *"You have a rule about never raising across the service boundary. Is putting it in CLAUDE.md enough?"* No, and this is the central point. Three levels of control: instruction (CLAUDE.md explains it), reminder (a skill re-states it at the moment it matters), enforcement (a lint rule or hook rejects it). Only the third is a constraint. There is also a hard mechanical reason: compaction reliably preserves the current task, recent errors, and file names, and reliably loses initial instructions, intermediate decisions, and style rules. A rule that lives in conversation history is gone by turn 60. A rule in CLAUDE.md lives in the system prompt and survives. A rule in a lint config cannot be lost.

### Q4 — Give me work an agent will fail at, and how you recognize it in advance.
**Testing:** the primary senior signal in this topic.
**Answer:** Five categories. Under-determined design decisions with long shadows: consistency models, tenancy strategies, service boundaries, data ownership. The agent has no access to the political, organizational, and roadmap constraints that dominate those choices, and the failure is not a bad answer but a plausible one delivered confidently. Anything whose correctness depends on unwritten invariants, which is why mature codebases invert the calculus relative to greenfield. Thinly-represented APIs, where confident hallucination concentrates: internal libraries, recently-changed SDKs. Cross-cutting migrations where 15% of call sites need human judgment, because the agent will make the 15% look like the 85%. And work where the test suite is the thing being fixed, because an agent optimizing to green with a wrong oracle makes things worse fast.
**Follow-up trap:** *"How do you recognize it before you have burned a day?"* Run the five-property check on the unit of work: can I name the files it should touch; is the contract fixed in advance; is there a command whose exit code decides "done"; is one `git revert` enough to undo it; does the relevant code and constraints fit in one window. Two or more failures means the decomposition is wrong, not the agent. The one that catches the most is the third: if I cannot write the machine-checkable success criterion, I have no verification, which means the completion claim is unfalsifiable, which means I should not delegate it yet.

### Q5 — You are reviewing an agent-authored PR. What do you look for, in what order?
**Testing:** whether you know the error distribution is different from human code.
**Answer:** Test diff first, then file list, then code. The test diff first because the highest-cost failure is *passes tests while being wrong*, typically by mocking out the exact dependency that is broken, or by asserting the implementation rather than the behaviour. The question to ask of every new test: would this fail if the feature were absent? Then the file list against the spec's named files, which catches scope leakage and dead code cheaply. Then the code, grepping specifically for escape hatches (`# type: ignore`, `Any`, casts, `unsafe`) and swallowed errors (bare `except`, discarded `Result`, unawaited coroutine, ignored return code), because those compile silently and that is why they survive review. Then unfamiliar API calls verified against real docs, because confident hallucination concentrates on thin APIs. Then abstraction bloat, where the diagnostic is asking "couldn't you just…?" and getting "of course!" followed by immediate simplification, which tells you it was never necessary.
**Follow-up trap:** *"Which failure class can you not catch at review time at all?"* Assumption propagation. If the model misunderstood something early and built the feature on a faulty premise, the diff can be locally excellent and globally wrong, and by the time you notice you may be five PRs deep with the architecture cemented. That is unfixable at diff-review time, which is exactly why plan review is a control rather than a courtesy, and why architecture-fitness functions (import-linter, dependency rules, boundary tests) belong in CI: they are the only mechanism that catches a wrong premise mechanically.

### Q6 — Your team's throughput doubled and delivery did not improve. Diagnose it.
**Testing:** systems thinking about the org, not just the code.
**Answer:** The constraint moved and nobody re-provisioned it. The data pattern is consistent: high-AI-adoption teams merged 98% more PRs while review times grew 91% and PR size grew 154%, and 2026 figures are worse, with median review time up 441% and 31% more PRs merging with no review at all. Agentic PRs specifically wait 5.3× longer for a reviewer and run 2.6× larger. So output backs up at the points requiring human judgment, and the queueing removes most of the speed gain before it reaches the system. Fixes in order: cap diff size in CI and split; spend the machine review budget fully first (lint, types, tests, import rules, security scan, agent code review) so humans never see a violation a rule could catch; target human review at trust boundaries, security-sensitive code, legal risk, and product taste; and turn every recurring human review comment into a rule.
**Follow-up trap:** *"Just hire more reviewers."* Review capacity scales linearly and generation capacity does not, so that is a losing race. It also does not address the second-order problem: Atlassian found 99% of AI-using developers saving 10+ hours a week with most reporting no decrease in overall workload, because the saved time was consumed by context switching and coordination overhead from the higher volume of change. The lever is reducing the *number of human-judgment events per unit of delivered value*, which means smaller batches, more machine gates, and not generating changes you did not need. Vercel deleting 80% of their agent's tools and getting better results is the same lesson in a different domain.

### Q7 — What is comprehension debt and what are you doing about it?
**Testing:** intellectual honesty, and this is the question where volunteering the problem is worth more than any answer.
**Answer:** Generation and discrimination are different capabilities. You can review code competently after your ability to write it from scratch has atrophied, and there is a threshold at which review silently becomes rubber-stamping. The mechanism is mundane: the agent never gets tired, the code looks plausible, the tests pass or seem to, you are shipping under pressure, so you skim and merge, and three days later you cannot explain how it works. It does not appear in any dashboard, which is what makes it different from technical debt. My mitigations, none of them complete: TDD so the specification stays in my head and I get the machine-checkable criterion for free; asking for justifications and evaluating the reasoning rather than the output; deliberately hand-writing some things to keep the capability; owning one subsystem end to end so depth exists somewhere; and treating "I don't understand this" as a stop signal rather than a win.
**Follow-up trap:** *"Isn't this just nostalgia? Compilers abstracted away assembly."* Different in one specific way, and it is the way that matters. A compiler is deterministic and its output is *correct by construction*, so you do not need to read it. An agent's output is probabilistic and occasionally confidently wrong, so somebody must retain the ability to read it and judge it. The relevant survey number is the honest one: 38% of developers say reviewing AI-generated logic takes *more* effort than reviewing human-written code, while only 48% consistently check it before committing. That gap is not nostalgia, it is an unpriced risk. When agent output becomes verifiable by construction, the analogy will hold, and we are not there.

### Q8 — Is agentic coding making engineers more productive? Give me the evidence.
**Testing:** whether you have read the unfavourable studies.
**Answer:** Present both sides, because a one-sided answer signals you have only read the marketing. Against: METR's July 2025 randomized controlled trial, 16 experienced open-source developers, 246 tasks on repositories they regularly contributed to, found early-2025 AI tools made them **19% slower** while they predicted a 24% speedup and, after experiencing the slowdown, still estimated they had been 20% faster. That 39-point perception gap is the most important number in the topic, because it means self-report is not evidence. Stack Overflow found only 16% reporting "great" productivity improvement, with the top frustrations "almost right, but not quite" at 66% and "debugging AI code takes longer than writing it myself" at 45%. And 30% of developers report little or no trust in AI-generated code. For: METR's own continuation estimates the slowdown flipping to roughly **+18% faster by early 2026**, and their transcript analysis estimates a 1.5× to 13× time-savings factor on Claude Code-assisted tasks for a small internal sample, with substantial caveats they state themselves. The synthesis I would actually defend is DORA's: **AI is an amplifier of existing practice.** Good processes get meaningfully better; bad processes accumulate debt faster. There is no silver bullet, and the variance between teams on identical tooling is larger than the average effect.
**Follow-up trap:** *"So which is it for your team?"* The honest answer is that you cannot know from self-report, given the 39-point gap, so measure the things that are hard to fool: PR cycle time end to end (not time-to-first-draft), change failure rate, time to restore, and defect escape rate. Anthropic's own three-metric set is a good starting point: onboarding ramp time, PR cycle time, and AI-assisted commit share, with the explicit warning attached to the third that throughput is not success and the real metric is the problem you were trying to solve.

### Q9 — Where would you draw the line on what you delegate?
**Testing:** whether the boundary is principled or vibes.
**Answer:** In-house always: architectural decisions and their rationale, trust and security boundaries, data model ownership, error-semantics contracts, dependency additions, anything with legal or compliance exposure, and the ship decision. Delegated freely: implementation to a fixed contract, mechanical refactor, test authoring, exploration and codebase Q&A, first drafts of everything, and review of the agent's own output in a fresh context. The organizing principle is reversibility multiplied by shadow length: an implementation mistake is cheap and local, a wrong service boundary or consistency model is paid for over years by people who were not in the conversation. And the specific reason the agent cannot own the second category is not capability, it is that it does not surface tradeoffs or push back unprompted, so a wrong choice arrives looking exactly like a right one.
**Follow-up trap:** *"Can the agent write the ADR?"* It can draft it, and that is genuinely useful because getting the alternatives enumerated is most of the work. But I own it, and the test I apply to myself is whether I can defend the *rejected* alternatives without re-reading the document. If I cannot, I have delegated the decision rather than the drafting, and I will not be able to defend it in six months when the constraint that drove it has been forgotten.

### Q10 — When have you decided *not* to use an agent on something?
**Testing:** judgment, and there is a documented failure case for candidates who cannot answer this.
**Answer:** Give a concrete one with the reasoning. The pattern to describe: work where the test suite was the oracle and the oracle was wrong, so an agent optimizing to green would have made it confidently worse; or a migration where roughly 15% of call sites needed a judgment call that the other 85% did not, where the agent would have made the 15% look like the 85% and I would have found out in production. Also the mundane case: a two-line fix where I could hold the whole change and its blast radius in my head, so spec-and-plan ceremony would have cost more than the fix.
**Follow-up trap:** *"Does saying that hurt you at an AI-forward company?"* The opposite, and there is evidence. There is a documented case of a borderline senior candidate getting a soft thumbs-down specifically for insisting LLMs could help with a regression problem where it did not make technical sense. Knowing the tools is table stakes at this point; knowing when not to reach for them is the seniority signal. The framing that works is "knowledge is free, judgment isn't."

### Q11 — You are given a real GitHub issue and 3 hours. You may use any AI tooling. What do you optimize for?
**Testing:** this is close to the actual "AI delta" round format, which scores what you add beyond what the AI produced.
**Answer:** Assume the diff is not the deliverable, because the evaluator can generate the diff themselves in ten minutes. What they are scoring is the delta: exploration strategy, engineering rigour, edge-case handling, and documentation quality. So: reproduce the bug with a failing test *first*, and say why that test is the right oracle. State the hypothesis and the alternatives you rejected. Fix it minimally. Then spend the remaining time on the things an agent will not volunteer: adjacent call sites with the same defect, the regression test that would have caught it originally, whether the bug indicates a missing invariant that belongs in a type or a lint rule, and a short note on what you did not do and why. Narrate the AI use rather than hiding it, because that is what is being assessed.
**Follow-up trap:** *"You have used Claude the whole time. How do we know you understand the code?"* Invite the verification. Explain the failure mechanism without looking, name the specific line where the invariant broke and why the previous author's assumption was reasonable, and identify what else in the repository shares the assumption. The documented pattern is that candidates leaning on AI in live interviews often perform *worse* precisely because follow-ups expose that they cannot explain a subtle bug the model introduced, so the defence is having actually read it. OpenAI's stated boundary for AI use in their coding rounds is the same idea: do not dump the whole problem in and paste the output back, because they are watching for reasoning and judgment.

### Q12 — Design the CI and enforcement layer for a team where most code is agent-written.
**Testing:** whether "enforcement over instruction" is a slogan or a design.
**Answer:** Layer it and make every layer machine-run before a human sees the PR. Formatting and lint, types under `--strict`, unit and integration tests, architecture fitness functions (import-linter or equivalent so `domain` cannot import `adapters`, plus explicit boundary tests), migration lint requiring a tested `downgrade`, dependency-addition gate requiring an ADR note, security scan, secret scan, **diff-size cap with a split requirement**, and a check that the PR touched only files the linked spec named. Then agent code review in a fresh context, then targeted human review. Plus hooks at `PreToolUse`/`PostToolUse` for rules that need to fire during the run rather than at merge, since catching a violation at edit time is cheaper than catching it in CI.
**Follow-up trap:** *"Which single gate would you add first?"* The spec-file-scope check: fail the PR if it touched files the linked spec did not name. It is about twenty lines, and it catches scope leakage, dead-code accumulation, and opportunistic refactors in one rule, which are three of the nine failure classes. Second would be the diff-size cap, because it is the only thing that actually addresses the 31%-merged-unreviewed problem: a 200-line PR reviewed properly beats a 2,000-line PR skimmed, and the skim is what is really happening.

### Q13 — Would you adopt Anthropic's just-in-time planning at our company?
**Testing:** whether you copy practices or reason about their preconditions.
**Answer:** Only conditionally, and the conditions are the answer. JIT planning worked for the Claude Code team because coding was the dominant cost, their users were internal, and their product surface moved weekly, so a six-month roadmap was out of date by month three. It fails where the roadmap exists for reasons other than typing cost: coordination with downstream teams planning against your dates, compliance calendars, contractual commitments, hardware or partner dependencies. Agentic coding reduces implementation cost and does not reduce coordination cost, so if your roadmap is a coordination artifact rather than a capacity estimate, shortening it just moves the coordination failure somewhere less visible. What I would adopt unconditionally is their meta-practice: relentlessly question why a process exists, grant explicit permission to kill obsolete ones, and pick the noisiest workflow first.
**Follow-up trap:** *"What would you drop instead?"* Whatever exists to close a gap that no longer exists. The specific candidates in most orgs: design docs whose function was to get typing right before typing was expensive (replaceable by a spec plus a prototype), estimation rituals that were capacity models for a capacity that changed, and status meetings whose content is now derivable from tooling. The test is Fung's: ask whether it still serves its purpose, and if it does, ask whether it can be automated.

### Q14 — What worries you most about how your organization is using these tools?
**Testing:** the closing question, and the one where genuine criticism outperforms optimism.
**Answer:** Three things, in order. First, comprehension debt distributed thinly across the whole team, because it is invisible until an incident and the incident is when you discover nobody can debug a subsystem. Second, plausible-but-wrong architecture accumulating: the models do not surface inconsistencies, do not present tradeoffs, and do not push back when they should, so a wrong premise arrives looking identical to a right one and gets cemented over several PRs. Third, the bimodal split, with 44% of developers writing under 10% of their code manually and another 44% writing over 90%, which means "how we build software here" is no longer a shared practice and code review across the two populations is genuinely difficult. And the summary of all three: the danger is not that the agent fails, it is that it succeeds so confidently in the wrong direction that you stop checking the compass.
**Follow-up trap:** *"Given all that, would you slow adoption?"* No, and the reason is that the evidence does not support slowing down, it supports investing in the constraint. DORA's finding is that AI amplifies existing practice, so the differentiator is process quality, not adoption level, and the variance between teams on identical tooling exceeds the average effect. So: adopt, and spend the budget on the enforcement layer, review capacity, and the specific discipline of keeping architectural judgment in-house. Slowing adoption gets you the comprehension debt anyway, at lower throughput, because individuals adopt whether or not the org does.

---

## Red flags that fail you

- Presenting productivity gains as settled, or quoting the favourable study without the METR result.
- Describing your workflow as "I tell it what to do and check the output" with no spec, no plan gate, and no machine gates.
- Believing a rule in CLAUDE.md is enforced.
- Not knowing that compaction loses initial instructions and style rules.
- Letting the agent own a service boundary, consistency model, or tenancy strategy.
- Reviewing the code diff without reading the test diff first.
- No answer for how you avoid comprehension debt, or dismissing it as nostalgia.
- Claiming your team's AI productivity gain from self-report.
- Reciting Anthropic's practices without naming the preconditions that make them work.
- Insisting an agent can help with a problem where it technically cannot.
- Raising PR size limits or reviewer counts as the answer to a review bottleneck.
- Not being able to explain the code you shipped in the last month.

## Cheat card

```
THE SHIFT
  bottleneck moved: coding/tests/refactor → VERIFICATION, REVIEW, SECURITY
  time: 40% spec · 10% decompose · 10% delegate · 35% review+verify · own outcome
  artifacts change: fewer implementations, more specs/ADRs/GATES

THREE LEVELS OF CONTROL (the load-bearing idea)
  L1 INSTRUCTION  CLAUDE.md/AGENTS.md  → a RECOMMENDATION
  L2 REMINDER     skill re-states it   → higher compliance, still probabilistic
  L3 ENFORCEMENT  hook/lint/CI/type    → a CONSTRAINT
  anything you'd be upset to find violated belongs at L3
  compaction KEEPS current task, recent errors, file names
            LOSES initial instructions, intermediate decisions, style rules

FIVE PHASES   research → PLAN(human gate) → execute → REVIEW(human gate) → ship
  plan mode = write tools PHYSICALLY UNAVAILABLE (L3), not a promise

SPEC = SELF-CONTAINED
  names files + interfaces · states OUT OF SCOPE · ends with an e2e verification
  step that actually runs · + "open questions for the human" (empty = suspicious)

AGENT-SIZED WORK (5 checks; 2 fails ⇒ decomposition is wrong)
  bounded blast radius · contract fixed in advance · machine-checkable "done"
  one `git revert` undoes it · fits one context window

AGENT CANNOT DO
  under-determined design w/ long shadows (boundaries, consistency, tenancy)
  correctness resting on unwritten invariants (mature codebase inverts vs greenfield)
  thinly-represented APIs (internal libs, new SDKs) → confident hallucination
  migrations where 15% of call sites need judgment
  work where the TEST SUITE is what's broken

REVIEW ORDER: test diff → file list → code
  1 assumption propagation  ← NOT catchable at diff review; that's why plan mode
  2 passes tests while wrong (mocks the broken dep) - "would this fail if absent?"
  3 silent bypass: `# type: ignore`, Any, casts, unsafe   ← compiles silently
  4 swallowed errors: bare except, discarded Result, unawaited coroutine
  5 hallucinated API on thin surfaces      6 abstraction bloat (1000 for 100)
  7 dead code            8 scope leakage   9 fail-plausible fabricated output
  require an "unrequested changes" paragraph

NUMBERS (know these cold)
  METR RCT Jul'25: 19% SLOWER; predicted +24%, still felt +20% after → 39pp gap
  METR cont.: ≈ +18% faster by early 2026 (and 1.5-13× transcript est., caveated)
  DORA'25: +98% PRs merged · +91% review time · +154% PR size
  2026: median review time +441% · 31% of PRs merge with NO review
  agentic PRs: 5.3× longer wait, 2.6× larger · batch size ~2× Q1'25→Q1'26
  48% consistently check AI code · 38% say reviewing AI logic is HARDER
  30% little/no trust in AI code · SO: only 16% "great" gains
  frustrations: 66% "almost right not quite" · 45% "debugging takes longer"
  BIMODAL: 44% write <10% manually, 44% write >90%
  Atlassian: 99% save 10+ h/wk, most report NO workload decrease
  DORA synthesis: AI is an AMPLIFIER of practice, not a silver bullet

ANTHROPIC (Fung, Jun'26)  before → after
  6-month roadmap → JIT planning (prototype, internal users, feedback)
  ask the author → ask Claude, then ask "can this be automated?"
  humans review all → Claude does style/lint/bugs/tests; humans do trust
    boundaries + security, legal risk tolerance, product taste
  metrics: onboarding ramp ↓ · PR cycle time ↓ · AI-assisted commits ↑ (≈100%)
  WARNING: don't confuse throughput with success
  start: pick your NOISIEST workflow, ask if it still serves its purpose

KEEP IN-HOUSE  architecture + rationale · trust/security boundaries · data model
  ownership · error semantics · dependency adds · legal exposure · ship decision
  agent may DRAFT the ADR; you must defend the REJECTED alternatives

COMPREHENSION DEBT
  generation ≠ discrimination; review silently becomes rubber-stamping
  "if reading doesn't scale with the agent's output, you're not engineering, hoping"
  mitigations: TDD · ask for justification · hand-write some · own a subsystem
    deeply · treat "I don't understand" as a STOP
  the danger isn't failure; it's succeeding confidently in the wrong direction
    until you stop checking the compass

FIRST TWO CI GATES TO ADD
  1. fail if the PR touched files the linked spec didn't name (~20 lines)
  2. diff-size cap + split requirement (the only real fix for merged-unreviewed)
```

## Sources

- [Running an AI-native engineering org](https://claude.com/blog/running-an-ai-native-engineering-org) — Fiona Fung, Director of Engineering for Claude Code, Code w/ Claude SF 2026, published 2026-06-03; bottleneck shift, JIT planning, trust-but-verify code review, the three metrics, "pick your noisiest workflow"; accessed 2026-07-26
- [The 80% Problem in Agentic Coding](https://addyo.substack.com/p/the-80-problem-in-agentic-coding) — Addy Osmani, 2026-01-28; comprehension debt, assumption propagation, abstraction bloat, dead-code accumulation, sycophantic agreement, the Karpathy and Cherny quotes, the 70/30 problem-definition split, and the survey figures on verification and trust; accessed 2026-07-26
- [Measuring the Impact of Early-2025 AI on Experienced Open-Source Developer Productivity](https://arxiv.org/abs/2507.09089) — METR RCT: 16 developers, 246 tasks, 19% slowdown, 39-point perception gap; accessed 2026-07-26
- [Analyzing coding agent transcripts to upper bound productivity gains from AI agents](https://metr.org/notes/2026-02-17-exploratory-transcript-analysis-for-estimating-time-savings-from-coding-agents/) — METR, Feb 2026; the 1.5×-13× estimate for 7 staff on Claude Code tasks, with the authors' caveats; accessed 2026-07-26
- [DORA 2025 State of DevOps Report](https://dora.dev/research/2025/dora-report/) — AI as amplifier of existing practice; throughput up with stability trade-offs; accessed 2026-07-26
- [Balancing AI tensions: Moving from AI adoption to effective SDLC use](https://dora.dev/insights/balancing-ai-tensions/) — DORA; trust and review-bottleneck framing; accessed 2026-07-26
- [Key Takeaways from the DORA Report 2025](https://www.faros.ai/blog/key-takeaways-from-the-dora-report-2025) — Faros AI; +98% PRs merged, +91% review time, +154% PR size, and the 2026 "Acceleration Whiplash" figures; accessed 2026-07-26
- [Claude Code for Spec-Driven Development: Capabilities and Limits](https://www.augmentcode.com/guides/claude-code-spec-driven-development) — plan mode as a tool-level read-only sandbox; the self-contained-spec guidance; accessed 2026-07-26
- [Agent Harnesses — Microsoft Learn](https://learn.microsoft.com/en-us/agent-framework/agents/harness) — plan/execute mode provider as a first-class capability; page updated 2026-07-08, accessed 2026-07-26
- [AGENTS.md Spec (2026): Recommended Sections + AGENTS.md vs CLAUDE.md vs .cursorrules](https://www.morphllm.com/agents-md-guide) — cross-tool adoption, Linux Foundation Agentic AI Foundation stewardship, 60,000+ repositories; accessed 2026-07-26
- [From CLAUDE.md to Hooks: How to Make AI Agents Actually Follow Rules](https://medium.com/@PopovOnline/from-claude-md-to-hooks-how-to-make-ai-agents-actually-follow-rules-ae33ff76e768) — the three-level instruction/reminder/enforcement model; accessed 2026-07-26
- [AGENTS.md Patterns: What Actually Changes Agent Behavior](https://blakecrosley.com/blog/agents-md-patterns) — command-first, task-organized, explicit verifiable done criteria; what to avoid; accessed 2026-07-26
- [Claude Code Compaction: How Context Compression Works](https://okhlopkov.com/claude-code-compaction-explained/) — what survives compaction (current task, recent errors, file names) versus what is lost (initial instructions, intermediate decisions, style rules); accessed 2026-07-26
- [Claude Code Deep Dive Part 2: The 1,421-Line While Loop](https://harrisonsec.com/blog/claude-code-deep-dive-query-loop/) — the internal behavioural constitution: don't add unrequested features, don't over-abstract, don't comment unchanged code, don't add unnecessary error handling, read before modifying, diagnose before retrying, report honestly; accessed 2026-07-26
- [Three Patterns Where Agent-Generated Code Quietly Fails](https://medium.com/@michael.hannecke/three-patterns-where-agent-generated-code-quietly-fails-1b9735493468) — silent bypass of language guarantees, confident hallucination on thin APIs, swallowed errors, and that most compile silently; accessed 2026-07-26
- [When Errors Become Narratives: A Longitudinal Taxonomy of Silent Failures in a Production LLM Agent Runtime](https://arxiv.org/html/2606.14589) — the "fail-plausible" class: polluted context becomes confident fabrication rather than silence; accessed 2026-07-26
- [Code Review — Claude Code docs](https://code.claude.com/docs/en/code-review) — the automated review surface Anthropic reports every internal team using; accessed 2026-07-26
- [Interview Trends (2026) — ai-engineering-field-guide](https://github.com/alexeygrigorev/ai-engineering-field-guide/blob/main/interview/05-trends.md) — the round formats and hiring-criteria data cited above: AI-delta assessments, code-review rounds, evaluating LLM-generated solutions, OpenAI's allowed-AI coding rounds, the Exponent Claude Code round and its stated top pitfall, Miro/TRM Labs/Toku/BetterUp expectations, and the "candidates using AI live often perform worse" pattern; accessed 2026-07-26
- [What It's Actually Like to Interview at OpenAI in 2026](https://medium.com/exponent/what-its-actually-like-to-interview-at-openai-in-2026-03a646c9436c) — AI tools allowed in coding rounds; screen-share and narrate; the "don't dump the problem in" boundary; accessed 2026-07-26
- [The AI Coding Trust Gap](https://www.sonarsource.com/blog/ai-coding-trust-gap/) — 48% consistently verify AI-assisted code; 38% find reviewing AI logic harder than human code; accessed 2026-07-26

## Changelog
- 2026-07-26 — created
