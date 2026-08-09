# IAM Deep: Policy Evaluation Logic, AssumeRole/STS, Boundaries, SCPs

> **Track:** C-AWS AWS Atlas · **Time:** 3.0h · **Prereqs:** none · **Updated:** 2026-08-01
> **Module id:** `C-AWS-iam` · **Tags:** security,critical

## Why this gets asked

Every principal-level AWS interview has an IAM segment, because IAM is the one service where a design mistake is invisible until an incident makes it visible, and by then it is either a breach or an outage. The interviewer has personally debugged a `AccessDenied` that made no sense given the identity policy, and traced it to an SCP, a permissions boundary, or a resource policy nobody remembered existed. They have also, more likely than not, cleaned up after `iam:PassRole` was handed out too broadly and someone escalated to admin through a Lambda execution role. The question is never "what is IAM" — it's "can you reconstruct the evaluation order from memory, under pressure, while a request is actually being denied in front of you."

---

## Lineage: past → present → future

**What came before.** AWS launched in 2006 with a single set of account root credentials — one login, full access to everything, shared across a whole engineering org. IAM shipped in 2010 specifically because customers were emailing root passwords to contractors and hardcoding root keys into EC2 user-data. The initial IAM model was users, groups, and policies — a flat permissions model borrowed from on-prem RBAC. It solved "stop sharing root" but not "stop long-lived credentials leaking," which remained the dominant AWS breach vector for the next decade (Capital One 2019, Uber 2016 — both rooted in credentials that should have been temporary).

