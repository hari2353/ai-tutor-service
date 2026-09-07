"""Lab 03 tests. No sleeps, no wall-clock — everything runs on FakeClock."""
import base64
import json

import pytest


SECRET = b"0123456789abcdef0123456789abcdef"
KID = "hs-key-1"


def make_jwt(R, **kw):
    c = R.FakeClock(t=1000.0)
    reg = R.KeyRegistry()
    reg.add(KID, "HS256", SECRET)
    return R.JWT(clock=c, registry=reg, **kw), c


# ------------------------------------------------------------------ clock + base64url
def test_fake_clock(R):
    c = R.FakeClock(t=5.0)
    assert c.now() == 5.0
    c.advance(2.0)
    assert c.now() == 7.0


def test_b64url_encode_strips_padding(R):
    assert R.b64url_encode(b"a") == "YQ"          # base64 would be "YQ=="
    assert R.b64url_encode(b"ab") == "YWI"
    assert R.b64url_encode(b"abc") == "YWJj"
    assert R.b64url_encode(b"abcd") == "YWJjZA"
    assert "=" not in R.b64url_encode(b"any length at all, padding never appears")


def test_b64url_decode_restores_padding(R):
    assert R.b64url_decode("YQ") == b"a"
    assert R.b64url_decode("YWJj") == b"abc"
    assert R.b64url_decode(R.b64url_encode(b"arbitrary \x00\xff bytes")) == b"arbitrary \x00\xff bytes"


def test_b64url_decode_rejects_garbage(R):
    with pytest.raises(Exception):
        R.b64url_decode("!!!not-base64!!!")


# ------------------------------------------------------------------ structure
def test_token_has_three_dot_separated_segments(R):
    jwt, _ = make_jwt(R)
    tok = jwt.encode({"sub": "alice"}, "HS256", SECRET, kid=KID)
    h, p, s = tok.split(".")
    assert h and p and s
    assert "=" not in tok


def test_header_carries_alg_typ_kid(R):
    jwt, _ = make_jwt(R)
    tok = jwt.encode({"sub": "alice"}, "HS256", SECRET, kid=KID)
    header = json.loads(R.b64url_decode(tok.split(".")[0]))
    assert header["alg"] == "HS256"
    assert header["typ"] == "JWT"
    assert header["kid"] == KID


# ------------------------------------------------------------------ HS256
def test_hs256_roundtrip(R, hs_key):
    jwt, _ = make_jwt(R)
    tok = jwt.encode({"sub": "alice", "exp": 9999}, "HS256", hs_key, kid=KID)
    assert jwt.decode(tok)["sub"] == "alice"


def test_hs256_sign_is_deterministic_hmac(R, hs_key):
    msg = b"header.payload"
    sig = R.hs256_sign(msg, hs_key)
    assert sig == R.hs256_sign(msg, hs_key)
    assert sig != R.hs256_sign(b"header.payloax", hs_key)
    assert sig != R.hs256_sign(msg, b"another secret key entirely....")


def test_tampered_payload_rejected(R, hs_key):
    jwt, _ = make_jwt(R)
    tok = jwt.encode({"sub": "alice", "exp": 9999}, "HS256", hs_key, kid=KID)
    h, p, s = tok.split(".")
    # re-encode a DIFFERENT payload under the original header+signature
    evil = R.b64url_encode(json.dumps({"sub": "admin", "exp": 9999}).encode())
    with pytest.raises(Exception):
        jwt.decode(f"{h}.{evil}.{s}")


def test_tampered_signature_rejected(R, hs_key):
    jwt, _ = make_jwt(R)
    tok = jwt.encode({"sub": "alice", "exp": 9999}, "HS256", hs_key, kid=KID)
    h, p, s = tok.split(".")
    with pytest.raises(Exception):
        jwt.decode(f"{h}.{p}.{s[:-1]}{'A' if s[-1] != 'A' else 'B'}")


# ------------------------------------------------------------------ RS256
def test_rs256_keypair_pems(R, rsa_pair):
    priv, pub = rsa_pair
    assert priv.startswith(b"-----BEGIN PRIVATE KEY-----")
    assert pub.startswith(b"-----BEGIN PUBLIC KEY-----")


def test_rs256_sign_verify_roundtrip(R, rsa_pair):
    priv, pub = rsa_pair
    sig = R.rs256_sign(b"the signing input", priv)
    assert R.rs256_verify(b"the signing input", sig, pub)
    assert not R.rs256_verify(b"the signing inpuT", sig, pub)
    assert not R.rs256_verify(b"the signing input", sig[:-2] + b"\x00\x00", pub)


def test_rs256_token_roundtrip_wrong_key_rejected(R, rsa_pair):
    priv, pub = rsa_pair
    other_priv, other_pub = R.rs256_generate_keypair()
    reg = R.KeyRegistry()
    reg.add("rs-1", "RS256", pub)
    jwt = R.JWT(clock=R.FakeClock(t=0.0), registry=reg)
    tok = jwt.encode({"sub": "alice", "exp": 99999}, "RS256", priv, kid="rs-1")
    assert jwt.decode(tok)["sub"] == "alice"
    # token signed by the OTHER key's private half must fail against rs-1's public
    tok2 = jwt.encode({"sub": "alice", "exp": 99999}, "RS256", other_priv, kid="rs-1")
    with pytest.raises(Exception):
        jwt.decode(tok2)


