# DDD: Aggregates, Bounded Contexts, Context Mapping, Event Storming

> **Track:** T21 Architecture & Design Principles · **Time:** 2.0h · **Prereqs:** none · **Updated:** 2026-08-01
> **Module id:** `T21-ddd` · **Tags:** architecture

## The 30-second version

Domain-Driven Design is two layers that most teams do backwards: **strategic design** decides where the boundaries are and what language is spoken inside each one, and **tactical design** is the toolbox (entities, value objects, aggregates, repositories) you use to express a model once you're inside a boundary. Teams skip the hard strategic conversation, "what are our bounded contexts and where do they disagree about what a 'customer' even is," and jump straight to tactical patterns, ending up with a codebase full of `Entity` and `Repository` classes wrapping what is still, underneath, one undifferentiated domain model shared across contexts that actually mean different things by the same words. The **bounded context** is the central idea: a boundary within which a model and its ubiquitous language are internally consistent, and outside of which the same word can mean something else entirely. The **aggregate** is the transactional consistency boundary, everything inside it is kept consistent by one transaction, everything outside is referenced by id and kept consistent eventually. Context mapping names the actual political and technical relationships between contexts, not just the technical ones. DDD is overkill for a domain with little real complexity; its whole cost is justified by the complexity it's managing, not by architectural taste.

## Why this gets asked

Because "we use DDD" and "we did the strategic modeling work" are different claims, and almost everyone who says the first has only done tactical patterns. The interviewer has watched a team build an "Order" aggregate with a repository and a domain event, congratulate themselves on doing DDD, and then discover eighteen months later that Sales' "Customer" and Support's "Customer" were silently the same table with fields nobody agreed on the meaning of, because nobody ever did the bounded-context exercise that would have surfaced it. They want to know if you understand DDD's actual value proposition, that complex domains have real conceptual seams, and that finding those seams (strategic) matters more than which pattern you use to implement one side of the seam (tactical).

---

## Lineage: past → present → future

**What came before.** Pre-DDD, the default approach to a complex domain was either a single shared "enterprise data model" everyone was expected to converge on, or an anaemic-CRUD approach where the domain was just a normalized schema and business rules lived scattered across services and stored procedures. Both failed the same way: a single shared model cannot simultaneously be correct for every department's actual usage, because "Customer" genuinely means something different to Sales (a lead with a probability score) than to Support (an account with a history) than to Billing (a payer with a balance), and forcing one canonical `Customer` table to serve all three produces a table with fields that are meaningful in one context and garbage in the others, with nobody quite sure which. Eric Evans' 2003 book *Domain-Driven Design: Tackling Complexity in the Heart of Software* named this directly: the fix isn't a better shared model, it's accepting there should be *multiple* models, each valid within its own bounded context, with explicit, designed relationships between them.

**Where it stands now.** The tactical patterns (entities, value objects, aggregates, repositories, domain events) are widely adopted and mostly uncontroversial as a vocabulary for expressing a rich domain model in code; frameworks and codebases across Java, C#, and increasingly Python and TypeScript use this language even when the team hasn't engaged with the strategic half at all. The strategic half, bounded contexts and context mapping, is the part that's inconsistently practiced: teams that do it report it as the highest-leverage exercise in the whole discipline (surfacing hidden disagreements before they become a production incident), and teams that skip it report DDD as "just extra ceremony around CRUD," which is the predictable result of applying the toolbox without the boundary-finding exercise the toolbox is meant to serve. The live disagreement is really about DDD's fit with microservices: a common and defensible heuristic is "one bounded context per microservice" (or per module in a modular monolith), but this is a starting heuristic, not a law — a single bounded context sometimes needs to span multiple services for operational reasons, and a single service can sometimes host more than one small bounded context.

