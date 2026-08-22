# RBAC/ABAC/ReBAC, Multi-Tenant Isolation, Zero Trust

> **Track:** T12 DevOps, Infra & Security · **Time:** 2h · **Prereqs:** T12-owasp, T12-secrets · **Updated:** 2026-08-05
> **Module id:** `T12-authz` · **Tags:** security, authz, multi-tenancy, zero-trust, critical

## The 30-second version

The three models answer three different questions and they compose rather than compete: RBAC answers "what may this job function do," ABAC answers "under what conditions," and ReBAC answers "what is this specific user's relationship to this specific object," which is the only one of the three that scales to per-document sharing and the only one that answers the reverse query ("who can see this?") without evaluating every user. Zanzibar is the reference implementation, and its published numbers are the ones to know: over 2 trillion relation tuples in ~100 TB, more than 10 million client QPS, p95 under 10 ms, and greater than 99.999% availability across three years on 10,000+ servers. Multi-tenant isolation is where authorization actually fails in production, and the enforcement ladder matters more than the model: developer discipline loses to ORM scopes, which lose to Postgres RLS with `FORCE ROW LEVEL SECURITY` and `SET LOCAL` inside an explicit transaction, which loses to per-tenant credentials, which loses to a silo. Zero Trust (NIST SP 800-207, August 2020) is about removing implicit trust from network location, with a Policy Engine and Policy Administrator forming a PDP and a PEP in front of every resource, and the single most important thing to say about it in an interview is that it is orthogonal to object-level authorization: a perfectly zero-trust network still hands tenant B's rows to tenant A when the `WHERE` clause is wrong, which is exactly why Broken Access Control is A01 in the web Top 10 and BOLA is API1 in the API Top 10.

## Why this gets asked

Because authorization is the #1 category in both OWASP lists simultaneously and almost nobody can design it. A01:2025 Broken Access Control is #1 in the web Top 10 with 40 CWEs and a 3.73% average incidence across 2.8 million applications, and API1:2023 Broken Object Level Authorization is #1 in the API Top 10. Those are the same bug seen from two angles: the request carried a valid session and asked for an object it did not own, and nothing checked.

The interviewer has lived one of two incidents. Either a cross-tenant leak, where a background job, a cache key, a search index, or a report query ran without the tenant predicate and one customer saw another's data, which is a breach-notification event and not a bug ticket. Or a role explosion, where five years of "just add a role for this" produced 400 roles for 200 people, nobody can answer "who can approve a refund," and the access review became a quarterly two-week project that everyone rubber-stamps.

The Zero Trust half is asked because the term has been so thoroughly marketed that it functions as a filter. A candidate who says "zero trust means we don't trust the network, so we buy a ZTNA product" has read a vendor page. A candidate who can name the PE/PA/PEP decomposition from SP 800-207, say which parts are genuinely deployed at scale, and then point out that none of it touches the row-level authorization bug, has thought about it.

---

## Lineage: past → present → future

**What came before.** Access control started as discretionary access control and access control lists, formalized in Lampson's 1971 protection matrix and shipped in Multics and then Unix as the owner/group/other permission bits. ACLs are per-object lists of principals, and they work beautifully at small scale and collapse at organizational scale for a specific reason: when a person changes jobs you must find and edit every object that named them. Role-Based Access Control was proposed by Ferraiolo and Kuhn at NIST in 1992 precisely to fix that indirection problem, and was standardized as ANSI INCITS 359-2004 with core, hierarchical, and constrained (separation-of-duty) variants. RBAC's own failure mode showed up within a decade and has a name: **role explosion**. Because a role is a static bundle, any dimension you need to vary (region, tenant, environment, resource sensitivity, time) multiplies the role count, so a system needing "editor" crossed with 4 regions crossed with 3 environments crossed with 2 data classifications needs 24 roles to express one job function. NIST published SP 800-162 in January 2014 to standardize Attribute-Based Access Control as the answer, building on OASIS XACML (3.0, 2013), which is where the PDP / PEP / PIP / PAP vocabulary that NIST later reused in SP 800-207 comes from. ABAC solved the combinatorics and introduced its own pain: because access is *computed* rather than *stored*, you cannot answer "who can access this document?" without evaluating the policy against every subject in the system, which makes access reviews, sharing UIs, and audit reports either impossible or O(users).

**Where it stands now.** The center of gravity for anything with user-to-user sharing moved to Relationship-Based Access Control after Google published Zanzibar at USENIX ATC 2019. Zanzibar stores relation tuples of the form `object#relation@subject`, computes `Check` by traversing that graph, and answers reverse queries natively via `Expand` and list operations. The paper's operating numbers are the ones worth memorizing because they settle the "does this scale" objection: more than 2 trillion relation tuples occupying close to 100 TB, more than 10 million client QPS in aggregate (Check peaking around 4.2M, Read 8.2M, Expand 760K, Write 25K), 95th-percentile latency under 10 ms, availability above 99.999% over three years, running on more than 10,000 servers in several dozen clusters with a median of about 500 servers per cluster, fully replicated to more than 30 locations. The 2026 open-source landscape is genuinely production-ready: OpenFGA is CNCF Incubating (originated at Auth0/Okta, used by Grafana, Docker, and Canonical), SpiceDB from AuthZed is the most Zanzibar-faithful implementation with a Watch API for cache invalidation, and Permify and Ory Keto round out the field. Cedar, AWS's policy language behind Amazon Verified Permissions, was open-sourced in 2023 and is now a CNCF Sandbox project. OPA/Rego graduated from CNCF in February 2021 and remains the default for policy-shaped decisions.

The live disagreements are three. First, **centralized PDP versus embedded evaluation**: a network call to a policy service adds 1 to 5 ms and couples your availability to it, so OPA ships as a sidecar and Zanzibar systems lean hard on caching, while a third camp argues authorization belongs *in the query* as a predicate (Postgres RLS, predicate pushdown) so it cannot be forgotten. Second, **one engine or several**: Rego is excellent at policy and bad at relationship graphs, Zanzibar systems are the reverse, and teams that force one to do both regret it. The honest current answer is that most large systems run RBAC for coarse job function, a Zanzibar-style store for resource relationships, and attribute conditions layered on top, which is why both SpiceDB (caveats) and OpenFGA (conditions) added contextual predicates to what began as a pure relationship model. Third, and most important commercially: what is *actually deployed at scale* is still overwhelmingly RBAC plus hand-written tenant predicates. Zanzibar-derived systems are real and growing (OpenAI reportedly uses SpiceDB for ChatGPT Enterprise connector permissions at tens of billions of tuples, which is secondary-sourced), but the median SaaS company in 2026 is enforcing tenant isolation with a `WHERE tenant_id = ?` written by hand in each repository, which is precisely why cross-tenant leaks remain a monthly news item.

Zero Trust followed a parallel arc. Forrester's Kindervag coined the term in 2010, Google's BeyondCorp papers (2014 onward) proved a large enterprise could actually remove VPN-based implicit trust, and NIST SP 800-207 formalized it in August 2020 with seven tenets and a PE/PA/PEP decomposition. US federal policy then forced adoption: Executive Order 14028 (May 2021), OMB M-22-09 (January 2022) requiring agencies to meet zero trust goals by the end of FY2024, and CISA's Zero Trust Maturity Model v2.0 (April 2023) with five pillars (Identity, Devices, Networks, Applications and Workloads, Data), three cross-cutting capabilities (Visibility and Analytics, Automation and Orchestration, Governance), and four maturity stages (Traditional, Initial, Advanced, Optimal). The live disagreement here is not technical, it is about honesty: what is genuinely deployed at scale is identity-aware proxies replacing VPNs for internal apps, mTLS plus SPIFFE/SPIRE workload identity inside service meshes, and device posture checks at login. What is described in SP 800-207 and is largely *not* deployed is continuous, per-request policy re-evaluation driven by real-time risk signals. Saying which half you mean is the difference between a technical answer and a marketing answer.

