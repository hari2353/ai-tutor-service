# Lab 10: The API Security Lab — BOLA, Mass Assignment, Rate Limits, Enumeration

**Track:** T30 Auth & Application Security · **Time:** 2h · **XP:** 50
**Module:** `T30-api-security`

**You will build:** four API security controls as vulnerable-then-fixed pairs — BOLA/IDOR (a `GET /orders/{id}` that authenticates but never checks ownership until you make it), mass assignment (a PATCH that binds the whole body — including `is_admin` — until an allowlist stops it), a per-key token-bucket rate limiter with burst + refill on the injectable clock, and a login endpoint that leaks a user-exists oracle until the message goes uniform with a timing placeholder.

**You will be able to answer:** *"Which OWASP API Top 10 items would I actually write myself, and what does the fix look like in code?"*

## Setup

```bash
cd labs/py/10-api-security-lab
python -m venv .venv && . .venv/bin/activate     # or: uv venv && . .venv/bin/activate
pip install pytest
```

## The spec

1. **BOLA** — `get_order_vulnerable`: authenticate the session, look up the order, return it — never compare `order.user_id` to the caller. `get_order_fixed`: object-level authorization; `PermissionError` for anyone else's order. (OWASP API1:2023)
2. **Mass assignment** — `update_user_vulnerable`: `user.update(body)` — `is_admin` rides along. `update_user_fixed`: allowlist `{display_name, email}`, self-update only. (OWASP API3:2023)
3. **`TokenBucketLimiter`** — per-key bucket: `capacity` burst, `refill_rate` tokens/sec via the injected clock; rejection spends nothing; keys independent. Test shape: 5 allowed in a minute, 6th denied, recovered after `advance(60)`.
4. **Enumeration** — `login_vulnerable`: "user not found" vs "wrong password" (a free oracle). `login_fixed`: one uniform "invalid credentials" + a dummy hash on the missing-user path so timing doesn't leak either. (OWASP API2:2023-adjacent, CWE-204)

## Run the tests

```bash
pytest tests/ -v          # against starter/ → FAILS. Make them pass.
```

To check the reference: `pytest tests/ -v --solution`

## Stretch goals

1. **BFLA** — broken function-level authorization: `/admin/deleteUser` that checks the session but not the role; fix with a policy check.
2. **Unrestricted resource consumption** — add a per-user concurrent-connection cap and a payload-size cap (OWASP API4:2023); test that the limiter composes with the bucket.
3. **CI authorization tests** — the automated BOLA pattern: for every object in the store, assert user B gets 403/404 on A's object. Generalize the two fixed methods into a table-driven test.
