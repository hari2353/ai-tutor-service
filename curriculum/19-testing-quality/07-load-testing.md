# Load & Stress: JMeter, Locust, k6, Gatling — Modelling Real Traffic

> **Track:** T19 Testing & Quality Engineering · **Time:** 3h · **Prereqs:** T19-perf-methodology (read together)
> **Module id:** `T19-load-testing` · **Tags:** performance, critical
> **Updated:** 2026-07-26

## The 30-second version

Load testing answers "does the system hold up under realistic traffic," and the word doing the work is *realistic* — the most common mistake is writing a closed-loop script that hammers one endpoint as fast as possible with zero think time, which measures your load-generator's throughput ceiling, not your system's behavior under actual user traffic. The four tools that matter in 2026: k6 (Grafana, JS-scripted, developer-first, CI-native, current stable 1.3.0 with k6 2.0 adding AI-agent integration and JSON summary output) for API/service load testing in CI/CD; Locust (Python, write tests as Python classes, distributed via multiprocessing/multiple workers) for Python-native teams and complex stateful user behavior; Gatling (Scala DSL, Netty-based core, highest throughput-per-machine of the open-source options, best-in-class HTML reports) for high-throughput API load testing where report quality and per-agent efficiency matter; and JMeter (Java, GUI-first, 20-year plugin ecosystem, broadest protocol coverage — HTTP, JDBC, JMS, LDAP, FTP, TCP) for legacy/enterprise protocol breadth and non-HTTP load testing. Modeling real traffic means three things together: an arrival process (Poisson/open-model arrivals for public-internet traffic where users don't wait for each other, versus closed-model fixed concurrent users for internal batch-style load), think time (random delay between a user's actions, typically log-normal, not a fixed sleep), and a ramp profile (gradual increase to target load, not an instant step function, because instant steps hide the difference between "can't handle this load" and "can't handle a sudden burst of connection setup"). Get the traffic model wrong and every downstream number — the p99 you report, the breakpoint you find — describes a scenario that doesn't exist in production.

## Why this gets asked

Because load testing is one of the easiest disciplines to fake competence in — everyone can run a tool and generate a chart — and one of the easiest to get wrong in a way that produces confident, useless numbers. The interviewer has almost certainly seen a load test "pass" at 10,000 fake concurrent users hammering one endpoint with no think time, ship to production, and fall over at 500 real users because the real traffic pattern (bursty, with realistic pauses, hitting a mix of endpoints, with connection churn) stressed a completely different part of the system than the synthetic test did. They want to know if you understand load generation as *traffic modeling*, not just tool operation.

---

## Lineage: past → present → future

**What came before.** Early performance testing (1990s-2000s) was largely manual stopwatch testing or simple scripted HTTP replay tools, and Apache JBMeter (1998, later JMeter) was one of the first widely-adopted tools to formalize scripted, repeatable load generation with a GUI test-plan builder — a real improvement over ad hoc scripting, but the GUI-first, XML-test-plan-underneath model became its own pain as teams tried to put load tests in version control and CI: JMeter `.jmx` files are verbose XML, painful to diff and code-review, and the GUI mode itself isn't meant for actual load generation (JMeter's own docs recommend running in non-GUI/CLI mode for real load, using the GUI only to build the plan) — a subtlety that trips up nearly everyone's first JMeter load test, which runs the GUI directly and gets misleading results because the GUI's own rendering and listener overhead competes with the load generation for resources.

