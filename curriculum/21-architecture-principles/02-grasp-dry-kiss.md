# GRASP, DRY/KISS/YAGNI, Demeter, Composition over Inheritance

> **Track:** T21 Architecture & Design Principles · **Time:** 1h · **Prereqs:** T21-solid
> **Updated:** 2026-07-26
> **Module id:** `T21-grasp-dry-kiss` · **Tags:** principles

## The 30-second version

GRASP is the older, less-quoted sibling of SOLID — nine patterns (Creator, Information Expert, Controller, Low Coupling, High Cohesion, Polymorphism, Pure Fabrication, Indirection, Protected Variations) that answer "which object should own this responsibility," where SOLID answers "how should a class already assigned a responsibility be shaped." DRY, KISS, and YAGNI are the three-word heuristics engineers actually say out loud in code review, and the honest version of each has a documented failure mode: DRY applied to accidentally-similar code creates false coupling between things that only look alike today, KISS is regularly used to justify skipping abstraction that would have prevented a real bug, and YAGNI is right about 90% of the time and dead wrong about the shared-kernel work nobody wants to redo under deadline pressure. The Law of Demeter and composition-over-inheritance are the two structural techniques that make all of the above easier to satisfy honestly, by keeping objects from reaching through each other and by replacing brittle "is-a" hierarchies with pluggable "has-a" collaborators. The senior signal is knowing exactly which of these is being violated on purpose and being able to say why that's the right call this time.

## Why this gets asked

Because GRASP and DRY/KISS/YAGNI are the vocabulary of day-to-day code review, not the vocabulary of a whiteboard interview — the interviewer wants to know if you'll be a good reviewer, not just a good designer. They've sat in a PR thread where someone said "this violates DRY" about two functions that happen to both compute a discount today and will diverge completely in three months, and watched the team spend a sprint un-coupling logic that should never have been merged. They've also sat in the opposite thread, where "KISS, ship it" got used to justify skipping a validation layer that let bad data into production. The question is really: do you have a felt sense for when a heuristic is protecting the team and when it's being invoked as a slogan to shut down a legitimate concern.

## Lineage: past → present → future

**What came before.** Structured programming (Dijkstra, 1968) and functional decomposition gave engineers a way to break programs into procedures, but object orientation in the 1980s-90s needed new guidance for a different question: not "how do I break this into steps" but "which *object* should be responsible for which behavior." Early OO projects, without that guidance, tended to either centralize everything into a few "God" controller classes or scatter behavior with no coherent ownership. Craig Larman's *Applying UML and Patterns* (1997) formalized GRASP as a direct answer, distilled from earlier informal practice and from the design-pattern literature the GoF book had just popularized. DRY comes from a different lineage entirely — Andy Hunt and Dave Thomas's *The Pragmatic Programmer* (1999) coined it explicitly as "every piece of knowledge must have a single, unambiguous, authoritative representation," a much narrower claim than the "don't write the same code twice" folklore version it became. YAGNI came out of Extreme Programming (Kent Beck, late 1990s) as a direct reaction against Big Design Up Front and speculative frameworks built for requirements that never arrived — the pain was months spent generalizing for a future that didn't materialize while the actual, present requirement shipped late.

**Where it stands now.** GRASP is taught but rarely name-checked directly in production conversation — "information expert" and "controller" show up as *practice* (put the logic where the data is; keep the entry point thin) without anyone saying "GRASP" out loud, which is itself informative: successful principles get absorbed into unnamed habit. DRY is the most actively contested of the three today. The mainstream 2020s position, propagated hard by Dan Abramov's "The WET Codebase" (2022) and the wider "duplication is far cheaper than the wrong abstraction" school (Sandi Metz), is that DRY's *original, narrow* meaning (single source of truth for one piece of *knowledge*) is correct and durable, while the folklore meaning (never write similar-looking code twice) is actively harmful and has caused real, well-documented damage in the form of premature, over-general shared modules. YAGNI has less controversy in principle but a live disagreement in practice around *cross-team* shared infrastructure — teams under YAGNI discipline routinely skip building a shared kernel or event schema registry "until we need it," and then need it under three simultaneous deadlines, at which point the field agrees the early investment would have been cheaper, but nobody can identify that moment reliably in advance.

