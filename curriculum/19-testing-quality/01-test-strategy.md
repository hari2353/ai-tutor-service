# Test Strategy: Pyramid vs Trophy, What to Test, What Never To

> **Track:** T19 Testing & Quality Engineering · **Time:** 2h · **Prereqs:** none
> **Module id:** `T19-test-strategy` · **Tags:** strategy, critical
> **Updated:** 2026-07-26

## The 30-second version

The test pyramid (many unit, some integration, few E2E) optimizes for speed and isolation; the testing trophy (static analysis, some unit, most integration, few E2E) optimizes for confidence per test written, because "the more your tests resemble how the software is actually used, the more confidence they give you" — Kent C. Dodds' framing, and the one that wins in most modern service architectures where the unit under test is rarely a pure function. Neither is a religion: pick pyramid-shaped ratios for a library or algorithm-heavy codebase where units are genuinely isolated and cheap to test in combination, and trophy-shaped ratios for a typical CRUD/API service where the interesting behavior lives at the boundary between your code and a database, queue, or another service. What you never test: framework code, trivial getters/setters, third-party library internals, and anything where the test would just re-assert the implementation line for line — those tests cost maintenance time and catch nothing a type checker or the library's own test suite didn't already catch. The actual skill being assessed is knowing which layer catches which class of bug and refusing to over-invest in the layer that's cheapest to write but weakest at catching real regressions.

## Why this gets asked

Because "how do you decide what to test" separates people who've internalized a slogan from people who've maintained a test suite for years and watched which tests actually caught real bugs before production versus which tests just added CI minutes and review friction. The interviewer has almost certainly inherited a suite with 90% unit coverage and constant production incidents, or the opposite — a suite where every commit touches twelve mock definitions — and wants to know if you'd repeat their mistake or diagnose it.

---

## Lineage: past → present → future

**What came before.** Mike Cohn's test pyramid (from *Succeeding with Agile*, 2009) formalized a shape that already existed informally: lots of fast unit tests, a smaller layer of integration tests, a thin layer of slow, expensive, brittle E2E/UI tests, sized inversely to their cost and flakiness. It was a genuine improvement over the pre-2000s norm of manual QA and all-UI-automation suites (`Selenium` scripts as the primary regression net), which were slow (minutes to hours per run), flaky (a CSS selector or timing change breaks dozens of tests), and gave weak localization of failure (a red E2E test tells you *something* broke, not *what*). The pain the pyramid solved was cost and flakiness at scale.

**Where it stands now.** The pyramid's weakness surfaced as codebases shifted toward service-oriented and API-heavy architectures: a "unit" in a thin controller calling three collaborators isn't meaningfully testable in isolation without mocking away all the actual behavior, so pyramid-shaped suites in these codebases accumulate thousands of unit tests that pass while the integration between components silently breaks — the classic "we shipped, tests were green, production paged" failure. Kent C. Dodds' testing trophy (2018) is the dominant counter-model in the JS/API-service world: static analysis (TypeScript/ESLint) catches an entire class of bugs for near-zero marginal cost per line, then a thick layer of integration tests (real HTTP calls into your app, real or `Testcontainers`-backed database, mocked only at the true external boundary) does most of the actual bug-catching, with unit tests reserved for genuinely complex pure logic (pricing engines, parsers, state machines) and E2E kept thin and reserved for the handful of critical user journeys. The live disagreement: teams building libraries, compilers, or algorithm-heavy systems (where the unit genuinely is the interesting boundary) still correctly run pyramid-shaped, and insisting on trophy-shaped ratios there is just as wrong as insisting on pyramid-shaped ratios for a REST CRUD service. There's also real disagreement about mutation testing's role here — treating line/branch coverage as the target metric regardless of shape is now recognized as actively counterproductive (see the coverage-mutation module), but not everyone has internalized that yet.
- Google's "Testing on the Toilet" and the *Software Engineering at Google* book (Winters, Manshreck, Wright, 2020) independently converged on similar guidance: prefer tests that don't know about implementation details, and treat a test suite that requires touching many tests for one behavioral change as a design smell, not a testing-thoroughness win.

