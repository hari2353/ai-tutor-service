# SOLID: Violations, Refactors, and the Counter-Arguments

> **Track:** T21 Architecture & Design Principles · **Time:** 2h · **Prereqs:** none
> **Updated:** 2026-07-26
> **Module id:** `T21-solid` · **Tags:** principles

## The 30-second version

SOLID is five heuristics for keeping change cheap, not five laws of good code — each one has a documented failure mode where following it literally makes the system worse, and a principal candidate is expected to know both directions. SRP taken to "one reason to change" per class produces class explosion and anemic domains where the object is a bag of getters and a `*Service` class holds all the logic. ISP and DIP, applied indiscriminately, produce interface bloat and DI-framework ceremony in codebases too small to need either. The actual skill being tested isn't reciting the five letters — every mid-level candidate can do that — it's recognizing which principle is buying you real optionality in this specific codebase, and which one is cargo-culted decoration that will cost the next reader an afternoon of jumping through indirection to find one `if` statement. Say the counter-argument before the interviewer has to drag it out of you.

## Why this gets asked

Because "define SOLID" is a screening question, not a signal question, and interviewers know it. What they're actually probing at senior/staff level is whether you've been burned by SOLID applied dogmatically — the codebase with 40 single-method interfaces and a DI container wiring together classes with three-line bodies, or the "clean" service layer where the domain model has no behavior and every operation lives in a manager class that mutates it externally. They've personally inherited one of these codebases, spent a week understanding a feature that should have taken an hour, and want to hear that you'd have made a different call. The trap for confident-sounding candidates is answering as if SOLID is uniformly good; the trap for contrarian candidates is dismissing it as irrelevant. The senior answer holds both: here's the failure it prevents, here's the failure it causes when overapplied, here's how I'd decide which risk is live in this codebase.

## Lineage: past → present → future

**What came before.** Object-oriented design in the 1990s optimized for reuse through inheritance — deep class hierarchies, `TemplateMethod`-heavy frameworks, and the assumption that "is-a" relationships model the world cleanly. The pain was fragile base class syndrome: a change to a shared superclass silently broke every subclass, and hierarchies grew rigid exactly where the business needed them flexible. Bertrand Meyer's Open/Closed Principle (*Object-Oriented Software Construction*, 1988) and Barbara Liskov's substitutability principle (1987, formalized 1994) were independent responses to that specific pain. Robert C. Martin collected these plus three of his own into the SOLID acronym in the early 2000s (the term itself was coined by Michael Feathers around 2004), packaging them for an industry moving from big design up front toward iterative, Agile delivery where the cost of a wrong abstraction needed to be visible immediately rather than at the next major rewrite.

