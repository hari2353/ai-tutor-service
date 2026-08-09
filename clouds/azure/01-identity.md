# Entra ID, RBAC, Managed Identities, Conditional Access

> **Track:** C-AZ Azure Atlas · **Time:** 2.5h · **Prereqs:** none · **Updated:** 2026-08-08
> **Module id:** `C-AZ-identity` · **Tags:** security,critical

## The 30-second version

Azure splits identity into two separate systems that AWS bundles into one: **Microsoft Entra ID** (the directory — users, groups, service principals, the OAuth2/OIDC token issuer) and **Azure RBAC** (who can do what to which resource, evaluated against Azure Resource Manager). RBAC decouples permissions (role definitions) from resources (scope) and connects them with a role assignment — "give this principal this role at this scope" — and scope inherits top-down through management group → subscription → resource group → resource, unlike AWS where a policy document bundles actions and resources together and there's no automatic hierarchy inheritance. Managed identities are Azure's answer to IAM roles for compute: system-assigned (1:1 with a resource, dies with it) or user-assigned (independent lifecycle, attachable to up to 20 resources... actually up to 1000 resources, 20 per single resource), and either way the workload calls the local Instance Metadata Service instead of ever handling a static key. Conditional Access is the policy engine that decides, per sign-in, whether to allow, block, or demand more (MFA, compliant device, terms of use) based on real-time signals — it requires Entra ID P1 for the baseline and P2 for risk-based signals and PIM. The single biggest trap for an AWS engineer: Azure RBAC (who can act) and Azure Policy (what configurations are allowed to exist) are two separate systems that people conflate with AWS's single IAM+SCP mental model — RBAC has no equivalent to a resource-based policy, and there's no analog of AWS's "explicit deny beats everything," because standard Azure RBAC assignments are additive-only (deny assignments exist but are a narrow, separate mechanism, not something you write yourself in the common case).

## Why this gets asked

The interviewer has watched a subscription accumulate role assignments until it silently hit the hard 4,000-per-subscription ceiling and a deployment pipeline started failing with an opaque error, has debugged a managed identity that worked in one region and mysteriously didn't in another because of IMDS token caching, and has had to explain to a security team why "Contributor at the subscription" is not the same guarantee as "least privilege" because Contributor can still create role assignments-adjacent resources and, critically, cannot itself grant RBAC access — the confusion there costs real incident time. They want to know you can reason about Azure's actual permission model instead of pattern-matching "it's basically IAM."

---

## Lineage: past → present → future

**What came before.** Azure launched with Azure Active Directory (2010) as essentially an extension of on-prem Active Directory into the cloud, built for federating corporate identities into Microsoft 365 — it was fundamentally a directory service first, an authorization system second. Early Azure resource access control was coarse: co-administrator roles on the classic (ASM) deployment model gave all-or-nothing access to a subscription, with no scoped, resource-level permission model. This mirrored the same pain AWS's IAM launch solved in 2010 — shared, overprivileged credentials with no way to scope access to a subset of resources.

**Where it stands now.** Azure RBAC (2014, alongside Azure Resource Manager) is the current, universally-deployed answer, and in **2023 Microsoft renamed Azure Active Directory to Microsoft Entra ID** — not a cosmetic rename but a signal that the product now spans an identity *portfolio* (Entra ID, Entra Permissions Management, Entra Verified ID, Entra Workload ID) rather than being just "the directory behind Azure." The live disagreement in 2026 is over how aggressively to license-gate security-critical Conditional Access features: baseline Conditional Access requires **Entra ID P1** (~$6-7/user/month as of mid-2026, after a July 2026 price increase of roughly 16%), while risk-based Conditional Access, Privileged Identity Management (PIM), and Identity Protection sit behind **P2** (~$9-10/user/month) — meaning a startup running "free tier" Entra ID has none of the sign-in risk controls a comparable AWS account gets for free via IAM Access Analyzer and GuardDuty's identity findings. [Microsoft Entra ID Pricing 2026](https://idsync.com/guides/microsoft-entra-pricing) — accessed 2026-08-08. Continuous Access Evaluation (CAE), which revokes a token within minutes of a critical signal (user disabled, password changed, location risk) instead of waiting for natural token expiry (60-90 min), is now broadly deployed and considered a baseline expectation for enterprise tenants rather than an advanced feature.

**Where it's heading.** Microsoft's stated direction is consolidating premium identity capability into an **Entra Suite** bundle (P2 + Permissions Management + Internet Access + Private Access) as the default recommendation for zero-trust-postured enterprises, high confidence given the pricing and marketing push through 2026. Passwordless and passkey/FIDO2 adoption is accelerating as the default sign-in method pushed by Conditional Access "authentication strength" policies, with password-based sign-in increasingly treated as the legacy path requiring extra scrutiny. More speculatively: expect continued convergence of Conditional Access and Azure RBAC's condition-based (ABAC-style) role assignments into a single "contextual access" story, though these remain two genuinely separate systems today and conflating them in an interview answer is a real mistake.

