"""Lab 11 — applied crypto for apps. Fill in every TODO. Tests define done.

Rules:
  * Only stdlib (hashlib, secrets, hmac) + the `cryptography` library.
  * Never compare secrets with == — hmac.compare_digest.
  * A fresh nonce on every encryption. Never reuse one.
  * Verification failures return False / raise your own DecryptionError —
    raw library exceptions never escape this module.
"""
from __future__ import annotations

import hashlib
import hmac
import secrets

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt


# --------------------------------------------------------------------------- errors
class DecryptionError(Exception):
    """Any authentication failure: tampered ct, wrong key, wrong AAD."""


# ----------------------------------------------------------------- password hashing
SCRYPT_N = 2 ** 14          # deliberately low for test speed; see PRODUCTION.md
SCRYPT_R = 8
SCRYPT_P = 1
KEY_LEN = 32


def hash_password(password: str, salt: bytes | None = None) -> dict:
    """scrypt with a fresh random salt. Returns the full verifiable record:

        {"algo": "scrypt", "salt_hex": ..., "hash_hex": ..., "n": ..., "r": ..., "p": ...}

    The params live in the record so verify can check them — a hash made
    with different params is not the same hash, so verification returns
    False rather than raising.
    """
    # TODO(step 1): salt = secrets.token_bytes(16) if salt is None
    # TODO(step 1): derive with Scrypt(n=SCRYPT_N, r=SCRYPT_R, p=SCRYPT_P)
    # TODO(step 1): return the dict record
    raise NotImplementedError


def verify_password(password: str, stored: dict) -> bool:
    """Constant-time verification against a stored record.

    Missing keys, an algo we do not recognise, or params that do not match
    the record -> False, never an exception. A malformed stored record is
    a normal event (old rows, migrations), not a crash.
    """
    # TODO(step 2): pull salt/hash/params from stored, re-derive, and
    #                return hmac.compare_digest(expected, actual)
    raise NotImplementedError


# ------------------------------------------------------------------------ AES-GCM
def encrypt(key: bytes, plaintext: bytes, aad: bytes | None = None) -> tuple[bytes, bytes]:
    """AES-GCM. Fresh 12-byte nonce on EVERY call. Returns (nonce, ct)."""
    # TODO(step 3): nonce = secrets.token_bytes(12); AESGCM(key).encrypt(...)
    raise NotImplementedError


def decrypt(key: bytes, nonce: bytes, ct: bytes, aad: bytes | None = None) -> bytes:
    """Inverse of encrypt. InvalidTag (tamper, wrong key, wrong AAD)
    -> raise DecryptionError."""
    # TODO(step 4): try AESGCM(key).decrypt(...) except InvalidTag -> DecryptionError
    raise NotImplementedError


# ------------------------------------------------------------------- key rotation
def new_key() -> bytes:
    """A fresh 32-byte AES-256 key."""
    # TODO(step 5): secrets.token_bytes(32)
    raise NotImplementedError


def rotate(old_key: bytes, ciphertexts: list[tuple[bytes, bytes]]) -> tuple[bytes, list[tuple[bytes, bytes]]]:
    """Decrypt-and-re-encrypt every (nonce, ct) under a brand-new key.

    Fail-closed: if ANY item fails to decrypt, abort the whole rotation and
    re-raise DecryptionError. Never return a half-rotated list — the caller
    must never believe rotation succeeded when it did not.
    """
    # TODO(step 5): new = new_key(); decrypt ALL items first, then re-encrypt
    #                all under the new key with fresh nonces
    raise NotImplementedError


# ------------------------------------------------------------------- file helpers
def encrypt_file(key: bytes, plaintext: bytes, aad: bytes | None = None) -> tuple[bytes, bytes]:
    """Bytes-in/bytes-out convenience over encrypt() — the persistence layer
    of a real app lives here (tests use tmp_path)."""
    # TODO(step 6)
    raise NotImplementedError


def decrypt_file(key: bytes, nonce: bytes, ct: bytes, aad: bytes | None = None) -> bytes:
    # TODO(step 6)
    raise NotImplementedError


# ------------------------------------------------------------------------- digest
def digest(data: bytes) -> str:
    """Fast SHA-256 hex digest for INTEGRITY, not for passwords."""
    # TODO(step 7)
    raise NotImplementedError
