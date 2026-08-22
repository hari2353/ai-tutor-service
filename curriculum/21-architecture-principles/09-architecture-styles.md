# Layered, Hexagonal, Onion, Clean, Modular Monolith, Microservices

> **Track:** T21 Architecture & Design Principles · **Time:** 2.0h · **Prereqs:** none · **Updated:** 2026-08-01
> **Module id:** `T21-architecture-styles` · **Tags:** architecture

## The 30-second version

Layered architecture is the default everyone starts with and the default everyone's domain model quietly rots under, because "the service layer talks to the repository layer" says nothing about which direction business rules depend on, and in practice they end up depending on the ORM. Hexagonal (2005), onion (2008), and clean (2012) are three names, three vocabularies, and one idea: dependencies point inward, toward the domain, never outward toward frameworks or infrastructure, so the business logic can be tested and reasoned about without a database or an HTTP server in the room. They differ mostly in what they call the pieces, not in what the pieces do. The **modular monolith** is what most teams should actually build first: one deployable unit with real internal module boundaries, no shared tables between modules, no reaching into another module's internals, enforced by tooling rather than convention. Microservices are a genuine answer to a genuine problem, independent scaling and independent deployment for teams that have outgrown a shared release train, but they are not free, and in 2026 a documented 42% of organizations that adopted them have walked at least some services back into larger units. Conway's Law is not a fun fact here; it is a design constraint, because your service boundaries will converge on your org chart whether you plan for it or not.

## Why this gets asked

Because "explain hexagonal architecture" is a knowledge check, and "when would you NOT use microservices" is the actual signal. The interviewer has personally either inherited a distributed monolith (twelve services, one release train, every deploy requires coordinating three teams) or watched a team over-invest in ports-and-adapters for a CRUD app that never needed to swap infrastructure. They are checking whether you reach for architecture as fashion or as a response to a named force: team size, deployment independence, scaling asymmetry, or genuine domain volatility at the boundary you're isolating.

---

## Lineage: past → present → future

**What came before.** Two-tier and three-tier architectures (presentation, business logic, data access) were the default from the 1990s client-server era onward, and layered architecture is their direct descendant: "N-tier," drawn as horizontal bands, each layer calling the one below. The pain it produced was specific and repeatable — the **anaemic domain model** — because layered architecture defines the *layers* but says nothing about dependency *direction* within the domain layer, so the path of least resistance is a domain object that is a bag of getters and setters, with all the actual behavior living in "service" classes that orchestrate it. Martin Fowler named this failure mode explicitly in 2003 (*AnemicDomainModel*), and it persists precisely because layered architecture doesn't structurally prevent it; it only organizes files, not dependencies.

