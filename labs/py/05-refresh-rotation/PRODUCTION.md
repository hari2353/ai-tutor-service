# Production notes — token lifecycle

## What you'd actually use

| Concern | Production answer |
|---|---|
| Rotation + reuse detection | The pattern is from the OAuth 2.1 draft (refresh tokens MUST be rotation-bound) and RFC 6749 §10.4–10.5 |
| Refresh token storage | Server-side, **hashed** — SHA-256 at minimum; Argon2id/bcrypt if you fear offline attacks on the store itself |
| Access token | JWT, 5–15 min, no crypto to implement — the introspection decision is the design work |
| Introspection | RFC 7662 (Token Introspection) endpoint behind a **short** cache, invalidated by revocation events |
| Rotation races | A 30–60s **grace window**: accept the just-rotated token once, flag it, don't revoke — real IdPs (Auth0, Okta) all do this |

## What the real systems add over yours

- **A revocation event bus, not method calls** — revocation must fan out to every node holding a cached "valid"; real systems publish to Redis pub/sub / Kafka and caches subscribe. Your `invalidate()` is the single-node version.
- **Database-backed families with a `replaced_by` chain** — the full audit trail of a session across 200 rotations, so you can answer "what did the attacker get?" after a breach.
- **Slow hashes for the store** — SHA-256 is fast (good for lookup, bad if the table leaks). Production splits the difference: SHA-256 for the lookup key + a slow KDF for verifiable copies. Your `hash_token` docstring says this.
- **Sliding absolute caps** — refresh_ttl 7d *sliding* but capped at 30d absolute: an idle attack surface that never expires is a compliance finding.
- **Sender-constrained tokens (DPoP / mTLS-bound)** — the post-2022 answer to replay: even a stolen refresh token can't be used from another client.

## What breaks at scale

| Symptom | Cause | Fix |
|---|---|---|
| Users randomly logged out | clock skew / in-flight requests racing rotation | grace window for the just-rotated token |
| Reuse detection false-positives | two tabs, one user, simultaneous refresh | grace window + per-user serialization, not per-token |
| Revoked tokens still work for 60s | introspection cache TTL | cache positive results short (≤30s), negatives never; invalidate on the event bus |
| Store leak = account takeover | raw refresh tokens in the DB | hashed only (you did this); slow KDF for the verifiable copy |
| Families table grows forever | ghosts kept for reuse detection | TTL the ghosts (e.g. 30d) — detection only needs to outlive the active attack |
| 401 storms at token boundary | client refreshes only on failure, all requests in flight | proactive refresh at 80% of TTL + backoff |

## Cost & latency

Every request: zero network (JWT verify, ~50µs). Once per 15 min per user: the refresh round-trip. Once per 15 min per user *per node*: an introspection miss — amortized, this is the "statelessness with a revocation lever" pitch in numbers.

## The 3 questions an interviewer asks after you describe this

1. *"Reuse detection kills the family — what happens to the legit user?"* — They re-login. That's the deal: you trade their session for a theft signal. The grace window exists so *races* don't trigger it, only actual theft does.
2. *"Why hash the refresh token in the store?"* — the store is the juiciest target (one row = one account). A leak of hashes is unusable without the raw tokens, which exist only client-side.
3. *"Why not just make access tokens 1 minute and skip refresh entirely?"* — the refresh round-trip moves to *every minute per user*; you've rebuilt statelessness with more traffic. 5–15 min + rotation is the empirically-settled middle.
