# Refactoring Catalogue, Strangler Fig, Legacy Migration

> **Track:** T13 SDE Craft & Vibe Coding · **Time:** 2.5h · **Prereqs:** `T21-architecture-principles` · **Updated:** 2026-08-03
> **Module id:** `T13-refactoring` · **Tags:** refactoring, migration, critical

## The 30-second version

Refactoring is a named catalogue of small, behavior-preserving transformations (Extract Method, Extract Class, Replace Conditional with Polymorphism, Inline Variable, Move Method — Fowler's *Refactoring*, 1999, second edition 2018), each triggered by a specific "code smell" and each individually small enough to verify by running tests before and after, never a vague "clean this up" — the discipline is naming which transformation applies and why, not aesthetic judgment. The Strangler Fig pattern (Fowler, 2004) is the dominant strategy for migrating a legacy system without a big-bang rewrite: put a routing layer (a proxy, a feature flag, an API gateway rule) in front of the legacy system, migrate one capability at a time behind it, and cut traffic over per-capability rather than all at once — the pattern is named for the fig that grows around a host tree and eventually replaces it entirely, and the fig only survives if the host keeps standing throughout, which is the whole discipline: the legacy system stays fully operational until each individual piece is verified. The number that actually predicts whether a strangler migration succeeds isn't the plan's quality, it's early velocity — analysis of enterprise strangler projects found roughly 68% stall before 90 days without replacing their first monolith component, and projects extracting under 5% of monolith functionality in the first 90 days had a 92% failure rate, which makes "ship something real, fast" the actual risk-mitigation strategy, not a nice-to-have. Getting time allocated for refactoring against a feature-hungry roadmap is a negotiation, not an engineering decision, and it's won by tying specific refactors to specific, already-felt costs (this exact class of bug, this exact deploy slowdown) rather than appeals to code quality in the abstract.

## Why this gets asked

Because "how do you handle technical debt" and "how would you migrate this legacy system" are the two most common ways a principal-level interview probes whether a candidate has actually executed a multi-quarter migration under real business pressure, or only ever discussed one in the abstract. The interviewer has almost certainly either run a strangler migration that stalled at month four because the team spent the first quarter building infrastructure with nothing shippable to show, or been on a team that attempted a big-bang legacy rewrite that got cancelled eighteen months in with nothing to show for it either — both are common, well-documented failure shapes, and they want to know if the candidate can name the specific mechanism (early velocity, or the missing routing layer, or no board-level buy-in) that would have prevented it, not just recite "strangler fig pattern" as a keyword.

---

## Lineage: past → present → future

**What came before.** Before refactoring had a name and a catalogue, "cleaning up code" was an individual, unstructured judgment call — an engineer decided something looked bad and rewrote it, with no shared vocabulary for what transformation was being applied, no guarantee the behavior was actually preserved beyond "it still compiles," and no way for a reviewer to check the change against a known-safe pattern versus a risky one. William Opdyke's 1992 PhD thesis formalized behavior-preserving program restructuring with provable safety conditions; Martin Fowler's *Refactoring: Improving the Design of Existing Code* (1999) turned that academic foundation into a practitioner's catalogue — over 60 named transformations, each with a specific trigger ("code smell"), mechanics, and worked example — and paired it with the specific discipline that made it trustworthy at speed: small steps, tests green before and after every single step, never a large uncontrolled rewrite masquerading as refactoring. Before the Strangler Fig pattern had a name, legacy migration meant either "big-bang rewrite" (freeze the old system, build the new one in parallel, cut over all at once) or "live with it indefinitely" — the big-bang approach's specific, repeated failure was well-documented even in the 1990s (the "second-system effect," Fred Brooks, 1975): the new system takes far longer than estimated because requirements were never fully captured from the old one, the business can't stop needing features from the old system while the new one is built, and the eventual cutover is a single, high-stakes, all-or-nothing event with no partial-success path.

**Where it stands now.** Fowler's refactoring catalogue (updated to a second edition in JavaScript, 2018, with the underlying transformations unchanged in substance from the 1999 original) is the accepted shared vocabulary across the industry — "extract this into a method" or "replace this conditional with polymorphism" needs no further explanation among practitioners because the catalogue did the work of standardizing the terms decades ago. The Strangler Fig pattern (Fowler, 2004, building on a name he credits to the strangler fig tree's growth habit) is the consensus default strategy for legacy migration specifically because it has an incremental, partial-success path a big-bang rewrite doesn't: each migrated capability is independently shippable and independently reversible via the routing layer, so a failed or stalled migration leaves a partially-modernized system rather than nothing. The live, well-documented failure mode at scale: analysis of enterprise strangler migrations attempted 2022-2025 found roughly 68% stall before 90 days without replacing their first monolith component, and the strongest predictor of eventual success was early velocity — projects extracting under 5% of monolith functionality in the first 90 days failed 92% of the time — which reframes the pattern's real risk not as "will the architecture work" (it does, mechanically) but "will the organization sustain momentum long enough to matter," a people-and-incentives problem more than a technical one.

