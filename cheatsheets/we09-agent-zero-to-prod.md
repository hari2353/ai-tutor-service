# Zero → Production: The Complete Multi-Agent System, End to End

> Sprint weekend 9 · source: `curriculum/07-agentic-ai/24-agent-zero-to-prod.md`

```
SHAPE:  15% agent, 85% platform.  Three state boundaries own every hard problem:
  MODEL boundary stateless   → context rebuilt each turn, cost QUADRATIC in turns
  PROCESS boundary unreliable → durable state in Postgres, not Python
  TRUST boundary porous      → label provenance, bound damage in CODE not prompt

SCOPING (6 answers before code)
  unit of work · verifiable success signal · blast radius · latency contract
  cost ceiling per unit · principal AND tenant (two axes; conflating = leak)
  + write the NON-GOALS down

SINGLE vs MULTI: one agent unless (a) real parallelism (b) context isolation
  (subagents ~67% fewer tokens, multi-domain) (c) different permission scopes
  tool COUNT is not a trigger; measured selection degradation is
  0.95^10≈60%  0.95^20≈36%   adding an agent adds handoff steps

HARNESS BUILD ORDER (each later one undebuggable without earlier)
  adapter → deterministic ctx builder → narrow registry → strict schema
  → runtime perms → structured obs → step+cost budget → OTel → compact-if-needed → evals

TOOL CONTRACT (order is load-bearing)
  resolve+phase → SCHEMA VALIDATE → PERMIT(allow|deny|ask) → HARNESS-INJECT TENANT SCOPE
  → budget precheck → idem key if mutating → exec w/ timeout → persist>50k + 2KB preview
  every rejection = OBSERVATION w/ remediation.  NO bare `except Exception`.

LANGGRAPH + AsyncPostgresSaver
  autocommit=True, row_factory=dict_row · .setup() in a MIGRATION not pod boot
  thread_id = tenant:user:session, deterministic, <255 chars, IS the isolation boundary
  InMemorySaver + multi-worker = silent cross-user corruption
  write 8-15 ms · ~40 KB · 4.2/session → ~1.3 GB/day → partition daily, prune 7/30d
  interrupt() re-executes the node on resume → no side effects before the interrupt

COST (Atlas)  $0.0348/call → $0.162/session → ~$39k/mo @ 8k sessions/day
  POC said $0.055. Gap = turns re-sending retrieval + a 5th verify call + cache miss
  levers: prompt cache on FROZEN prefix (61% cached, -34% cost) > routing
    (RouteLLM 95% quality @ 26% strong calls, ~48% cheaper; prod reports 40-85%)
    > fewer output tokens > fewer steps > semantic cache LAST (20-45% real hit rate)
  ENFORCE AT THE GATEWAY. No provider creds in the worker. NetworkPolicy egress.
  In-agent budget = advisory. Reconcile nightly; >3% drift = accounting bug.

EVAL GATE (blocking, on prompts/tools/graph/model-pin)
  deterministic >=0.95 no regression · trajectory F1 >=0.85 · judge >=4.1 and ±0.15
  p95 cost <= $0.45 · 22-case critical-safety subset 100%
  140 cases, ~11 min / 8 workers, ~$9, T=0, 3 seeds median
  outcome-only evals pass 20-40% MORE cases than trajectory evals → they overstate readiness
  sample 10 live cases/week in, or the golden set drifts and passes while prod degrades

OTEL: span/node + child/model-call + child/tool-call, gen_ai.* (still DEVELOPMENT,
  moved to its own repo v1.42.0 2026-06-12 → PIN IT)
  #1 attribute = HASH OF ASSEMBLED STATIC PREFIX (catches drift AND cache destruction)
  alert p99 not mean: steps/run · cost/run · deny-rate by rule_id · checkpoint p99

HITL: interrupt → checkpoint → return slot → approval row w/ expiry → resume
  REVALIDATE preconditions in the same txn as the write · expire at 24 h
  rejection = observation, not error
  approve_rate >95% && median review <10 s ⇒ RUBBER STAMP, narrow the rule

K8S: NO GPU in the agent tier (model is an API call; vLLM is a separate pool)
  2 vCPU/4 GiB, ~50 concurrent runs, 8-15% CPU → KEDA on QUEUE DEPTH, never HPA-on-CPU
  terminationGracePeriodSeconds 600 + preStop drain · PDB 60% · scale-down stabilise 300 s
  readiness must NOT probe the LLM provider (else a blip drains your fleet)

CANARY: bad prompts return 200 OK → score QUALITY, not CPU/5xx
  immutable content-addressed prompts in a registry; rollback = pointer flip
  5% stratified sticky 24 h → 25% → 100%; auto-rollback on judge -3pp (n>=400),
  block rate 1.5×, unresolved citations >2%, escalation +5pp, cost 1.25×, p95 1.2×
  ONE CHANGE PER CANARY (Anthropic Apr 2026: 3 harness changes = a week of bisecting)

PHASES / GATES
  POC 2w:  1 agent, RO tools, MemorySaver, 20 cases by hand
           GATE: >=60% + one real user changed behaviour
  MVP 6w:  LangGraph+PG, tool contract, budgets, OTel, 1 HITL write, 60 advisory
           GATE: p95 25s, $0.35/session, 0 unapproved writes, EVAL GATE GOES BLOCKING
  PROD 8w: perms engine, provenance, compaction, memory, ledger, registry+canary,
           140 blocking, runbooks, SLOs
           GATE: 2 weeks at SLO + security review + signed cost forecast
  structural change at each gate: state process→DB, then enforcement app-code→boundary

TWO WEEKS INSTEAD OF TWO MONTHS
  CUT: multi-agent · memory · compaction (cap 8 steps) · perms DSL (allow-list + HITL
       on all writes) · semantic cache · registry+canary · judge scorers · output rail
       beyond schema+citations · autoscaling · per-tenant attribution · provider failover
  KEEP: PG checkpointer · tool contract · gateway budget + no worker creds · OTel w/
        prompt hash + pinned model · 20 blocking goldens incl. cross-tenant + unapproved
        write · HITL on writes · harness-injected tenant scope · the cost-spike runbook

WHEN NOT TO BUILD THIS
  steps known → pipeline · one prompt suffices → one prompt
  40 uses/day internal tool → 20 goldens, a cost cap, traces. Not a platform.
  no articulable success signal → go get one first
```
