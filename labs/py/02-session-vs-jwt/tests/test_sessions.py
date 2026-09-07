"""Lab 02 tests. No sleeps — everything runs on FakeClock."""
import pytest


# ------------------------------------------------------------------ clock
def test_fake_clock(R):
    c = R.FakeClock(t=1000.0)
    assert c.now() == 1000.0
    c.advance(30.0)
    assert c.now() == 1030.0


# ------------------------------------------------------------------ session store
def test_session_create_returns_opaque_unguessable_id(R):
    store = R.SessionStore(clock=R.FakeClock())
    sid = store.create("alice")
    assert isinstance(sid, str) and len(sid) >= 32
    assert sid != store.create("alice"), "sequential/guessable session ids are a vuln"


def test_session_validate_returns_record(R):
    store = R.SessionStore(clock=R.FakeClock(), ttl=100.0)
    sid = store.create("alice", {"cart": [1, 2]})
    s = store.validate(sid)
    assert s is not None and s["user_id"] == "alice"
    assert s["data"]["cart"] == [1, 2]


def test_session_expiry_via_fake_clock(R):
    c = R.FakeClock()
    store = R.SessionStore(clock=c, ttl=60.0, sliding=False)
    sid = store.create("alice")
    assert store.validate(sid) is not None
    c.advance(61.0)
    assert store.validate(sid) is None, "expired session still validates"


def test_session_sliding_window_renews_on_activity(R):
    c = R.FakeClock()
    store = R.SessionStore(clock=c, ttl=100.0, sliding=True)
    sid = store.create("alice")
    for _ in range(10):                     # active user keeps touching it
        c.advance(80.0)                     # less than ttl each time
        assert store.validate(sid) is not None
    c.advance(80.0)                         # still fine — window slid
    assert store.validate(sid) is not None
    c.advance(101.0)                        # now truly idle past ttl
    assert store.validate(sid) is None


def test_session_non_sliding_hard_expiry(R):
    c = R.FakeClock()
    store = R.SessionStore(clock=c, ttl=100.0, sliding=False)
    sid = store.create("alice")
    c.advance(50.0)
    assert store.validate(sid) is not None  # activity does not extend a fixed window
    c.advance(51.0)
    assert store.validate(sid) is None


def test_session_revocation_is_instant(R):
    """THE session-store superpower: logout kills the very next request."""
    c = R.FakeClock()
    store = R.SessionStore(clock=c, ttl=3600.0)
    sid = store.create("alice")
    assert store.validate(sid) is not None
    assert store.revoke(sid) is True
    assert store.validate(sid) is None, "revoked session still validates — logout broken"
    assert store.revoke(sid) is False      # second revoke: nothing left to revoke


def test_session_revoke_is_per_session(R):
    """Revoking one user's session must not nuke everyone's."""
    store = R.SessionStore(clock=R.FakeClock())
    a = store.create("alice")
    b = store.create("bob")
    store.revoke(a)
    assert store.validate(a) is None
    assert store.validate(b) is not None


# ------------------------------------------------------------------ stateless tokens
def test_jwt_issue_validate_roundtrip(R):
    tok = R.StatelessToken(secret="0123456789abcdef0123456789abcdef", clock=R.FakeClock(t=1000.0))
    t = tok.issue("alice", ttl=300.0)
    claims = tok.validate(t)
    assert claims["sub"] == "alice"
    assert claims["exp"] > claims["iat"] >= 1000


def test_jwt_expiry_via_fake_clock(R):
    c = R.FakeClock(t=1000.0)
    tok = R.StatelessToken(secret="0123456789abcdef0123456789abcdef", clock=c)
    t = tok.issue("alice", ttl=300.0)
    assert tok.validate(t)["sub"] == "alice"
    c.advance(301.0)
    with pytest.raises(Exception):
        tok.validate(t)


