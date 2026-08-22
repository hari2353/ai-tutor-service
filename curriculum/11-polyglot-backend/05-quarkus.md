# Quarkus: Build-Time DI, GraalVM Native Images, Panache, Mutiny

> **Track:** T11 Polyglot Backend · **Time:** 2h · **Prereqs:** T11-spring-boot, T11-jvm-tuning · **Updated:** 2026-08-03
> **Module id:** `T11-quarkus` · **Tags:** java

## The 30-second version

Quarkus's entire design premise is doing at build time what Spring does at runtime: its DI container (**ArC**, a build-time implementation of Jakarta CDI Lite) resolves the dependency graph, processes annotations, and generates the wiring code during the Maven/Gradle build, so none of that reflection-heavy classpath scanning happens on JVM startup — the tradeoff is that anything genuinely dynamic (a bean chosen by a runtime condition unknown at compile time) needs an explicit escape hatch, because the container's shape is frozen before the app ever runs. Compiled to a native executable with GraalVM (ahead-of-time compilation, no JVM at runtime), a typical Quarkus service starts in tens of milliseconds instead of seconds and uses tens of megabytes of memory instead of hundreds — one commonly cited measurement puts it at roughly 29x faster startup (0.079s vs 2.292s) and 86% less memory at startup versus the same app on the JVM — which is the entire reason Quarkus exists: serverless/scale-to-zero and Kubernetes workloads where cold-start latency and per-pod memory cost are the metrics that matter, not peak sustained throughput. The real cost of that tradeoff is native image builds losing the JIT's adaptive, profile-guided runtime optimization entirely (AOT decisions are fixed at build time, no C2-style hot-path specialization from live traffic), longer and more resource-hungry build steps (minutes, not seconds, and real memory pressure during the native build itself), and a closed-world assumption that breaks naive reflection-heavy code (older ORMs, some serialization libraries) unless explicitly configured. Panache trims Hibernate ORM/Reactive boilerplate to near-nothing via an active-record or repository base class; Mutiny (`Uni<T>` for 0-or-1 result, `Multi<T>` for a reactive stream — Quarkus's answer to Reactor's `Mono`/`Flux`) is the reactive API threaded through the framework, with `@Blocking` as the explicit escape hatch for legacy blocking code running on a Vert.x event loop by default. The honest answer to "when do you reach for Quarkus over Spring Boot" is specifically: serverless functions, CLI tools shipped as native binaries, and high-pod-count Kubernetes services where startup time and memory footprint are the actual bottleneck — not as a default JVM framework choice for a long-running, steady-traffic monolith where Spring's deeper ecosystem usually wins.

## Why this gets asked

