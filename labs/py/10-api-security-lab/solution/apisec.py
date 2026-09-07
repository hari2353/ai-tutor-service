"""Lab 10 — reference solution."""
from __future__ import annotations

import hashlib
import hmac
import time
from typing import Optional


class SystemClock:
    def now(self) -> float:
        return time.time()


class FakeClock:
    def __init__(self, t: float = 0.0) -> None:
        self.t = t

    def now(self) -> float:
        return self.t

    def advance(self, dt: float) -> None:
        self.t += dt


class Api:
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
        self._sessions: dict[str, int] = {}
        self._next_user_id = 4
        self._next_order_id = 200

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

    # ---- (1) BOLA / IDOR ---------------------------------------------------------
    def get_order_vulnerable(self, session_token: str, user_id: int,
                             order_id: int) -> dict:
        caller = self._caller(session_token)          # authenticated...
        order = self.orders.get(order_id)
        if order is None:
            raise LookupError("no such order")
        return dict(order)                            # ...but never authorized

    def get_order_fixed(self, session_token: str, user_id: int,
                        order_id: int) -> dict:
        caller = self._caller(session_token)
        order = self.orders.get(order_id)
        if order is None:
            raise LookupError("no such order")
        if order["user_id"] != caller:                # object-level authz
            raise PermissionError("not your order")
        return dict(order)

    # ---- (2) mass assignment -------------------------------------------------------
    def update_user_vulnerable(self, session_token: str, user_id: int,
                               body: dict) -> dict:
        self._caller(session_token)
        user = self.users.get(user_id)
        if user is None:
            raise LookupError("no such user")
        user.update(body)                             # everything rides along
        return dict(user)

    def update_user_fixed(self, session_token: str, user_id: int,
                          body: dict) -> dict:
        caller = self._caller(session_token)
        if caller != user_id:                         # only edit yourself
            raise PermissionError("you may only update your own account")
        user = self.users.get(user_id)
        if user is None:
            raise LookupError("no such user")
        allowed = {"display_name", "email"}
        for k, v in body.items():
            if k in allowed:
                user[k] = v                           # allowlisted fields only
        return dict(user)

    # ---- (4) enumeration -------------------------------------------------------------
    def login_vulnerable(self, username: str, password: str) -> str:
        user = next((u for u in self.users.values()
                     if u["username"] == username), None)
        if user is None:
            return "user not found"                   # the oracle
        if password != "pw":
            return "wrong password"                   # ...confirmed the user
        token = f"sess-{user['id']}"
        self._sessions[token] = user["id"]
        return "ok"

    def login_fixed(self, username: str, password: str) -> str:
        # timing placeholder: burn the same hash work whether or not the user exists
        dummy_salt = "pepper-for-missing-users"
        hmac.new(dummy_salt.encode(), password.encode(), hashlib.sha256).digest()
        user = next((u for u in self.users.values()
                     if u["username"] == username), None)
        if user is None:
            return "invalid credentials"              # one uniform failure
        if password != "pw":
            return "invalid credentials"
        token = f"sess-{user['id']}"
        self._sessions[token] = user["id"]
        return "ok"


class TokenBucketLimiter:
    def __init__(self, clock, capacity: float = 5.0,
                 refill_rate: float = 0.1) -> None:
        self.clock = clock
        self.capacity = capacity
        self.refill_rate = refill_rate
        self._buckets: dict[str, tuple[float, float]] = {}

    def allow(self, key: str, cost: float = 1.0) -> bool:
        now = self.clock.now()
        tokens, last = self._buckets.get(key, (self.capacity, now))
        tokens = min(self.capacity, tokens + (now - last) * self.refill_rate)
        if tokens < cost:
            self._buckets[key] = (tokens, now)
            return False
        self._buckets[key] = (tokens - cost, now)
        return True
