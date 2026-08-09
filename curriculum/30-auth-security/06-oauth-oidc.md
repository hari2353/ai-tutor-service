# OAuth 2.0 + OIDC: Auth Code + PKCE, Client Credentials, Device Flow, and the Dead Ones

> **Track:** T30 Auth & Application Security · **Time:** 3h · **Prereqs:** `T30-token-lifecycle`
> **Updated:** 2026-07-26
> **Module id:** `T30-oauth-oidc` · **Tags:** oauth, critical
> **Lab:** none yet — see `labs/py/02-agent-loop/` for the pattern if you want to build one

## The 30-second version

OAuth 2.0 is a *delegation* protocol — it lets an application access a resource on a user's behalf without ever seeing the user's password — with four roles (resource owner, client, authorization server, resource server) and a handful of grant types for different client shapes. Authorization Code with PKCE is the one correct default in 2026 for anything with a redirect and a user present, including public clients (SPAs, mobile apps) where PKCE closes the authorization-code-interception attack that made the Implicit grant necessary in the first place — which is exactly why OAuth 2.1 removes Implicit and the Resource Owner Password Credentials grant entirely rather than merely discouraging them. OIDC is a thin identity layer bolted on top of OAuth, adding the ID token (a JWT describing *who authenticated*, meant for the client to consume) alongside OAuth's access token (an opaque-or-JWT credential describing *what the client can do*, meant for the resource server to consume) — conflating the two is the single most common OAuth/OIDC interview trap, because they answer genuinely different questions and using one where the other belongs is a real, recurring security bug, not just a naming confusion.

## Why this gets asked

Because OAuth is the protocol most engineers integrate via a library ("click here to log in with Google") without ever reading the RFC, and the interviewer wants to know if you understand what's actually happening during that redirect dance — specifically whether `state` and PKCE's `code_verifier`/`code_challenge` are decorative or load-bearing, and whether you know an ID token is not a credential to send to an API. They've likely debugged an integration where a team used the ID token as if it were an access token (or vice versa) and broken authorization somewhere as a result.

---

## Lineage: past → present → future

**What came before.** Before OAuth, the standard pattern for third-party integrations was straightforwardly bad: a third-party app (a photo-printing service, an early social-media aggregator) asked users to type their actual username and password for another service (their email, their bank) directly into the third-party's own form, then stored those credentials to act on the user's behalf indefinitely. This is called the "password anti-pattern," and its failure mode was structural, not incidental: the third party now held a permanent, unscoped, unrevocable-except-by-password-change credential with full account access, with no way for the user to grant a narrower scope ("just read my contacts") or revoke access to just that one integration without changing their password everywhere. OAuth 1.0 (2007) was the first serious standardized fix, using cryptographic request-signing instead of shared passwords, but its signature-computation process was notoriously fiddly to implement correctly across languages and HTTP client quirks, which drove the industry toward OAuth 2.0 (RFC 6749, 2012), which dropped request-signing in favor of bearer tokens over mandatory TLS — simpler to implement, at the cost of making TLS itself a hard dependency for security (a bearer token with no signature is only as safe as the channel carrying it).

**Where it stands now.** OAuth 2.0's original spec included several grant types tuned for the client landscape of 2012 — notably the Implicit grant (return the access token directly in the redirect URI fragment, designed for browser-based JS apps that couldn't securely hold a client secret) and the Resource Owner Password Credentials grant (the client collects the user's password directly and exchanges it for a token, designed for "trusted first-party" native apps). Both are now considered dead: Implicit exposes the access token in browser history, referrer headers, and any JS on the page, with no code-exchange step to add a layer of indirection, and has been fully superseded by Authorization Code + PKCE, which even public clients (SPAs, mobile apps, previously Implicit's target audience) can now use safely because PKCE removes the need for a client secret while still preventing authorization-code interception. Resource Owner Password Credentials is dead because it reintroduces the exact password anti-pattern OAuth was invented to eliminate — the client sees the raw password — and is incompatible with anything beyond single-factor password auth (no room for MFA, no room for federated/social login, no room for passkeys). The live disagreement in 2026 is less about grant-type choice (this part is settled) and more about the OAuth 2.1 consolidation itself: as of early-to-mid 2026 it remains an IETF Internet Draft, not a ratified RFC, yet its recommendations (mandatory PKCE for all clients, removal of Implicit and ROPC, refresh token rotation as a MUST) are already the de facto standard enforced by every major identity provider and increasingly required by security audits (SOC 2, ISO 27001) regardless of its formal RFC status.

