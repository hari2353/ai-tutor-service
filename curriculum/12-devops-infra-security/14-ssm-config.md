# SSM Parameter Store vs Secrets Manager vs AppConfig; Config Hierarchies

> **Track:** T12 DevOps, Infra & Security · **Time:** 1.5h · **Prereqs:** T12-eks-ecs-ecr
> **Module id:** `T12-ssm-config` · **Tags:** aws, config, secrets

## The 30-second version

These three AWS services get reached for interchangeably and shouldn't be: SSM Parameter Store is free (standard tier, 40 ops/sec) key-value storage for config and secrets with no built-in rotation, Secrets Manager costs $0.40/secret/month plus $0.05 per 10,000 API calls specifically because you're paying for automatic rotation orchestration (native rotation for RDS/Redshift/DocumentDB, Lambda-based rotation for anything else) and cross-account/cross-region replication, and AppConfig is not a key-value store at all — it's a *deployment* mechanism (canary/linear/all-at-once rollout strategies with automatic rollback on CloudWatch alarm breach) for configuration and feature flags that happens to source its data from Parameter Store, Secrets Manager, S3, or its own hosted store. The wrong-choice pattern that shows up constantly: using Secrets Manager for pure application config that never rotates (paying $0.40/month per value for a feature you never use), using Parameter Store for a database credential that needs rotation (building a bespoke rotation Lambda that Secrets Manager already ships), or shipping a config change by editing a Parameter Store value directly and pushing it live to 100% of instances instantly with no canary and no automatic rollback, which AppConfig exists specifically to prevent. Path-based namespacing (`/app/{env}/{service}/{key}`) plus IAM policy scoped to the path prefix is the whole config-hierarchy story; there's no cleverer pattern hiding underneath it.

## Why this gets asked

Because config and secrets management is the layer where "it worked in my terminal" AWS knowledge (IAM basics, a `get-parameter` call) gets tested against real operational judgment: does the candidate know rotation orchestration is a paid, specific Secrets Manager feature rather than assuming any KV store does it, do they know a raw parameter edit is a global instant push with no blast-radius control, and have they actually designed a config hierarchy that scales past "a folder full of parameters nobody remembers the naming convention for." The interviewer has likely debugged a production incident where a config value was updated for one service and, because of loose IAM scoping or ambiguous path naming, three unrelated services picked up the same value at their next restart, or watched a rotation Lambda silently fail for months because nobody was alerted when Secrets Manager's rotation health check started failing.

---

## Lineage: past → present → future

**What came before.** Before these services existed as anything mature, AWS-hosted config lived in environment variables baked into AMIs or container images (a config change meant rebuilding and redeploying the artifact — the same rebuild-not-promote anti-pattern covered in `T12-artifact-registries`), in home-grown S3-JSON-plus-polling schemes, or in Consul/etcd/ZooKeeper self-hosted alongside the workload, all of which meant the team owned availability, encryption-at-rest, and access control themselves. Secrets specifically were routinely stored as plaintext environment variables or committed (sometimes accidentally, sometimes "temporarily") straight into source control or CI variables — the pain that made this era end wasn't philosophical, it was breach reports: leaked API keys in public GitHub repos and CI logs were, and remain, one of the most common real-world incident root causes, which is the direct reason "secrets never touch source control, ever" became a hard compliance line.

**Where it stands now.** SSM Parameter Store (free at standard throughput, 40 ops/sec, 4KB standard-tier value size, 10,000 standard parameters per region) is the default choice for non-rotating application config and even for secrets that don't need automatic rotation — a large fraction of real AWS shops use Parameter Store SecureString (KMS-encrypted at rest) for things like feature-flag defaults, third-party API keys rotated manually/infrequently, and per-environment config values, specifically to avoid paying Secrets Manager's per-secret fee for a rotation capability they're not using. Secrets Manager earns its cost specifically for credentials needing automatic rotation without downtime — native rotation support for RDS, Aurora, Redshift, and DocumentDB (AWS-managed rotation Lambda templates that handle the create-new-credential-test-it-cut-over-old-one dance) is the concrete feature nobody wants to hand-roll, and cross-region replication for DR is a second real differentiator Parameter Store doesn't offer natively. AppConfig sits at a different layer entirely and the live confusion is that people compare it to the other two as if it were a third KV store — it's a **deployment control plane**: it can read from Parameter Store, Secrets Manager, S3, or its own hosted configuration profiles, and its actual value-add is deployment strategies (canary percentage-based rollout, bake time, automatic rollback triggered by a CloudWatch alarm breaching during rollout) plus a Lambda extension/agent that gives a service in-process cached config access without hitting the API on every read.

