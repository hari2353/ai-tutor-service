# Secret Management & Rotation, JWT TTL Caching

> **Track:** T12 DevOps, Infra & Security · **Time:** 2h · **Prereqs:** T12-ssm-config
> **Module id:** `T12-secrets` · **Tags:** security, auth, secrets

## The 30-second version

Secret rotation without downtime works on exactly one mechanism: never have a single point in time where only one credential is valid — maintain two (old and new) simultaneously across a defined grace period long enough for every application instance to pick up the new one, then revoke the old one, which is the dual-secret pattern that both hand-rolled rotation Lambdas and Vault's dynamic-secret leases implement under the hood. Dynamic secrets (Vault issuing a unique, TTL-bound database credential per lease, auto-revoked on expiry) eliminate the rotation problem structurally — there's nothing long-lived to rotate — but only work for applications that are lease-aware and can refresh before expiry; a legacy app with a hardcoded connection string can't use them at all, which is exactly why static secrets with scheduled rotation remain the majority pattern in real production estates. JWT TTL is a direct tradeoff against revocation cost: a JWT has no built-in revocation, so a compromised or logged-out token stays valid until it naturally expires, which is why the 2026 consensus default is a short-lived access token (5-15 minutes, capping how stale a resource server's view of "is this still valid" can ever be) paired with a longer-lived, rotated refresh token (7-30 days) that's actually revocable server-side — and refresh token rotation with reuse detection (issue a new refresh token on every use, immediately invalidate the old one, and treat a reused old token as proof of theft, invalidating the whole token family) is the mechanism that makes the long-lived half of that pair safe.

## Why this gets asked

Because "we rotate our secrets" and "we use short-lived JWTs" are both sentences that sound like solved problems until someone asks how, specifically, and the answer reveals whether the candidate has actually operated a rotation that didn't cause an outage, or debugged a revoked user whose session kept working for twenty more minutes because nobody thought through what "stateless" actually costs at logout time. The interviewer has likely either watched a rotation script take down a service because the old credential was revoked before every instance had picked up the new one (the exact single-point-of-failure the dual-secret pattern exists to prevent), or handled an incident response where "revoke this user's access immediately" ran into the hard truth that a bare JWT has no server-side kill switch — this tests whether cryptographic and operational tradeoffs are understood together, not just "JWTs are stateless and that's good."

---

## Lineage: past → present → future

**What came before.** Early secret management meant static credentials baked into config files or environment variables, rotated manually (if at all) on a calendar cadence measured in months or years, with rotation itself often requiring a coordinated deploy or even downtime because there was no mechanism for two credentials to be simultaneously valid — the operational cost of rotation was high enough that teams rotated rarely, which is precisely backwards from a security posture where compromised, long-lived credentials are one of the most common real incident root causes. Early stateful session management (server-side session IDs in a shared store) had trivial revocation (delete the row) but didn't scale horizontally without a shared session store becoming a bottleneck and single point of failure — which is the specific pain JWTs were designed to solve: a self-contained, cryptographically-signed token any service could verify locally without a network round-trip to a central session store, at the direct cost of giving up that same store's easy revocation.

**Where it stands now.** The dual-secret/grace-period pattern (maintain two valid credentials across a bounded overlap window, cut over readers gradually, then revoke the old one) is the settled mechanism behind both manual rotation runbooks and automated tooling — Secrets Manager's native RDS/Aurora rotation templates and HashiCorp Vault's rotation both implement this same overlap-then-revoke shape under different names. Vault's dynamic secrets (a unique, per-lease database credential generated on request and auto-revoked at TTL expiry) represent the more radical fix — not rotating a long-lived secret faster, but eliminating long-lived secrets from the picture entirely — and are genuinely deployed at scale for lease-aware, cloud-native applications, but the real, live constraint is that they require the application to actually renew or fetch fresh leases before expiry, which rules out legacy applications with hardcoded connection strings or anything that can't be made lease-aware without real refactoring. For JWTs, the 2026 consensus has converged tightly around short access-token TTLs (5-15 minutes) specifically because that window is the practical bound on "how long can a revoked or compromised token remain usable," paired with refresh-token rotation-with-reuse-detection (a new refresh token issued on every use, the prior one immediately invalidated, and a replay of an already-rotated refresh token treated as a theft signal invalidating the entire token family) as the mechanism giving the long-lived half of the pair real revocability. The live disagreement is less about the TTL number itself (5-15 minutes is close to universal guidance now) and more about where to enforce revocation for the *access* token specifically — a Redis-backed deny list keyed on the token's `jti` claim gives immediate, real revocation at the cost of reintroducing a network round-trip and shared-state dependency into what was supposed to be a stateless verification, and different shops land differently on whether that tradeoff is worth it for their specific threat model.

