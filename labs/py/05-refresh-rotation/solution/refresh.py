"""Lab 05 — reference solution."""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
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


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64url_dec(seg: str) -> bytes:
    return base64.urlsafe_b64decode(seg + "=" * ((-len(seg)) % 4))


class RefreshStore:
    def __init__(self) -> None:
        self._by_hash: dict[str, dict] = {}

    @staticmethod
    def hash_token(raw: str) -> str:
        return hashlib.sha256(raw.encode()).hexdigest()

    def put(self, raw: str, record: dict) -> None:
        self._by_hash[self.hash_token(raw)] = record

    def get(self, raw: str) -> Optional[dict]:
        return self._by_hash.get(self.hash_token(raw))

    def mark_rotated(self, raw: str) -> None:
        rec = self._by_hash[self.hash_token(raw)]
        rec["rotated"] = True

    def revoke_family(self, family: str) -> int:
        dead = [h for h, r in self._by_hash.items() if r["family"] == family]
        for h in dead:
            del self._by_hash[h]
        return len(dead)

    def records(self) -> dict[str, dict]:
        return dict(self._by_hash)


def sign_access(user_id: str, ttl: float, now: float, secret: bytes) -> str:
    header = {"alg": "HS256", "typ": "JWT"}
    claims = {"sub": user_id, "iat": int(now), "exp": int(now + ttl)}
    h = _b64url(json.dumps(header, separators=(",", ":")).encode())
    p = _b64url(json.dumps(claims, separators=(",", ":")).encode())
    sig = hmac.new(secret, f"{h}.{p}".encode(), hashlib.sha256).digest()
    return f"{h}.{p}.{_b64url(sig)}"


def verify_access(token: str, secret: bytes, now: float) -> dict:
    try:
        h, p, s = token.split(".")
    except ValueError:
        raise ValueError("malformed")
    header = json.loads(_b64url_dec(h))
    if header.get("alg") != "HS256":
        raise ValueError("bad alg")
    expected = hmac.new(secret, f"{h}.{p}".encode(), hashlib.sha256).digest()
    if not hmac.compare_digest(expected, _b64url_dec(s)):
        raise ValueError("bad signature")
    claims = json.loads(_b64url_dec(p))
    if now >= claims.get("exp", 0):
        raise ValueError("expired")
    return claims


class ReuseDetected(Exception):
    pass


class AuthServer:
    def __init__(self, secret: bytes, clock, access_ttl: float = 900.0,
                 refresh_ttl: float = 604800.0) -> None:
        self.secret = secret
        self.clock = clock
        self.access_ttl = access_ttl
        self.refresh_ttl = refresh_ttl
        self.store = RefreshStore()
        self.revocation_events: list[str] = []
        self._access_issued: dict[str, str] = {}   # access token -> family (for cache invalidation)
        self._revoked_families: set[str] = set()

    def _mint_refresh(self, user_id: str, family: str) -> str:
        raw = secrets.token_urlsafe(32)
        self.store.put(raw, {
            "family": family,
            "user": user_id,
            "expires_at": self.clock.now() + self.refresh_ttl,
            "rotated": False,
        })
        return raw

    def _new_family(self) -> str:
        return secrets.token_urlsafe(16)

    def issue_pair(self, user_id: str) -> tuple[str, str]:
        family = self._new_family()
        access = sign_access(user_id, self.access_ttl, self.clock.now(), self.secret)
        self._access_issued[access] = family
        return access, self._mint_refresh(user_id, family)

    def refresh(self, raw_refresh: str) -> tuple[str, str]:
        rec = self.store.get(raw_refresh)
        if rec is None:
            raise PermissionError("unknown refresh token")
        if rec.get("rotated"):
            # REUSE — the breach signal. Kill the family, remember it happened.
            fam = rec["family"]
            self._revoke_family(fam)
            raise ReuseDetected(f"reuse of rotated token — family {fam} revoked")
        if self.clock.now() >= rec["expires_at"]:
            self._revoke_family(rec["family"])
            raise PermissionError("refresh expired")
        user, family = rec["user"], rec["family"]
        self.store.mark_rotated(raw_refresh)
        access = sign_access(user, self.access_ttl, self.clock.now(), self.secret)
        self._access_issued[access] = family
        return access, self._mint_refresh(user, family)

    def _revoke_family(self, family: str) -> int:
        self._revoked_families.add(family)
        n = self.store.revoke_family(family)
        self.revocation_events.append(family)
        return n

    def revoke_all_for_user(self, user_id: str) -> int:
        fams = {r["family"] for r in self.store.records().values()
                if r["user"] == user_id}
        return sum(self._revoke_family(f) for f in fams)

    def access_family(self, token: str) -> Optional[str]:
        return self._access_issued.get(token)

    def check_access(self, token: str) -> bool:
        try:
            verify_access(token, self.secret, self.clock.now())
        except ValueError:
            return False
        fam = self.access_family(token)
        # Unknown to this issuer, or its family was revoked — both are 'not valid'
        return fam is not None and fam not in self._revoked_families


class IntrospectionCache:
    def __init__(self, server: AuthServer, ttl: float = 60.0) -> None:
        self.server = server
        self.ttl = ttl
        self._cache: dict[str, tuple[bool, float]] = {}
        self.hits = 0
        self.misses = 0

    def introspect(self, token: str) -> bool:
        now = self.server.clock.now()
        entry = self._cache.get(token)
        if entry is not None and entry[1] > now:
            self.hits += 1
            return entry[0]
        self.misses += 1
        valid = self.server.check_access(token)
        self._cache[token] = (valid, now + self.ttl)
        return valid

    def invalidate(self, token: str) -> None:
        self._cache.pop(token, None)

    def invalidate_family(self, family: str) -> None:
        for tok in [t for t, f in self.server._access_issued.items() if f == family]:
            self.invalidate(tok)
