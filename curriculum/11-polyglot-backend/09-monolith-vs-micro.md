# Monolith vs Modular Monolith vs Microservices vs Monorepo

> **Track:** T11 Polyglot Backend · **Time:** 2.5h · **Prereqs:** none · **Updated:** 2026-08-03
> **Module id:** `T11-monolith-vs-micro` · **Tags:** architecture, critical

## The 30-second version

The 2026 industry consensus has genuinely shifted from the 2015-2020 "microservices by default" era: a CNCF 2025 report found **42% of organizations actively consolidating microservices back into larger units**, Gartner reports **60% of teams regret adopting microservices for small-to-medium applications**, and the emerging default explicitly recommended across current architecture writing is **start with a well-structured (modular) monolith, split into services only when scale or team size specifically justifies it** — not the reverse. A modular monolith enforces strict domain boundaries (separate modules/packages with disciplined internal APIs between them, often backed by compile-time or lint-enforced dependency rules) inside a **single deployable unit**, capturing most of microservices' organizational benefit (clear ownership boundaries, the ability to reason about one module at a time) without the distributed-systems tax: no network calls between modules, one deployment pipeline, one transaction boundary, trivial local debugging. The actual, defensible reasons to split into real microservices are narrow and specific — independent deployment cadence for teams that are blocked on each other's release schedule, independent scaling for a component with genuinely different resource/traffic profile than the rest, fault isolation where one component's failure must not take down others, or a hard requirement for polyglot implementation (a genuinely CPU-bound component needing Go/Rust while the rest stays Python) — and the cost is real and now well-documented: a DZone 2024 study found teams spend **35% more time debugging microservices versus modular monoliths**, and case studies like Segment (consolidating 140+ services back into one application after a shared-library change forced deploying all of them, making development untenably slow) and Amazon Prime Video's monitoring tool (a 90% infrastructure cost reduction moving from a serverless/microservices design to a monolith, though notably scoped to one tool, not the whole platform) are now the commonly cited cautionary tales, not the growth-story exceptions they were framed as a decade ago. Monorepo versus polyrepo is an orthogonal axis, not a proxy for monolith versus microservices — Shopify runs a massive monorepo *and* a modular-monolith architecture; Amazon runs polyrepo *with* microservices — the actual criterion is whether cross-cutting refactors and consistent tooling (monorepo's strengths) matter more than per-service deployment autonomy and blast-radius isolation of CI/tooling changes (polyrepo's strengths) for your organization's specific change patterns.

## Why this gets asked

Because this is one of the most consequential, expensive-to-reverse architectural decisions a team makes, and the industry's own understanding of it has visibly swung within the candidate's career — someone who joined the industry during "microservices are how you scale" and hasn't updated since is giving a stale answer in 2026. The interviewer has almost certainly either lived through an over-eager microservices split that made the team slower (the Segment story, or something structurally identical at smaller scale — a change touching three "independent" services requiring three coordinated deployments and a distributed debugging session to find which one actually broke) or defended a monolith against pressure to split it prematurely and wants to hear the actual decision criteria, not a reflexive "microservices are the scalable, modern choice." At staff/principal level, they're testing whether you reason from Conway's Law and team topology (who actually needs independent deploy cadence, and why) rather than from architectural fashion.

---

## Lineage: past → present → future

**What came before.** The pre-2010s default was the monolith — a single deployable application, often growing over years into what critics called a "big ball of mud": no enforced internal boundaries, any module able to call any other module's internals directly, shared mutable state reached from everywhere, and a build/deploy pipeline that became slower and riskier as the codebase grew, because any change anywhere required rebuilding, retesting, and redeploying the entire application. This genuine pain — Amazon's own oft-cited early-2000s internal story about a monolithic retail application where deployment coordination became a bottleneck — motivated the industry's move toward service-oriented architecture and, more specifically, the mid-2010s microservices wave (Netflix, Amazon, and later a wide swath of the industry publishing case studies and conference talks establishing microservices as the default "how to scale" answer), which decomposed applications into independently deployable, independently scalable services communicating over the network, directly addressing the monolith's deployment-coupling pain by giving each team full ownership of its own service's build/deploy/scale lifecycle.

