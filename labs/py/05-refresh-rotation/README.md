# Lab 05: Refresh Token Rotation with Reuse Detection

**Track:** T30 Auth & Application Security · **Time:** 2h · **XP:** 50
**Module:** `T30-token-lifecycle`

**You will build:** an `AuthServer` issuing 15-minute signed access tokens plus 7-day opaque refresh tokens (stored **hashed**), rotating the refresh on every use within a "family", detecting replay of a rotated token as a theft signal and revoking the family, and an RFC 7662-style introspection cache that must invalidate on revocation — all on an injectable clock.

**You will be able to answer:** *"Your access token is stateless — so how do you actually log someone out, and how do you know a refresh token was stolen?"*

## Setup

```bash
cd labs/py/05-refresh-rotation
python -m venv .venv && . .venv/bin/activate     # or: uv venv && . .venv/bin/activate
pip install pytest
```

## The spec

1. **`RefreshStore`** — keyed by `hash_token(raw)` (SHA-256). `mark_rotated()` keeps the ghost record — reuse detection needs it. `revoke_family(family)` deletes every record in the family.
2. **`sign_access` / `verify_access`** — minimal HS256 JWT (`sub, iat, exp`) with `hmac`/`hashlib` — no PyJWT; you proved the codec in Lab 03.
3. **`AuthServer.issue_pair`** — (access, raw refresh); refresh stored hashed with a fresh family id.
4. **`AuthServer.refresh`** — rotate: presented token must be live. Already-rotated → `ReuseDetected` + family revoked + event logged. Expired → family revoked + `PermissionError`. Live → mark rotated, mint a new pair **in the same family**.
5. **`AuthServer.revoke_all_for_user`** — the admin kill-switch.
6. **`IntrospectionCache`** — `introspect(token) -> bool` with a TTL (serve cached, else ask server), `invalidate(token)` on revocation, and hit/miss counters. A cached "valid" must never outlive a revocation.

## Run the tests

```bash
pytest tests/ -v          # against starter/ → FAILS. Make them pass.
```

To check the reference: `pytest tests/ -v --solution`

## Stretch goals

1. **Grace window** — accept a just-rotated token for 30s (clock-skew races) WITHOUT skipping reuse detection; log the grace use as suspicious but don't revoke. This is what real IdPs ship.
2. **DPoP binding** — bind refresh tokens to a client keypair so a stolen token is useless without the key.
3. **Concurrent refresh** — two tabs refresh simultaneously; assert exactly one rotation wins and the loser's reuse is handled by the grace window, not a logout.
