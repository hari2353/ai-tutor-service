"""Lab 09 — reference solution."""
from __future__ import annotations

import re
import time
from functools import lru_cache
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


# ---------------------------------------------------------------- condition parsing
def _strip_comment(expr: str) -> str:
    """Drop '-- ...' to end of line, OUTSIDE single quotes."""
    in_quote = False
    i = 0
    while i < len(expr):
        ch = expr[i]
        if ch == "'":
            in_quote = not in_quote
        elif not in_quote and expr[i:i + 2] == "--":
            return expr[:i].strip()
        i += 1
    return expr.strip()


def _balanced(expr: str) -> bool:
    return expr.count("'") % 2 == 0


def _split_top(expr: str, keyword: str) -> Optional[tuple[str, str]]:
    """Split on the first top-level ' KEYWORD ' (outside quotes). None if absent."""
    in_quote = False
    i = 0
    kw = f" {keyword} "
    while i < len(expr):
        if expr[i] == "'":
            in_quote = not in_quote
        elif not in_quote and expr[i:i + len(kw)].upper() == kw.upper():
            return expr[:i], expr[i + len(kw):]
        i += 1
    return None


def _eval_condition(cond: str, row: dict) -> bool:
    """col='value' or 'a'='b' — a literal-minded evaluator. Comparisons of two
    quoted literals are plain string equality: '1'='1 is True (the tautology)."""
    cond = cond.strip()
    m = re.fullmatch(r"(\w+)\s*=\s*'([^']*)'", cond)
    if m and m.group(1) in row:
        return str(row[m.group(1)]) == m.group(2)
    # a quoted-literal comparison — tolerate a missing closing quote, which
    # is exactly what a successful quote-break leaves behind:
    m = re.fullmatch(r"'([^']*)'\s*=\s*'([^']*)'?", cond)
    if m:
        return m.group(1) == m.group(2)
    m = re.fullmatch(r"(\w+)\s*=\s*'([^']*)'?", cond)
    if m and m.group(1) in row:
        return str(row[m.group(1)]) == m.group(2)
    raise ValueError(f"cannot evaluate condition: {cond!r}")


def _eval_where(expr: str, row: dict) -> bool:
    """OR binds loosest, AND tighter — one level of each, enough for the demo."""
    or_split = _split_top(expr, "OR")
    if or_split:
        return _eval_where(or_split[0], row) or _eval_where(or_split[1], row)
    and_split = _split_top(expr, "AND")
    if and_split:
        return _eval_where(and_split[0], row) and _eval_where(and_split[1], row)
    return _eval_condition(expr, row)


# ---------------------------------------------------------------- LIKE semantics
def _like_match(text: str, pattern: str) -> bool:
    """SQL LIKE: % = any run, _ = any single char, backslash escapes."""
    @lru_cache(maxsize=None)
    def m(t: str, p: str) -> bool:
        if p == "":
            return t == ""
        if len(p) >= 2 and p[0] == "\\":
            return t.startswith(p[1]) and m(t[1:], p[2:])
        if p[0] == "%":
            return any(m(t[i:], p[1:]) for i in range(len(t) + 1))
        if p[0] == "_":
            return t != "" and m(t[1:], p[1:])
        return t != "" and t[0] == p[0] and m(t[1:], p[1:])
    return m(text, pattern)


class MiniDB:
    def __init__(self) -> None:
        self.users: list[dict] = [
            {"id": 1, "username": "admin", "password": "hunter2",
             "bio": "I am the admin", "is_admin": True},
            {"id": 2, "username": "alice", "password": "correct horse",
             "bio": "just a user", "is_admin": False},
            {"id": 3, "username": "bob", "password": "battery staple",
             "bio": "just another user", "is_admin": False},
        ]

    def query_unsafe(self, sql: str) -> list[dict]:
        m = re.search(r"SELECT\s+\*\s+FROM\s+users\s+WHERE\s+(.*)$",
                      sql, re.IGNORECASE | re.DOTALL)
        if not m:
            raise ValueError("unsupported query shape")
        expr = m.group(1).strip()
        if expr.endswith("'") and not _balanced(expr):
            expr = expr[:-1]          # swallow the dangling quote-remainder
        expr = _strip_comment(expr)  # ...and 'admin'-- style payloads
        return [row for row in self.users if _eval_where(expr, row)]

    def query_parameterized(self, where_col: str, where_val: str) -> list[dict]:
        allowed = {"id", "username", "password", "bio", "is_admin"}
        if where_col not in allowed:
            raise ValueError(f"unknown column: {where_col}")
        return [row for row in self.users
                if row.get(where_col) == where_val or str(row.get(where_col)) == where_val]

    def query_like_unsafe(self, pattern: str) -> list[dict]:
        """LIKE '%<pattern>%': % and _ in the pattern are LIVE WILDCARDS —
        input '%' matches every row (enumeration primitive)."""
        like = f"%{pattern}%"
        return [r for r in self.users if _like_match(r["username"], like)]

    def query_like_parameterized(self, pattern: str) -> list[dict]:
        """The fix: % and _ in the BOUND value are escaped to literals first."""
        escaped = pattern.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        like = f"%{escaped}%"
        return [r for r in self.users if _like_match(r["username"], like)]

    def order_by(self, column: str, descending: bool = False) -> list[dict]:
        allowed = {"id", "username", "password", "bio", "is_admin"}
        if column not in allowed:
            raise ValueError(f"column not allowed in ORDER BY: {column}")
        return sorted(self.users, key=lambda r: r[column], reverse=descending)
