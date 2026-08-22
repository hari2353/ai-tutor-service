# Anti-Patterns: Distributed Monolith, Dual Writes, Shared Database, God Object, Chatty Services, Anemic Domain Model

> **Track:** T21 Architecture & Design Principles · **Time:** 1.5h · **Prereqs:** `T21-architecture-styles`, `T21-ddd`, `T21-outbox-saga-cqrs` · **Updated:** 2026-08-02
> **Module id:** `T21-anti-patterns` · **Tags:** architecture, critical

## The 30-second version

Six anti-patterns account for most of the architectural pain interviewers have personally lived through: the **distributed monolith** (services deployed separately but coupled so tightly they must ship together — all the latency and failure modes of microservices, none of the independence), **dual writes** (writing to two systems non-atomically, so a crash between them leaves them permanently disagreeing), **shared database** (multiple services reading and writing the same tables, so a schema change becomes a cross-team migration), **god object** (one class or service that knows and does everything, becoming the bottleneck for every change and every incident), **chatty services** (one logical operation fans out into dozens of synchronous inter-service calls, so latency and failure probability compound), and **anemic domain model** (entities reduced to getters/setters with all business logic external, so invariants can be violated from anywhere). Each has one concrete, observable symptom you can name without hand-waving, and each has a specific mechanical fix — not "just be more careful," but a structural change that makes the failure mode impossible rather than merely unlikely.

## Why this gets asked

Because naming the pattern is trivia; recognizing it from a symptom in someone else's system, live, is the actual skill. The interviewer has debugged a 2am page caused by one of these — a service that "owns" an entity but three other services also write to its table, or a deploy that had to touch four repos in lockstep because nobody drew the line between "two services" and "one service in two processes." They're testing whether you reach for the anti-pattern name from a vague description of pain, and whether your fix addresses the structural cause rather than papering over the symptom with more monitoring or more process.

---

## Lineage: past → present → future

**What came before.** These anti-patterns are what happens when the physical topology of a system (how many processes, how many databases, how many deploy pipelines) gets decided before the logical topology (where the actual seams of change and ownership are). The 2010s microservices wave, driven by Netflix's and Amazon's publicized decompositions, created enormous pressure to "do microservices" as a checkbox rather than as a response to an observed organizational or scaling need — Conway's Law (1967) predicted this outcome decades earlier: if your team structure doesn't match your service boundaries, your architecture will either mirror the org chart badly or fight it constantly. The specific pain that named each pattern: distributed monolith was named once teams noticed they'd paid the network-latency and partial-failure tax of microservices while retaining monolith-style synchronized releases; dual writes was named after enough "the cache and the DB disagree and nobody knows why" incidents that Gregor Hohpe's and later Kafka-ecosystem writing (2015-2019) formalized change-data-capture and the outbox pattern as the fix; shared database goes back further, to the "integration database" anti-pattern named in Pat Helland's and Jim Gray's distributed-systems writing in the 1990s-2000s, well before microservices existed; anemic domain model was named by Martin Fowler in 2003, reacting specifically to J2EE-era entity beans that were pure data holders.

**Where it stands now.** Consensus is strong that these are genuine anti-patterns, not merely style preferences — the disagreement is about *diagnosis*, not remediation. The live debate: is a distributed monolith a service-boundary problem (wrong seams) or a database problem (shared schema forcing coordination)? Practitioners increasingly argue the database is the real root cause in most real cases — if each service owned its data exclusively, many "services must deploy together" constraints would dissolve even with imperfect boundaries. The modular monolith movement (a genuine resurgence since roughly 2020, championed by Shopify's public writing about their own Rails monolith and by DHH's "majestic monolith" framing) is a direct reaction: enforce module boundaries with language-level tooling inside one deployable, and only split into physically separate services when you have an actual scaling or team-autonomy reason to pay the distributed-systems tax. What's actually deployed at most companies past a few hundred engineers is a hybrid — a handful of true microservices around genuine bounded contexts with independent scaling needs, and a modular monolith for everything else — which is a more sophisticated answer than either "microservices everywhere" or "monolith forever."

