# API Security: Rate Limiting, Enumeration, BOLA/IDOR, Mass Assignment, OWASP API Top 10

> **Track:** T30 Auth & Application Security · **Time:** 2.5h · **Prereqs:** `T30-authn-vs-authz`, `T30-web-attacks`
> **Updated:** 2026-07-26
> **Module id:** `T30-api-security` · **Tags:** appsec, critical
> **Lab:** none yet — see `labs/py/02-agent-loop/` for the pattern if you want to build one

## The 30-second version

APIs fail differently than traditional web apps because there's no browser sitting between the attacker and the endpoint enforcing anything — no same-origin policy, no CSP, no rendered UI hiding what parameters exist — so an API's entire security posture rests on server-side checks that traditional web apps could partially outsource to the browser. BOLA (Broken Object Level Authorization, #1 on OWASP's API Top 10 since 2019 and present in roughly 40% of real API attacks) is the single most common and most damaging API vulnerability: an endpoint that authenticates the caller correctly but never checks whether *this specific caller* owns *this specific object ID*, letting anyone iterate `/api/orders/{id}` and read every order in the system. Broken authentication, mass assignment (binding a client-supplied JSON body directly onto an internal model, letting an attacker set fields like `is_admin` that were never meant to be client-writable), missing rate limiting (enabling both brute force and enumeration attacks), and unrestricted resource consumption round out the recurring pattern: APIs expose a much larger, more mechanically enumerable attack surface per unit of functionality than a traditional rendered web page does, and every fix in this module is some version of "check authorization at the object level, validate the shape of what you bind, and bound how much any single caller can do."

## Why this gets asked

Because APIs are now the majority of what production traffic actually is — mobile apps, SPAs, partner integrations, and internal microservices all talk via APIs, not rendered HTML — and BOLA/IDOR specifically is the vulnerability class most likely to show up in a real pentest of anything you've shipped, precisely because it's the easiest to introduce (forget one authorization check on one endpoint) and the easiest to miss in testing (it works perfectly for the test user testing their own data, and only fails for a different, adversarial user ID nobody tried in QA).

---

## Lineage: past → present → future

**What came before.** Before APIs became the dominant traffic pattern, most web application security thinking was optimized for the server-rendered, browser-mediated model: a user requests a page, the server renders HTML with embedded data, and much of the attack surface (what parameters exist, what actions are possible) is implicitly constrained by what the rendered UI exposes — a user can't easily probe an endpoint they've never seen a link to. REST and, later, GraphQL APIs inverted this: the entire schema of available operations and parameters is often documented, discoverable, or directly inferable from client-side JavaScript bundles, meaning the "security by obscurity of unlinked functionality" that (never a real defense, but a common accidental mitigation) partially protected server-rendered apps simply doesn't apply to APIs at all. OWASP recognized this shift explicitly by publishing a dedicated **API Security Top 10** in 2019, separate from the general Top 10, specifically because the general list's ordering and framing (heavily influenced by traditional web app vulnerability prevalence) didn't reflect what was actually breaking in API-first architectures — BOLA topping that list from day one, at #1, was a direct acknowledgment that object-level authorization gaps were already the dominant real-world API vulnerability by the time the list was written.

**Where it stands now.** The OWASP API Security Top 10 was substantially revised in 2023, consolidating two 2019 categories (Excessive Data Exposure and Mass Assignment) into a single root-cause category — Broken Object *Property* Level Authorization — reflecting a broader industry shift (visible across the whole 2025 general Top 10 refresh too) toward grouping vulnerabilities by root cause rather than by symptom. BOLA remains #1 in the 2023 edition and remains, by a wide margin, the most common real-world finding — reported as present in roughly 40% of API attacks in industry data — precisely because it requires no sophisticated technique to exploit (incrementing an ID in a URL) and is the easiest authorization gap to introduce by simply forgetting one check on one endpoint, a failure mode module 1 covers architecturally and this module covers from the attacker's-eye view. The live disagreement in the field isn't about BOLA's severity (settled, and has been since 2019) but about *how* to systematically prevent it at scale across dozens or hundreds of endpoints — ad hoc per-handler checks don't scale reliably, which is exactly the argument for centralized policy engines and ReBAC models from module 1, applied here to the specific, recurring shape of "does this caller own this object."

**Where it's heading.** API security tooling is moving toward automated, schema-aware testing — tools that ingest an OpenAPI/GraphQL schema and automatically probe every parameterized endpoint for BOLA by testing with a second, non-owning test identity, rather than relying purely on manual pentest coverage, since manual testing at the scale of a large API surface (hundreds of endpoints) reliably misses individual gaps. GraphQL-specific tooling for query complexity analysis and depth limiting (defending against a GraphQL-specific flavor of unrestricted resource consumption, where a single query can recursively request deeply nested relations) is maturing alongside REST-focused tooling. More broadly, API security testing is increasingly being folded into CI/CD as a standard gate (contract testing plus authorization-negative-case testing run automatically on every PR) rather than treated as a separate, periodic pentest activity — a direction of travel consistent with "shift left" security practice generally, though the maturity of this automation varies significantly across organizations and it remains far from universal.

---

## Mental model

```
   TRADITIONAL WEB APP                          API

   ┌──────┐   renders HTML,                     ┌──────┐   returns raw JSON/data,
   │Server│   hides unlinked                     │Server│   schema often documented
   │      │   functionality behind               │      │   or inferable from client
   └──────┘   UI the browser shows                └──────┘   bundles/OpenAPI spec
      │                                              │
      ▼                                              ▼
   attacker mostly sees                          attacker sees (or can infer)
   what the UI exposed                           EVERY parameterized endpoint,
   -> smaller EXPLORABLE surface                 EVERY object ID pattern
                                                  -> the FULL surface is
                                                     mechanically enumerable

   THE #1 CONSEQUENCE: BOLA/IDOR

   GET /api/orders/12345          <- caller authenticated correctly (valid token)
                                     but WAS THE OBJECT-LEVEL CHECK EVEN RUN?

   if server only checks: "is this token valid?"           -> BOLA vulnerability
   if server checks: "is this token valid AND does token's  -> correctly authorized
      subject actually own order 12345?"

   THE ATTACK: just increment the ID.
   GET /api/orders/12346, /api/orders/12347, /api/orders/12348 ...
   No exploit sophistication required. Pure enumeration against a gap
   that has NOTHING to do with authentication strength — the token is
   perfectly valid, the CHECK THAT SHOULD FOLLOW IT was simply never written.
```

---

## How it actually works — the OWASP API Top 10 (2023), with mechanism and fix

### API1:2023 — Broken Object Level Authorization (BOLA/IDOR)

**Mechanism.** An endpoint accepts an object identifier from the caller (in the URL path, a query parameter, or the request body) and fetches/modifies that object without verifying the authenticated caller actually has a legitimate relationship to that specific object — this is exactly the module 1 authz gap (scope-level check present, object-level check absent) restated as the field's most-exploited API vulnerability.

**Exploit.**

```
GET /api/v1/orders/12345 HTTP/1.1
Authorization: Bearer <valid token for user_A>

-- Server logic (VULNERABLE):
--   order = db.get_order(order_id=12345)
--   return order              <- no check that order.owner_id == token.subject

-- Attacker, authenticated only as user_A, simply changes the path parameter:
GET /api/v1/orders/12346
GET /api/v1/orders/12347
-- ... every order in the system is readable by iterating IDs, regardless
-- of who actually owns each one.
```

**Fix.**

```python
# FIXED:
@app.get("/api/v1/orders/{order_id}")
def get_order(order_id: str, identity: Identity = Depends(verify_jwt)):
    order = db.get_order(order_id)
    if order is None or order.owner_id != identity.subject_id:
        raise HTTPException(404)   # 404, not 403 — avoid confirming the object EXISTS
    return order
```

Object-level authorization must run on **every** operation touching an identified object — reads, writes, and deletes alike — and the check belongs at the point the object is fetched, not inferred from route structure or trusted because the caller "must have gotten this ID from somewhere legitimate" (IDs are frequently sequential, guessable, or simply enumerable regardless of how they were originally issued).

### API2:2023 — Broken Authentication

**Mechanism.** Covered mechanically across modules 1-5 of this track; restated here in the API-specific frame: weak token generation, missing or bypassable MFA, credential stuffing with no rate limiting, and tokens with no expiry or absurdly long TTLs are the recurring authentication-layer gaps that specifically show up in APIs, often because API authentication is implemented ad hoc per-service rather than delegated to a hardened, shared identity provider.

**Exploit.** An API's password-reset endpoint accepts an email and a 4-digit reset code with no rate limiting — an attacker can brute-force all 10,000 possible codes for a targeted account in a short automated run, since nothing throttles repeated attempts against the same endpoint.

**Fix.** Delegate to a hardened, shared authentication implementation (module 6) rather than building bespoke per-API auth; rate-limit authentication-adjacent endpoints specifically (login, password reset, MFA verification) more aggressively than general API traffic, since these are the highest-value targets for automated attack.

### API3:2023 — Broken Object Property Level Authorization

**Mechanism.** This 2023 category merges two distinct 2019 issues that share a root cause — insufficient control over which *properties* of an object a given caller can read or write, as opposed to whether they can access the object at all:

- **Excessive data exposure** (the read side): an endpoint returns an entire internal object serialized wholesale (including internal fields like `password_hash`, `internal_notes`, `cost_basis`) relying on the client to simply not display fields it doesn't need, rather than the server withholding them.
- **Mass assignment** (the write side): an endpoint binds a client-supplied request body directly onto an internal model or ORM object without an explicit allowlist of which fields the client may set, so a field the client was never intended to control (`is_admin`, `account_balance`, `role`) can be set simply by including it in the request body, if the underlying framework auto-binds unknown-but-matching fields.

**Exploit — mass assignment:**

```python
# VULNERABLE: binds the ENTIRE request body onto the model, trusting
# that the client will only ever send the fields the UI form exposes
@app.patch("/api/users/{user_id}")
def update_user(user_id: str, body: dict):
    user = db.get_user(user_id)
    for key, value in body.items():
        setattr(user, key, value)   # client can set ANY attribute, including is_admin
    db.save(user)

# Attacker's request body:
# PATCH /api/users/42
# {"display_name": "New Name", "is_admin": true}
# -- is_admin was never meant to be client-settable, but nothing stopped it
```

**Fix — explicit allowlist for both directions:**

```python
ALLOWED_UPDATE_FIELDS = {"display_name", "bio", "avatar_url"}   # is_admin NOT in this set

@app.patch("/api/users/{user_id}")
def update_user(user_id: str, body: dict, identity: Identity = Depends(verify_jwt)):
    user = db.get_user(user_id)
    if user.owner_id != identity.subject_id:            # object-level check (API1)
        raise HTTPException(404)
    for key, value in body.items():
        if key not in ALLOWED_UPDATE_FIELDS:              # property-level check (API3)
            raise HTTPException(400, f"field '{key}' is not updatable")
        setattr(user, key, value)
    db.save(user)

ALLOWED_READ_FIELDS = {"id", "display_name", "bio", "avatar_url"}   # password_hash NOT in this set

def serialize_user(user) -> dict:
    return {field: getattr(user, field) for field in ALLOWED_READ_FIELDS}
```

Most modern web frameworks provide a schema/serializer layer (Pydantic models in FastAPI, Django REST Framework serializers, Rails' `strong_parameters`) specifically to enforce this allowlist mechanically rather than relying on developer discipline per-endpoint — using them by default, rather than passing raw dicts through, closes this category almost entirely for free.

### API4:2023 — Unrestricted Resource Consumption

**Mechanism.** An API operation that consumes non-trivial resources (CPU, memory, storage, or metered third-party services like SMS/email/biometric-verification APIs billed per call) with no cap on how many times, how large, or how frequently a single caller can invoke it — leading to denial of service or, for metered integrations, a direct and attacker-controllable increase in operational cost.

**Exploit.** An endpoint accepting a `page_size` query parameter with no upper bound (`GET /api/search?q=foo&page_size=5000000`) forces the server to construct an enormous response, consuming memory and CPU disproportionate to any legitimate use case; a GraphQL endpoint with no query-depth limit lets an attacker request deeply nested relations (`user { posts { comments { author { posts { comments { ... } } } } } }`) that fan out combinatorially against the database.

**Fix.** Enforce explicit maximums on every resource-affecting parameter (page size, upload size, query depth/complexity for GraphQL specifically), rate-limit per caller (not just globally), and set hard timeouts and resource quotas at the infrastructure layer as a backstop for whatever the application layer misses.

### API5:2023 — Broken Function Level Authorization

**Mechanism.** Distinct from BOLA (object-level): this is about whether a caller can invoke a *function/endpoint* at all, regardless of which object it targets — commonly, an admin-only endpoint that's reachable by any authenticated user because the authorization check was implemented as "is this route hidden from the regular UI" (a UI-layer, not server-layer, restriction) rather than an actual server-side role check.

**Exploit.** `POST /api/admin/users/{id}/promote` exists and functions identically for any valid authenticated token, because the only thing preventing a regular user from calling it was that the admin UI's frontend simply didn't render a button linking to it — the endpoint itself never checked the caller's role.

**Fix.** Every endpoint must independently verify the caller's authorization to invoke that specific function server-side — never infer restriction from "the UI doesn't expose a way to call this," since an API's entire surface is reachable directly, with or without a corresponding UI affordance.

### API6:2023 — Unrestricted Access to Sensitive Business Flows

**Mechanism.** A business-critical flow (purchasing a limited-inventory item, posting a comment, requesting a password reset) is exposed via an API with no protection against automated, excessive use — not necessarily an implementation bug, but a business-logic gap where the *functionality itself* being automatable at scale harms the business, even if every individual request is perfectly "valid."

**Exploit.** A ticket-purchasing API with no per-account or per-IP limit lets a bot buy the entire available inventory of a limited-release product within seconds of it going on sale, reselling at a markup — nothing about any individual purchase request is malformed or unauthorized, the harm is purely in the *volume and automation* of otherwise-legitimate-looking requests.

**Fix.** Rate limiting alone is often insufficient here since a sophisticated attacker distributes requests across many accounts/IPs; mitigations include CAPTCHA or proof-of-work challenges at points of known automation risk, device/behavioral fingerprinting to detect non-human request patterns, and business-logic-specific caps (e.g., "one ticket per verified account" enforced against a durable identity signal, not just a session).

### API7:2023 — Server Side Request Forgery

Covered mechanically in module 8; restated here as an API-specific instance: any API endpoint that fetches a resource based on a client-supplied URL (a webhook-URL validator, an "import from URL" feature) is a candidate SSRF vector using the exact same mechanism and mitigations (allowlisting, network isolation, IMDSv2) as module 8's general treatment.

### API8:2023 — Security Misconfiguration

**Mechanism.** A broad catch-all for configuration gaps that aren't specific to API logic but are especially consequential for APIs given their larger surface: verbose error messages leaking stack traces or internal implementation details, unnecessary HTTP methods left enabled on an endpoint, missing security headers, default credentials left unchanged, and overly permissive CORS (module 8) specifically in an API context.

**Fix.** Systematic configuration hardening (disable verbose errors in production, remove default credentials, enforce a minimal-methods policy per endpoint, apply the CORS allowlist discipline from module 8) as a standard deployment checklist rather than an ad hoc, per-team practice.

### API9:2023 — Improper Inventory Management

**Mechanism.** APIs tend to accumulate more endpoints, more versions, and more environments (staging, deprecated-but-still-live v1 endpoints, debug routes never removed) than traditional web apps, and a stale or undocumented endpoint is an unmonitored, unpatched, and often forgotten attack surface — the classic case being a deprecated API version that received a security fix in v2 but was never actually decommissioned in v1, leaving the vulnerable version silently reachable indefinitely.

**Fix.** Maintain an accurate, actively-verified inventory of every deployed API version and environment (not just a documentation page that may drift from reality), and treat deprecation as requiring actual decommissioning with monitoring to confirm zero remaining traffic, not just an announcement that a version is "deprecated" while it continues serving requests.

### API10:2023 — Unsafe Consumption of APIs

**Mechanism.** The inverse direction of trust: developers frequently apply less scrutiny to data received *from* a trusted third-party API than to data received from their own end users, on the assumption that a partner or vendor API is inherently safer — but a compromised or malicious upstream API (or a legitimate one with its own vulnerability) can inject the same classes of malicious data (injection payloads, oversized responses, unexpected schema) that direct user input would.

**Fix.** Apply the same input validation, size limits, and schema checking to data received from third-party APIs as you would to direct user input — trust in a partner relationship is not a substitute for validating what actually arrives over the wire.

---

## Build it from scratch

A minimal harness demonstrating BOLA detection — the single highest-value test to be able to write, since it catches the most common and most damaging API vulnerability class:

```python
# untested sketch — illustrates an automated BOLA test pattern for CI,
# not a full security scanner
import requests

def test_bola_on_endpoint(base_url: str, endpoint_template: str,
                            user_a_token: str, user_a_owned_id: str,
                            user_b_token: str) -> bool:
    """Returns True if a BOLA vulnerability is detected: user B's token
    can access an object owned by user A."""
    url = f"{base_url}{endpoint_template.format(id=user_a_owned_id)}"
    resp = requests.get(url, headers={"Authorization": f"Bearer {user_b_token}"})
    if resp.status_code == 200:
        # user B, who does NOT own this object, got a 200 — BOLA present
        return True
    return False

# Usage in a CI security-regression suite: for every parameterized
# endpoint discovered in the OpenAPI schema, provision two distinct
# test identities, create an object owned by identity A, and assert
# identity B is rejected (404/403) when accessing it by ID.
endpoints_to_check = [
    "/api/v1/orders/{id}",
    "/api/v1/invoices/{id}",
    "/api/v1/profile/{id}/documents",
]
for template in endpoints_to_check:
    vulnerable = test_bola_on_endpoint(
        base_url="https://staging.example.com",
        endpoint_template=template,
        user_a_token="...", user_a_owned_id="obj_owned_by_a_123",
        user_b_token="...",
    )
    assert not vulnerable, f"BOLA detected on {template}"
```

Full lab covering BOLA, mass assignment, broken function-level authorization, and a rate-limiting bypass scenario against a deliberately vulnerable sample API: **`labs/py/10-api-security-lab/`**.

---

## How it's done in production

**API gateways** — Kong, AWS API Gateway, Apigee centralize rate limiting, authentication delegation, and basic schema validation at the edge, but critically **cannot** enforce object-level authorization (API1/BOLA) themselves, since that requires business-logic knowledge of which specific object a specific caller legitimately owns — a gateway can validate "is this token structurally valid and within rate limits," never "does this token's subject own order 12345," which is exactly why BOLA remains the #1 vulnerability even in architectures with a mature API gateway layer in front of every service.

**Schema/serializer enforcement** — FastAPI's Pydantic models, Django REST Framework serializers, and similar frameworks in other languages mechanically enforce the API3 allowlist (both read and write) as a first-class part of the framework rather than a manually-applied practice, closing mass assignment and excessive data exposure by default for teams that use them as intended rather than passing raw request dicts through.

**Automated authorization testing** — mature API security programs run automated BOLA/BFLA regression tests in CI, provisioning multiple test identities specifically to assert cross-identity access is rejected, rather than relying purely on manual pentest cadence (often annual or per-major-release) to catch what a CI-integrated test would catch on every single PR.

### Failure-mode table

| Symptom | Cause | Fix |
|---|---|---|
| Any authenticated user can read any other user's private data by changing a URL's ID | BOLA — object-level ownership never checked | Check `object.owner_id == caller.subject_id` at every object-touching endpoint |
| A user updates their profile and their account becomes an admin account | Mass assignment — unchecked binding of request body onto an internal model | Explicit allowlist of client-writable fields (schema/serializer enforced, not ad hoc) |
| Admin-only functionality invocable by regular authenticated users | Broken function-level authorization — restriction only existed in the UI, not the server | Server-side role check on every function/endpoint, independent of UI affordances |
| A single account exhausts the entire limited-inventory stock via an automated script | Unrestricted access to a sensitive business flow, no automation-resistant controls | CAPTCHA/proof-of-work at high-automation-risk points; per-verified-account business caps |
| A `GraphQL` endpoint causes a database CPU spike from one query | Unrestricted resource consumption — no query depth/complexity limit | Enforce max query depth/complexity server-side, in addition to general rate limiting |
| A years-old, unpatched API v1 endpoint is still receiving live traffic | Improper inventory management — "deprecated" in docs, never actually decommissioned | Maintain a verified, monitored inventory; decommission means removing the route, not just announcing it |
| A partner API's malformed response causes an unhandled exception or unexpected behavior downstream | Unsafe consumption of a trusted third-party API with no independent validation | Validate and size-limit third-party API responses exactly as you would direct user input |

---

## Tradeoffs & when NOT to use it

- **Don't rely on an API gateway to close BOLA.** It's a real, valuable layer for rate limiting and authentication delegation, but object-level authorization requires business-logic knowledge the gateway structurally doesn't have — this must be implemented at the service/handler level, every time, for every object-touching operation.
- **Don't hand-roll field allowlisting per-endpoint if your framework provides a serializer/schema layer.** Manual, ad hoc `if key in [...]` checks scattered per-handler are exactly the kind of scattered logic module 1 warns against for authorization generally — use the framework's schema enforcement as the default, and treat any raw-dict-binding pattern as a specific, reviewed exception.
- **Rate limiting alone doesn't close API6 (unrestricted business flow access).** A sophisticated attacker distributes requests across many accounts and IPs specifically to stay under any single rate-limit threshold; business-logic-specific controls (CAPTCHA, per-verified-identity caps, behavioral analysis) are necessary for genuinely high-value flows, and treating rate limiting as sufficient here is a common, incomplete response.
- **Don't apply the same trust level to third-party API responses as to your own internal service calls**, even for well-established, reputable partners — API10 exists precisely because "it's a trusted vendor" is not a technical control, and a vendor's own compromise or bug becomes your problem the moment you consume their response without validation.
- **Improper inventory management (API9) is a process failure, not purely a technical one** — no amount of scanning tooling substitutes for an organizational discipline of actually decommissioning deprecated versions rather than just documenting them as deprecated while traffic continues.
- **For a very small, internal-only API with a single trusted caller** (a backend job calling its own sibling service under a shared deployment), the full weight of this module's controls (per-object authorization checks, strict schema allowlisting, business-flow rate limiting) may be genuine overkill — the risk calculus changes meaningfully when there's no untrusted external caller at all, though this exception shrinks fast the moment any external or less-trusted consumer gets added later, and "internal-only" access assumptions have a documented history of quietly becoming false over a system's lifetime.

---

## Interview questions

### Q1 — What is BOLA, why has it remained #1 on OWASP's API Top 10 since 2019, and how would you find it in a codebase you've just joined?
**Testing:** the single most important fact in this module, and whether the candidate can operationalize finding it.
**Answer:** BOLA is a missing object-level authorization check — an endpoint verifies the caller is authenticated but never checks whether the caller actually owns or has a legitimate relationship to the specific object identified in the request. It's remained #1 because it requires zero sophisticated technique to exploit (simply changing an ID in a URL) and is trivially easy to introduce by forgetting one check on one endpoint, while working perfectly in ordinary testing since the test user typically only ever tests against their own data. To find it: for every endpoint accepting an object identifier, write an automated test asserting that a *second*, non-owning authenticated identity is rejected — this is the systematic check that manual testing (which naturally uses one test account per tester) tends to miss.
**Follow-up trap:** *"Your API gateway already validates every token before requests reach your service. Doesn't that cover this?"* — no; the gateway validates that the token is structurally valid and within any configured rate limits, which is authentication and coarse authorization, but has no business-logic knowledge of which specific object a given subject legitimately owns — that check can only be implemented at the service layer, with access to the actual data model.

### Q2 — Explain mass assignment and why it's dangerous even in a codebase that never has an explicit SQL injection vulnerability.
**Testing:** whether the vulnerability is understood as an authorization gap, not an injection variant.
**Answer:** Mass assignment happens when an endpoint binds an entire client-supplied request body directly onto an internal model or ORM object with no allowlist restricting which fields the client may actually set — so if the underlying framework auto-binds any matching field name, a client can set attributes it was never meant to control (`is_admin`, `role`, `account_balance`) simply by including them in the JSON body, entirely independent of whether the query itself is parameterized correctly. It's an authorization gap at the property level (module 1's authz concept, applied per-field rather than per-object), not an injection vulnerability at all.
**Follow-up trap:** *"What's the fix that closes this almost for free in most modern frameworks?"* — use the framework's schema/serializer layer (Pydantic models, DRF serializers, Rails strong parameters) which mechanically enforces an explicit allowlist of writable fields as a first-class part of request handling, rather than manually binding raw dicts onto model objects — teams that pass raw request bodies through without this layer are the ones that reintroduce the vulnerability.

### Q3 — What's the difference between BOLA (API1) and Broken Function Level Authorization (API5)?
**Testing:** a commonly confused distinction within the OWASP API list itself.
**Answer:** BOLA is about *which object* a caller can access — the caller is allowed to call the endpoint in general, but shouldn't be allowed to access *this specific* object instance. Broken function-level authorization is about whether the caller can invoke the *function/endpoint at all*, independent of any object — commonly, an admin-only route that any authenticated user can successfully call because the restriction only ever existed in "the UI doesn't show a link to it," never as an actual server-side role check.
**Follow-up trap:** *"Could an endpoint have both vulnerabilities simultaneously?"* — yes, and this is common: an admin endpoint (`/api/admin/users/{id}/promote`) with no function-level check at all is trivially callable by any authenticated user (API5), and if it also doesn't verify the caller has any legitimate administrative relationship to the *specific* target user's account/organization (API1), a regular user could not only call an admin function but target it at an arbitrary other user — the two gaps compound rather than being mutually exclusive.

### Q4 — Design rate limiting for a public API and explain why rate limiting alone doesn't fully address API6 (unrestricted access to sensitive business flows).
**Testing:** whether rate limiting is understood as necessary but insufficient for certain classes of business-logic abuse.
**Answer:** Standard rate limiting (per-token or per-IP request caps over a sliding window) defends against straightforward automation from a single source, but a sophisticated attacker targeting a genuinely high-value business flow (limited-inventory purchasing, for instance) distributes requests across many accounts and IP addresses specifically to stay under any single-source threshold — each individual request looks legitimate and rate-compliant, but the aggregate volume and automation still harms the business. Rate limiting is a necessary baseline, not a sufficient defense for this specific category.
**Follow-up trap:** *"What would actually address the distributed-automation case?"* — controls tied to a durable identity signal that's harder to multiply than accounts or IPs — verified-account caps (one purchase per verified, KYC'd identity), device/behavioral fingerprinting to flag non-human interaction patterns, and friction mechanisms (CAPTCHA, proof-of-work) specifically at the points of highest automation risk, accepting that none of these are individually complete either, and layering multiple weak-but-different signals is the practical answer.

