# Production notes — AuthN/AuthZ middleware

## Why conflating 401 and 403 leaks user existence

401 means "I do not know who you are"; 403 means "I know exactly who you are, and the answer is no." Return 403 for an *unauthenticated* request and you are asserting the caller's identity was established — and telling an attacker the credential they tampered with was *accepted*. Return 401 for an *unauthorized* one and a legitimate, fully authenticated user goes hunting for credentials they already presented correctly. Worse: if `unknown token` and `missing token` produce different errors, timing or body differences let an attacker enumerate which accounts exist. Every authn failure — missing, malformed, unknown — must be indistinguishable from outside. The same logic applies at authz: deny for a non-existent resource and a non-permitted resource must look identical, or you leak your resource inventory.

## Real stacks

- **FastAPI** — `Depends(get_current_user)` resolves AuthN per-route and stashes the identity; AuthZ is a second dependency (`require_role("admin")`) that receives the first's output. Authn-before-authz is enforced by the dependency graph, and short-circuiting is the DI container refusing to resolve downstream deps.
- **Spring Security** — a `SecurityFilterChain`: `UsernamePasswordAuthenticationFilter`/`BearerTokenAuthenticationFilter` populate the `SecurityContext`, then `FilterSecurityInterceptor`/`AuthorizationFilter` and `@PreAuthorize` decide. One misordered filter and every endpoint 500s or — worse — fail-opens. Your `compose` is this chain; your wrong-order test is a regression test real teams have shipped without.

## RBAC / ABAC / ReBAC in one paragraph each

- **RBAC** — `subject.role ∈ allowed_roles`. Cheap to audit ("what can an Editor do?" is one query), explodes when permissions must vary per-object — you start minting `editor_of_doc_123` roles, and role count grows with content.
- **ABAC** — policies over attributes of subject, resource, environment: `allow if subject.dept == resource.dept and time.hour in business_hours`. Expressive, but the policy space is combinatorial, so exhaustive audit of "who can reach X" gets hard fast.
- **ReBAC** (Zanzibar) — a graph query: `allow if (user, viewer, doc) is reachable via typed edges` — user → member-of → team → editor-of → folder → contains → doc. This is the only model that scales to "share this specific doc with this specific person" semantics; OpenFGA/SpiceDB/Ory Keto ship it.

## What production adds over your lab

| Stage | Your lab | Production |
|---|---|---|
| AuthN | opaque token in a dict | JWT validation — signature (`RS256`/`EdDSA`), `exp`/`nbf`/`iat` clocks, `iss`/`aud` pinning, JWKS rotation; or server-side session lookup. Never `verify=none`; never trust `alg` from the header |
| AuthZ | static ACL dict | OPA (Rego sidecar/policy-as-code) or AWS Cedar — decoupled policy files, versioned, unit-testable, CI-checked; the app calls `POST /v1/data/authz/allow` and must choose fail-open vs fail-closed |
| Accounting | in-memory list | structured, append-only events to a SIEM (Splunk/Sentinel/ELK) with `user`, `resource`, `action`, `decision`, `trace_id`, timestamp; alerts on deny-rate spikes — a burst of 403s on one resource is an attack in progress, not noise |
| Transport | function calls | mTLS between services, OAuth2 client-credentials for machine identity, short-TTL tokens minted per task |

## The 3 questions an interviewer asks after you describe this

1. *"A valid token but 403 on every endpoint — where do you look?"* — AuthZ's subject: the IdP's user/role claims don't match the policy's expectations. AuthN is demonstrably fine; debug the mapping between identity and permissions, never the credential.
2. *"Policy engine is down — fail open or closed?"* — closed, for writes and anything touching PII; opening is a breach you invited. "It depends" plus a named risk either way is the senior answer.
3. *"Where do you audit — allow, deny, or both?"* — both, always. An allow that was wrong is the most expensive line in your SIEM.