**Where it's heading.** Dynamic secrets and short-TTL-workload-identity patterns (Kubernetes service accounts federated to cloud IAM via OIDC, the same mechanism covered for EKS in `T12-eks-ecs-ecr`, rather than any stored secret at all) are the clear direction of travel — the industry-wide trend is toward eliminating static, long-lived credentials structurally rather than rotating them faster, since a credential that never exists in a durable, exfiltratable form can't be stolen from a config file or log. For JWTs, expect continued convergence on short access-TTL-plus-rotated-refresh as the default, with the open, unresolved question remaining how much stateful revocation infrastructure (deny lists, token-family tracking) is worth reintroducing for a specific application's actual risk profile — a genuinely stateless, no-deny-list JWT setup is still a reasonable, common choice for lower-sensitivity applications where "worst case, a stolen token is useless in 10 minutes" is an acceptable risk, and it would be dishonest to claim deny-list-based revocation is now mandatory for every JWT deployment.

---

## Mental model

```
DUAL-SECRET ROTATION: never a moment where only ONE credential is valid.

  t0: credential A is the only valid one, everyone's using it
  t1: generate credential B, ADD it (A still valid) -> BOTH valid
  t2: update secret store, readers gradually pick up B on their own cadence
  t3: grace period elapses -- long enough for the SLOWEST reader to have
      refreshed (cache TTL + retry backoff + deploy cadence, whichever
      is longest)
  t4: revoke credential A -- only NOW, after every reader is confirmed
      (or safely assumed) to be on B

  SKIP THE GRACE PERIOD (revoke A right after creating B) = an instance
  still holding a cached A gets a hard auth failure -- the exact outage
  this pattern exists to prevent.

DYNAMIC SECRETS (Vault): skip rotation ENTIRELY by making secrets short-
  lived from birth.
  app requests DB credential -> Vault generates a UNIQUE user+password,
  TTL-bound lease -> app uses it -> Vault auto-REVOKES at lease expiry
  -> "rotation" is just... the lease ending. Nothing durable to rotate.
  CONSTRAINT: app must be lease-aware (renew/refetch before expiry) --
  a hardcoded connection string can't participate at all.

JWT TTL vs REVOCATION COST (the actual tradeoff, not a free lunch):

  SHORT access-token TTL (5-15 min)     LONG access-token TTL (hours+)
  -> revoked/stolen token is useless    -> revoked/stolen token stays
     within minutes, NO deny list          valid for HOURS unless you
     needed for the common case             build a deny list (adds
                                             back shared state + network
                                             round-trip per verification)

  REFRESH TOKEN (7-30 days) is the ACTUALLY revocable one:
  rotate on every use -> old one immediately invalidated -> a REPLAYED
  (already-used) refresh token = theft signal -> invalidate the WHOLE
  token family, not just that one token.
```

---

## How it actually works

### The dual-secret / grace-period pattern, mechanically

The pattern generalizes across every real rotation mechanism: a Secrets Manager rotation Lambda's four-step contract (`createSecret` stages a new candidate labeled `AWSPENDING`, `setSecret` applies it to the downstream system, `testSecret` verifies it works, `finishSecret` promotes it to `AWSCURRENT` and demotes the old one to `AWSPREVIOUS` rather than deleting it outright), and a hand-rolled database credential rotation both implement the same overlap: **create the new credential alongside the old one, verify the new one actually works, cut readers over gradually, and only revoke the old credential once you're confident every reader has moved off it** — never revoke first and hope readers catch up.

```python
# untested sketch — dual-secret rotation for a shared DB credential, no downtime
def rotate_db_credential(secret_store, db_admin_client):
    old = secret_store.get_current("db-app-user")

    # 1. create a SECOND, distinct user -- old stays fully valid throughout
    new_password = generate_secure_password()
    db_admin_client.create_user("app_user_v2", password=new_password)
    db_admin_client.grant_same_permissions("app_user_v2", like="app_user_v1")

    # 2. verify the new credential actually works before anyone depends on it
    assert db_admin_client.test_connection("app_user_v2", new_password)

    # 3. publish the new credential -- readers pick it up on THEIR OWN cadence
    #    (cache expiry, next restart, next scheduled config poll)
    secret_store.set_pending("db-app-user", user="app_user_v2", password=new_password)

    # 4. GRACE PERIOD -- must exceed the slowest reader's refresh interval
    wait(grace_period=max(reader_cache_ttl, deploy_cadence) + safety_margin)

    # 5. only now, revoke the OLD credential
    db_admin_client.drop_user("app_user_v1")
    secret_store.promote_pending_to_current("db-app-user")
```

