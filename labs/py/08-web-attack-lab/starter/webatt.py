"""Lab 08 — XSS, CSRF, SSRF mechanics in miniature.

Three independent sections; each has a vulnerable and a fixed mode:
  * XSS:  TemplateEngine with autoescape ON vs raw interpolation
  * CSRF: form handler with per-session CSRF tokens (clock-expiring)
  * SSRF: URL fetcher with scheme + private-CIDR allowlist, redirect re-checks

Rules: all time via the injected clock. The SSRF fetcher takes a fake resolver
and a fake fetch function — no network, ever.
"""
from __future__ import annotations

import html
import secrets
import time
from typing import Callable, Optional


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


# --------------------------------------------------------------------------- XSS
class TemplateEngine:
    """Renders 'Hello {name}' style templates from a context dict.

    autoescape=True  — every substituted value goes through html escaping
    autoescape=False — raw interpolation (the vulnerability)
    """

    def __init__(self, autoescape: bool = True) -> None:
        self.autoescape = autoescape

    def render(self, template: str, context: dict) -> str:
        """Substitute {key} for context[key]. Escape each value iff autoescape.
        Raise KeyError on a missing key (fail closed — never render partial)."""
        # TODO(step 3)
        raise NotImplementedError


# --------------------------------------------------------------------------- CSRF
class CsrfProtectingFormHandler:
    """Per-session CSRF tokens, expiring via the clock.

    The token is session-bound: a token from ANOTHER session is rejected even
    if it's syntactically valid — otherwise the attacker just needs any token."""

    def __init__(self, clock, token_ttl: float = 600.0) -> None:
        self.clock = clock
        self.token_ttl = token_ttl
        self._tokens: dict[str, tuple[str, float]] = {}   # session -> (token, expires_at)

    def issue_token(self, session_id: str) -> str:
        """Fresh random token for THIS session, expiring at now + ttl."""
        # TODO(step 4)
        raise NotImplementedError

    def submit(self, session_id: str, form: dict) -> str:
        """Accept the POST iff form['csrf_token'] is THIS session's CURRENT
        token and it hasn't expired. Raise PermissionError otherwise."""
        # TODO(step 5)
        raise NotImplementedError


# --------------------------------------------------------------------------- SSRF
def ip_in_cidr(ip: str, cidr: str) -> bool:
    """IPv4 only: is ip inside cidr (e.g. '10.0.0.0/8')? Implement the math
    yourself: mask = (0xffffffff << (32-prefix)) & 0xffffffff, compare networks."""
    # TODO(step 6)
    raise NotImplementedError


PRIVATE_RANGES = [
    "10.0.0.0/8", "127.0.0.0/8", "169.254.0.0/16",
    "172.16.0.0/12", "192.168.0.0/16", "0.0.0.0/8", "192.0.2.0/24",
]

BLOCKED_HOSTS = ("metadata.google.internal", "instance-data")   # DNS-level names


class FetchDenied(Exception):
    def __init__(self, url: str, why: str):
        super().__init__(f"refused {url}: {why}")
        self.url = url
        self.why = why


class UrlFetcher:
    """SSRF-safe fetcher. resolver(host) -> ip is injectable (no real DNS).
    fetch(url) -> (status, body) is injectable (no real network).

    Checks: scheme in (http, https); resolved IP not in any private range;
    blocked metadata hostnames; and on a redirect, the TARGET is re-checked."""

    def __init__(self, resolver: Callable[[str], str],
                 fetch: Callable[[str], tuple[int, str]],
                 extra_blocked_hosts=BLOCKED_HOSTS) -> None:
        self.resolver = resolver
        self.fetch = fetch
        self.extra_blocked_hosts = tuple(extra_blocked_hosts)

    def _check_url(self, url: str) -> None:
        # TODO(step 7): parse scheme; reject non-http(s) outright (file:, gopher:,
        # internal schemes). Resolve host; reject blocked names; reject any
        # private-range IP via ip_in_cidr (also reject IPv6 ::1/loopback text).
        raise NotImplementedError

    def get(self, url: str, max_redirects: int = 3) -> tuple[int, str]:
        """Fetch with redirect-following that re-validates EVERY hop. Refuse
        the whole chain if any hop fails a check (never follow blindly)."""
        # TODO(step 8)
        raise NotImplementedError