**Where it's heading.** High confidence: tenant isolation moves down the stack into infrastructure that enforces it structurally rather than by convention. AWS Lambda's tenant isolation mode, announced November 2025 and available in all regions except Asia Pacific (New Zealand), GovCloud, and China, is the clearest signal: you pass a tenant identifier at invoke time and Lambda guarantees an execution environment is never reused across tenants. Expect the same shape from more managed services, and expect per-tenant KMS keys and dynamically-scoped STS credentials to become the default pattern rather than the advanced one. Medium confidence: policy-as-data (Zanzibar tuples) and policy-as-code (Cedar, Rego) converge behind a single decision API, with Cedar's formal verification story pushing the industry toward policies that can be *proven* rather than tested. Low confidence and explicitly speculative: authorization for agentic systems becomes its own subdiscipline, because an agent acting on a user's behalf breaks the assumption that a request has one principal. The delegation question ("this agent may read what Alice may read, but only these three tools, only for 20 minutes, and it may not re-delegate") has no standard answer in 2026. OAuth token exchange (RFC 8693) and per-agent identities are the pieces people are assembling from, and anyone claiming a solved pattern here is selling something.

---

## Mental model

Two pictures. The first is the decision path, using NIST SP 800-207's own vocabulary, which is also XACML's:

```
                          ┌──────────────────────────────────────┐
   subject ──request──▶   │            PEP                        │
   (user / service /      │   Policy Enforcement Point            │
    agent)                │   sits in front of EVERY resource     │
                          └───────────────┬───────────────────────┘
                                          │ "may S do A on O, in context C?"
                                          ▼
                     ┌────────────────────────────────────┐
                     │   PDP  =  PE  +  PA                 │
                     │   Policy Engine decides             │
                     │   Policy Administrator issues/      │
                     │   revokes the session credential    │
                     └──────┬──────────────────────────────┘
                            │ reads from (PIPs / data sources):
       ┌────────────────────┼────────────────────┬─────────────────┐
       ▼                    ▼                    ▼                 ▼
  ID management      device posture /       relation tuples    threat intel /
  + entitlements     CDM, PKI               (Zanzibar)         activity logs, SIEM
```

The second is the one that actually predicts incidents: **the further down this ladder your check lives, the harder it is to forget.**

```
  WEAKEST  ┌──────────────────────────────────────────────────────────┐
     ▲     │ 1. Developer writes WHERE tenant_id = ? by hand           │
     │     │    fails at: the first background job, the first report,  │
     │     │              the first raw SQL, the new hire              │
     │     ├──────────────────────────────────────────────────────────┤
     │     │ 2. ORM global scope / query filter                        │
     │     │    fails at: raw SQL, migrations, admin tools, analytics  │
     │     ├──────────────────────────────────────────────────────────┤
     │     │ 3. Postgres RLS + SET LOCAL in an explicit transaction    │
     │     │    fails at: table owner without FORCE, BYPASSRLS roles,  │
     │     │              SET (not SET LOCAL) + transaction pooling    │
     │     ├──────────────────────────────────────────────────────────┤
     │     │ 4. Per-tenant DB credentials / per-tenant schema          │
     │     │    fails at: the shared connection pool                   │
     │     ├──────────────────────────────────────────────────────────┤
     ▼     │ 5. Silo: separate database / account / cluster            │
  STRONGEST│    fails at: your ops budget, at ~50 tenants              │
           └──────────────────────────────────────────────────────────┘

  Every real cross-tenant leak I have read about is a path that skipped
  the rung the rest of the system was standing on.
```

And the model-selection rule, in one line each:

```
RBAC  → "what may this JOB FUNCTION do?"      static bundles. explodes on dimensions.
ABAC  → "under what CONDITIONS?"              computed. cannot answer "who can see X?"
ReBAC → "what is this USER's RELATIONSHIP     stored graph. answers reverse queries.
         to this OBJECT?"                      bad at time-of-day / IP / MFA-level.
```

---

## How it actually works

### 1. RBAC, and the exact shape of role explosion

The NIST/ANSI model is three assignments: users→roles, roles→permissions, and (in hierarchical RBAC) roles→roles. Constrained RBAC adds static and dynamic separation of duty, which is the part almost nobody implements and the part auditors care about: SSD says a user may not be *assigned* both "requester" and "approver"; DSD says they may hold both but not *activate* both in the same session.

Role explosion is arithmetic, not sloppiness. The role count is the product of every dimension you need to vary:

```
job functions (viewer, editor, admin)                =  3
× regions (us, eu, apac, latam)                      =  4
× environments (dev, staging, prod)                  =  3
× data classifications (public, internal)            =  2
                                                     ──────
                                                       72 roles
```

Add one dimension and you multiply again. The observable symptom is that role creation outpaces headcount: if you are minting roles faster than you are hiring, RBAC has already failed for that dimension. The fix is not "more roles," it is to move the exploding dimension out of the role and into either an attribute condition (ABAC) or a relationship (ReBAC), and to keep RBAC for the genuinely coarse, genuinely static part. Keeping RBAC for job function is correct and cheap: it is the easiest model to audit, because entitlements are enumerable by a `SELECT`.

### 2. ABAC, and the reverse-query problem

ABAC evaluates a policy over four attribute sources: subject, resource, action, environment. Cedar makes the shape explicit:

```cedar
// Cedar. Deny takes precedence over permit; the language is designed to be
// analyzable, which is the actual differentiator vs Rego.
permit (
  principal in Group::"engineering",
  action == Action::"viewDocument",
  resource in Folder::"designs"
)
when {
  context.mfa_authenticated == true &&
  context.source_ip.isInRange(ip("10.0.0.0/8")) &&
  resource.classification != "restricted"
};
```

That expresses in one policy what would take dozens of RBAC roles. The cost is exact and is the thing to name in an interview: **access is computed, not stored**, so the reverse query is O(subjects). "Show me everyone who can read this document" requires evaluating the policy for every principal. That breaks three things people always need later: the sharing UI, the quarterly access review, and the "who saw this before we revoked it" incident question. It also introduces attribute freshness as a correctness property, since a decision is only as right as the staleness of the attribute feed behind it.

### 3. ReBAC and Zanzibar, including the question that separates people

Zanzibar's data model is one relation:

```
                  object          # relation   @ subject
  doc:roadmap            # owner      @ user:alice
  doc:roadmap            # viewer     @ group:eng#member
  group:eng              # member     @ user:bob
  folder:designs         # viewer     @ user:carol
  doc:mock               # parent     @ folder:designs
```

with a namespace config that says how relations derive from each other:

```
name: "doc"
relation { name: "owner" }
relation { name: "editor"
  userset_rewrite { union {
      child { _this {} }                       // direct editor tuples
      child { computed_userset { relation: "owner" } }   // owners are editors
} } }
relation { name: "viewer"
  userset_rewrite { union {
      child { _this {} }
      child { computed_userset { relation: "editor" } }  // editors are viewers
      child { tuple_to_userset {                          // INHERIT from the folder
          tupleset { relation: "parent" }
          computed_userset { relation: "viewer" } } }
} } }
```

`Check(doc:mock#viewer@user:carol)` traverses: no direct tuple, not an editor, so follow `parent` to `folder:designs` and check `viewer` there. Found. Two graph hops. This is the thing RBAC and ABAC both do badly: **inherited, per-object, user-granted permissions**, which is every document product, every repository host, and every "share this dashboard" feature.

**The new enemy problem** is the deepest question in this space and the one that reveals whether you have read the paper. Two flavors:

```
FLAVOR 1 — ACL updates applied out of order
  t1: Alice REMOVES Bob from the folder
  t2: Alice ADDS a secret document to the folder
  If a replica applies t2 before t1, Bob's Check at t1.5 succeeds. Bob reads it.

FLAVOR 2 — old ACL applied to new content
  t1: Alice REMOVES Bob from the document
  t2: Alice ADDS sensitive content to the document
  If the content read at t2 is authorized against an ACL snapshot from before
  t1 (because stale reads are fast and cheap), Bob reads the new content
  under the old permission.
```

