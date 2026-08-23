# Entra ID Deep: RBAC, Managed Identities, Conditional Access, Token Lifetimes

> **Track:** C-AZ Azure Atlas · **Time:** 3h · **Prereqs:** none · **Updated:** 2026-08-23
> **Module id:** `C-AZ-identity` · **Tags:** identity,security,critical

## The 30-second version

Azure splits identity into three systems people constantly conflate: **Entra ID** issues tokens and decides who you are, **Azure RBAC** decides which resources that token may touch on the ARM control plane, and **Conditional Access** sits between authentication and token issuance to enforce session policy. Managed identities remove stored credentials entirely: the compute platform fetches tokens from the Instance Metadata Service, but the tradeoff is that group and role membership claims are cached in tokens for up to ~24 hours, so permission changes propagate slowly unless you scope roles directly to the identity. Access tokens default to a random 60-90 minute lifetime, and since 2021 refresh/session lifetimes are not configurable at all; Microsoft's answer to revocation lag is Continuous Access Evaluation, which stretches CAE-aware tokens to up to 28 hours but revokes them near-real-time on critical events. The interview question underneath all of it: can you tell apart a control-plane denial from a data-plane one, and do you know where the caching layers are?

## Why this gets asked

Because identity failures in Azure are almost never "wrong password" failures. They are silent mismatches between planes: someone grants `Owner` on the subscription and the app still gets 401 from Key Vault, because Key Vault data-plane actions don't care about management-plane roles; or a role assignment was added five minutes ago and the managed identity's cached token doesn't carry the new group claim yet, so the fix "didn't work"; or Conditional Access blocks a daemon because the team assumed CA applies to service principals the way it applies to users. Interviewers who run Azure estates have personally lost hours to each of these. What they're probing is whether you understand *where* authorization decisions happen and *when* cached decisions expire, versus reciting "use managed identities, they're secure."

---

## Lineage: past → present → future

**What came before.** Azure AD grew out of Microsoft Online Services identity in the late 2000s as a multi-tenant directory for Office 365 sign-in, bolted onto Windows Server Active Directory's mental model: users, groups, Kerberos-style domain trust. Early Azure resource authorization wasn't even RBAC — until 2014-2015 subscriptions used co-administrator flags with essentially three privilege levels, and enterprise teams ran wild shared admin accounts because there was nothing finer-grained. Classic Azure AD App Model (ACS namespaces, shared keys) meant applications authenticated with account keys pasted into config files, which is how storage account keys ended up in source control for a decade. The pain that killed this model: no delegation boundary, no least privilege, and credential leakage as the dominant breach vector.

**Where it stands now.** The current stack is layered and mostly settled. Entra ID (renamed from Azure AD in late 2023) handles authentication and issues JWTs; Azure RBAC handles ARM control-plane authorization with ~700 built-in roles scoped at management-group/subscription/resource-group/resource level, plus deny assignments that trump allows; managed identities (system- and user-assigned) give workloads credential-free token acquisition; Conditional Access (Entra ID P1) enforces MFA/device/compliance/location policy at sign-in time, with P2 adding Identity Protection risk signals into those policies; workload identity federation lets CI systems and even other clouds exchange OIDC tokens for Entra tokens with zero stored secrets. The live disagreements: whether user-assigned or system-assigned identities should be the org default (Microsoft now recommends user-assigned for most services), and how much to trust token-lifetime shortening versus CAE — Microsoft itself abandoned configurable short-token strategies after finding they degraded reliability without reducing risk.

**Where it's heading.** Three directions with different confidence. High confidence: credential-free everywhere — federated identity credentials replacing client secrets, passkeys/FIDO2 replacing passwords for humans, and workload identity federation extending beyond CI into cross-cloud scenarios. Medium confidence: Continuous Access Evaluation becoming the default enforcement model across more services, making static token lifetimes increasingly irrelevant; today CAE covers Exchange, Teams, and SharePoint first-party workloads, so custom APIs still live in the 60-90 minute world. Speculative: ABAC-style condition-based RBAC (already shipping for Blob Storage with role assignment conditions) expanding across services, and agent identities — Entra Agent ID — giving AI agents their own governed lifecycle. Treat the last one as direction-of-travel, not deployed consensus.

