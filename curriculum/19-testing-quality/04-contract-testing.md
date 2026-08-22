# Consumer-Driven Contracts (Pact), Schema Compat, Breaking-Change Gates

> **Track:** T19 Testing & Quality Engineering · **Time:** 2h · **Prereqs:** T19-integration-testing
> **Module id:** `T19-contract-testing` · **Tags:** integration
> **Updated:** 2026-07-26

## The 30-second version

Contract testing verifies that a consumer and a provider agree on the shape of an API interaction without either side spinning up the other's full stack: the consumer records the exact requests it makes and the responses it depends on as a "pact," and the provider replays those recorded requests against its real implementation to prove it still satisfies them. Pact is the dominant consumer-driven implementation — code-first, broker-mediated, with a `can-i-deploy` gate that blocks a release if the specific consumer/provider version pair hasn't been verified compatible. This is a different failure mode than integration testing: an integration test proves your code works against a *copy* of the dependency you built yourself (a stub, a Testcontainers instance), which silently drifts from what the real dependency actually does; a contract test proves compatibility against the dependency's *actual, currently deployed* behavior, verified independently on both sides and reconciled through a broker. It earns its cost specifically in many-team, many-service organizations where a full staging environment with every service wired together is too slow, too flaky, or physically doesn't exist for every commit — and it's the wrong tool for a public API with unknown, unlistable consumers, where schema-based compatibility rules (OpenAPI diffing, semantic versioning) are the only mechanism that scales.

## Why this gets asked

Because it separates people who've actually operated a multi-team microservice org from people who've only worked in a monolith or a two-service demo. The interviewer has almost certainly lived through a "the staging environment was green, prod broke because service A deployed a schema change and service B hadn't redeployed yet" incident, or the opposite failure — a contract-testing rollout that turned into broker maintenance nobody wanted to own, with pact files nobody updated after the API moved on. They want to know if you understand *why* this exists (not "another testing tool") and where it stops paying for itself.

---

## Lineage: past → present → future

**What came before.** Before contract testing had a name, teams caught cross-service breakage one of two ways, both expensive. The first was a shared staging/integration environment where every service's latest build was deployed together and manually or automatically smoke-tested — slow to provision, constantly in a broken state because *someone's* branch was always mid-deploy, and useless for pinpointing which of a dozen simultaneously-deployed services caused a break. The second was full end-to-end integration tests that spun up real (or containerized) copies of every dependency for every test run — correct in principle, but combinatorially expensive: a system with 15 services each needing 2-3 real dependencies for a meaningful integration test either never finishes in CI or requires an environment nobody can run locally. Both approaches shared the same root problem: they tested "does my code work against a copy of your service," which only ever proves compatibility with whatever that copy happened to be at build time, not with what's actually deployed in production right now. Ian Robinson's original 2011 "Consumer-Driven Contracts" pattern and the Pact project (started 2013, out of REA Group and Thoughtworks in Australia and New Zealand) reframed the problem: let the consumer state what it actually needs, and make the provider prove — independently, against its real code — that it satisfies that need.

