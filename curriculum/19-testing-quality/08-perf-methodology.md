# Perf Testing Method: Baseline, Soak, Spike, Breakpoint; Reading Results

> **Track:** T19 Testing & Quality Engineering · **Time:** 2h · **Prereqs:** T19-load-testing (read together)
> **Module id:** `T19-perf-methodology` · **Tags:** performance
> **Updated:** 2026-07-26

## The 30-second version

Load testing (the previous module) is the mechanism — the tool, the traffic model. Performance methodology is the discipline of *which test to run to answer which question*, and the four standard tests answer four genuinely different questions that get conflated constantly: a baseline test establishes what "normal" looks like under expected load so every later test has something to compare against; a soak test runs expected load for hours or days to catch degradation that only accumulates over time (memory leaks, connection pool exhaustion, log/disk growth, cache eviction pathology); a spike test ramps load up sharply, back down, and repeats, to see whether the system survives sudden bursts and — just as importantly — recovers cleanly afterward rather than staying degraded; a breakpoint test deliberately pushes load past any realistic level until something breaks, to find the actual ceiling and, more usefully, *how* it fails (graceful degradation and shed load, versus cascading failure that takes down healthy capacity too). A benchmark is a different thing entirely from a load test: a benchmark measures a fixed unit of work's performance in isolation (a database driver's serialization speed, a hashing function's throughput) under controlled, repeatable conditions to compare implementations or catch regressions between versions; a load test measures a whole system's behavior under realistic concurrent traffic, where the interesting effects (contention, queueing, cascading failure) only exist because of that concurrency. And averages lie categorically: a p50 of 50ms sitting next to a p99 of 4 seconds means 1% of your users — which at any real scale is thousands of people — are having a genuinely broken experience that the average completely hides, and averages get worse as tail latency worsens because a handful of extreme outliers can pull a mean up while barely moving a median.

## Why this gets asked

Because "we load tested it and it passed" is one of the most common false-confidence statements in engineering, and the interviewer wants to know if you actually understand which specific question a given test answers — someone who ran one 5-minute load test and calls the system "performance tested" hasn't checked for the leak that only shows up after 6 hours, hasn't checked whether the system recovers after a burst, and doesn't know the actual capacity ceiling. They've likely watched a service that "passed load testing" degrade over a multi-day period (a soak-test gap) or fail to recover after a traffic spike during an incident (a spike-test gap), and want someone who reasons about performance testing as a portfolio of distinct questions, not a single checkbox.

---

## Lineage: past → present → future

