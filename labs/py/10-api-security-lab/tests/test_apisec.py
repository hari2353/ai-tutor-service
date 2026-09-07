"""Lab 10 tests: BOLA, mass assignment, rate limiting, enumeration."""
import pytest


# ------------------------------------------------------------------ (1) BOLA / IDOR
def test_bola_vulnerable_read_of_others_order(api):
    """alice walks the order ids and reads bob's order 101 — the API checks
    her session but never that the ORDER is hers."""
    a, s = api
    order = a.get_order_vulnerable(s["alice"], user_id=1, order_id=101)
    assert order["user_id"] == 2, "alice just read bob's order — BOLA works"


def test_bola_fixed_rejects_cross_user_read(api):
    a, s = api
    with pytest.raises(PermissionError):
        a.get_order_fixed(s["alice"], user_id=1, order_id=101)


def test_bola_fixed_allows_own_order(api):
    a, s = api
    order = a.get_order_fixed(s["alice"], user_id=1, order_id=100)
    assert order["id"] == 100 and order["user_id"] == 1


def test_bola_sequential_ids_make_walking_trivial(api):
    """The structural enabler: dense sequential ids mean an attacker just
    increments. (Fix is authorization, not UUIDs — but note both.)"""
    a, s = api
    seen = []
    for oid in (100, 101):
        try:
            seen.append(a.get_order_vulnerable(s["alice"], user_id=1, order_id=oid)["id"])
        except LookupError:
            pass
    assert seen == [100, 101]


def test_unauthenticated_call_rejected(api):
    a, s = api
    with pytest.raises(PermissionError):
        a.get_order_fixed("forged-token", user_id=1, order_id=100)
    with pytest.raises(PermissionError):
        a.get_order_vulnerable("forged-token", user_id=1, order_id=100)


# ------------------------------------------------------------------ (2) mass assignment
def test_mass_assignment_escalation(api):
    """The bug: PATCH binds the WHOLE body. is_admin rides along."""
    a, s = api
    assert a.users[1]["is_admin"] is False
    a.update_user_vulnerable(s["alice"], user_id=1,
                             body={"display_name": "A", "is_admin": True})
    assert a.users[1]["is_admin"] is True, "privilege escalation via PATCH body"


def test_mass_assignment_fixed_ignores_is_admin(api):
    a, s = api
    a.update_user_fixed(s["alice"], user_id=1,
                        body={"display_name": "A", "is_admin": True})
    assert a.users[1]["is_admin"] is False, "is_admin was client-settable"
    assert a.users[1]["display_name"] == "A"      # allowed fields still work


def test_mass_assignment_fixed_cannot_update_others(api):
    a, s = api
    with pytest.raises(PermissionError):
        a.update_user_fixed(s["alice"], user_id=2, body={"email": "x@y.z"})


# ------------------------------------------------------------------ (3) rate limiter
def test_rate_limiter_hits_limit_at_6th_request_in_a_minute(R):
    c = R.FakeClock(t=0.0)
    rl = R.TokenBucketLimiter(clock=c, capacity=5.0, refill_rate=5.0 / 60.0)
    for _ in range(5):
        assert rl.allow("ip-1") is True            # burst of 5 allowed
    assert rl.allow("ip-1") is False               # 6th within the minute: denied


def test_rate_limiter_recovers_after_refill(R):
    c = R.FakeClock(t=0.0)
    rl = R.TokenBucketLimiter(clock=c, capacity=5.0, refill_rate=5.0 / 60.0)
    for _ in range(5):
        assert rl.allow("ip-1") is True
    assert rl.allow("ip-1") is False
    c.advance(60.0)                               # a full minute: bucket refilled
    assert rl.allow("ip-1") is True


def test_rate_limiter_keys_are_independent(R):
    c = R.FakeClock(t=0.0)
    rl = R.TokenBucketLimiter(clock=c, capacity=2.0, refill_rate=0.0)
    assert rl.allow("ip-1") and rl.allow("ip-1")
    assert rl.allow("ip-1") is False
    assert rl.allow("ip-2") is True                # different key, own bucket


def test_rate_limiter_partial_refill(R):
    c = R.FakeClock(t=0.0)
    rl = R.TokenBucketLimiter(clock=c, capacity=5.0, refill_rate=5.0 / 60.0)
    for _ in range(5):
        rl.allow("ip-1")
    c.advance(12.0)                               # 12s * 5/60 = exactly 1 token
    assert rl.allow("ip-1") is True
    assert rl.allow("ip-1") is False              # only 1 had refilled


def test_rate_limiter_rejection_spends_nothing(R):
    c = R.FakeClock(t=0.0)
    rl = R.TokenBucketLimiter(clock=c, capacity=1.0, refill_rate=0.0)
    assert rl.allow("k") is True
    assert rl.allow("k") is False
    assert rl.allow("k") is False                  # still empty — nothing leaked


# ------------------------------------------------------------------ (4) enumeration
def test_enumeration_vulnerable_leaks_a_user_exists_oracle(api):
    a, _ = api
    assert a.login_vulnerable("alice", "WRONG") == "wrong password"
    assert a.login_vulnerable("nobody-here", "WRONG") == "user not found"
    # the two messages differ — a free oracle for credential stuffing


def test_enumeration_fixed_is_uniform(api):
    a, _ = api
    assert a.login_fixed("alice", "WRONG") == "invalid credentials"
    assert a.login_fixed("nobody-here", "WRONG") == "invalid credentials"


def test_enumeration_fixed_still_logs_real_users_in(api):
    a, _ = api
    assert a.login_fixed("alice", "pw") == "ok"
    assert a.login_fixed("nobody-here", "pw") == "invalid credentials"


def test_enumeration_fixed_dummy_work_runs_for_missing_users(api):
    """The timing placeholder: the missing-user path must do comparable
    password work as the wrong-password path (hashing), not return early."""
    import time as _t
    a, _ = api
    t0 = _t.perf_counter()
    for _ in range(50):
        a.login_fixed("nobody-here", "WRONG")
    t_missing = _t.perf_counter() - t0
    t0 = _t.perf_counter()
    for _ in range(50):
        a.login_fixed("alice", "WRONG")
    t_wrongpw = _t.perf_counter() - t0
    # same order of magnitude — no early-return gap (allow 10x slack in CI)
    assert t_missing >= t_wrongpw * 0.1


# ------------------------------------------------------------------ clock
def test_fake_clock(R):
    c = R.FakeClock(t=100.0)
    assert c.now() == 100.0
    c.advance(1.0)
    assert c.now() == 101.0