---

## Mental model

```
ENTRA ID (the directory — who exists, how they authenticate)
  Users, Groups, Service Principals, Managed Identities, App Registrations
  Issues OAuth2/OIDC tokens after Conditional Access evaluates the sign-in
                    │
                    ▼
CONDITIONAL ACCESS (per sign-in gate, evaluated at token issuance)
  IF user=X AND app=Y AND device=unmanaged AND risk=medium
  THEN require MFA + compliant device, else block
                    │
                    ▼ (token issued)
AZURE RBAC (what the now-authenticated principal can DO to resources)
  Role Assignment = Security Principal + Role Definition + Scope
                    │
       Scope inherits top-down:
       Management Group
          └── Subscription
                └── Resource Group
                      └── Resource
       A role granted at "Subscription" is inherited by every RG and
       resource beneath it — there is no equivalent AWS mechanic;
       AWS policies don't auto-inherit down a resource hierarchy.

AZURE POLICY (separate system — governs resource CONFIGURATION, not access)
  "No VM may exist without disk encryption" — evaluates properties,
  doesn't care who made the change, only whether the resulting state
  is compliant. This is Azure's rough analog to AWS Config Rules,
  NOT to SCPs — the SCP-equivalent ceiling-on-permissions concept
  barely exists in Azure the way AWS builds it.
```

---

## How it actually works

### RBAC: role definitions, assignments, and scope inheritance

A **role definition** is a JSON document listing allowed (`Actions`), denied (`NotActions`), and data-plane (`DataActions`/`NotDataActions`) operations — Azure's rough equivalent of an IAM policy document, except it describes *only* permissions, never a principal or a resource. A **role assignment** is the tuple that actually grants something: `(security principal, role definition, scope)`. This decoupling is the single biggest structural difference from AWS: in AWS, a policy document mixes actions and resource ARNs together and gets attached to an identity; in Azure, the same role definition (say, "Storage Blob Data Reader") can be assigned at wildly different scopes for different teams without ever touching the role definition itself.

Scope forms a strict hierarchy: **management group → subscription → resource group → resource**. A role assigned at a higher scope is inherited by everything beneath it automatically — assign "Reader" at the management group and every subscription, resource group, and resource under it inherits Reader with zero additional configuration. AWS has no direct equivalent; the closest AWS gets is an SCP's org-unit inheritance, but SCPs are a ceiling (deny-by-default outside explicit allows), not a grant — Azure's scope inheritance is an actual **grant** that cascades down.

```
# Role assignment concept (Azure CLI)
az role assignment create \
  --assignee <principal-id> \
  --role "Storage Blob Data Contributor" \
  --scope /subscriptions/<sub-id>/resourceGroups/<rg>/providers/Microsoft.Storage/storageAccounts/<acct>
```

### Built-in roles that come up constantly

| Role | What it actually grants | Trap |
|---|---|---|
| **Owner** | Full access including granting access to others | Only role that can create/modify role assignments by default |
| **Contributor** | Full access to manage resources, **cannot** grant access to others | Common mistake: assuming Contributor is "almost Owner" — it structurally cannot touch RBAC |
| **Reader** | View-only, no ability to modify anything | |
| **User Access Administrator** | Manage role assignments specifically, no resource management rights | Split from Owner intentionally — lets a security team grant access without also being able to modify the resources |

The Owner/Contributor split (Contributor cannot self-escalate by granting itself more access) is a deliberate design choice with no clean AWS parallel — AWS's `iam:PassRole` privilege-escalation problem doesn't have a direct Azure equivalent precisely because Contributor structurally lacks any RBAC-write action.

### Azure RBAC vs Azure Policy — the distinction that gets conflated

**RBAC answers "who can act."** **Azure Policy answers "what configurations are allowed to exist,"** independent of who made the change. A policy like "deny creation of any storage account without HTTPS-only enabled" fires regardless of which principal (however over-privileged) attempts it — this is Azure's rough analog to AWS Config Rules combined with parts of Service Control Policies, but it is evaluated at the resource-configuration layer, not the identity-permission layer. **The critical interview point**: Azure has no clean, single equivalent to an AWS SCP's blanket "no identity in this OU can ever call this API regardless of its own policy" — RBAC has no ceiling concept at all (it's purely additive: a principal's effective permissions are the union of every role assigned at every scope above it), and Azure Policy governs resource state, not API-call permission. The nearest thing to an SCP-style hard ceiling in Azure is a **deny assignment**, but those are created automatically by Azure Blueprints/Landing Zones or Azure Lighthouse delegation, not something teams routinely author by hand the way AWS teams author SCPs.