**Where it stands now.** SOLID is close to universal vocabulary in interviews and code review, but there is genuine, public disagreement about how literally to apply it. The mainstream position, including from Martin himself, is that SOLID describes *symptoms to watch for*, not a checklist to satisfy per class — SRP's "reason to change" is about actors and stakeholders, not "does this method do one thing." The live disagreement is between that reading and a more literal one that treats each principle as a rule to apply per file, which is exactly what produces the counter-examples this module is built around: SRP-as-decomposition-rule yields class explosion and anemic domains; ISP-as-rule yields an interface per method; DIP-as-rule yields dependency-injection frameworks and factory indirection in a service with three callers. What's actually deployed at scale, in codebases people call well-architected (Stripe's API layer, most idiomatic Go standard library code, most well-regarded Python services), tends to follow the *spirit* — small interfaces where there's a real reason for multiple implementations, dependency inversion where there's a real seam for testing or swapping infra — without applying every letter everywhere. Functional and lightly-OO languages (Go, Rust, modern Python) have also partially absorbed several of these concerns into language features: structural typing (Go interfaces, Python protocols) gives you ISP and DIP without an abstract base class or annotation, so "SOLID" in those ecosystems looks less like the GoF-era Java diagrams the acronym was originally illustrated with.

**Where it's heading.** Confidence is moderate-to-high that the trend continues: less inheritance-based OOP, more composition and structural typing, and SOLID increasingly discussed as "which of these five tradeoffs is live here" rather than a checklist applied uniformly. More speculative: as LLM-assisted code generation becomes routine, there's an open question about whether the abstraction discipline SOLID enforces — interfaces as change-insulation — becomes *more* valuable (because generated code needs stable seams for humans to review and swap) or less relevant (because the marginal cost of regenerating an implementation drops, reducing the payoff of insulating against change). Treat that as a direction of travel, not settled practice.

---

## Mental model

Every SOLID principle answers "where do I want change to be cheap, and what am I willing to pay for that?" Draw it as a knob, not a switch:

```
        cheap change here                              cheap change nowhere
        (many small seams)                              (one big file)
              │                                                  │
   over-applied SOLID              the actual target        no structure
   (interface bloat,          (seams exist where change      (God object,
    DI ceremony,              is expected; nowhere else)      shotgun surgery)
    anemic domain)
              └──────────────────────┬───────────────────────────┘
                          "one reason to change,
                           per actor, not per method"
```

The five letters are five different places you can put that knob: SRP (how much logic lives per class), OCP (how you add behavior — new code vs. edited code), LSP (whether a subtype is safe to substitute), ISP (how narrow a consumer's view of a dependency is), DIP (which direction the compile-time dependency arrow points). Getting all five right does not mean maximizing every knob. It means matching each knob to where *this* codebase actually changes.

---

## How it actually works

### S — Single Responsibility Principle

**The real definition, ignored by most examples.** "A class should have only one reason to change" — Martin later clarified this means *one actor/stakeholder* whose requirements drive changes to that class, not "one method" or "one verb." A `Employee` class with `calculatePay()`, `save()`, and `reportHours()` violates SRP not because it has three methods, but because Accounting, DBA, and Operations are three different actors who will each demand changes to that class for their own reasons, and those changes will collide in the same file.

**Violation (real pattern, seen constantly):**

```python
class OrderProcessor:
    def process(self, order: Order) -> None:
        # validation — changes when business rules change
        if not order.items:
            raise ValueError("empty order")
        # pricing — changes when finance changes tax rules
        total = sum(i.price * i.qty for i in order.items)
        total *= self._tax_rate(order.region)
        # persistence — changes when DBA changes schema
        self.db.execute("INSERT INTO orders ...", order.id, total)
        # notification — changes when marketing changes copy
        self.email_client.send(order.customer_email, f"Order total: {total}")
```

Four actors (product/business rules, finance, DBA, marketing) all cause changes to one class. A tax rule change and a schema migration now touch the same file and the same PR review, with no way to test pricing without a live DB and email client.

**Refactor:**

```python
class OrderValidator:
    def validate(self, order: Order) -> None: ...

class Pricer:
    def total(self, order: Order) -> Decimal: ...

class OrderRepository:
    def save(self, order: Order, total: Decimal) -> None: ...

class OrderNotifier:
    def notify(self, order: Order, total: Decimal) -> None: ...

class OrderProcessor:
    def __init__(self, validator, pricer, repo, notifier):
        self._validator, self._pricer = validator, pricer
        self._repo, self._notifier = repo, notifier

    def process(self, order: Order) -> None:
        self._validator.validate(order)
        total = self._pricer.total(order)
        self._repo.save(order, total)
        self._notifier.notify(order, total)
```

Pricer is now unit-testable with no DB or network. A tax law change touches `Pricer` only.

**The honest counter-argument.** Taken further than this — say, splitting `Pricer` into `TaxCalculator`, `DiscountCalculator`, `SurchargeCalculator`, each with its own interface and factory — you get **class explosion**: twelve files to read to understand one calculation, and worse, you get an **anemic domain model**. If SRP is applied to the *domain entities themselves* ("Order should have no behavior, only data, because behavior is a separate reason to change"), you end up with `Order` as a bag of fields and an `OrderService` that does everything to it from outside. Martin has explicitly called this a misreading of SRP — the entity's own invariants (can this order transition to `shipped`? is this line item valid?) belong on the entity, because "the rules for what makes an order valid" is itself one actor (the domain expert), and splitting that logic out into a service is not respecting SRP, it's violating encapsulation while believing you're following a principle. The interview-ready version: SRP is about actors, not verb count, and the failure mode of over-applying it is exactly the anemic domain model the DDD module and the anti-patterns module both call out independently.

### O — Open/Closed Principle

**Definition.** Software entities should be open for extension, closed for modification — you add behavior by adding new code, not editing code that already works and is already tested.

**Violation:**

```python
def calculate_shipping(order: Order) -> Decimal:
    if order.carrier == "ups":
        return order.weight_kg * Decimal("2.10")
    elif order.carrier == "fedex":
        return order.weight_kg * Decimal("1.95")
    elif order.carrier == "usps":
        return order.weight_kg * Decimal("1.50")
    # every new carrier = another elif, and a re-test of the whole function
```

Every new carrier requires editing a function that shipping for three other carriers already depends on and already passed review. One typo in the new branch risks the existing branches through shared test fixtures and shared blast radius on deploy.

**Refactor — strategy via polymorphism (or, in Python, just a dict of callables):**

```python
from typing import Protocol

class ShippingStrategy(Protocol):
    def cost(self, order: Order) -> Decimal: ...

class UPSShipping:
    def cost(self, order: Order) -> Decimal:
        return order.weight_kg * Decimal("2.10")

STRATEGIES: dict[str, ShippingStrategy] = {"ups": UPSShipping(), ...}

def calculate_shipping(order: Order) -> Decimal:
    return STRATEGIES[order.carrier].cost(order)
```

Adding FedEx Ground is a new class and one dict entry; UPS's tested code is untouched.

**Honest counter-argument.** OCP is the principle most likely to produce **speculative generality** — building a plugin architecture for "carriers we might add" when there are two carriers and no roadmap for a third. YAGNI directly conflicts with OCP here: the abstraction has a real cost (an extra layer to read, an extra place to look for the actual logic) that only pays off if extension actually happens. A staff-level answer says: the `if/elif` chain is *fine* at 3 branches that change rarely; the strategy pattern earns its cost around 5-8 branches that change independently, or when a second axis appears (carrier × region pricing) that would otherwise multiply the branches combinatorially. Don't reach for OCP on the first extension point you see — reach for it on the second or third, once you've observed the actual axis of change rather than guessed at it.

### L — Liskov Substitution Principle

**Definition.** If `S` is a subtype of `T`, objects of type `T` should be replaceable with objects of type `S` without altering the correctness of the program — subtypes must honor the base type's preconditions (no strengthening), postconditions (no weakening), and invariants.

**Violation — the canonical rectangle/square, but a production-flavored one:**

```python
class ReadOnlyCache:
    def get(self, key: str) -> Any: ...
    def set(self, key: str, value: Any) -> None:
        raise NotImplementedError("read-only cache")  # breaks the contract callers assume

class Cache:
    def get(self, key: str) -> Any: ...
    def set(self, key: str, value: Any) -> None: ...
```

If `ReadOnlyCache` is typed as a `Cache` (inherits or implements the same interface) and any code path calls `.set()` polymorphically — a write-through decorator, a generic warm-up routine — it now raises at runtime in a code path that type-checked cleanly. The caller had every reason to believe `Cache.set()` was safe to call.

**Refactor:** don't make `ReadOnlyCache` a subtype of the mutable interface at all. Split the interface:

```python
class Readable(Protocol):
    def get(self, key: str) -> Any: ...

class Writable(Protocol):
    def set(self, key: str, value: Any) -> None: ...

class Cache(Readable, Writable): ...
```

Code that only needs to read depends on `Readable`; `ReadOnlyCache` implements only `Readable` and the type system makes the illegal call impossible rather than a runtime surprise.

**Honest counter-argument.** LSP is the SOLID principle with the least practical daylight for "overapplying it" — a genuine LSP violation is a correctness bug, not a taste preference, so there's little room to argue the other direction. The closest thing to a real counter-argument is that chasing LSP purity can push you toward the same interface fragmentation ISP produces (splitting `Readable`/`Writable`/`Deletable`/`Listable` because some implementation can't honor one of them), and at that point you're paying ISP's cost to fix an LSP violation — which is the correct trade, but worth naming explicitly rather than treating each principle as if it operates in isolation.

### I — Interface Segregation Principle

**Definition.** No client should be forced to depend on methods it does not use. Prefer several small, client-specific interfaces over one general-purpose one.

**Violation:**

```python
class ToolExecutor(Protocol):
    def execute(self, args: dict) -> Any: ...
    def validate_schema(self, args: dict) -> bool: ...
    def get_cost_estimate(self, args: dict) -> float: ...
    def supports_streaming(self) -> bool: ...
    def cancel(self, run_id: str) -> None: ...

class SimpleCalculatorTool:
    def execute(self, args): ...
    def validate_schema(self, args): return True
    def get_cost_estimate(self, args): return 0.0     # meaningless for this tool
    def supports_streaming(self): return False         # meaningless
    def cancel(self, run_id): pass                     # meaningless, silently does nothing
```

Three of five methods are dead stubs. Every new tool author has to know to implement (or safely no-op) methods irrelevant to their tool, and a caller that calls `.cancel()` on a tool that silently no-ops it gets no signal that cancellation didn't happen.

**Refactor:**

```python
class Executable(Protocol):
    def execute(self, args: dict) -> Any: ...

class SchemaValidated(Protocol):
    def validate_schema(self, args: dict) -> bool: ...

class Cancellable(Protocol):
    def cancel(self, run_id: str) -> None: ...

class SimpleCalculatorTool:
    def execute(self, args): ...
```

`SimpleCalculatorTool` implements exactly what it needs. Callers that need cancellation do `isinstance(tool, Cancellable)` or, in a typed system, only accept `Cancellable` where cancellation matters, and get a type error instead of a silent no-op if a tool doesn't support it.

**Honest counter-argument.** ISP is the principle most prone to **interface bloat in the other direction** — one interface per method, so a caller that genuinely needs `execute`, `validate_schema`, and `cancel` together has to import and compose three protocols and the type signature of any function accepting "a tool" balloons. This is a real, named failure mode (Wikipedia's "interface bloat" entry exists because of exactly this pattern in enterprise Java, where `IReadable`, `IWritable`, `IDeletable`, `IListable` fragmentation made simple code hard to write generically). The judgment call: segregate along the axis where implementations *actually* diverge (some tools genuinely can't be cancelled; almost none skip schema validation), not along every method independently. If every real implementation supports every method, one interface is correct and ISP's "several small interfaces" advice is actively the wrong call.

### D — Dependency Inversion Principle

**Definition.** High-level modules should not depend on low-level modules; both should depend on abstractions. Abstractions should not depend on details; details depend on abstractions. This is distinct from dependency *injection* (a mechanism) — DIP is about which direction the compile-time dependency arrow points.

**Violation:**

```python
class RecommendationService:
    def __init__(self):
        self.db = PostgresClient(host="prod-db-1", ...)  # high-level module
                                                            # depends directly on
                                                            # a concrete low-level one
    def recommend(self, user_id: str) -> list[Item]:
        rows = self.db.query("SELECT ...")
        ...
```

`RecommendationService` cannot be unit tested without a live Postgres instance, cannot be pointed at a different store without editing this class, and a schema-detail change in `PostgresClient` ripples upward into business logic that has nothing to do with SQL.

**Refactor:**

```python
class ItemRepository(Protocol):
    def candidates_for(self, user_id: str) -> list[Item]: ...

class PostgresItemRepository:
    def __init__(self, client: PostgresClient): self.client = client
    def candidates_for(self, user_id: str) -> list[Item]: ...

class RecommendationService:
    def __init__(self, repo: ItemRepository):   # depends on the abstraction
        self.repo = repo
    def recommend(self, user_id: str) -> list[Item]:
        return self.repo.candidates_for(user_id)
```

`RecommendationService` now compiles against `ItemRepository`, an abstraction it owns conceptually (the high-level module defines the interface it needs; the low-level module implements it — "the client owns the interface," not the provider). Tests inject an in-memory fake in microseconds.

**Honest counter-argument.** This is where the interview should get interesting. DIP's cost is real: an interface, a concrete implementation, and — in many Java/Spring codebases — a DI container, `@Autowired` wiring, and a factory, for a dependency that has exactly one implementation and will likely always have exactly one implementation. That is pure ceremony bought for optionality nobody will exercise. In small services and scripts, direct instantiation is not a violation worth fixing; it's correctly-scoped simplicity. The signal that DIP is earning its keep: you actually swap implementations (prod vs. test, Postgres vs. an in-memory fake, one vendor vs. another) or you need the seam for testing without spinning up infrastructure. The signal it's cargo cult: an interface with one implementation that has never changed, wired through three layers of factory to satisfy a framework convention, where nobody has ever needed to swap it and nobody plans to. At staff level, saying "I'd skip DIP here — one implementation, no test-isolation need, the container wiring costs more than it buys" is a stronger answer than "always inject."

---

## Build it from scratch

The interview-relevant exercise isn't implementing a pattern from zero — it's taking a small violating snippet (usually 15-30 lines, exactly like the `OrderProcessor` above) and refactoring it live while narrating the actor/reason-to-change reasoning out loud. Practice this shape:

1. Read the snippet, name the actors/reasons-to-change out loud before writing code.
2. Extract one seam at a time — don't do all five principles in one pass; that overengineers a toy example, which is itself a red flag the interviewer will note.
3. After each extraction, say what you'd verify before merging (a unit test, a check that behavior is unchanged) and what you would *not* extract further, and why.

The last step is what separates SRP-as-catechism from SRP-as-judgment. A candidate who stops extracting and says "I'd leave notification and persistence together here because they change together in this codebase's history" is showing more seniority than one who keeps splitting until every method is its own class.

---

## How it's done in production

**Where SOLID shows up as language features rather than discipline:**

| Language ecosystem | What replaces manual DIP/ISP discipline |
|---|---|
| Go | Structural typing — any type satisfying a method set implements the interface with zero declaration. ISP is close to free: define the narrow interface at the *consumer*, not the provider. |
| Python | `typing.Protocol` gives structural typing (PEP 544); duck typing gave you this informally for two decades before the type checker caught up. |
| Java/C# | Nominal typing means DIP/ISP require explicit interface declarations and usually a DI container (Spring, `Microsoft.Extensions.DependencyInjection`) — this is why SOLID discourse is heaviest in the Java ecosystem: the language makes you pay the ceremony cost explicitly. |
| Rust | Traits + generics/dyn give you ISP and DIP with compile-time or dynamic dispatch, and the borrow checker independently forces you to be honest about ownership, which sidesteps a class of LSP violations around mutable aliasing. |

**Failure-mode table:**

| Symptom | Cause | Fix |
|---|---|---|
| Every PR touches 6+ files for a one-line business rule change | SRP over-applied; logic fragmented across too many collaborators for one actor's concern | Consolidate collaborators that change together back into one class |
| Domain entities are pure data classes; all logic lives in `*Service`/`*Manager` classes | Misapplied SRP ("behavior is a separate reason to change") | Move invariant-protecting logic onto the entity; keep only cross-entity orchestration in services |
| New team members can't find the actual logic — it's behind 3 layers of interface and factory | DIP/OCP applied to code with one implementation and no extension in its history | Collapse the abstraction; reintroduce it only when a second implementation is real |
| `NotImplementedError` / silent no-op stubs on interface implementations | ISP violated — interface too wide for some implementers | Split the interface along the axis where implementations actually diverge |
| A subtype override throws or silently changes behavior callers relied on | LSP violation | Don't model the relationship as inheritance/subtyping; use composition or split the interface |
| A trivial `if/elif` carrier/type dispatch has grown to 15+ branches, each edited by a different team, breaking each other's branches | OCP violation — should have become a strategy/registry pattern several branches ago | Extract to strategy pattern or dispatch table once a second independent axis of change appears |

---

## Tradeoffs & when NOT to use it

- **Don't apply SRP to entities themselves.** Business invariants (what makes an `Order` valid) belong on the entity. Extracting them into a service in the name of SRP produces the anemic domain model — data with no behavior, logic scattered externally, and every operation needing to reach into the entity's internals to enforce rules it should enforce on itself.
- **Don't reach for OCP before you've seen the second or third variation.** A 3-branch `if/elif` is not a violation; it's proportionate. Building a plugin system for one hypothetical future carrier is YAGNI colliding with OCP, and YAGNI should win until the axis of change is observed, not guessed.
- **Don't segregate interfaces along axes where every real implementation agrees.** If all your tools support cancellation, one `Tool` interface with a `cancel()` method is correct; five micro-interfaces for a divergence that doesn't exist is interface bloat, a real named anti-pattern.
- **Don't invert a dependency that has exactly one implementation and no test-isolation need.** The interface-plus-DI-container ceremony costs real reading time; it should be justified by an actual swap you make (test double, alternate vendor), not by "best practice."
- **LSP is the exception — there is close to no legitimate "overapplication."** A subtype that can't honor its supertype's contract is a latent bug, not a style choice. The only nuance is that fixing an LSP violation correctly (splitting the interface) inherits ISP's cost, which is a fair trade, not a reason to avoid the fix.
- **All five degrade badly under short-lived code.** A one-off ETL script, a Jupyter analysis notebook, a hackathon prototype — none of this benefits from SOLID's change-insulation because the code won't live long enough to need to change safely. Applying it there is a signal of inexperience, not diligence.

---

## Interview questions

### Q1 — What does "one reason to change" actually mean in SRP?
**Testing:** whether you know the actor-based definition or the folklore "one method" version.
**Answer:** One reason to change means one *actor or stakeholder* whose requirements drive changes to the class — Martin's later clarification, not "does one verb." A class serving three different stakeholders (finance, DBA, marketing) violates SRP even if every method is one line, because those stakeholders' changes will collide in the same file at different times for unrelated reasons.
**Follow-up trap:** *"So more methods always means more reasons to change?"* — no. A class with ten methods that all serve one actor (e.g., ten query methods on a single repository, all changing only when the schema changes) has one reason to change and is a correct SRP application, not a violation.

### Q2 — Show me SRP applied so far it hurts.
**Testing:** whether you can name the failure, not just recite the principle.
**Answer:** An anemic domain model — entities reduced to getters/setters, all business logic pushed into external `*Service` classes because "validation is a separate reason to change from persistence." This breaks encapsulation: the entity can no longer protect its own invariants, callers must know and re-apply business rules externally, and Martin himself has called this a misapplication of SRP, not a correct one.
**Follow-up trap:** *"Isn't separating persistence from business logic just DIP?"* — that's a different, correct concern (which datastore, injected as an abstraction). Anemia is different: it's stripping *domain logic* out of the entity, not swapping *storage*. Conflating the two is a common interview stumble.

### Q3 — When would you deliberately violate OCP?
**Testing:** whether OCP is dogma or judgment to you.
**Answer:** When there are 2-3 known variants with no evidence of more coming, and the abstraction (strategy interface, plugin registry) would cost more reading time than the `if/elif` it replaces. I'd introduce the strategy pattern once a second independent axis of variation appears (e.g., carrier × region) or once branch count crosses roughly 5-8 and starts being edited by different owners who step on each other.
**Follow-up trap:** *"What if the interviewer/PM insists this will definitely need 10 more variants next quarter?"* — then build the abstraction now; OCP is a bet on a *known* future, not a hedge against an *imagined* one. The judgment is about evidence, not risk-aversion in either direction.

### Q4 — Rectangle/square: is a square a rectangle in code?
**Testing:** the canonical LSP example, checking whether you understand *why*, not just the punchline.
**Answer:** Mathematically yes; behaviorally, no, if `Rectangle` exposes independent `setWidth`/`setHeight` — a `Square` subtype must keep both sides equal, so setting one silently changes the other, breaking any caller that sets width expecting height to stay fixed. That's a postcondition/invariant violation, which is exactly what LSP forbids: substituting `Square` for `Rectangle` changes program correctness.
**Follow-up trap:** *"So how do you model it correctly?"* — don't model `Square` as a subtype of mutable `Rectangle`. Either make both immutable (construct with both dimensions, no setters — LSP holds trivially) or don't relate them by inheritance at all; a shared `Shape` interface exposing only `area()` avoids the trap entirely.

### Q5 — Give a real example where ISP fragmentation went too far.
**Testing:** recognition of interface bloat as a named, real anti-pattern, not a hypothetical.
**Answer:** Enterprise Java codebases with `IReadable`, `IWritable`, `IDeletable`, `IListable`, `ISortable` per entity type, where every real implementation implements all five. A function that should accept "a repository" now has to accept five type parameters or the caller composes an intersection type, and reading the code requires jumping through five files to see what one repository actually does. This is literally documented as "interface bloat."
**Follow-up trap:** *"How do you decide where the segregation line actually is?"* — segregate along axes where implementations *actually diverge in your codebase today*, verified by looking at existing implementers, not by imagining hypothetical future ones that might not support a method.

### Q6 — DIP vs dependency injection — same thing?
**Testing:** whether you conflate the principle with the mechanism, a very common mistake.
**Answer:** No. DIP is about which direction the *dependency arrow* points at compile time — high-level and low-level modules should both depend on an abstraction, not the high-level depending directly on the low-level's concrete type. Dependency injection is one *mechanism* (constructor/setter/framework injection) for supplying an implementation of that abstraction at runtime. You can follow DIP without a DI framework (manual constructor injection); you can use a DI framework and still violate DIP if the injected type is a concrete class, not an abstraction.
**Follow-up trap:** *"Then why do people use them interchangeably?"* — because in practice they're usually paired (once you invert the dependency, you need *some* way to supply the concrete implementation, and injection is the natural mechanism), but conflating them in an interview reads as not having thought about it past the acronym.

### Q7 — When is a DI container actively the wrong call?
**Testing:** the honest counter-argument to DIP, a genuine senior signal.
**Answer:** When a dependency has exactly one implementation, no plan for a second, and no test-isolation need that a plain constructor call couldn't satisfy with a manual fake. The container adds indirection (locate the binding, trace the wiring, understand the container's lifecycle rules) that costs real onboarding and debugging time, for optionality nobody exercises. Small services and most CLI tools fall here.
**Follow-up trap:** *"But doesn't it make testing easier regardless?"* — manual constructor injection (`def __init__(self, repo: ItemRepository)`) gives you the same testability without a container; the container specifically buys you configuration-driven wiring and lifecycle management (singleton/scoped/transient), which only pays off with enough dependencies and enough environments (dev/test/staging/prod) that manual wiring becomes unwieldy — usually somewhere past a dozen services, not at three.

