# Authentication vs Authorization vs Accounting — and Why Conflating Them Breaks Systems

> **Track:** T30 Auth & Application Security · **Time:** 1.5h · **Prereqs:** none
> **Updated:** 2026-07-26
> **Module id:** `T30-authn-vs-authz` · **Tags:** fundamentals, critical
> **Lab:** `labs/py/01-authn-authz-middleware/`

## The 30-second version

Authentication (AuthN) answers "who are you" and produces an identity; authorization (AuthZ) answers "what can this identity do" and produces a decision; accounting (the third A, often dropped) answers "what did they actually do" and produces an audit trail you can reconstruct after the fact. They are three separate concerns with three separate failure modes — a stolen credential is an authentication failure, a privilege escalation is an authorization failure, an undetected breach that ran for eleven months is an accounting failure — and systems that conflate them end up checking "is this a valid token" and treating that as "is this action allowed," which is exactly the bug class behind most IDOR and BOLA incidents. The fix is architectural: authenticate once at the edge, produce a stable identity + claims, and authorize per-resource per-action at the point of access, with every decision logged regardless of outcome.

## Why this gets asked

Because the interviewer has debugged a production incident where "the auth was working" (authentication succeeded, the token was valid) and the actual bug was a missing authorization check on one specific endpoint — a classic BOLA/IDOR where `GET /api/orders/12345` never verified the caller owned order 12345. They want to hear you name authentication and authorization as genuinely separate systems with separate libraries, separate failure surfaces, and separate places they belong in an architecture, not as two words for "login." At senior level they're also probing whether you treat audit logging as a security control or as an afterthought bolted on for compliance.

---

## Lineage: past → present → future

**What came before.** Early multi-user systems (Unix, mainframe RACF/ACF2 in the 1970s) fused identity and permission into one artifact: your username was both who you were and, via group membership and file ownership bits, largely what you could do. Web applications inherited this shape — HTTP Basic Auth (RFC 2617, 1999) sends a username/password on every request and the server checks both "is this valid" and "is this allowed" in the same code path, often the same `if` statement. The pain this caused was structural: authorization logic got smeared across every handler as ad-hoc `if user.role == 'admin'` checks, with no central place to audit what a role actually permitted, no way to change a policy without a deploy, and — critically — no separation meant no way to reason about the two failure modes independently when an incident happened. Session-based web apps in the 2000s (PHP `$_SESSION`, Rails `current_user`) mostly preserved this fusion; `current_user.can_edit?(post)` still lived inline in the controller.

**Where it stands now.** The industry consensus is a hard separation of concerns, both organizationally and architecturally: authentication is delegated to an identity provider (Okta, Auth0, Keycloak, AWS Cognito, or an internal one built on OIDC) that does one job — verify identity and mint a token — while authorization is either handled in application code against an explicit model (RBAC, ABAC) or delegated to a dedicated policy engine (OPA/Rego, AWS Cedar, OpenFGA/Zanzibar-style ReBAC) that evaluates a decision against a policy independent of the request-handling code. The live disagreement is over *where* authorization should live: centralized policy-as-code (OPA sidecar, Cedar) gives one auditable source of truth but adds a network hop and a new failure mode (policy engine down = fail open or fail closed?), while in-app authorization is faster and has no extra infrastructure but scatters logic across services and is harder to audit consistently. Google's Zanzibar paper (2019) is the most influential recent artifact here: it demonstrated that relationship-based authorization (ReBAC) — "can user U view document D" answered by walking a graph of typed relationships — scales to trillions of ACL entries and millions of QPS with sub-10ms p95 latency, and OpenFGA, SpiceDB, and Ory Keto are the open-source implementations of that model now seeing real production adoption in 2026, not just publication.

