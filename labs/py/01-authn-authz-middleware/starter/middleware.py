"""Lab 01 — AuthN vs AuthZ as middleware. Fill in every TODO. Tests define done.

Rules:
  * Pure stdlib. No frameworks, no network, no sleeping.
  * authenticate() must never make an allow/deny decision — that is authorize's job.
  * authorize() must never verify a credential — that is authenticate's job.
  * A middleware stage that raises stops the chain: later stages never run.
"""
from __future__ import annotations

from typing import Callable, Dict, List, Set, Tuple

Request = Dict[str, object]
Handler = Callable[[Request], Dict[str, object]]
Middleware = Callable[[Handler], Handler]


# --------------------------------------------------------------------------- errors
class HTTPError(Exception):
    """Base for errors the edge translates into an HTTP status."""

    def __init__(self, message: str, status: int):
        super().__init__(message)
        self.status = status


class AuthenticationError(HTTPError):
    """401 semantics: 'I do not know who you are.' Credentials missing/invalid."""

    def __init__(self, message: str = "unauthenticated"):
        super().__init__(message, status=401)


class AuthorizationError(HTTPError):
    """403 semantics: 'I know exactly who you are, and the answer is no.'"""

    def __init__(self, message: str = "forbidden"):
        super().__init__(message, status=403)


# --------------------------------------------------------------------------- authenticate
def authenticate(req: Request, token_store: Dict[str, str]) -> None:
    """AuthN stage — 'who are you?'

    Extract the Bearer token from req["headers"]["Authorization"]
    (format: "Bearer <opaque-token>", case-sensitive scheme, exactly one space).
    Missing header, wrong scheme, or a token not in token_store
    -> raise AuthenticationError (401 semantics).
    Valid -> attach req["user"] = token_store[token] and return.

    MUST NOT touch any ACL: authentication never makes an allow/deny decision.
    """
    # TODO(step 1)
    raise NotImplementedError


# --------------------------------------------------------------------------- authorize
def authorize(req: Request,
              acl: Dict[Tuple[str, str], Set[str]],
              resource: str,
              action: str) -> None:
    """AuthZ stage — 'what is this identity allowed to do, here, now?'

    Precondition: authenticate() already ran (authz assumes authn, never repeats it).
    req has no "user" -> raise AuthenticationError, not AuthorizationError:
    denying with 403 before identity exists would leak that authz ran at all.

    acl maps (resource, action) -> {allowed users} or {"*"} for everyone.
    Deny -> raise AuthorizationError (403 semantics). The user exists — that is
    exactly the authn/authz distinction this lab exists to burn in.

    Admin bypass: user "admin" passes every check before the ACL is consulted.
    """
    # TODO(step 2)
    raise NotImplementedError


# --------------------------------------------------------------------------- accounting
def audit(req: Request,
          decision: bool,
          resource: str,
          action: str,
          log: List[Tuple[str, str, str, bool]]) -> None:
    """Accounting — record the decision either way, allow or deny.

    Appends (user, resource, action, allow: bool) to the caller's log object.
    The caller owns the log so tests stay hermetic (no process-global mutable state).
    """
    # TODO(step 3)
    raise NotImplementedError


# --------------------------------------------------------------------------- middleware
def log_mw(log: List[str]) -> Middleware:
    """Middleware that appends a marker to the caller's log list, then calls next.

    Exists so tests can prove the chain executes stages in order.
    """
    # TODO(step 4)
    raise NotImplementedError


def authn_mw(token_store: Dict[str, str]) -> Middleware:
    """Middleware wrapping authenticate(). Must run BEFORE any authz stage."""
    # TODO(step 5)
    raise NotImplementedError


def authz_mw(acl: Dict[Tuple[str, str], Set[str]],
             resource: str,
             action: str,
             audit_log: List[Tuple[str, str, str, bool]]) -> Middleware:
    """Middleware wrapping authorize() plus accounting: every decision — allow
    OR deny — is recorded via audit() before the exception (if any) propagates.
    Must run AFTER authn_mw; the wrong-order test proves why.
    """
    # TODO(step 6)
    raise NotImplementedError


# --------------------------------------------------------------------------- composition
def compose(fns: List[Middleware], handler: Handler) -> Handler:
    """Build a single callable from a list of middleware stages.

    Stages run in the given order (fns[0] outermost — first to run per request).
    A stage that raises stops the chain: the handler never executes and no
    later stage runs. The handler returns a response dict; middleware may
    add to it — the response gains a "headers" dict ({"Content-Type": ...}).
    """
    # TODO(step 7)
    raise NotImplementedError
