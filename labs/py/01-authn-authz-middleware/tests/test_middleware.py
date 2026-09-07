"""Lab 01 tests — AuthN vs AuthZ vs Accounting as separate middleware stages.

No sleeps, no network, pure stdlib. The tests assert behaviour (statuses,
attached identity, recorded decisions, execution order), never private state.
"""
import pytest


# ------------------------------------------------------------------ fixtures
TOKENS = {"tok-alice": "alice", "tok-bob": "bob", "tok-admin": "admin"}
ACL = {
    ("reports", "read"): {"alice"},
    ("reports", "write"): {"alice", "bob"},
    ("announcements", "read"): {"*"},
}

ORDER_LOG = []          # shared marker list for order tests
AUDIT_LOG = []          # shared audit list for middleware tests


def _req(token=None, path="/reports"):
    headers = {} if token is None else {"Authorization": f"Bearer {token}"}
    return {"path": path, "headers": headers}


def _ok_handler(req):
    return {"status": 200, "user": req.get("user")}


# ------------------------------------------------------------------ 1. authenticate
def test_missing_token_is_401_not_403(R):
    """No Authorization header at all: we cannot even name the caller — 401."""
    with pytest.raises(R.AuthenticationError) as ei:
        R.authenticate(_req(token=None), TOKENS)
    assert ei.value.status == 401


def test_unknown_token_is_401(R):
    """Well-formed Bearer token that maps to nobody: still 401 — the 403 would
    leak that the token format was accepted, and 401 must not distinguish
    'unknown token' from 'missing token' (user enumeration)."""
    with pytest.raises(R.AuthenticationError) as ei:
        R.authenticate(_req(token="tok-nobody"), TOKENS)
    assert ei.value.status == 401


def test_valid_token_attaches_user(R):
    """AuthN's whole output: a stable identity on the request, nothing else."""
    req = _req(token="tok-alice")
    assert "user" not in req
    R.authenticate(req, TOKENS)
    assert req["user"] == "alice"


# ------------------------------------------------------------------ 2. authorize
def test_allowed_acl_entry_passes(R):
    req = _req(token="tok-alice")
    R.authenticate(req, TOKENS)
    R.authorize(req, ACL, "reports", "read")      # no raise == allowed


def test_denied_user_exists_is_403_not_401(R):
    """THE authn/authz distinction: bob authenticated fine (we know who he is),
    and the answer is no. 401 here would send him hunting for credentials he
    already presented correctly."""
    req = _req(token="tok-bob")
    R.authenticate(req, TOKENS)
    assert req["user"] == "bob"
    with pytest.raises(R.AuthorizationError) as ei:
        R.authorize(req, ACL, "reports", "read")
    assert ei.value.status == 403
    assert not isinstance(ei.value, R.AuthenticationError)


def test_wildcard_grants_every_authenticated_user(R):
    req = _req(token="tok-bob")
    R.authenticate(req, TOKENS)
    R.authorize(req, ACL, "announcements", "read")   # bob not listed — "*" covers him


def test_admin_bypasses_acl(R):
    """Admin passes even (resource, action) pairs with no entry at all."""
    req = _req(token="tok-admin")
    R.authenticate(req, TOKENS)
    R.authorize(req, ACL, "payroll", "delete")        # no entry, not listed — still passes


# ------------------------------------------------------------------ 3. authz assumes authn
def test_authorize_without_user_raises_authentication_error(R):
    """Authz never re-verifies credentials; if identity is missing it assumes
    authn did not run and raises AuthenticationError — NOT AuthorizationError."""
    req = _req(token="tok-alice")
    assert "user" not in req
    with pytest.raises(R.AuthenticationError) as ei:
        R.authorize(req, ACL, "reports", "read")
    assert ei.value.status == 401


# ------------------------------------------------------------------ 4. accounting
def test_audit_records_allow_and_deny(R):
    log = []
    allow_req = _req(token="tok-alice")
    R.authenticate(allow_req, TOKENS)
    R.authorize(allow_req, ACL, "reports", "read")
    R.audit(allow_req, True, "reports", "read", log)

    deny_req = _req(token="tok-bob")
    R.authenticate(deny_req, TOKENS)
    try:
        R.authorize(deny_req, ACL, "reports", "read")
        denied = False
    except R.AuthorizationError:
        denied = True
    R.audit(deny_req, not denied, "reports", "read", log)

    assert log == [("alice", "reports", "read", True),
                   ("bob", "reports", "read", False)]


# ------------------------------------------------------------------ 5. the middleware stack
def test_compose_runs_stages_in_order(R):
    """The log proves execution order: log_mw wraps authn, authn runs before
    authz, and the handler runs last only after every stage passed."""
    trace = []

    def tracking_handler(req):
        trace.append("handler")
        return {"status": 200}

    stack = R.compose(
        [R.log_mw(trace), R.authn_mw(TOKENS),
         R.authz_mw(ACL, "reports", "read", AUDIT_LOG)],
        tracking_handler,
    )
    resp = stack(_req(token="tok-alice"))
    assert resp["status"] == 200
    assert trace == ["/reports", "handler"]          # log first, handler last
    assert AUDIT_LOG[-1] == ("alice", "reports", "read", True)


def test_response_gains_headers(R):
    resp = R.compose([R.log_mw(ORDER_LOG)], _ok_handler)(_req())
    assert "headers" in resp and isinstance(resp["headers"], dict)


def test_denied_request_stops_before_handler(R):
    """A middleware raising stops the chain — the handler must not execute."""
    ran = []

    def handler(req):
        ran.append("ran")
        return {"status": 200}

    stack = R.compose(
        [R.log_mw(ORDER_LOG), R.authn_mw(TOKENS),
         R.authz_mw(ACL, "reports", "read", AUDIT_LOG)],
        handler,
    )
    with pytest.raises(R.AuthorizationError):
        stack(_req(token="tok-bob"))
    assert ran == []
    assert AUDIT_LOG[-1] == ("bob", "reports", "read", False)   # deny also audited


# ------------------------------------------------------------------ 6. order matters
def test_wrong_order_authz_before_authn_raises_authentication_error(R):
    """The failure mode of a misconfigured stack. authz first finds no user
    attached and raises AuthenticationError — NOT AuthorizationError —
    because it cannot authorize an anonymous identity. If your authz stage
    403s an unauthenticated request it is conflating the two concerns."""
    with pytest.raises(R.AuthenticationError) as ei:
        stack = R.compose(
            [R.log_mw(ORDER_LOG),                      # outermost
             R.authz_mw(ACL, "reports", "read", AUDIT_LOG),   # WRONG: before authn
             R.authn_mw(TOKENS)],
            _ok_handler,
        )
        stack(_req(token="tok-alice"))
    assert ei.value.status == 401
    assert not isinstance(ei.value, R.AuthorizationError)


def test_missing_token_through_full_stack_is_401_and_never_audited_as_user(R):
    """401 short-circuits before authz/accounting: anonymous callers never
    reach the decision stage, so the audit log does not grow."""
    before = len(AUDIT_LOG)
    stack = R.compose(
        [R.log_mw(ORDER_LOG), R.authn_mw(TOKENS),
         R.authz_mw(ACL, "reports", "read", AUDIT_LOG)],
        _ok_handler,
    )
    with pytest.raises(R.AuthenticationError) as ei:
        stack(_req(token=None))
    assert ei.value.status == 401
    assert len(AUDIT_LOG) == before
