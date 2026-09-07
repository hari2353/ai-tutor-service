"""Lab 01 — AuthN vs AuthZ as middleware. Reference solution."""
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
    """AuthN stage — 'who are you?' Attaches req['user'] or raises 401."""
    headers = req.get("headers") or {}
    auth = headers.get("Authorization")
    if not isinstance(auth, str) or not auth.startswith("Bearer "):
        raise AuthenticationError("missing or malformed Authorization header")
    token = auth[len("Bearer "):]
    if token not in token_store:
        raise AuthenticationError("unknown token")
    req["user"] = token_store[token]


# --------------------------------------------------------------------------- authorize
def authorize(req: Request,
              acl: Dict[Tuple[str, str], Set[str]],
              resource: str,
              action: str) -> None:
    """AuthZ stage — per-resource, per-action decision. Assumes authn ran."""
    user = req.get("user")
    if user is None:
        # No identity yet: authz must not 403 — that would assert we know
        # who the caller is, which we do not. Authn is missing, so 401.
        raise AuthenticationError("authorize() ran before authenticate()")
    allowed = acl.get((resource, action), set())
    if user == "admin" or "*" in allowed or user in allowed:
        return
    raise AuthorizationError(f"{user!r} may not {action} {resource}")


# --------------------------------------------------------------------------- accounting
def audit(req: Request,
          decision: bool,
          resource: str,
          action: str,
          log: List[Tuple[str, str, str, bool]]) -> None:
    """Accounting — record the decision either way, allow or deny."""
    log.append((req.get("user"), resource, action, decision))


# --------------------------------------------------------------------------- middleware
def log_mw(log: List[str]) -> Middleware:
    """Middleware that appends a marker to the caller's log list, then calls next."""
    def wrap(next_handler: Handler) -> Handler:
        def wrapped(req: Request) -> Dict[str, object]:
            log.append(req["path"])
            return next_handler(req)
        return wrapped
    return wrap


def authn_mw(token_store: Dict[str, str]) -> Middleware:
    """Middleware wrapping authenticate(). Must run BEFORE any authz stage."""
    def wrap(next_handler: Handler) -> Handler:
        def wrapped(req: Request) -> Dict[str, object]:
            authenticate(req, token_store)
            return next_handler(req)
        return wrapped
    return wrap


def authz_mw(acl: Dict[Tuple[str, str], Set[str]],
             resource: str,
             action: str,
             audit_log: List[Tuple[str, str, str, bool]]) -> Middleware:
    """Middleware wrapping authorize() plus accounting.

    Every decision — allow OR deny — is recorded before the exception (if
    any) propagates. The audit trail is more valuable on the deny path than
    the allow path; recording only allows is the classic accounting failure.
    """
    def wrap(next_handler: Handler) -> Handler:
        def wrapped(req: Request) -> Dict[str, object]:
            try:
                authorize(req, acl, resource, action)
            except AuthorizationError:
                audit(req, False, resource, action, audit_log)
                raise
            audit(req, True, resource, action, audit_log)
            return next_handler(req)
        return wrapped
    return wrap


# --------------------------------------------------------------------------- composition
def compose(fns: List[Middleware], handler: Handler) -> Handler:
    """Nest middleware around the handler; fns[0] is outermost (runs first).

    A stage that raises unwinds the chain naturally — the handler never runs
    and no later stage executes. The response dict gains a "headers" key.
    """
    def wrapped(req: Request) -> Dict[str, object]:
        chain = handler
        for fn in reversed(fns):
            chain = fn(chain)
        resp = chain(req)
        if isinstance(resp, dict) and "headers" not in resp:
            resp["headers"] = {"Content-Type": "application/json"}
        return resp
    return wrapped
