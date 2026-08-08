# Unit Testing Done Right: Doubles, Fixtures, Parametrize, Property-Based

> **Track:** T19 Testing & Quality Engineering · **Time:** 2.5h · **Prereqs:** T19-test-strategy
> **Module id:** `T19-unit-testing` · **Tags:** unit
> **Updated:** 2026-07-26

## The 30-second version

A unit test verifies one behavior of one unit in isolation from its collaborators, and "isolation" is achieved with test doubles chosen deliberately by role: a **stub** returns canned data, a **fake** is a lightweight working implementation (in-memory DB), a **spy** records calls for later assertion, and a **mock** asserts expected interactions during the test — conflating these (calling everything "a mock") is the single most common sloppiness signal. Fixtures set up the arrange phase and should be scoped to the smallest lifetime that's still correct (function > class > module > session, in pytest terms) because over-broad fixture scope causes cross-test state leakage that manifests as order-dependent failures. Parametrization (`pytest.mark.parametrize`, JUnit `@ParameterizedTest`) turns N near-duplicate test functions into one test function plus a table of cases, which is both less code and — more importantly — forces you to enumerate the actual equivalence classes instead of picking three arbitrary examples. Property-based testing (Hypothesis, `fast-check`, QuickCheck) inverts the entire model: instead of asserting `f(3) == 9`, you assert a property that must hold for *all* generated inputs (`f(x) >= 0 for all x`), and the framework searches for a counterexample and shrinks it to a minimal failing case — this catches the input you never thought to write by hand, and it's the highest-leverage technique in this module that most engineers have never used.

## Why this gets asked

Because unit testing is the layer everyone claims to already know, and the interviewer wants to see whether "I write unit tests" means disciplined use of doubles and equivalence-class thinking, or a pile of `assert result == expected` calls copy-pasted with different numbers. The production failure behind this question is almost always the same: a suite with thousands of green tests that used the wrong test double (a mock instead of a fake, asserting call sequences instead of outcomes) and consequently didn't catch a real regression, or a suite so entangled with fixture state that adding one new test broke three unrelated ones.

---

## Lineage: past → present → future

**What came before.** Early unit testing (JUnit, 1997-1998, from Kent Beck and Erich Gamma) formalized xUnit-style setUp/tearDown and assertion-based verification, replacing ad hoc `print`-and-eyeball checking and manual QA scripts. The pain it solved was regression safety net cost: before automated unit tests, verifying "did this change break anything" required either manual retesting (slow, inconsistent) or trusting code review alone (misses runtime behavior entirely). Mock objects as a distinct concept were formalized by Steve Freeman, Nat Pryce, Tim Mackinnon, and Joe Walnes ("Mock Roles, Not Objects," 2004), specifically to address a problem plain stubs couldn't: verifying that a unit *collaborates correctly* with something it can't observably return a value from (e.g., "did we call `sendEmail`," not just "what does `sendEmail` return").

**Where it stands now.** The industry has mostly converged on Gerard Meszaros's test double taxonomy (*xUnit Test Patterns*, 2007) as the correct vocabulary — dummy, stub, spy, mock, fake — even though most engineers still say "mock" for all five, which is a real, ongoing terminology sloppiness that correlates with actually choosing the wrong double for the job. The live disagreement is "classicist vs mockist" (London school vs Detroit/Chicago school): classicists (Kent Beck, Martin Fowler) prefer real collaborators or fakes wherever feasible and reserve mocks for true external boundaries, asserting on state/outcomes; mockists (the Freeman/Pryce "Growing Object-Oriented Software" camp) verify interactions extensively, asserting on the conversation between objects. In practice, most production codebases lean classicist by necessity — mockist-heavy suites are exactly the ones that break on every refactor because they assert on *how* something happened, not *what* happened. Property-based testing (QuickCheck, Haskell, 1999-2000; Hypothesis for Python, 2013) has moved from a niche functional-programming technique to mainstream tooling with first-class pytest integration, but adoption still lags well behind example-based testing because generating good input strategies requires more upfront thought than writing three examples.

**Where it's heading.** LLM-assisted test generation is making example-based test *volume* nearly free, which paradoxically increases the value of property-based testing and mutation testing as the filters that catch what volume alone doesn't: an LLM asked to write unit tests will happily generate ten examples that all exercise the same code path and miss the actual edge case, exactly the failure mode property-based testing is designed to catch by construction. Expect continued growth of property-based testing specifically as a counterbalance to AI-generated example bloat — this is a reasoned prediction, not yet a dominant industry pattern.