**Where it's heading.** LLM-assisted test generation is shifting the marginal cost of writing more tests toward zero, which removes "tests are expensive to write" as a reason to under-test, but doesn't remove "tests are expensive to *maintain and read when they fail*" — so the real skill is shifting from "can I write this test" to "should this test exist, and will a human trust its failure." Expect continued growth of trophy-shaped and "test where the risk lives" strategies over pure pyramid dogma, with contract testing and consumer-driven contracts (separate module) picking up the slack that pure integration testing leaves at service boundaries; this is a confident, already-happening trend, not speculation.

---

## Mental model

```
           PYRAMID                          TROPHY
        (isolated units)              (confidence-first)
             /\                           _________
            /  \  E2E (few)              |  E2E    |  (few)
           /----\                        |_________|
          / INTEG\                       |         |
         /--------\                      |  INTEG  |  (most)
        /   UNIT   \                     |_________|
       /____________\                    |  UNIT   |  (some)
                                          |_________|
                                          | STATIC  |  (all, ~free)
                                          |_________|
```
The pyramid's shape encodes "cost and speed decide the ratio." The trophy's shape encodes "bug-catching-power-per-test decides the ratio," and static analysis sits at the base because it's the only layer that's essentially free per line of code and catches an entire category (type errors, unreachable code, unused imports) before a test even runs.

## How it actually works

**The actual decision procedure**, in order:
1. **Can static analysis catch this class of bug?** Type mismatches, null-safety violations, unreachable branches, unused variables — route these to the type checker/linter, not a test. A test that only re-verifies "this function returns a string" duplicates what `mypy --strict` or TypeScript already guarantees at zero runtime cost.
2. **Is the behavior a pure function of its inputs, with meaningful internal complexity?** Pricing calculators, parsers, DP-based schedulers, regex-heavy validators — these deserve real unit tests, and this is exactly where property-based testing (Hypothesis, `fast-check`) earns its cost, because example-based tests only ever cover the cases you thought of.
3. **Does the behavior only manifest when your code talks to a real collaborator** (DB, cache, queue, another service)? This is the trophy's fat middle — integration tests against `Testcontainers`-backed real Postgres/Redis/Kafka catch the class of bug that mocked-unit tests structurally cannot: a wrong SQL join, an off-by-one in a Redis TTL, a serialization mismatch that only appears with the real driver.
4. **Is this a top-5 revenue-critical user journey that only fails when the whole system is wired together** (login → checkout → payment)? E2E, and only a handful — Playwright/Cypress suites with more than ~30-50 E2E specs almost always have a flakiness and maintenance problem, not a coverage problem.
5. **Is this cross-team, cross-repo behavior at an API boundary?** Contract tests (Pact), not integration tests — integration tests only prove your side works against a *copy* of the other side, contract tests prove compatibility against the other side's *actual* behavior, verified independently on both ends.

