# Resilience4j: Circuit Breaker, Bulkhead, Retry, Rate Limiter in Practice

> **Track:** T11 Polyglot Backend · **Time:** 1.5h · **Prereqs:** T21-resilience-catalogue, T11-spring-boot · **Updated:** 2026-08-03
> **Module id:** `T11-resilience4j` · **Tags:** java, resilience
> **Lab:** none yet — see `labs/py/02-agent-loop/` for the pattern if you want to build one

## The 30-second version

Resilience4j is the Hystrix successor — a lightweight, functional-composition fault-tolerance library for the JVM built around decorating a `Supplier`/`Function`/`CompletableFuture` with one or more of five modules: CircuitBreaker, Retry, RateLimiter, Bulkhead (two flavors), and TimeLimiter, each independently configurable and independently testable, unlike Hystrix's single monolithic command object. The single most-tested fact about the library: when you stack multiple `@Retry`, `@CircuitBreaker`, `@RateLimiter`, `@Bulkhead` annotations on one Spring method, **the execution order is fixed by the library, not by the order you wrote the annotations** — `Retry(CircuitBreaker(RateLimiter(TimeLimiter(Bulkhead(Method))))))`, Retry outermost, Bulkhead innermost, and reordering the annotations on the method changes nothing unless you explicitly override it via `*AspectOrder` properties. `RateLimiter` is a fixed-window limiter, not a token bucket — it resets `limitForPeriod` permissions at the start of each `limitRefreshPeriod` cycle via an atomic, lock-free `AtomicRateLimiter`, which means it allows bursts at window boundaries that a true token bucket or sliding-window-log implementation would smooth out. `Bulkhead` ships as two genuinely different implementations — `SemaphoreBulkhead` (a counting semaphore on the calling thread, cheap, can't interrupt a blocking call) and `ThreadPoolBulkhead` (a real dedicated `ThreadPoolExecutor` + bounded `ArrayBlockingQueue`, true isolation, the only one that can enforce a timeout on a blocking client you don't otherwise control) — and picking the wrong one for a blocking client is a common, checkable mistake.

## Why this gets asked

Because Resilience4j configuration is exactly the kind of thing that looks trivial in a tutorial and is subtly wrong in most real codebases — teams stack the four annotations in "logical" order (Retry first, then CircuitBreaker, then RateLimiter) assuming that's what executes, and it isn't; the library's hardcoded aspect order silently overrides intent. The interviewer has likely debugged a service where a `RateLimiterConfig` set for "2 requests per second, smooth" actually let through short bursts right at window boundaries because they assumed token-bucket behavior from a fixed-window implementation, or watched a `SemaphoreBulkhead` fail to protect a service from a genuinely stuck blocking call because semaphores can't interrupt the thread that's holding them. They want to see you reason from the library's actual mechanics, not from the pattern names — this module assumes you already know *why* the four patterns exist (`T21-resilience-catalogue`) and tests whether you know how *this specific library* implements them.

---

## Lineage: past → present → future

**What came before.** Netflix's Hystrix (2012) was the library that introduced circuit breakers to mainstream JVM engineering — a command-object model where every remote call was wrapped in a `HystrixCommand` with its own dedicated thread pool, giving bulkheading as a default rather than an opt-in. Hystrix went into maintenance mode in 2018 (Netflix itself moved internally toward adaptive concurrency limits rather than static per-dependency thread pools), and its architecture aged poorly for two concrete reasons: mandatory thread-pool-per-command was expensive at scale (hundreds of dependencies meant hundreds of pools, each with real memory and context-switch cost), and it had no first-class concept of "slow but successful" calls — a dependency returning 200s in 10 seconds never tripped a Hystrix breaker, which is a documented, real production killer.

**Where it stands now.** Resilience4j (first released 2016, matured through the Hystrix maintenance-mode period as its clear successor) is the current standard JVM in-process resilience library — genuinely production-standard, not a research alternative. Its design fixes both Hystrix gaps directly: modules are independently composable (you can use just `RateLimiter` without paying for the others), the default `SemaphoreBulkhead` avoids mandatory per-dependency thread pools, and `slowCallRateThreshold`/`slowCallDurationThreshold` on `CircuitBreaker` explicitly detect the slow-success case Hystrix missed. The Spring Boot starter (`resilience4j-spring-boot3`) auto-configures annotation-driven aspects (`@CircuitBreaker`, `@Retry`, `@RateLimiter`, `@Bulkhead`, `@TimeLimiter`) with Micrometer metrics wired in by default, and supports synchronous, `CompletableFuture`, and Reactor (`Mono`/`Flux`) return types. The live disagreement, as in the broader resilience catalogue, is in-process (Resilience4j) versus service-mesh-level (Envoy/Istio outlier detection, retry budgets) resilience — Resilience4j wins wherever the decision needs application semantics (is this specific call idempotent, what's a meaningful fallback) that a mesh cannot see, and loses ground for pure transport-level defaults a mesh applies uniformly with no redeploy.

**Where it's heading.** Resilience4j itself is stable and mature rather than rapidly evolving — most 2025-2026 activity is incremental (Spring Boot 3/4 compatibility work, reactive-type support refinement) rather than architectural change, which is itself a signal: the library has settled into "boring, reliable infrastructure" territory. The more active direction of travel sits one layer up, in adaptive/auto-tuned limits (Netflix's own `concurrency-limits`, Envoy's adaptive concurrency) that infer bulkhead/rate-limit sizing from observed latency rather than requiring a human to guess a static number — Resilience4j has no first-class adaptive-limit module as of 2026, so teams wanting that reach outside it. For LLM/agent-tool-calling resilience specifically — retrying a $0.02, 3-second tool call is a genuinely different cost/latency profile than retrying a cheap, fast HTTP call — Resilience4j's primitives apply mechanically but weren't designed with that cost model in mind; see `T21-resilience-catalogue` Q12 for the fuller treatment of resilience patterns adapted to agentic systems.

---

## Mental model

```
FIXED AOP DECORATOR ORDER (Spring annotations — NOT reorderable by annotation order):

  @Retry
    @CircuitBreaker
      @RateLimiter
        @TimeLimiter
          @Bulkhead
            public Mono<Result> callDownstream() { ... }

  Executes as:  Retry( CircuitBreaker( RateLimiter( TimeLimiter( Bulkhead( call ) ) ) ) )
                 ▲ outermost                                              ▲ innermost

  Retry sees the OUTCOME of the whole inner stack as one attempt — so one
  logical failure (which may have been bulkhead-rejected, rate-limited, or
  a genuine downstream error) counts as ONE retry-eligible failure, not
  several. Reorder the @annotations on the method: NOTHING CHANGES. Order
  is hardcoded; override only via resilience4j.<module>.<module>AspectOrder
  properties (higher number = higher priority = more outer).

BULKHEAD: TWO DIFFERENT IMPLEMENTATIONS, PICK DELIBERATELY

  SemaphoreBulkhead                    ThreadPoolBulkhead
  ┌─────────────────────┐              ┌─────────────────────┐
  │ counting semaphore   │              │ dedicated            │
  │ caller's OWN thread  │              │ ThreadPoolExecutor +  │
  │ does the work         │              │ bounded ArrayBlocking │
  │                       │              │ Queue                 │
  │ cheap, no context     │              │ true isolation, CAN   │
  │ switch                │              │ enforce a timeout on  │
  │ CANNOT interrupt a    │              │ a blocking client you │
  │ stuck blocking call   │              │ don't otherwise control│
  └─────────────────────┘              └─────────────────────┘
  async/reactive code, high volume       legacy blocking clients you
                                          cannot make cooperative

RATE LIMITER: FIXED WINDOW, NOT TOKEN BUCKET

  |--- cycle 1 (limitRefreshPeriod) ---|--- cycle 2 ---|
  permissions reset to limitForPeriod   reset again
  at the START of each cycle            at the START
  ^ calls can burst right at the boundary — 2 permits used at the very END
    of cycle 1, then 2 MORE immediately at the very START of cycle 2 = 4
    calls in a very short window, still "compliant" with a 2-per-cycle config
```

---

## How it actually works

### The fixed aspect order, and why it's fixed that way

The documented, hardcoded Spring AOP order is:

```
Retry ( CircuitBreaker ( RateLimiter ( TimeLimiter ( Bulkhead ( Method ) ) ) ) )
```

This matches the general catalogue's default ordering discussion (`T21-resilience-catalogue`) with Bulkhead innermost and Retry outermost — the rationale is the same: Bulkhead should reject *before* any thread/resource is spent on the rest of the chain, and Retry needs to see the combined outcome of everything inside it as a single attempt, so that one logical failure (which might have been a rate-limit rejection, a circuit-open fast-fail, or a genuine timeout) is retried as one unit rather than each inner layer separately amplifying it. If you write the annotations in a different order on the method, **nothing changes** — the order is applied by the library's AOP infrastructure regardless of declaration order, a specific and frequently-misunderstood detail. Overriding it requires explicit configuration:

```yaml
resilience4j.retry.retryAspectOrder: 1
resilience4j.circuitbreaker.circuitBreakerAspectOrder: 2
resilience4j.ratelimiter.rateLimiterAspectOrder: 3
resilience4j.bulkhead.bulkheadAspectOrder: 4
# higher number = evaluated later = more OUTER in the composed call
```

### Annotation-driven usage and fallbacks

```java
@Service
public class PricingClient {

    @CircuitBreaker(name = "pricingService", fallbackMethod = "fallbackPrice")
    @Retry(name = "pricingService")
    @Bulkhead(name = "pricingService")
    public Mono<Price> getPrice(String sku) {
        return webClient.get().uri("/price/{sku}", sku)
            .retrieve()
            .bodyToMono(Price.class);
    }

    // fallback signature must match the original + a Throwable parameter
    private Mono<Price> fallbackPrice(String sku, Throwable t) {
        return Mono.just(Price.stale(sku));   // serve cached/stale, per the fallback ladder in T21
    }
}
```

The `fallbackMethod` parameter is resolved by **reflection at startup** against the exact method signature (same parameters, plus a trailing `Throwable` or a specific exception subtype) — a common, silent failure is a fallback method whose signature doesn't match, which fails to register with no compile error and falls through to the original exception at runtime instead of the intended fallback. Configuration is centralized in `application.yml`:

```yaml
resilience4j.circuitbreaker:
  instances:
    pricingService:
      failureRateThreshold: 50
      slowCallRateThreshold: 50
      slowCallDurationThreshold: 2s
      slidingWindowType: TIME_BASED
      slidingWindowSize: 60
      minimumNumberOfCalls: 20
      waitDurationInOpenState: 30s
      permittedNumberOfCallsInHalfOpenState: 5
resilience4j.retry:
  instances:
    pricingService:
      maxAttempts: 3
      waitDuration: 500ms
      retryExceptions: [java.io.IOException, java.util.concurrent.TimeoutException]
      ignoreExceptions: [com.example.BusinessValidationException]
```

Every knob here maps directly to the concepts in `T21-resilience-catalogue` — this module's job is knowing where they live in Resilience4j specifically, not re-deriving why `minimumNumberOfCalls` matters.

### Bulkhead: choosing the right implementation

```java
// Semaphore bulkhead (default) — async/reactive code, no thread ownership transfer
@Bulkhead(name = "pricingService")   // type = SEMAPHORE is the default
public Mono<Price> getPrice(String sku) { ... }

// Thread-pool bulkhead — for a blocking legacy client you cannot make async
@Bulkhead(name = "legacySoapClient", type = Bulkhead.Type.THREADPOOL)
public CompletableFuture<Quote> getQuoteBlocking(String id) {
    return CompletableFuture.supplyAsync(() -> legacySoapSdk.fetchQuote(id));
}
```

```yaml
resilience4j.thread-pool-bulkhead:
  instances:
    legacySoapClient:
      maxThreadPoolSize: 10
      coreThreadPoolSize: 2
      queueCapacity: 20
```

`SemaphoreBulkhead` (`java.util.concurrent.Semaphore` under the hood) caps concurrent calls on the *caller's own thread* — cheap, no context-switch cost, but it fundamentally **cannot interrupt** a call already in flight; if the blocking SDK call hangs forever with no timeout of its own, the semaphore permit is held forever too, and the bulkhead only prevents *new* calls from starting, not the one already stuck. `ThreadPoolBulkhead` (a real `ThreadPoolExecutor` backed by a bounded `ArrayBlockingQueue`) hands the call off to a dedicated pool, which is the only variant that lets you enforce a hard timeout on a blocking client you don't otherwise control (interrupt the pool thread, abandon the call), at the cost of a genuine context switch and its own pool sizing (Little's Law, same as the general catalogue: `concurrency ≈ throughput × latency`, provisioned with headroom for burst).

### RateLimiter: fixed window via a lock-free atomic reference

Resilience4j's `RateLimiter` splits time into cycles of length `limitRefreshPeriod`; at the start of each cycle, available permissions reset to `limitForPeriod`. The default implementation, `AtomicRateLimiter`, tracks `(activeCycle, activePermissions)` as a single **immutable state object swapped via `AtomicReference`** — a lock-free compare-and-swap loop rather than a `synchronized` block, which matters directly for the virtual-thread pinning discussion in `T11-java-modern`: a lock-free limiter doesn't pin a virtual thread the way a `synchronized`-based one would on pre-JDK-24 runtimes.

```yaml
resilience4j.ratelimiter:
  instances:
    pricingService:
      limitForPeriod: 20        # permits per cycle
      limitRefreshPeriod: 1s    # cycle length
      timeoutDuration: 100ms    # how long a call waits for a permit before rejecting
```

**The fixed-window burst gap, concretely**: with `limitForPeriod: 20` and `limitRefreshPeriod: 1s`, nothing stops 20 calls landing in the last 10ms of cycle N and another 20 in the first 10ms of cycle N+1 — 40 calls in a 20ms window, still fully "compliant" with a nominal 20-per-second configuration. A true token bucket (permits accrue continuously rather than resetting in a step function) or a sliding-window-log approach smooths this; Resilience4j's `RateLimiter` does not, and that gap is worth naming explicitly if a design calls for smooth, burst-resistant limiting rather than a coarse per-second cap — in that case, layering a token-bucket-based gateway/mesh-level limiter in front, or choosing a different library, is the honest answer rather than assuming Resilience4j's `RateLimiter` already smooths it.

### TimeLimiter, and why it's usually paired with a thread-pool bulkhead

`TimeLimiter` wraps a `CompletableFuture`-returning (or reactive) call and cancels it if it exceeds `timeoutDuration` — but "cancels" for a `CompletableFuture` backed by a blocking call on a shared thread pool only interrupts the *Future*, not necessarily the underlying blocking I/O, unless the blocking client itself honors thread interruption. This is the same server-side-work-continues-after-client-gives-up gap covered generally in `T21-resilience-catalogue` Q13 — a `TimeLimiter` alone doesn't guarantee the downstream work actually stops, only that your code stops waiting for it.

---

## Build it from scratch

A minimal composed call showing the correct annotation stack and a fallback, runnable against a Spring Boot test slice:

```java
// untested sketch — Resilience4j-Spring Boot annotation stack
@RestController
public class InventoryController {

    private final InventoryClient client;
    public InventoryController(InventoryClient client) { this.client = client; }

    @GetMapping("/inventory/{sku}")
    public Mono<StockLevel> getStock(@PathVariable String sku) {
        return client.checkStock(sku);
    }
}

@Component
class InventoryClient {
    private final WebClient webClient;
    InventoryClient(WebClient.Builder builder) {
        this.webClient = builder.baseUrl("http://inventory-service").build();
    }

    // executes as: Retry(CircuitBreaker(RateLimiter(Bulkhead(call))))
    // regardless of the order the annotations are written below
    @Bulkhead(name = "inventory")
    @RateLimiter(name = "inventory")
    @CircuitBreaker(name = "inventory", fallbackMethod = "staleStock")
    @Retry(name = "inventory")
    public Mono<StockLevel> checkStock(String sku) {
        return webClient.get().uri("/stock/{sku}", sku).retrieve().bodyToMono(StockLevel.class);
    }

    private Mono<StockLevel> staleStock(String sku, Throwable t) {
        return Mono.just(StockLevel.unknown(sku));
    }
}
```

A fuller lab with a fake flaky downstream (WireMock, configurable failure/latency injection), assertions on breaker state transitions via `CircuitBreaker.EventPublisher`, and a load test proving the fixed-window `RateLimiter`'s boundary-burst behavior directly belongs in `labs/java/04-resilience4j/`.

---

## How it's done in production

| Symptom | Cause | Fix |
|---|---|---|
| Annotations reordered on a method expecting different behavior, nothing changes | Resilience4j's AOP aspect order is hardcoded, not derived from annotation declaration order | Use `resilience4j.<module>.<module>AspectOrder` properties to explicitly override, don't rely on annotation position |
| `fallbackMethod` silently never invoked, original exception propagates instead | Fallback method signature doesn't exactly match (parameters + trailing `Throwable`/exception type), fails reflection-based registration at startup with no compile error | Verify the fallback signature matches exactly; check startup logs for a registration warning, don't assume silence means success |
| A `SemaphoreBulkhead`-protected call hangs indefinitely under a stuck downstream, exhausting all permits | Semaphore can't interrupt an in-flight blocking call with no timeout of its own; the bulkhead only blocks *new* calls from starting | Pair with a `TimeLimiter`/explicit client timeout so the call itself is bounded, or switch to `ThreadPoolBulkhead` if the client is genuinely uninterruptible otherwise |
| Metrics show `RateLimiter` "compliant" at the configured rate, but downstream still sees short traffic spikes | Fixed-window algorithm allows a full `limitForPeriod` burst at the end of one cycle immediately followed by another full burst at the start of the next | Reduce `limitRefreshPeriod` granularity (smaller windows spread bursts thinner), or add a token-bucket-based limiter upstream (gateway/mesh) if smooth limiting is a hard requirement |
| Circuit breaker never trips despite a genuinely degraded, slow-but-200-returning downstream | Only `failureRateThreshold` configured; `slowCallRateThreshold`/`slowCallDurationThreshold` unset | Add slow-call detection — this is the exact Hystrix gap Resilience4j was built to close, and it's still commonly left unconfigured |
| `ThreadPoolBulkhead` queue fills and starts rejecting under a traffic spike that used to be fine | `queueCapacity`/`maxThreadPoolSize` sized by intuition, not by Little's Law against real observed throughput and latency | Resize using `concurrency ≈ throughput × latency` with burst headroom, verified under load, not guessed |

---

## Tradeoffs & when NOT to use it

- **Don't assume annotation order controls execution order.** This is the single most common Resilience4j misunderstanding — verify against the fixed `Retry→CircuitBreaker→RateLimiter→TimeLimiter→Bulkhead` order, and use the explicit `*AspectOrder` properties if you genuinely need a different sequence.
- **Don't use `SemaphoreBulkhead` for a blocking client with no timeout of its own.** It cannot interrupt a stuck call; you'll still exhaust the bulkhead's protection, just slower than with no bulkhead at all. Pair it with a timeout or use `ThreadPoolBulkhead` instead.
- **Don't rely on `RateLimiter` for smooth, burst-resistant limiting without checking whether the fixed-window boundary-burst behavior is acceptable for your case.** For anything protecting a fragile downstream from bursts specifically (not just an average rate), a token-bucket-based limiter at the gateway/mesh level is the more honest tool.
- **Don't skip `slowCallRateThreshold`.** Leaving it unconfigured reproduces the exact Hystrix-era gap (slow-success threads exhausting the pool undetected) that Resilience4j exists to fix — configuring only `failureRateThreshold` is an incomplete migration, not a complete one.
- **Don't reach for Resilience4j for cross-language or mesh-uniform transport defaults.** It's a JVM in-process library — for uniform behavior across a polyglot fleet with no redeploy, that's Envoy/Istio's job (see `T21-resilience-catalogue`), and Resilience4j is the layer above it for business-semantic decisions the mesh can't make.
- **Don't stack all five modules on every call reflexively.** Each one adds real overhead and cognitive load; a low-risk, fast, internal call between two trusted services in the same deployment often needs none of this, and applying the full stack everywhere is over-engineering that makes genuinely risky calls harder to spot in review.

---

## Interview questions

### Q1 — You stack `@Retry`, `@CircuitBreaker`, `@RateLimiter`, and `@Bulkhead` on one method. What order do they actually execute in, and does annotation order matter?
**Testing:** the single most-tested Resilience4j-specific fact.
**Answer:** Fixed by the library regardless of how the annotations are written: `Retry(CircuitBreaker(RateLimiter(TimeLimiter(Bulkhead(Method)))))` — Retry outermost, Bulkhead innermost. Annotation declaration order on the method has no effect on execution order; it's purely cosmetic.
**Follow-up trap:** *"How would you actually change the order if you needed to?"* — explicit `resilience4j.<module>.<module>AspectOrder` properties, where a higher number means the aspect is evaluated later (more outer in the composed call). Most teams never need this; the default order matches the general catalogue's recommended default for good reason.

### Q2 — Why does Retry sit outermost in the default order, and what would go wrong if it were innermost?
**Testing:** whether the *why*, not just the *what*, is understood — ties directly to `T21-resilience-catalogue`.
**Answer:** Retry needs to see the combined outcome of the entire inner stack (bulkhead rejection, rate-limit rejection, circuit-breaker fast-fail, or a genuine downstream failure) as one attempt, so one logical failure triggers one retry decision. If Retry were innermost, each retry attempt would separately trip the bulkhead/rate-limiter/breaker, meaning three retries could record three separate breaker failures for what's logically one failed operation — amplifying exactly the way unprotected retry amplifies in the general catalogue.
**Follow-up trap:** *"Is Retry-outermost the only defensible order?"* — no; the general catalogue notes Resilience4j's own documented alternative philosophy (some configurations reasonably put retry closer to the call so it can hit a different instance behind a load balancer with its own independent breaker state) — know that both exist and that the tradeoff is about whether a retry can plausibly route to a healthier target.

### Q3 — What's the difference between `SemaphoreBulkhead` and `ThreadPoolBulkhead`, and when would picking the wrong one hurt you?
**Testing:** knowing this is a real implementation choice, not a single "Bulkhead" concept.
**Answer:** `SemaphoreBulkhead` (the default) caps concurrent calls via a `java.util.concurrent.Semaphore` on the caller's own thread — cheap, no context switch, but structurally unable to interrupt a call already in progress. `ThreadPoolBulkhead` hands work to a dedicated `ThreadPoolExecutor` with a bounded queue — true isolation, and the only one that can enforce a hard timeout (interrupt the executing thread) on a blocking client that has no timeout of its own. Picking `SemaphoreBulkhead` for a legacy blocking SDK with no internal timeout means a single stuck call holds its permit forever; the bulkhead only stops *new* calls, not the stuck one, so you still degrade, just more slowly than with no bulkhead.
**Follow-up trap:** *"So should you always use ThreadPoolBulkhead to be safe?"* — no; for async/reactive, non-blocking code, `ThreadPoolBulkhead`'s context-switch and dedicated-pool memory cost is pure overhead with no isolation benefit the semaphore variant doesn't already provide, since there's no blocking thread to protect against in the first place.

### Q4 — Explain how Resilience4j's `RateLimiter` actually works internally, and name a scenario where its behavior surprises someone expecting a token bucket.
**Testing:** the specific algorithmic detail that separates library-level knowledge from pattern-name knowledge.
**Answer:** It's a fixed-window limiter: time splits into cycles of `limitRefreshPeriod`, and at the start of each cycle, permissions reset to `limitForPeriod`, tracked via a lock-free `AtomicReference`-swapped immutable state (`AtomicRateLimiter`). Unlike a token bucket, where permits accrue continuously and smoothly, a fixed window resets in a step function — so a full `limitForPeriod` burst at the very end of one cycle immediately followed by another full burst at the very start of the next cycle is fully "compliant," producing up to roughly double the nominal rate in a short window straddling the boundary.
**Follow-up trap:** *"How would you fix that if smooth limiting is a hard requirement?"* — shrink `limitRefreshPeriod` to reduce the size of the boundary-burst window, or layer a genuine token-bucket limiter (at a gateway or mesh layer, or a different library) in front — Resilience4j's `RateLimiter` doesn't natively smooth this, and pretending it does is the mistake to avoid.

### Q5 — A `fallbackMethod` is configured on `@CircuitBreaker` but never actually gets called when the breaker opens — the original exception propagates instead. Diagnose it.
**Testing:** a specific, real, silent-failure Resilience4j bug class.
**Answer:** The fallback method is resolved by reflection at startup against the original method's exact parameter list plus a trailing `Throwable` (or specific exception subtype) parameter; if the signature doesn't match precisely, registration fails, but there's no compile-time error — it's a runtime/startup-log issue only. Check the application startup logs for a fallback-registration warning, and verify the signature character-for-character.
**Follow-up trap:** *"What if the signature matches but the fallback still isn't invoked?"* — check whether the exception thrown is in the module's configured `ignoreExceptions` list, since `CircuitBreaker` deliberately does not record (and therefore does not trigger fallback logic through) exceptions explicitly marked as business/ignored errors — that's working as intended, not a bug, and it's a common source of "why didn't my fallback fire" confusion.

### Q6 — Your circuit breaker is configured with only `failureRateThreshold` and never trips despite a downstream that's clearly degraded. What's missing?
**Testing:** the specific historical Hystrix gap Resilience4j exists to close, and whether it's actually configured.
**Answer:** `slowCallRateThreshold` and `slowCallDurationThreshold` — without them, a downstream returning 200s but taking, say, 10 seconds per call never registers as a failure by rate alone, yet it exhausts threads/connections exactly like an outright failure would. This is the exact gap that made Hystrix miss "slow success" as a failure mode; leaving it unconfigured in Resilience4j reproduces the same blind spot the library was specifically built to fix.
**Follow-up trap:** *"What threshold would you pick for slowCallDurationThreshold?"* — derive it from your own SLO budget for that call, not the downstream's typical latency — if you owe the user 3 seconds total and this is one of several sequential calls, anything approaching a large fraction of that budget is already "too slow to be useful," which is usually a much tighter number than the downstream's own advertised p99.

### Q7 — How does Resilience4j's default lock-free `RateLimiter` implementation relate to the virtual-thread pinning problem covered in `T11-java-modern`?
**Testing:** cross-module synthesis — whether the candidate connects library internals to JVM concurrency mechanics rather than treating them as separate topics.
**Answer:** `AtomicRateLimiter` swaps an immutable state object via `AtomicReference` compare-and-swap rather than a `synchronized` block. On JDK versions before 24, a `synchronized`-based implementation used inside a hot virtual-thread path would risk pinning the virtual thread to its carrier for the block's duration; a lock-free CAS-based design has no such risk on any JDK version, since there's no monitor to pin on. This is a small but real, checkable design detail that matters more as virtual threads become the default concurrency model.
**Follow-up trap:** *"Does that mean Resilience4j is fully 'virtual-thread safe' everywhere?"* — no; that's specific to the `RateLimiter`'s internals. Other parts of the stack (a `ThreadPoolBulkhead`'s underlying `ThreadPoolExecutor`, or a downstream blocking client the bulkhead wraps) still have their own concurrency characteristics worth auditing independently — one component being lock-free doesn't make the whole call chain pinning-free.

### Q8 — When would you choose Resilience4j's in-process patterns over letting a service mesh (Envoy/Istio) handle resilience for the same call?
**Testing:** applying the general catalogue's mesh-vs-in-process framing specifically to Resilience4j.
**Answer:** Whenever the decision needs application semantics the mesh has no visibility into — whether this specific operation is idempotent (so retry is safe), what a meaningful fallback response actually is (stale cached price vs. a generic error), or per-tenant policy. A mesh gives uniform, redeploy-free transport-level defaults (connection-pool limits, outlier ejection, retry budgets) across every language in the fleet, but it cannot express "return the cached price" as a fallback — that's Resilience4j's (or equivalent in-process code's) job specifically.
**Follow-up trap:** *"Both are configured for the same call — mesh retries 3 times, Resilience4j's @Retry also retries 3 times. What happens?"* — they multiply: 3 mesh retries × 3 application retries = up to 9 attempts for one logical call, a real and common misconfiguration. Pick one layer to own retry for a given call and explicitly disable it at the other.

### Q9 — Design the resilience configuration for a call to a downstream pricing service that's occasionally slow (p99 spikes to 4s under load) but rarely outright fails.
**Testing:** synthesizing the modules into a coherent, workload-specific design rather than reciting each in isolation.
**Answer:** A `TimeLimiter` bounding each attempt below the caller's actual budget (not the downstream's raw p99 — if the caller owes a user 2 seconds total, the timeout might be 800ms, leaving room for one retry and a fallback within budget); `CircuitBreaker` with `slowCallRateThreshold`/`slowCallDurationThreshold` configured specifically because the described problem *is* the slow-success case, not outright failure; `Retry` with a small `maxAttempts` (2, not the default-adjacent 3+, since a slow downstream retried too aggressively just adds more load exactly when it's struggling) and full-jitter backoff; a `SemaphoreBulkhead` if the client is reactive/non-blocking, sized via Little's Law against real observed throughput; and a fallback returning the last-known-good cached price rather than a bare error, since price staleness is usually an acceptable degradation for a pricing display.
**Follow-up trap:** *"Why not just increase the timeout to accommodate the p99 spike instead of all this?"* — a timeout generous enough to accommodate the downstream's own p99 gives up almost the entire caller's latency budget to one call, defeating the purpose of having a budget at all, and doesn't address the actual problem (threads/connections held during those slow calls) — bounding the timeout below budget and handling the "too slow" case via breaker + fallback is the more resilient design even though it means occasionally serving stale data instead of waiting.

### Q10 — What's the actual, mechanical reason Hystrix fell out of favor, and how does Resilience4j's architecture address it directly?
**Testing:** lineage knowledge — not "Hystrix is old" but the specific design flaw.
**Answer:** Hystrix's command-object model mandated a dedicated thread pool per command/dependency by default, which meant real memory and context-switch cost multiplying with the number of dependencies a service called — expensive at scale, and not something you could opt out of without losing the isolation benefit entirely. Resilience4j decouples the modules: bulkheading defaults to the cheap `SemaphoreBulkhead` (no mandatory thread pool), and you opt into `ThreadPoolBulkhead` specifically where true thread isolation is needed, rather than paying for it universally.
**Follow-up trap:** *"Was thread-pool-per-dependency actually a bad idea, or just expensive?"* — it wasn't a bad idea in principle (true isolation is real and valuable), it was an inflexible default — Resilience4j's contribution isn't rejecting the idea, it's making it opt-in per dependency instead of mandatory for all of them, which is the more defensible framing if asked to defend Hystrix's original designers.

---

## Red flags that fail you

- Assuming the order annotations are written in a method determines execution order.
- Claiming Resilience4j's `RateLimiter` is a token bucket, or not knowing it's fixed-window with a boundary-burst gap.
- Using `SemaphoreBulkhead` for a blocking client with no timeout and no awareness that it can't interrupt a stuck call.
- Configuring `CircuitBreaker` with only `failureRateThreshold`, missing `slowCallRateThreshold` entirely.
- Not knowing why a `fallbackMethod` can silently fail to register (signature mismatch).
- Recommending Resilience4j as a replacement for mesh-level transport defaults across a polyglot fleet.
- Stacking all five modules on every call regardless of actual risk, with no cost-benefit reasoning.
- Confusing `TimeLimiter` cancellation with guaranteed downstream work cancellation.

---

## Cheat card

```
FIXED AOP ORDER (annotation position on the method does NOT matter):
  Retry( CircuitBreaker( RateLimiter( TimeLimiter( Bulkhead( Method ) ) ) ) )
  outermost ────────────────────────────────────────────▶ innermost
  Override via resilience4j.<module>.<module>AspectOrder (higher = more outer)

MODULES: CircuitBreaker, Retry, RateLimiter, Bulkhead (2 types), TimeLimiter.
  All independently composable — unlike Hystrix's monolithic command object.
  fallbackMethod resolved by REFLECTION at startup: signature must match
  exactly (+ trailing Throwable/exception param) or silently fails to register.

BULKHEAD:
  SemaphoreBulkhead (default): counting semaphore, caller's own thread, cheap,
    CANNOT interrupt an already-in-flight call. Use: async/reactive code.
  ThreadPoolBulkhead: real ThreadPoolExecutor + bounded ArrayBlockingQueue,
    true isolation, CAN enforce a timeout on a blocking client. Use: legacy
    blocking SDKs you don't control. Size via Little's Law + burst headroom.

RATE LIMITER: FIXED WINDOW, not token bucket. limitForPeriod permits reset
  at the START of each limitRefreshPeriod cycle, tracked via lock-free
  AtomicReference CAS (AtomicRateLimiter) — no synchronized block, so no
  virtual-thread pinning risk regardless of JDK version.
  BURST GAP: full limitForPeriod at end of cycle N + full limitForPeriod at
  start of cycle N+1 = up to ~2x nominal rate in a short boundary window.
  Fix for smooth limiting: shrink limitRefreshPeriod, or add a token-bucket
  limiter upstream (gateway/mesh) — Resilience4j doesn't smooth this natively.

CIRCUIT BREAKER: configure BOTH failureRateThreshold AND slowCallRateThreshold
  + slowCallDurationThreshold. Missing the slow-call config reproduces the
  exact Hystrix gap (slow-success exhausts threads, never trips a failure-
  rate-only breaker) Resilience4j was built to fix.

TIMELIMITER: cancels the Future/reactive chain on timeout — does NOT
  guarantee the underlying downstream work actually stops unless the client
  itself honors interruption. Same server-work-continues gap as T21 Q13.

LINEAGE: Hystrix (2012, maintenance since 2018) mandated a thread pool PER
  command — expensive at scale, no slow-call detection. Resilience4j:
  modules independently composable, semaphore bulkhead cheap by default,
  slowCallRateThreshold added explicitly to close the slow-success gap.

MESH vs IN-PROCESS: mesh (Envoy/Istio) = uniform transport defaults, no
  redeploy, no app-semantic awareness. Resilience4j = where idempotency,
  fallback content, per-tenant policy live. Both retrying the same call =
  multiplicative amplification — pick ONE layer per call.
```

## Sources

- [Getting Started — resilience4j](https://resilience4j.readme.io/docs/getting-started-3) — accessed 2026-08-03
- [Rate Limiter Internals in Resilience4j — DZone](https://dzone.com/articles/rate-limiter-internals-in-resilience4j) — accessed 2026-08-03
- [RateLimiter — resilience4j docs](https://resilience4j.readme.io/docs/ratelimiter) — accessed 2026-08-03
- [Bulkhead — resilience4j docs](https://resilience4j.readme.io/docs/bulkhead) — accessed 2026-08-03
- [Guide to Resilience4j With Spring Boot — Baeldung](https://www.baeldung.com/spring-boot-resilience4j) — accessed 2026-08-03
- [Resilience4j Bulkhead: Building Robust Services with Concurrency Limits — BootcampToProd](https://bootcamptoprod.com/spring-boot-resilience4j-bulkhead/) — accessed 2026-08-03
- [GitHub — resilience4j/resilience4j](https://github.com/resilience4j/resilience4j) — accessed 2026-08-03

## Changelog
- 2026-08-03 — created