**Where it's heading.** Event storming (Alberto Brandolini, workshop format popularized from roughly 2013 onward) has become the default facilitation technique for finding bounded contexts collaboratively rather than having an architect declare them from a whiteboard alone, and its adoption looks stable rather than growing or shrinking. The more interesting speculative direction is DDD's relationship to AI-assisted development: an agent can draft a bounded-context map from a codebase's existing structure and naming inconsistencies faster than a human reading the same code, which changes event storming from a pure discovery exercise into a validation exercise against an AI-drafted starting point — this is plausible and some teams report doing it informally, but there's no settled methodology yet, treat it as a direction of travel rather than practice.

---

## Mental model

```
STRATEGIC (where are the seams, what do words mean where):

  ┌─────────────────────┐        ┌─────────────────────┐        ┌─────────────────────┐
  │   Sales Context      │        │  Fulfillment Context │        │   Billing Context    │
  │  "Customer" = a lead  │  ACL   │  "Order" = a shipment │  OHS/PL │  "Customer" = a payer │
  │   with a probability  │◄──────►│   with a manifest     │◄───────►│   with a balance      │
  │   Ubiquitous Language: │       │  Ubiquitous Language:  │        │  Ubiquitous Language:  │
  │   lead, pipeline, deal │       │   pick, pack, manifest │        │   invoice, dunning     │
  └─────────────────────┘        └─────────────────────┘        └─────────────────────┘
        each box = a BOUNDED CONTEXT. The arrows are CONTEXT MAPPING relationships:
        which side translates for the other, and who is upstream vs downstream.

TACTICAL (inside one bounded context):

  Aggregate boundary = one transaction, one consistency guarantee
  ┌──────────────────────────────────────┐
  │  Order (AGGREGATE ROOT — entity,      │
  │         has identity, the only thing  │
  │         referenced from outside)      │
  │    ├─ LineItem (entity, internal,     │
  │    │            only reachable via    │
  │    │            Order)                │
  │    └─ Money (VALUE OBJECT — no        │
  │              identity, compared by    │
  │              value: $10 == $10)       │
  └──────────────────────────────────────┘
   Another aggregate (Customer) never holds a direct reference to Order's
   internals — only Order.id. Cross-aggregate consistency is eventual,
   coordinated by domain events, not a shared transaction.
```

---

## How it actually works

### Strategic vs tactical, and why teams do it backwards

**Strategic design** answers: where are the boundaries, what is each boundary's ubiquitous language, and how do the boundaries relate. **Tactical design** answers: given that I'm inside one boundary, how do I express its model in code. Teams reach for tactical patterns first because they're concrete, learnable from a blog post in an afternoon, and immediately produce code that looks more "DDD" (an `Order` aggregate root with a repository). Strategic design requires a workshop with domain experts, produces a diagram rather than code, and its payoff (avoiding a future disaster) is invisible until the disaster would have happened. The result of doing it backwards: a codebase with tactical vocabulary wrapped around a domain model that was never actually decomposed into the right boundaries, so the aggregates are drawn along technical convenience (one aggregate per database table) rather than around real consistency requirements, and the "bounded contexts" are just service names with no examined difference in language or model underneath.

### Bounded context and ubiquitous language

A bounded context is the boundary within which a specific model, and the language describing it, is internally consistent and doesn't need qualification. Inside the Fulfillment context, "Order" unambiguously means a shipment with a pick list and a manifest; you don't need to say "the fulfillment sense of Order" because there's no other sense in the room. The **ubiquitous language** is the vocabulary domain experts and engineers agree to use, consistently, in conversation, in code, in tests, inside that boundary — the discipline is that the code's class and method names *are* the domain expert's words, not a translation layer where the expert says "cancel the order" and the code says `updateStatusFlag(4)`.

**The concrete symptom that a bounded-context boundary is missing:** the same word, used in two different meetings, means two different things, and nobody has noticed because nobody has ever put both meanings in the same sentence. This surfaces in production as a field that's "usually right" in most contexts and silently wrong in one, because the shared model was correct for the context it was designed against and coincidentally close enough for the others until a specific transaction exposed the gap.

### Context mapping

Context mapping names the actual relationship between two bounded contexts, technical and organizational, not just "they call an API."

