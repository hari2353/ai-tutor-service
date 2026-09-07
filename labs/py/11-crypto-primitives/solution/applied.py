"""Lab 11 — reference solution."""
from __future__ import annotations

import hashlib
import hmac
import secrets

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt


class DecryptionError(Exception):
    """Any authentication failure: tampered ct, wrong key, wrong AAD."""


# ----------------------------------------------------------------- password hashing
SCRYPT_N = 2 ** 14          # deliberately low for test speed; see PRODUCTION.md
SCRYPT_R = 8
SCRYPT_P = 1
KEY_LEN = 32
SALT_LEN = 16
NONCE_LEN = 12


def hash_password(password: str, salt: bytes | None = None) -> dict:
    if salt is None:
        salt = secrets.token_bytes(SALT_LEN)
    kdf = Scrypt(salt=salt, length=KEY_LEN, n=SCRYPT_N, r=SCRYPT_R, p=SCRYPT_P)
    derived = kdf.derive(password.encode("utf-8"))
    return {
        "algo": "scrypt",
        "salt_hex": salt.hex(),
        "hash_hex": derived.hex(),
        "n": SCRYPT_N,
        "r": SCRYPT_R,
        "p": SCRYPT_P,
    }


def verify_password(password: str, stored: dict) -> bool:
    try:
        if stored.get("algo") != "scrypt":
            return False
        salt = bytes.fromhex(stored["salt_hex"])
        expected = bytes.fromhex(stored["hash_hex"])
        n, r, p = stored["n"], stored["r"], stored["p"]
    except (KeyError, TypeError, ValueError):
        # missing keys, non-dict, malformed hex — a bad record is a failed
        # verification, not a crash
        return False
    kdf = Scrypt(salt=salt, length=len(expected), n=n, r=r, p=p)
    try:
        derived = kdf.derive(password.encode("utf-8"))
    except (ValueError, TypeError):
        # params that do not match the record cannot re-derive the hash
        return False
    return hmac.compare_digest(derived, expected)


# ------------------------------------------------------------------------ AES-GCM
def encrypt(key: bytes, plaintext: bytes, aad: bytes | None = None) -> tuple[bytes, bytes]:
    nonce = secrets.token_bytes(NONCE_LEN)
    ct = AESGCM(key).encrypt(nonce, plaintext, aad)
    return nonce, ct


def decrypt(key: bytes, nonce: bytes, ct: bytes, aad: bytes | None = None) -> bytes:
    try:
        return AESGCM(key).decrypt(nonce, ct, aad)
    except InvalidTag as exc:
        raise DecryptionError(str(exc)) from exc


# ------------------------------------------------------------------- key rotation
def new_key() -> bytes:
    return secrets.token_bytes(KEY_LEN)


def rotate(old_key: bytes, ciphertexts: list[tuple[bytes, bytes]]) -> tuple[bytes, list[tuple[bytes, bytes]]]:
    # decrypt everything FIRST — one bad item aborts before anything is
    # re-encrypted, so the caller can never mistake a partial rotation
    # for a complete one
    plaintexts = []
    for nonce, ct in ciphertexts:
        try:
            plaintexts.append(decrypt(old_key, nonce, ct))
        except DecryptionError as exc:
            raise DecryptionError(f"rotation aborted: item failed to decrypt: {exc}") from exc

    new = new_key()
    rotated = [encrypt(new, pt) for pt in plaintexts]
    return new, rotated


# ------------------------------------------------------------------- file helpers
def encrypt_file(key: bytes, plaintext: bytes, aad: bytes | None = None) -> tuple[bytes, bytes]:
    return encrypt(key, plaintext, aad)


def decrypt_file(key: bytes, nonce: bytes, ct: bytes, aad: bytes | None = None) -> bytes:
    return decrypt(key, nonce, ct, aad)


# ------------------------------------------------------------------------- digest
def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()