---

## Mental model

Two separate gates, and a cache behind each:

```
 HUMAN USER                                WORKLOAD (Function/VM/Pod)
     │                                             │
     ▼                                             ▼
┌─────────────────────┐                  ┌──────────────────────────┐
│ ENTRA ID            │                  │ IMDS endpoint            │
│ (authentication)    │                  │ 169.254.169.254          │
│  - validates creds  │                  │  - hands out tokens      │
│  - CONDITIONAL      │                  │  - no user, no password  │
│    ACCESS gate here │                  │  - identity pre-wired    │
│  - issues JWT       │                  │    to the resource       │
└─────────┬───────────┘                  └────────────┬─────────────┘
          │ access token (claims incl. groups)        │ access token
          ▼                                           ▼
┌─────────────────────────────────────────────────────────────────┐
│ AZURE RBAC (authorization, control plane)                       │
│   deny assignment? → DENY                                       │
│   else any ALLOW at any scope (MG > sub > RG > resource)? → OK  │
└─────────┬───────────────────────────────────────────────────────┘
          │
          ▼
┌─────────────────────────────────────────────────────────────────┐
│ RESOURCE DATA PLANE (Key Vault, Storage, SQL...)                │
│   checks the TOKEN'S claims again — control-plane roles         │
│   don't automatically grant data-plane operations               │
└─────────────────────────────────────────────────────────────────┘
        caches: token ~1h · MI group/role claims ~24h · RBAC propagation ~min
```

The single sentence that unlocks most Azure identity debugging: **a token is a snapshot of your permissions taken at issuance time, and every layer between you and the data keeps its own copy of that snapshot for its own duration.**

---

## How it actually works

### Token issuance and lifetimes

An access token is a signed JWT whose claims encode identity, audience (`aud`), tenant (`tid`), scopes/roles, and group memberships at issuance time. Defaults:

| Token type | Lifetime | Configurable? |
|---|---|---|
| Access token (default) | Random 60-90 minutes, ~75 average | Yes, 10 min to 24 h max, Graph API only, no portal UI |
| ID token / SAML | 1 hour | Same mechanism |
| Refresh/session tokens | Not configurable since Jan 30, 2021 | No — use Conditional Access sign-in frequency |
| CAE-negotiated access token | Up to 28 hours | Revoked near-real-time on critical events |

The refresh/session retirement matters operationally: you cannot make sessions longer or shorter by touching token policies anymore. Sign-in frequency (default: rolling window of 90 days without prompt) and session controls live in Conditional Access instead, which requires P1 licensing.

**Continuous Access Evaluation** flips the model: instead of expiring tokens quickly, Entra pushes critical events (account disabled, password changed, token revoked, IP moved out of a trusted named location) to enlightened relying parties within ~15 minutes worst case, and IP-location enforcement is immediate. Both client and resource API must be CAE-capable; MSAL declares the `cp1` client capability. A revoked CAE token produces HTTP 401 with a `WWW-Authenticate` claims challenge the client must handle. Non-CAE apps keep the standard ~1-hour world.

### Managed identities, mechanically

Enabling a system-assigned identity makes Azure create a special service principal in Entra tied 1:1 to the resource lifecycle; delete the VM/Function and the principal goes with it (though it still counts against tenant quota until purged, ~30 days later). User-assigned identities are standalone resources you attach to one or more compute resources — Microsoft's recommended default because role assignments can be provisioned before the compute exists and survive blue/green replacement of the workload.

Token flow for code running on Azure compute:

```python
# untested sketch — what DefaultAzureCredential does under the hood on a VM
import urllib.request, json

def mi_token(resource: str, client_id: str | None = None) -> str:
    url = ("http://169.254.169.254/metadata/identity/oauth2/token"
           f"?api-version=2018-02-01&resource={resource}")
    headers = {"Metadata": "true"}
    if client_id:
        url += f"&client_id={client_id}"   # REQUIRED once >1 user-assigned exists
    req = urllib.request.Request(url, headers=headers)
    return json.load(urllib.request.urlopen(req))["access_token"]
```

Three operational facts that decide production incidents:

1. **IMDS throttling.** General IMDS requests are limited to ~5 requests/second; the managed-identity category allows ~20 req/s with 5 concurrent requests. A function app with hundreds of cold instances each minting tokens on startup hits 429s. Cache tokens in-process for their full lifetime; never fetch per-request.
2. **The 24-hour claim cache.** Azure's backend caches managed-identity tokens per-resource-URI for around 24 hours. If you add the identity to a security group that grants access, existing cached tokens still lack the new group claim — access changes can take several hours to take effect, and there is no force-refresh API. Granting roles directly to the identity (not via groups) avoids the group-claim path entirely and takes effect on the next token mint (~RBAC propagation, minutes to ~half an hour).
3. **No cross-tenant support.** Managed identities authenticate only within their own tenant. Multi-tenant SaaS needs either a multi-tenant app registration with admin consent, or workload identity federation.

### Azure RBAC evaluation

Evaluation order is short: **deny assignments always win**, then any allow anywhere in the inherited scope chain grants access. Unlike AWS IAM there is no SCP-equivalent ceiling inside a single tenant (guardrails come via Azure Policy and deployment stacks), and unlike AWS there *is* a native deny-assignment construct, though only certain roles can create them and they're mostly deployed by Defender/Policy automation.

Scope hierarchy: management group → subscription → resource group → resource. Assignments inherit downward. Practical ceilings worth knowing: ~4,000 role assignments per subscription (raised from 2,000), ~700 built-in roles, and role assignment changes propagate in minutes-to-tens-of-minutes. For storage specifically, **ABAC role assignment conditions** let one `Storage Blob Data Reader` assignment carry conditions like "only blobs under prefix `/tenants/42/`", which is how you keep the assignment count sane in multi-tenant estates.

The classic confusion: **control plane vs data plane**. `Owner` on a storage account does NOT let you read blobs — blob reads require a data-plane role (`Storage Blob Data Reader`) or a data-plane key/SAS. Key Vault is worse historically: access policies were a third parallel system; the modern answer is Key Vault RBAC roles on the data plane.

### Conditional Access

CA policies evaluate at token issuance: users, target resources (cloud apps), conditions (sign-in risk, device compliance, location/named locations, client app type), and controls (require MFA, require compliant device, block, sign-in frequency, app-enforced restrictions). Facts that get tested:

- Requires Entra ID **P1**; risk-based policies (sign-in risk, user risk) require **P2**.
- CA does not apply to service principals/workload identities — those are governed separately (Conditional Access for workloads covers sign-in frequency for workload identities, a narrower surface).
- Report-only mode evaluates without enforcing; the What If tool simulates a single sign-in against all policies.
- Primary Refresh Token on Entra-joined devices refreshes roughly every 4 hours, which interacts with sign-in-frequency policies.
- Break-glass: two cloud-only emergency accounts excluded from all CA policies, monitored for any use.

### Groups overage — the deep-cut failure

A user in more than ~200 groups gets a JWT whose group list exceeds size limits: the token emits `_claim_names`/`_claim_values` referencing a Graph endpoint instead of inline `groups` claims. Applications that read `groups` naively see the user as belonging to nothing and silently fail authorization. SAML has a similar threshold (~150). Fixes: assign apps directly, use app roles, or query Graph transitively at runtime. This is a favorite staff-level follow-up because everyone has hit "works for me, fails for that one admin" without connecting it to overage.

---

## Build it from scratch