| Pattern | Relationship | When it applies |
|---|---|---|
| **Shared Kernel** | Two teams share a subset of the model (code, schema, or both) by deliberate agreement, changes require both teams' buy-in | Small, tightly collaborating teams where the shared subset is genuinely stable |
| **Customer/Supplier** | Downstream team's needs are treated as a first-class input to upstream's planning; upstream has some obligation to the downstream team | Upstream and downstream teams are in the same organization with a real prioritization relationship |
| **Conformist** | Downstream just accepts upstream's model as-is, no translation layer, no negotiation | Upstream has no incentive to accommodate you (e.g., a third-party API, a much larger internal team) and the cost of an ACL isn't justified |
| **Anticorruption Layer (ACL)** | Downstream builds a translation layer that converts upstream's model into its own, so upstream's model never leaks into downstream's domain | Upstream's model is a poor fit, unstable, or actively harmful to let leak in (a legacy system, an external vendor's schema) |
| **Open Host Service (OHS) + Published Language (PL)** | Upstream deliberately publishes a well-documented, stable protocol/schema for many downstream consumers | Upstream serves many consumers and can't negotiate a bespoke integration with each |
| **Separate Ways** | No integration at all; duplicate the small amount of overlapping logic rather than coupling two contexts for a marginal shared feature | The integration cost exceeds the benefit of not duplicating a small amount of logic |

**The ACL is the pattern most worth internalizing**, because it's the direct answer to "how do I depend on a system I don't trust the model of without importing its mess": every field of the upstream response is mapped explicitly into your domain's vocabulary at the boundary, so a change or a wart in the upstream schema is absorbed in one translation function instead of rippling through your codebase.

### Aggregates

An aggregate is a cluster of entities and value objects treated as one unit for the purpose of consistency, with a single **aggregate root** as the only entry point external code may hold a reference to.

**One-aggregate-per-transaction, and why.** The rule of thumb from Evans and reinforced heavily by Vaughn Vernon's *Effective Aggregate Design* (2011, a three-part paper that is the most cited tactical-DDD source after the original book) is that a single transaction should modify exactly one aggregate instance. The reason is concurrency and scalability: if a transaction touches two aggregates, you need either a distributed transaction (expensive, often unavailable across service boundaries) or a lock spanning both (a scalability bottleneck as concurrent load grows). Keeping aggregates small and transactions single-aggregate means locks are narrow and contention is local.

**Sizing.** The temptation is to make aggregates large (an `Order` that contains its `Customer`, its `Payments`, its `Shipments`) because it feels convenient to load everything at once. The cost is that every transaction against any part of that graph contends for the same lock, and a large aggregate that's loaded and saved as a whole becomes a serialization and memory cost even for a change to one field. Vernon's guidance: model true invariants, the rules that must be enforced *atomically*, inside the aggregate boundary, and reference everything else by id. `Order` needs its `LineItems` inside the boundary because "total can't exceed the customer's credit limit" might be an invariant enforced at add-line-item time; `Order` does not need `Customer` inside it, a `customerId` reference is enough, because nothing about adding a line item needs to atomically change the customer record.

**Referencing by id.** Cross-aggregate references are always by identity (`customerId`, not a live `Customer` object reference), because holding a live reference either means loading the whole graph (defeating the purpose of separate aggregates) or means the aggregate boundary isn't actually a consistency boundary at all. Cross-aggregate consistency (when `Order.total` needs to reflect something about `Customer`) is achieved eventually, via domain events, not atomically.

### Entities, value objects, domain events, repositories

- **Entity**: has identity that persists across state changes; two entities with identical field values but different ids are different things (`Order#123` and `Order#124` with the same line items are still two different orders).
- **Value object**: has no identity, compared by value; `Money(10, "USD")` equals another `Money(10, "USD")` regardless of which instance. Value objects should be immutable, so passing one around never risks a caller mutating shared state unexpectedly.
- **Domain event**: something that happened in the domain that other parts of the system (possibly other bounded contexts) care about, named in the past tense in the ubiquitous language (`OrderCancelled`, not `CancelOrderEvent`), and the mechanism by which aggregates stay eventually consistent with each other without a shared transaction.
- **Repository**: an abstraction that makes an aggregate look like an in-memory collection (`repo.find(id)`, `repo.save(aggregate)`), hiding persistence details from the domain, one repository per aggregate root — never a repository for an internal entity, since internal entities aren't independently addressable.

### Event storming mechanics

A facilitated workshop (Alberto Brandolini) that surfaces the domain model and its boundaries by having domain experts and engineers collaboratively populate a wall (physical or digital) with colored sticky notes, in a specific sequence:

1. **Orange stickies — domain events**, past tense, brainstormed first and roughly chronologically (`OrderPlaced`, `PaymentAuthorized`, `InventoryReserved`).
2. **Blue stickies — commands** that trigger each event (`PlaceOrder` triggers `OrderPlaced`).
3. **Yellow stickies — actors** who issue each command (a customer, a scheduled job, another system).
4. **Pink stickies — external systems** the flow depends on.
5. **Purple stickies — policies/reactions**, "whenever X happens, do Y" rules that connect one event to the next command.
6. Once the timeline is populated, clusters of related events and commands are circled: those clusters are candidate **bounded contexts**, and the sticky-note vocabulary that emerged is the candidate **ubiquitous language**.

The value isn't the diagram, it's that domain experts and engineers build the timeline together in the same room, so disagreements about what a word means surface as a live conversation ("wait, when Support says 'cancelled' do they mean the same thing Sales does?") instead of surfacing eighteen months later as a production bug.

---

## Build it from scratch

A minimal aggregate with an enforced invariant, a domain event, and a repository abstraction:

```python
# untested sketch
from dataclasses import dataclass, field
from datetime import datetime

@dataclass(frozen=True)
class Money:  # value object: immutable, compared by value
    amount: int
    currency: str = "USD"
    def __add__(self, other: "Money") -> "Money":
        assert self.currency == other.currency
        return Money(self.amount + other.amount, self.currency)

@dataclass
class LineItem:  # internal entity, not independently reachable
    sku: str
    unit_price: Money
    qty: int

class DomainError(Exception): ...

class Order:  # aggregate root
    def __init__(self, order_id: str, credit_limit: Money):
        self.id = order_id
        self._credit_limit = credit_limit
        self._items: list[LineItem] = []
        self.status = "open"
        self.events: list[dict] = []   # collected, published after the transaction commits

    def add_line_item(self, sku: str, unit_price: Money, qty: int) -> None:
        if self.status != "open":
            raise DomainError("cannot modify a non-open order")
        new_total = self._total() + Money(unit_price.amount * qty)
        if new_total.amount > self._credit_limit.amount:   # the invariant this aggregate exists to enforce
            raise DomainError("would exceed credit limit")
        self._items.append(LineItem(sku, unit_price, qty))

    def cancel(self) -> None:
        if self.status == "shipped":
            raise DomainError("cannot cancel a shipped order")
        self.status = "cancelled"
        self.events.append({"type": "OrderCancelled", "order_id": self.id, "at": datetime.utcnow()})

    def _total(self) -> Money:
        total = Money(0)
        for item in self._items:
            total = total + Money(item.unit_price.amount * item.qty)
        return total

class OrderRepository:  # makes the aggregate look like an in-memory collection
    def __init__(self):
        self._store: dict[str, Order] = {}
    def find(self, order_id: str) -> Order:
        return self._store[order_id]
    def save(self, order: Order) -> None:
        self._store[order.id] = order
        # in production: also drain order.events through a transactional outbox, same TX as the save
```

No dedicated lab folder exists for this module yet; the invariant-enforcement pattern here extends directly from `T21-solid`'s encapsulation examples, and the event-publishing line is the same outbox mechanism as `T21-outbox-saga-cqrs`.

---

## How it's done in production

| Concern | Tool / approach | What it adds |
|---|---|---|
| Facilitating strategic discovery | Event storming workshops (physical stickies or Miro/Mural for remote), Context Mapper (CML, a DSL for context maps) | A structured, repeatable technique instead of one architect's whiteboard guess |
| Enforcing aggregate boundaries in code | One repository per aggregate root, package-private/internal visibility on non-root entities | Prevents accidental direct references to internal entities from outside the aggregate |
| Cross-aggregate consistency | Domain events published via a transactional outbox (see `T21-outbox-saga-cqrs`), consumed by sagas or projectors | Keeps the one-aggregate-per-transaction rule intact while still achieving system-wide consistency, just eventually |
| Context map as a living artifact | Context Mapper's CML files checked into the repo, or a maintained diagram reviewed at architecture reviews | Prevents the map from being a one-time workshop output that goes stale within a quarter |
| ACL implementation | A dedicated adapter module per external/legacy dependency, translating at the boundary | Contains the blast radius of an upstream schema change or a legacy system's quirks to one file |

### What breaks at scale

| Symptom | Cause | Fix |
|---|---|---|
| "Customer" means something subtly different in two services and a report is silently wrong | No bounded-context exercise was ever done; one shared model forced across contexts that need different ones | Run event storming across both contexts, name the actual boundary, add an ACL or context map at the seam |
| A transaction spans two aggregates and deadlocks under load | Aggregate boundaries drawn for convenience, not around real invariants; violates one-aggregate-per-transaction | Redesign so only true atomic invariants live inside one aggregate; move everything else to eventual consistency via events |
| Every change to `Order` requires touching `Customer` and `Payment` in the same PR | Aggregates too large, or a live object reference held across aggregate boundaries instead of an id | Reference other aggregates by id only; shrink the aggregate to just its true invariants |
| A repository exists for an internal entity (`LineItemRepository`) | Misapplied tactical pattern; internal entities aren't independently addressable | Remove it; access line items only through the `Order` aggregate root |
| Domain code reads like a translation of a legacy system's field names | No anticorruption layer; upstream's model leaked directly into the downstream domain | Add an ACL that maps upstream's model into your ubiquitous language at the boundary, once |
| Event storming produced a nice wall of stickies that nobody has looked at since | Treated as a one-time deliverable instead of a living artifact | Keep the context map in the repo (Context Mapper CML or a maintained diagram) and revisit at real architecture decision points |

---

## Tradeoffs & when NOT to use it

- **DDD is overkill for a domain with little real complexity.** A CRUD app with straightforward, uncontested vocabulary (an internal tool that manages one list of one kind of thing) gains nothing from bounded-context workshops or aggregate design; the entire value proposition of DDD is managing complexity that's actually there, and applying it where the complexity isn't produces ceremony (repositories, value objects, aggregate roots) around what is still, underneath, a straightforward CRUD model.
- **Skipping strategic design and doing tactical-only is the most common misuse**, and it's worse than not doing DDD at all in one specific way: it creates the appearance of rigor (an `Order` aggregate, a `Repository`, a `DomainEvent`) without the substance (the boundaries were never actually examined), which can be more misleading than an honestly unstructured CRUD app, because nobody questions "is this Order aggregate actually right" once it has the trappings of a DDD design.
- **One-aggregate-per-transaction is a real constraint on what a single API call can atomically guarantee.** If a business requirement genuinely needs two aggregates updated atomically together, that's a signal either the aggregate boundary is drawn wrong (they should be one aggregate) or the requirement itself needs to be renegotiated to eventual consistency (a saga), not solved by reaching for a distributed transaction.
- **Context mapping patterns like Shared Kernel require sustained coordination overhead** between the teams sharing the kernel; it's the right choice for a small number of tightly collaborating teams and the wrong choice once more than two or three teams would need to coordinate every change to the shared subset.
- **Event storming's value depends entirely on getting real domain experts in the room.** A workshop run only by engineers, guessing at what the business side would say, produces a diagram with the same blind spots the engineers already had, just with sticky notes.

---

## Interview questions

### Q1 — What's the difference between strategic and tactical DDD, and why do teams usually get the order backwards?
**Testing:** whether you understand DDD as more than a pattern catalogue.
**Answer:** Strategic design decides where the domain's real boundaries are (bounded contexts) and how they relate (context mapping); tactical design is the toolbox (entities, value objects, aggregates) for expressing a model inside one boundary. Teams do tactical first because it's concrete and learnable from a blog post, while strategic design requires a workshop with domain experts and produces a diagram, not code, with a payoff that's invisible until the disaster it prevented would have happened.
**Follow-up trap:** *"Is it bad to just use tactical patterns without doing the strategic work?"* — it's arguably worse than not doing DDD, because it creates the appearance of rigor without the substance: nobody questions whether the aggregate boundary is right once it has a `Repository` and looks properly "DDD."

### Q2 — Define a bounded context and give a concrete symptom that one is missing.
**Answer:** A boundary within which a model and its ubiquitous language are internally consistent, so a word doesn't need qualification inside it. The symptom of a missing boundary: the same word means different things in two different meetings and nobody has noticed, because nobody has ever put both meanings in the same sentence, until a report or a bug surfaces the gap.
**Follow-up trap:** *"How do you find bounded context boundaries in an existing, unstructured codebase?"* — look for places where the same table or class is accessed by very different parts of the business with contradictory assumptions about what its fields mean; those contradictions mark the seam. Event storming with domain experts from both sides is the structured way to surface it.

### Q3 — What is an aggregate, and what is the aggregate root's job?
**Answer:** A cluster of entities and value objects treated as one unit for consistency, with a designated root entity as the only object external code may hold a reference to. The root enforces the aggregate's invariants on every modification and is the unit a repository loads and saves as a whole.
**Follow-up trap:** *"Can you have a reference directly to an internal entity from outside the aggregate?"* — no, that breaks encapsulation of the consistency boundary; if you need to address an internal entity from outside, that's a signal it should be its own aggregate, or the aggregate needs to expose an operation on the root instead.

### Q4 — Explain one-aggregate-per-transaction and why it's the rule.
**Answer:** A single transaction should modify exactly one aggregate instance, because a transaction spanning two aggregates needs either a distributed transaction or a lock across both, either expensive or unavailable across service boundaries, and either way a scalability bottleneck under concurrent load. Keeping transactions single-aggregate keeps locks narrow.
**Follow-up trap:** *"A business rule genuinely needs two aggregates updated together atomically. What now?"* — that's a signal to re-examine whether they should actually be one aggregate, or to renegotiate the requirement to eventual consistency via a domain event and a saga rather than reaching for a distributed transaction.

### Q5 — How do you decide how big to make an aggregate?
**Answer:** Model only the true invariants, rules that must hold atomically, inside the boundary; reference everything else by id. `Order` includes `LineItems` if "total can't exceed credit limit" must be enforced atomically on every add, but doesn't include `Customer`, a `customerId` reference is enough since nothing about adding a line item needs to atomically change the customer.
**Follow-up trap:** *"What's the failure mode of making aggregates too large?"* — every transaction against any part of the graph contends for the same lock, and loading/saving the whole aggregate becomes a cost even for a one-field change; concurrency and performance both degrade as the aggregate grows.

### Q6 — Entity vs value object. Give an example of getting this wrong.
**Answer:** An entity has identity that persists across state changes; a value object has no identity and is compared by value, and should be immutable. Getting it wrong: modeling an `Address` as an entity with its own id and mutable fields when two orders shipping to the same address should just compare equal by value; this adds needless identity-tracking and repository machinery to something that's really just a value.
**Follow-up trap:** *"Why does immutability matter for value objects specifically?"* — because a value object is often shared or passed around by multiple entities; if it's mutable, one holder mutating it silently changes what every other holder sees, which is exactly the kind of bug that only shows up under concurrent access.

### Q7 — What's an anticorruption layer, and when do you build one versus just conforming to upstream's model?
**Answer:** An ACL is a translation layer at a context boundary that maps an upstream system's model into your own domain's vocabulary, so upstream's schema, quirks, or instability never leak into your domain code directly. Build one when upstream's model is a poor fit, unstable, or you don't control it (a legacy system, a third-party API); conform (accept upstream's model as-is with no translation) when upstream has no incentive to accommodate you and the mismatch is small enough that a translation layer isn't worth the maintenance cost.
**Follow-up trap:** *"What's the actual failure this pattern prevents, concretely?"* — a wart or breaking change in the upstream schema rippling through your codebase because every internal function used the upstream's field names and types directly; with an ACL, the fix is one translation function, not a search-and-replace across the domain.

