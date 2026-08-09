# Spec-Driven Development: Plan → Approve → Build → Verify

> **Track:** T28 AI-Assisted Architecture · **Time:** 2h · **Prereqs:** `T28-claude-code-model`, `T19-testing-quality`, `T21-architecture-principles` · **Updated:** 2026-07-26
> **Module id:** `T28-spec-driven-dev` · **Tags:** workflow, critical
> **Lab:** none yet — see `labs/py/02-agent-loop/` for the pattern if you want to build one

## The 30-second version

Specifying before building beats iterating with an agent for one mechanical reason: an agent's failure mode is not writing bad code, it is confidently building on a wrong premise, and a premise error is invisible in the diff and unfixable at review time once three PRs sit on top of it. So the loop is Plan → **Approve** → Build → Verify, with the human mandatory at exactly two gates, and the approve gate is the one everybody skips and the only one that catches premise errors. A spec an agent can execute is not a design document: it names the files and interfaces in play, states what is explicitly out of scope, converts each acceptance criterion into a command with an exit code, and ends with a verification plan that actually runs. This is TDD with the oracle written first and a wider blast radius, and it is RFC/ADR practice with the decision record pulled *upstream* of the code instead of filed after it. Marc Brooker's framing is the right correction to the waterfall objection: spec-driven development is not about pulling design **up-front**, it is about pulling design **up**, into versioned living artifacts the implementation flows from. And the honest failure modes are severe: spec-kit generating 8 files and 1,300 lines of markdown for "display the current date," review time *doubling* because you now review the spec's code and then the real code, agents marking a "verify implementation" task done having written manual testing instructions instead of a single unit test, and specs drifting precisely because everyone can edit them and nobody owns reconciliation.

## Why this gets asked

Because it is the workflow question, and it separates two populations cleanly. One group describes an iterative chat: "I tell it what I want, look at the output, and correct it," which is a real methodology that works fine up to a scope ceiling and collapses above it. The other describes a gated pipeline with a machine-checkable definition of done. The interviewer has lived the collapse: a feature that looked finished, passed CI, and turned out to have been built against an interface the agent invented in turn six, discovered when a neighbouring team's integration broke. They have also lived the overcorrection, a team that adopted a spec framework and shipped less because everyone spent their days reading generated markdown. So they are probing for calibration, not enthusiasm: can you tell which regime you are in, and do you know what the ceremony costs.

---

## Lineage: past → present → future

**What came before.** Three predecessors, each killed by a specific pain, and you need all three because the objections to spec-driven development are all inherited from them. **Waterfall specification, 1970s-1990s:** freeze requirements, then implement. It died because software requirements are, in François Zaninotto's phrasing of the classic critique, "complex, dynamically changing, internally conflicting, and invariably incomplete," so Big Design Up Front piles up hypotheses and No Silver Bullet (Brooks, 1986) explained why planning does not eliminate that uncertainty. The pain was specific: by the time the spec was approved it described a product nobody wanted, and the phase gates made changing it expensive. **Agile's answer, 2001 onward:** kill the specification document, put a customer in the loop, iterate on the implementation. That worked for two decades and its own pain surfaced only when implementation cost collapsed: iterating on the *implementation* is the right strategy when implementation is the expensive step, and when an agent can produce 800 lines in ninety seconds, iterating on the implementation means iterating on an artifact you now have to *review* at the same rate you generate it. **Vibe coding, 2024-2025:** prompt, look, correct, repeat. The pain that killed it above small scope is documented and specific: plausible code that drifts from intent, hallucinated APIs, and decay as the project grows, plus the premise-error problem, where a misunderstanding in turn six becomes load-bearing by turn forty and the diff never shows it.

**Where it stands now.** By 2026 every major tool ships a flavour: GitHub Spec Kit (a Python CLI, 93,000+ stars, v0.8.7 on 2026-05-07, supporting 30+ agents, and **GitHub itself calls it an experiment**), AWS Kiro (spec-first IDE and CLI with `requirements.md` / `design.md` / `tasks.md`), Claude Code's plan mode plus todo list, Cursor's plan mode, OpenSpec, BMAD, Tessl, Google Antigravity. Microsoft Agent Framework's harness ships plan and execute as a first-class *mode provider*: plan mode is interactive, the agent asks clarifying questions, drafts a todo list and plan, and gets approval before significant work; execute mode is autonomous. That independent convergence is the strongest evidence the two-phase shape is real. Claimed results exist and should be quoted with their provenance: GitHub reports internal teams shipping features with roughly an order of magnitude fewer "regenerate from scratch" cycles, and AWS documents customer cases where 40-hour features shipped in under 8 hours of human time when authored as specs first. Both are vendor-reported. The **live disagreement is genuine and unresolved**, and you should be able to argue both sides. Zaninotto's position: SDD is the waterfall model returning, it "tries to solve a faulty challenge, how do we remove developers from software development," it requires you to be a business analyst to catch requirement errors *and* a developer to catch design errors, and the trade-off of "spending 80% of your time reading instead of thinking" is not worth it. His alternative is to split complex requirements into simple ones rather than translating complex requirements into complex documents, and he has a working 3D sculpting tool built in about 10 hours with no spec as evidence. Brooker's rebuttal, from inside AWS: it "isn't about pulling designs up-front, it's about pulling designs up," making specifications "explicit, versioned, living artifacts that the implementation of the software flows from, rather than static artifacts," with the iteration cycle unchanged and specs staying in sync by being **upstream** of implementation. His decisive argument is economic rather than philosophical: the largest velocity gains are in teams that can let agents run autonomously for long periods, and a spec is what makes that possible, because it gives the agent a map instead of turn-by-turn directions, so it knows what to test and what good looks like. Both are right about different regimes, and saying so is the senior answer.

**Where it's heading.** **High confidence: verification becomes a distinct, tooled phase rather than a trailing test run.** It has already shipped: Claude Code's `/verify` bundled skill builds and runs your app to confirm a change does what it should **without falling back to tests or type checks**, `/run` launches and drives it, and `/run-skill-generator` records the working recipe (install commands, env vars, launch script) as a committed per-project skill at `.claude/skills/run-<name>/` so every agent in the repo follows it instead of rediscovering it. As of v2.1.215 `/verify` and `/code-review` run **only when you invoke them**, which is a deliberate statement that these are gates you schedule, not background chatter. **High confidence: the spec becomes a reviewed artifact with an owner.** The drift critique is precise and it is a governance gap, not a tooling gap. Expect CODEOWNERS on spec directories, spec-diff review, and CI checks tying a PR's touched files to its linked spec. **Medium confidence: partial formality wins over full formality.** Brooker's list is the shape: free-form or structured prose (RFC 2119, EARS), pictures, snippets, and rarely exact statements in Lean or TLA+ where it matters, mixing levels within one spec. **Speculative: specs become the primary versioned artifact and code becomes derived output** for some class of software. That is Brooker's explicit bet ("the future is specification-driven") and it is a bet, made by someone with a strong track record, from inside a company shipping a spec-first product. Weight it accordingly and label it.

---

## Mental model

The two gates, and what each one catches. Everything in this module is a consequence of the left-hand column being uncatchable at the right-hand gate.