Because "cloud-native Java" is a real, current hiring signal — companies running Kubernetes at scale increasingly care about cold-start latency and per-pod memory cost in a way that didn't matter when everything ran on a handful of long-lived VMs, and Quarkus (alongside Micronaut) is the concrete technical answer to that shift. The interviewer has likely either sized a Kubernetes cluster around JVM services' actual memory footprint and watched it balloon, or debugged a Quarkus native-image build failure caused by an untested reflection path (a library doing runtime bytecode generation that works fine on the JVM and breaks silently, or loudly, under GraalVM's closed-world assumption). They want to know whether you understand *why* the startup/memory numbers are what they are — build-time wiring plus AOT compilation, not "Quarkus is just faster" — and whether you'd actually reach for it, versus reciting the benchmark numbers without being able to say when they don't matter.

---

## Lineage: past → present → future

**What came before.** Traditional JVM application servers and Spring's runtime DI container both do their heaviest lifting at startup: classpath scanning for annotated classes, reflection-based bean instantiation, proxy generation, auto-configuration condition evaluation — work that happens fresh every single time the JVM boots, which was an acceptable cost when "boot the process" meant once per deploy on a long-lived VM or a small number of long-lived containers. The pain that motivated a different approach arrived with two simultaneous shifts: serverless functions (AWS Lambda, Cloud Functions) where cold-start latency is directly billed and directly user-visible, and Kubernetes at high pod-count scale, where a JVM service's typical hundreds-of-MB resident memory footprint, multiplied across hundreds of pods, becomes a real infrastructure cost line item. Neither problem is solvable by tuning a runtime DI container faster — the fix requires moving work out of the runtime critical path entirely.

**Where it stands now.** Quarkus (Red Hat, first released 2019) answers this by inverting when the expensive work happens: **ArC**, its build-time CDI-Lite implementation, resolves the entire dependency graph and generates the wiring code during the build, so the runtime `main()` method starts a Vert.x kernel, boots an already-resolved DI container, fires startup events, and begins serving traffic — commonly cited at well under a second on the JVM and under 50ms compiled to a GraalVM native executable. This is genuinely production-deployed technology, not experimental — Quarkus 3.x (3.33 cited as the current LTS line in 2026, with full Java 25 compatibility) is a mature, actively maintained framework with real enterprise adoption, particularly in Red Hat's own OpenShift-adjacent customer base and serverless-first shops. The live disagreement is Quarkus/Micronaut (build-time DI, AOT-native-first design) versus Spring Boot (runtime DI, JIT-optimized-first design) as the default JVM backend choice: Spring's ecosystem depth (Spring Data, Spring Security, Spring Cloud, Spring AI, the sheer volume of "how do I do X in Spring" answers and hire-able experience) remains a real, non-trivial advantage for most teams, while Quarkus's cold-start/memory numbers are a decisive, specific win only for the workloads that actually have a cold-start or per-pod-memory constraint. Multiple 2026 comparisons frame this explicitly as "performance is solved, architecture isn't" — the native-image performance case is no longer contested, but whether a given team's actual workload benefits enough to justify the ecosystem tradeoff remains a genuine, workload-specific decision.

**Where it's heading.** GraalVM native image tooling keeps maturing — better reflection-configuration tooling, faster and less memory-hungry build pipelines, growing library-ecosystem support for the closed-world assumption (fewer libraries requiring manual `reflect-config.json` entries than a few years ago) — which is real, incremental, and reduces Quarkus's historical "great until you hit an unsupported library" friction over time. Quarkus's own reactive-first design (Mutiny woven through the framework, Vert.x as the runtime kernel) positions it well for the continued growth of streaming and event-driven architectures, though this is a design-philosophy alignment rather than a unique capability — Spring's virtual-thread maturation (`T11-spring-boot`) is separately narrowing the specific "handle high I/O concurrency" motivation that used to favor reactive frameworks generally. Expect continued incremental convergence on capability between the two ecosystems, with the real differentiator staying where it already is: deployment model (serverless/high-pod-count Kubernetes favors Quarkus's build-time/AOT bet; long-running, steady-traffic, ecosystem-hungry services favor Spring's runtime/JIT bet) rather than one framework becoming strictly better than the other.

---

## Mental model

```
SPRING BOOT: runtime-heavy startup                QUARKUS: build-time-heavy, thin runtime

  BUILD                                              BUILD
  compile classes                                    compile classes
                                                       + ArC resolves ENTIRE DI graph
                                                       + extensions run "deployment" logic
                                                       + bytecode for wiring GENERATED here
  RUNTIME (every process start, every time)          RUNTIME (every process start)
  scan classpath for annotations   ◀── slow          start Vert.x kernel
  reflect to instantiate beans     ◀── slow           boot ALREADY-RESOLVED DI container
  evaluate auto-config conditions  ◀── slow           fire StartupEvent
  generate AOP proxies             ◀── slow           begin serving traffic
  → serving traffic (seconds)                        → serving traffic (<1s JVM, <50ms native)

NATIVE IMAGE (GraalVM AOT) vs JVM (JIT):

  JVM:    interpreter → C1 → C2, PROFILE-GUIDED, adapts to actual live traffic
          patterns over time — can out-optimize AOT for long-running steady load
  NATIVE: every optimization decision FIXED at build time (closed-world
          assumption: the AOT compiler must know every reachable class/method
          UP FRONT — reflection, dynamic proxies, unregistered classes break
          unless explicitly configured) — no runtime adaptation, but starts
          in milliseconds because there's no JIT warm-up path to run at all

MUTINY: Uni<T> = 0-or-1 result-or-error (like CompletableFuture, richer ops)
         Multi<T> = a reactive stream of 0..N items (like Reactor's Flux)
         @Blocking = explicit escape hatch: this method needs a worker thread,
         not the Vert.x event loop — same blocking-call-on-event-loop hazard
         as WebFlux, covered in T11-spring-boot and T16-io-models
```

---

## How it actually works

### ArC: build-time CDI, and what breaks when the graph isn't knowable at build time

```java
@ApplicationScoped
public class PricingService {
    @Inject
    ExchangeRateClient exchangeRateClient;   // resolved and wired at BUILD time
}
```

Quarkus's extension model means every extension (RESTEasy, Hibernate, a messaging connector) contributes a **build step** that runs during compilation — augmenting the bytecode, generating reflection metadata, and resolving the CDI graph — before the application ever runs. `ArC` (Quarkus's own implementation of Jakarta CDI Lite, a deliberately reduced subset of full CDI) supports the standard scopes (`@ApplicationScoped`, `@RequestScoped`, `@Dependent`, `@Singleton`) but is explicitly *not* full CDI — some dynamic, runtime-resolved CDI features (certain forms of programmatic lookup, dynamic interceptor binding decided at runtime rather than compile time) either aren't supported or need Quarkus-specific alternatives, because the whole point is that the graph must be knowable and fixable at build time. This is the direct mechanical tradeoff behind the startup-time win: Spring's `ApplicationContext.refresh()` doing classpath scanning and reflection-based instantiation at every JVM boot is precisely the cost ArC eliminates by doing that resolution once, at build time, and generating direct, reflection-free wiring code instead.