**Where it's heading.** AppConfig's 2026 enhancements toward entity-based, sticky targeting (rolling a flag out to a specific, consistent segment of users/sessions across a gradual rollout, rather than pure percentage-based randomness) reflect the broader industry direction of feature-flag platforms converging toward LaunchDarkly-style targeting sophistication natively inside the cloud provider, reducing the case for a third-party flag vendor for teams already AWS-native. Secrets Manager and Parameter Store's rotation/replication feature sets have been converging slowly (Parameter Store gained higher-throughput tiers and broader programmatic parity over time) but the fundamental cost/rotation split is stable and unlikely to change — expect AWS to keep this a deliberate two-tier pricing model (free/cheap KV without managed rotation vs paid KV with it) rather than merge the products, since the pricing split is itself the signal steering customers toward the right tool.

---

## Mental model

```
THREE DIFFERENT JOBS, OFTEN MISTAKEN FOR ONE:

  SSM Parameter Store        Secrets Manager           AppConfig
  ---------------------      ---------------------     ---------------------
  Key-value store            Key-value store           DEPLOYMENT mechanism
  FREE (standard tier,       $0.40/secret/month        $0.0000002/request +
  40 ops/sec)                + $0.05/10k API calls      $0.0008/config received
  No built-in rotation       Native rotation (RDS,      Reads FROM Param Store/
                             Redshift, Aurora, Docs)    Secrets Manager/S3/own
                             + Lambda rotation for       hosted profiles
                             anything else
  4KB standard / 8KB         No hard size limit          Canary/linear/all-at-
  advanced value size        practically                once rollout strategies,
                                                          auto-rollback on alarm

CONFIG HIERARCHY (path-based namespacing -- the whole pattern):

  /myapp/prod/api/db-host
  /myapp/prod/api/db-password        <- SecureString, KMS-encrypted
  /myapp/prod/worker/queue-url
  /myapp/staging/api/db-host
  /myapp/staging/api/db-password
        |
        v
  IAM policy scoped to path PREFIX:
    "Resource": "arn:aws:ssm:*:*:parameter/myapp/prod/api/*"
  -> the prod api service's role can read ITS OWN namespace, nothing else's

WHY A RAW PARAMETER EDIT IS DANGEROUS:
  aws ssm put-parameter --name /myapp/prod/api/feature-x --value true --overwrite
  -> next config poll/restart, EVERY instance picks up the new value AT ONCE.
     No canary, no bake time, no automatic rollback if it breaks something.
     This is exactly the gap AppConfig's deployment strategies close.
```

---

## How it actually works

### SSM Parameter Store: tiers, throughput, and the free-tier trap

Standard parameters (up to 4KB, up to 10,000 per region) are free at **standard throughput** (40 requests/second across the account/region), which is fine for most config-read patterns (a service reading its own handful of parameters at startup or on an infrequent poll) but becomes a real, checkable ceiling for a large fleet — hundreds of instances all polling Parameter Store on a tight interval can hit the 40 ops/sec wall and start seeing throttling errors. **Higher throughput** (up to 3,000 ops/sec at time of writing, with `GetParameter` supporting up to 10,000 TPS in some configurations) is opt-in and, once enabled, every API interaction (standard or advanced parameter) is billed at $0.05 per 10,000 calls — a real, easy-to-miss cost consequence of flipping on higher throughput for the whole account/region, not just the parameters that actually need it. Advanced parameters (up to 8KB, up to 100,000 per region, support parameter policies like expiration and change notification) are the tier to reach for when you need larger values or the 10,000-parameter ceiling, and they always incur the per-API-call charge regardless of throughput mode.