**Where it stands now.** Alistair Cockburn's Hexagonal (Ports and Adapters, 2005), Jeffrey Palermo's Onion Architecture (2008), and Robert Martin's Clean Architecture (2012) are the current answer, and the honest thing to say in an interview is that they are the same idea published three times with different vocabulary: isolate the domain, invert dependencies so infrastructure depends on the domain's interfaces rather than the reverse, and push every framework, database, and I/O concern to the outside where it can be swapped without touching business logic. The differences are naming (Clean calls the domain object an "entity" and an application service a "use case"; Onion doesn't prescribe a specific mechanism for the inversion; Hexagonal calls the interfaces "ports" and the implementations "adapters") plus emphasis, not substance. On the deployment-topology axis, the live and data-backed disagreement is modular monolith versus microservices: reported 2026 industry data shows 42% of organizations that adopted microservices have consolidated some services back into larger deployable units, with microservices satisfaction down 19 percentage points versus 2024, and infrastructure cost comparisons in the 3.75x-6x range for equivalent functionality (roughly $15k/month for a monolith versus $40k-65k/month for the microservices equivalent once platform-team and coordination overhead are counted) ([byteiota, accessed 2026-08-01](https://byteiota.com/modular-monolith-42-ditch-microservices-in-2026/)). Treat the specific multipliers as one source's estimate, not an industry-wide constant, but the direction, a real and growing consolidation trend, is corroborated across multiple 2026 write-ups.

**Where it's heading.** The modular monolith is consolidating as the stated default starting point in 2026 material, with tooling maturing to enforce module boundaries mechanically rather than by convention (Spring Modulith with ArchUnit fitness functions in the JVM world; equivalent lint-level boundary enforcement emerging elsewhere) — high confidence, this is a tooling and consensus shift already underway, not speculation. The framing that's gaining ground is a spectrum rather than a binary: start modular monolith, extract a service only when a specific team or scaling boundary demands independent deployment, and treat that extraction as a migration with a clear trigger, not a default. Whether "microservices by default" fully reverses or just plateaus at a smaller footprint (used deliberately at true scale-out points, not as a starting architecture) is the speculative part; the consolidation trend is real, its ultimate floor is not yet settled.

---

## Mental model

```
LAYERED (horizontal bands, no enforced dependency direction within the domain):
  Presentation
      |
  Business/Service   <-- can quietly depend on infra types if nothing stops it
      |
  Data Access
      |
   Database

HEXAGONAL / ONION / CLEAN (concentric rings, dependencies point INWARD only):

        ┌─────────────────────────────────────┐
        │   Frameworks, DB, HTTP, UI (outside) │   <- depends on the ring inside it
        │   ┌─────────────────────────────┐    │
        │   │  Adapters / Infrastructure  │    │
        │   │   ┌───────────────────┐     │    │
        │   │   │  Application /    │     │    │
        │   │   │  Use Cases        │     │    │
        │   │   │   ┌───────────┐   │     │    │
        │   │   │   │  Domain   │   │     │    │
        │   │   │   │ (Entities)│   │     │    │
        │   │   │   └───────────┘   │     │    │
        │   │   └───────────────────┘     │    │
        │   └─────────────────────────────┘    │
        └─────────────────────────────────────┘
        Nothing in the center ring imports anything from an outer ring.
        The outer rings implement interfaces the center ring defines.

MODULAR MONOLITH (one deployable, real internal boundaries):
  ┌──────────────────────────────────────────────────────────┐
  │  process / deployable unit                                │
  │  ┌────────────┐  ┌────────────┐  ┌────────────┐          │
  │  │  Orders    │  │  Inventory │  │  Billing   │          │
  │  │  module    │  │  module    │  │  module    │          │
  │  │  own table │  │  own table │  │  own table │          │
  │  └─────┬──────┘  └─────┬──────┘  └─────┬──────┘          │
  │        └── talks only through public module APIs ─┘        │
  │            never a direct SQL join across module tables    │
  └──────────────────────────────────────────────────────────┘

MICROSERVICES (independently deployable, independent data, network between):
  [Orders service] --HTTP/event--> [Inventory service] --HTTP/event--> [Billing service]
   own DB, own deploy                own DB, own deploy                own DB, own deploy
```

---

## How it actually works

### Layered and the anaemic-domain trap

A layered design typically looks like `Controller -> Service -> Repository -> Entity`. Nothing in that stack forbids the `Entity` from being a plain data holder and every rule about it living in `Service`. That's the anaemic domain model: objects with state but no behavior, and behavior scattered across service classes that operate *on* the data rather than objects that *enforce invariants about themselves*. The tell in code review: a domain object where every method is a getter or setter, and a service class with a method name that is itself a business verb (`OrderService.cancelOrder(order)` instead of `order.cancel()`). The fix is not a new architecture, it's discipline: push behavior that belongs to an entity's invariants onto the entity, and reserve services for orchestration across multiple entities or external systems. Layered architecture doesn't prevent this discipline, it also doesn't enforce it, which is exactly the gap hexagonal/onion/clean close by making the domain a structurally separate, dependency-free ring.

### Hexagonal, onion, clean: one idea, three vocabularies

All three enforce the **Dependency Inversion Principle** at the architecture level: source-code dependencies point toward the domain, and where control flow needs to go the other way (the domain needs to save something to a database), the domain defines an interface and an outer layer implements it.

| Concept | Hexagonal (Cockburn, 2005) | Onion (Palermo, 2008) | Clean (Martin, 2012) |
|---|---|---|---|
| Core | Domain + application logic | Domain model | Entities |
| Boundary interface | Port | (not separately named) | Boundary / Interface Adapter |
| Implementation of the interface | Adapter | Infrastructure | Interface Adapter / Framework |
| Orchestration layer | Application service | Application services | Use Cases |
| Framing | Inside/outside, hexagon is just "not a rectangle so people stop drawing 3 boxes" | Concentric rings | Concentric rings + the Dependency Rule stated explicitly |

```python
# untested sketch — the dependency-inversion move, independent of which name you use
# domain layer (innermost, ring/hexagon center) — defines the interface, imports nothing outward
class OrderRepository(Protocol):
    def save(self, order: "Order") -> None: ...
    def find(self, order_id: str) -> "Order": ...

class Order:
    def cancel(self) -> None:
        if self.status == "shipped":
            raise DomainError("cannot cancel a shipped order")
        self.status = "cancelled"

# application layer — orchestrates, depends only on the domain's interface
class CancelOrderUseCase:
    def __init__(self, repo: OrderRepository):
        self.repo = repo
    def execute(self, order_id: str) -> None:
        order = self.repo.find(order_id)
        order.cancel()
        self.repo.save(order)

# infrastructure layer (outermost) — implements the interface, depends INWARD on the domain
class PostgresOrderRepository:  # implements OrderRepository
    def save(self, order: Order) -> None: ...  # SQL here
    def find(self, order_id: str) -> Order: ...
```

Note what never happens: `Order` and `CancelOrderUseCase` never import anything from `PostgresOrderRepository` or a web framework. Swapping Postgres for DynamoDB, or a REST controller for a CLI, touches only the outer ring.

**Honest caveat:** the payoff is real (testable domain logic with zero DB in the loop, genuine infrastructure swappability) and the cost is also real — more files, more indirection, an interface for every dependency the domain has. For a CRUD app with one datastore that will never change, this is often more ceremony than value; see Tradeoffs below.

### Modular monolith: what makes a boundary real

A "module" that's just a folder with no enforcement is not a modular monolith, it's a monolith with optimistic naming. A real module boundary has three properties:

1. **No shared tables.** Module A's tables are never queried directly by Module B's code, not even with a "just this once" join. If B needs Order data, it calls Orders' public API (a function call in-process, but a *defined* one), not `SELECT * FROM orders`.
2. **No reaching into internals.** Only a module's declared public interface (its package's `__init__.py` exports, its public classes) is callable from outside; internal classes, internal tables, internal helper functions are invisible across the boundary, enforced by the language's visibility rules or a linter, not a comment saying "please don't."
3. **Boundaries enforced by tooling, not convention.** Spring Modulith plus ArchUnit fitness functions is the reference example in the JVM world: a test that fails the build if a class in `orders` imports a class in `inventory.internal`. Equivalent enforcement exists via import-linter in Python, dependency-cruiser in JS/TS, or simply separate Go modules with unexported internals. Without this, "modules" degrade into a big ball of mud with extra folders within a year, because nothing stops the shortcut under deadline pressure.