### Native image: what AOT actually costs you, mechanically

```bash
# untested sketch — building and measuring a native executable
./mvnw package -Dnative                    # AOT compile via GraalVM — minutes, memory-hungry
./target/pricing-service-1.0-runner        # the resulting native binary, no JVM needed
```

GraalVM's native-image compiler performs **static reachability analysis** at build time: starting from the application's entry points, it determines every class, method, and field that could possibly be reached, and compiles *only* that closed set ahead-of-time into a single native binary — this "closed-world assumption" is what makes the aggressive dead-code elimination and startup-time win possible, and it's also exactly what breaks reflection-heavy code that the analysis can't statically prove reachable (a library calling `Class.forName()` with a computed string, a serialization framework generating proxies at runtime, dynamic classloading). The fix is explicit configuration (`reflect-config.json`, or Quarkus extensions that already ship the necessary metadata for common libraries) telling the AOT compiler "this class/method is reachable even though static analysis can't see it" — Quarkus's own extensions handle this automatically for supported libraries, which is why sticking to extensions with native-image support is the practical path, and reaching for an arbitrary unsupported library is where native-image builds most commonly break, sometimes with a build-time failure (better) and sometimes with a runtime `ClassNotFoundException` on a path that was never exercised until production traffic hit it (worse).

The other real cost, less discussed than the reflection issue: **native image builds are expensive** — commonly minutes rather than seconds, with real peak memory pressure during the build itself (large services can need several GB of RAM just to build), which changes CI pipeline design (a native-image build step needs a bigger, slower CI runner and can't be treated as a cheap, incremental step the way a JVM compile is) and is a real, concrete operational cost to weigh against the runtime win.

### JIT-vs-AOT: the throughput tradeoff nobody puts on the marketing slide

```
JVM startup:  slow to start, FAST to reach peak steady-state throughput
              (C2 profile-guided optimization adapts to actual production
              traffic patterns over the service's lifetime — see T11-jvm-tuning)

Native image: FAST to start, throughput is whatever AOT compiled it to be —
              no further adaptation from live traffic, ever, because there's
              no JIT running at all in a native executable
```

For a long-running service handling steady, predictable, high-volume traffic for hours or days at a time, the JVM's ability to progressively specialize hot paths based on *actual observed* production traffic (inlining the branches that are actually hot, not the ones that were guessed hot at build time) can out-perform a native image's fixed, build-time-only optimization decisions at true steady state — this is a real, cited tradeoff, not FUD against native images. The decisive factor is whether your workload's bottleneck is *startup latency and idle-memory footprint* (native wins decisively — Lambda cold starts, scale-to-zero Knative services, CLI tools) or *sustained peak throughput on a long-lived process* (JVM with a mature JIT has room to out-optimize an AOT-fixed decision set, though the gap has narrowed as GraalVM's AOT compiler has matured and Quarkus increasingly supports profile-guided-optimization-assisted native builds that feed it representative traffic samples at build time to narrow this gap further).

### Panache: minimal-boilerplate persistence

```java
// Active-record style
@Entity
public class Order extends PanacheEntity {
    public String customerId;
    public BigDecimal total;

    public static List<Order> findByCustomer(String customerId) {
        return list("customerId", customerId);
    }
}

// usage — no repository interface needed at all for the active-record style
Order order = Order.findById(id);
Order.findByCustomer("cust-123").forEach(o -> ...);

// Repository style — for teams preferring separation from the entity itself
@ApplicationScoped
public class OrderRepository implements PanacheRepository<Order> {
    public List<Order> findByCustomer(String customerId) {
        return list("customerId", customerId);
    }
}
```

Panache generates the boilerplate (`id`, basic CRUD, query helpers built on a simplified JPQL-like syntax) that Spring Data's repository interfaces provide via a different mechanism (proxy-generated implementations of derived method names). Panache's active-record style (extending `PanacheEntity` directly) is a genuinely different design choice from Spring Data's always-separate-repository convention — it puts persistence methods directly on the domain object, which is more concise but couples the entity class to persistence concerns more tightly, a real design tradeoff worth naming rather than treating Panache's brevity as strictly better. **The N+1 query trap from `T11-spring-boot` applies identically here** — Panache doesn't change the underlying Hibernate lazy-loading mechanics, only the syntax for declaring queries.