A minimal evaluator showing the decision logic interviewers ask you to whiteboard:

```python
# untested sketch — Azure RBAC + token-cache semantics in ~40 lines
from dataclasses import dataclass, field
from time import monotonic

@dataclass
class Assignment:
    principal_id: str
    role: str                 # e.g. "Key Vault Secrets User"
    scope: str                # e.g. "/subscriptions/s1/resourceGroups/rg1"
    effect: str = "Allow"

@dataclass
class DenyAssignment(Assignment):
    effect: str = "Deny"

def scope_covers(assignment_scope: str, resource_id: str) -> bool:
    return resource_id.startswith(assignment_scope)

def evaluate(principal_id: str, action: str, resource_id: str,
             assignments: list[Assignment]) -> str:
    # 1. deny assignments win unconditionally (no exceptions, no ordering)
    if any(a.effect == "Deny" and a.principal_id == principal_id
           and scope_covers(a.scope, resource_id)
           and action_matches(a.role, action) for a in assignments):
        return "Deny"
    # 2. any allow in the inherited scope chain grants
    if any(a.effect == "Allow" and a.principal_id == principal_id
           and scope_covers(a.scope, resource_id)
           and action_matches(a.role, action) for a in assignments):
        return "Allow"
    return "Deny"   # default deny — silence is never consent

class TokenCache:
    """Models the two caches people forget: the token itself and the
    claims baked into it at mint time."""
    def __init__(self):
        self._tokens = {}   # (principal, resource) -> (token, minted_at, claims)

    def get_token(self, principal, resource, ttl_s=3600):
        hit = self._tokens.get((principal, resource))
        if hit and monotonic() - hit[2] < ttl_s:
            return hit[0], hit[1], True   # cached claims — NEW role grants invisible
        claims = fetch_claims_from_entra(principal)  # snapshot NOW
        self._tokens[(principal, resource)] = (claims, None, monotonic())
        return claims, None, False
```

The point of the exercise: the evaluator is trivially simple (deny wins, else allow-anywhere-in-chain); the difficulty in production lives entirely in the caches and the plane separation.

## How it's done in production

Standard estate pattern: human access via Entra ID groups synced from the IdP, assigned PIM-managed eligible roles (just-in-time activation with approval and MFA on activation, time-bound ~8 hours by default); workloads exclusively on user-assigned managed identities created in Terraform alongside their role assignments, one identity per workload-per-data-store rather than shared god-identities; Conditional Access baseline of require-MFA-all-users, block-legacy-auth, require-compliant-device for admins, plus named-location rules; break-glass accounts excluded and alarmed; client secrets replaced by federated identity credentials for anything with an OIDC issuer (GitHub Actions, GitLab, other clouds).

| Symptom | Cause | Fix |
|---|---|---|
| App gets 401/403 right after "we added the role" | RBAC propagation delay or stale MI token cache (~24 h) | Wait out propagation; restart instance to remint token; prefer direct role over group |
| `Multiple user assigned identities exist, please specify clientId` | Second user-assigned MI attached; IMDS can't disambiguate | Always pass an explicit `clientId` per credential, even with one identity |
| Intermittent 429 during scale-out bursts | IMDS token-mint rate limit (~20 req/s MI category) | Mint once per process, reuse for token lifetime |
| `Owner` on subscription still gets denied reading blobs | Control-plane role vs data-plane action mismatch | Assign data-plane role (e.g. `Storage Blob Data Reader`) |
| User in 250 groups fails authorization silently | JWT group overage → `_claim_names` indirection | Use app roles or Graph transitive lookup, not raw groups claim |
| Daemon blocked after CA rollout | Assumed CA exempts service principals | Scope CA policies to users; govern workloads separately |

## Tradeoffs & when NOT to use it