The grace period's correct length is not a guess — it must exceed the *slowest* reader's actual refresh cadence (an application caching a secret in-process for 10 minutes, a service that only re-reads config on restart and redeploys weekly, whichever is longer), and getting this wrong in either direction is a real, checkable failure: too short causes an outage for slow readers still on the old credential; needlessly long delays closing the exposure window if the rotation was triggered by a suspected leak.

### Dynamic secrets: making rotation unnecessary, not faster

Vault's dynamic secrets engine (for databases, cloud IAM, and other backends) inverts the problem: instead of a long-lived credential that periodically needs rotating, the application requests a credential *on demand*, Vault generates a genuinely unique username/password (or IAM credential) bound to a lease with a defined TTL, and Vault itself revokes that specific credential when the lease expires or is explicitly revoked — there's no durable secret sitting in a config file or Parameter Store entry to rotate at all, because each lease's credential is disposable by design.

```hcl
# untested sketch -- Vault dynamic database secret configuration
resource "vault_database_secret_backend_role" "app_role" {
  backend             = vault_mount.db.path
  name                = "app-readonly"
  db_name             = "postgres-primary"
  creation_statements = [
    "CREATE ROLE \"{{name}}\" WITH LOGIN PASSWORD '{{password}}' VALID UNTIL '{{expiration}}';",
    "GRANT SELECT ON ALL TABLES IN SCHEMA public TO \"{{name}}\";"
  ]
  default_ttl = 3600   # 1 hour lease -- app must renew or refetch before this
  max_ttl     = 86400
}
```

The hard constraint this creates: the requesting application must itself be **lease-aware** — able to request a fresh credential (or renew the existing lease) before it expires, and handle a lease expiring or being revoked mid-operation gracefully. A legacy application expecting a single, static connection string it reads once at startup and never refreshes structurally cannot participate in this pattern without real code changes — which is exactly why static secrets with scheduled dual-secret rotation remain the dominant pattern for a large fraction of real production estates, not because dynamic secrets are inferior, but because adopting them has a real prerequisite cost in application design.

### JWT TTL: the revocation cost you're actually paying for

A JWT's core property — a resource server can verify it locally via signature check, with no network call to an auth server — is also exactly what makes revocation hard: there's no built-in mechanism to invalidate a specific already-issued token before its `exp` claim says it's expired. This is why access-token TTL is a direct, quantifiable tradeoff against revocation risk, not an arbitrary tuning knob: a 5-15 minute access token means a stolen or should-be-revoked token is only actually dangerous for that narrow window, capping the worst case even with zero additional revocation infrastructure — this is the mechanism, not a coincidence, behind the 2026 consensus default of 5-15 minutes for web/mobile API access tokens.

```
# access/refresh split, with numbers
access token:  5-15 min TTL, stateless verification, NO deny list needed
               for the common "just expire it" revocation story
refresh token: 7-30 day TTL, used ONLY to mint new access tokens,
               and IS actually revocable server-side (it's checked
               against a store on every use, unlike the access token)
```

```python
# untested sketch — refresh token rotation with reuse detection
def refresh_access_token(refresh_token: str, store):
    record = store.lookup(refresh_token)
    if record is None:
        raise AuthError("unknown refresh token")
    if record.already_rotated:
        # this exact refresh token was already used ONCE before and rotated --
        # someone is replaying an old token. THEFT SIGNAL.
        store.invalidate_entire_family(record.family_id)
        raise AuthError("refresh token reuse detected -- session family revoked")

    new_refresh = generate_token()
    store.mark_rotated(refresh_token, replaced_by=new_refresh, family_id=record.family_id)
    new_access = issue_access_token(record.user_id, ttl_seconds=600)
    return new_access, new_refresh
```

The reuse-detection mechanism is what makes a long-lived refresh token safe despite being long-lived: because every refresh token is single-use (rotated on each call) and the *previous* token in the chain is recorded, a stolen refresh token used by an attacker *after* the legitimate client has already rotated past it is detectable — the attacker's replay of the stale token is distinguishable from legitimate use, and the correct response is invalidating the entire token family (every token descended from that session), not just the one flagged token, since the attacker may have already minted further tokens from the stolen one before detection.

### Caching validated tokens safely

Verifying a JWT's signature on every single request is cheap (a local cryptographic operation, no network call), so the temptation to cache "this token is valid" results is mostly unnecessary for signature verification itself — the actual caching decision that matters is around **anything that requires a network call to check**, specifically deny-list lookups. If a shop has decided the revocation-cost tradeoff of a short-only-TTL JWT isn't acceptable for some sensitive action (an admin operation, a financial transaction) and layers in a Redis-backed deny list keyed on the token's `jti` claim, that lookup is a real per-request cost (though cheap in absolute terms — one published estimate is roughly 50KB of Redis storage per 10,000 revoked entries, and an O(1) lookup) worth caching locally with a short TTL (seconds, not minutes) to avoid a network round-trip on every single request, while still bounding how stale that local cache's view of "is this token revoked" can be.

