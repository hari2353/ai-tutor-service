"""Lab 04 tests: each attack SUCCEEDS against the insecure verifier and
FAILS against the secure one. Break it, then fix it."""
import json

import pytest

from conftest import STRONG_SECRET


def claims(admin=False, exp=99999):
    return {"sub": "admin" if admin else "alice", "role": "admin" if admin else "user",
            "exp": exp, "iat": 0}


# ------------------------------------------------------------------ (a) alg=none
def test_attack_a_alg_none_succeeds_on_insecure(R):
    """Classic: craft an unsigned token with alg=none; the attacker makes
    themselves admin because the verifier trusts the header's algorithm."""
    v = R.make_verifier_insecure_none(STRONG_SECRET, R.FakeClock())
    forged = R.encode_jwt(claims(admin=True), "none", None)
    assert v.verify(forged)["role"] == "admin", "alg=none token was REJECTED — attack failed?"


def test_attack_a_alg_none_fails_on_secure(R):
    v = R.make_verifier_secure_none(STRONG_SECRET, R.FakeClock())
    forged = R.encode_jwt(claims(admin=True), "none", None)
    with pytest.raises(Exception):
        v.verify(forged)
    # and normal tokens still work — the fix didn't break the legit path
    good = R.encode_jwt(claims(), "HS256", STRONG_SECRET)
    assert v.verify(good)["sub"] == "alice"


def test_fix_a_rejects_alg_case_variants(R):
    """The wild variants: 'None', '' — the parser tricks that plagued CVE-2015-9235."""
    v = R.make_verifier_secure_none(STRONG_SECRET, R.FakeClock())
    for alg in ("None", "none", "NONE", ""):
        forged = R.encode_jwt(claims(admin=True), alg if alg else "none", None)
        h, p, s = forged.split(".")
        hdr = json.loads(R.b64url_decode(h))
        hdr["alg"] = alg
        h2 = R.b64url_encode(json.dumps(hdr).encode())
        with pytest.raises(Exception):
            v.verify(f"{h2}.{p}.{s}")


# ------------------------------------------------------------------ (b) key confusion
def test_attack_b_key_confusion_succeeds_on_insecure(R, rsa_pair):
    """The public key IS public — attacker signs HS256 with the public PEM as the secret."""
    priv, pub = rsa_pair
    v = R.make_verifier_insecure_confusion(pub, R.FakeClock())
    forged = R.encode_jwt(claims(admin=True), "HS256", pub)
    assert v.verify(forged)["role"] == "admin"


def test_attack_b_key_confusion_fails_on_secure(R, rsa_pair):
    priv, pub = rsa_pair
    v = R.make_verifier_secure_confusion(pub, R.FakeClock())
    forged = R.encode_jwt(claims(admin=True), "HS256", pub)
    with pytest.raises(Exception):
        v.verify(forged)
    # the legit RS256 path still works
    good = _rs256_token(R, priv, claims())
    assert v.verify(good)["sub"] == "alice"


def _rs256_token(R, priv, claims):
    """Build a real RS256 token (helper — uses cryptography, not PyJWT)."""
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import padding
    h = R.b64url_encode(json.dumps({"alg": "RS256", "typ": "JWT"},
                                   separators=(",", ":")).encode())
    p = R.b64url_encode(json.dumps(claims, separators=(",", ":")).encode())
    key = serialization.load_pem_private_key(priv, password=None)
    sig = key.sign(f"{h}.{p}".encode(), padding.PKCS1v15(), hashes.SHA256())
    return f"{h}.{p}.{R.b64url_encode(sig)}"


# ------------------------------------------------------------------ (c) weak secret
def test_attack_c_weak_secret_is_offline_crackable(R):
    token = R.encode_jwt(claims(admin=True), "HS256", b"jwt_secret")
    cracked = R.crack_hs256_secret(token)
    assert cracked == b"jwt_secret"
    # attacker now mints arbitrary tokens with the recovered secret
    forged = R.encode_jwt({"sub": "victim", "role": "admin", "exp": 99999},
                          "HS256", cracked)
    v = R.make_verifier_secure_none(b"jwt_secret", R.FakeClock())
    assert v.verify(forged)["role"] == "admin"