- **Don't use managed identities as a substitute for least privilege.** They remove credential theft risk, not over-granting risk; a managed identity holding `Contributor` at subscription scope is still a catastrophic blast radius.
- **Don't route workload permissions through Entra security groups** when fast revocation matters — the ~24-hour token claim cache makes group-based grants slow to both grant and revoke. Direct role assignments to the identity are slower to administer and faster to converge.
- **Don't shorten token lifetimes as your revocation strategy.** Microsoft tried it and backed off: configurable refresh/session lifetimes were retired in January 2021, and short-lived access tokens buy you at most ~an hour of exposure while multiplying auth traffic and fragility. CAE is the designed answer for custom-app revocation lag, but it requires both ends to implement the profile.
- **System-assigned isn't always "safer."** Its auto-cleanup is genuinely good, but in Terraform-heavy fleets the recreate-cycle breaks role assignments silently (new principalId, empty grants). User-assigned decouples identity lifecycle from compute lifecycle at the cost of needing explicit cleanup discipline.
- **When you'd skip Entra-native patterns entirely:** workloads that must authenticate machines outside any Entra tenant (some OT/edge systems) still need mTLS or API keys; forcing Entra there creates availability coupling — your factory floor should not stop producing when a token endpoint is slow.

---

## Interview questions

### Q1 — Walk me through what happens mechanically when an Azure Function reads a secret from Key Vault using a managed identity.
**Testing:** whether the end-to-end token path is understood, including caching layers.
**Answer:** Code asks DefaultAzureCredential for a token targeting `https://vault.azure.net`; the SDK calls IMDS (169.254.169.254) with the Metadata header, IMDS returns an Entra-issued JWT bound to the identity's service principal; the SDK sends it to Key Vault, which validates signature/audience and then checks its data-plane RBAC role (e.g. Key Vault Secrets User) for that principal. Tokens are cached in-process for their lifetime; IMDS itself throttles mints to ~20 req/s, and backend caches identity tokens per resource URI for ~24 hours.
**Follow-up trap:** *"You rotate a secret's access policy — why might the app still fail for hours?"* — if the permission came via a group membership, the group claim is baked into already-cached tokens; the ~24h claim cache means old tokens lack the new claim. Restarting instances forces a remint; granting directly to the identity avoids the group-claim path next time.

### Q2 — System-assigned vs user-assigned managed identity: how do you choose?
**Testing:** lifecycle reasoning, not memorized pros/cons.
**Answer:** System-assigned ties 1:1 to the resource lifecycle: automatic cleanup, but role assignments die with the resource, which hurts in Terraform/blue-green flows (new VM = new principalId = empty grants) and causes Entra object-quota churn under rapid creation (deleted principals count until ~30-day purge). User-assigned is standalone: attach to many resources, pre-provision roles before compute exists, survive replacements — which is why Microsoft recommends it as the default for new services. Choose system-assigned when per-resource isolation and guaranteed non-persistence are requirements (compliance revoke-on-delete).
**Follow-up trap:** *"Isn't sharing one user-assigned identity across services a least-privilege violation?"* — yes if overdone; the discipline is one identity per workload-per-dependency set, so blast radius stays bounded while avoiding per-VM assignment explosion.

### Q3 — Why did Microsoft retire configurable refresh/session token lifetimes, and what replaced that capability?
**Testing:** currency and understanding of CAE's rationale.
**Answer:** Shortening tokens degraded UX and reliability without materially reducing risk — attackers stealing a token use it immediately, and legitimate users paid constant re-authentication tax. Since Jan 30, 2021 refresh/session lifetimes are fixed; session length is controlled by Conditional Access sign-in frequency, and revocation latency is addressed by Continuous Access Evaluation: critical events push to enlightened services within ~15 minutes, IP-location violations enforce instantly, and CAE-aware tokens stretch to up to 28 hours because revocation no longer depends on expiry.
**Follow-up trap:** *"So can I still make my custom API's access tokens shorter?"* — access-token lifetime remains configurable via Graph-only token lifetime policies (10 min to 24 h max), but it's per-client/resource policy friction, doesn't apply to managed identities, and Microsoft explicitly steers you away from it as a security strategy.