### Q5 — A colleague argues your API gateway's authentication and rate-limiting layer means individual services don't need their own authorization logic. Evaluate this claim.
**Testing:** the gateway/BOLA distinction restated as a direct challenge to a common architectural misconception.
**Answer:** The gateway can enforce that a request carries a valid, unexpired token and stays within a rate-limit budget, but it has no visibility into your data model — it cannot know that order 12345 belongs to user A and not user B, because that's a fact about your application's specific business data, not something a generic gateway can be configured to check without essentially reimplementing your authorization logic inside it. Object-level and function-level authorization (API1, API5) must be implemented in the service that actually has access to the ownership data, full stop — a gateway is a necessary complement, not a substitute.
**Follow-up trap:** *"Could you configure the gateway to call back into each service to check ownership before forwarding the request?"* — technically possible but architecturally awkward and slower (an extra round-trip per request, likely to the same service that would perform the check anyway), and it doesn't actually simplify anything — the ownership-check logic still has to live somewhere with access to the data, so you've added a hop without removing the requirement; the pragmatic answer is keep object-level checks in the service itself.

### Q6 — Explain excessive data exposure and why "the client just won't display the extra fields" is not a security control.
**Testing:** understanding client-side filtering as a UX decision, not an enforcement mechanism.
**Answer:** If an endpoint serializes and returns an entire internal object — including fields like `password_hash`, `internal_notes`, or `cost_basis` that the legitimate UI simply chooses not to render — that data is fully present in the HTTP response and trivially visible to anyone inspecting network traffic (browser dev tools, a proxy, `curl`) regardless of what the intended client application displays. The client's rendering choices are a UX layer with zero enforcement power; the server must actually withhold fields it doesn't intend any caller to see, via an explicit read-side allowlist (the same serializer/schema layer that fixes mass assignment on the write side).
**Follow-up trap:** *"Is this ever an acceptable tradeoff for development speed — return everything, filter client-side, for an internal admin tool built quickly?"* — even for internal tools, this is a bad default given how often "internal only" access assumptions quietly become false over a system's lifetime (a new integration, a support tool given broader access than intended, a data breach anywhere in the chain exposing the full response) — the marginal cost of an explicit read serializer is low relative to the risk of an unbounded, growing set of sensitive fields silently accumulating in a wholesale-serialized response over time.

