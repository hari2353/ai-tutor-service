# Lab 03: JWT From Scratch

**Track:** T30 Auth & Application Security · **Time:** 2h · **XP:** 50
**Module:** `T30-jwt-deep`

**You will build:** the compact JWS serialization `header.payload.signature` by hand — base64url with padding rules, HS256 via `hmac`/`hashlib`, RS256 via `cryptography` RSA keypair, a JWKS-like `kid` key registry, and `exp`/`nbf`/`iat` validation against an injectable clock with leeway. PyJWT is used by exactly one optional test, as a cross-check.

**You will be able to answer:** *"What actually is a JWT — draw it — and how do HS256 and RS256 differ in who holds what key?"*

## Setup

```bash
cd labs/py/03-jwt-from-scratch
python -m venv .venv && . .venv/bin/activate     # or: uv venv && . .venv/bin/activate
pip install pytest pyjwt cryptography            # cryptography only for RS256
```

## The spec

1. **`b64url_encode` / `b64url_decode`** — RFC 7515 base64url: URL-safe alphabet, `=` padding stripped on encode, restored (to a multiple of 4) on decode; garbage input raises.
2. **`hs256_sign`** — HMAC-SHA256: one symmetric secret both signs and verifies. Deterministic.
3. **`rs256_generate_keypair` / `rs256_sign` / `rs256_verify`** — 2048-bit RSA, PKCS#1 v1.5, SHA-256: private signs, public verifies.
4. **`KeyRegistry`** — `kid -> (alg, key)`, the miniature JWKS. Unknown `kid` → reject.
5. **`JWT.encode`** — header `{alg, typ, kid}` + payload JSON, both base64url, signature over `header.payload`.
6. **`JWT.decode`** — verify signature with the alg the header claims (refuse alg/key-family mismatches), then check `nbf`/`exp` against the injected clock with `leeway`. Everything that can go wrong raises `ValueError`.

## Run the tests

```bash
pytest tests/ -v          # against starter/ → FAILS. Make them pass.
```

To check the reference: `pytest tests/ -v --solution`

## Stretch goals

1. **JWKS endpoint shape** — emit `{"keys":[{"kty":"RSA","kid":...,"n":...,"e":"AQAB"}]}` with modulus/exponent base64url-encoded, exactly like a real `/.well-known/jwks.json`.
2. **Key rotation** — two kids, one "current" one "previous"; tokens signed by the previous kid keep validating until a cutoff; then only the new one does.
3. **ES256** — ECDSA P-256 via `cryptography`; note the low-S / malleability problem JWTs sidestep via RFC 6979-style deterministic signatures.
4. **`aud` + `iss` validation** — add them to `decode` with the same fail-closed discipline.