```
  PLAN ──────────►[ APPROVE ]──────► BUILD ──────►[ VERIFY ]──────► SHIP
   │                  ▲                              ▲
   │                  │                              │
   │            HUMAN MANDATORY               HUMAN MANDATORY
   │            catches: PREMISE errors       catches: BEHAVIOUR errors
   │              wrong interface              wrong output
   │              wrong boundary               missed edge case
   │              wrong problem                perf regression
   │              missing constraint           broken contract
   │              invented module
   │                  │                              │
   │            ┌─────┴─────┐                  ┌─────┴─────┐
   │            │ COST TO   │                  │ COST TO   │
   │            │ FIX HERE: │                  │ FIX HERE: │
   │            │ one       │                  │ one diff  │
   │            │ sentence  │                  │           │
   │            └───────────┘                  └───────────┘
   │
   └─ if you skip the APPROVE gate, premise errors are found at VERIFY,
      where they are no longer premise errors: they are ARCHITECTURE.
      cost to fix: revert 3 PRs, or live with it for 2 years.
```

Second picture: the spec is a *contract with an executable half*, and the executable half is what makes it a spec rather than a document.

```
   ┌──────────── SPEC ─────────────┐
   │ PROSE HALF (humans read)      │  ← this is where over-specification
   │   problem, why, constraints,  │    lives. keep it SHORT.
   │   rejected alternatives        │
   ├───────────────────────────────┤
   │ EXECUTABLE HALF (CI runs)     │  ← this is what makes it a spec.
   │   named files + interfaces    │    every line here has an exit code.
   │   explicit NON-GOALS           │
   │   acceptance criteria AS       │
   │     COMMANDS                   │
   │   verification plan            │
   └───────────────────────────────┘

   A spec with no executable half is a design doc. A design doc cannot
   falsify a completion claim, which means "done" is unverifiable, which
   means you are trusting a narrative.
```

---

## How it actually works

### Why specifying beats iterating, stated precisely

Not "because planning is good." Three mechanical reasons:

**1. The error distribution is different.** A human writing code makes local errors: off-by-one, missed null, wrong operator. Those are caught by tests and by reading the diff. An agent makes *premise* errors: it assumes an interface, a boundary, an ownership model, and then builds correctly on top of it. Karpathy's catalogue is exact: the models "make wrong assumptions on your behalf and run with them without checking. They don't manage confusion, don't seek clarifications, don't surface inconsistencies, don't present tradeoffs, don't push back when they should. They're still a little too sycophantic." A premise error produces a locally excellent, globally wrong diff, and no amount of diff review finds it.

**2. Iteration cost is asymmetric in the wrong direction.** In classic development, iterating on the implementation was cheap relative to specifying, so you iterated. With an agent, generating is cheap and *reviewing* is the constraint, so each iteration cycle costs you a review, not a build. Ten iterations is ten reviews. One spec plus one review of the plan plus one review of the diff is two. The industry data says the same thing from the other end: high-AI-adoption teams merged 98% more PRs while review time grew 91% and PR size grew 154%, with 2026 figures worse (median review time up 441%, 31% more PRs merging with no review at all).

**3. It is what makes long autonomous runs possible.** This is Brooker's argument and it is the strongest one. The largest observed velocity gains are in teams that let agents run autonomously for extended periods, and an agent can only do that if it has a map rather than turn-by-turn directions, because it needs to decide, unsupervised, what to test and what good looks like. A vague prompt forces a human back into the tight loop every few minutes.

### The approval gate, mechanically

Plan mode is the gate, and it is a real control rather than a convention: Claude explores and proposes, runs read-only commands, writes a plan, and **source edits stay blocked until you approve**, enforced by the harness rather than by the model's cooperation. Enter with `Shift+Tab`, or `/plan` as a one-prompt prefix, or `claude --permission-mode plan`, or `permissions.defaultMode: "plan"` in `.claude/settings.json` to make it the project default. When the plan is ready you get four options: approve into auto mode (or accept-edits when auto is unavailable), approve with manual per-edit review, send it to Ultraplan for browser-based refinement, or keep planning with feedback. **`Ctrl+G` opens the proposed plan in your editor so you can change it directly before Claude proceeds**, which is the single most underused control in the workflow: editing the plan is cheaper and more precise than describing the edit you want.

Two honest caveats. First: **in sessions where bypass permissions are available, Claude Code does not enforce plan mode's blocks.** Claude is still instructed to plan without editing, and an edit it attempts during planning runs without prompting. So "we use plan mode" and "we run with `--dangerously-skip-permissions`" are contradictory safety claims. Second: plan mode delegates its research to the built-in Plan subagent, which **skips CLAUDE.md and the parent git status** to keep exploration cheap. That is usually fine, because the main conversation reads its results with full context, but a constraint that must shape the *research* has to be in your prompt.

Microsoft Agent Framework implements the same gate as an `agent mode provider` paired with a persistent todo provider, disableable via `DisableAgentModeProvider` / `disable_mode=True`. That is worth knowing because it means the pattern is portable: if you build your own harness, plan/execute is a supported first-class shape, not something you improvise.

### What makes a spec executable

Six properties. The first three prevent specific documented failures; the last three make "done" falsifiable.

| Property | Failure it prevents | What the failure looks like |
|---|---|---|
| **Names the files and interfaces** | Premise error / assumption propagation | Agent invents a plausible module boundary, builds three PRs on it, and you find out when it collides with the real one |
| **States explicit non-goals** | Scope creep, abstraction bloat | 1,000 lines where 100 would do; a config system nobody asked for; eleven files touched when three were named |
| **Ends with a verification step that runs** | Fail-plausible completion | "I've implemented the feature" with a green unit test that mocks the thing that is broken |
| **Acceptance criteria are commands with exit codes** | Unfalsifiable done | You cannot distinguish "works" from "the agent believes it works" |
| **Has an open-questions slot the agent must fill** | Silent wrong assumptions | An empty list on an ambiguous task is a signal about framing, not reassurance |
| **Has a rollback statement** | Irreversible mistakes | You discover in production that undoing it needs a data migration |

### The worked example: vague request → executable spec → verification plan

**The request as it actually arrives, in Slack:**

> "Search results are stale for some customers. Can you fix the indexing?"

Everything is wrong with this as agent input. "Stale" is undefined. "Some customers" is undefined. "Fix the indexing" presumes the cause. There is no target, no owner of the SLO, and no statement of what must not change. Hand it to an agent and you will get a plausible change to the indexing pipeline that may address a different staleness than the one being complained about.

**Step 1: interrogate before specifying.** Five questions, answerable in fifteen minutes with a dashboard and one conversation:

1. Stale by how much, measured how? → Source-update-to-searchable lag. p50 is 90 s; p99 is **45 min**.
2. Which customers? → Only tenants above ~500k documents. 7 of 1,240 tenants, but they are 60% of revenue.
3. What is the actual target? → Support committed **p99 under 5 minutes**. Nobody wrote it down; that is its own finding.
4. What must not change? → Query p99 (currently 180 ms) must not regress. The bulk-reindex path is used for onboarding and is out of scope.
5. Is the cause known? → Partly: the ingest worker batches by document count (1,000) with no time bound, so low-write-rate-but-large-tenants wait for a batch to fill. Unconfirmed.

