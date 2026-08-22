# Integration Tests: Testcontainers, Real DBs, Seeding, Isolation

> **Track:** T19 Testing & Quality Engineering · **Time:** 2.5h · **Prereqs:** T19-unit-testing
> **Module id:** `T19-integration-testing` · **Tags:** integration, critical
> **Updated:** 2026-07-26

## The 30-second version

An integration test verifies that your code correctly talks to a *real* collaborator — a real Postgres, a real Redis, a real Kafka broker — rather than a mock or an in-memory fake, because the class of bug that matters here (wrong SQL, a driver serialization quirk, a real network timeout) is structurally invisible to a mocked unit test. `Testcontainers` is the dominant modern mechanism: it spins up the real dependency in Docker per test run (or per suite, reused), giving you production-parity behavior without a shared, stateful test environment that different test runs stomp on each other in. The two things that make or break this layer are **seeding** (deterministic, minimal test data created per test, not a giant shared fixture database) and **isolation** (each test either gets its own container/schema, or truncates and reseeds between tests — never assumes a clean database as a starting condition it didn't create itself). Done right, a Testcontainers-backed suite of a few hundred to a couple thousand tests runs in 3-5 minutes in CI by reusing one container across the whole suite (Testcontainers' "singleton container" pattern) and isolating via per-test transactions rolled back at teardown, rather than paying container startup cost (typically 1-3 seconds for Postgres, more for Kafka) per test.

## Why this gets asked

Because integration testing is where "the tests were green and it still broke in prod" incidents concentrate, and the interviewer wants to know if the candidate has actually run a real dependency in CI and hit its specific failure modes — flaky container startup, port collisions, state leaking between tests, tests that pass locally with a warm Docker cache and time out cold in CI — versus someone who's only ever mocked the database and calls it "integration testing" because the word integration is in the test file name.

---

## Lineage: past → present → future

