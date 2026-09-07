# Lab 06: OAuth 2.0 Authorization Code + PKCE

**Track:** T30 Auth & Application Security · **Time:** 2h · **XP:** 50
**Module:** `T30-oauth-oidc`

**You will build:** the full authorization-code flow with every party as an in-process object — an `AuthorizationServer` (authorize + token endpoints: client validation, exact redirect_uri matching, scope checking, single-use 60s codes, S256 PKCE verification), a `ClientApp` that mints the verifier and exchanges it, and a `ProtectedResource` that accepts only tokens the AS issued. No network; the browser is you.

**You will be able to answer:** *"Walk me through the authorization-code flow with PKCE — and what does each step prevent?"*

## Setup

```bash
cd labs/py/06-oauth-pkce-flow
python -m venv .venv && . .venv/bin/activate     # or: uv venv && . .venv/bin/activate
pip install pytest
```

## The spec

1. **`pkce_s256_challenge(verifier)`** — `b64url(sha256(verifier))`, padding stripped (RFC 7636 §4.2). Anchor to the RFC's Appendix B test vector.
2. **`pkce_verifier_ok`** — 43–128 chars, unreserved charset `[A-Za-z0-9-._~]` only (§4.1).
3. **`AuthorizationServer.authorize`** — reject unknown `client_id`, non-registered `redirect_uri` (exact match), un-allowed scope, and `code_challenge_method="plain"` when the server requires S256. Mint a single-use code bound to (client, redirect_uri, challenge) with 60s TTL via the injected clock; return the `?code=...&state=...` redirect.
4. **`AuthorizationServer.token`** — `grant_type` must be `authorization_code`; code must exist, be unused and unexpired; client + redirect_uri must match the binding; `sha256(verifier)` must equal the stored challenge. Mark used. Issue the access token.
5. **`ClientApp.begin` / `complete`** — generate verifier + state; on callback, verify `state` (CSRF on the front channel) and exchange with the stored verifier.
6. **`ProtectedResource`** — accepts only tokens the AS actually issued; everything else is `invalid_token`.

## Run the tests

```bash
pytest tests/ -v          # against starter/ → FAILS. Make them pass.
```

To check the reference: `pytest tests/ -v --solution`

## Stretch goals

1. **ID token** — add an OIDC `id_token` (JWT with `iss, sub, aud, exp, nonce`) issued alongside the access token when `scope` includes `openid`; verify the `nonce` matches the one sent at authorize.
2. **Client credentials** — the machine-to-machine grant: no user, no code, one token-endpoint call with a client secret.
3. **Refresh grant** — after the code exchange, return a refresh token and implement the rotation rules from Lab 05.
4. **Device flow** — `device_code` + `user_code` + slow polling with `authorization_pending` — RFC 8628.