**Where it's heading.** AI-assisted refactoring tooling is making individual catalogue transformations (Extract Method, Rename, Inline Variable) close to mechanically free to execute correctly, which shifts the actual bottleneck further toward judgment: knowing *which* transformation the current code smell calls for, and knowing where the strangler routing layer should sit architecturally, remain human judgment calls that tooling accelerates the execution of but doesn't make for you — this mirrors the exact "bottleneck moved, didn't disappear" shift covered for AI-assisted coding generally (`T13-vibe-coding`, `T28-claude-architect`). More speculative but actively discussed: AI-assisted dependency-mapping tools that ingest a legacy codebase and propose a strangler cut-order based on actual call-graph coupling (rather than a human manually reverse-engineering the dependency graph) are emerging and genuinely promising for de-risking the "we didn't know that function existed" timeline-blowout failure mode, but aren't yet a mature, trusted replacement for a human doing the dependency mapping directly on a codebase with real architectural stakes.

---

## Mental model

```
FOWLER'S CATALOGUE: SMELL -> NAMED TRANSFORMATION -> VERIFY, ONE STEP AT A TIME

  SMELL                          TRANSFORMATION                  WHEN IT APPLIES
  ──────────────────────         ─────────────────────────       ─────────────────
  Long Method                    Extract Method                  a method does >1 thing
  Large Class / God Object       Extract Class                   a class has >1 responsibility
  Switch/if-chain on TYPE        Replace Conditional              adding a new type means
                                   with Polymorphism                touching the same switch
                                                                    in N places
  Feature Envy                   Move Method                      a method uses another
                                                                    class's data more than
                                                                    its own
  Data Clump                     Extract Class / Introduce         same 3-4 params always
                                   Parameter Object                 travel together
  Primitive Obsession             Replace Primitive with Object    a raw string/int actually
                                                                    represents a domain concept

  EACH STEP: small, behavior-preserving, tests green BEFORE and
  AFTER. A "refactor" that changes behavior isn't a refactor,
  it's a rewrite wearing a refactor's name -- and it doesn't get
  the safety guarantee refactoring exists to provide.

STRANGLER FIG: route by capability, migrate one piece at a time, cut over per-piece

          ┌─────────────┐
  traffic →│   ROUTER    │→ still-legacy capabilities → [ LEGACY MONOLITH ]
          │ (proxy/flag/│
          │  gateway)   │→ already-migrated capability A → [ NEW SERVICE A ]
          └─────────────┘→ already-migrated capability B → [ NEW SERVICE B ]

  the fig GROWS AROUND the host tree and only replaces it once
  fully established -- the host (legacy system) stays alive and
  fully operational for the ENTIRE migration, cut over piece by
  piece, never frozen, never big-banged.

  THE NUMBER THAT PREDICTS SUCCESS: not the migration plan's
  elegance -- EARLY VELOCITY. <5% of monolith functionality
  extracted in the first 90 days -> 92% failure rate (stalls,
  reverts, gets cancelled). Ship something real, fast, or the
  project dies to organizational attention decay before the
  architecture is even tested at scale.
```

## How it actually works

### The refactoring catalogue, mechanically, with named transformations

Fowler's catalogue pairs each transformation with a specific trigger smell and a small, reversible mechanical procedure — the discipline that makes refactoring trustworthy is that each individual step is small enough to verify immediately, not that the *overall* change is small (a large refactor is just many small verified steps in sequence). A few of the highest-frequency transformations, concretely:

**Extract Method** — the response to Long Method: identify a cohesive chunk of a large method's body, pull it into a new, well-named method, replace the original code with a call to it. The mechanical safety check: the extracted method's inputs are exactly the local variables it references, its output is exactly what the original code computed at that point — if this isn't true, the extraction changed behavior and isn't actually this transformation.

**Extract Class** — the response to a class doing too much (a God Object, or a class with two distinct sets of methods/fields that rarely interact with each other): create a new class, move the relevant fields and methods to it, and reference the new class from the old one. This is frequently the first, hardest step in breaking apart a legacy monolith's internal structure before attempting a strangler-style extraction at the service level, because a monolith's internal classes are often as tangled as its external API surface.

**Replace Conditional with Polymorphism** — the response to a switch or if/else chain that branches on an object's type, especially one that recurs in multiple places (adding a new type means finding and updating every one of those switches). The mechanical procedure: for each branch of the conditional, create a subclass; move the branch's logic into an overridden method on that subclass; replace the conditional's call site with a polymorphic method call. The concrete payoff: adding a new type now means adding one new subclass, not finding and editing every scattered switch statement — this is precisely the kind of transformation an AI coding agent can execute mechanically once a human has identified that this smell, specifically, is present.

**Move Method** — the response to Feature Envy, where a method on class A uses class B's data and methods far more than its own class's — move the method to B, where the data it actually operates on already lives. This is a small, often-overlooked transformation that directly reduces the hidden-coupling failure mode covered in `T13-code-review`: a method living on the wrong class is itself a form of coupling that isn't visible in any type signature.

**Introduce Parameter Object** — the response to a Data Clump, where the same three or four parameters always travel together across multiple method signatures — bundle them into a single object. This one has a specific, checkable payoff for review: a data clump that later needs a fifth field means updating every call site that passed the four individually; a parameter object needs updating in one place.

### Strangler Fig, mechanically: the routing layer is the whole discipline

The Strangler Fig pattern's mechanics reduce to one architectural decision executed carefully: insert a routing layer — a reverse proxy (nginx, an API gateway), a feature-flag-driven dispatch inside the existing entry point, or DNS/load-balancer-level routing for whole-service cutover — in front of the legacy system, such that the router, not the client, decides whether a given request is served by the legacy system or by a newly-migrated piece. Each capability migrates independently: build the new implementation, verify it against the legacy behavior (often by running both in parallel and diffing outputs — a "shadow" or "dark launch" phase — before actually cutting traffic over), flip the router for that capability specifically, and only then decommission that piece of the legacy system. The property that makes this safer than a big-bang rewrite: at every point in the migration, the system as a whole is fully operational, and a problem discovered in newly-migrated capability A doesn't require rolling back capabilities B through Z that already cut over successfully — the router lets you revert *per capability*, which is the actual risk-reduction mechanism, not a side benefit.

### The 90-day velocity number, and why it's the real predictor

Analysis of 41 enterprise strangler migrations (2022-2025) found 68% stalled before 90 days without ever replacing their first monolith component, and separately found that projects extracting less than 5% of monolith functionality in the first 90 days failed 92% of the time — while projects clearing that early bar succeeded at a dramatically higher rate. The mechanism behind this number is organizational, not technical: a migration's first quarter is disproportionately spent on infrastructure (standing up the router, the shadow-traffic comparison tooling, the new service's baseline scaffolding) that produces no visible business value, and if that infrastructure phase drags past 90 days with nothing shipped, executive attention and budget commitment erode — the project doesn't fail because the architecture doesn't work, it fails because organizational patience for an invisible-progress phase runs out before the pattern gets to demonstrate its actual payoff. The practical implication: the very first capability chosen for migration should be picked for how fast it can visibly ship, not for architectural cleanliness or "logical starting point" — a small, low-risk, highly visible win in the first 90 days buys the political capital the rest of the migration needs.

### Getting buy-in and time for refactoring against a feature-hungry roadmap

