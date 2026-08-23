# GCP IAM Deep: Resource Hierarchy, Roles, Service Accounts, Workload Identity Federation, Deny & Org Policy

> **Track:** C-GCP Google Cloud Atlas · **Time:** 2.5h · **Prereqs:** none · **Updated:** 2026-08-23
> **Module id:** `C-GCP-iam` · **Tags:** security,critical

## The 30-second version

GCP authorization is allow-by-binding: every resource carries an allow policy whose bindings say "member M gets role R," roles are named bundles of permissions, and everything inherits down the organization → folder → project → resource hierarchy. Two layers sit above allows: **deny policies** win at request time regardless of any binding, and **Organization Policy** constrains what anyone can configure at deploy time; **Principal Access Boundary policies** add a third axis by capping *which* resources a principal can ever touch. Credentials follow one rule: workloads running on Google compute get short-lived tokens from the metadata server via an attached service account, everything outside uses **Workload Identity Federation** to trade an external OIDC/SAML/AWS assertion for a short-lived token, and downloadable service-account keys are what you eliminate, not rotate. When someone says "just use the default compute service account, it's easier," that sentence is the interview.

## Why this gets asked

Because the expensive GCP incidents are almost never exotic: a JSON service-account key committed to a repo (it never expires by default and logs nothing about who used it), a pipeline granted `roles/editor` because a tutorial said so, or data copied into an attacker-controlled project that IAM alone cannot stop once the identity holds the right permission — which is exactly the hole VPC Service Controls and Principal Access Boundary exist to close. Interviewers who run GCP estates probe three things: whether you know the actual evaluation order (deny beats allow, always), whether you understand that a service account is simultaneously an *identity* you grant roles to and a *resource* you need permission to act as (`iam.serviceAccounts.actAs` being GCP's answer to AWS's `PassRole` problem), and whether your "no static keys" answer includes federation mechanics rather than the slogan. Candidates who recite "least privilege" without knowing how `google.subject` mappings and attribute conditions gate a federated token exchange fail here.

---

## Lineage: past → present → future

**What came before.** Before Cloud IAM (launched 2014–2015, GA across services through 2016), each Google API carried its own access model: Cloud Storage had per-object ACLs, BigQuery had dataset ACLs, and projects were administered with three primitive team roles inherited from Google's internal tooling. There was no hierarchy, no reusable role concept beyond primitive owner/editor/viewer, and auditing "who can read this table" meant walking product-specific ACL systems one by one. The pain that killed this model was scale: companies with hundreds of projects could not express "this contractor may deploy, but never delete, in these twelve projects only" without hand-maintaining ACLs per service. Uniform bucket-level access eventually replaced GCS ACLs entirely; the old object-ACL model survives only as a legacy mode you must explicitly keep.