Notice that question 3 produced a *written SLO that did not previously exist*, and question 5 turned "fix the indexing" into a falsifiable hypothesis. That fifteen minutes is the highest-leverage part of the whole workflow.

**Step 2: the spec.** Roughly 70 lines, and the length is the point.

```markdown
# Spec: bound index freshness for large tenants

## Problem
Source-update-to-searchable lag for tenants above ~500k documents has p99 = 45 min
against a support-committed target of p99 < 5 min. 7 of 1,240 tenants are affected;
they represent ~60% of ARR. Hypothesis (unconfirmed): `IngestBatcher` flushes on
count only (1,000 docs), so tenants with large corpora but low write rates wait for
a batch to fill. Evidence: `ingest_batch_age_seconds` p99 = 2,640 s for those tenants,
p99 = 40 s for all others.

## Goals (each maps to an acceptance criterion below)
G1. p99 source-to-searchable lag < 5 min for all tenants.
G2. Query p99 does not regress beyond 190 ms (current 180 ms, 5% budget).
G3. Indexing throughput does not drop more than 10% on the bulk path.

## Non-goals (do NOT do these; if you believe one is required, STOP and say so)
- Do NOT change the bulk-reindex path (`src/ingest/bulk.py`). Onboarding depends on it.
- Do NOT change the embedding model, chunking strategy, or vector index parameters.
- Do NOT introduce a new queue, broker, or infrastructure component.
- Do NOT add a caching layer.
- Do NOT refactor `IngestBatcher` beyond what G1 requires.
- No new config keys outside the one named below.

## Contract
- Entry point:    `src/ingest/batcher.py::IngestBatcher.should_flush`
- Interfaces:     `BatchPolicy` (NEW, in the same module). `IngestBatcher.__init__`
                  signature MAY change; `IngestBatcher.submit` MUST NOT.
- Config:         ONE new key, `ingest.max_batch_age_seconds`, default 30,
                  overridable per tenant via the existing `tenant_settings` table.
                  No migration required (JSONB column).
- Data touched:   none structurally. Read-write on `ingest_batches` as today.
- Error semantics: a flush failure MUST NOT drop documents. Existing retry contract
                  in `src/ingest/retry.py` applies unchanged. Never raise across
                  `IngestBatcher.submit`.
- Concurrency:    flush must remain safe under the existing per-tenant lock. Do NOT
                  widen the lock scope.
- Observability:  emit `ingest_batch_flush_reason{reason="count"|"age"}` and keep
                  `ingest_batch_age_seconds` a histogram, not a gauge.

## Constraints already enforced in CI (do not restate as prose; they are gates)
`ruff`, `mypy --strict`, `pytest -q`, `import-linter`, `bandit`, diff-size cap 400 lines

## Acceptance criteria (each is a command; exit code decides)
A1. `pytest tests/unit/test_batch_policy.py -q`
    Covers: flush at count boundary; flush at age boundary; flush when BOTH trip;
    no flush when neither; age measured from FIRST document in batch, not last.
A2. `pytest tests/integration/test_freshness.py -q`
    Simulates a 600k-doc tenant writing 3 docs/min; asserts observed lag < 300 s
    over a 20-minute simulated window. MUST fail on the current main branch.
A3. `scripts/bench_query.sh --iters 2000` reports p99 <= 190 ms.
A4. `scripts/bench_ingest.sh --bulk` reports throughput >= 0.9 × the recorded
    baseline in `bench/baselines/ingest.json`.
A5. `pytest tests/integration/test_no_document_loss.py -q` — kill the worker mid-flush
    500 times; assert zero documents lost and no duplicates beyond the documented
    at-least-once contract.
A6. `git diff --stat` touches ONLY: `src/ingest/batcher.py`, `src/config/schema.py`,
    and files under `tests/`. Any other path fails review.

## Rollback
`ingest.max_batch_age_seconds = 0` disables the age trigger and restores current
behaviour with no deploy. State this in the PR description. One `git revert` is
sufficient; no data migration.

## Open questions for the human (fill this in during planning; empty is suspicious)
- <agent fills in>

## Verification plan (see below — this section is not optional)
```

**Step 3: the verification plan.** This is the part most people leave as "run the tests," and it is why "done" claims are unfalsifiable. Five layers, ordered so each one can only fail for reasons the previous layer did not cover:

| Layer | What it proves | Command | Must fail on main? |
|---|---|---|---|
| **0. Reproduce** | The problem exists and we measure it correctly | `pytest tests/integration/test_freshness.py -q` | **Yes.** If it passes on main, either the bug is elsewhere or the test is wrong. This gate is non-negotiable |
| **1. Unit** | The new policy is correct at boundaries | `pytest tests/unit/test_batch_policy.py -q` | n/a (new code) |
| **2. Integration** | It works against real components, not mocks | A2, plus A5 for the durability contract | Yes for A2 |
| **3. Non-regression** | The things we promised not to break | A3 (query p99), A4 (bulk throughput) | No |
| **4. Scope** | Nothing outside the contract changed | A6 file-list check, plus `import-linter` | No |
| **5. Observability** | We can tell in production whether it worked | Query the new `flush_reason` metric in staging and confirm `reason="age"` fires for a large tenant | No |

Two things distinguish this from a test list. **The reproduce step must fail on main.** A test that passes before the fix proves nothing, and this is the single most common defect in agent-written tests: an integration test that mocks the exact dependency that is broken and therefore would pass with or without the feature. Ask of every new test: *would this fail if the feature were absent?* And **layer 5 exists because the verification is not complete when CI is green.** You have not verified an SLO fix until you can observe the SLO. The `flush_reason` metric was put in the contract for this reason, not for tidiness.

**Step 4: what the plan gate then catches.** In plan mode the agent comes back with a plan and, because the spec demanded it, an open-questions list. A realistic one:

> - `should_flush` is also called from `bulk.py::_drain`, which the spec says is out of scope. Adding an age trigger changes bulk behaviour too. Do you want the age policy disabled on the bulk path, or is a behaviour change there acceptable?
> - "Age from first document in batch" requires storing a timestamp per batch. `ingest_batches` has `created_at` but it is set on *first flush attempt*, not on batch open. Should I add a field, or is `created_at` semantics wrong today?
> - Per-tenant override via `tenant_settings` JSONB has no validation layer. A tenant with `max_batch_age_seconds = 1` would flush per document. Cap it, or accept?

Every one of those is a premise error caught for the price of one sentence. The first would have silently changed the one path the spec explicitly excluded. The second reveals an existing semantic bug in `created_at`. The third is a foot-gun that would have shipped. **None of the three is visible in a diff.** That is the entire argument for the approve gate, and this is the concrete form of it to tell in an interview.

### How this maps to TDD and to RFC/ADR

