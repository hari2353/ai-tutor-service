"""Lab 05 tests: rotation chains, reuse detection, expiry via FakeClock, cache."""
import pytest

from conftest import SECRET, make_server


# ------------------------------------------------------------------ happy chain
def test_happy_rotation_chain_keeps_same_family(R):
    s, c = make_server(R)
    acc, ref = s.issue_pair("alice")
    fam0 = s.store.get(ref)["family"]
    for i in range(5):                       # Mon–Fri: five clean rotations
        c.advance(3600.0)
        acc, ref = s.refresh(ref)
        rec = s.store.get(ref)
        assert rec is not None and not rec["rotated"]
        assert rec["family"] == fam0, "rotation must stay in the same family"
    assert s.revocation_events == []


def test_access_token_valid_between_rotations(R):
    s, c = make_server(R)
    acc, ref = s.issue_pair("alice")
    claims = R.verify_access(acc, SECRET, c.now())
    assert claims["sub"] == "alice"
    c.advance(899.0)                          # 15-min access TTL, 1s to spare
    assert R.verify_access(acc, SECRET, c.now())["sub"] == "alice"


def test_access_expires_before_refresh_does(R):
    """The whole design: access is short, refresh is long."""
    s, c = make_server(R)
    acc, ref = s.issue_pair("alice")
    c.advance(901.0)                          # access dead
    with pytest.raises(ValueError):
        R.verify_access(acc, SECRET, c.now())
    acc2, ref2 = s.refresh(ref)               # refresh still alive at 15min
    assert R.verify_access(acc2, SECRET, c.now())["sub"] == "alice"


# ------------------------------------------------------------------ reuse detection
def test_reuse_of_rotated_token_kills_family(R):
    """THE breach signal: attacker replays the token stolen before rotation."""
    s, c = make_server(R)
    acc, ref = s.issue_pair("alice")
    stolen = ref                              # copied at t=0
    acc2, ref2 = s.refresh(ref)                # legit rotation
    with pytest.raises(R.ReuseDetected):
        s.refresh(stolen)                     # attacker replays the old one
    assert len(s.revocation_events) == 1
    # family revoked: even the CURRENT legit refresh is dead
    with pytest.raises(PermissionError):
        s.refresh(ref2)
    # and re-replaying the stolen one now hits 'unknown', not ReuseDetected again
    with pytest.raises(PermissionError):
        s.refresh(stolen)


def test_reuse_detection_survives_long_chains(R):
    """A ghost from rotation #2 replayed after rotations #3–5 is still detected."""
    s, c = make_server(R)
    _, r1 = s.issue_pair("alice")
    _, r2 = s.refresh(r1)
    _, r3 = s.refresh(r2)
    _, r4 = s.refresh(r3)
    with pytest.raises(R.ReuseDetected):
        s.refresh(r2)                         # three rotations later
    with pytest.raises(PermissionError):
        s.refresh(r4)                         # current token died with the family


def test_families_are_independent(R):
    s, c = make_server(R)
    _, ra = s.issue_pair("alice")
    _, rb = s.issue_pair("bob")
    _, ra2 = s.refresh(ra)
    with pytest.raises(R.ReuseDetected):
        s.refresh(ra)                         # alice's family killed
    _, rb2 = s.refresh(rb)                    # bob untouched
    assert s.store.get(rb2) is not None


# ------------------------------------------------------------------ expiry
def test_expired_refresh_fails(R):
    s, c = make_server(R, refresh_ttl=86400.0)          # 1 day
    _, ref = s.issue_pair("alice")
    c.advance(86401.0)
    with pytest.raises(PermissionError):
        s.refresh(ref)


def test_refresh_expiry_boundary_via_fake_clock(R):
    s, c = make_server(R, refresh_ttl=3600.0)
    _, ref = s.issue_pair("alice")
    c.advance(3599.0)
    _, ref2 = s.refresh(ref)                  # one second to spare — valid
    c.advance(3601.0)
    with pytest.raises(PermissionError):
        s.refresh(ref2)


def test_revoke_all_for_user_is_the_admin_kill_switch(R):
    s, c = make_server(R)
    _, ra = s.issue_pair("alice")
    _, rb = s.issue_pair("bob")
    n = s.revoke_all_for_user("alice")
    assert n >= 1
    with pytest.raises(PermissionError):
        s.refresh(ra)
    _, rb2 = s.refresh(rb)                   # bob keeps working


# ------------------------------------------------------------------ hashed storage
def test_store_never_holds_the_raw_refresh_token(R):
    """If the store leaks, the attacker gets hashes — not usable tokens."""
    s, c = make_server(R)
    _, ref = s.issue_pair("alice")
    for h, rec in s.store.records().items():
        assert h != ref and ref not in json_dumps(rec)
    assert s.store.hash_token(ref) != ref


def json_dumps(x) -> str:
    import json
    return json.dumps(x, default=str)


def test_hash_token_is_deterministic_and_opaque(R):
    h1 = R.RefreshStore.hash_token("abc")
    h2 = R.RefreshStore.hash_token("abc")
    assert h1 == h2 and h1 != "abc" and len(h1) == 64


# ------------------------------------------------------------------ introspection cache
def test_introspection_caches_and_serves_hits(R):
    s, c = make_server(R)
    acc, _ = s.issue_pair("alice")
    cache = R.IntrospectionCache(server=s, ttl=60.0)
    assert cache.introspect(acc) is True
    assert cache.misses == 1 and cache.hits == 0
    assert cache.introspect(acc) is True       # cached
    assert cache.introspect(acc) is True
    assert cache.hits == 2 and cache.misses == 1


def test_introspection_cache_expires_and_refetches(R):
    s, c = make_server(R)
    acc, _ = s.issue_pair("alice")
    cache = R.IntrospectionCache(server=s, ttl=60.0)
    assert cache.introspect(acc) is True
    assert cache.misses == 1 and cache.hits == 0
    c.advance(61.0)                           # cache entry stale now
    assert cache.introspect(acc) is True       # token still valid — but REFETCHED
    assert cache.misses == 2 and cache.hits == 0
    c.advance(7200.0)                          # past the 900s access TTL
    assert cache.introspect(acc) is False      # refetch sees expiry


def test_introspection_cache_invalidated_on_revocation(R):
    """A cached 'valid' must not outlive a revocation — that's the whole
    reason invalidate() exists."""
    s, c = make_server(R)
    acc, ref = s.issue_pair("alice")
    cache = R.IntrospectionCache(server=s, ttl=300.0)   # long cache TTL
    assert cache.introspect(acc) is True
    s.revoke_all_for_user("alice")            # family revoked
    cache.invalidate(acc)                     # revocation invalidates cache
    assert cache.introspect(acc) is False
    assert cache.misses == 2                  # refetch happened, cache bypassed


def test_introspection_rejects_garbage_and_unknown_tokens(R):
    s, c = make_server(R)
    cache = R.IntrospectionCache(server=s, ttl=60.0)
    assert cache.introspect("not-a-token") is False
    acc, _ = s.issue_pair("alice")
    # a token signed by a DIFFERENT issuer (different secret, different clock)
    other = R.AuthServer(b"Z" * 32, R.FakeClock(t=0.0))
    acc2, _ = other.issue_pair("alice")
    assert acc2 != acc
    assert cache.introspect(acc2) is False     # wrong signer → rejected
    # a token from the SAME issuer but never registered (forged-with-secret edge)
    forged = R.sign_access("mallory", 900.0, c.now(), SECRET)
    assert cache.introspect(forged) is False   # valid signature, unknown to issuer
