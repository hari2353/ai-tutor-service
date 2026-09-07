# Lab 01: AuthN vs AuthZ as Middleware

**Track:** T30 Auth & Application Security · **Time:** 2h · **XP:** 50
**Module:** `T30-authn-vs-authz`

**You will build:** an authentication stage, an authorization stage and an accounting hook as separate middleware in one composable stack — with tests that prove the wrong stage order fails with 401, not 403.

**You will be able to answer:** *"Authentication vs authorization — where does each live in a request pipeline, and what breaks when you conflate them?"*

## Setup

```bash
cd labs/py/01-authn-authz-middleware
python -m venv .venv && . .venv/bin/activate     # or: uv venv && . .venv/bin/activate
pip install pytest                                # only dependency
```

## The spec

1. **`authenticate(req, token_store)`** — the AuthN stage. Extract the Bearer token from `req["headers"]["Authorization"]` (`"Bearer <opaque-token>"`). Missing header, wrong scheme, or a token not in `token_store` → raise `AuthenticationError` (401 semantics — same error for all three; distinguishing them leaks who exists). Valid → attach `req["user"] = token_store[token]`. Tokens are opaque strings in a dict; no JWT, no crypto.
2. **`authorize(req, acl, resource, action)`** — the AuthZ stage. `req` must already carry `"user"` (authz assumes authn ran — it never re-verifies credentials); if it doesn't, raise `AuthenticationError`, not `AuthorizationError` — you cannot deny a request whose identity you never established. `acl = {(resource, action): {allowed users or "*"}}`; deny → `AuthorizationError` (403). **Admin bypass:** user `"admin"` passes every check before the ACL is consulted.
3. **`audit(req, decision, resource, action, log)`** — the third A, accounting. Appends `(user, resource, action, allow: bool)` to a caller-owned log object — allows AND denies, or you have no forensic trail for the one decision that was wrong.
4. **Middleware** — `log_mw(log)` appends to a log list then calls next; `authn_mw(token_store)` wraps `authenticate`; `authz_mw(acl, resource, action, audit_log)` wraps `authorize` + `audit` and must run after `authn_mw`.
5. **`compose(fns, handler)`** — a handler wrapper running stages in order (`fns[0]` outermost). A middleware that raises stops the chain: no later stage, no handler. The response dict gains a `"headers"` dict.
6. **Order matters** — `log → authn → authz` is the only correct order. A test proves `authz` before `authn` raises `AuthenticationError`, not `AuthorizationError`.

## Run the tests

```bash
pytest tests/ -v          # against starter/ → FAILS. Make them pass.
```

To check the reference: `pytest tests/ -v --solution`

## Stretch goals

1. **Deny-by-default** — make a missing ACL entry a deny with a distinct audit reason code. *(Interview: "what does an empty ACL mean in your system?")*
2. **Attribute checks** — add time-of-day or IP-range conditions to `authorize` and watch pure RBAC fail. *(Interview: "when does RBAC break down?")*
3. **Two resources** — authz twice in the chain for `doc/{id}` and `folder/{id}`, the second depending on the first's result. *(Interview: "how does an IDOR/BOLA slip past a working authn layer?")*
4. **Denials are cheap** — ensure a denied request costs zero handler work; assert with a counter. *(Interview: "what does a 403 path cost you?")*