```python
# untested sketch — local short-TTL cache in front of a Redis deny-list lookup
_local_cache = {}   # jti -> (is_revoked, cached_at)
LOCAL_CACHE_TTL_SECONDS = 5   # short enough that a fresh revocation propagates fast

def is_token_revoked(jti: str, redis_client) -> bool:
    cached = _local_cache.get(jti)
    if cached and (time.time() - cached[1]) < LOCAL_CACHE_TTL_SECONDS:
        return cached[0]
    is_revoked = redis_client.sismember("revoked_jtis", jti)
    _local_cache[jti] = (is_revoked, time.time())
    return is_revoked
```

The specific, checkable trap: caching a "not revoked" result for too long defeats the entire purpose of adding a deny list in the first place — if the local cache TTL exceeds how quickly you need a revocation to take effect (an incident response SLA of "kill this session within 30 seconds," say), the cache itself becomes the bottleneck the deny list was supposed to close, and the cache TTL needs to be chosen against that SLA explicitly, not left at a default.

---

## Build it from scratch

A minimal end-to-end JWT issuance/refresh/revocation flow demonstrating the short-access/rotated-refresh pattern together — the piece most worth sketching cold:

```python
# untested sketch — issuance, refresh-with-rotation, and family revocation
import jwt, time, uuid

def issue_tokens(user_id: str, store) -> tuple[str, str]:
    access = jwt.encode(
        {"sub": user_id, "exp": time.time() + 600, "jti": str(uuid.uuid4())},
        SECRET, algorithm="HS256",
    )
    family_id = str(uuid.uuid4())
    refresh = str(uuid.uuid4())
    store.save_refresh(refresh, user_id=user_id, family_id=family_id, rotated=False)
    return access, refresh

def refresh(refresh_token: str, store) -> tuple[str, str]:
    record = store.lookup(refresh_token)
    if record is None:
        raise AuthError("invalid refresh token")
    if record["rotated"]:
        store.revoke_family(record["family_id"])   # theft: kill the whole family
        raise AuthError("reuse detected, session revoked")

    store.mark_rotated(refresh_token)
    new_refresh = str(uuid.uuid4())
    store.save_refresh(new_refresh, user_id=record["user_id"],
                        family_id=record["family_id"], rotated=False)
    new_access = jwt.encode(
        {"sub": record["user_id"], "exp": time.time() + 600, "jti": str(uuid.uuid4())},
        SECRET, algorithm="HS256",
    )
    return new_access, new_refresh

def logout(user_id: str, store):
    store.revoke_all_families_for_user(user_id)   # explicit revocation path
```

A fuller lab exercising dual-secret database credential rotation against a live Postgres (via Testcontainers, `T12-local-cloud-parity`) with a deliberately-too-short grace period demonstrating the outage, then corrected, belongs in `labs/security/16-secrets/`.

---

## How it's done in production

| Symptom | Cause | Fix |
|---|---|---|
| A scheduled secret rotation causes a brief but real service outage | The old credential was revoked before every reader had a chance to pick up the new one — grace period too short or skipped entirely | Extend the grace period to exceed the slowest reader's actual refresh cadence (cache TTL, restart/deploy interval), and revoke the old credential only after that window elapses |
| A rotation Lambda's `testSecret` step keeps failing silently and nobody notices for months | No alerting on rotation-specific failure signals, only on eventual downstream symptoms | Alert directly on rotation failure events/metrics, not just on connection failures once a credential eventually does expire |
| An application can't participate in Vault dynamic secrets without a real refactor | The application reads a static connection string once at startup and has no mechanism to renew or refetch a lease before expiry | Either refactor the application to be lease-aware (fetch/renew before TTL expiry) or accept static secrets with scheduled dual-secret rotation for that specific legacy component |
| A user reports they can still perform actions minutes after an admin revoked their access | The access token issued before revocation remains valid until its `exp` claim, since JWTs have no built-in revocation | This is expected behavior for a short-TTL-only design (the token expires naturally within the TTL window); if immediate revocation is a hard requirement, add a deny-list check on the specific sensitive action, understanding the added state/network cost |
| A deny-list-backed revocation check adds meaningful latency across every single request | The deny-list lookup (even at Redis O(1) cost) is being checked on every request instead of cached locally, or the local cache TTL is too aggressive | Add a short local cache (seconds) in front of the deny-list lookup, chosen against the actual revocation-propagation SLA needed, not left unbounded |
| A stolen refresh token is used by an attacker weeks after the legitimate user's last login | Refresh tokens weren't rotated on use, or reuse detection wasn't implemented — a static, long-lived refresh token has no mechanism to detect it's been copied and is being used by two parties | Implement refresh token rotation (new token issued and old one invalidated on every use) with reuse detection (a replayed, already-rotated token immediately revokes the entire token family) |
| Two application instances briefly disagree about whether a secret is current during a rotation | Readers refreshing config/secrets at different cadences during the grace period is expected, not a bug, as long as both the old and new credential remain simultaneously valid throughout that window | This is the correct, intended behavior of the dual-secret pattern during its grace period — the bug would be if one of the two credentials stopped working before every reader had transitioned |

