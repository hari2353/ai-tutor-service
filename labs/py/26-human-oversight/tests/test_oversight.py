import pytest


def test_read_only_auto_executes(O):
    clock = O.FakeClock()
    gate = O.ApprovalGate(clock)
    pol = O.EscalationPolicy(gate, clock)
    a = O.Action("ls", {}, "read_only")
    assert pol.route(a) == "executed"


def test_side_effect_queues_to_digest(O):
    clock = O.FakeClock()
    gate = O.ApprovalGate(clock)
    pol = O.EscalationPolicy(gate, clock)
    pol.route(O.Action("write_cache", {"k": 1}, "side_effect"))
    pol.route(O.Action("write_cache", {"k": 2}, "side_effect"))
    assert len(pol.digest()) == 2
    assert pol.approve_all("hari") == 2
    assert pol.digest() == []


def test_destructive_denied_without_approval(O):
    clock = O.FakeClock()
    gate = O.ApprovalGate(clock)
    pol = O.EscalationPolicy(gate, clock)
    a = O.Action("rm", {"path": "/data"}, "destructive")
    assert pol.route(a, approver="nobody") == "denied"


def test_destructive_executes_with_fresh_approval(O):
    clock = O.FakeClock()
    gate = O.ApprovalGate(clock)
    pol = O.EscalationPolicy(gate, clock, freshness=300)
    a = O.Action("rm", {"path": "/data"}, "destructive")
    pol.approve_destructive(a, "hari")
    assert pol.route(a) == "executed"


def test_destructive_stale_approval_denied(O):
    clock = O.FakeClock()
    gate = O.ApprovalGate(clock)
    pol = O.EscalationPolicy(gate, clock, freshness=300)
    a = O.Action("rm", {"path": "/data"}, "destructive")
    pol.approve_destructive(a, "hari")
    clock.advance(301)
    assert pol.route(a) == "denied"


def test_ttl_expiry_default_denies(O):
    clock = O.FakeClock()
    gate = O.ApprovalGate(clock, ttl=120)
    pol = O.EscalationPolicy(gate, clock)
    a = O.Action("write_cache", {"k": 1}, "side_effect")
    tid = gate.submit(a)
    clock.advance(121)
    # expired ticket can neither be approved nor executed
    with pytest.raises(ValueError):
        gate.approve(tid, "hari")
    assert gate.execute_if_approved(tid) is False
    assert gate.pending() == []


def test_gate_approve_execute_flow(O):
    clock = O.FakeClock()
    gate = O.ApprovalGate(clock)
    a = O.Action("write_cache", {"k": 1}, "side_effect")
    tid = gate.submit(a)
    assert gate.pending()[0]["ticket"] == tid
    gate.approve(tid, "hari")
    assert gate.execute_if_approved(tid) is True
    assert gate.pending() == []


def test_gate_reject(O):
    clock = O.FakeClock()
    gate = O.ApprovalGate(clock)
    tid = gate.submit(O.Action("write_cache", {}, "side_effect"))
    gate.reject(tid)
    assert gate.execute_if_approved(tid) is False


def test_audit_log_append_and_read(O):
    log = O.AuditLog()
    log.append(10, "submitted", "agent", {"action_id": "a1"})
    log.append(12, "approved", "hari", {"action_id": "a1"})
    es = log.entries()
    assert len(es) == 2
    assert es[0]["event"] == "submitted"
    # returned entries are copies — mutating them must not affect the log
    es[0]["event"] = "hacked"
    assert log.entries()[0]["event"] == "submitted"


def test_audit_log_tamper_raises(O):
    log = O.AuditLog()
    log.append(1, "submitted", "agent", None)
    with pytest.raises(O.TamperError):
        log.tamper(0, event="deleted")


def test_accountability_trace_full_chain(O):
    log = O.AuditLog()
    log.append(10, "submitted", "agent", {"action_id": "a1"})
    log.append(11, "approved", "hari", {"action_id": "a1"})
    log.append(12, "executed", "agent", {"action_id": "a1"})
    tr = O.accountability_trace(log, "a1")
    assert tr["approver"] == "hari"
    assert tr["approved"] is True
    assert tr["submitted_at"] == 10
    assert tr["executed_at"] == 12


def test_accountability_trace_incomplete_when_unapproved(O):
    log = O.AuditLog()
    log.append(10, "submitted", "agent", {"action_id": "a2"})
    log.append(12, "executed", "agent", {"action_id": "a2"})   # executed w/o approval
    tr = O.accountability_trace(log, "a2")
    assert tr is not None
    assert tr["approved"] is False
    assert tr["approver"] is None


def test_accountability_trace_missing_returns_none(O):
    log = O.AuditLog()
    assert O.accountability_trace(log, "zzz") is None