Zanzibar's answer is the **zookie**: an opaque consistency token containing a Spanner timestamp. When content is written, the content store records the zookie of that moment. Every subsequent `Check` for that content passes the zookie, and Zanzibar guarantees evaluation at a snapshot no earlier than that timestamp. That preserves causal ordering between content updates and ACL updates while leaving Zanzibar free to pick *any* later timestamp, which is what lets it serve most checks from a stale-but-safe snapshot and hit p95 under 10 ms. The design insight worth stating: they did not choose "always strongly consistent" (too slow) or "eventually consistent" (unsafe); they made the *caller* carry the minimum-freshness requirement, so only the requests that need consistency pay for it.

Cost model for the reverse query, which is where ReBAC earns its keep: listing "everyone who can view doc X" in ABAC is O(all subjects) policy evaluations. In Zanzibar it is an `Expand` over the userset tree, bounded by the actual relationship graph, typically tens of tuples. Conversely, expressing "only during business hours from a managed device" in pure ReBAC requires you to materialize time-of-day as a relationship, which is absurd, and that is exactly why SpiceDB added caveats and OpenFGA added conditions.

### 4. Multi-tenant isolation, where the incidents actually are

The AWS SaaS Factory taxonomy is the shared vocabulary:

| Model | Shape | Isolation | Cost per tenant | Breaks at |
|---|---|---|---|---|
| **Silo** | Stack or DB per tenant | Strongest, infrastructure-enforced | Highest | ~50 tenants, where you now patch 50 databases and your migration story is a fleet operation |
| **Pool** | Shared everything, logical isolation | Weakest, code-enforced | Lowest | The first code path that forgets the predicate |
| **Bridge** | Shared compute, per-tenant schema/key | Middle | Middle | Connection pooling and schema-count limits |

Pool is where almost everyone lands and where almost every leak happens. The enforcement mechanics for Postgres:

```sql
-- 1. Turn it on. This alone is NOT enough.
ALTER TABLE documents ENABLE ROW LEVEL SECURITY;

-- 2. THE #1 GOTCHA: the table OWNER bypasses RLS by default. If your app
--    connects as the role that owns the tables (the default with ORM-managed
--    migrations) your policies do exactly nothing.
ALTER TABLE documents FORCE ROW LEVEL SECURITY;

-- 3. USING filters reads and the PRE-image of writes.
--    WITH CHECK validates the POST-image of INSERT/UPDATE.
--    Omit WITH CHECK and a tenant can UPDATE a row's tenant_id to another
--    tenant's value: a write-side cross-tenant leak that reads look clean on.
CREATE POLICY tenant_isolation ON documents
  USING      (tenant_id = current_setting('app.tenant_id', true)::uuid)
  WITH CHECK (tenant_id = current_setting('app.tenant_id', true)::uuid);

-- 4. The app role must not be superuser and must not have BYPASSRLS.
--    The built-in `postgres` role has BYPASSRLS and it cannot be removed.
CREATE ROLE app_rw LOGIN NOBYPASSRLS;
GRANT SELECT, INSERT, UPDATE, DELETE ON documents TO app_rw;

-- 5. Index it. The policy is an invisible WHERE clause on every query.
--    tenant_id must be the LEADING column of your composite indexes or you
--    get a sequential scan per request.
CREATE INDEX ON documents (tenant_id, created_at DESC);
```

**The connection-pooling trap, which is the single most common way RLS fails in production.** `SET app.tenant_id = ...` is session-scoped. With PgBouncer in transaction pooling mode (or any pool that hands the same backend connection to a different request), the value survives into the next transaction on that connection and the next tenant inherits it. The fix is `SET LOCAL` inside an explicit transaction, which is scoped to the transaction and rolled back at commit:

```python
# (lab pending)tenant_ctx.py
from contextlib import contextmanager

@contextmanager
def tenant_scope(conn, tenant_id: str):
    """
    SET LOCAL is transaction-scoped, so it cannot leak across a pooled
    connection. SET (without LOCAL) is session-scoped and WILL leak under
    PgBouncer transaction pooling. This distinction is the bug.
    """
    with conn.transaction():                       # explicit txn is REQUIRED
        # set_config(name, value, is_local=true) == SET LOCAL, but parameterized.
        conn.execute("SELECT set_config('app.tenant_id', %s, true)", (str(tenant_id),))
        yield conn
        # commit/rollback resets it; nothing to clean up

def assert_isolated(conn) -> None:
    """Fail closed. Run this in a test AND as a startup self-check."""
    row = conn.execute("SELECT current_setting('app.tenant_id', true)").fetchone()
    if row[0] in (None, ""):
        raise RuntimeError("no tenant context: refusing to query tenant tables")
```

**RLS is a boundary with known holes, and naming them is senior signal.** Two PostgreSQL CVEs are worth carrying:

- **CVE-2024-10976**: incomplete tracking of tables with row security meant a reused query plan referenced below a subquery, a `WITH` query, a security-invoker view, or a SQL-language function could view or change *different rows than intended* when the user ID changed. The boundary was correct; the plan cache was not.
- **CVE-2025-8713** (disclosed 2025-08-14, fixed in 17.6 / 16.10 / 15.14 / 14.19 / 13.22): PostgreSQL **optimizer statistics** let a user read sampled data that a row security policy intended to hide, and read sampled data inside views they cannot access, by crafting a leaky operator. Histograms and most-common-values lists are a side channel around RLS. The lesson: RLS constrains the *query results*, not everything the query planner is willing to tell you about the data.

**The leaks that are not in the database at all.** Cross-tenant leakage is rarely one dramatic flaw; it is an accumulation of paths that skipped a rung:

- A **cache key** without the tenant id. `user_profile:{user_id}` looks fine until two tenants have colliding external ids, or until the key is `dashboard:{dashboard_id}` and dashboard ids are global.
- A **background worker** running outside tenant context, because the job payload carried an object id and the worker helpfully looked it up with an admin connection.
- A **search index** with no tenant filter, or with the filter applied in the application after the top-K comes back, so tenant A's documents consumed the K slots and tenant B's results silently disappeared while tenant A's titles appeared in the "did you mean" suggestions.
- **Object storage** prefixes without a per-tenant IAM boundary, so a path-traversal or an id guess crosses tenants.
- **Sequential ids** plus a missing object-level check, which is BOLA in its purest form. UUIDs raise the cost of enumeration and are not authorization.
- **Error and timing differences** between "not found" and "not yours," which turn a 404 into an existence oracle.
- For anyone serving LLMs multi-tenant: **KV-cache sharing across tenants**. Prefix-cache reuse is the single biggest throughput win in vLLM-class serving and it is also a cross-tenant side channel, because cache-hit timing lets one tenant infer whether a prefix was recently processed and, in the research, partially reconstruct another tenant's prompt. If you share a prefix cache across tenants, you have made a deliberate confidentiality tradeoff and should be able to say so. (This threat class is secondary-sourced; treat the specific reconstruction rates as unverified and the mechanism as sound.)

**AWS-side enforcement worth naming.** The dynamically-scoped credential pattern: the request handler calls `sts:AssumeRole` with a session tag carrying the tenant id, and the role's policy conditions the resource on that tag, so the credential the code holds *physically cannot* reach another tenant's data even if the query is wrong.

```json
{
  "Effect": "Allow",
  "Action": ["dynamodb:GetItem", "dynamodb:Query", "dynamodb:PutItem"],
  "Resource": "arn:aws:dynamodb:us-east-1:111122223333:table/Documents",
  "Condition": {
    "ForAllValues:StringEquals": {
      "dynamodb:LeadingKeys": ["${aws:PrincipalTag/tenant}"]
    }
  }
}
```

This is rung 4 of the ladder implemented in IAM rather than in the database, and it is strictly better than rung 1 because the enforcement point is outside the process that has the bug. And AWS Lambda's tenant isolation mode (November 2025) is rung 5 for compute: pass a tenant identifier on invoke, and Lambda guarantees an execution environment is never reused across tenants. The tradeoff is exact and worth stating: you multiply cold starts by the number of active tenants, so a 10,000-tenant function with low per-tenant traffic pays a cold start on nearly every request, which makes it a good fit for high-value, low-cardinality tenants and a bad fit for a long tail.