---

## Mental model

```
                    UNIT UNDER TEST
                    /      |       \
              collab-A  collab-B  collab-C
                 |          |         |
              [DUMMY]   [STUB]    [FAKE]      <- state-verification (classicist)
                                  or
                                [SPY]/[MOCK]  <- interaction-verification (mockist)

DUMMY: passed but never used (fills a required parameter)
STUB:  returns canned data, no assertions made on it
SPY:   records what was called, asserted AFTER the fact
MOCK:  pre-programmed with expectations, fails the test itself if violated
FAKE:  a real, working, lightweight implementation (in-memory dict as a "DB")
```
The decision that matters: **assert on outcomes through fakes/stubs whenever a working substitute is cheap to build; reserve mocks for verifying calls to true external systems** (payment gateway, email sender) where there's no observable return value to assert on and the interaction itself *is* the behavior.

## How it actually works

### Choosing the right double

```python
# untested sketch
# STUB: canned response, we don't care how many times it's called
class StubPriceService:
    def get_price(self, sku: str) -> float:
        return 9.99

# FAKE: real behavior, in memory — the classicist's preferred default
class FakeOrderRepository:
    def __init__(self):
        self._orders = {}
    def save(self, order):
        self._orders[order.id] = order
    def get(self, order_id):
        return self._orders.get(order_id)

# SPY: records calls, asserted after
class SpyEmailSender:
    def __init__(self):
        self.sent = []
    def send(self, to, subject):
        self.sent.append((to, subject))

def test_order_confirmation_sends_one_email():
    email = SpyEmailSender()
    place_order(sku="X", price_service=StubPriceService(), email_sender=email)
    assert len(email.sent) == 1
    assert email.sent[0][0] == "customer@example.com"

# MOCK: expectations set up-front, verified by the framework itself
from unittest.mock import Mock
def test_payment_gateway_charged_correct_amount():
    gateway = Mock()
    charge_customer(amount=42.00, gateway=gateway)
    gateway.charge.assert_called_once_with(amount=42.00)
```
The FakeOrderRepository is doing real work — it's not "mocked," it's a working substitute, and tests against it survive refactors that change *how* orders are persisted internally as long as `save`/`get` semantics hold. The Mock in the payment example is justified because the actual behavior under test — "did we call the gateway correctly" — has no other observable side effect to assert against.

### Fixture scoping (pytest terms, translates directly to JUnit `@BeforeEach`/`@BeforeAll` and Go `TestMain`)