### Q7 — What's the specific GraphQL-flavored version of unrestricted resource consumption (API4), and how do you defend against it?
**Testing:** whether resource-consumption risk is understood beyond simple "add a rate limiter" for the GraphQL case specifically.
**Answer:** A single GraphQL query can request deeply and recursively nested relations (`user { posts { comments { author { posts { ... } } } } }`), and because the query looks like one request from a rate-limiter's perspective, standard per-request rate limiting doesn't capture how disproportionately expensive that one request is to actually execute against the database — the fan-out can be combinatorial. Defense requires query complexity/depth analysis specific to GraphQL: assigning a cost to each field/relation and rejecting queries whose total estimated cost or nesting depth exceeds a configured maximum, independent of and in addition to standard rate limiting.
**Follow-up trap:** *"How would you set the complexity threshold without breaking legitimate deeply-nested queries some clients genuinely need?"* — profile actual legitimate query patterns in production traffic to establish a realistic ceiling, and consider a tiered approach (a lower default limit for public/unauthenticated access, a higher limit for authenticated or specifically-trusted internal clients) rather than one global threshold that has to satisfy every use case simultaneously.

### Q8 — Your company deprecated API v1 eighteen months ago in documentation, announced it to partners, and shipped v2 with a critical authorization fix. A pentest finds the v1 vulnerability still exploitable in production. What happened, and what's the fix going forward?
**Testing:** API9 (improper inventory management) understood as an organizational process gap, not purely a technical one.
**Answer:** "Deprecated in documentation" and "actually decommissioned" are different things, and the gap between them is exactly API9's failure mode — some partners or internal consumers likely never migrated off v1 (whether due to their own inertia or simply not noticing the deprecation notice), the route was never actually removed or gated, and v1 kept quietly serving live traffic with the known, unfixed vulnerability the whole time. Going forward: deprecation needs an enforced decommission date with monitoring confirming zero remaining traffic before removal (not just an announcement), and ideally a hard cutoff (returning an explicit "this version is retired" error) rather than allowing indefinite quiet continuation.
**Follow-up trap:** *"What if a major partner genuinely can't migrate off v1 by the deadline?"* — that's a business/relationship negotiation, not a reason to leave a known-vulnerable version silently live indefinitely; options include a time-boxed extension with compensating controls specifically for that partner (additional monitoring, a WAF rule targeting the known vulnerability as a stopgap) rather than treating "someone still needs it" as justification for open-ended risk acceptance with no mitigating action.

