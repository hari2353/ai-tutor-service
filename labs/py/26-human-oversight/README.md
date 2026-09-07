# Lab 26: Human Oversight — Gates, Escalation, Accountability

**Track:** T07 Agentic AI · **Time:** 2.5h · **XP:** 50
**Module:** `T07-human-oversight`

**You will build:** an approval-gate system with risk-ladder routing, TTL expiry, freshness windows for destructive actions, an append-only audit log, and accountability traces.

**You will be able to answer:** *"Where do you put the human in an agent loop — and how do you prove later who approved what?"*

## Setup

```bash
cd labs/py/26-human-oversight
pip install pytest
```

## The spec

1. **`Action(name, args, risk)`** — risk in `read_only | side_effect | destructive`.
2. **`ApprovalGate(clock, ttl=300)`** — `submit(action)` → ticket id; `approve(ticket, approver_id)`; `reject(ticket)`; `pending()` list. A ticket older than TTL default-denies on the next gate touch (expired tickets never execute).
3. **`EscalationPolicy(gate, clock, freshness=300)`** — `route(action, approver=None)`: read_only executes immediately; side_effect queues into a batch digest (`digest()` lists them; `approve_all(approver_id)`); destructive executes only if `approver` approved *this* action within the freshness window — an approval older than the window denies.
4. **`AuditLog`** — `append(t, event, actor, detail)`; `entries()` read-only view; `tamper(index, ...)` raises `TamperError` (it exists only to prove append-only).
5. **`accountability_trace(log, action_id)`** — reconstruct the chain: submitted → approver → executed; `None`/incomplete when an action executed without approval.

## Run the tests

```bash
pytest tests/ -q          # against starter/ — FAILS. Make them pass.
```

Reference: `pytest tests/ -q --solution`

## Stretch goals

1. **Quorum** — destructive requires 2 distinct approvers; single approval denies.
2. **Rate-limited escalation** — one human can only approve N destructive actions per hour (burnout is a real attack surface).
3. **Signed audit** — hash-chain entries (each entry embeds the previous hash); tampering anywhere invalidates the chain.