### 5. Zero Trust, said honestly

SP 800-207's seven tenets, compressed: all data sources and computing services are resources; all communication is secured regardless of network location; access is granted per-session; access is determined by dynamic policy including observable client, service, and asset state; the enterprise monitors the integrity and security posture of all owned and associated assets; all authentication and authorization is dynamic and strictly enforced before access is allowed; and the enterprise collects as much information as possible about assets, infrastructure, and communications to improve its posture.

The logical decomposition matters more than the tenets: **PE + PA = PDP**, and a **PEP** in front of every resource. The Policy Engine decides, the Policy Administrator establishes or tears down the session credential, and the PEP is the thing in the data path. Everything a vendor sells you is one of those three boxes.

What is actually deployed at scale in 2026: identity-aware proxies replacing VPN for internal apps (the BeyondCorp pattern, now productized by every cloud), mTLS with SPIFFE/SPIRE workload identity inside service meshes so services authenticate as workloads rather than as IP addresses, device posture as a factor at authentication time, and short-lived scoped credentials. What is described in the standard and is mostly not deployed: *continuous* re-evaluation of policy per request against live risk telemetry. Most "zero trust" deployments evaluate richly at session establishment and then coast on a token for its lifetime, which is a meaningful gap between the document and the practice and is a good thing to volunteer.

**And the point that ties the module together:** zero trust is about the *network* and the *session*. Object-level authorization is about the *row*. They are orthogonal. Full mTLS, device posture, per-session credentials, and an identity-aware proxy in front of every service will not stop `GET /api/documents/8123` from returning another tenant's document when the handler looks it up by id and forgets to check ownership. A01 and BOLA live entirely on the other side of the PEP.

---

## Build it from scratch

A minimal Zanzibar-style checker. This is the thing to write on a whiteboard, and getting the userset rewrite and the cycle guard right is the whole exercise.

```python
# (lab pending)rebac.py
# Minimal ReBAC check with computed usersets and parent inheritance.
from collections import defaultdict
from dataclasses import dataclass, field

Tuple_ = tuple[str, str, str]          # (object, relation, subject)

@dataclass
class Store:
    tuples: set[Tuple_] = field(default_factory=set)
    # namespace -> relation -> rewrite spec
    #   ("computed", rel)          : this relation includes members of `rel` on the SAME object
    #   ("tuple_to_userset", r, t) : follow relation `r` to a parent object, then check `t` there
    rewrites: dict[str, dict[str, list]] = field(default_factory=lambda: defaultdict(dict))

    def add(self, obj: str, rel: str, sub: str) -> None:
        self.tuples.add((obj, rel, sub))

    def _direct(self, obj: str, rel: str) -> set[str]:
        return {s for (o, r, s) in self.tuples if o == obj and r == rel}

    def check(self, obj: str, rel: str, subject: str, _seen: set | None = None) -> bool:
        seen = _seen if _seen is not None else set()
        key = (obj, rel, subject)
        if key in seen:                       # cycle guard: group A member of group B member of A
            return False
        seen.add(key)

        for s in self._direct(obj, rel):
            if s == subject:
                return True
            if "#" in s:                      # userset: "group:eng#member"
                sub_obj, sub_rel = s.split("#", 1)
                if self.check(sub_obj, sub_rel, subject, seen):
                    return True

        ns = obj.split(":", 1)[0]
        for spec in self.rewrites[ns].get(rel, []):
            if spec[0] == "computed":
                if self.check(obj, spec[1], subject, seen):
                    return True
            elif spec[0] == "tuple_to_userset":
                _, via, target_rel = spec
                for parent in self._direct(obj, via):
                    if self.check(parent, target_rel, subject, seen):
                        return True
        return False

    def expand(self, obj: str, rel: str, _seen: set | None = None) -> set[str]:
        """The REVERSE query ABAC cannot do cheaply: who has this relation?"""
        seen = _seen if _seen is not None else set()
        if (obj, rel) in seen:
            return set()
        seen.add((obj, rel))
        out: set[str] = set()
        for s in self._direct(obj, rel):
            if "#" in s:
                o2, r2 = s.split("#", 1)
                out |= self.expand(o2, r2, seen)
            else:
                out.add(s)
        ns = obj.split(":", 1)[0]
        for spec in self.rewrites[ns].get(rel, []):
            if spec[0] == "computed":
                out |= self.expand(obj, spec[1], seen)
            elif spec[0] == "tuple_to_userset":
                _, via, target_rel = spec
                for parent in self._direct(obj, via):
                    out |= self.expand(parent, target_rel, seen)
        return out


s = Store()
s.rewrites["doc"]["editor"] = [("computed", "owner")]
s.rewrites["doc"]["viewer"] = [("computed", "editor"), ("tuple_to_userset", "parent", "viewer")]

s.add("doc:roadmap", "owner", "user:alice")
s.add("doc:roadmap", "viewer", "group:eng#member")
s.add("group:eng", "member", "user:bob")
s.add("folder:designs", "viewer", "user:carol")
s.add("doc:mock", "parent", "folder:designs")

assert s.check("doc:roadmap", "viewer", "user:alice")   # owner → editor → viewer
assert s.check("doc:roadmap", "viewer", "user:bob")     # via group userset
assert s.check("doc:mock",    "viewer", "user:carol")   # via folder inheritance
assert not s.check("doc:mock", "viewer", "user:bob")
assert s.expand("doc:roadmap", "viewer") == {"user:alice", "user:bob"}
```

What this deliberately does not have, and what you should say it does not have: no zookie or consistency token (so it has the new enemy problem), no caching or leopard-style denormalized index for deep group nesting, no negation, and no contextual conditions. Naming the gaps is the answer to "what would you add next."

The tenant-isolation half of the lab is a Postgres instance with RLS enabled, a deliberately-owner-connected app role that demonstrates policies silently doing nothing until `FORCE ROW LEVEL SECURITY` is added, and a PgBouncer transaction-pooling reproduction of the `SET` versus `SET LOCAL` leak: **`(lab pending)`**.

---

## How it's done in production

**Choosing the stack, honestly:**

| Need | Reach for | Do not reach for |
|---|---|---|
| Coarse job function, auditable entitlements | RBAC in your own tables | A policy engine |
| Contextual conditions (MFA level, IP range, time, data class) | Cedar or OPA/Rego | Minting more roles |
| Per-object sharing, inheritance, "who can see this?" | OpenFGA / SpiceDB / Permify | Rego (relationship graphs are the wrong shape for it) |
| Tenant isolation | RLS + `FORCE` + `SET LOCAL`, or scoped STS credentials | Developer discipline |
| K8s and infra policy | OPA/Gatekeeper, Kyverno | A Zanzibar store |
| Formal "prove no policy grants X" | Cedar (designed for analysis) | Rego (Turing-complete, not analyzable) |

**Deployment topology tradeoffs:**

- **Centralized PDP service**: one place to change policy, one place to audit. Costs a network hop on every decision (1 to 5 ms typical) and couples your availability to it. Mitigate with aggressive caching and a fail-closed default, and be explicit that fail-closed means a PDP outage is a full outage.
- **Sidecar** (the OPA default): sub-millisecond decisions, no availability coupling, at the cost of a policy-distribution problem and N copies of possibly-divergent policy.
- **In-query** (RLS, predicate pushdown): the strongest guarantee, because the check cannot be forgotten by a code path that does not know it exists. Limited to what you can express as a SQL predicate, and it moves your authorization logic into the database, which some teams find unmaintainable.

The practical answer for a large system is all three at different layers, and being able to say *which decision goes where* is the senior signal.

**Failure-mode table:**