**TDD.** Structurally the same move: write the oracle before the implementation, so "done" is decided by something other than your own judgment. Three differences. The unit of specification is wider, since a spec covers interfaces, non-goals, and observability, not just a function's behaviour. The oracle is the *acceptance criteria set* rather than one failing test, and layer 0 of the verification plan is literally red-green: it must fail on main. And the consumer is different, since a test tells a human what broke while a spec tells an agent what to aim at, which is why non-goals matter here and do not exist in TDD, because a human does not need to be told not to build a config system nobody asked for. Practically: **TDD is the mechanism inside the spec**, and writing the tests yourself (or at minimum thinking through the cases before delegating) is also the best available defence against comprehension debt, because it keeps the specification in your head.

**RFC/ADR.** An ADR records a decision and its rejected alternatives *after* the discussion; a spec directs work *before* it. Brooker's framing resolves the relationship: pull design **up**, not up-front, into versioned living artifacts that the implementation flows from, staying in sync by being upstream. The practical integration is a hierarchy: an ADR owns the decision and its rationale with a long shelf life; the spec owns one bounded change and cites the ADRs it operates under; a `CLAUDE.md` pointer tells the agent to read `docs/adr/` and **stop if its plan contradicts one**. That last instruction is the cheapest architectural guardrail in the whole track, and it is one line. A spec that contradicts an ADR is either a bug in the spec or a signal the ADR needs superseding, and either way a human decides.

---

## Build it from scratch

`labs/py/28-spec-to-verified/` ships the staleness scenario above as a real repository with the bug present, and grades you on the gate you skipped.

**Part 1 (30 min): interrogate.** You get only the Slack message and access to a metrics fixture. Produce the five answers. Graded on whether you discovered that the SLO was never written down, which is the finding, not a detail.

**Part 2 (30 min): write the spec.** Against the six-property checklist. The grader checks mechanically: are files and interfaces named, are non-goals present and specific, is every acceptance criterion a command, does at least one command fail on main, is rollback stated.

**Part 3 (20 min): plan-mode-only run.** `claude --permission-mode plan` with your spec. Do not approve. Read the plan and the open questions. Score yourself on how many of the three seeded premise errors your spec surfaced. A spec with no non-goals surfaces zero, because the agent has no reason to notice it is about to touch `bulk.py`.

**Part 4 (40 min): build and verify.** Approve, let it build, then run the verification plan in order. The repo seeds three traps: an integration test that mocks the batcher (so it passes with or without the fix), a change to `bulk.py` justified as "necessary for consistency," and a completion report claiming the query benchmark ran with plausible numbers. The A6 file-scope check catches the second and running the benchmark yourself catches the third. The first is caught only by asking whether the test would fail if the feature were absent.

**Part 5 (20 min): the anti-lab.** Same feature, no spec, pure iteration, with a wall-clock cap. Compare: total tokens, number of review cycles, whether the three traps appeared anyway, and whether you finished. This part matters because sometimes iteration wins, and knowing when is the actual skill. On a bug this well-localized, iteration is often competitive; the spec's advantage shows up in the non-goals, which is where the expensive mistakes were.

**Deliverable:** a one-page table with rows for spec and no-spec, columns for wall time, review cycles, tokens, traps caught, and premise errors surfaced before code existed.

---

## How it's done in production

Two shapes, and they are not the same methodology.

**Lightweight, which is what most teams should run.** The spec is one markdown file in `docs/specs/`, 50-80 lines, in the PR that implements it. Plan mode is the default (`permissions.defaultMode: "plan"`). The acceptance criteria are the CI job. There is no separate requirements/design/tasks pipeline, no generated user stories, and no framework. This is Claude Code's native shape plus discipline, and its overhead is roughly 20 minutes per feature.

**Heavyweight frameworks.** Spec Kit's `/specify` → `/plan` → `/tasks` chain, Kiro's `requirements.md` / `design.md` / `tasks.md`. These add real value in exactly two situations: greenfield work where there is no code to derive intent from, and teams needing an auditable requirements trail. Outside those, read the cost honestly: spec-kit produced **8 files and 1,300 lines of text** for a feature that displayed the current date on a time-tracking app.

**Verification tooling.** `/verify` builds and runs your app to confirm a change does what it should, deliberately *without* falling back to tests or type checks, which is the point: a green test suite is not evidence the app works. `/run` launches and drives it. Inference gets unreliable for anything needing a database, an env file, a graphical session, or a multi-step build, so `/run-skill-generator` gets the app running from a clean environment, captures what worked, and commits it as a per-project skill at `.claude/skills/run-<name>/` that every agent in the repo then follows. Run it once per project and again when the build changes. As of v2.1.215, `/verify` and `/code-review` run only when *you* invoke them.

**Failure-mode table**

| Symptom | Cause | Fix |
|---|---|---|
| Feature "done," breaks a neighbouring team's integration | Premise error: the agent invented an interface and built on it. Skipped or rubber-stamped approve gate | Plan mode with an approve gate; spec names interfaces; require the open-questions list; `import-linter` boundary contracts in CI |
| Agent marked "verify implementation" done, having written **manual testing instructions instead of unit tests** | Verification specified as prose, not as commands. Documented in the wild with Kiro | Every acceptance criterion is a command with an exit code. Make the verification step a CI job, not a narrative |
| Green suite, broken feature | The integration test mocks the exact dependency that is broken, or asserts the implementation rather than the behaviour | Layer 0: the reproduce test **must fail on main**. Read the test diff before the code diff. Ask: would this fail if the feature were absent? |
| Review time doubled after adopting a spec framework | The design doc contains code, so you review the spec's code and then the implementation | Keep the prose half short and code-free. Specify interfaces and criteria, not implementations |
| 8 files, 1,300 lines of markdown for a trivial feature | Framework ceremony applied below its threshold | Lightweight spec for anything you can hold in your head; frameworks for greenfield and audit trails only |
| Spec and code diverged; nobody noticed | No ownership of reconciliation. In waterfall specs drift because nobody updates them; in SDD they drift because **everyone can** and nobody owns it | CODEOWNERS on `docs/specs/`; the spec is amended in the PR that changes behaviour; CI check that a PR touching named files links a spec |
| Agent touched 11 files where the spec named 3 | No non-goals, or no scope gate | Explicit non-goals; CI check failing a PR that touches files the linked spec did not name (~20 lines and the highest-value gate available) |
| Plan approved in 4 seconds, every time | The gate exists but is not being used. This is the most common real failure | Make the plan a *reviewed artifact*: `Ctrl+G` to edit it in your editor, require the open-questions list to be non-empty on ambiguous work, and treat an empty list as a signal about framing |
| "We use plan mode" but edits happen during planning | Bypass-permissions session; plan mode's blocks are not enforced there | Do not run bypass in the same workflow you claim plan mode as a control. Use hooks for gates that must survive flags |
| Specs slow the team down as the codebase grows | Diminishing returns: SDD shines greenfield, and for large existing codebases context blindness means specs miss existing functions that need updating | Shrink the spec to contract-plus-criteria; rely on the code as the source of truth for structure; do the interrogation step against real metrics, not against the spec generator |
| Agent produced an empty open-questions list on a genuinely ambiguous task | Sycophancy: it does not manage confusion, seek clarification, or surface inconsistencies unprompted | Treat empty as a red flag, not reassurance. Ask a pointed question you already know the answer to and see whether it pushes back |

---

## Tradeoffs & when NOT to use it