### Mutiny: Uni, Multi, and the @Blocking escape hatch

```java
@GET
@Path("/price/{sku}")
public Uni<Price> getPrice(String sku) {
    return pricingClient.fetchPrice(sku)          // returns Uni<Price>
        .onFailure().retry().atMost(2)
        .onItem().ifNull().continueWith(Price::unknown);
}

@GET
@Path("/legacy-report")
@Blocking                                          // explicit: run on a WORKER thread,
public Report getLegacyReport() {                  // not the Vert.x event loop —
    return legacyBlockingReportGenerator.build();   // same hazard as WebFlux's blocking-
}                                                    // call-on-event-loop trap otherwise
```

`Uni<T>` models "eventually zero-or-one result or a failure" — Quarkus's analog to `CompletableFuture`/Reactor's `Mono`, with a richer composable operator set (`onFailure().retry()`, `onItem().transform()`). `Multi<T>` models a reactive stream of zero-to-many items — the analog of Reactor's `Flux`. Quarkus's HTTP layer runs on Vert.x's event loop by default, exactly like WebFlux's Netty event loop — a method that does blocking work (a legacy JDBC call, a synchronous SDK) without `@Blocking` stalls an event-loop thread precisely the way an unmarked blocking call inside a WebFlux `Mono` chain or a FastAPI `async def` handler does, covered mechanically in `T11-spring-boot` and `T11-fastapi-deep`. `@Blocking` is the explicit, checkable signal that a method needs to run on Quarkus's separate worker thread pool instead.

---

## Build it from scratch

A minimal REST endpoint showing the build-time-DI-plus-reactive combination, and the specific commands that expose the startup/memory difference concretely:

```java
// untested sketch — minimal Quarkus reactive endpoint
@Path("/inventory")
public class InventoryResource {

    @Inject
    InventoryService service;   // resolved at BUILD time by ArC, not runtime reflection

    @GET
    @Path("/{sku}")
    public Uni<StockLevel> getStock(@PathParam("sku") String sku) {
        return service.checkStock(sku)
            .onFailure().recoverWithItem(StockLevel::unknown);
    }
}

@ApplicationScoped
class InventoryService {
    Uni<StockLevel> checkStock(String sku) {
        return Uni.createFrom().item(() -> lookupInCache(sku))
            .runSubscriptionOn(Infrastructure.getDefaultWorkerPool());
    }
}
```

```bash
# JVM mode: fast dev loop, live reload
./mvnw quarkus:dev

# Measure JVM startup and RSS memory
java -jar target/quarkus-app/quarkus-run.jar &
time curl localhost:8080/inventory/sku-1
ps -o rss= -p $!

# Native build and the same measurement, to see the actual delta firsthand
./mvnw package -Dnative
./target/*-runner &
time curl localhost:8080/inventory/sku-1
ps -o rss= -p $!
```

A fuller lab comparing JVM-mode and native-mode startup time, RSS memory, and steady-state throughput under sustained load (to observe the JIT-vs-AOT tradeoff directly rather than just the startup numbers) belongs in `(lab pending)`.

---

## How it's done in production

| Symptom | Cause | Fix |
|---|---|---|
| Native image build fails with a `ClassNotFoundException`/reflection error at build time | GraalVM's closed-world static reachability analysis couldn't prove a dynamically-loaded class/method reachable | Add explicit `reflect-config.json` entries, or prefer a Quarkus extension that already ships native-image metadata for that library over an unsupported raw dependency |
| Native image runs fine in testing, then throws a reflection error on a rarely-hit production code path | The untested path wasn't exercised during the build's reachability analysis or integration tests, so its reflection need was never surfaced until real traffic hit it | Exercise all realistic code paths in CI against the native binary specifically, not just the JVM-mode build, before shipping |
| CI pipeline for native builds is slow and occasionally OOMs the build agent | Native-image compilation is memory- and CPU-intensive, minutes not seconds, a genuinely different cost profile than a JVM compile | Provision a dedicated, larger CI runner/build resource pool for native builds; don't treat it as a drop-in replacement step in an existing lightweight pipeline |
| A Quarkus REST endpoint's throughput collapses under load despite the reactive rewrite | A blocking call left in a method not marked `@Blocking`, stalling a Vert.x event-loop thread — the exact WebFlux/async-Python hazard, different framework | Add `@Blocking` to route the method to Quarkus's worker thread pool, or replace the blocking call with a genuinely non-blocking client |
| Long-running, high-steady-throughput service migrated to native shows worse peak throughput than the JVM version did | AOT-fixed optimization decisions can't adapt to actual live traffic the way JIT's profile-guided C2 compilation does over a long-lived process's lifetime | For workloads where sustained peak throughput matters more than startup/memory, JVM mode (or Quarkus's PGO-assisted native builds feeding representative traffic samples at build time) may be the better fit than plain native |
| A CDI injection that worked in a quick prototype fails at build time with "no bean found" | ArC's build-time resolution needs the bean's shape knowable at compile time; some dynamic/programmatic-lookup CDI patterns from full Jakarta CDI aren't supported by CDI Lite | Restructure to a build-time-resolvable injection pattern, or check whether the specific dynamic pattern needed has a Quarkus-specific alternative |

