"""Human oversight: approval gates, escalation ladder, append-only audit, accountability."""
import itertools
import time


class SystemClock:
    def now(self):
        return time.time()


class FakeClock:
    def __init__(self, t=0):
        self._t = t

    def now(self):
        return self._t

    def advance(self, dt):
        self._t += dt


class Action:
    _ids = itertools.count(1)

    def __init__(self, name, args, risk, action_id=None):
        assert risk in ("read_only", "side_effect", "destructive")
        self.name = name
        self.args = args
        self.risk = risk
        self.id = action_id or f"a{next(Action._ids)}"


class ApprovalGate:
    def __init__(self, clock, ttl=300):
        self.clock = clock
        self.ttl = ttl
        self._tickets = {}
        self._next = itertools.count(1)

    def _expire(self):
        now = self.clock.now()
        for tid in list(self._tickets):
            tk = self._tickets[tid]
            if tk["state"] == "pending" and now - tk["submitted_t"] > self.ttl:
                tk["state"] = "expired"

    def submit(self, action):
        tid = f"t{next(self._next)}"
        self._tickets[tid] = dict(action=action, state="pending",
                                 approver=None, submitted_t=self.clock.now(),
                                 decided_t=None)
        return tid

    def approve(self, ticket_id, approver_id):
        self._expire()
        tk = self._tickets[ticket_id]
        if tk["state"] != "pending":
            raise ValueError(f"ticket {ticket_id} is {tk['state']}")
        tk["state"] = "approved"
        tk["approver"] = approver_id
        tk["decided_t"] = self.clock.now()

    def reject(self, ticket_id):
        self._expire()
        tk = self._tickets[ticket_id]
        if tk["state"] != "pending":
            raise ValueError(f"ticket {ticket_id} is {tk['state']}")
        tk["state"] = "rejected"
        tk["decided_t"] = self.clock.now()

    def pending(self):
        self._expire()
        return [dict(ticket=tid, action=td["action"].name, risk=td["action"].risk)
                for tid, td in self._tickets.items() if td["state"] == "pending"]

    def execute_if_approved(self, ticket_id):
        self._expire()
        tk = self._tickets[ticket_id]
        return tk["state"] == "approved"


class EscalationPolicy:
    def __init__(self, gate, clock, freshness=300):
        self.gate = gate
        self.clock = clock
        self.freshness = freshness
        self._digest = []
        self._approvals = {}     # action_id -> (approver, approved_at)

    def approve_destructive(self, action, approver_id):
        """Record a human's approval of a specific action (fresh from now)."""
        self._approvals[action.id] = (approver_id, self.clock.now())

    def route(self, action, approver=None):
        if action.risk == "read_only":
            return "executed"
        if action.risk == "side_effect":
            self._digest.append(action)
            return "queued"
        # destructive: needs a recorded approval inside the freshness window
        appr = self._approvals.get(action.id)
        if appr is None:
            return "denied"
        who, when = appr
        if self.clock.now() - when > self.freshness:
            return "denied"
        return "executed"

    def digest(self):
        return list(self._digest)

    def approve_all(self, approver_id):
        n = len(self._digest)
        self._digest.clear()
        return n


class TamperError(Exception):
    pass


class AuditLog:
    def __init__(self):
        self._entries = []

    def append(self, t, event, actor, detail=None):
        self._entries.append(dict(t=t, event=event, actor=actor, detail=detail))

    def entries(self):
        return [dict(e) for e in self._entries]

    def tamper(self, index, **changes):
        raise TamperError("audit log is append-only")


def accountability_trace(log, action_id):
    submitted = None
    approval = None
    executed = None
    for e in log.entries():
        d = e.get("detail") or {}
        if d.get("action_id") != action_id:
            continue
        if e["event"] == "submitted":
            submitted = e
        elif e["event"] == "approved":
            approval = e
        elif e["event"] == "executed":
            executed = e
    if submitted is None or executed is None:
        return None
    return {
        "submitted_at": submitted["t"],
        "approver": approval["actor"] if approval else None,
        "executed_at": executed["t"],
        "approved": approval is not None,
    }
