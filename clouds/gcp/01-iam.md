# GCP IAM: Roles, Service Accounts, Workload Identity Federation, Org Policy

> **Track:** C-GCP Google Cloud Atlas · **Time:** 2.5h · **Prereqs:** none · **Updated:** 2026-08-08
> **Module id:** `C-GCP-iam` · **Tags:** security, critical

## The 30-second version

GCP IAM binds **roles** (bundles of permissions — basic, predefined, or custom, capped at 3,000 permissions and 64KB total size) to **principals** (users, groups, service accounts, or a Workload Identity Federation subject) on a **resource** somewhere in the hierarchy Organization → Folder → Project → Resource. Every binding is inherited **downward and additively**: the effective policy on a resource is the union of what's bound there plus everything inherited from every ancestor, and — this is the one fact that separates people who've actually run GCP from people who've only read about it — **you cannot remove or narrow a permission at a lower level**. There is no equivalent of an AWS explicit-deny statement in the base model; the only way to block an inherited grant is a separate **deny policy** (added 2021, a real overlay that always wins) or an **Organization Policy** constraint, which is a categorically different mechanism that restricts *configurations*, not principals, and works alongside IAM rather than through it — both layers must allow an action for it to succeed. Workload Identity Federation lets an external identity (a GitHub Actions OIDC token, an AWS role, a Kubernetes service account) exchange its token for short-lived GCP credentials via a workload identity pool and CEL-based **attribute condition**, so you never mint a downloadable service account key for CI/CD. The resource-hierarchy-inheritance model is the single most-probed GCP IAM topic in interviews because it inverts the mental model AWS engineers walk in with.

## Why this gets asked

Every interviewer asking this has personally cleaned up after an org-level Owner grant that fanned out to 400 projects with no way to carve out an exception at the project level, or debugged a service that unexpectedly had access to a resource because a folder three levels up granted `roles/editor` to a group nobody remembered existed. They also want to know whether you understand that GCP simply doesn't have AWS's resource-policy-plus-identity-policy dual evaluation with explicit-deny-wins semantics — candidates who answer "just add a deny statement like in AWS" are describing a system that doesn't exist on GCP without a specific, separate deny-policy resource.

---

## Lineage: past → present → future

**What came before.** GCP's original 2011-era access model had exactly three roles — Owner, Editor, Viewer — applied at the project level with no resource-hierarchy structure above the project and no way to scope permissions more narrowly than "can edit everything" or "can view everything." The pain: any team past a few dozen engineers either over-granted Editor to get people unblocked or hand-rolled brittle per-resource ACLs in the services that supported them (Cloud Storage bucket ACLs, BigQuery dataset ACLs), and there was no way to apply one policy across a whole department's projects. AWS's IAM, by contrast, launched with fine-grained identity policies from early on but never got a native multi-project grouping primitive as clean as folders — AWS bolted Organizations and SCPs on in 2017, years after IAM itself.

**Where it stands now.** GCP shipped the Organization → Folder → Project hierarchy in 2016 specifically to fix the "no grouping" problem, with allow policies that are additive and inherited down the tree by default — a resource's effective policy is the union of its own bindings and everything inherited from ancestors, and a child **cannot subtract** a permission an ancestor granted. [Allow policy inheritance — Google Cloud IAM docs](https://docs.cloud.google.com/iam/docs/resource-hierarchy-access-control) — accessed 2026-08-08. This is a deliberate design choice, not an oversight: Google's model treats IAM as strictly additive so that reasoning about "can this principal do X" never requires walking the whole tree looking for an override that cancels it back out. The live disagreement in the ecosystem is whether that additive-only model is actually safer in practice — proponents say it makes blast radius easy to reason about (nothing above you can be silently narrowed below you, so audits of the top of the tree are trustworthy); critics point out it pushes teams toward **deny policies** and **Organization Policy** as bolt-on exception mechanisms that most engineers don't reach for until they've already been burned once. Workload Identity Federation (GA 2021, expanded through 2024-2025 with managed workload identities for Compute Engine and GKE and Agent Identity for AI agents in 2025-2026) is now Google's explicit, repeated recommendation over service account keys for anything external — AWS (IRSA/Pod Identity) and Azure (Managed Identity) converged on the same "no static keys" direction around the same period, but GCP's version is the most general: it federates literally any OIDC or SAML provider, not just the hyperscaler's own compute fabric.

