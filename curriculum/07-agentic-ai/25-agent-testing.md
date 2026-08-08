# Testing Agents: Unit, Integration, Regression, Golden Trajectories, CI Gates

> **Track:** T07 Agentic AI · **Time:** 3.0h · **Prereqs:** none · **Updated:** 2026-08-01
> **Module id:** `T07-agent-testing` · **Tags:** testing,critical

## The 30-second version

Testing an agent works because most of an agent is deterministic code wearing a nondeterministic hat: the loop, the tool dispatch, the permission engine, the compactor, and the context builder are ordinary functions you can unit-test at speed against a scripted fake model, and that's where most of the bugs actually live. The layer that genuinely can't be pinned down is the model's own output, and the engineering answer to that is deterministic replay — record a real model response once into a cassette, replay it offline forever after, so your fast suite runs in seconds and costs nothing. Above that sits golden-trajectory testing, which asserts the tool-call sequence, the final state, and the cost/step envelope of a run, and deliberately does not assert exact wording, because wording varies run to run and locking it produces a suite that's flaky for no reason connected to correctness. Because the model layer is still genuinely stochastic even at temperature 0 in practice, you track pass rate as a distribution across N reruns with an explicit flakiness budget, not a single pass/fail, and you gate merges on that distribution crossing a threshold, not on one green run. The named failure this whole structure exists to prevent is the suite that stays green while the agent silently regresses: a golden trajectory so loose it asserts nothing meaningful, or a cassette so stale it no longer reflects the real API, both of which produce the same observable symptom — passing CI and rising production error rate with no bisectable cause.

## Why this gets asked

Because you've shipped remediation work under a deadline and know the difference between "tests pass" and "the system is actually correct," and testing agents is where that distinction gets hardest to hold onto, since the thing under test genuinely doesn't return the same output twice. The interviewer has usually watched a team either give up on testing agents entirely ("it's nondeterministic, we can't unit test it") or over-invest in brittle string-matching assertions that break on every prompt tweak and get disabled one by one until the suite is decoration. They want to know whether you'll separate the deterministic 80% of the system from the genuinely stochastic 20%, test each appropriately, and design a CI gate that catches real regressions without crying wolf on every PR — because a suite that cries wolf gets its alerts muted, which is the same failure mode as a guardrail with too high a false-positive rate.

---

## Lineage: past → present → future

**What came before.** Early LLM application testing inherited directly from single-turn NLG evaluation: give the model a prompt, compare the output to a reference string or grade it with a judge, done. That was a reasonable fit for single-shot classification or summarization, where the input/output relationship is close to a pure function. As soon as teams wrapped models in tool-calling loops (2023 onward, per `T07-agent-loop-from-scratch`), that same outcome-only habit got applied to something structurally different — a multi-step process with sixteen ways to reach a plausible-looking wrong answer — and it missed the actual failure surface every time: an agent that called `create_refund(amount=500)` instead of `create_refund(amount=50)`, then wrote a summary claiming success, looked identical to a correct run under an outcome-only check that only reads the final text (`T08-agent-eval` develops this failure mode in depth). The parallel pain on the engineering side was cost and speed: hitting a real model API on every test run made a CI suite slow, flaky, and expensive enough that teams either shrank it to a token handful of smoke tests or stopped running it on every PR.