### Q4 — Your team's Terraform pipeline deploys a Function and a role assignment in one apply. It intermittently fails on fresh environments. Why?
**Testing:** propagation-delay awareness.
**Answer:** Two race-shaped causes: the identity's service principal may not have replicated in Entra before the role assignment references it, and even when both exist, RBAC grants take minutes to tens of minutes to become effective while the app starts fetching tokens immediately. Standard fixes: retry/backoff on first token acquisition, split identity creation from role assignment (or use user-assigned identities created ahead of compute), and treat first-run 401s as expected transient state rather than a bug.
**Follow-up trap:** *"How would you prove it's propagation and not misconfiguration?"* — reproduce deterministically by checking `az role assignment list --assignee <principalId>` immediately after apply, then polling until effective; compare against a manual grant that works after waiting. Time-correlation distinguishes delay from typo.

### Q5 — Explain control plane vs data plane authorization with a concrete Azure example that bites people.
**Testing:** the single most common senior-level confusion.
**Answer:** ARM control-plane actions (create a Key Vault, change network rules) authorize via Azure RBAC roles like Contributor/Owner; data-plane actions (get secret, read blob) authorize against the resource's own plane — Key Vault data roles, Storage Blob Data roles, or legacy access policies/SAS. An `Owner` on the subscription can create and configure everything yet read zero blobs. The reverse bite: `Storage Blob Data Contributor` on a container doesn't let you regenerate account keys — that's control-plane.
**Follow-up trap:** *"Which services blur the line worst?"* — Key Vault (legacy access policies were a third parallel system; migrate to KV-RBAC) and Cosmos DB (its keys bypass Entra entirely; disable local-auth to force RBAC).

### Q6 — What actually wins when policies conflict in Azure RBAC, and how does that differ from AWS?
**Testing:** cross-cloud precision, valuable for his polyglot profile.
**Answer:** Explicit deny assignments win absolutely — no exception, no evaluation-order nuance. Absent a deny, ANY allow anywhere in the inherited scope chain grants; there's no requirement that multiple layers agree. Versus AWS: Azure lacks an SCP-like org ceiling inside the tenant (guardrails live in Azure Policy, enforced at deploy/change time rather than request time), and Azure ships native deny assignments that ordinary admins rarely create, whereas AWS achieves deny via policy statements in every layer.
**Follow-up trap:** *"Who creates deny assignments in practice?"* — mostly Azure Policy's DeployIfNotExists/Modify effects and Defender for Cloud remediations; hand-authoring them is rare, so teams are often surprised to find them blocking an action with no visible allow-side explanation.

### Q7 — Design authentication for a multi-tenant SaaS where each customer's users sign in from their own IdP.
**Testing:** whether managed identities' limits are known and the right federation pattern chosen.
**Answer:** Human tenants: Entra B2B collaboration or multi-tenant app registration with per-tenant admin consent, validating issuer per tenant. Workloads: managed identities cannot cross tenants, so cross-tenant machine auth uses workload identity federation — the customer's tenant trusts your app's federated credential, or vice versa; CI uses OIDC federation (GitHub Actions exchanges its token via `loginWithOIDC`-style trust) with a hard cap of 20 federated credentials per identity/app. Never store client secrets for tenant-scoped daemons if federation is possible.
**Follow-up trap:** *"Why is the 20-FIC cap a real constraint?"* — large enterprises mapping one credential per environment/repo/branch exhaust it fast; the mitigation is fewer, broader credentials scoped by subject claims, accepting slightly wider trust than ideal, or splitting across multiple app registrations.

