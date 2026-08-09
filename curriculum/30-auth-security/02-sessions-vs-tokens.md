# Sessions vs Tokens: Stateful vs Stateless, and the Honest Tradeoff

> **Track:** T30 Auth & Application Security · **Time:** 2h · **Prereqs:** `T30-authn-vs-authz`
> **Updated:** 2026-07-26
> **Module id:** `T30-sessions-vs-tokens` · **Tags:** fundamentals, critical
> **Lab:** none yet — see `labs/py/02-agent-loop/` for the pattern if you want to build one

## The 30-second version

Server-side sessions store a small opaque ID in the cookie and look up the actual session state in a shared store (Redis, a DB) on every request; stateless tokens (JWTs) encode the state itself into a signed artifact the client holds, so any server can verify it with no shared storage. The single question that decides between them is **revocation**: sessions can be invalidated instantly because "logged out" is a row deletion, while a stateless JWT is valid until it expires no matter what the server wants, because there is nothing to delete — you're trusting a signature, not looking anything up. Everything else people cite (scalability, cross-domain SSO, mobile-friendliness) is a real but secondary factor; the actual production decision in 2026 is a hybrid: short-lived stateless access tokens (5-15 min) for authorization decisions, backed by a server-side-tracked refresh token that gives you the revocation lever tokens otherwise lack.

## Why this gets asked

Because "JWT vs sessions" gets recited as a solved debate ("JWTs are stateless and scale better") by people who have never had to revoke one during an active incident — kick a compromised account off *right now*, not in 15 minutes when the token happens to expire. The interviewer wants to know if you understand that statelessness is a tradeoff you're making deliberately, with a specific cost, not a strictly superior architecture. They've likely lived through an incident where "just wait for the token to expire" was the actual incident response plan, and it was unacceptable.

---

## Lineage: past → present → future

**What came before.** Early web apps were stateless by necessity — HTTP has no memory between requests — so Netscape's cookie specification (1994) and the subsequent server-side session pattern (PHP's `session_start()`, Java servlet `HttpSession`, Rails' `ActionDispatch::Session`) became the default: issue an opaque session ID in a cookie, store the actual user state (identity, cart contents, CSRF token) server-side keyed by that ID. This worked cleanly for a single application server with in-process memory, but broke the moment you needed more than one server: session affinity ("sticky sessions") tied a user to one specific backend instance, which meant that instance's failure logged the user out and that scaling out required either replicating session state or centralizing it — the exact pain that led to shared session stores (memcached, then Redis) becoming standard infrastructure by the mid-2000s.

**Where it stands now.** JWTs (finalized as RFC 7519 in 2015, though the pattern predates the RFC by years in SAML and early token schemes) solved the shared-state problem by moving the state into the token itself, signed so it can't be tampered with, verifiable by any server holding the public key or shared secret with zero network calls. This made stateless horizontal scaling and cross-service authorization trivial — any of your 200 pods can verify a request with no Redis round-trip — and made cross-domain/mobile/SPA authentication dramatically simpler than cookie-based sessions, which don't cross domains cleanly. The live disagreement is precisely the revocation problem: purists argue that reintroducing a server-side check (a revocation list, a "logged out" flag looked up on every request) to handle logout/compromise defeats the entire point of stateless tokens — you're back to a database lookup per request, just with extra steps and a bigger token. The pragmatic consensus that has actually won in production is the **hybrid**: short-lived (5-15 minute) stateless access tokens for the bulk of authorization checks, paired with a stateful, database-tracked refresh token that can be revoked, so you get JWT's low-latency verification for 99% of requests while retaining a real revocation lever with a bounded worst case (at most one access-token TTL of exposure after revocation).

**Where it's heading.** The industry is converging on tokens getting *shorter*-lived rather than longer, treating the access token as closer to a capability that expires in minutes, with refresh-token rotation and reuse detection (module 5) doing the heavy lifting for both security and revocability. Durable, database-backed session stores are making a partial comeback even for API-first architectures, but reframed: not "sessions vs tokens" as a binary but "what's the minimum-TTL token plus what's the fastest revocation check we can afford," which is really a latency/consistency budget question rather than an architecture-style question. More speculatively, some platforms are exploring token introspection as a first-class fast path (OAuth 2.0 Token Introspection, RFC 7662, with heavily cached results) as a middle ground — a network call, but one that can be cached at the edge with sub-millisecond amortized cost — though this remains less common than the refresh-token hybrid in practice.