**What never to test, concretely:**
- Third-party library internals (`requests.get` actually making an HTTP call — that's the library's test suite's job).
- Trivial delegation (`def full_name(self): return f"{self.first} {self.last}"` — a test here only re-asserts the implementation).
- Framework wiring that a smoke test already proves (every Django URL resolves to *a* view — fine as one test, not per-URL).
- Anything where writing the test required more mocking setup than the assertion itself — that ratio is a signal the design, not the test, is wrong (the unit has too many collaborators; consider whether the code needs restructuring before it needs a test).

**Numbers that matter:** a well-run trophy-shaped API service suite typically runs 200-2,000 integration tests in under 3-5 minutes in CI using `Testcontainers` with reused container instances (see integration-testing module); a pyramid-shaped suite with 5,000+ unit tests and heavy mocking commonly runs in under 60 seconds but still misses 30-40% of production incidents in post-mortems that trace back to "the unit tests were green, the integration was wrong" (this ratio is reported consistently across teams that do blameless postmortems and tag root cause by test-layer-that-should-have-caught-it).

## Build it from scratch

The exercise that actually proves understanding isn't writing more tests, it's classifying an existing, uncategorized test suite and re-deriving the ratio it *should* have:

```python
# untested sketch — a simple triage script for an existing suite
import ast
from pathlib import Path
from collections import Counter

def classify_test_file(path: Path) -> str:
    src = path.read_text()
    tree = ast.parse(src)
    mock_calls = sum(1 for node in ast.walk(tree)
                      if isinstance(node, ast.Call)
                      and getattr(node.func, "attr", "") in ("Mock", "patch", "MagicMock"))
    assert_calls = sum(1 for node in ast.walk(tree)
                        if isinstance(node, ast.Call)
                        and getattr(node.func, "attr", "").startswith("assert"))
    if mock_calls == 0:
        return "integration-or-e2e"
    if mock_calls > assert_calls:
        return "over-mocked-unit"  # smell: more mock setup than assertions
    return "unit"

report = Counter(classify_test_file(p) for p in Path("tests/").rglob("test_*.py"))
print(report)
# a healthy trophy-shaped suite: integration-or-e2e >> unit, over-mocked-unit near zero
```
This is deliberately crude, but running something like it across a real codebase and confronting the actual ratio — versus the ratio you assumed — is the exercise that changes how you argue for test strategy in a design review.

## How it's done in production

| Symptom | Cause | Fix |
|---|---|---|
| CI green, production incident traces to a component-boundary bug | Pyramid-shaped suite with heavy mocking hides the exact boundary that broke | Add integration tests at that boundary using real dependencies (Testcontainers), not more unit tests |
| Every small refactor breaks 40+ unit tests | Tests assert on implementation structure (exact mock call sequences, private method calls) instead of observable behavior | Rewrite tests to assert on outputs/side effects through the public interface; this is the single biggest maintenance-cost driver in unit-heavy suites |
| E2E suite takes 45+ minutes and is flaky 15% of the time | Too many E2E specs covering paths integration tests could cover faster and more reliably | Cut E2E to the top 10-20 critical journeys; push the rest down to integration |
| New engineers avoid writing tests for a module | Existing tests in that module require excessive mock setup to add one case | Treat this as a design smell first — too many collaborators, or a test that shouldn't need this much setup — before adding more tests in the same style |
| Coverage dashboard shows 95% but bugs keep escaping | Coverage measures execution, not verification — see coverage-mutation module | Track mutation score alongside coverage, and audit whether high-coverage tests actually assert meaningful behavior |

## Tradeoffs & when NOT to use it

- **Don't apply trophy-shaped ratios to a library, SDK, or algorithm-heavy codebase** — if the actual product surface *is* the function signature (a JSON parser, a rate-limiting library, a DP solver), a pyramid shape with heavy unit coverage and property-based testing is correct, and forcing integration-heavy testing there adds slowness without adding confidence.
- **Don't treat "trophy > pyramid" as universal** — a team that's never had a production incident traced to integration gaps and instead suffers from slow, flaky CI has the opposite problem and needs *fewer*, faster, more isolated tests, not more integration tests.
- **Don't chase 100% of any layer** — the marginal 5th percentile of coverage in any layer is almost always the least valuable code to test (error-handling for conditions that can't occur, defensive code for already-validated inputs) and the effort is better spent finding untested *behaviors*, not untested *lines*.
- **Don't let "we don't have time to write tests" excuse skipping the layer that catches the most expensive class of bug for your architecture** — this is a genuine tradeoff under deadline pressure, and the honest answer is to name explicitly which layer you're skipping and why, not to silently ship less confidence than the team believes it has.

---

## Interview questions

