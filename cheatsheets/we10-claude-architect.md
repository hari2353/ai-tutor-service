# The Claude Architect Model: Operating as the Architect, Not the Typist

> Sprint weekend 10 · source: `curriculum/28-ai-assisted-architecture/09-claude-architect.md`

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
