# Lab 02: Sessions vs Tokens — the Honest Tradeoff

**Track:** T30 Auth & Application Security · **Time:** 2h · **XP:** 50
**Module:** `T30-sessions-vs-tokens`

**You will build:** a server-side `SessionStore` (create/validate/revoke, opaque ids, clock-driven expiry, sliding renewal) next to a stateless `StatelessToken` (JWT HS256 via PyJWT), plus the production hybrid — short-lived access JWT + server-side refresh session with rotation — and prove in tests that sessions revoke instantly while JWTs cannot be revoked at all.

**You will be able to answer:** *"JWTs or sessions — which do you pick and what does it cost you?"* — and survive the follow-up: *"Then how do you log out a JWT?"*

## Setup

```bash
cd labs/py/02-session-vs-jwt
python -m venv .venv && . .venv/bin/activate     # or: uv venv && . .venv/bin/activate
pip install pytest pyjwt                         # only dependencies
```

## The spec

1. **`Clock`** — injectable time source (`SystemClock`, `FakeClock(t=0).advance(dt)`). All expiry logic goes through it; no `time.sleep()`, no `time.time()`.
2. **`SessionStore`** — `create(user_id, data) -> opaque id` (`secrets.token_urlsafe`), `validate(sid)` returning the record or `None` (expired sessions never resurrect), `revoke(sid)` with instant effect on the next validate. `ttl` via clock; `sliding=True` renews `expires_at` on activity, `sliding=False` is a hard absolute window.
3. **`StatelessToken`** — JWT HS256 with claims `sub, iat, nbf, exp`; issue and validate against the clock. `revoke()` exists only to prove the point: it cannot work, and the test asserts exactly that.
4. **`HybridAuth`** — `login` issues (access JWT, refresh session id); `refresh` rotates: old refresh revoked, new pair issued; `logout` revokes the refresh lever. Access stays stateless and fast; revocation lives on the refresh side.

## Run the tests

```bash
pytest tests/ -v          # against starter/ → FAILS. Make them pass.
```

To check the reference: `pytest tests/ -v --solution`

## Stretch goals

1. **Revocation-list JWT** — add a `denylist` set of `jti` claims checked on every validate; measure what you just lost (a store lookup per request — the thing statelessness was supposed to avoid).
2. **Reuse detection** — if a rotated refresh token is presented a second time, kill the whole family (see Lab 05, which builds exactly this).
3. **Session fixation** — add a `rotate_id(old_sid)` that keeps the record but mints a fresh id on privilege change; write the test that fails without it.