**What came before.** Performance testing pre-2000s was largely capacity planning by extrapolation — measure throughput at a few load points, fit a curve, guess the ceiling — combined with production incidents as the de facto discovery mechanism for the failure modes that mattered (an application server that leaked memory over days, discovered when it OOM'd on a Sunday, not in a pre-release test). The pain: a single "load test passed" checkbox before launch told you nothing about behavior over time (soak) or under bursty, non-uniform traffic (spike) or at the actual edge of capacity (breakpoint), because a single short test at a single load level is definitionally silent on all three of those questions — it can only speak to the one scenario it ran.

**Where it stands now.** The four-test taxonomy (baseline, load/soak, stress/spike, breakpoint/capacity) is broadly standard vocabulary across the industry (Grafana's, BlazeMeter's, and most enterprise performance-testing guides converge on essentially this set, sometimes with slightly different names — "endurance" for soak, "stress test" sometimes used interchangeably with breakpoint, sometimes as a synonym for spike, so always clarify which specific test someone means rather than assuming from the name alone). The live disagreement is less about the taxonomy and more about how much of this actually gets run in practice: many teams run a baseline and maybe a single load test before a major release and skip soak and breakpoint entirely because they're expensive (soak tests need hours-to-days of dedicated environment time; breakpoint tests deliberately break something, which is uncomfortable to do against anything resembling a shared environment) — and this gap is exactly where the "passed load testing, degraded/fell over in production anyway" failure mode comes from. Separately, there's a real and useful distinction increasingly emphasized in performance engineering literature between *benchmarks* (isolated, repeatable, comparative — did this code change make the hash function 8% slower) and *load tests* (system-level, concurrency-dependent — does the whole request path hold up at 500 concurrent users), with microbenchmarks specifically flagged as detecting real regressions that may not matter in practice (a 2% slowdown in an isolated function that's 0.01% of end-to-end latency) alongside real ones that do.

**Where it's heading.** Continuous/automated benchmarking in CI (frameworks doing per-commit microbenchmark tracking to catch performance regressions the moment they're introduced, rather than at a pre-release load test) is an active, growing practice — genuinely useful for the benchmark side of the benchmark/load-test distinction, and increasingly standard for performance-sensitive libraries and hot paths; this doesn't replace system-level load/soak/spike/breakpoint testing, which requires a different, heavier setup (a realistic environment, realistic traffic, real duration) that doesn't fit the same per-commit cadence. Expect continued growth in this direction as a confident trend, while the harder, more expensive system-level tests (soak, breakpoint) remain something most orgs still under-invest in relative to their actual production-incident cost — this gap is a known, not-yet-solved problem, not something to claim is fixed.

---

## Mental model

```
              WHAT QUESTION DOES EACH TEST ANSWER?

BASELINE     "What does normal look like?"           expected load, short duration
             └─ every other test's reference point

SOAK         "Does it degrade over TIME?"            expected load, LONG duration
             └─ catches: leaks, disk/log growth,      (hours-days)
                cache eviction pathology, connection
                pool exhaustion that accumulates

SPIKE        "Does it survive a BURST, and recover?"  sharp up-down-up-down cycles
             └─ catches: connection storms, autoscale  short duration per spike
                lag, whether recovery is clean or the
                system stays degraded after the burst passes

BREAKPOINT   "Where's the actual CEILING, and HOW      unrealistically high load,
              does it fail?"                           ramped until failure
             └─ catches: the real capacity number,
                graceful-shed vs. cascading-collapse
                failure mode

     None of these substitute for the others — each is silent
     on the failure mode the others are designed to catch.
```

## How it actually works

**Baseline test.** Run at expected/normal load for a representative duration (30-60 min is common), capture the full metric set — p50/p90/p95/p99 latency, throughput, error rate, CPU/memory/GC pause time, DB connection pool utilization — and store it as the reference every subsequent test (and every subsequent release) gets compared against. Without a baseline, "is this slower" has no answer; a baseline turns a one-off number into a trend.

**Soak test.** Same load as baseline, but sustained for hours to days. The mechanism this catches that a short test cannot: a memory leak that grows 2MB/hour is invisible in a 30-minute test (60MB growth, noise) and fatal in a 48-hour test (nearly 100GB growth, OOM). Concretely watch: heap growth over time (not just peak heap — the *slope*), GC pause frequency/duration trending upward (a sign of the collector working harder against fragmenting/growing live-object sets), connection pool exhaustion (connections leaked one at a time per request, invisible until the pool's absolute ceiling is hit hours in), disk/log growth rate against actual disk capacity, and cache hit-rate drift as an unbounded cache grows past available memory and starts evicting useful entries.

**Spike test.** Ramp sharply from baseline to a high multiple (commonly 3-10x baseline) over seconds to low minutes, hold briefly, drop back to baseline, repeat the cycle several times. Two things to check, and the second is the one people skip: (1) does the system survive the spike itself without cascading failure (dropped connections, timeout storms, thread-pool exhaustion), and (2) does it *recover* to baseline latency/error-rate after the spike passes, or does it stay degraded (a common real failure: a connection pool or cache that got poisoned/exhausted during the spike doesn't self-heal, so post-spike performance is permanently worse until a restart). A test that only checks "survived the spike" and stops before confirming recovery misses this second, common, and expensive failure mode.

**Breakpoint test.** Ramp load steadily upward past any realistic production level until the system visibly fails (error rate crosses a threshold, latency crosses an unacceptable bound, or throughput itself starts *decreasing* as load increases — the clearest sign you've passed the actual capacity ceiling and are now in resource-contention collapse). The number itself (say, "this service handles 2,400 req/s before p99 exceeds 2s") matters less than *how* it fails: a system that sheds load gracefully past its ceiling (rejects new requests with 503s while continuing to serve what it can) is fundamentally safer in production than one that cascades (a slow downstream dependency causes upstream thread-pool exhaustion, which then takes down capacity that would otherwise have been healthy — the classic "one slow dependency takes down the whole fleet" incident pattern).

**Benchmark vs. load test — the distinction interviewers specifically probe.** A benchmark measures a fixed, isolated unit of work under controlled, repeatable conditions — a microbenchmark timing a single function/method (JMH for JVM, `pytest-benchmark`/`timeit` for Python) in tight iteration, explicitly to compare two implementations or catch a regression between commits. Its scope is comparable to a unit test's scope, and 5-30 iterations are typically enough for a stable microbenchmark result. A load test measures the emergent behavior of a *whole system under concurrent, realistic traffic* — the interesting effects (queueing, lock contention, connection pool behavior, cascading degradation) only exist because of that concurrency and load, and cannot be observed by benchmarking any single function in isolation. The practical trap: a microbenchmark showing a function got 8% slower is a real, valid signal, but it may be *practically irrelevant* if that function is 0.01% of end-to-end request latency — and conversely, a load test can show a system-level regression (higher p99, more errors under load) with no single function benchmark showing any change at all, because the regression is in the interaction (a new lock, a connection pool misconfiguration, a cache with worse eviction behavior under real concurrency).

**Why averages lie — the arithmetic, not just the assertion.** Suppose 990 requests take 40ms and 10 requests (1%) take 4,000ms. Mean = (990×40 + 10×4000) / 1000 = (39,600 + 40,000) / 1000 = 79.6ms — the average looks like "somewhat slower than typical," completely hiding that 1% of users experienced a 100x-worse-than-typical request. p50 in this distribution is 40ms (correctly reflects "typical"); p99 is somewhere at or above 4,000ms (correctly reflects the tail). At real production scale — say 10,000 req/s — that 1% tail is 100 requests/sec experiencing a 4-second response, every second, continuously; averaged into a single "avg latency: 79.6ms" dashboard number, this is completely invisible, and it's exactly the traffic pattern real incidents live in (a specific shard, a specific cache-miss path, a specific slow dependency affecting a consistent subset of traffic). Percentiles (p95, p99, sometimes p99.9) are the standard fix precisely because they report "how bad is the tail," which is where user-visible pain and SLA violations concentrate, while the mean is dominated by (and mostly describes) the bulk of fast, unremarkable requests.

## Build it from scratch

The exercise that makes "averages lie" concrete rather than a slogan: generate a realistic latency distribution and compute both, side by side.
```python
# untested sketch — why averages lie, with real numbers
import random
import statistics

def simulate_latencies(n: int, tail_fraction: float = 0.01, tail_multiplier: float = 100) -> list[float]:
    typical = 40  # ms, "normal" latency
    latencies = []
    for _ in range(n):
        if random.random() < tail_fraction:
            latencies.append(typical * tail_multiplier * random.uniform(0.8, 1.2))
        else:
            latencies.append(typical * random.uniform(0.7, 1.3))
    return latencies

def percentile(data: list[float], p: float) -> float:
    s = sorted(data)
    idx = int(len(s) * p / 100)
    return s[min(idx, len(s) - 1)]

latencies = simulate_latencies(100_000)
print(f"mean:  {statistics.mean(latencies):.1f}ms")   # ~79-80ms — looks "mildly slow"
print(f"p50:   {percentile(latencies, 50):.1f}ms")    # ~40ms — "typical" is fine
print(f"p95:   {percentile(latencies, 95):.1f}ms")    # ~40-50ms — still looks fine!
print(f"p99:   {percentile(latencies, 99):.1f}ms")    # ~4000ms — the real story
print(f"p99.9: {percentile(latencies, 99.9):.1f}ms")  # confirms the tail's severity
```
Note p95 in this specific distribution (1% tail) still looks fine — this is the concrete reason p99 (or even p99.9 for systems at real scale) is the standard SLO metric, not p95: a 1% tail is entirely invisible at p95 and only becomes visible right around p99, which is exactly the threshold real incidents tend to sit at.

## How it's done in production

Production performance programs run baseline and (lightweight) regression-style load tests on a recurring cadence tied to releases (sometimes every deploy for a fast smoke-style check, weekly/pre-release for a fuller run), soak tests less frequently (pre-major-release, or continuously in a dedicated long-running environment for services where leaks have historically been a problem), spike tests around known traffic-pattern risk (before a product launch, a marketing campaign, a known seasonal peak), and breakpoint tests periodically to keep the known-capacity number current as the system evolves (a breakpoint found 6 months ago may no longer be accurate after a dependency upgrade, schema change, or infrastructure change). Dashboards report percentiles (p50/p95/p99, sometimes p99.9) by default, never a bare average, and results get compared against the stored baseline automatically (a CI-gated performance regression check fails the build if p99 regresses beyond a threshold versus the last approved baseline) rather than relying on a human eyeballing a chart.

| Symptom | Cause | Fix |
|---|---|---|
| Service "passed load testing" pre-launch, OOMs in production after 30+ hours | No soak test was run — only a short baseline/load test, silent on multi-hour accumulation effects | Add a soak test (hours-to-days at expected load) to the pre-release checklist for any service handling long-lived connections, caches, or in-memory state |
| Service handles a traffic spike fine during the spike, but stays slow for an hour afterward | Spike test only checked survival during the burst, not recovery after it — a connection pool or cache got exhausted/poisoned and doesn't self-heal | Extend spike tests to hold post-spike measurement long enough to confirm return to baseline latency/error rate, not just survival through the peak |
| Team reports "average latency is fine" while support tickets about slowness keep coming in | Dashboard reports mean, not percentiles; a real tail (1-5% of traffic) is being averaged away | Switch default dashboards and SLOs to p95/p99 (or p99.9 at high scale); treat mean latency as a secondary, not primary, metric |
| A microbenchmark shows a 10% regression in a hot function, but end-to-end load test shows no measurable change | The function is a small fraction of total request time; a real, valid microbenchmark regression that isn't practically significant at the system level | Track both, but gate releases on the load-test/system-level number for user-facing SLOs; use the microbenchmark for early, cheap regression detection on the specific component |
| Breakpoint test found capacity was 5,000 req/s six months ago; production now falls over at 3,000 req/s | System changed (new dependency, schema, added feature) since the last breakpoint test; the old number is stale | Re-run breakpoint tests periodically, tied to significant architecture/dependency changes, not treated as a one-time discovery |

## Tradeoffs & when NOT to use it

- **Don't run a breakpoint test against a shared production-adjacent environment without isolation.** Breakpoint tests deliberately push a system past failure by design; running one against shared infrastructure risks a real incident for unrelated tenants/services — use an isolated environment or a carefully scoped canary with real rollback capability.
- **Don't treat a single load test as covering soak, spike, and breakpoint questions.** Each requires a genuinely different test design (duration, ramp shape, target load); a single 10-minute test at expected load cannot answer "does it leak over time," "does it survive a burst," or "where's the ceiling."
- **Don't use microbenchmarks as your only performance regression signal for user-facing SLAs.** A microbenchmark regression may not matter at the system level, and a system-level regression can appear with zero microbenchmark change (interaction/contention effects); use both, but gate releases on system-level load-test numbers for user-facing commitments.
- **Don't run soak tests for stateless, ephemeral, short-lived-instance services where recycling happens more often than any leak could accumulate to matter.** If instances are recycled every 30 minutes by design (a common serverless/autoscaling pattern), a multi-day soak test is testing a scenario the architecture prevents from occurring — proportionate soak duration should match realistic instance lifetime, not be run reflexively regardless of architecture.
- **Don't report a single latency number (average or even just p50) as "the" performance metric.** Any single number, including a percentile, is incomplete without at least a full latency histogram or a small set of percentiles (p50/p95/p99) reported together — a senior answer always reports a spread, not a point estimate.

---

## Interview questions

### Q1 — What specific question does a soak test answer that a standard load test doesn't?
**Testing:** whether the candidate can name the accumulation mechanism, not just "soak tests run longer."
**Answer:** Whether the system degrades over time under sustained expected load — memory leaks, connection pool exhaustion, disk/log growth, cache eviction pathology — all of which require hours to days to manifest and are invisible in a 10-30 minute standard load test, where the same leak might only account for noise-level growth.
**Follow-up trap:** *"How long should a soak test run?"* — long enough to exceed the realistic lifetime of the accumulation mechanism you're worried about (if instances live for days between restarts, soak for at least that long); there's no universal duration, and running a soak test shorter than the realistic accumulation window defeats its purpose.

### Q2 — Why does a spike test need to measure recovery, not just survival?
**Answer:** A common real failure mode is a system that survives the burst itself but doesn't self-heal afterward — a connection pool or cache exhausted/poisoned during the spike stays in that state, so latency and error rate remain elevated well after load has returned to baseline, sometimes requiring a manual restart to clear. A test that stops measuring once the spike ends misses this entirely.
**Follow-up trap:** *"How would you actually observe a failure to recover in test data?"* — hold the post-spike measurement window at baseline load for long enough to see whether p99/error-rate returns to the pre-spike baseline value, not just whether it trends downward; "trending down" and "returned to baseline" are different claims.

### Q3 — Explain the difference between a benchmark and a load test.
**Answer:** A benchmark measures a fixed, isolated unit of work (a function, a driver call) under controlled, repeatable conditions to compare implementations or catch a regression between versions — its scope is comparable to a unit test. A load test measures a whole system's emergent behavior under realistic concurrent traffic, where the interesting effects (contention, queueing, cascading failure) only exist because of that concurrency and can't be observed by benchmarking any single component in isolation.
**Follow-up trap:** *"If a microbenchmark shows no regression, does that mean the system is fine under load?"* — no; a system-level regression can appear purely from interaction effects (a new lock, worse cache eviction under real concurrency, a connection pool misconfiguration) with zero change visible in any individual function's benchmark.

### Q4 — Why do averages lie about latency specifically, with a concrete numeric example?
**Answer:** If 990 of 1000 requests take 40ms and 10 (1%) take 4,000ms, the mean is about 79.6ms — looking like "somewhat slower than typical" — while p50 (40ms) correctly shows typical latency is fine, and p99 (≥4,000ms) correctly shows a real 1% tail is broken. At real scale (say 10,000 req/s), that 1% tail is 100 requests per second experiencing a 4-second response continuously, completely invisible in a single averaged dashboard number.
**Follow-up trap:** *"Wouldn't p95 catch this too?"* — not necessarily; with exactly a 1% tail, p95 sits entirely within the "typical" 990 requests and looks fine — this specific example is precisely why p99 (or p99.9 at higher scale) is the standard SLO metric rather than p95, since a small enough tail hides below p95 but not below p99.

### Q5 — What does it mean, mechanically, when throughput starts *decreasing* as offered load increases during a breakpoint test?
**Answer:** It means the system has passed its actual capacity ceiling and entered resource-contention collapse — added load is now consuming resources (CPU on retries, connection churn, lock contention) faster than it's producing completed work, so total completed throughput falls even as more requests are thrown at the system. This is the clearest, most unambiguous signal of having found the real breakpoint, more reliable than watching latency alone (which can degrade gradually before this point).
**Follow-up trap:** *"Is finding this breakpoint number itself the goal?"* — the number matters less than the failure *shape*: a system that sheds load gracefully (503s, controlled rejection) past this point is far safer in production than one that cascades (slow downstream causing upstream thread-pool exhaustion, taking down otherwise-healthy capacity) — the interview answer should distinguish these explicitly.

### Q6 — Your team ran one 15-minute load test before a major release and calls the service "performance tested." What's missing, and why does it matter?
**Answer:** Missing soak (no visibility into multi-hour degradation), spike (no visibility into burst survival or recovery), and breakpoint (no known actual capacity ceiling or failure mode) — a single short test at one load level is, by construction, silent on all three of those questions, and each has caused real production incidents independently (OOM after hours, staying degraded after a traffic spike, cascading collapse at an unknown ceiling).
**Follow-up trap:** *"Is running all four always necessary before every release?"* — no; proportion the investment to risk and change — a low-risk config-only release may only need the recurring baseline check, while a release touching connection handling, caching, or resource lifecycle genuinely warrants soak; the senior answer names which specific test maps to which specific risk rather than treating all four as mandatory boilerplate.

### Q7 — A microbenchmark shows a hot function got 8% slower after a refactor, but the system-level load test shows no measurable change in p99. How do you reason about whether to block the release?
**Answer:** Both results can be simultaneously correct and non-contradictory: an 8% slowdown in a function that's a tiny fraction of total end-to-end latency (say 0.01% of request time) is a real regression that's practically invisible at the system level. The decision isn't "which number is right," it's whether this function is on a path likely to become more significant later (a growth trajectory, an upcoming increased call frequency) — if not, don't block the release on the microbenchmark alone, but do track it so it doesn't silently compound over many small refactors ("death by a thousand 8% regressions" is a real failure mode too).
**Follow-up trap:** *"So should you just ignore microbenchmark regressions that don't show up at the system level?"* — no, track and gate them with a separate, appropriately looser threshold (microbenchmarks are for early, cheap detection); "doesn't matter today" isn't the same as "will never matter," especially if the function's usage grows.

### Q8 — How would you decide the target load level for a spike test?
**Answer:** Base it on a real or plausible traffic event specific to the system — a known marketing campaign multiplier, a historical peak-to-normal ratio from actual logs, or (for a new product without historical data) a documented, explicitly-stated assumption about worst-case burst size — rather than an arbitrary round number. Common practice ranges from 3-10x baseline, but the number should be traceable to an actual scenario, not picked for being a "big enough" multiple.
**Follow-up trap:** *"What if the real traffic spike ends up being larger than what you tested?"* — this is exactly what the breakpoint test is for; a spike test validates a specific plausible scenario, a breakpoint test finds the actual ceiling regardless of scenario — running both, not just one, covers this gap.

### Q9 — Why might running a multi-day soak test be the wrong investment for a particular service?
**Answer:** If the service's actual instances are recycled well before any realistic leak could accumulate to matter (e.g., an autoscaled, stateless service where instances live 30 minutes by design), a multi-day soak test is testing a scenario the architecture already prevents — the proportionate soak duration should match realistic instance lifetime, and spending the time/cost of a multi-day test there is disproportionate to the actual risk.
**Follow-up trap:** *"So stateless services never need soak testing?"* — not quite; even short-lived instances can suffer accumulation effects within their actual lifetime (a leak that matters within 30 minutes, not just within days) — the right soak duration is "at least as long as realistic instance lifetime," which can still be short, not "skip soak entirely for anything stateless."

### Q10 — Staff-level: leadership asks why the team needs a dedicated soak/breakpoint testing environment when the load-testing CI job already runs on every PR. How do you make the case?
**Answer:** The per-PR CI load test is answering a narrow, valuable question (did this specific change introduce an obvious immediate regression) at a cadence and duration (minutes) that structurally cannot answer the soak question (hours-to-days accumulation) or the breakpoint question (deliberately pushing past failure, which is unsafe to do on every PR against shared infrastructure). Make the case with the actual incident cost: name the specific production incidents (or industry-known patterns) that soak/breakpoint gaps cause — multi-hour OOMs, cascading failures at unknown capacity ceilings — and show that a dedicated, less-frequent (not per-PR) environment for these tests is proportionate to that cost, not redundant with the fast per-PR check, because it answers a different question on a different timescale.
**Follow-up trap:** *"Couldn't you just run a longer CI job occasionally instead of a separate environment?"* — you could schedule the same test types on a different cadence without necessarily needing wholly separate infrastructure, and this is a reasonable middle ground for smaller orgs — the substantive point isn't "you need separate infra," it's "you need the actual soak/spike/breakpoint test designs run somewhere, on some cadence," and the interviewer is testing whether you conflate "this needs to happen" with "this needs to happen exactly this way."

---

## Red flags that fail you

- Using "load test," "stress test," "soak test," and "performance test" interchangeably without being able to name what distinguishes them.
- Reporting or defending average latency as the primary performance metric.
- Treating a single load test run as validating soak, spike, and breakpoint behavior simultaneously.
- Confusing a benchmark (isolated unit, comparative) with a load test (whole system, concurrency-dependent).
- No answer for "how does the system fail" beyond a single number at breakpoint (missing the graceful-shed vs. cascading distinction).

## Cheat card

```
BASELINE: expected load, short duration -> establishes the reference
  point every later test/release compares against.

SOAK (endurance): expected load, HOURS-DAYS -> catches leaks, log/disk
  growth, connection pool exhaustion, cache eviction pathology that
  only accumulate over time. Duration must exceed realistic accumulation
  window / instance lifetime.

SPIKE: sharp ramp up/down, repeated cycles -> catches burst survival
  AND recovery. Common gap: teams check survival, skip checking the
  system actually returns to baseline latency afterward.

BREAKPOINT: ramp past realistic load until failure -> finds real
  capacity ceiling. THROUGHPUT DECREASING as load increases = passed
  the ceiling, in contention collapse. Care about failure SHAPE
  (graceful shed/503s) vs. cascading collapse, not just the number.

BENCHMARK != LOAD TEST: benchmark = isolated unit, controlled,
  comparative (5-30 iterations often enough). Load test = whole
  system, concurrency-dependent emergent behavior (queueing,
  contention, cascading failure).

AVERAGES LIE: e.g. 990 reqs@40ms + 10 reqs@4000ms -> mean ~79.6ms
  (looks "mildly slow"), p50=40ms (fine), p99>=4000ms (real story).
  A 1% tail can hide below p95 and only surface at p99/p99.9 — this
  is WHY p99 is the standard SLO metric, not p95.

DRIFT (perf number staleness): re-run breakpoint periodically —
  a 6-month-old ceiling number is stale after dependency/schema changes.
```

## Sources
- [A Guide to Soak Testing and Spike Testing — Perforce BlazeMeter](https://www.blazemeter.com/blog/soak-testing-and-spike-testing) — accessed 2026-07-26
- [Types of load testing — Grafana Labs](https://grafana.com/load-testing/types-of-load-testing/) — accessed 2026-07-26
- [Benchmarking vs. Performance Testing — ASSIST Software](https://assist-software.net/blog/benchmarking-testing-vs-performance-testing-applications-know-difference) — accessed 2026-07-26
- [What is a microbenchmark? — Code Blueprint](https://www.codeblueprint.co.uk/2016/10/08/what-is-microbenchmark.html) — accessed 2026-07-26
- [Why Percentiles Matter More Than Average Response Time in Performance Testing — Oleh Koren, Medium](https://medium.com/@oleh.koren96/why-percentiles-matter-more-than-average-response-time-in-performance-testing-529c9e235d8f) — accessed 2026-07-26

## Changelog
- 2026-07-26 — created