| Symptom | Cause | Fix |
|---|---|---|
| RLS policies exist, are enabled, and filter nothing | The app connects as the table **owner**, who bypasses RLS by default | `ALTER TABLE ... FORCE ROW LEVEL SECURITY`, and separate the migration role from the runtime role |
| Tenant A intermittently sees tenant B's rows under load, and only under load | `SET app.tenant_id` (session-scoped) with PgBouncer in transaction pooling mode; the value survives into the next tenant's transaction | `SET LOCAL` / `set_config(..., true)` inside an explicit transaction |
| Reads are correctly scoped but a tenant's row appears in another tenant's table | Policy has `USING` but no `WITH CHECK`, so an `UPDATE` may rewrite `tenant_id` | Add `WITH CHECK` with the same predicate |
| Every query on a tenant table does a sequential scan after enabling RLS | The policy predicate is not indexable, or `tenant_id` is not the leading column | Index `(tenant_id, ...)`; verify with `EXPLAIN` that the policy predicate is an index condition |
| A user reads data RLS should hide, without ever running a query that returns it | Optimizer statistics side channel (CVE-2025-8713): histograms and MCV lists leak sampled values | Patch to 17.6 / 16.10 / 15.14 / 14.19 / 13.22 or later |
| A cached plan under a subquery or SQL function returns rows for the wrong user | CVE-2024-10976: incomplete tracking of RLS tables across user id changes in reused plans | Patch; avoid reusing a pooled connection across principals without a reset |
| Nightly job emails tenant A's report to tenant B | Background worker looked the object up by id with an admin connection, outside tenant context | Jobs carry `(tenant_id, object_id)` and run inside `tenant_scope`; make the admin connection unavailable to worker code |
| Two tenants see each other's cached dashboard | Cache key omits tenant id, or uses a globally-unique-looking id that is not | Tenant id is a mandatory prefix on every cache key; enforce in the cache client wrapper, not by convention |
| Tenant B's search results silently disappear as tenant A's corpus grows | Tenant filter applied *after* top-K retrieval instead of as a pre-filter in the index | Filter inside the index (per-tenant partition, or a filtered ANN query), never post-hoc |
| `GET /objects/8123` returns another tenant's object with a valid session | BOLA / A01: object fetched by id, ownership never checked | Authorize on the object at the data-access layer using the requester's identity; UUIDs are not authorization |
| 404 vs 403 reveals which object ids exist | Existence oracle from differentiated responses | Return the same status and body for "not found" and "not yours" |
| One LLM tenant can infer another's prompts from response timing | Shared prefix/KV cache across tenants in a pooled serving deployment | Partition the prefix cache by tenant, or accept and document the tradeoff explicitly |
| Roles grew from 40 to 400 in three years, access review takes two weeks | Role explosion: a varying dimension was encoded as roles | Move the exploding dimension into an attribute condition or a relationship; keep RBAC for job function only |
| Policy service outage takes the whole product down | Centralized PDP with fail-closed and no cache | Decision cache with a short TTL, sidecar topology, and an explicitly-reasoned fail-open/fail-closed policy per action class |

---

## Tradeoffs & when NOT to use it

- **Do not deploy a Zanzibar-style system for a product with no user-to-user sharing.** If permissions are "your org's members can see your org's data" and nothing else, you have needed RBAC plus a tenant predicate the whole time, and you have just added a distributed database, a consistency model, and a new on-call rotation to solve a `WHERE` clause. The honest trigger for ReBAC is per-object grants with inheritance, or a genuine need for the reverse query.
- **Do not use pure ABAC for anything that needs a sharing UI or an access review.** Computed access cannot be enumerated. If a product manager will ever ask "show the user who has access to this," you need stored relationships for at least that part.
- **Do not use pure ReBAC for contextual conditions.** Time of day, IP range, MFA level, and device posture are not relationships, and materializing them as tuples is how you get a store with a billion junk rows. Use caveats/conditions, or layer a policy engine.
- **Do not pick a silo model reflexively "because isolation."** At 50 tenants you own 50 databases: 50 migrations per release, 50 backup verifications, 50 sets of connection limits, and a per-tenant cost floor that kills your low-tier pricing. Silo is right for regulated, high-value, low-cardinality tenants, and is a tax you cannot afford for a long tail. Bridge (shared compute, per-tenant schema or per-tenant KMS key) is often the honest middle.
- **Do not treat RLS as a complete boundary.** It is the best rung most teams can reach, and it is bypassed by superusers and `BYPASSRLS` roles, silently no-op for table owners without `FORCE`, historically leaky through the plan cache (CVE-2024-10976) and through optimizer statistics (CVE-2025-8713), and enforced only inside Postgres, which means it does nothing for your cache, your search index, or your object storage.
- **Do not centralize the PDP without answering the availability question first.** Fail-closed plus a hard dependency means a policy-service outage is a total outage. Decide per action class: reads of non-sensitive data might fail open to a cached decision, money movement never does. Not deciding is deciding.
- **Do not run a "zero trust program" for a 3-service internal system.** SP 800-207 presumes a heterogeneous enterprise with unmanaged devices, contractors, and decades of accumulated network trust. For a small cloud-native estate you already have most of the properties (short-lived credentials, mTLS in the mesh, no flat corporate network) and the program is a budget transfer to vendors.
- **Do not let a zero trust rollout close your access-control risk.** They are orthogonal. Full mTLS, device posture, and identity-aware proxies do not prevent BOLA. If someone presents a ZTNA deployment as a remediation for A01, the correct response is that they have secured the transport to a handler that still does not check ownership.
- **The counter-argument worth stating:** a real school of thought holds that externalizing authorization at all is premature for most companies, and that a well-factored in-process authorization module with a single choke point and good tests beats an external PDP on latency, availability, testability, and operational cost until you have either multiple services needing the same decisions or a genuine per-object sharing model. That is right more often than the vendor landscape implies. The failure mode it guards against is real: teams adopt an external engine, keep writing ad-hoc checks anyway, and end up with two authorization systems and no single source of truth.

---

## Interview questions

### Q1 — RBAC, ABAC, ReBAC. When do you use each?
**Testing:** whether you treat them as competitors or as answers to different questions.
**Answer:** RBAC answers "what may this job function do," and it is the cheapest to build and the only one that is trivially auditable, because entitlements are a `SELECT`. ABAC answers "under what conditions," using subject, resource, action, and environment attributes, and it kills role explosion. ReBAC answers "what is this user's relationship to this object," and it is the only one that handles per-object grants with inheritance and the only one that answers the reverse query cheaply. In a real system they compose: RBAC for coarse job function, ReBAC for the resource graph, attribute conditions layered on top. Both SpiceDB and OpenFGA added contextual conditions to a pure relationship model for exactly this reason.
**Follow-up trap:** *"Give me the failure mode of each, in one sentence."* — RBAC explodes combinatorially when you add a varying dimension. ABAC cannot answer "who can access this?" without evaluating every subject, which breaks sharing UIs and access reviews. ReBAC cannot express time of day, IP range, or MFA level without materializing nonsense as relationships.

### Q2 — What is role explosion and how do you actually fix it?
**Testing:** whether you understand it as arithmetic rather than as sloppiness.
**Answer:** The role count is the product of every dimension you encode into roles. Three job functions crossed with four regions, three environments, and two data classifications is 72 roles for one conceptual job. The observable symptom is that role creation outpaces headcount. The fix is not consolidation, it is to move the exploding dimension out of the role: encode region and environment as attribute conditions, or as relationships if they are really resource scoping, and keep RBAC for the genuinely static coarse function.
**Follow-up trap:** *"Your access review takes two weeks. Does ABAC fix that?"* — no, it makes it worse. ABAC computes access rather than storing it, so a reviewer cannot enumerate who has what without running every principal through the engine. If auditability is the pain, you want stored grants (RBAC or ReBAC tuples) for the reviewable surface and attributes only for genuinely contextual conditions.