### Q1 — Pyramid or trophy: which do you use and why?
**Testing:** whether the candidate has an actual decision procedure or just a favorite diagram.
**Answer:** Depends on where the unit boundary actually sits. For a typical service with a thin controller and real external dependencies, trophy-shaped (integration-heavy) catches more real bugs per test written. For a library or algorithm-heavy codebase where the function signature is the product, pyramid-shaped with property-based testing is correct.
**Follow-up trap:** *"Give me a specific example where pyramid is wrong for a service."* — a controller test suite with 200 unit tests that mock the database, cache, and downstream service; every test passes on a broken SQL join because the mock never had the join logic to break.

### Q2 — What do you explicitly refuse to write tests for?
**Testing:** judgment about maintenance cost versus bug-catching value.
**Answer:** Third-party library internals, trivial delegation methods, framework wiring already proven by one smoke test, and anything where the mock setup outweighs the assertion.
**Follow-up trap:** *"Isn't 100% coverage the safe default?"* — no; coverage measures execution not verification, and forcing tests onto trivial code adds maintenance burden with zero bug-catching value; the counter-signal (mutation score) exposes this directly.

### Q3 — Your team has 90% unit coverage and monthly production incidents from integration bugs. Diagnose.
**Answer:** The suite is pyramid-shaped in an architecture where the interesting behavior lives at component boundaries — heavy mocking hides exactly the bugs that matter. Add an integration layer with real dependencies via Testcontainers at those boundaries; coverage percentage won't move the needle, layer allocation will.
**Follow-up trap:** *"Would you just add more unit tests targeting those files?"* — no, more unit tests with the same mocking style reproduce the same blind spot; the fix is a different layer, not more of the same layer.

### Q4 — How many E2E tests is too many?
**Answer:** No fixed number, but past roughly 30-50 specs for most services, E2E suites become a flakiness and maintenance tax rather than a confidence source; the fix is triaging to the top revenue-critical journeys and pushing the rest to integration tests that run faster and fail less spuriously.
**Follow-up trap:** *"What if the E2E suite is fast and stable at 200 specs?"* — then it's working, and the "keep E2E thin" guidance is a heuristic responding to the common failure mode (slow, flaky), not a hard rule; state the actual reasoning rather than reciting the number.

### Q5 — What's wrong with a unit test that mocks every collaborator?
**Answer:** It proves the unit calls its collaborators in the expected sequence, not that the system behaves correctly when those collaborators are real — a wrong SQL query, a serialization mismatch, or an actual network failure mode is invisible to a suite built this way.
**Follow-up trap:** *"So should we never mock?"* — mock at true external boundaries (a third-party paid API, a non-deterministic clock/random source) where a real call is undesirable or impossible in CI; don't mock your own database or your own internal collaborators when a real instance is cheap to run via Testcontainers.

### Q6 — A refactor that changes internal structure but not behavior breaks 40 tests. What's wrong?
**Answer:** The tests assert on implementation details (specific method call sequences, private state, mock call counts) instead of observable outputs and side effects. Rewriting to test through the public interface fixes both the immediate breakage and the ongoing maintenance tax.
**Follow-up trap:** *"Is that always the tests' fault?"* — not always; if the refactor genuinely changed a documented contract, some breakage is correct. The tell is whether the *behavior* visible to a caller changed, not whether the internal call graph changed.

### Q7 — How does static analysis fit into the testing trophy, and why is it "free"?
**Answer:** Static analysis (type checkers, linters) runs on every keystroke/save in an IDE and on every commit in CI, catching an entire category of defects (type mismatches, unreachable code, null-safety violations) before any test executes, at effectively zero marginal cost per line once the tooling is set up.
**Follow-up trap:** *"What does static analysis definitely not catch?"* — logic errors, wrong business rules, incorrect algorithm behavior, and anything that's type-correct but semantically wrong (e.g., adding tax twice, off-by-one in a loop bound) — these require actual tests.

### Q8 — When would you deliberately choose a pyramid shape for a brand-new service?
**Answer:** When the service is a computation-heavy library or SDK (a pricing engine, a scoring model, a parser) where the interesting complexity is genuinely internal and pure, and external dependencies are minimal or absent — the unit *is* the meaningful boundary.
**Follow-up trap:** *"What if that service later grows external dependencies (a cache, a DB)?"* — re-evaluate the shape; a service that started as a pure library and grew integrations needs a corresponding shift toward more integration-layer tests, and clinging to the original pyramid shape as the codebase evolves is the actual failure mode teams fall into.