```python
# untested sketch
import pytest

@pytest.fixture(scope="function")  # fresh for every test — default, safest
def order():
    return Order(id=1, items=[])

@pytest.fixture(scope="module")    # shared across a file — faster, riskier
def db_connection():
    conn = connect_to_test_db()
    yield conn
    conn.close()

@pytest.fixture(scope="session")   # shared across the whole run — fastest, riskiest
def docker_postgres():
    container = PostgresContainer("postgres:16")
    container.start()
    yield container
    container.stop()
```
The rule: **scope as narrow as correctness allows.** Session-scoped fixtures (a real Testcontainers Postgres instance) are appropriate for expensive-to-start, cheap-to-reset resources (truncate tables between tests, don't restart the container). Function-scoped fixtures are mandatory for anything with mutable state that a previous test could have altered — the classic bug is a module-scoped fixture returning a shared mutable object, and test B passes only because test A happened to run first and left it in the right state; this manifests as tests that pass in isolation but fail in a different run order, a smell worth naming by name (order-dependent test) because "flaky" undersells that it's a real correctness bug in the test, not randomness.

### Parametrization forces equivalence-class thinking

```python
# untested sketch
import pytest

@pytest.mark.parametrize("input_str,expected", [
    ("", False),                    # empty string — boundary
    ("   ", False),                 # whitespace-only — easy to miss
    ("a@b.com", True),              # minimal valid
    ("a@b", False),                 # missing TLD
    ("a"*64 + "@example.com", True),# local-part length boundary (RFC 5321: 64 octets)
    ("a"*65 + "@example.com", False), # one over the boundary
])
def test_email_validation(input_str, expected):
    assert is_valid_email(input_str) == expected
```
The value isn't fewer lines of code, it's that writing the table *forces* enumerating boundary conditions (empty, whitespace, exactly-at-limit, one-over-limit) that ad hoc example tests routinely skip.

### Property-based testing: the highest-leverage technique here

```python
# untested sketch
from hypothesis import given, strategies as st

@given(st.lists(st.integers()))
def test_sort_is_idempotent(lst):
    once = sorted(lst)
    twice = sorted(once)
    assert once == twice

@given(st.lists(st.integers(), min_size=1))
def test_sort_preserves_length_and_elements(lst):
    result = sorted(lst)
    assert len(result) == len(lst)
    assert sorted(result) == sorted(lst)   # multiset equality regardless of order proof method
    assert all(result[i] <= result[i+1] for i in range(len(result)-1))
```
Hypothesis generates hundreds of random lists (including adversarial ones: empty, single-element, all-duplicates, negative numbers, very long) and, on failure, **shrinks** the counterexample to the smallest list that still fails — if your sort breaks on `[3, 1, -2]`, Hypothesis reports something close to the minimal failing case, not the original 200-element random list it happened to find it in. This is the mechanical reason property-based testing catches bugs example-based testing misses: it doesn't rely on the test author's imagination for what to try.

## Build it from scratch

The exercise: take an existing example-based test suite for one function and (1) classify every double used by Meszaros's taxonomy, (2) convert at least one to a property-based test, (3) audit fixture scope for hidden shared state.

```python
# untested sketch
def is_valid_email(s: str) -> bool:
    if not s or s.isspace():
        return False
    if "@" not in s:
        return False
    local, _, domain = s.partition("@")
    if not local or not domain or "." not in domain:
        return False
    if len(local) > 64:  # RFC 5321 local-part limit
        return False
    return True

# property: validation is deterministic and total (never raises) for any string input
from hypothesis import given, strategies as st

@given(st.text())
def test_is_valid_email_never_raises(s):
    is_valid_email(s)  # just proving it doesn't crash on arbitrary text — a real, common bug class

@given(st.text())
def test_is_valid_email_is_deterministic(s):
    assert is_valid_email(s) == is_valid_email(s)
```
The "never raises" property looks trivial but catches a genuinely common bug class: unhandled exceptions on unexpected input shapes (unicode, null bytes, extremely long strings) that hand-picked examples never happen to include.

## How it's done in production

| Symptom | Cause | Fix |
|---|---|---|
| Tests pass alone, fail in CI or in a different order | Shared mutable state from a fixture scoped broader than test lifetime requires | Narrow fixture scope to function-level, or make module/session-scoped fixtures reset state explicitly between tests |
| Refactor with no behavior change breaks many tests | Mockist-style tests asserting exact call sequences/internal collaborators instead of outcomes | Convert to fakes + outcome assertions for anything not a true external boundary |
| A hand-picked-example suite has 100% coverage but a boundary bug ships | Example tests only cover cases the author thought of | Add property-based tests for pure functions with a clear invariant (idempotence, round-trip, ordering) |
| New test requires 15 lines of mock setup for a 2-line assertion | Unit under test has too many collaborators (a design smell, not a testing gap) | Consider whether the class needs decomposing before adding more tests in the current style |
| CI test suite runtime dominated by fixture setup (spinning up a container per test) | Fixture scope too narrow for an expensive-to-start resource | Move to session-scoped fixture with per-test cleanup (truncate, not recreate) |

## Tradeoffs & when NOT to use it

- **Don't mock your own internal collaborators by default** — if a fake is cheap to build (in-memory repository, in-memory queue), it survives refactors better and catches more real bugs than a mock asserting call sequences.
- **Don't property-test everything** — property-based testing pays off for pure functions with a clear, statable invariant (sorting, serialization round-trips, parser idempotence); it's a poor fit for testing UI wiring or one-off business rules with no general property ("if the user's plan is Enterprise and it's a Tuesday, apply this specific discount" has no elegant property, just an example).
- **Don't parametrize past the point of readability** — a 40-row parametrize table that mixes unrelated concerns is worse than three well-named, focused tests; parametrize when the cases are genuinely the same logical test with different data.
- **Don't reach for session-scoped fixtures for anything with meaningfully different state per test** — the speed win isn't worth chasing order-dependent bugs that cost hours to debug later.

---

## Interview questions

### Q1 — Define the five test doubles (Meszaros's taxonomy) with an example each.
**Testing:** whether "mock" is used precisely or as a catch-all.
**Answer:** Dummy (passed but never used, fills a required param), stub (returns canned data, unasserted), spy (records calls, asserted after the fact), mock (pre-programmed expectations, fails the test itself on violation), fake (a real, lightweight working implementation, e.g. in-memory repo).
**Follow-up trap:** *"Which would you use to verify an email was sent?"* — a spy, generally: record what was called and assert on it afterward reads more naturally and survives minor implementation reordering better than a strict mock expectation, unless the exact call arguments/order genuinely matter to the contract.

### Q2 — Classicist vs mockist: which are you, and why does it matter?
**Answer:** Classicist — prefer real collaborators or fakes, assert on state/outcomes, reserve mocks for true external boundaries. It matters because mockist-heavy suites (asserting on interaction sequences) break on refactors that don't change observable behavior, which is the single biggest ongoing maintenance cost in unit-heavy suites.
**Follow-up trap:** *"When is mockist correct?"* — when the behavior under test genuinely is the interaction itself and there's no other observable effect — verifying a payment gateway was charged the right amount, where the "real" side effect (money moving) can't happen in a test.

### Q3 — What's wrong with a test that passes alone but fails when run after another test?
**Testing:** fixture scope understanding.
**Answer:** Shared mutable state from a fixture scoped broader than needed — a module- or session-scoped fixture returning a mutable object that a prior test altered. This is a real correctness bug in the test suite, not randomness; the fix is narrowing scope or resetting state explicitly.
**Follow-up trap:** *"Isn't this just 'flaky tests,' inherently unfixable noise?"* — no, calling it flaky undersells that it's a deterministic bug (order-dependent state), fully diagnosable by running tests in isolation vs. in the suspect order, and fully fixable by correct fixture scoping.

### Q4 — Explain property-based testing and how shrinking works.
**Answer:** Instead of asserting `f(x) == y` for chosen examples, you assert an invariant that must hold for all generated inputs (`sorted(sorted(x)) == sorted(x)`); the framework (Hypothesis, QuickCheck) generates hundreds of inputs including adversarial ones, and on failure, shrinks the counterexample toward the smallest input that still fails, so you debug against a minimal repro instead of the original large random input.
**Follow-up trap:** *"Give an invariant that's hard to state for a real business rule."* — tiered discount logic with arbitrary date/plan-specific rules often has no clean general property; that's a signal property-based testing isn't the right tool there, and example-based/parametrized tests are correct instead.

### Q5 — When would you deliberately avoid parametrizing a test?
**Answer:** When the "cases" aren't actually the same logical test — mixing unrelated concerns into one parametrize table trades a few extra lines of code for a much harder-to-read failure (which row failed, why, is it even testing the same thing) — three well-named separate tests communicate better.
**Follow-up trap:** *"Isn't less code always better?"* — no; test code optimizes for readability of failures and intent, not line count; a parametrize table should represent one enumerated equivalence class, not several unrelated ones glued together.

### Q6 — Your new test needs 15 lines of mock setup for a 2-line assertion. What do you do?
**Answer:** Treat it as a design smell in the unit under test (too many collaborators) before adding more tests in the same style — consider decomposing the class/function so the behavior under test has fewer dependencies to fake out.
**Follow-up trap:** *"What if decomposing isn't feasible this sprint?"* — extract a test builder/helper to centralize the setup once, and flag the design debt explicitly rather than let every subsequent test re-pay the same setup cost silently.

### Q7 — What's a dummy object and why does it matter to distinguish it from a stub?
**Answer:** A dummy is passed to satisfy a signature but never actually used or asserted on (e.g., a logger interface passed to a constructor that never gets called on the tested path). Distinguishing it from a stub matters because asserting behavior on a dummy is a sign the test doesn't understand what's actually exercised — and dead dummy parameters sometimes reveal the unit has an unnecessary dependency at all.
**Follow-up trap:** *"Isn't this pedantic vocabulary?"* — the vocabulary forces the question "what am I actually verifying here," and conflating dummy/stub/mock in practice correlates with picking the wrong verification strategy (asserting call counts on something that's actually a dummy, for instance).

### Q8 — How do you unit test a function with a non-deterministic dependency (current time, random number)?
**Answer:** Inject the dependency (clock, RNG) rather than calling `datetime.now()`/`random()` directly inside the function, then supply a fixed/fake value in the test — a fake clock returning a fixed timestamp, or a seeded/fake RNG. This is one of the few cases where injecting a stub for a "true external, non-deterministic boundary" is correct even under a classicist philosophy.
**Follow-up trap:** *"What if the function is deep in a call chain and threading the clock through everywhere is ugly?"* — that's a legitimate cost/benefit call; a thread-local or context-based clock override (careful with test isolation) is a common pragmatic compromise, but state explicitly that it trades some purity for ergonomics.

### Q9 — What's the actual mechanical difference between a stub and a mock, given both "return canned data"?
**Answer:** A stub returns canned data and is never itself the subject of an assertion — you assert on what the *unit under test* did with that data. A mock is pre-programmed with expectations about how it will be called, and the mock itself fails the test if those expectations aren't met — the mock is asserting, not just responding.
**Follow-up trap:** *"Show me code where using a mock where a stub was appropriate causes a real problem."* — a `Mock()` used just to feed a return value, with `assert_called_once()` tacked on unnecessarily, breaks the test the moment an unrelated, harmless refactor changes call count (e.g., caching adds a second no-op call) even though the actual behavior (the returned data being used correctly) is unaffected.

### Q10 — Property-based test finds a failing case after shrinking: `f([0])` fails. How do you use this in debugging versus a hand-written example test failure?
**Answer:** The shrunk case is already close to minimal, so you skip the manual "let me try to reproduce with a smaller input" step that a hand-written failing example (often large, real-world data) usually requires — you can typically go straight to reasoning about why `f([0])` specifically breaks the invariant.
**Follow-up trap:** *"What if the shrunk case looks nothing like real production data and seems like an edge case no one cares about?"* — the invariant you stated (idempotence, ordering, round-trip) is either genuinely required for correctness (fix the code) or was mis-stated (the property was too strong/wrong, fix the test) — both outcomes are informative, and dismissing the failure without deciding which is a common mistake.

---

## Red flags that fail you

- Calling every test double "a mock," including fakes and stubs.
- Asserting on internal call sequences/private state as the default rather than the exception.
- Session-scoped fixtures returning mutable objects with no reset between tests.
- Never having used property-based testing, or dismissing it as "not applicable to my codebase" without a specific reason.
- Parametrize tables mixing unrelated test concerns for the sake of fewer lines.

## Cheat card

```
DOUBLES (Meszaros, xUnit Test Patterns 2007):
  DUMMY: unused, fills signature      STUB: canned return, unasserted
  SPY: records calls, asserted after  MOCK: pre-set expectations, self-asserting
  FAKE: real lightweight impl (in-memory DB) -- classicist default

CLASSICIST (Beck/Fowler): assert state/outcomes, mocks only at TRUE external boundary
MOCKIST (Freeman/Pryce): assert interactions/conversation -- breaks on refactors more

FIXTURE SCOPE: function > class > module > session (pytest)
  narrower = safer default. Session-scope ONLY for expensive+resettable resources.
  order-dependent test failure = shared mutable state bug, not "flakiness"

PARAMETRIZE: forces enumerating equivalence classes (empty, boundary, over-boundary)
  don't mix unrelated concerns into one table

PROPERTY-BASED (Hypothesis/QuickCheck/fast-check):
  assert an INVARIANT for ALL generated inputs, not one example
  framework SHRINKS failing case to minimal repro automatically
  best for: idempotence, round-trip, ordering invariants in pure functions
  poor fit for: one-off business rules with no general property

SMELL: 15 lines mock setup / 2 line assertion -> too many collaborators,
  fix the design before adding more tests in the same style
```

## Sources
- Meszaros, G. — *xUnit Test Patterns: Refactoring Test Code* (2007), the double taxonomy
- Freeman, S. & Pryce, N. — *Growing Object-Oriented Software, Guided by Tests* (2009), mockist school
- [How to Build Property-Based Testing with Hypothesis — OneUptime](https://oneuptime.com/blog/post/2026-01-30-how-to-build-property-based-testing-with-hypothesis/view) — accessed 2026-07-26
- [Top Python Testing Frameworks in 2026 — TestGrid](https://testgrid.io/blog/python-testing-framework/) — accessed 2026-07-26

## Changelog
- 2026-07-26 — created