**Where it's heading.** Tooling for *detecting* these patterns automatically is real and improving — static analysis of inter-service call graphs (to flag chatty services and circular dependencies), database-access auditing (to flag cross-service table access before it's discovered in an incident), and dependency-cruiser-style module-boundary linters for monoliths are shipping in CI at a growing number of shops, moving detection from "architecture review meeting" to "failed build." Expect this trend to continue — treating architectural fitness functions (Ford/Parsons/Kua's *Building Evolutionary Architectures*, 2017, still the reference) as CI gates rather than periodic audits. More speculatively, LLM-assisted architecture review (an agent that reads a PR's diff plus the service dependency graph and flags "this introduces a new cross-service table read") is being piloted at a few large engineering orgs as of 2026; treat this as an emerging practice, not yet a standard one.

---

## Mental model

Each anti-pattern is a **coupling that should be explicit and isn't** — the fix is almost always "make the implicit coupling an explicit contract," which either reveals it's fine at a smaller scope, or forces the real conversation about ownership.

```
 SYMPTOM YOU'D SEE                      ANTI-PATTERN            IMPLICIT COUPLING
 ──────────────────                     ─────────────           ──────────────────
 "we can't deploy A without B"    ───▶  distributed monolith ─▶ shared contract/DB,
                                                                  no versioning
 "the cache says X, the DB says Y" ──▶  dual writes         ─▶ two writes, one
                                                                  transaction boundary
 "who broke my table with that
  migration?"                     ───▶  shared database     ─▶ shared schema,
                                                                  no data ownership
 "everyone is scared to touch
  OrderService.java"               ──▶  god object          ─▶ every concern routed
                                                                  through one place
 "checkout makes 40 calls to
  render one page"                 ──▶  chatty services     ─▶ no aggregation layer,
                                                                  no data locality
 "the Order class can't tell you
  if it's valid"                   ──▶  anemic domain model ─▶ logic lives outside
                                                                  the thing it's about
```

---

## How it actually works

### 1. Distributed monolith

**Symptom:** deploys of service A and service B must be coordinated (a specific order, or the same release window) because B assumes A's current API shape, or both read/write the same underlying tables. Rolling back A without rolling back B breaks something. You have the network latency, partial-failure surface, and operational overhead of N services, and the release cadence of one.

**Root causes, usually more than one at once:** (1) a shared database — the most common single cause — where two "independent" services are actually coupled through table structure; (2) synchronous, un-versioned contracts, where a field rename in A's response breaks B with no deprecation window; (3) services split along technical layers (a "data service," a "business-logic service") rather than along business capability, so a single business change touches both.

**Fix:** each service owns its data exclusively — no other service reads or writes its tables directly, only through its API or its published events. Contracts are versioned (see contract-testing, `T19-contract-testing`) with an explicit deprecation window. If after fixing both of these you *still* can't deploy independently, the boundary itself is wrong and the two "services" are one service that should be one deployable — that's not a failure, it's the correct diagnosis. Merging two chattily-coupled services back into a modular monolith is often the actual fix, not more tooling to manage the coupling.

### 2. Dual writes

**Symptom:** two systems that are supposed to agree — a database and a cache, a database and a search index, a database and a message queue — silently disagree after a crash, a timeout, or a partial failure between the two writes. "The order shows as paid in the DB but the confirmation email never went out" is dual writes: the write to the DB and the write to the outbound-email trigger were two separate, non-atomic operations, and the process died (or the network blipped) between them.

```python
# Dual write — classic, broken
def place_order(order):
    db.save(order)                 # write 1 succeeds
    queue.publish("order.placed", order)  # write 2 fails / process dies here
    # order exists in DB, event never published — downstream consumers never know

# Outbox pattern — fix
def place_order(order):
    with db.transaction():
        db.save(order)
        db.save(OutboxEvent("order.placed", order))  # same transaction, same commit
    # separate poller/CDC process reads the outbox table and publishes,
    # retrying until acknowledged — the DB write and the "intent to publish"
    # are now atomic; publishing itself is at-least-once with a durable retry
```

