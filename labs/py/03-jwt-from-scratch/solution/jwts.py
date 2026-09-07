"""Lab 03 — reference solution."""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from typing import Optional

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa


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
    if not isinstance(segment, str):
        raise ValueError("segment must be a string")
    pad = (-len(segment)) % 4
    return base64.urlsafe_b64decode(segment + "=" * pad)


def hs256_sign(message: bytes, secret: bytes) -> bytes:
    return hmac.new(secret, message, hashlib.sha256).digest()


def rs256_generate_keypair() -> tuple[bytes, bytes]:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    priv = key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    )
    pub = key.public_key().public_bytes(
        serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    return priv, pub


def rs256_sign(message: bytes, private_pem: bytes) -> bytes:
    key = serialization.load_pem_private_key(private_pem, password=None)
    return key.sign(message, padding.PKCS1v15(), hashes.SHA256())


def rs256_verify(message: bytes, signature: bytes, public_pem: bytes) -> bool:
    try:
        key = serialization.load_pem_public_key(public_pem)
        key.verify(signature, message, padding.PKCS1v15(), hashes.SHA256())
        return True
    except Exception:
        return False


class KeyRegistry:
    def __init__(self) -> None:
        self._keys: dict[str, tuple[str, bytes]] = {}

    def add(self, kid: str, alg: str, key: bytes) -> None:
        self._keys[kid] = (alg, key)

    def get(self, kid: str) -> tuple[str, bytes]:
        return self._keys[kid]


class JWT:
    def __init__(self, clock, registry: KeyRegistry, leeway: float = 0.0) -> None:
        self.clock = clock
        self.registry = registry
        self.leeway = leeway

    def encode(self, claims: dict, alg: str, key: bytes,
               kid: Optional[str] = None, typ: str = "JWT") -> str:
        header = {"alg": alg, "typ": typ}
        if kid is not None:
            header["kid"] = kid
        h = b64url_encode(json.dumps(header, separators=(",", ":")).encode())
        p = b64url_encode(json.dumps(claims, separators=(",", ":")).encode())
        signing_input = f"{h}.{p}".encode()
        if alg == "HS256":
            sig = hs256_sign(signing_input, key)
        elif alg == "RS256":
            sig = rs256_sign(signing_input, key)
        else:
            raise ValueError(f"unsupported alg: {alg}")
        return f"{h}.{p}.{b64url_encode(sig)}"

    def decode(self, token: str, expected_alg: Optional[str] = None) -> dict:
        try:
            h_seg, p_seg, s_seg = token.split(".")
        except ValueError:
            raise ValueError("malformed token: need three dot-separated segments")

        header = json.loads(b64url_decode(h_seg))
        alg = header.get("alg")
        if not alg:
            raise ValueError("missing alg")
        if expected_alg is not None and alg != expected_alg:
            raise ValueError(f"alg mismatch: expected {expected_alg}, got {alg}")

        kid = header.get("kid")
        if kid is not None:
            try:
                key_alg, key = self.registry.get(kid)
            except KeyError:
                raise ValueError(f"unknown kid: {kid}")
            if key_alg != alg:
                raise ValueError(f"key for kid={kid} is not an {alg} key")
        else:
            raise ValueError("missing kid — cannot locate verification key")

        signing_input = f"{h_seg}.{p_seg}".encode()
        signature = b64url_decode(s_seg)
        if alg == "HS256":
            ok = hmac.compare_digest(hs256_sign(signing_input, key), signature)
        elif alg == "RS256":
            ok = rs256_verify(signing_input, signature, key)
        else:
            raise ValueError(f"unsupported alg: {alg}")
        if not ok:
            raise ValueError("signature verification failed")

        claims = json.loads(b64url_decode(p_seg))
        now = self.clock.now()
        if "nbf" in claims and now + self.leeway < claims["nbf"]:
            raise ValueError("token not yet valid (nbf)")
        if "exp" in claims and now - self.leeway >= claims["exp"]:
            raise ValueError("token expired (exp)")
        return claims