Refactoring work competes directly with feature work for the same engineering time, and "the code quality is bad" as a pitch to a roadmap-owning stakeholder consistently loses, because it's an appeal to an abstraction the stakeholder can't verify or prioritize against a concrete feature request. What wins, consistently: tying a specific refactor to a specific, already-observed, already-costed production event — "we've had three incidents in the past two months traced to this exact conditional-on-type logic, each costing roughly N hours of on-call time, and Replace Conditional with Polymorphism here would have prevented the third one entirely, verifiably, because the new type wouldn't need to touch the other four call sites" — because this is a concrete cost the stakeholder can weigh against a concrete feature's value, using the same currency (time, incident cost, deploy risk) they already use for feature prioritization. The technique that keeps refactoring funded across multiple planning cycles rather than requiring a fresh pitch each time: attach small, catalogue-named refactors to feature work that's touching the same code anyway (a Boy Scout Rule application, scoped and named specifically rather than an open-ended "clean up while you're in there"), so the marginal cost is small and doesn't need its own separate budget line, reserving the dedicated-refactoring-sprint pitch for genuinely large structural work (a strangler migration's routing-layer phase) that can't be smuggled in incrementally.

## Build it from scratch

A minimal illustration of Replace Conditional with Polymorphism, plus the shape of a strangler router:

```python
# untested sketch — BEFORE: Long Method + switch-on-type (two smells at once)
def calculate_shipping(order):
    if order.carrier == "ups":
        base = order.weight * 0.5
        return base + (2.0 if order.expedited else 0)
    elif order.carrier == "fedex":
        base = order.weight * 0.45
        return base + (2.5 if order.expedited else 0)
    elif order.carrier == "usps":
        base = order.weight * 0.6
        return base  # USPS has no expedited surcharge -- easy to miss adding this
    # adding a 4th carrier means finding and editing every switch like this one, elsewhere

# AFTER: Replace Conditional with Polymorphism
class ShippingStrategy:
    def calculate(self, order): raise NotImplementedError

class UPSShipping(ShippingStrategy):
    def calculate(self, order):
        return order.weight * 0.5 + (2.0 if order.expedited else 0)

class FedExShipping(ShippingStrategy):
    def calculate(self, order):
        return order.weight * 0.45 + (2.5 if order.expedited else 0)

class USPSShipping(ShippingStrategy):
    def calculate(self, order):
        return order.weight * 0.6   # explicit: this carrier has no expedited surcharge

STRATEGIES = {"ups": UPSShipping(), "fedex": FedExShipping(), "usps": USPSShipping()}
def calculate_shipping(order):
    return STRATEGIES[order.carrier].calculate(order)
# a 4th carrier is now ONE new class + one dict entry, not a hunt across the codebase
```

```nginx
# untested sketch — strangler router: per-capability cutover via path-based proxy rule
location /api/v1/pricing/ {
    # already migrated: route to the new service
    proxy_pass http://new-pricing-service;
}
location /api/v1/ {
    # not yet migrated: everything else still goes to the legacy monolith
    proxy_pass http://legacy-monolith;
}
# cutting over the NEXT capability (e.g. /api/v1/inventory/) is one new location
# block, added when that specific piece's shadow-traffic comparison passes --
# never a global cutover, never a moment where the whole system is "the new one"
```

## How it's done in production

| Symptom | Cause | Fix |
|---|---|---|
| A strangler migration stalls at month 3-4 with nothing shipped yet | First quarter spent entirely on invisible infrastructure (router, shadow-comparison tooling) with no capability actually cut over | Choose the very first migrated capability for shipping speed and visibility, not architectural cleanliness — get something real live inside 90 days to preserve organizational patience |
| A "refactor" PR changes observable behavior and breaks a caller | It wasn't actually a refactoring — a real refactor is behavior-preserving by definition; this was an uncontrolled rewrite mislabeled as one | Revert to the catalogue discipline: name the specific transformation, verify tests green before and after each small step, never bundle a behavior change into a "refactor"-labeled PR |
| Adding a new type/carrier/payment-method requires finding and editing the same switch statement in five different files | Conditional-on-type logic scattered across the codebase instead of centralized via polymorphism | Replace Conditional with Polymorphism at the point of highest edit frequency first; each new type becomes one new subclass instead of N scattered edits |
| A refactoring pitch to leadership gets deprioritized every planning cycle | The pitch was framed as a code-quality abstraction, not tied to a specific, already-costed production event | Reframe using the same currency leadership already prioritizes with (incident hours, deploy risk, on-call cost) tied to a specific, named past incident this exact refactor would have prevented |
| A strangler migration's legacy system and new system silently diverge in behavior after cutover | No shadow-traffic/parallel-run verification phase before flipping the router for a capability | Run both implementations in parallel against real traffic, diffing outputs, before cutting the router over for that capability — never cut over on faith that the new implementation matches |
| A migration succeeds technically but the legacy system never actually gets decommissioned | Highest-visibility capabilities migrated first, then organizational attention moved elsewhere, leaving the legacy system running indefinitely alongside the new one (double maintenance burden) | Track decommissioning as an explicit, separately-tracked milestone per capability — cutting the router over is not the same as finishing the migration; the legacy code has to actually be deleted |
| A dependency-mapping effort for a strangler migration blows a 6-month estimate into 18 months | Skipped detailed dependency mapping upfront; testing surfaces functions and call paths nobody knew existed as the migration proceeds | Invest in real dependency mapping (static analysis of the actual call graph, not documentation) before committing to a timeline, treating discovery of the true dependency graph as part of the estimate, not a risk to discover mid-migration |