**Where it stands now.** The genuine, current, well-documented correction is that many organizations over-applied microservices to problems that didn't need distributed-systems complexity — small-to-medium applications, teams without the platform/tooling maturity (service mesh, distributed tracing, robust CI/CD per service) to operate dozens of services well, and systems where the actual bottleneck was never deployment coupling in the first place. The specific, current numbers matter here: 42% of organizations (CNCF 2025) actively consolidating services back, 60% of teams (Gartner) reporting regret specifically for small-to-medium applications, and a well-documented 35% debugging-time cost (DZone 2024) for microservices versus modular monoliths — this isn't anecdotal backlash, it's a measured, repeated finding. The **modular monolith** has emerged as the explicit, named alternative filling the gap: Shopify's own public architecture writing describes exactly this — a shift *away* from an earlier microservices push *toward* a modular monolith retaining a unified Ruby codebase (in a large monorepo) while enforcing strict internal module boundaries, explicitly because a full microservices split's operational cost outweighed its benefit for their actual team/scale reality at the time, while preserving the *option* to extract a genuinely justified service later. The live, still-contested nuance: this is a *correction*, not a full reversal — genuinely large-scale, many-team organizations (Amazon's polyrepo microservices fleet remains a real, functioning, justified architecture at Amazon's specific scale and team-independence requirements) still run real microservices successfully, and the current consensus is explicitly about *right-sizing the decision to actual team/scale reality*, not "microservices were always wrong."

**Where it's heading.** Team Topologies-style thinking (explicitly organizing service boundaries around team cognitive load and communication patterns, following Conway's Law deliberately rather than accidentally) is becoming the more sophisticated framing replacing the older, cruder "microservices vs monolith" binary — the real unit of decision is closer to "what's the smallest number of independently deployable units that matches our actual team structure and change patterns," which sometimes yields one modular monolith, sometimes yields a handful of coarser-grained services (sometimes called "macroservices" informally), and rarely yields the fine-grained, one-service-per-domain-entity decomposition that characterized the mid-2010s microservices maximalism. A more speculative, actively-discussed direction (referenced in current writing, including specifically around AI coding agents) is that AI-assisted development changes the calculus somewhat — a single AI agent reasoning across a well-organized modular monolith's clear module boundaries may navigate and modify it more effectively than reasoning across a fragmented, network-boundary-separated microservices fleet where context is scattered across repos and services — this is a genuinely new, not-yet-settled argument as of 2026, worth naming as speculative rather than established consensus.

---

## Mental model

```
MONOLITH (no enforced internal boundaries):
  ┌─────────────────────────────────────┐
  │ [Orders][Users][Billing][Inventory]  │  any module calls any other
  │  all sharing one codebase, one DB,   │  module's internals directly,
  │  one deploy, NO enforced boundaries  │  no discipline enforcing "the
  └─────────────────────────────────────┘  right way in" — the "big ball
                                             of mud" failure mode over time

MODULAR MONOLITH (enforced boundaries, SINGLE deployable unit):
  ┌─────────────────────────────────────┐
  │ [Orders]──API──▶[Billing]            │  modules talk through DEFINED
  │    │                                  │  internal interfaces only —
  │    └──API──▶[Inventory]              │  compile-time/lint-enforced,
  │ [Users]──API──▶[Orders]              │  NOT reachable-if-you-try-hard
  │  ONE deploy, ONE process, ONE DB     │  ONE transaction boundary,
  │  (or per-module schemas within it)   │  trivial LOCAL debugging
  └─────────────────────────────────────┘

MICROSERVICES (enforced boundaries, SEPARATE deployable units, NETWORK calls):
  [Orders Svc]──HTTP/gRPC──▶[Billing Svc]──▶[own DB]
       │
       └──HTTP/gRPC──▶[Inventory Svc]──▶[own DB]
  [Users Svc]──HTTP/gRPC──▶[Orders Svc]
  EACH: own deploy pipeline, own scaling, own on-call, own DB —
  but EVERY module boundary is now ALSO a network boundary: latency,
  partial failure, distributed tracing needed to debug ONE user request
  spanning 4 services, eventual consistency where a single-DB transaction
  used to be atomic and free.

MONOREPO vs POLYREPO: ORTHOGONAL to the above — a monolith OR microservices
  can live in either. Monorepo = one repo, cross-cutting refactors and
  consistent tooling easy, blast radius of a bad CI change is EVERYTHING.
  Polyrepo = one repo per service, deployment/tooling autonomy per team,
  cross-service refactors require coordinating N separate PRs/repos.
```

---

## How it actually works

### The modular monolith: what "enforced boundaries" actually means

A modular monolith isn't "a monolith with good intentions" — the boundary enforcement needs to be real and checkable, not aspirational:

```python
# untested sketch — enforced module boundary via import-linter / architecture tests
# billing/ can depend on orders/'s PUBLIC interface, never orders/internal/*
[importlinter]
root_package = myapp

[importlinter:contract:1]
name = orders internals are private
type = forbidden
source_modules = myapp.billing
forbidden_modules = myapp.orders.internal
```

```go
// untested sketch — Go's own package-privacy (lowercase = unexported) as a
// language-level enforcement mechanism, no external tool needed
package orders

type Order struct { ... }              // exported — the module's public API
func New(...) *Order { ... }           // exported

type internalPricingEngine struct { ... }  // unexported — billing CANNOT import this,
                                             // the COMPILER enforces it, not a linter
```