```bash
# untested sketch -- SecureString with a customer-managed KMS key, path-namespaced
aws ssm put-parameter \
  --name "/myapp/prod/api/db-password" \
  --value "correct-horse-battery-staple" \
  --type SecureString \
  --key-id "arn:aws:kms:us-east-1:123456789012:key/abcd-1234" \
  --tier Standard
```

### Secrets Manager: what the $0.40/month actually buys

Secrets Manager's per-secret fee is specifically the price of **managed rotation orchestration**, not of storing an encrypted string (Parameter Store SecureString already does encryption-at-rest via KMS for free). For RDS, Aurora, Redshift, and DocumentDB, AWS ships pre-built rotation Lambda templates that handle the actual hard part of rotation without downtime: create a new credential alongside the old one, test the new credential against the live database, update the secret's current version, and only then invalidate the old credential — the **dual-secret, grace-period pattern** covered in more depth in `T12-secrets`. For anything else (a third-party API key, a non-AWS-managed database), you write your own rotation Lambda against Secrets Manager's rotation Lambda contract (implementing the four rotation steps: `createSecret`, `setSecret`, `testSecret`, `finishSecret`), which is real engineering work Parameter Store gives you no framework for at all.

```python
# untested sketch — Secrets Manager rotation Lambda skeleton, the four-step contract
def lambda_handler(event, context):
    step = event["Step"]
    if step == "createSecret":
        # generate/stage a new credential value as AWSPENDING
        ...
    elif step == "setSecret":
        # apply the new credential to the actual downstream system
        ...
    elif step == "testSecret":
        # verify the AWSPENDING credential actually works before cutover
        ...
    elif step == "finishSecret":
        # move AWSPENDING -> AWSCURRENT, old AWSCURRENT -> AWSPREVIOUS
        ...
```

The concrete cost math that should drive the SSM-vs-Secrets-Manager decision: 200 secrets at $0.40/month is $80/month just for storage, before any API calls — for an org with hundreds of purely-static config values (feature flags, non-rotating third-party keys), routing all of them through Secrets Manager "because it's the secrets one" is a real, avoidable monthly cost with zero corresponding rotation benefit.

### AppConfig: the deployment layer neither of the other two has

AppConfig is billed per API interaction, not per stored value: $0.0000002 per configuration request plus $0.0008 per configuration actually received in response — meaning a fleet of 2,000 instances polling every 30 seconds racks up request costs that are worth modeling before enabling aggressive polling intervals across a large fleet, since the per-request cost is trivial individually but multiplies with instance count and poll frequency. Its actual value is the **deployment strategy**: a rollout can be configured as a percentage-based canary over a defined bake time (e.g., 10% of targets for 10 minutes, then 25%, then 50%, then 100%), with an attached CloudWatch alarm that, if it breaches during the rollout window, triggers an **automatic rollback** to the prior configuration version without any human intervening — a capability neither raw Parameter Store nor Secrets Manager has any concept of, since both are simple key-value stores where a `put-parameter` call is instantaneously and globally live to every reader on its next poll.

```json
// untested sketch -- AppConfig deployment strategy: canary with auto-rollback
{
  "Name": "Canary10PercentEvery10Minutes",
  "DeploymentDurationInMinutes": 40,
  "GrowthFactor": 10,
  "GrowthType": "LINEAR",
  "FinalBakeTimeInMinutes": 10,
  "ReplicateTo": "NONE"
}
```

```yaml
# untested sketch -- AppConfig deployment tied to a CloudWatch alarm for auto-rollback
Deployment:
  ApplicationId: myapp
  EnvironmentId: prod
  DeploymentStrategyId: !Ref Canary10PercentEvery10Minutes
  ConfigurationProfileId: feature-flags
  MonitorAlarmArns:
    - arn:aws:cloudwatch:us-east-1:123456789012:alarm:myapp-error-rate-high
  # if this alarm goes into ALARM state during the rollout window,
  # AppConfig automatically halts and rolls back to the previous version
```

The 2026 enhancement worth knowing: entity-based, "sticky" targeting during a gradual rollout — a specific user/session identifier can be pinned to consistently receive (or not receive) a flag throughout the rollout, rather than pure percentage-based randomness that could flip a given user in and out of a feature across requests, which matters for anything where mid-session consistency (a UI feature, an A/B test bucket) is a correctness requirement, not just a nice-to-have.