- **Do not spec a change you can hold entirely in your head.** A two-line fix where you can name the blast radius and verify it by reading does not need a spec, a plan gate, or a verification plan. Applying the apparatus to trivia is how the practice earns a reputation for overhead and then gets abandoned wholesale, which costs you the cases where it mattered.
- **Do not use a heavyweight framework on a mature codebase.** The reported failure is consistent: context blindness means the spec generator misses existing functions that need updating, specs contain repetitions, imaginary corner cases, and overkill refinements, and the returns diminish as the application grows. On a large existing codebase the code is a better source of truth about structure than any generated document, and the spec should shrink to contract-plus-criteria.
- **Do not let the spec contain implementation.** This is what doubles review time: if the design document has code in it, you review that code, then you review the code it produced, and you have paid twice for one artifact. Specify interfaces, error semantics, non-goals, and acceptance criteria. Let the agent choose the implementation; that is the part it is good at.
- **Do not skip the approve step, and be honest that you will want to.** It is boring, it feels like a formality, the plan usually looks fine, and it is the only gate that catches premise errors. A 4-second approval is not an approval. If you cannot commit to reading plans, do not claim plan mode as a control in an interview, because the follow-up question will find out.
- **Do not treat the spec as frozen.** That is the waterfall objection and it is only true if you make it true: waterfall locks specs through phase gates, while spec-driven development updates them through short implementation feedback loops. Brooker's version is that you do not need to, and probably should not, develop the entire specification up front. If your spec cannot change after a build reveals something, you have rebuilt the thing that failed.
- **Do not adopt it because a vendor benchmark says so.** GitHub's order-of-magnitude fewer regenerate-from-scratch cycles and AWS's 40-hours-to-8-hours case are both vendor-reported on their own tooling. Quoting them without provenance is a tell. GitHub itself calls Spec Kit an experiment.
- **The counter-argument, stated fairly, because you should be able to make it:** Zaninotto's case is that SDD is solving the wrong problem, "how do we remove developers from software development," and that it requires both business-analyst judgment to catch requirement errors and developer judgment to catch design errors, so it can only be used by people who are both, which is exactly the failure of no-code tools. His alternative is real and it works: split complex requirements into simple ones instead of translating complex requirements into complex documents, then iterate in small increments, which he demonstrated by building a working 3D sculpting tool in about 10 hours with no spec. My reconciliation is that both are correct in their regimes and the discriminator is *blast radius*, not size. Iterate freely where a mistake costs one revert. Specify where a mistake costs an interface other teams depend on, an SLO, a data model, or a migration. Getting that boundary right is the judgment being tested, and picking a side unconditionally is the wrong answer either way.

---

## Interview questions

### Q1 — Why specify before building instead of iterating with the agent?
**Testing:** whether you have a mechanical reason or a preference.
**Answer:** Three reasons, and the first is the load-bearing one. The error distribution differs: a human makes local errors that tests and diff-reading catch, while an agent makes *premise* errors, assuming an interface or a boundary and then building correctly on top of it, and that produces a locally excellent, globally wrong diff no amount of diff review finds. Second, iteration cost is asymmetric in the wrong direction now: generating is cheap and reviewing is the bottleneck, so ten iterations is ten reviews, whereas one spec plus a plan review plus a diff review is two. Third, and this is Brooker's argument, a spec is what makes long autonomous runs possible, because the agent needs a map rather than turn-by-turn directions to decide unsupervised what to test and what good looks like.
**Follow-up trap:** *"But iterating is faster for small things."* Yes, and I do it. The discriminator is blast radius, not size. If a mistake costs one revert, iterate. If it costs an interface another team depends on, an SLO, a data model, or a migration, specify. Zaninotto's counter-case is genuinely strong here, a working 3D sculpting tool built in about 10 hours with no spec at all, and the honest reading is that his regime (greenfield, single owner, reversible) is exactly where iteration dominates. Choosing per-change rather than per-team is the skill.

### Q2 — Turn "search results are stale for some customers, fix the indexing" into a spec.
**Testing:** whether you interrogate before writing, which is the actual work.
**Answer:** I do not write anything yet. Five questions: stale by how much and measured how (source-update-to-searchable lag, p50 90 s, p99 45 min); which customers (7 of 1,240 tenants, all above ~500k documents, about 60% of ARR); what the target actually is (support committed p99 under 5 minutes, which was never written down anywhere, and that is a finding); what must not change (query p99 currently 180 ms, and the bulk-reindex path is used for onboarding and is out of scope); and is the cause known (partly: the batcher flushes on document count with no time bound, evidenced by batch age p99 of 2,640 s for those tenants versus 40 s for everyone else, and that is a hypothesis, not a fact). Then the spec: problem with numbers, three goals each mapping to an acceptance criterion, six explicit non-goals, a contract naming `IngestBatcher.should_flush` and stating that `submit`'s signature must not change, six acceptance criteria that are all commands, a rollback (`max_batch_age_seconds = 0` restores current behaviour with no deploy), and an open-questions slot for the agent.
**Follow-up trap:** *"Which part of that would you cut under time pressure?"* Not the non-goals and not the acceptance-criteria commands. The non-goals are what stop the agent "helpfully" changing the bulk path, which is the one path I explicitly excluded and the one a plausible refactor would touch. The commands are what make "done" falsifiable at all. What I would cut is the prose: the problem paragraph can be three sentences, the goals can be one line each, and the rationale can live in an ADR I link to. The failure mode of a rushed spec is not that it is short, it is that it is short on the executable half and long on the narrative.

### Q3 — What does the approve gate catch that review doesn't?
**Testing:** the central claim of the module.
**Answer:** Premise errors, which are structurally invisible in a diff. Concretely, from the staleness spec: the agent's plan surfaced that `should_flush` is also called from the bulk path the spec excluded, so an age trigger would silently change behaviour there; that "age from first document in batch" is not implementable because `created_at` is set on first flush attempt rather than batch open, which is an existing semantic bug; and that a per-tenant override with no validation would let a tenant set the age to 1 second and flush per document. Each of those costs one sentence to fix at the plan gate. None of them is visible in a code review, because the code implementing the wrong premise is correct code. By the time you would notice, you are three PRs deep and the invented boundary is load-bearing.
**Follow-up trap:** *"How do you make sure the gate is real rather than a rubber stamp?"* Three mechanics. Make plan mode the default with `permissions.defaultMode: "plan"` so it is not a thing you remember to do. Use `Ctrl+G` to open the plan in my editor and edit it directly, because editing is cheaper and more precise than describing an edit and it forces me to actually read it. And require the spec's open-questions section to be filled, treating an empty list on ambiguous work as a red flag rather than reassurance, because the models do not manage confusion, seek clarification, or surface inconsistencies unprompted. If I approve in four seconds, I do not have a gate, I have a habit.

