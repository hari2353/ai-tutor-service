# Testing LLM Systems: Non-Determinism, Golden Trajectories, Judge Drift

> **Track:** T19 Testing & Quality Engineering · **Time:** 2.5h · **Prereqs:** none · **Updated:** 2026-08-01
> **Module id:** `T19-llm-testing` · **Tags:** llm,critical

## The 30-second version

Testing an LLM-backed system starts from accepting that variance is baseline behavior, not noise to eliminate — even at temperature 0, batched inference means your token's routing and reduction order depend on what else is in the batch at that instant, so identical requests genuinely produce different outputs across runs, across hardware, and after any silent model-version bump. The engineering response is not "make it deterministic," it's "stop asserting exact strings and start asserting invariants": recorded/cassette responses for the fast deterministic layer, property-based and structural assertions (schema valid, required fields present, tool called, cost under budget) for the layer that has to touch a real model, and N-runs-with-a-pass-threshold instead of single pass/fail for anything genuinely stochastic — retrying a flaky LLM test until it goes green is actively dangerous, because it papers over real instability instead of measuring it. Golden trajectories extend this to multi-step systems: assert the tool sequence and end state against reality, never the wording. The failure mode unique to this domain is judge drift — the judge model itself changes under you (a silent version bump, a provider deprecation) with no code change on your side, and the observable symptom is eval scores moving on a stable prompt/model pairing with nothing in the diff to explain it, which is why a judge has to be pinned, versioned, and re-calibrated against human labels exactly like any other dependency you don't control.

## Why this gets asked

Because every team that ships an LLM feature eventually needs a CI gate that doesn't cry wolf on every PR and doesn't stay green while the system silently regresses, and both failure directions are well-documented and expensive: teams that give up on testing entirely ("it's nondeterministic, you can't unit test it") ship regressions a five-minute smoke test would have caught, and teams that string-match exact model output end up with a suite that's flaky for reasons unconnected to correctness and gets disabled test-by-test until it's decoration. The interviewer has usually watched a real incident from one of two shapes: a prompt or harness change that passed every eval and broke production because the eval set never covered the failure category, or a quality dashboard that quietly moved because the judge model was silently upgraded underneath the pinned "gpt-4" alias. They want to know whether you'll separate what's genuinely stochastic from what's deterministic engineering wearing a nondeterministic hat, and whether you know the specific cost and reliability tradeoffs of each layer, not just that "you should eval your prompts."

---

## Lineage: past → present → future

**What came before.** Early LLM application testing (2022-2023) inherited directly from single-turn NLG evaluation: send a prompt, diff the output against a reference string or a hand-checked example, done — a reasonable fit for near-deterministic classification tasks, and a poor fit for anything generative, where two correct answers can share zero substring overlap. The pain this produced was immediate and specific: exact-match and even fuzzy-string assertions failed constantly on harmless rephrasing, so teams either disabled assertions one by one until the suite tested nothing, or avoided testing generative output altogether and relied on manual spot-checks before each release — which doesn't scale past a handful of prompts and catches nothing between manual passes. The parallel problem was cost and speed: hitting a live model API on every test run made a CI suite slow and expensive enough that most teams shrank it to a token handful of smoke tests rather than something that ran on every commit.

**Where it stands now.** The field converged on treating the model call as the one genuinely nondeterministic seam and testing everything around it like ordinary software: deterministic replay (cassette-recorded model responses, `T07-agent-testing`) for a fast, free, CI-blocking layer; property-based and structural assertions instead of string matching for anything that must touch a real model; and N-reruns-with-a-threshold ("flakiness budgets," `T07-agent-testing`) instead of single pass/fail for the genuinely stochastic top layer. What's changed the underlying model is a clearer mechanical understanding of *why* temperature 0 isn't actually deterministic: recent analysis attributes most of the observed non-determinism not to floating-point non-associativity in isolation but to the **batch-size dependence of reduction kernels** — a request's dynamic batch composition changes which reduction tree executes, and in MoE serving, tokens from different concurrent sequences compete for the same expert-routing slots, so the routing decision for your token can depend on what else happens to be in the batch at that moment [Understanding and Mitigating Numerical Sources of Nondeterminism in LLM Inference (arXiv:2506.09501)](https://arxiv.org/pdf/2506.09501) — accessed 2026-08-01. Batch-invariant kernels (deterministic RMSNorm, matmul, attention) can produce bit-identical output across 1,000 repeated runs, but at a measured ~61.5% throughput cost in a baseline implementation, which is exactly why almost no production serving stack runs with them by default — you are testing a system that is nondeterministic by a real, load-bearing engineering tradeoff, not an oversight. The live disagreement is less "should you test LLM systems" (settled: yes, extensively) and more where the LLM-judge layer belongs and how much to trust it without calibration (`T08-llm-as-judge`), and how large an eval-as-CI-gate a team can actually afford to run on every PR before the dollar cost and wall-clock time become the real constraint.

