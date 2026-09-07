"""Lab 06 tests: happy flow, every rejection path, PKCE downgrade."""
import pytest

from conftest import run_happy


# ------------------------------------------------------------------ PKCE helpers
def test_s256_challenge_matches_rfc7636_vector(R):
    """RFC 7636 Appendix B test vector — the interoperability anchor."""
    verifier = "dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk"
    assert R.pkce_s256_challenge(verifier) == "E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM"


def test_s256_challenge_is_b64url_no_padding(R):
    ch = R.pkce_s256_challenge("a" * 43)
    assert "=" not in ch and "+" not in ch and "/" not in ch


def test_verifier_length_and_charset_rules(R):
    assert R.pkce_verifier_ok("a" * 43) and R.pkce_verifier_ok("a" * 128)
    assert not R.pkce_verifier_ok("a" * 42)      # too short
    assert not R.pkce_verifier_ok("a" * 129)     # too long
    assert not R.pkce_verifier_ok("a" * 43 + " ")    # space not unreserved
    assert not R.pkce_verifier_ok("a" * 43 + "$")    # $ not unreserved


# ------------------------------------------------------------------ happy flow
def test_full_happy_flow_end_to_end(R, as_server, client):
    tokens = run_happy(R, as_server, client)
    assert tokens["access_token"]
    assert tokens["token_type"] == "Bearer"
    assert as_server.tokens_issued


def test_happy_flow_resource_accepts_the_token(R, as_server, client):
    tokens = run_happy(R, as_server, client)
    res = R.ProtectedResource(as_server)
    assert res.get(tokens["access_token"])["resource"] == "profile"


def test_client_verifier_never_leaves_in_authorize_request(R, as_server, client):
    """The point of PKCE: only the CHALLENGE travels on the front channel."""
    params = client.begin()
    redirect = as_server.authorize(
        client_id=params["client_id"], redirect_uri=params["redirect_uri"],
        scope="openid profile", code_challenge=params["code_challenge"],
        code_challenge_method=params["code_challenge_method"], state=params["state"])
    assert client.verifier not in redirect
    assert params["code_challenge"] != client.verifier
    assert params["code_challenge_method"] == "S256"


# ------------------------------------------------------------------ wrong verifier
def test_wrong_verifier_rejected(R, as_server, client):
    params = client.begin()
    redirect = as_server.authorize(
        client_id="web-app", redirect_uri="https://app.example/callback",
        scope="openid profile", code_challenge=params["code_challenge"],
        code_challenge_method="S256", state=params["state"])
    qs = dict(pair.split("=") for pair in redirect.lstrip("?").split("&"))
    # attacker intercepts the code but holds the WRONG verifier
    with pytest.raises(R.OAuthError) as e:
        as_server.token(grant_type="authorization_code", code=qs["code"],
                        client_id="web-app",
                        redirect_uri="https://app.example/callback",
                        code_verifier="b" * 64)
    assert "PKCE" in e.value.reason or "invalid_grant" in e.value.reason


def test_short_verifier_rejected(R, as_server, client):
    """RFC 7636 §4.1: verifiers are 43-128 chars. A 3-char one is malformed."""
    params = client.begin()
    redirect = as_server.authorize(
        client_id="web-app", redirect_uri="https://app.example/callback",
        scope="openid profile", code_challenge=params["code_challenge"],
        code_challenge_method="S256", state=params["state"])
    qs = dict(pair.split("=") for pair in redirect.lstrip("?").split("&"))
    with pytest.raises(R.OAuthError):
        as_server.token(grant_type="authorization_code", code=qs["code"],
                        client_id="web-app",
                        redirect_uri="https://app.example/callback",
                        code_verifier="abc")


# ------------------------------------------------------------------ code replay
def test_replayed_code_rejected(R, as_server, client):
    tokens1 = run_happy(R, as_server, client)
    # second client tries to replay the SAME code with the SAME verifier
    params = client.begin()
    redirect = as_server.authorize(
        client_id="web-app", redirect_uri="https://app.example/callback",
        scope="openid profile", code_challenge=params["code_challenge"],
        code_challenge_method="S256", state=params["state"])
    qs = dict(pair.split("=") for pair in redirect.lstrip("?").split("&"))
    as_server.token(grant_type="authorization_code", code=qs["code"],
                    client_id="web-app", redirect_uri="https://app.example/callback",
                    code_verifier=client.verifier)
    with pytest.raises(R.OAuthError) as e:
        as_server.token(grant_type="authorization_code", code=qs["code"],
                        client_id="web-app", redirect_uri="https://app.example/callback",
                        code_verifier=client.verifier)
    assert "already" in e.value.reason or "invalid_grant" in e.value.reason