### Q3 — Explain Zanzibar's data model and give me its production numbers.
**Testing:** whether you have read the paper or a blog about it.
**Answer:** One relation tuple type, `object#relation@subject`, where the subject can itself be a userset like `group:eng#member`, plus a namespace config with userset rewrites: unions, computed usersets on the same object (owners are editors, editors are viewers), and tuple-to-userset for inheritance (a doc's viewers include its parent folder's viewers). `Check` is a graph traversal over that. Published numbers: more than 2 trillion tuples in about 100 TB, more than 10 million client QPS in aggregate with Check peaking around 4.2M, p95 under 10 ms, availability above 99.999% over three years, on more than 10,000 servers in several dozen clusters replicated to more than 30 locations.
**Follow-up trap:** *"Those numbers include a lot of caching. What does that cost them?"* — consistency, which is why the zookie exists. Serving checks from a stale snapshot is what makes p95 under 10 ms possible at that scale, and the zookie is how they bound the staleness only for the requests that actually need it.

### Q4 — What is the new enemy problem and how does the zookie solve it?
**Testing:** the deepest question in this space.
**Answer:** Two flavors. One, ACL updates applied out of order: Alice removes Bob from a folder, then adds a secret document to it, and a replica that applies the second write before the first lets Bob read the document. Two, an old ACL applied to new content: Alice removes Bob from a document, then adds sensitive content, and if the content read is authorized against a pre-removal ACL snapshot, Bob reads the new content under the old permission. The zookie is an opaque consistency token containing a Spanner timestamp. The content store records a zookie when content is written; subsequent checks pass it, and Zanzibar guarantees evaluation at a snapshot no earlier than that timestamp. It preserves causal ordering between content and ACL updates while leaving Zanzibar free to pick any later timestamp, which is what preserves the cache hit rate.
**Follow-up trap:** *"Why not just make every check strongly consistent?"* — throughput and latency. At 4.2M Check QPS, forcing every read to the latest timestamp destroys the cache and couples every check to global commit latency. The design insight is that the *caller* knows its freshness requirement, so they pushed it into the request as a token instead of picking one global consistency level for everyone.

### Q5 — You enabled RLS, wrote a policy, and it filters nothing. Diagnose.
**Testing:** whether you have actually shipped RLS.
**Answer:** Most likely the application connects as the role that **owns** the tables, and table owners bypass RLS by default. That is the single most common RLS gotcha and it is silent: the policy exists, `ENABLE ROW LEVEL SECURITY` is on, and every row comes back. Fix with `ALTER TABLE ... FORCE ROW LEVEL SECURITY`, and separate the migration role (owner) from the runtime role. The other two candidates: the app role is superuser or has `BYPASSRLS`, which always bypasses and cannot be removed from the built-in `postgres` role, or the policy predicate reads a setting that was never set and `current_setting(..., true)` returned NULL, making the comparison NULL and filtering everything or nothing depending on how you wrote it.
**Follow-up trap:** *"You added FORCE. Now writes are letting a tenant move rows to another tenant. Why?"* — the policy has `USING` but no `WITH CHECK`. `USING` filters reads and the pre-image of a write; `WITH CHECK` validates the post-image. Without it, an `UPDATE ... SET tenant_id = <other>` passes, because the row was visible before the change and nothing validates it after.

### Q6 — Tenant A intermittently sees tenant B's data, only under load. Walk me through it.
**Testing:** the highest-value production bug in this module.
**Answer:** Almost certainly `SET app.tenant_id` (session-scoped) combined with a connection pooler in transaction pooling mode. The setting persists on the backend connection after the transaction ends, and the next request that borrows that connection inherits the previous tenant's context. It only appears under load because that is when connection reuse across requests actually happens. The fix is `SET LOCAL`, or `set_config('app.tenant_id', $1, true)`, inside an explicit transaction, so the value is transaction-scoped and discarded at commit. Add a startup and per-request assertion that fails closed when no tenant context is set.
**Follow-up trap:** *"How do you prove it is fixed, rather than just less frequent?"* — a test that runs against a real pooler in transaction mode with two tenants hammering the same small pool, asserting zero cross-tenant rows across some millions of queries; plus a database-side canary that asserts `current_setting('app.tenant_id')` matches the row's `tenant_id` on every read in staging. Intermittent bugs need a reproduction that fails reliably before the fix, or you have not found the bug.

### Q7 — Is RLS a sufficient tenant-isolation boundary?
**Testing:** whether you will oversell your favorite control.
**Answer:** It is the best rung most teams can reach and it is not sufficient. It is bypassed by superusers and `BYPASSRLS` roles, silently no-op for table owners without `FORCE`, and it has had real CVEs at the boundary: CVE-2024-10976, where incomplete tracking of RLS tables let a reused plan under a subquery or SQL function return rows for the wrong user, and CVE-2025-8713 (fixed August 2025 in 17.6 / 16.10 / 15.14 / 14.19 / 13.22), where optimizer statistics, histograms and most-common-values lists, leaked sampled data that RLS was supposed to hide. And it only covers Postgres: your cache, search index, object storage, and message queue are all outside it.
**Follow-up trap:** *"So what do you add on top?"* — dynamically-scoped credentials so the process physically cannot reach another tenant's data (STS session tags with an IAM condition on `aws:PrincipalTag/tenant`, or per-tenant database credentials), tenant id as a mandatory prefix in the cache-client wrapper rather than by convention, tenant partitioning inside the search index rather than post-filtering, and per-tenant KMS keys so a storage-layer mistake fails at decrypt.

### Q8 — Design tenant isolation for a SaaS going from 20 to 2,000 tenants.
**Testing:** a real architecture tradeoff with a cost dimension.
**Answer:** Silo does not survive that transition: 2,000 databases means 2,000 migrations per release and a per-tenant cost floor that destroys the low tier. Pool with rung-3-and-4 enforcement is the target: shared database with RLS plus `FORCE`, `SET LOCAL` in an explicit transaction, `tenant_id` as the leading column of every composite index, and dynamically-scoped credentials at the compute layer so the enforcement point is outside the process. Keep a bridge escape hatch: the handful of tenants with contractual isolation requirements get their own database or their own KMS key, driven by a routing layer that reads tenant metadata, so the code path is identical and only the connection target differs. Budget explicitly for the cross-cutting leak surfaces, which are where the incidents actually come from: cache keys, background jobs, search indexes, and object storage prefixes.
**Follow-up trap:** *"A tenant's contract demands their data never share a database. Now what?"* — that is exactly what the bridge escape hatch is for, and the important part is that you built the routing indirection *before* you needed it. Retrofitting per-tenant routing into a codebase that assumed one connection string is a multi-quarter project, whereas the same change made while you have 20 tenants is a week. Naming that sequencing is the answer they want.

### Q9 — What is BOLA and why is it #1 in the API Top 10?
**Testing:** whether you connect the model to the actual bug.
**Answer:** Broken Object Level Authorization, API1:2023: an endpoint takes an object identifier, fetches the object, and never checks that the authenticated caller is entitled to *that* object. It is the API framing of A01 Broken Access Control, which is also #1 in the web Top 10 with 40 CWEs and 3.73% average incidence. It is #1 because it is the default outcome of the most natural way to write a handler: authenticate, take the id from the path, look it up, return it. Reported figures put BOLA at roughly 40% of API attacks (secondary-sourced). The fix is to authorize on the object at the data-access layer using the requester's identity, ideally by making the unscoped fetch unavailable, so `get_document(id)` does not exist and only `get_document(id, for_principal=...)` does.
**Follow-up trap:** *"Would UUIDs fix it?"* — no. UUIDs raise the cost of enumeration and change nothing about authorization; a leaked, logged, shared, or referrer-exposed id is still a working key. Treating unguessable identifiers as an access control is security through obscurity with a modern font.

### Q10 — Explain NIST SP 800-207's architecture. What is actually deployed?
**Testing:** whether you can separate the standard from the marketing.
**Answer:** The decomposition is the useful part: a Policy Engine makes the decision and a Policy Administrator establishes or tears down the session credential, together forming the PDP, with a Policy Enforcement Point in the data path in front of every resource. The PE reads from identity management, device posture and CDM, PKI, activity logs, threat intel, and data access policy. CISA's ZTMM v2.0 (April 2023) organizes adoption into five pillars (Identity, Devices, Networks, Applications and Workloads, Data), three cross-cutting capabilities, and four maturity stages. Genuinely deployed at scale: identity-aware proxies replacing VPN for internal apps, mTLS and SPIFFE/SPIRE workload identity in meshes, device posture at authentication, and short-lived credentials. Largely not deployed despite being in the document: continuous per-request re-evaluation against live risk telemetry. Most deployments evaluate richly at session establishment and then coast on a token.
**Follow-up trap:** *"We finished our zero trust rollout. Does that close our Broken Access Control risk?"* — no, and this is the most important thing in the module. Zero trust is about the network and the session; object-level authorization is about the row. A fully zero-trust network still returns tenant B's document to tenant A when the handler looks it up by id without an ownership check. The PEP authorizes access to the *service*; A01 and BOLA live entirely behind it.