### Config hierarchy design: path namespacing and IAM scoping

The pattern that actually works at scale is boring and that's the point: `/​{app}/{env}/{component}/{key}`, with IAM policies scoped to the path prefix a given role should be allowed to read, and nothing cleverer layered on top. Two failure modes account for nearly all real config-hierarchy incidents: **ambiguous naming** (two teams both naming a parameter `/shared/db-host` with different actual meanings, discovered when one team's deploy accidentally reads the other's value) and **over-broad IAM scoping** (a role granted `ssm:GetParameter` on `/myapp/*` instead of `/myapp/prod/api/*`, so a bug or compromise in the api service can read the worker service's secrets too, or read staging values in a prod context). A per-environment overlay pattern (a shared `/myapp/common/` prefix for values genuinely identical across environments, layered under environment-specific overrides at `/myapp/{env}/`) is a reasonable additional layer, but only worth the complexity once you've actually got real cross-environment duplication to justify it — introducing an overlay/inheritance scheme prematurely is over-engineering for a problem you don't have yet.

---

## Build it from scratch

A minimal pattern combining path-scoped IAM, SecureString secrets, and an AppConfig-fronted feature flag — the shape most worth being able to sketch cold:

```hcl
# untested sketch -- Terraform: path-scoped IAM policy for the prod api service role
resource "aws_iam_role_policy" "api_config_read" {
  name = "api-prod-config-read"
  role = aws_iam_role.api_prod.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = ["ssm:GetParameter", "ssm:GetParametersByPath"]
      Resource = "arn:aws:ssm:us-east-1:123456789012:parameter/myapp/prod/api/*"
    }, {
      Effect   = "Allow"
      Action   = ["kms:Decrypt"]
      Resource = "arn:aws:kms:us-east-1:123456789012:key/abcd-1234"
      Condition = { StringEquals = { "kms:ViaService" = "ssm.us-east-1.amazonaws.com" } }
    }]
  })
}
```

```python
# untested sketch -- app startup: load config by path, cache in-process
import boto3

ssm = boto3.client("ssm")

def load_config(prefix: str) -> dict:
    params = {}
    paginator = ssm.get_paginator("get_parameters_by_path")
    for page in paginator.paginate(Path=prefix, Recursive=True, WithDecryption=True):
        for p in page["Parameters"]:
            key = p["Name"].removeprefix(prefix + "/")
            params[key] = p["Value"]
    return params

config = load_config("/myapp/prod/api")   # one call at startup, cached for process lifetime
```

A fuller lab exercising an AppConfig canary deployment with a deliberately broken config version (triggering the CloudWatch-alarm-driven auto-rollback) belongs in `(lab pending)`.

---

## How it's done in production

| Symptom | Cause | Fix |
|---|---|---|
| A fleet of instances polling Parameter Store starts seeing throttling errors under load | Standard throughput (40 ops/sec) ceiling hit by a large fleet's polling frequency | Enable higher throughput mode (up to 3,000 ops/sec), knowing every API call across the account/region then bills at $0.05/10k calls |
| Monthly AWS bill has an unexpectedly large Secrets Manager line item | Static, non-rotating config values (feature flags, rarely-changed third-party keys) stored in Secrets Manager purely out of habit, at $0.40/secret/month each | Migrate non-rotating values to Parameter Store SecureString (free at standard tier); reserve Secrets Manager for credentials with genuine rotation needs |
| A config change to one service silently breaks an unrelated service | Ambiguous or overlapping parameter naming (e.g., two teams both using `/shared/db-host` with different intended meaning), or IAM scoped too broadly across a shared prefix | Enforce strict `/app/env/component/key` namespacing; scope IAM to the narrowest path prefix each role actually needs |
| A feature-flag change deployed instantly breaks 100% of production traffic with no warning | A raw `put-parameter`/`update-secret` call pushed directly, with no canary, no bake time, no automatic rollback mechanism | Front config changes needing controlled rollout through AppConfig's deployment strategies with a CloudWatch alarm wired for automatic rollback |
| A rotation Lambda has been silently failing for months and nobody noticed until a credential expired | No monitoring/alerting on Secrets Manager rotation failures — rotation health isn't visible unless explicitly watched | Alert on Secrets Manager's rotation failure CloudWatch metrics/events, not just on downstream connection failures when the credential finally does expire |
| A/B test or feature-flag rollout produces inconsistent behavior for the same user across requests | Pure percentage-based random targeting flipping a user in and out of the flagged cohort on different requests | Use AppConfig's entity-based sticky targeting (2026+) or an equivalent consistent-hashing approach keyed on a stable user/session identifier |
| A prod IAM role can read a staging secret it should never have access to | IAM policy scoped to `/myapp/*` instead of `/myapp/prod/*`, granting cross-environment read access | Scope every IAM policy to the fully-qualified environment-specific path prefix, never a wildcard spanning environments |