### Q8 — A user in 230 groups can't access your app; colleagues with 30 groups can. Diagnose.
**Testing:** the groups-overage deep cut.
**Answer:** The JWT's `groups` claim hit size limits: beyond ~200 groups (≈150 for SAML) Entra stops inlining groups and emits `_claim_names` pointing at a Graph URL. Apps reading `groups` naively see zero memberships and fail authorization silently. Fix in the app (decode `_claim_names`, call Graph `/users/{id}/transitiveMemberOf/$count`), or better, move authorization to app roles assigned directly, which always inline.
**Follow-up trap:** *"Why not just increase the token size?"* — it's not a tunable knob; header/body limits across proxies and the protocol make oversized tokens fragile. The supported paths are overage handling or redesigning the claim payload (app roles, groups-filtered-to-assigned-app).

### Q9 — What does Conditional Access require license-wise, what does P2 add, and where does CA simply not reach?
**Testing:** practical scoping knowledge.
**Answer:** Any CA policy requires Entra ID P1; P2 adds Identity Protection risk signals (sign-in risk, user risk) usable as conditions or automated risk remediation, plus PIM for privileged-role JIT. CA doesn't apply to service principals/workload identities (separate, narrower workload CA surface), doesn't gate raw SAS-key or account-key usage on data planes (disable local auth to close that), and report-only/what-if coverage gaps show up for legacy-auth protocols — hence the standard block-legacy-auth policy.
**Follow-up trap:** *"Your CA 'block all except compliant devices' policy locked out break-glass. What went wrong?"* — exclusion design: break-glass accounts must be explicitly excluded AND monitored; if they weren't, the policy was correctly enforced but the emergency path was never tested. Runbook failure, not product failure.

### Q10 — How would you give a Kubernetes pod on AKS its own identity without storing secrets?
**Testing:** workload identity mechanics beyond Functions/VMs.
**Answer:** Entra Workload Identity: the cluster runs a mutating webhook injecting projected service-account tokens; a federated identity credential on the app registration/user-assigned MI trusts that cluster's OIDC issuer with subject = namespace:serviceaccount. Pod SDKs exchange the projected token for an Entra token — same FIC mechanism CI uses, no secrets anywhere. KEDA and most Azure SDK charts integrate natively.
**Follow-up trap:** *"What rotates the trust?"* — the cluster's public signing keys rotate automatically and the FIC references the issuer URL, not keys; the operational risk is issuer/subject typos, which fail with AADSTS70021-style errors at exchange time, not subtle drift.

### Q11 — When is a managed identity the wrong choice even though credentials-free sounds strictly better?
**Testing:** honest tradeoff articulation.
**Answer:** Three cases: (1) cross-tenant access — MIs don't leave their tenant, so partner integrations need federation or multi-tenant apps; (2) sub-minute revocation SLAs on group-derived permissions — the ~24h claim cache makes group-based grants/revoke lag unacceptable, so direct roles or app-level authz are needed; (3) non-Azure-hosted compute — IMDS is an Azure-platform feature; on-prem/other-cloud code needs workload identity federation configured manually or plain service principals. Also IMDS throttling means extreme-fan-out designs must batch/cache deliberately.
**Follow-up trap:** *"So how do you revoke a leaked managed identity fast?"* — remove its role assignments (effective within propagation minutes on next token mint for direct roles), disable the identity, and for defense-in-depth add a deny assignment — the group-cache problem only applies to claims fetched via groups.

### Q12 — Someone proposes "one big managed identity per environment" to simplify RBAC. Argue both sides briefly, then give your recommendation.
**Testing:** judgment synthesis, the actual staff-level deliverable.
**Answer:** For: drastically fewer role assignments (~4000/subscription ceiling becomes real in big estates), simpler onboarding, easier audits of a handful of principals. Against: any compromise or bug in one workload inherits everything every workload can touch; attribution dies (whose call was that?); least-privilege reviews become meaningless at that grain. Recommendation: middle path — identity per workload-tier per data-domain (e.g. ingest-write vs api-read), ABAC conditions on storage to collapse tenant-scoped assignments, PIM for any human-adjacent elevation, and Azure Policy denying subscription-scope grants to workload identities.
**Follow-up trap:** *"What metric tells you the consolidation went too far?"* — role-assignment breadth per identity (distinct actions granted) trending up over releases, plus incident forensics failing to attribute callers — both are early warnings before the first real incident.

