# Weekend 10 — Harness Engineering, Loop Engineering, and Operating as the Architect

This weekend decides interviews because it's the closing argument: it asks whether you understand that the model is a small, replaceable piece of a much larger system you're responsible for engineering and reviewing — the harness around the loop, and your own judgment around the agent writing the code.

## Harness Engineering: The 15-Component Model

**30-sec:** A harness is everything in an agent except the model — loop, instruction assembly, context builder, tool registry, permission engine, sandbox, state store, compactor, approval manager, traces. `Agent = Model + Harness`, and the harness is where almost all the engineering and failures live. **The model never calls a tool** — it emits a structured request; the harness validates schema, resolves permissions, executes inside a boundary the model can't modify, truncates, and injects the result back as an observation.

**Membership test (necessary+sufficient, only 4 of the 15 components):** a loop (reason/act/observe at runtime) · a tool interface that alters the environment · active content-aware context management (not just size truncation) · one control independent of model cooperation (a step cap passes; logging a failure doesn't).

**Authority hierarchy (anti-injection):** provider > org > product > project (CLAUDE.md) > directory > user task > runtime reminders > tool observations > untrusted retrieved content. Retrieved instructions are data, never policy — compaction can silently launder authority unless classified during summarisation.

**Maturity ladder:** 0 answer-only → 1 retrieval → 2 drafting → 3 approval-gated → 4 policy-bounded autonomous → 5 long-running goal worker. Promote only when evals show the simpler level is insufficient.

**Bitter-lesson tax:** every component encodes an assumption the model can't do X — and assumptions expire as models improve (one team ran 5 harness refactors in 6 months; another deleted 80% of its tools and got *better* results). Build to delete.

## Loop Engineering: Budgets, Compaction Triggers, Stop Conditions

**30-sec:** The loop is forty lines; the controls are two thousand — Claude Code's production loop body is 1,421 lines with nine `continue` points because 413s, cache invalidation, and 500-turn sessions are all real. Loop engineering is: hierarchical budgets that are *reserved*, not just checked; compaction triggers ordered cheapest-first with correct token accounting; the full nine-condition stop set including a progress detector measuring state delta, not argument-hash repeats; and resumability via a typed event log, never a pickled process.

**Two token counts — get this wrong and every budget bug follows:** context_tokens (per-agent, in the window now, drives compaction, shrinks) vs billed_tokens (per-run, everything ever paid, drives cost, only grows). Compaction lowers the first and *raises* the second — the summarizer call itself costs money.

**Compaction cascade, cheapest first — 4 of 5 stages cost zero API calls:**

| Stage | Trigger | Reversible | API cost |
|---|---|---|---|
| Tool-result budget | >50K chars | yes | free |
| Snip stale scaffolding | — | yes | free |
| Microcompact (cache edits) | — | yes | free |
| Context collapse | ~90% util | yes | free |
| Autocompact | ~87% util | **no** | 1 call |

**Nine stop conditions:** verified natural termination · local step cap · tree step cap · billed-token budget · cost budget · absolute deadline · no-progress · compaction circuit breaker · external interrupt.

**Progress = state delta, not arg-hash repeats.** Signal: dirty file hashes, tests passing, todos closed, artifacts. K=4 nudge → K=7 shrink the tool set → K=10 stop and escalate.

**Reliability math at 12 steps:** bare 0.90¹²=28% → +errors-as-observations 0.94¹²=48% → +resume (checkpoint-and-resume, the biggest single win) → 0.976¹²=75%. A better model alone (0.98¹²=79%) doesn't remove 503s, turn-40 overflow, or false success claims.

## The Claude Architect Model: Operating as the Architect, Not the Typist

**30-sec:** Agentic coding didn't remove the bottleneck, it moved it — writing code stopped being the constraint, and verification, review, and security became it. The Principal-level job is now specification, decomposition, delegation boundaries, and review discipline, with architectural judgment kept explicitly in-house. Three practices carry the most weight: plan-mode-first (draft and approve a plan before any write tool is available), self-contained specs (files/interfaces named, out-of-scope stated, ends with an e2e verification step), and the recognition that **instructions are not enforcement** — a rule in CLAUDE.md is a recommendation, a rule in a hook/linter/CI gate is a constraint. The visible cost: high-AI-adoption teams merged 98% more PRs while review time grew 91% and PR size grew 154%; the 2026 numbers are worse still.

**Three levels of control:** L1 instruction (CLAUDE.md — a recommendation) → L2 reminder (a skill re-states it — higher compliance, still probabilistic) → L3 enforcement (hook/lint/CI/type check — an actual constraint). Anything you'd be upset to find violated belongs at L3.

**Five phases:** research → plan (human gate) → execute → review (human gate) → ship. Plan mode means write tools are *physically unavailable*, not a promise.

**Agent-sized work, five checks (2 failures = decomposition is wrong):** bounded blast radius, contract fixed in advance, machine-checkable "done," one `git revert` undoes it, fits one context window.

**Review order:** test diff → file list → code. Watch for: assumption propagation (not catchable at diff review — this is why plan mode exists), tests passing while wrong (mocking the broken dependency), silent bypass (`# type: ignore`, unsafe casts), swallowed errors (bare except, discarded results), hallucinated APIs on thin surfaces, abstraction bloat, dead code, scope leakage.

**Comprehension debt is the one that ends careers:** generation ≠ discrimination — review silently becomes rubber-stamping. If reading doesn't scale with the agent's output, you're not engineering, you're hoping. Mitigation: TDD, ask for justification, hand-write some of it, own a subsystem deeply, treat "I don't understand" as a stop.

## If you remember nothing else

1. `Agent = Model + Harness` — the model proposes a tool call, the harness disposes: validates, permits, executes, truncates, and returns it as an observation.
2. A harness needs exactly four things to qualify at all: a loop, a tool interface that alters the world, active context management, and one control independent of model cooperation.
3. Context tokens drive compaction and shrink; billed tokens drive cost and only grow — compaction lowers one while raising the other.
4. Checkpoint-and-resume is the single largest reliability lever in the whole loop: 0.94¹²=48% jumps to 0.976¹²=75% once you add resumability.
5. A rule in CLAUDE.md is a recommendation; a rule in a hook, linter, or CI gate is a constraint — anything non-negotiable belongs at L3, not L1.
6. Plan mode works because write tools are physically unavailable, not because the model promised to ask first.
7. Assumption propagation is not catchable at diff review — that's the entire justification for a human gate at the plan stage, before code exists.
8. Comprehension debt is the real failure mode of agentic coding: if your reading doesn't scale with the agent's output, you're hoping, not engineering.

## Numbers table

| Fact | Value |
|---|---|
| Claude Code production loop | 1,421-line while body, 9 named continue points |
| Compaction cascade cost | 4 of 5 stages cost zero API calls |
| Stop conditions | 9 total |
| Reliability at 12 steps, bare / +errors-as-obs / +resume | 28% / 48% / 75% |
| Reliability with a better model alone | 79% (doesn't fix 503s or overflow) |
| No-progress escalation ladder | K=4 nudge, K=7 shrink tools, K=10 stop |
| DORA 2025: PRs merged / review time / PR size | +98% / +91% / +154% |
| DORA 2026: review time / no-review PRs | +441% / 31% merge with no review |
| METR RCT (Jul 2025) | agentic coding measured 19% *slower*, predicted +24% |
| Control levels | L1 instruction, L2 reminder, L3 enforcement |
| Agent-sized work checks | 5 checks, 2 failures = decomposition is wrong |