**Where it's heading.** Deny policies and the newer **Principal Access Boundary (PAB) policies** (IAM v3, conceptually close to an AWS permission boundary — a ceiling on what a principal can ever be granted, regardless of what allow policies say) are Google's answer to the "additive-only is dangerous" critique, and the direction of travel is clearly toward giving admins more restrictive, deny-shaped tools without abandoning the additive allow-policy core — moderate-to-high confidence, since PAB policies shipped as GA-adjacent in 2025-2026 specifically to close this gap. **Privileged Access Manager (PAM)** for just-in-time elevated access (time-boxed grants with approval workflows, replacing "give someone Owner and remember to revoke it later") is Google's converging answer to what AWS does with IAM Identity Center permission sets plus manual processes — moderate confidence this becomes the default pattern for break-glass access. Static service account keys are on a slow, explicit deprecation glide path in guidance (not yet a hard platform deprecation) in favor of Workload Identity Federation everywhere possible — treat "just use a key" as an increasingly indefensible answer in an interview.

---

## Mental model

```
GOOGLE CLOUD RESOURCE HIERARCHY (allow policy = ADDITIVE, UNION, inherited DOWN)
┌─────────────────────────────────────────────────────────────────────┐
│ ORGANIZATION  (root; roles/resourcemanager.organizationAdmin lives   │
│                here; org policies usually anchored here)             │
│   └── FOLDER   (roles granted here inherit to all child folders/     │
│         │        projects; mirrors a business unit / team)           │
│         └── PROJECT  (trust boundary; most workloads live here)      │
│               └── RESOURCE  (bucket, topic, VM, dataset...)          │
└─────────────────────────────────────────────────────────────────────┘
  Effective policy on any node = union(bindings here, bindings on every ancestor)
  A child CANNOT remove a grant an ancestor made.  ← the AWS-brain trap
  The only ways to block an inherited allow:
    1. DENY POLICY  (separate resource, explicit block, always wins over allow)
    2. ORG POLICY   (restricts *configuration*, not principals; IAM grants
                      "who can act", Org Policy restricts "what's allowed to
                      exist" — BOTH must permit the action)

AWS MODEL FOR COMPARISON (identity policy ∩ resource policy, explicit deny wins)
  principal's identity policy(ies)  ──┐
                                       ├──▶ evaluate: explicit Deny anywhere
  resource's resource policy         ──┘     beats any Allow, else union of
                                              Allows, else implicit deny
  + permission boundaries (a ceiling) + SCPs (org-wide ceiling, deny-only)

WORKLOAD IDENTITY FEDERATION (no static key)
  external token (GitHub OIDC / AWS STS / K8s SA / any OIDC-SAML)
        │  exchanged via
        ▼
  workload identity POOL  →  PROVIDER (attribute mapping + CEL condition)
        │  produces short-lived STS token, mapped to
        ▼
  principalSet://.../attribute.repository/org/repo  ──▶ granted a role
        │  usually via
        ▼
  service account IMPERSONATION (roles/iam.workloadIdentityUser) for the
  final API-scoped access token — the external identity is never itself
  granted product roles directly in most real deployments
```

---

## How it actually works

### Role types and the concentric-permission trap