**Where it's heading.** Fine-grained authorization as an external, queryable service (the Zanzibar/OpenFGA model) is displacing role-based checks scattered through code for any product with meaningfully complex sharing semantics — this is real and shipping, not speculative, because "can this user see this specific object" is a question RBAC alone cannot answer well. Passwordless authentication (passkeys/FIDO2/WebAuthn) is displacing passwords as the default authentication factor: FIDO Alliance's 2026 report puts active passkeys at roughly 5 billion worldwide, 75% of consumers having enabled one on at least one account, and ~48% of the top 100 websites supporting them — this is a live transition, not a prediction, though password-based fallback remains ubiquitous for years yet. The more speculative direction is authorization for agentic systems: when an LLM agent acts on a user's behalf across five tools, "who is the identity performing this action" and "what is this action allowed to touch" stop being simple questions, because the agent is not the user and not a service account either. Expect delegated, scoped, short-lived credentials minted per-task to become the norm here, but the patterns are not yet settled.

---

## Mental model

Think of an airport, because it cleanly maps all three concerns onto physical checkpoints most people have stood in:

```
 PASSPORT CONTROL           GATE / BOARDING PASS         FLIGHT MANIFEST
 "who are you?"             "what are you allowed        "what actually
                             to do, right now, here?"     happened?"
 ┌─────────────────┐        ┌─────────────────────┐      ┌──────────────────┐
 │  AUTHENTICATION  │  ───▶  │    AUTHORIZATION     │ ──▶  │    ACCOUNTING     │
 │                  │        │                      │      │                   │
 │ verify identity  │        │ check this identity  │      │ record every      │
 │ (passport +      │        │ against a specific    │      │ decision, allowed │
 │  biometric)      │        │ resource + action     │      │ or denied, with   │
 │ → issues a       │        │ (this seat, this      │      │ who/what/when     │
 │  boarding pass   │        │  flight, this cabin)   │      │                   │
 └─────────────────┘        └─────────────────────┘      └──────────────────┘
        │                            │                            │
        ▼                            ▼                            ▼
  ONE identity token           MANY decisions,               ONE audit trail,
  (JWT / session)              one per resource/action        queryable after
  reused across the            touched, re-evaluated          the fact even if
  whole visit                  every time, every gate          the decision was
                                                                "allow"
```

The passport is checked once and trusted for the rest of the trip — that is authentication's job, and it should not be re-derived at every gate. But having a valid passport says nothing about whether you can walk into the first-class cabin, sit in seat 14C that belongs to someone else, or board a flight you're not ticketed for — that is authorization's job, and it must be re-evaluated **per resource, per action**, not once at the door. And the manifest records who boarded which flight in which seat regardless of whether they were supposed to be there — that is accounting, and its value is precisely in the cases where authorization said "allow" incorrectly or "deny" and someone tried anyway.

---

## How it actually works

### Authentication: producing a stable, verifiable identity

Authentication mechanisms differ in what "prove who you are" means, but the output is always the same shape: a claim of identity the rest of the system can trust without re-verifying credentials on every request.

| Mechanism | What's verified | Where it belongs |
|---|---|---|
| Password + hash compare | Something you know | Never re-checked per-request; verified once at login, exchanged for a token |
| TOTP / SMS OTP (MFA factor 2) | Something you have (device) | Login-time step-up, or step-up before a sensitive action |
| WebAuthn / passkey (FIDO2) | Possession of a private key bound to a device, unlockable by biometric/PIN | Increasingly the primary factor; phishing-resistant because the credential is origin-bound |
| mTLS client certificate | Possession of a private key, chained to a trusted CA | Service-to-service and machine identity, not human login |
| Federated (OIDC ID token, SAML assertion) | An external IdP already verified the user | SSO, delegated to Okta/Auth0/Keycloak so you never store passwords |

The critical architectural rule: **authenticate once, at the edge**, and carry the result forward as a signed, tamper-evident token (session ID looked up server-side, or a signed JWT). Every downstream service trusts that token's signature/session validity rather than re-running credential checks. This is why a compromised authentication step (a stolen JWT signing key, a session-fixation bug) is catastrophic — it invalidates the "who are you" answer for every subsequent decision built on top of it.