The reward for getting this right: a modular monolith gives you most of microservices' organizational clarity (a team owns a module, a module has a clear contract) without the operational cost of a network hop, a separate deploy pipeline, and separate data stores per boundary. The extraction path to a real microservice, if you ever need one, is comparatively cheap precisely because the boundary was already real.

### Microservices: actual costs vs actual benefits

**Actual benefits, when they apply:** independent deployability (team A ships without waiting for team B's release train), independent scaling (a hot service scales without over-provisioning the cold ones), fault isolation at the process level, and the ability for different services to use different languages/runtimes when a specific workload genuinely benefits.

**Actual costs, always paid:** a network call where there was a function call (latency, partial failure, the entire resilience catalogue in `T21-resilience-catalogue` becomes mandatory rather than optional); distributed data (no cross-service transactions, sagas required, see `T21-outbox-saga-cqrs`); operational multiplication (N services means N deploy pipelines, N sets of dashboards, N on-call surfaces); and a documented infrastructure cost premium, reported around 3.75x-6x for equivalent functionality in 2026 analyses, driven by platform-team and coordination overhead as much as raw compute ([byteiota, accessed 2026-08-01](https://byteiota.com/modular-monolith-42-ditch-microservices-in-2026/)).

**When to split, concretely:** a specific module has a scaling profile wildly different from the rest of the system (an image-processing endpoint that needs GPU instances while the rest of the app is CPU-bound); a specific module needs an independent release cadence because a different team owns it and shared releases are provably the bottleneck (not "might be" — measured deploy-queue wait time); or a genuine security/compliance boundary requires process isolation. Splitting because "microservices are what serious companies do" is the single most common way teams end up with a **distributed monolith** (see `T21-anti-patterns`): all the network cost of microservices, none of the independent-deployability benefit, because the services still have to release together.

### Conway's Law as a design constraint

"Organizations which design systems ... are constrained to produce designs which are copies of the communication structures of these organizations" (Melvin Conway, 1967). In practice: if three teams jointly own one service, that service's internal structure will fracture along team lines whether or not anyone draws that boundary on purpose, because each team optimizes its own subset without a forcing function to coordinate globally. The corollary the industry calls the **Inverse Conway Maneuver**: if you want a target architecture, restructure the teams first, because team boundaries will produce matching service boundaries with much less friction than trying to hold a service boundary against the grain of who actually talks to whom day to day. This is why "just draw better microservice boundaries" fails without matching org boundaries, and why a modular monolith with real module ownership per team is often the more Conway-compatible choice for a team that hasn't yet split into fully independent squads.

---

## Build it from scratch

The demonstrable artifact for this module is a small hexagonal slice: a domain (`Order`), one port (`OrderRepository`), two adapters (in-memory for tests, SQLite for "production"), and a use case, with a test suite that never touches SQLite:

```python
# untested sketch
class InMemoryOrderRepository:
    def __init__(self):
        self._store: dict[str, Order] = {}
    def save(self, order: Order) -> None:
        self._store[order.id] = order
    def find(self, order_id: str) -> Order:
        return self._store[order_id]

def test_cancel_order_use_case():
    repo = InMemoryOrderRepository()
    order = Order(id="1", status="pending")
    repo.save(order)
    CancelOrderUseCase(repo).execute("1")
    assert repo.find("1").status == "cancelled"
    # zero database, zero network, zero framework in this test
```

For the modular-monolith boundary check, the equivalent artifact is a fitness function: a test that fails the build if `orders/` imports anything from `inventory/internal/`. In Python, a minimal version with `import-linter`'s `contracts` config; in the JVM, Spring Modulith's `ApplicationModules.verify()`.

No dedicated lab folder exists for this module yet; the pattern is a direct extension of the DIP examples in `T21-solid`.

---

## How it's done in production

| Concern | Tool / approach | What it adds |
|---|---|---|
| Enforcing hexagonal/clean boundaries | ArchUnit (JVM), import-linter / `flake8-clean-architecture` (Python), dependency-cruiser (JS/TS) | Build fails on an inward dependency violation instead of relying on code review to catch it |
| Modular monolith boundary enforcement | Spring Modulith + ArchUnit fitness functions, Go's unexported internals + separate modules, NX/Turborepo project boundaries in a monorepo | Compile-time or CI-time boundary violations, not a convention in a wiki page |
| Microservice extraction | Strangler fig pattern: route an increasing slice of traffic to the new service while the monolith path still exists, cut over, then delete the old path | A reversible, incremental migration instead of a big-bang rewrite |
| Service boundary discovery | Domain-driven design's bounded contexts (see `T21-ddd`), event storming workshops | A principled way to decide where a split actually belongs, versus splitting by technical layer (a "database service," a "validation service") which produces exactly the chattiness anti-pattern this track warns against |

### What breaks at scale

| Symptom | Cause | Fix |
|---|---|---|
| Domain objects are all getters/setters, business rules scattered across "Service" classes | Layered architecture with no enforced dependency direction; anaemic domain model | Push invariant-enforcing behavior onto the entity; consider hexagonal/onion if this recurs across the codebase |
| A change to one "module" requires touching three others in the same PR | Modules exist as folders only, no enforced boundary; internal classes reached across the boundary | Add fitness-function tests (ArchUnit/import-linter); make internals actually inaccessible, not just discouraged |
| Every deploy of Service A requires Service B and C to deploy in lockstep | Distributed monolith: services split by network but not by data/release independence | Either genuinely decouple data ownership and contracts, or accept it's one deployable and consolidate (see `T11-monolith-vs-micro`) |
| Infra bill triples after a microservices migration with no throughput change | Coordination and platform-team overhead absorbed the split's theoretical efficiency gains | Measure per-service cost against the specific scaling/deployment win claimed before the split; consolidate services that never needed independent scaling |
| Two teams keep blocking each other on the same service | Conway's Law: the org structure doesn't match the service boundary | Either restructure team ownership to match the desired architecture (Inverse Conway Maneuver) or split the service along the team seam |
| New engineer can't tell which layer owns a piece of business logic | No agreed vocabulary/ring model adopted; ad hoc "layered-ish" structure | Pick one of hexagonal/onion/clean explicitly and document the mapping (what's a "port," what's a "use case") so the vocabulary is shared |

---

## Tradeoffs & when NOT to use it

- **Hexagonal/onion/clean is overkill for a CRUD app with one datastore that will never realistically change.** The interfaces, the extra indirection, and the "which ring does this go in" debates cost real time; pay that cost when you actually need to swap infrastructure, test the domain in isolation at scale, or the domain logic is complex enough to be worth protecting. A thin CRUD service gains little from three layers of ports and adapters around a single `UPDATE` statement.
- **Modular monolith is the wrong starting point only when you already know, with evidence, that you need independent scaling or independent deployment from day one** (e.g., a component with a fundamentally different traffic and cost profile, like ML inference alongside a CRUD API). Otherwise, start here — it is not a compromise, it is usually the correct default in 2026, and it keeps the extraction path open.
- **Microservices are the wrong choice for a team smaller than the number of services it would own.** If five engineers are running fifteen services, the operational tax (fifteen dashboards, fifteen deploy pipelines, fifteen on-call rotations) dwarfs any benefit, and this is precisely the shape of the 42% who have started consolidating.
- **Splitting along technical layers ("auth service," "validation service," "database service") is close to always wrong.** It produces the chattiness anti-pattern, not the independence you wanted, because a single business operation now fans out across N network hops for what used to be N function calls. Split along bounded contexts (business capabilities), not technical concerns.
- **Ignoring Conway's Law is not neutral, it's actively wrong.** A service boundary that cuts across a single team's day-to-day communication pattern will be fought by that team's actual workflow indefinitely, regardless of how clean the diagram looks.

---

## Interview questions

### Q1 — What's the actual difference between hexagonal, onion, and clean architecture?
**Testing:** whether you know these are one idea or three separate systems.
**Answer:** They're the same underlying idea, published by three people in three years (Cockburn 2005, Palermo 2008, Martin 2012): dependencies point inward toward the domain, infrastructure implements interfaces the domain defines rather than the domain depending on infrastructure. The differences are vocabulary (Clean calls the domain "entities" and application logic "use cases"; Hexagonal calls the boundary interfaces "ports" and implementations "adapters"; Onion doesn't prescribe a specific inversion mechanism) and slight emphasis, not substance.
**Follow-up trap:** *"So why do people argue about which one to use?"* — mostly bikeshedding over naming conventions in a codebase, which is a real cost (onboarding confusion) but not an architectural one. Pick one vocabulary, document the mapping, move on.

### Q2 — What's the anaemic domain model, and why does layered architecture produce it?
**Answer:** Domain objects that are pure data holders (getters/setters only) with all actual business logic living in "service" classes that operate on them. Layered architecture organizes code into horizontal bands (presentation/service/data-access) but says nothing about dependency direction *within* those bands, so nothing stops the domain object from becoming an anemic bag of fields while behavior accumulates in the service layer, which is the path of least resistance under time pressure.
**Follow-up trap:** *"Is an anaemic domain model always wrong?"* — no, it's a legitimate choice for simple CRUD where there's genuinely little behavior to encapsulate, i.e., transaction-script style is honest there. It's wrong when the domain has real invariants (an order that can't ship after cancellation) and those invariants end up enforced inconsistently across multiple service methods instead of in one place.

### Q3 — When would you explicitly choose NOT to use hexagonal/clean architecture?
**Answer:** When the app has one datastore it will never swap, the domain logic is thin, and the team is small enough that the extra ports/adapters/use-case layers cost more in navigation and boilerplate than they save in testability. A CRUD admin panel over one Postgres database rarely needs three layers of indirection around each endpoint.
**Follow-up trap:** *"What if the team plans to grow the domain complexity later?"* — that's a real reason to adopt it proactively, but say so explicitly rather than defaulting to it out of habit; the cost should be justified by a stated future need, not "best practice."

### Q4 — Modular monolith vs microservices. Where do you start a new system in 2026?
**Answer:** Modular monolith, by default. One deployable unit, real internal module boundaries enforced by tooling (no shared tables, no reaching into another module's internals), which gives most of the organizational clarity microservices are credited with at a fraction of the operational cost. 2026 industry data shows 42% of organizations that adopted microservices have since consolidated some services back, with satisfaction down 19 points from 2024 and infrastructure costs reported 3.75x-6x higher for equivalent functionality — consolidation is a real, measured trend, not just a contrarian take.
**Follow-up trap:** *"What would make you start with microservices instead?"* — a component with a genuinely different scaling profile from day one (e.g., GPU-bound inference next to a CPU-bound API), or an organizational requirement for fully independent teams shipping independently from day one. Absent a concrete forcing function, defaulting to microservices is optimizing for a scale you don't have yet.

### Q5 — What makes a module boundary "real" in a modular monolith, versus just a folder?
**Answer:** Three things: no shared tables across modules (each owns its own schema, cross-module access goes through the module's public API, never a direct join); no reaching into another module's internal classes (only the declared public interface is callable); and enforcement by tooling — a fitness-function test (ArchUnit, import-linter, dependency-cruiser) that fails the build on a violation, not a comment or a wiki page.
**Follow-up trap:** *"What happens if you skip the tooling and just document the rule?"* — the boundary degrades within roughly a release cycle under deadline pressure; someone adds "just this one join" to hit a date, and six months later there are a dozen and the modular monolith is a monolith with extra folders.

### Q6 — Name two actual costs of microservices that are easy to underestimate.
**Answer:** Distributed data, meaning cross-service consistency now requires sagas and eventual consistency instead of a database transaction (the entire outbox/saga/CQRS catalogue becomes load-bearing rather than optional); and operational multiplication, meaning N services means N deploy pipelines, N dashboards, N on-call surfaces, which is a headcount and process cost that scales with service count independent of actual traffic.
**Follow-up trap:** *"Isn't a service mesh supposed to absorb a lot of that operational cost?"* — it absorbs some transport-level concerns (retries, mTLS, outlier detection) but adds its own operational surface (the mesh itself needs operating, upgrading, debugging) and does nothing for the data-consistency cost, which is architectural, not infrastructural.

### Q7 — What's the difference between microservices and a distributed monolith?
**Answer:** A distributed monolith has the network-call cost of microservices (latency, partial failure, serialization) without the benefit of independent deployability, because the services still have to release together — usually because they share a database, or their contracts are so tightly coupled that a change to one forces a coordinated change to the others. It's the worst of both worlds: monolith coupling, microservices operational tax.
**Follow-up trap:** *"How do you diagnose whether you have one?"* — check whether any single change (a schema migration, a field rename) requires coordinating a release across more than one service's team. If yes routinely, you have a distributed monolith regardless of how many separate repos or deploy pipelines exist.

### Q8 — Explain Conway's Law and why it's not just a fun observation.
**Answer:** Melvin Conway's 1967 observation: systems mirror the communication structure of the organizations that build them, because each team optimizes locally without a forcing function for the whole. Practically: a service jointly owned by three teams will fracture along those team lines internally regardless of the diagram, and a clean architectural boundary that cuts against how people actually talk day to day will be fought continuously. It's a design constraint because ignoring it doesn't make it not apply, it just makes the mismatch a recurring source of friction nobody names correctly.
**Follow-up trap:** *"What's the Inverse Conway Maneuver?"* — deliberately restructuring teams to match the target architecture, on the theory that it's cheaper to move team boundaries than to hold a service boundary against the grain of actual communication patterns. It's a real, named technique, not just theory — used explicitly in large re-orgs justified by architecture goals.

### Q9 — Your five-person team owns fifteen microservices. What's your assessment?
**Answer:** The operational tax (fifteen dashboards, fifteen deploy pipelines, fifteen sets of alerts, cross-service debugging) is almost certainly costing more than any independent-scaling or independent-deployment benefit the team is actually using, especially at five engineers where nobody can specialize. This is exactly the shape of team the 2026 consolidation trend describes. The fix is consolidating services with correlated release cadence and no real scaling divergence back into a modular monolith, keeping genuinely independent-scaling components (if any) as separate services.
**Follow-up trap:** *"How would you decide which services to consolidate first?"* — start with the pairs that always deploy together anyway (evidence they were never independently deployable in practice) and the ones with the lowest traffic/lowest scaling divergence from the rest, since those capture the operational savings with the least migration risk.

### Q10 — How do you decide where a service boundary belongs?
**Answer:** Along bounded contexts, business capabilities with their own ubiquitous language and data ownership (see `T21-ddd`), discovered via domain modeling or event storming, not along technical layers. A split into an "auth service," a "validation service," and a "database service" produces chattiness (many network round trips per business operation) rather than independence, because a single business operation now has to hop across all three for what used to be one function call.
**Follow-up trap:** *"What's a concrete symptom that a boundary was drawn along the wrong axis?"* — N+1 network calls where you'd expect N+1 in-process calls at worst: a single user-facing request fanning out to five internal services for what is conceptually one operation, each round trip adding tens of milliseconds and its own failure mode.

### Q11 — Walk me through the strangler fig pattern for extracting a service from a monolith.
**Answer:** Introduce a routing layer (a proxy, a feature flag, a facade) in front of the functionality being extracted. Build the new service, and incrementally route a growing percentage of traffic to it while the old code path in the monolith still exists and still works. Once the new service is proven at full traffic, delete the old path. The point is that at every step the system is in a working, releasable state, unlike a big-bang rewrite where nothing works until everything does.
**Follow-up trap:** *"What's the hard part in practice?"* — dual-writing or synchronizing data during the transition period when both the old and new code paths might be live for different requests; this usually needs exactly the outbox/CDC machinery from `T21-outbox-saga-cqrs` to keep both sides consistent during the migration window, which is often underestimated in the project plan.

### Q12 — Design a system where you'd genuinely justify microservices from day one.
**Testing:** whether you can name a concrete forcing function rather than defaulting to fashion.
**Answer:** A platform with a component that has an inherently different scaling and cost profile from the rest, for example, a GPU-bound video-transcoding pipeline behind a CPU-bound web app, where co-locating them in one deployable would force over-provisioning one side or under-provisioning the other. Splitting there from day one is justified because the scaling divergence is known up front, not discovered later. The rest of the system still starts as a modular monolith.
**Follow-up trap:** *"Would you split it into one service or several?"* — one, for that specific scaling-divergent workload; resist the temptation to also split the surrounding CRUD app into further services just because you're "already doing microservices" for the one component that needed it.

---

## Red flags that fail you

- Describing hexagonal, onion, and clean as fundamentally different architectures rather than the same idea with different vocabulary.
- Recommending microservices as a default with no named scaling, deployment, or team-boundary forcing function.
- Not knowing what an anaemic domain model is, or defending it as always correct.
- Treating "modules" as a naming convention with no enforcement and calling that a modular monolith.
- Splitting a system along technical layers (auth service, validation service) and calling it domain-driven.
- No mention of Conway's Law when asked why a service boundary keeps causing friction.
- Claiming microservices are strictly better for testability, scalability, or maintainability with no caveat.

---

## Cheat card

```
LAYERED             N-tier bands, no enforced dependency DIRECTION -> anaemic domain model risk
                     Fowler named "AnemicDomainModel" in 2003

HEX/ONION/CLEAN      Cockburn 2005 (hexagonal/ports&adapters) / Palermo 2008 (onion) / Martin 2012 (clean)
                     SAME IDEA: dependencies point INWARD to domain; infra implements domain's interfaces
                     Hex: port=interface, adapter=impl · Clean: entity, use case
                     cost: extra indirection; skip for thin CRUD with 1 datastore that won't change

MODULAR MONOLITH     one deployable, real module boundaries: no shared tables, no reaching into internals,
                     enforced by TOOLING (ArchUnit/Spring Modulith, import-linter, dependency-cruiser)
                     the 2026 DEFAULT starting point for most teams

MICROSERVICES        benefits: independent deploy/scale, fault isolation, polyglot
                     costs: network>function call, distributed data (sagas), N x ops surfaces
                     2026 data: 42% of adopters consolidated some services back;
                     satisfaction -19pp vs 2024; infra cost ~3.75-6x for equiv functionality
                     split trigger: NAMED scaling/deployment/team divergence, not fashion

DISTRIBUTED MONOLITH  network cost of microservices + release coupling of a monolith = worst of both
                       symptom: any schema change needs multi-team coordinated release

CONWAY'S LAW          (1967) systems mirror the org's communication structure
                       Inverse Conway Maneuver: restructure teams to get the architecture you want

STRANGLER FIG          route growing % of traffic to new service, old path stays live until cutover,
                        then delete old path — always releasable, unlike big-bang rewrite

SPLIT ALONG            bounded contexts / business capability, NOT technical layers
                        wrong-axis symptom: N+1 network calls for one logical business operation
```

## Sources

- [The Modular Monolith 2026 Complete Guide — Spring Modulith, ArchUnit Fitness Functions](https://dev.to/x4nent/the-modular-monolith-2026-complete-guide-spring-modulith-archunit-fitness-functions-and-lessons-878) — accessed 2026-08-01
- [Modular Monolith: 42% Ditch Microservices in 2026 — byteiota](https://byteiota.com/modular-monolith-42-ditch-microservices-in-2026/) — accessed 2026-08-01
- [Clean Architecture vs. Onion Architecture vs. Hexagonal Architecture](https://ccd-akademie.de/en/clean-architecture-vs-onion-architecture-vs-hexagonal-architecture/) — accessed 2026-08-01
- [Understanding Hexagonal, Clean, Onion, and Traditional Layered Architectures — Roman Glushach, Medium](https://romanglushach.medium.com/understanding-hexagonal-clean-onion-and-traditional-layered-architectures-a-deep-dive-c0f93b8a1b96) — accessed 2026-08-01
- [Monolith vs. Modular Monolith vs. Microservices: What is Better? — Leobit](https://leobit.com/blog/monolith-vs-modular-monolith-vs-microservices/) — accessed 2026-08-01

## Changelog
- 2026-08-01 — created