### Q11 — Centralized PDP, sidecar, or in-query? Defend a choice.
**Testing:** deployment-topology judgment with real numbers.
**Answer:** In-query (RLS, predicate pushdown) has the strongest guarantee because a code path that does not know the check exists still gets it, and it is limited to what a SQL predicate can express. A sidecar (the OPA pattern) gives sub-millisecond decisions with no availability coupling, at the cost of policy distribution and N possibly-divergent copies. A centralized PDP gives one auditable place to change policy and costs a network hop of roughly 1 to 5 ms plus a hard availability dependency. Large systems run all three at different layers, and the decision is which *class* of decision goes where: tenant scoping in-query, contextual policy in a sidecar, relationship checks against a central store with aggressive caching.
**Follow-up trap:** *"Your central PDP is down. Fail open or closed?"* — per action class, decided in advance and written down. Money movement, permission changes, and data export fail closed, always. Reads of non-sensitive data may serve from a decision cache with a bounded TTL. The wrong answers are "fail closed everywhere" without acknowledging you just made the PDP a single point of total outage, and "fail open" without naming which actions you are willing to let through unauthorized.

### Q12 — Your PDP adds 4 ms p50 and you make 12 authorization calls per request. Fix it.
**Testing:** whether you optimize the right thing.
**Answer:** Twelve sequential calls at 4 ms is 48 ms of pure authorization latency, which is usually the real problem rather than the per-call cost. Three moves in order. First, batch: Zanzibar-derived systems all expose a bulk check, so 12 calls become one. Second, invert the query: if you are checking 12 objects to render a list, you wanted `ListObjects` (what can this user see) rather than 12 `Check` calls, which also fixes the pagination bug where you filter after fetching and return short pages. Third, cache with a bounded staleness and a real invalidation signal, which is what SpiceDB's Watch API exists for. Only after those three do you consider moving to a sidecar.
**Follow-up trap:** *"Caching authorization decisions sounds dangerous. What bounds the risk?"* — the same thing that bounds it in Zanzibar: an explicit staleness contract. Pick a maximum staleness you can defend to a security reviewer (single-digit seconds for most reads), make revocation-sensitive operations bypass the cache entirely, and subscribe to a change feed so revocations invalidate rather than wait for TTL. An unbounded cache on authorization decisions is how "we revoked their access" becomes "we revoked their access, eventually, probably."

### Q13 — How does authorization change when an AI agent acts on a user's behalf?
**Testing:** whether you can extend the model to the domain you claim.
**Answer:** The core assumption breaks: a request no longer has one principal, it has a user, an agent, and possibly a chain of agents, and the decision needs all of them. The pieces that work today: the agent gets its own identity rather than sharing the user's (ASI03 in the OWASP agentic list), it receives a *delegated* credential scoped to a subset of the user's permissions and a short TTL (OAuth token exchange, RFC 8693, is the closest standard), tool access is allowlisted at the gateway rather than described in the prompt, and irreversible actions require a human confirmation regardless of what the token permits. The decision becomes an intersection: the agent may do X only if the user may do X *and* the agent's own grant permits X *and* the context conditions hold.
**Follow-up trap:** *"Can the agent re-delegate to a sub-agent?"* — that is the unsolved part, and saying so is better than inventing an answer. The safe posture in 2026 is that delegation does not transit: a sub-agent gets a credential minted by your orchestrator from the original user grant with a strictly smaller scope, never a credential passed down from the parent agent, because a passed-down credential means a prompt-injected parent can hand full authority to something you did not authorize. There is no standard for this, and anyone who tells you there is has a product to sell.

### Q14 — You inherit a pool-model SaaS with tenant filtering done by hand in every repository. Sequence the remediation.
**Testing:** staff-level sequencing under constraint.
**Answer:** First, find out how bad it is: a query-log audit in staging asserting that every statement touching a tenant table carries a tenant predicate, which gives you a count rather than a feeling. Second, ship the enforcement rung that catches everything at once rather than fixing repositories one at a time: RLS with `FORCE ROW LEVEL SECURITY`, a `tenant_scope` context manager using `SET LOCAL` in an explicit transaction, and a fail-closed assertion so a query with no tenant context raises instead of returning everything. That single change converts every existing missing-predicate bug from a leak into an empty result set. Third, fix the surfaces RLS does not cover, in incident-frequency order: background jobs, cache keys, search index, object storage. Fourth, add the regression tests: a two-tenant integration suite that asserts zero cross-tenant rows on every endpoint, run in CI. Fifth, only then remove the now-redundant hand-written predicates, and only where tests cover them.
**Follow-up trap:** *"RLS turns those bugs into empty result sets. Is that a fix or a new bug?"* — both, deliberately. It converts a confidentiality failure into an availability failure, which is the correct direction to fail, and it makes the previously-silent bugs *loud*, because an endpoint that suddenly returns nothing gets reported in hours where a cross-tenant leak can run for years. Expect a wave of tickets in week one, staff for it, and treat each one as a found bug rather than a regression. Saying that out loud, including the operational cost, is the part that signals you have actually done it.

---

## Red flags that fail you

- Presenting RBAC, ABAC, and ReBAC as competitors and picking one for everything.
- Not being able to name a failure mode for the model you just recommended.
- Saying role explosion is fixed by consolidating roles.
- Claiming ABAC can answer "who has access to this resource" cheaply.
- Not knowing that Postgres table owners bypass RLS by default.
- Using `SET` instead of `SET LOCAL` for tenant context, or setting it outside an explicit transaction, with a pooler in the stack.
- Writing an RLS policy with `USING` and no `WITH CHECK`.
- Treating RLS as a complete boundary, with no answer for cache, search, or object storage.
- Saying UUIDs prevent IDOR/BOLA.
- Describing zero trust as a product you buy, or as a network perimeter replacement with no mention of PE/PA/PEP.
- Claiming a zero trust rollout remediates Broken Access Control.
- Recommending a centralized PDP with no answer for what happens when it is down.
- Caching authorization decisions with no staleness contract and no invalidation path.
- Never having heard of the new enemy problem when discussing a distributed authorization store.
- For agentic systems: passing the user's own credential to the agent, or letting an agent re-delegate its credential to a sub-agent.

---

## Cheat card