---

## Mental model

```
SESSION MODEL                          TOKEN MODEL
(state on the server)                  (state in the client's hand)

 Client          Server                 Client            Server
 ┌──────┐        ┌────────────┐         ┌──────┐          ┌────────────┐
 │cookie│───────▶│ look up ID │         │ JWT  │─────────▶│ verify sig │
 │ (sid)│        │ in Redis:  │         │(self-│          │ locally,   │
 └──────┘        │ {user:42,  │         │contained)       │ NO lookup  │
                 │  role:admin,         └──────┘          └────────────┘
                 │  cart:[...]}
                 └────────────┘
 REVOKE = DELETE the row.               REVOKE = ??? the signature is
 Takes effect on the VERY NEXT          still valid until expiry. There
 request, everywhere.                   is nothing to delete.

 Cost: a lookup on every request        Cost: none on read (that's the
 (Redis round-trip, ~1ms).              whole appeal) — but you paid for
 Scaling = scale the store.             it by losing instant revocation.
```

The whole debate compresses to one line: **a session is a pointer to truth; a token is a photocopy of truth, timestamped.** A pointer can be redirected instantly. A photocopy is valid until someone checks the timestamp and it's expired — no amount of wishing changes what's already printed on it.

---

## How it actually works

### Server-side sessions, precisely

1. On login, the server creates a session record: `{session_id: <random 128+ bit token>, user_id, created_at, expires_at, ...}` and stores it in a fast shared store (Redis is the default; a relational table works but is slower under high QPS).
2. The client receives only the `session_id` in a cookie — `Set-Cookie: sid=<opaque>; HttpOnly; Secure; SameSite=Lax`. The cookie itself carries no information; it's a lookup key.
3. On every subsequent request, the server reads the cookie, does `GET session:<sid>` against the store, and if found and unexpired, treats the request as authenticated with whatever's in that record.
4. Logout = `DEL session:<sid>`. The very next request with that cookie fails the lookup. **This is the entire value proposition.**

Cost model: one round-trip to the session store per request, typically ~0.5-2ms for Redis on the same network segment, negligible for most workloads but a real, measurable tax at extreme QPS, and a genuine availability dependency — if the session store is down, nobody can be authenticated, full stop.

### Stateless tokens (JWT), precisely

1. On login, the server creates a JWT: header (algorithm), payload (claims: `sub`, `exp`, `iat`, custom claims like `role`), signature (HMAC or RSA/ECDSA over header+payload). Full mechanics in module 3.
2. The client stores the JWT (cookie, localStorage, or in-memory — module 5 covers the tradeoffs) and sends it with each request, typically `Authorization: Bearer <jwt>`.
3. **Any server holding the verification key** checks the signature and the `exp` claim — no network call, no shared store, no dependency on a central service being up.
4. Logout: there is no server-side action that invalidates an already-issued, unexpired JWT. The token remains cryptographically valid until `exp` passes. "Logout" in a pure-JWT system is a client-side fiction — you delete the token from the client, but if an attacker already copied it, it works until expiry regardless of anything the server does.

```python
# Session-based auth check — costs a store round-trip
def authenticate_session(request):
    sid = request.cookies.get("sid")
    session = redis.get(f"session:{sid}")   # network call, ~1ms
    if session is None or session["expires_at"] < now():
        raise Unauthorized()
    return session["user_id"]

# JWT-based auth check — zero network calls
def authenticate_jwt(request):
    token = request.headers["Authorization"].removeprefix("Bearer ")
    payload = jwt.decode(token, key=PUBLIC_KEY, algorithms=["RS256"])  # local CPU op, ~0.1ms
    if payload["exp"] < now():
        raise Unauthorized()
    return payload["sub"]
    # Note: no check exists here for "has this token been revoked" —
    # that information isn't in the token and isn't anywhere the
    # verifier looks by default. This is the entire tradeoff, made concrete.
```