**Where it stands now.** The consensus mechanism for eliminating long-lived credentials is STS-issued temporary credentials via role assumption: EC2 instance profiles, IRSA/Pod Identity for EKS, and OIDC federation for CI. AWS's own tooling nudges this — IAM Identity Center for human access, `AssumeRoleWithWebIdentity` for workloads. The live disagreement is at the org-guardrail layer: Service Control Policies (SCPs) have existed since 2015 and cap what any identity policy can ever grant across an OU; **Resource Control Policies (RCPs)**, GA'd in November 2024, close the gap SCPs never covered — SCPs cannot restrict what a resource-based policy grants to an external principal, RCPs can. Most organizations have SCPs deployed and are only now rolling out RCPs, so "have you used RCPs" is a genuine signal of currency, not just study. [Introducing resource control policies (RCPs)](https://aws.amazon.com/about-aws/whats-new/2024/11/resource-control-policies-restrict-access-aws-resources) — accessed 2026-08-01.

**Where it's heading.** EKS Pod Identity (GA 2023) is AWS's stated direction for workload identity on Kubernetes, replacing the OIDC-trust-policy dance of IRSA with an EKS-managed auth API — confident this is where new clusters go, though IRSA has no deprecation date and huge existing footprint. [EKS Pod Identity announcement](https://aws.amazon.com/blogs/containers/amazon-eks-pod-identity-a-new-way-for-applications-on-eks-to-obtain-iam-credentials/) — accessed 2026-08-01. More speculatively: continuous, automated least-privilege via IAM Access Analyzer policy generation is maturing from "suggestion tool" toward "CI-gate," and expect more of the industry's static-key incidents to keep IAM roles and short-lived tokens as the default framing rather than an advanced pattern.

---

## Mental model

Think of an IAM request as passing through gates that can each say "no," and only one gate that can say "yes":

```
REQUEST
   │
   ▼
[1] Explicit DENY anywhere (any layer)? ──yes──▶ DENY (stop, no further checks)
   │ no
   ▼
[2] SCP (Org) — does it ALLOW this action? ──no──▶ DENY
   │ yes (SCPs are allow-lists: silence = implicit deny)
   ▼
[2b] RCP (Org, resource-side) — does it ALLOW? ──no──▶ DENY
   │ yes
   ▼
[3] Resource-based policy present & explicitly ALLOWs? ──yes──▶ ALLOW (skips 4-6 for same-account principal)
   │ no explicit allow here (fall through to identity side)
   ▼
[4] Permissions boundary attached? ──yes, must ALLOW too (intersection) ──not present in boundary──▶ DENY
   │ boundary allows or none attached
   ▼
[5] Session policy present (from AssumeRole call)? ──must ALLOW too (intersection) ──▶ DENY if not
   │ allows or none attached
   ▼
[6] Identity-based policy — explicit ALLOW? ──no──▶ DENY (default deny)
   │ yes
   ▼
ALLOW
```

**The one sentence that matters:** every applicable layer must either be silent-and-irrelevant or explicitly allow, and if *any* layer explicitly denies, that wins immediately regardless of every other layer. SCPs, RCPs, and permissions boundaries can only take away — they never grant permission by themselves, they cap what identity/resource policies are allowed to grant. [Policy evaluation logic — AWS IAM docs](https://docs.aws.amazon.com/IAM/latest/UserGuide/reference_policies_evaluation-logic.html) — accessed 2026-08-01.

---

## How it actually works

### The evaluation order, precisely

1. **Explicit deny, anywhere.** A `Deny` statement in an SCP, RCP, resource policy, permissions boundary, session policy, or identity policy ends the request immediately. This is why "just add a deny" is the correct answer to "block this one dangerous action even though the role has `*`."
2. **SCPs.** Organization-level allow-lists attached to the account, OU, or root. If the SCP doesn't explicitly allow the action (default `FullAWSAccess` SCP allows everything, but custom SCPs typically don't), no identity policy in that account can ever grant it — SCPs bound the *ceiling*.
3. **RCPs.** Same ceiling concept as SCPs but evaluated against the *resource* side of the request — they restrict what a resource-based policy can grant to a principal, including principals in other accounts. This is the piece SCPs structurally cannot do, because SCPs only apply to principals in the org, and a resource policy can grant access to a principal *outside* the org.
4. **Resource-based policies.** An S3 bucket policy, an SNS topic policy, a KMS key policy. If the resource policy explicitly allows a principal (including a same-account one), that alone can satisfy the identity-side check for cross-account access — the classic case being "the bucket policy grants account B read access; account B's own identity policy doesn't even need to mention this bucket."
5. **Permissions boundaries.** A managed policy attached to a *user or role* (not a group) that caps the maximum permissions that identity's own policies can grant. The effective permission is the **intersection** of the identity policy and the boundary — the boundary never grants anything by itself.
6. **Session policies.** Passed inline at `AssumeRole`/`GetFederationToken` call time. Same intersection logic as boundaries, scoped to that one session.
7. **Identity-based policies.** The policies attached to the user, group, or role. If none of the above denied, and at least one identity-based statement (or the resource policy, for cross-account) explicitly allows, the result is `Allow`. Otherwise: **default deny.** IAM has no notion of "permit unless denied" — silence is always deny.

### Cross-account access needs both sides

This is the single most common conceptual gap. To let account B's role read a bucket in account A:

- Account A's **bucket policy** must grant account B's principal `s3:GetObject`.
- Account B's **identity policy** (on the role B is using) must also grant `s3:GetObject` on that bucket ARN.

Missing either side is `AccessDenied`. The resource policy alone is not sufficient for a *different-account* principal (same-account principals can rely on the resource policy alone) — you need explicit allow on both, because from account B's side, the identity policy still gates what that principal is permitted to ask for at all.

```json
// Account A bucket policy (resource-based) — grants account B
{
  "Effect": "Allow",
  "Principal": {"AWS": "arn:aws:iam::222222222222:role/ReaderRole"},
  "Action": "s3:GetObject",
  "Resource": "arn:aws:s3:::shared-bucket/*"
}
```
```json
// Account B identity policy on ReaderRole — must also allow it
{
  "Effect": "Allow",
  "Action": "s3:GetObject",
  "Resource": "arn:aws:s3:::shared-bucket/*"
}
```

### AssumeRole, STS, and the confused deputy

`sts:AssumeRole` exchanges a caller's identity for temporary credentials (default 1 hour, configurable 15 min–12 hr via `DurationSeconds`, hard cap set by the role's `MaxSessionDuration`) scoped to a role's own permissions. The role's **trust policy** (a resource-based policy on the role itself) decides who is allowed to assume it:

```json
{
  "Effect": "Allow",
  "Principal": {"AWS": "arn:aws:iam::111111111111:root"},
  "Action": "sts:AssumeRole",
  "Condition": {"StringEquals": {"sts:ExternalId": "cust-7f3a91"}}
}
```

**The confused deputy problem** this solves: a third-party SaaS vendor (a "deputy" with legitimate access to many customers' AWS accounts) could be tricked into acting on the wrong customer's behalf if two customers unknowingly reuse the same role ARN reference, or if the vendor's own account ID is guessable and someone crafts a request pretending to be the vendor. `sts:ExternalId` is a shared secret the customer puts in the trust policy and the vendor must supply on every `AssumeRole` call for that customer — without it, one confused or compromised deputy call could touch the wrong tenant. Independent research found **37% of vendors did not implement `ExternalId` correctly**, and another 15% implemented it in the UI but never validated it server-side. [Demystifying AssumeRole and sts:ExternalId — NCC Group](https://www.nccgroup.com/research/demystifying-aws-assumerole-and-stsexternalid/) — accessed 2026-08-01.

### Workload identity: three patterns, no static keys

| Pattern | Mechanism | Use case |
|---|---|---|
| **Instance profile** | EC2 instance metadata service hands the instance temporary creds tied to a role | Any EC2-based workload |
| **IRSA** | EKS annotates a K8s service account with a role ARN; pod's projected token is exchanged via `AssumeRoleWithWebIdentity` against the cluster's OIDC provider | EKS, launched 2019, huge existing footprint |
| **EKS Pod Identity** | EKS Auth API + a Pod Identity Agent DaemonSet issue creds directly; no per-cluster OIDC trust policy needed, so one role is portable across clusters | EKS, GA 2023, AWS's current recommendation for new workloads |
| **OIDC federation** | GitHub Actions / GitLab CI presents a signed OIDC token; the role trust policy validates the issuer and `sub` claim, then `AssumeRoleWithWebIdentity` | CI/CD pipelines needing AWS access with zero stored secrets |

IRSA and Pod Identity both eliminate the older, worse pattern: mounting a static access key as a Kubernetes secret. [IRSA vs Pod Identity — AWS Containers blog](https://aws.amazon.com/blogs/containers/amazon-eks-pod-identity-a-new-way-for-applications-on-eks-to-obtain-iam-credentials/) — accessed 2026-08-01.

### Permissions boundaries vs SCPs — who is each for

| | SCP | Permissions boundary |
|---|---|---|
| Attached to | Account, OU, org root | Individual user or role |
| Set by | Central platform/security team | Same team, but scoped per-identity, often for delegation |
| Typical use | "No account in this OU may ever disable CloudTrail" | "This role, which a self-service pipeline creates, may never exceed X even if a developer over-grants its identity policy" |
| Can be self-escalated by an account admin? | No — org management account only | Yes if the admin also controls the boundary policy, which is why it's for *delegated* admin, not external attackers |

The boundary's real job is enabling **delegated IAM administration**: let an app team create their own roles and policies via CI, but cap what those self-service roles can ever become, without central security reviewing every PR.

### Condition keys that actually matter

- **`aws:SourceArn`** — restricts to exactly one resource (e.g., "only this specific SNS topic may invoke this Lambda"). Most restrictive, preferred for confused-deputy prevention on service-to-service calls.
- **`aws:SourceAccount`** — restricts to any resource in a given account. Looser than `SourceArn`; use when the exact resource ARN isn't known ahead of time but the account is fixed.
- **`aws:PrincipalOrgID`** — restricts to any IAM principal that belongs to a given AWS Organization, regardless of which account within it. Used for org-wide data perimeters ("only my org's accounts may read this bucket"), not for single-resource confused-deputy prevention.

Conflating `SourceAccount` with `PrincipalOrgID` is a common mistake: the former is about which account a *resource* lives in when a service calls on your behalf, the latter is about which org a *calling principal* belongs to.

### `iam:PassRole` — the quiet privilege escalation

`iam:PassRole` doesn't grant access to any AWS resource by itself — it grants the right to *hand a role to a service* (EC2 launch, Lambda creation, ECS task definition). If a user can `iam:PassRole` an admin-capable role and can also create a Lambda function, they can create a Lambda with that role attached, write a handler that does anything the role permits, and invoke it — full escalation without ever being granted the underlying permissions directly. This is why `iam:PassRole` should always be scoped with `iam:PassedToService` and a resource ARN condition, never left as `"Resource": "*"`.

```json
{
  "Effect": "Allow",
  "Action": "iam:PassRole",
  "Resource": "arn:aws:iam::123456789012:role/lambda-exec-role-*",
  "Condition": {"StringEquals": {"iam:PassedToService": "lambda.amazonaws.com"}}
}
```

### Debugging "why is this denied" — the method

1. **Read the actual error**, not just "AccessDenied." `aws sts get-caller-identity` to confirm which principal is actually making the call — it is very often not the one you assumed (wrong profile, wrong assumed role).
2. **Run IAM Policy Simulator** or `aws iam simulate-principal-policy` against the exact action + resource ARN.
3. **Check for an explicit deny first** — grep every attached policy, SCP, RCP, and permissions boundary for `"Effect": "Deny"` before anything else, since one deny anywhere ends the search.
4. **Check CloudTrail** for the denied event — the `errorMessage` field frequently names which policy type caused it (`explicit deny in an identity-based policy`, `explicit deny in a service control policy`) as of the newer CloudTrail message format.
5. **Walk the six layers in order**: SCP allows it? RCP allows it? Resource policy relevant? Boundary intersects it? Session policy (if assumed) intersects it? Identity policy allows it? The first "no" in that chain is your answer.
6. **For cross-account**, verify both sides independently — simulate as if you were each account.

### Access Analyzer

IAM Access Analyzer statically analyzes resource policies to find any that grant access to an external entity (another account, the public, an untrusted org), and separately can generate a least-privilege policy from a role's actual CloudTrail activity over an observation window. It doesn't evaluate SCPs/RCPs for you — its "external access" findings are about resource policies granting outside the zone of trust you define, and its "unused access" findings flag over-permissioned identity policies. Not a policy simulator, not a real-time blocker — a periodic finder.

---

## Build it from scratch

A minimal "evaluate this request" function, the shape of what the interviewer may ask you to reason through on a whiteboard:

```python
# untested sketch
def evaluate(request, scps, rcps, resource_policy, boundary, session_policy, identity_policies):
    all_layers = scps + rcps + [resource_policy, boundary, session_policy] + identity_policies
    # 1. explicit deny anywhere wins immediately
    for policy in all_layers:
        if policy and policy.explicitly_denies(request):
            return "Deny"

    # 2. SCP/RCP must allow (ceiling, not grant)
    if scps and not any(p.explicitly_allows(request) for p in scps):
        return "Deny"
    if rcps and not any(p.explicitly_allows(request) for p in rcps):
        return "Deny"

    # 3. resource policy can satisfy same-account or cross-account allow directly
    if resource_policy and resource_policy.explicitly_allows(request):
        return "Allow"

    # 4/5. boundary and session policy narrow via intersection, never grant alone
    if boundary and not boundary.explicitly_allows(request):
        return "Deny"
    if session_policy and not session_policy.explicitly_allows(request):
        return "Deny"

    # 6. identity policy must explicitly allow; default deny otherwise
    if any(p.explicitly_allows(request) for p in identity_policies):
        return "Allow"
    return "Deny"  # implicit default deny — no policy said yes
```

---

## How it's done in production

Most orgs run this stack: **AWS Organizations + SCPs** for guardrails (deny `iam:CreateAccessKey` org-wide, deny leaving the org, deny disabling CloudTrail/GuardDuty), **RCPs** for data-perimeter enforcement (only org principals or specific external accounts can ever be granted access via a resource policy, closing the loophole where a compromised or careless engineer attaches a public bucket policy), **Permission Sets in IAM Identity Center** for human SSO access instead of IAM users, **Terraform/CDK-managed roles** with permissions boundaries for any self-service role creation, and **Access Analyzer** wired into CI to fail a PR that introduces a new external-access finding.

| Symptom | Cause | Fix |
|---|---|---|
| `AccessDenied` despite identity policy clearly allowing it | SCP or RCP doesn't allow the action at the org/account ceiling | Check SCPs/RCPs first; identity policy is irrelevant if the ceiling denies |
| Works for account A's role, fails for account B's identical role on the same resource | Resource policy grants A but not B, or B's own identity policy never explicitly allows it | Verify both sides of cross-account access independently |
| Role assumable by anyone who guesses the ARN | Trust policy has no `ExternalId` or IP/org condition | Add `sts:ExternalId` condition, scope `Principal` tightly |
| Developer's self-service role ends up with admin | `iam:PassRole` granted with `Resource: "*"` and no `iam:PassedToService` condition | Scope PassRole to specific role ARNs and target service |
| EKS pod can't reach S3 despite IRSA annotation | OIDC provider not registered for the cluster, or service account annotation ARN typo | `eksctl utils associate-iam-oidc-provider`, verify annotation matches trust policy `sub` claim exactly |
| CI pipeline stores a long-lived AWS key that eventually leaks | No OIDC federation set up, static key used instead | Move to GitHub/GitLab OIDC + `AssumeRoleWithWebIdentity`, delete the key |

---

## Tradeoffs & when NOT to use it

- **Don't use permissions boundaries as a substitute for SCPs.** Boundaries are per-identity and opt-in per role; a forgotten boundary on a newly created role provides zero protection. SCPs are mandatory and inherited from the OU — use them for anything that must never be bypassable.
- **Don't use IAM users with long-lived access keys for anything new.** Every legitimate pattern today (human access via Identity Center SSO, workload access via role assumption) uses temporary credentials. A new IAM user with an access key in 2026 is close to always the wrong answer in an interview and in production.
- **Don't reach for single-role-does-everything simplicity in multi-tenant SaaS.** It optimizes onboarding speed at the cost of the confused-deputy problem being structurally probable rather than a remote edge case — enforce `ExternalId` and per-tenant role ARNs from day one.
- **RCPs are not a replacement for SCPs** — they cover different evaluation points (resource-side ceiling vs identity-side ceiling) and most real data-perimeter designs need both.
- **Don't over-rotate to condition-key gymnastics when the real fix is fewer, more specific roles.** A single role with a dozen conditions trying to serve five use cases is harder to audit than five narrow roles.

---

## Interview questions

### Q1 — Walk me through IAM's full policy evaluation order.
**Testing:** whether you actually know the order or are pattern-matching "explicit deny wins."
**Answer:** Explicit deny anywhere ends it immediately. Then SCPs must allow (ceiling). Then RCPs must allow (resource-side ceiling). Then a resource-based policy, if present, can directly satisfy the allow (including for cross-account). Then a permissions boundary, if attached, must also allow — as an intersection, not a grant. Then a session policy, if this is an assumed-role session, same intersection logic. Finally the identity-based policy must explicitly allow. If nothing explicitly allowed, default deny.
**Follow-up trap:** *"Where do RCPs fit relative to resource policies?"* — RCPs are evaluated as an org-level ceiling before the resource policy is consulted; a resource policy can never grant something an RCP has capped, exactly like SCPs cap identity policies.

### Q2 — Two customers, one third-party SaaS vendor with `AssumeRole` access into both accounts. What stops the vendor's own bug from touching the wrong customer's account?
**Testing:** confused deputy understanding, not just the term.
**Answer:** `sts:ExternalId` in the trust policy condition, unique per customer, which the vendor must include on every `AssumeRole` call. Without it, a vendor bug that reuses the wrong stored role ARN could act on the wrong tenant's resources with valid credentials, because AWS itself has no way to know the calls are "supposed" to be scoped per-customer — the ExternalId is the only signal.
**Follow-up trap:** *"Is ExternalId a secret?"* — treat it as one operationally (don't leak it in logs), but it's not a substitute for authentication; it's a shared value that prevents *accidental* misrouting, not a determined attacker with the vendor's actual credentials.

### Q3 — A role has `s3:*` in its identity policy. It still can't touch a bucket. Why?
**Testing:** understanding boundaries/SCPs as ceilings, not just naming them.
**Answer:** Something above the identity policy is denying or failing to allow: an SCP not explicitly allowing `s3:*` at the OU/account level, an RCP restricting the resource side, a permissions boundary attached to the role that doesn't include S3, or an explicit deny anywhere. Since identity policy is evaluated last and the effective permission is always the intersection with boundary/SCP/RCP, a generous identity policy is necessary but not sufficient.
**Follow-up trap:** *"You check all of those and none apply. What's left?"* — check the bucket's own policy for an explicit deny (bucket policies can deny same-account principals too), and check whether the bucket has a VPC endpoint policy or Object Lock in a mode that blocks the operation regardless of IAM.

### Q4 — Design least-privilege for a self-service platform where app teams create their own IAM roles via Terraform in CI.
**Testing:** whether you know permissions boundaries exist for delegation, not just for restriction.
**Answer:** Attach a mandatory permissions boundary to every role the CI pipeline is allowed to create, enforced by an SCP-level condition requiring `iam:PermissionsBoundary` on `CreateRole`/`CreatePolicy` calls. App teams can then write arbitrarily generous-looking identity policies on their own roles; the boundary intersection caps the actual blast radius regardless of what they attach. Central security reviews the boundary policy once, not every team's PR.
**Follow-up trap:** *"What stops a team from creating a role without the boundary?"* — an SCP that denies `iam:CreateRole` unless the request includes the required `PermissionsBoundary` parameter; without that enforcement the boundary is opt-in and someone eventually forgets it.

### Q5 — Why is `iam:PassRole` dangerous, and how do you scope it safely?
**Testing:** the quiet privilege-escalation path most candidates never mention unprompted.
**Answer:** `PassRole` grants the ability to attach a role to a service resource (EC2 instance, Lambda function, ECS task) without granting the underlying permissions of that role directly — so if a user can `PassRole` an admin-capable role and can create a Lambda, they get admin by writing code that runs with that role, entirely bypassing whatever narrower identity policy they were actually given. Scope it with a `Resource` condition to specific role ARNs (or a naming convention with wildcard) and `iam:PassedToService` to the specific service, never `Resource: "*"`.
**Follow-up trap:** *"Your scoped PassRole still allows passing 'lambda-exec-role-*'. Is that safe?"* — only if every role matching that pattern is itself scoped to least privilege; a wildcard PassRole onto a wildcard role-naming convention just moves the escalation surface into "did someone ever create an over-permissioned role matching that pattern."

### Q6 — IRSA vs EKS Pod Identity. Which do you pick for a new cluster in 2026?
**Testing:** currency and whether you understand the actual mechanism difference, not just the names.
**Answer:** Pod Identity for new clusters — AWS's stated direction since GA in 2023. The trust relationship is managed by the EKS Auth API rather than a per-cluster OIDC trust policy, so one IAM role can be reused across multiple clusters without editing its trust policy, and the setup has fewer moving parts (no manual OIDC provider association). IRSA remains fully supported with no deprecation date and is what most existing fleets run, so "how do you migrate an existing IRSA cluster" is a fair follow-up, not a trick — the honest answer is "when there's a concrete reason (multi-cluster role reuse, ABAC), not reflexively."
**Follow-up trap:** *"Does Pod Identity remove the need for OIDC entirely?"* — for AWS workload identity, largely yes; it doesn't remove OIDC federation for *other* identity providers like GitHub Actions, which still uses `AssumeRoleWithWebIdentity` against GitHub's own OIDC issuer.

### Q7 — Explain the difference between `aws:SourceArn`, `aws:SourceAccount`, and `aws:PrincipalOrgID` with a concrete example of when each is correct.
**Testing:** precision — these get conflated constantly.
**Answer:** `SourceArn` restricts to one exact resource — "only my specific SNS topic `arn:...:my-topic` may invoke this Lambda," the strongest confused-deputy defense for a service-to-service trigger. `SourceAccount` restricts to any resource in a given account — use it when you trust the whole account but the exact resource ARN isn't fixed (e.g., any S3 bucket in account X may trigger this). `PrincipalOrgID` restricts by which *calling principal's* AWS Organization it belongs to, independent of account or resource — used for org-wide perimeters like "only principals inside my org can ever assume this role," regardless of which of the org's 200 accounts they're in.
**Follow-up trap:** *"Can you combine SourceArn and SourceAccount in one condition?"* — yes, and if you do, the account IDs must match between the two or the condition can never be satisfied; using both is occasionally done for defense-in-depth clarity even though `SourceArn` alone already implies the account.

### Q8 — A cross-account S3 read is failing. Debug it live.
**Testing:** the "why is this denied" method under time pressure.
**Answer:** First `aws sts get-caller-identity` to confirm the actual assumed role making the call — wrong profile is the single most common self-inflicted cause. Then check the bucket policy for an explicit allow naming that exact role ARN as principal. Then check the calling account's identity policy on that role for an explicit allow on the bucket/object ARN — cross-account access needs both sides granting it, resource policy alone doesn't suffice for the identity side's own gate. Then check for any explicit deny in an SCP on either account, since SCPs apply per-account and either side could be blocking it. Then run `simulate-principal-policy` with the exact action and resource to get AWS's own evaluation trace.
**Follow-up trap:** *"Simulator says Allow, real call still denies. Now what?"* — the simulator doesn't evaluate resource-based policies, SCPs, or RCPs in older API versions/some scenarios by default depending on which simulate call you use; check CloudTrail's `errorMessage` for the actual denying layer, which the simulator can miss.

### Q9 — What does a permissions boundary actually prevent, and what does it not prevent?
**Testing:** the "intersection, not grant" nuance.
**Answer:** It prevents the identity's *own* attached policies from ever exceeding the boundary — the effective permission is always `identity_policy ∩ boundary`. It does not grant anything by itself (a boundary with `s3:*` and an identity policy with nothing still yields nothing), and it does not protect against a resource-based policy separately granting that same identity access from the *resource* side in some scenarios, nor against someone with `iam:CreateRole`/`iam:PutRolePolicy` and no boundary-enforcement SCP simply creating a new, unbounded role.
**Follow-up trap:** *"So boundaries are useless without an SCP enforcing them?"* — not useless, but structurally incomplete: a boundary is a technical control on one identity, an SCP-enforced requirement that all created identities *have* a boundary is what makes the control organization-wide rather than best-effort.

### Q10 — When would you use SCPs vs RCPs for the same-sounding goal ("no data leaves the org")?
**Testing:** whether you understand what RCPs newly cover, since this is recent (Nov 2024 GA) and separates current knowledge from stale knowledge.
**Answer:** An SCP can stop identities *inside* the org from taking an action that would expose data (e.g., deny `s3:PutBucketPolicy` unless it includes an org-ID condition), but SCPs have no jurisdiction over what an external, non-org principal can be granted by a resource policy — if someone inside the org attaches a bucket policy granting a random external account, the SCP can restrict the *identity* making that PutBucketPolicy call, but historically nothing restricted the resource-side grant itself except manual review. RCPs directly cap what any resource policy in the account/OU can grant, regardless of which identity wrote it, closing that gap without relying on catching the identity-side action.
**Follow-up trap:** *"Do RCPs apply to every AWS service?"* — no, RCP support is service-by-service (S3, STS, SQS, KMS, Secrets Manager among the early set) — verify current coverage before promising it protects a specific resource type, since this list has been expanding and is one of the version-dependent facts worth a fresh check before an interview.

### Q11 — Your Lambda's execution role has zero explicit S3 permissions, yet it can read a specific bucket. How?
**Testing:** whether you remember resource-based policies can grant cross-principal access without identity-side grants, for same-account access specifically.
**Answer:** For a same-account principal, a resource-based policy (the bucket policy) explicitly allowing that role's ARN is sufficient on its own — same-account resource-policy grants don't require a matching identity-policy statement the way cross-account access does. This is a frequent source of "but I never granted that" confusion during audits: the grant lives on the resource, not the identity.
**Follow-up trap:** *"Is this a security smell?"* — often yes, because it makes permissions hard to discover by reading the role alone; Access Analyzer's external-access findings won't even flag it since it's same-account, so it typically requires explicitly auditing resource policies, not just IAM roles, during a review.

### Q12 — Someone proposes eliminating all IAM users in favor of Identity Center SSO plus role assumption everywhere. What breaks?
**Testing:** senior judgment about when the "obviously correct" modern pattern has real exceptions.
**Answer:** Break-glass emergency access still typically needs a small number of tightly controlled root/IAM-user credentials in a sealed process, because SSO federation itself can be a single point of failure (IdP outage, misconfigured trust). Some legacy third-party tools and older CI systems don't support role assumption or OIDC federation and genuinely need a scoped access key — the fix there is minimizing blast radius (narrow permissions, rotation, monitoring) rather than pretending it's zero-key, since the tool doesn't support that.
**Follow-up trap:** *"How do you monitor for someone quietly reintroducing IAM users?"* — an SCP denying `iam:CreateUser` org-wide except in a designated break-glass account, plus Config rules or Access Analyzer alerting on any user creation as an anomaly.

### Q13 — Explain how EKS Pod Identity actually gets credentials into a pod, mechanically.
**Testing:** whether "IRSA/Pod Identity" is a memorized term or an understood mechanism.
**Answer:** The EKS Pod Identity Agent runs as a DaemonSet on each node. A pod's service account is associated with an IAM role via the EKS Auth API (not a Kubernetes annotation read by a webhook, as IRSA does it). When the pod's SDK requests credentials, it calls the local Pod Identity Agent, which authenticates to the EKS Auth API on the pod's behalf and receives temporary STS credentials scoped to the associated role — the trust relationship lives in EKS's control plane, not in the IAM role's own trust policy referencing a specific cluster's OIDC provider.
**Follow-up trap:** *"What does this buy you that IRSA didn't?"* — role portability across clusters (no per-cluster trust-policy edit) and simpler ABAC via EKS-native tags on the association, at the cost of requiring the newer EKS add-on and node agent to be present.

### Q14 — Your organization wants to enforce that no S3 bucket anywhere in a 200-account org can ever be made public, even by an account admin. Design it.
**Testing:** applying SCPs/RCPs to a real guardrail design, not just defining them.
**Answer:** An SCP denying `s3:PutBucketPolicy` and `s3:PutBucketAcl` calls that would set public access, layered with **S3 Block Public Access** enabled at the *organization* level (a separate, purpose-built control, not IAM), which overrides any bucket-level ACL or policy regardless of what IAM would otherwise allow. Belt-and-suspenders: SCP prevents the attempt at the API-call layer, Block Public Access prevents the *effect* even if some future service bypasses the SCP path.
**Follow-up trap:** *"Why not rely on the SCP alone?"* — an SCP only stops the specific actions you enumerate; a new API or a service feature that changes bucket exposure without going through `PutBucketPolicy`/`PutBucketAcl` would slip past a narrowly-written SCP, whereas Block Public Access is enforced at the S3 data-plane level regardless of how public access was attempted.

### Q15 — What's the actual difference between "least privilege" as a principle and Access Analyzer's "unused access" feature as a tool?
**Testing:** whether you can separate the goal from one implementation of it, and know the tool's limits.
**Answer:** Least privilege is the target state: every identity has exactly the permissions its actual workload needs, no more. Access Analyzer's unused-access finding is a heuristic based on observed CloudTrail activity over a lookback window — it will flag permissions that are genuinely needed but rarely exercised (an annual disaster-recovery runbook action, for instance) as "unused," and it cannot see permissions that were used exactly once maliciously. It's a starting point for a review, not a certification that a policy is least-privilege.
**Follow-up trap:** *"How do you avoid breaking the annual DR runbook if you blindly trim based on Access Analyzer?"* — tag or separately document break-glass/DR permissions so they're excluded from automated trimming, and validate any trim against a documented list of low-frequency-but-legitimate use cases before applying it.

---

## Red flags that fail you

- Saying "IAM checks allow, then deny" — the order is backwards; explicit deny always wins first, checked across every layer.
- Not knowing that SCPs/RCPs/boundaries are ceilings that never grant anything by themselves.
- Confusing `aws:SourceAccount` with `aws:PrincipalOrgID`.
- Not knowing what `iam:PassRole` actually does, or treating it as harmless because "it's just a role reference."
- Recommending long-lived IAM user access keys for a new workload integration in 2026.
- Describing cross-account access as needing only the resource policy, or only the identity policy.
- Never having heard of RCPs, or confusing them with SCPs as if they're the same control applied twice.
- Treating IRSA as the only EKS workload-identity option without knowing Pod Identity exists.

---

## Cheat card

```
ORDER: explicit deny (any layer) > SCP > RCP > resource policy > boundary > session policy > identity policy > default deny
  SCP/RCP/boundary/session policy = CEILINGS (intersect), never grant alone
  resource policy CAN grant alone for same-account; cross-account needs BOTH sides to allow

STS AssumeRole: default 1hr creds, 15min-12hr via DurationSeconds, capped by role's MaxSessionDuration
  ExternalId in trust policy = confused-deputy fix for 3rd-party/SaaS cross-account access
  37% of vendors historically got ExternalId wrong (NCC Group research)

WORKLOAD IDENTITY (no static keys):
  EC2            -> instance profile
  EKS (legacy)   -> IRSA: per-cluster OIDC trust policy, webhook injects token (2019)
  EKS (current)  -> Pod Identity: EKS Auth API + DaemonSet agent, role portable across clusters (GA 2023)
  CI/CD          -> OIDC federation (GitHub/GitLab issuer) + AssumeRoleWithWebIdentity

SCP vs boundary: SCP = org/account ceiling, mandatory, inherited. Boundary = per-identity ceiling, opt-in, for delegated admin.
RCP (GA Nov 2024): resource-side ceiling SCPs structurally can't do (blocks grants TO external principals)

CONDITION KEYS:
  aws:SourceArn      -> exactly one resource (strongest, confused-deputy)
  aws:SourceAccount  -> any resource in one account (looser)
  aws:PrincipalOrgID -> any principal in an org, any account (org perimeter)

iam:PassRole = quiet privilege escalation: PassRole(admin-role) + CreateLambda = admin
  ALWAYS scope: Resource=<role-arn-pattern> + Condition iam:PassedToService

DEBUG METHOD: get-caller-identity -> simulate-principal-policy -> check explicit denies first
  -> walk 7 layers in order -> check CloudTrail errorMessage for which layer denied

Access Analyzer: finds external-access grants + unused-access heuristic. NOT a real-time blocker.
```

## Sources

- [Policy evaluation logic — AWS IAM docs](https://docs.aws.amazon.com/IAM/latest/UserGuide/reference_policies_evaluation-logic.html) — accessed 2026-08-01
- [How AWS enforcement code logic evaluates requests](https://docs.aws.amazon.com/IAM/latest/UserGuide/reference_policies_evaluation-logic_policy-eval-denyallow.html) — accessed 2026-08-01
- [Introducing Resource Control Policies (RCPs)](https://aws.amazon.com/about-aws/whats-new/2024/11/resource-control-policies-restrict-access-aws-resources) — accessed 2026-08-01
- [RCP evaluation — AWS Organizations docs](https://docs.aws.amazon.com/organizations/latest/userguide/orgs_manage_policies_rcps_evaluation.html) — accessed 2026-08-01
- [Demystifying AWS' AssumeRole and sts:ExternalId — NCC Group](https://www.nccgroup.com/research/demystifying-aws-assumerole-and-stsexternalid/) — accessed 2026-08-01
- [Amazon EKS Pod Identity announcement — AWS Containers blog](https://aws.amazon.com/blogs/containers/amazon-eks-pod-identity-a-new-way-for-applications-on-eks-to-obtain-iam-credentials/) — accessed 2026-08-01
- [IRSA vs Pod Identity — EKS Security Deep Dive](https://dev.to/himaatluri/eks-security-deep-dive-irsa-vs-eks-pod-identity-4562) — accessed 2026-08-01
- [Fine-tuning access with IAM global condition context keys — Alex Smolen](https://alsmola.medium.com/fine-tuning-access-with-aws-iam-global-condition-context-keys-784d6374ee) — accessed 2026-08-01
- [Establishing a data perimeter on AWS — AWS Security Blog](https://aws.amazon.com/blogs/security/establishing-a-data-perimeter-on-aws-allow-only-trusted-identities-to-access-company-data/) — accessed 2026-08-01

## Changelog
- 2026-08-01 — created
- 2026-08-09 — IAM Identity Center now replicates the Identity Center directory (not just external-IdP-backed instances) to secondary Regions, so users keep provisioned entitlements if the primary Region has a disruption ([src](https://aws.amazon.com/blogs/aws/aws-weekly-roundup-price-reduction-of-gpt-models-in-bedrock-cloudwatch-managed-collectors-for-prometheus-metrics-and-more-august-3-2026/))

## The 30-second version

IAM evaluates a request through layers, and only one thing can say yes while many can say no: an explicit deny anywhere ends it immediately; SCPs and RCPs act as organization-level ceilings that identity policies can never exceed; a resource-based policy can grant same-account access directly and is one of two required halves for cross-account access; permissions boundaries and session policies narrow via intersection, never grant; and the identity-based policy is the final, and only, real grant — with default deny if nothing explicitly allowed it. `AssumeRole`/STS issues short-lived credentials instead of static keys, with `ExternalId` closing the confused-deputy hole for third-party cross-account access. `iam:PassRole` is the permission most likely to produce silent privilege escalation because it hands a role to a service rather than granting the role's permissions directly — always scope it to specific role ARNs and a target service. Debugging a denial means walking those layers in order and checking for an explicit deny before anything else.
