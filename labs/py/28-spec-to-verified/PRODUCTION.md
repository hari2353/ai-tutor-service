# Production notes — spec-driven development with agents

## What you actually use

| Role | Lightweight (most teams) | Heavyweight |
|---|---|---|
| Spec | `docs/specs/<change>.md`, 50-80 lines, in the implementing PR | GitHub Spec Kit (`/specify` → `/plan` → `/tasks`), AWS Kiro (`requirements.md` / `design.md` / `tasks.md`) |
| Approve gate | Claude Code plan mode (`permissions.defaultMode: "plan"`, `Ctrl+G` to edit the plan) | Plan as a reviewed artifact with CODEOWNERS |
| Verify | CI job per acceptance criterion — every criterion is a command with an exit code | `/verify` (builds and runs the app, deliberately not falling back to tests), `/run`, per-project run skills |
| Drift control | Spec amended in the same PR; CI check that a PR touching named files links the spec | CODEOWNERS on spec dirs, spec-diff review |

Your `verify()` is the acceptance criteria of a real spec turned into a CI job. Your `run_spec()` loop is the agent loop with the human removed — which is exactly why the guardrails carry all the weight.

## The failure taxonomy of agent-built code

The three failures this lab models mechanically, in rising order of cost:

1. **Unverifiable requirements** (your no-criteria default-fail). The agent marked "verify implementation" done having written *manual testing instructions* instead of a single unit test. Documented in the wild with Kiro. Fix: every acceptance criterion is a command with an exit code; the verification step is a CI job, not a narrative.
2. **Vacuous passes** (your never-mentioned criterion). The integration test mocks the exact dependency that is broken — green suite, broken feature. Fix: layer 0 of the verification plan — the reproduce test **must fail on main**. Ask of every new test: *would this fail if the feature were absent?*
3. **Hallucinated requirements** (your `"hallucinated"` key — the real risk this lab's guardrail models). The agent confidently built on a premise: invented an interface, built three PRs on it, and the neighbouring team's integration breaks in production. The diff is locally excellent and globally wrong — **no amount of diff review finds it**, because the code implementing the wrong premise is correct code. Fix: the spec names files and interfaces (so there is a right answer to check against), explicit non-goals (so the agent has a reason not to touch `bulk.py`), and mechanical scope gates (~20 lines of CI: a PR touching files the linked spec did not name fails review).

## The loop, with the human back in

Your `run_spec()` feeds failures back for up to 3 rounds. Production inserts the human at exactly two gates:

- **APPROVE** (after plan, before build) — catches *premise* errors: wrong interface, wrong boundary, invented module. Cost to fix here: one sentence. Skip it and premise errors arrive at VERIFY as *architecture*: revert 3 PRs or live with it for 2 years.
- **VERIFY** (after build) — catches *behaviour* errors: wrong output, missed edge case, broken contract. Cost: one diff.

The approve gate is the one everybody skips and the only one that catches premise errors. Make it real: plan mode as default, `Ctrl+G` to edit the plan in your editor, and require the spec's open-questions slot to be filled — an empty list on ambiguous work is a red flag, not reassurance, because models don't manage confusion or push back unprompted.

## What production adds over your loop

- **CI as the verifier, not the self-report.** Your `implementation` dict is the builder's self-report — production does not trust it. Each criterion becomes a command (`pytest ...`, `scripts/bench_query.sh`, `git diff --stat` scope check) whose exit code decides. The agent cannot mark done what CI can falsify.
- **Coverage gates.** A criterion passing without executing the code it names is a vacuous pass. Coverage floors catch some of it.
- **Mutation tests** (`mutmut`, Stryker) catch the rest: flip a `True` in a passing implementation — if the report stays green, the criterion never discriminated anything. Your stretch goal 3 is a hand-rolled mutation score for criteria.
- **Observability as a criterion.** CI green is not verification of an SLO fix — you haven't verified freshness until you can *observe* freshness. Layer 5: query the new metric in staging.
- **Spec ownership.** In waterfall specs drift because nobody updates them; with agents they drift because *everyone can* and nobody owns reconciliation. CODEOWNERS on `docs/specs/`, the spec amended only in the PR that changes behaviour, and a CI check tying touched files to the linked spec.

## The 3 questions an interviewer asks after you describe this

1. *"Isn't this just waterfall?"* — No: waterfall locks specs through phase gates; SDD updates them through short implementation feedback loops. Brooker's framing: pull design *up*, not *up-front*, into versioned living artifacts the implementation flows from. Concede the failure mode: if your spec can't change after a build reveals something, you rebuilt the thing that failed.
2. *"A spec framework gave us 8 files and 1,300 lines of markdown for a date display. Diagnose."* — Ceremony below its threshold. Discriminator is blast radius, not size: iterate where a mistake costs one revert; specify where it costs an interface another team depends on, an SLO, a data model, or a migration.
3. *"Your builder's self-report passed everything. Now what?"* — That is this lab's hallucination guard inverted: never score the report, score the exit codes. Layer 0 must fail on main, or you are trusting a narrative.
