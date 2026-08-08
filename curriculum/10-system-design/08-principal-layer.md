# The Principal Layer: Multi-Tenancy, Cost Modeling, Migration Strategy, RFC Writing

> **Track:** T10 System Design · **Time:** 2.0h · **Prereqs:** `T10-design-method` · **Updated:** 2026-08-01
> **Module id:** `T10-principal-layer` · **Tags:** principal

## The 30-second version

Four things separate a principal-level design answer from a senior one, and none of them are architecture knowledge: treating tenant isolation as a security requirement with a stated blast radius rather than a checkbox, producing a cost-per-unit number broken into its dominant line items instead of a vague "it'll be expensive," running a migration with a proof-of-correctness step and a rollback that actually works rather than a plan that only covers the happy path, and writing a decision document whose "alternatives considered" section could talk a skeptical room into agreeing with you. A senior engineer builds the pool-model multi-tenant service, computes the AWS bill, executes the migration, and writes the doc. A principal engineer states which tenant gets siloed and why, names the line item that dominates the cost and what happens when it 10x's, proves correctness mid-migration with data rather than confidence, and writes the RFC so the room's hardest questions are already answered on page two.

## Why this gets asked

Because a principal-track interview loop has already confirmed you can design a system; what it's testing next is whether you can be trusted with a decision that a hundred engineers will build on top of and that costs real money to get wrong. The interviewer has personally sat in the room where a "pool" multi-tenant design shipped without a stated isolation boundary and a single tenant's runaway batch job took down every other tenant's read path at 2am; where a migration's "we'll dual-write and reconcile later" turned into eighteen months of silent data drift because nobody ever built the reconciliation job; where a cost estimate of "a few thousand a month" turned out to be $180k because nobody asked which line item was dominant before scaling it; or where an RFC got re-litigated three times because the alternatives section was three bullet points nobody could argue with because there was nothing to argue with. These four topics are the ones where the interviewer can tell, in five minutes, whether you have actually owned a decision at this scope or only implemented one someone else made.

---

## Lineage: past → present → future

**What came before.** Multi-tenancy in the 2000s and early 2010s was mostly binary: either you ran a dedicated instance per customer (expensive, safe, what every enterprise software vendor did before SaaS) or you built a single shared schema with a `tenant_id` column and hoped application code remembered to filter by it everywhere, a pattern that produced exactly the class of cross-tenant authorization bugs documented in `T14-star-bank`'s S06. Cost accounting for cloud infrastructure through the 2010s was largely a finance-team exercise done monthly from the vendor invoice, disconnected from the engineering decisions that drove it, because nobody had built the tagging and telemetry to attribute spend to a request, a tenant, or a feature in near-real-time. Migrations were, more often than teams care to admit, "big bang" cutovers scheduled for a low-traffic maintenance window, a strategy that worked until systems got large enough that no maintenance window was long enough to validate a full cutover before traffic returned. RFC-equivalent documents existed informally at every company that had ever had a bad outcome from a decision made in a hallway conversation, but the discipline of a required, structured "alternatives considered" section is comparatively recent and traces most visibly to Amazon's internal narrative-memo culture and to the wave of public engineering-blog RFC processes (Rust, Cloudflare, Uber) that made the format itself an artifact other companies could copy.

**Where it stands now.** The AWS SaaS Tenant Isolation whitepaper's three-way framing, silo, pool, and bridge, is now the standard vocabulary for describing multi-tenant isolation choices in an interview, precisely because it replaces "how do you handle multi-tenancy" with a spectrum you can place a specific design on and defend ([AWS, SaaS Tenant Isolation Strategies](https://docs.aws.amazon.com/whitepapers/latest/saas-tenant-isolation-strategies/the-bridge-model.html) — accessed 2026-08-01). Cost modeling has matured into a maturity ladder recognized across the FinOps community: coarse monthly cost-per-feature, then per-request or per-job cost with telemetry-driven allocation, then real-time tenant-aware unit cost integrated into autoscaling and CI ([FinOps Foundation, Measuring Unit Costs](https://www.finops.org/framework/previous-capabilities/measure-unit-costs/) — accessed 2026-08-01), and the live disagreement is where a given team should sit on that ladder given the cost of building the telemetry versus the cost of flying blind. Migration strategy has converged on the strangler fig pattern (incrementally routing traffic to the new system behind a facade rather than a big-bang rewrite) as the default answer, with the acknowledged, widely-reported failure mode that the "temporary" dual-write/reconciliation layer becomes permanent, load-bearing infrastructure nobody schedules time to remove ([AppScale, Strangler Fig Migration Pattern 2026](https://appscale.blog/en/blog/microservices-pattern-strangler-fig-migration-2026), [OneUptime, Strangler Fig Migration Pattern](https://oneuptime.com/blog/post/2026-01-24-strangler-fig-migration-pattern/view) — accessed 2026-08-01). RFC and ADR (Architecture Decision Record) practices have split into two complementary artifacts at most mature engineering orgs: the RFC proposes a change and is retired once decided, the ADR records the decision permanently, and the reported effect of requiring either is a measured reduction in post-hoc architecture disputes at companies that track it ([Pragmatic Engineer, RFCs and Design Docs](https://blog.pragmaticengineer.com/rfcs-and-design-docs/) — accessed 2026-08-01).