### Q8 — Walk me through the six sticky-note categories in an event storming session and what they produce.
**Answer:** Orange domain events (past tense, brainstormed roughly chronologically), blue commands that trigger each event, yellow actors who issue commands, pink external systems, purple policies connecting one event to the next command; clustering related events/commands afterward surfaces candidate bounded contexts and the ubiquitous language that emerged live in the room.
**Follow-up trap:** *"What makes an event storming session fail to produce anything useful?"* — running it with only engineers and no real domain experts; the resulting timeline just encodes the engineers' existing (possibly wrong) mental model with sticky notes attached, and disagreements that only a domain expert would catch never surface.

### Q9 — Context mapping: explain Customer/Supplier versus Conformist and when each applies.
**Answer:** Both are upstream/downstream relationships. In Customer/Supplier, the downstream team's needs are a first-class input to the upstream team's planning, appropriate when both teams are in the same org with a real prioritization relationship. In Conformist, downstream just accepts upstream's model with no negotiation and no translation layer, appropriate when upstream has no incentive to accommodate you (a third-party API, a much larger internal team) and building an ACL isn't worth the cost.
**Follow-up trap:** *"What breaks if you pick Conformist when you should have picked ACL?"* — upstream's model, including its instability and its mismatched vocabulary, leaks directly into your domain code, so every future upstream change ripples through your codebase instead of being absorbed at one boundary.

