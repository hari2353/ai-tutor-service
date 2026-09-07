"""Lab 04 — reference solution."""
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


def b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def b64url_decode(segment: str) -> bytes:
    pad = (-len(segment)) % 4
    return base64.urlsafe_b64decode(segment + "=" * pad)


def hs256_sign(message: bytes, secret: bytes) -> bytes:
    return hmac.new(secret, message, hashlib.sha256).digest()


def encode_jwt(claims: dict, alg: str, key: Optional[bytes],
               header_extra: Optional[dict] = None) -> str:
    header = {"alg": alg, "typ": "JWT"}
    if header_extra:
        header.update(header_extra)
    h = b64url_encode(json.dumps(header, separators=(",", ":")).encode())
    p = b64url_encode(json.dumps(claims, separators=(",", ":")).encode())
    signing_input = f"{h}.{p}".encode()
    if alg in ("none", "None", "NONE", ""):
        sig = b""
    elif alg == "HS256":
        sig = hs256_sign(signing_input, key)
    else:
        raise ValueError(f"unsupported alg in encode_jwt: {alg}")
    return f"{h}.{p}.{b64url_encode(sig)}"


class InsecureAlgNoneVerifier:
    def __init__(self, secret: bytes, clock) -> None:
        self.secret = secret
        self.clock = clock

    def verify(self, token: str) -> dict:
        h_seg, p_seg, s_seg = token.split(".")
        header = json.loads(b64url_decode(h_seg))
        alg = header.get("alg")
        claims = json.loads(b64url_decode(p_seg))
        signing_input = f"{h_seg}.{p_seg}".encode()
        if alg in ("none", "None", ""):
            # THE BUG: attacker-controlled alg skips verification entirely.
            return claims
        if alg == "HS256" and hmac.compare_digest(
                hs256_sign(signing_input, self.secret), b64url_decode(s_seg)):
            return claims
        raise ValueError("verification failed")


def make_verifier_insecure_none(secret: bytes, clock) -> InsecureAlgNoneVerifier:
    return InsecureAlgNoneVerifier(secret, clock)


def make_verifier_secure_none(secret: bytes, clock) -> SecurePinnedVerifier:
    return SecurePinnedVerifier(secret, clock)


def make_verifier_insecure_confusion(rsa_public_pem: bytes, clock) -> InsecureConfusionVerifier:
    return InsecureConfusionVerifier(rsa_public_pem, clock)


def make_verifier_secure_confusion(rsa_public_pem: bytes, clock) -> SecureConfusionVerifier:
    return SecureConfusionVerifier(rsa_public_pem, clock)


class SecurePinnedVerifier:
    def __init__(self, secret: bytes, clock) -> None:
        self.secret = secret
        self.clock = clock

    def verify(self, token: str) -> dict:
        h_seg, p_seg, s_seg = token.split(".")
        header = json.loads(b64url_decode(h_seg))
        if header.get("alg") != "HS256":
            raise ValueError("algorithm not allowed — pinned to HS256")
        signing_input = f"{h_seg}.{p_seg}".encode()
        if not hmac.compare_digest(hs256_sign(signing_input, self.secret),
                                   b64url_decode(s_seg)):
            raise ValueError("signature verification failed")
        claims = json.loads(b64url_decode(p_seg))
        now = self.clock.now()
        if "exp" in claims and now >= claims["exp"]:
            raise ValueError("expired")
        if "nbf" in claims and now < claims["nbf"]:
            raise ValueError("not yet valid")
        return claims


class InsecureConfusionVerifier:
    def __init__(self, rsa_public_pem: bytes, clock) -> None:
        self.public_pem = rsa_public_pem
        self.clock = clock

    def verify(self, token: str) -> dict:
        h_seg, p_seg, s_seg = token.split(".")
        header = json.loads(b64url_decode(h_seg))
        alg = header.get("alg")
        claims = json.loads(b64url_decode(p_seg))
        signing_input = f"{h_seg}.{p_seg}".encode()
        if alg == "HS256":
            # THE BUG: the RSA public PEM bytes used as an HMAC secret.
            if hmac.compare_digest(hs256_sign(signing_input, self.public_pem),
                                   b64url_decode(s_seg)):
                return claims
        elif alg == "RS256":
            from cryptography.hazmat.primitives import hashes, serialization
            from cryptography.hazmat.primitives.asymmetric import padding
            key = serialization.load_pem_public_key(self.public_pem)
            try:
                key.verify(b64url_decode(s_seg), signing_input,
                           padding.PKCS1v15(), hashes.SHA256())
                return claims
            except Exception:
                pass
        raise ValueError("verification failed")


