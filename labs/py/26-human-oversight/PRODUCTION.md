# Production notes — human oversight

## Where this actually runs

LangGraph's `interrupt()` + checkpointer is exactly the approval gate pattern:
the graph halts, state persists, a human resumes with `Command(resume=...)`.
Production agent platforms (AgentCore, Copilot Studio approvals, custom HITL
UIs) add identity, quorum, and signed trails.

## What production adds

| Component | Production version |
|---|---|
| ApprovalGate | Durable queue (DB-backed), resumable across process death, SLA timers |
| Freshness windows | Mandatory for financial/destructive ops: re-auth (step-up) + re-check preconditions on resume, not just expiry |
| Approver identity | SSO-bound, recorded with the approval — "someone clicked yes" is not accountability |
| Audit log | Append-only store (event sourcing), hash-chained, often WORM storage for regulated industries |
| Escalation ladder | Risk taxonomies per tool; batch digests for low-risk side effects to keep humans in the loop without becoming the bottleneck |

## Failure modes

| Symptom | Cause | Fix |
|---|---|---|
| Human approves, agent executes wrong thing later | No freshness window / precondition re-check | Approve-the-current-world: re-validate args against live state at execution |
| Approval queue becomes a rubber stamp | Alert fatigue (everything is destructive) | Honest risk ladder; batch digests for the routine |
| "Who approved this?" unanswerable | Audit log separate from execution | Trace must be derivable from the log alone — test it |