### Authorization: a decision function, not a boolean flag

Authorization is a function `authorize(subject, action, resource, context) -> allow | deny`, and the interesting design question is where that function lives and what model it implements:

- **RBAC (role-based)** — `subject.role in {admin, editor}`. Cheap to reason about, breaks down when permissions need to vary per-object ("editor of *this* document, not all documents") — this is "role explosion," where you end up minting `editor_of_doc_123` roles to compensate.
- **ABAC (attribute-based)** — policy references attributes of subject, resource, and environment: `allow if subject.department == resource.department and time.hour in business_hours`. More expressive, harder to audit exhaustively because the policy space is combinatorial.
- **ReBAC (relationship-based, Zanzibar-style)** — authorization is a graph query: `allow if (user, viewer, document) is reachable via typed relationship edges`, including transitive ones (`user is member of team, team is editor of folder, folder contains document`). This is the model that scales to "share this doc with this specific person" semantics that RBAC cannot express cleanly.

**Where the check must live:** at the point of access, not at the point of routing. A common real bug: an API gateway checks "does this token have a valid `orders:read` scope" (that's authentication-adjacent scope checking) and the service handler assumes that's sufficient, never checking "does this specific order belong to this specific caller." The scope check answers "can this identity read orders in general"; the object-level check answers "can this identity read *this* order" — conflating the two is precisely the BOLA/IDOR failure mode (module 10 covers this in depth). The rule: **authenticate at the edge, authorize at the resource.**

```python
# Anti-pattern: authentication result treated as authorization
@app.get("/api/orders/{order_id}")
def get_order(order_id: str, token: str = Depends(verify_jwt)):
    # token is valid => request proceeds. No check that token's
    # subject owns order_id. This is a BOLA vulnerability.
    return db.get_order(order_id)

# Correct: authentication and authorization are two distinct steps
@app.get("/api/orders/{order_id}")
def get_order(order_id: str, identity: Identity = Depends(verify_jwt)):
    order = db.get_order(order_id)
    if not authz.can(identity, action="read", resource=order):
        audit_log.record(identity, "read", order_id, decision="deny")
        raise HTTPException(403)
    audit_log.record(identity, "read", order_id, decision="allow")
    return order
```

### Accounting: the third A that gets skipped

Accounting (also called auditing, or the "A" that RADIUS's AAA model names explicitly alongside Authentication and Authorization) is the record of what happened: who did what, to what, when, and whether it was allowed. Its value shows up almost entirely in hindsight — during incident response, in a compliance audit, or when a customer disputes "I never approved that transfer."

Three properties separate a real accounting system from `print` statements scattered through handlers:

1. **Both allows and denies are logged.** A stream of only denials tells you about attackers; a stream of only allows tells you about legitimate traffic but hides the attempts. You need both to reconstruct an incident — "was this the fifth denied attempt before the sixth succeeded" is only answerable if failures are recorded with the same rigor as successes.
2. **The log is tamper-evident and centralized**, not sitting in an ephemeral container's stdout that rotates out in 24 hours. Append-only storage (a WORM bucket, a dedicated audit service) with retention matching your compliance obligation (often 1-7 years for regulated industries) is the baseline.
2. **The log answers "who, what, when, from where, decision"** at minimum — `subject_id, action, resource_id, timestamp, source_ip, decision, policy_version` — enough to reconstruct the authorization decision after the fact, including *which version of the policy* made that call, because policies change over time and "was this allowed under the rules at the time" is a real forensic question.

**Named failure mode:** the 2013-2014 Target breach was detected by the company's own security monitoring tooling (FireEye) days before the public disclosure — alerts fired, but the accounting/alerting pipeline routed them to a team that didn't escalate in time. The symptom in a real incident is not "no logs exist," it's "logs existed, nobody could query them fast enough, or nobody was watching." Accounting without alerting is a diary nobody reads until it's too late; the failure shows up as a multi-week or multi-month gap between compromise and detection in the post-mortem timeline.

---

## Build it from scratch

A minimal illustration of keeping the three concerns as genuinely separate code paths — not three files that still call into each other's internals:

```python
from dataclasses import dataclass
from enum import Enum
import time

@dataclass
class Identity:
    subject_id: str
    claims: dict          # from the verified token; authn's output

class Decision(Enum):
    ALLOW = "allow"
    DENY = "deny"

class Authenticator:
    """Only job: turn a credential into an Identity. Never asks 'can they'."""
    def verify(self, token: str) -> Identity:
        payload = verify_jwt_signature(token)   # raises on invalid/expired
        return Identity(subject_id=payload["sub"], claims=payload)

class Authorizer:
    """Only job: given an Identity + action + resource, decide. Never issues tokens."""
    def __init__(self, policy_store):
        self.policy_store = policy_store

    def check(self, identity: Identity, action: str, resource) -> Decision:
        policy = self.policy_store.get(resource.type)
        if policy.evaluate(identity, action, resource):
            return Decision.ALLOW
        return Decision.DENY

class AuditLog:
    """Only job: record the decision. Never influences it."""
    def __init__(self, sink):
        self.sink = sink

    def record(self, identity: Identity, action: str, resource_id: str, decision: Decision):
        self.sink.append({
            "subject_id": identity.subject_id,
            "action": action,
            "resource_id": resource_id,
            "decision": decision.value,
            "ts": time.time(),
        })

# Composition — the request handler orchestrates all three but implements none:
def handle_request(token, action, resource, authn: Authenticator, authz: Authorizer, audit: AuditLog):
    identity = authn.verify(token)                       # AuthN
    decision = authz.check(identity, action, resource)    # AuthZ
    audit.record(identity, action, resource.id, decision) # Accounting
    if decision is Decision.DENY:
        raise PermissionError("denied")
    return resource
```

The point of this shape is testability and blast-radius containment: you can unit-test `Authorizer.check` with zero HTTP or JWT machinery, you can swap policy engines (hand-rolled → OPA → Cedar) without touching authentication code, and a bug in the audit sink cannot silently change an authorization decision because `AuditLog.record` has no return value the caller depends on. Full version with an OPA sidecar and a Postgres audit table: **`labs/py/01-authn-authz-middleware/`**.

---

## How it's done in production

**Authentication providers** — Okta, Auth0, AWS Cognito, Keycloak (self-hosted, open source) implement OIDC/SAML, MFA, and passkey enrollment so you never store a password hash yourself. What they add over rolling your own: breach-credential checking (rejecting passwords found in known dumps), adaptive/risk-based MFA (step up only when the login looks anomalous), and SOC 2 compliance you inherit rather than build.

**Authorization engines**:

| Tool | Model | Adds |
|---|---|---|
| **OPA (Open Policy Agent)** | Policy-as-code (Rego) | Decouples policy from app code; sidecar deployment gives ~1ms local decisions; policies are unit-testable and version-controlled |
| **AWS Cedar** | Policy language with formal verification | Used by AWS Verified Permissions; provable properties about policies (this policy can never grant X) |
| **OpenFGA / SpiceDB / Ory Keto** | Zanzibar-style ReBAC | Graph-based relationship queries; p95 single-digit milliseconds at scale (Zanzibar itself: <10ms p95, trillions of tuples, millions of QPS at Google) |

**Accounting/audit** — centralized logging (Splunk, Datadog, an internal SIEM) with alerting rules, not just storage. The operational gotcha: audit logs are themselves a target — an attacker who can write to or truncate the audit log can hide their own tracks, so the log's write path needs its own authorization model, ideally append-only with a separate write identity than the application's own service account.

### Failure-mode table

| Symptom | Cause | Fix |
|---|---|---|
| Endpoint returns another user's data despite a valid token | Authorization check missing or checks scope, not object ownership | Add object-level check at the resource, not just at the gateway |
| "It worked in the token debugger but the API rejects it" | Confusing authentication (token validity) with authorization (permission) in error messages | Return distinct 401 (authn failed) vs 403 (authz failed) so clients and on-call engineers can triage correctly |
| Incident took 6+ months to detect (median dwell time in breach reports) | Accounting exists but nobody alerts on anomalous patterns | Route audit events to a SIEM with alerting rules, not just a log bucket |
| Role explosion — hundreds of near-duplicate roles like `editor_of_project_42` | RBAC used for what is actually per-object sharing | Migrate to ReBAC (OpenFGA/SpiceDB) for object-level sharing semantics |
| Policy engine outage takes down the whole app | Centralized authz service is a single point of failure with no fail-closed/fail-open decision made explicitly | Decide and document fail-open vs fail-closed per resource sensitivity; cache last-known-good policy locally (OPA does this natively) |
| Audit log missing the "who approved this" for a since-reverted change | Only current state stored, not decision history | Store audit events as an immutable append log, not just current permission state |

---

## Tradeoffs & when NOT to use it

- **Don't stand up a separate policy engine (OPA/Cedar/OpenFGA) for a five-endpoint internal tool with two roles.** The network hop and operational surface (another service to deploy, monitor, and keep available) costs more than an `if user.is_admin` check saves you. Centralized policy earns its keep once you have more than a handful of resource types or need consistent policy across multiple services.
- **Don't treat RBAC as sufficient once sharing gets personal.** "Any editor can edit any document" is RBAC. "This specific person can edit this specific document because I shared it with them" is a relationship, and forcing it into roles produces role explosion — a real, observable symptom (hundreds of near-identical role names) rather than a theoretical concern.
- **Don't skip accounting because "we'll add logging later."** Retrofitting audit trails after an incident means you cannot answer "was this allowed under the policy that existed then" for anything that already happened — there is no log for the past.
- **Don't authorize based on client-supplied role claims without re-verification server-side**, e.g., trusting a `role: admin` field embedded in a JWT that the client itself could have influenced during a prior less-privileged flow, or trusting stale claims in a long-lived token after a permission was revoked (this is the token-revocation problem covered in module 5).
- **Fail-open is sometimes correct** — a payment authorization system should almost always fail closed (deny on policy-engine outage), but a read-only internal dashboard might reasonably fail open to avoid an outage cascading into "nobody can see anything, including the on-call engineer trying to diagnose it." The senior signal is making this choice explicitly per resource, not by accident of what the framework defaults to.

---

## Interview questions

### Q1 — What's the difference between authentication and authorization?
**Testing:** baseline vocabulary; almost everyone passes, the score is in precision.
**Answer:** Authentication verifies identity — "who are you" — and produces a trusted identity token. Authorization evaluates a specific action against a specific resource for that identity — "what can you do, here, now" — and produces an allow/deny decision. They fail independently: a stolen password is an authentication failure; a user editing another user's record because the check was missing is an authorization failure.
**Follow-up trap:** *"Is checking a JWT's scope claim authentication or authorization?"* — it's authorization, specifically a coarse-grained one (can this identity act on this resource *type* at all), and it is not sufficient on its own; it must be paired with an object-level check (can this identity act on *this specific* resource), or you have a BOLA vulnerability.

### Q2 — Where does the "accounting" A in AAA actually live in a typical web architecture, and why is it usually the weakest of the three?
**Testing:** whether audit logging is understood as a security control, not an afterthought.
**Answer:** It should live as a cross-cutting concern invoked from the same middleware that performs authorization, writing to a centralized, append-only, alertable store — not scattered `print`/`logger.info` calls per handler. It's weakest in practice because it has no immediate functional payoff (nothing breaks visibly if it's missing) until an incident, at which point its absence is catastrophic; the median breach dwell time in industry reports is measured in months, and that gap is almost always an accounting/alerting failure, not an authentication or authorization one.
**Follow-up trap:** *"Your audit log shows everything was 'allowed.' Does that mean there was no breach?"* — no; if authorization itself was mis-configured (over-permissive policy), every malicious action would show as a legitimate "allow." The audit log is only as trustworthy as the policy it's auditing against, which is why you also need policy version history in the log.

### Q3 — A candidate says "we use JWTs so we don't need a database for auth." What's wrong with that framing?
**Testing:** whether they conflate authentication statelessness with authorization statelessness.
**Answer:** A stateless JWT can carry authentication claims (who the subject is, when the token expires) without a database lookup, but authorization decisions frequently need current state — permissions can change between token issuance and use, resources can be reassigned, and object-level checks (does this order belong to this user) require a data lookup regardless of what's in the token. JWTs make authentication statelessness cheap; they don't make authorization free.
**Follow-up trap:** *"So should permissions ever be baked into the JWT itself?"* — coarse, slow-changing claims (role, tenant ID) are reasonable to embed since they're cheap to invalidate by short TTL; fine-grained, fast-changing permissions should not be, because embedding them means a permission revocation doesn't take effect until the token expires — this is exactly the revocation problem covered in the JWT security module.

### Q4 — Design the authorization model for a Google-Docs-style app where documents can be shared with individuals, teams, or made org-wide, with three permission levels (view/comment/edit). Would you use RBAC?
**Testing:** whether they recognize when RBAC is the wrong tool.
**Answer:** No — pure RBAC would require a role per document per user ("editor_of_doc_123"), which is role explosion. This is a textbook ReBAC (Zanzibar-style) problem: model `(user, relation, document)` tuples where relation can be direct ("user is editor of doc") or transitive ("user is member of team; team is editor of folder; folder contains doc"), and answer "can user X edit doc Y" as a graph reachability query. OpenFGA or SpiceDB implement this pattern with production latencies in the single-digit milliseconds.
**Follow-up trap:** *"What if you also need org-wide policy exceptions, like 'no external sharing outside business hours'?"* — that's an ABAC-shaped constraint (attribute of environment: time; attribute of resource: sharing scope) layered on top of the ReBAC relationship check. Real systems combine ReBAC for "is there a path granting access" with ABAC for contextual constraints — say this plainly rather than picking one model as globally sufficient.

### Q5 — Your service checks `if request.user.role == 'admin'` in twelve different handlers, copy-pasted with slight variations. What's the architectural problem, independent of any specific bug?
**Testing:** whether they see scattered authorization as a systemic risk, not just a code-smell.
**Answer:** There is no single place to audit what "admin" is allowed to do, no way to change the policy without redeploying every handler, and — critically — no guarantee the twelve copies stay in sync, so a typo or missed update in one creates an inconsistent, unauditable authorization surface. This is exactly the failure mode centralized policy engines (OPA, Cedar) exist to fix: one policy, evaluated consistently, testable independent of the twelve call sites.
**Follow-up trap:** *"Isn't a policy engine just moving the same logic somewhere else?"* — it's moving it somewhere *singular and versioned*. The value isn't that the logic disappears, it's that it exists exactly once, can be unit-tested without spinning up the app, and its history is a git log rather than twelve independent PRs across two years.

### Q6 — What's the difference between a 401 and a 403, and why does conflating them hurt incident response?
**Testing:** precise understanding of the authn/authz boundary as expressed in HTTP semantics.
**Answer:** 401 Unauthorized means authentication failed or is missing — the server doesn't know who you are, or doesn't trust the credential presented. 403 Forbidden means authentication succeeded but authorization denied the specific action. Conflating them (returning 403 for an expired token, or 401 for a valid-but-insufficient-permission user) means an on-call engineer triaging an incident from logs alone can't tell "our auth provider is down" from "someone's permissions changed and clients are erroring" — two very different response paths.
**Follow-up trap:** *"Does returning the correct code leak information to an attacker probing for valid resources?"* — yes, potentially: 404 vs 403 on a resource a user doesn't have access to can confirm the resource exists. This is a genuine tension between debuggability and information disclosure; the common resolution is 404 for resources the caller has no visibility into at all, and 403 only when the caller can at least confirm the resource's existence through other legitimate means.

### Q7 — Walk through what breaks if you authenticate at the API gateway but never re-check identity in the downstream service.
**Testing:** trust-boundary reasoning across service hops.
**Answer:** If the gateway strips the original credential and forwards a plain internal request (common for performance), any service reachable from inside the network — including one compromised via an unrelated vulnerability, or one an attacker reaches via SSRF — can call the downstream service with no identity check at all, because the downstream service was built assuming the gateway "already handled auth." The fix is propagating identity forward as a signed, verifiable assertion (an internal JWT, a mTLS client identity) that the downstream service verifies itself, not implicit trust in "requests from inside the network are pre-authenticated."
**Follow-up trap:** *"Isn't that redundant — the gateway already checked it?"* — no, because the trust boundary the gateway protects (external internet → your network) is different from the trust boundary downstream services need to protect (this specific service → that specific service, given lateral movement risk). Defense in depth here isn't redundancy, it's independent verification at each hop that has its own blast radius if bypassed.

### Q8 — Explain the role explosion failure mode and how you'd detect it's happening in a codebase you've just joined.
**Testing:** pattern recognition for a common but under-named anti-pattern.
**Answer:** Role explosion is when object-level sharing needs get bolted onto RBAC by minting a role per object — `editor_of_doc_1`, `editor_of_doc_2` — so the role table grows proportional to the resource count rather than staying a small, stable set of business functions. Detect it by querying the roles table: if the role count correlates with the object count (or grows unboundedly with usage) rather than staying flat, RBAC is being asked to do ReBAC's job.
**Follow-up trap:** *"Is there ever a legitimate reason to have thousands of roles?"* — very rarely, and usually it indicates the same underlying mismatch even when each role is individually "correct." A cleaner tell is whether roles are named after business functions (`billing_admin`) versus named after specific resource instances (`admin_of_workspace_88214`) — the latter is always the smell.

### Q9 — Design an authorization strategy for an LLM agent that can call five tools on a user's behalf, including one that sends emails and one that reads a database.
**Testing:** whether the candidate can transfer AAA to agentic systems, given their production background.
**Answer:** The agent is not the user — it needs its own scoped, short-lived identity, delegated from the user's session, that carries the *minimum* set of permissions needed for the current task rather than the user's full permission set (principle of least privilege applied to delegation). Each tool call is authorized independently at the point of execution, not once at agent-start, because a multi-step agent's later steps shouldn't inherit blanket trust from an earlier authorization decision made before the agent chose its plan. Accounting is non-negotiable here specifically because the "who did what" question is harder to answer post-hoc when an LLM, not a human, chose the action — you need to log the tool call, its parameters, the authorization decision, and ideally the reasoning trace that led to it.
**Follow-up trap:** *"What if the agent needs to escalate privileges mid-task, like sending an email only after finding a match in the database?"* — that's a step-up authorization pattern: the agent's initial delegated scope shouldn't include email-send by default; reaching that step should trigger a fresh, narrower authorization check (possibly requiring human-in-the-loop confirmation for irreversible actions like sending), not a single upfront grant covering the whole multi-tool plan.

### Q10 — You inherit a system where authorization checks are `if` statements inline in Django views with no test coverage for the negative case (denied access). How do you prioritize fixing this?
**Testing:** practical remediation judgment under real constraints, not idealism.
**Answer:** First, inventory which endpoints handle the highest-sensitivity resources (financial data, PII, admin functions) and add negative-case tests there first — "user B cannot read user A's resource" — since that's the highest-value, lowest-effort fix and it's exactly the class of bug (BOLA/IDOR) most likely to be actively exploited. Centralizing into a policy engine is a larger, valuable refactor but shouldn't block the immediate test-coverage gap, which can be closed in days rather than the weeks a full authorization-engine migration takes.
**Follow-up trap:** *"Your fix passed all tests but a pentest still found an IDOR three weeks later. What did you miss?"* — likely an endpoint not in the original inventory (a newer feature, an internal admin tool, a webhook handler) — this is why the inventory step itself needs to be systematic (grep for every route/resource pattern) rather than based on memory of "the important endpoints," and why a centralized policy engine's real advantage is that new endpoints inherit enforcement by construction rather than by developer discipline.

---

## Red flags that fail you

- Using "authentication" and "authorization" interchangeably, or answering an authorization question with an authentication mechanism (e.g., "we use OAuth" as the answer to "how do you authorize actions").
- Treating a valid token as sufficient proof that an action should be allowed, with no mention of an object-level check.
- Not knowing the difference between 401 and 403.
- Describing audit logging as "nice to have" or purely a compliance checkbox rather than a security control with its own failure modes.
- Proposing RBAC for a problem that is actually per-object sharing, without recognizing role explosion as the resulting symptom.
- Assuming authentication only needs to happen once globally, with no mention of step-up authentication for sensitive actions.

---

## Cheat card

```
AAA:  Authentication (who) -> Authorization (what, on what) -> Accounting (what happened)
RULE: authenticate ONCE at the edge; authorize AT THE RESOURCE, every action
401 = authn failed/missing   ·   403 = authn OK, authz denied
BOLA/IDOR root cause: authz check missing at object level, only checked at scope/route level

MODELS:
  RBAC  - role -> permission set. Cheap. Breaks down at per-object sharing (role explosion)
  ABAC  - policy over attributes of subject/resource/env. Expressive, hard to audit exhaustively
  ReBAC - graph of typed relationships (Zanzibar). Answers "share this ONE doc with this ONE person"
          Zanzibar: <10ms p95, trillions of tuples, millions QPS at Google scale
          OSS: OpenFGA, SpiceDB, Ory Keto. Prod FGA queries: 1-10ms

POLICY ENGINES: OPA (Rego, ~1ms local sidecar decisions) · AWS Cedar (formally verifiable) · OpenFGA/SpiceDB (ReBAC)
IDENTITY PROVIDERS: Okta, Auth0, Cognito, Keycloak (self-hosted) - do authn, MFA, passkeys, SSO

ACCOUNTING: log BOTH allow and deny; append-only; store policy VERSION with each decision
  failure mode: logs exist, nobody alerts -> median breach dwell time = months, not days

FAIL-OPEN vs FAIL-CLOSED: decide explicitly per resource sensitivity when the policy engine is down
PASSKEYS 2026: ~5B active, 75% of consumers enabled one, ~48% of top-100 sites support them
```

## Sources

- [Zanzibar: Google's Consistent, Global Authorization System (research.google)](https://research.google/pubs/zanzibar-googles-consistent-global-authorization-system/) — accessed 2026-07-26
- [Fine-Grained Authorization (FGA): A 2026 Implementation Guide](https://guptadeepak.com/ciam-compass/guides/fine-grained-authorization-fga/) — accessed 2026-07-26
- [What is FGA? Fine-Grained Authorization Explained — OpenFGA docs](https://openfga.dev/docs/fga) — accessed 2026-07-26
- [Five Billion Passkeys: FIDO Alliance Reports Mainstream Global Usage on World Passkey Day 2026](https://fidoalliance.org/fido-alliance-reports-accelerating-global-passkey-adoption-on-world-passkey-day-2026/) — accessed 2026-07-26
- [OWASP API Security Top 10 2023 — Broken Object Level Authorization](https://owasp.org/API-Security/editions/2023/en/0xa1-broken-object-level-authorization/) — accessed 2026-07-26
- [OWASP Top 10:2025 — A01 Broken Access Control](https://owasp.org/Top10/2025/A01_2025-Broken_Access_Control/) — accessed 2026-07-26

## Changelog
- 2026-07-26 — created
