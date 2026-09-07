"""Lab 02 — session store vs stateless tokens. Fill in every TODO.

Rules:
  * No time.sleep() / time.time() — all expiry logic goes through the injected Clock.
  * Session ids come from secrets.token_urlsafe — never a counter, never guessable.
"""
from __future__ import annotations

import secrets
from typing import Optional, Protocol

from jwt import PyJWT  # you MAY use PyJWT for StatelessToken (that's the point)


# --------------------------------------------------------------------------- clock
class Clock(Protocol):
    def now(self) -> float: ...


class SystemClock:
    def now(self) -> float:
        import time
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


# --------------------------------------------------------------------------- session store
class SessionStore:
    """Server-side sessions: opaque id -> server-held record. Revocable."""

    def __init__(self, clock: Clock, ttl: float = 1800.0, sliding: bool = True) -> None:
        self.clock = clock
        self.ttl = ttl
        self.sliding = sliding
        self._sessions: dict[str, dict] = {}

    def create(self, user_id: str, data: Optional[dict] = None) -> str:
        """Create a session; return the opaque session id (secrets.token_urlsafe).
        Record created_at and expires_at = now + ttl."""
        # TODO(step 3)
        raise NotImplementedError

    def validate(self, session_id: str) -> Optional[dict]:
        """Return the session dict if it exists and is unexpired, else None.
        If sliding and valid, extend expires_at = now + ttl.
        Never resurrect an expired session."""
        # TODO(step 4)
        raise NotImplementedError

    def revoke(self, session_id: str) -> bool:
        """Delete the session. Instant effect: the very next validate() is None.
        Return True if a live session was deleted."""
        # TODO(step 5)
        raise NotImplementedError


# --------------------------------------------------------------------------- stateless tokens
class StatelessToken:
    """JWT HS256 — the state it carries is in the token; the server holds nothing."""

    def __init__(self, secret: str, clock: Clock) -> None:
        self.secret = secret
        self.clock = clock

    def issue(self, user_id: str, ttl: float = 900.0) -> str:
        """Encode claims {sub, iat, nbf, exp} with algorithm HS256. Return the JWT string."""
        # TODO(step 6) — use the PyJWT instance imported above
        raise NotImplementedError

    def validate(self, token: str) -> dict:
        """Decode + verify signature + exp/nbf. Raise jwt.InvalidTokenError on any failure.
        On success return the claims dict."""
        # TODO(step 7)
        raise NotImplementedError

    def revoke(self, token: str) -> bool:
        """THE HONEST TEST: prove revocation is impossible for a stateless token.
        Whatever you do here, a still-valid token must keep validating — there is
        nowhere to record 'this token is dead'. Return False always."""
        # TODO(step 8)
        raise NotImplementedError


# --------------------------------------------------------------------------- hybrid
class HybridAuth:
    """Short-lived access JWT + server-side refresh session with rotation.

    The hybrid's honest pitch: 99% of requests are verified statelessly (fast),
    and the revocation lever lives on the refresh side (server-side session).
    """

    def __init__(self, token: StatelessToken, store: SessionStore,
                 refresh_ttl: float = 604800.0) -> None:
        self.token = token
        self.store = store
        self.refresh_ttl = refresh_ttl

    def login(self, user_id: str) -> tuple[str, str]:
        """Return (access_jwt, refresh_session_id). Access is short-lived
        (use the token issuer's default ttl), refresh is a server-side session."""
        # TODO(step 9)
        raise NotImplementedError

    def refresh(self, refresh_session_id: str) -> tuple[str, str]:
        """Rotate: validate the refresh session, revoke it, create a fresh one,
        issue a fresh access token. Raise PermissionError if the refresh
        session is invalid/expired/revoked."""
        # TODO(step 10)
        raise NotImplementedError

    def logout(self, refresh_session_id: str) -> bool:
        """Revoke the refresh session — the revocation lever."""
        # TODO(step 11)
        raise NotImplementedError