**Where it stands now.** Pact is the practical default for internal service-to-service contracts in polyglot orgs: consumer and provider can be written in different languages (Pact has JVM, JS, Python, Go, .NET, Ruby implementations that all speak the same pact-file format), and the Pact Broker (or PactFlow, its hosted/commercial form) becomes the source of truth for which consumer version is compatible with which provider version, gating deploys through `can-i-deploy`. The live disagreement is between Pact's fully consumer-driven model and "bi-directional contract testing," where the provider publishes its own contract (often generated from an OpenAPI spec or from real traffic capture) and the consumer's expectations are checked against that published contract without the consumer having to write and run Pact-specific test code — proponents (including Pact's own newer PactFlow features) argue this lowers the adoption barrier for teams that already maintain OpenAPI specs; critics argue it reintroduces provider-first thinking and loses the "the contract is derived from actual consumer usage" guarantee that made CDC valuable in the first place. Event-driven contracts (Kafka, Pub/Sub) are handled by a different but related mechanism — schema registries (Confluent Schema Registry, AWS Glue Schema Registry) enforcing backward/forward compatibility rules on Avro/Protobuf/JSON Schema at publish time — and most orgs run both: Pact for synchronous HTTP, schema registry compatibility checks for async events.

**Where it's heading.** AI-assisted code generation is making the failure mode this addresses more common, not less: an LLM-assisted change to an endpoint can alter response shape or a field's semantics faster than a human reviewer registers it, which is exactly the class of drift contract tests catch mechanically rather than by review vigilance — this is an already-visible trend, not speculation. Expect continued convergence between OpenAPI-based schema diffing (cheap, provider-first, catches structural breaks) and Pact-style CDC (catches semantic breaks the schema alone can't express, like "this field is always present when status is X") as complementary layers rather than competing choices; a confident but not yet universal practice.

---

## Mental model

```
CONSUMER SIDE                  BROKER                    PROVIDER SIDE
──────────────                ────────                   ──────────────
1. Write consumer test    →   3. pact file        →      4. Provider verification
   against Pact mock          stored + versioned          test replays each
   server, asserting               │                      recorded interaction
   expected request/               │                      against REAL provider
   response shape                  │                      code (with "provider
        │                          │                      states" seeding data)
        ▼                          ▼                              │
   generates pact.json  ──────────────────────────────────────────┘
                                   │
                          5. verification result
                             published back to broker
                                   │
                                   ▼
                    6. can-i-deploy(consumer v1.4, provider v2.1)?
                       → checks broker: has v2.1 verified v1.4's pact?
                       → yes: safe to deploy. no: BLOCK the deploy.
```
The key inversion versus integration testing: the provider never sees a mock of the consumer. The provider test runs against the *real* provider implementation, replaying interactions the consumer *actually recorded*, and the broker is the only thing that needs to know about every pairing.

## How it actually works

**Consumer side** (Python, `pact-python`, current stable line targets Pact Specification v3/v4):
```python
# untested sketch — consumer test using pact-python
import atexit
from pact import Consumer, Provider

pact = Consumer("OrderService").has_pact_with(
    Provider("InventoryService"), pact_dir="./pacts"
)
pact.start_service()
atexit.register(pact.stop_service)

def test_get_stock_level():
    expected = {"sku": "ABC123", "quantity": 42, "warehouse": "US-EAST"}
    (pact
     .given("product ABC123 exists with stock 42")   # provider state
     .upon_receiving("a request for stock level")
     .with_request("GET", "/inventory/ABC123")
     .will_respond_with(200, body=expected))

    with pact:
        result = inventory_client.get_stock("ABC123")  # real client code, hits pact mock server
        assert result["quantity"] == 42
```
This produces a `pact.json` file: a serialized list of interactions (request matchers, response matchers, and the provider state name `"product ABC123 exists with stock 42"`). Matching rules matter here — a naive pact asserting `quantity == 42` exactly is *too specific* and will break the moment real inventory changes; well-written pacts use type/shape matchers (`Matchers.like(42)`, meaning "an integer, don't care about the exact value") so the contract expresses structural compatibility, not a frozen fixture.

**Provider side** verifies against real code:
```python
# untested sketch — provider verification with pact-python Verifier
from pact import Verifier

verifier = Verifier(provider="InventoryService", provider_base_url="http://localhost:8080")

# provider states map string -> setup function that seeds the real DB
def setup_stock_exists(interaction, provider_state_params=None):
    db.insert_product("ABC123", quantity=42, warehouse="US-EAST")

success, logs = verifier.verify_with_broker(
    broker_url="https://pactbroker.internal.example.com",
    broker_username=os.environ["PACT_BROKER_USER"],
    broker_password=os.environ["PACT_BROKER_PASS"],
    provider_states_setup_url="http://localhost:8080/_pact/provider-states",
    publish_verification_results=True,
    provider_version=os.environ["GIT_SHA"],
)
```
The provider spins up its real HTTP server (in-process or in a test container), seeds state via the provider-states callback, and the Pact library replays every recorded consumer request against it, asserting the real response matches the matchers in the pact. Verification results are published back to the broker keyed by provider version.

**The deploy gate**, the part that actually prevents incidents:
```bash
pact-broker can-i-deploy \
  --pacticipant OrderService --version $ORDER_SVC_SHA \
  --pacticipant InventoryService --version $INVENTORY_SVC_SHA \
  --broker-base-url https://pactbroker.internal.example.com
# exit code 0 = safe, non-zero = block the CD pipeline
```
This is the mechanism that turns contract testing from "a nice test suite" into "an actual deploy safety gate" — CI/CD pipelines call `can-i-deploy` as a required step before promoting to any shared environment, and it correctly answers "has *this exact* provider version verified compatibility with *this exact* consumer version," which a green integration-test suite from last week cannot answer.

## Build it from scratch

The from-zero exercise: implement the two halves of Pact's core mechanism yourself, without the library, to internalize what the broker actually decides.
```python
# untested sketch — minimal CDC mechanism, no Pact library
import json, hashlib

def consumer_record(interactions: list[dict], out_path: str):
    """Consumer test writes what it expects, structurally not literally."""
    json.dump({"interactions": interactions}, open(out_path, "w"))

def provider_verify(pact_path: str, real_handler) -> bool:
    """Provider replays each interaction against the REAL handler function."""
    pact = json.load(open(pact_path))
    for i in pact["interactions"]:
        actual = real_handler(i["request"])
        if not shape_matches(actual, i["response"]):  # structural, not exact match
            print(f"BROKEN: {i['description']}")
            return False
    return True

def can_i_deploy(consumer_ver: str, provider_ver: str, verification_log: dict) -> bool:
    key = f"{consumer_ver}:{provider_ver}"
    return verification_log.get(key, {}).get("verified") is True
```
Running this against a deliberately-broken provider (rename a response field, change a status code) and watching `provider_verify` catch it — versus watching a mocked unit test on the consumer side pass regardless — is the exercise that makes the value concrete.

## How it's done in production

Real deployments add: the **Pact Broker/PactFlow** as a hosted service (not a local file store) with a **network graph UI** showing which consumer/provider version pairs are compatible; **webhooks** that trigger the provider's verification build automatically whenever a consumer publishes a new pact; **tags/branches** (`main`, `prod`) so `can-i-deploy` can ask "is this safe for prod" specifically; and **pending pacts** / **WIP pacts**, a feature that lets a consumer publish a pact for a not-yet-implemented interaction without failing the provider's existing verification build, which is what makes CDC adoption incremental rather than a big-bang cutover.

| Symptom | Cause | Fix |
|---|---|---|
| Provider verification build is green, but the actual API broke for a real consumer last week | Consumer never wrote a pact for the interaction that broke, or the pact used an exact-value matcher that happened to still pass | Audit pact coverage against actual traffic (some Pact setups now ingest real request logs to auto-suggest missing interactions); replace exact matchers with shape matchers |
| Provider verification build takes 20+ minutes and blocks every consumer's release train | Provider verifies against every historical pact version ever published, not just the ones still in use | Use `can-i-deploy` semantics and pact "pruning"/retention policies in the broker; only verify against pacts still tagged for active environments |
| Team adopted Pact, six months later half the pacts are stale and nobody trusts the broker | No ownership model — contract testing was bolted on without making `can-i-deploy` a hard CD gate | Make the broker query a mandatory, automated CD step, not an optional dashboard; a contract test that doesn't block a deploy decays into documentation nobody reads |
| A public-facing API team tries to adopt Pact with dozens of unknown external consumers | CDC assumes you can identify and get cooperation from every consumer to write pact tests; you cannot do this for a public API | Wrong tool — use OpenAPI-based contract validation, strict semantic versioning, and deprecation windows instead of consumer-driven contracts |
| Event-driven service (Kafka) breaks a downstream consumer despite HTTP contract tests being green | Pact (as classically used) covers synchronous HTTP; the break was in an Avro schema evolution | Add schema registry compatibility enforcement (BACKWARD/FORWARD/FULL mode) on the topic; this is a different mechanism from Pact and both are needed |

## Tradeoffs & when NOT to use it

- **Don't use consumer-driven contracts for public APIs with unknown or uncooperative consumers.** CDC requires the consumer to write and publish a pact; if you can't enumerate your consumers (a public REST API, a widely distributed SDK), use OpenAPI diffing and semantic versioning with deprecation windows instead.
- **Don't treat contract tests as a replacement for all integration or E2E testing.** A contract test proves the *shape* of an interaction is compatible; it does not prove the end-to-end business flow behaves correctly when three services are chained together with real data — that's still integration/E2E territory.
- **Don't adopt Pact without committing to `can-i-deploy` as a hard gate.** Contract tests that don't block a deploy are read by nobody after month two; this is the single most common reason Pact rollouts die.
- **Don't write pacts with exact-value matchers as a default.** Overly literal pacts turn into brittle snapshot tests that break on every legitimate data change and get muted rather than fixed — use shape/type matchers and reserve exact values for fields with real business meaning (a status enum, an error code).
- **Small team, one service, no cross-team boundary?** Contract testing has no target — this only pays for itself once there's an actual consumer/provider boundary owned by different teams or deploy cadences.

---

## Interview questions

### Q1 — What's the difference between contract testing and integration testing?
**Testing:** whether the candidate understands the actual mechanism, not just "they're both about testing services talking to each other."
**Answer:** Integration testing verifies your code against a copy of the dependency (stub, Testcontainers instance, mock) that you control and that can silently drift from the real thing. Contract testing verifies your code's expectations against the dependency's actual, currently deployed behavior, independently confirmed on both sides through a broker.
**Follow-up trap:** *"So does contract testing replace integration testing?"* — no, they catch different bug classes; a contract test won't tell you your SQL join is wrong, an integration test won't tell you the other team's provider silently changed a field name.

### Q2 — Explain consumer-driven contracts in your own words.
**Testing:** can they explain the inversion (consumer-first) and why it matters, not just recite "Pact is a tool."
**Answer:** The consumer states exactly what it needs from the provider as a versioned artifact (the pact); the provider must prove, against its real implementation, that it satisfies exactly that — not an idealized full spec, just what real consumers actually use. This avoids over-specifying a contract for behavior nobody depends on.
**Follow-up trap:** *"What happens if the provider changes something no pact covers?"* — nothing breaks the contract check, correctly, because CDC only protects what's proven to be depended upon; this is a real gap (undocumented but relied-upon behavior with no test) and a legitimate criticism of the approach.

### Q3 — Walk through what `can-i-deploy` actually checks.
**Answer:** It queries the broker for whether the specific provider version being deployed has a recorded, successful verification against the specific consumer version currently deployed (or being deployed) in the target environment — and vice versa. If no matching verification exists, or the last one failed, the gate blocks the deploy regardless of whether either side's own test suite is green.
**Follow-up trap:** *"What if the provider changed but never ran verification against this consumer's pact?"* — `can-i-deploy` returns false/blocks; this is the intended behavior, and the fix is to run verification (often triggered by a broker webhook when a new pact is published), not to bypass the gate.

### Q4 — Your provider verification test suite takes 25 minutes and is on the critical path for every deploy. Diagnose and fix.
**Answer:** Likely verifying against every pact ever published rather than only the versions currently relevant (deployed, or tagged for an active environment/branch). Use broker retention/pruning policies and tag-based verification (verify only against pacts tagged `prod` or `main`) to cut this down; also check whether provider-state setup (seeding a real DB per interaction) is the actual bottleneck versus the HTTP replay itself.
**Follow-up trap:** *"Would you just run verification less often, like nightly?"* — no, that reopens the exact race condition CDC exists to close (broken compatibility ships before it's caught); fix the verification speed, don't reduce its frequency on the deploy path.

### Q5 — A team wants to skip Pact and just diff OpenAPI specs instead. When is that the right call?
**Answer:** When the interesting compatibility question is purely structural (did a field get removed, did a type change) and consumers are numerous/unknown/uncooperative — OpenAPI diffing scales to public APIs in a way CDC cannot. It's the wrong call when the compatibility question is semantic (a field's *meaning* changed even though its type didn't, or a combination of fields implies a business rule the schema can't express) — that needs real consumer-recorded expectations.
**Follow-up trap:** *"Can you use both?"* — yes, and mature orgs do: OpenAPI/schema diffing as a fast, cheap first gate on every PR, CDC for the subset of internal, high-stakes service pairs where semantic compatibility matters.

### Q6 — How do you handle contract testing for asynchronous, event-driven interactions (Kafka)?
**Answer:** Classic Pact targets synchronous request/response; for events, use a schema registry (Confluent Schema Registry, AWS Glue Schema Registry) enforcing compatibility mode (BACKWARD: new schema can read old data; FORWARD: old schema can read new data; FULL: both) at publish time, rejecting incompatible schema registrations before they reach the topic. Pact does have message-pact support for this, but schema registry enforcement is the more common production mechanism for Kafka specifically.
**Follow-up trap:** *"What compatibility mode would you pick for a topic with slow consumers that can't redeploy quickly?"* — BACKWARD compatibility (new producer schema, old consumer code still works), because it decouples the producer's deploy from requiring an immediate consumer upgrade.

### Q7 — What's a "provider state" and why does it exist?
**Answer:** A named precondition (e.g., `"product ABC123 exists with stock 42"`) that the provider's verification test setup uses to seed real data before replaying the consumer's recorded request — without it, the provider has no way to make its real database/state match what the consumer's test assumed.
**Follow-up trap:** *"What if provider state setup requires a call to a third external system?"* — mock or stub only at that true external boundary during verification; the provider's own logic and data layer should still be real, or the verification isn't proving anything about the provider's actual behavior.

### Q8 — Why do exact-value matchers in a pact eventually get muted or deleted by the team?
**Answer:** Because they turn the contract into a frozen snapshot of one moment's data rather than a structural agreement — legitimate data changes (a new valid enum value, a changed but still-valid quantity) break the pact, and after enough false-positive failures the team either stops trusting Pact failures or deletes the assertion, defeating the point.
**Follow-up trap:** *"So should you never assert exact values?"* — assert exact values only where the value carries real contractual meaning (a fixed status enum, an error code, a required field's presence) — use type/shape matchers (`like()`, `eachLike()`, regex matchers) for everything else.

### Q9 — How would you roll out contract testing to an org of 40 microservices with no prior practice?
**Answer:** Start with the highest-incident-cost boundary (the pair that's caused the most recent production breaks), get one consumer/provider pair fully wired through the broker with `can-i-deploy` as a real CD gate, prove the incident-prevention value concretely, then expand by boundary criticality — not by mandating full coverage on day one, which produces exactly the "half-adopted, nobody trusts it" failure mode.
**Follow-up trap:** *"What if a provider team refuses to write verification tests?"* — this is an organizational, not technical, problem; CDC requires both sides to participate, and a provider that won't verify makes the practice worthless for that boundary — escalate it as a cross-team dependency risk, don't pretend the consumer's pact alone provides protection.

### Q10 — Staff-level: your org has both Pact and OpenAPI-based schema validation running, and they occasionally disagree — Pact says compatible, the OpenAPI diff says breaking. How do you reason about this?
**Answer:** They're checking different things and both can be simultaneously "correct": OpenAPI diffing flags a structural change (a field removed from the spec) that no consumer pact actually exercises, meaning it's a real breaking change for the *contract as documented* but not for any *actual consumer in production*. The right response depends on whether you trust the spec to be the source of truth (in which case the OpenAPI diff should block) or you trust CDC to represent real usage (in which case it's safe to proceed and update the spec) — the honest answer is this exposes a documentation/reality gap that should be fixed by writing a pact for the real dependency or removing the unused field from the spec, not by picking whichever gate is more convenient that day.
**Follow-up trap:** *"Which gate should be authoritative by default?"* — favor CDC for internal service pairs where you can enumerate consumers (it reflects reality); favor the schema/spec diff for anything with unknown consumers, where "nobody's using it yet" isn't a safe assumption.

---

## Red flags that fail you

- Describing Pact as "just another integration test" without naming the consumer-driven inversion.
- Not knowing what `can-i-deploy` does or why it's the part that actually prevents incidents.
- Proposing CDC for a public API with unenumerable consumers.
- Writing (or defending) exact-value matchers as the default without acknowledging the brittleness tradeoff.
- Treating contract testing and schema registry compatibility as the same mechanism.

## Cheat card

```
CDC = consumer records what it needs (pact file) -> provider verifies against
  REAL implementation -> broker reconciles who's compatible with whom.

PACT (2013, REA/Thoughtworks) = dominant CDC tool. Polyglot: JVM/JS/Python/
  Go/.NET/Ruby all read/write the same pact-file format.

can-i-deploy = the actual safety gate: "has THIS provider version verified
  THIS consumer version's pact?" Non-zero exit = block the deploy.

MATCHERS: use like()/eachLike()/regex (shape) not exact values, except for
  fields with real contractual meaning (status enum, error code).

PROVIDER STATE = named precondition string; provider test seeds real data
  to match before replaying consumer's recorded request.

WRONG for: public APIs w/ unknown consumers (use OpenAPI diff + semver
  + deprecation windows instead). Async events: use schema registry
  (BACKWARD/FORWARD/FULL compat), not classic Pact.

FAILURE MODE: Pact adopted without can-i-deploy as a hard CD gate ->
  pacts go stale in ~months, nobody trusts the broker.

Contract test != integration test: proves SHAPE compatibility against
  real deployed behavior, not end-to-end business-flow correctness.
```

## Sources
- [Introduction — Pact Docs](https://docs.pact.io/) — accessed 2026-07-26
- [Pact | Microservices testing made easy](https://pact.io/) — accessed 2026-07-26
- [PACT Contract Testing — Because Not Everything Needs Full Integration Tests, Microsoft ISE Developer Blog](https://devblogs.microsoft.com/ise/pact-contract-testing-because-not-everything-needs-full-integration-tests/) — accessed 2026-07-26
- [Consumer-Driven Contract Testing with Pact: Microservices QA Guide for 2026 — SQAExperts](https://www.sqaexperts.com/consumerdriven-contract-testing-with-pact-microservices-qa-guide-for-2026) — accessed 2026-07-26
- Robinson, I. — "Consumer-Driven Contracts: A Service Evolution Pattern" (2011), origin of the CDC pattern

## Changelog
- 2026-07-26 — created