---

## Tradeoffs & when NOT to use it

- **Don't skip the grace period "to close the exposure window faster" after a suspected leak.** Revoking the old credential immediately, before confirming every reader has the new one, converts a security incident into a security incident *plus* an outage — extend rotation urgency by shortening the grace period deliberately and carefully, not by skipping it.
- **Don't force dynamic secrets onto an application that structurally can't be made lease-aware without real engineering investment.** Static secrets with disciplined dual-secret rotation is a legitimate, common production pattern for legacy components — dynamic secrets are the better default for anything new, not a mandatory migration for everything old.
- **Don't add a deny-list-backed revocation check to every JWT verification path by default.** It reintroduces the network round-trip and shared-state dependency that stateless JWT verification exists to avoid; reserve it for genuinely sensitive actions or applications with an explicit, hard revocation-latency requirement, and rely on short access-token TTL alone for the common case.
- **Don't set an access-token TTL longer than necessary "to reduce refresh traffic."** The TTL is the direct bound on how long a compromised or should-be-revoked token stays dangerous with no additional infrastructure — every extra minute of TTL is extra blast radius, traded for a marginal reduction in refresh-endpoint load that's usually cheap to serve anyway.
- **Don't skip refresh-token rotation because "the refresh token is already long-lived, rotating it doesn't matter."** Rotation-with-reuse-detection is precisely what makes a long-lived refresh token's compromise *detectable* — a static, non-rotated refresh token gives an attacker who steals it the same multi-week access window with zero chance of the legitimate user's normal usage ever revealing the theft.
- **Don't cache a deny-list "not revoked" result for longer than your actual incident-response SLA tolerates.** A local cache in front of a revocation check is correct for performance, but its TTL needs to be chosen against how fast a revocation must actually propagate, not left at an arbitrary default that quietly reintroduces the same staleness the deny list was added to eliminate.

---

## Interview questions

### Q1 — Explain the dual-secret rotation pattern and why revoking the old credential immediately after creating the new one causes an outage.
**Testing:** the core mechanism, not just "rotate secrets regularly."
**Answer:** The pattern maintains both old and new credentials as simultaneously valid across a grace period long enough for every reader to pick up the new one on its own refresh cadence, then revokes the old one only after that window elapses. Revoking immediately assumes every reader has already switched, which is false for anything caching the credential in-process or reading config on a slower cadence than the rotation — those readers get a hard auth failure the moment the old credential is revoked while they're still using it.
**Follow-up trap:** *"How do you determine the correct grace period length?"* — it must exceed the slowest reader's actual refresh interval (cache TTL, restart/deploy cadence, whichever is longest), not a fixed arbitrary number — getting this wrong in either direction either causes an outage (too short) or needlessly extends the exposure window if the rotation was leak-driven (too long).

### Q2 — Why do Vault dynamic secrets eliminate the rotation problem rather than just automating it?
**Testing:** whether the structural difference (no durable secret at all) is understood versus "Vault rotates faster."
**Answer:** Dynamic secrets are generated per-lease, on request, unique to that lease, and auto-revoked by Vault at TTL expiry — there's no durable, long-lived credential sitting anywhere (a config file, Parameter Store) that ever needs rotating, because each credential is disposable by construction. Automating rotation (even the fastest scheduled rotation) still has a static secret existing in a durable form between rotations; dynamic secrets remove that window entirely.
**Follow-up trap:** *"What's the hard requirement an application must meet to use dynamic secrets at all?"* — it must be lease-aware, able to request or renew a fresh credential before the current lease's TTL expires and handle a lease expiring mid-operation — a legacy application reading a static connection string once at startup structurally cannot participate without real code changes.