**Where it stands now.** The field split by audience: k6 and Gatling target developers who want load tests as code, reviewed like code, run in CI like code (JS and Scala DSLs respectively); Locust targets Python-native teams with the same "test as code" philosophy using Python classes and decorators; JMeter remains the choice when protocol breadth (JDBC, JMS, LDAP, legacy TCP/SOAP) or an existing plugin/team-knowledge investment outweighs the developer-experience gap. TestDevLab's 2026 analysis reports Locust handling roughly 5x more concurrent simulated users than JMeter on identical 8GB hardware, reflecting JMeter's heavier per-virtual-user thread/JVM memory footprint (JMeter allocates a full thread per virtual user by default) versus Locust's greenlet-based (gevent) concurrency model and Gatling's Netty-based async I/O — a live, practically important distinction when deciding how many load-generator machines a large test needs. The live disagreement isn't about which tool is "best" (there's no universal winner, and market position is genuinely split: k6 owns developer-experience/CI-native, Locust owns Python shops, JMeter owns protocol breadth and legacy investment, Gatling owns per-agent throughput and reporting) but about traffic modeling discipline — plenty of teams using any of these four tools still write closed-loop, zero-think-time scripts that misrepresent real traffic, and the tool doesn't fix that; only correct arrival-process and think-time modeling does.

**Where it's heading.** k6 2.0 (announced 2026) adds explicit AI-agent integration (`k6 x agent` for bootstrapping agentic testing workflows in tools like Claude Code/Cursor) and machine-readable JSON summary output specifically aimed at CI/CD and AI-agent consumption — a concrete, already-shipping trend toward load testing being driven and interpreted by automated pipelines and agents rather than only humans reading dashboards. Cloud-hosted, managed variants of these tools (Grafana Cloud k6, Gatling Enterprise) are absorbing more of the distributed-load-generation and historical-trend-analysis problem that used to require self-hosted Locust/JMeter clusters — a confident trend for teams willing to pay for it, not yet universal because self-hosted remains cheaper and sufficient for smaller-scale needs.

---

## Mental model

```
CLOSED MODEL (wrong for public-internet traffic)          OPEN MODEL (right for it)
─────────────────────────────────────────────             ─────────────────────────────
Fixed N virtual users, each:                               New requests ARRIVE at a rate
  request -> wait for response -> repeat                   independent of how fast the
                                                             system responds
  ┌─┐→req→[SYSTEM]→resp→┌─┐ (loop)                          arrivals: •  • •   •  ••  •
  │u│                    │u│                                          (Poisson process,
  └─┘                    └─┘                                          rate λ req/s)
     N users total, ALWAYS N in flight                            system just has to
     — if the system slows down, load                             keep up with λ, or
     AUTOMATICALLY drops (users are                                a queue builds —
     waiting, not arriving faster)                                 THIS is what a real
                                                                    slow system actually
     THIS HIDES THE FAILURE MODE                                   experiences: unbounded
     you actually care about                                       queueing, not self-
                                                                     limiting demand
```
The closed-model trap: if your system gets slower, a closed-model test's effective request rate drops too (each virtual user is waiting longer between requests), so throughput looks "stable" even as latency explodes — masking the exact failure mode (queue buildup, cascading timeouts) that kills systems in production, where new users keep arriving regardless of how slow you've become.

## How it actually works

**Arrival distributions.** Real internet traffic is well-modeled as a Poisson arrival process for the aggregate of many independent users — the number of arrivals in a fixed window follows a Poisson distribution, and the *inter-arrival time* between consecutive requests follows an exponential distribution with rate λ (mean inter-arrival time = 1/λ). This matters concretely: a naive load test that sends a request exactly every 100ms (deterministic, λ=10/s) produces perfectly smooth, unrealistically uniform load; real traffic at the same average rate has bursts and lulls (some 100ms windows get 3 requests, some get 0), and burst handling — not average-rate handling — is very often what actually breaks a system (connection pool exhaustion during a burst, not a graceful average).

**Think time.** Real users pause between actions — reading a page, filling a form — and this pause is typically modeled as log-normal (a right-skewed distribution: most users pause a "typical" amount, a long tail pauses much longer, and pauses are never negative) rather than a fixed delay. Skipping think time entirely (issuing the next request the instant the previous response arrives) is the single most common way a load test overstates a per-user request rate — a user who actually issues 1 request per 8 seconds of real browsing gets modeled, with zero think time, as issuing requests as fast as the network allows, which can be 50-100x the real per-user rate and consequently requires 50-100x fewer virtual users to reach a target aggregate throughput, fundamentally changing what you're actually testing (connection/session-count behavior at unrealistic concurrency, not realistic user concurrency).

