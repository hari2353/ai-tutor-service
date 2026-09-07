# Production notes — JWT attacks in the wild

## The real incidents these map to

| Attack | Real-world case | The lesson |
|---|---|---|
| `alg=none` | CVE-2015-9235 (node.js `jsonwebtoken` ≤4.2.0) | the attacker picks the algorithm if you let the header decide |
| Key confusion | the 2018 Spotify showcase (algorithm-per-key confusion against a Java service) | one `key` parameter + several accepted algs = the bug |
| Weak HMAC secret | everywhere, forever | offline cracking; only length+entropy defends |
| Replay | inherent to stateless tokens | bounded by TTL, not prevented |
| Revocation gap | every "logout doesn't work" bug report | hybrid + short TTL |

## The real defenses

- **Pin algorithms at the decode call.** PyJWT: `jwt.decode(tok, key, algorithms=["HS256"])` — the `algorithms` list is not optional hygiene; an `alg` accepted that you didn't expect IS the vulnerability, whether it's `none`, `HS256` where you meant `RS256`, or `RS256` with a spoofed `kid`.
- **Never share one key slot across algorithm families.** Key confusion is a *type* problem: HMAC secrets and RSA public keys are different types; APIs that take "a key" blur that. Spotify's fix was exactly the `SecureConfusionVerifier` shape: separate fields, strict mapping.
- **HS256 secrets: ≥32 random bytes** (RFC 7518 §3.2 — and PyJWT ≥2.13 warns below 32). Generate with a CSPRNG, store in a secrets manager, never in env-var-committed YAML.
- **`kid` is attacker input.** Allowlist formats; never filesystem paths, never SQL, never unbounded length.
- **The revocation answer:** access TTL 5–15 min (the *bounded worst case* you accept), revocable server-side refresh, rotation + reuse detection (OAuth 2.1 draft §refresh-token-rotation: replay of a rotated token ⇒ revoke the family — it's a theft signal).
- **`jti` + denylist only when you need instant kill** — and admit you've reintroduced a per-request lookup; cache it (this is Lab 05's introspection cache).

## Production-grade nuances

- **The failure mode of fixes:** breaking legitimate tokens during key rotation. Real verifiers accept *two* kids during the overlap window and log which one validated.
- **CRIME-level subtlety:** even a correct verifier leaks via *timing* which alg branch ran. Compare digests with `hmac.compare_digest` — constant-time, never `==`.
- **Test continuously, not once.** The alg=none and key-confusion tests here are exactly what belongs in your CI security suite — a dependency upgrade can silently reintroduce the bug you fixed.
- **Watch for JWT libraries with permissive defaults** — `jwt.decode(tok, key)` with no `algorithms` kwarg was PyJWT's own CVE-2022-29217 class of footgun (it now refuses; older code still errors this way).
- **JWKS endpoints are attack surface too:** unbounded `kid` lookups = DoS; cache with TTL; re-fetch only on unknown kid.

## Failure table

| Symptom | Cause | Fix |
|---|---|---|
| Unsigned token validates | verifier trusts header alg | pin `algorithms=[...]` at every decode site |
| HS256 token validates on an RS256 service | one key arg, multi-alg acceptance | typed keys per alg family; reject alg mismatch first |
| Secret cracked from a public token | dictionary/short HMAC secret | 32+ random bytes from CSPRNG; rotate periodically |
| Stolen token can't be killed | stateless exp is the only lever | short TTL + revocable refresh + rotation with reuse detection |
| Rotation locks out legit users | no grace window on refresh | 30–60s grace for clock-skew/token-in-flight races (see Lab 05) |