### Q3 — Why does a JWT have no built-in revocation mechanism, and what's the direct consequence for choosing its TTL?
**Testing:** the fundamental stateless-verification tradeoff.
**Answer:** A JWT's whole value proposition is local, network-call-free verification via signature check — a resource server doesn't ask a central authority "is this still valid," it just checks the signature and the `exp` claim. That design has no mechanism to invalidate a specific already-issued token before its expiry, which makes the TTL a direct, quantifiable bound on how long a compromised or should-be-revoked token remains dangerous, and is the specific reason 2026 consensus guidance converges on 5-15 minutes for access tokens rather than hours.
**Follow-up trap:** *"If revocation matters this much, why not just always use a deny list?"* — a deny list reintroduces the network round-trip and shared-state dependency stateless verification was designed to avoid, for every single request — it's a legitimate choice for genuinely sensitive actions or a hard revocation-latency requirement, but applying it universally defeats the reason JWTs were chosen over server-side sessions in the first place.

### Q4 — Explain refresh token rotation with reuse detection, and why it's the mechanism that makes a long-lived refresh token safe.
**Testing:** the actual theft-detection logic, not just "refresh tokens get rotated."
**Answer:** Every refresh token is single-use: using it to mint a new access token also issues a new refresh token and invalidates the one just used. If that already-invalidated (rotated) refresh token is ever presented again, it's a replay — meaning two parties (the legitimate client, which already moved to the new token, and an attacker holding a stolen copy of the old one) both tried to use the same credential, which is detectable specifically because rotation makes the old token's reuse anomalous rather than normal.
**Follow-up trap:** *"When reuse is detected, should you revoke just that one token or something broader?"* — the entire token family (every token descended from that original session), not just the flagged token — by the time reuse is detected, the attacker may have already used the stolen token to mint further refresh tokens downstream of it, so revoking only the one detected token leaves those descendants still valid.

### Q5 — A 2026 consensus guideline recommends 5-15 minute access-token TTLs. What's the actual reasoning behind that specific range, not just "shorter is more secure"?
**Testing:** whether the number is understood as a deliberate tradeoff, not an arbitrary security-theater default.
**Answer:** It's the practical bound on "how stale can any resource server's view of token validity be, and how long can a stolen/should-be-revoked token remain usable" — short enough that the blast radius of a compromised token is genuinely small without needing any additional revocation infrastructure (a deny list), but long enough to avoid excessive refresh-endpoint traffic and latency from re-authenticating too frequently.
**Follow-up trap:** *"Would a 1-hour access-token TTL be indefensible for every application?"* — no — for a low-sensitivity application with an acceptable risk profile and infrequent refresh-traffic concerns, a longer TTL is a legitimate, deliberate choice; the point isn't that 5-15 minutes is universally mandatory, it's that whatever TTL is chosen should be a conscious tradeoff against the specific application's revocation-cost tolerance, not a default copied without understanding what it's trading away.

### Q6 — Design the caching strategy for a Redis-backed JWT deny list, given the lookup itself is cheap (O(1), ~50KB per 10,000 entries) but still a network call on every request.
**Testing:** whether local caching in front of a cheap-but-nonzero-cost check is understood as still worth doing, with the right constraint.
**Answer:** Cache "is this token revoked" results locally with a short TTL (seconds, not minutes) to avoid a Redis round-trip on every single request, choosing that local TTL explicitly against the actual revocation-propagation SLA the system needs (e.g., "a revoked session must stop working within 30 seconds") rather than an arbitrary default.
**Follow-up trap:** *"What's the failure mode if the local cache TTL is set too long?"* — a revoked token's local cache entry (cached as "not revoked" before the revocation happened) continues being treated as valid until the cache entry expires, silently reintroducing the exact staleness the deny list was added specifically to eliminate — the cache TTL needs to be shorter than whatever revocation latency the deny list was supposed to guarantee.