### The revocation problem, worked through numerically

Suppose access token TTL is 15 minutes. An attacker steals a valid token (via XSS, a leaked log, a compromised laptop). Without any revocation mechanism, that token authenticates the attacker for **up to 15 minutes** regardless of anything the victim or the security team does — changing the password, disabling the account in the admin panel, none of it touches an already-issued JWT's validity. Compare to a session: the security team runs `DEL session:<sid>` (or, more realistically, deletes all sessions for that user) and the token is dead on the next request, typically within seconds of the decision being made.

This is why the honest engineering answer is never "JWTs don't need revocation because they're short-lived" — 15 minutes of unauthorized access to a payments API or an admin panel is not an acceptable residual risk for most systems. The real answer is a hybrid, covered next.

### The hybrid that's actually deployed

- **Access token**: JWT, 5-15 minutes, stateless, verified with zero lookups, used for the actual authorization decision on every request.
- **Refresh token**: opaque, long-lived (days to weeks), stored server-side (a DB row, not just a signature), used only to mint new access tokens. Because it's stored server-side, it **can** be revoked instantly — delete the row, and the next refresh attempt fails, and the compromised access token (if any) expires naturally within its short TTL.
- **Worst-case exposure window after revocation**: bounded by the access token's TTL, not the refresh token's — this is the number you quote in an interview. A 10-minute access-token TTL means revocation takes full effect within 10 minutes even though the underlying token itself can't be individually invalidated.

This is exactly the pattern OAuth 2.0/2.1 formalizes with refresh token rotation and reuse detection (module 5 goes deep on the mechanics), and it's the reason "stateless" JWT systems in production are rarely *purely* stateless — they've reintroduced a small amount of state exactly where it buys the most safety per byte.

---

## Build it from scratch

A minimal illustration of both models side by side, enough to reason about the actual code difference:

```python
import time, secrets, jwt  # untested sketch — illustrates the shape, not production-hardened

SECRET = "demo-only-do-not-use"
SESSION_STORE = {}   # stand-in for Redis

# --- Session model ---
def create_session(user_id: str) -> str:
    sid = secrets.token_urlsafe(32)
    SESSION_STORE[sid] = {"user_id": user_id, "expires_at": time.time() + 3600}
    return sid

def check_session(sid: str) -> str | None:
    s = SESSION_STORE.get(sid)
    if s is None or s["expires_at"] < time.time():
        return None
    return s["user_id"]

def revoke_session(sid: str) -> None:
    SESSION_STORE.pop(sid, None)   # takes effect immediately, everywhere

# --- Token model ---
def create_access_token(user_id: str, ttl_seconds: int = 900) -> str:
    now = int(time.time())
    return jwt.encode(
        {"sub": user_id, "iat": now, "exp": now + ttl_seconds},
        SECRET, algorithm="HS256",
    )

def check_access_token(token: str) -> str | None:
    try:
        payload = jwt.decode(token, SECRET, algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None
    return payload["sub"]
    # There is deliberately no revocation check here. Verifying
    # this way means "revoke" is a fiction until ttl_seconds elapses.

# --- Hybrid: server-tracked refresh token gives back a revocation lever ---
REFRESH_STORE = {}

def create_refresh_token(user_id: str) -> str:
    rt = secrets.token_urlsafe(32)
    REFRESH_STORE[rt] = {"user_id": user_id, "revoked": False}
    return rt

def refresh_access_token(refresh_token: str) -> str | None:
    record = REFRESH_STORE.get(refresh_token)
    if record is None or record["revoked"]:
        return None
    return create_access_token(record["user_id"])

def revoke_refresh_token(refresh_token: str) -> None:
    if refresh_token in REFRESH_STORE:
        REFRESH_STORE[refresh_token]["revoked"] = True
        # existing access tokens minted from this refresh token still
        # work until THEIR OWN exp — this is the bounded worst case.
```

