"""Lab 04 — the JWT attack lab: break it, then fix it.

Five attacks, each with a make_insecure()/make_secure() verifier pair:
  (a) alg=none            (d) replay window
  (b) key confusion       (e) revocation gap
  (c) weak HMAC secret

Rules:
  * No PyJWT for the vulnerable/secure verifiers — you built the codec in Lab 03;
    here you build the same primitives again, compactly, by hand (hmac/hashlib).
  * All time via the injected clock.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from typing import Optional


# --------------------------------------------------------------------------- clock
class SystemClock:
    def now(self) -> float:
        return time.time()


class FakeClock:
    def __init__(self, t: float = 0.0) -> None:
        self.t = t

    def now(self) -> float:
        # TODO(step 1)
        raise NotImplementedError

    def advance(self, dt: float) -> None:
        # TODO(step 2)
        raise NotImplementedError


# --------------------------------------------------------------------------- codec
def b64url_encode(data: bytes) -> str:
    # TODO(step 3): base64url, '=' stripped
    raise NotImplementedError


def b64url_decode(segment: str) -> bytes:
    # TODO(step 4): restore padding, decode
    raise NotImplementedError


def hs256_sign(message: bytes, secret: bytes) -> bytes:
    # TODO(step 5)
    raise NotImplementedError


def encode_jwt(claims: dict, alg: str, key: Optional[bytes],
               header_extra: Optional[dict] = None) -> str:
    """Compact JWS. alg='none' signs with an EMPTY signature segment (this is
    what makes the attack possible — you need it to build the malicious token)."""
    # TODO(step 6)
    raise NotImplementedError


# ---- factory functions: build the insecure/secure verifier pair ---------------
def make_verifier_insecure_none(secret: bytes, clock) -> "InsecureAlgNoneVerifier":
    return InsecureAlgNoneVerifier(secret, clock)


def make_verifier_secure_none(secret: bytes, clock) -> "SecurePinnedVerifier":
    return SecurePinnedVerifier(secret, clock)


def make_verifier_insecure_confusion(rsa_public_pem: bytes, clock) -> "InsecureConfusionVerifier":
    return InsecureConfusionVerifier(rsa_public_pem, clock)


def make_verifier_secure_confusion(rsa_public_pem: bytes, clock) -> "SecureConfusionVerifier":
    return SecureConfusionVerifier(rsa_public_pem, clock)


# --------------------------------------------------------------------------- (a) alg=none
def make_verifier_insecure_none(secret: bytes, clock) -> "InsecureAlgNoneVerifier":
    return InsecureAlgNoneVerifier(secret, clock)


def make_verifier_secure_none(secret: bytes, clock) -> "SecurePinnedVerifier":
    return SecurePinnedVerifier(secret, clock)


class InsecureAlgNoneVerifier:
    """Accepts whatever alg the token's own header claims — including 'none'.
    The bug: the ATTACKER picks the algorithm; you must never let them."""

    def __init__(self, secret: bytes, clock) -> None:
        self.secret = secret
        self.clock = clock

    def verify(self, token: str) -> dict:
        # TODO(step 7): branch on header alg; 'none'/'None'/'' -> accept with
        # NO signature check. Yes, really — that's the vulnerability.
        raise NotImplementedError


class SecurePinnedVerifier:
    """Pins algorithms=["HS256"] regardless of what the header claims."""

    def __init__(self, secret: bytes, clock) -> None:
        self.secret = secret
        self.clock = clock

    def verify(self, token: str) -> dict:
        # TODO(step 8): header alg MUST be HS256 (anything else -> reject);
        # verify signature; check exp/nbf via clock. Raise ValueError on failure.
        raise NotImplementedError


# --------------------------------------------------------------------------- (b) key confusion
def make_verifier_insecure_confusion(rsa_public_pem: bytes, clock):
    return InsecureConfusionVerifier(rsa_public_pem, clock)


def make_verifier_secure_confusion(rsa_public_pem: bytes, clock):
    return SecureConfusionVerifier(rsa_public_pem, clock)


class InsecureConfusionVerifier:
    """One key argument, many accepted algs: if the header says HS256, the
    RSA PUBLIC key PEM bytes get used as the HMAC secret. Attacker knows the
    public key (it's public!) and can therefore forge anything."""

    def __init__(self, rsa_public_pem: bytes, clock) -> None:
        self.public_pem = rsa_public_pem
        self.clock = clock

    def verify(self, token: str) -> dict:
        # TODO(step 9): accept HS256 OR RS256; for HS256 use self.public_pem
        # bytes as the HMAC secret (THE BUG); for RS256 verify properly.
        raise NotImplementedError


class SecureConfusionVerifier:
    """Key material is typed and separated per algorithm family: HMAC secrets
    and RSA public keys never substitute for each other."""

    def __init__(self, rsa_public_pem: bytes, clock) -> None:
        self.public_pem = rsa_public_pem
        self.clock = clock

    def verify(self, token: str) -> dict:
        # TODO(step 10): RS256-only. An HS256 header must be rejected BEFORE
        # any HMAC verification could run (there is no HMAC secret here at all).
        raise NotImplementedError


# --------------------------------------------------------------------------- (c) weak secret
WEAK_DICTIONARY = [
    b"secret", b"password", b"123456", b"jwt_secret", b"changeme",
    b"letmein", b"qwerty", b"admin", b"test", b"key",
    b"iloveyou", b"monkey", b"dragon", b"supersecret", b"mysecret",
]


def crack_hs256_secret(token: str, dictionary=WEAK_DICTIONARY) -> Optional[bytes]:
    """Offline brute force: the token is public, so anyone can try candidate
    secrets until the signature verifies. No rate limit can save you — this
    never touches your server."""
    # TODO(step 11)
    raise NotImplementedError


# --------------------------------------------------------------------------- (d) replay / (e) revocation gap
class StatelessGateway:
    """The plain stateless verifier: no replay memory, no revocation. Used to
    demonstrate (d) and (e) — then fixed by a hybrid with short TTL + rotation."""

    def __init__(self, secret: bytes, clock, ttl: float = 900.0) -> None:
        self.secret = secret
        self.clock = clock
        self.ttl = ttl

    def issue(self, user_id: str) -> str:
        # TODO(step 12): claims {sub, iat, exp=now+ttl}; HS256
        raise NotImplementedError

    def verify(self, token: str) -> dict:
        # TODO(step 13): signature + exp via clock. No memory. No denylist.
        raise NotImplementedError


class HybridRotatingGateway:
    """The mitigation: SHORT access TTL + server-side refresh with rotation.
    Replay of a rotated refresh token kills the family (breach signal)."""

    def __init__(self, secret: bytes, clock, access_ttl: float = 300.0,
                 refresh_ttl: float = 604800.0) -> None:
        self.secret = secret
        self.clock = clock
        self.access_ttl = access_ttl
        self.refresh_ttl = refresh_ttl
        self._refresh: dict[str, dict] = {}       # token -> {family, user, expires}

    def issue_pair(self, user_id: str) -> tuple[str, str]:
        """(access_jwt, refresh_token). refresh stored server-side, family id minted."""
        # TODO(step 14)
        raise NotImplementedError

    def refresh(self, refresh_token: str) -> tuple[str, str]:
        """Rotate. If the token was ALREADY rotated (its family's current token
        differs), treat as theft: revoke the whole family, raise PermissionError."""
        # TODO(step 15)
        raise NotImplementedError

    def verify_access(self, token: str) -> dict:
        # TODO(step 16): same as StatelessGateway.verify
        raise NotImplementedError