Three role tiers: **basic roles** (Owner/Editor/Viewer, project-wide, dangerously broad — Owner includes IAM-admin permissions, i.e. a principal with Owner can grant itself anything), **predefined roles** (Google-curated, service-scoped, e.g. `roles/storage.objectAdmin`), and **custom roles** (you assemble the permission list yourself, capped at **3,000 permissions**, **300 per organization** and **300 per project** as separate limits — project-level custom roles don't count against the org cap). [IAM quotas and limits — Google Cloud docs](https://docs.cloud.google.com/iam/quotas) — accessed 2026-08-08. Basic roles are concentric (Owner ⊃ Editor ⊃ Viewer), which produces a specific interview trap: granting someone Viewer on a resource when they already have Editor at the project level is a complete no-op, because the inherited Editor grant already contains every Viewer permission — a common "why doesn't my more-restrictive-looking grant do anything" incident.

### Allow policy: additive, no local override

```python
# untested sketch — reasoning through effective permissions, not a runnable API call
# Org-level binding:  roles/editor  →  group:platform-team@company.com
# Project-level binding on "payments-prod":  (nothing that removes editor)
#
# A member of platform-team can edit EVERYTHING in payments-prod, full stop.
# There is no IAM binding you can add ON payments-prod that revokes it.
# Your only levers:
#   1. Move payments-prod out from under that org/folder binding's scope
#      (re-parent it under a different folder — expensive, disruptive)
#   2. Add a DENY POLICY on payments-prod for platform-team's specific
#      permissions (works, but is a distinct, separately-audited resource)
#   3. Redesign the org-level grant to a narrower predefined/custom role
#      in the first place (the actual fix almost everyone should reach for)
```

**Limits worth knowing cold**: a single allow policy is capped at **1,500 total principal appearances** (including domains and Google groups, not deduplicated across role bindings) and **250 unique domains/groups**; a role binding's IAM Condition expression is capped at **12 logic operators**; and up to **20 role bindings for the same role+principal pair** can coexist if they carry different condition expressions (e.g. time-boxed access windows). [IAM quotas and limits](https://docs.cloud.google.com/iam/quotas) — accessed 2026-08-08.

### Deny policies — the actual "explicit deny"

A **deny policy** is a separate IAM v2 resource (not a role binding) that lists principals and permissions to block, evaluated at every level of the hierarchy alongside allow policies, and it **always wins** regardless of what any allow policy grants — this is the closest GCP gets to AWS's explicit-deny-overrides-allow semantics, but it's opt-in and structurally separate rather than baked into the same policy object. Limits: **500 deny policies and 500 deny rules per resource**, **2,500 total principal appearances** across a resource's deny policies. [IAM quotas and limits](https://docs.cloud.google.com/iam/quotas) — accessed 2026-08-08.

### Organization Policy — restricting configuration, not principals

Org Policy is a *different axis entirely*: IAM answers "who can do X," Org Policy answers "is configuration X even allowed to exist, for anyone." A **boolean constraint** is an on/off toggle (e.g. `constraints/iam.disableServiceAccountKeyCreation` — block key creation platform-wide); a **list constraint** allows/denies specific values (e.g. which regions VMs can be created in). Both must permit an action for it to succeed — a project Owner with full IAM permissions still cannot create an external IP on a VM if an org policy list constraint denies it. Org Policy inheritance has a genuinely different override model than IAM: a child can choose to **override the parent's policy**, **merge with the parent**, or the constraint can be marked non-overridable by Google (a small set of "managed constraints" can't be loosened below where they're set). [Understanding hierarchy evaluation — Google Cloud docs](https://docs.cloud.google.com/resource-manager/docs/organization-policy/understanding-hierarchy) — accessed 2026-08-08.

### Service accounts and Workload Identity Federation

A service account is both an identity (something you grant roles to) and a resource (something you grant `roles/iam.serviceAccountUser` or `roles/iam.serviceAccountTokenCreator` on, to let other principals impersonate it). Static **keys** are capped at **10 per service account**, and Google's guidance for 2025-2026 is explicit: avoid them for anything that can instead use attached identity (Compute Engine/GKE/Cloud Run's automatic metadata-server identity) or **Workload Identity Federation** for anything external. Access tokens minted via impersonation max out at **3,600 seconds (1 hour)**, extendable to **43,200 seconds (12 hours)** only via the `constraints/iam.allowServiceAccountCredentialLifetimeExtension` org policy list constraint naming the specific service accounts. [IAM quotas and limits](https://docs.cloud.google.com/iam/quotas) — accessed 2026-08-08.

```hcl
# untested sketch — Workload Identity Federation for GitHub Actions, Terraform
resource "google_iam_workload_identity_pool" "github" {
  workload_identity_pool_id = "github-pool"
}

resource "google_iam_workload_identity_pool_provider" "github" {
  workload_identity_pool_id          = google_iam_workload_identity_pool.github.workload_identity_pool_id
  workload_identity_pool_provider_id = "github-provider"
  attribute_mapping = {
    "google.subject"       = "assertion.sub"
    "attribute.repository" = "assertion.repository"
  }
  # WITHOUT this, any repo in your GitHub org can mint GCP credentials.
  attribute_condition = "assertion.repository_owner == 'my-org'"
  oidc { issuer_uri = "https://token.actions.githubusercontent.com" }
}

# The external identity impersonates a real service account for the
# actual API access token — it is rarely granted product roles directly.
resource "google_service_account_iam_member" "wif_binding" {
  service_account_id = google_service_account.deployer.name
  role                = "roles/iam.workloadIdentityUser"
  member              = "principalSet://iam.googleapis.com/${google_iam_workload_identity_pool.github.name}/attribute.repository/my-org/my-repo"
}
```

The `attribute_condition` line is the whole interview question in miniature: omit it and every credential the external IdP has ever issued, for any repo/subject in that IdP, is accepted — the pool trusts the *provider*, not any specific caller, until you constrain it. Attribute mapping is capped at **8,192 bytes total**, **50 custom attribute mappings**, and a mapped `google.subject` at **127 bytes**. [IAM quotas and limits](https://docs.cloud.google.com/iam/quotas) — accessed 2026-08-08.

---

## Build it from scratch

Minimal end-to-end: a CI pipeline that deploys to GCP with zero long-lived secrets.

```bash
# untested sketch
gcloud iam workload-identity-pools create github-pool --location=global

gcloud iam workload-identity-pools providers create-oidc github-provider \
  --location=global --workload-identity-pool=github-pool \
  --issuer-uri="https://token.actions.githubusercontent.com" \
  --attribute-mapping="google.subject=assertion.sub,attribute.repository=assertion.repository" \
  --attribute-condition="assertion.repository_owner=='my-org'"

gcloud iam service-accounts add-iam-policy-binding deployer@my-project.iam.gserviceaccount.com \
  --role="roles/iam.workloadIdentityUser" \
  --member="principalSet://iam.googleapis.com/projects/PROJECT_NUM/locations/global/workloadIdentityPools/github-pool/attribute.repository/my-org/my-repo"

# GitHub Actions step: exchange the OIDC token, no JSON key file anywhere
# - uses: google-github-actions/auth@v2
#   with:
#     workload_identity_provider: projects/PROJECT_NUM/locations/global/workloadIdentityPools/github-pool/providers/github-provider
#     service_account: deployer@my-project.iam.gserviceaccount.com
```

---

## How it's done in production

A mature GCP org: folders mirror business units, custom roles replace basic roles almost everywhere (Owner is reserved for a break-glass group with two-plus members, per Google's own best practice), Workload Identity Federation replaces every service account key in CI/CD, deny policies carve out the handful of exceptions an additive-only hierarchy can't express cleanly (e.g. "everyone in platform-team except contractors can edit prod"), and Org Policy constraints enforce platform-wide guardrails (no external IPs, no public buckets, restricted regions) that no amount of correct IAM grants can bypass.

| Symptom | Cause | Fix |
|---|---|---|
| A user has access to a resource nobody explicitly granted it to them | An ancestor (folder or org) has a broad role binding (often a basic role) that inherits down; IAM is additive and the resource-level policy can't cancel it | Audit up the hierarchy with Policy Analyzer / `gcloud asset search-all-iam-policies`; narrow the ancestor grant rather than trying to patch it at the leaf |
| Granting a narrower role on a resource has no visible effect | The principal already holds a broader, concentric role (Editor/Owner) inherited from a parent; the narrower grant is redundant, not additive-restrictive | Confirm the effective policy (union of all levels) before assuming a leaf-level grant changes behavior; remove or scope the parent grant instead |
| A CI/CD pipeline's Workload Identity Federation exchange succeeds for repos it shouldn't | Missing or too-broad `attribute_condition` on the provider — the pool trusts any subject the IdP will vouch for | Add an explicit `attribute_condition` scoping to the exact repo/org/environment; treat its absence as equivalent to an open S3 bucket |
| A project Owner can't create a resource despite having every relevant IAM permission | An Organization Policy boolean or list constraint denies the configuration platform-wide or at a parent folder | Check `gcloud resource-manager org-policies describe`; Org Policy and IAM are separate axes and both must allow the action |
| Access token requests for a service account fail after 1 hour of intended use | Default token lifetime is 3,600 seconds; something assumed a longer-lived token without configuring the extension | Either re-mint tokens more frequently (the correct default posture) or explicitly opt the service account into the 12-hour extension via the `iam.allowServiceAccountCredentialLifetimeExtension` list constraint |
| Custom role creation starts failing in a large organization | Hit the 300-custom-roles-per-org or per-project hard limit | Consolidate near-duplicate custom roles; project-level custom roles don't count against the org cap, so scope roles to project level where they don't need org-wide reuse |

---

## Tradeoffs & when NOT to use it

- **Don't reach for deny policies as a first-line design tool.** They're a real, evaluated-everywhere override, but a hierarchy full of deny policies patching over badly-scoped allow grants is harder to audit than one with narrower grants in the first place — treat deny policies as an exception mechanism, not a substitute for correct role scoping.
- **Don't grant basic roles (Owner/Editor/Viewer) to groups above the smallest scope that needs them.** Owner at a folder fans out IAM-admin capability to every project under it; there is no way to claw that back at a child project without re-parenting or a deny policy.
- **Don't use service account keys for anything that can run on GCP-attached compute or authenticate via an external OIDC/SAML IdP.** Workload Identity Federation and attached identity cover the overwhelming majority of real cases; keys should be the answer only when a workload genuinely cannot obtain any of those (rare, shrinking further every year).
- **Don't assume Org Policy constraints are inherited the same way IAM allow policies are.** IAM is strictly additive-union with no local override; Org Policy supports override/merge semantics per constraint and some managed constraints can't be loosened below where Google or an admin fixed them — conflating the two models is a fast way to misconfigure a guardrail.
- **Don't default to a single flat project-level structure for anything beyond a small team.** The resource hierarchy exists specifically to let departments own their own project sets while still inheriting central guardrails; skipping folders means every new grouping problem gets solved with ad hoc per-project policy duplication.

---

## Interview questions

### Q1 — Explain how GCP's IAM policy evaluation model differs fundamentally from AWS's.
**Testing:** whether the resource-hierarchy-inheritance model is actually understood, not just named.
**Answer:** AWS evaluates a principal's identity-based policies together with the target resource's resource-based policy (if any), with an explicit `Deny` anywhere beating any `Allow`, and otherwise unions the allows; permission boundaries and SCPs add outer ceilings. GCP binds roles onto nodes in a resource hierarchy (Organization → Folder → Project → Resource), and a resource's effective policy is the union of its own bindings plus everything inherited from every ancestor — there is no local override; a child cannot narrow or remove a grant an ancestor made. The closest thing to AWS's explicit deny is a separately-managed **deny policy** resource, not a clause inside the allow policy itself.
**Follow-up trap:** *"So GCP has no way to express 'deny wins'?"* — it does, via deny policies (IAM v2, GA since 2021), but it's an opt-in, separately-audited overlay resource, not baked into every allow-policy evaluation the way AWS's explicit-deny is — conflating the two in an answer signals you haven't actually configured either.

### Q2 — A group has `roles/editor` bound at the organization level. Someone asks you to revoke their access to one specific "payments-prod" project. What are your actual options?
**Testing:** whether the additive-inheritance trap is understood at the level of "what do I actually do about it," not just "name the concept."
**Answer:** You cannot remove or narrow the org-level grant at the project. Real options: (1) re-parent payments-prod under a different folder/org node not covered by that binding — disruptive but structurally correct; (2) add a deny policy on payments-prod blocking the specific permissions for that group — works immediately, adds an auditable exception; (3) the actual fix is almost always to go back and narrow the org-level grant itself (predefined/custom role instead of basic Editor), since the org-wide binding was very likely wrong to begin with.
**Follow-up trap:** *"Why not just add a more-restrictive role binding at the project level for that group?"* — that binding would be additive, not restrictive; it would only add permissions, never take any away, so it has zero effect on an already-inherited Editor grant.

### Q3 — What is a deny policy, how does it differ structurally from an allow policy, and what are its hard limits?
**Testing:** currency on the actual mechanism, plus real numbers.
**Answer:** A deny policy is a distinct IAM v2 resource, separate from a resource's allow policy, listing principals and permissions to explicitly block; it's evaluated at every hierarchy level alongside allow policies and always wins over any allow grant, inherited or local. Limits: up to 500 deny policies and 500 deny rules per resource, up to 2,500 total principal appearances across a resource's deny policies, and up to 12 logic operators in a deny rule's condition expression.
**Follow-up trap:** *"Does a deny policy at a project override an allow policy inherited from the org?"* — yes, that's precisely its purpose; deny always wins regardless of which level of the hierarchy the conflicting allow came from.

### Q4 — Explain the difference between IAM and Organization Policy, with a concrete example where both matter.
**Testing:** the "who can act" vs "what's allowed to exist" distinction, a frequently-missed nuance.
**Answer:** IAM controls which principals can perform which actions by granting roles; it cannot restrict configuration choices for everyone regardless of identity. Organization Policy restricts configurations (e.g. "no VM in this org may have an external IP," "resources may only be created in these regions") platform-wide, independent of who's acting, and cannot itself grant any permission. Example: a project Owner has every IAM permission needed to attach an external IP to a VM, but if an org policy list constraint denies external IPs at a parent folder, the creation still fails — both layers must permit the action.
**Follow-up trap:** *"If I need one exception to an org-wide org policy, can I just grant more IAM permissions to the exception principal?"* — no; IAM and Org Policy are orthogonal axes, so more IAM permissions never override an Org Policy denial. The exception has to be carved out in Org Policy itself, typically by overriding the constraint at a lower-scoped resource (if the constraint allows override) or via a documented Google-approved managed-constraint exception process.

### Q5 — Walk through what Workload Identity Federation actually does mechanically, and name the one misconfiguration that defeats it.
**Testing:** whether the candidate has configured it, not just heard of it.
**Answer:** An external identity presents a token from its own IdP (GitHub OIDC, AWS STS, a Kubernetes service account token, any OIDC/SAML provider) to a GCP workload identity pool provider. The provider's attribute mapping (a set of CEL expressions) maps claims from that token into GCP-recognized attributes (`google.subject`, custom attributes), and an attribute condition (also CEL) gates which tokens are accepted at all. On success, GCP's Security Token Service issues a short-lived federated token, which is then typically used to impersonate a real service account (`roles/iam.workloadIdentityUser`) to obtain the actual product-scoped access token. The misconfiguration that defeats the whole design: omitting or under-scoping the `attribute_condition`, which means any subject the IdP will vouch for — any repo in the whole GitHub org, any AWS principal in the linked account — gets accepted, not just the intended one.
**Follow-up trap:** *"Isn't binding the impersonation IAM policy to a specific `principalSet://` path enough on its own?"* — it narrows *which* federated identity can impersonate the service account, but without a matching attribute condition on the provider itself, a broader set of external tokens are still accepted by the pool in the first place; both layers should be scoped, and relying on only one is a common half-fix.

### Q6 — What are the hard limits on custom roles, and what's the practical consequence of hitting them?
**Testing:** real numbers, and judgment about role design at scale.
**Answer:** 300 custom roles per organization and 300 per project (independent caps — project-level custom roles don't count against the org limit), up to 3,000 permissions per role, and a 64KB cap on the combined size of a role's title, description, and permission names. In a large org, hitting the cap usually means teams have been creating near-duplicate custom roles per team or per project instead of sharing a smaller, well-designed set — the fix is consolidation and possibly moving reusable roles to org-level custom roles referenced by many projects.
**Follow-up trap:** *"If a project needs a very specific one-off role, should you always create it at the org level for reuse?"* — no; project-scoped custom roles are the better default for anything not genuinely reusable, precisely because they don't consume the org-level 300-role budget, which is a shared, more contended resource across the whole company.

### Q7 — Compare service account keys, attached identity, and Workload Identity Federation, and state when each is actually the right choice.
**Testing:** the "when NOT to" judgment, not just definitions.
**Answer:** Attached identity (a service account attached directly to Compute Engine, GKE via its metadata server, Cloud Run, Cloud Functions) is the right default for anything running *on* GCP compute — no credential material to manage at all. Workload Identity Federation is the right choice for anything running *outside* GCP that has its own OIDC/SAML-capable identity (CI/CD runners, workloads on AWS/Azure, on-prem systems with a compatible IdP). Static service account keys are the fallback only when neither applies — a shrinking, explicitly discouraged category — because keys are long-lived, exportable, and capped at only 10 per service account with no built-in expiry.
**Follow-up trap:** *"Isn't rotating keys frequently just as safe as avoiding them?"* — rotation reduces but doesn't eliminate the exposure window, and it adds an operational burden (rotation pipelines, revocation on leak) that Workload Identity Federation's short-lived, non-exportable tokens remove entirely; "we rotate keys every 90 days" is a weaker answer than "we don't have keys to rotate."

### Q8 — A logical partition of your org has a mix of GCP-native workloads and a large existing AWS estate authenticating cross-cloud. How would you avoid distributing GCP service account keys to AWS-hosted workloads?
**Testing:** applying Workload Identity Federation to the specific AWS case, which has a dedicated, slightly different configuration path.
**Answer:** Configure a workload identity pool provider of type AWS, which trusts AWS STS-signed `GetCallerIdentity` credentials from a specific AWS account (and optionally specific IAM roles via the attribute condition). The AWS-hosted workload's existing AWS IAM role credentials are exchanged for a short-lived GCP token with no key material ever touching the AWS side — this is the standard "Configure Workload Identity Federation with AWS or Azure" pattern Google documents explicitly, and it removes an entire class of "we found a GCP JSON key committed to a repo hosted for an AWS workload" incidents.
**Follow-up trap:** *"Does this require the AWS account to be part of the same GCP organization or project in any way?"* — no; the AWS account only needs to be nameable in the attribute condition/mapping. This is precisely why the attribute condition matters so much here — without scoping to a specific AWS account and role, any AWS principal that can produce a valid STS `GetCallerIdentity` call could potentially be accepted, depending on how loosely the provider is configured.

### Q9 — Explain Principal Access Boundary (PAB) policies and how they differ from a deny policy.
**Testing:** currency on the newer (2025-2026) IAM v3 surface, and whether the "ceiling vs override" distinction lands.
**Answer:** A PAB policy defines the maximum set of resources a principal can ever access, regardless of what any allow policy — present or future — grants it; it's a ceiling, conceptually close to an AWS permission boundary, not a per-permission block like a deny policy. It's meant for cases like "this service account, no matter how its role bindings evolve over time, must never be able to touch resources outside these three projects," which a deny policy (which blocks specific permissions, not a whole resource scope) doesn't cleanly express. Limits: up to 500 rules per PAB policy, up to 10 PAB policies bound to a single resource, up to 1,000 PAB policies per organization.
**Follow-up trap:** *"If I bind a PAB policy to a service account, do I still need to manage its role bindings carefully?"* — yes; a PAB policy narrows the *ceiling*, it grants nothing on its own and doesn't replace correct, minimal role bindings — a principal with an overly broad role binding but a tight PAB policy is still over-permissioned within that ceiling, just contained.

### Q10 — Design the IAM structure for a company with three product teams, a shared platform team, and a hard compliance requirement that production payment data access be time-boxed and approved.
**Testing:** synthesizing hierarchy design, custom roles, and Privileged Access Manager into one coherent answer — a staff-level system-design probe.
**Answer:** Three folders, one per product team, each containing that team's dev/staging/prod projects; a separate platform folder for shared infrastructure. Predefined/custom roles scoped per-project rather than broad basic roles at any folder or org level; the org-level binding set is kept minimal (billing admin, org policy admin, a small break-glass Owner group). For payments-prod specifically, standing role bindings are limited to read-only/operational roles, and any elevated write access to payment data goes through **Privileged Access Manager entitlements** — engineers request time-boxed access, an approver grants it, PAM creates a temporary role binding with an automatic expiry, and the whole cycle is captured in audit logs — rather than anyone holding standing write access to payments-prod at all.
**Follow-up trap:** *"Why not just use IAM Conditions with a time-based expression on a standing role binding instead of PAM?"* — IAM Conditions can express a time window, but they're static (someone has to remember to create/remove them per request) and don't provide the approval workflow, entitlement catalog, or audit trail PAM gives natively; Conditions are a building block PAM uses internally, not a substitute for the request/approve/expire lifecycle a compliance requirement like this actually needs.

### Q11 — Someone asks: "why doesn't GCP support resource-based policies the way S3 bucket policies or SNS topic policies do?" How do you respond?
**Testing:** whether the candidate over-claims a parity that doesn't fully exist, or correctly nuances it.
**Answer:** GCP does support resource-level policy attachment for many services (a Cloud Storage bucket, a Pub/Sub topic, a BigQuery dataset can all have their own allow policy, per the resource-hierarchy model), so it's not accurate to say GCP has *no* resource-level policy concept. The real difference is architectural: those resource-level bindings are just another node in the same additive resource hierarchy — evaluated by union with everything inherited from above — rather than a structurally separate policy type intersected against an identity policy the way AWS evaluates a bucket policy against an IAM identity policy. There's no GCP equivalent of an S3 bucket policy that can grant access to a principal that has *no* IAM role anywhere in the hierarchy at all (cross-account-style anonymous/public-style resource policies exist for some services, like Cloud Storage's `allUsers`/`allAuthenticatedUsers`, but it's a narrower mechanism than AWS's general resource-policy model).
**Follow-up trap:** *"So can you grant a principal from an entirely different, unrelated GCP organization access to one bucket without any org-level trust relationship?"* — yes, for services like Cloud Storage that support resource-level bindings, you can bind a role to any principal identifier directly on the bucket regardless of what org they belong to; it doesn't require a cross-organization trust setup the way some other clouds' account-boundary models do, precisely because GCP's binding model treats the bucket itself as just another node that can carry principal bindings.

### Q12 — A workload identity pool provider's attribute condition was recently loosened during a migration and nobody noticed for three weeks. What's the blast radius, and how do you detect this class of incident going forward?
**Testing:** incident-response reasoning and monitoring maturity, a staff-level probe tying the mechanism back to operational practice.
**Answer:** The blast radius is every external caller the IdP itself considers valid — for a GitHub-backed pool with a loosened `attribute_condition`, that could mean any repository in the entire GitHub organization (or, if the issuer scope was also loosened, any GitHub org at all) could exchange a token and impersonate whichever service account the pool's bindings allow, for the three-week window. Detection going forward: alert on changes to workload identity pool/provider configuration via Cloud Audit Logs (`SetIamPolicy`/provider-update events are logged), and separately monitor Security Token Service token-exchange volume and *source* attributes for the pool — a spike in distinct `attribute.repository` values exchanging tokens against a pool that's supposed to serve one repo is the operational signal, independent of whether anyone caught the config change itself.
**Follow-up trap:** *"Is auditing the provider config change itself sufficient, or do you also need runtime detection?"* — config-change auditing alone is necessary but not sufficient, since it only tells you a risky change happened, not whether it was exploited during the exposure window; runtime detection on STS exchange logs is what actually answers "was this abused," which is the question that matters for incident response.

---

## Red flags that fail you

- Claiming GCP has an explicit-deny-in-the-allow-policy mechanism like AWS, without naming deny policies as the actual, separate mechanism.
- Not knowing that IAM allow policies are strictly additive with no local override — proposing to "just add a more restrictive binding" at a child resource to counter an inherited grant.
- Confusing IAM (who can act) with Organization Policy (what configuration is allowed) — treating them as the same axis.
- Recommending service account keys as a first choice for CI/CD without mentioning Workload Identity Federation.
- Describing Workload Identity Federation without mentioning the attribute condition, or not knowing that omitting it is the classic misconfiguration.
- Not knowing the 300-custom-role cap or claiming custom roles are unlimited.
- Treating basic roles (Owner/Editor/Viewer) as an acceptable default for anything beyond a personal sandbox project.

---

## Cheat card

```
HIERARCHY: Organization -> Folder -> Project -> Resource. Allow policy = ADDITIVE
  UNION of all levels; a child CANNOT remove/narrow an ancestor's grant.
DENY POLICY: separate IAM v2 resource, ALWAYS wins over allow, evaluated at
  every level. Limits: 500 deny policies/resource, 500 deny rules/resource,
  2,500 principal appearances/resource.
ORG POLICY != IAM: IAM grants "who can act"; Org Policy restricts "what config
  is allowed" for EVERYONE. Both must permit the action. Boolean or List
  constraints. Override modes: override parent / merge with parent / some
  managed constraints non-overridable.
CUSTOM ROLES: 300/org + 300/project (independent caps), up to 3,000 perms/role,
  64KB combined title+desc+perms.
ALLOW POLICY LIMITS: 1,500 total principal appearances/policy, 250 unique
  domains/groups, 12 logic operators/condition, 20 bindings for same role+
  principal w/ different conditions.
SERVICE ACCOUNT KEYS: max 10/SA. Avoid for anything with attached identity or
  WIF available. Access token lifetime: 3,600s default, up to 43,200s (12h)
  only via iam.allowServiceAccountCredentialLifetimeExtension org policy.
WORKLOAD IDENTITY FEDERATION: external OIDC/SAML token -> pool -> PROVIDER
  (attribute mapping, CEL attribute_condition) -> STS token -> usually
  impersonates a real SA (roles/iam.workloadIdentityUser). Missing/loose
  attribute_condition = the classic misconfig (any subject IdP vouches for
  gets in). Mapping limits: 8,192B total, 50 custom attrs, subject 127B.
PAB POLICIES (IAM v3, ~AWS permission boundary): hard CEILING on what a
  principal can ever access, doesn't grant anything itself. 500 rules/policy,
  10 policies/resource, 1,000/org.
PAM: just-in-time, time-boxed, approved elevated access -- replaces standing
  Owner grants for break-glass/compliance-sensitive access.
CROSS-CLOUD: AWS = identity policy + resource policy, explicit Deny wins,
  boundaries + SCPs as outer ceilings. GCP = additive hierarchy, deny policy
  as bolt-on override, Org Policy as separate restriction axis. This is the
  #1 GCP IAM interview trap for AWS engineers.
```

## Sources

- [Using resource hierarchy for access control — Google Cloud IAM docs](https://docs.cloud.google.com/iam/docs/resource-hierarchy-access-control) — accessed 2026-08-08
- [Quotas and limits — Identity and Access Management — Google Cloud docs](https://docs.cloud.google.com/iam/quotas) — accessed 2026-08-08
- [Workload Identity Federation — Google Cloud IAM docs](https://docs.cloud.google.com/iam/docs/workload-identity-federation) — accessed 2026-08-08
- [Best practices for using Workload Identity Federation — Google Cloud docs](https://docs.cloud.google.com/iam/docs/best-practices-for-using-workload-identity-federation) — accessed 2026-08-08
- [Understanding hierarchy evaluation — Organization Policy — Google Cloud docs](https://docs.cloud.google.com/resource-manager/docs/organization-policy/understanding-hierarchy) — accessed 2026-08-08
- [Organization Policy overview — Google Cloud docs](https://docs.cloud.google.com/organization-policy/overview) — accessed 2026-08-08
- [Principal access boundary policies — Google Cloud IAM docs](https://docs.cloud.google.com/iam/docs/principal-access-boundary-policies) — accessed 2026-08-08
- [About resource hierarchy — Resource Manager — Google Cloud docs](https://docs.cloud.google.com/resource-manager/docs/cloud-platform-resource-hierarchy) — accessed 2026-08-08

## Changelog
- 2026-08-08 — created