The specific, checkable property that distinguishes a genuine modular monolith from an unstructured one: a violation of a module boundary is a **build failure or a CI-gate failure**, not a code-review nit someone might miss. Java modules (JPMS), Go's package-level visibility, `import-linter`/`ArchUnit`-style architecture tests, and deliberate database schema separation (each module owns its own tables even inside one shared database instance, with cross-module data access only through the owning module's API, never a direct cross-schema join) are all real mechanisms for this — the tooling differs by language, the discipline is the same.

### Why microservices' cost is real, mechanically, not just cultural

Every module boundary that becomes a *network* boundary inherits the full distributed-systems tax covered mechanically elsewhere in this curriculum (`T21-resilience-catalogue`, `T16-io-models`): latency (a function call becomes a network round trip, milliseconds instead of nanoseconds), partial failure (the callee can be down, slow, or return a malformed response in ways a function call never can), and — the specific, underrated cost — **debugging a single user-facing request now requires distributed tracing across services rather than reading a stack trace**, because the request's actual execution path is scattered across process boundaries with no single call stack tying it together. The DZone-cited 35% additional debugging time is the direct, measurable consequence of this: an engineer used to `grep`-ing a monolith's logs or setting a breakpoint now needs distributed tracing (Jaeger/Zipkin-style spans stitched by a correlation ID) correctly propagated through every hop to reconstruct what happened, and if any service in the chain didn't propagate the trace context correctly, that visibility gap is exactly where debugging time balloons.

**Data consistency changes shape entirely.** A monolith's single database gives you real ACID transactions across what used to be "module" boundaries for free — updating an order and decrementing inventory in one transaction is trivial. Split into separate services with separate databases (the correct, necessary pattern for genuine service independence — sharing one database across services just recreates tight coupling through the schema instead of the code), and the same operation needs a saga pattern, an outbox pattern, or eventual consistency with compensating actions — real, well-understood patterns (covered in `T21-resilience-catalogue`'s adjacent modules on outbox/saga/CQRS), but genuinely more complex than a `BEGIN; UPDATE; UPDATE; COMMIT;` block, and a source of real production bugs (a lost message between the order-created event and the inventory-decrement consumer, discovered only when inventory counts silently drift from reality) that simply cannot happen inside one transactional boundary.

### Conway's Law and the actual decision criterion

> "Organizations which design systems ... are constrained to produce designs which are copies of the communication structures of these organizations." — Melvin Conway, 1967

The practical, current framing (Team Topologies-adjacent): **service boundaries should follow team boundaries, deliberately, not accidentally** — if two teams are perpetually blocked on each other's release cadence because their work lives in the same deployable unit, that's the concrete, specific symptom that justifies a split, not a general belief that "services scale better." Conversely, splitting a system into services *before* team structure and actual deployment-cadence conflict exists just imports network latency, partial failure, and eventual consistency for a coordination problem that didn't actually exist yet — Conway's Law running in reverse, where the architecture was designed to match an org chart that hadn't been built yet, or wasn't going to be.

**The actual, defensible reasons to split**, in the order they typically become real:

1. **Independent deployment cadence** — team A is genuinely blocked shipping because team B's changes, living in the same deployable unit, require coordinated review/testing/release even when unrelated to team A's work. This is the single most common *real* justification, and it's specifically about *team* blocking, not a vague sense that "this should be independent."
2. **Independent scaling profile** — one component's resource needs (CPU-bound image processing, a component receiving 100x the traffic of the rest of the system) are different enough from the rest that scaling the whole monolith to serve that one hot path wastes resources on everything else.
3. **Fault isolation** — a specific component's failure mode must not be allowed to take down unrelated functionality (a recommendation engine's outage shouldn't prevent checkout from working), and the failure modes are different enough (an ML inference service's GPU-related failures vs. a payment service's database failures) that shared-fate is a real risk, not a hypothetical one.
4. **Forced polyglot** — a specific, proven need for a different language/runtime for one component (a genuinely CPU-bound hot path needing Go's parallelism per `T11-fastapi-to-go`, or a component needing a language-specific library with no equivalent) that can't be satisfied within the monolith's language.

**What's notably absent from that list**: "microservices are more modern," "it'll scale better eventually," and "each service can use its own database, which is more flexible" as reasons *on their own* — all of these are either not actually true without one of the four real justifications above backing them, or are premature optimization for a scale/team-size the organization hasn't reached yet.

### Monorepo vs polyrepo: an orthogonal, separate decision

```
SHOPIFY: modular monolith (mostly) + MONOREPO
  -> cross-cutting refactors across the whole Ruby codebase are ONE PR,
     consistent linting/testing/tooling applies uniformly, no version-
     skew problem between "modules" since they deploy together anyway.

AMAZON: microservices + POLYREPO
  -> each service team owns its repo, its CI pipeline, its release
     cadence FULLY independently — a bad CI change in one repo can't
     break another team's pipeline, matches the genuine deployment-
     independence that justified the microservices split in the first place.
```

The actual criterion: monorepo wins when cross-cutting changes (a shared library update, a consistent lint rule, a company-wide refactor) are frequent and you want them atomic and easy; polyrepo wins when service-level autonomy (independent CI, independent release cadence, isolating one team's tooling choices from another's) is the actual organizational need. Notably, **the architecture-vs-repo-layout pairing is not fixed** — Shopify's monorepo houses a modular monolith specifically because their actual deployment unit *is* mostly singular, so a monorepo's cross-cutting-refactor benefit matters more than per-service autonomy they don't need; Amazon's polyrepo pairs with microservices because their actual deployment units genuinely are separate, so per-repo autonomy matches real organizational independence. Choosing monorepo-with-microservices or polyrepo-with-a-monolith are both real, defensible combinations depending on which specific pain (cross-cutting refactor friction, or deployment-autonomy friction) your organization actually has.

---

## Build it from scratch

A minimal illustration of enforcing a module boundary in a modular monolith — the concrete, checkable mechanism worth being able to describe or sketch, since "we have modules" without enforcement isn't actually a modular monolith:

```python
# untested sketch — a Python modular monolith's directory structure
# and the enforcement mechanism that makes the boundaries real
myapp/
    orders/
        __init__.py        # exports ONLY what's meant to be public: OrderService, Order
        internal/           # private implementation details
            pricing.py
            fulfillment.py
    billing/
        __init__.py
        internal/
            invoice_generator.py
    shared_kernel/          # deliberately minimal — genuinely cross-cutting types only
        money.py
        user_id.py

# billing/__init__.py:
from myapp.orders import OrderService   # OK — public interface
# from myapp.orders.internal.pricing import calculate_discount  # FORBIDDEN,
# caught by import-linter/ArchUnit-equivalent CI gate, not just convention
```

```bash
# CI gate that makes the boundary REAL, not aspirational
import-linter --config setup.cfg   # fails the build on a forbidden import,
                                     # exactly like a compile error would in
                                     # a language with real module privacy
```

A fuller lab building a small modular monolith (orders/billing/inventory modules with enforced boundaries and per-module database schemas within one Postgres instance), then a version of the same functionality split into three services with a saga-pattern-based cross-service transaction, measuring the actual added latency/complexity of the split directly, belongs in `(lab pending)`.

---

## How it's done in production

| Symptom | Cause | Fix |
|---|---|---|
| A single-line change requires coordinating deploys across 3 "independent" services and a distributed debugging session to find the actual failure | Premature microservices split — boundaries drawn before real team/deployment-cadence independence existed, creating network-boundary overhead for coupling that still exists logically | Consolidate the tightly-coupled services back (Segment's real case), or at minimum audit whether the split boundary matches an actual team boundary |
| Debugging a production incident takes hours tracing a request across 5 services with incomplete distributed tracing | Trace context not propagated correctly through every hop, or tracing infrastructure not mature enough for the number of services deployed | Invest in trace-context propagation as a non-negotiable engineering standard before splitting further, or consolidate services where tracing maturity hasn't kept pace with service count |
| A shared library change requires deploying 140+ services together, defeating the entire point of independent deployability | Services were never actually independent — shared-library coupling recreated a distributed monolith with all of microservices' operational cost and none of its benefit | Consolidate back into fewer, coarser-grained services (Segment's actual resolution), or invest in proper library versioning/backward compatibility discipline if consolidation isn't viable |
| A monolith's deploy pipeline takes 45 minutes and any unrelated team's change blocks another team's release | Genuine deployment-cadence coupling — the first of the four real justifications for splitting | This is the actual, evidence-based case for extracting a service — but extract the SPECIFIC component causing the blocking, not the whole system |
| Cross-module data queries in a "modular monolith" turn out to be direct SQL joins across module schema boundaries | Boundary enforcement was aspirational (a folder structure) rather than real (an enforced, checkable rule) | Add automated boundary-violation detection (import-linter, ArchUnit-equivalent, or schema-level access control) to CI, treating a violation as a build failure |
| A monorepo's CI pipeline breaks for every team whenever any team merges a change | Monorepo chosen without the tooling investment (proper build caching/sharding, ownership-scoped CI triggers) that makes monorepo blast radius manageable at scale | Invest in monorepo-appropriate tooling (Bazel/Nx-style incremental builds, CODEOWNERS-scoped CI), or reconsider whether polyrepo's isolated blast radius better matches current tooling maturity |

---

## Tradeoffs & when NOT to use it

- **Don't default to microservices for a new product, a small team, or an uncertain domain model.** The 2026 consensus is explicit and well-evidenced: start with a modular monolith, preserve the option to extract a service later once a real justification (one of the four above) actually materializes.
- **Don't split a service boundary that doesn't match a real team boundary.** A split driven by "this feels like it should be its own service" rather than genuine deployment-cadence conflict, scaling-profile difference, fault-isolation need, or forced polyglot requirement imports real distributed-systems cost for no corresponding benefit.
- **Don't treat "modular monolith" as a synonym for "unstructured monolith with folders."** Without enforced, CI-gated boundaries, it degrades back into a big ball of mud with extra directory nesting — the enforcement mechanism is the entire point, not decoration.
- **Don't assume monorepo implies microservices are wrong, or polyrepo implies they're right.** The two decisions are genuinely orthogonal — Shopify's monorepo-with-modular-monolith and Amazon's polyrepo-with-microservices are both real, working, defensible combinations matched to each organization's actual cross-cutting-refactor versus deployment-autonomy needs.
- **Don't underestimate data-consistency complexity when splitting a monolith's single database.** A transaction that was one `BEGIN/COMMIT` block becomes a saga or an outbox pattern with real failure modes (a lost message between steps) that simply couldn't occur before — this is usually the most underestimated cost of a service split, more than the network latency itself.
- **Don't reverse a legitimately justified microservices architecture just because consolidation is trendy in 2026.** Amazon's genuine, large-scale, many-team microservices fleet remains correct for Amazon's actual scale and team-independence reality — the current correction is about right-sizing the decision, not a universal "monoliths are always right" reflex in the other direction.

---

## Interview questions

### Q1 — What's the actual, current (2026) industry consensus on microservices versus monolith, and how has it shifted from the mid-2010s default?
**Testing:** whether the candidate's mental model is current, not stuck in the "microservices are how you scale" era.
**Answer:** The mid-2010s default was "microservices by default, monolith is legacy/outdated." The 2026 consensus has visibly corrected: a CNCF 2025 report found 42% of organizations actively consolidating services back, Gartner found 60% of teams regret microservices adoption for small-to-medium applications, and the emerging explicit best practice is starting with a well-structured modular monolith and splitting only when scale or team-size specifically justifies it — not defaulting to microservices from day one.
**Follow-up trap:** *"Does that mean microservices were a mistake industry-wide?"* — no; the correction is about *right-sizing* the decision to actual organizational scale and need, not a blanket reversal. Genuinely large, many-team organizations (Amazon's real polyrepo microservices fleet) still run real, justified microservices successfully — the mistake was applying microservices reflexively to small-to-medium applications and teams that never had the deployment-coupling pain that justifies the split.

### Q2 — What specifically makes a "modular monolith" different from a monolith with a nice folder structure?
**Testing:** whether boundary *enforcement* is understood as the defining, checkable property.
**Answer:** Enforced, checkable module boundaries — a violation (one module reaching into another's private internals) is a build failure or CI-gate failure, not a code-review nit that might be missed. Mechanisms include language-level module privacy (Go's unexported identifiers, Java's JPMS), architecture-testing tools (`import-linter`, ArchUnit-equivalent), or deliberate per-module database schema separation with no cross-schema joins allowed. Without an enforcement mechanism, a "modular monolith" degrades back into an ordinary big ball of mud with extra directory nesting.
**Follow-up trap:** *"How would you catch a boundary violation that snuck past code review?"* — an automated CI gate specifically checking for forbidden cross-module imports/dependencies, run on every PR — relying on reviewers to catch it manually doesn't scale and is exactly how boundary discipline erodes over time in a codebase without automated enforcement.

### Q3 — Name the four defensible reasons to split a monolith into real microservices, and explain why "it'll scale better" isn't on the list.
**Testing:** whether the decision criteria are concrete and specific, not vague architectural fashion.
**Answer:** (1) Independent deployment cadence — a team is genuinely blocked by another team's unrelated changes living in the same deployable unit. (2) Independent scaling profile — a component's resource needs are different enough from the rest that scaling the whole system to serve it wastes resources. (3) Fault isolation — a component's failure mode must not take down unrelated functionality, with genuinely different failure modes from the rest. (4) Forced polyglot — a proven need for a different language/runtime the monolith's language can't satisfy. "It'll scale better" isn't specific enough — a well-structured monolith scales horizontally (multiple instances behind a load balancer) just fine for the vast majority of real traffic levels, and vague scaling concerns without a concrete bottleneck are premature optimization.
**Follow-up trap:** *"What if a system genuinely might need to scale to Amazon-level traffic eventually — shouldn't you build for that from day one?"* — no; building distributed-systems complexity for a scale you haven't reached yet is exactly the premature-optimization pattern the 2026 correction pushes back against. The evidence (Segment, Prime Video's monitoring tool) is that this bet frequently doesn't pay off, and the modular monolith's whole value proposition is preserving the *option* to split later without having paid the cost upfront.

### Q4 — A DZone study found teams spend 35% more time debugging microservices than modular monoliths. Explain the mechanism behind that number.
**Testing:** whether the debugging cost is understood mechanically, not just cited as a statistic.
**Answer:** In a monolith, a single user request's entire execution path is one call stack, in one process, debuggable with a breakpoint, a stack trace, or grep-ing logs from one source. In microservices, that same request's execution is scattered across multiple processes connected by network calls — reconstructing what happened requires distributed tracing (spans correlated by a trace ID propagated through every hop), and if any single hop fails to propagate that context correctly, the trace has a gap exactly where the bug likely is, making the investigation both more tooling-dependent and more fragile than a single-process stack trace ever was.
**Follow-up trap:** *"Doesn't good distributed tracing tooling solve this?"* — it mitigates it, but doesn't eliminate the fundamental gap: tracing tooling requires correct instrumentation at every service boundary, ongoing maintenance as services are added, and genuine platform investment (a service mesh, consistent SDK usage) that many organizations running microservices haven't actually made — the 35% figure reflects real-world tooling maturity, not a theoretical ceiling that perfect tracing would eliminate to zero.

### Q5 — Explain Amazon Prime Video's 2023 monolith-migration case study accurately — what did it actually show, and what's the common overstatement of it?
**Testing:** precision about a frequently-cited but often-mischaracterized case study.
**Answer:** Prime Video moved one specific monitoring tool from a serverless/microservices design to a monolith and reported a 90% infrastructure cost reduction. The common overstatement is treating this as "Amazon abandoned microservices for the whole Prime Video platform" — it was scoped to one tool, not the entire platform, and the starting point was specifically a serverless architecture (with its own particular cost characteristics around inter-service calls and state transitions) rather than a general microservices architecture.
**Follow-up trap:** *"Does that scoping mean the case study doesn't matter?"* — no, it's still a genuine, useful data point specifically about matching architecture to actual workload characteristics (in this case, a tightly-coupled, high-throughput frame-analysis pipeline that benefited from being in-process rather than serverless-orchestrated) — the lesson is "measure and match architecture to the specific workload," not "Amazon proved monoliths beat microservices everywhere," which overstates a scoped, specific result into a universal claim it doesn't support.

### Q6 — Is monorepo vs polyrepo the same decision as monolith vs microservices? Give a real example proving they're separable.
**Testing:** whether these genuinely orthogonal axes are kept distinct, a common conflation.
**Answer:** No — they're independent decisions. Shopify runs a large monorepo housing a mostly modular-monolith architecture; Amazon runs polyrepo with genuine microservices. The repo-layout decision is about whether cross-cutting refactors and consistent tooling (monorepo's strength) matter more than per-team deployment/CI autonomy and blast-radius isolation (polyrepo's strength) — independent of whether the deployable units themselves are one monolith or many services.
**Follow-up trap:** *"When would you choose polyrepo with a monolith, or monorepo with microservices?"* — polyrepo-with-monolith is unusual but defensible if, say, regulatory/access-control requirements demand physically separate repos even though the deployment unit is singular. Monorepo-with-microservices is common and often the *better* combination when cross-cutting refactors across many services are frequent enough that coordinating N separate PRs across polyrepo would be the bigger organizational pain — Google's internal monorepo housing many independently-deployed services is the canonical large-scale example of exactly this combination.

### Q7 — A team's monolith deploy pipeline takes 45 minutes, and Team A's unrelated feature keeps getting blocked by Team B's in-progress, unrelated changes going through the same release. Is this sufficient justification to split into microservices?
**Testing:** applying the four real justifications to a realistic, ambiguous scenario.
**Answer:** This is a real instance of justification #1 (independent deployment cadence), so a split is directionally justified — but the next question is *what*, specifically, to split, not whether to split at all. The right move is extracting the specific component(s) causing the actual blocking (likely whatever Team B owns that's coupled tightly enough to force coordinated releases with Team A), not a wholesale decomposition into many fine-grained services. A narrower fix — better feature flagging, decoupling the deploy pipeline itself (independent deploy of unrelated modules within the same codebase, if the monolith's build system supports it) — might resolve the actual pain without paying the full distributed-systems cost at all.
**Follow-up trap:** *"What if extracting just that one component doesn't fully resolve the blocking because of shared database tables?"* — that's the real signal the split needs to include ownership of the relevant data too, not just the code — a service extraction that leaves the extracted service still reading/writing another module's database tables directly hasn't actually achieved independence; it's recreated the coupling through the schema instead of the code, which is precisely the "distributed monolith" failure mode Segment's case represents at larger scale.

### Q8 — How does Conway's Law inform where you'd draw service boundaries, and what happens if you draw boundaries that don't match team structure?
**Testing:** whether Conway's Law is applied as an active design tool, not just cited as a quote.
**Answer:** Conway's Law observes that system architecture tends to mirror organizational communication structure whether deliberately designed that way or not — so the practical, deliberate application is drawing service boundaries to *match* team boundaries on purpose (each service owned end-to-end by one team that can deploy it independently) rather than drawing them along some other axis (data-entity boundaries, layer boundaries) that doesn't correspond to who actually needs independence from whom. Draw boundaries that don't match team structure, and you get either a distributed monolith (multiple teams still coordinating changes across the "independent" services because the boundary doesn't match how work actually flows) or unnecessary cross-team coordination overhead for a split that didn't need to happen.
**Follow-up trap:** *"What if your organization's team structure keeps changing — should service boundaries chase it?"* — not reflexively; re-drawing service boundaries has real migration cost, so the practical answer is designing team structure and service boundaries together deliberately when possible (Team Topologies' framing), and treating a boundary mismatch as a signal to investigate — sometimes the fix is reorganizing the team to match a stable, sensible service boundary, not always re-splitting the service to match a team structure that itself might be temporary.

### Q9 — Your team already has a working microservices architecture with 30 services and it's genuinely painful to operate. Do you recommend consolidating back to a monolith?
**Testing:** whether the answer is nuanced (targeted consolidation) rather than a blanket reversal in either direction.
**Answer:** Not necessarily a full consolidation — first diagnose which specific services are causing the pain and why: services that are tightly coupled to each other (frequently deployed together, sharing data indirectly) are strong consolidation candidates, following Segment's actual playbook of merging what was never truly independent. Services with genuine, ongoing justification (real independent scaling needs, real fault-isolation requirements, teams that are genuinely productive with independent deploy cadence) shouldn't be merged just because *other* services in the fleet are painful — the fix is targeted, evidence-based consolidation of the specific coupled/painful subset, not an assumption that 30 is inherently too many or that the whole architecture is wrong.
**Follow-up trap:** *"How do you tell the difference between a service that's genuinely justified and one that's a consolidation candidate, in practice?"* — look at deployment coupling empirically: pull deployment logs and check how often services are deployed together or within a short window of each other due to a shared change, and check whether any team has actually exercised independent scaling or fault isolation for a given service in the last several months — a service that's never actually been scaled independently or never had an isolated failure that mattered is a much weaker case for staying separate than one with a documented instance of either.

### Q10 — Design the migration path for extracting a genuinely justified microservice from a modular monolith, given the four real justifications from Q3.
**Testing:** applying the earlier module's decision criteria to an actual extraction plan, mirroring the strangler-fig discipline from `T11-fastapi-to-go`.
**Answer:** First, confirm the module already has enforced boundaries within the modular monolith (if the module boundary isn't already clean and enforced in-process, extracting it into a service just moves an unenforced boundary across a network, which is strictly worse, not better). Second, resolve data ownership before extraction — the module being extracted needs to own its data outright, with any cross-module access converted to an API call before the network boundary goes in, not after. Third, extract behind a stable interface with the rest of the monolith calling the new service exactly as it called the in-process module, ideally with the interface unchanged from the caller's perspective. Fourth, apply the same shadow-then-gradual-cutover discipline as any other production migration, monitoring for the new failure modes (latency, partial failure) the network boundary introduces that were structurally impossible before.
**Follow-up trap:** *"What's the single most common mistake teams make extracting a service from a monolith?"* — extracting the code before resolving data ownership, ending up with a "service" that still reads/writes the monolith's shared database directly — this recreates tight coupling through the schema while paying the full network/deployment overhead of separation, the exact distributed-monolith failure mode this module warns about, and it's specifically common because the code extraction feels like the main task while the data migration feels like an afterthought.

---

## Red flags that fail you

- Recommending microservices by default for a new, small, or uncertain-domain project without citing the actual current evidence against that default.
- Describing a modular monolith as just "a monolith with good folder organization," missing the enforced-boundary requirement.
- Naming vague reasons ("it scales better," "it's more modern") as justification for splitting into services, rather than one of the four concrete, evidence-based reasons.
- Overstating the Prime Video case study as "Amazon abandoned microservices" rather than correctly scoping it to one tool.
- Conflating monorepo/polyrepo with monolith/microservices as if they're the same decision.
- Not knowing the real, measured costs (35% more debugging time, the Segment/140-service consolidation story) when arguing for microservices.
- Suggesting a service split that doesn't also address data ownership, leaving a "split" architecture that still shares a database directly.
- Treating the 2026 correction as "microservices are always wrong now" rather than "right-size the decision to actual scale and team need."

---

## Cheat card

```
2026 CONSENSUS (measured, not vibes): CNCF 2025 -- 42% of orgs actively
  consolidating microservices back. Gartner -- 60% of teams regret
  microservices for SMALL-TO-MEDIUM apps; monoliths cut costs ~25% on
  average. DZone 2024 -- 35% MORE debugging time for microservices vs
  modular monoliths. Emerging default: start MODULAR MONOLITH, split
  only when scale/team-size specifically justifies it.

MODULAR MONOLITH: ENFORCED, CI-GATED module boundaries (import-linter/
  ArchUnit-equivalent, language-level privacy, per-module DB schema, no
  cross-schema joins) inside ONE deployable unit. Boundary violation =
  build/CI failure, NOT a code-review nit. Without enforcement it's just
  an unstructured monolith with extra folders.

4 REAL REASONS TO SPLIT INTO MICROSERVICES:
  1. Independent DEPLOYMENT CADENCE (team genuinely blocked by another
     team's unrelated releases in the same unit) -- most common real one
  2. Independent SCALING PROFILE (genuinely different resource needs)
  3. FAULT ISOLATION (genuinely different failure modes, shared fate risk)
  4. FORCED POLYGLOT (proven need, e.g. Go for a CPU-bound hot path)
  NOT on the list: "modern," "will scale eventually," "more flexible."

MICROSERVICES COST, MECHANICALLY: every module boundary -> NETWORK
  boundary = latency + partial failure + distributed tracing needed to
  debug ONE request across N services (context must propagate correctly
  at EVERY hop or the trace has a gap exactly where the bug is).
  DATA: single-DB ACID transaction -> saga/outbox/eventual consistency
  across separate per-service DBs, with new failure modes (lost message
  between steps) that literally couldn't happen in one transaction.

CAUTIONARY CASE STUDIES (know precisely, don't overstate):
  Segment: consolidated 140+ services back -- shared library change forced
    deploying ALL of them, defeating independent-deployability's purpose.
  Prime Video (2023): ONE monitoring tool, serverless->monolith, 90% infra
    cost cut. NOT "Amazon abandoned microservices platform-wide" -- scoped.

CONWAY'S LAW (1967): architecture mirrors org communication structure,
  deliberately or not. Draw service boundaries to MATCH team boundaries
  on purpose. Mismatch -> distributed monolith (still coordinating across
  "independent" services) or unnecessary split overhead.

MONOREPO vs POLYREPO: ORTHOGONAL to monolith/microservices choice.
  Shopify = monorepo + modular monolith. Amazon = polyrepo + microservices.
  Monorepo wins: frequent cross-cutting refactors, consistent tooling.
  Polyrepo wins: per-team CI/deploy autonomy, isolated blast radius.
  Google = monorepo + MANY independently-deployed services (valid combo too).
```

## Sources

- [Microservices Rollback 2026: 42% Return to Monoliths — byteiota](https://byteiota.com/microservices-rollback-2026-42-return-to-monoliths/) — accessed 2026-08-03
- [Monolith to Microservices: When to Migrate (and When Not) — Catio](https://www.catio.tech/blog/monolith-to-microservices) — accessed 2026-08-03
- [Modular Monolith Instead of Microservices — What Changed When the AI Agent Started Reading Code — Medium](https://medium.com/@wasowski.jarek/modular-monolith-instead-of-microservices-what-changed-when-the-ai-agent-started-reading-code-c586d9f63fd7) — accessed 2026-08-03
- [Monolith vs Microservices in 2026: Are We Going Back Again? — Medium](https://medium.com/@mbodhija80/monolith-vs-microservices-in-2026-are-we-going-back-again-3b1e75d9ed1d) — accessed 2026-08-03
- [Exploring Shopify Microservices Architecture: A Comprehensive Guide — Praella](https://praella.com/blogs/shopify-insights/exploring-shopify-microservices-architecture-a-comprehensive-guide) — accessed 2026-08-03
- [All Hail the Monorepo. Long Live Microservices. — Medium](https://medium.com/jonathans-musings/all-hail-the-monorepo-long-live-microservices-4f96209c66e4) — accessed 2026-08-03
- [Monorepo vs Polyrepo for micro-service architecture — Medium](https://medium.com/@jaspreet2379/monorepo-vs-polyrepo-for-micro-service-architecture-e258a6e550d7) — accessed 2026-08-03

## Changelog
- 2026-08-03 — created