## Tradeoffs & when NOT to use it

- **Don't apply the refactoring catalogue's small-step discipline to a change that's actually a rewrite.** If behavior is supposed to change, call it what it is — a feature change or a rewrite — and give it the review scrutiny and test coverage that implies; disguising it as a "refactor" forfeits the specific safety guarantee (behavior-preservation, verified at each step) the catalogue exists to provide.
- **Don't choose a strangler migration's first capability for architectural elegance over shipping speed.** The 90-day velocity data is specific and severe (92% failure rate below 5% early extraction) — a technically "correct" but slow-to-ship first choice is a worse choice than a less elegant but fast one, because the project has to survive politically before its architecture gets to matter.
- **Don't attempt a big-bang rewrite of a legacy system with active, evolving business requirements.** The Strangler Fig pattern exists specifically because a frozen old system can't absorb the business's ongoing need for changes during a long rewrite, and a big-bang cutover has no partial-success path — if it's wrong, it's wrong all at once, at the worst possible moment.
- **Don't treat cutting the router over as the finish line.** A strangler migration that never explicitly tracks and executes legacy decommissioning per capability leaves both systems running indefinitely — a real, common, expensive failure mode distinct from the migration "failing," since it technically succeeded at building the new thing while failing to retire the old one.
- **Don't pitch refactoring time using code-quality language to a stakeholder who prioritizes in incident-cost and deploy-risk language.** The pitch fails not because the refactor is unjustified but because it was translated into the wrong currency — the fix is reframing, not abandoning the ask.
- **Small, low-risk, well-isolated legacy code that's rarely touched and not on a growth path?** Don't strangler-migrate it at all — the pattern's cost (routing layer, shadow verification, phased cutover) is only worth paying for a system under active development pressure or genuine operational pain; leaving stable, low-traffic legacy code alone is a legitimate, common, correct choice.

---

## Interview questions

### Q1 — Name three transformations from Fowler's refactoring catalogue and the specific smell each one responds to.
**Testing:** whether the candidate has actual vocabulary, not just "I refactor when code looks messy."
**Answer:** Extract Method responds to Long Method (a method doing more than one cohesive thing). Replace Conditional with Polymorphism responds to a switch/if-chain branching on an object's type, especially one repeated across multiple call sites. Move Method responds to Feature Envy, where a method uses another class's data and methods more than its own class's.
**Follow-up trap:** *"What makes something a refactor versus a rewrite wearing a refactor's name?"* — behavior preservation, verified at each small step by running tests before and after; if the observable behavior changes, it's a feature change or a rewrite and should get that review scrutiny, not the lighter-touch trust a true refactor earns.

### Q2 — What is the Strangler Fig pattern, and why is it named that specifically?
**Testing:** understanding the metaphor as a description of the actual discipline, not just a memorized term.
**Answer:** A migration strategy where a routing layer sits in front of a legacy system, and capabilities migrate one at a time behind it, with traffic cut over per-capability rather than all at once — the legacy system stays fully operational throughout. It's named for the strangler fig tree, which grows around a host tree and gradually replaces it, but only survives because the host keeps standing throughout the process — the migration analog is that the legacy system must remain fully operational the entire time, never frozen or big-banged.
**Follow-up trap:** *"What's the actual architectural component that makes this possible?"* — the router (a reverse proxy, gateway rule, or feature-flag dispatch) that decides per-request whether legacy or new code serves it — without that component, you don't have a strangler migration, you have a plan to eventually do a big-bang cutover, which is a different (and riskier) thing.