**What came before.** Before Testcontainers (2015, Java-first, expanded to most major languages by the early 2020s), integration testing against real dependencies meant either a shared, long-lived test database (the "staging DB" anti-pattern: tests fight over state, one team's test data corrupts another's, and a test that passed yesterday fails today because someone else's test left rows behind) or an in-memory substitute pretending to be the real thing (H2 pretending to be Postgres, `fakeredis` pretending to be Redis) — the classic pain being that the substitute's behavior *diverges* from the real thing exactly where it matters: Postgres-specific SQL (window functions, `ON CONFLICT`, JSONB operators) simply doesn't run against H2, and subtle differences in isolation-level or locking behavior between the fake and the real system hide real bugs until production.

**Where it stands now.** Testcontainers-style ephemeral, code-defined, real-dependency-in-Docker integration testing is now the consensus best practice across the industry for services with real infrastructure dependencies, precisely because it eliminates both failure modes at once: every test run gets a fresh real instance, defined in code and versioned alongside the tests, with no shared mutable state between runs or teams. The live disagreement is over container lifecycle scope: per-test containers (safest isolation, slowest — full startup cost per test) versus per-suite/session containers with per-test cleanup via transaction rollback or truncation (much faster, requires discipline to avoid cross-test leakage). Most mature teams land on session-scoped containers with function-scoped transactional isolation for relational databases specifically because Postgres transaction rollback is essentially free (microseconds) compared to container restart (seconds), while accepting that non-transactional stores (Kafka, most NoSQL) need explicit truncate/reset logic instead.

**Where it's heading.** Cloud-native "ephemeral environment per PR" patterns (spinning up a full stack, not just one dependency, per pull request) are extending the Testcontainers idea from "one dependency in a unit-adjacent test" to "the whole system, disposable, per change" — this is real and growing at well-resourced teams, though it remains expensive enough (compute cost, provisioning time) that it's not yet universal outside larger organizations. Testcontainers Cloud and similar remote-execution offerings (running the containers on shared infrastructure rather than the CI runner's local Docker daemon) are addressing the CI-resource-constraint version of this problem, letting resource-limited CI runners still get real-dependency integration tests.

---

## Mental model

```
  SHARED STAGING DB (old, bad)          TESTCONTAINERS (current default)
  ___________________                   Test run 1: [fresh Postgres:16 container]
 |  many teams write |                             |-- seed minimal fixture data
 |  and read the same |                             |-- run tests in transactions
 |  mutable rows      |                             |-- rollback after each test
 |____________________|                             |-- container torn down (or reused)
   test B fails because                  Test run 2: [fresh Postgres:16 container]
   test A left dirty state                          |-- completely independent
```
The core shift: isolation moves from "hope nobody else's test touched this row" to "every test run gets its own real, disposable instance of the actual thing it depends on."

## How it actually works

### Testcontainers, singleton pattern (Java, but the pattern is identical everywhere)

```java
// untested sketch
class OrderRepositoryIntegrationTest {
    // Singleton container: started once, shared across the whole test class/suite
    static final PostgreSQLContainer<?> postgres =
        new PostgreSQLContainer<>("postgres:16")
            .withDatabaseName("test_db")
            .withReuse(true);  // reuse across test runs on the same machine, not just same JVM run

    static { postgres.start(); }

    @BeforeEach
    void seed() {
        // minimal, deterministic fixture per test — not a giant shared dataset
        jdbcTemplate.update("INSERT INTO orders (id, sku, qty) VALUES (1, 'X', 3)");
    }

    @AfterEach
    void cleanup() {
        jdbcTemplate.update("TRUNCATE orders CASCADE");  // or wrap the whole test in a rolled-back transaction
    }

    @Test
    void findsOrderById() {
        Order order = repository.findById(1);
        assertThat(order.getSku()).isEqualTo("X");
    }
}
```

### Python (pytest + Testcontainers-python)

```python
# untested sketch
import pytest
from testcontainers.postgres import PostgresContainer

@pytest.fixture(scope="session")
def pg_container():
    with PostgresContainer("postgres:16") as pg:
        yield pg

@pytest.fixture()
def db_session(pg_container):
    engine = create_engine(pg_container.get_connection_url())
    conn = engine.connect()
    trans = conn.begin()          # transactional isolation: near-zero cost per test
    yield conn
    trans.rollback()              # every test's writes vanish, no truncation needed
    conn.close()

def test_order_repository_saves_and_retrieves(db_session):
    repo = OrderRepository(db_session)
    repo.save(Order(id=1, sku="X", qty=3))
    assert repo.get(1).sku == "X"
```
The transaction-rollback pattern is the single highest-leverage isolation technique for relational databases: a real Postgres, real SQL, real constraints — but each test's writes are invisible to every other test and cost roughly the same as an in-memory operation because nothing is actually committed to disk in a durable sense that needs cleanup.

### Non-transactional stores need explicit reset

```python
# untested sketch — Kafka/Redis don't have free transactional rollback
@pytest.fixture()
def redis_client(redis_container):
    client = redis.Redis.from_url(redis_container.get_connection_url())
    yield client
    client.flushdb()   # explicit reset — no free rollback available here
```

### Seeding strategy: minimal, explicit, per-test — never a shared golden dataset

The anti-pattern is a `fixtures.sql` with 500 rows loaded once for the whole suite; tests then implicitly depend on specific rows existing with specific values, and adding a new test that needs slightly different data risks breaking three other tests that assumed the old shape. The correct pattern: each test creates exactly the rows it needs, in the test itself or a small helper factory, so the test is self-documenting about its actual dependencies and immune to other tests' data needs changing.

```python
# untested sketch — factory pattern for readable, self-contained seeding
def make_order(**overrides):
    defaults = dict(id=1, sku="X", qty=3, status="pending")
    defaults.update(overrides)
    return Order(**defaults)

def test_cancelled_order_cannot_be_shipped(db_session):
    order = make_order(status="cancelled")
    db_session.save(order)
    with pytest.raises(InvalidStateError):
        ship(order)
```

## Build it from scratch

A minimal from-zero integration test harness that proves the isolation model, without a real framework:

```python
# untested sketch
import subprocess, time, psycopg2

def start_postgres_container():
    subprocess.run(["docker", "run", "-d", "--name", "test-pg",
                     "-e", "POSTGRES_PASSWORD=test", "-p", "55432:5432",
                     "postgres:16"], check=True)
    for _ in range(30):
        try:
            conn = psycopg2.connect(host="localhost", port=55432,
                                     user="postgres", password="test")
            conn.close()
            return
        except psycopg2.OperationalError:
            time.sleep(0.5)
    raise RuntimeError("postgres never became ready")

def run_test_in_transaction(test_fn):
    conn = psycopg2.connect(host="localhost", port=55432, user="postgres", password="test")
    conn.autocommit = False
    try:
        test_fn(conn)
    finally:
        conn.rollback()   # the whole point: nothing persists past this test
        conn.close()
```
This is deliberately primitive, but writing the readiness-poll loop and the rollback-based isolation by hand once is what makes "Testcontainers just handles this" click as a specific, understandable mechanism rather than magic.

## How it's done in production

| Symptom | Cause | Fix |
|---|---|---|
| Tests pass locally, fail/time out in CI | Container startup slower/cold on CI runner, no readiness wait, or Docker-in-Docker resource limits | Poll for actual readiness (not a fixed sleep), increase CI runner resources, use Testcontainers Cloud for resource-constrained runners |
| Test order affects pass/fail | Non-transactional store (Kafka, Redis, some NoSQL) not reset between tests | Explicit teardown per test (flushdb, delete topics/consumer groups, drop-and-recreate) |
| Suite runtime dominated by container startup | New container spun up per test instead of reused | Use session/module-scoped container + per-test transaction rollback or targeted truncation |
| Port conflicts when running suites in parallel | Fixed port mappings across parallel test workers | Let Testcontainers assign random host ports (default behavior); never hardcode `-p 5432:5432` |
| Flaky test that only fails ~1% of the time under parallel CI load | Shared container across parallel workers without per-worker isolation (shared DB/schema) | Give each parallel worker its own schema/database within the shared container, or its own container entirely |

## Tradeoffs & when NOT to use it

- **Don't reach for a full Testcontainers-backed integration suite for pure-logic code** — if there's no real external dependency, this is unit-testing territory (see the unit-testing module); adding a container here adds runtime cost for zero additional confidence.
- **Don't use a shared, long-lived staging database for automated tests** even if it's tempting for speed — the state-leakage and cross-team interference cost compounds as the team grows, and it's exactly the anti-pattern Testcontainers exists to replace.
- **Don't fake a database engine with a different one (H2-for-Postgres) and call it integration testing** — divergent SQL dialect behavior and locking/isolation semantics hide real bugs specifically in the area integration tests are supposed to catch.
- **Don't run these in tight inner-loop TDD cycles if they're not fast** — if a Testcontainers suite takes 30+ seconds to start, keep a smaller, faster subset runnable in the tight edit-test loop and run the full suite in CI/pre-push, or invest in the reuse patterns above to get it fast enough for the inner loop too.

---

## Interview questions

### Q1 — Why is a mocked-database unit test not a substitute for a real-database integration test?
**Answer:** A mock only proves your code calls the driver as expected; it can't catch a wrong SQL join, an actual constraint violation, a serialization/type mismatch with the real driver, or a genuine transaction/locking interaction — all classes of bugs that only manifest against the real engine.
**Follow-up trap:** *"Would an in-memory fake database (H2 for Postgres) catch these?"* — partially, but SQL dialect divergence (window functions, `JSONB`, `ON CONFLICT`) and different isolation/locking semantics mean the fake can still pass while the real engine fails, which is why Testcontainers running the *actual* engine is the stronger choice.

### Q2 — Explain the transactional-rollback isolation pattern and why it's faster than truncation.
**Answer:** Wrap each test in a database transaction that's rolled back at teardown instead of committed; the writes are fully real within the test (constraints enforced, queries see them) but invisible to every other test, and rollback is a near-free operation compared to truncating tables or restarting a container.
**Follow-up trap:** *"Does this work for testing code that itself manages transactions (commits mid-test)?"* — it breaks down if the code under test calls its own commit, since a nested/savepoint structure is needed (or the test framework must use `SAVEPOINT`s), and getting this wrong is a common source of subtly leaking state between tests.

### Q3 — A test suite is flaky specifically under parallel CI execution but stable when run serially. Diagnose.
**Answer:** Parallel workers are likely sharing one container/database/schema without per-worker isolation, so concurrent writes from different tests race or collide. Fix: give each parallel worker its own schema or its own container instance.
**Follow-up trap:** *"Would adding retries mask this?"* — yes, and that's exactly the wrong fix — retries hide a real isolation bug rather than fixing it, and the bug will eventually manifest as data corruption or a genuinely wrong assertion under just the right timing.

### Q4 — What's wrong with a shared `fixtures.sql` loaded once for the whole test suite?
**Answer:** Tests end up implicitly depending on specific rows/values existing, so any test needing slightly different data risks silently breaking other tests that assumed the old shape — the dependency is invisible in the test itself, only visible by reading the shared fixture file.
**Follow-up trap:** *"Isn't per-test seeding slower?"* — usually negligibly so if seeding uses lightweight factories and the underlying container/transaction is already fast; the readability and isolation win outweighs the marginal per-test seed cost in nearly all cases.

### Q5 — Postgres via Testcontainers takes 1-3 seconds to start. How do you keep a suite of 1,000 integration tests fast?
**Answer:** Start one container per session/suite (not per test), and isolate each test via a rolled-back transaction rather than a fresh container — this amortizes the 1-3 second startup cost across the whole suite instead of paying it 1,000 times.
**Follow-up trap:** *"What if the code under test needs a fresh schema, not just a rolled-back transaction (e.g., testing a migration)?"* — that's a legitimate exception; migration tests specifically may need a fresh container/schema per test or per small group of tests, and it's correct to accept the slower runtime for that narrower suite rather than force everything into the same isolation pattern.

### Q6 — How do you integration-test against Kafka, given it has no transactional rollback like Postgres?
**Answer:** Explicit teardown per test — delete the topic and recreate it, or use unique topic names per test and clean up after, or reset consumer group offsets; there's no free rollback, so isolation must be built deliberately rather than assumed.
**Follow-up trap:** *"Would you use a single shared topic across tests with unique message keys to avoid recreating topics?"* — a legitimate optimization if topic creation is the bottleneck, but it shifts the isolation burden to consumer-group/offset management and requires the same discipline; state clearly what isolation mechanism you're relying on either way.

### Q7 — Your integration suite passes locally but times out in CI. What's your triage order?
**Answer:** First check whether the test is polling for actual readiness (not a fixed `sleep(2)`) since CI runners are commonly slower/colder than local Docker; then check CI runner resource limits (CPU/memory throttling containers); then check for Docker-in-Docker overhead if CI itself runs in a container.
**Follow-up trap:** *"Is increasing the sleep duration a valid fix?"* — no, a longer fixed sleep just moves the flakiness threshold rather than removing it; a proper readiness poll (retry a real connection/health check with backoff, bounded by a generous but finite timeout) is the correct fix.

### Q8 — When is integration testing the wrong layer, even for a service with real external dependencies?
**Answer:** For pure business logic that doesn't touch the dependency at all — routing that logic through a slow, real-database-backed integration test adds runtime cost for confidence a fast unit test already provides.
**Follow-up trap:** *"How do you decide where the boundary is inside a single request-handling function?"* — separate the pure logic (validation, calculation) from the I/O (repository calls) at the code level if possible, so each can be tested at its appropriate layer instead of forcing everything through the slowest layer capable of exercising it.

### Q9 — Explain Testcontainers' "singleton container" pattern and its main risk.
**Answer:** One container instance is started once (often via a static initializer or session-scoped fixture) and reused across the whole test class or suite, avoiding repeated container startup cost. The main risk is state leakage between tests if isolation (transaction rollback, truncation, unique schemas) isn't applied rigorously on top of the shared container.
**Follow-up trap:** *"What's `withReuse(true)` specifically for?"* — it allows the container to persist across separate test *runs* on the same machine (not just within one JVM/process run), useful for fast local iteration, but requires opting in explicitly since it changes cleanup semantics (the container isn't torn down when the test process exits) and needs care in CI where a fresh environment per run is usually preferred.

### Q10 — How would you integration-test a service that depends on three different real systems (Postgres, Redis, Kafka) without the suite becoming unmanageably slow?
**Answer:** Start all three as session-scoped containers once per suite, apply the cheapest correct isolation per system (transaction rollback for Postgres, flush/reset for Redis, unique topics or explicit cleanup for Kafka), and keep the number of tests exercising all three simultaneously to the genuinely cross-system behaviors — push single-system logic down to that system's own faster integration tests.
**Follow-up trap:** *"What if the cross-system behavior is inherently the interesting bug (e.g., a distributed transaction/outbox pattern across Postgres and Kafka)?"* — that's exactly where this layer earns its cost; don't shrink coverage of genuinely cross-system correctness (e.g., outbox-pattern delivery guarantees) just to save runtime — that's the bug class integration tests at this layer exist to catch.

---

## Red flags that fail you

- Calling a test "integration" when every dependency is mocked.
- Using a shared, long-lived staging database as the test target.
- Substituting a different database engine (H2 for Postgres) and treating it as equivalent.
- Fixed `sleep()` calls instead of readiness polling for container startup.
- No isolation strategy named at all when asked how tests avoid interfering with each other.

## Cheat card

```
INTEGRATION TEST = real collaborator (real DB/queue/cache), not mock/fake
  catches: wrong SQL, driver serialization, real locking/constraint behavior

TESTCONTAINERS: spin up real dep in Docker, per-test or per-suite
  session-scoped container + per-test TRANSACTION ROLLBACK = fast + isolated
    (Postgres rollback ~free; avoids container-per-test startup cost, 1-3s each)
  non-transactional stores (Kafka/Redis): explicit reset (flushdb, recreate topic)
    -- no free rollback available

SEEDING: minimal, per-test, factory-based. NEVER a shared fixtures.sql loaded once
  -- shared fixture data = invisible cross-test dependency, breaks silently

ISOLATION FAILURE MODES:
  flaky ONLY under parallel CI -> shared container/schema across workers,
    give each worker its own schema or container
  passes locally, times out CI -> fixed sleep instead of readiness poll,
    or CI runner resource limits
  Kafka/Redis order-dependent -> no rollback, needs explicit teardown

ANTI-PATTERN: H2-for-Postgres or any fake-engine substitute -- SQL dialect
  and isolation/locking semantics diverge exactly where it matters

WHEN NOT TO USE: pure logic with no real dependency (that's unit-test territory)
```

## Sources
- [Testcontainers Playwright Module — testcontainers.com](https://testcontainers.com/modules/playwright/) — accessed 2026-07-26
- [Testcontainers Tutorial: Getting Started with Playwright — Collabnix](https://collabnix.com/testcontainers-and-playwright/) — accessed 2026-07-26
- Testcontainers official documentation (singleton container pattern, reuse)

## Changelog
- 2026-07-26 — created
