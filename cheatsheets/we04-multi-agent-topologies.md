# Multi-Agent Topologies (and When NOT To)

> Sprint weekend 4 · source: `curriculum/07-agentic-ai/12-multi-agent-topologies.md`

```
TWO AXES GENERATE EVERYTHING
  who decides next: central (supervisor) vs distributed (swarm)
  what crosses:     full history vs distilled summary
  → orchestrator + DISTILLED read-only subagents is the shape that usually wins

FIVE TOPOLOGIES
  SUPERVISOR    one router · all decisions in one trace · +1 LLM call per hop
                4 workers ≈ 9 model calls (4 route + 4 work + 1 synthesise)
  HIERARCHICAL  supervisor of supervisors · split ONLY on permission/model/ownership
                cost: ~1.5s routing latency PER LEVEL before any work starts
  SWARM         peer handoff · Command(goto=X, graph=Command.PARENT)
                faster/cheaper · no single place to look · OpenAI SDK sends FULL history
  BLACKBOARD    typed+versioned slots, optimistic concurrency, write journal
                failure = LOST UPDATE (both writes "succeed", one vanishes)
  DEBATE        N agents × (R+1) rounds · 2.1-3.4x tokens for ≈ or WORSE accuracy
                sycophantic conformity · contextual fragility · consensus collapse
                → prefer SELF-CONSISTENCY (independent samples + vote) or ONE VERIFIER

THE FIVE COSTS (recite these unprompted)
  1 routing errors      0.92³ ≈ 78% over 3 hops, silent, confident wrong specialist
  2 handoff loss        full history = no isolation + N× cost; summary = undetectable loss
  3 latency mult.       coordination is sequential; fan-out p50 ≈ branches' p90
  4 cost mult.          Anthropic's own system ≈ 15x tokens of a normal chat
  5 debugging           failure lives in the SEAM; MAST needed a taxonomy for 1,600 traces

THE PLAIN STATEMENT
  A single agent with good tools beats a poorly decomposed MAS almost always.
  MAST (arXiv 2503.13657, 1600+ traces / 7 frameworks, 14 modes / 3 categories):
    system design issues · inter-agent misalignment · task verification
    → failures are DESIGN, not model capability

WHAT JUSTIFIES SPLITTING (need ≥1)
  1 parallel read-heavy subtasks, big intermediate → small return (40k in, 1.5k out)
  2 mandatory context isolation
  3 different PERMISSION/trust tier      ← candidates forget; interviewers love
  4 different model/latency tier
  5 independent deployment ownership     ← A2A: LF, 1.0 Apr 2026, 150+ orgs
  6 untrusted content quarantine         ← tool-less summariser reads the raw page
  NOT reasons: 30 tools · the org chart · the diagram looks tidy

NOT A FIX FOR TOOL BLOAT
  better descriptions → remove overlap → group → tool search.  THEN maybe agents.

SINGLE-WRITER PRINCIPLE
  one agent mutates; others contribute intelligence, not actions
  parallel writes needed? workers PROPOSE, orchestrator validates + applies in order

THE EVIDENCE ON BOTH SIDES
  Anthropic Research: +90.2% vs single-agent Opus 4 · ~15x tokens
    tokens alone explain ~80% of perf variance ← so part of the "win" is just spending
  Cognition "Don't Build Multi-Agents" (Jun 2025): single-threaded + compression model
  synthesis: parallel BREADTH w/ independent branches → split
             sequential DEPTH w/ shared evolving context → one agent

DECISION ORDER
  one prompt → workflow/DAG → ONE AGENT (default) → fix tools/context
  → orchestrator + read-only subagents → add a VERIFIER → prove with an eval
  no single-agent baseline = no architecture decision, just a bigger bill
```