### Q3 — What number actually predicts whether a strangler migration succeeds, and why is it organizational rather than technical?
**Testing:** the specific, cited statistic and its real mechanism.
**Answer:** Early velocity in the first 90 days — analysis of 41 enterprise strangler migrations found projects extracting under 5% of monolith functionality in that window failed 92% of the time, and 68% of migrations stalled before 90 days without replacing their first component at all. The mechanism is organizational: the first quarter is disproportionately spent on invisible infrastructure (the router, shadow-comparison tooling), and if that phase drags on with nothing shipped, executive patience and budget commitment erode before the architecture ever gets tested at real scale.
**Follow-up trap:** *"Does this mean you should pick the easiest capability first regardless of architectural logic?"* — yes, deliberately: choose the first migrated capability for shipping speed and visibility, not architectural elegance, because the project has to survive its first 90 days politically before its long-term architecture gets a chance to matter at all.

### Q4 — Why is a big-bang legacy rewrite a worse default choice than a strangler migration, mechanically?
**Testing:** the specific risk-shape argument, not just "big-bang rewrites are risky."
**Answer:** A big-bang rewrite freezes the old system's requirements while building the new one over a long timeline during which the business's actual needs keep evolving, so the new system is often already behind the business's real requirements by the time it ships; and the cutover itself is a single, all-or-nothing event with no partial-success path — if something's wrong, it's wrong for the whole system at once, discovered at the worst possible moment. A strangler migration's per-capability cutover means a problem in one piece doesn't require rolling back everything already successfully migrated.
**Follow-up trap:** *"Is there ever a legitimate case for a big-bang rewrite?"* — yes, when the legacy system is small enough and isolated enough that a full rewrite genuinely fits in a short timeline with low business-requirement drift risk, or when the legacy system is being fully decommissioned rather than replaced (no functional parity needed) — the strangler pattern's cost (routing layer, phased verification) isn't worth paying for a genuinely small, contained system.

### Q5 — What's the shadow-traffic or dark-launch phase in a strangler migration, and why is skipping it dangerous?
**Testing:** the specific verification mechanic that prevents silent divergence.
**Answer:** Before cutting the router over for a capability, both the legacy and new implementations run against real traffic in parallel, with outputs diffed to confirm they actually match before the new implementation becomes authoritative. Skipping it means the first time a divergence is discovered is after cutover, in production, potentially as a customer-facing incident rather than a caught discrepancy in a comparison log.
**Follow-up trap:** *"What if the new implementation is *intentionally* different in some behavior, not just migrated as-is?"* — then shadow comparison needs an explicit allowlist of expected differences rather than a blanket diff, and each expected difference should be independently verified as intentional and correct — an unreviewed "expected difference" is exactly how a real bug gets waved through as an intentional change.

### Q6 — How do you get engineering time allocated for refactoring against a roadmap that's entirely feature-driven?
**Testing:** the negotiation/framing skill, not a technical answer.
**Answer:** Tie a specific, catalogue-named refactor to a specific, already-observed, already-costed production event — incident hours, deploy risk, on-call load — using the same currency the stakeholder already prioritizes features in, rather than an abstract code-quality appeal they can't weigh against a concrete feature request. For smaller refactors, attach them to feature work already touching the same code (a scoped, named Boy Scout Rule application) so they don't need a separate budget line at all.
**Follow-up trap:** *"What if leadership still says no even with a concrete incident-cost argument?"* — that's a legitimate outcome if the stated cost genuinely doesn't outweigh the feature work's value this cycle; the discipline isn't "refactoring always wins," it's "make the tradeoff visible and comparable" — sometimes the honest answer is the feature really is more valuable this quarter, and the refactor gets re-pitched next cycle with updated incident data.