### Q8 — How do you decide whether to apply SOLID at all in a given piece of code?
**Testing:** whether you have a decision procedure or just a reflex.
**Answer:** By expected lifetime and expected axis of change. Short-lived scripts, one-off ETL, hackathon code: skip it, the insulation never pays off before the code is deleted. Long-lived services with multiple contributors and an observed (not imagined) axis of variation: apply the specific principle that addresses *that* axis, not all five uniformly. The tell that you're doing this right is that different files in the same codebase get different amounts of structure.
**Follow-up trap:** *"Isn't that just 'it depends' dressed up?"* — no, because it names the two variables (lifetime, observed variation) that decide it, rather than leaving the judgment unstated. "It depends" without naming what it depends on is the actual red flag; naming the two axes is the answer.

### Q9 — Walk me through refactoring a God object using SOLID.
**Testing:** the practical, live-coding version of this whole module.
**Answer:** Identify the actors (who asks for changes and why) before touching code. Extract one collaborator per actor (SRP), have the original class depend on those collaborators through interfaces it owns conceptually (DIP), keep the interfaces as wide as the actual implementers need and no wider (ISP), and if there's a real branching axis (e.g., three notification channels), extract a strategy (OCP) — but only for that one axis, not preemptively for axes that don't exist yet. Verify behavior is unchanged after each step, ideally with characterization tests written before the first extraction.
**Follow-up trap:** *"What order do you do the extractions in?"* — persistence and I/O first, because isolating them buys you fast unit tests for everything else you extract next; pure-logic extraction (pricing, validation) benefits most from those fast tests existing already.