### Q10 — When is DDD overkill?
**Answer:** When the domain has little real complexity, an internal tool managing one straightforward list of one kind of thing, where the entire vocabulary is uncontested and there's no meaningful boundary to find. The value proposition of DDD is managing complexity that's actually present; applying its ceremony (repositories, value objects, aggregate roots) to a simple CRUD domain adds indirection with nothing to show for it.
**Follow-up trap:** *"How do you tell the difference between 'this looks simple but has hidden complexity' and 'this is actually simple'?"* — try to name a real invariant that must be atomically enforced, or a place where the same word means two different things to two stakeholders. If you can't name either after actually asking, it's probably simple.

### Q11 — How do domain events keep two aggregates consistent without violating one-aggregate-per-transaction?
**Answer:** Aggregate A's transaction commits and, in the same transaction (via an outbox), records that something happened. A consumer of that event, possibly updating Aggregate B, runs in a separate transaction, achieving eventual rather than atomic consistency. This is exactly the CQRS/saga machinery, applied at the tactical-DDD level: the aggregate boundary stays a strict transactional boundary, and cross-aggregate effects are handled as a second, independent step.
**Follow-up trap:** *"What if B's update needs to see A's change immediately, with no lag?"* — that's evidence A and B should be the same aggregate, or that the requirement needs to be renegotiated; eventual consistency is a real, visible tradeoff, not a detail to paper over with a shorter poll interval.