### Q4 — Design the verification plan for that spec.
**Testing:** whether verification is a phase or an afterthought.
**Answer:** Five layers, ordered so each can only fail for reasons the previous one did not cover. Layer 0, reproduce: an integration test asserting observed lag under 300 s for a simulated 600k-document tenant writing 3 docs/min, and it **must fail on main**. Layer 1, unit: the new batch policy at boundaries, including the case where both count and age trip, and that age is measured from the first document in the batch. Layer 2, integration: the freshness test against real components, plus a durability test that kills the worker mid-flush 500 times and asserts no document loss. Layer 3, non-regression: query p99 at or under 190 ms against the 180 ms baseline, and bulk throughput at or above 0.9× the recorded baseline, because those were promises in the goals. Layer 4, scope: the diff touches only the three named paths, plus `import-linter`. Layer 5, observability: query the new `flush_reason` metric in staging and confirm `reason="age"` actually fires for a large tenant.
**Follow-up trap:** *"Why does the reproduce test have to fail on main?"* Because a test that passes before the fix proves nothing, and this is the single most common defect in agent-written tests: an integration test that mocks the exact dependency that is broken, so it is green with or without the feature. The question to ask of every new test is whether it would fail if the feature were absent. And layer 5 is the other half of the same idea: CI being green is not verification of an SLO fix. I have not verified a freshness SLO until I can observe freshness, which is why the metric was in the contract rather than added as a nicety.

### Q5 — Is spec-driven development just waterfall?
**Testing:** whether you can handle the standard objection without being defensive.
**Answer:** No, and the distinction is precise: waterfall locks specs through phase gates, while spec-driven development updates them through short implementation feedback loops. Brooker's formulation is the one I use, that it is not about pulling designs *up-front* but pulling designs *up*, into explicit versioned living artifacts the implementation flows from, staying in sync by being upstream of implementation for most changes, and that you do not need to and probably should not develop the whole specification in advance. But I would concede the failure mode is real and common: if your spec cannot change after a build reveals something, you have rebuilt the thing that failed, and every framework that generates a requirements-then-design-then-tasks chain makes that easier to do accidentally because the documents have dependencies.
**Follow-up trap:** *"So what's the strongest version of the waterfall criticism?"* Not the process shape, it is the *role* argument. Zaninotto's point is that SDD tries to answer "how do we remove developers from software development," and to catch requirement errors you must be a business analyst while to catch design errors you must be a developer, so it only works for people who are both, which is the same trap no-code tools fell into. Plus his concrete costs: spec-kit producing 8 files and 1,300 lines for displaying a date, review time doubling because the design doc contains code you must review before the code you must also review, and 80% of your time spent reading rather than thinking. My answer to that is to keep the prose half short and code-free and let the executable half do the work, but the criticism lands hard against the heavyweight frameworks specifically.

### Q6 — How does this relate to TDD?
**Testing:** whether you can connect it to something you already do, which is the fastest way to show it is not cargo cult.
**Answer:** Structurally the same move, write the oracle before the implementation so done is decided by something other than my judgment, with three differences. The unit is wider: a spec covers interfaces, non-goals, and observability, not one function's behaviour. The oracle is the acceptance-criteria set rather than a single test, and layer 0 of the verification plan is literally red-green because it must fail on main. And the consumer differs: a test tells a human what broke, a spec tells an agent what to aim at, which is why non-goals exist in a spec and not in TDD, since a human does not need to be told not to build a config system nobody asked for. So TDD is the mechanism *inside* the spec.
**Follow-up trap:** *"If you have TDD, do you need the spec?"* For a bounded change to existing behaviour, often not, and I would say so rather than defend the ceremony. What TDD does not give you is the negative space and the contract: a failing test does not tell the agent which files are in scope, that `submit`'s signature must not change, or that the bulk path is off limits, and those omissions are where the expensive mistakes came from in the worked example. There is also a comprehension argument for keeping TDD regardless: writing the tests myself, or at least thinking through the cases before delegating, keeps the specification in my head, which is the main defence against reviewing code I could no longer write.

### Q7 — Your team adopted a spec framework and velocity dropped. Diagnose.
**Testing:** whether you can diagnose an overcorrection, which is the failure mode of people who read this module and get enthusiastic.
**Answer:** Most likely three things at once. Ceremony below its threshold: a framework that generates a requirements/design/tasks chain applied to features you could hold in your head, which is how you get 1,300 lines of markdown for a date display. Double review: the design document contains code, so people review that code, then review the implementation, and review time is the bottleneck already. And diminishing returns on a mature codebase: the generator has context blindness, so it misses existing functions that need updating and pads with imaginary corner cases, and the reviewers spend their time hunting basic mistakes hidden in verbose expert-sounding prose. Fix: keep the framework only for greenfield work and audit-trail requirements, replace it elsewhere with a 50-80 line spec in the implementing PR, and strip code out of the prose half.
**Follow-up trap:** *"How would you know which features need a spec?"* A written threshold rather than judgment per case, because judgment per case degrades to never. Mine: a spec is required if the change touches an interface another team consumes, an SLO, a data model or migration, a security or trust boundary, or if reverting it needs more than one `git revert`. Everything else is plan-mode-and-go. That rule is testable against last quarter's incidents, which is how I would calibrate it: if an incident came from a change that my threshold would have exempted, the threshold is wrong.

### Q8 — Specs drift from code. What's your answer?
**Testing:** whether you know the specific mechanism, which differs from waterfall.
**Answer:** The mechanism is different from waterfall and that matters: in waterfall specs drift because nobody updates them, in spec-driven development they drift because *everyone can* update them and nobody owns reconciling concurrent changes. So it is a governance gap, not a discipline gap, and the open questions are concrete: who reviews spec changes, when do conflicting updates get resolved, and what happens when an agent updates the spec with something the developer disagrees with. My answer is three mechanisms. The spec is amended in the PR that changes the behaviour, never separately, so drift requires actively lying in a reviewed diff. CODEOWNERS on `docs/specs/` so someone must approve. And a CI check that a PR touching the spec's named files must link the spec, which is about twenty lines and also catches scope leakage.
**Follow-up trap:** *"What about the parts of a spec you can't check mechanically?"* Then they should not be phrased as invariants. The rule I apply to context files applies here: if a claim is not worth asserting in CI, it is a preference rather than a constraint, and it should read that way or be deleted. Concretely, "query p99 must not regress beyond 190 ms" is an invariant with a benchmark; "the design should feel simple" is a preference and belongs in a review conversation. Brooker's mix-of-formality point is the mature version: use prose where prose is adequate, structured forms like RFC 2119 or EARS where precision matters, and exact statements in something like TLA+ only where you genuinely need them, which is rare.

### Q9 — Plan mode is on. Is it enforced?
**Testing:** the caveat, which most candidates miss.
**Answer:** In a normal session, yes: Claude explores and proposes, runs read-only commands, and source edits stay blocked until you approve, enforced by the harness rather than by the model's cooperation, with approval switching the session into whichever permission mode you chose. **But in sessions where bypass permissions are available, Claude Code does not enforce plan mode's blocks.** Claude is still instructed to plan without editing, and an edit it attempts during planning runs without prompting. So "we use plan mode" and "we run with `--dangerously-skip-permissions`" are contradictory claims, and if a team says both, they do not have the gate they think they have.
**Follow-up trap:** *"How do you get a gate that survives someone passing a flag?"* Move it below the mode layer. `PreToolUse` hooks fire regardless of permission mode, with exit 2 or `permissionDecision: "deny"`, and when several hooks match the most restrictive answer wins in the order deny, defer, ask, allow. `permissions.deny` in managed settings cannot be overridden by a user. And the real backstop is CI, which does not care what mode anyone was in: the diff-size cap, the spec-file-scope check, and the acceptance-criteria jobs run on the PR. General principle from the whole track: a mode is a default, a hook is a constraint, a CI gate is a wall.