### Q10 — Your team lead says "just follow SOLID, it's best practice." How do you respond in a design review?
**Testing:** whether you can push back on dogma constructively, a real staff/principal competency.
**Answer:** Agree on the goal (cheap, safe change) and ask which specific axis of change is actually live in this code — then apply the one or two principles that address it, and explicitly flag the ones that would add cost without buying anything here (e.g., "I wouldn't add a repository interface for this table; we have one datastore, no test-isolation need beyond what a transaction rollback in test setup already gives us"). This reframes "best practice" as a claim that needs evidence, without dismissing the principles wholesale.
**Follow-up trap:** *"What if they push back that 'best practice' should just always apply?"* — point to a concrete cost: interface-per-implementation ceremony that has, in this specific codebase's git history, never had a second implementation land. Evidence from the actual repo beats abstract argument.

### Q11 — A subtype needs to reject a call its supertype allows. What are your options?
**Testing:** LSP repair strategies, staff-level depth beyond "don't do that."
**Answer:** Three real options: (1) don't model it as inheritance — use composition, the subtype wraps rather than extends; (2) split the interface (ISP) so the supertype only promises what all subtypes can honor, and the rejecting type simply doesn't implement the narrower piece; (3) if the rejection is truly a runtime business rule rather than a type-level incapability (e.g., "cancel is allowed only before shipping"), express it as a return value or exception that's part of the *documented* contract, not a surprise — LSP is violated by silently strengthening preconditions or weakening postconditions, not by every possible failure path.
**Follow-up trap:** *"Isn't option 3 just weakening the contract you said not to weaken?"* — no, if the possibility of that failure is part of the contract from the start (e.g., the method's documented signature returns a `Result` type or raises a named, expected exception for all implementers), every substitutable subtype honors the same contract; it's only an LSP violation when a subtype's behavior surprises callers who reasonably relied on the supertype's stated contract.

### Q12 — Design a plugin system for something with genuinely open-ended extension (e.g., a tool-calling agent's tool registry). Which SOLID principles actually matter here and why?
**Testing:** transferring SOLID to a domain the candidate claims expertise in — agentic systems.
**Answer:** OCP is the load-bearing one: new tools are added by registering a new implementation, not editing a dispatcher. ISP matters at the tool-interface boundary — a tool that can't be cancelled or streamed shouldn't be forced to fake support for those; the agent loop should query capability (`isinstance(tool, Cancellable)`) rather than assume a monolithic interface. DIP matters at the layer between the agent loop and the tool registry — the loop depends on a `ToolRegistry` abstraction, not a concrete list, so tests can inject a fake registry with deterministic tools. SRP matters less here than in typical CRUD code, because "execute this tool" genuinely is one actor's (the agent runtime's) concern end to end.
**Follow-up trap:** *"What breaks if you get ISP wrong here?"* — every tool author is forced to implement `cancel()`, `estimate_cost()`, `supports_streaming()` even for a stateless calculator tool; most will stub them incorrectly (return `True` for `supports_streaming` without actually supporting it), and the agent loop discovers this at runtime as a hang or a malformed stream, not at registration time.