### Q7 — A migration cuts every capability's router over successfully, but eighteen months later the legacy system is still running in production. What went wrong?
**Testing:** recognizing decommissioning as a distinct, trackable milestone.
**Answer:** Cutting the router over per capability isn't the same as finishing the migration — the legacy code has to actually be deleted and its infrastructure decommissioned, and this step is commonly skipped because organizational attention moves on once the highest-visibility capabilities are migrated, leaving both systems running indefinitely with a doubled maintenance burden.
**Follow-up trap:** *"Why would a team leave the legacy system running if the new one already handles all the traffic?"* — inertia and unclear ownership: decommissioning feels like it can be done "later" with no urgency once traffic has moved, and without an explicit, separately-tracked milestone (and often a hard deadline, like a scheduled infrastructure decommission date), "later" becomes indefinite — treating decommissioning as part of the migration's definition of done, not an optional cleanup step, is the actual fix.

### Q8 — What's Feature Envy, and what does the Move Method refactor targeting it have to do with the hidden-coupling review problem?
**Testing:** connecting the refactoring catalogue to a review concept from elsewhere in this track.
**Answer:** Feature Envy is a method that uses another class's data and methods more than its own class's — a sign it's living on the wrong class. Move Method relocates it to the class whose data it actually operates on. The connection to hidden coupling (`T13-code-review`): a method living on the wrong class is itself a form of coupling invisible in any type signature — the class it's declared on suggests one dependency relationship while its actual behavior implies a different one, which is exactly the kind of implicit, unchecked dependency that's hard to catch in review until something changes on the "wrong" side and silently breaks the misplaced method.
**Follow-up trap:** *"How would code review actually catch a Feature Envy smell before it becomes a production bug?"* — reading a new or changed method and asking "which class's data does this actually touch most" rather than just "does this class make logical sense to declare this on" — the smell is visible in the method body's actual field/method accesses, not in its declared location, which is exactly why it's easy to miss on a quick review pass.

### Q9 — Why doesn't dependency-mapping tooling fully solve the "six-month estimate becomes eighteen months" strangler-migration failure mode?
**Testing:** honest scoping of what tooling can and can't do here.
**Answer:** Dependency-mapping tools can surface the actual call graph more completely than manual reverse-engineering, reducing (not eliminating) the "we didn't know this function existed" discovery risk — but a legacy codebase's true dependency graph often includes runtime-only coupling (data shared through a database table with no code-level reference, timing assumptions, config-driven branching) that static call-graph analysis doesn't fully capture, so real testing against production-like conditions still surfaces genuine surprises tooling can't predict in advance.
**Follow-up trap:** *"So is dependency-mapping tooling not worth investing in?"* — it's worth investing in specifically because it reduces the *volume* of surprises even though it doesn't eliminate them, which directly helps the early-velocity number (Q3) by making the initial capability's scope more accurately estimated before committing — the honest framing is "meaningfully de-risks, doesn't fully solve," not "unnecessary" or "solves it."

### Q10 — Staff-level: your org has successfully strangler-migrated the highest-visibility 30% of a legacy monolith over 18 months, but the remaining 70% — lower-visibility, more tangled, more load-bearing internally — has stalled for six months with no progress. Diagnose and propose a path forward.
**Testing:** recognizing that the pattern's early-success dynamic can invert on the harder remaining work, and that this requires a different argument than the one that got the migration started.
**Answer:** The easy, high-visibility capabilities were migrated first precisely because they were easy and visible — exactly the sequencing the 90-day velocity data recommends — but that means the remaining 70% is disproportionately the tangled, load-bearing, low-visibility code that's both technically harder to safely extract and organizationally harder to get funded, because it doesn't produce a visible win the way the first wave did. The path forward requires a different pitch than the original one: reframe the remaining work not as "finishing the migration" (an abstraction) but around the concrete, growing cost of running two systems indefinitely (the doubled maintenance burden named in the failure-mode table) and the specific operational risk of the legacy system's most tangled, least-understood code being the part still running unmonitored by the newer team's tooling and practices.
**Follow-up trap:** *"What if leadership's response is 'the 30% already migrated captured most of the value, why keep going'?"* — that's sometimes the honest, correct answer, and the senior move is testing it directly rather than assuming the migration must be finished: quantify the actual remaining maintenance cost, operational risk, and opportunity cost of the still-legacy 70% against the cost of continuing, and if the numbers genuinely favor stopping, recommend stopping and explicitly maintaining the remainder rather than defaulting to "migrations should always be completed" as an unexamined assumption.

---

## Red flags that fail you

