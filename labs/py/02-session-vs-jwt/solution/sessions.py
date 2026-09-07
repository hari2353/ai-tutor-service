"""Lab 02 — reference solution."""
from __future__ import annotations

import secrets
from typing import Optional, Protocol

from jwt import PyJWT
from jwt.exceptions import ExpiredSignatureError, ImmatureSignatureError


class Clock(Protocol):
    def now(self) -> float: ...


class SystemClock:
    def now(self) -> float:
        import time
        return time.time()


class FakeClock:
    def __init__(self, t: float = 0.0) -> None:
        self.t = t

    def now(self) -> float:
        return self.t

    def advance(self, dt: float) -> None:
        self.t += dt


class SessionStore:
    def __init__(self, clock: Clock, ttl: float = 1800.0, sliding: bool = True) -> None:
        self.clock = clock
        self.ttl = ttl
        self.sliding = sliding
        self._sessions: dict[str, dict] = {}

    def create(self, user_id: str, data: Optional[dict] = None) -> str:
        sid = secrets.token_urlsafe(32)
        now = self.clock.now()
        self._sessions[sid] = {
            "user_id": user_id,
            "data": dict(data or {}),
            "created_at": now,
            "expires_at": now + self.ttl,
        }
        return sid

    def validate(self, session_id: str) -> Optional[dict]:
        s = self._sessions.get(session_id)
        if s is None:
            return None
        if self.clock.now() >= s["expires_at"]:
            del self._sessions[session_id]
            return None
        if self.sliding:
            s["expires_at"] = self.clock.now() + self.ttl
        return s

    def revoke(self, session_id: str) -> bool:
        s = self._sessions.pop(session_id, None)
        return s is not None


class StatelessToken:
    def __init__(self, secret: str, clock: Clock) -> None:
        self.secret = secret
        self.clock = clock
        self._jwt = PyJWT()

    def issue(self, user_id: str, ttl: float = 900.0) -> str:
        now = int(self.clock.now())
        claims = {"sub": user_id, "iat": now, "nbf": now, "exp": now + int(ttl)}
        return self._jwt.encode(claims, self.secret, algorithm="HS256")

    def validate(self, token: str) -> dict:
        # Signature verification via PyJWT; exp/nbf checked against the
        # INJECTED clock (PyJWT's internal checks use wall time — a clock you
        # cannot fake, so you check the claims yourself).
        claims = self._jwt.decode(
            token, self.secret, algorithms=["HS256"],
            options={"verify_exp": False, "verify_nbf": False, "verify_iat": False},
        )
        now = self.clock.now()
        if "nbf" in claims and now < claims["nbf"]:
            raise ImmatureSignatureError("Token not yet valid")
        if "exp" in claims and now >= claims["exp"]:
            raise ExpiredSignatureError("Signature has expired")
        return claims

    def revoke(self, token: str) -> bool:
        # There is nothing to delete: statelessness means no server-side record
        # exists. A valid token stays valid until exp, no matter what we do here.
        return False


class HybridAuth:
    def __init__(self, token: StatelessToken, store: SessionStore,
                 refresh_ttl: float = 604800.0) -> None:
        self.token = token
        self.store = store
        self.refresh_ttl = refresh_ttl

    def login(self, user_id: str) -> tuple[str, str]:
        access = self.token.issue(user_id, ttl=900.0)
        refresh_sid = self.store.create(user_id)
        return access, refresh_sid

    def refresh(self, refresh_session_id: str) -> tuple[str, str]:
        s = self.store.validate(refresh_session_id)
        if s is None:
            raise PermissionError("refresh session invalid, expired, or revoked")
        self.store.revoke(refresh_session_id)
        new_refresh = self.store.create(s["user_id"])
        new_access = self.token.issue(s["user_id"], ttl=900.0)
        return new_access, new_refresh

    def logout(self, refresh_session_id: str) -> bool:
        return self.store.revoke(refresh_session_id)