---

## Red flags that fail you

- Reciting the five definitions with no example of a real violation for any of them.
- Treating SRP as "one method per class" instead of "one actor per class."
- Claiming SOLID has no downside, or claiming SOLID is universally outdated — both are absolutist answers to a judgment question.
- Not knowing what an anemic domain model is, or not connecting it to SRP misapplication.
- Confusing dependency injection (the mechanism) with dependency inversion (the principle).
- Proposing a strategy pattern / plugin architecture for a 2-branch conditional with no stated evidence of more branches coming.
- Segregating an interface into one method per file with no divergence among real implementers to justify it.
- Saying "always inject dependencies" with no acknowledgment that a DI container has a real cost.

---

## Cheat card

```
SRP   "one reason to change" = one ACTOR, not one method/verb
      over-applied → anemic domain model, class explosion
      entity invariants belong ON the entity, not extracted "for SRP"

OCP   add behavior via NEW code (strategy/registry), not edited if/elif
      apply at ~5-8 branches or a 2nd independent axis, not before
      under-applying too early = speculative generality = YAGNI violation

LSP   subtype must honor super's pre/postconditions + invariants
      near-zero legitimate "overapplication" — it's a correctness bug
      fix: composition instead of inheritance, or split the interface

ISP   no client forced to depend on methods it doesn't use
      over-applied → interface bloat (1 interface per method)
      segregate along axes where REAL implementers diverge, not imagined ones

DIP   high + low level modules both depend on an ABSTRACTION
      client (high-level) owns the interface, not the provider
      skip it: 1 implementation, no test-isolation need, no DI container payoff
      DIP ≠ dependency injection (principle vs. mechanism)

DECISION RULE: apply the ONE principle addressing the OBSERVED axis of
change in THIS code. Short-lived/one-off code → skip all five.
Different files in one repo should carry different amounts of structure.
```

## Sources

- [When Using SOLID Principles May Not Be Appropriate — Baeldung on Computer Science](https://www.baeldung.com/cs/solid-principles-avoid) — accessed 2026-07-26
- [Anemic Domain Model — Martin Fowler](https://martinfowler.com/bliki/AnemicDomainModel.html) — accessed 2026-07-26
- [Anemic domain model — Wikipedia](https://en.wikipedia.org/wiki/Anemic_Domain_Model) — accessed 2026-07-26
- [Interface bloat — Wikipedia](https://en.wikipedia.org/wiki/Interface_bloat) — accessed 2026-07-26
- [135 SOLID interview questions — Adaface](https://www.adaface.com/blog/solid-principles-interview-questions/) — accessed 2026-07-26
- [100+ SOLID Principles Interview Questions and Answers (2026) — We Create Problems](https://www.wecreateproblems.com/interview-questions/solid-principles-interview-questions) — accessed 2026-07-26

## Changelog
- 2026-07-27 — created