### Q10 — The agent says it verified the feature. How do you check?
**Testing:** whether you know that completion claims are unfalsifiable by default.
**Answer:** I do not read the claim, I run the commands. There is a documented case of an agent marking a "verify implementation" task done having written **manual testing instructions instead of a single unit test**, and the general class is fail-plausible reporting, where absent or polluted evidence becomes confident fabrication rather than silence. So: every acceptance criterion is a command whose exit code decides, the verification step is a CI job rather than a narrative, the spec requires pasted command output, and I spot-check by running one myself. Then two reads in order: the test diff before the code diff, asking of each new test whether it would fail if the feature were absent, and the file list against the spec's named files.
**Follow-up trap:** *"What if the pasted output is fabricated?"* Assume it can be, which is why pasted output is a convenience and CI is the control. The verification that counts runs in an environment the agent does not author: the PR job, on a clean checkout, producing artifacts I can open. That is also why `/verify` is designed to build and run the app rather than falling back to tests and type checks, and why the useful pattern is `/run-skill-generator` recording the actual launch recipe as a committed per-project skill so every agent follows the same reproducible path instead of rediscovering it and describing what it thinks would happen.

### Q11 — Where does an ADR fit?
**Testing:** whether you can integrate this with existing architecture practice rather than replacing it.
**Answer:** Different shelf lives and different jobs. An ADR owns a decision and its rejected alternatives, lives for years, and is the thing I have to be able to defend when the constraint that drove it has been forgotten. A spec directs one bounded change, cites the ADRs it operates under, and is closed when the change ships. The integration that actually changes agent behaviour is one line in `CLAUDE.md`: read `docs/adr/` before proposing a change to a module boundary, and **stop if your plan contradicts an ADR**. That is the cheapest architectural guardrail available. If a spec contradicts an ADR, that is either a bug in the spec or a signal the ADR should be superseded, and a human decides which.
**Follow-up trap:** *"Can the agent write the ADR?"* It can draft it, and that is genuinely useful because enumerating the alternatives is most of the work. But I own it, and the test I apply to myself is whether I can defend the *rejected* alternatives without re-reading the document. If I cannot, I delegated the decision rather than the drafting, and in six months I will not be able to defend it. That is also the boundary I would not cross under any deadline: implementation mistakes are cheap and local, but a wrong service boundary or consistency model is paid for over years by people who were not in the conversation, and the specific danger is not a bad answer, it is a plausible one delivered confidently by something that does not surface tradeoffs unprompted.

### Q12 — Sell me on skipping the spec.
**Testing:** whether you can argue the other side, which is where calibration shows.
**Answer:** For a bounded reversible change with a clear oracle, iteration wins and I would say so. Concretely: a bug with a reproducing test, in one file, where the blast radius is nameable and `git revert` undoes it. Writing a spec there costs 20 minutes to save nothing, and the ceremony tax is real, because a practice applied indiscriminately gets abandoned wholesale and then you lose it for the cases that mattered. Zaninotto's Lean-style loop is the honest articulation: identify the riskiest assumption, design the simplest experiment to test it, build that, and repeat, with short and sometimes vague instructions, on the reasoning that when implementing simple ideas is cheap, building in small increments is the fastest way to converge. He built a working 3D sculpting tool that way in about ten hours.
**Follow-up trap:** *"Then when does that approach break?"* At the boundary where a mistake stops being local. Three specific breaks. When the change touches an interface someone else consumes, because you find out from their broken build, not yours. When correctness depends on unwritten invariants, because the agent cannot intuit them and its confidence scales inversely with context understanding. And when the fix is a migration or a data-model change, because there is no cheap revert. The tell in practice is when I catch myself saying "and also fix" for the third time in one session: that means I did not know what I was asking for, which is the condition a spec exists to resolve.

---

## Red flags that fail you

- Describing your workflow with no gate: "I tell it what to do and check the output."
- A spec with no non-goals.
- Acceptance criteria written as prose instead of commands.
- No reproduce step, or one that passes on main.
- Approving plans without reading them, and not knowing that this is the common failure.
- Claiming plan mode as a control while running bypass permissions.
- Putting implementation code in the spec.
- Applying a heavyweight framework to a mature codebase.
- No answer for spec drift, or answering "keep the docs updated."
- Treating verification as "the tests pass."
- Accepting a completion claim without running anything.
- Quoting vendor SDD benchmarks without provenance.
- Insisting specs are always right, or that iteration is always right.

## Cheat card