**Fix:** the transactional outbox pattern (write the event to an outbox table in the same transaction as the state change, then a separate relay publishes it, at-least-once, with the outbox row deleted or marked only after ack) or change-data-capture (Debezium reading the DB's write-ahead log directly, so there's only ever one true write and the event stream is derived from it). Both convert two non-atomic writes into one atomic write plus a durable, retryable relay. Covered in depth in `T21-outbox-saga-cqrs`.

### 3. Shared database

**Symptom:** a migration in service A's database breaks service B, and nobody on B's team knew A's table existed, let alone that B depended on its shape. Or: two services both write to the same `orders` table with different validation rules, and rows exist that are valid by one service's rules and invalid by the other's.

**Fix:** one service owns each table; every other consumer goes through that service's API or its published event stream. If B genuinely needs A's data in near-real-time and an API call is too slow or too tightly coupled, B gets its own materialized read model, kept in sync via CDC or events — not a second writer to A's table. This is the single highest-leverage fix in this whole catalogue: most distributed-monolith and dual-write pain traces back to a shared table.

### 4. God object

**Symptom:** one class, module, or service accretes every new feature because it's the thing that "already knows about" the domain — `OrderService.java` growing to 4,000 lines because pricing, inventory, shipping, tax, and loyalty-points logic all got added there since it already had an `Order` reference. Observable in practice: a disproportionate share of PRs touch this one file, a disproportionate share of merge conflicts happen in it, and it has the highest bus-factor risk on the team (one or two people who understand the whole thing).