class SecureConfusionVerifier:
    def __init__(self, rsa_public_pem: bytes, clock) -> None:
        self.public_pem = rsa_public_pem
        self.clock = clock

    def verify(self, token: str) -> dict:
        h_seg, p_seg, s_seg = token.split(".")
        header = json.loads(b64url_decode(h_seg))
        if header.get("alg") != "RS256":
            raise ValueError("algorithm not allowed — this issuer uses RS256 only")
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import padding
        key = serialization.load_pem_public_key(self.public_pem)
        key.verify(b64url_decode(s_seg), f"{h_seg}.{p_seg}".encode(),
                   padding.PKCS1v15(), hashes.SHA256())
        claims = json.loads(b64url_decode(p_seg))
        now = self.clock.now()
        if "exp" in claims and now >= claims["exp"]:
            raise ValueError("expired")
        return claims


WEAK_DICTIONARY = [
    b"secret", b"password", b"123456", b"jwt_secret", b"changeme",
    b"letmein", b"qwerty", b"admin", b"test", b"key",
    b"iloveyou", b"monkey", b"dragon", b"supersecret", b"mysecret",
]


def crack_hs256_secret(token: str, dictionary=WEAK_DICTIONARY) -> Optional[bytes]:
    h_seg, p_seg, s_seg = token.split(".")
    signing_input = f"{h_seg}.{p_seg}".encode()
    signature = b64url_decode(s_seg)
    for candidate in dictionary:
        if hmac.compare_digest(hs256_sign(signing_input, candidate), signature):
            return candidate
    return None


class StatelessGateway:
    def __init__(self, secret: bytes, clock, ttl: float = 900.0) -> None:
        self.secret = secret
        self.clock = clock
        self.ttl = ttl

    def issue(self, user_id: str) -> str:
        now = int(self.clock.now())
        claims = {"sub": user_id, "iat": now, "exp": now + int(self.ttl)}
        return encode_jwt(claims, "HS256", self.secret)

    def verify(self, token: str) -> dict:
        h_seg, p_seg, s_seg = token.split(".")
        header = json.loads(b64url_decode(h_seg))
        if header.get("alg") != "HS256":
            raise ValueError("algorithm not allowed")
        if not hmac.compare_digest(hs256_sign(f"{h_seg}.{p_seg}".encode(), self.secret),
                                   b64url_decode(s_seg)):
            raise ValueError("signature verification failed")
        claims = json.loads(b64url_decode(p_seg))
        if self.clock.now() >= claims.get("exp", 0):
            raise ValueError("expired")
        return claims


class HybridRotatingGateway:
    def __init__(self, secret: bytes, clock, access_ttl: float = 300.0,
                 refresh_ttl: float = 604800.0) -> None:
        self.secret = secret
        self.clock = clock
        self.access_ttl = access_ttl
        self.refresh_ttl = refresh_ttl
        self._refresh: dict[str, dict] = {}       # current token per record
        self._rotated_map: dict[str, str] = {}    # dead token -> family (replay memory)

    def _mint_refresh(self, user_id: str, family: Optional[str] = None) -> str:
        token = secrets.token_urlsafe(32)
        self._refresh[token] = {
            "family": family or secrets.token_urlsafe(16),
            "user": user_id,
            "expires": self.clock.now() + self.refresh_ttl,
        }
        return token

    def issue_pair(self, user_id: str) -> tuple[str, str]:
        access = self.issue_access(user_id)
        return access, self._mint_refresh(user_id)

    def issue_access(self, user_id: str) -> str:
        now = int(self.clock.now())
        claims = {"sub": user_id, "iat": now, "exp": now + int(self.access_ttl)}
        return encode_jwt(claims, "HS256", self.secret)

    def refresh(self, refresh_token: str) -> tuple[str, str]:
        rec = self._refresh.get(refresh_token)
        if rec is None:
            family = self._rotated_map.get(refresh_token)
            if family is not None:
                # REPLAY of an already-rotated token: theft signal — kill family
                for tok in [t for t, r in self._refresh.items()
                            if r["family"] == family]:
                    del self._refresh[tok]
                raise PermissionError("refresh reuse detected — family revoked")
            raise PermissionError("refresh token unknown or expired")
        if self.clock.now() >= rec["expires"]:
            family = rec["family"]
            del self._refresh[refresh_token]
            for tok in [t for t, r in self._refresh.items()
                        if r["family"] == family]:
                del self._refresh[tok]
            raise PermissionError("refresh token expired")
        family, user = rec["family"], rec["user"]
        del self._refresh[refresh_token]
        self._rotated_map[refresh_token] = family
        new_refresh = self._mint_refresh(user, family=family)
        return self.issue_access(user), new_refresh

    def verify_access(self, token: str) -> dict:
        h_seg, p_seg, s_seg = token.split(".")
        header = json.loads(b64url_decode(h_seg))
        if header.get("alg") != "HS256":
            raise ValueError("algorithm not allowed")
        if not hmac.compare_digest(hs256_sign(f"{h_seg}.{p_seg}".encode(), self.secret),
                                   b64url_decode(s_seg)):
            raise ValueError("signature verification failed")
        claims = json.loads(b64url_decode(p_seg))
        if self.clock.now() >= claims.get("exp", 0):
            raise ValueError("expired")
        return claims