```
THE LOOP   PLAN → [APPROVE] → BUILD → [VERIFY] → SHIP
  approve gate catches PREMISE errors (wrong interface/boundary/problem)
    → INVISIBLE IN A DIFF. cost to fix here: one sentence.
    → cost to fix at verify: revert 3 PRs, or 2 years of architecture.
  verify gate catches BEHAVIOUR errors (wrong output, perf, contract)

WHY SPEC > ITERATE
  1 error distribution: humans make LOCAL errors, agents make PREMISE errors
  2 iteration now costs a REVIEW, not a build (review is the bottleneck:
    +98% PRs, +91% review time, +154% PR size; 2026: +441% review time,
    31% merged with NO review)
  3 a spec is what enables LONG AUTONOMOUS RUNS (map, not turn-by-turn)
  Karpathy: models "make wrong assumptions on your behalf and run with them
    without checking… don't surface inconsistencies… too sycophantic"

SIX PROPERTIES OF AN EXECUTABLE SPEC
  names files + interfaces        → prevents premise error
  EXPLICIT NON-GOALS              → prevents scope creep / abstraction bloat
  ends with a verification step that RUNS → prevents fail-plausible completion
  acceptance criteria ARE COMMANDS with exit codes → makes "done" falsifiable
  open-questions slot the agent fills → EMPTY IS SUSPICIOUS
  rollback statement              → prevents irreversible mistakes

VERIFICATION PLAN, 5 LAYERS
  0 REPRODUCE   MUST FAIL ON MAIN. non-negotiable.
  1 unit        boundaries, incl. both-conditions case
  2 integration real components, not mocks + durability/crash test
  3 non-regression  the things you PROMISED not to break (with baselines)
  4 scope       diff touches ONLY the named files + import-linter
  5 OBSERVABILITY  can you SEE it working in staging/prod? green CI ≠ verified SLO
  ask of EVERY new test: WOULD THIS FAIL IF THE FEATURE WERE ABSENT?

APPROVE GATE MECHANICS
  Shift+Tab / /plan / --permission-mode plan / permissions.defaultMode:"plan"
  four options: auto · manual-approve-edits · Ultraplan · keep planning
  Ctrl+G EDITS THE PLAN IN YOUR EDITOR  ← most underused control
  plan mode delegates research to the Plan subagent, which SKIPS CLAUDE.md + git
  ⚠ BYPASS-PERMISSIONS SESSIONS DO NOT ENFORCE PLAN MODE'S BLOCKS
  MS Agent Framework: same shape as an `agent mode provider` (plan interactive /
    execute autonomous) + persistent todo provider

MAPS TO
  TDD   same move (oracle first). wider unit · criteria SET not one test ·
        layer 0 IS red-green · non-goals exist here and not in TDD
        TDD is the mechanism INSIDE the spec (also the comprehension-debt defence)
  ADR   ADR owns the DECISION + rejected alternatives, years. spec owns ONE change,
        cites ADRs, closes on ship. CLAUDE.md: "read docs/adr/, STOP if your plan
        contradicts one" ← cheapest architectural guardrail in the track
  Brooker: not pulling design UP-FRONT, pulling design UP — explicit, versioned,
    LIVING artifacts; specs stay in sync by being UPSTREAM of implementation

THE HONEST FAILURE MODES
  over-specification: spec-kit → 8 FILES / 1,300 LINES for "display the date"
  DOUBLE CODE REVIEW: design doc contains code → review it, then review the code
  "80% of your time reading instead of thinking"
  FALSE SECURITY: agent marked "verify implementation" DONE having written MANUAL
    TESTING INSTRUCTIONS instead of a single unit test
  CONTEXT BLINDNESS: generator misses existing functions needing updates
  DIMINISHING RETURNS: shines greenfield, "mostly unusable" on large legacy
  DRIFT: waterfall = nobody updates. SDD = EVERYONE CAN and nobody owns
    reconciliation → CODEOWNERS on docs/specs/, amend in the implementing PR,
    CI check linking PR files to the spec
  SKIPPING APPROVE: a 4-second approval is not an approval

THE THRESHOLD (write it down; judgment-per-case degrades to never)
  SPEC REQUIRED if it touches: an interface another team consumes · an SLO ·
    a data model / migration · a security or trust boundary · or needs >1 git revert
  otherwise: plan-mode-and-go

TOOLING  /verify builds+runs the app, deliberately WITHOUT falling back to tests
    or type checks · /run drives it · /run-skill-generator records the recipe as a
    committed .claude/skills/run-<name>/ · v2.1.215+: /verify and /code-review only
    run when YOU invoke them
  Spec Kit: 93k+ stars, v0.8.7 (2026-05-07), 30+ agents, GITHUB CALLS IT AN
    EXPERIMENT · Kiro: requirements.md/design.md/tasks.md
  vendor claims (label them): GitHub ~10× fewer regenerate-from-scratch cycles;
    AWS 40h feature → <8h human time
```

## Sources

- [Spec Driven Development isn't Waterfall](https://brooker.co.za/blog/2026/04/09/waterfall-vs-spec.html) — Marc Brooker (AWS, agentic AI safety and policy), 2026-04-09; "not about pulling designs up-front, it's about pulling designs up," specs as explicit versioned living artifacts staying in sync by being upstream, the mix-of-formality point (free-form, RFC 2119, EARS, Lean, TLA+), and the argument that specs are what enable long autonomous agent runs; accessed 2026-07-26
- [Spec-Driven Development: The Waterfall Strikes Back](https://marmelab.com/blog/2025/11/12/spec-driven-development-waterfall-strikes-back.html) — François Zaninotto, 2025-11-12; the 8-files/1,300-lines spec-kit example, context blindness, markdown madness, systematic bureaucracy, double code review, the false-sense-of-security case where the agent marked verify-implementation done with manual testing instructions instead of unit tests, diminishing returns on large codebases, the "80% reading instead of thinking" figure, the business-analyst-and-developer role critique, and the Lean-style alternative with the 10-hour 3D sculpting tool; accessed 2026-07-26
- [Understanding Spec-Driven Development: Kiro, spec-kit, and Tessl](https://martinfowler.com/articles/exploring-gen-ai/sdd-3-tools.html) — Birgitta Böckeler, martinfowler.com; the comparative anatomy of the three toolchains; accessed 2026-07-26
- [Permission modes](https://code.claude.com/docs/en/permission-modes) — plan mode semantics, the four approve options, `Ctrl+G` to edit the plan, `defaultMode: "plan"`, `showClearContextOnPlanAccept`, and the explicit statement that bypass-permissions sessions do not enforce plan mode's blocks; accessed 2026-07-26
- [Extend Claude with skills](https://code.claude.com/docs/en/skills) — the `/run`, `/verify`, and `/run-skill-generator` bundled skills, `/verify` deliberately not falling back to tests or type checks, and the v2.1.215 change making `/verify` and `/code-review` user-invoked only; accessed 2026-07-26
- [Create custom subagents](https://code.claude.com/docs/en/sub-agents) — the built-in Plan subagent used during plan mode, and its skipping of CLAUDE.md and git status; accessed 2026-07-26
- [Agent Harnesses — Microsoft Learn](https://learn.microsoft.com/en-us/agent-framework/agents/harness) — the agent mode provider's plan (interactive, clarifying questions, todo list, approval before significant work) and execute (autonomous) phases, and the persistent todo provider; page updated 2026-07-08, accessed 2026-07-26
- [GitHub Spec Kit](https://github.com/github/spec-kit) — the `/specify` → `/plan` → `/tasks` chain, and GitHub's own framing of it as an experiment; accessed 2026-07-26
- [Kiro: specs](https://kiro.dev/docs/specs/) — the `requirements.md` / `design.md` / `tasks.md` structure; accessed 2026-07-26
- [9 Best AI Tools for Spec-Driven Development in 2026](https://www.marktechpost.com/2026/05/08/9-best-ai-tools-for-spec-driven-development-in-2026-kiro-bmad-gsd-and-more-compare/) — the 2026 tooling landscape, Spec Kit's 93,000+ stars and v0.8.7 (2026-05-07) with 30+ agent support, and the vendor-reported GitHub and AWS Kiro outcome claims; accessed 2026-07-26
- [Putting Spec Kit Through Its Paces: Radical Idea or Reinvented Waterfall?](https://blog.scottlogic.com/2025/11/26/putting-spec-kit-through-its-paces-radical-idea-or-reinvented-waterfall.html) — Scott Logic, 2025-11-26; a hands-on account of the "sea of markdown" and weak iteration/legacy-code story; accessed 2026-07-26
- [Spec-Driven Development Isn't Waterfall Unless You're Using It That Way](https://yuvalyeret.com/blog/spec-driven-development-isnt-waterfall-unless-youre-using-it-that-way/) — Yuval Yeret; the "creates learning versus pretends learning is no longer needed" framing and the spec-ownership/drift argument; accessed 2026-07-26
- [The 80% Problem in Agentic Coding](https://addyo.substack.com/p/the-80-problem-in-agentic-coding) — Addy Osmani, 2026-01-28; assumption propagation, the Karpathy quote on wrong assumptions and sycophancy, and the review-burden figures; accessed 2026-07-26
- [Key Takeaways from the DORA Report 2025](https://www.faros.ai/blog/key-takeaways-from-the-dora-report-2025) — Faros AI; +98% PRs merged, +91% review time, +154% PR size, and the 2026 figures (median review time +441%, 31% merging with no review); accessed 2026-07-26

## Changelog
- 2026-07-26 — created