# ------------------------------------------------------------------ expiry
def test_expired_code_rejected(R, as_server, client):
    c = as_server.clock
    params = client.begin()
    redirect = as_server.authorize(
        client_id="web-app", redirect_uri="https://app.example/callback",
        scope="openid profile", code_challenge=params["code_challenge"],
        code_challenge_method="S256", state=params["state"])
    qs = dict(pair.split("=") for pair in redirect.lstrip("?").split("&"))
    c.advance(59.0)
    ok = as_server.token(grant_type="authorization_code", code=qs["code"],
                         client_id="web-app", redirect_uri="https://app.example/callback",
                         code_verifier=client.verifier)
    assert ok["access_token"]
    # fresh code, this time let it lapse past 60s
    params = client.begin()
    redirect = as_server.authorize(
        client_id="web-app", redirect_uri="https://app.example/callback",
        scope="openid profile", code_challenge=params["code_challenge"],
        code_challenge_method="S256", state=params["state"])
    qs = dict(pair.split("=") for pair in redirect.lstrip("?").split("&"))
    c.advance(61.0)
    with pytest.raises(R.OAuthError) as e:
        as_server.token(grant_type="authorization_code", code=qs["code"],
                        client_id="web-app",
                        redirect_uri="https://app.example/callback",
                        code_verifier=client.verifier)
    assert "expired" in e.value.reason or "invalid_grant" in e.value.reason


# ------------------------------------------------------------------ redirect_uri
def test_redirect_uri_mismatch_rejected_at_authorize(R, as_server, client):
    params = client.begin()
    with pytest.raises(R.OAuthError) as e:
        as_server.authorize(client_id="web-app",
                            redirect_uri="https://evil.example/callback",
                            scope="openid profile",
                            code_challenge=params["code_challenge"],
                            code_challenge_method="S256", state="x")
    assert "redirect" in e.value.reason


def test_redirect_uri_mismatch_rejected_at_token(R, as_server, client):
    """Code issued for callback A must not redeem against callback B."""
    params = client.begin()
    redirect = as_server.authorize(
        client_id="web-app", redirect_uri="https://app.example/callback",
        scope="openid profile", code_challenge=params["code_challenge"],
        code_challenge_method="S256", state=params["state"])
    qs = dict(pair.split("=") for pair in redirect.lstrip("?").split("&"))
    with pytest.raises(R.OAuthError):
        as_server.token(grant_type="authorization_code", code=qs["code"],
                        client_id="web-app",
                        redirect_uri="https://evil.example/callback",
                        code_verifier=client.verifier)


# ------------------------------------------------------------------ PKCE downgrade
def test_plain_challenge_downgrade_rejected(R, as_server, client):
    """The AS requires S256: a 'plain' challenge (verifier sent as-is, so an
    interceptor who sees the request can redeem) must be refused outright."""
    params = client.begin()
    with pytest.raises(R.OAuthError) as e:
        as_server.authorize(client_id="web-app",
                            redirect_uri="https://app.example/callback",
                            scope="openid profile",
                            code_challenge=client.verifier,   # plain = no hashing
                            code_challenge_method="plain", state="x")
    assert "plain" in e.value.reason or "S256" in e.value.reason


# ------------------------------------------------------------------ other failures
def test_unknown_client_rejected(R, as_server):
    with pytest.raises(R.OAuthError) as e:
        as_server.authorize(client_id="ghost-app",
                            redirect_uri="https://app.example/callback",
                            scope="openid", code_challenge="x" * 43,
                            code_challenge_method="S256", state="x")
    assert "client" in e.value.reason


def test_scope_not_allowed_rejected(R, as_server, client):
    params = client.begin()
    with pytest.raises(R.OAuthError) as e:
        as_server.authorize(client_id="web-app",
                            redirect_uri="https://app.example/callback",
                            scope="openid profile admin",
                            code_challenge=params["code_challenge"],
                            code_challenge_method="S256", state="x")
    assert "scope" in e.value.reason


def test_state_mismatch_on_callback_rejected(R, as_server, client):
    """state protects the callback against CSRF/login interception."""
    params = client.begin()
    redirect = as_server.authorize(
        client_id="web-app", redirect_uri="https://app.example/callback",
        scope="openid profile", code_challenge=params["code_challenge"],
        code_challenge_method="S256", state=params["state"])
    qs = dict(pair.split("=") for pair in redirect.lstrip("?").split("&"))
    qs["state"] = "attacker-state"
    with pytest.raises(R.OAuthError):
        client.complete(as_server, qs)


def test_wrong_grant_type_rejected(R, as_server, client):
    params = client.begin()
    redirect = as_server.authorize(
        client_id="web-app", redirect_uri="https://app.example/callback",
        scope="openid profile", code_challenge=params["code_challenge"],
        code_challenge_method="S256", state=params["state"])
    qs = dict(pair.split("=") for pair in redirect.lstrip("?").split("&"))
    with pytest.raises(R.OAuthError) as e:
        as_server.token(grant_type="password", code=qs["code"],
                        client_id="web-app",
                        redirect_uri="https://app.example/callback",
                        code_verifier=client.verifier)
    assert "grant" in e.value.reason