**Where it's heading.** OIDC's adoption for new builds is essentially universal — "start with OIDC unless you're integrating with a legacy enterprise IdP that only speaks SAML" is the practical 2026 rule of thumb (module 7 covers the SAML side) — and the direction of travel for OAuth itself is toward sender-constrained tokens (DPoP, mTLS) becoming the recommended default for access tokens issued to sensitive APIs, closing the bearer-token replay gap that plain OAuth 2.0/2.1 doesn't address (module 4, module 5). More speculatively, OAuth-style delegated authorization is being adapted for agentic AI systems — an LLM agent acting on a user's behalf needs something *like* an OAuth grant (scoped, time-limited, revocable, auditable) but the existing grant types assume a human clicking "allow" in a browser redirect, which doesn't map cleanly onto a multi-step autonomous agent deciding at runtime which tool to call next; expect purpose-built delegation protocols for agents to emerge from this gap, but treat this as an open problem rather than a solved pattern as of mid-2026.

---

## Mental model

```
                          OAUTH 2.0 — FOUR ROLES

  RESOURCE OWNER          CLIENT              AUTHORIZATION SERVER      RESOURCE SERVER
  (the user)          (the app wanting       (issues tokens after        (the API holding
                        access on your        the resource owner          the actual data,
                        behalf — e.g. a       grants consent —            e.g. Google's
                        photo-print app)      e.g. Google's OAuth         Photos API)
                                              server)
       │                     │                       │                        │
       │  1. "let this app   │                       │                        │
       │  see my photos"─────┼──────────────────────▶│                        │
       │◀── consent screen ──┤                       │                        │
       │  2. user clicks     │                       │                        │
       │  "Allow" ───────────┼──────────────────────▶│                        │
       │                     │◀── authorization code ┤                        │
       │                     │  3. code + PKCE       │                        │
       │                     │  verifier ────────────▶                        │
       │                     │◀── access_token ───────┤                        │
       │                     │  4. access_token ──────┼───────────────────────▶│
       │                     │◀───────────── the actual photos data ──────────┤

  OIDC adds a FIFTH artifact on top of this exact flow: an ID_TOKEN (JWT),
  returned alongside the access_token in step 3, describing WHO authenticated.
  It is for the CLIENT to read ("oh, this is alice@example.com"), never to
  be sent to the resource server as if it were an access token.

  ACCESS TOKEN  -> "what can the bearer DO"   -> sent to the RESOURCE SERVER
  ID TOKEN      -> "WHO authenticated"        -> read by the CLIENT, stops there
```

---

## How it actually works

### The four roles, and where each maps to your architecture

