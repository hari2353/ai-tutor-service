# Production notes — OAuth 2.0 / OIDC

## What you'd actually use

Never build this. Use it *understood*: Auth0, Okta, Keycloak, AWS Cognito, Azure AD, or a hardened OSS AS like Ory Hydra / Authentik. RFC-relevant sections worth citing in an interview: **RFC 6749** (the framework), **RFC 7636** (PKCE), **RFC 8252** (native apps — PKCE required), **OAuth 2.1 draft** (kills implicit + password grants, mandates PKCE for ALL clients), **OpenID Connect Core** (ID token semantics), **RFC 7662** (introspection).

## What the real ones add over yours

- **Redirect URI exactness beyond equality** — RFC 8252 §7.2 allows *case-insensitive scheme/host* comparison for native app custom schemes; every real AS documents its rule and rejects everything else. Your exact-match is the web rule.
- **Client authentication on the token endpoint** — confidential clients send `client_secret` (or `private_key_jwt` / mTLS per RFC 7521/8705); public clients (yours) have no secret, which is exactly why PKCE is mandatory for them.
- **The `state` you built is CSRF protection; real ASes add a full session-binding + PKCE on top** — `state` alone must be high-entropy (you did `token_urlsafe`) because guessable `state` reopens login CSRF.
- **ID token validation rules (OIDC Core §3.1.3.7)** — the client MUST check `iss`, `aud`, `exp`, `nonce`, and (if using max_age) `auth_time`. Getting `aud` wrong is how tokens from the wrong AS get accepted.
- **Code binding is per-AS-account** — real codes also bind to the resource owner's session, so a code minted for one user can't be redeemed in another's context.
- **PAR (RFC 9126)** — push the authorization request to the AS *before* the redirect, so nothing attacker-mutable (scope, redirect, challenge) rides on the front channel.

## What breaks at scale

| Symptom | Cause | Fix |
|---|---|---|
| Codes redeem twice | no single-use atomicity under concurrency | mark-used in one DB transaction (`UPDATE ... WHERE used=false` and check rowcount) |
| Token endpoint DDoS | unauthenticated code probing | rate-limit per client_id + IP; constant-ish responses |
| Codes harvested from logs | codes in query strings get logged everywhere | short TTL (60s), single-use (you built both), POST-only redirects where possible |
| Redirect-based phishing | sloppy client registration (wildcard URIs) | exact registration; reject subpath/wildcard; audit registrations |
| Implicit grant leftovers | 2012-era SPA tutorials | OAuth 2.1 removes it; SPA = code + PKCE with a backend-for-frontend |
| Mixed-up tokens | one client accepting tokens from multiple ASes | `iss` claim check + per-issuer key set |

## Cost & latency

The user-visible part is two redirects + consent; the machine part is one token-endpoint call (~10ms). The design work is all in what's *replayed* on the front channel: codes (short, single-use) and challenges (hashes, not verifiers). PKCE's entire contribution is making a front-channel interception worthless: the interceptor needs the verifier, which never travels on that channel.

## The 3 questions an interviewer asks after you describe this

1. *"Why is PKCE needed if the code is single-use and short-lived?"* — because the *code* travels on the front channel where an attacker can grab it; without PKCE the code alone is enough to redeem. PKCE makes the code useless without the verifier, which only the legitimate client holds in its own memory.
2. *"Why exact redirect_uri matching?"* — open redirects on the AS are the classic account-takeover chain: register `https://app.example/callback/logout`; a registered subpath redirect leaks codes to attacker pages.
3. *"What's wrong with implicit flow?"* — tokens on the front channel, no refresh, no client auth, replayable — OAuth 2.1 deletes it. If a system still uses it, that's a finding.