### Q9 — Design the authorization architecture for a multi-tenant SaaS API where each tenant's users should only ever see their own tenant's data, layered with per-user object ownership within that tenant.
**Testing:** synthesizing BOLA-style object-level checks with a broader tenant-isolation requirement, a realistic staff-level design question.
**Answer:** Two layers of object-level checks, not one: first, every query must be scoped to the caller's tenant ID (derived from the verified token, never from a client-supplied parameter, since a tenant ID supplied by the client is itself an object-identifier the caller could tamper with — a BOLA-adjacent risk at the tenant level) — ideally enforced structurally via row-level security at the database layer as a backstop, not just application-layer filtering that could be forgotten in one query path. Second, within the correctly tenant-scoped result set, the standard per-object ownership check (does this specific object belong to this specific caller within the tenant) still applies exactly as in the single-tenant case.
**Follow-up trap:** *"Why enforce tenant scoping at the database layer specifically, rather than trusting the application layer to always add a `WHERE tenant_id = ?` clause?"* — because relying purely on application-layer discipline means a single forgotten `WHERE` clause in one query, anywhere across a large codebase, is a full cross-tenant data leak, which is precisely the "one missed check across many endpoints" failure mode that makes BOLA the top vulnerability in the first place — database-layer row-level security (native in Postgres, or enforced via a tenant-scoped connection/session context) provides a structural backstop that doesn't depend on every single query author remembering the filter.