### Q9 — What's the relationship between test strategy and mutation testing?
**Answer:** Test strategy decides which layer to invest in; mutation testing is the tool that tells you whether the tests you wrote in that layer actually verify behavior or just execute code. High coverage with low mutation score in the "confidence-heavy" layer (integration, in a trophy shape) means the strategy is right but the execution is weak.
**Follow-up trap:** *"So mutation testing replaces the pyramid/trophy decision?"* — no, it's orthogonal; mutation testing measures test *quality* within a layer, not which layer deserves investment.

### Q10 — A staff engineer asks you to justify cutting your E2E suite from 80 specs to 15. What's your argument?
**Answer:** Identify the 15 as the actual revenue-critical, cross-system journeys (login, checkout, core workflow) and show that the remaining 65 either duplicate integration-test coverage or test paths with negligible business impact relative to their flakiness and runtime cost; back it with the CI time and flake-rate numbers, not a general principle.
**Follow-up trap:** *"What if one of the cut 65 catches a real regression a month later?"* — accept that trade explicitly: an occasional missed edge case caught late is often cheaper than a permanently slow, low-trust CI pipeline that engineers route around; the counter-argument is legitimate if that specific journey is high-risk enough to justify the cost, and a senior answer names that tradeoff rather than pretending it doesn't exist.

---

## Red flags that fail you

- Reciting "70/20/10" or any fixed ratio as if it applies universally regardless of architecture.
- Treating coverage percentage as equivalent to test quality.
- Claiming trophy always beats pyramid, or vice versa, without naming the architecture that decides it.
- Being unable to name a single thing they deliberately don't test.
- Describing E2E suites as inherently bad rather than naming the specific failure mode (flakiness, slowness) that makes thin E2E the right default.

## Cheat card

```
PYRAMID (Cohn, 2009): unit >> integration >> E2E. Optimizes for SPEED/COST.
  Right for: libraries, algorithm-heavy code, pure-function-shaped units.

TROPHY (Kent C. Dodds, 2018): static >> integration >> unit > E2E.
  Optimizes for CONFIDENCE PER TEST. "Resembles how software is used."
  Right for: typical API/service architectures, boundary-heavy code.

DECISION ORDER: static analysis -> pure-logic unit tests -> integration
  (real deps via Testcontainers) -> contract tests (cross-service) -> thin E2E (top 10-20 journeys)

NEVER TEST: 3rd-party internals, trivial delegation, framework wiring
  (1 smoke test suffices), tests where mock setup > assertion size

SMELL: refactor breaks many tests w/o behavior change -> tests assert
  implementation, not behavior -> rewrite through public interface

NUMBERS: trophy-shaped 200-2000 integration tests, ~3-5min CI w/ Testcontainers
  reuse. E2E >30-50 specs -> flakiness tax, not confidence gain.
  90% coverage + monthly integration incidents = WRONG LAYER, not more tests.

Coverage != quality. Pair with mutation score (see coverage-mutation module).
```

## Sources
- [Write tests. Not too many. Mostly integration. — Kent C. Dodds](https://kentcdodds.com/blog/write-tests) — accessed 2026-07-26
- [The Testing Trophy and Testing Classifications — Kent C. Dodds](https://kentcdodds.com/blog/the-testing-trophy-and-testing-classifications) — accessed 2026-07-26
- [Test Pyramid vs Testing Trophy — Baytech Consulting](https://www.baytechconsulting.com/blog/test-pyramid-vs-testing-trophy-whats-the-difference) — accessed 2026-07-26
- Cohn, M. — *Succeeding with Agile* (2009), origin of the test pyramid
- Winters, Manshreck, Wright — *Software Engineering at Google* (2020), Ch. 11-12 on testing culture

## Changelog
- 2026-07-26 — created