**Where it stands now.** Two separate disciplines converged on the same architecture from different directions. From software testing came the **test pyramid inverted for agents**: most tests live at the bottom (deterministic unit tests against a scripted fake model, at the speed and cost of ordinary code), a middle layer stubs the model but exercises real tool dispatch and harness logic, and a thin top layer runs real end-to-end evals against a live or recorded model, because that layer is slow and expensive and should only prove what the lower layers structurally cannot. From integration testing came **cassette-based deterministic replay** (the pattern is a direct descendant of `vcr.py` and Ruby's VCR gem for HTTP): record a real API interaction once into a stored file, replay it in every subsequent run with all external calls blocked, so the same test suite that took real API calls in record mode runs in milliseconds and for free in replay mode thereafter. From ML evaluation came **golden trajectories** — a labeled reference path through a task, scored on tool-call sequence and end-state rather than surface text — now standard enough that Docker's Cagent project and multiple observability vendors (LangSmith, Arize Phoenix) ship trajectory capture and replay as first-class features rather than a bespoke harness. The live disagreement is where the LLM-judge layer belongs: some teams score full trajectories holistically with an LLM judge because it catches things deterministic assertions can't (a technically correct but rude tool-failure recovery); others insist on decomposing into deterministic per-step checks wherever possible, because a judge grading a multi-thousand-token trace has its own reliability ceiling (`T08-llm-as-judge`) and stacks a second source of noise on top of the agent's own.

**Where it's heading.** High confidence: **replay-driven regression testing becomes the default CI shape** for any team running agents at more than toy scale, because the alternative (hitting a live model on every PR) doesn't survive contact with a normal-sized test suite's runtime and cost. Medium confidence: **golden-trajectory construction shifts from hand-authored to semi-automated**, recording real successful production runs and having humans lightly edit them into canonical goldens, rather than writing them from scratch — this closes the gap between what your eval set covers and what production traffic actually looks like, and it's actively being built rather than settled. Medium confidence: **durable-execution checkpointing becomes part of the testing story, not just the runtime story** — if a run is checkpointed (`T07-langgraph-durable`), you can replay from any intermediate state to isolate exactly which step diverged from a golden trajectory, instead of re-running the whole task to reproduce a failure. Speculative, flag it: fully automated golden-trajectory grading with no human review loop at all; current tooling still leans on a human editing pass to keep goldens canonical rather than trusting automated curation end to end.

---

## Mental model

```
              THE TEST PYRAMID, INVERTED FOR A NONDETERMINISTIC TOP LAYER

    ┌─────────────────────────────────────────────────────────────┐
    │  E2E / EVAL SUITE          real or recorded model, live run  │  slow, $$,
    │  golden trajectories, pass^k across N reruns, run in CI      │  small N
    ├─────────────────────────────────────────────────────────────┤
    │  INTEGRATION               stubbed model via CASSETTE replay │  fast, free,
    │  real tool dispatch, real harness code, scripted responses   │  runs on
    │                                                               │  every push
    ├─────────────────────────────────────────────────────────────┤
    │  UNIT                      no model at all                   │  instant,
    │  permission engine, budgets, compactor invariants, schema    │  most bugs
    │  validation, dispatch — ordinary deterministic code           │  live HERE
    └─────────────────────────────────────────────────────────────┘

    THE CASSETTE PATTERN (borrowed from vcr.py / HTTP integration testing)
    ────────────────────────────────────────────────────────────────────
    RECORD MODE (once, deliberately):
      test → real model API → response saved to cassette.yaml
    REPLAY MODE (every CI run, forever after):
      test → cassette.yaml → same response, no network call, no cost,
             no flakiness from the model itself
    STALE CASSETTE = a real risk: the recorded response no longer matches
      what the CURRENT api/schema/tool would actually return

    GOLDEN TRAJECTORY: assert the SHAPE, not the WORDS
    ────────────────────────────────────────────────────────────────────
      ASSERT:  tool-call sequence (fuzzy: right tools, reasonable order)
               final state (the DB row changed, the email queue has 1 item)
               cost/step count within an envelope
      DO NOT ASSERT: exact response wording -- this is the #1 cause of
               tests that are flaky for reasons that have nothing to do
               with whether the agent is actually correct
```

The one thing to internalize: **the nondeterminism is smaller than it looks, and it's isolated to one layer.** Everything below the model call is exactly as testable as any other backend system. Treat the model call itself as the one seam that needs special handling (cassettes for speed, distributions for correctness), and the rest of your agent testing strategy is just good engineering practice applied honestly.

---

## How it actually works

### Unit tests for tools and pure functions

Tools and harness logic are ordinary code and get ordinary tests: a tool's business logic tested with mocked dependencies exactly like any other function; the permission engine tested table-driven against `(principal, tool, args) → allow|deny|ask` fixtures with no model in the loop at all; budget and stop-condition logic tested with an injected fake clock; the compactor tested for the specific invariant that `messages[0]` and the open-items list survive every compaction (`T07-harness-engineering` covers the harness side of this in depth — this module's angle is that these are the highest-value, cheapest tests you'll write, and they should be the large base of the pyramid, not an afterthought next to flashy eval scores).

### Deterministic replay: the backbone of a fast suite

Record a real model interaction once — the request sent and the response received — into a cassette file (YAML or JSON), then replay it on every subsequent test run with all real network calls to the model blocked. In record mode the test suite behaves exactly like a live integration test; in replay mode it's fully offline, deterministic, and fast enough to run on every commit.

```python
# untested sketch - illustrates the cassette pattern, not a specific library
import json, os

class Cassette:
    def __init__(self, path: str, mode: str = "replay"):
        self.path, self.mode = path, mode
        self._recorded = json.load(open(path)) if os.path.exists(path) else []
        self._calls = []

    def model_call(self, messages, tools):
        if self.mode == "record":
            resp = real_model_client.create(messages=messages, tools=tools)
            self._recorded.append({"request": messages, "response": resp})
            return resp
        # replay: match by call index, not by re-hashing the request verbatim --
        # exact-match replay breaks on any harmless prompt reformatting
        idx = len(self._calls)
        self._calls.append(True)
        if idx >= len(self._recorded):
            raise AssertionError(
                f"Cassette exhausted at call {idx}. Re-record: "
                f"the agent under test made more model calls than the fixture has."
            )
        return self._recorded[idx]["response"]

    def save(self):
        json.dump(self._recorded, open(self.path, "w"), indent=2)
```

Why this is the backbone and not just a nice-to-have: a suite of 200 harness-level tests, each needing one to five model calls, at even 1-2 seconds of real API latency per call, is 5-15 minutes of wall-clock time and real money on every PR. The same suite against cassettes runs in single-digit seconds for free. That difference determines whether the suite runs on every commit (cassettes) or gets relegated to a nightly job people ignore (live calls) — and a suite that doesn't run on every commit doesn't catch regressions before they merge, which defeats the point.

**The real risk with this pattern is cassette staleness**: a cassette recorded against an older tool schema, an older system prompt, or an older model version can silently diverge from what the live system would actually do, and a stale cassette makes a broken integration look tested. Mitigate this the way you'd mitigate stale fixtures anywhere: re-record on any schema or prompt change (not just any code change), and run a smaller live-call smoke suite periodically (nightly, or gated on release) specifically to catch drift the cassettes can't see by construction.

### Integration tests with a stubbed model

One level above cassette-driven unit tests: exercise the *real* loop, the *real* tool registry, and the *real* permission engine, with a scripted or cassette-backed model standing in for the live one. This is where you test things like "does a denied tool call actually produce an observation the loop continues from" or "does the loop correctly stop after a scripted no-tool-call response" — behavior that spans several components and can't be verified by unit-testing each one in isolation.

### Golden trajectories: what to assert, what not to assert

A golden trajectory is a labeled reference for one task: the tool calls expected (in a reasonable order, not necessarily byte-identical), the end state the task should produce, and a cost/step envelope.

**Assert:**
- **Tool-call sequence**, fuzzy-matched: did it call roughly the right tools, in a reasonable order, not necessarily an exact sequence match to the golden. A run that calls `search` then `create_ticket` instead of the golden's `search` → `check_duplicate` → `create_ticket` may still be a legitimate alternate path if `check_duplicate` wasn't actually necessary for this input.
- **Final state**, checked against reality, never the agent's own summary: did the database row actually change, is there actually one item in the email queue, does the file actually exist on disk. Grading the agent's self-reported "I've updated the record" instead of the record itself certifies a failure as a pass (`T08-agent-eval` names this failure mode directly).
- **Cost and step count**, as a bounded envelope: an agent that reaches the right final state by taking 40 steps and $2 of tokens when the golden does it in 6 steps and $0.05 is not shippable even though the outcome matches — this needs its own assertion, not a footnote.

**Do not assert:**
- **Exact response wording.** The model will phrase the same correct action differently run to run, and locking wording produces a suite that fails constantly for reasons uncorrelated with correctness — this is the single most common cause of an agent test suite getting disabled test-by-test until it's decorative.
- **An exact, rigid tool-call sequence with zero tolerance for equivalent alternate paths**, unless the task genuinely has only one correct sequence (rare).

### Regression suites and the eval-set-as-test-suite pattern

Once you have a golden trajectory format, the natural next step is treating your evaluation set as your regression test suite: every task in the eval set is a test case, run on every meaningful change (a prompt edit, a tool schema change, a harness config change, a model version bump), with the same golden-trajectory assertions. This is the direct answer to "how do you know a harness change didn't silently break something the demo doesn't cover" — you re-run the whole eval set, not just the three scenarios someone remembered to manually re-check. The overlap with `T08-agent-eval` is real and deliberate: that module owns the *scoring methodology* (trajectory scoring, pass^k, tau-bench-style benchmarks); this module owns the *engineering practice* of wiring that scoring into a CI-gated, cassette-backed, fast-running test suite that a team actually runs on every change rather than occasionally by hand.

### Flakiness budgets: running N times with a pass threshold

Even at temperature 0, real-world agent runs are not perfectly deterministic (tool timing, upstream API variance, and non-greedy decoding in some serving configurations all introduce variance), and tau-bench-style benchmarks make this unavoidable to ignore: pass^1 (any success in one attempt) can be dramatically higher than pass^8 (all 8 of 8 repeated attempts succeeding) on the identical task, with published results showing pass^8 dropping below 25% in retail-domain tasks even for capable models (`T08-agent-eval`). The engineering response is a **flakiness budget**: define an explicit pass threshold over N reruns (e.g., "8 of 10 reruns must pass for this golden task to count as passing this build") rather than treating a single run as ground truth, and track pass-rate-over-N as a tracked metric per task over time, not just a pass/fail gate on the day of the PR. A task whose pass rate at N=10 is trending down release over release is telling you something a single green run would hide entirely.

### CI gates that block a merge, and their runtime cost

The realistic CI shape has three tiers, matching the pyramid: unit tests (seconds, run on every push, block every merge), cassette-backed integration tests (tens of seconds to a couple of minutes for a few hundred cases, run on every push, block every merge), and a golden-trajectory eval gate (minutes, because it reruns each golden task N times for the flakiness budget and may hit a live or semi-live model for a sampled subset) run on every PR but with a slightly higher latency tolerance, gating merge on the aggregate pass rate crossing a threshold rather than 100% green. Teams that skip the third tier because "it's slow" are the ones who ship the regression the demo didn't cover; teams that run only the third tier because "that's the real test" are the ones with a 45-minute CI pipeline nobody waits for and a base layer of harness bugs the eval set never happened to exercise.

### Testing failure paths: tool errors, timeouts, malformed output

The failure paths are not edge cases to get to eventually, they're a required part of the suite, because `T07-agent-loop-from-scratch` and `T07-harness-engineering` both establish that error-handling design is one of the highest-leverage decisions in the whole system. Concretely: a test that makes a tool raise mid-run and asserts the loop receives an observation string and continues rather than crashing; a test that makes a tool hang past its timeout and asserts the loop times it out and the observation says so; a test that returns malformed JSON from a tool and asserts schema validation catches it before it reaches business logic; a test that induces a transient failure on a retry-eligible tool and asserts the idempotency key prevents a duplicate side effect on the retry. None of these need a real model — they're deterministic harness tests, which is exactly why they belong at the base of the pyramid and should be numerous.

### The observable symptom of a suite that passes while the agent silently regressed

Two concrete patterns to look for, and both are diagnosable from the suite's own metadata without touching production:

1. **A golden trajectory whose assertions are too loose to fail on a real regression** — e.g., asserting only "the agent called at least one tool" on a task that requires a specific sequence to be correct. Audit this by deliberately injecting a known-bad trajectory (call the wrong tool, skip a required step) into the test and confirming the golden actually fails on it; a golden that can't be made to fail by an obviously wrong run is not testing anything.
2. **A cassette or eval set that has drifted from what production traffic actually looks like** — the suite is green because it's testing yesterday's distribution of tasks, while production has shifted to a category of request the eval set never covered. The symptom in the wild: CI stays green release over release while a production error-rate or complaint-rate metric climbs, with no single commit that bisects to the regression, because the regression isn't in the code, it's in the coverage gap between what's tested and what's actually being asked of the agent now.

---

## Build it from scratch

The lab progression mirrors the pyramid, building up from the deterministic base:

1. **Unit layer first.** Scripted fake model (a Python generator yielding pre-defined responses, no cassette needed yet), test the loop's stop conditions, tool dispatch, and error-as-observation behavior in isolation. Free, instant, and where the harness's actual bugs live.
2. **Add the permission engine as pure-function tests.** Table-driven `(principal, tool, args) → decision`, including argument-pattern rules. No model involved at all.
3. **Add cassette recording.** Pick three real tasks, record real model interactions once, commit the cassettes, and rewrite the same tests to replay from cassette instead of the scripted fake — prove the suite still passes and now runs against realistic model behavior at unit-test speed.
4. **Add a golden-trajectory format and three golden tasks.** Write the assertion helpers (fuzzy tool-sequence match, end-state check against a fixture database, cost/step envelope check) and deliberately inject one wrong trajectory per golden to prove the assertion actually fails on it — this is the step most teams skip and the one that catches a toothless eval set before it ships.
5. **Add the flakiness-budget runner.** Run each golden task N=10 times against the cassette (or a live model in a separate, slower job), compute pass rate, and gate on a threshold rather than a single boolean.
6. **Add failure-path tests.** Tool exception, tool timeout, malformed tool output, retry-with-idempotency-key — four tests, no model needed, each proving a specific piece of `T07-agent-loop-from-scratch`'s error-handling design.
7. **Wire the three tiers into CI** with the runtime and merge-blocking behavior described above, and measure your own pipeline's wall-clock time at each tier so you know where the budget is going.

---

## How it's done in production

**Failure-mode table**

| Symptom | Cause | Fix |
|---|---|---|
| CI green, production error rate climbing, no bisectable commit | Eval set / golden trajectories drifted from real production traffic | Periodically sample real production trajectories into the golden set (semi-automated curation with a human review pass), don't let it freeze at initial authoring |
| Suite is disabled test-by-test over a few months | Assertions on exact response wording, which fails on every harmless prompt tweak | Rewrite assertions to check tool-call sequence and end-state, never exact text |
| CI takes 45 minutes, PRs sit unreviewed | Every test hits a live model instead of a cassette | Move the bulk of the suite to cassette replay; reserve live-model calls for a smaller, slower, less-frequent smoke tier |
| A golden task "passes" even when you inject an obviously wrong trajectory | Assertions too loose (e.g., "called at least one tool") | Tighten to check the specific required tool-call sequence and end-state; validate the golden itself by proving it can fail |
| Cassette-backed tests all pass, live integration breaks in staging | Cassette recorded against a stale tool schema or API version | Re-record cassettes on every schema/prompt change, not just code changes; run a periodic live smoke suite to catch drift by construction |
| Flaky test gets "fixed" by adding a retry loop around the test itself | Root cause (model-level or environment-level nondeterminism) was never diagnosed | Track pass-rate-over-N per task explicitly; a task with a declining trend is real information, not noise to retry away |
| Idempotency bug (duplicate ticket created on retry) reaches production despite a passing suite | No test ever induced the retry path | Add a dedicated failure-path test that forces a transient failure and asserts the idempotency key prevented duplication |

---

## Tradeoffs & when NOT to use it

- **Don't cassette-record everything and never re-record.** A cassette suite that's 100% offline and never touches a live model is fast but blind to drift; it needs a periodic live-smoke companion or it becomes exactly the "green while regressing" failure this module warns about.
- **Don't build golden trajectories for tasks with genuinely high legitimate path variance.** If a task can be correctly solved via three or four meaningfully different tool sequences depending on incidental factors, a rigid golden trajectory will generate false failures faster than it catches real ones; for those tasks, lean harder on end-state assertions and looser sequence checks, or fall back to LLM-judge trajectory scoring (`T08-agent-eval`, `T08-llm-as-judge`) despite its own noise, because a bad deterministic assertion is worse than an imperfect judge.
- **Don't gate every merge on the full flakiness-budget eval suite if it takes tens of minutes.** Run the cheap unit and cassette-integration tiers as hard merge gates; run the expensive N-rerun golden-trajectory suite on a slightly relaxed cadence (every PR but async, or pre-merge with a longer timeout budget) so the team isn't blocked on a 20-minute pipeline for every small change.
- **When the system genuinely has no meaningful failure modes below the model call** — a single-prompt, no-tool-call classifier wrapped in a thin service — the whole apparatus of cassettes, golden trajectories, and flakiness budgets is overkill; that's a straightforward eval-set problem (`T08-llm-as-judge`), not an agent-testing problem, and building the full pyramid for it is solving a problem you don't have.
- **Don't treat a passing CI suite as proof of production correctness.** The suite proves the agent behaves as expected on the tasks and inputs it was built to cover; it cannot prove correctness on inputs outside that coverage, which is exactly the "silent regression" failure mode this module centers on. State this limit explicitly rather than letting a green pipeline imply more confidence than it earns.

---

## Interview questions

### Q1 — How do you test something that doesn't return the same output twice?
**Testing:** whether nondeterminism is an excuse or a design constraint that's been engineered around.
**Answer:** Separate the layers. Most of an agent — the loop, tool dispatch, permission engine, budgets, compactor — is ordinary deterministic code and gets ordinary unit tests against a scripted fake model, at speed, for free; that's most of the code and most of the bugs. The genuinely nondeterministic layer is the model's own output, and that gets deterministic replay (cassettes) for speed plus distribution-based pass-rate tracking (flakiness budgets) for correctness, rather than either being skipped or treated as a single pass/fail.
**Follow-up trap:** *"Give me one property test that would have caught a real bug."* Snapshot the assembled request for a fixed conversation fixture and assert the static prefix is byte-stable across turns — this catches silent prompt drift and cache-destroying mutations, a class of bug that otherwise shows up in production as an unexplained cost spike, not a test failure.

### Q2 — What's a cassette, and why is it the backbone of a fast agent test suite rather than a nice-to-have?
**Testing:** whether they know the mechanism and its actual leverage, not just the name.
**Answer:** A cassette records a real model request/response pair once, then replays it offline on every subsequent test run with the real API call blocked. It's the backbone because the alternative — hitting a live model on every test — makes a few-hundred-case suite take minutes and cost real money per run, which determines whether it runs on every commit (cassettes) or gets relegated to an ignored nightly job (live calls).
**Follow-up trap:** *"What's the failure mode of a cassette-only suite?"* Staleness — a cassette recorded against an old tool schema or prompt can pass while the live integration is actually broken, because the recorded response no longer reflects reality. Mitigate with re-recording on schema/prompt changes and a periodic live smoke tier.

### Q3 — What should a golden trajectory assert, and what should it explicitly not assert?
**Testing:** the central practical skill in the module.
**Answer:** Assert the tool-call sequence (fuzzy-matched, not byte-identical), the final state checked against actual reality rather than the agent's self-reported summary, and a cost/step envelope. Do not assert exact response wording, because it varies run to run for reasons unconnected to correctness and is the leading cause of agent test suites getting disabled test-by-test.
**Follow-up trap:** *"Your golden trajectory passes even when you feed it a deliberately wrong tool sequence. What does that tell you?"* The assertion is too loose to be testing anything real — a golden that can't be made to fail by an obviously wrong run isn't a test, it's decoration, and this should be validated for every golden by injecting a known-bad run before trusting it.

### Q4 — CI is green, production error rate is climbing, and no single commit bisects to the regression. What's happening?
**Testing:** the named failure mode the module centers on.
**Answer:** The eval set or cassette suite has drifted from what production traffic actually looks like — the suite is testing an accurate but stale distribution of tasks, while production has shifted into a category the suite never covered. It's a coverage gap, not a code regression, which is exactly why it doesn't bisect.
**Follow-up trap:** *"How do you prevent this proactively rather than diagnosing it after the fact?"* Periodically sample real production trajectories into the golden/eval set with a human review pass to canonicalize them, rather than freezing the set at initial authoring — semi-automated golden construction is the current direction of travel specifically to close this gap.

### Q5 — Explain pass^k and why a single passing run proves less than it seems to.
**Testing:** connecting the flakiness-budget engineering practice to its statistical justification, cross-referencing eval methodology.
**Answer:** pass^k is whether all k of k repeated attempts at the identical task succeed; pass^1 (any success in one try) can look dramatically better than pass^8 on the same task, and published tau-bench-style results show pass^8 dropping below 25% in some domains even for capable models. A single green CI run for a task is closer to a pass^1 sample than a reliability estimate, so a flakiness budget (N reruns, explicit pass threshold) is the engineering response to that gap.
**Follow-up trap:** *"Doesn't running N times just make CI slower for no benefit?"* It's slower and that's the correct tradeoff for the golden-trajectory eval tier specifically — the fix is tiering (fast deterministic unit/integration tests block every merge; the N-rerun eval gate runs on a slightly relaxed cadence), not skipping the reruns.

### Q6 — Design the CI gates for an agent's test suite, with runtime budgets.
**Testing:** whether they can turn the pyramid into an actual pipeline design.
**Answer:** Three tiers. Unit tests (permission engine, budgets, compactor invariants, dispatch) run in seconds, block every merge. Cassette-backed integration tests (a few hundred cases at cassette speed) run in tens of seconds to low minutes, block every merge. Golden-trajectory eval suite (N reruns per task for the flakiness budget, possibly a sampled subset against a live model) runs in minutes, gates on aggregate pass rate crossing a threshold, on a cadence that doesn't block every small change if it's genuinely slow.
**Follow-up trap:** *"Your eval-gate tier takes 25 minutes. The team is complaining. What do you cut?"* Not the reruns — reduce N selectively for lower-risk golden tasks, parallelize the reruns, or move the tier to run async on PR-open rather than blocking merge, while keeping the fast deterministic tiers as the hard gate. Cutting reruns to make CI faster reintroduces the exact problem the tier exists to solve.

### Q7 — A tool call fails with a transient error mid-run. Walk me through how you'd test that this doesn't produce a duplicate side effect on retry.
**Testing:** whether failure-path testing is a real practice or an afterthought.
**Answer:** A deterministic, no-model-needed test: mock the tool to fail once then succeed, trigger a retry, and assert the idempotency key (derived from run id, tool name, and arguments per `T07-agent-loop-from-scratch`) causes the second attempt to return the stored result rather than executing the side effect again. This belongs in the base of the pyramid, not the eval tier, because it's fully deterministic.
**Follow-up trap:** *"This bug reached production despite a passing suite. Why?"* Almost certainly because no test ever exercised the retry path at all — passing tests only prove what they actually invoke, and a suite with no induced-failure tests has a coverage gap in exactly the place where idempotency bugs live.

### Q8 — When would you use an LLM judge to score a trajectory instead of a deterministic assertion, and what's the risk?
**Testing:** knowing the live disagreement named in the lineage, and its tradeoff.
**Answer:** When the task has genuinely high legitimate path variance (multiple correct tool sequences depending on incidental input details) such that a rigid deterministic assertion would generate more false failures than it catches real ones. The risk is that an LLM judge grading a long trace has its own reliability ceiling and adds a second source of noise on top of the agent's own nondeterminism, so it should be reserved for cases deterministic checks genuinely can't handle, not used by default because it's easier to set up.
**Follow-up trap:** *"How do you know your LLM judge itself isn't the flaky component?"* Validate the judge the same way you validate a golden trajectory — feed it known-good and known-bad trajectories and confirm it discriminates correctly before trusting its verdicts in a CI gate.

### Q9 — Your teammate wants to assert the agent's exact response text in a golden-trajectory test "so we know it's really right." What's your pushback?
**Testing:** the single most common practical mistake named in the module.
**Answer:** Exact-text assertions fail on harmless rephrasing that has nothing to do with correctness, and it's the leading cause of agent suites getting disabled test-by-test until they're decorative. The correct assertions are tool-call sequence and end-state — if the database row is right and the right tools were called in a reasonable order, the wording is not part of what "really right" means for this test's purpose.
**Follow-up trap:** *"What if the exact wording actually matters for this specific task, like a legally required disclosure?"* Then that's a legitimate case for a targeted assertion checking for the presence of specific required phrases or clauses (a schema/compliance check), not a full string match against one golden phrasing — narrow the assertion to what actually matters rather than pinning the whole response.

### Q10 — What's the highest-leverage test you'd write if you could only write five for a new agent?
**Testing:** prioritization judgment, the senior signal.
**Answer:** Permission-engine table tests (catches the class of bug with the worst blast radius), a compaction invariant test (task and open-items survive compaction), a tool-error-as-observation test (loop continues rather than crashing), one golden trajectory with a deliberately-injected-wrong-run validation (proves the assertion actually discriminates), and a request-prefix snapshot test (catches silent prompt drift and cache-destroying mutations). None of these need a live model, and together they cover the harness bug classes most likely to reach production silently.
**Follow-up trap:** *"No eval-set test in your top five?"* Deliberate — the eval/golden-trajectory tier is valuable but expensive and slower to pay off; the five listed are cheap, fast, deterministic, and catch bug classes that a golden trajectory often won't isolate cleanly (a permission bug can pass a golden trajectory that never happens to probe that specific denied path).

---

## Red flags that fail you

- Saying agents "can't be tested" because the model is nondeterministic.
- Asserting exact response text in a golden trajectory.
- Grading task completion against the agent's own summary instead of actual end state.
- A CI suite where every test hits a live model, with no cassette layer.
- No flakiness budget — treating a single run as ground truth for a stochastic system.
- A golden trajectory that was never validated to actually fail on a wrong run.
- No test that induces a tool failure, timeout, or malformed output.
- Claiming a green CI suite proves production correctness with no caveat about coverage gaps.

## Cheat card

```
PYRAMID (inverted top layer is the only nondeterministic one)
  UNIT: harness code, no model — permission engine, budgets, compactor,
        dispatch. MOST bugs live here. instant, free.
  INTEGRATION: real loop/tools/perms + CASSETTE-replayed model. fast, free,
        runs every push.
  E2E/EVAL: golden trajectories, N reruns, live/semi-live model. slow, $,
        gates merge on pass-rate threshold not 100% green.

CASSETTE (vcr.py pattern): record once -> replay forever, no network,
  no cost. RISK: staleness — re-record on schema/prompt change, run a
  periodic LIVE smoke tier to catch drift cassettes can't see.

GOLDEN TRAJECTORY
  ASSERT: tool-call sequence (fuzzy) · final state vs REALITY not agent's
          own summary · cost/step envelope
  NEVER ASSERT: exact wording -> #1 cause of suites disabled test-by-test
  VALIDATE the golden itself: inject a known-wrong run, confirm it FAILS

FLAKINESS BUDGET
  pass^1 (any success) >> pass^8 (all 8/8) on the SAME task
  tau-bench: pass^8 < 25% in retail domain even for capable models
  -> run N reruns, gate on pass-rate threshold (e.g. 8/10), track trend
     per task over time, not single boolean

CI GATES (3 tiers, know the runtime cost)
  unit + cassette-integration: seconds-minutes, block EVERY merge
  eval/golden tier: minutes (N reruns), gate on aggregate pass rate,
    relax cadence (async / slightly longer budget) rather than cutting N

FAILURE-PATH TESTS (deterministic, no model needed)
  tool raises -> observation, loop continues (never crash the run)
  tool times out -> observation states timeout
  malformed tool output -> schema validation catches it pre-business-logic
  transient failure + retry -> idempotency key prevents duplicate side effect

SILENT REGRESSION SYMPTOM: CI green, prod error rate up, NO bisectable
  commit -> eval set / cassettes drifted from real production traffic
  FIX: sample real prod trajectories into golden set periodically (semi-
       automated curation + human review), don't freeze at authoring time

WHEN NOT TO: high legitimate path variance -> loosen to end-state only or
  use LLM-judge (validate the judge itself first). No tool calls at all ->
  this is an eval-set problem (T08-llm-as-judge), not agent testing.
```

## Sources

- [End Vibe-Driven Development: Testing AI Agents in CI Pipelines](https://ai.plainenglish.io/end-vibe-driven-development-testing-ai-agents-in-ci-pipelines-promptfoo-golden-traces-b9b222b23d72) — golden traces for deterministic regression testing; accessed 2026-08-01
- [Docker's Cagent Brings Deterministic Testing to AI Agents](https://www.infoq.com/news/2026/01/cagent-testing/) — Jan 2026; accessed 2026-08-01
- [Trustworthy AI Agents: Deterministic Replay](https://www.sakurasky.com/blog/missing-primitives-for-trustworthy-ai-part-8/) — record/replay pattern, vcr.py lineage; accessed 2026-08-01
- [Deterministic Testing for LangChain Agents](https://blog.sixty-north.com/deterministic-testing-for-langchain-agents.html) — accessed 2026-08-01
- [Behavioral testing for AI agents](https://developers.redhat.com/articles/2026/07/30/behavioral-testing-for-ai-agents) — Red Hat Developer, July 2026; accessed 2026-08-01
- [Get Experience from Practice: LLM Agents with Record & Replay](https://arxiv.org/html/2505.17716v1) — accessed 2026-08-01
- `curriculum/08-eval-observability/04-agent-eval.md` (`T08-agent-eval`) — trajectory scoring methodology, pass^k, tau-bench numbers this module cites and builds a CI practice around
- `curriculum/07-agentic-ai/01-agent-loop-from-scratch.md` (`T07-agent-loop-from-scratch`) — error-as-observation design, idempotency keys
- `curriculum/07-agentic-ai/25-harness-engineering.md` (`T07-harness-engineering`) — compaction invariants, permission engine mechanics under test

## Changelog
- 2026-08-01 — created