**Where it stands now.** The core is settled: allow policies with role bindings evaluated against a four-level resource hierarchy; three role families (basic, predefined, custom); IAM Conditions adding CEL expressions to bindings; service accounts as both identity and resource. What changed recently is the guardrail stack. **Deny policies** went GA in 2022 and gave GCP a true explicit-deny that outranks every allow. **Organization Policy** moved to a v2 API with custom constraints (CEL over incoming resource fields, enforced on CREATE/UPDATE) alongside hundreds of predefined constraints. **Workload Identity Federation** became the documented default for anything authenticating from outside Google — CI systems, AWS/Azure workloads, Kubernetes elsewhere — turning downloadable keys into a compliance finding rather than a design choice. **Principal Access Boundary policies** (rolling out 2024–2025) cap the set of resources a principal can access, closing the phishing/exfiltration gap where a valid identity with valid permissions reads data into the wrong project. [Just say no: build defense in depth with IAM Deny and Org Policies](https://cloud.google.com/blog/products/identity-security/just-say-no-build-defense-in-depth-with-iam-deny-and-org-policies); accessed 2026-08-23. The live operational disagreement: group-based grants. Group membership changes propagate with noticeable delay (commonly minutes to tens of minutes, ~), so designs that need fast revocation bind roles directly to identities instead.

**Where it's heading.** Three directions, stated confidence. High confidence: continued elimination of long-lived credentials — org-policy constraints like `iam.disableServiceAccountKeyCreation` are already baseline guidance, and key existence keeps trending toward "audit finding." High confidence: agentic access control — Google's IAM surface now explicitly targets AI agents (dedicated agent identity types, PAB used to down-scope agent permissions below their delegating user's), because an agent borrowing a human's identity today is an unaudited privilege escalation. Medium confidence: just-in-time elevation going mainstream via Privileged Access Manager (time-bound, approval-gated role activation) replacing standing admin grants. Speculative: fully policy-generated least privilege, where observed usage automatically rewrites bindings — Recommender already suggests removals based on a 90-day observation window, but automated remediation without human review remains rare because absence-of-recent-use is not absence-of-need.

---

## Mental model

One request passes three gates, and only the middle gate can say yes:

```
REQUEST (principal P wants permission X on resource R)
   │
   ▼
[1] DENY POLICY matches (P, X)? ────────────────yes──▶ DENY (final; only
   │ no                                           exceptionPrincipals escape)
   ▼
[2] ALLOW POLICIES: does ANY binding in the inherited
    chain (org → folder → project → resource) give P
    a role containing X, conditions satisfied? ───no───▶ DENY (default deny)
   │ yes
   ▼
[3] PRINCIPAL ACCESS BOUNDARY: is R inside the set of
    resources P is eligible to touch? ─────────────no───▶ DENY
   │ yes
   ▼
  ALLOW
```

And behind the identity sits exactly one credential rule worth memorizing:

```
WHERE DOES THE WORKLOAD RUN?
 ├─ on Google compute (VM / Cloud Run / GKE / Functions)
 │    └─ attached SA → metadata server hands out ~1h tokens. No key.
 ├─ anywhere else (CI, AWS, Azure, on-prem, other K8s)
 │    └─ Workload Identity Federation: external OIDC/SAML/AWS token
 │       → STS exchange (gated by attribute conditions)
 │       → optional service-account impersonation. No key.
 └─ "we downloaded a JSON key file"
      └─ wrong answer. Max 10 keys per SA, none expire by default,
         org policy exists specifically to ban creating them.
```

The ordering matters less than the asymmetry: gate 2 needs exactly one yes anywhere in the hierarchy; gates 1 and 3 need one hit to end the request. That is why guardrails are cheap to add late and grants are dangerous to add carelessly.

---

## How it actually works

### The resource hierarchy and inheritance

Organization → folders (nestable) → projects → resources. Allow policies inherit downward; a binding at any level applies everywhere below it. Practical consequences: a binding on the org node reaches tens of thousands of resources instantly, and "why does this intern have BigQuery admin" usually resolves to a binding placed too high in the tree. Projects are the tenancy unit — most multi-tenant blast-radius arguments on GCP reduce to "one project per tenant/environment," because IAM, network defaults, and quotas all stop at project edges.

### Roles and permissions, precisely

A permission looks like `service.resource.verb` (`storage.objects.get`). A role is a set of permissions. Three families:

| Family | Examples | When defensible |
|---|---|---|
| Basic | `roles/owner`, `roles/editor`, `roles/viewer` | `owner` on throwaway sandboxes; almost never otherwise. `editor` mutates every resource in scope |
| Predefined | `roles/run.invoker`, `roles/storage.objectViewer` | Default choice — curated, updated by Google |
| Custom | your own bundles | Only when no predefined role fits; quota-capped (~300 per org and ~300 per project, ~) and maintained forever |

Custom-role maintenance cost is what people underestimate: Google adds permissions constantly, and a frozen custom role silently drifts. Senior pattern: predefined-first, custom as last resort with an owner and a review date.

### IAM Conditions

Bindings accept a CEL condition evaluated per request:

```json
{
  "role": "roles/storage.objectViewer",
  "members": ["group:data-scientists@example.com"],
  "condition": {
    "title": "staging-buckets-only",
    "expression": "resource.name.startsWith(\"projects/_/buckets/staging\") && request.time.getHours(\"UTC\") >= 13"
  }
}
```

Condition context includes `resource.name/type/tags`, `request.time`, and for some services `origin.resource`. Two traps: expressions fail closed on error (good), and time-based conditions are access-control knobs, not session terminators — an already-issued OAuth token keeps working until expiry even after the condition turns false.

### Deny policies

Deny policies attach to org/folder/project (not individual resources), specify `deniedPermissions`, `deniedPrincipals`, and `exceptionPrincipals` for break-glass. They evaluate before allows and cannot be overridden by any binding, including `roles/owner`. Constraints: only a subset of IAM permissions is deny-supportable (a growing list across major services, ~; verify coverage before designing a control around one), and rules match permissions, not REST methods. The denial error names the deny policy, which makes debugging straightforward compared to silent allow-absence.

```json
{
  "displayName": "no-new-sa-keys-org-wide",
  "rules": [{
    "denyRule": {
      "deniedPrincipals": ["principalSet://goog/public:all"],
      "deniedPermissions": ["iam.googleapis.com/serviceAccountKeys.create"],
      "exceptionPrincipals": ["principalSet://goog/group/security-admins@example.com"]
    }
  }]
}
```

### Service accounts: identity and resource

A service account is an email-shaped principal (`sa-name@project-id.iam.gserviceaccount.com`) that applications authenticate *as*. The duality matters:

- **As identity**, it receives role bindings like any member.
- **As resource**, acting as it requires permission. Two distinct roles get conflated constantly:
  - `roles/iam.serviceAccountUser` — the *attach* right: launch a VM/Cloud Run service/function running as that SA (`iam.serviceAccounts.actAs`). This is GCP's `PassRole`.
  - `roles/iam.serviceAccountTokenCreator` — the *mint* right: call `generateAccessToken`, `generateIdToken`, `signJwt` directly, i.e., become the SA without attaching anything.

TokenCreator granted broadly is worse than User, because minting skips the "launch a workload" indirection entirely. Minted access tokens default to 3600 seconds; lifetime extension up to 12 hours exists but is gated by org policy and rarely justified.

Every project ships two default SAs: App Engine default (`project-id@appspot.gserviceaccount.com`) and Compute Engine default (`project-number-compute@developer.gserviceaccount.com`). Historically both received `roles/editor` automatically; newer projects can be created without that auto-grant (configurable since ~2024), but existing estates are full of Editor-granted defaults, and every service that leaves the SA field blank quietly uses them. "Which SA did this actually run as?" is a daily production question.

### Attached service accounts and the metadata server

Code on Google compute never handles a key file. SDKs fetch tokens from the metadata server (`metadata.google.internal`, 169.254.169.254):

```python
# untested sketch
import urllib.request, json
req = urllib.request.Request(
    "http://metadata.google.internal/computeMetadata/v1/instance/"
    "service-accounts/default/token",
    headers={"Metadata-Flavor": "Google"})
tok = json.load(urllib.request.urlopen(req))["access_token"]  # ~3600s TTL
```

In practice call ADC (`google.auth.default()`), which resolves this for you. SDKs cache tokens for their lifetime; hammering the metadata endpoint per-request is an anti-pattern that surfaces as throttling under fan-out.

### GKE Workload Identity

The Kubernetes-native version: pods authenticate as a *Kubernetes* service account (KSA), and IAM maps KSA → Google service account (GSA):

```
pod (uses KSA "backend") annotated
    iam.gke.io/gcp-service-account: backend-prod@proj.iam.gserviceaccount.com
        │
        ▼  pod presents KSA-signed credential to GKE's metadata emulator / STS
GCP validates the KSA↔GSA mapping (roles/iam.workloadIdentityUser bound to
principal://iam.googleapis.com/projects/<n>/clusters/<c>/namespaces/<ns>/sa/<ksa>)
        │
        ▼
GCP-issued token carrying the GSA's roles
```

Enable Workload Identity Federation for GKE per cluster and node pool (workload metadata config). Classic failure: the binding granted to a namespace-wide `principalSet` instead of the specific KSA principal, letting every workload in the namespace impersonate the GSA.

### Workload Identity Federation, mechanically

For anything *outside* Google:

```
GitHub Actions job                     GCP side
────────────────────                   ─────────────────────────────────
1. request OIDC token from             POOL (trust boundary)
   token.actions.githubusercontent.com └ PROVIDER (issuer-uri, JWKS, audience)
2. POST token to sts.googleapis.com       ├ attribute.mapping: google.subject =
                                             assertion.sub (+ extras)
                                          └ attribute.condition: CEL gate
3. STS validates signature via JWKS,
   evaluates condition, returns
   short-lived federated token
4. exchange via iamcredentials          SA binding:
   generateAccessToken                  roles/iam.workloadIdentityUser on
                                        principalSet://…/attribute.repository/my-org/my-repo
```

Both steps produce ~1-hour tokens; nothing is stored; nothing rotates. Security rests on two independent gates and interviews test whether you know *both*: the provider's **attribute condition** decides who may exchange at all (missing it means every repo on GitHub can attempt exchange against your pool), and the IAM binding's **principalSet attribute selector** decides which of those identities may impersonate which SA (`attribute.repository/my-org/deploy-repo`, not the bare pool wildcard). Use immutable attributes — numeric `repository_owner_id` rather than reassignable names — per Google's own best-practice guidance. [Best practices for using Workload Identity Federation](https://docs.cloud.google.com/iam/docs/best-practices-for-using-workload-identity-federation); accessed 2026-08-23. [Workload Identity Federation](https://docs.cloud.google.com/iam/docs/workload-identity-federation); accessed 2026-08-23.

Federation isn't only OIDC: AWS role ARNs (asserted via `sts:GetCallerIdentity`), SAML v2 IdPs, and X.509 certificates are supported provider types — how cross-cloud pipelines go keyless in both directions.

### Organization Policy

Org policy is *configuration guardrails*, evaluated when someone creates or changes a resource — a different plane from IAM's request-time checks. Boolean constraints (`iam.disableServiceAccountKeyCreation`, `storage.publicAccessPrevention`, `compute.disableSerialPortAccess`), list constraints (`iam.allowedPolicyMemberDomains` for domain-restricted sharing, `compute.vmExternalIpAccess`), and since 2023 **custom constraints**: a CEL expression over the incoming resource definition, enforced on CREATE/UPDATE for supported services. Custom constraints encode house rules no predefined constraint covers ("node pools must set autoUpgrade"), though support is service-by-service and expanding. Policies inherit down the org/folder/project tree and support dry-run (evaluate, log, don't enforce) — the correct rollout vehicle, because an enforced misconfigured boolean constraint at org level halts deploys org-wide within seconds. [Create and manage custom organization policy constraints](https://docs.cloud.google.com/resource-manager/docs/organization-policy/creating-managing-custom-constraints); accessed 2026-08-23.

### Principal Access Boundary policies

PAB closes the last structural hole in the pure allow model: a legitimate principal holding legitimate permissions reading data *into the wrong place* (attacker-created project, another organization). A PAB policy enumerates the resources — by org/folder/project — that a principal is eligible to access; requests targeting anything outside the boundary are denied even though every allow check would pass. It grants nothing; purely subtractive. Coverage is still service-scoped (major storage/data services first, ~), so treat PAB as defense-in-depth beside VPC Service Controls rather than a replacement: VPC-SC draws the network/API perimeter, PAB draws the identity perimeter. [Principal access boundary policies](https://docs.cloud.google.com/iam/docs/principal-access-boundary-policies); accessed 2026-08-23.

### Debugging "who can do what" and "why was I denied"

Three tools, three questions:

1. **Policy Troubleshooter** — "why did/didn't principal P get permission X on resource R?" Walks bindings, conditions, and deny policies; reports the deciding rule.
2. **Policy Analyzer** — "which principals can call permission X on resource Y?" Expands groups and hierarchy inheritance into a flat answer.
3. **IAM Recommender** — "which roles are over-provisioned?" Uses observed usage over a 90-day window; suggests narrower predefined roles or removal. Handle low-frequency-but-real permissions (DR runbooks) with care before acting on findings.

## Build it from scratch

An evaluator capturing the three-gate logic plus a federation check showing why one missing line opens the pool:

```python
# untested sketch
def evaluate(principal, perm, resource, deny_policies, bindings_chain):
    # Gate 1: deny wins absolutely; exceptionPrincipals are break-glass carve-outs
    for dp in deny_policies:
        for rule in dp.rules:
            if (perm in rule.denied_permissions
                    and principal_matches(rule.denied_principals, principal)
                    and not principal_matches(rule.exception_principals, principal)):
                return "DENY", f"deny policy {dp.name}"
    # Gate 2: ONE allow anywhere in the inherited chain suffices;
    # a binding condition failing to evaluate = no allow (fail closed)
    for scope, bindings in bindings_chain:      # org -> folder -> project -> resource
        for b in bindings:
            if perm in ROLES[b.role] and principal_matches(b.members, principal):
                if b.condition is None or cel_eval(b.condition, principal, resource):
                    return "ALLOW", f"binding at {scope}"
    return "DENY", "default deny"

def federate(assertion_attrs, provider):
    # signature validation against JWKS assumed done upstream
    if provider.attribute_condition and not cel_eval(provider.attribute_condition,
                                                     assertion_attrs):
        raise PermissionError("attribute condition rejected")   # THE forgotten gate
    return assertion_attrs["google.subject"]     # becomes the pool principal
```

Teaching point: gate 2 is a union across scopes while gates 1 and 3 intersect downward — and in `federate`, deleting the condition line converts a locked trust boundary into an open one with no error surfacing later.

## How it's done in production

Standard estate shape: Terraform-managed bindings only (console drift treated as incident-worthy), one project per environment per tenant tier, workload SAs named per workload-per-dependency, human access via group bindings synced from the IdP with Privileged Access Manager gating elevated roles. Baseline org policy at the org node: disable SA key creation and upload, domain-restricted sharing, public-access-prevention enforced, dry-run-first rollouts for everything new. Deny policies for non-negotiables (key creation except security team; org-level IAM mutations except platform admins) with exception principals wired to a monitored break-glass path. WIF for every CI system; attached SAs and GKE Workload Identity inside the estate; Recommender findings triaged monthly.

| Symptom | Cause | Fix |
|---|---|---|
| `PERMISSION_DENIED ... by IAM deny policy 'X'` | Request hit a deny rule | Working as designed; route through the exception-principal process |
| Works locally, fails in CI with "same" setup | CI authenticates as a different principal than assumed | Read the exact principal in the audit log entry; verify the principalSet selector |
| Pod gets 403 despite correct KSA-GSA annotation | Workload Identity not enabled on cluster/node pool, or binding wrong | Enable workload metadata config; bind to the exact KSA principal |
| New VM launches but can't use its own SA's roles | Deployer lacked `iam.serviceAccounts.actAs`, or SA has no bindings | Grant actAs to deployer; bind roles to the workload SA, never to users |
| Group membership added, access still failing an hour later | Group propagation delay | Bind critical roles directly to identities; treat groups as slow-path |
| Audit finds JSON keys on a laptop | Keys created before the org-policy ban | Revoke, migrate workload to WIF/attached SA, enforce `disableServiceAccountKeyCreation` |

## Tradeoffs & when NOT to use it

- **Don't use basic roles beyond sandboxes.** `roles/editor` means "mutate every resource in scope," which makes binding review meaningless. Migration cost is front-loaded; incident cost compounds.
- **Don't create custom roles when a predefined role is close.** You take permanent ownership of permission drift as Google evolves its own.
- **Don't rely on groups where revocation speed matters.** Propagation delay (minutes to tens of minutes, ~) makes group grants the slow path; direct bindings are the fast path.
- **Don't treat org policy as request-time security.** It gates configuration writes only; resources created before enforcement stay non-compliant until changed. Pair deploy-time guardrails with deny policies for request-time guarantees.
- **Don't assume deny coverage.** Deny-supportable permissions are a subset of IAM permissions; verify before promising a control.
- **Don't make PAB your only exfiltration control.** Service coverage is partial and evolving; VPC Service Controls still owns the network-perimeter case. They compose rather than substitute.
- **Where keys remain defensible:** genuinely air-gapped systems and third-party appliances accepting only key files. Scope tightly (dedicated SA, minimal roles), store in Secret Manager, rotate on schedule, alert on age over 90 days (~) — and say out loud in review that this is tolerated debt, not a pattern.

---

## Interview questions

### Q1 — Walk me through how GCP evaluates an IAM request.
**Testing:** whether you know there is an order at all, versus "it checks allows."
**Answer:** Deny policies first: a matching deny rule on any applicable org/folder/project ends the request unless the caller is an exception principal. Then allow policies: one binding anywhere in the inherited chain granting a role containing the permission, with its CEL condition satisfied, produces allow. Then principal access boundary policies, if bound: the target resource must be inside the principal's eligibility set. Default is deny everywhere.
**Follow-up trap:** *"Where do Organization Policies fit?"* — they don't evaluate on the request path at all; they gate configuration writes (CREATE/UPDATE). A constraint can stop you creating a public bucket, but it isn't what checks your read of an existing object.

### Q2 — Why does everyone say service-account keys should be eliminated? What replaces them?
**Testing:** whether "no keys" is a slogan or a design.
**Answer:** Keys are long-lived bearer credentials — up to 10 downloadable per SA, no expiry by default, no attribution in logs — so leakage equals identity theft until manually revoked. Replacement depends on where code runs: attached service accounts plus the metadata server for Google-hosted compute, GKE Workload Identity for pods, and Workload Identity Federation (OIDC/SAML/AWS providers through STS) for everything external including CI. All three issue ~1-hour tokens continuously instead of storing anything.
**Follow-up trap:** *"You can rotate keys every 90 days — isn't that enough?"* — rotation shortens exposure but doesn't fix attribution, doesn't help if the leak went undetected for 89 days, and rotation automation is its own failure surface. Elimination removes the credential class; rotation manages it.

### Q3 — `iam.serviceAccountUser` vs `iam.serviceAccountTokenCreator` — difference, and why does it matter?
**Testing:** the actAs/mint distinction, which separates operators from readers.
**Answer:** User grants `iam.serviceAccounts.actAs`: attaching the SA to a resource at creation time (VM, Cloud Run service, function). TokenCreator grants direct token minting (`generateAccessToken`, `generateIdToken`, `signJwt`) — full impersonation without launching anything. TokenCreator is strictly more dangerous per grant because it collapses the indirection; both mint ~3600-second tokens by default.
**Follow-up trap:** *"A pipeline needs to run jobs as a service account — which one?"* — usually actAs via User (attach at job-submission time); TokenCreator only when something genuinely must sign tokens or ID tokens for downstream OIDC validation.

### Q4 — Explain GKE Workload Identity mechanically, plus its classic misconfiguration.
**Testing:** mechanism recall under pressure.
**Answer:** Cluster has Workload Identity Federation enabled; node pools run workload metadata config so pod metadata requests are intercepted by a metadata emulator. A pod using Kubernetes SA "backend" annotated `iam.gke.io/gcp-service-account: backend-prod@...` presents a KSA-signed credential to STS; GCP validates it because `roles/iam.workloadIdentityUser` is bound to `principal://iam.googleapis.com/projects/N/clusters/C/namespaces/ns/sa/backend`; STS returns a Google token carrying the GSA's permissions. Classic misconfiguration: binding the role to the namespace-wide principal instead of the specific KSA, letting every workload in that namespace impersonate the account.
**Follow-up trap:** *"Why not mount a key as a K8s secret like before?"* — secret-mounting reintroduces a long-lived downloadable credential with no expiry and no attribution, leaks via etcd dumps/logs, and needs rotation plumbing; the point of WI is that nothing durable exists to steal.

### Q5 — Set up GitHub Actions deploys to GCP with zero stored secrets. What are the failure modes?
**Testing:** real WIF design experience.
**Answer:** Create a workload identity pool; an OIDC provider with issuer `https://token.actions.githubusercontent.com`; attribute mappings `google.subject=assertion.sub` plus repository/owner claims; an attribute condition restricting exchange to your org (ideally by numeric owner id); bind `roles/iam.workloadIdentityUser` to a principalSet filtered on `attribute.repository` for the specific repo, impersonating a dedicated deploy SA holding only deployment roles. Failure modes: missing attribute condition (any repo on GitHub can attempt exchange), pool-wide binding without repo filter, reassignable names in conditions, over-privileged deploy SAs.
**Follow-up trap:** *"Why prefer `repository_owner_id` over `repository_owner`?"* — GitHub names can be released and reclaimed after account deletion; numeric IDs are immutable. A mutable claim means your trust anchor can change hands without any GCP-side edit.

### Q6 — Org Policy vs deny policy vs Principal Access Boundary — when do you reach for each?
**Testing:** whether three overlapping-sounding controls collapse into one blob in their head.
**Answer:** Org policy: configuration guardrails evaluated at CREATE/UPDATE ("no one may ever configure X"), inherited down the tree, dry-run supported. Deny policy: request-time hard stop on specific permissions regardless of any allow, with exception principals for break-glass. PAB: request-time cap on which *resources* a principal may touch at all, independent of permissions held. Stack: org policy prevents bad configurations being born; deny protects the most dangerous actions on existing ones; PAB contains identity misuse across project boundaries.
**Follow-up trap:** *"Which one stops a compromised admin from exfiltrating BigQuery data to an external project?"* — none fully alone: deny can block specific export permissions where covered, PAB blocks access outside the boundary where supported, VPC Service Controls blocks the API egress path. Honest answer: layered defense, each covering holes the others leave.

### Q7 — When would you build a custom role, and what does it cost you?
**Testing:** judgment beyond "least privilege good."
**Answer:** Only when no predefined role approximates the need — typically a narrow operational persona (redeploy Cloud Run revisions but not touch traffic splitting or IAM). Cost: quota (~300 per org and ~300 per project, ~), permanent maintenance as permissions evolve, drift risk — a custom role frozen two years ago silently misses newer, safer permissions. Mitigate with an owner, a review cycle, Recommender cross-checks.
**Follow-up trap:** *"Your custom role has `storage.objects.create` but a new feature needs a newer permission. What happens?"* — features fail with PERMISSION_DENIED despite the role looking correct; this is why predefined-first wins — Google updates predefined roles in place, your YAML never notices.

### Q8 — A deploy pipeline suddenly gets PERMISSION_DENIED after months of working. Debug method?
**Testing:** structured debugging, not guesswork.
**Answer:** First confirm the actual calling principal from the audit log entry — pipelines often run as a different identity than assumed (wrong SA, federated subject vs SA confusion). Then Policy Troubleshooter with that principal/permission/resource: it returns the deciding factor — binding removed, condition now false (check time/resource-tag expressions), deny policy added, or PAB boundary applied. Then diff recent Terraform applies and org-policy changes; a newly enforced constraint explains many "nothing changed" incidents.
**Follow-up trap:** *"Troubleshooter says allow, the call still fails."* — the tool evaluates IAM only; failures can come from layers it doesn't cover: VPC Service Controls perimeter denial, org-policy enforcement on a write, CMEK key-permission issues, or quota. The error string distinguishes these — read it before theorizing.

### Q9 — What's wrong with the Compute Engine default service account, concretely?
**Testing:** estate reality, not docs recitation.
**Answer:** Historically auto-granted `roles/editor` project-wide; still used implicitly whenever a service leaves the SA field blank, so workloads inherit whatever it holds; shared across every workload in the project so attribution dies; and because it's convenient, people keep adding grants to it. Modern posture: dedicated per-workload SAs, project creation defaults that skip the automatic Editor grant (configurable since ~2024), blank-SA fields treated as review findings.
**Follow-up trap:** *"It still has editor across a 500-project legacy estate — migration plan?"* — inventory actual API usage per default SA from audit logs first, create replacements with observed-minimal roles, roll service-by-service behind a flag, then enforce via org policy/deny. Measurement before removal, or something breaks at 3am.

### Q10 — Two real uses of IAM Conditions and their gotchas.
**Testing:** whether conditions are a tool or trivia.
**Answer:** Use one: environment-scoped access — same group, binding active only when `resource.name` matches a prefix or resource tags match `env=staging`, collapsing role sprawl. Use two: time-boxed contractor access via `request.time` bounds. Gotchas: expressions fail closed (a malformed tag comparison denies everyone), time conditions don't revoke already-minted tokens, tag-based conditions break if someone edits tags outside change control.
**Follow-up trap:** *"Can a condition shrink an already-granted session mid-session?"* — no; evaluation happens per API call but OAuth tokens minted earlier remain valid until expiry — which is why short-lived token issuance (WIF, impersonation) is the complement, not conditions alone.

### Q11 — An AWS-hosted workload must read GCS daily. Keyless design?
**Testing:** cross-cloud federation fluency.
**Answer:** Create an AWS provider in a workload identity pool with the AWS account ID; GCP validates the assertion via `sts:GetCallerIdentity` semantics; map attributes so `google.subject` derives from the assuming role ARN, narrowed further by attribute conditions; bind `workloadIdentityUser` to that principalSet on a reader SA holding objectViewer on the bucket. The workload assumes its AWS role, then exchanges an AWS-signed GetCallerIdentity request with GCP STS for a Google token. No AWS IAM user, no GCP key.
**Follow-up trap:** *"What actually authenticates the exchange — couldn't anything in that AWS account do it?"* — yes, anything able to assume the mapped role can exchange; account-level trust is coarse. Tighten by mapping the specific ARN plus conditions on it; the ceiling is the AWS side's own role hygiene.

### Q12 — Design tenancy isolation for a multi-customer SaaS on GCP.
**Testing:** senior synthesis across hierarchy, guardrails, operations.
**Answer:** Project-per-tenant-tier as the base (hard edges: IAM inheritance, quotas, networking defaults), shared services in dedicated projects reached via Shared VPC. Bind tenant-scoped roles to per-tenant workload identities — never one shared god-SA. Enforce domain-restricted sharing and public-access-prevention org-wide; apply PAB per tenant-facing principal set where service coverage exists; wrap the data estate in VPC Service Controls so even valid credentials cannot cross the perimeter from outside. Human break-glass via PAM with time-bound grants.
**Follow-up trap:** *"Why projects instead of folder + tags + conditions everywhere?"* — conditions and PAB reduce binding sprawl but are newer, partially covered surfaces; project boundaries are the oldest, hardest isolation primitive on GCP. Start with hard edges; layer conditions/PAB as refinement, not as the primary wall.

### Q13 — What does `roles/editor` actually include that surprises people?
**Testing:** whether "basic roles" is understood as a legacy artifact.
**Answer:** Editor is view-plus-mutate across essentially every service in scope — including actions with security consequences like creating and modifying service account keys (via the underlying permissions) in the era before dedicated constraints, changing firewall rules, and deleting data. It predates granular IAM and exists only because it shipped first; Google's own guidance has said for years to prefer predefined roles.
**Follow-up trap:** *"'Viewer' is safe then?"* — mostly, but Viewer on a project still exposes all metadata and data-readable-through-list APIs across services, which for many estates includes sensitive config. "Safe" depends on what reading costs you.

### Q14 — Someone proposes managing everything through groups because "it's how we did AD." Push back.
**Testing:** operational judgment about GCP-specific latency and auditability.
**Answer:** Groups are fine as the slow-path human layer synced from the IdP. Pushback points: membership changes propagate with meaningful delay (~minutes, sometimes tens of minutes), which breaks fast revocation and breaks CI that expects instant effect; group nesting complicates Policy Analyzer expansions; and workload identities should bind directly, not via groups, so audit trails and Troubleshooter output stay precise.
**Follow-up trap:** *"How do you keep direct bindings from exploding in count?"* — conditions (tag/prefix-scoped bindings), PAB for resource-set capping, and role design: one well-chosen predefined role bound once beats five narrow ones bound everywhere.

---

## Red flags that fail you

- Saying GCP IAM "works like AWS" — deny policies, org policy, PAB, and the single-policy-per-resource model are structurally different from SCPs/RCPs/boundaries.
- Recommending downloadable service-account keys for any new integration in 2026.
- Confusing `serviceAccountUser` (actAs) with `serviceAccountTokenCreator` (mint).
- Describing Workload Identity Federation without attribute conditions or principalSet selectors.
- Claiming org policy blocks request-time access — it gates configuration writes only.
- Granting `roles/editor` or default SAs as a "pragmatic" default without flagging the debt.
- Not knowing that deny policies outrank every allow, including Owner.

## Cheat card

```
HIERARCHY: org -> folder(s) -> project -> resource; bindings inherit DOWNWARD
EVAL:      deny policy (request-time, outranks all) -> ANY allow binding
           (one suffices, CEL condition must pass) -> PAB resource-eligibility
           -> default deny.  Org Policy = deploy-time (CREATE/UPDATE) guardrail.

ROLES:     basic (owner/editor/viewer = legacy, avoid) | predefined (default)
           | custom (~300/org, ~300/project, drift risk)
CONDITIONS: CEL on bindings: resource.name/tags, request.time; fail closed;
            do NOT revoke already-minted tokens

SA DUALITY: identity (gets roles) AND resource (actAs to use)
  serviceAccountUser       = actAs: attach SA to VM/Run/Fn   (= AWS PassRole)
  serviceAccountTokenCreator = mint tokens directly (worse per grant)
  default SAs: PROJECT_NUMBER-compute@developer... / PROJECT_ID@appspot...
  keys: max 10 per SA, no default expiry -> eliminate via org policy ban

CREDENTIALS: on Google compute -> attached SA + metadata server (169.254.169.254,
             ~1h tokens). GKE pods -> KSA annotated iam.gke.io/gcp-service-account,
             workloadIdentityUser bound to principal://.../sa/<ksa>.
             Outside -> WIF: pool+provider, attribute.mapping + attribute.condition,
             principalSet selector on binding; OIDC/SAML/AWS/X.509; ~1h tokens.

GUARDRAILS: org policy boolean/list/custom(CEL since 2023), dry-run first
            deny policies: attachment org/folder/project, exceptionPrincipals,
            permission subset only. PAB: subtractive resource cap, partial coverage.
DEBUG:      Troubleshooter (why denied) / Analyzer (who has X) / Recommender (90d)
```

## Sources

- [Workload Identity Federation — Google Cloud IAM docs](https://docs.cloud.google.com/iam/docs/workload-identity-federation); accessed 2026-08-23
- [Best practices for using Workload Identity Federation](https://docs.cloud.google.com/iam/docs/best-practices-for-using-workload-identity-federation); accessed 2026-08-23
- [Principal access boundary policies — Google Cloud IAM docs](https://docs.cloud.google.com/iam/docs/principal-access-boundary-policies); accessed 2026-08-23
- [Build defense in depth with IAM Deny and Org Policies — Google Cloud blog](https://cloud.google.com/blog/products/identity-security/just-say-no-build-defense-in-depth-with-iam-deny-and-org-policies); accessed 2026-08-23
- [Creating and managing custom organization policy constraints](https://docs.cloud.google.com/resource-manager/docs/organization-policy/creating-managing-custom-constraints); accessed 2026-08-23
- [How to replace service account keys with Workload Identity Federation](https://oneuptime.com/blog/post/2026-02-17-how-to-replace-service-account-keys-with-workload-identity-federation-in-gcp/view); accessed 2026-08-23
- [How to create IAM deny policies for security guardrails](https://oneuptime.com/blog/post/2026-02-17-how-to-create-iam-deny-policies-to-enforce-security-guardrails-in-google-cloud/view); accessed 2026-08-23

## Changelog

- 2026-08-23 — created