---

## Tradeoffs & when NOT to use it

- **Don't choose Quarkus by default for a long-running, steady-traffic monolith with no cold-start or per-pod-memory constraint.** That's exactly the workload where Spring's deeper ecosystem (Spring Data, Spring Security, Spring Cloud, Spring AI, sheer volume of prior art) usually outweighs Quarkus's startup/memory advantage, which doesn't matter if the process runs for days between restarts anyway.
- **Don't assume every library "just works" under native image.** The closed-world assumption breaks naive reflection; verify a dependency has Quarkus native-image support (an extension, or documented `reflect-config` metadata) before committing to it in a native-image-targeted service, and test the actual native binary in CI, not just JVM mode.
- **Don't treat native-image build time as free or fast.** It's a genuinely different, more expensive CI cost (minutes, real memory pressure) than a JVM build — budget for it explicitly rather than discovering it when a build agent starts OOMing.
- **Don't expect native image to out-throughput a warmed-up JVM on long-running, high-steady-state workloads.** AOT's fixed, build-time optimization decisions can't adapt to live traffic the way the JIT's profile-guided C2 compilation does over a process's lifetime — native's win is startup time and idle memory, not necessarily peak sustained throughput.
- **Don't leave a blocking call unmarked in a Quarkus reactive route.** It stalls a Vert.x event-loop thread exactly like the equivalent WebFlux/async mistake — `@Blocking` is the required, explicit signal, not optional documentation.
- **Don't pick Panache's active-record style reflexively "because it's less code."** Coupling persistence methods directly onto the domain entity is a real design tradeoff (harder to test the entity in isolation from persistence, less separation of concerns) versus the repository style — know both exist and pick deliberately.

---

## Interview questions

### Q1 — What does Quarkus actually do at build time that Spring Boot does at runtime, and why does that produce the startup-time difference?
**Testing:** whether the mechanism, not just the benchmark number, is understood.
**Answer:** ArC (Quarkus's build-time CDI-Lite implementation) resolves the entire dependency injection graph, and Quarkus's extension "deployment" build steps process annotations and generate the wiring bytecode, all during compilation. Spring's `ApplicationContext` does the equivalent work — classpath scanning, reflection-based bean instantiation, auto-configuration condition evaluation, proxy generation — fresh at every JVM boot. Quarkus's runtime `main()` starts with an already-resolved graph, so it just boots a Vert.x kernel, instantiates the pre-wired container, and starts serving — which is why startup drops from seconds to well under a second on the JVM, and under 50ms on a native executable.
**Follow-up trap:** *"Does that mean ArC is strictly better than Spring's container?"* — no; it's a tradeoff. Because the graph must be knowable at build time, genuinely dynamic DI patterns (some programmatic/runtime CDI lookup patterns from full Jakarta CDI) either aren't supported by CDI Lite or need Quarkus-specific alternatives — Spring's runtime resolution is more flexible precisely because it pays the cost ArC avoids.

### Q2 — Explain GraalVM's "closed-world assumption" and why it breaks some libraries under native image.
**Testing:** the actual mechanism behind the most common native-image production failure.
**Answer:** Native-image compilation performs static reachability analysis from the application's entry points, determining every class/method/field that could possibly be reached, and compiles only that closed set ahead-of-time. Anything the static analysis can't prove reachable — `Class.forName()` with a computed string, runtime bytecode/proxy generation, dynamic classloading — isn't included by default, so calling it at runtime throws a `ClassNotFoundException` or similar, sometimes at build time (if exercised during the build) and sometimes only in production on a code path the build never touched.
**Follow-up trap:** *"How do you fix a library that needs reflection the analysis can't see?"* — explicit `reflect-config.json` metadata telling the AOT compiler that class/method is reachable regardless of what static analysis found, or, preferably, use a Quarkus extension that already ships this metadata for the library rather than hand-maintaining it for an arbitrary unsupported dependency.

### Q3 — A team reports their native-image service starts in 40ms but their long-running JVM-mode version has higher sustained throughput under steady load. Is that a bug?
**Testing:** whether the JIT-vs-AOT tradeoff is understood as real, not marketing spin.
**Answer:** Not a bug — a real, cited tradeoff. Native image is AOT-compiled: every optimization decision is fixed at build time with no further adaptation. The JVM's JIT (see `T11-jvm-tuning`) profiles actual live traffic and progressively specializes hot paths (C2's inlining, escape analysis) based on what's *actually* hot in production, which can out-perform AOT's fixed, build-time-guessed decisions at true long-running steady state. Native's decisive win is startup latency and idle memory footprint, not necessarily peak sustained throughput.
**Follow-up trap:** *"So when would you deliberately choose the JVM mode over native for a production Quarkus service?"* — a long-running, high-steady-throughput service with no cold-start or per-pod-memory constraint (not serverless, not scale-to-zero, not extremely high pod-count) — exactly the workload where the JIT's adaptive advantage matters more than a startup-time win nobody's actually waiting on.