### Q12 — You inherit a codebase with a `Customer` aggregate referenced directly (via live object, not id) from `Order`, `Invoice`, and `SupportTicket` aggregates. Diagnose the risk.
**Testing:** synthesis, spotting a violation in a realistic shape.
**Answer:** Holding live references across aggregate boundaries means loading `Order` can transitively load all of `Customer`'s graph, defeating the purpose of separate aggregates, and any transaction that touches `Order` and also happens to mutate the loaded `Customer` object violates one-aggregate-per-transaction without anyone intending it, since nothing in the code structure prevents it. Fix: replace live references with `customerId`, and any place currently mutating `Customer` through an `Order`'s reference needs to instead go through `Customer`'s own repository in its own transaction.
**Follow-up trap:** *"How would you find every place this is happening without a full audit?"* — search for the type of `Customer` used as a field type on other aggregate roots rather than a plain id type; a static analysis rule (or fitness function, see `T21-architecture-styles`) can enforce "no aggregate root holds a live reference to another aggregate root" going forward.

---

## Red flags that fail you

- Describing DDD purely in terms of tactical patterns (entities, repositories) with no mention of bounded contexts.
- Claiming "one aggregate per database table" as the sizing rule instead of "one aggregate per true invariant."
- Not knowing that a value object should be immutable.
- Recommending a distributed transaction to keep two aggregates consistent instead of reconsidering the boundary or accepting eventual consistency.
- Treating context mapping patterns as purely technical, ignoring the organizational relationship they encode.
- Running (or endorsing) event storming with no domain experts present.
- Applying full DDD ceremony to a genuinely simple CRUD domain and calling it best practice.