**Where it's heading.** High confidence: **cost becomes a per-tenant, per-request SLO enforced the way latency already is**, not a monthly report, mirroring the shift `T10-design-method` documents for conventional system-design rounds, because AI-workload costs (a $0.02-0.30 LLM call inside a request path) made the gap between "the bill was fine last month" and "this specific feature is bleeding money right now" too large to ignore. Medium confidence: **isolation-as-code**, where a tenant's isolation tier (silo/pool/bridge) is a declared, enforced policy checked in CI and at the infrastructure layer rather than a design document nobody re-reads after the initial build, following the same trajectory as the resilience patterns in `21-architecture-principles/06-resilience-catalogue.md` moving from application code into policy layers. Medium confidence: **migration correctness proofs become standard tooling** (automated dual-read comparison and diffing, not a manually-run reconciliation script), because the strangler fig pattern's most consistently reported failure is a reconciliation job that existed on paper but was never actually run to completion. Low confidence, speculative: **AI-assisted RFC review** catching missing alternatives or unstated assumptions before a human reviewer does; the tooling exists in early form but is not yet a trusted gate at most companies as of 2026.

---

## Mental model

The four topics are not four unrelated skills; they are the same underlying move, **stating the cost of a choice you are not defending as free**, applied to four different surfaces.

```
 MULTI-TENANCY    "shared infrastructure is cheaper" -- cost of that cheapness is
                   a noisy-neighbour blast radius. Name the radius, don't hide it.

 COST MODELING     "the total bill is $X" -- cost of stopping there is that nobody
                   can act on it. Name the DOMINANT line item, the thing that moves
                   the bill 10x if it 10x's.

 MIGRATION         "we'll cut over gradually" -- cost of gradual is a window where
                   two systems can disagree. Name how you PROVE they don't, not just
                   that you intend to check.

 RFC WRITING        "here is my recommendation" -- cost of a recommendation with no
                   rejected alternative is that it reads as the only idea you had.
                   Name what you rejected and why, in the room's own terms.
```

Each one has the same failure shape when done wrong: **a plan that only describes the happy path**, presented with enough confidence that nobody in the room asks what happens when the assumption breaks. The principal-level version of each artifact answers the question nobody asked, because the senior version already answered every question that was asked.

---

## How it actually works

### 1. Multi-tenancy: silo, pool, bridge