**Fix:** decompose by responsibility along the axis of *who asks for changes* (SRP's actor-based definition, `T21-solid`) — pricing, inventory, tax, and loyalty become separate collaborators the god object was doing on their behalf, each independently testable and independently ownable. At the service level, this is the same failure as a monolith with no internal module boundaries; the fix is the same decomposition, whether it lands as internal modules or as separate services depends on whether there's an actual independent-scaling or independent-team reason to pay for the split.

### 5. Chatty services

**Symptom:** rendering one page or completing one logical operation requires tens of synchronous inter-service calls — one real account: a checkout flow making 40+ calls to render a single page, each a network hop with its own latency and failure probability. Latency compounds (even at 10ms p50 per call, 40 sequential calls is 400ms minimum, and p99 tail latencies compound multiplicatively, not additively, across a synchronous chain). Failure probability compounds too: if each call succeeds 99.9% of the time independently, 40 calls in sequence succeed only ~96% of the time (0.999^40 ≈ 0.961), turning a "five nines" component into a "two nines" user experience.

**Fix:** three levers, usually combined. (1) **Aggregation** — a backend-for-frontend or API gateway layer that fans out in parallel rather than the client doing it sequentially, cutting wall-clock time even without cutting call count. (2) **Data locality** — the calling service keeps a local, eventually-consistent read replica of data it needs often (via events or CDC) instead of calling out for it on every request. (3) **Coarser service boundaries** — if two services are always called together for every operation, they may be the wrong boundary; merging them removes the calls entirely rather than optimizing them.

### 6. Anemic domain model

**Symptom:** entity classes are pure data holders — `Order` has `get_status()`/`set_status()` and nothing else — while all business logic (can this order be cancelled? does this discount apply? is this state transition legal?) lives in external `*Service` classes that operate on the entity from outside. Any code anywhere can call `order.set_status("shipped")` regardless of whether the order was ever paid, because the entity itself enforces no invariant.

**Fix:** move logic that's actually *about* the entity's own invariants back into the entity — `order.ship()` that internally checks `self.status == PAID` and raises if not, rather than a `ShippingService.ship(order)` that may or may not remember to check. This is DDD's core prescription (rich domain model, `T21-ddd`) and it's a genuine overcorrection risk in the other direction — see Tradeoffs below.

---

## Build it from scratch

A lightweight static check that catches two of these mechanically — cross-service table access and synchronous call fan-out depth — is worth being able to sketch:

```python
# untested sketch: detect cross-service DB access from a services->tables ownership map
def find_shared_database_violations(ownership: dict[str, set[str]],
                                     access_log: list[tuple[str, str]]) -> list[str]:
    """ownership: {service: {tables it owns}}; access_log: [(service, table_accessed)]"""
    owner_of = {t: s for s, tables in ownership.items() for t in tables}
    violations = []
    for service, table in access_log:
        owner = owner_of.get(table)
        if owner and owner != service:
            violations.append(f"{service} accessed {table}, owned by {owner}")
    return violations

# untested sketch: flag chatty fan-out from a distributed trace
def find_chatty_operations(trace, threshold: int = 15) -> bool:
    call_count = sum(1 for span in trace.spans if span.kind == "rpc")
    return call_count > threshold  # flag for aggregation-layer review
```

Wire the first into a nightly job reading query logs against a maintained ownership map (or, better, enforced at the connection-string/credential level — a service literally cannot authenticate to a database it doesn't own). Wire the second into trace sampling on your highest-traffic endpoints, alerting when p50 fan-out crosses your threshold.

---

## How it's done in production

| Anti-pattern | Detection mechanism used in practice | Structural fix |
|---|---|---|
| Distributed monolith | Deploy-order dependency documented (a smell in itself); coupled CI pipelines | Data ownership per service + versioned contracts; merge if still coupled after that |
| Dual writes | Reconciliation jobs finding drift between two "sources of truth" | Transactional outbox or CDC (Debezium) — one true write, derived event stream |
| Shared database | Cross-schema query audits; credential scoping per service | One owner per table; consumers get an API or a CDC-derived read replica |
| God object | Code-churn/PR-touch-frequency analysis flagging one file as a hotspot | Decompose along actor/responsibility axis (SRP); extract collaborators |
| Chatty services | Distributed tracing showing high fan-out per request; tail-latency budget blown | BFF/aggregation layer, data locality via events, or merge coarser boundaries |
| Anemic domain model | Code review noting `*Service` classes as the only place logic lives | Move invariant-enforcing logic into the entity; keep orchestration in services |

### Failure-mode table

| Symptom | Cause | Fix |
|---|---|---|
| Two teams' deploys must be sequenced in a specific order every release | Distributed monolith via shared contract or shared table | Own data exclusively per service; version contracts with deprecation windows |
| Search index shows a product as in-stock after it was sold out in the DB | Dual write between order DB and index, no atomicity | Transactional outbox or CDC from the DB's WAL |
| A migration in one service silently breaks another service's queries | Shared database, no ownership boundary | One writer per table; others consume via API/events |
| One file/class receives 3x the PR volume of any other in the repo | God object accreting unrelated responsibilities | Decompose by actor (who drives the change), extract collaborators |
| p99 latency on a page is dominated by network hops, not compute | Chatty services, no aggregation layer | BFF fan-out in parallel, or data locality via local read replica |
| A field can be set to an invalid combination and no code objects | Anemic domain model, logic lives outside the entity | Push invariant checks into the entity's own methods |

---

## Tradeoffs & when NOT to use it

- **Don't chase a "rich domain model" to the point of a god object.** Overcorrecting anemic-domain-model criticism by stuffing every conceivable rule into the entity recreates the god-object problem one level down — an `Order` class that also knows how to calculate tax, render an invoice, and talk to a payment gateway is not "rich," it's anemic-domain-model's mirror-image mistake. Entities own *their own* invariants; cross-entity orchestration belongs in a service/use-case layer.
- **A shared database is sometimes the right call, deliberately.** A small team, low change velocity, and a genuine need for cross-entity transactional consistency (an actual ACID transaction spanning what would be two services) is a real argument for keeping things in one database behind one service, or accepting a modular monolith rather than physically splitting. The anti-pattern is *accidental* coupling via a shared table nobody planned for, not *deliberate* single-database design.
- **Aggressive decomposition to avoid "god object" can create chattiness.** Splitting a cohesive concept into five tiny services because "god object bad" often just relocates the problem into anti-pattern #5 — now every operation needs five network calls instead of five method calls. Cohesion should drive the boundary, not a fear of large files.
- **The outbox pattern adds latency and operational surface you don't always need.** For a low-consequence side effect (an analytics event that's fine to lose occasionally), a best-effort fire-and-forget write may be the pragmatic choice over the operational cost of an outbox table, relay process, and dedup logic on the consumer side. Reserve outbox/CDC for writes where drift is actually expensive.
- **Merging services back together is a legitimate fix, not a failure.** If two services are always deployed together and always called together, undoing the split (back into one deployable, still internally modular) is frequently the correct staff-level call, and it's a harder conversation to have than "add more tooling" — but it's usually right.

---

## Interview questions

### Q1 — What's the difference between microservices and a distributed monolith?
**Testing:** whether the candidate can distinguish physical topology from actual independence.
**Answer:** Microservices are independently deployable — you can change and release service A without coordinating with service B's team or release schedule. A distributed monolith looks the same on an architecture diagram (multiple processes, multiple repos, a network between them) but isn't independently deployable, because a shared database or an un-versioned synchronous contract couples the two so tightly that a change in one requires a coordinated change in the other. You've paid for network latency, partial failure, and operational complexity without buying release independence.
**Follow-up trap:** *"How would you detect it without a diagram, just from operational signals?"* — look for deploy-order dependencies in your release runbook, rollback of one service breaking another, and cross-service database credentials that can read/write tables outside their nominal ownership. Any of those three is a distributed monolith regardless of what the service diagram claims.

### Q2 — Explain the dual-write problem and how the outbox pattern fixes it.
**Testing:** understanding atomicity across heterogeneous systems, not just pattern recall.
**Answer:** Writing to two systems (a DB and a queue, a DB and a cache) as two separate operations is not atomic — a crash or network failure between them leaves the systems disagreeing, with no way to tell from either system alone that the other write didn't happen. The outbox pattern writes the state change and an outbox event row in the *same database transaction*, so they either both commit or neither does; a separate relay process (polling the outbox table, or CDC reading the WAL) then publishes the event, retrying until acknowledged, and marks it done. This converts an unsafe two-system write into one atomic write plus a durable, at-least-once relay.
**Follow-up trap:** *"The relay can still fail after publishing but before marking the row done — what happens?"* — the event gets republished on retry, so consumers must be idempotent (dedupe by event ID). At-least-once delivery plus idempotent consumers is the actual guarantee, not exactly-once — say this explicitly, because claiming exactly-once here is the trap.

### Q3 — A migration in your service just broke a completely unrelated team's queries. How did this happen and how do you prevent it?
**Testing:** shared-database recognition and the ownership fix.
**Answer:** It happened because their service was reading or writing a table your service "owns" directly, without going through your API — a shared-database anti-pattern, even though the org chart shows two separate services. Prevention: enforce data ownership at the credential level (their service's DB user literally cannot authenticate against your schema), and give them an explicit API or an event-derived read replica for whatever they needed from that table.
**Follow-up trap:** *"They say the API is too slow for their use case — what now?"* — a materialized read model on their side, kept current via CDC or your published domain events, gives them local, fast reads without a second writer to your table. This is the standard resolution when "call the API" and "share the table" are both wrong answers.

### Q4 — What makes something a god object rather than just "a big class"?
**Testing:** whether they can articulate the actual failure mode, not just size.
**Answer:** Size alone isn't the tell — a big class with one cohesive responsibility, well-tested, rarely touched by unrelated changes, isn't a problem. A god object is defined by *unrelated responsibilities accreting because it's the convenient place to add them* — you can usually spot it operationally as the file with disproportionate PR churn and merge-conflict rate, and as the single point every unrelated feature routes through. The fix is decomposing along the actor axis: who, independently, drives changes to each piece.
**Follow-up trap:** *"Isn't 'decompose by responsibility' just SRP? Why is this a separate anti-pattern?"* — it's the same principle, but the anti-pattern names the *symptom you observe in production and code metrics* (churn, conflict rate, bus factor) rather than the principle you'd cite in a design review; interviewers want to see you connect the operational symptom to the design-principle cause, not just recite the principle.

### Q5 — Your checkout page makes 40 synchronous calls to render. Walk through the fix.
**Testing:** the mechanics of the chatty-services fix, with numbers.
**Answer:** First quantify: even at a generous 10ms p50 per call, 40 sequential calls is a 400ms floor before any real work, and independent per-call reliability compounds multiplicatively — 99.9% success per call, 40 calls, lands around 96% overall success, turning a "five nines" set of dependencies into a "two nines" user experience. Fix with a combination: a backend-for-frontend that fans calls out in parallel rather than the client doing them sequentially (cuts wall-clock without cutting count), data locality for the data actually needed on every request (a local eventually-consistent copy synced via events instead of a live call), and re-examining whether some of those 40 calls are between services that are always called together and might be the wrong boundary.
**Follow-up trap:** *"Parallelizing the 40 calls doesn't reduce failure probability. Does it solve the reliability half of the problem?"* — no, only the latency half. Reliability requires either reducing the actual call count (locality, merging boundaries) or making individual calls more reliable (the resilience catalogue: timeout, retry with jitter, circuit breaker, bulkhead) — parallelization and reliability are separate levers and a full answer names both.

### Q6 — What's an anemic domain model and what's the actual cost of having one?
**Testing:** whether they can name a concrete cost, not just the definition.
**Answer:** Entities that are pure data holders (getters/setters, no behavior) with all business logic living in external service classes that operate on them. The concrete cost: invariants can be violated from anywhere, because nothing about the entity itself prevents an illegal state — any code with a reference to the object can call a setter that produces a combination of fields that should never coexist (a shipped order with no payment, a discount applied twice). You end up relying on every caller remembering to check preconditions correctly, rather than the object refusing an illegal transition itself.
**Follow-up trap:** *"When is an anemic domain model actually fine?"* — for simple CRUD entities with genuinely no behavior or invariants beyond field validation (a `Tag` with a name and a color), forcing "rich" methods onto them is ceremony with no payoff. The anti-pattern is specifically entities *with real invariants* (an Order's valid state transitions) being modeled anemically — not anemia everywhere being wrong.

### Q7 — Give an example of overcorrecting anemic domain model into a new anti-pattern.
**Testing:** whether the candidate understands these patterns compose and can double back.
**Answer:** Stuffing an entity with responsibilities that aren't actually about its own invariants — an `Order` class that also formats an invoice PDF, calls a payment gateway, and computes shipping rates from a live carrier API — recreates the god-object problem, just inside what was meant to be a "rich" entity. The correct scope for entity behavior is invariant enforcement about the entity's *own* state (can this order transition to shipped); cross-entity orchestration, external I/O, and multi-entity workflows belong in an application/use-case service layer that coordinates entities without absorbing their internal rules.
**Follow-up trap:** *"Where exactly is that line, concretely?"* — if the logic only needs the entity's own current fields to decide, it belongs on the entity (`order.can_cancel()` needs only `self.status`); if it needs another entity, an external system, or orchestration across steps, it belongs in a service (`OrderCancellationService` that checks inventory *and* calls `order.cancel()` *and* triggers a refund).

### Q8 — How do you distinguish "deliberately shared database, single team, low complexity" from the shared-database anti-pattern?
**Testing:** whether the candidate treats these as context-dependent rather than absolute rules.
**Answer:** The anti-pattern is *accidental, unplanned* coupling — a table that started as one service's private implementation detail and silently accumulated a second, then third writer, none of whom coordinated on the schema. A deliberately single-database design, chosen because a small team needs real ACID transactions spanning what could be separate concerns, with one team owning the whole schema and no cross-team coordination cost, isn't the anti-pattern — it's a legitimate architecture choice (arguably a modular monolith with a shared schema). The tell is whether schema changes require cross-team coordination that wasn't anticipated when the sharing began.
**Follow-up trap:** *"The team is about to split in two. What do you do about the shared database before that happens?"* — that's exactly the trigger point to introduce explicit ownership boundaries (assign each table to the service that will own it post-split, migrate cross-boundary access to an API or event stream) *before* the org split, not after — doing it after the split is when you get the shared-database anti-pattern by default, because nobody owns the migration once two teams both depend on the status quo.

### Q9 — Rank these six anti-patterns by how often their absence of a fix causes a real production incident, in your experience.
**Testing:** synthesis and prioritization judgment, staff-level framing.
**Answer:** Dual writes and shared database tend to cause the most acute incidents (silent data divergence, a migration breaking an unrelated team with no warning) because the failure is invisible until something reconciles and finds drift, or until deploy day. Distributed monolith causes chronic pain (slow releases, coordinated deploys) more than acute incidents, but escalates into one when a rollback of A can't happen without B, mid-incident. Chatty services and god object are usually availability/latency risks that show up under load or during a change, rather than correctness incidents. Anemic domain model is the slowest-burning — it rarely pages anyone directly, but it's a root cause you find during the postmortem for a data-integrity bug days or weeks after the actual write happened.
**Follow-up trap:** *"Why is that the opposite of how often they're discussed in system design interviews?"* — dual writes and shared database are less conceptually glamorous than "microservices vs monolith" debates, so they get less airtime, but they're the ones an operator actually loses sleep over. Being able to say this, and name the ranking from lived incident cost rather than interview-question popularity, is itself the senior signal.

---

## Red flags that fail you

- Naming "distributed monolith" and stopping at "microservices done wrong" without identifying the specific coupling (shared DB or un-versioned contract).
- Describing dual writes as fixable by "just adding retries" — retries don't create atomicity, they just retry a non-atomic operation.
- Treating every large class as a god object regardless of whether its responsibilities are actually cohesive.
- Proposing "split into more services" as the reflexive fix for chatty services, without recognizing that can make it worse.
- Claiming anemic domain model is always wrong, with no acknowledgment that simple CRUD entities are fine anemic.
- Not knowing that these anti-patterns compound — recommending a fix for one that recreates another (rich-domain overcorrection into god object being the classic case).
- Treating a deliberately shared single-team database as automatically an anti-pattern.

---

## Cheat card

```
DISTRIBUTED MONOLITH   symptom: coordinated deploys, rollback of A breaks B
  causes: shared DB (most common) · un-versioned sync contracts · layered-not-capability split
  fix: own data exclusively + versioned contracts; merge if still coupled

DUAL WRITES            symptom: two "sources of truth" silently disagree after a crash
  fix: transactional outbox (write state + event, same txn, relay publishes)
       or CDC (Debezium reads WAL — one true write, derived stream)
  guarantee: at-least-once delivery + idempotent consumers, NOT exactly-once

SHARED DATABASE        symptom: migration in A silently breaks B's queries
  fix: one writer per table; others get API or CDC-derived read replica
  enforce at credential level, not just convention

GOD OBJECT              symptom: disproportionate PR churn/conflict rate in one file
  fix: decompose by actor (who drives the change) — SRP's real definition
  overcorrection risk: "rich domain model" stuffed with orchestration = god object again

CHATTY SERVICES         symptom: one page/op = dozens of sync inter-service calls
  math: 40 calls @99.9% each ≈ 96% success (0.999^40) — 5-nines dep → 2-nines UX
  fix: BFF parallel fan-out (latency) + data locality via events (call count)
       + reconsider boundary if always-called-together

ANEMIC DOMAIN MODEL     symptom: entity has no methods enforcing its own invariants
  fix: push invariant checks INTO the entity (order.ship() checks status itself)
  scope line: entity's own current fields → entity method;
              needs another entity/external I/O → service/use-case layer

ROOT-CAUSE ORDERING     shared DB usually underlies distributed monolith AND dual writes —
                        fix the database ownership first, the others often shrink
```

## Sources

- [Distributed monolith architecture: What it is, why it happens, and how to fix it — vFunction](https://vfunction.com/blog/distributed-monolith-architecture/) — accessed 2026-08-02
- [The Perils of the Distributed Monolith — ONDEMANDENV.dev](https://ondemandenv.dev/articles/distributed-monolith/) — accessed 2026-08-02
- [10 Common Microservices Anti-Patterns — DesignGurus](https://www.designgurus.io/blog/10-common-microservices-anti-patterns) — accessed 2026-08-02
- [Anemic domain model — Wikipedia](https://en.wikipedia.org/wiki/Anemic_domain_model) — accessed 2026-08-02
- [The Chatty Service Anti-Pattern: Why Microservices Talk Too Much — AIM Consulting](https://aimconsulting.com/insights/chatty-service-anti-pattern-explained/) — accessed 2026-08-02
- [16 Must-Know Microservices Anti-Patterns — Medium](https://medium.com/@meet2sudhakar/16-must-know-microservices-anti-patterns-3257c8a73d2e) — accessed 2026-08-02

## Changelog
- 2026-08-02 — created