### Q4 — What's `Uni<T>` versus `Multi<T>` in Mutiny, and how do they map to Reactor's types for someone coming from Spring WebFlux?
**Testing:** cross-framework fluency, since candidates often know one reactive library and not the other.
**Answer:** `Uni<T>` models zero-or-one eventual result or a failure — the Mutiny analog of `Mono<T>` (or `CompletableFuture`, with richer composable operators). `Multi<T>` models a reactive stream of zero-to-many items — the analog of `Flux<T>`. Both frameworks solve the same underlying reactive-streams problem with different but conceptually parallel APIs.
**Follow-up trap:** *"Does a blocking call inside a Uni chain cause the same problem as an unmarked blocking call in WebFlux?"* — yes, identically: Quarkus's HTTP layer runs on Vert.x's event loop by default, so a blocking call inside a reactive chain stalls an event-loop thread the same way it would in WebFlux/Netty. The fix is Quarkus-specific syntax (`@Blocking` annotation, or `.runSubscriptionOn(Infrastructure.getDefaultWorkerPool())`), but the underlying hazard is the same mechanism covered generally in `T16-io-models`.

### Q5 — When would you choose Panache's active-record style over a repository-style class, and what's the real cost of that choice?
**Testing:** whether Panache's convenience is understood as a design tradeoff, not a free win.
**Answer:** Active-record style (persistence methods directly on the `@Entity` class extending `PanacheEntity`) is more concise and reads naturally for simple CRUD-heavy domains. The real cost is coupling: the domain entity now directly depends on persistence concerns, making it harder to test the entity's business logic in true isolation from Hibernate, and it blurs the separation-of-concerns boundary that a dedicated repository class (Panache's alternative `PanacheRepository<T>` style, closer to Spring Data's convention) maintains.
**Follow-up trap:** *"Does Panache change the N+1 query risk from lazy JPA associations?"* — no; Panache is a syntax layer over the same Hibernate lazy-loading mechanics covered in `T11-spring-boot`. A lazy `@OneToMany` accessed in a loop is exactly as N+1-prone under Panache as under a Spring Data repository — the fix (`JOIN FETCH`, projections) is identical.

### Q6 — Design the deployment decision: your team is choosing between Spring Boot and Quarkus for a new AWS Lambda-based service versus a new long-running Kubernetes Deployment with steady, predictable traffic. Walk through both.
**Testing:** staff-level judgment applying the tradeoff to two concretely different deployment shapes.
**Answer:** For the Lambda service: Quarkus, compiled to a native image, is close to the correct default — cold-start latency is directly billed and directly user-visible, and native's tens-of-milliseconds startup is the specific, decisive advantage over a JVM cold start that can run into the low seconds. For the steady-traffic Kubernetes Deployment with predictable, sustained load and no aggressive scale-to-zero requirement: Spring Boot on the JVM is the more defensible default, since the process runs for hours/days between restarts (startup time amortizes to irrelevance), the JIT's adaptive optimization has time to pay off at steady state, and Spring's ecosystem depth reduces integration risk for whatever the service actually needs to talk to.
**Follow-up trap:** *"What if the Kubernetes cluster runs at very high pod count and per-pod memory cost is the actual budget constraint, not startup time?"* — that shifts the calculus toward Quarkus even without a cold-start concern, since native's idle-memory footprint (tens of MB vs hundreds) multiplied across hundreds of pods is a real infrastructure cost — the decision criterion is "which specific resource is actually the constraint," not a blanket rule tied to deployment platform alone.