**Ramp profiles.** A step function (0 to 10,000 users instantly) tests something real but narrow: whether the system survives a sudden burst of connection setup, TLS handshakes, and cold caches all at once. A gradual ramp (0 to 10,000 over 10 minutes) tests a different, usually more representative question: whether the system holds up as load organically grows. Conflating the two — running only a ramp and calling it done — misses genuine burst-driven failure modes (a flash-sale traffic spike, a cache eviction storm); conflating the other way (only step tests) misses gradual degradation patterns (a memory leak that only manifests after sustained load, a connection pool that degrades under prolonged pressure) — see the perf-methodology module for the full baseline/soak/spike/breakpoint taxonomy this feeds into.

**k6 script — open-model traffic with the `ramping-arrival-rate` executor** (the mechanism that actually implements open-model, arrival-rate-driven load rather than closed-model fixed-VU load):
```javascript
// untested sketch — k6, realistic open-model traffic with think time
import http from 'k6/http';
import { sleep, check } from 'k6';
import { randomIntBetween } from 'https://jslib.k6.io/k6-utils/1.2.0/index.js';

export const options = {
  scenarios: {
    realistic_traffic: {
      executor: 'ramping-arrival-rate',   // OPEN model: arrivals independent of response time
      startRate: 10,                      // requests/sec at t=0
      timeUnit: '1s',
      preAllocatedVUs: 200,               // pool k6 can draw from to sustain the arrival rate
      maxVUs: 1000,                       // hard ceiling if the system slows and VUs pile up
      stages: [
        { target: 50,  duration: '2m' },  // ramp: 10 -> 50 req/s over 2min
        { target: 200, duration: '5m' },  // ramp: 50 -> 200 req/s over 5min
        { target: 200, duration: '10m' }, // sustain at 200 req/s (this is the actual load test)
        { target: 0,   duration: '2m' },  // ramp down
      ],
    },
  },
  thresholds: {
    http_req_duration: ['p(95)<300', 'p(99)<800'],  // fail the test run if these are breached
    http_req_failed: ['rate<0.01'],
  },
};

export default function () {
  const res = http.get('https://staging.example.com/api/search?q=widgets');
  check(res, { 'status is 200': (r) => r.status === 200 });

  // think time: log-normal-ish approximation via randomIntBetween on a skewed range,
  // NOT a fixed sleep(1) — real users don't pause a uniform, identical amount
  sleep(randomIntBetween(2, 12) / 2);  // ~1-6s pause, weighted toward the shorter end
}
```
The `preAllocatedVUs`/`maxVUs` distinction is the mechanical core of open-model testing in k6: the executor tries to sustain the *arrival rate* you specified, allocating however many concurrent VUs it needs to do so — if the system slows down and requests take longer, k6 draws more VUs (up to `maxVUs`) to keep the arrival rate constant, and hitting `maxVUs` is itself a load-test finding (it means the system can't sustain that arrival rate without unbounded concurrency growth).

**Locust script — Python classes with weighted tasks and built-in think time via `wait_time`:**
```python
# untested sketch — Locust, weighted tasks + log-normal-ish think time
from locust import HttpUser, task, between, LoadTestShape
import random

class RealisticUser(HttpUser):
    # between() models think time as uniform(1, 6)s per user, per iteration —
    # Locust also supports custom wait_time functions for a real log-normal draw
    wait_time = between(1, 6)

    def on_start(self):
        self.client.post("/api/login", json={"user": "loadtest", "pass": "x"})

    @task(10)          # weight 10: this is the common path — 71% of traffic
    def search(self):
        self.client.get("/api/search?q=widgets", name="/api/search")

    @task(3)           # weight 3: less common — ~21% of traffic
    def view_item(self):
        item_id = random.randint(1, 10000)
        self.client.get(f"/api/items/{item_id}", name="/api/items/[id]")

    @task(1)           # weight 1: rare, ~7% of traffic — but often the expensive path
    def checkout(self):
        self.client.post("/api/checkout", json={"item_id": random.randint(1, 10000)})

# custom ramp shape: mirrors a real traffic curve instead of a flat step
class RampUpShape(LoadTestShape):
    stages = [
        {"duration": 120, "users": 50,  "spawn_rate": 5},
        {"duration": 300, "users": 200, "spawn_rate": 5},
        {"duration": 600, "users": 200, "spawn_rate": 5},   # sustained plateau
        {"duration": 120, "users": 0,   "spawn_rate": 10},  # ramp down
    ]

    def tick(self):
        run_time = self.get_run_time()
        for stage in self.stages:
            if run_time < stage["duration"]:
                return (stage["users"], stage["spawn_rate"])
            run_time -= stage["duration"]
        return None  # stop the test
```
Locust's default model is closer to closed-loop (a fixed number of simulated users, each looping through tasks with `wait_time` between iterations) rather than k6's open-arrival-rate executor — which is fine and often *more* representative for internal/authenticated systems with a genuinely bounded concurrent user population (e.g., an internal tool with 500 named users), and less representative for public, unauthenticated, arrival-driven traffic (a public API, a marketing site during a launch) where an open model is the honest choice. Knowing which model matches your actual traffic is the graded skill here, not memorizing either tool's default.

## Build it from scratch

The exercise that proves you understand traffic modeling rather than tool syntax: implement a minimal open-model load generator with proper inter-arrival timing and log-normal think time, without any framework.
```python
# untested sketch — minimal open-model async load generator
import asyncio
import random
import time
import httpx

async def poisson_arrivals(rate_per_sec: float):
    """Yields control at intervals drawn from an exponential distribution —
    the correct inter-arrival model for a Poisson arrival PROCESS."""
    while True:
        yield
        await asyncio.sleep(random.expovariate(rate_per_sec))

async def simulate_user_session(client: httpx.AsyncClient, results: list):
    t0 = time.perf_counter()
    resp = await client.get("/api/search?q=widgets")
    results.append((time.perf_counter() - t0, resp.status_code))

    # log-normal think time: mean ~3s, right-skewed (mu, sigma chosen so
    # median ~3s but a real tail of slower users exists)
    await asyncio.sleep(random.lognormvariate(mu=1.1, sigma=0.6))

    t0 = time.perf_counter()
    resp = await client.get(f"/api/items/{random.randint(1, 10000)}")
    results.append((time.perf_counter() - t0, resp.status_code))

async def run_open_model_test(target_rate: float, duration_s: int, base_url: str):
    results = []
    async with httpx.AsyncClient(base_url=base_url, timeout=10.0) as client:
        deadline = time.monotonic() + duration_s
        tasks = set()
        async for _ in poisson_arrivals(target_rate):
            if time.monotonic() > deadline:
                break
            tasks.add(asyncio.create_task(simulate_user_session(client, results)))
            tasks = {t for t in tasks if not t.done()}
        await asyncio.gather(*tasks, return_exceptions=True)
    return results

# usage: asyncio.run(run_open_model_test(target_rate=50, duration_s=300,
#                                          base_url="https://staging.example.com"))
```
Building this once — and specifically getting `random.expovariate` for inter-arrival time and `random.lognormvariate` for think time right — makes it obvious why a `for i in range(10000): send_request()` loop (the naive first instinct) measures something entirely different from real traffic, before ever opening a real tool's docs.

## How it's done in production

Real load-testing programs run the chosen tool (often k6 or Gatling for CI-gated pre-release checks, Locust for exploratory Python-team-driven testing, JMeter where protocol breadth is non-negotiable) from **distributed load generators** — a single machine generating "load" is itself a bottleneck (network card, CPU for TLS handshakes, file descriptor limits) well before most real systems' actual capacity limit, so k6 Cloud/Grafana Cloud k6, Gatling Enterprise, Locust's built-in distributed mode (`--master`/`--worker` processes), or JMeter's distributed testing (remote JMeter server nodes controlled by one client) all exist specifically to generate load from multiple machines and aggregate results centrally. Production load tests also model **realistic traffic mix** (not one endpoint — a weighted distribution across the actual top-N endpoints by real production traffic share, ideally derived from real access logs rather than guessed) and **realistic payload/data variance** (not the same product ID or search query on every request, which lets caches give artificially perfect hit rates that hide real cache-miss latency).

| Symptom | Cause | Fix |
|---|---|---|
| Load test "passes" cleanly at high throughput, production falls over at a fraction of that load | Closed-model, zero-think-time script tested raw request-handling throughput on one endpoint, not realistic concurrent-user behavior with think time and a realistic endpoint mix | Rebuild the script as open-model (arrival-rate executor) with think time and a weighted multi-endpoint mix derived from real traffic logs |
| Single-machine JMeter/Locust load generator caps out well below expected system capacity | The load generator itself is bottlenecked (CPU on TLS handshakes, file descriptors, network egress) before the system under test is | Distribute load generation across multiple machines/workers; verify generator-side CPU/network isn't saturated during the test |
| Test looks fine at steady average throughput but production has periodic latency spikes under the same average load | Deterministic, uniform request spacing in the test hides burst behavior that a Poisson/exponential inter-arrival model would expose | Use an arrival-rate/open-model executor with proper random inter-arrival timing, not a fixed-interval loop |
| Cache hit rate in the load test is near 100%, but production cache hit rate is 60% and latency is much higher | Test reused the same few IDs/queries repeatedly, giving the cache an unrealistically easy workload | Sample request parameters (product IDs, search terms) from a realistic distribution matching real traffic (e.g., Zipfian for popularity-skewed access patterns), not a fixed small set |
| JMeter GUI-mode test shows wildly inconsistent numbers between runs on the same hardware | Running the actual load generation in GUI mode, where rendering/listener overhead competes with the load generator for CPU | Build the test plan in GUI mode, but always execute real load runs via CLI (`jmeter -n -t plan.jmx -l results.jtl`) |

## Tradeoffs & when NOT to use it

- **Don't use a closed-model (fixed concurrent users) test to represent public, unauthenticated, arrival-driven traffic.** It structurally cannot represent the failure mode where new demand keeps arriving regardless of system slowness — use an open/arrival-rate model there.
- **Don't use an open/arrival-rate model to represent a genuinely bounded internal user population** (an internal tool with 500 named employees who literally cannot exceed 500 concurrent sessions) — a closed model with realistic concurrency and think time is the accurate representation there, and an unbounded arrival-rate model would test a scenario that can't occur.
- **Don't pick Gatling for a team with zero Scala familiarity and a tight deadline** — the DSL's learning curve is real, and k6 (JS) or Locust (Python) will get a realistic test written faster for most teams, even though Gatling's per-agent throughput and report quality are genuinely best-in-class.
- **Don't pick JMeter as a new default for a greenfield HTTP-only service** — its GUI-first workflow, XML test plans, and heavier per-VU resource footprint are a real tax versus code-first tools, unless you specifically need its protocol breadth (JDBC, JMS, LDAP) or existing team expertise/plugins.
- **Don't run a load test as a one-off before a single big launch and call performance testing "done."** Traffic patterns, code, and infrastructure all drift; load testing (like the baseline/soak/spike/breakpoint methodology in the companion module) is a recurring practice tied to the release cycle, not a pre-launch checkbox.

---

## Interview questions

### Q1 — What's wrong with a load test script that sends the next request immediately after the previous response, with no delay?
**Testing:** whether the candidate identifies think time and its effect on required VU count.
**Answer:** It eliminates think time, which massively overstates each simulated user's real request rate — a user who actually issues one request per several seconds gets modeled as issuing requests as fast as the network allows, requiring far fewer virtual users to hit a target aggregate throughput than reality would, and testing a fundamentally different concurrency/connection-count scenario than production.
**Follow-up trap:** *"So just add a fixed sleep(1) between requests — problem solved?"* — a fixed, uniform delay is still unrealistic; real user pauses are right-skewed (log-normal), with a long tail of much slower users, and a uniform delay smooths out the burst/lull pattern that real traffic (and real failure modes) actually has.

### Q2 — Explain the difference between an open-model and closed-model load test, with an example of when each is correct.
**Answer:** Closed model: a fixed number of virtual users loop request→wait for response→repeat, so if the system slows down, each user's effective request rate drops too, making throughput look artificially stable while latency explodes — correct for genuinely bounded populations like an internal tool with a fixed number of named users. Open model: new requests arrive at a rate independent of how fast the system responds (Poisson/exponential inter-arrival), so a slow system experiences unbounded queue buildup exactly as it would with real, arrival-driven public traffic — correct for public APIs, marketing sites, anything where users don't wait for each other.
**Follow-up trap:** *"Which model does Locust use by default, and does that matter?"* — Locust's default is closer to closed-loop (fixed users looping with wait_time); this is fine for bounded populations but understates queueing behavior for open, arrival-driven traffic unless deliberately modeled with a custom shape/rate approach.

### Q3 — Why is running JMeter's actual load-generation phase in GUI mode a mistake?
**Answer:** The GUI's own rendering and listener overhead (updating live graphs, logging every sample to the UI) competes with the load generator for CPU and memory, producing both lower achievable throughput and less trustworthy latency numbers than the same test run headless. Build the test plan in the GUI, but execute real runs via CLI (`jmeter -n -t plan.jmx`).
**Follow-up trap:** *"Does this matter for k6/Locust/Gatling too?"* — the specific GUI-competing-with-load-generation mechanism is JMeter-specific (its GUI is a heavyweight Java Swing app doing live rendering); code-first tools don't have this failure mode in the same way, though any tool run on an under-resourced generator machine can bottleneck the generator itself, a related but distinct problem.

### Q4 — What's the mechanical difference between how k6's `ramping-arrival-rate` executor and a fixed-VU executor decide how much load to generate?
**Answer:** `ramping-arrival-rate` targets a specified request-arrival rate directly and allocates however many VUs (up to `maxVUs`) are needed to sustain it — if responses slow down, k6 spins up more concurrent VUs to keep the arrival rate constant. A fixed-VU executor holds VU count constant and lets the *effective* request rate fall as responses slow, which is the closed-model behavior.
**Follow-up trap:** *"What does it mean if a test hits maxVUs during a run?"* — that's itself a finding: it means the system under test can't sustain the target arrival rate without unbounded concurrency/queue growth, which is exactly the failure mode an open-model test is designed to surface — don't just raise maxVUs and rerun without noting why it was hit.

### Q5 — When would you choose Gatling over k6 for a new load-testing initiative, and what's the real cost of that choice?
**Answer:** Gatling's Netty-based async core gives it the highest throughput-per-machine of the open-source options and best-in-class HTML reporting, so for high-throughput API load testing where minimizing the number of load-generator machines and getting polished reports both matter, it's a strong choice. The real cost is the Scala DSL's learning curve for teams without JVM/Scala background — a team that will maintain these tests needs to actually be able to read and modify Scala, or the tests become a black box only one person can touch.
**Follow-up trap:** *"Isn't 'highest throughput per machine' always worth it?"* — not if the team can't maintain the tests afterward; a load-testing practice that only one Scala-literate engineer can extend is a bus-factor risk, and for many teams k6 (JS) or Locust (Python) written and maintained by the whole team is the more durable choice even at somewhat lower per-agent efficiency.

### Q6 — How would you model realistic traffic mix across endpoints, rather than testing one endpoint in isolation?
**Answer:** Derive a weighted distribution of request types from real production access logs (the actual proportion of search vs. product-view vs. checkout traffic), and encode that as weighted tasks (Locust's `@task(weight)`, or k6/Gatling's equivalent scenario weighting) rather than guessing proportions — testing one endpoint at high throughput in isolation misses interaction effects (shared connection pools, shared caches, shared downstream services) that only appear under a realistic mix.
**Follow-up trap:** *"What if you don't have real production logs yet (a new product)?"* — model from the closest available proxy (a similar existing product's traffic mix, or explicit product/UX assumptions about the user journey), and treat the traffic-mix assumption as a documented, revisitable input to the test — not a detail to skip because the "real" data doesn't exist yet.

### Q7 — Your load test shows near-100% cache hit rate and low latency; production shows 60% hit rate and much higher latency at the same throughput. Diagnose.
**Answer:** The test almost certainly reused a small, fixed set of request parameters (the same few product IDs/search terms) repeatedly, giving the cache an unrealistically easy workload. Real traffic has a much wider, typically Zipfian-skewed distribution of accessed items (a long tail of rarely-requested items alongside a few very popular ones), which the test needs to sample from to reproduce realistic cache-miss behavior.
**Follow-up trap:** *"Would using purely random IDs across the whole ID space fix this?"* — not necessarily; uniform random sampling across the whole space can *understate* cache effectiveness if real traffic is actually concentrated on popular items — matching the real access distribution (Zipfian or whatever the actual data shows) is more accurate than either extreme (fixed few IDs, or uniform random).

### Q8 — Explain why a step-function ramp (0 to 10k users instantly) and a gradual ramp (0 to 10k over 10 minutes) test different things.
**Answer:** A step function specifically stresses simultaneous connection setup, TLS handshakes, cold caches, and connection-pool/thread-pool cold-start behavior all at once — it answers "can the system survive a sudden burst" (e.g., a flash sale, a viral link). A gradual ramp answers a different question: whether the system degrades gracefully as load organically increases, surfacing issues like resource exhaustion that only appears past a certain sustained load, or a scaling policy that reacts too slowly. Running only one of the two misses the failure mode the other is designed to catch.
**Follow-up trap:** *"If you only have time for one, which do you run?"* — match it to the real traffic pattern the system actually experiences (a service behind a CDN with organic growth needs the ramp test more; a service that's the target of scheduled drops/flash sales needs the step/spike test more) rather than defaulting to either without that context — this overlaps directly with the spike-test discussion in the perf-methodology module.

### Q9 — A teammate proposes testing with the exact same request payload on every virtual user to make results "cleaner and easier to compare." What's wrong with this?
**Answer:** Identical payloads produce artificially favorable cache behavior, potentially skip real data-dependent code paths (a search query that always hits the same index shard, a checkout that always resolves the same discount logic), and hide payload-size/complexity variance that real traffic has — the resulting numbers are "clean" precisely because they're not measuring the messy reality the system will actually face.
**Follow-up trap:** *"Doesn't payload variance make results less reproducible and harder to compare across test runs?"* — use a fixed *random seed* for the variance generator so runs are reproducible while still varied — reproducibility and realism aren't actually in tension if you seed the randomness deliberately.

### Q10 — Staff-level: your team runs k6 in CI on every PR with a 2-minute load test, and it's never once failed a threshold even though production has had three load-related incidents this year. What's your diagnosis and plan?
**Answer:** A 2-minute test almost certainly can't surface the failure modes that matter in production — connection pool exhaustion under sustained load, memory growth that only appears after tens of minutes (soak-test territory), or a genuine capacity breakpoint that only appears well above the load level a 2-minute smoke-style test reaches. The CI test is answering "did this PR introduce an obvious immediate regression," a narrower and legitimate question, but the team appears to be treating it as their entire performance-testing practice. Plan: keep the fast PR-gate test for regression-catching, and add a separate, less frequent (nightly/weekly, or pre-release) longer-duration test program covering soak, spike, and breakpoint scenarios against realistic traffic models — see the perf-methodology module for the full taxonomy — since no single 2-minute test can answer all of those questions at once.
**Follow-up trap:** *"Why not just make the PR-gate test longer to catch everything?"* — because a 30+ minute test on every PR destroys development velocity for a benefit better achieved by a separate, correctly-scoped test cadence; name the actual tradeoff (fast feedback vs. thoroughness) rather than trying to force one test to serve both purposes.

---

## Red flags that fail you

- Describing a load test as "send N requests as fast as possible" without any concept of arrival rate, think time, or ramp.
- Not knowing the difference between open-model and closed-model load generation.
- Claiming one tool (k6, Locust, Gatling, or JMeter) is universally best without naming what it trades off against the others.
- Testing one endpoint at maximum throughput and calling it a load test for the whole system.
- Running JMeter load generation in GUI mode without knowing that's a mistake.

## Cheat card

```
TOOLS (2026): k6 (Grafana, JS, CI-native, stable 1.3.0 / 2.0 adds AI-agent
  hooks + JSON summary) — dev-first API load testing.
  Locust (Python classes, gevent-based) — Python teams, ~5x concurrent
  users vs JMeter on same 8GB box (TestDevLab 2026).
  Gatling (Scala DSL, Netty async core) — highest throughput/machine,
  best HTML reports; real Scala learning-curve cost.
  JMeter (Java, GUI test-plan + CLI execution, 20yr plugin ecosystem) —
  broadest protocol coverage (HTTP/JDBC/JMS/LDAP/FTP/TCP); ALWAYS run
  real load in CLI (-n) mode, never GUI mode.

OPEN MODEL: arrivals independent of response time (Poisson process,
  exponential inter-arrival). Right for public/unauthenticated traffic —
  slow system -> queue builds, exactly like reality.

CLOSED MODEL: fixed N users loop request->wait->repeat. Right for
  bounded internal populations. WRONG for public traffic — slow system
  hides itself by dropping effective request rate.

THINK TIME: log-normal, not fixed sleep(). Skipping it -> massively
  overstates per-VU request rate -> needs far fewer VUs than reality
  to hit a target throughput -> tests wrong concurrency scenario.

RAMP: step function tests sudden-burst survival (connection/TLS storm).
  Gradual ramp tests organic-growth degradation. Run BOTH; they catch
  different failure modes.

TRAFFIC MIX: weight endpoints by REAL production traffic share (access
  logs), vary payload/IDs (Zipfian, not fixed few) to avoid fake cache
  hit rates.

k6 ramping-arrival-rate: preAllocatedVUs/maxVUs — hitting maxVUs IS a
  finding (system can't sustain that arrival rate without unbounded
  concurrency growth).
```

## Sources
- [k6 2.0 release — Grafana Labs](https://grafana.com/blog/k6-2-0-release/) — accessed 2026-07-26
- [Grafana k6 release notes](https://grafana.com/docs/k6/latest/release-notes/) — accessed 2026-07-26
- [JMeter vs k6 vs Locust in 2026 — QAInsights](https://qainsights.com/jmeter-vs-k6-vs-locust-in-2026-which-load-testing-tool-should-you-pick/) — accessed 2026-07-26
- [Best Load Testing Tools 2026: JMeter vs Gatling vs k6 & 10 More — Vervali](https://www.vervali.com/blog/best-load-testing-tools-in-2026-definitive-guide-to-jmeter-gatling-k6-loadrunner-locust-blazemeter-neoload-artillery-and-more/) — accessed 2026-07-26
- [Gatling vs Locust: Which Load Testing Tool Wins in 2026? — loadtest.qa](https://loadtest.qa/blog/gatling-vs-locust/) — accessed 2026-07-26
- [k6 ramping-arrival-rate executor — Grafana k6 docs](https://grafana.com/docs/k6/latest/using-k6/scenarios/executors/ramping-arrival-rate/) — accessed 2026-07-26
- [Locust documentation — LoadTestShape](https://docs.locust.io/en/stable/generating-custom-load-shape.html) — accessed 2026-07-26

## Changelog
- 2026-07-26 — created