Full version with Redis-backed sessions, RS256 JWTs, and refresh-token rotation with reuse detection: **`labs/py/02-session-vs-jwt/`**.

---

## How it's done in production

**Sessions at scale** — Redis Cluster or a managed equivalent (ElastiCache, MemoryStore) as the shared store, with session data kept intentionally small (a user ID and a few flags, not the full user object) to keep lookups fast and memory bounded. Sticky sessions are largely avoided now precisely because the shared store removes the need for them — any backend instance can serve any request.

**Tokens at scale** — access tokens verified locally at every service with no central dependency; the identity provider (Auth0, Okta, a custom auth service) is only in the request path for login and refresh, not for every authenticated request. This is the actual scalability win people cite, and it's real: removing a network hop from the hot path for the vast majority of requests.

**What frameworks add**: Auth0/Okta/Cognito manage refresh-token rotation, reuse detection, and revocation-list infrastructure for you, plus session-equivalent "kill switches" (revoke all sessions for a user) that operate against their own token/session store rather than yours.

### Failure-mode table

| Symptom | Cause | Fix |
|---|---|---|
| User reports "I logged out but I'm still logged in on another device" | Pure JWT with no refresh-token revocation; old access token still valid until its own exp | Add server-tracked refresh tokens; "logout everywhere" revokes all refresh tokens for the user, bounded exposure = one access-token TTL |
| Redis outage takes down all authentication | Session store is a single point of failure with no fallback | Redis Cluster with replicas; consider a short-TTL local cache of "known valid" sessions to survive brief store blips, invalidated conservatively |
| Latency spike correlates exactly with session-store network hops under load | Session lookup on the hot path, store under-provisioned or in a different AZ | Co-locate store with app tier; consider read replicas for session lookups |
| Compromised admin account stayed active for 15 minutes after password reset | Access token TTL too long relative to incident-response tolerance for that resource's sensitivity | Shorten access-token TTL for high-privilege scopes specifically; don't use one global TTL for all roles |
| JWT grows to several KB, requests start hitting header-size limits | Too many/large custom claims embedded (permission lists, full profile data) | Keep JWT claims minimal (sub, exp, a few flags); look up anything large server-side by ID |
| "Stateless" JWT system actually does a DB lookup on every request anyway | Team added a revocation check per-request to compensate for missing hybrid design, defeating the latency win | Either commit to short TTL + refresh-token hybrid (bounded staleness, no per-request lookup) or commit to sessions (accept the lookup, get instant revocation) — don't pay the cost of both without the benefit of either |

---

## Tradeoffs & when NOT to use it

- **Don't choose pure stateless JWTs for anything requiring instant, no-exceptions revocation** — a payments authorization service, an admin control plane, anything where "compromised credential valid for N more minutes" is an unacceptable answer to a security review. Use sessions or the refresh-token hybrid with an aggressively short access-token TTL.
- **Don't choose server-side sessions for a system whose primary need is cross-service, cross-domain, or high-fan-out verification** — a public API consumed by dozens of independent services, a mobile app talking to multiple backend clusters. The per-request store round-trip and the operational dependency on a single shared store become the bottleneck and the outage risk.
- **Don't treat "we use JWTs" as synonymous with "we don't need a database."** As covered in module 1, authorization decisions (not authentication ones) frequently need current state regardless of what's in the token, so the database dependency you thought you removed often comes back for a different reason.
- **The "stateless scales better" argument is real but overstated** — a well-provisioned Redis cluster serving session lookups handles enormous QPS (tens of thousands of ops/sec per node is unremarkable), and for most systems the actual bottleneck is elsewhere. Choose statelessness for its revocation cost, not because sessions are secretly slow — they usually aren't, at the scale most companies actually operate at.
- **Cookies vs Authorization header is a related but separate axis** — sessions are almost always cookie-based (browser-managed, `HttpOnly` protects against XSS exfiltration); JWTs can be carried in either a cookie or a header, and putting a JWT in a cookie gets you CSRF exposure that a header-based Bearer token doesn't have, while a header-based token loses the `HttpOnly` protection cookies offer against XSS. Neither storage location is free of tradeoffs; module 5 covers this in depth.

