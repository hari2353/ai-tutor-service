"""Lab 06 — OAuth 2.0 authorization-code + PKCE flow, all parties in-process.

Rules:
  * No network. The browser is you; the AS and client are objects.
  * All expiry via the injected clock (codes live 60s).
  * PKCE: code_challenge = b64url(sha256(code_verifier)) for S256. The verifier
    NEVER travels in the authorization request — only its hash does.
"""
from __future__ import annotations

import base64
import hashlib
import secrets
import time
from typing import Optional


# --------------------------------------------------------------------------- clock
class SystemClock:
    def now(self) -> float:
        return time.time()


class FakeClock:
    """Deterministic clock — advance() instead of sleeping."""
    def __init__(self, t: float = 0.0) -> None:
        self.t = t

    def now(self) -> float:
        # TODO(step 1)
        raise NotImplementedError

    def advance(self, dt: float) -> None:
        # TODO(step 2)
        raise NotImplementedError


# --------------------------------------------------------------------------- PKCE helpers
def pkce_s256_challenge(verifier: str) -> str:
    """b64url(sha256(verifier_ascii)) with padding stripped — RFC 7636 §4.2.
    The verifier is 43-128 chars of unreserved characters."""
    # TODO(step 3)
    raise NotImplementedError


def pkce_verifier_ok(verifier: str) -> bool:
    """43-128 chars, [A-Za-z0-9-._~] only (RFC 7636 §4.1)."""
    # TODO(step 4)
    raise NotImplementedError


# --------------------------------------------------------------------------- errors
class OAuthError(Exception):
    """The AS refused — map to invalid_request / invalid_grant / access_denied
    with a `reason` attribute so tests can assert on the *why*."""
    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


# --------------------------------------------------------------------------- the AS
class AuthorizationServer:
    """The authorization endpoint + the token endpoint, in miniature.

    Registered clients have: client_id, allowed redirect_uris, allowed scopes.
    Authorization codes are single-use, 60s TTL, bound to (client_id,
    redirect_uri, code_challenge)."""

    def __init__(self, clock, code_ttl: float = 60.0,
                 require_s256: bool = True) -> None:
        self.clock = clock
        self.code_ttl = code_ttl
        self.require_s256 = require_s256
        self.clients: dict[str, dict] = {}
        self._codes: dict[str, dict] = {}
        self.tokens_issued: list[dict] = []

    def register_client(self, client_id: str, redirect_uris: list[str],
                        scopes: list[str]) -> None:
        # TODO(step 5)
        raise NotImplementedError

    # ---- authorization endpoint (front-channel: browser hits this) ------------
    def authorize(self, client_id: str, redirect_uri: str, scope: str,
                  code_challenge: str, code_challenge_method: str = "S256",
                  state: str = "x") -> str:
        """User is already authenticated and consented. Validate client_id,
        redirect_uri (exact match against the registered list), scope (all
        requested must be allowed), challenge method (reject 'plain' when
        require_s256). On success mint a single-use code bound to everything
        and return ?code=...&state=... as the redirect string."""
        # TODO(step 6)
        raise NotImplementedError

    # ---- token endpoint (back-channel: the client's server hits this) ---------
    def token(self, grant_type: str, code: str, client_id: str,
              redirect_uri: str, code_verifier: str) -> dict:
        """Code exchange. grant_type MUST be 'authorization_code'. The code
        must exist, be unexpired, UNUSED, bound to this client+redirect_uri,
        and sha256(code_verifier) must equal the stored challenge.
        On success: mark used, return {'access_token':..., 'scope':...}."""
        # TODO(step 7)
        raise NotImplementedError


# --------------------------------------------------------------------------- the client
class ClientApp:
    """A public SPA/native client — no client secret, PKCE is its defense."""

    def __init__(self, client_id: str, redirect_uri: str) -> None:
        self.client_id = client_id
        self.redirect_uri = redirect_uri
        self.verifier: Optional[str] = None
        self.state: Optional[str] = None
        self.tokens: Optional[dict] = None

    def begin(self) -> dict:
        """Generate code_verifier + state; return the authorize-redirect params
        (client_id, redirect_uri, response_type='code', scope, code_challenge,
        code_challenge_method='S256', state)."""
        # TODO(step 8)
        raise NotImplementedError

    def complete(self, server: "AuthorizationServer", callback_params: dict) -> dict:
        """Called with ?code=...&state=... from the redirect. Check state
        matches ours (CSRF on the callback), then exchange at the token endpoint
        with the stored verifier. Store and return the tokens."""
        # TODO(step 9)
        raise NotImplementedError


# --------------------------------------------------------------------------- protected resource
class ProtectedResource:
    """Checks a bearer token against what the AS issued."""

    def __init__(self, server: AuthorizationServer) -> None:
        self.server = server

    def get(self, access_token: str) -> dict:
        """Return the resource if the token was issued by the AS; else OAuthError."""
        # TODO(step 10)
        raise NotImplementedError
