# Lab 11: Applied Crypto — Hashing, Encryption, Rotation

**Track:** T30 Auth & Application Security · **Time:** 2.5h · **XP:** 50
**Module:** `T30-crypto-practice`

**You will build:** the four crypto operations every app backend needs — slow salted password hashing with constant-time verification, AES-GCM authenticated encryption, fail-closed key rotation, and content digests — in one `applied.py`.

**You will be able to answer:** *"How do you store passwords, encrypt data at rest, and rotate the encryption key without downtime — and why does reusing an AES-GCM nonce break everything?"*

## Setup

```bash
cd labs/py/11-crypto-primitives
python -m venv .venv && . .venv/bin/activate     # or: uv venv && . .venv/bin/activate
pip install pytest cryptography                 # cryptography>=42 is fine
```

## The spec

1. **`hash_password(password, salt=None) -> dict`** — scrypt with fixed params `n=2**14, r=8, p=1`. Generates a fresh random salt when none is given; returns `{"algo": "scrypt", "salt_hex": ..., "hash_hex": ...}`. The salt and hash are hex strings. Two hashings of the same password must differ (fresh salt).
2. **`verify_password(password, stored) -> bool`** — re-derives the hash from `stored["salt_hex"]` and compares with `hmac.compare_digest` (constant-time — `==` on secrets leaks timing). A wrong password, a missing key in `stored` (`KeyError`-proof), or params that no longer match the record **returns `False`, never raises**.
3. **`encrypt(key, plaintext, aad=None) -> (nonce, ct)`** — AES-GCM via `cryptography.hazmat.primitives.ciphers.aead.AESGCM`. The nonce is `secrets.token_bytes(12)`, **fresh on every call — never reused**. `aad` (additional authenticated data) is authenticated but not encrypted. Returns `(nonce, ciphertext)`.
4. **`decrypt(key, nonce, ct, aad=None) -> bytes`** — the inverse. Any authentication failure (`cryptography.exceptions.InvalidTag`) — tampered ciphertext, wrong key, wrong AAD — re-raises as **`DecryptionError`**, your own exception type.
5. **`rotate(old_key, ciphertexts) -> (new_key, new_ciphertexts)`** — generate a fresh 32-byte key, decrypt-and-re-encrypt every `(nonce, ct)` in the list under it, each with a fresh nonce. **Fail-closed:** if *any* item fails to decrypt, abort the whole rotation and re-raise the `DecryptionError` — never return a half-rotated list.
6. **`encrypt_file(key, plaintext_bytes) / decrypt_file(key, nonce, ct)`** — bytes-in/bytes-out convenience wrappers over `encrypt`/`decrypt` (in production the persistence layer lives here; tests use `tmp_path`).
7. **`digest(data: bytes) -> str`** — `hashlib.sha256` hex digest of the contents. Equal contents → equal digest; any change → different digest. This is the integrity check, and it is *fast* hashing — which is exactly why it is **not** a password hash.

## Run the tests

```bash
pytest tests/ -q                 # against starter/ → FAILS. Make them pass.
pytest tests/ -q --solution      # the reference — must be green
```

No sleeps, no network. Scrypt params stay low (`n=2**14`) so the suite runs in seconds.

## Stretch goals

1. **Pepper** — hash with a server-side secret mixed in, stored outside the database, and explain what a pepper adds over a salt and why it is compared with `compare_digest` too. *(Interview: "Salt vs pepper?")*
2. **AAD on rows** — encrypt a user's PII with the `user_id` as AAD so a ciphertext copied from user A to user B fails to decrypt even though the key is shared. *(Interview: "What is AAD actually for?")*
3. **Rotation tombstones** — wrap `rotate` in a transaction with a `pending_dek` write-ahead log and explain what happens if the process dies between the DEK re-encrypt and the tombstone write. *(Interview: "How does envelope encryption make rotation cheap?")*
4. **Nonce misuse-resistance** — swap AES-GCM for AES-GCM-SIV (`AESGCMSIV` in the same library) and explain what SIV mode costs you and when the trade is worth it. *(Interview: "What if I cannot guarantee nonce uniqueness?")*