**Where it's heading.** Confidence is high that "duplicate until a third occurrence forces the abstraction" (the informal Rule of Three, attributed loosely to the XP community) continues to gain ground over reflexive DRY, especially as LLM-assisted refactoring makes de-duplicating *later* cheaper than it used to be — if an AI coding agent can safely extract a shared abstraction once three call sites exist and their actual shared shape is visible, the cost of waiting drops further, strengthening the case for YAGNI-flavored patience. More speculatively: as AI-assisted code generation makes writing *new* code cheaper relative to reading and maintaining *existing* abstractions, some practitioners argue the balance should tilt further toward simple, locally-duplicated code that's cheap to regenerate over shared abstractions that are expensive to keep everyone's mental model of current. Treat this as an emerging argument, not consensus.

---

## Mental model

Think of the whole cluster as three different questions asked at three different points in a design:

```
 "WHO should own this responsibility?"          → GRASP
        │
        ▼
 "Is this the ONE place this fact lives?"        → DRY (narrow sense)
        │
        ▼
 "Is this the simplest thing that could work
  for what we ACTUALLY need right now?"          → KISS + YAGNI
        │
        ▼
 "Does this object reach through others
  it shouldn't know about?"                       → Law of Demeter
        │
        ▼
 "Am I modeling variation as inheritance
  when it should be a pluggable collaborator?"    → Composition over Inheritance
```

They compose: GRASP tells you where a responsibility lives, Demeter checks that the resulting object graph doesn't leak internals, composition checks you didn't reach for the wrong tool (subclassing) to add variation, and DRY/KISS/YAGNI are the three brakes that stop all of the above from turning into premature architecture.

---

## How it actually works

### GRASP — nine patterns, condensed to what actually gets used

