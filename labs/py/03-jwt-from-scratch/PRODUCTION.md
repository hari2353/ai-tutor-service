# Production notes — JWT in the real world

## What you'd actually use

| Language | Library |
|---|---|
| Python | `pyjwt` / `joserfc` / `authlib` |
| Java | `spring-security-oauth2-jose`, `nimbus-jose-jwt` |
| Go | `golang-jwt/jwt/v5`, `go-jose` |
| Node/TS | `jose`, `jsonwebtoken` (v9+ only — ≤8.x had the alg=none class of bugs) |

Never hand-roll JWT in production. You just built it so you can *debug* it — reading a `kid` mismatch from a hex dump, or knowing why a 0-length signature segment is fatal.

## What the real ones add over yours

- **JWKS fetching + caching + rotation** — `/.well-known/jwks.json`, cached with `Cache-Control`, re-fetched on unknown `kid` (a signal a rotation just happened). Your registry is the in-memory core of that.
- **`kid` injection defenses** — real verifiers treat `kid` as an untrusted string: no filesystem paths from it (the classic `kid: "../../../dev/null"` attack), no SQL, bounded length.
- **Leeway you must have** — distributed clocks skew; PyJWT's default is 0 but every production deployment sets 30–60s. Yours is explicit and injectable — the right shape.
- **Required-claim policy** — `options={"require": ["exp", "sub", "iss"]}` so a token *missing* exp is rejected, not treated as never-expiring. Your `decode` only checks claims that are present — add `require` semantics in the stretch.
- **PS256/ES256** — randomized/deterministic signatures with better length properties than PKCS#1 v1.5; RS256 remains the interop default.

## What breaks at scale

| Symptom | Cause | Fix |
|---|---|---|
| Valid tokens rejected sporadically | clock skew between issuer and verifier | leeway 30–60s; NTP everywhere |
| Intermittent 401s after key rollover | verifier cached old JWKS forever | re-fetch on unknown kid + respect cache headers |
| Giant tokens in headers | stuffing the whole profile into claims | claims are for *identity*, not data; keep JWTs < 8KB (some proxies 413 on bigger) |
| `alg` confusion incidents | verifier trusts the token's own alg header | pin `algorithms=[...]` at the decode call — always, no exceptions |
| Nobody can log out | stateless exp is the only kill switch | Lab 02's hybrid: short access TTL + revocable refresh |

## Cost & latency

HS256 verify: ~50µs, zero network — but the symmetric secret is shared with every verifier, so any verifier can also *forge* tokens. RS256 verify: ~100–200µs (public-key op), and verifiers only ever hold public keys — the right choice once more than one service verifies. Rule of thumb: one issuer, one verifier, internal → HS256; anything multi-party → RS256.

## The 3 questions an interviewer asks after you describe this

1. *"Why does RS256 even exist when HS256 is faster?"* — key distribution: with HMAC every verifying service holds a key that can mint tokens; RSA splits that power (public verifies, private signs, kept in one place/KMS).
2. *"What's in the signature, exactly?"* — over `base64url(header) + "." + base64url(payload)` — the ASCII bytes including the dot, not the decoded JSON. Getting this wrong is why hand-rolled JWTs fail.
3. *"Your token has `exp` — what if the clock is wrong?"* — leeway for skew both directions, and `nbf` on issued tokens so a slightly-fast verifier doesn't accept a token before it exists.