**Where it's heading.** High confidence: **eval-as-regression-suite becomes the default CI shape** for any team shipping LLM features past prototype stage, the same way `T07-agent-testing`'s golden-trajectory pipeline is becoming default for agents specifically — the alternative doesn't survive contact with a normal release cadence. Medium confidence: **token-efficient regression techniques** (behavioral fingerprinting, adaptive per-test budgets, multi-fidelity proxy testing using a cheaper model as a first-pass filter before a full eval) are actively narrowing the cost gap that makes large eval suites expensive to run on every commit, though the irreducible live-run cost floor for genuinely new-model-version validation doesn't go to zero. Medium confidence: **judge-drift attribution tooling** — explicitly separating "did the system under test regress" from "did the judge itself regress" via anytime-valid statistical methods — is moving from research into production eval platforms, because conflating the two has caused real, documented incidents (a judge model version bump in mid-2026 reportedly produced a complete collapse in evaluator behavior on one team's suite, with identical reruns showing no coupling at all between repeated judgments) [Who Drifted: the System or the Judge? (arXiv:2606.15474)](https://arxiv.org/abs/2606.15474) — accessed 2026-08-01.

---

## Mental model

```
THE ONE THING TO INTERNALIZE: nondeterminism lives in exactly ONE layer.
Everything else is ordinary software with ordinary tests.

  ┌───────────────────────────────────────────────────────────────┐
  │  MODEL CALL ITSELF          genuinely stochastic, even at T=0  │  <- special handling:
  │  (the seam)                 batch-size-dependent reduction      │     cassettes + N-run
  │                              kernels, MoE routing depends on     │     distributions
  │                              what else is in the batch           │
  ├───────────────────────────────────────────────────────────────┤
  │  EVERYTHING AROUND IT       prompt assembly, parsing, retries,  │  <- ordinary unit tests,
  │                              schema validation, tool dispatch,   │     deterministic, fast,
  │                              retry/backoff, cost tracking        │     most bugs live here
  └───────────────────────────────────────────────────────────────┘

WHY TEMPERATURE 0 ISN'T ACTUALLY DETERMINISTIC
  T=0 fixes the TOKEN SELECTION RULE (always pick argmax), not the LOGITS
  that selection rule operates on. Continuous/dynamic batching means your
  request's batch composition varies run to run -> different reduction
  tree order for matmul/attention/RMSNorm -> different floating-point
  rounding -> occasionally a different argmax token -> divergent
  generation from that token onward. MoE adds: your token's expert
  routing can depend on which OTHER tokens are in the same batch.
  Batch-invariant kernels fix this at ~60%+ throughput cost -- almost
  nobody pays that in production, so assume real nondeterminism exists.

ASSERT INVARIANTS, NOT STRINGS
  WRONG:  assert response == "The capital of France is Paris."
  RIGHT:  assert "Paris" in response
          assert schema_valid(response)
          assert tool_called == "lookup_capital"
          assert cost_usd < 0.02
          assert len(response) < 500

JUDGE DRIFT, the observable symptom
  Eval score on a STABLE prompt+model pairing moves, with NOTHING in
  the diff to explain it -> the JUDGE changed underneath you (silent
  version bump, provider deprecation, or the alias you pinned actually
  points at a moving target). This is diagnosable ONLY if you logged
  the judge's own model/version alongside every score.
```

---

## How it actually works

### Non-determinism as the core problem, mechanically

The naive mental model — "temperature 0 means greedy decoding means deterministic" — is wrong in practice for three independent, stackable reasons, and knowing all three (not just "GPUs are nondeterministic") is the actual interview signal:

1. **Batch-size-dependent reduction kernels.** Matrix multiplication, attention, and normalization kernels on GPU execute as a sum-reduction across many parallel units, and floating-point addition is not associative — `(a+b)+c != a+(b+c)` in finite precision. The specific reduction tree a kernel executes depends on the batch size and shape it's dispatched with, and in a production server under continuous/dynamic batching, your request's batch composition changes from call to call depending on concurrent traffic — so the same prompt can hit a different reduction order on two calls a second apart, producing a different rounding result, which can occasionally flip an argmax tie and cascade into a fully divergent generation from that token onward.
2. **MoE expert-routing contention.** In a Mixture-of-Experts model served with batched requests, the router's top-k expert selection for a token can be influenced by what other tokens are concurrently competing for the same expert's capacity in that batch — meaning your token's routing, and therefore its output, is not purely a function of your input, it's a function of your input *and* who else happened to be in the batch with you.
3. **Model version drift underneath a stable-looking alias.** A provider silently swapping which checkpoint an API alias (`gpt-4`, `claude-latest`) resolves to is a distinct, non-numerical source of "the same prompt now returns something different" — this is not floating-point noise, it's your dependency changing without a version bump you controlled.

The practical consequence: batch-invariant deterministic kernels exist and can produce bit-identical output across 1,000 reruns, but at a real, substantial throughput cost (measured around 60%+ in a baseline implementation), which is why they're essentially never the default in production serving — you should assume the system you're testing is nondeterministic by a deliberate performance tradeoff someone else made, not a bug you can report upstream.

### Strategies for testing around genuine nondeterminism

**Recorded/cassette responses.** Record a real model interaction once, replay it in every subsequent test run with the network call blocked (`T07-agent-testing` covers the mechanics — record mode writes a fixture, replay mode reads it back deterministically). This is the backbone of a fast, CI-blocking test tier: it eliminates both the cost and the flakiness of a live call for anything that doesn't specifically need to prove the live integration still works. The real risk is staleness — a cassette recorded against an old prompt or tool schema can pass while the live system has actually drifted, so cassettes need re-recording on any prompt/schema change, paired with a smaller, slower, periodic live-smoke tier that exists specifically to catch what cassettes can't see by construction.

**Asserting invariants rather than strings.** The single highest-leverage practice in this whole module: never assert exact response text, assert properties of the response that are true regardless of exact phrasing. Concretely — does the output parse as valid JSON against the expected schema; does it contain a required fact or citation; was the expected tool called with arguments in the right shape; is the token count/cost under a budget; is a disallowed pattern (a leaked system prompt fragment, an unescaped injection) absent. Every one of these is checkable without caring what the model's exact wording was, and every one of these is a real property a regression can actually violate, unlike exact wording, which changes for reasons that have nothing to do with correctness.

**N-runs-with-a-threshold, not single pass/fail.** Because variance is baseline behavior for a stochastic system, a single green run is weak evidence — it's closer to one sample from a distribution than a reliability measurement. The practice: run the same test N times (5-10 is a common practical range), compute the pass rate (or mean and standard deviation for a scored metric), and gate on the rate crossing a threshold, not on any single run's result. **Retrying a failing test until it passes is the dangerous version of this same idea done backwards** — "retry until green" silently discards the exact instability signal the N-run practice exists to measure, and a team that reflexively retries flaky LLM tests is quietly disabling its own regression detector one retry at a time.

**Property-based assertions.** Beyond fixed-schema checks, define properties that should hold across a *range* of inputs rather than a single example — a summarizer's output should always be shorter than its input by some factor; a translation should round-trip through back-translation within a similarity bound; a structured extractor's output should always be re-parseable by the same schema it was validated against at generation time. This generalizes unit-test coverage across an input space a handful of hand-picked examples can't reach, the same motivation as property-based testing anywhere else in software (`T19-test-strategy`), applied to a generative system specifically because example-based testing under-covers a space this large.

### Golden trajectories, restated for non-agent LLM systems

`T07-agent-testing` develops golden trajectories in full for tool-calling agents (assert tool sequence and end state, never wording, with fuzzy sequence matching and validated-against-a-known-bad-run assertions). The same discipline applies to any multi-step LLM system even without an agent loop — a multi-turn support flow, a document-processing pipeline with several LLM-backed stages, a RAG answer that must cite specific retrieved chunks: define the reference path as the *shape* of correct behavior (which stages ran, what the final state/output structurally contains, which sources were cited) rather than the literal text produced at any stage. The trap is identical to the agent case and worth restating because it's the most common practical mistake in this whole domain: a golden that asserts exact wording generates false failures on every harmless rephrasing and gets disabled test-by-test; a golden that's too loose to ever fail on an obviously wrong run isn't testing anything and needs to be validated by deliberately injecting a known-bad case and confirming it actually fails.

### Judge drift: the failure mode specific to this domain

`T08-llm-as-judge` covers judge biases (position, verbosity, self-preference) and the calibration workflow (human-labeled traces, Cohen's kappa/Krippendorff's alpha, re-calibrate on rubric or model change) in depth — this module's angle is narrower and specifically about **drift as a CI/regression-testing failure**, distinct from the biases a judge has even when perfectly stable.

**The mechanism.** A judge is itself a model, served the same way any other model is — behind an alias that can silently resolve to a different checkpoint, subject to the same provider-side version bumps and eventual deprecations as the system under test. If your eval pipeline references `"judge_model": "gpt-4o"` without pinning an exact dated version, the provider can change what that string resolves to with zero action on your part, and your eval scores move for a reason that has nothing to do with the system you're actually testing.

**The observable symptom.** Eval scores shift on a stable prompt/model pairing — nothing in your code, prompt, or model version changed, and the score trend line still moves, sometimes sharply. This is diagnosable *only* if you logged which judge model/version actually produced each historical score; without that, a real regression in the system under test and a drifted judge look identical from the dashboard, and teams without judge-version logging have genuinely lost the ability to tell them apart after the fact. Documented cases include a mid-2026 judge version change producing what one team described as a complete collapse in evaluator coupling — identical repeated N=8 evaluations of the same trace showing essentially no agreement with each other after the drift, versus stable near-total agreement before it [Who Drifted: the System or the Judge? (arXiv:2606.15474)](https://arxiv.org/abs/2606.15474) — accessed 2026-08-01.

**The fix.** Pin the judge to an exact, dated model version, never a rolling alias, treated as a real dependency version, not a config nicety. Version the rubric and prompt template alongside the pinned model id (a stable tuple of judge_model_id + rubric_version + prompt_template_hash is a common practical contract), and treat any change to *any* element of that tuple as a full re-calibration event against human labels, not a quiet config edit. Log the judge's model/version with every score it produces, specifically so a future drift investigation can separate "the system regressed" from "the judge regressed" by cross-referencing score history against judge-version history. Run a periodic stability check — score a fixed, unchanging set of reference traces with the current pinned judge and confirm the scores haven't moved — as an early-warning canary independent of your main regression suite.

### Eval-as-test-suite and its CI cost

Treating your evaluation set as your regression suite (run every eval case on every meaningful change — a prompt edit, a model version bump, a harness change) is the direct answer to "how do you know a change didn't silently break something the manual smoke test didn't cover." The real, unavoidable constraint is cost: a single LLM-judge call commonly runs $0.05-$0.50 depending on judge tier and trace length, so a 5,000-example regression set scored by an LLM judge lands at roughly $250-$2,500 **per run**, and running each case N=5 times for a flakiness budget multiplies that directly — 200 test cases at 5 reruns and $0.04/call is $40 in a single CI run, which is real, recurring money at PR-per-commit cadence [Building a Production LLM Evaluation Harness in Pytest](https://dev.to/velsof/building-a-production-llm-evaluation-harness-in-pytest-cost-bounded-flake-aware-ci-gated-26pc) — accessed 2026-08-01. The practical resolution is tiering, the same shape as `T07-agent-testing`'s CI pyramid: a small, cheap, deterministic-assertion tier runs on every commit and blocks every merge; a mid-size cassette-backed tier runs on every push; the full live-model eval-as-regression-suite runs on PRs that actually touch prompts, tools, or model version, on a cadence the team can afford (async, nightly, or gated specifically on the files that changed) rather than on every single commit regardless of relevance. A representative team running two to three prompt paths with a tiered CI/nightly split reports landing around $50-$200/month in evaluation API cost — a budget line worth naming explicitly in a design doc, not an afterthought discovered on the first invoice.

### Regression detection on a rolling window

A single before/after comparison on one release is a weak signal for a system with real run-to-run variance — a score that's "down 3 points" from the last release could be real regression or could be normal noise for that metric's variance at your sample size. The practice: track each metric (per-task pass rate, judge score, cost, latency) as a **rolling window trend** over the last N releases rather than a single before/after diff, and treat a metric that's declining over several consecutive windows as a real signal even if no single release-to-release delta alone would clear a significance threshold — this is the same instinct as `T27-debug-methodology`'s point that a stable-looking system can still be silently degrading if nobody's watching the trend, applied to eval scores specifically. A documented rule of thumb: a 5-point drop in a faithfulness/quality metric over a week is a real regression that pure latency/error-rate monitoring won't catch, because the request is still succeeding, it's just succeeding with worse output.

### Testing prompts as artifacts

Treat a prompt template the way you'd treat any other versioned artifact with a test suite gating changes to it: store it under version control with an explicit version identifier (not inline in application code with no history), run the full regression/eval suite against any prompt change before merge exactly as you would for a code change, and diff prompt versions in code review the same way you'd review a logic change, because a prompt edit is a logic change with a larger and less predictable blast radius than most code edits. This also directly supports the judge-drift fix above: a `prompt_template_hash` you can point to in a score log is only meaningful if the prompt is actually a versioned artifact with stable hashes, not a string interpolated fresh from several files at request time.

### Flakiness budgets, restated for the general LLM-testing case

`T07-agent-testing` covers this in the tool-calling-agent context (pass^k, tau-bench numbers). The same practice applies to any LLM-backed test: define an explicit threshold over N reruns (for example, 8 of 10 must pass) rather than treating one run as ground truth, and track the pass-rate-over-N per test case as a monitored trend, not a one-time gate — a task whose pass rate is declining release over release carries real information a single green run hides completely.

### When the provider deprecates your model mid-suite

This is a concrete, recurring operational event, not a hypothetical: providers deprecate model versions on a schedule, and a pinned model id your suite depends on (both the system-under-test's model and, separately, the judge's model) will eventually stop being servable. The response, in order: (1) treat this exactly like any other pinned-dependency deprecation — you get a deprecation notice with a timeline, not a surprise, if you're actually watching provider changelogs; (2) before swapping to the replacement version, re-run your full calibration/regression baseline against the *new* version in parallel with the old one, because a same-numbers-different-model swap is exactly the silent-change judge drift describes, just applied to the primary model instead of the judge; (3) treat the swap as a genuine version migration with its own review, not a config toggle — expect some eval scores to move for reasons connected to the model change itself, and have the baseline comparison ready so you can distinguish "the new model is worse at this task" from "the new model phrases things differently and our assertions were accidentally string-based after all."

---

## Build it from scratch

A minimal harness demonstrating cassette replay, invariant-based assertions, N-run flakiness budgets, and judge-version pinning together — the shape of what a real eval harness's core loop looks like.

```python
# untested sketch
import json
import statistics
from dataclasses import dataclass, field

@dataclass
class Cassette:
    path: str
    mode: str = "replay"          # "record" or "replay"
    _recorded: list = field(default_factory=list)
    _idx: int = 0

    def call(self, prompt: str, real_model_client=None):
        if self.mode == "record":
            resp = real_model_client(prompt)
            self._recorded.append({"prompt": prompt, "response": resp})
            return resp
        if self._idx >= len(self._recorded):
            raise AssertionError(f"Cassette exhausted at call {self._idx}; re-record.")
        resp = self._recorded[self._idx]["response"]
        self._idx += 1
        return resp


def assert_invariants(response: dict, *, required_fields: list[str],
                       max_cost_usd: float, forbidden_substrings: list[str]) -> list[str]:
    """Returns a list of violated invariants -- never asserts exact text."""
    violations = []
    for field_name in required_fields:
        if field_name not in response.get("parsed", {}):
            violations.append(f"missing required field: {field_name}")
    if response.get("cost_usd", 0) > max_cost_usd:
        violations.append(f"cost {response['cost_usd']} exceeds budget {max_cost_usd}")
    text = response.get("text", "")
    for bad in forbidden_substrings:
        if bad in text:
            violations.append(f"forbidden substring present: {bad!r}")
    return violations


def run_with_flakiness_budget(test_fn, n: int = 10, pass_threshold: float = 0.8) -> dict:
    """Runs a stochastic test N times; gates on pass RATE, never a single run."""
    results = [test_fn() for _ in range(n)]
    pass_rate = sum(results) / n
    return {
        "n": n, "pass_rate": pass_rate,
        "passed": pass_rate >= pass_threshold,
        "note": "single-run pass/fail is not a valid signal for a stochastic system",
    }


@dataclass
class PinnedJudge:
    """Judge identity is a versioned CONTRACT, not a rolling alias."""
    judge_model_id: str   # exact dated version, e.g. "gpt-4o-2026-05-13", never "gpt-4o"
    rubric_version: str
    prompt_template_hash: str

    def score(self, judge_call_fn, trace: dict) -> dict:
        result = judge_call_fn(self.judge_model_id, self.rubric_version, trace)
        # log the FULL identity tuple with every score -- this is what makes a
        # future "did the system regress or did the judge regress" investigation
        # possible at all; without it the two are indistinguishable after the fact
        return {
            "score": result,
            "judge_model_id": self.judge_model_id,
            "rubric_version": self.rubric_version,
            "prompt_template_hash": self.prompt_template_hash,
        }


def rolling_window_regression_check(history: list[float], window: int = 5,
                                     drop_threshold: float = 0.05) -> bool:
    """Flags a REGRESSION signal from trend, not a single before/after diff."""
    if len(history) < window + 1:
        return False
    recent = statistics.mean(history[-window:])
    prior = statistics.mean(history[-2 * window:-window])
    return (prior - recent) >= drop_threshold
```

This omits a real cost-tracking budget guard and the property-based generators you'd use for a summarizer/translator-style property test, but shows the four mechanisms composed together: replay for speed, invariants instead of strings, N-run thresholds instead of single pass/fail, and a judge identity that's a logged, versioned contract rather than an implicit assumption.

---

## How it's done in production

**Frameworks**: DeepEval and promptfoo (pytest/CI-native, golden-trace and assertion-based regression testing), Ragas (RAG-specific faithfulness/relevancy metrics), Braintrust and LangSmith (full lifecycle — dataset management, CI gates, production monitoring, human annotation queues for calibration), Arize Phoenix (trace capture plus drift detection). None of these frameworks make nondeterminism or judge drift disappear on their own — they give you the harness to run cassette replay, N-run budgets, and judge-version pinning at scale and track the results over time, which is the actual practice this module describes.

**Failure-mode table:**

| Symptom | Cause | Fix |
|---|---|---|
| CI green, production quality complaints rising, no bisectable commit | Eval set drifted from real production traffic distribution, or judge drifted underneath a rolling alias | Sample real production traces into the eval set periodically with human review; audit whether the judge model id is actually pinned to an exact version |
| Test suite disabled test-by-test over a few months | Assertions on exact response text, which fails on every harmless rephrasing | Rewrite to invariant/structural assertions (schema, required fields, tool calls, cost, forbidden substrings); never assert exact wording |
| Eval score moves sharply on a release with no prompt or model change in the diff | Judge model silently version-bumped by the provider under a rolling alias | Pin judge to an exact dated version; log judge_model_id with every historical score so drift is attributable after the fact |
| A flaky LLM test gets "fixed" by wrapping it in a retry loop | Root cause (model-level variance) was never measured, just hidden | Replace retry-until-green with N-run-and-report-rate; track pass-rate-over-N as a trend, not noise to retry away |
| CI takes 30-45 minutes and costs real money on every PR | Every test hits a live model instead of cassette replay, or the full eval-as-regression-suite runs on every commit regardless of relevance | Move the bulk of the suite to cassette replay; gate the expensive live-eval tier on prompt/model-touching changes specifically, not every commit |
| A prompt "improvement" ships and production quality quietly drops over the following week | No rolling-window trend tracking; a single before/after eval comparison looked acceptable within normal variance | Track metrics as rolling windows over releases, not single diffs; treat a multi-window declining trend as a real signal even below a single-release significance threshold |
| Provider deprecates the pinned model version, team swaps to the replacement with no re-baseline | Treated a model swap as a config change instead of a dependency migration | Re-run full calibration/regression against the new version in parallel with the old before cutover; expect and account for genuine behavior differences, not just assume equivalence |

---

## Tradeoffs & when NOT to use it

- **Don't run the full live-model eval-as-regression-suite on every single commit.** The dollar and wall-clock cost is real and compounds at PR-per-commit cadence; gate the expensive tier on changes that actually touch prompts, tools, or model version, and let cheap deterministic/cassette tiers block every merge instead.
- **Don't retry a flaky LLM test until it passes.** This is the single most common anti-pattern in the domain — it doesn't fix anything, it actively destroys the variance signal the N-run practice exists to measure, and a team that does this systematically has quietly disabled its own regression detector.
- **Don't assert exact response wording, ever, in a system where the model's phrasing is expected to vary.** This is the leading cause of suites getting disabled test-by-test; assert structure, presence, cost, and tool calls instead.
- **Don't treat an LLM judge as a stable, version-free dependency.** A rolling alias is a real, recurring source of unattributable score movement; pin it, version the rubric alongside it, and log the full identity tuple with every score.
- **Don't build the full apparatus (cassettes, N-run budgets, rolling-window trend tracking, judge pinning) for a system with no meaningful stochastic surface** — a single-call, low-stakes internal tool with cheap manual review may not need more than a handful of deterministic structural assertions; scale the investment to the system's actual blast radius and query volume.
- **Don't assume a passing eval-as-regression-suite proves production correctness.** It proves the system behaves as expected on the distribution the suite covers; a coverage gap between the suite and actual production traffic is exactly the "green CI, declining production quality" failure mode this module centers on, and it needs to be stated as a real limit, not implied away by a passing dashboard.

---

## Interview questions

### Q1 — Why isn't temperature 0 actually deterministic in production LLM serving?
**Testing:** whether the candidate knows the mechanism, not just the fact.
**Answer:** Temperature 0 fixes the token-selection rule (always argmax) but not the logits that rule operates on. Under batched/continuous-batching production serving, a request's dynamic batch composition varies call to call, which changes the reduction-tree order executed by matmul/attention/normalization kernels; floating-point addition is not associative, so different reduction orders produce different rounding, which can occasionally flip an argmax tie and cascade into fully divergent generation. In MoE models, expert routing for a token can additionally depend on which other tokens are concurrently in the same batch.
**Follow-up trap:** *"Can you make it fully deterministic?"* — yes, with batch-invariant deterministic kernels, but at a real, substantial throughput cost (measured around 60%+ in one baseline implementation), which is why it's essentially never the production default; assume the system under test is nondeterministic by a deliberate tradeoff, not an oversight you can get fixed upstream.

### Q2 — What's wrong with asserting exact response text in an LLM system test, and what do you assert instead?
**Answer:** Exact-text assertions fail on harmless rephrasing that has nothing to do with correctness, and this is the leading cause of LLM test suites getting disabled test-by-test until they're decorative. Assert invariants instead: schema validity, presence of required fields/facts, which tool was called and with what argument shape, cost/token budget, absence of forbidden content — properties that are true regardless of exact wording and that a real regression can actually violate.
**Follow-up trap:** *"What if exact wording genuinely matters, like a legally required disclosure?"* — that's a legitimate case for a narrow, targeted assertion checking for presence of specific required phrases (a compliance/schema check), not a full string match against one golden phrasing.

### Q3 — Why is "retry the flaky test until it passes" actively dangerous rather than merely lazy?
**Testing:** the module's central anti-pattern.
**Answer:** Variance is baseline behavior for a stochastic system, not noise — retrying until green silently discards exactly the instability signal an N-run flakiness budget exists to measure. A test that's genuinely passing 60% of the time looks identical to a solidly passing test if you keep retrying until you get a green result, and the team loses the ability to see a declining pass-rate trend, which is real information a single retried-to-green run actively hides.
**Follow-up trap:** *"So what's the correct response to a flaky LLM test?"* — run it N times (5-10 is a common practical range), report the pass rate or mean/stddev, gate on that rate crossing an explicit threshold, and track the rate as a trend over releases rather than treating any single run — retried or not — as ground truth.

### Q4 — What is judge drift, and what's its observable symptom?
**Answer:** The judge model itself changes underneath the eval pipeline — a silent provider-side version bump under a rolling alias, or an eventual deprecation — with no code, prompt, or model change on the system-under-test side. The observable symptom: eval scores move on a stable prompt/model pairing with nothing in the diff to explain it, and this is only distinguishable from a real system regression if the judge's exact model/version was logged alongside every historical score.
**Follow-up trap:** *"How would you actually prove, after the fact, whether a score drop was the system or the judge?"* — cross-reference the score-history timeline against a logged judge-version-history timeline; if the score movement lines up with a judge version change and not with any system/prompt change, that's strong evidence it's judge drift, which is exactly why judge identity has to be logged with every score, not just recorded in a config file that might not match what actually ran historically.

### Q5 — How do you pin an LLM judge so it can't drift underneath you?
**Answer:** Treat judge identity as a versioned contract, not a config nicety: pin to an exact, dated model version (never a rolling alias like "gpt-4o"), version the rubric text alongside it, and treat the tuple of judge_model_id + rubric_version + prompt_template_hash as what has to stay stable for scores to be comparable over time. Any change to any element of that tuple is a full re-calibration event against human labels (`T08-llm-as-judge`), not a quiet edit.
**Follow-up trap:** *"The provider deprecates your pinned judge version. What now?"* — this is a real, expected operational event, not a surprise if you're watching provider changelogs; re-run full calibration against the replacement version in parallel with the old one before cutover, and treat the swap as a genuine eval-suite migration, exactly the same discipline as swapping the primary system-under-test model.

### Q6 — What's a golden trajectory for a non-agent, multi-stage LLM pipeline (say, a document-processing system with several LLM-backed stages), and how does it differ from asserting the literal output?
**Answer:** Define the reference as the shape of correct behavior — which stages actually ran, what the final structured output contains, which source chunks were cited — rather than the literal text any stage produced. This is the same discipline `T07-agent-testing` develops for tool-calling agents (assert tool sequence and end state, never wording), applied to any multi-step LLM system whether or not it has an agent loop.
**Follow-up trap:** *"How do you know your golden trajectory's assertions are actually strict enough to catch a real regression?"* — validate the golden itself by deliberately injecting a known-wrong run (skip a required stage, cite the wrong source) and confirming the assertion actually fails on it; a golden that can't be made to fail by an obviously wrong run isn't testing anything.

### Q7 — Your 5,000-example LLM-judge-scored regression suite costs real money to run. How do you make it affordable on every PR without weakening the signal?
**Testing:** the CI-cost tradeoff, a practical engineering question, not just a testing-theory one.
**Answer:** Tier it. A cheap, fast, deterministic-assertion layer (schema, structural checks, cassette-replayed cases) runs on every commit and blocks every merge for near-zero cost. The full live-model eval-as-regression-suite runs only on changes that actually touch prompts, tools, or model version, not on every commit regardless of relevance — and even then, techniques like a cheaper proxy-model first pass or adaptive per-case budgeting can reduce the live-run cost without eliminating the irreducible floor for genuinely validating a new model version.
**Follow-up trap:** *"The team wants to cut the eval tier's N-reruns to save money. What's your pushback?"* — cutting N specifically undermines the flakiness-budget signal itself (see Q3); if cost needs to come down, reduce scope (which cases run the expensive tier) or reduce judge tier cost (cheap judge for most cases, frontier judge reserved for hard/ambiguous ones, `T08-llm-as-judge`) before cutting the statistical sample size that makes the pass-rate number meaningful at all.

### Q8 — Explain rolling-window regression detection and why a single before/after comparison isn't enough.
**Answer:** A single release-to-release delta on a metric with real run-to-run variance is a weak signal — a 3-point drop could be genuine regression or normal noise given the metric's variance at your sample size. Tracking each metric as a rolling window trend over several releases surfaces a real, gradual decline that no single release-to-release comparison alone would clear a significance threshold for, while a metric moving within normal bounds release to release but trending down over several windows is real, actionable information.
**Follow-up trap:** *"What's a concrete threshold you'd act on?"* — there's no universal number, but a commonly cited practical signal is something like a 5-point drop in a faithfulness/quality metric sustained over roughly a week of rolling comparison — small enough that pure latency/error-rate monitoring won't catch it (the requests are still succeeding), which is exactly why it needs its own dedicated tracking.

### Q9 — Testing prompts as artifacts — what does this actually require operationally, beyond "put the prompt in a file"?
**Answer:** Version control with an explicit version identifier (not inline-interpolated strings scattered across application code with no history), the full regression/eval suite run against any prompt change before merge exactly like a code change, and code review that treats a prompt diff as a logic change with potentially larger blast radius than an equivalent-sized code diff. This also underpins judge-drift attribution: a `prompt_template_hash` logged with a score is only meaningful if the prompt is genuinely a stable, hashable versioned artifact.
**Follow-up trap:** *"Isn't this overkill for a prompt that gets tweaked constantly during development?"* — during active prototyping, lighter process is reasonable; the point where this becomes non-negotiable is once the prompt is serving real production traffic, where an unreviewed, unversioned prompt change is functionally an unreviewed, untested code deploy.

### Q10 — Staff-level: your provider announces deprecation of both the model your system uses and the model your judge uses, six weeks out, on different timelines. Walk through your plan.
**Testing:** synthesis — dependency management, calibration discipline, and CI cost awareness together.
**Answer:** Treat these as two separate, real migrations, not one config change, because they have different blast radii: the system-model migration risks changing actual output quality/behavior, and the judge-model migration risks changing what "correct" measures without the system changing at all. For each: identify the replacement version early, run the existing regression/eval suite against the new version in parallel with the old one well before the deprecation date (not on the deadline), and for the judge specifically, re-run full human-label calibration (`T08-llm-as-judge`) rather than assuming score continuity. Sequence matters — validate the system-model swap first using the *current, still-stable* judge, then validate the judge swap separately against a fixed set of reference traces, so a problem discovered late is attributable to one change, not an unbisectable combination of both landing at once.
**Follow-up trap:** *"Both deprecations land the same week and you only have capacity to properly validate one before the deadline. What do you do?"* — escalate for a deprecation extension or pin-and-pay-for-legacy-access if the provider offers it, rather than silently shipping an under-validated swap on a system serving real traffic; if truly forced to choose, prioritize whichever swap has the larger measured historical blast radius (usually the system model, since judge drift is at least partially self-diagnosing via the version-logging discipline in Q4-Q5, while a system-model regression reaching production silently is the more expensive failure).

---

## Red flags that fail you

- Saying LLM systems "can't be tested" because the model is nondeterministic.
- Asserting exact response text as the primary test strategy.
- Retrying a flaky test until it passes instead of measuring and reporting the pass rate.
- Referencing a judge model by a rolling alias with no pinned version, and no explanation of how drift would even be detected.
- Treating a single before/after eval comparison as sufficient evidence of no regression.
- Running the full live-model eval suite on every commit with no cost-tiering, or conversely never running it and relying purely on cassettes.
- Not knowing that temperature 0 doesn't guarantee determinism, or attributing all nondeterminism vaguely to "GPUs" without the batch-size/reduction-kernel mechanism.
- Claiming a green CI/eval suite proves production correctness with no caveat about coverage gaps.

## Cheat card

```
WHY T=0 ISN'T DETERMINISTIC   fixes token-selection rule, not the logits.
  batch-size-dependent reduction kernels (matmul/attention/norm, FP addition
  not associative) + MoE expert-routing contention (your token's routing
  depends on concurrent batch) -> real run-to-run divergence. Batch-invariant
  kernels fix it at ~60%+ throughput cost -- almost never the prod default.

ASSERT INVARIANTS NOT STRINGS   schema valid · required fields present ·
  tool called w/ right arg shape · cost/token budget · forbidden substrings
  absent. NEVER assert exact wording -- #1 cause of suites disabled
  test-by-test.

N-RUNS + THRESHOLD, not single pass/fail   run 5-10x, report pass rate /
  mean+stddev, gate on threshold (e.g. 8/10). NEVER retry-until-green --
  that destroys the exact variance signal you're trying to measure.

GOLDEN TRAJECTORIES (multi-step, agent or not)   assert tool sequence +
  final STATE (vs reality) + cost/step envelope. NEVER exact wording.
  Validate the golden: inject a known-wrong run, confirm it FAILS.

JUDGE DRIFT   judge is a model too -> can silently version-bump under a
  rolling alias. SYMPTOM: score moves on stable prompt+model, nothing in
  diff explains it. FIX: pin exact dated judge_model_id + rubric_version +
  prompt_template_hash as a contract; log the FULL tuple with every score;
  ANY change to the tuple = full human-label re-calibration, not a config edit.

EVAL-AS-CI: COST   single judge call ~$0.05-0.50. 5K-case suite/run ~
  $250-2500. Tier it: cheap/deterministic+cassette tier blocks EVERY merge;
  full live eval tier gates only prompt/tool/model-touching PRs.

ROLLING WINDOW REGRESSION   track metrics over N releases, not one before/
  after diff. ~5pt faithfulness drop over ~a week = real regression that
  latency/error-rate monitoring won't catch (requests still succeed).

PROVIDER DEPRECATES MODEL MID-SUITE   real recurring event, not a surprise
  if watching changelogs. Re-baseline new version in PARALLEL with old
  before cutover. Treat as a dependency migration, not a config toggle --
  applies to BOTH the system model and the judge model, separately.
```

## Sources

- [Understanding and Mitigating Numerical Sources of Nondeterminism in LLM Inference (arXiv:2506.09501)](https://arxiv.org/pdf/2506.09501) — accessed 2026-08-01
- [Who Drifted: the System or the Judge? Anytime-Valid Attribution in LLM Evaluation Pipelines (arXiv:2606.15474)](https://arxiv.org/abs/2606.15474) — accessed 2026-08-01
- [Setting the temperature to zero will make an LLM deterministic? — Sara Zan](https://www.zansara.dev/posts/2026-03-24-temp-0-llm/) — accessed 2026-08-01
- [Building a Production LLM Evaluation Harness in Pytest: Cost-Bounded, Flake-Aware, CI-Gated](https://dev.to/velsof/building-a-production-llm-evaluation-harness-in-pytest-cost-bounded-flake-aware-ci-gated-26pc) — accessed 2026-08-01
- [AgentAssay: Token-Efficient Regression Testing for Non-Deterministic AI Agent Workflows (arXiv:2603.02601)](https://arxiv.org/pdf/2603.02601) — accessed 2026-08-01
- [LLM Model Drift Detection 2026: Monitoring AI Degradation](https://stackpulsar.com/blog/llm-model-drift-detection/) — accessed 2026-08-01
- `curriculum/07-agentic-ai/25-agent-testing.md` (`T07-agent-testing`) — cassette pattern, golden-trajectory assertion discipline, flakiness-budget mechanics this module extends beyond the agent-specific case
- `curriculum/08-eval-observability/02-llm-as-judge.md` (`T08-llm-as-judge`) — judge biases (position/verbosity/self-preference), calibration methodology, Cohen's kappa/Krippendorff's alpha workflow
- `curriculum/19-testing-quality/01-test-strategy.md` (`T19-test-strategy`) — general test-pyramid/trophy strategy this module specializes for LLM systems
- `curriculum/19-testing-quality/10-ml-testing.md` (`T19-ml-testing`) — classical ML testing (data/model/behavioral/metamorphic/drift layers), the adjacent but distinct discipline for non-generative ML

## Changelog
- 2026-08-01 — created