### Q10 — A junior engineer says "our API only accepts requests from our own official mobile app, so we don't need to worry about most of this OWASP API Top 10 list." Respond.
**Testing:** the "client identity" fallacy — whether the candidate recognizes that server-side controls can't assume anything about the actual calling client.
**Answer:** An API has no reliable way to verify that a request actually originated from the official mobile app rather than from a reverse-engineered client, a modified version of the app, or a direct `curl`/Postman request replaying captured traffic — any client-side identifier (an API key embedded in the app binary, a custom header, app-attestation signals) can be extracted, replicated, or spoofed by a sufficiently motivated attacker, and none of it changes what the server actually receives: an HTTP request indistinguishable, at the protocol level, from one sent by the legitimate app. Every control in this module's list applies regardless of the claimed or assumed client, because the server can only ever act on what actually arrives, never on assumptions about who's supposed to be sending it.
**Follow-up trap:** *"What about app attestation (e.g., Apple's App Attest, Android's Play Integrity API) — doesn't that solve this?"* — these raise the bar meaningfully (they cryptographically attest the request came from an unmodified, legitimate app installation on a genuine device) and are a real, valuable additional signal, but they're not infallible (attestation bypasses and rooted/jailbroken-device workarounds exist and evolve over time) and, more importantly, they attest *the client*, not *the specific request's authorization* — even a perfectly attested, unmodified official app can still send a request for an object the authenticated user doesn't own, so attestation is a complementary defense-in-depth signal, never a substitute for the object/function-level authorization checks this module covers.