### Q7 — Why does a native-image build sometimes fail in CI when the exact same code runs fine in `quarkus:dev` (JVM mode)?
**Testing:** understanding that dev-mode and native-mode are genuinely different execution models, not just a compile-target switch.
**Answer:** `quarkus:dev` runs on the JVM with the full reflection capability of a normal JVM process — any reflective call, dynamic proxy, or runtime classloading works exactly as it would on any JVM. Native-image compilation applies the closed-world static reachability analysis, which can fail to prove a reflective call site reachable even though it's perfectly valid Java that runs fine on any JVM, including Quarkus's own dev mode. The two modes are not the same execution semantics with a different startup time — one has GraalVM's AOT constraints and one doesn't.
**Follow-up trap:** *"So should teams always test against a native build before merging?"* — for anything targeting production native-image deployment, yes — testing only in JVM/dev mode gives false confidence, since the reflection-reachability failures are specifically invisible there. This is a real, recurring "works in dev, fails in CI/production" bug class specific to native-image projects.

### Q8 — What's the actual argument for choosing build-time DI (ArC) over runtime DI (Spring's container) beyond "it's faster to start"?
**Testing:** whether the deeper design rationale, not just the headline metric, is understood.
**Answer:** Beyond startup time, build-time resolution catches wiring errors (a missing bean, an ambiguous injection point) at build time rather than at application startup or, worse, only when a specific code path is first exercised at runtime — shifting a class of bugs left, from "discovered in a deployed environment" to "discovered in CI." It also means the shape of the dependency graph is fully static and inspectable from the build artifact itself, which is a genuine, if secondary, benefit for tooling and auditability.
**Follow-up trap:** *"Doesn't Spring also fail fast on a missing bean at ApplicationContext startup?"* — yes, Spring's `ApplicationContext.refresh()` does fail fast too, at runtime startup rather than build time — the distinction is *when* in the pipeline the failure surfaces (build vs. the first runtime boot of that specific deployment), which matters for how early in CI/CD the error is caught, not whether it's caught at all.

### Q9 — A library your team depends on has no documented GraalVM native-image support. What are your options, in order of preference?
**Testing:** practical judgment for a real, common blocker.
**Answer:** First, check whether a Quarkus extension already wraps that library with native-image metadata included — many common libraries have community or Red Hat-maintained Quarkus extensions specifically to solve this. Second, if no extension exists, check whether the library's own GraalVM reachability metadata repository (the shared community `graalvm-reachability-metadata` project) has an entry. Third, hand-write the `reflect-config.json`/resource-config entries yourself by testing the native build and iteratively adding metadata for each failure — the most labor-intensive and fragile option, worth avoiding if either prior option exists. Fourth, and legitimately: run that specific service in JVM mode instead of native, if the library is critical and none of the above pans out — native image isn't mandatory just because you're using Quarkus.
**Follow-up trap:** *"Isn't 'just run it on the JVM' giving up on Quarkus's whole value proposition?"* — no; Quarkus's build-time DI and lighter runtime overhead still provide real value on the JVM alone (faster than Spring's runtime-scanned startup, though not as fast as native) — native image is one feature of the framework, not the entire reason to choose it, and a service that can't go native for a dependency reason can still benefit from the rest of the framework.

### Q9 — Compare Quarkus's ArC and Spring's `ApplicationContext` on how each handles a bean whose configuration depends on a runtime environment variable only known at deploy time.
**Testing:** whether the build-time/runtime split's practical boundary is understood precisely, not just at a slogan level.
**Answer:** Spring resolves this naturally at runtime — `@Value("${some.property}")` or a `@ConfigurationProperties` class reads the actual deployed environment's values when `ApplicationContext.refresh()` runs, no build-time knowledge required. Quarkus's ArC still resolves the *shape* of the dependency graph (which beans exist, how they're wired together) at build time, but individual configuration *values* are deliberately kept resolvable at runtime via Quarkus's own config system (`@ConfigProperty`, MicroProfile Config) — the bean graph structure is fixed at build time, but the values flowing into that fixed structure can still come from runtime environment variables, config maps, or secrets.
**Follow-up trap:** *"So is anything actually different between the two if config values still resolve at runtime either way?"* — yes: what's fixed at build time in Quarkus is the *existence and wiring* of beans (which implementation gets injected where, whether an extension's beans are even included in the final artifact), not just configuration values — a Spring `@ConditionalOnProperty`-driven bean that only exists if a runtime environment variable is set a certain way has no clean ArC equivalent, since ArC needs to know the graph shape before the runtime environment is known; Quarkus handles genuinely conditional bean *existence* via build-time profiles/conditions instead, which is a real, different mechanism from Spring's runtime-conditional beans.

---

## Red flags that fail you

- Claiming native image is unconditionally faster or better than JVM mode with no mention of the JIT-vs-AOT throughput tradeoff at steady state.
- Not knowing what the closed-world assumption is or why it breaks reflection-heavy libraries.
- Treating native-image build time/resource cost as negligible or ignorable in CI planning.
- Recommending Quarkus by default for a long-running, steady-traffic service with no cold-start or memory-footprint constraint, without weighing Spring's ecosystem tradeoff.
- Leaving a blocking call unmarked (`@Blocking` missing) in a Quarkus reactive route and not recognizing the event-loop-stall hazard.
- Confusing `Uni`/`Multi` with Reactor's `Mono`/`Flux` incorrectly, or not knowing they're conceptually parallel.
- Assuming Panache eliminates the N+1 query risk that applies to any lazy JPA association.
- Assuming full Jakarta CDI dynamic-lookup patterns all work identically under ArC/CDI Lite.

