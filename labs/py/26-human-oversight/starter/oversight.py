"""Human oversight: approval gates, escalation ladder, append-only audit, accountability."""
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
    def __init__(self, name, args, risk, action_id=None):
        """risk in {read_only, side_effect, destructive}. action_id: optional id."""


class ApprovalGate:
    def __init__(self, clock, ttl=300):
        """Tickets expire (default-deny) ttl seconds after submission."""

    def submit(self, action):
        """Return a ticket id."""

    def approve(self, ticket_id, approver_id):
        raise NotImplementedError

    def reject(self, ticket_id):
        raise NotImplementedError

    def pending(self):
        """Live (non-expired, undecided) tickets as a list of dicts."""

    def execute_if_approved(self, ticket_id):
        """True iff approved and not expired. Expired tickets return False."""


class EscalationPolicy:
    def __init__(self, gate, clock, freshness=300):
        """freshness: seconds an approval stays valid for destructive actions."""

    def route(self, action, approver=None):
        """read_only -> execute immediately (return 'executed').
        side_effect -> queue in batch digest (return 'queued').
        destructive -> execute only if approver given and approved within the
        freshness window (return 'executed'); else 'denied'."""

    def digest(self):
        """Queued side_effect actions."""

    def approve_all(self, approver_id):
        """Approve the digest queue; returns count approved."""


class TamperError(Exception):
    pass


class AuditLog:
    def __init__(self):
        """Append-only store."""

    def append(self, t, event, actor, detail=None):
        raise NotImplementedError

    def entries(self):
        """Read-only list of dicts {t, event, actor, detail}."""

    def tamper(self, index, **changes):
        """Must ALWAYS raise TamperError — exists to prove append-only."""


def accountability_trace(log, action_id):
    """Return the chain for an action_id: {submitted_at, approver, executed_at}
    or None if incomplete (e.g. executed without a matching approval)."""
