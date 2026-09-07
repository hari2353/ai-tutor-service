# Production notes — sessions vs tokens

## What you'd actually use

| Concern | Production answer |
|---|---|
| Session store | Redis with `SETEX` (expiry is the store's job, not yours), or a `sessions` table in Postgres for durability |
| Opaque id | 256-bit random, cookie flags: `HttpOnly; Secure; SameSite=Lax` |
| JWTs | `pyjwt`/`joserfc` (py), `spring-security-oauth2` (java), `golang-jwt/jwt/v5` (go), `jose` (node/ts) |
| Hybrid | The 2026 default: 5–15 min access JWT + server-tracked refresh with rotation + reuse detection |
| Revocation for JWTs | Short TTL as the *bounded worst case*, optionally a cached denylist (`jti` in Redis) for instant kill |

## What the real systems add over yours

- **Shared session store across pods** — your dict is one process. Real stores are external (Redis cluster), so revocation is global and instant.
- **Sliding windows done by the store** — Redis TTL refreshes on `GET` via `EXPIRE`; you re-implemented it in Python, which is fine for one node and wrong for 200.
- **Refresh rotation + reuse detection** — OAuth 2.1 draft and RFC 6749 §10.4/10.5: rotate on every use; if a rotated token is replayed, revoke the whole family — it's a theft signal, not just an error.
- **DPoP / sender-constrained tokens** — binding tokens to a client-held key so a stolen token can't even be replayed by the thief.
- **Session versioning** — a `pwd_version` claim checked against the user row: password change invalidates all outstanding tokens without a denylist.

## What breaks at scale

| Symptom | Cause | Fix |
|---|---|---|
| "Logout doesn't work" bug reports | stateless access JWT outlives the logout click | hybrid: revoke refresh + accept ≤TTL access window; denylist only for admin kill-switch |
| Redis blip logs everyone out | sessions live only in cache | write-through to a durable store, or accept it deliberately |
| Stale sessions forever | sliding window with no absolute cap | max-lifetime cap (e.g. 30d) regardless of activity — you built both modes |
| JWTs working after "revoke" | you revoked only the refresh token | that's the design, not a bug — shorten access TTL until the exposure window is acceptable |
| Session table grows unbounded | no TTL sweep | store-native expiry, or a periodic `DELETE WHERE expires_at < now()` |

## Cost & latency

Session validate = 1 network round-trip (~0.5–1ms in-DC, the reason stateless fans love JWTs). JWT validate = pure CPU (~50µs, but ~1KB more per request header, and you pay it on *every* hop). The hybrid's insight: pay the network cost only on refresh (once per 15 min per user), not per request.

## The 3 questions an interviewer asks after you describe this

1. *"How do you log out a JWT?"* — You don't, not really. Hybrid: kill the refresh token, wait out a ≤15-min access window, denylist `jti` only if you need instant kill and can afford the lookup.
2. *"When is a plain session store the right answer?"* — One domain, one first-party web app, revocation matters (banking, admin panels): sessions are simpler, safer, and the "JWT scale" argument rarely survives contact with a Redis cluster.
3. *"Where do you store the refresh token client-side?"* — Web: `HttpOnly; Secure; SameSite=Lax` cookie on a separate path. NEVER `localStorage` (any XSS = full account theft). Mobile: OS secure storage (Keychain/Keystore).
