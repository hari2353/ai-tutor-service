"""Lab 10 — API security controls: BOLA/IDOR, mass assignment, rate limiting,
user enumeration. Each vulnerability is built, demonstrated, then fixed.

Rules: all time via the injectable clock. No real HTTP — endpoints are methods.
"""
from __future__ import annotations

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


# --------------------------------------------------------------------------- the API
class Api:
    """A tiny REST-ish API over an in-memory user + order store.

    session_token -> user_id is the AUTHENTICATION layer (already done).
    The AUTHORIZATION bugs are yours to demonstrate and fix."""

    def __init__(self) -> None:
        self.users: dict[int, dict] = {
            1: {"id": 1, "username": "alice", "is_admin": False,
                "display_name": "Alice", "email": "alice@example.com"},
            2: {"id": 2, "username": "bob", "is_admin": False,
                "display_name": "Bob", "email": "bob@example.com"},
            3: {"id": 3, "username": "root", "is_admin": True,
                "display_name": "Root", "email": "root@example.com"},
        }
        self.orders: dict[int, dict] = {
            100: {"id": 100, "user_id": 1, "total": "49.99", "items": ["book"]},
            101: {"id": 101, "user_id": 2, "total": "5.00", "items": ["pen"]},
        }
        self._sessions: dict[str, int] = {}       # token -> user_id
        self._next_user_id = 4
        self._next_order_id = 200

    # ---- auth (provided, not the bug) -----------------------------------------
    def login(self, username: str, password: str) -> Optional[str]:
        if username in ("alice", "bob", "root") and password == "pw":
            uid = {u["username"]: u["id"] for u in self.users.values()}[username]
            token = f"sess-{uid}"
            self._sessions[token] = uid
            return token
        return None

    def _caller(self, session_token: str) -> int:
        uid = self._sessions.get(session_token)
        if uid is None:
            raise PermissionError("not authenticated")
        return uid

    # ---- (1) BOLA / IDOR: GET /users/{id}/orders/{oid} -------------------------
    def get_order_vulnerable(self, session_token: str, user_id: int,
                             order_id: int) -> dict:
        """Authenticates the caller, looks up order_id... and never checks
        that the order belongs to caller's user_id. THE BUG."""
        # TODO(step 3): authenticate; return the order regardless of ownership
        raise NotImplementedError

    def get_order_fixed(self, session_token: str, user_id: int,
                        order_id: int) -> dict:
        """The fix: object-level authorization — the caller's user_id must
        match the order's user_id. Raise PermissionError otherwise."""
        # TODO(step 4)
        raise NotImplementedError

    # ---- (2) mass assignment: PATCH /users/{id} ---------------------------------
    def update_user_vulnerable(self, session_token: str, user_id: int,
                               body: dict) -> dict:
        """Binds the ENTIRE request dict onto the user record. is_admin rides
        along if the client sends it. THE BUG."""
        # TODO(step 5)
        raise NotImplementedError

    def update_user_fixed(self, session_token: str, user_id: int,
                          body: dict) -> dict:
        """The fix: a field ALLOWLIST (display_name, email only). Ignore or
        reject everything else — is_admin must never be client-settable here.
        Also: users may only update THEMSELVES (object-level authz again)."""
        # TODO(step 6)
        raise NotImplementedError

    # ---- (4) enumeration: POST /login -------------------------------------------
    def login_vulnerable(self, username: str, password: str) -> str:
        """Distinguishes 'user not found' from 'wrong password' — a free
        username-exists oracle for credential stuffing. THE BUG."""
        # TODO(step 7): user missing -> 'user not found'; wrong pw ->
        # 'wrong password'; match -> 'ok'
        raise NotImplementedError

    def login_fixed(self, username: str, password: str) -> str:
        """The fix: ONE uniform failure message. Timing placeholder: the
        missing-user path runs the same dummy work as the wrong-pw path."""
        # TODO(step 8)
        raise NotImplementedError


# --------------------------------------------------------------------------- (3) rate limiter
class TokenBucketLimiter:
    """Token bucket per key: capacity tokens, refill_rate tokens/second.
    burst up to capacity, then refill-limited; empty bucket -> rejected."""

    def __init__(self, clock, capacity: float = 5.0,
                 refill_rate: float = 0.1) -> None:
        self.clock = clock
        self.capacity = capacity
        self.refill_rate = refill_rate
        self._buckets: dict[str, tuple[float, float]] = {}   # key -> (tokens, last)

    def allow(self, key: str, cost: float = 1.0) -> bool:
        """Try to spend `cost` tokens for key. Refill elapsed*rate first
        (via the clock). Return False if fewer than cost tokens remain —
        and spend NOTHING in that case."""
        # TODO(step 9)
        raise NotImplementedError