---

## Tradeoffs & when NOT to use it

- **Don't default to Secrets Manager for every config value "because secrets."** The $0.40/month per secret is specifically paying for managed rotation and cross-region replication; static config with no rotation need belongs in Parameter Store SecureString, which is free at standard tier and equally KMS-encrypted at rest.
- **Don't hand-roll a rotation Lambda against Parameter Store when the credential type (RDS, Aurora, Redshift, DocumentDB) already has a native Secrets Manager rotation template.** Reimplementing the create-test-cutover dance yourself is real, unnecessary engineering risk when AWS ships a maintained template for exactly this.
- **Don't push a config or flag change via a raw `put-parameter`/`update-secret` call for anything with real blast radius.** That call is instantly and globally live to every reader on next poll, with no canary and no automatic rollback — front it through AppConfig if the change could plausibly break something in production.
- **Don't enable Parameter Store higher throughput mode account-wide just to fix one noisy service's polling pattern.** Every API call across the account/region then bills at $0.05/10k calls; consider reducing that one service's poll frequency or caching more aggressively before paying to raise the ceiling for everything.
- **Don't build a deep, clever config-inheritance/overlay hierarchy before you have actual cross-environment duplication to justify it.** Flat, boring `/app/env/component/key` namespacing scoped by IAM prefix is the right default; layer in a shared/common overlay only once real, repeated duplication makes the added complexity worth it.
- **Don't use AppConfig as a general-purpose high-throughput KV store.** It's billed per request and per configuration received, and its value is the deployment/rollout mechanism — for a workload needing frequent small reads with no deployment-strategy need, Parameter Store or Secrets Manager (read directly or via the AppConfig Lambda extension's local cache) is the better fit.

---

## Interview questions

### Q1 — What is the SSM Parameter Store standard-tier throughput limit, and what happens when a large fleet exceeds it?
**Testing:** whether "Parameter Store is free" is understood alongside its real ceiling.
**Answer:** 40 requests per second at standard throughput. A fleet polling Parameter Store frequently enough to exceed that starts receiving throttling errors; the fix is enabling higher throughput mode (up to 3,000 ops/sec), which then bills every API call (standard or advanced) at $0.05 per 10,000 calls across the account/region.
**Follow-up trap:** *"Is enabling higher throughput mode scoped to just the noisy service?"* — no, it's an account/region-level setting affecting billing on every Parameter Store API call going forward, not a per-parameter or per-role toggle — a common mistake is enabling it to fix one service's throttling without realizing every other service's previously-free calls now bill too.

### Q2 — What does Secrets Manager's $0.40/secret/month fee actually pay for, given Parameter Store SecureString also encrypts at rest for free?
**Testing:** whether the actual differentiator (rotation orchestration) is understood, not just "Secrets Manager is the paid one."
**Answer:** It pays for managed rotation orchestration — native rotation templates for RDS/Aurora/Redshift/DocumentDB implementing the create-test-cutover credential dance without downtime, a Lambda rotation framework (the four-step `createSecret`/`setSecret`/`testSecret`/`finishSecret` contract) for anything else, and cross-region replication for DR. Encryption at rest via KMS is not the differentiator — Parameter Store SecureString already provides that for free.
**Follow-up trap:** *"So is it ever correct to use Secrets Manager for something that never rotates?"* — occasionally, if you need its cross-region replication for DR and don't want to build that yourself, or if organizational policy mandates all secrets live in one service for audit simplicity — but absent one of those specific reasons, paying $0.40/month for unused rotation capability on a static value is an avoidable cost.

### Q3 — Explain the four-step contract a custom Secrets Manager rotation Lambda must implement.
**Testing:** the actual mechanical rotation flow, not just "Secrets Manager can rotate."
**Answer:** `createSecret` (generate and stage a new candidate credential value under the `AWSPENDING` label), `setSecret` (apply that new credential to the actual downstream system, e.g., create the new database user), `testSecret` (verify the pending credential genuinely works before committing to it), `finishSecret` (promote `AWSPENDING` to `AWSCURRENT`, demoting the prior `AWSCURRENT` to `AWSPREVIOUS`). This is the same underlying dual-secret/grace-period pattern covered in `T12-secrets`.
**Follow-up trap:** *"What happens if testSecret fails?"* — rotation halts before `finishSecret` runs, leaving the old `AWSCURRENT` credential still active and valid — the entire point of the staged, tested rollout is that a failed test never cuts over the currently-working credential, avoiding a rotation-induced outage.

### Q4 — Why is AppConfig not simply "a third key-value store" alongside Parameter Store and Secrets Manager?
**Testing:** the category distinction that's most commonly missed.
**Answer:** AppConfig doesn't own storage at all by necessity — it can source configuration from Parameter Store, Secrets Manager, S3, or its own hosted configuration profiles. Its actual product is the deployment mechanism layered on top: percentage-based canary rollout strategies with defined bake times, and automatic rollback triggered by a CloudWatch alarm breaching during the rollout window — a capability neither underlying KV store has any concept of.
**Follow-up trap:** *"If a team already uses Parameter Store for all their config, is there still value in adding AppConfig?"* — yes, specifically for any config change with real blast radius (a feature flag, a rate limit, a routing rule) — AppConfig can front the existing Parameter Store values with canary/rollback behavior without requiring a full migration of where the data itself lives.

### Q5 — A raw `aws ssm put-parameter --overwrite` is used to flip a feature flag in production. What goes wrong that AppConfig would have prevented?
**Testing:** the specific, checkable danger of direct parameter mutation for anything with blast radius.
**Answer:** The new value becomes instantly and globally live to every reader on its next poll or restart — no canary percentage, no bake time to observe impact on a small slice of traffic first, and no automatic rollback mechanism if the change breaks something; recovery requires someone noticing the incident and manually reverting the parameter.
**Follow-up trap:** *"Doesn't a service's own caching/poll interval provide some natural staggering?"* — only accidentally and unreliably — poll intervals stagger *when* instances pick up the change, not *whether* they all eventually get the same bad value with no controlled percentage or automatic revert; that's a coincidental delay, not a deployment strategy.

### Q6 — Design the IAM scoping for a config hierarchy with `/myapp/{env}/{component}/{key}` paths, given prod and staging share the account. What's the specific mistake to avoid?
**Testing:** the most common real-world config-hierarchy IAM incident.
**Answer:** Scope each role's policy to the fully-qualified, environment-specific path prefix (`/myapp/prod/api/*` for the prod api role), never to a wildcard spanning environments (`/myapp/*`). The specific mistake: granting `/myapp/*` "for convenience" lets a prod role read staging values (and vice versa) — usually harmless until a staging secret with weaker rotation/access hygiene is readable from a prod context, or a compromised prod service can enumerate staging credentials too.
**Follow-up trap:** *"What if a value genuinely needs to be identical across environments, like a shared third-party API endpoint?"* — put it under a genuinely shared prefix (`/myapp/common/`) that both environment-specific roles are separately granted read access to, rather than granting the broader `/myapp/*` wildcard just to reach that one shared value — the scoping stays precise even for legitimately shared values.

### Q7 — What's the AppConfig billing model, and why does it matter for a fleet of thousands of instances polling frequently?
**Testing:** real numbers, and judgment about when a per-request cost model needs modeling before deployment.
**Answer:** $0.0000002 per configuration request plus $0.0008 per configuration actually received. Individually trivial, but a fleet of 2,000 instances polling every 30 seconds accumulates real, worth-modeling cost at scale — the fix isn't avoiding AppConfig, it's using its Lambda extension/agent for in-process local caching so instances aren't hitting the API on every single config read.
**Follow-up trap:** *"Does the AppConfig extension change the freshness guarantee?"* — yes, there's a real tradeoff — a local cache means an instance may serve a slightly stale configuration for the cache's TTL window rather than always seeing the absolute latest value; this is almost always the correct tradeoff for cost and latency, but it should be a deliberate choice, not a surprise discovered during an incident where "why didn't the rollback take effect on this instance immediately" turns out to be an unexpired local cache.

### Q8 — Compare rotating a secret manually via Parameter Store versus Secrets Manager's automatic rotation, for an RDS database credential.
**Testing:** whether the practical engineering-effort gap is understood, not just "Secrets Manager rotates automatically."
**Answer:** With Parameter Store, rotation is entirely bespoke: you write and maintain your own process (a scheduled Lambda, a runbook) to create a new database user, update the parameter, and revoke the old user, with no framework enforcing the create-test-cutover order or providing rollback if the test step is skipped. Secrets Manager's native RDS rotation template implements this exact sequence as a maintained, AWS-provided Lambda — you configure it, you don't build it.
**Follow-up trap:** *"If a team already has Parameter Store everywhere and doesn't want a second service, is a hand-rolled rotation Lambda a reasonable engineering investment?"* — it's a real, non-trivial amount of engineering and testing effort to get the dual-credential grace-period logic correct (avoiding a window where neither old nor new credential is valid) — for anything beyond a handful of rotating credentials, adopting Secrets Manager for just those specific values (while keeping static config in Parameter Store) is usually cheaper than maintaining bespoke rotation logic correctly over time.

### Q9 — What's the concrete difference between AppConfig's 2026 entity-based sticky targeting and plain percentage-based canary rollout, and when does the difference actually matter?
**Testing:** whether a specific, current feature is understood at the mechanism level, not just named.
**Answer:** Plain percentage-based rollout assigns cohort membership per-request via randomization, which can flip a given user in and out of the flagged behavior across different requests during the rollout window. Entity-based sticky targeting pins a specific identifier (a user ID, a session ID) to a consistent cohort assignment for the duration of the rollout, so the same user always gets the same flag state. It matters specifically when mid-session or cross-request consistency is a correctness requirement — a UI feature that would look broken flickering on and off, or an A/B test where inconsistent bucketing would corrupt the experiment's results.
**Follow-up trap:** *"Does sticky targeting eliminate the need for a canary bake time at all?"* — no, they solve different problems — sticky targeting fixes *consistency within* the rollout, bake time and gradual percentage increase still control *blast radius* of the rollout itself; you'd typically want both together for anything with real user-facing consistency requirements and real risk of breaking something.

### Q10 — A team stores 300 static, rarely-changing config values in Secrets Manager and asks whether that's a problem. What's your answer, with numbers?
**Testing:** applying the cost-model numbers to a concrete scenario, and judgment about the actual severity.
**Answer:** 300 secrets at $0.40/month each is $120/month, or roughly $1,440/year, purely for storage of values that never use the rotation feature they're paying for. It's not a security problem (Secrets Manager isn't wrong, just expensive for this use case) but it is an avoidable cost — migrating the genuinely-static values to Parameter Store SecureString (free at standard tier) while keeping only the values that actually rotate in Secrets Manager would eliminate most of that spend with no functional loss.
**Follow-up trap:** *"Is there a reason a team might accept that cost deliberately?"* — yes — if the org has a compliance requirement that all secrets (rotating or not) live in a single auditable service, or if the operational cost of maintaining two config sources outweighs $120/month for a smaller team, that's a legitimate, deliberate tradeoff — the point isn't that Secrets Manager-for-everything is always wrong, it's that the cost should be a conscious decision, not a default reached without comparing it to the free alternative.

---

## Red flags that fail you

- Treating Parameter Store, Secrets Manager, and AppConfig as three interchangeable config stores rather than naming their actual distinct jobs.
- Not knowing Secrets Manager's per-secret monthly fee ($0.40) or that it specifically pays for rotation orchestration, not encryption.
- Not knowing Parameter Store's standard-tier throughput ceiling (40 ops/sec) or that raising it bills every account-wide API call afterward.
- Describing AppConfig as a KV store rather than a deployment/rollout mechanism layered on top of one.
- Pushing a production config or feature-flag change via a raw parameter/secret write for anything with real blast radius, with no canary or rollback plan.
- Scoping IAM policy to a wildcard spanning environments (`/app/*`) instead of the fully-qualified environment-specific path.
- Recommending a hand-rolled rotation Lambda for RDS/Aurora/Redshift/DocumentDB when Secrets Manager already ships a maintained template for exactly that.
- Introducing a complex config-inheritance/overlay hierarchy before there's real cross-environment duplication to justify it.

---

## Cheat card

```
SSM PARAMETER STORE: FREE at standard throughput (40 ops/sec). Standard tier:
  4KB value, 10,000 params/region. Advanced tier: 8KB, 100,000 params/region,
  ALWAYS billed per API call. Higher throughput (up to 3,000 ops/sec, opt-in,
  ACCOUNT-WIDE) = every call then bills $0.05/10k. NO built-in rotation.
  SecureString = KMS-encrypted at rest, free.

SECRETS MANAGER: $0.40/secret/month + $0.05/10k API calls. Pays for MANAGED
  ROTATION, not encryption (Parameter Store SecureString already encrypts
  free). Native rotation templates: RDS, Aurora, Redshift, DocumentDB.
  Custom rotation = 4-step Lambda contract: createSecret -> setSecret ->
  testSecret -> finishSecret (AWSPENDING -> AWSCURRENT -> AWSPREVIOUS).
  Also: cross-region replication (Parameter Store lacks this natively).
  300 static secrets = $120/mo wasted if none rotate -- migrate to Param Store.

APPCONFIG: NOT a KV store -- a DEPLOYMENT mechanism. Sources from Param
  Store/Secrets Manager/S3/own profiles. Billed $0.0000002/request +
  $0.0008/config received (model this for large fleets/frequent polling).
  Value = deployment strategies: canary % + bake time + auto-ROLLBACK on
  CloudWatch alarm breach during rollout. 2026: entity-based STICKY
  targeting (consistent per-user cohort, not per-request random flip).

CONFIG HIERARCHY: /{app}/{env}/{component}/{key}. IAM scoped to the
  NARROWEST env-specific prefix (/myapp/prod/api/*), never a cross-env
  wildcard (/myapp/*). Shared values -> separate /myapp/common/ prefix,
  granted explicitly, not via a broader wildcard.

RAW put-parameter/update-secret = INSTANT, GLOBAL, no canary, no rollback.
  Front anything with real blast radius through AppConfig instead.
```

## Sources

- [SSM Parameter Store pricing: what to model (advanced params + API calls) — CloudCostKit](https://cloudcostkit.com/guides/aws-ssm-parameter-store-pricing/) — accessed 2026-08-03
- [Increasing or resetting Parameter Store throughput — AWS Systems Manager docs](https://docs.aws.amazon.com/systems-manager/latest/userguide/parameter-store-throughput.html) — accessed 2026-08-03
- [AWS Secrets Manager Pricing 2026: $0.40/secret/month — CostBench](https://costbench.com/software/secrets-management/aws-secrets-manager/) — accessed 2026-08-03
- [AWS Secrets Manager Cost: 2026 Pricing Guide — Akeyless](https://www.akeyless.io/blog/aws-secrets-manager-cost/) — accessed 2026-08-03
- [AWS AppConfig Pricing model — AWS re:Post](https://repost.aws/questions/QUevHYubJ-TESBPlUxRyujmg/i-want-to-understand-aws-appconfig-pricing-model) — accessed 2026-08-03
- [AWS AppConfig adds enhanced targeting during feature flag rollout — AWS What's New](https://aws.amazon.com/about-aws/whats-new/2026/03/appconfig-enhanced-targeting-feature-flag-rollout) — accessed 2026-08-03
- [Deploying feature flags and configuration data in AWS AppConfig — AWS docs](https://docs.aws.amazon.com/appconfig/latest/userguide/deploying-feature-flags.html) — accessed 2026-08-03
- [The Old Faithful: Why SSM Parameter Store Still Reigns Over Secrets Manager — DEV Community](https://dev.to/aws-heroes/the-old-faithful-why-ssm-parameter-store-still-reigns-over-secrets-manager-51ck) — accessed 2026-08-03

## Changelog
- 2026-08-03 — created