---

## Interview questions

### Q1 — What's the fundamental tradeoff between server-side sessions and stateless JWTs?
**Testing:** whether the answer centers on revocation or gets lost in secondary factors.
**Answer:** Sessions store an opaque ID that's looked up server-side on every request, so logout/revocation is an instant row deletion; JWTs encode the state itself in a signed artifact verified locally with no lookup, which removes a network round-trip on every request but means there's nothing to delete — a valid JWT stays valid until it expires no matter what the server wants. Everything else (scalability, cross-domain SSO) is real but secondary to this.
**Follow-up trap:** *"So JWTs are just worse?"* — no; the right framing is that JWTs trade instant revocability for zero-lookup verification, and production systems that need both use a hybrid: short-lived JWT access tokens plus a server-tracked, revocable refresh token.

### Q2 — Your security team needs to kill a compromised user's access immediately. Walk through what happens under a pure-JWT system versus the hybrid.
**Testing:** whether the candidate can quantify the actual exposure window, not just describe the pattern.
**Answer:** Pure JWT: there is no action that invalidates an already-issued token; the attacker's session remains valid until the token's own `exp`, full stop, regardless of password resets or account disables done elsewhere. Hybrid: revoke the refresh token (a DB row delete/flag flip) immediately; the attacker's current access token still works until its own short TTL elapses, so worst-case exposure equals the access-token TTL, not the refresh-token lifetime — typically minutes, not days.
**Follow-up trap:** *"What if the attacker already has a valid, unexpired access token when you revoke the refresh token?"* — that access token still works until it naturally expires; revoking the refresh token only stops *new* access tokens from being minted. This is exactly why the access-token TTL should be chosen based on your tolerance for this specific residual-risk window, not set arbitrarily long "for convenience."

### Q3 — Why did the industry move toward tokens in the first place if sessions can scale via Redis?
**Testing:** whether they can articulate the real scaling win precisely, without overstating it.
**Answer:** Removing the network dependency for cross-service and cross-domain verification — any of N services can verify a JWT locally with zero calls to a central store, which matters enormously for microservice fan-out and for mobile/SPA clients hitting multiple independently-scaled backends. Redis-backed sessions scale fine for a single application's request volume; the pain shows up specifically at cross-service verification fan-out, not raw QPS to one service.
**Follow-up trap:** *"Doesn't the refresh-token hybrid reintroduce that same central dependency?"* — only for the (much rarer) refresh flow, not for every request; the access-token verification path, which is the hot path, stays lookup-free. The central dependency moves from "every request" to "once every 5-15 minutes per client," which is the actual engineering win.

