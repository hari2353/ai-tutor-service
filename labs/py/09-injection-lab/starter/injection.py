"""Lab 09 — SQL injection and why parameterization wins.

A tiny in-memory "database" with TWO query methods:
  * query_unsafe(sql)          — string-concatenates user input into a WHERE
                                clause and naively evaluates it: a mini parser
                                where an injected quote breaks out to a
                                TAUTOLOGY ('1'='1' is always true).
  * query_parameterized(col, val) — the value can never become syntax.

Rules:
  * The unsafe parser is DELIBERATELY literal: it must be exploitable by
    ' OR '1'='1 style payloads. That's the demonstration.
  * The parameterized path must be immune to every payload the unsafe one
    falls for.
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


# --------------------------------------------------------------------------- the "database"
class MiniDB:
    """One table of users: (id, username, password, bio, is_admin)."""

    def __init__(self) -> None:
        self.users: list[dict] = [
            {"id": 1, "username": "admin", "password": "hunter2",
             "bio": "I am the admin", "is_admin": True},
            {"id": 2, "username": "alice", "password": "correct horse",
             "bio": "just a user", "is_admin": False},
            {"id": 3, "username": "bob", "password": "battery staple",
             "bio": "just another user", "is_admin": False},
        ]

    # ---- the vulnerable one --------------------------------------------------
    def query_unsafe(self, sql: str) -> list[dict]:
        """Accept SQL like:  SELECT * FROM users WHERE username = '<INPUT>'
        (also password = '<INPUT>'). Build the query by CONCATENATING sql's
        literal parts with what the caller passed — then evaluate the WHERE
        clause with a literal parser:
          * strip a trailing '  quote-remainder,
          * treat " OR " as a disjunction,
          * treat x='y' as equality, and a comparison with IDENTICAL literals
            on both sides ('1'='1') as TRUE (the tautology).
        Rows matching the final expression are returned. This must be
        EXPLOITABLE — that's the point of the lab.
        """
        # TODO(step 3)
        raise NotImplementedError

    # ---- the safe one ----------------------------------------------------------
    def query_parameterized(self, where_col: str, where_val: str) -> list[dict]:
        """The value can never become syntax: match rows where
        row[where_col] == where_val (exact string equality, nothing parsed).
        Reject unknown columns with ValueError."""
        # TODO(step 4)
        raise NotImplementedError

    # ---- LIKE: wildcards are the trap ------------------------------------------
    def query_like_unsafe(self, pattern: str) -> list[dict]:
        """LIKE '%<pattern>%': % matches any run, _ any single char. The
        pattern is concatenated RAW, so input '%' matches EVERY row — an
        enumeration primitive. Implement SQL LIKE semantics (% and _, no
        escape processing)."""
        # TODO(step 5)
        raise NotImplementedError

    def query_like_parameterized(self, pattern: str) -> list[dict]:
        """The fix: escape % _ \\ in the bound value FIRST, so the user's
        percent sign can only ever mean a literal percent sign."""
        # TODO(step 6)
        raise NotImplementedError

    # ---- ORDER BY: the honest parameterization exception -----------------------
    def order_by(self, column: str, descending: bool = False) -> list[dict]:
        """ORDER BY cannot be parameterized (column names are syntax, not
        values). The fix: an ALLOWLIST. Unknown column -> ValueError."""
        # TODO(step 7)
        raise NotImplementedError