### Managed identities — mechanics and limits

**System-assigned**: created as a 1:1 property of a single resource (a VM, an App Service, a Function App), Azure creates and manages its lifecycle automatically, and it's deleted the instant the resource is deleted. **User-assigned**: an independent Azure resource in its own right, created once and attached to as many compute resources as needed, with its own lifecycle decoupled from any single VM.

Real numbers that matter operationally: a user-assigned identity can be attached to **up to 1,000 Azure resources**, but a single VM or App Service can have **up to 20 user-assigned identities** attached at once. Creation is rate-limited: **400 create operations per 20 seconds per Entra tenant per region**, and **80 create operations per 20 seconds per subscription per region** — a Terraform apply that fans out and creates hundreds of user-assigned identities in a tight loop across a single subscription/region can hit this and start failing with throttling errors that look nothing like a quota problem at first glance. [Managed identities FAQ — Microsoft Learn](https://learn.microsoft.com/en-us/entra/identity/managed-identities-azure-resources/managed-identities-faq) — accessed 2026-08-08.

Mechanically, a workload never sees a credential: code calls the local **Instance Metadata Service (IMDS)** endpoint (`http://169.254.169.254/metadata/identity/oauth2/token`), which returns a short-lived Entra ID access token scoped to whatever resource the code requests (e.g., `https://storage.azure.com/`). This is Azure's version of the EC2 instance-metadata-service pattern AWS pioneered — same non-routable link-local address, same "credentials never touch disk" property, and the same historical caveat that IMDS itself, if reachable from an SSRF vulnerability in the application, becomes a token-theft vector (Azure's IMDS requires the `Metadata: true` header specifically to make trivial SSRF-via-redirect harder, a mitigation AWS later matched with IMDSv2's token requirement).

### Conditional Access — the real-time policy engine

Conditional Access evaluates **at token issuance**, not at resource-access time — it's a sign-in gate, not an authorization system, and this distinction trips people who conflate it with RBAC. A policy is built from **assignments** (who: users/groups; what: cloud apps or actions; conditions: device platform, location, sign-in risk, user risk) and **access controls** (grant: require MFA, require compliant device, require approved client app, block entirely; session: limit session lifetime, require app-enforced restrictions, use Conditional Access App Control for real-time session monitoring). A typical enterprise policy: "if a user in the Finance group signs into a cloud app from outside a trusted named location, require MFA and a compliant (Intune-managed) device; if the sign-in risk is high, block outright."

Licensing gates what you can actually build: **baseline Conditional Access requires Entra ID P1**; **risk-based conditions (sign-in risk, user risk) and PIM require P2**. A tenant on the free tier has zero Conditional Access — this is a meaningfully different security posture from AWS, where MFA enforcement and basic identity risk signals (via IAM/GuardDuty) don't require a paid identity tier. [Entra ID Pricing 2026 — P1 vs P2](https://idsync.com/guides/microsoft-entra-pricing) — accessed 2026-08-08.

**Continuous Access Evaluation (CAE)** closes the gap between "the policy said block" and "the token is actually revoked" — instead of waiting for a token to naturally expire (60-90 minutes for access tokens by default), CAE-enabled services (Exchange Online, SharePoint, Teams, and increasingly custom apps via the CAE API) get near-real-time revocation, typically within minutes, when a critical event fires (user disabled, password reset, high sign-in risk detected, network location change for Conditional Access location-based policies). [Continuous Access Evaluation — 2026 update](https://contentwave.net/article/microsoft-entra-id-premium-p1p2-2026-update-zerotrust) — accessed 2026-08-08.

### PIM — just-in-time privilege

Privileged Identity Management (P2-gated) converts standing role assignments into **eligible** assignments: a user is eligible for "Global Administrator" but doesn't hold it by default. To use the role, they **activate** it — typically requiring MFA re-authentication, a business justification, and optionally manager approval — for a bounded duration (commonly 1-8 hours), after which the assignment automatically expires back to eligible-only. This is Azure's equivalent of AWS's temporary STS credentials via `AssumeRole`, but applied to the *administrative role* layer rather than to workload credentials — the AWS analog for a human admin would be requiring `AssumeRole` with MFA for every privileged action rather than holding a standing admin-attached IAM user, which is exactly the anti-pattern PIM is designed to eliminate for Entra/Azure admin roles specifically.

### Scale limits worth knowing cold

- **4,000 role assignments per subscription**, hard ceiling, cannot be raised — includes assignments at subscription, resource-group, and resource scope, but **eligible** (PIM) and future-scheduled assignments do not count against it.
- **5,000 custom role definitions per tenant** (2,000 in the 21Vianet/China cloud), and roles created at the management-group scope still count against the tenant-wide total.
- Conditional Access supports on the order of **~195 policies** per tenant before hitting practical/documented limits (verify current cap near interview time — this number moves with product updates).
[Troubleshoot Azure RBAC limits — Microsoft Learn](https://learn.microsoft.com/en-us/azure/role-based-access-control/troubleshoot-limits) — accessed 2026-08-08.

### Cross-cloud mapping (see `clouds/CROSS-CLOUD-MAP.md`)

| AWS | Azure | Watch out |
|---|---|---|
| IAM users/roles/policies | Entra ID + RBAC | AWS bundles action+resource in one policy; Azure decouples role definition from scope |
| IAM role for EC2 (instance profile) | Managed Identity (system/user-assigned) | Same IMDS-based pattern, different endpoint shape |
| STS AssumeRole | PIM activation (admin roles) / Managed Identity token (workload) | PIM is for *human* privileged roles; managed identity is the workload-credential analog |
| SCPs | *No direct equivalent* — closest is deny assignments (rare, usually Blueprint/Lighthouse-generated) + Azure Policy (config-state, not permission-ceiling) | This gap is the single most-tested cross-cloud trap |
| IAM Access Analyzer | Entra Permissions Management (part of Entra Suite) | Separately licensed, not bundled by default |

---

## Build it from scratch

Minimal Python using `azure-identity`'s `DefaultAzureCredential`, which transparently tries managed identity first (falls back to CLI/env credentials for local dev) — the mechanical shape of how a workload actually gets a token without ever holding a secret:

```python
# untested sketch
from azure.identity import DefaultAzureCredential
from azure.storage.blob import BlobServiceClient

# On an Azure VM/App Service/Function with a managed identity attached,
# this silently calls the local IMDS endpoint and caches the token
# until shortly before expiry. Locally, it falls back to `az login`
# credentials — same code path in dev and production.
credential = DefaultAzureCredential()

client = BlobServiceClient(
    account_url="https://mystorageacct.blob.core.windows.net",
    credential=credential,
)

# The RBAC role assignment (e.g., "Storage Blob Data Reader" scoped to
# this storage account) is what actually determines whether this call
# succeeds -- the credential above only proves identity, not authorization.
container_client = client.get_container_client("data")
for blob in container_client.list_blobs():
    print(blob.name)
```

For the whiteboard version of "how would you check if a request is authorized," Azure exposes this as an actual API rather than requiring you to hand-simulate it the way AWS's evaluation chain does:

```bash
# Check what a principal can actually do at a scope -- Azure's rough
# analog to `aws iam simulate-principal-policy`, but it queries real
# assignment state rather than simulating a hypothetical policy.
az role assignment list --assignee <principal-id> --scope <resource-id> --include-inherited
```

---

## How it's done in production

A typical enterprise Entra/RBAC deployment: **management groups** mirror the org chart (Platform, Workloads-Prod, Workloads-NonProd, Sandbox) with Azure Policy initiatives assigned at each management group to enforce guardrails (mandatory tagging, disk encryption, no public IPs on certain resource types) — this is the practical replacement for "no SCP equivalent," accepting that it's a configuration-compliance control, not a hard permission ceiling. **Custom roles** are minted sparingly (against the 5,000/tenant ceiling) for genuinely novel permission sets; most access uses built-ins. **User-assigned managed identities** are preferred over system-assigned for anything that needs to survive resource recreation (a blue-green App Service swap, a VM Scale Set instance replacement) since a system-assigned identity's token cache and role assignments die with the resource. **PIM** gates every standing admin role for humans, with **Conditional Access** requiring phishing-resistant MFA (FIDO2/passkey) for any PIM activation. **Terraform/Bicep** manages role assignments as code, with a CI gate that fails a PR introducing a role assignment at management-group or subscription scope without a second reviewer, since scope inheritance means a mistake there blast-radiuses across everything beneath it.

| Symptom | Cause | Fix |
|---|---|---|
| Deployment pipeline suddenly fails creating role assignments with an opaque error | Subscription hit the hard 4,000 role-assignment ceiling | Reduce assignment sprawl by assigning roles to **groups** instead of individual principals (a group counts as one assignment regardless of member count), or move some assignments to a higher scope where fewer, broader assignments cover more resources |
| Managed identity works on one VM, fails after a VM Scale Set instance is replaced | System-assigned identity's lifecycle was tied to the old instance; the new instance has a new, unconfigured system identity (or none) | Use a user-assigned identity attached to the scale set model so it survives instance churn |
| Terraform apply throttled creating many managed identities in one region | Exceeded 80 create ops/20s per subscription/region (or 400/20s per tenant/region) | Batch/rate-limit identity creation, or spread creation across regions/time |
| User reports being randomly signed out mid-session | Continuous Access Evaluation revoked the token in response to a real signal (password change, risk detection, network change) — working as intended, not a bug | Confirm via Entra sign-in logs which CAE event fired; this is expected security behavior, not an outage |
| Contributor-role user can't understand why they can't grant a teammate access | Contributor structurally excludes `Microsoft.Authorization/roleAssignments/write` | Correct role for the task is **User Access Administrator** (or Owner), not a "more powerful" Contributor variant — there isn't one |
| A security review finds an over-permissioned service principal nobody remembers creating | No PIM/expiry on a standing app registration credential, or a broad role assigned at subscription scope years ago and never revisited | Run Entra Permissions Management (if licensed) or a scripted `az role assignment list` audit across all scopes; enforce access reviews via PIM for anything privileged |

---

## Tradeoffs & when NOT to use it

- **Don't assume Contributor is "almost Owner."** It's a hard, deliberate boundary — Contributor cannot touch RBAC at all. Treat any request for "give me Contributor so I can also manage access" as a red flag; the correct grant is User Access Administrator, scoped narrowly.
- **Don't reach for custom roles by default.** Every custom role counts against a tenant-wide 5,000 ceiling and is one more thing to audit and keep in sync as built-in roles evolve; use a built-in role at a tighter scope before minting a custom one.
- **Don't rely on Azure Policy as a substitute for an SCP-style permission ceiling.** It governs resource configuration state, not who-can-call-what — a principal with excessive RBAC permissions can still make disallowed API calls that simply get flagged non-compliant after the fact (or blocked at deployment time for `deny`-effect policies), which is a materially different guarantee than AWS's SCP evaluation happening before the action is even attempted.
- **Don't put Conditional Access and PIM off as "we'll add P2 later" for anything handling real production access.** Without P2, there is no risk-based sign-in blocking and no just-in-time admin activation — a genuinely different security posture than a comparably-priced AWS account gets by default.
- **Don't assign roles to individual users at scale.** Every individual assignment eats into the 4,000-per-subscription ceiling and is harder to audit; assign to Entra groups and manage membership instead.
- **System-assigned managed identities are the wrong choice for anything designed to be replaced or scaled horizontally** (scale sets, blue-green deployments) — the identity's lifecycle tied to the resource means role assignments have to be redone on every replacement; user-assigned avoids this entirely.

---

## Interview questions

### Q1 — Explain the difference between a role definition and a role assignment in Azure RBAC, and why that split doesn't exist the same way in AWS IAM.
**Testing:** whether the decoupled permission model is understood mechanically.
**Answer:** A role definition is a reusable JSON document listing allowed/denied actions — it names no principal and no specific resource. A role assignment is the tuple `(principal, role definition, scope)` that actually grants something. AWS bundles actions and resource ARNs together inside a single policy document attached to an identity, so the same "permission set" can't be cleanly reused across wildly different resource scopes without duplicating or parameterizing the policy; in Azure, the same role definition (e.g., "Storage Blob Data Reader") gets reused across every team by just creating new assignments at different scopes.
**Follow-up trap:** *"So is Azure RBAC strictly more flexible?"* — no, it's a different tradeoff: the decoupling makes broad reuse easy but makes it harder to see "everything this principal can do" at a glance, since you have to enumerate every assignment across every scope in the hierarchy rather than reading one policy document.

### Q2 — A user has Contributor at the subscription scope and wants you to also let them add a teammate to the subscription. What do you tell them?
**Testing:** the Owner/Contributor split, a very commonly missed distinction.
**Answer:** Contributor structurally cannot manage role assignments — it explicitly excludes `Microsoft.Authorization/roleAssignments/write`, regardless of how broad its other permissions are. The correct grant is User Access Administrator (scoped as narrowly as possible, ideally not at the same broad scope as their Contributor access) or, if they genuinely need both resource and access management, Owner.
**Follow-up trap:** *"Is there a role between Contributor and Owner that does 'resource management plus a little access management'?"* — not as a built-in; you'd need a custom role explicitly granting a narrow slice of `Microsoft.Authorization/roleAssignments/write` (e.g., only for a specific role definition ID), which is exactly the kind of narrow, deliberate custom role that's worth the tenant-wide custom-role budget.

### Q3 — What does Azure Policy actually protect against that RBAC doesn't, and vice versa?
**Testing:** the RBAC-vs-Policy conflation that trips nearly everyone coming from AWS.
**Answer:** RBAC controls who can call which management-plane/data-plane operations. Azure Policy evaluates resource *state* against rules regardless of who made the change — it can deny a non-compliant create/update at admission time (`deny` effect) or just flag existing non-compliant resources (`audit` effect), but it has no concept of "this principal may never call this API," only "this resource may never end up in this configuration." A principal with broad RBAC could still attempt a disallowed action; Policy is what actually stops the resulting state from existing.
**Follow-up trap:** *"So can Policy fully replace the need for tight RBAC?"* — no, because Policy doesn't gate data-plane operations the way RBAC data actions do (e.g., reading a specific blob's contents) — Policy is about resource configuration compliance, not data access; both layers are needed and they cover genuinely different attack surfaces.

### Q4 — There's no Azure equivalent to an AWS SCP. What do teams actually use to build the same guardrail?
**Testing:** currency and the honest "there's a real gap here" answer rather than false-equivalencing something.
**Answer:** The closest structural analog is a **deny assignment** — but these aren't hand-authored the way SCPs routinely are; they're typically generated automatically by Azure Blueprints/Landing Zone deployments or by Azure Lighthouse cross-tenant delegation, and aren't a general-purpose, team-authored guardrail mechanism. In practice, teams build the "no identity may ever do X across this whole OU" guarantee using a combination of Azure Policy (deny-effect policies at the management group level for configuration-level guardrails) plus disciplined RBAC assignment review — there is no single mechanism giving AWS's clean "ceiling on all identity policies below this OU" guarantee.
**Follow-up trap:** *"Doesn't Azure Policy's deny effect just do the same job?"* — only for resource *creation/update* attempts matching a specific configuration pattern; it can't express "this principal can never call `Microsoft.Compute/virtualMachines/delete`" the way an SCP denies an API action outright regardless of resource state.

### Q5 — Walk through exactly how a VM's system-assigned managed identity gets a token, and name one real security consideration in that flow.
**Testing:** mechanical understanding, not just "it uses IMDS."
**Answer:** The workload code calls the local Instance Metadata Service at `http://169.254.169.254/metadata/identity/oauth2/token` with a `Metadata: true` header and the target resource's audience URI; IMDS (running on the hypervisor, not reachable off-box) returns a short-lived Entra ID access token scoped to that audience, which the SDK caches until shortly before expiry. The security consideration: if the application has an SSRF vulnerability that lets an attacker make the app fetch an arbitrary URL, and the attacker can reach the IMDS endpoint through it, they can potentially steal a live token — the `Metadata: true` header requirement exists specifically to make naive SSRF-via-redirect harder, mirroring AWS's IMDSv2 hardening.
**Follow-up trap:** *"Does requiring the `Metadata: true` header fully close the SSRF risk?"* — no, it raises the bar (a naive open redirect can't set custom headers) but an SSRF vulnerability sophisticated enough to control headers, or a server-side proxy an attacker fully controls, can still reach IMDS; defense in depth (network segmentation, WAF rules, least-privilege on the identity itself) is still required.

### Q6 — Give me the real numbers: how many user-assigned identities can attach to one resource, and how many resources can one user-assigned identity attach to?
**Testing:** whether the specific limits are known, not just the concept.
**Answer:** A single resource (VM, App Service, etc.) can have up to **20 user-assigned identities** attached at once; a single user-assigned identity can be attached to up to **1,000 Azure resources**. Creation itself is separately rate-limited at 400 create operations per 20 seconds per tenant per region, and 80 per 20 seconds per subscription per region.
**Follow-up trap:** *"What happens if a Terraform apply tries to create 200 user-assigned identities in one subscription/region in a tight loop?"* — it will likely get throttled against the 80-per-20-seconds subscription/region ceiling well before the tenant-wide 400 ceiling, producing retriable throttling errors that look like generic API failures unless you specifically know to check against this limit.

### Q7 — What's the difference between Conditional Access and PIM, and why do people conflate them?
**Testing:** the sign-in-time vs role-activation-time distinction.
**Answer:** Conditional Access evaluates every sign-in against real-time signals (device, location, risk) and decides allow/block/step-up, regardless of what role the user holds — it's a gate on *authentication*. PIM converts standing administrative role assignments into eligible-only, requiring explicit time-bounded activation — it's a gate on *authorization elevation*, specifically for privileged roles. People conflate them because a well-designed tenant chains them: PIM activation itself is typically required to pass through a Conditional Access policy demanding MFA, so in practice they're layered, but they solve different problems and either can exist without the other.
**Follow-up trap:** *"Can Conditional Access alone provide just-in-time privileged access without PIM?"* — no, Conditional Access has no concept of "this role assignment expires after N hours"; it only gates the sign-in event itself, not the duration a standing role assignment remains active, which is exactly the gap PIM's eligible/active model closes.

### Q8 — A tenant is on Entra ID free tier. What security capability are they missing that a comparably-sized AWS account gets without paying extra?
**Testing:** currency on the licensing gate, a genuine and frequently underestimated gap.
**Answer:** No Conditional Access at all (requires P1 minimum) means no MFA enforcement policy, no device-compliance gating, and no location/app-based sign-in restrictions — and no risk-based sign-in blocking or PIM even with P1, since those specifically require P2. AWS provides baseline MFA enforcement options, IAM Access Analyzer, and GuardDuty's identity-focused findings without a separate paid identity tier, meaning "we can't afford identity security yet" is a materially riskier statement on Azure's free tier than the equivalent statement on a base AWS account.
**Follow-up trap:** *"So is P1/P2 licensing basically mandatory for any real Azure deployment?"* — for anything beyond a personal/sandbox subscription, yes in practice; most enterprise landing zone reference architectures assume at least P1 tenant-wide and P2 for admin accounts as a starting requirement, not an optional upgrade.

### Q9 — Design least-privilege access for a CI/CD pipeline that deploys to multiple resource groups across dev/staging/prod subscriptions.
**Testing:** synthesizing RBAC scope, managed identity/workload identity federation, and PIM into a coherent design.
**Answer:** Use a user-assigned managed identity (or, for external CI like GitHub Actions, Entra Workload ID Federation via OIDC — Azure's equivalent to AWS's GitHub OIDC + AssumeRoleWithWebIdentity, no stored secret) with narrow, environment-specific role assignments: Contributor scoped to the specific resource group per environment, not subscription-wide, and never Owner. Prod deployment approval gates should require a human-in-the-loop step (pipeline environment protection rules) rather than relying on RBAC alone to express "needs approval." Any human break-glass access to prod should go through PIM-eligible roles requiring MFA activation, not a standing assignment even for the pipeline's operators.
**Follow-up trap:** *"Why not just give the pipeline identity Contributor at the subscription level to simplify management across all three resource groups?"* — that violates least privilege and means a compromised pipeline identity (a leaked federated-credential trust misconfiguration, a malicious PR in a repo with write access) can touch every environment including prod from a single foothold; scoping per-RG contains blast radius to exactly the environment being deployed.

### Q10 — A subscription's deployment automation starts failing with role-assignment errors, but no one on the team believes they're anywhere near a quota. Debug it.
**Testing:** the specific hard limit and the fix pattern, under a "nobody believes this is the cause" framing that tests whether the number is actually memorized.
**Answer:** Check the subscription's total role assignment count against the hard 4,000-per-subscription ceiling (`az role assignment list --scope /subscriptions/<id> --include-inherited --all | length`) — teams routinely undercount because assignments accumulate silently across every resource group and resource scope over years, and CI-created assignments for short-lived environments often aren't cleaned up. The fix isn't raising the limit (it can't be raised) — it's consolidating individual-principal assignments into group-based assignments (a group with 50 members assigned once still counts as one assignment) and auditing for stale assignments from decommissioned environments.
**Follow-up trap:** *"Do PIM-eligible assignments count toward this limit?"* — no, eligible (not yet activated) and future-scheduled assignments are excluded from the 4,000 count, which is a real lever: converting rarely-used standing assignments to PIM-eligible ones both improves security posture and reduces pressure on the hard ceiling simultaneously.

### Q11 — Explain Continuous Access Evaluation and give a concrete scenario where its absence would have mattered.
**Testing:** whether "near real-time revocation" is understood with the actual mechanism and a real-world stake.
**Answer:** Without CAE, a stolen or leaked access token remains valid until natural expiry — typically 60-90 minutes — even after an admin disables the compromised account or resets its password, because the token itself was already issued and the resource wasn't re-checking with Entra ID on every call. CAE-enabled services subscribe to critical event signals (account disabled, password changed, high-risk sign-in detected, network location change relevant to a Conditional Access policy) and revoke the token's validity within minutes of the event, closing that 60-90-minute exposure window. Concretely: an employee's laptop is stolen with an active session; the moment IT disables the account in Entra ID, CAE-enabled services (not all services support it) cut off the stolen token almost immediately instead of leaving up to 90 minutes of continued access.
**Follow-up trap:** *"Does CAE protect every Azure/Entra-integrated app automatically?"* — no, CAE requires the resource provider/application to actually implement support for it; Microsoft 365 services are CAE-enabled broadly, but a custom application needs to explicitly integrate with the CAE-aware token validation flow to get the near-real-time revocation benefit rather than assuming it's automatic for anything issuing Entra tokens.

---

## Red flags that fail you

- Calling Azure RBAC "basically the same as AWS IAM" without naming the decoupled role-definition/role-assignment/scope model as the actual structural difference.
- Saying Contributor is "almost Owner" or that it can grant access to others.
- Claiming Azure has a direct SCP equivalent, or conflating Azure Policy with a permission ceiling.
- Not knowing Conditional Access requires paid licensing (P1 baseline, P2 for risk-based/PIM).
- Confusing Conditional Access (sign-in gate) with PIM (privileged role activation) as if they're the same mechanism.
- Not knowing the difference in lifecycle between system-assigned and user-assigned managed identities.
- Treating the 4,000-role-assignment-per-subscription limit as something you can request an increase for.

---

## Cheat card

```
ENTRA ID = directory (users/groups/SPs) + token issuer. Renamed from Azure AD in 2023.
RBAC = who can act. Role Assignment = (principal, role definition, scope). Scope inherits
  top-down: mgmt group -> subscription -> resource group -> resource. No AWS equivalent
  to this cascading grant.
AZURE POLICY != RBAC. Policy governs resource CONFIG STATE, not who-can-call-what.
  No clean Azure equivalent to an AWS SCP ceiling; closest is deny assignments
  (Blueprint/Lighthouse-generated, not hand-authored) + Policy deny-effect.

OWNER: full access + can grant access to others.
CONTRIBUTOR: full resource management, CANNOT touch RBAC (no roleAssignments/write).
USER ACCESS ADMIN: manage role assignments only, no resource management.

MANAGED IDENTITY:
  System-assigned: 1:1 with resource, dies with it.
  User-assigned: independent lifecycle, up to 1000 resources per identity,
    up to 20 identities per single resource.
  Create rate limits: 400/20s per tenant/region, 80/20s per subscription/region.
  Token flow: IMDS at 169.254.169.254, requires "Metadata: true" header (anti-SSRF).

CONDITIONAL ACCESS: real-time sign-in gate (allow/block/step-up). Requires P1 baseline,
  P2 for risk-based conditions. Free tier tenant = ZERO Conditional Access.
CAE (Continuous Access Evaluation): revokes tokens in minutes on critical signal,
  vs 60-90min natural token expiry. Requires resource-side CAE support, not automatic.

PIM: converts standing admin roles to ELIGIBLE-only; activation = MFA + duration-bounded
  (1-8h typical) + optional approval. Eligible/future assignments don't count vs 4000 limit.

HARD LIMITS: 4,000 role assignments/subscription (not raisable, groups count as 1).
  5,000 custom role definitions/tenant (2,000 in 21Vianet/China cloud).
  ~195 Conditional Access policies/tenant (verify current figure near interview date).

CROSS-CLOUD: Entra ID+RBAC ~= IAM. Managed Identity ~= IAM role for EC2 (IRSA-like).
  PIM activation ~= AssumeRole for human admins. No RBAC equivalent to resource-based
  policies or SCPs -- this gap is the #1 tested cross-cloud trap.
```

## Sources

- [Microsoft Entra ID Pricing 2026 — IDSync](https://idsync.com/guides/microsoft-entra-pricing) — accessed 2026-08-08
- [Microsoft Entra ID Premium P1/P2 — May 2026 Update — ContentWave](https://contentwave.net/article/microsoft-entra-id-premium-p1p2-2026-update-zerotrust) — accessed 2026-08-08
- [Managed identities for Azure resources frequently asked questions — Microsoft Learn](https://learn.microsoft.com/en-us/entra/identity/managed-identities-azure-resources/managed-identities-faq) — accessed 2026-08-08
- [Best practice recommendations for managed system identities — Microsoft Learn](https://learn.microsoft.com/en-us/entra/identity/managed-identities-azure-resources/managed-identity-best-practice-recommendations) — accessed 2026-08-08
- [Troubleshoot Azure RBAC limits — Microsoft Learn](https://learn.microsoft.com/en-us/azure/role-based-access-control/troubleshoot-limits) — accessed 2026-08-08
- [Deconstructing Azure Access Management using RBAC — Tenable](https://ermetic.com/blog/azure/deconstructing-azure-access-management-using-rbac/) — accessed 2026-08-08
- [Mapping AWS IAM concepts to similar ones in Azure — Arsen Vladimirskiy](https://arsenvlad.medium.com/mapping-aws-iam-concepts-to-similar-ones-in-azure-c31ed7906abb) — accessed 2026-08-08
- [Privileged Identity Management 2026: Just-in-Time Access, PAM](https://www.decryptiondigest.com/blog/privileged-identity-management-pim) — accessed 2026-08-08
- [Compare and contrast Azure RBAC vs Azure policies — KodeKloud](https://notes.kodekloud.com/docs/Microsoft-Azure-Security-Technologies-AZ-500/Enterprise-Governance/Compare-and-contrast-Azure-RBAC-vs-Azure-policies/page) — accessed 2026-08-08

## Changelog
- 2026-08-08 — created
- 2026-08-09 — Trusted Launch as Default (TLaD) reaches GA for new Gen2 VMs and VMSS — Secure Boot and vTPM are now enabled automatically on supported deployments instead of opt-in, raising the default security baseline for new compute ([src](https://www.microsoft.com/releasecommunications/api/v2/azure/rss))
- 2026-08-09 — Symmetric keys on Azure Key Vault Premium reach public preview (oct-HSM key type, AES) — first native symmetric-key support in Key Vault Premium ([src](https://www.microsoft.com/releasecommunications/api/v2/azure/rss))