---

## Cheat card

```
DDD (Evans, 2003)     strategic (find the boundaries) + tactical (express the model inside one)
                       most teams do tactical first — backwards, produces fake rigor

BOUNDED CONTEXT        boundary where a model + ubiquitous language is internally consistent
                        symptom of a missing one: same word, 2 meanings, nobody's noticed yet

CONTEXT MAPPING         Shared Kernel     — 2 teams share a model subset by agreement
                        Customer/Supplier — downstream's needs are first-class upstream input
                        Conformist        — downstream accepts upstream's model as-is, no ACL
                        Anticorruption Layer (ACL) — downstream translates upstream at the boundary
                        Open Host Service + Published Language — upstream publishes a stable contract
                        Separate Ways     — no integration, duplicate the small overlap instead

AGGREGATE               cluster of entities/VOs = 1 consistency boundary; root = only external ref
                        ONE AGGREGATE PER TRANSACTION (Vernon) — else distributed TX or cross-lock
                        size by TRUE INVARIANTS, not by table; ref other aggregates by ID only

ENTITY vs VALUE OBJECT   entity = identity persists across changes
                         value object = no identity, compared by value, MUST be immutable

DOMAIN EVENT             past tense (OrderCancelled), the mechanism for cross-aggregate
                         eventual consistency — same outbox machinery as T21-outbox-saga-cqrs

REPOSITORY               1 per aggregate ROOT only, makes it look like an in-memory collection

EVENT STORMING (Brandolini)  orange=events(past tense) -> blue=commands -> yellow=actors ->
                              pink=external systems -> purple=policies -> cluster = bounded context

WHEN NOT TO USE DDD      simple domain, uncontested vocabulary, no real invariant to name
```

## Sources

- [Domain-Driven Design Interview Questions — Devinterview-io](https://github.com/Devinterview-io/domain-driven-design-interview-questions) — accessed 2026-08-01
- [Domain-Driven Design: A Complete Guide (2026) — generalistprogrammer.com](https://generalistprogrammer.com/tutorials/domain-driven-design-complete-guide) — accessed 2026-08-01
- [Anticorruption Layer — Context Mapper docs](https://contextmapper.org/docs/anticorruption-layer/) — accessed 2026-08-01
- [Customer/Supplier — Context Mapper docs](https://contextmapper.org/docs/customer-supplier/) — accessed 2026-08-01
- [Shared Kernel — Context Mapper docs](https://contextmapper.org/docs/shared-kernel/) — accessed 2026-08-01
- [Domain-Driven Design in Practice: A Large-Scale Empirical Characterisation of the Open-Source Ecosystem (arXiv 2607.06471)](https://arxiv.org/pdf/2607.06471) — accessed 2026-08-01

## Changelog
- 2026-08-01 — created