def test_attack_c_strong_secret_survives_the_dictionary(R):
    token = R.encode_jwt(claims(), "HS256", STRONG_SECRET)
    assert R.crack_hs256_secret(token) is None


# ------------------------------------------------------------------ (d) replay
def test_attack_d_replayed_jwt_still_validates_stateless(R):
    """No server memory = nothing to remember a stolen token by. The SAME token
    validates twice (and N times). This is the capability an attacker gets."""
    c = R.FakeClock()
    gw = R.StatelessGateway(STRONG_SECRET, c, ttl=900.0)
    t = gw.issue("alice")
    stolen = t                                   # attacker copies it off the wire
    first = gw.verify(stolen)
    second = gw.verify(stolen)                   # replay — indistinguishable
    assert first["sub"] == second["sub"] == "alice"


def test_attack_d_expired_access_with_refresh_rotation_mitigates(R):
    """The mitigation for (d)+(e): short access TTL shrinks the replay window;
    rotation gives the server a lever. After expiry, the stolen token is dead."""
    c = R.FakeClock()
    gw = R.HybridRotatingGateway(STRONG_SECRET, c, access_ttl=300.0)
    access, refresh = gw.issue_pair("alice")
    assert gw.verify_access(access)["sub"] == "alice"
    c.advance(301.0)                             # past the SHORT ttl
    with pytest.raises(Exception):
        gw.verify_access(access)                 # stolen token is now worthless
    access2, refresh2 = gw.refresh(refresh)      # legit user rotates, unaffected
    assert gw.verify_access(access2)["sub"] == "alice"
    assert refresh2 != refresh


# ------------------------------------------------------------------ (e) revocation gap
def test_attack_e_revocation_gap_stolen_token_outlives_logout(R):
    """The gap: 'logout' revokes nothing stateless; the stolen token keeps
    working until exp. With ttl=900 the attacker has 15 minutes, guaranteed."""
    c = R.FakeClock()
    gw = R.StatelessGateway(STRONG_SECRET, c, ttl=900.0)
    t = gw.issue("alice")
    stolen = t
    c.advance(899.0)                            # user "logs out" at t=0; thief waits
    assert gw.verify(stolen)["sub"] == "alice"  # still valid — nothing was revoked
    c.advance(2.0)
    with pytest.raises(Exception):
        gw.verify(stolen)                       # only exp ever kills it


def test_attack_e_rotation_makes_breach_detectable_and_bounded(R):
    """Fixed: reuse of a rotated refresh token = theft signal → family revoked."""
    c = R.FakeClock()
    gw = R.HybridRotatingGateway(STRONG_SECRET, c, access_ttl=300.0)
    access, refresh = gw.issue_pair("alice")
    stolen_refresh = refresh                    # attacker copies it
    access2, refresh2 = gw.refresh(refresh)     # legit user rotates
    # attacker replays the OLD refresh — the server sees reuse → kills family
    with pytest.raises(PermissionError):
        gw.refresh(stolen_refresh)
    # and now the LEGIT current refresh is dead too — theft was detected
    with pytest.raises(PermissionError):
        gw.refresh(refresh2)
    # while the current access token remains valid only until its short exp
    assert gw.verify_access(access2)["sub"] == "alice"
    c.advance(301.0)
    with pytest.raises(Exception):
        gw.verify_access(access2)


def test_happy_rotation_chain_is_not_broken_by_detection(R):
    """The fix must not cry wolf on normal use: a long clean chain rotates freely."""
    c = R.FakeClock()
    gw = R.HybridRotatingGateway(STRONG_SECRET, c, access_ttl=300.0)
    access, refresh = gw.issue_pair("alice")
    for _ in range(5):
        c.advance(250.0)
        access, refresh = gw.refresh(refresh)
        assert gw.verify_access(access)["sub"] == "alice"