---

## Cheat card

```
ARC: Quarkus's build-time CDI-Lite DI container. Resolves the ENTIRE bean
  graph + generates wiring bytecode at BUILD time, not runtime. Scopes:
  @ApplicationScoped, @RequestScoped, @Dependent, @Singleton. NOT full CDI —
  some dynamic/programmatic runtime lookup patterns unsupported by design.

STARTUP/MEMORY (cited): native ~29x faster startup (0.079s vs 2.292s JVM),
  ~86% less memory at startup (16.27 MiB vs 113.5 MiB). Quarkus 3.33 = 2026
  current LTS, full Java 25 support.

NATIVE IMAGE (GraalVM AOT): closed-world assumption — static reachability
  analysis from entry points determines EVERY reachable class/method at
  build time; compiles ONLY that set. Breaks: Class.forName() w/ computed
  string, runtime proxy/bytecode gen, dynamic classloading — unless
  reflect-config.json entries or a Quarkus extension supplies the metadata.
  Fails sometimes at BUILD (better) sometimes at RUNTIME on an untested
  path (worse — test the actual native binary in CI, not just dev mode).
  Build cost: MINUTES + real memory pressure, not a cheap incremental step.

JIT vs AOT TRADEOFF: JVM = slow start, JIT adapts to LIVE traffic over time,
  can out-throughput AOT at true steady state (see T11-jvm-tuning C2 tiers).
  Native = fast start, low idle memory, optimization FIXED at build time,
  no runtime adaptation ever. Native wins: serverless/Lambda, scale-to-zero,
  high-pod-count K8s. JVM wins: long-running steady-traffic, ecosystem-heavy.

PANACHE: active-record (PanacheEntity, methods ON the entity, concise but
  couples entity to persistence) OR repository (PanacheRepository<T>,
  Spring-Data-like separation). Same Hibernate lazy-loading underneath —
  N+1 risk from T11-spring-boot applies identically, unchanged by Panache.

MUTINY: Uni<T> = 0-or-1 result-or-error (~ Mono/CompletableFuture, richer
  ops). Multi<T> = 0..N stream (~ Flux). Vert.x event loop by default —
  blocking call w/o @Blocking = stalls event-loop thread, SAME hazard as
  unmarked blocking call in WebFlux (T11-spring-boot) or async def (fastapi-deep).

WHEN: Quarkus for serverless/Lambda, CLI-as-native-binary, high-pod-count
  K8s where startup/memory is the actual constraint. Spring Boot default
  for long-running steady-traffic services where ecosystem depth (Data,
  Security, Cloud, AI) outweighs a startup-time win nobody's waiting on.
```

## Sources

- [How to build lightning-fast Quarkus native executables — TechTarget](https://www.techtarget.com/searchapparchitecture/tip/How-to-build-lightning-fast-Quarkus-native-executables) — accessed 2026-08-03
- [Native Image Build Pipeline — DeepWiki (quarkusio/quarkus)](https://deepwiki.com/quarkusio/quarkus/4.1-native-image-build-pipeline) — accessed 2026-08-03
- [Mutiny - Async for mere mortals — Quarkus guides](https://quarkus.io/guides/mutiny-primer) — accessed 2026-08-03
- [Spring Boot vs Quarkus vs Micronaut: The Ultimate 2026 Showdown — Java Code Geeks](https://www.javacodegeeks.com/2025/12/spring-boot-vs-quarkus-vs-micronaut-the-ultimate-2026-showdown.html) — accessed 2026-08-03
- [Quarkus vs. Spring Boot: The 2026 Application Lifecycle Deep Dive — Medium](https://medium.com/@erbharatp/quarkus-vs-spring-boot-the-2026-application-lifecycle-deep-dive-9e6f871ebe66) — accessed 2026-08-03
- [Quarkus Native vs JVM: Real-World Performance Comparison — Medium](https://medium.com/@issam1991/quarkus-native-vs-jvm-real-world-performance-comparison-e766f59706f6) — accessed 2026-08-03
- [Quarkus Performance — quarkus.io](https://quarkus.io/performance/) — accessed 2026-08-03
- [Hibernate Reactive and Quarkus — Baeldung](https://www.baeldung.com/java-hibernate-reactive-and-quarkus) — accessed 2026-08-03

## Changelog
- 2026-08-03 — created