---

## Red flags that fail you

- Still calling it "Azure AD" without knowing the Entra rename, or worse, mixing "Entra roles" (directory roles like Global Administrator) with "Azure RBAC roles" (resource-scope roles).
- Claiming managed identities eliminate the need for least-privilege RBAC.
- Not knowing CA applies at sign-in/token issuance and doesn't govern service principals.
- Proposing short token lifetimes as a modern revocation strategy (retired approach; CAE is the answer).
- Confusing control-plane and data-plane authorization when explaining a Key Vault or Storage denial.
- Saying "managed identity works across tenants" or "you can refresh an MI token's claims on demand."
- Having no answer for why permission changes sometimes take hours to affect workloads.

---

## Cheat card

```
THREE SYSTEMS:  Entra ID = who you are (issues JWTs)
                Azure RBAC = what tokens may touch (ARM control plane)
                Conditional Access = policy gate at token ISSUANCE (needs P1; P2 = risk-based)

TOKENS:  access token default 60-90 min (random, ~75 avg) · CTL range 10 min-24 h, Graph-only
         refresh/session NOT configurable since Jan 30 2021 -> use CA sign-in frequency (default 90d rolling)
         CAE: up to 28 h tokens, revoke in <=~15 min, instant for IP moves; needs cp1-capable client AND resource

MANAGED IDENTITIES:  system-assigned 1:1 lifecycle · user-assigned standalone (MS-recommended default)
         IMDS 169.254.169.254 · ~5 req/s general, ~20 req/s MI category + 5 concurrent
         backend caches MI tokens ~24 h per resource URI -> group/role CLAIMS frozen in token
         no cross-tenant · deleted system MI counts vs quota until ~30-day purge
         >1 user-assigned on resource => MUST specify clientId
         FIC (workload identity federation): max 20 per identity/app

AZURE RBAC:  DENY assignment beats everything -> else ANY allow in scope chain (MG>sub>RG>resource)
             ~700 built-in roles · ~4000 assignments/subscription · propagation minutes-~30 min
             control plane != data plane (Owner cannot read blobs; needs Storage Blob Data Reader)
             groups overage: >~200 groups -> _claim_names indirection in JWT (~150 SAML)

CA FACTS:  PRT refreshes ~every 4 h on Entra-joined devices · report-only mode + What If tool
           CA does NOT cover service principals · break-glass = 2 cloud-only accounts, excluded + alerted

DEBUG ORDER:  which principal? -> control or data plane? -> deny assignment? -> propagation/cache wait?
```

## Sources

- [Managed identities for Azure resources — overview, Microsoft Learn](https://learn.microsoft.com/en-us/entra/identity/managed-identities-azure-resources/overview); accessed 2026-08-23
- [Managed identities FAQ — Microsoft Learn](https://learn.microsoft.com/en-us/entra/identity/managed-identities-azure-resources/managed-identities-faq); accessed 2026-08-23
- [Managed identity best practice recommendations — Microsoft Learn](https://learn.microsoft.com/en-us/entra/identity/managed-identities-azure-resources/managed-identity-best-practice-recommendations); accessed 2026-08-23
- [Continuous access evaluation — Microsoft Learn](https://learn.microsoft.com/en-us/entra/identity/conditional-access/concept-continuous-access-evaluation); accessed 2026-08-23
- [Configurable token lifetimes — Microsoft identity platform](https://learn.microsoft.com/en-us/entra/identity-platform/configurable-token-lifetimes); accessed 2026-08-23
- [Conditional Access adaptive session lifetime — Microsoft Learn](https://learn.microsoft.com/en-us/entra/identity/conditional-access/concept-session-lifetime); accessed 2026-08-23

## Changelog

- 2026-08-23 — created