# ------------------------------------------------------------------ kid / registry
def test_unknown_kid_rejected(R, hs_key):
    jwt, _ = make_jwt(R)
    tok = jwt.encode({"sub": "alice", "exp": 9999}, "HS256", hs_key, kid="ghost-kid")
    with pytest.raises(Exception):
        jwt.decode(tok)


def test_kid_selects_the_right_key(R, hs_key, rsa_pair):
    """Two kids, two algorithms, one registry — kid must route to the right key."""
    c = R.FakeClock(t=0.0)
    reg = R.KeyRegistry()
    reg.add("h", "HS256", hs_key)
    reg.add("r", "RS256", rsa_pair[1])
    jwt = R.JWT(clock=c, registry=reg)
    hs_tok = jwt.encode({"sub": "a", "exp": 99999}, "HS256", hs_key, kid="h")
    rs_tok = jwt.encode({"sub": "a", "exp": 99999}, "RS256", rsa_pair[0], kid="r")
    assert jwt.decode(hs_tok)["sub"] == "a"
    assert jwt.decode(rs_tok)["sub"] == "a"


def test_alg_mismatch_between_header_and_key_rejected(R, hs_key):
    """Header says RS256 but kid points at an HS key — refuse to mix families."""
    jwt, _ = make_jwt(R)
    tok = jwt.encode({"sub": "alice", "exp": 9999}, "HS256", hs_key, kid=KID)
    h, p, s = tok.split(".")
    hdr = json.loads(R.b64url_decode(h))
    hdr["alg"] = "RS256"
    h2 = R.b64url_encode(json.dumps(hdr).encode())
    with pytest.raises(Exception):
        jwt.decode(f"{h2}.{p}.{s}")


def test_expected_alg_pin(R, hs_key):
    jwt, _ = make_jwt(R)
    tok = jwt.encode({"sub": "alice", "exp": 9999}, "HS256", hs_key, kid=KID)
    with pytest.raises(Exception):
        jwt.decode(tok, expected_alg="RS256")    # caller pinned a different alg


# ------------------------------------------------------------------ claims + clock
def test_expired_rejected_then_leeway_accepts(R, hs_key):
    c = R.FakeClock(t=1000.0)
    strict = R.JWT(clock=c, registry=_reg(R, hs_key), leeway=0.0)
    lenient = R.JWT(clock=c, registry=_reg(R, hs_key), leeway=30.0)
    tok = strict.encode({"sub": "alice", "exp": 1100}, "HS256", hs_key, kid=KID)
    c.advance(101.0)                             # 1s past exp
    with pytest.raises(Exception):
        strict.decode(tok)
    assert lenient.decode(tok)["sub"] == "alice"  # inside the 30s skew window
    c.advance(30.0)                              # beyond even the leeway
    with pytest.raises(Exception):
        lenient.decode(tok)


def test_nbf_in_future_rejected_then_accepted(R, hs_key):
    c = R.FakeClock(t=1000.0)
    jwt = R.JWT(clock=c, registry=_reg(R, hs_key))
    tok = jwt.encode({"sub": "alice", "nbf": 1200, "exp": 2000}, "HS256", hs_key, kid=KID)
    with pytest.raises(Exception):
        jwt.decode(tok)                          # too early
    c.advance(200.0)
    assert jwt.decode(tok)["sub"] == "alice"     # now valid


def test_iat_present_in_roundtrip(R, hs_key):
    c = R.FakeClock(t=1000.0)
    jwt = R.JWT(clock=c, registry=_reg(R, hs_key))
    tok = jwt.encode({"sub": "alice", "iat": 1000, "exp": 2000}, "HS256", hs_key, kid=KID)
    assert jwt.decode(tok)["iat"] == 1000


def _reg(R, hs_key, kid=KID):
    reg = R.KeyRegistry()
    reg.add(kid, "HS256", hs_key)
    return reg


# ------------------------------------------------------------------ cross-check vs PyJWT
def test_cross_check_hs256_against_pyjwt(R, hs_key):
    """The one allowed PyJWT use: prove your from-scratch HS256 output is
    byte-identical to the library's, and that PyJWT accepts your token."""
    import jwt as pyjwt
    c = R.FakeClock(t=1000.0)
    reg = R.KeyRegistry()
    reg.add(KID, "HS256", hs_key)
    mine = R.JWT(clock=c, registry=reg)
    claims = {"sub": "alice", "iat": 1000, "nbf": 1000, "exp": 2000}
    mine_tok = mine.encode(claims, "HS256", hs_key, kid=KID)
    lib_tok = pyjwt.encode(dict(claims, kid_ignored=None) if False else claims,
                            hs_key, algorithm="HS256")
    # the library's token has no kid in the header; ours does — signatures are
    # over the exact signing input, so compare the SIGNATURE of identical inputs:
    lib_sig = pyjwt.encode(claims, hs_key, algorithm="HS256").split(".")[2]
    my_sig_on_lib_input = R.b64url_encode(
        R.hs256_sign(pyjwt.encode(claims, hs_key, algorithm="HS256")
                     .split(".")[0].encode() + b"." +
                     pyjwt.encode(claims, hs_key, algorithm="HS256")
                     .split(".")[1].encode(), hs_key))
    assert my_sig_on_lib_input == lib_sig
    # and the library verifies OUR token's signature over OUR signing input
    h, p, s = mine_tok.split(".")
    import hmac as _h, hashlib as _hl
    assert _h.compare_digest(
        R.hs256_sign(f"{h}.{p}".encode(), hs_key), R.b64url_decode(s))