def test_jwt_tampering_fails(R):
    import jwt as pyjwt
    tok = R.StatelessToken(secret="0123456789abcdef0123456789abcdef", clock=R.FakeClock(t=1000.0))
    t = tok.issue("alice")
    with pytest.raises(pyjwt.PyJWTError):
        tok.validate(t + "x")              # crude tamper: different signature


def test_jwt_cannot_be_revoked_the_honest_test(R):
    """THE stateless-token cost: 'logout' does nothing to a valid JWT.
    This is not a bug to fix — it is the tradeoff you must be able to state."""
    c = R.FakeClock(t=1000.0)
    tok = R.StatelessToken(secret="0123456789abcdef0123456789abcdef", clock=c)
    t = tok.issue("alice", ttl=900.0)
    assert tok.validate(t)["sub"] == "alice"
    tok.revoke(t)                          # "logout" — best effort
    assert tok.validate(t)["sub"] == "alice", \
        "a stateless token was revoked — that would require server-side state"
    c.advance(901.0)
    with pytest.raises(Exception):
        tok.validate(t)                    # the ONLY way out: wait for exp


def test_jwt_replay_twice_still_validates(R):
    """Stateless has no replay memory: the same token validates N times."""
    tok = R.StatelessToken(secret="0123456789abcdef0123456789abcdef", clock=R.FakeClock(t=1000.0))
    t = tok.issue("alice", ttl=900.0)
    for _ in range(5):
        assert tok.validate(t)["sub"] == "alice"


def test_jwt_wrong_secret_rejected(R):
    tok = R.StatelessToken(secret="0123456789abcdef0123456789abcdef", clock=R.FakeClock(t=1000.0))
    t = tok.issue("alice")
    other = R.StatelessToken(secret="an entirely different 32+ byte secret!", clock=R.FakeClock(t=1000.0))
    with pytest.raises(Exception):
        other.validate(t)


# ------------------------------------------------------------------ hybrid
def test_hybrid_login_returns_access_and_refresh(R):
    c = R.FakeClock()
    store = R.SessionStore(clock=c)
    h = R.HybridAuth(token=R.StatelessToken("0123456789abcdef0123456789abcdef", c), store=store)
    access, refresh = h.login("alice")
    assert access and refresh and access != refresh
    assert R.StatelessToken("0123456789abcdef0123456789abcdef", c).validate(access)["sub"] == "alice"


def test_hybrid_rotation_chain(R):
    c = R.FakeClock()
    store = R.SessionStore(clock=c, ttl=604800.0)
    h = R.HybridAuth(token=R.StatelessToken("0123456789abcdef0123456789abcdef", c), store=store)
    _, refresh = h.login("alice")
    old_refresh = refresh
    for _ in range(3):                      # rotate three times
        access, refresh = h.refresh(refresh)
        assert access
        assert refresh != old_refresh       # rotation actually rotates
        old_refresh = refresh


def test_hybrid_reuse_of_rotated_refresh_rejected(R):
    c = R.FakeClock()
    store = R.SessionStore(clock=c, ttl=604800.0)
    h = R.HybridAuth(token=R.StatelessToken("0123456789abcdef0123456789abcdef", c), store=store)
    _, r1 = h.login("alice")
    _, r2 = h.refresh(r1)
    with pytest.raises(PermissionError):
        h.refresh(r1)                      # presenting the OLD refresh again


def test_hybrid_logout_kills_refresh_not_still_valid_access(R):
    """The honest hybrid: logout revokes the refresh lever immediately; any
    already-issued access token lives on until its short TTL expires."""
    c = R.FakeClock()
    store = R.SessionStore(clock=c, ttl=604800.0)
    tok = R.StatelessToken("0123456789abcdef0123456789abcdef", c)
    h = R.HybridAuth(token=tok, store=store)
    access, refresh = h.login("alice")
    assert h.logout(refresh) is True
    with pytest.raises(PermissionError):
        h.refresh(refresh)                  # refresh side: dead instantly
    assert tok.validate(access)["sub"] == "alice"   # access side: alive till exp
    c.advance(901.0)
    with pytest.raises(Exception):
        tok.validate(access)                # ...but not a second longer