### Q7 — A legacy service reads a database connection string once at startup and never refreshes it. Can it use Vault dynamic secrets, and if not, what's the alternative?
**Testing:** applied judgment about the real constraint dynamic secrets impose.
**Answer:** Not without a real code change — dynamic secrets require the application to request or renew a lease before it expires, and a service that reads a static connection string once at startup has no such mechanism; its lease would simply expire and the credential would stop working with no renewal path. The alternative is static secrets (from Secrets Manager or Vault's static-secret/KV mode) with a scheduled dual-secret rotation the service picks up on its next restart, accepting a longer effective credential lifetime as the tradeoff for not requiring an application refactor.
**Follow-up trap:** *"Is there a middle-ground option short of a full application refactor?"* — a sidecar or init-container pattern that fetches a dynamic secret and writes it to a location the legacy app reads at startup, combined with a scheduled restart cadence, can approximate some of dynamic secrets' benefit (shorter-lived credentials than a purely static one) without the app itself becoming lease-aware — though this only works if the app's restart cadence is frequent enough relative to the lease TTL to avoid using an expired credential.

### Q8 — Walk through what happens, mechanically, when an admin clicks "revoke this user's session" in an application using short-TTL JWTs with no deny list.
**Testing:** whether the honest limitation is stated plainly rather than glossed over.
**Answer:** The admin action can revoke the user's *refresh token* (delete/invalidate it server-side, since refresh tokens are checked against a store), preventing any *future* access token from being minted — but any access token already issued and not yet expired remains valid and usable until its `exp` claim passes, since there's no mechanism to invalidate an already-issued JWT early in this design. The user's access effectively ends within the access-token TTL window (5-15 minutes), not instantly.
**Follow-up trap:** *"Is a 5-15 minute delay before revocation fully takes effect acceptable for every use case?"* — no — for anything requiring genuinely immediate revocation (a compromised admin account, an active financial transaction), that delay is unacceptable, and the correct fix is adding a deny-list check specifically on sensitive actions/endpoints rather than lowering the access-token TTL further (which has diminishing returns and rising refresh-traffic cost) or accepting the gap silently.

### Q9 — Compare the operational cost of static-secret dual-rotation versus Vault dynamic secrets for a fleet of 50 microservices sharing a handful of databases.
**Testing:** a realistic, applied cost/complexity tradeoff at scale.
**Answer:** Static-secret dual rotation needs a scheduled, tested rotation process per credential (or per credential type, if automated via Secrets Manager templates), with grace-period tuning per consumer's refresh cadence — manageable but real, ongoing operational surface that scales with the number of distinct credentials. Dynamic secrets shift the operational cost to a one-time (per service) integration effort to make each of the 50 services lease-aware, after which Vault handles issuance/expiry/revocation centrally with no per-rotation-event coordination needed — a better amortized cost at that scale, provided the services can actually be made lease-aware without prohibitive refactoring cost.
**Follow-up trap:** *"If 40 of the 50 services are legacy and can't easily be made lease-aware, does that change the recommendation?"* — yes — a mixed approach (dynamic secrets for the 10 lease-aware-capable services, disciplined static dual-rotation for the 40 legacy ones) is more realistic than an all-or-nothing migration, and forcing dynamic secrets onto services that can't support them well is a common, avoidable source of production incidents from lease-expiry-related failures in code never designed to handle mid-operation credential expiration.

### Q10 — Why does a Secrets Manager rotation Lambda's `finishSecret` step demote the old credential to `AWSPREVIOUS` rather than deleting it outright?
**Testing:** whether the rollback-safety reasoning behind the labeling scheme is understood.
**Answer:** Keeping the prior credential retrievable (not deleted) as `AWSPREVIOUS` provides an immediate rollback path if the newly-promoted `AWSCURRENT` credential turns out to have a problem discovered shortly after rotation completes — deleting the old credential the moment rotation finishes would remove that safety net, forcing a full new rotation cycle (or manual credential recreation) to recover from a bad rotation instead of a quick rollback to the still-existing previous version.
**Follow-up trap:** *"How long should AWSPREVIOUS be retained before actual deletion, and what determines that window?"* — long enough to cover the realistic detection window for a rotation-introduced problem (monitoring/alerting latency plus a reasonable human response time), balanced against not leaving a stale, unused credential valid indefinitely as its own lingering exposure — this is a deliberate policy choice, not a default AWS enforces uniformly, and teams should set an explicit retention/cleanup policy for `AWSPREVIOUS` rather than leaving it unmanaged.

### Q11 — A team caches JWT signature-verification results to "reduce CPU cost," claiming this is the same class of optimization as caching a deny-list lookup. Evaluate that claim.
**Testing:** whether the distinction between cheap-local-computation and network-bound-lookup caching is understood.
**Answer:** They're not the same class of optimization — JWT signature verification is a local cryptographic operation with no network call, and its cost is typically negligible compared to the rest of a request's processing; caching it mainly risks incorrectly treating a token as still valid past a boundary condition (like `exp`) if the cache isn't invalidated correctly, for a CPU saving that's rarely meaningful. Deny-list lookup caching is solving a genuinely different problem — avoiding a real network round-trip to Redis on every request — which is a legitimate, meaningful cost to optimize.
**Follow-up trap:** *"Is there ever a legitimate reason to cache signature verification results?"* — in an extremely high-throughput, latency-sensitive path where even negligible per-request CPU adds up at massive scale, caching the verified-claims result for the remaining lifetime of that specific token (bounded strictly by its own `exp`, never longer) could be a reasonable micro-optimization — but it's a narrow, scale-specific case, not a general recommendation, and the caching must still respect the token's own expiry exactly.

---

## Red flags that fail you

- Describing secret rotation without naming the dual-secret/grace-period mechanism, or claiming a credential can be rotated by simply revoking the old one and issuing a new one atomically.
- Claiming Vault dynamic secrets are a drop-in replacement for any application without naming the lease-aware requirement that rules out legacy static-connection-string apps.
- Recommending long JWT access-token TTLs "for convenience" without acknowledging the direct revocation-cost tradeoff being made.
- Not knowing that a JWT has no built-in revocation mechanism, or claiming logout instantly invalidates an already-issued access token in a stateless design.
- Describing refresh tokens as long-lived and stopping there, without mentioning rotation-with-reuse-detection as what actually makes that safe.
- Recommending a deny-list check on every JWT verification path by default, without weighing the network/shared-state cost it reintroduces.
- Setting or accepting a grace period for rotation shorter than the slowest consumer's actual refresh cadence.
- Not having a clear answer for "how long after an admin revokes a user's access does that access actually stop working, mechanically" in a JWT-based system.

---

## Cheat card

```
DUAL-SECRET ROTATION: never a moment with only ONE valid credential.
  create new (both valid) -> readers pick up new on THEIR OWN cadence
  -> GRACE PERIOD >= slowest reader's refresh interval -> THEN revoke old.
  Secrets Manager rotation Lambda 4-step contract: createSecret ->
  setSecret -> testSecret -> finishSecret (AWSPENDING -> AWSCURRENT,
  old -> AWSPREVIOUS, not deleted -- rollback safety net).

DYNAMIC SECRETS (Vault): eliminate rotation, don't automate it. Per-
  lease unique credential, TTL-bound, auto-revoked at expiry -- nothing
  durable to rotate. HARD CONSTRAINT: app must be LEASE-AWARE (renew/
  refetch before expiry) -- a static connection-string legacy app can't
  participate without a refactor.

JWT: NO built-in revocation -- stateless verification = no network call
  to check validity = no way to invalidate early. TTL is a DIRECT bound
  on blast radius of a compromised/should-be-revoked token.
  2026 consensus: access token 5-15 min TTL. refresh token 7-30 days,
  ACTUALLY revocable (checked server-side on every use).

REFRESH TOKEN ROTATION + REUSE DETECTION: every refresh = single-use,
  issues a new one, invalidates itself. REPLAY of an already-rotated
  refresh token = THEFT SIGNAL -> revoke the ENTIRE token family (not
  just that token -- attacker may have chained further tokens from it).

DENY LIST (Redis, jti-keyed): O(1) lookup, ~50KB/10k revoked entries.
  Reintroduces network call + shared state -- use for SENSITIVE actions
  only, not every verification, by default. Cache "not revoked" result
  LOCALLY with a SHORT TTL (seconds) chosen against your actual
  revocation-propagation SLA, or the cache itself becomes the staleness
  bug the deny list was added to fix.

REVOKING A USER'S ACCESS in a pure short-TTL-JWT, no-deny-list design:
  refresh token dies immediately (no NEW access tokens issued), but any
  ALREADY-ISSUED access token stays valid until its own exp -- up to the
  full access-token TTL (5-15 min) of lag before revocation fully takes
  effect. Needs a deny list on sensitive paths if that lag is unacceptable.
```

## Sources

- [How to Implement Vault Secret Rotation for Kubernetes ServiceAccounts — OneUptime](https://oneuptime.com/blog/post/2026-02-09-vault-secret-rotation-serviceaccounts/view) — accessed 2026-08-03
- [Secrets management & rotation strategies — Medium](https://medium.com/@rajesh.sgr/secrets-management-rotation-strategies-76eec21a6a36) — accessed 2026-08-03
- [How to Create Secret Rotation Strategies — OneUptime](https://oneuptime.com/blog/post/2026-01-30-security-secret-rotation-strategies/view) — accessed 2026-08-03
- [Token Lifetime Best Practices: Access, Refresh, ID, and Session Tokens in 2026 — CIAM Compass](https://guptadeepak.com/ciam-compass/guides/token-lifetime-best-practices/) — accessed 2026-08-03
- [JWT Best Practices in 2026 — What to Use, What to Avoid — JSONCraft](https://jsoncraft.dev/docs/jwt-best-practices-2026/) — accessed 2026-08-03
- [JWT Refresh Token: Rotation, Revocation, and Secure Storage — Jsonic](https://jsonic.io/guides/jwt-refresh-token) — accessed 2026-08-03
- [JWT Token Lifecycle: Expiration, Refresh, Revocation, and Spring Boot Validation — Skycloak](https://skycloak.io/blog/jwt-token-lifecycle-management-expiration-refresh-revocation-strategies/) — accessed 2026-08-03

## Changelog
- 2026-08-03 — created