- Describing "refactoring" as any code cleanup, without naming a specific transformation from the catalogue or the smell that triggered it.
- Calling a behavior-changing rewrite a "refactor," forfeiting the safety guarantee (verified behavior preservation) the term actually implies.
- Recommending a big-bang legacy rewrite without naming the specific risk (frozen requirements during a long build, no partial-success path) the Strangler Fig pattern exists to avoid.
- Not knowing the early-velocity data (68% stall before 90 days, 92% failure rate below 5% early extraction) or treating architectural elegance as more important than early shipping speed for the first migrated capability.
- Pitching refactoring time to leadership using code-quality abstractions instead of the incident-cost/deploy-risk currency stakeholders actually prioritize with.
- Treating router cutover as the finish line of a strangler migration, with no explicit tracked decommissioning milestone.
- Skipping shadow-traffic verification before cutting a capability's router over, or having no plan for reviewing intentional differences between old and new behavior.

## Cheat card

```
FOWLER'S CATALOGUE (Refactoring, 1999/2018): smell -> named transformation
  Long Method            -> Extract Method
  God Object/Large Class  -> Extract Class
  switch/if on TYPE       -> Replace Conditional with Polymorphism
  Feature Envy            -> Move Method
  Data Clump              -> Introduce Parameter Object
  Primitive Obsession     -> Replace Primitive with Object
  DISCIPLINE: small steps, tests GREEN before+after EVERY step.
  behavior CHANGES = not a refactor, it's a rewrite -- review it as one.

STRANGLER FIG (Fowler, 2004): ROUTER (proxy/flag/gateway) in front of
  legacy system, migrate ONE capability at a time, cut over PER
  CAPABILITY. Legacy system stays FULLY OPERATIONAL the whole time --
  never frozen, never big-banged. Named for the fig that grows around
  its host and only replaces it once established.

WHY NOT BIG-BANG REWRITE: (1) requirements frozen while business keeps
  evolving during the long build, (2) cutover is all-or-nothing with
  NO partial-success path. Strangler's per-capability cutover means a
  problem in ONE piece doesn't require rolling back everything else.

THE PREDICTIVE NUMBER: 41 enterprise strangler migrations (2022-2025):
  68% STALL before 90 days w/o replacing first component.
  <5% monolith functionality extracted in first 90 days -> 92% FAILURE.
  Mechanism: ORGANIZATIONAL, not technical -- invisible infra phase
  burns executive patience before architecture is even tested at scale.
  => pick the FIRST migrated capability for SHIPPING SPEED, not elegance.

SHADOW/DARK-LAUNCH: run legacy + new in parallel against real traffic,
  DIFF outputs, before cutting router over -- never cut over on faith.

DECOMMISSIONING != cutover. Router flip is not migration-done. Track
  legacy deletion as its OWN milestone or both systems run forever
  (doubled maintenance burden -- a real, common, distinct failure mode).

GETTING BUY-IN: pitch in the stakeholder's OWN currency (incident
  hours, deploy risk, on-call cost) tied to a SPECIFIC past incident
  this exact refactor prevents -- not an abstract code-quality appeal.
  Smaller refactors: attach to feature work touching the same code
  (scoped Boy Scout Rule), no separate budget line needed.
```

## Sources

- Fowler, M. — *Refactoring: Improving the Design of Existing Code*, 2nd ed. (2018), the catalogue's canonical reference
- [Strangler Fig Pattern: A Real Case Study with Metrics, Reconciliation Data — Modernization Intel](https://softwaremodernizationservices.com/insights/strangler-fig-pattern-example/) — accessed 2026-08-03
- [Embracing the Strangler Fig pattern for legacy modernization — Thoughtworks](https://www.thoughtworks.com/insights/articles/embracing-strangler-fig-pattern-legacy-modernization-part-one) — accessed 2026-08-03
- [Strangler Fig Pattern and Legacy System Migration Methods — AltexSoft](https://www.altexsoft.com/blog/strangler-fig-legacy-system-migration/) — accessed 2026-08-03
- [Replace Conditional with Polymorphism — refactoring.com](https://refactoring.com/catalog/replaceConditionalWithPolymorphism.html) — accessed 2026-08-03
- `T13-code-review` — hidden coupling as a review category (this repo)
- `T28-claude-architect` — the "bottleneck moved, didn't disappear" framing applied to AI-assisted refactoring tooling (this repo)

## Changelog
- 2026-08-03 — created