```
MODEL SELECTION (they COMPOSE, they do not compete)
 RBAC  "what may this JOB FUNCTION do"   ANSI INCITS 359-2004
       cheapest, trivially auditable (entitlements are a SELECT)
       FAILS: role explosion = PRODUCT of dimensions.
              3 fn x 4 region x 3 env x 2 class = 72 roles for ONE job.
              symptom: roles growing faster than headcount.
 ABAC  "under what CONDITIONS"            NIST SP 800-162 (Jan 2014)
       subject/resource/action/environment attrs. Kills role explosion.
       FAILS: access is COMPUTED not STORED → "who can see X?" is
              O(all subjects). Breaks sharing UI + access review + audit.
 ReBAC "what RELATIONSHIP does this user  Zanzibar, USENIX ATC 2019
        have to this OBJECT"
       tuples: object#relation@subject (subject may be a userset)
       rewrites: computed_userset (owner→editor→viewer),
                 tuple_to_userset (inherit from parent folder)
       Reverse query (Expand) is NATIVE and cheap.
       FAILS: time-of-day / IP / MFA-level are not relationships.
              → SpiceDB "caveats", OpenFGA "conditions" exist for this.

ZANZIBAR NUMBERS (memorize; they settle the "does it scale" objection)
 >2 TRILLION tuples · ~100 TB · >10M client QPS aggregate
 Check ~4.2M QPS · Read 8.2M · Expand 760K · Write 25K
 p95 < 10 ms · availability > 99.999% over 3 years
 >10,000 servers, several dozen clusters, median ~500/cluster, >30 locations

NEW ENEMY PROBLEM (the deep question)
 1) ACL updates applied OUT OF ORDER: remove Bob, then add secret doc →
    replica applies in reverse → Bob reads it.
 2) OLD ACL applied to NEW CONTENT: remove Bob, then add sensitive content →
    stale ACL snapshot authorizes the new content.
 ZOOKIE = opaque token carrying a Spanner timestamp. Content store records it
 on write; Check passes it; evaluation happens at >= that timestamp.
 → causal order preserved, but Zanzibar still picks a LATER timestamp freely,
   which is what keeps the cache hot and p95 under 10 ms.

2026 IMPLEMENTATIONS
 OpenFGA (CNCF Incubating, ex-Auth0/Okta; Grafana, Docker, Canonical)
 SpiceDB (AuthZed; most Zanzibar-faithful; Watch API for invalidation)
 Permify · Ory Keto · Cedar (AWS, CNCF Sandbox, analyzable by design)
 OPA/Rego (CNCF Graduated Feb-2021) — great at policy, BAD at relation graphs

TENANT ISOLATION — ENFORCEMENT LADDER (weakest → strongest)
 1 hand-written WHERE tenant_id = ?   → dies at the first background job
 2 ORM global scope                   → dies at raw SQL / admin tools
 3 Postgres RLS + FORCE + SET LOCAL   → the realistic target
 4 per-tenant creds / STS session tag → enforcement OUTSIDE the buggy process
 5 silo (separate DB/account)         → dies at your ops budget (~50 tenants)

RLS, THE FOUR THINGS THAT BITE
 a) TABLE OWNER BYPASSES RLS BY DEFAULT → ALTER TABLE ... FORCE ROW LEVEL
    SECURITY. #1 gotcha. Policies silently do nothing.
 b) SET (session) + PgBouncer TRANSACTION POOLING = tenant context LEAKS to
    the next request. Use SET LOCAL / set_config(...,true) in an EXPLICIT txn.
 c) USING filters READS + write PRE-image. WITH CHECK validates POST-image.
    No WITH CHECK → UPDATE can move a row to another tenant_id.
 d) superuser + BYPASSRLS always bypass; built-in `postgres` role has
    BYPASSRLS and it CANNOT be removed. Never run the app as it.
 + index (tenant_id, ...) LEADING or the invisible predicate seq-scans.

RLS CVEs WORTH NAMING
 CVE-2024-10976: reused plan under subquery / WITH / security-invoker view /
   SQL function disregards user ID changes → wrong rows.
 CVE-2025-8713 (14-Aug-2025, fixed 17.6/16.10/15.14/14.19/13.22): OPTIMIZER
   STATISTICS (histograms, MCV lists) leak sampled data RLS meant to hide.
   RLS constrains query RESULTS, not what the PLANNER will tell you.

LEAKS RLS DOES NOT COVER
 cache keys without tenant prefix · background workers outside tenant ctx ·
 search index filtered POST-topK instead of in-index · object storage
 prefixes · sequential IDs + no object check (BOLA) · 404-vs-403 existence
 oracle · SHARED KV/PREFIX CACHE in multi-tenant LLM serving (timing side
 channel; mechanism sound, reconstruction rates secondary-sourced)

AWS
 STS session tag + IAM condition on aws:PrincipalTag/tenant (e.g.
 dynamodb:LeadingKeys) = rung 4 in IAM, outside the buggy process.
 Lambda TENANT ISOLATION MODE (Nov-2025): pass a tenant id on invoke, exec
 environments never reused across tenants. COST: cold starts x active tenants
 → good for high-value low-cardinality, bad for a long tail.

ZERO TRUST — NIST SP 800-207 (Aug 2020, Rose/Borchert/Mitchell/Connelly)
 7 tenets · PE + PA = PDP · PEP in front of EVERY resource
 CISA ZTMM v2.0 (Apr-2023): 5 pillars (Identity, Devices, Networks,
   Applications & Workloads, Data) + 3 cross-cutting + 4 stages
   (Traditional → Initial → Advanced → Optimal)
 EO 14028 (May-2021) → OMB M-22-09 (Jan-2022), agencies by end of FY2024
 DEPLOYED AT SCALE: identity-aware proxy replacing VPN · mTLS + SPIFFE/SPIRE
   workload identity · device posture at auth · short-lived credentials
 NOT DEPLOYED despite being in the doc: CONTINUOUS per-request re-evaluation
   against live risk telemetry. Most setups evaluate at session start, coast.

THE SENTENCE THAT WINS THE ROUND
 Zero trust is about the NETWORK and the SESSION.
 A01 / BOLA is about the ROW.
 A perfectly zero-trust network still returns tenant B's document to tenant A
 when the handler fetches by id and never checks ownership.
 A01:2025 Broken Access Control = #1 web (40 CWEs, 3.73% incidence)
 API1:2023 BOLA = #1 API (~40% of API attacks, secondary-sourced)
 UUIDs are NOT authorization.
```

## Sources

- [Zanzibar: Google's Consistent, Global Authorization System (USENIX ATC 2019, Pang et al.)](https://www.usenix.org/system/files/atc19-pang.pdf) — accessed 2026-08-05
- [NIST SP 800-207, Zero Trust Architecture (August 2020)](https://csrc.nist.gov/pubs/sp/800/207/final) — accessed 2026-08-05
- [CISA Zero Trust Maturity Model v2.0 (April 2023)](https://www.cisa.gov/sites/default/files/2023-04/CISA_Zero_Trust_Maturity_Model_Version_2_508c.pdf) — accessed 2026-08-05
- [OWASP API Security Top 10 — API1:2023 Broken Object Level Authorization](https://owasp.org/API-Security/editions/2023/en/0xa1-broken-object-level-authorization/) — accessed 2026-08-05
- [OWASP Top 10:2025 — A01 Broken Access Control](https://owasp.org/Top10/2025/A01_2025-Broken_Access_Control/) — accessed 2026-08-05
- [PostgreSQL Documentation: Row Security Policies](https://www.postgresql.org/docs/current/ddl-rowsecurity.html) — accessed 2026-08-05
- [PostgreSQL: CVE-2025-8713 — optimizer statistics can expose sampled data within a view, partition, or child table](https://www.postgresql.org/support/security/CVE-2025-8713/) — accessed 2026-08-05
- [PostgreSQL: CVE-2024-10976 — row security below e.g. subqueries disregards user ID changes](https://www.postgresql.org/support/security/CVE-2024-10976/) — accessed 2026-08-05
- [AWS Database Blog: Multi-tenant data isolation with PostgreSQL Row Level Security](https://aws.amazon.com/blogs/database/multi-tenant-data-isolation-with-postgresql-row-level-security/) — accessed 2026-08-05
- [AWS What's New: Lambda announces new tenant isolation mode (November 2025)](https://aws.amazon.com/about-aws/whats-new/2025/11/aws-lambda-tenant-isolation-mode) — accessed 2026-08-05
- [AWS Compute Blog: Building multi-tenant SaaS applications with AWS Lambda's new tenant isolation mode](https://aws.amazon.com/blogs/compute/building-multi-tenant-saas-applications-with-aws-lambdas-new-tenant-isolation-mode) — accessed 2026-08-05
- [OpenFGA — Fine-Grained Authorization (CNCF)](https://openfga.dev/) — accessed 2026-08-05
- [AuthZed: Zanzibar, the paper explained](https://authzed.com/zanzibar) — accessed 2026-08-05
- [Fine-Grained Authorization (FGA): A 2026 Implementation Guide (landscape and adoption claims; secondary source)](https://guptadeepak.com/ciam-compass/guides/fine-grained-authorization-fga/) — accessed 2026-08-05

## Changelog
- 2026-08-05 — created
