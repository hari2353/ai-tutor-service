"""Lab 03 — JWT from scratch (no PyJWT for the core — hmac/hashlib/base64 only).

Rules:
  * PyJWT is used by ONE optional cross-check test, never by your implementation.
  * exp/nbf/iat validation goes through the injected clock, with leeway.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from typing import Optional

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa


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


# --------------------------------------------------------------------------- base64url
def b64url_encode(data: bytes) -> str:
    """base64url WITHOUT padding ('=' stripped) — the JWT wire format."""
    # TODO(step 3)
    raise NotImplementedError


def b64url_decode(segment: str) -> bytes:
    """Restore stripped padding (to a multiple of 4), then base64url-decode.
    Raise ValueError on non-base64 input."""
    # TODO(step 4)
    raise NotImplementedError


# --------------------------------------------------------------------------- algorithms
def hs256_sign(message: bytes, secret: bytes) -> bytes:
    """HMAC-SHA256 — symmetric. One secret both signs and verifies."""
    # TODO(step 5)
    raise NotImplementedError


def rs256_generate_keypair() -> tuple[bytes, bytes]:
    """Return (private_pem, public_pem). 2048-bit RSA via the cryptography lib."""
    # TODO(step 6)
    raise NotImplementedError


def rs256_sign(message: bytes, private_pem: bytes) -> bytes:
    """RSASSA-PKCS1-v1_5 with SHA-256 — asymmetric. Private signs, public verifies."""
    # TODO(step 7)
    raise NotImplementedError


def rs256_verify(message: bytes, signature: bytes, public_pem: bytes) -> bool:
    # TODO(step 8)
    raise NotImplementedError


# --------------------------------------------------------------------------- key registry
class KeyRegistry:
    """A JWKS in miniature: kid -> key material, per algorithm family."""

    def __init__(self) -> None:
        self._keys: dict[str, tuple[str, bytes]] = {}   # kid -> (alg, key)

    def add(self, kid: str, alg: str, key: bytes) -> None:
        # TODO(step 9)
        raise NotImplementedError

    def get(self, kid: str) -> tuple[str, bytes]:
        """Return (alg, key) for kid. Raise KeyError on unknown kid."""
        # TODO(step 10)
        raise NotImplementedError


# --------------------------------------------------------------------------- JWT
class JWT:
    """header.payload.signature — the compact JWS serialization, by hand."""

    def __init__(self, clock, registry: KeyRegistry, leeway: float = 0.0) -> None:
        self.clock = clock
        self.registry = registry
        self.leeway = leeway

    def encode(self, claims: dict, alg: str, key: bytes,
               kid: Optional[str] = None, typ: str = "JWT") -> str:
        """Build header (alg, typ, kid if given), payload, sign, join with '.'.
        HS256 -> HMAC secret; RS256 -> RSA private PEM."""
        # TODO(step 11)
        raise NotImplementedError

    def decode(self, token: str, expected_alg: Optional[str] = None) -> dict:
        """Split, decode header, pick the key by kid (fall back to caller's expected
        alg if the registry misses), verify the signature with the header's alg,
        then check exp/nbf against the clock + leeway. Raise ValueError on any
        failure: bad format, unknown kid, wrong alg, bad signature, expired, immature."""
        # TODO(step 12)
        raise NotImplementedError