---

## Red flags that fail you

- Not naming BOLA when asked "what's the most common API vulnerability."
- Believing an API gateway's authentication/rate-limiting layer closes object-level authorization gaps.
- Describing mass assignment as a SQL injection variant rather than an authorization/schema-binding issue.
- Confusing BOLA (object-level) with broken function-level authorization (endpoint-level) as though they're the same thing.
- Proposing rate limiting alone as sufficient defense against automated abuse of a sensitive business flow.
- Claiming "our API is only called by our own official client" as a reason to skip standard API security controls.

---

## Cheat card

```
OWASP API SECURITY TOP 10 (2023):
  API1  Broken Object Level Authorization (BOLA/IDOR) -- #1 since 2019, ~40% of API attacks
        caller authenticated OK, but object OWNERSHIP never checked -> increment an ID, read anything
        FIX: check object.owner_id == caller.subject_id at EVERY object-touching op. Gateway CANNOT do this.
  API2  Broken Authentication -- weak tokens, no MFA, no rate limit on auth endpoints (see mod 1-6)
  API3  Broken Object PROPERTY Level Authorization (merges 2019's Excessive Data Exposure + Mass Assignment)
        READ side: server returns whole object, trusts client to not DISPLAY sensitive fields (no enforcement)
        WRITE side: client body bound directly onto model -- sets is_admin/role client was never meant to touch
        FIX: explicit ALLOWLIST both directions -- use framework serializer (Pydantic/DRF/strong_params), not raw dict binding
  API4  Unrestricted Resource Consumption -- unbounded page_size, GraphQL query depth/complexity, no caps
        FIX: max params server-side, GraphQL query cost/depth limits, per-caller rate limits, infra-layer quotas as backstop
  API5  Broken Function Level Authorization -- admin endpoint reachable because ONLY the UI hid the button
        DISTINCT from API1: this is "can call the FUNCTION at all", not "can access THIS object"
        FIX: server-side role check on every endpoint, never inferred from UI affordances
  API6  Unrestricted Access to Sensitive Business Flows -- legit-looking requests, automated at harmful VOLUME
        rate limiting alone INSUFFICIENT (attacker distributes across accounts/IPs)
        FIX: CAPTCHA/proof-of-work at automation-risk points, per-VERIFIED-identity caps, behavioral signals
  API7  SSRF -- see module 8 (same mechanism/fix: allowlist destinations, IMDSv2, network isolation)
  API8  Security Misconfiguration -- verbose errors, default creds, permissive CORS, unneeded methods enabled
  API9  Improper Inventory Management -- deprecated-in-docs != decommissioned; stale v1 stays live+vulnerable
        FIX: verified inventory + enforced decommission dates + monitoring for zero remaining traffic
  API10 Unsafe Consumption of APIs -- trusting third-party API responses MORE than user input, no validation

KEY DISTINCTIONS:
  BOLA (API1) = which OBJECT      vs   Broken Function-Level Authz (API5) = which FUNCTION/endpoint at all
  API gateway enforces: token validity + rate limits.  CANNOT enforce: object ownership (needs business data)

MULTI-TENANT: tenant_id from VERIFIED TOKEN, never client param + DB-layer row-level security as
  structural backstop (application-layer WHERE clause alone = one forgotten filter = full cross-tenant leak)

"our API is only called by our official app" -> FALSE ASSUMPTION. Server can't verify caller identity
  from the wire alone; app attestation (App Attest/Play Integrity) helps but isn't infallible and
  doesn't substitute for object/function-level authorization regardless.
```

## Sources

- [2023 OWASP API Security Top 10](https://owasp.org/API-Security/editions/2023/en/0x00-header/) — accessed 2026-07-26
- [OWASP Top 10 API Security Risks – 2023](https://owasp.org/API-Security/editions/2023/en/0x11-t10/) — accessed 2026-07-26
- [API1:2023 Broken Object Level Authorization](https://owasp.org/API-Security/editions/2023/en/0xa1-broken-object-level-authorization/) — accessed 2026-07-26
- [OWASP API Security Top 10 2023 Explained — Salt Security](https://salt.security/blog/owasp-api-security-top-10-explained) — accessed 2026-07-26
- [What is the OWASP API Security Top 10? — Cloudflare](https://www.cloudflare.com/learning/security/api/owasp-api-security-top-10/) — accessed 2026-07-26

## Changelog
- 2026-07-26 — created