- **Resource owner** — the user. Owns the data being accessed.
- **Client** — your application, requesting access on the user's behalf. Can be *confidential* (can hold a secret safely — a backend server) or *public* (cannot — a SPA running in a browser, a mobile app whose binary can be decompiled).
- **Authorization server** — issues tokens after the resource owner consents (Okta, Auth0, Google's OAuth server, your own OIDC provider).
- **Resource server** — the API that actually holds the protected data and accepts the access token.

### Authorization Code + PKCE, mechanically

1. Client redirects the user's browser to the authorization server with a `code_challenge` (a hash of a locally-generated random `code_verifier`), `redirect_uri`, `scope`, and `state`.
2. User authenticates with the authorization server and consents.
3. Authorization server redirects back to the client's `redirect_uri` with a short-lived, single-use **authorization code**.
4. Client exchanges the code for tokens by POSTing it to the token endpoint, **along with the original `code_verifier`** (not the hashed challenge — the raw value).
5. Authorization server recomputes the hash of the presented `code_verifier` and checks it matches the `code_challenge` from step 1 — if they don't match, the exchange fails.

```python
import hashlib, base64, secrets

# Step 0 (client, before redirecting the user)
code_verifier = secrets.token_urlsafe(64)   # 43-128 chars per RFC 7636
code_challenge = base64.urlsafe_b64encode(
    hashlib.sha256(code_verifier.encode()).digest()
).rstrip(b"=").decode()

# code_verifier is kept ONLY client-side (never sent in the initial redirect)
# code_challenge (the hash) IS sent in the initial authorization redirect URL

authorization_url = (
    f"https://auth.example.com/authorize?response_type=code"
    f"&client_id=abc123&redirect_uri=https://app.example.com/callback"
    f"&scope=openid%20profile%20photos.read"
    f"&state={secrets.token_urlsafe(16)}"
    f"&code_challenge={code_challenge}&code_challenge_method=S256"
)

# ... user authenticates, consents, browser redirected back with ?code=XYZ&state=...

# Step 4: exchange the code — MUST include the ORIGINAL verifier
token_response = post_to_token_endpoint({
    "grant_type": "authorization_code",
    "code": "XYZ",
    "redirect_uri": "https://app.example.com/callback",
    "client_id": "abc123",
    "code_verifier": code_verifier,   # the RAW value, proving this client
                                      # is the same one that started the flow
})
```

**Why PKCE closes the specific attack it was designed for.** Without PKCE, an authorization code intercepted in transit (a malicious app on the same mobile device registering the same custom URL scheme and grabbing the redirect before the legitimate app does — a real, documented attack against public clients) can be exchanged for tokens by *anyone* who has it, since the code alone was sufficient. With PKCE, possessing the intercepted code is not enough — the attacker would also need the `code_verifier`, which was never transmitted anywhere except directly from the legitimate client to the authorization server in the final token-exchange request, so an intercepted code alone is useless to them.

**`state`, precisely.** A random value the client generates before the redirect, echoed back unchanged by the authorization server, and verified by the client on return. Its job is CSRF protection for the OAuth flow itself: without it, an attacker can initiate their own OAuth flow, get their own valid authorization code, and trick a victim's browser into completing the callback step with the attacker's code — binding the victim's session to the attacker's authorized account (a real, exploitable "login CSRF" if `state` is missing or not verified).

### Client Credentials grant — no user in the loop at all

```python
# Machine-to-machine: the CLIENT is also, in effect, the resource owner —
# there is no human consenting in a browser redirect, so none of the
# authorization-code machinery applies.
token_response = post_to_token_endpoint({
    "grant_type": "client_credentials",
    "client_id": "service-a",
    "client_secret": SERVICE_A_SECRET,   # confidential client only — never for public clients
    "scope": "inventory.read",
})
```

Used for service-to-service calls where there's no resource owner distinct from the client itself — a backend job calling another backend API under its own identity, not on behalf of any particular user. Requires a confidential client (something that can hold `SERVICE_A_SECRET` safely, i.e., never a browser or a mobile app).

### Device Authorization Grant — no browser on the device at all

Designed for input-constrained devices (a smart TV, a CLI tool) that can display a code but can't easily host a redirect-capable browser flow:

1. Device requests a `device_code` and a short `user_code` from the authorization server.
2. Device displays the `user_code` and a URL (e.g., "go to example.com/device and enter ABCD-1234").
3. User visits that URL on a *different* device (their phone), enters the code, authenticates, and consents.
4. Meanwhile, the original device polls the token endpoint with the `device_code` until the authorization server reports the user has completed the flow, at which point it returns the tokens.

This decouples "where the user authenticates" from "where the client needs the token," which is exactly the property a smart TV or a headless CLI tool needs and the redirect-based flows don't provide.

### The dead grants, and precisely why

| Grant | Why it existed | Why it's dead |
|---|---|---|
| **Implicit** | Browser-based JS apps (SPAs) couldn't hold a client secret, and the Authorization Code flow's token-exchange step assumed one; Implicit skipped that step and returned the access token directly in the redirect fragment | The access token appears in the browser's history, in `Referer` headers if not carefully stripped, and is readable by any JS on the page with no code-exchange indirection to protect it. PKCE fixed the underlying problem (public clients using Authorization Code safely) without any of Implicit's exposure, making Implicit strictly worse with no remaining advantage |
| **Resource Owner Password Credentials (ROPC)** | "Trusted" first-party native apps wanted a simple, redirect-free flow: just POST the username/password directly | Reintroduces the exact password anti-pattern OAuth exists to eliminate — the client sees the raw password — and structurally can't support MFA, passkeys, or federated login, since there's no redirect step for the authorization server to present any of those. Any client trusted enough to be a candidate for ROPC is trusted enough to implement Authorization Code + PKCE instead |

### OIDC: the identity layer on top

OpenID Connect (OIDC) adds exactly three things to plain OAuth 2.0: the `openid` scope (which signals "please also authenticate the user, not just authorize access to a resource"), the **ID token** (a JWT, returned alongside the access token, containing standard claims like `sub`, `iss`, `aud`, `iat`, `exp`, `auth_time`, and profile claims if scoped), and a UserInfo endpoint (an API the client can call with the access token to fetch additional profile data).

**The interview-famous confusion, stated precisely:**

| | ID Token | Access Token |
|---|---|---|
| Answers | "Who authenticated, and when" | "What can the bearer do" |
| Audience | The **client** — meant to be consumed by your application, never forwarded elsewhere | The **resource server** (the API) |
| Format | Always a JWT, always signed, standard OIDC claims | Often opaque or a JWT, format is an implementation detail between the authorization server and resource server |
| Correct use | Client reads `sub`/claims to know who's logged in, establishes a local session | Client attaches it as `Authorization: Bearer <token>` when calling the actual API |
| Common bug | Sending the ID token to an API as if it were an access token | Using the access token to determine "who is this" client-side instead of the ID token |

Sending the ID token to a resource server as a bearer credential is a real, recurring bug: the ID token was never issued *for* that resource server (its `aud` claim names the client application itself, not the API), so a correctly-implemented resource server checking `aud` should reject it — but a resource server that skips `aud` validation (module 4's missing-`aud` attack, restated in an OIDC-specific context) might accept it anyway, at which point you have identity information doing authorization's job with no actual permission scoping behind it.

### Scopes vs claims

**Scopes** are requested by the client and granted by the authorization server *before* any token exists — they describe what the client is asking permission to do (`photos.read`, `openid`, `profile`) and typically end up encoded into the access token as an authorization boundary the resource server checks. **Claims** are facts *about the subject*, delivered inside a token (typically the ID token, though access tokens can carry claims too) — `sub`, `email`, `given_name`. The distinction matters because scopes gate *what you asked to be allowed to do*, while claims describe *who you are* — a client can request the `profile` scope and, as a result, receive `given_name`/`family_name` claims in the ID token; the scope is the request/grant, the claims are the resulting data.

---

## Build it from scratch

A minimal, runnable Authorization Code + PKCE exchange, self-contained enough to run against a local mock authorization server:

```python
# untested sketch — full working version with a real authorization server in the lab
import hashlib, base64, secrets, urllib.parse

def generate_pkce_pair() -> tuple[str, str]:
    verifier = secrets.token_urlsafe(64)[:128]
    challenge = base64.urlsafe_b64encode(
        hashlib.sha256(verifier.encode()).digest()
    ).rstrip(b"=").decode()
    return verifier, challenge

def build_authorization_url(client_id: str, redirect_uri: str, scope: str,
                             code_challenge: str, state: str) -> str:
    params = {
        "response_type": "code", "client_id": client_id,
        "redirect_uri": redirect_uri, "scope": scope, "state": state,
        "code_challenge": code_challenge, "code_challenge_method": "S256",
    }
    return f"https://auth.example.com/authorize?{urllib.parse.urlencode(params)}"

def handle_callback(returned_state: str, expected_state: str) -> None:
    if not secrets.compare_digest(returned_state, expected_state):
        raise ValueError("state mismatch — possible CSRF, abort the flow")

def exchange_code_for_tokens(code: str, code_verifier: str, client_id: str,
                              redirect_uri: str) -> dict:
    # POST to the token endpoint — server recomputes SHA256(code_verifier)
    # and compares against the code_challenge stored with this auth code
    return post_to_token_endpoint({
        "grant_type": "authorization_code", "code": code,
        "redirect_uri": redirect_uri, "client_id": client_id,
        "code_verifier": code_verifier,
    })

# --- Full flow ---
verifier, challenge = generate_pkce_pair()
state = secrets.token_urlsafe(16)
auth_url = build_authorization_url("app-1", "https://app.example.com/cb",
                                     "openid profile photos.read", challenge, state)
# ... redirect user to auth_url, they authenticate/consent, browser returns with ?code=...&state=...
handle_callback(returned_state="...", expected_state=state)
tokens = exchange_code_for_tokens(code="...", code_verifier=verifier,
                                    client_id="app-1", redirect_uri="https://app.example.com/cb")
# tokens now contains access_token AND id_token (because scope included "openid")
```

Full lab with a working local authorization server, the Device Flow polling loop, and Client Credentials for service-to-service calls: **`labs/py/06-oauth-pkce-flow/`**.

---

## How it's done in production

**Identity providers** — Auth0, Okta, AWS Cognito, Keycloak (self-hosted) implement the full grant catalogue, PKCE enforcement, and OIDC discovery (`/.well-known/openid-configuration`, which advertises the authorization/token/JWKS endpoints and supported scopes/claims so clients don't need any of it hardcoded). Spring Security's OAuth2 client and Authorization Server modules, and libraries like `authlib` (Python), `oidc-client-ts` (JS), implement the client and server sides respectively with PKCE on by default in current versions.

**Consent and scope granularity** — production systems increasingly support incremental/dynamic consent (request a minimal scope initially, ask for more only when a feature that needs it is actually used) rather than front-loading every possible scope at initial login, both for UX (a shorter, less alarming consent screen) and for the principle of least privilege (a token that was never granted `email.send` scope can't be misused for that even if compromised).

**Token endpoint hardening** — rate limiting and monitoring on the token endpoint specifically, since it's the highest-value target in the whole flow (successful exchange yields live tokens); anomalous patterns (many authorization codes generated but never exchanged, or exchange attempts with mismatched `code_verifier`s) are a detectable signal of an active interception attempt in progress.

### Failure-mode table

| Symptom | Cause | Fix |
|---|---|---|
| A user is silently logged into the attacker's account after clicking a crafted link | Missing/unverified `state` — login CSRF | Always generate and verify `state`; reject the callback if it doesn't match |
| Public client (SPA/mobile) had its authorization code intercepted and tokens stolen | No PKCE — a bare Authorization Code flow on a public client | Add PKCE; it's mandatory for public clients per OAuth 2.1 and a strict improvement even where "optional" |
| Access token used as identity ("logged in as") without an OIDC flow at all | Team implemented plain OAuth 2.0 for what was actually an authentication need | Add the `openid` scope and use the ID token for identity; access tokens describe permissions, not identity |
| ID token accepted by a resource server as a bearer credential | Resource server skipped `aud` validation, or team confused the two token types | Reject any token whose `aud` isn't this specific resource server; educate the team on the ID-token/access-token split |
| Mobile app using ROPC breaks the moment the IdP adds MFA | ROPC has no redirect step for a second factor to be presented | Migrate to Authorization Code + PKCE, which supports MFA/passkeys/federated login naturally through the redirect |
| Client credentials leaked from a mobile app binary | Confidential-client grant (Client Credentials, or a plain secret-based Authorization Code exchange) implemented on a public client | Public clients must never hold a client secret; use PKCE-based flows designed for public clients instead |

---

## Tradeoffs & when NOT to use it

- **Don't use Client Credentials for anything with a human resource owner in the loop.** If there's a specific user whose data is being accessed, Client Credentials is the wrong grant regardless of how "trusted" the client is — it authenticates the client itself, not any particular user, and has no consent step.
- **Don't use the Device Flow for anything with a normal browser available.** Its UX (leave this screen, go to another device, type a code) is a deliberate accommodation for genuinely input-constrained devices; imposing it on a normal web or mobile client is worse UX for no security benefit.
- **Don't skip PKCE for confidential clients "because they can hold a secret and don't need it."** OAuth 2.1 makes PKCE mandatory for all clients, confidential or public, specifically because it's a strict additional layer of protection against authorization-code interception with no meaningful downside — treating it as optional for confidential clients is legacy thinking from OAuth 2.0 that current guidance has explicitly moved past.
- **Don't treat OIDC as required for every OAuth integration.** If your application only needs to access a resource on the user's behalf and never needs to know or care *who* the user specifically is beyond "some authorized user," plain OAuth without the `openid` scope is sufficient and simpler — OIDC's identity layer is overhead you don't need for pure delegation use cases.
- **Rolling your own OAuth authorization server is almost always the wrong choice** given the grant-type subtlety, PKCE verification correctness, and JWKS/rotation machinery involved — use a managed IdP or a mature open-source implementation (Keycloak, `ory/hydra`) rather than reimplementing RFC 6749/7636/OIDC Core from scratch, for the same reason module 4 argues against hand-rolled JWT libraries.

---

## Interview questions

### Q1 — Why does OAuth exist — what specific problem did it solve that wasn't solvable before?
**Testing:** whether the answer centers on delegation and the password anti-pattern, not just "it's how login works."
**Answer:** Before OAuth, a third-party app needing access to your data on another service required you to give it your actual password for that service, which meant permanent, unscoped, hard-to-revoke access. OAuth introduces a delegation model: the app never sees your password, receives a scoped and revocable token instead, and the resource owner explicitly consents to a specific, limited grant rather than handing over full account control.
**Follow-up trap:** *"Is OAuth an authentication protocol?"* — no, OAuth on its own is purely about authorization/delegation; it says nothing about verifying who the user is to the *client* application. That's exactly the gap OIDC fills, and conflating the two is the most common mistake in this space.

### Q2 — Walk through why PKCE is necessary even for a confidential client that can safely hold a secret.
**Testing:** whether PKCE is understood as protecting the *authorization code exchange step*, not as a client-secret substitute exclusively for public clients.
**Answer:** PKCE protects against authorization-code interception regardless of client type — if an attacker intercepts the code in transit (a compromised network, a malicious app registering the same redirect URI on a shared device) before it reaches the legitimate client, possessing the code alone is useless without the `code_verifier`, which never left the legitimate client until the final token-exchange request. A client secret protects the *client's identity* at the token endpoint; PKCE protects the *specific authorization code* from being redeemed by anyone but the party that initiated that specific flow — two different things, both worth having.
**Follow-up trap:** *"If PKCE already protects the code, why does a confidential client still need a client secret too?"* — the secret proves the token-exchange request is coming from the registered client application itself, independent of which specific user flow it's for; PKCE proves this exchange is for the same flow the code was issued for. They protect against different attackers (a malicious third-party client impersonator vs. an interceptor of one specific code), and OAuth 2.1 requires both where applicable, not one instead of the other.

### Q3 — What's the difference between an ID token and an access token, and what's the concrete bug that results from confusing them?
**Testing:** the single most commonly cited OAuth/OIDC interview trap.
**Answer:** The ID token answers "who authenticated" and is meant for the client application to consume locally (establish a session, display the user's name); the access token answers "what can the bearer do" and is meant to be sent to the resource server. The concrete bug: sending the ID token to an API as if it were an access token — a correctly-implemented resource server should reject it on `aud` mismatch (the ID token's `aud` names the client app, not the API), but a resource server that skips `aud` validation might accept it, granting access based on identity information that was never actually scoped as a permission grant.
**Follow-up trap:** *"Can an access token ever be a JWT with the same claims as an ID token?"* — yes, its format is an implementation detail and nothing stops it from being a JWT with similar-looking claims, which is exactly why relying on "it looks like an ID token" rather than the explicit `aud` claim (and the fact that it arrived via the access-token field of the response, not the id_token field) as your distinguishing signal is fragile; always validate the token's intended purpose explicitly, not by shape.

### Q4 — Explain why the Implicit grant is dead, precisely — not just "it's deprecated."
**Testing:** whether they know the specific exposure, not just the verdict.
**Answer:** Implicit returns the access token directly in the redirect URI's fragment, with no code-exchange step — meaning the token ends up in browser history, can leak via `Referer` headers to any subsequent page the browser navigates to if not carefully controlled, and is exposed to any JavaScript running on the page with no indirection protecting it. PKCE fixed the underlying reason Implicit existed (public clients using Authorization Code safely, without needing a client secret) with none of that exposure, so Implicit has no remaining use case it serves better than Authorization Code + PKCE.
**Follow-up trap:** *"If a legacy client still only supports Implicit, what would you tell the team?"* — migrate it to Authorization Code + PKCE as a priority security fix, not a nice-to-have modernization; the exposure isn't theoretical, it's a documented, exploitable gap in a live system, and OAuth 2.1's formal removal of the grant reflects that this isn't a stylistic preference.

### Q5 — Design the authentication/authorization strategy for a CLI tool that needs to call a cloud provider's API on behalf of a developer who doesn't have a browser readily available in their terminal session.
**Testing:** recognizing when Device Flow is the right tool.
**Answer:** Device Authorization Grant: the CLI requests a `device_code`/`user_code` pair, displays the `user_code` and a URL, the developer opens that URL on any device with a browser (their laptop's browser, their phone), authenticates and consents there, and the CLI polls the token endpoint until the flow completes. This decouples the constrained device (no convenient browser) from where the actual authentication UX happens.
**Follow-up trap:** *"What's the security risk specific to Device Flow, and how is it mitigated?"* — phishing: an attacker could show a victim a fake "enter this code" prompt for a code the attacker generated, tricking the victim into authorizing the attacker's device. Mitigations include short-lived, short-format codes (limiting the attack window), rate-limiting code generation, and user-facing warnings during the consent step naming what's being authorized.

### Q6 — A backend service needs to call another backend service's API with no specific end-user involved. Which grant, and why not Authorization Code?
**Testing:** recognizing when there's no resource owner distinct from the client.
**Answer:** Client Credentials — there's no human resource owner to redirect for consent; the calling service authenticates as itself using its own client ID and secret, and the resulting access token represents the *service's* permissions, not any particular user's. Authorization Code assumes a browser-based consent step from a specific resource owner, which doesn't exist in a pure service-to-service call.
**Follow-up trap:** *"What if the backend service is acting on behalf of a specific end-user, not just itself?"* — that's a different, harder problem (token exchange / delegation, sometimes handled via RFC 8693 OAuth 2.0 Token Exchange, or by the calling service holding and forwarding the user's own access token if scopes allow) — Client Credentials specifically represents the calling service's own identity and shouldn't be stretched to also represent a specific user's authorization.

### Q7 — Why is the Resource Owner Password Credentials grant fundamentally incompatible with MFA, even in principle?
**Testing:** understanding the structural (not just policy) reason ROPC is dead.
**Answer:** ROPC's entire flow is a single POST of username and password directly to the token endpoint with no redirect step — there's no point in that exchange where the authorization server can present a second factor (an OTP prompt, a push notification, a WebAuthn challenge) back to the user, because the user isn't interacting with the authorization server's own UI at all, only with the client's login form. Any second factor would have to be bolted on outside the standard flow entirely, defeating the purpose of a standardized grant.
**Follow-up trap:** *"Couldn't the client itself prompt for the second factor and include it in the request?"* — that just relocates the same fundamental problem: the client now needs to see and handle the raw second factor too, which reintroduces the same trust concentration ROPC has for passwords, and still doesn't support factors that require an out-of-band channel the client doesn't control (a push notification to a separate authenticator app, a hardware key challenge tied to the authorization server's own origin).

### Q8 — Your team's SPA fetches an access token, decodes it (it happens to be a JWT), and displays the user's name from a claim inside it. What's wrong with this even if it currently works?
**Testing:** whether they catch the ID-token/access-token conflation even when the access token happens to be JWT-shaped.
**Answer:** The access token's format and claims are an implementation detail of the authorization server/resource server relationship, not a contract with the client — relying on it containing user-identity claims couples the client to internal details that can change without notice (the resource server team could switch to opaque tokens, or stop including a display-name claim, with no warning to client-side code depending on it). The correct source for "who is this user" is the ID token, which is explicitly, contractually meant for the client and whose claims (`sub`, `name`, `email`) are part of the OIDC standard rather than an incidental implementation detail.
**Follow-up trap:** *"Is there ever a legitimate reason to decode the access token client-side?"* — rarely, and even when technically possible, it's fragile for the reason above; if the client needs identity information, request the `openid` scope and use the ID token, which is the artifact designed and guaranteed for that purpose.

### Q9 — OAuth 2.1 is still an IETF Internet Draft, not a ratified RFC, as of mid-2026. Does that mean its recommendations are optional to follow?
**Testing:** judgment about de facto versus de jure standards, a real nuance in this space.
**Answer:** Practically, no — every major identity provider (Auth0, Okta, Google, Microsoft) already enforces or strongly defaults to OAuth 2.1's core recommendations (mandatory PKCE, no Implicit/ROPC, refresh rotation), and security audits (SOC 2, ISO 27001) increasingly treat them as baseline expectations regardless of the draft's formal ratification status. Waiting for the RFC number before adopting these practices would mean deliberately shipping against a security posture the entire ecosystem has already moved past.
**Follow-up trap:** *"If a client library still defaults to allowing Implicit or ROPC, is that the library's fault or yours?"* — ultimately yours to catch in review; a library exposing a legacy option for backward compatibility doesn't mean it's safe to use it, and "the library allowed it" isn't a defense in a security review that should be checking your actual configuration, not just assuming defaults are safe.

### Q10 — Design a delegated-authorization scheme for an LLM agent that needs to book a flight on a user's behalf, using OAuth concepts. Where does the standard model break down?
**Testing:** staff-level transfer of OAuth's principles to a genuinely unsolved problem, connecting to the lineage section's speculative direction.
**Answer:** The natural mapping is Authorization Code-like consent (the user explicitly grants the agent a scoped, time-limited permission — "book one flight under $500, this session only") followed by the agent using something Client-Credentials-like to act with that scoped grant against the airline's API. Where it breaks down: OAuth's flows assume a human clicking "Allow" in a browser at a fixed point before any action happens, but an agent's plan is often decided at runtime across multiple steps, so "what exactly is being authorized" isn't fully known at consent time the way it is when a user clicks "allow this app to read my calendar." A single upfront grant either has to be very broad (defeating least-privilege) or the agent needs a way to request incremental, in-flight authorization for actions it discovers it needs mid-task — a pattern OAuth's redirect-based consent model isn't built for.
**Follow-up trap:** *"Is there a way to make this safe with today's OAuth primitives, without waiting for a new protocol?"* — a defensible interim answer: issue a narrowly-scoped, short-TTL token per task (not per session), require explicit human-in-the-loop re-confirmation for any action above a pre-defined risk threshold (a price ceiling, an irreversible booking), and log every tool call against the grant for audit — using existing OAuth token mechanics conservatively rather than inventing new protocol machinery, while being explicit that this is a workaround, not a purpose-built solution to the underlying gap.

---

## Red flags that fail you

- Calling OAuth an "authentication protocol" without qualification.
- Not knowing the specific difference between an ID token and an access token, or where each is meant to be sent.
- Recommending Implicit or ROPC for a new integration in 2026 without immediately flagging them as deprecated/removed.
- Treating PKCE as "only for public clients" rather than understanding it protects the code-exchange step regardless of client type.
- Not knowing what `state` protects against.
- Proposing Client Credentials for a flow that has a specific human resource owner.

---

## Cheat card

```
4 ROLES: resource owner (user) · client (app) · authorization server (issues tokens)
         · resource server (the API)

AUTH CODE + PKCE (the 2026 default for anything with a browser + user):
  code_verifier (random, client-only) -> code_challenge = SHA256(verifier), sent upfront
  auth code returned via redirect -> exchanged for tokens WITH the raw verifier
  PKCE defeats: authorization-code interception, EVEN for confidential clients (OAuth 2.1: mandatory for ALL)
  state: random value, echoed back, verified on callback -> defeats login CSRF

CLIENT CREDENTIALS: no resource owner, service-to-service, confidential clients only
DEVICE FLOW: input-constrained device displays user_code + URL; user completes auth
             elsewhere; device polls token endpoint until done

DEAD GRANTS:
  IMPLICIT   token in redirect fragment, no code-exchange indirection -> browser history/
             Referer/JS-readable exposure. Killed by PKCE making Auth Code safe for public clients too
  ROPC       client sees raw password directly -> password anti-pattern reborn, structurally
             incompatible with MFA/passkeys/federated login (no redirect step to present them)

OIDC = OAuth + openid scope + ID_TOKEN (JWT) + UserInfo endpoint
  ID TOKEN     -> "who authenticated" -> for the CLIENT, never forward to an API
  ACCESS TOKEN -> "what can bearer do" -> for the RESOURCE SERVER
  BUG: sending ID token to an API as bearer cred -> should fail aud check, often doesn't

SCOPES = requested/granted BEFORE token exists, describe permission boundary
CLAIMS = facts ABOUT the subject, delivered INSIDE a token (mostly ID token)

OAUTH 2.1 status (2026): still an IETF Internet Draft, NOT ratified RFC --
  but de facto universal: every major IdP already enforces it; audits (SOC2/ISO27001) expect it
```

## Sources

- [RFC 6749 — The OAuth 2.0 Authorization Framework](https://www.rfc-editor.org/rfc/rfc6749) — accessed 2026-07-26
- [RFC 7636 — Proof Key for Code Exchange (PKCE)](https://www.rfc-editor.org/rfc/rfc7636) — accessed 2026-07-26
- [RFC 8693 — OAuth 2.0 Token Exchange](https://www.rfc-editor.org/rfc/rfc8693) — accessed 2026-07-26
- [OpenID Connect Core 1.0 specification](https://openid.net/specs/openid-connect-core-1_0.html) — accessed 2026-07-26
- [OAuth 2.1 Explained: What Changed and Why It Matters](https://guptadeepak.com/ciam-compass/guides/oauth-2-1-explained/) — accessed 2026-07-26
- [PKCE Downgrade Attacks: Why OAuth 2.1 is No Longer Optional](https://medium.com/@instatunnel/pkce-downgrade-attacks-why-oauth-2-1-is-no-longer-optional-887731326f24) — accessed 2026-07-26

## Changelog
- 2026-07-26 — created
