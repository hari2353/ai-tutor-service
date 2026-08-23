# Harness Engineering: The 15-Component Model, Everything Except the Model

> Sprint weekend 10 · source: `curriculum/07-agentic-ai/25-harness-engineering.md`

```
AGENT = MODEL + HARNESS         harness = everything except the model
  CPU=model · RAM=context window · OS=harness · app=agent        (Schmid, Jan 2026)
  Model PROPOSES (structured tool_call). Harness DISPOSES.

NECESSARY & SUFFICIENT (arXiv 2606.10106, Jun 2026) - membership test
  T1 loop (reason/act/observe at runtime)   T2 tool iface that ALTERS environment
  T3 active context mgmt (content-aware, NOT size truncation)
  T4 >=1 control independent of model cooperation (log fails; step cap passes)
  memory/verify/observability = specializations, NOT a 5th condition
  guardrail = PART of harness (limits); harness enables. part-whole, not siblings

THE 15 COMPONENTS
  1 instruction mgr   2 context builder   3 model adapter   4 tool registry
  5 permission engine 6 execution engine  7 state store     8 memory/retrieval
  9 compactor        10 planner/goal     11 skill registry 12 MCP/connectors
 13 approval mgr     14 trace+eval       15 sandbox/execution boundary
  NOT required: multi-agent · fine-tuning · specific model · UI

TOOL-CALL CONTRACT (order is load-bearing)
  resolve+visibility → SCHEMA VALIDATE → PERMISSION (allow|deny|ask)
    → ask? checkpoint & return (human may take a day) → idem key if mutating
      → SANDBOX exec w/ timeout → persist >50K chars + 2KB preview → observation
  every rejection = OBSERVATION with remediation, never an exception
  tool dependency fails → observation | harness bug → crash loudly

AUTHORITY HIERARCHY (anti-injection)
  provider > org > product > project(CLAUDE.md) > dir > user task
    > runtime reminders > tool observations > UNTRUSTED RETRIEVED CONTENT
  retrieved instructions are DATA, not policy
  compaction LAUNDERS authority unless you classify (real Claude Code gap)

MVP HARNESS (10) then sequence
  adapter · deterministic ctx builder · narrow registry · strict schema
  runtime perms · structured obs · step+cost budget · traces · compact-if-needed · evals
  manual loop → tools → perms → structured obs → budgets → tracing
    → planning → ctx/memory → compaction → skills/MCP → goal loop → subagents

MATURITY 0 answer-only · 1 retrieval · 2 drafting · 3 approval-gated
          4 policy-bounded autonomous · 5 long-running goal worker
  promote only when evals show the simpler level insufficient

NUMBERS
  harness-only: rank 30 → top-5 Terminal Bench 2.0 (no model swap)
  statewright: 2/10 → 10/10 SWE-bench subset by shrinking per-phase tool space
  Azure SRE Agent: Intent Met 45% → 75% (files+grep beat 100+ bespoke tools)
  subagents process 67% fewer tokens than skills (multi-domain)
  skill routing 73% → 85% from negative examples in manifests
  harness config alone = 5+ pp benchmark swing (Anthropic Trends 2026)
  0.85^10 ≈ 20% · 0.95^10 ≈ 60%  → state store is priority #1

BITTER LESSON TAX
  every component = an assumption the model can't do X; assumptions EXPIRE
  Manus: 5 harness refactors / 6 months · Vercel: deleted 80% of tools, got better
  models can OVERFIT to a harness → build to delete
  "deny-list is a UX pre-filter, not a security boundary" (MS Agent Framework docs)

WHEN NOT TO
  single-turn → no harness · steps known → write the pipeline
  hours/days + exactly-once → Temporal/Step Functions, not a hand-rolled state store
```
