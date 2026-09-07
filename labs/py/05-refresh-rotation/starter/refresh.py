"""Lab 05 — refresh token rotation with reuse detection + introspection TTL cache.

Rules:
  * All expiry via the injected clock. No sleeps, no wall clock.
  * Refresh tokens are OPAQUE server-issued randoms — the server stores a HASH
    of them, never the raw token (a stolen store must not yield usable tokens).
"""
from __future__ import annotations

import hashlib
import hmac
import json
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


# --------------------------------------------------------------------------- store
class RefreshStore:
    """token_hash -> {family, user, expires_at, rotated: bool}.
    The store only ever sees SHA-256 of the raw token."""

    def __init__(self) -> None:
        self._by_hash: dict[str, dict] = {}

    @staticmethod
    def hash_token(raw: str) -> str:
        # TODO(step 3): SHA-256 hex of the raw token. (SHA-256, not a fast
        # plain compare — production would use a slow KDF; see PRODUCTION.md)
        raise NotImplementedError

    def put(self, raw: str, record: dict) -> None:
        # TODO(step 4)
        raise NotImplementedError

    def get(self, raw: str) -> Optional[dict]:
        # TODO(step 5): lookup by hash; None if absent
        raise NotImplementedError

    def mark_rotated(self, raw: str) -> None:
        # TODO(step 6): set rotated=True, KEEP the record (reuse detection needs
        # the ghost) — store the family id so replay can be traced to its family
        raise NotImplementedError

    def revoke_family(self, family: str) -> int:
        """Delete every record whose family == family. Return count deleted."""
        # TODO(step 7)
        raise NotImplementedError


# --------------------------------------------------------------------------- access tokens
def sign_access(user_id: str, ttl: float, now: float, secret: bytes) -> str:
    """A minimal HS256 JWT: claims {sub, iat, exp}, header {alg, typ}.
    Build it with hmac/hashlib/base64/json — no PyJWT needed for access tokens."""
    # TODO(step 8)
    raise NotImplementedError


def verify_access(token: str, secret: bytes, now: float) -> dict:
    """Decode + verify signature + exp. Raise ValueError on any failure."""
    # TODO(step 9)
    raise NotImplementedError


# --------------------------------------------------------------------------- server
class ReuseDetected(Exception):
    """Raised when a rotated-away refresh token is presented again — a breach signal."""


class AuthServer:
    """Issues (access 15min, refresh 7d). Rotates on every refresh.
    Reuse of a rotated token → the whole family is revoked."""

    def __init__(self, secret: bytes, clock, access_ttl: float = 900.0,
                 refresh_ttl: float = 604800.0) -> None:
        self.secret = secret
        self.clock = clock
        self.access_ttl = access_ttl
        self.refresh_ttl = refresh_ttl
        self.store = RefreshStore()
        self.revocation_events: list[str] = []      # families killed, in order

    def issue_pair(self, user_id: str) -> tuple[str, str]:
        """Login: return (access_token, raw_refresh). Store the refresh HASH
        with a fresh family id."""
        # TODO(step 10)
        raise NotImplementedError

    def refresh(self, raw_refresh: str) -> tuple[str, str]:
        """Rotate: the presented token must be live (not rotated, not expired).
        If it was already rotated → ReuseDetected: revoke_family + record it.
        Otherwise: mark old rotated, mint a new pair in the SAME family."""
        # TODO(step 11)
        raise NotImplementedError

    def revoke_all_for_user(self, user_id: str) -> int:
        """Admin kill-switch: revoke every family belonging to user_id."""
        # TODO(step 12)
        raise NotImplementedError


# --------------------------------------------------------------------------- introspection + cache
class IntrospectionCache:
    """RFC 7662-style: is this access token valid right now? Result cached with
    a TTL; a revocation must INVALIDATE the cached 'valid' immediately."""

    def __init__(self, server: AuthServer, ttl: float = 60.0) -> None:
        self.server = server
        self.ttl = ttl
        self._cache: dict[str, tuple[bool, float]] = {}   # token -> (valid, expires_at)
        self.hits = 0
        self.misses = 0

    def introspect(self, token: str) -> bool:
        """True if the token is valid. Serve from cache while fresh; otherwise
        ask the server, then cache the answer with expires_at = now + ttl."""
        # TODO(step 13)
        raise NotImplementedError

    def invalidate(self, token: str) -> None:
        """Drop the cached entry — called when THIS token's family was revoked."""
        # TODO(step 14)
        raise NotImplementedError