**The spectrum.** Three models, in increasing order of resource sharing and decreasing order of isolation ([AWS, SaaS Tenant Isolation Strategies](https://docs.aws.amazon.com/whitepapers/latest/saas-tenant-isolation-strategies/the-bridge-model.html), [AWS, Pool Isolation](https://docs.aws.amazon.com/whitepapers/latest/saas-tenant-isolation-strategies/pool-isolation.html) — accessed 2026-08-01):

| Model | What's shared | Isolation mechanism | Cost profile |
|---|---|---|---|
| **Silo** | Nothing; each tenant gets a dedicated stack (compute, DB, sometimes a full account) | Physical/account boundary | Highest cost per tenant, near-zero noisy-neighbour risk, most operational overhead (N stacks to patch and monitor) |
| **Pool** | Everything; tenants share compute and storage, isolated logically | Row-level `tenant_id` scoping, enforced in application code or a policy layer | Lowest cost per tenant, highest noisy-neighbour risk, single stack to operate |
| **Bridge** | Some shared, some siloed (e.g., shared compute, per-tenant database; or shared everything for small tenants, silo for large ones) | Mixed, tenant-tier-dependent | The pragmatic default: high-value or compliance-sensitive tenants get silo, the long tail gets pool |

**Isolation is a security requirement, not a feature.** The distinction that separates a senior answer from a principal one: pool-model isolation enforced only by application code remembering to add `WHERE tenant_id = ?` to every query is a **convention**, not a **guarantee**, and conventions get violated the first time someone writes a new endpoint under deadline pressure. `T14-star-bank`'s S06 is the canonical failure this produces: a cross-tenant object-level authorization bypass where a valid token for tenant A could reference an object belonging to tenant B, OWASP API1 (Broken Object Level Authorization), discovered not by a test but by inspection, and fixed by making tenant scoping a required, non-defaultable parameter at the data-access layer rather than a per-endpoint habit. **The fix that survives the next engineer**, not the current one, is enforcement at the layer a new endpoint cannot bypass: a data-access wrapper that requires a tenant context object to construct any query, row-level security policies enforced by the database itself (Postgres RLS, for instance), or a service mesh sidecar that injects and verifies the tenant claim independent of application code.

**Noisy neighbours, quantified.** A pool-model service sizing its database connection pool at 200 connections for 500 tenants, uniformly distributed, budgets 0.4 connections/tenant on average. One tenant running a bulk export that opens 50 concurrent connections has just consumed 25% of total pool capacity, and every other tenant's p99 latency degrades in lockstep with that one tenant's batch job, an entirely predictable outcome from the arithmetic, not a rare edge case. Per-tenant limits (rate limits, connection quotas, concurrency caps) are the mitigation, and they must be enforced at a layer that cannot be bypassed by a legitimate, well-behaved caller having a busy day, the same "budget rule" concept as timeout propagation in the resilience catalogue: a shared resource with 200 slots and 500 possible claimants needs an explicit per-claimant ceiling or the ceiling is decided by whichever tenant happens to be busiest.

**Choosing a tier.** The decision is rarely "pick one model for the whole product"; it's a function of tenant value, compliance requirement, and traffic shape: a tenant under a data-residency contract (EU data must not leave the EU) may require silo regardless of size, since a pool model's shared infrastructure footprint makes a residency guarantee an architectural claim you'd have to prove tenant-by-tenant rather than structurally true. A small trial tenant generating negligible load costs more to silo than the isolation is worth. The honest principal answer states the threshold explicitly (revenue tier, compliance flag, or observed traffic percentile) rather than deciding per-tenant ad hoc, because an undocumented threshold is a threshold nobody can audit later.

### 2. Cost modeling: unit cost and the dominant line item

**The unit-cost formula.** `(direct allocations + shared costs allocated by a stated method) / units delivered`, where the unit is whatever the business actually cares about, cost per request, per tenant, per token, per active user ([FinOps Foundation, Measuring Unit Costs](https://www.finops.org/framework/previous-capabilities/measure-unit-costs/) — accessed 2026-08-01). The formula is trivial; the actual engineering work is in **direct allocation via resource tagging** (which line items can be attributed to a specific tenant/feature without ambiguity) and **shared-cost allocation** (a load balancer, a shared database's baseline capacity, an on-call rotation, none of which have an obvious per-tenant attribution and all of which need a stated, defensible splitting method, by request volume, by seat count, or by a negotiated flat allocation).

**Finding the dominant line item is the actual skill.** A cost breakdown with fifteen roughly-equal line items is less useful than one that immediately shows which single item is 60% of the bill, because that is the one worth optimizing and the one that determines what happens when volume scales. Worked example, an LLM-backed feature at 10M requests/month:

```
compute (API servers, always-on)         $8,000/mo    fixed-ish, scales in steps
database (managed Postgres, r6g.xlarge)  $1,200/mo    fixed-ish
LLM inference (10M req x avg 800 tokens
  in + 200 out x blended $6/M tok)      $48,000/mo    SCALES LINEARLY WITH VOLUME
observability/logging                     $600/mo     fixed-ish
                                        ─────────
TOTAL                                   $57,800/mo

LLM inference is 83% of the bill and the only line item that scales linearly
with the metric the product team is trying to grow (requests). Doubling usage
without a routing/caching change doubles the dominant cost, not the total.
```

Stating this out loud, unprompted, the way `T10-design-method`'s notification-service worked example does with its $1M/month SMS figure, is the specific move that separates a principal cost answer from a senior one: the total number is table stakes, naming which lever actually moves it is the finding.

**Cost as a first-class NFR, not a footnote.** The 2026 shift documented in `T10-design-method` (interviewers now grade cost explicitly) applies doubly at the principal layer: a design review that produces an architecture with no unit-cost figure attached is, at this level, an incomplete review, the same way a design with no failure-mode analysis is incomplete. The maturity ladder from coarse monthly reporting to real-time tenant-aware unit cost integrated into autoscaling decisions is itself worth naming as a roadmap, not a binary you either have or don't ([FinOps Foundation](https://www.finops.org/framework/previous-capabilities/measure-unit-costs/) — accessed 2026-08-01): most orgs are honestly somewhere in the middle, and saying so, with a stated next step, reads better than claiming a maturity you don't have.

**Cost ceilings as a design constraint, not a post-hoc audit.** The strongest cost-modeling answer treats the ceiling as an input to the architecture decision, not a number computed after the design is fixed: "the LLM call is 83% of cost and scales linearly with volume, so before scaling this feature we need either a cache in front of it, a cheaper model for the majority case with escalation to the expensive one for hard cases, or a rate limit tied to a customer's plan tier" is a design decision the cost model produced, not a report filed afterward.

### 3. Migration strategy: strangler fig, dual-write, backfill, shadow, rollback

**The four building blocks.**

| Technique | What it does | When it's the right tool | The trap |
|---|---|---|---|
| **Strangler fig** | A routing facade sits in front of the legacy system; new functionality is built behind the facade and traffic is incrementally redirected, endpoint by endpoint or tenant by tenant, until the legacy system serves nothing | The default for any migration where a big-bang cutover's blast radius is unacceptable | The facade is meant to be temporary; teams routinely leave it in place indefinitely because removing it requires a second migration nobody scheduled |
| **Dual-write with reconciliation** | The application writes to both the old and new store during the transition; a reconciliation job periodically diffs the two and reports or repairs drift | Needed whenever the strangler facade can't cleanly route 100% of a given entity's traffic to one system at a time (e.g., reads still hit the old store while writes move first) | The reconciliation job is the actual correctness mechanism, and it is the piece most often built as an afterthought, run once, and never re-run; drift accumulates silently the moment it stops running |
| **Backfill-then-cutover** | Historical data is migrated in bulk (usually offline, via an export/transform/load job) before any live traffic moves, so the new system starts populated rather than empty | Cleaner than dual-write when the entity doesn't need continuous consistency during the transition window, e.g., an analytics store, an archive | Backfill jobs typically run once against a snapshot; any writes to the source system between snapshot and cutover are missed unless a second, smaller backfill or a brief write-freeze closes the gap |
| **Shadow traffic** | Production requests are duplicated (not routed for real) to the new system so its behavior can be compared against the legacy system's real output before any user-facing traffic depends on it | The step that actually validates correctness before cutover, distinct from dual-write, which validates data consistency; shadow traffic validates behavioral correctness | Shadowing must not have side effects the real system depends on (a shadowed write must not double-charge a customer); needs an explicit no-side-effects boundary, often meaning the shadow path writes to a sandboxed copy, not the real downstream system |

**Proving correctness mid-migration, not assuming it.** The single most reported production failure across all four techniques is treating them as a plan rather than a proof: dual-writing without ever running the reconciliation job to completion, or running it once at the start and never again as drift accumulates over the following weeks ([OneUptime, Strangler Fig Migration Pattern](https://oneuptime.com/blog/post/2026-01-24-strangler-fig-migration-pattern/view), [Codelit, Strangler Fig Pattern](https://codelit.io/blog/strangler-fig-migration-pattern) — accessed 2026-08-01). The principal-level answer names the specific comparison the reconciliation job runs (row counts, checksums over a sampled key range, a full diff for entities under a size threshold) and the cadence it runs on (continuously via a stream processor, not a manually-triggered script), and treats "the reconciliation job's own drift rate" as a metric worth dashboarding, the same instinct as the resilience catalogue's insistence that every pattern is invisible until instrumented.

**Rollback is a plan, not a hope.** A migration without a tested rollback path is a one-way door dressed up as a two-way one. The routing-facade pattern's real value is that rollback is "flip the router back," which is only true if the facade's routing decision is cheap to reverse and if the legacy system was kept in a state capable of resuming service (still receiving writes, or capable of being caught up from the dual-write log) rather than already decommissioned the moment the new system looked stable. Worked failure mode: a team dual-writes for two weeks, sees no reconciliation errors, decommissions the legacy write path to "reduce complexity," and then discovers a bug in the new system three days later with no path back except restoring from backup, because the thing that made rollback cheap (the legacy system still being live) was removed before the thing that made rollback necessary (confidence the new system was actually correct, not just quiet) was earned.

### 4. RFC writing: structure, real alternatives, driving a decision

**Structure.** The converged template across companies that have published theirs (Rust RFCs, Cloudflare, Uber, Amazon's six-pager tradition) is remarkably consistent: a one-paragraph summary, the motivation (what's wrong with the status quo, stated as a cost, not a preference), the proposal itself, an alternatives-considered section, a risks-and-mitigations section, and an implementation/rollout plan, held to roughly 2-5 pages because length past that point is read by fewer people, not more thoroughly ([Pragmatic Engineer, Software Engineering RFC and Design Doc Examples](https://newsletter.pragmaticengineer.com/p/software-engineering-rfc-and-design), [PanDev Metrics, RFC Process for Engineering Teams](https://pandev-metrics.com/docs/blog/rfc-process-engineering-teams) — accessed 2026-08-01).

**Making "alternatives considered" real, not decorative.** The test for whether an alternatives section is doing its job: could a smart reader who disagreed with your recommendation use this section to argue for a different option, using your own words? A real alternatives section states what each option costs and what it would have been correct for, the exact pattern `T14-star-bank`'s S03 uses for the ClickHouse-over-Weaviate decision: "Weaviate would have been the safe résumé answer and better at 50M+ rows with heavy hybrid search," a rejected alternative stated with its actual merit, not strawmanned. A three-bullet alternatives section that lists options with no stated cost for each is decorative, and an experienced reader can tell the difference in the first ten seconds, because a decorative section never mentions a scenario where the rejected option would have been the right call.

**RFC versus ADR: two artifacts, not one.** An RFC proposes a change and exists to gather input before a decision; once decided, its job is done and it should be archived, not maintained. An Architecture Decision Record captures the decision itself, in a short, durable format (context, decision, consequences), meant to be read by someone six months later asking "why does this system work this way," a question an RFC's discussion-oriented format answers poorly once the discussion is over ([ITNEXT, RFCs, ADRs, and Getting Everyone Aligned](https://itnext.io/how-to-make-architecture-decisions-rfcs-adrs-and-getting-everyone-aligned-ab82e5384d2f) — accessed 2026-08-01). Conflating the two produces a document that's too long to be a quick durable reference and too settled-sounding to invite real debate while it's still open.

**Driving a decision through a room.** The mechanical parts of the format are necessary but not sufficient; the actual skill is sequencing the document so the room's hardest objection is addressed before it's raised, not defended reactively in a comment thread after the fact. That means: naming the failure mode a skeptical reader would bring up in the "risks and mitigations" section yourself, stating the cost you're accepting explicitly rather than letting a reviewer discover it, and closing with a concrete, time-boxed decision request ("I'm asking for a decision by Friday; if I don't hear objections I'll proceed with option B") rather than an open-ended "thoughts welcome," which is how RFCs stall in review for months. The reported effect of doing this well, teams citing measurably fewer post-hoc architecture disputes when a design doc existed and was actually read ([Pragmatic Engineer, RFCs and Design Docs](https://blog.pragmaticengineer.com/rfcs-and-design-docs/) — accessed 2026-08-01), is the business case for spending the extra hour writing the alternatives section properly instead of shipping a decision and explaining it after the fact.

---

## Build it from scratch

The one piece of this module that has a concrete, checkable artifact is a **tenant-scoping enforcement layer**, the fix that turns pool-model isolation from a convention into a guarantee, which is exactly the gap `T14-star-bank`'s S06 names as the root cause of a cross-tenant authorization bypass.

```python
# untested sketch: illustrates the enforcement-layer shape, not a production ORM.
from contextlib import contextmanager
from dataclasses import dataclass

@dataclass(frozen=True)
class TenantContext:
    tenant_id: str

class MissingTenantContext(Exception):
    """Raised if any query is attempted without an active tenant scope."""

_current_tenant: TenantContext | None = None

@contextmanager
def tenant_scope(ctx: TenantContext):
    global _current_tenant
    prev, _current_tenant = _current_tenant, ctx
    try:
        yield
    finally:
        _current_tenant = prev

class ScopedQuery:
    """Every query MUST go through this. There is no code path that
    reaches the database without a tenant_id predicate, which is the
    property a per-endpoint 'remember to filter' convention cannot give you."""
    def __init__(self, table: str):
        if _current_tenant is None:
            raise MissingTenantContext(
                f"attempted to query '{table}' with no active tenant_scope()"
            )
        self.table = table
        self.tenant_id = _current_tenant.tenant_id

    def fetch(self, object_id: str):
        # tenant_id is NOT an optional filter the caller can forget to add;
        # it is structurally required to construct this object at all.
        return f"SELECT * FROM {self.table} WHERE tenant_id = '{self.tenant_id}' AND id = '{object_id}'"
        # (a real implementation parameterizes this; the point is the
        # tenant predicate cannot be omitted, not the SQL string-building)

# usage: a new endpoint literally cannot query without a tenant context,
# which is what makes this a guarantee rather than a code-review reminder.
with tenant_scope(TenantContext(tenant_id="acme-corp")):
    q = ScopedQuery("invoices")
    q.fetch("inv_123")
```

The interviewer follow-up this invites: *"What stops a developer from just calling the raw database client directly and skipping `ScopedQuery` entirely?"* Nothing, at the application-code layer, which is precisely why the durable version of this fix lives one layer lower: database row-level security (Postgres `CREATE POLICY ... USING (tenant_id = current_setting('app.tenant_id'))`) enforced by the database itself regardless of which code path constructs the query, or a service-mesh-level check on the tenant claim in every request, so the guarantee doesn't depend on every future engineer using the wrapper correctly.

---

## How it's done in production

| Topic | Framework/managed version | What it adds |
|---|---|---|
| Tenant isolation | Postgres Row-Level Security, AWS RLS + IAM tenant-scoped roles, dedicated-VPC-per-tenant for silo tier | Enforcement at a layer application code cannot bypass |
| Cost attribution | CloudZero, Amnic, native AWS Cost Categories + tagging | Automated tag-based allocation, per-tenant/per-feature dashboards without hand-built ETL |
| Migration facade | Envoy/API gateway routing rules, feature-flag-driven traffic splitting (LaunchDarkly-style) | Cheap, auditable, instantly-reversible traffic routing without a custom proxy |
| Reconciliation | CDC-based diffing (Debezium feeding a comparison job), scheduled checksum jobs | Continuous drift detection instead of a one-time manual script |
| RFC process | Confluence/Notion templates with mandatory sections, GitHub-native RFC repos (Rust-style) | Enforced structure and a durable, searchable decision archive |

### What breaks in production

| Symptom | Cause | Fix |
|---|---|---|
| One tenant's batch job degrades p99 latency for all tenants | Pool model with no per-tenant rate/connection limit | Per-tenant quotas enforced at the connection-pool or API-gateway layer, not just monitored |
| A tenant's data appears in another tenant's response | Pool-model isolation enforced only by application-code convention | Move enforcement to a layer code cannot bypass (RLS, mesh-level claim check) |
| Monthly cloud bill jumps 3x with no corresponding traffic growth | No per-line-item cost attribution, so the dominant driver (often a per-request external API call) was invisible until the invoice | Tenant/feature-tagged cost telemetry with alerting on the dominant line item specifically, not just total spend |
| A migration's legacy and new systems silently disagree for weeks before anyone notices | Reconciliation job run once at project start, never re-run on a schedule | Continuous, scheduled reconciliation with its own drift-rate dashboard and alert threshold |
| A migration rollback fails when it's actually needed | Legacy system decommissioned before confidence in the new system was actually earned, not just assumed | Keep the legacy path live (even if not serving traffic) until a stated confidence bar is met, not a stated calendar date |
| An RFC gets re-litigated after "approval" | Alternatives section didn't address the room's actual objection, so it resurfaces post-decision | Route the draft past the most likely skeptic before the formal review, not after |

---

## Tradeoffs & when NOT to use it

- **Silo everything is not automatically safer; it's a different risk profile.** N independently-operated stacks means N things to patch, monitor, and get paged for; a security fix now has to roll out N times instead of once. Silo trades a shared-blast-radius risk for an operational-consistency risk, and for tenants without a compliance requirement forcing the choice, that trade is often not worth it.
- **Do not build tenant-aware, real-time cost telemetry before you have the traffic or the tenant count to justify it.** The FinOps maturity ladder is a ladder for a reason; a five-person startup building tenant-level unit-cost dashboards before product-market fit is solving a problem it doesn't have yet at the expense of one it does.
- **Do not strangler-fig a system that's being fully replaced anyway, not incrementally evolved.** If the new system has a fundamentally different data model and there's no meaningful way to serve some entities from the old system and some from the new one simultaneously, a well-scoped, well-tested big-bang cutover with a real rehearsal can be simpler and safer than an incremental migration that never finds a clean seam to split traffic on.
- **Do not treat dual-write as free correctness insurance.** It has a real cost: every write path now has two failure modes instead of one (what happens when the second write fails after the first succeeds), and that failure mode needs its own design, not an assumption that "eventually consistent" covers it.
- **Do not write a full RFC for a reversible, cheap decision.** The rigor of the artifact should scale with how hard the decision is to undo, the same reversible-vs-one-way-door calibration covered in `T10-tech-selection`; a two-way door decision documented with a full RFC is a process cost with no corresponding risk reduction.
- **The alternatives-considered section can become theater if the decision was already made.** If a design doc is written to justify a decision made in a hallway conversation last week, the alternatives section becomes a post-hoc rationalization exercise rather than real analysis, and readers who were in that hallway conversation know it, which quietly erodes trust in every future document from the same author.

---

## Interview questions

### Q1 — Design the tenant isolation strategy for a new B2B SaaS product with both trial users and enterprise contracts.
**Testing:** whether isolation is treated as a security requirement with a stated boundary, or a vague "we'll use tenant IDs."
**Answer:** A bridge model: pool isolation (shared compute, row-level `tenant_id` scoping enforced via RLS or a mandatory data-access layer) for trial and small tenants where the cost of silo isn't justified, silo (dedicated database, possibly dedicated compute) for enterprise tenants under a data-residency or compliance requirement where a pool model's shared footprint can't structurally guarantee the contractual claim. State the threshold explicitly, e.g., a named compliance flag or a revenue tier, rather than deciding per-tenant informally.
**Follow-up trap:** *"How do you migrate a growing trial tenant from pool to silo without downtime?"* This is itself a mini version of the migration section: dual-write to the new dedicated store during transition, backfill historical data, verify via reconciliation, then cut reads over, keeping the pool-model data live until confidence is earned, not just until the new store looks populated.

### Q2 — A pool-model service's p99 latency spikes every day at 2am. What's your hypothesis and how do you confirm it?
**Testing:** whether noisy-neighbour effects are understood as a quantifiable, predictable consequence of shared capacity, not a mysterious flake.
**Answer:** Hypothesize a single tenant's scheduled batch job (an export, a nightly sync) consuming a disproportionate share of a shared resource, most commonly database connections or CPU. Confirm by correlating the latency spike's timing against per-tenant request/connection metrics, which requires per-tenant telemetry to exist in the first place, itself worth naming as a prerequisite the design should have included from the start rather than added reactively during an incident.
**Follow-up trap:** *"The offending tenant is your biggest customer. You can't just rate-limit them."* Then the fix is architectural, not policy: move that tenant to a silo or a dedicated resource pool rather than throttling them, which is exactly the bridge-model reasoning, sized around the specific tenant whose load profile doesn't fit the shared tier rather than a blanket policy change affecting everyone.

### Q3 — Walk me through computing the unit cost of a feature, and tell me which number in your breakdown actually matters.
**Testing:** whether cost modeling produces an actionable finding or just a total.
**Answer:** Sum direct allocations (resources tagged to this feature) plus a stated method for shared-cost allocation (by request volume, by seat), divide by units delivered. The number that matters is the dominant line item, the one that scales linearly with the metric growth is targeting, not the total; in an LLM-backed feature that's usually the inference cost, not compute or storage, and naming that unprompted, with the arithmetic shown, is the actual deliverable.
**Follow-up trap:** *"Your dominant line item scales linearly and the product wants 10x growth next year. What do you do before that happens?"* Attack the dominant line item specifically, not the whole system: a semantic cache, a cheaper model for the common case with escalation for hard cases, or a usage-based pricing tier that passes the marginal cost through, stated as a design decision the cost model produced rather than a report filed after the bill arrived.

### Q4 — Design a migration from a monolithic user-profile service to a new microservice, with zero acceptable downtime.
**Testing:** whether the migration plan includes a proof of correctness, not just an intent to migrate carefully.
**Answer:** Strangler fig facade routing profile-read traffic; dual-write on profile updates to both the legacy and new store during transition; backfill historical profile data into the new store from a snapshot before enabling dual-write, with a short gap-closing backfill covering writes between snapshot and dual-write activation; a continuously-scheduled reconciliation job diffing both stores (checksums or full diff below a size threshold) with its own drift-rate dashboard; cut reads over once reconciliation shows zero drift for a stated observation window, not a stated calendar date; keep the legacy write path live until that same confidence bar is met on the read side too, so rollback stays cheap.
**Follow-up trap:** *"Your reconciliation job has been reporting zero drift for two weeks. Is it safe to decommission the legacy system?"* Not automatically: check whether the reconciliation job would actually catch every class of drift it claims to (a checksum comparison can miss row-level replacement that happens to produce the same checksum, or the job itself could have silently stopped running), and specifically verify it against an injected known-bad record before trusting a clean report as proof of correctness rather than absence of a check that's actually working.

### Q5 — Your team disagrees on whether to dual-write or backfill-then-cutover for a migration. How do you decide?
**Testing:** matching the technique to the actual consistency requirement rather than defaulting to whichever pattern is more familiar.
**Answer:** The deciding question is whether the entity needs continuous consistency during the transition window. If reads and writes must both reflect the same up-to-date state throughout (an account balance, an inventory count), dual-write with reconciliation is close to mandatory despite its cost. If the entity tolerates a bounded staleness window and doesn't need both systems live simultaneously (an analytics table, an archival store), backfill-then-cutover is simpler and has fewer failure modes, since there's no ongoing dual-write path to keep correct.
**Follow-up trap:** *"What if you're wrong about which category the entity falls into?"* Name the cost of being wrong in each direction: choosing dual-write when backfill would have sufficed costs extra engineering complexity for no correctness benefit; choosing backfill-then-cutover when dual-write was actually needed produces a correctness gap during the transition window that may not surface until a customer complains, which is the more expensive mistake, so when genuinely uncertain, the safer default leans toward dual-write despite the cost.

### Q6 — Write the "alternatives considered" section for a decision to use a message queue instead of synchronous HTTP calls between two services.
**Testing:** whether the alternatives section states real costs for the rejected options or just lists them.
**Answer:** "We considered synchronous HTTP, which is simpler to reason about and debug (a request either succeeds or fails immediately, with no eventual-consistency window) and is the right choice if the caller genuinely needs the result before proceeding. We rejected it because the downstream service's occasional 2-3 second processing spikes would block the caller's request thread, and the caller doesn't actually need the result synchronously, it needs the work to happen reliably. We also considered a scheduled batch job instead of a queue, rejected because the latency requirement (processed within seconds, not hours) doesn't fit a batch cadence." Each rejected option states what it would have been correct for, not just why it lost.
**Follow-up trap:** *"Your alternatives section didn't mention cost or operational overhead of running a message broker. Why not?"* That's a real gap: a complete alternatives section states the accepted option's cost too, not just the rejected ones', since "we're adding a new stateful system to operate, with its own on-call surface" is exactly the kind of cost a skeptical reader will bring up if you don't name it first.

### Q7 — An RFC you wrote got approved, then re-litigated three weeks later when a senior engineer raised an objection nobody had addressed. What went wrong in the process, not the technical decision?
**Testing:** whether you can diagnose a process failure, not just defend the original technical call.
**Answer:** The objection existed and was predictable but wasn't surfaced before the review, either because the RFC wasn't routed past the people most likely to raise it, or because the risks-and-mitigations section didn't anticipate it. The fix isn't rewriting the technical decision defensively after the fact; it's routing future drafts past the most likely skeptic before the formal review round, and treating "what would the harshest reasonable reviewer say" as a required pass before publishing, not an optional nicety.
**Follow-up trap:** *"Doesn't pre-routing to your harshest critic just mean you can suppress objections before they're on the record?"* No, and naming the distinction matters: pre-routing is about addressing the objection in the document, not about talking the critic out of raising it; if their objection changes the recommendation, that's the document doing its job earlier and cheaper than a public re-litigation three weeks in.

### Q8 — When should a decision be a full RFC versus a two-line Slack message and a follow-up ADR?
**Testing:** calibrating process weight to decision cost, the same reversible-vs-one-way-door judgment as `T10-tech-selection`.
**Answer:** Scale the artifact to how expensive the decision is to reverse and how many people it constrains. A config default one team can change back in five minutes doesn't need a five-page RFC; a data-model or public-API choice that other teams will build on for years does, because the cost of under-processing a one-way door (silently constraining everyone who builds on it) is far higher than the cost of over-processing a two-way door (a wasted afternoon of review for something you could've just tried).
**Follow-up trap:** *"Who decides which category a given decision falls into?"* That itself needs to be a stated, lightweight norm (a rule of thumb like "touches more than one team's data model or is expensive to reverse -> RFC," posted somewhere discoverable), not a judgment call made fresh every time, or the norm itself becomes a source of disagreement before any actual decision gets discussed.

### Q9 — How do you compute the cost of NOT migrating, when a migration project is being deprioritized against feature work?
**Testing:** whether "technical debt" can be translated into the same cost-per-unit language as the rest of this module, which is what actually gets it prioritized.
**Answer:** Name the ongoing cost the legacy system imposes in the same unit-cost terms as any other design: engineering hours spent working around it per sprint, the incident rate or MTTR difference attributable to it, or a specific, dated cliff it's approaching (a vendor end-of-life date, a scaling ceiling with a stated headroom number). "It's old and we should modernize it" competes poorly against a feature with a clear revenue number; "$40k/quarter in engineering time spent on workarounds, plus a scaling ceiling we hit in approximately 8 months at current growth" competes on the same terms the feature work is being justified with.
**Follow-up trap:** *"Your dated cliff estimate turns out to be wrong; the scaling ceiling is actually 18 months out, not 8. Does that kill the case for migrating now?"* Not necessarily, but it changes the urgency argument: separate the "cliff" argument (time-boxed, revisable) from the "ongoing tax" argument (workaround hours, which accrue regardless of the cliff's exact date), so a revised cliff estimate doesn't invalidate the whole business case, only the urgency framing built on that specific number.

### Q10 — You inherit a multi-tenant system with no documented isolation tier per tenant, cost attribution, or migration history. Where do you start?
**Testing:** prioritization under an inherited, undocumented system, a realistic principal-scope scenario rather than a greenfield design.
**Answer:** Start with whichever gap has the highest blast radius if it's wrong: audit the isolation boundary first (is tenant scoping actually enforced at a layer that can't be bypassed, or only by convention), because a cross-tenant data exposure is the failure with the worst combination of likelihood-you-can't-currently-measure and consequence-you-can't-undo. Cost attribution and migration-history documentation are important but recoverable if delayed a quarter; an undiscovered authorization gap is not something you get a second chance to catch before it's exploited or reported.
**Follow-up trap:** *"The isolation audit turns up nothing wrong. What's next?"* Cost attribution, specifically finding the dominant line item, because an inherited system with no cost visibility is the most common place a principal engineer finds an unforced, fixable expense (an unbounded cache, a per-request external call nobody's questioned in years) that pays for the audit work many times over once found.

---

## Red flags that fail you

- Describing multi-tenancy as "we add a `tenant_id` column" with no statement of where isolation is actually enforced.
- A cost estimate with a total and no breakdown, or a breakdown with no stated dominant line item.
- A migration plan with no reconciliation step, or a reconciliation step described as "we'll check the data looks right."
- Treating dual-write as costless, with no mention of the two-failure-modes-instead-of-one problem.
- Decommissioning the legacy system as the first action after cutover, rather than the last, once confidence is actually earned.
- An "alternatives considered" section that lists options with no stated cost or scenario where each would have been correct.
- Writing a full RFC for a trivially reversible decision, or skipping one for a decision other teams will be structurally constrained by for years.
- Claiming a cost or migration confidence figure with no stated measurement method, the same failure `T14-star-bank` calls out for the ~25% engagement uplift claim.
- No stated threshold for tenant tiering (silo vs. pool), deciding case-by-case with no documented rule.

---

## Cheat card

```
TENANCY        silo = dedicated stack, highest isolation, highest cost/tenant
               pool = shared, lowest cost, isolation is a CONVENTION unless
                      enforced at a layer code can't bypass (RLS, mesh claim check)
               bridge = mixed by tenant tier; STATE the threshold explicitly
               noisy neighbour: shared_capacity / N_tenants = predictable budget;
                      enforce PER-TENANT limits, don't just monitor

COST           unit_cost = (direct allocations + shared costs / stated method)
                            / units delivered
               find the DOMINANT line item -- the one that scales with growth
               cost is an NFR: state it unprompted, same as latency/availability
               maturity ladder: monthly report -> per-request telemetry ->
                                 real-time tenant-aware, tied into autoscaling

MIGRATION      strangler fig = routing facade, incremental cutover, NOT permanent
               dual-write = 2 failure modes instead of 1; needs reconciliation
               backfill-then-cutover = simpler when staleness is tolerable
               shadow traffic = validates BEHAVIOR, dual-write validates DATA
               reconciliation must be SCHEDULED and DASHBOARDED, not run-once
               rollback stays cheap only if legacy stays live until EARNED
                      confidence, not a calendar date

RFC            summary -> motivation (cost of status quo) -> proposal ->
                      alternatives (cost + correct-for-scenario, each) ->
                      risks/mitigations -> rollout. 2-5 pages.
               RFC = proposes, retired after decision. ADR = records the
                      decision, durable, read 6 months later.
               route past your harshest skeptic BEFORE formal review
               rigor scales with REVERSIBILITY, not decision size

CALIBRATION    reversible + cheap  -> Slack message + ADR
               one-way-door + org-wide -> full RFC, alternatives section
                      that could argue against you
```

## Sources

- [AWS, SaaS Tenant Isolation Strategies — The Bridge Model](https://docs.aws.amazon.com/whitepapers/latest/saas-tenant-isolation-strategies/the-bridge-model.html) — accessed 2026-08-01
- [AWS, SaaS Tenant Isolation Strategies — Pool Isolation](https://docs.aws.amazon.com/whitepapers/latest/saas-tenant-isolation-strategies/pool-isolation.html) — accessed 2026-08-01
- [nonstopio, Choosing Multi-Tenant SaaS Architectures: Silo, Pool, or Bridge Models](https://blog.nonstopio.com/choosing-multi-tenant-saas-architectures-silo-pool-or-bridge-models-a-devops-perspective-fff92216672c) — accessed 2026-08-01
- [FinOps Foundation, Measuring Unit Costs](https://www.finops.org/framework/previous-capabilities/measure-unit-costs/) — accessed 2026-08-01
- [CloudZero, FinOps Cost-Per-Unit Glossary](https://www.cloudzero.com/blog/finops-cost-per-unit-glossary/) — accessed 2026-08-01
- [AppScale, Strangler Fig Pattern: Migrate Legacy Systems Incrementally (2026)](https://appscale.blog/en/blog/microservices-pattern-strangler-fig-migration-2026) — accessed 2026-08-01
- [OneUptime, How to Handle Strangler Fig Migration Pattern](https://oneuptime.com/blog/post/2026-01-24-strangler-fig-migration-pattern/view) — accessed 2026-08-01
- [Codelit, Strangler Fig Pattern — Incremental Migration Without the Big Bang Rewrite](https://codelit.io/blog/strangler-fig-migration-pattern) — accessed 2026-08-01
- [AWS Prescriptive Guidance, Strangler Fig Pattern](https://docs.aws.amazon.com/prescriptive-guidance/latest/cloud-design-patterns/strangler-fig.html) — accessed 2026-08-01
- [Pragmatic Engineer, Companies Using RFCs or Design Docs and Examples](https://blog.pragmaticengineer.com/rfcs-and-design-docs/) — accessed 2026-08-01
- [Pragmatic Engineer, Software Engineering RFC and Design Doc Examples and Templates](https://newsletter.pragmaticengineer.com/p/software-engineering-rfc-and-design) — accessed 2026-08-01
- [PanDev Metrics, RFC Process for Engineering Teams: Template + Real Examples](https://pandev-metrics.com/docs/blog/rfc-process-engineering-teams) — accessed 2026-08-01
- [ITNEXT, How to Make Architecture Decisions: RFCs, ADRs, and Getting Everyone Aligned](https://itnext.io/how-to-make-architecture-decisions-rfcs-adrs-and-getting-everyone-aligned-ab82e5384d2f) — accessed 2026-08-01

## Changelog
- 2026-08-01 — created