| Pattern | Question it answers | One-line application |
|---|---|---|
| **Information Expert** | Who should own this behavior? | The class that already holds the data needed to do it — an `Order` computing its own total, not an external `OrderCalculator` reaching in for line items. |
| **Creator** | Who should instantiate X? | The class that contains, aggregates, records, or closely uses X — an `Order` creates its own `LineItem`s, not a distant factory that has to be told the order's internals. |
| **Controller** | What receives a system-boundary event? | A thin coordinating object (a use-case handler, not the UI or the domain object) that delegates immediately rather than doing the work itself. |
| **Low Coupling** | How do I limit dependency fan-out? | Depend on interfaces, not concrete neighbors; the fewer classes a change ripples through, the cheaper the change. |
| **High Cohesion** | Does this class have a focused, related set of responsibilities? | If you can't summarize a class's job in one sentence without "and," it's not cohesive. |
| **Polymorphism** | How do I handle type-based variation? | Dispatch through an overridden method or interface implementation instead of a type-check `if/elif` chain (this is GRASP's version of OCP). |
| **Pure Fabrication** | What if no *domain* class naturally owns this? | Invent a class that doesn't correspond to a real-world concept purely for cohesion/coupling reasons — a `PricingEngine` that isn't "a thing" in the business domain but keeps pricing logic out of `Order`. |
| **Indirection** | How do I decouple two things that shouldn't know about each other? | Insert a mediating object — a repository between domain logic and the database, a message broker between producer and consumer. |
| **Protected Variations** | How do I insulate against a known point of instability? | Wrap the unstable thing (an external API, an unstable schema) behind a stable interface — this is GRASP's OCP/DIP equivalent, applied specifically at points you *know* will change. |

Most of these are absorbed into habit under different names: "put logic where the data is" (Information Expert) is just good OO instinct; "keep the controller thin" is standard in every MVC framework; "Pure Fabrication" is why `*Service` and `*Engine` classes exist even though "the pricing engine" isn't a thing your business stakeholders would draw.

### DRY — the narrow meaning vs. the folklore meaning

**Narrow (correct) meaning:** every piece of *knowledge* — a business rule, a fact, a policy — should have one authoritative representation in the system. If your tax rate calculation exists in two places and one gets updated without the other, that's the failure DRY prevents.

**Folklore (dangerous) meaning:** any two blocks of code that look similar should be merged into one function/class.

**Where the folklore meaning actively harms:**

```python
# Two validation functions that look identical today:
def validate_signup_email(email: str) -> bool:
    return "@" in email and len(email) < 255

def validate_invite_email(email: str) -> bool:
    return "@" in email and len(email) < 255

# "DRY this up," someone says. Six months later, signup needs
# disposable-email blocking and invite doesn't (invites are
# pre-vetted by an admin). Now there's one shared function with
# a boolean flag, an if-branch, and two call sites that both have
# to know which flag to pass — the abstraction actively made the
# divergence harder to express than just having two functions.
```

This is **coincidental duplication** (Sandi Metz's term): code that is identical today because it happens to solve two unrelated problems the same way right now, not because it represents the same underlying business knowledge. Merging it creates **false coupling** — two call sites that had no real relationship now share one function and must renegotiate every time either one's true requirement changes. The Rule of Three (attributed loosely to the XP/Pragmatic Programmer community) is the practical antidote: tolerate duplication through the second occurrence; only extract on the third, once you can see the actual shared shape rather than guessing at it from two data points.

### KISS — where "simple" is honestly used to mean "underbuilt"

KISS says prefer the simplest design that satisfies the actual requirement. The failure mode is using KISS to justify skipping a piece of structure that isn't there for elegance, it's there for correctness:

```python
# "KISS" — skips validation because it's "simpler":
def apply_discount(order: Order, pct: float) -> None:
    order.total *= (1 - pct)

# Called with pct=1.5 from a bug upstream: order.total goes negative.
# The "complexity" the KISS argument skipped was one bounds check,
# not an abstraction — that's not simplicity, that's a missing guard.
```

The honest distinction: KISS argues against unnecessary *structural* complexity (extra layers, extra abstraction, extra generality) — not against necessary *correctness* work (validation, error handling, edge cases). "Simple" means fewer moving parts for the same guarantees, not fewer guarantees.

### YAGNI — right most of the time, wrong at the shared-kernel boundary

YAGNI: don't build a capability until a current, real requirement needs it. This is correct and load-bearing against speculative generality (see the OCP counter-argument in the SOLID module — it's the same failure mode). The genuine counter-case is **shared infrastructure that multiple teams will need but no single team is incentivized to build early**: an event schema registry, a shared authentication library, an idempotency-key convention. Every individual team correctly applies YAGNI to their own backlog ("we don't need a schema registry for our two events"), and the aggregate effect is that the shared thing never gets built until three teams simultaneously need it during an incident, at which point it's built under worse conditions than if one team had absorbed the YAGNI-violating cost eighteen months earlier. This is a coordination failure, not a flaw in YAGNI's logic at the individual-team level — which is exactly why it's a good staff-level answer: YAGNI is locally correct and can still be globally wrong.

### Law of Demeter — "don't talk to strangers"

A method of object `A` should only call methods on: `A` itself, objects passed as parameters, objects `A` creates, or `A`'s direct components. Not on objects returned by those calls.

**Violation:**

```python
# reaching through three objects to get one fact
if order.customer.billing_address.country.tax_treaty_exempt:
    ...
```

This couples the calling code to `Order`'s internal structure, `Customer`'s internal structure, and `Address`'s internal structure simultaneously. If `billing_address` moves to a separate `BillingProfile` object in a future refactor, every caller doing this chain breaks.

**Fix — ask, don't reach:**

```python
if order.is_tax_treaty_exempt():
    ...
# Order delegates internally:
class Order:
    def is_tax_treaty_exempt(self) -> bool:
        return self.customer.is_tax_treaty_exempt()
class Customer:
    def is_tax_treaty_exempt(self) -> bool:
        return self.billing_address.country.tax_treaty_exempt
```

Each object only reaches one level deep. A refactor to `Customer`'s internals only touches `Customer`.

**Honest counter-argument:** taken literally, Demeter produces "wrapper explosion" — every object gets a forwarding method for every fact any caller might ever want, and you end up with `Order.get_customer_billing_country_tax_treaty_status()`-style methods that are really just accessors in a trench coat, adding indirection without adding real encapsulation. The judgment call: apply Demeter where the chain crosses a genuine ownership/module boundary (this is exactly why it matters more at a bounded-context boundary than inside one aggregate); inside a single, cohesive aggregate that changes as a unit, a getter chain of one or two hops is often just noise-free reading, and forcing delegation methods for every internal traversal adds ceremony without adding real insulation, because the whole aggregate already changes together.

### Composition over inheritance

**Violation — the classic fragile hierarchy:**

```python
class Bird:
    def fly(self): ...

class Penguin(Bird):
    def fly(self):
        raise NotImplementedError("penguins can't fly")  # LSP violation, again
```

Inheritance here encodes "is-a" for taxonomy, not for behavior, and behavior is what callers actually depend on.

**Fix — compose behavior as pluggable strategies:**

```python
class FlightBehavior(Protocol):
    def fly(self) -> None: ...

class CanFly:
    def fly(self) -> None: print("flying")

class CannotFly:
    def fly(self) -> None: print("walking")

class Bird:
    def __init__(self, flight: FlightBehavior):
        self.flight = flight
    def fly(self) -> None:
        self.flight.fly()

penguin = Bird(CannotFly())
eagle = Bird(CanFly())
```

This is the classic Head First Design Patterns "Strategy over inheritance" example, and it's the same underlying fix as OCP's strategy pattern and LSP's "don't model it as a subtype" fix — three principles converging on one technique. **The rule of thumb:** prefer inheritance only for genuine "is-a, and every subtype can be used everywhere the supertype is used" relationships (rare in practice — most real hierarchies are 2 levels deep at most before they should switch to composition); prefer composition for "has-a" and "behaves-like" relationships, which is most of what production code actually needs. Multiple inheritance and deep hierarchies (3+ levels) are a code smell in almost every mainstream language; Go and Rust structurally forbid classical inheritance entirely and lean on composition (embedding, traits) by design, which is itself evidence of where the industry consensus has landed.

---

## Build it from scratch

The practical exercise: take a 20-30 line snippet with (a) a Law of Demeter violation, (b) two coincidentally-similar functions, and (c) a subclass that overrides a method to throw — and fix all three live, narrating which fix is GRASP (where does this responsibility belong), which is DRY-correctly-applied (is this actually one piece of knowledge?), and which is composition-over-inheritance. The failure mode interviewers watch for: fixing (b) by merging the two functions anyway, out of reflex, without first asking whether they represent the same *knowledge* or just currently look alike.

---

## How it's done in production

**Where these show up as tooling rather than discipline:**

| Concern | Tooling that encodes it |
|---|---|
| Demeter violations | Linters flag chained attribute access depth (`.`-chain length) in some codebases; more commonly caught in code review, not tooling |
| DRY (narrow sense) | Single source of truth enforced by schema registries (Avro/Protobuf schema registry for event contracts), shared constants modules, feature flags — not by merging every similar function |
| Coincidental duplication avoidance | `jscpd`/`flake8-copy-paste`-style duplicate-code detectors flag candidates for review, but a human still has to judge knowledge-vs-coincidence; tools cannot make that call |
| YAGNI at the org level | RFC/design-doc processes that force an explicit "who else needs this" check before building shared infra, specifically to catch the shared-kernel undercount problem |
| Composition over inheritance | Go and Rust enforce this at the language level (no classical inheritance); Java/Python require discipline, and `@dataclass` / records nudge toward composition by making small value objects cheap to create |

**Failure-mode table:**

| Symptom | Cause | Fix |
|---|---|---|
| A shared "generic" function has 4+ boolean flags controlling its behavior | Coincidental duplication was DRY'd prematurely; divergent knowledge got forced into one function | Split back into separate functions per actual use case; re-merge later only if a *third* occurrence proves the shape is genuinely shared |
| A bug slipped through because "we kept it simple" | KISS used to justify skipping a correctness guard, not skipping structural complexity | Restore the validation/edge-case handling; KISS never licensed removing guarantees |
| Three teams each build their own version of the same cross-cutting capability under deadline pressure | YAGNI applied correctly at each team's level, but no one owned the aggregate need | Stand up a shared-infra RFC process that explicitly checks for this before three teams hit it simultaneously |
| A one-line change to an `Address` class breaks unrelated call sites three files away | Law of Demeter violated; callers reached through `Order.customer.address` | Add a delegating method at the boundary that actually owns the concept (`Order.billing_country()`) |
| A subtype throws `NotImplementedError` on an inherited method | Composition-over-inheritance ignored; behavior modeled as "is-a" when it's really "has-a" | Extract the varying behavior into a strategy object, inject it instead of subclassing |
| Every class has 10+ one-line delegate methods forwarding to internals | Law of Demeter applied too literally inside a single cohesive aggregate | Allow direct traversal within one aggregate/module boundary; reserve delegation for cross-boundary access |

---

## Tradeoffs & when NOT to use it

- **Don't DRY coincidental duplication.** Two functions that look alike today because they happen to solve unrelated problems the same way are not "the same knowledge." Merging them creates false coupling that costs more than the duplication did. Wait for a third occurrence (Rule of Three) before extracting.
- **Don't invoke KISS to skip correctness work.** Simplicity is about fewer structural layers for the same guarantees, not fewer guarantees. A missing bounds check is not "simpler," it's a latent bug.
- **Don't apply YAGNI at the org level the same way you apply it at the team level.** Individually correct YAGNI decisions across teams can add up to a shared-infrastructure gap that costs more in aggregate than the early investment would have. This needs an explicit cross-team process, not more individual discipline.
- **Don't chase Law of Demeter across a cohesive aggregate boundary.** Inside one aggregate that changes as a unit, forcing a delegation method for every internal traversal adds ceremony with no real insulation benefit. Apply it at genuine ownership/module/bounded-context boundaries.
- **Don't reach for GRASP's Pure Fabrication reflexively.** Inventing a non-domain class for every piece of logic that doesn't obviously belong to an entity can produce the same anemic-domain symptom SRP over-application causes — sometimes the entity really is the right owner, and Pure Fabrication is a tool for the genuine exceptions, not a default.
- **Composition over inheritance has a real cost too**: more objects to construct and wire, more indirection to read through to find the actual behavior. For a true, stable "is-a" taxonomy that will never need runtime-swappable behavior (rare, but it happens — e.g., a fixed set of exception types), a shallow inheritance hierarchy is simpler to read than an injected-strategy version with one implementation.

---

## Interview questions

### Q1 — What's the difference between GRASP and SOLID?
**Testing:** whether you know these aren't the same nine-vs-five list.
**Answer:** GRASP answers "which object should own this responsibility" (Information Expert, Creator, Controller, etc.) — it's about responsibility *assignment*. SOLID answers "given a class already has a responsibility, how should it be shaped and related to others" (single reason to change, substitutability, etc.) — it's about *shape*, once assignment is settled. GRASP is used earlier in design; SOLID is used to critique/refine what GRASP produced.
**Follow-up trap:** *"Give an example where they overlap."* — Polymorphism (GRASP) and OCP (SOLID) both push you toward dispatch-through-interface instead of type-check chains; GRASP frames it as "who handles type-based variation," SOLID frames it as "closed for modification."

### Q2 — What is the actual, narrow definition of DRY, and how does it differ from what most people mean?
**Testing:** the single most commonly misquoted principle in this cluster.
**Answer:** DRY, per the Pragmatic Programmer's original wording, means every piece of *knowledge* (a business rule, a fact) should have one authoritative representation. Most people use it to mean "don't write two blocks of code that look alike," which is a much broader and more dangerous claim — it doesn't distinguish knowledge duplication from coincidental duplication.
**Follow-up trap:** *"Give an example of DRY correctly applied vs. incorrectly applied."* — Correct: one `TAX_RATE_BY_REGION` table instead of the same rate hardcoded in three files. Incorrect: merging `validate_signup_email` and `validate_invite_email` because they're identical today, when they represent two unrelated policies that happen to coincide.

### Q3 — What is coincidental duplication and why does merging it hurt?
**Testing:** Sandi Metz's framing, a strong senior signal if named correctly.
**Answer:** Code that's identical right now because two unrelated requirements happen to be satisfied the same way today, not because they represent the same underlying knowledge. Merging it creates false coupling — the two call sites now share one function and must renegotiate every time either one's *true*, independent requirement changes, usually via added boolean flags and branches that make the shared function harder to read than the two originals combined.
**Follow-up trap:** *"How do you tell coincidental duplication from real duplication in the moment?"* — you often can't, with only two data points. The Rule of Three: tolerate duplication through the second occurrence; extract on the third, once the actual shared shape (not just the current code) is visible.

### Q4 — Where does YAGNI fail as an organizational strategy even though it's correct for an individual team?
**Testing:** the honest counter-argument, staff-level framing.
**Answer:** Shared cross-team infrastructure — an event schema registry, an idempotency-key convention, a shared auth library. Every team correctly applies YAGNI to their own immediate backlog and skips building it. The aggregate effect is nobody builds it until three teams need it simultaneously during an incident, at which point it costs more than if one team had absorbed the "unnecessary" cost eighteen months earlier. It's a coordination failure, not a flaw in YAGNI's logic per team.
**Follow-up trap:** *"So should teams stop applying YAGNI?"* — no, the fix is an explicit cross-team process (an RFC or architecture-review step that asks "who else needs this") that catches the aggregate gap, not abandoning YAGNI at the individual level, which would just reintroduce speculative generality everywhere.

### Q5 — Explain the Law of Demeter and show a violation.
**Testing:** baseline recognition plus a concrete example.
**Answer:** A method should only invoke methods on itself, its parameters, objects it creates, or its direct components — not on objects returned by those calls ("don't talk to strangers"). Violation: `order.customer.billing_address.country.tax_treaty_exempt` reaches through three objects' internals, coupling the caller to all of their structures simultaneously.
**Follow-up trap:** *"Fix it and explain why the fix is better."* — delegate: `order.is_tax_treaty_exempt()`, with `Order` asking `Customer`, which asks `Address`. Each hop is one level deep; a refactor of `Address`'s internals only touches `Customer`, not every caller in the codebase.

### Q6 — When does the Law of Demeter become counterproductive?
**Testing:** the honest counter-argument, whether you'll apply it everywhere reflexively.
**Answer:** Inside a single cohesive aggregate that changes as a unit — forcing a one-hop-only rule there produces "wrapper explosion," where every object grows forwarding methods for every internal fact any caller might want, adding indirection with no real encapsulation benefit, since the whole aggregate changes together anyway. Apply Demeter where the chain crosses a genuine module or bounded-context boundary, not inside one.
**Follow-up trap:** *"How do you decide where that boundary is in an ambiguous case?"* — ask whether the objects on either side of the chain are owned/versioned/deployed independently. If yes, it's a real boundary and Demeter matters; if they're part of one aggregate root's consistency boundary, it's noise.

### Q7 — Why is `Penguin extends Bird` with `fly()` throwing an exception a design smell, and what's the fix?
**Testing:** the connection between LSP and composition-over-inheritance — the same failure, viewed from two principles.
**Answer:** It models "is-a" for taxonomy when callers actually depend on behavior — a caller holding a `Bird` reasonably expects `fly()` to work, and `Penguin` breaks that (an LSP violation). Fix: extract flight as a pluggable `FlightBehavior` strategy injected into `Bird`, so `Penguin` composes a `CannotFly` behavior instead of inheriting and overriding to fail.
**Follow-up trap:** *"When is inheritance still the right call?"* — genuine, stable "is-a" relationships where every subtype is safely substitutable everywhere the supertype is used, and there's no need for runtime-swappable behavior — these are less common in practice than people assume, and most real hierarchies deeper than two levels should be reconsidered as composition.

### Q8 — What's Pure Fabrication and why does it exist if it's not "real" domain modeling?
**Testing:** whether you understand GRASP's answer to "no natural owner."
**Answer:** A class invented purely for cohesion/coupling reasons, with no corresponding real-world business concept — e.g., a `PricingEngine` that isn't "a thing" stakeholders would name, but keeps pricing logic out of `Order` where it would otherwise bloat the entity or force it to depend on things (currency conversion services, tax APIs) it has no business knowing about directly.
**Follow-up trap:** *"Isn't that just creating a Service class, which causes anemic domains?"* — the distinction is what's being extracted: cross-cutting orchestration or infrastructure concerns (Pure Fabrication) versus the entity's own invariant-protecting logic (which should stay on the entity). Extracting the former is fine; extracting the latter is the anemic-domain mistake.

### Q9 — Controller pattern: what's the failure mode of getting it wrong?
**Testing:** whether "thin controller" is understood mechanically, not just as a slogan.
**Answer:** A "fat controller" that does business logic itself instead of delegating to domain/service objects — this couples the entry point (HTTP handler, CLI command, message consumer) to business rules, making the logic untestable without simulating the entry point and unreusable from a second entry point (e.g., a batch job that needs the same logic the API uses).
**Follow-up trap:** *"How thin is too thin?"* — a controller that does nothing but parse input, call one method, and format output is correctly thin; if you find yourself needing 3+ orchestration steps with branching logic inside the controller, that's a sign a use-case/application-service object should own the orchestration instead.

### Q10 — Design review: a teammate proposes a shared `BaseEntity` class with common CRUD methods that every domain entity will inherit. What do you say?
**Testing:** synthesizing composition-over-inheritance with GRASP/DRY judgment in a live scenario.
**Answer:** Ask what's actually shared: if it's truly identical mechanical behavior (an `id`, `created_at`, equality-by-id), a shared base is reasonable and low-risk since it's data, not diverging business behavior. If "CRUD methods" means persistence operations, prefer composition — inject a repository per entity type rather than inheriting save/load behavior, because persistence concerns (this entity's constraints, this entity's validation before save) diverge per entity and a shared base class will accumulate overridden methods that throw or no-op, which is the same LSP smell as the Penguin example.
**Follow-up trap:** *"What if three entities genuinely need identical persistence behavior?"* — that's exactly the third occurrence the Rule of Three asks for; at that point, either a generic repository (`Repository<T>`) via composition, or a shared base for genuinely identical behavior, both work — the point is you now have evidence instead of a guess.

### Q11 — Rank DRY, KISS, and YAGNI by how often you've seen each one invoked incorrectly in a real code review.
**Testing:** whether you have real experience with this or are reciting definitions.
**Answer:** In most codebases, DRY is invoked incorrectly most often — "these look the same, merge them" is a much easier reflex to trigger than "this is genuinely too complex" or "we don't need this yet," and it's the one with the most subtle correct/incorrect boundary (knowledge vs. coincidence). KISS is invoked incorrectly second-most, usually to skip a guard rather than an abstraction. YAGNI is invoked incorrectly least often at the individual level — its failure is structural (org-level undercounting) rather than a reflex misapplication in a single PR.
**Follow-up trap:** *"Why is DRY the easiest to misapply?"* — because similarity is visible immediately (you can see two blocks of code look alike) while shared-knowledge-vs-coincidence requires knowing the business context and the future roadmap, which code review often doesn't surface in the moment.

---

## Red flags that fail you

- Saying "DRY" without being able to state the difference between knowledge duplication and coincidental duplication.
- Justifying a missing validation/guard as "keeping it simple" (KISS).
- Treating YAGNI as always correct with no acknowledgment of the shared-infrastructure coordination failure.
- Not recognizing a `NotImplementedError`-throwing override as the same failure LSP names.
- Applying Law of Demeter uniformly with no distinction between crossing a module boundary and traversing inside one aggregate.
- Confusing GRASP's nine patterns with SOLID's five, or being unable to name what GRASP is for.
- Proposing to merge two similar functions on sight, with no mention of the Rule of Three or checking whether they represent the same requirement.

---

## Cheat card

```
GRASP (9): Information Expert, Creator, Controller, Low Coupling, High Cohesion,
           Polymorphism, Pure Fabrication, Indirection, Protected Variations
           → answers "who owns this responsibility", not "how should it be shaped" (SOLID)

DRY   narrow/correct: one piece of KNOWLEDGE, one representation
      folklore/dangerous: never write similar-looking code twice
      coincidental duplication (Sandi Metz): looks same today, unrelated tomorrow
      Rule of Three: tolerate dupe through 2nd occurrence, extract on 3rd

KISS  simpler = fewer structural layers for the SAME guarantees
      NOT fewer guarantees — a missing bounds check isn't "simple," it's a bug

YAGNI correct per-team; fails at ORG level — shared infra (schema registry,
      idempotency convention) nobody builds until 3 teams need it in an incident
      fix = explicit cross-team RFC process, not abandoning YAGNI

DEMETER  "don't talk to strangers" — only call methods on: self, params,
         objects you create, direct components. NOT on objects THEY return.
         apply at module/bounded-context boundaries; skip inside one aggregate
         (over-applying → wrapper explosion, forwarding methods everywhere)

COMPOSITION > INHERITANCE  prefer "has-a"/"behaves-like" (strategy injection)
         over "is-a" when subtypes need to override-to-reject (LSP smell)
         Go/Rust forbid classical inheritance by design — composition only
         exception: genuine stable taxonomy, no runtime-swappable behavior needed
```

## Sources

- [The WET Codebase — overreacted.io (Dan Abramov)](https://overreacted.io/the-wet-codebase/) — accessed 2026-07-26
- [Demystifying Software Development Principles: DRY, KISS, YAGNI, SOLID, GRASP, and LoD — Level Up Coding](https://levelup.gitconnected.com/demystifying-software-development-principles-dry-kiss-yagni-solid-grasp-and-lod-8606113c0313) — accessed 2026-07-26
- [IEC 61131-3: The Principles KISS, DRY, LoD and YAGNI — Stefan Henneken](https://stefanhenneken.net/2023/12/17/iec-61131-3-the-principles-kiss-dry-lod-and-yagni/) — accessed 2026-07-26
- [Applying UML and Patterns (GRASP) — Craig Larman, summarized in course/reference material] — accessed 2026-07-26
- [Anemic domain model — Wikipedia](https://en.wikipedia.org/wiki/Anemic_Domain_Model) — accessed 2026-07-26

## Changelog
- 2026-07-27 — created