### Q4 — A junior engineer proposes storing the user's full permission list in the JWT payload "so we never have to hit the database." What's your response?
**Testing:** understanding of claim staleness and token bloat.
**Answer:** Two problems: first, a permission revoked mid-token-lifetime won't take effect until the token expires, which for anything beyond trivial TTLs is an authorization bug waiting to happen (this connects directly to module 1's authn/authz separation); second, large claim sets bloat the token, which is sent on every request and can hit header-size limits or add meaningful bytes at high request volume. Keep JWTs to `sub`, `exp`, and a small number of coarse, slow-changing claims (role, tenant ID); look up fine-grained or fast-changing permissions server-side by ID when needed.
**Follow-up trap:** *"What counts as 'slow-changing enough' to embed?"* — anything whose staleness window (bounded by the token's TTL) is acceptable if it's wrong for that long. A role that changes rarely and where a stale value being wrong for 10 minutes is low-risk is fine to embed; a permission flag tied to an active security incident is not.

### Q5 — Explain why putting a JWT in a cookie versus an Authorization header changes the security model, not just the transport.
**Testing:** whether they connect storage location to specific attack surfaces (previewing module 5's depth).
**Answer:** A JWT in a cookie is automatically attached by the browser to matching-origin requests, which reintroduces CSRF exposure (an attacker's page can trigger a request that carries the cookie) unless mitigated with `SameSite` and/or anti-CSRF tokens; a JWT sent via `Authorization: Bearer` header requires explicit JavaScript to attach it, which removes CSRF risk but requires the client to have the token accessible to JS, which is exactly what exposes it to XSS-based exfiltration if stored in `localStorage`. Neither is unconditionally safer; they trade CSRF exposure for XSS exposure.
**Follow-up trap:** *"Can you get the best of both?"* — an `HttpOnly` cookie holding the token gets you XSS-exfiltration protection (JS can't read it) while keeping CSRF exposure, which you then mitigate with `SameSite=Strict/Lax` plus a double-submit or synchronizer CSRF token. This is a legitimate "best available" combination, not a free lunch — it just relocates where you have to do the mitigation work.

### Q6 — What's the actual latency cost difference between a session lookup and a JWT verification, and does it matter?
**Testing:** numbers-over-adjectives, and judgment about when it matters.
**Answer:** A Redis session lookup on the same network segment is typically sub-2ms; a local JWT signature verification (especially HMAC, somewhat more for RSA) is sub-0.5ms and involves no network hop at all. For most systems this difference is immaterial next to overall request latency (tens to hundreds of milliseconds including business logic and downstream calls); it matters at extreme fan-out (hundreds of internal service calls per user request, each needing independent verification) or at very high QPS where the session store itself becomes a capacity-planning concern.
**Follow-up trap:** *"So should everyone just default to JWTs for the latency win?"* — no; if the actual bottleneck isn't verification latency, you shouldn't accept JWT's revocation cost for a benefit you're not capturing. Profile before optimizing for a cost that may not be your system's actual constraint.

### Q7 — Design the token strategy for a banking app's mobile client, where a stolen phone needs to be lockable within seconds.
**Testing:** applying the hybrid model to a concrete, high-stakes scenario.
**Answer:** Very short access-token TTL (60-300 seconds is defensible for high-sensitivity banking flows) paired with a server-tracked refresh token bound to the device (device fingerprint or a hardware-backed key), so "lock this device" is a refresh-token revocation that takes full effect within the access token's short TTL — worst case a few minutes of exposure on an already-open session, and zero on any new request needing a fresh access token.
**Follow-up trap:** *"Isn't refreshing every 60 seconds expensive?"* — it's one extra request per minute per active client to the auth service, which is a bounded, predictable load the auth service can be provisioned for; that's a much smaller and more acceptable cost than an unrevocable multi-minute-or-longer token window on a banking app.

### Q8 — Someone argues "sessions are legacy, tokens are the modern approach." Push back.
**Testing:** resistance to false dichotomies, a strong senior signal.
**Answer:** Sessions and tokens solve different problems and both remain in active, correct use in 2026 — a server-rendered monolith with one backend cluster serving one first-party domain has no real need for stateless cross-service verification and gains real, instant revocation from sessions with negligible cost. "Modern" systems that need cross-service fan-out or cross-domain SSO benefit from tokens, but the honest modern architecture is usually the hybrid, which is neither pure sessions nor pure stateless tokens — it deliberately reintroduces a small amount of server-side state exactly where revocation matters most.
**Follow-up trap:** *"If someone asked you to pick one right now for a new project with unknown future scale, which would you pick?"* — start with the hybrid pattern (short JWT access token + server-tracked refresh token) by default, because it's the one that doesn't foreclose either scaling path and gives you a working revocation story from day one rather than retrofitting one under incident pressure later.

### Q9 — Your team's incident response runbook says "for a compromised account, disable the user in the admin panel." Under a pure-JWT system, why is that runbook incomplete?
**Testing:** connecting the abstract revocation problem to a concrete operational gap.
**Answer:** Disabling the user changes a database flag that a *future* login check would see, but it does nothing to an *already-issued* JWT, which carries no reference back to that flag and is verified purely by signature and expiry — the attacker's existing token keeps working until it naturally expires regardless of the disable flag. The runbook needs an explicit "revoke all refresh tokens / add to a deny-list checked on the auth path" step, or the fix is cosmetic.
**Follow-up trap:** *"What if you don't have refresh tokens and access tokens are the only artifact?"* — then your only lever is a revocation list of individual token IDs (`jti` claims) checked against on every verification, which reintroduces the exact per-request lookup you adopted JWTs to avoid — a real, sometimes necessary compromise, and worth naming explicitly as "we gave up the latency win to regain revocability" rather than pretending it's free.

### Q10 — What would make you recommend token introspection (RFC 7662) over a local-JWT-plus-refresh-token hybrid?
**Testing:** awareness of the less common middle-ground pattern and when it earns its keep.
**Answer:** When the resource servers verifying tokens don't trust each other enough (or aren't positioned) to hold the verification key material directly, or when you need centralized, real-time visibility into every token check for compliance reasons, introspection — a network call to the authorization server per verification, heavily cached at the edge — trades some latency for centralized control and audit visibility that local JWT verification structurally can't give you (the auth server never sees most verifications happen).
**Follow-up trap:** *"Isn't that just sessions with extra steps?"* — functionally similar in cost profile (a lookup per verification, cacheable), yes; the meaningful difference is that it's a standardized protocol (RFC 7662) usable across organizational boundaries where you don't control or trust the resource server's internals, which a bespoke session store doesn't offer.

---

## Red flags that fail you

- Calling JWTs "more secure" than sessions, or vice versa, without naming the specific tradeoff (revocation vs statelessness) being made.
- Proposing "just make the JWT TTL very long for convenience" without acknowledging the resulting revocation exposure window.
- Not knowing that a pure-JWT system has no server-side logout mechanism for already-issued tokens.
- Treating the refresh-token hybrid as something exotic rather than the actual production default.
- Claiming sessions "don't scale" without qualifying against what specific dimension (cross-service fan-out vs raw QPS to a single service).
- Storing large or fast-changing data in JWT claims and calling it a performance optimization.

---

## Cheat card

```
SESSION = pointer to server-side truth. Revoke = DELETE row. Instant, everywhere.
  Cost: lookup per request (~0.5-2ms Redis), shared-store availability dependency.

JWT     = signed photocopy of truth, timestamped. Revoke = nothing you can do to
          an issued token; valid until exp() regardless of server-side state changes.
  Cost: zero lookup per request (the whole appeal) -- lost instant revocation.

THE ACTUAL PRODUCTION PATTERN (hybrid):
  access token  = JWT, 5-15 min TTL, stateless verify, used for every request
  refresh token = opaque, server-tracked (DB row), days-weeks TTL, revocable
  worst-case exposure after revocation = access-token TTL, NOT refresh-token TTL

DECISION RULE: need instant no-exceptions revocation? -> sessions or hybrid w/ short TTL
               need cross-service/cross-domain zero-lookup verification? -> tokens/hybrid
               "JWTs mean no DB" is FALSE -- authz decisions still need current state

STORAGE AXIS (separate from stateful/stateless):
  cookie  -> CSRF exposure, mitigate w/ SameSite + anti-CSRF token; HttpOnly blocks XSS read
  header  -> no CSRF exposure, but JS must hold token -> XSS exfiltration risk if in localStorage

LATENCY: Redis session lookup ~0.5-2ms · local JWT verify ~<0.5ms, zero network calls
NEVER: embed fast-changing permissions or large data in JWT claims (staleness + bloat)
```

## Sources

- [RFC 7519 — JSON Web Token (JWT)](https://www.rfc-editor.org/rfc/rfc7519) — accessed 2026-07-26
- [RFC 7662 — OAuth 2.0 Token Introspection](https://www.rfc-editor.org/rfc/rfc7662) — accessed 2026-07-26
- [Refresh Token Security: Best Practices for OAuth Token Protection — Obsidian Security](https://www.obsidiansecurity.com/blog/refresh-token-security-best-practices) — accessed 2026-07-26
- [Token Lifetime Best Practices: Access, Refresh, ID, and Session Tokens in 2026](https://guptadeepak.com/ciam-compass/guides/token-lifetime-best-practices/) — accessed 2026-07-26

## Changelog
- 2026-07-26 — created
