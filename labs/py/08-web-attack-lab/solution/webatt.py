"""Lab 08 — reference solution."""
from __future__ import annotations

import html
import secrets
import time
from typing import Callable, Optional
from urllib.parse import urlsplit


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


# --------------------------------------------------------------------------- XSS
class TemplateEngine:
    def __init__(self, autoescape: bool = True) -> None:
        self.autoescape = autoescape

    def render(self, template: str, context: dict) -> str:
        out = template
        for key, value in context.items():
            rendered = str(value)
            if self.autoescape:
                rendered = html.escape(rendered, quote=True)
            out = out.replace("{" + key + "}", rendered)
        if "{" in out and "}" in out:
            import re
            leftover = re.findall(r"\{([a-zA-Z_][a-zA-Z0-9_]*)\}", out)
            if leftover:
                raise KeyError(leftover[0])
        return out


# --------------------------------------------------------------------------- CSRF
class CsrfProtectingFormHandler:
    def __init__(self, clock, token_ttl: float = 600.0) -> None:
        self.clock = clock
        self.token_ttl = token_ttl
        self._tokens: dict[str, tuple[str, float]] = {}

    def issue_token(self, session_id: str) -> str:
        token = secrets.token_urlsafe(32)
        self._tokens[session_id] = (token, self.clock.now() + self.token_ttl)
        return token

    def submit(self, session_id: str, form: dict) -> str:
        rec = self._tokens.get(session_id)
        if rec is None:
            raise PermissionError("no CSRF token issued for this session")
        token, expires_at = rec
        supplied = form.get("csrf_token")
        if supplied != token:
            raise PermissionError("CSRF token missing or wrong")
        if self.clock.now() >= expires_at:
            raise PermissionError("CSRF token expired")
        return "accepted"


# --------------------------------------------------------------------------- SSRF
def ip_in_cidr(ip: str, cidr: str) -> bool:
    try:
        i = _ip_to_int(ip)
        base, prefix_str = cidr.split("/")
        prefix = int(prefix_str)
        c = _ip_to_int(base)
        mask = (0xFFFFFFFF << (32 - prefix)) & 0xFFFFFFFF
        return (i & mask) == (c & mask)
    except (ValueError, IndexError):
        return False


def _ip_to_int(ip: str) -> int:
    parts = ip.split(".")
    if len(parts) != 4:
        raise ValueError(ip)
    val = 0
    for p in parts:
        octet = int(p)
        if not 0 <= octet <= 255:
            raise ValueError(ip)
        val = (val << 8) | octet
    return val


PRIVATE_RANGES = [
    "10.0.0.0/8", "127.0.0.0/8", "169.254.0.0/16",
    "172.16.0.0/12", "192.168.0.0/16", "0.0.0.0/8", "192.0.2.0/24",
]

BLOCKED_HOSTS = ("metadata.google.internal", "instance-data")


class FetchDenied(Exception):
    def __init__(self, url: str, why: str):
        super().__init__(f"refused {url}: {why}")
        self.url = url
        self.why = why


class UrlFetcher:
    def __init__(self, resolver: Callable[[str], str],
                 fetch: Callable[[str], tuple[int, str]],
                 extra_blocked_hosts=BLOCKED_HOSTS) -> None:
        self.resolver = resolver
        self.fetch = fetch
        self.extra_blocked_hosts = tuple(extra_blocked_hosts)

    def _check_url(self, url: str) -> None:
        parts = urlsplit(url)
        if parts.scheme not in ("http", "https"):
            raise FetchDenied(url, f"scheme {parts.scheme!r} not allowed")
        host = parts.hostname or ""
        if not host:
            raise FetchDenied(url, "no host")
        if host in self.extra_blocked_hosts:
            raise FetchDenied(url, "blocked metadata host")
        ip = self.resolver(host)
        if ":" in ip:   # IPv6 text — block loopback/link-local/unique-local
            low = ip.lower()
            if low == "::1" or low.startswith("fe80:") or low.startswith("fc") \
                    or low.startswith("fd"):
                raise FetchDenied(url, f"IPv6 {ip} is private/loopback")
            raise FetchDenied(url, "IPv6 not allowed in this lab")
        for cidr in PRIVATE_RANGES:
            if ip_in_cidr(ip, cidr):
                raise FetchDenied(url, f"{host} resolves to private {ip} ({cidr})")

    def get(self, url: str, max_redirects: int = 3) -> tuple[int, str]:
        current = url
        for _ in range(max_redirects + 1):
            self._check_url(current)               # EVERY hop re-checked
            status, body_or_target = self.fetch(current)
            if status in (301, 302, 303, 307, 308):
                current = body_or_target
                continue
            return status, body_or_target
        raise FetchDenied(url, "too many redirects")
