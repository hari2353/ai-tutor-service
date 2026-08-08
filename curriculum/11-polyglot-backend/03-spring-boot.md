# Spring Boot: DI Internals, WebFlux vs MVC, Data, Security, Testcontainers, Spring AI

> **Track:** T11 Polyglot Backend · **Time:** 3h · **Prereqs:** T11-java-modern · **Updated:** 2026-08-03
> **Module id:** `T11-spring-boot` · **Tags:** java

## The 30-second version

Spring's dependency injection isn't magic — it's a bean lifecycle (instantiate, populate dependencies, run `BeanPostProcessor`s before and after `@PostConstruct`, hand you a ready object) plus, for anything annotated `@Transactional`/`@Async`/`@Cacheable` or matched by an `@Aspect`, a runtime-generated **proxy** (CGLIB subclass for concrete classes, JDK dynamic proxy for interfaces) that wraps your bean so the container can intercept calls before they hit your code — which is exactly why calling an `@Transactional` method from another method *on the same class* silently skips the transaction: you bypassed the proxy by calling `this.method()` directly. Spring MVC (Tomcat, blocking, thread-per-request) versus WebFlux (Netty, non-blocking, event-loop) is a real architectural fork, not a style preference: WebFlux only pays off when you're I/O-bound and fanning out to multiple concurrent downstreams with a fully non-blocking stack top to bottom (R2DBC, not JDBC, all the way down) — and Java 21+ virtual threads (`spring.threads.virtual.enabled=true`, matured further in Spring Boot 4) have quietly removed most of the reason to choose WebFlux for the "handle more concurrent connections" use case, leaving reactive's real remaining case narrower: genuine backpressure requirements and streaming pipelines. Spring Data's repository abstraction generates queries from method names or JPQL, but the classic N+1 query trap (a `findAll()` that looks like one query and executes 1+N) is still the single most common Spring performance bug in production. Spring Security 6/7's `SecurityFilterChain` bean replaced the deprecated `WebSecurityConfigurerAdapter` entirely — component-based, composable filter chains are now the only supported pattern. Testcontainers plus `@ServiceConnection` (Spring Boot 3.1+) replaced H2-as-a-Postgres-stand-in for integration tests, running the real database in Docker instead of a fake that silently diverges from production SQL dialect behavior. And as of mid-2026, the ecosystem itself moved: Spring Boot 4.0 (November 2025, on Spring Framework 7) is the current generation, and Spring AI 2.0 (GA June 2026) hard-requires Boot 4 — a team still on Boot 3.x cannot adopt Spring AI 2.0 without migrating first, which is a real, current planning constraint, not a hypothetical.

## Why this gets asked

Because Spring is the framework almost every Java backend candidate claims fluency in, and the gap between "I've used `@Autowired` for years" and "I understand what the container actually does" is enormous and easy to probe. The interviewer has debugged the self-invocation-skips-the-proxy bug personally — it's one of the most common Spring surprises in code review — and has almost certainly watched a team adopt WebFlux because it sounded more scalable, then spend months fighting a reactive pipeline for a workload that didn't need it (a CRUD service with no real fan-out, forced into `Mono`/`Flux` everywhere, debugging stack traces that don't match the code anymore). They want to know whether you reach for the architecture that fits the actual I/O shape of the workload, or the one that sounds impressive in a design doc — and whether you know that virtual threads changed this calculus in the last two years, which is current enough that many engineers' mental model is stale.

---

## Lineage: past → present → future

**What came before.** Pre-Spring Java EE (J2EE) enterprise development meant heavyweight, XML-configured EJB containers, verbose `web.xml` deployment descriptors, and a programming model where testing anything required a running application server — a unit test for a service class typically meant standing up a container, because EJBs couldn't easily be instantiated plain. Rod Johnson's *Expert One-on-One J2EE Design and Development* (2002) and the Spring Framework that followed argued the opposite: plain old Java objects (POJOs), dependency injection instead of container lookups (`JNDI`), and configuration that didn't require a full app server to test. Spring Boot (2014) then killed the second half of that era's pain — hand-assembled XML bean wiring and manual `web.xml`/servlet configuration — with convention-over-configuration auto-configuration and an embedded servlet container, collapsing "set up a runnable web app" from a day of XML to a single `@SpringBootApplication` annotation and a `main` method.

**Where it stands now.** Spring Boot's DI container, auto-configuration, and starter-dependency model are the dominant pattern for JVM backend services — genuinely production-standard, not a research direction. Spring Data (repository abstraction over JPA/JDBC/MongoDB/R2DBC), Spring Security (declarative, filter-chain-based auth), and Spring Cloud (for the microservices-adjacent concerns) round out an ecosystem most JVM shops build on by default rather than assembling equivalent tooling themselves. The live disagreement, and it is genuinely live, is WebFlux versus MVC-with-virtual-threads for I/O-bound services: WebFlux (built on Project Reactor, running on Netty) was the answer to C10K-style thread exhaustion before virtual threads existed, and it remains the right tool for genuine backpressure and streaming use cases, but for the much larger set of "I just want to handle more concurrent blocking I/O without paying for thousands of OS threads" services, Java 21+ virtual threads under plain Spring MVC now solve the same underlying problem with dramatically simpler code — sequential, debuggable, ordinary stack traces — which has visibly slowed new WebFlux adoption industry-wide since 2023. Separately, and more urgent for anyone job-hunting in mid-2026 specifically: **Spring Boot 4.0 (GA November 20, 2025, on Spring Framework 7.0) is now the current generation**, and **Spring AI 2.0 (GA June 2026) hard-requires Boot 4** — Spring Boot 3.5 and Spring Framework 6.2 reached end-of-life June 30, 2026, meaning teams still on Boot 3.x are on an unsupported line and cannot adopt the current Spring AI without migrating first. This is a concrete, current fact worth knowing cold rather than assuming "Spring Boot 3" is still the latest, which was true as recently as late 2025 and is a common stale assumption.

**Where it's heading.** Virtual threads keep eating into WebFlux's traditional territory as Spring Boot 4's virtual-thread support matures (better interaction with `RestClient`, `JdbcTemplate`, and the broader ecosystem that was historically blocking-only) — expect WebFlux to keep narrowing toward its genuinely differentiated use cases (true streaming APIs, systems with hard backpressure requirements) rather than being the default answer to "we need to scale." Spring AI's rapid 2025-2026 iteration (1.0 GA, then 2.0 GA within about a year, tightly coupled to the Boot 4/Framework 7 baseline) signals the Spring team treating AI-application plumbing — `ChatClient`, structured output binding, RAG "advisors," MCP tool integration — as first-class framework surface rather than a bolt-on library, which is a real and fast-moving direction, not settled consensus yet; expect continued API churn there for at least another major version or two given the pace already observed (1.0 to 2.0 with breaking changes inside about a year). Testcontainers-based integration testing (real Docker containers over embedded fakes) is fully consensus now and the direction is toward tighter first-class framework integration (`@ServiceConnection` auto-detecting more container types) rather than any reversal back toward embedded-database testing.

---

## Mental model

```
BEAN LIFECYCLE (what @Autowired actually triggers):

  1. Instantiate           constructor called (constructor injection resolves
                            dependencies from the container HERE, recursively)
  2. Populate properties   field/setter injection happens after construction
  3. Aware interfaces      BeanNameAware, ApplicationContextAware, etc.
  4. BeanPostProcessor     postProcessBeforeInitialization() -- proxies for
     (before)              AOP/@Transactional CAN be created around here
  5. Init callbacks        @PostConstruct, then InitializingBean.afterPropertiesSet()
  6. BeanPostProcessor     postProcessAfterInitialization() -- THIS is commonly
     (after)               where the AOP proxy actually gets swapped in, wrapping
                            the real bean; the object returned to the container
                            from here on is the PROXY, not your raw instance
  7. ---- bean is READY, used by the application ----
  8. @PreDestroy, then DisposableBean.destroy() on context shutdown

PROXY MECHANICS (why self-invocation breaks @Transactional/@Async/@Cacheable):

  Caller ──▶ [PROXY] ──▶ intercepts call, opens transaction/checks cache/etc
                │              │
                └─ calls ──▶ [REAL BEAN.method()]

  Caller = OUTSIDE the bean: goes through the proxy. Annotation honored.
  Caller = `this.method()` FROM INSIDE the same bean: bypasses the proxy
  entirely — you're calling the real object directly, proxy never sees it,
  @Transactional/@Async/@Cacheable silently does nothing.

MVC vs WEBFLUX (the actual fork):

  MVC (Tomcat):  1 thread blocks per in-flight request (or per virtual thread
                 if enabled) — simple, sequential, debuggable stack traces
  WEBFLUX (Netty): small fixed event-loop thread count, Mono/Flux everywhere,
                 REQUIRES non-blocking all the way down (R2DBC not JDBC, or
                 you've just reintroduced blocking on an event-loop thread
                 and made things WORSE than plain MVC)
```

---

## How it actually works

### Dependency injection: constructor vs field, and why constructor wins

```java
// PREFERRED: constructor injection
@Service
public class OrderService {
    private final PaymentClient paymentClient;
    private final OrderRepository repository;

    public OrderService(PaymentClient paymentClient, OrderRepository repository) {
        this.paymentClient = paymentClient;
        this.repository = repository;
    }
}

// DISCOURAGED (but common in legacy code): field injection
@Service
public class OrderService {
    @Autowired
    private PaymentClient paymentClient;   // final impossible, hard to test without
}                                            // Spring, hides missing dependencies until runtime
```

Constructor injection makes dependencies explicit and `final` — the class literally cannot exist in a half-constructed state with a missing collaborator, and plain unit tests can `new OrderService(mockClient, mockRepo)` with zero Spring context needed. Field injection compiles even with a missing bean until the container tries to wire it at startup, and requires reflection-based test setup (`@InjectMocks` or a full Spring context) to exercise. As of Spring Framework 4.3, a single constructor no longer needs an explicit `@Autowired` — it's inferred — which is part of why constructor injection is now the unambiguous default recommendation, not merely a preference.

**Circular dependencies**: constructor injection for a genuine A→B→A cycle fails fast at startup with `BeanCurrentlyInCreationException` — which is the correct outcome, because a true constructor-level cycle usually indicates a design problem (extract a third collaborator, or use `@Lazy` on one side deliberately). Field/setter injection can *paper over* circular dependencies via Spring's three-level cache (`singletonObjects`, `earlySingletonObjects`, `singletonFactories`) that exposes a partially-constructed bean early specifically to break cycles — this works, but masking a real cyclical-design smell behind a container mechanism is exactly the tradeoff to be able to name if asked why constructor injection is preferred.

### AOP proxies: CGLIB vs JDK dynamic proxy, and the self-invocation trap

```java
@Service
public class ReportService {
    @Transactional
    public void generateReport() {
        saveIntermediateResult();   // BUG: this call bypasses the proxy entirely
    }

    @Transactional
    public void saveIntermediateResult() {
        // this method's OWN @Transactional never actually starts a new
        // transaction boundary when called via `this.` from generateReport() —
        // it just runs as part of whatever transaction (or none) generateReport
        // is already in, because the proxy that would open a NEW transaction
        // was never invoked
    }
}
```

Spring creates a proxy for any bean matched by AOP (declarative `@Transactional`, `@Async`, `@Cacheable`, or a custom `@Aspect`): a **JDK dynamic proxy** if the bean implements at least one interface (proxying the interface), or a **CGLIB proxy** (a runtime-generated subclass overriding the public/protected methods) if it doesn't — Spring Boot defaults to CGLIB-style proxying for classes since Spring Boot 2 regardless of interface presence, for consistency. Either way, the proxy is a *separate object wrapping yours*, and only calls arriving **from outside the bean, through the container-managed reference**, pass through it. A call from `this.` inside the same class goes directly to the real object's method, skipping the proxy's interception logic entirely — the classic, extremely common bug where a developer expects `@Transactional` (or `@Async`, or `@Cacheable`) to "just work" on a method called internally and it silently doesn't, with no error, no warning, just wrong behavior discovered under load or during an incident. The fixes, in order of preference: restructure so the method is called from a different bean (through the proxy naturally), or inject a self-reference (`@Autowired private ReportService self;` and call `self.saveIntermediateResult()`, deliberately routing through the proxy), or use `AopContext.currentProxy()` with `exposeProxy=true` as a last resort.

### WebFlux vs MVC: the actual decision, not the marketing

Spring MVC runs on a Servlet container (Tomcat by default) with a thread-per-request (or per-virtual-thread) model — each request occupies a thread for its full duration, including any blocking I/O it does, exactly the model covered mechanically in `T16-io-models`. Spring WebFlux runs on Netty by default with a small, fixed pool of event-loop threads handling many concurrent requests non-blockingly via `Mono`/`Flux` — the reactive analog of the epoll-based event loop, also covered there.

**The trap that defeats WebFlux entirely**: calling a blocking JDBC driver, a blocking HTTP client, or `Thread.sleep()` from inside a reactive pipeline blocks an event-loop thread exactly like the async-Python or Node.js equivalent — and because there are only a handful of event-loop threads (commonly sized near CPU core count), one blocked call can stall a disproportionate share of total request-handling capacity. This is why "migrate to WebFlux" is not a drop-in change: it requires a genuinely non-blocking stack end to end — **R2DBC** instead of JDBC for reactive relational database access, `WebClient` instead of `RestTemplate`/blocking HTTP clients, reactive Redis/Mongo drivers — and any legacy blocking dependency in the chain (a third-party SDK with no reactive variant) either needs wrapping via `Schedulers.boundedElastic()` (WebFlux's escape hatch, conceptually similar to `run_in_threadpool` in FastAPI, covered in `T11-fastapi-deep`) or becomes a hard blocker to full adoption.

**Where virtual threads changed the calculus**: `spring.threads.virtual.enabled=true` (Java 21+, matured in Spring Boot 4 with broader ecosystem support) lets plain Spring MVC handle very high concurrent blocking I/O without WebFlux's programming model cost — the exact motivating use case for WebFlux (many concurrent I/O-bound requests without exhausting OS threads) is now addressable with ordinary sequential code and virtual threads. This has genuinely narrowed WebFlux's remaining differentiated territory to: (1) true streaming/long-lived-connection APIs (server-sent events, WebSocket-heavy services) where Reactor's operators are a natural fit for the data flow itself, not just for concurrency; (2) hard backpressure requirements, where a slow consumer needs to signal a fast producer to slow down, which `Flux`'s reactive-streams-based backpressure protocol handles natively and a virtual-thread-based blocking pipeline does not; and (3) services already deeply invested in the reactive ecosystem where migrating back would cost more than it's worth.

```java
// Spring Boot 4 — enabling virtual threads for the MVC thread pool, application.yml
spring:
  threads:
    virtual:
      enabled: true

// WebFlux — the correct way to call a blocking legacy client from a reactive pipeline
Mono<Report> generateReport() {
    return Mono.fromCallable(() -> legacyBlockingSdk.fetch())
        .subscribeOn(Schedulers.boundedElastic());   // moves the blocking call OFF the event loop
}
```

### Spring Data: the N+1 trap and how to actually see it

```java
public interface OrderRepository extends JpaRepository<Order, Long> {
    List<Order> findByCustomerId(Long customerId);   // query DERIVED from the method name
}

// Looks like one query. Is actually 1 + N if Order.items is a lazy @OneToMany:
for (Order order : orderRepository.findByCustomerId(customerId)) {
    System.out.println(order.getItems().size());   // triggers a SEPARATE query PER order
}
```

Spring Data JPA generates the initial query correctly (one `SELECT` for the orders), but each lazy-loaded association accessed afterward triggers its own round trip — for 50 orders, that's 51 queries instead of 1 or 2, invisible in the code (it *looks* like a plain getter call) and only visible in a query log or an APM trace showing repeated near-identical `SELECT ... WHERE order_id = ?` calls in a tight loop. This is, empirically, one of the most common real-world Spring performance incidents — it passes code review because nothing about the code *looks* wrong, and it passes unit tests against small datasets because N+1 with N=3 is invisible; it only becomes a production incident at N=5,000. The fixes: `JOIN FETCH` in a custom JPQL query to eagerly fetch the association in the original query, `@EntityGraph` to declare which associations to fetch eagerly for a specific repository method without changing the entity's default fetch type globally, or Spring Data's **projection** interfaces to select only the fields actually needed instead of hydrating full entity graphs.

```java
@Query("SELECT o FROM Order o JOIN FETCH o.items WHERE o.customerId = :customerId")
List<Order> findByCustomerIdWithItems(@Param("customerId") Long customerId);   // ONE query
```

### Spring Security: the filter chain, and why `WebSecurityConfigurerAdapter` is gone

Spring Security intercepts every request through a chain of servlet `Filter`s — authentication filters, CSRF checks, authorization decisions — configured today exclusively as a `SecurityFilterChain` `@Bean`, not by extending a base class:

```java
@Bean
public SecurityFilterChain filterChain(HttpSecurity http) throws Exception {
    return http
        .authorizeHttpRequests(auth -> auth
            .requestMatchers("/api/public/**").permitAll()
            .requestMatchers("/api/admin/**").hasRole("ADMIN")
            .anyRequest().authenticated())
        .oauth2ResourceServer(oauth2 -> oauth2.jwt(Customizer.withDefaults()))
        .csrf(csrf -> csrf.disable())   // typical for a stateless JWT-based API; NOT for session-based apps
        .build();
}
```

`WebSecurityConfigurerAdapter` — the old pattern of extending a base class and overriding `configure(HttpSecurity)` — was deprecated in Spring Security 5.7 and removed entirely by Spring Security 6/7; the component-based `SecurityFilterChain` bean approach is the only supported pattern now, and it composes better (multiple filter chains for different URL patterns, each independently testable as a bean) than the old single-inheritance model ever could. **A specific, checkable trap**: disabling CSRF is correct and standard for a stateless, token-authenticated (JWT/OAuth2) API with no browser session/cookie-based auth, but disabling it reflexively on a session-cookie-based application reopens a real cross-site request forgery vector — the decision depends on the auth mechanism, not on "CSRF is annoying in tests."

### Testcontainers: real containers over fakes

```java
@SpringBootTest
@Testcontainers
class OrderRepositoryIT {
    @Container
    @ServiceConnection
    static PostgreSQLContainer<?> postgres = new PostgreSQLContainer<>("postgres:17");

    @Autowired
    OrderRepository repository;
    // no manual datasource URL wiring needed — @ServiceConnection auto-configures it
}
```

Before Testcontainers' Spring integration, integration tests commonly ran against H2 in Postgres-compatibility mode — fast, but H2 doesn't implement Postgres's actual SQL dialect, JSON functions, or locking behavior faithfully, so a query that works against H2 can fail (or silently behave differently) against real Postgres in production, and vice versa — a real, recurring class of "works in tests, breaks in prod" bug. `@ServiceConnection` (Spring Boot 3.1+) auto-detects the container type and wires the corresponding `ConnectionDetails` bean automatically, eliminating the manual `@DynamicPropertySource` boilerplate earlier Testcontainers integration required. The tradeoff is real too: container startup adds seconds per test class (mitigated by container reuse across a test suite run) and requires Docker in CI, which is now a standard, accepted cost almost everywhere but is worth naming as a cost, not pretending it's free.

### Spring AI: current shape, briefly

Spring AI 2.0 (GA June 2026, requiring Spring Boot 4/Framework 7) provides `ChatClient` as the primary abstraction over LLM providers, structured output binding (mapping a model's response directly to a Java record/POJO), an "advisor" chain concept for composing RAG retrieval, memory, and logging around a chat call declaratively, and MCP (Model Context Protocol) integration for tool calling — the framework's own answer to the agentic-tool-calling pattern covered generally in `T07-agentic-ai`. Because it hard-requires Boot 4, a team on Boot 3.x planning to adopt current Spring AI needs to budget the Boot 3→4 migration first — a real, current sequencing constraint worth naming unprompted if the topic comes up, since it's easy to assume (incorrectly, as of mid-2026) that the two can be adopted independently.

---

## Build it from scratch

A minimal slice demonstrating the proxy trap and its fix — the piece most worth being able to write cold:

```java
// WRONG — self-invocation bypasses the @Transactional proxy
@Service
public class AccountService {
    private final AccountRepository repo;
    public AccountService(AccountRepository repo) { this.repo = repo; }

    public void transferBatch(List<Transfer> transfers) {
        for (Transfer t : transfers) {
            applyTransfer(t);   // BUG: calls the real object, not the proxy —
        }                        // each applyTransfer() runs WITHOUT its own
    }                             // transaction boundary; a failure mid-batch
                                   // leaves partial writes committed already

    @Transactional
    public void applyTransfer(Transfer t) { /* debit, credit */ }
}

// RIGHT — split into a separate bean so the call crosses the proxy boundary
@Service
public class AccountBatchService {
    private final AccountTransferService transferService;   // different bean
    public AccountBatchService(AccountTransferService transferService) {
        this.transferService = transferService;
    }
    public void transferBatch(List<Transfer> transfers) {
        for (Transfer t : transfers) {
            transferService.applyTransfer(t);   // crosses the proxy — @Transactional honored
        }
    }
}

@Service
public class AccountTransferService {
    @Transactional
    public void applyTransfer(Transfer t) { /* debit, credit, isolated tx per transfer */ }
}
```

A fuller runnable lab pairing a WebFlux vs MVC-with-virtual-threads throughput comparison (fan-out to 3 simulated downstreams under `wrk`), plus the N+1 query demo with a query-count assertion, belongs in `labs/java/03-spring-boot/`.

---

## How it's done in production

| Symptom | Cause | Fix |
|---|---|---|
| `@Transactional`/`@Async`/`@Cacheable` silently doesn't work on a specific call path | Self-invocation — the method was called via `this.` from another method on the same bean, bypassing the AOP proxy | Move the annotated method to a separate bean, or inject a self-reference and call through it |
| A single "list orders" endpoint fires dozens to thousands of near-identical SQL queries under load | N+1 — lazy-loaded JPA associations accessed in a loop, each triggering its own round trip | `JOIN FETCH` or `@EntityGraph` for the specific query path, or a projection interface selecting only needed fields |
| WebFlux service throughput collapses under load despite the reactive rewrite | A blocking call (legacy SDK, blocking JDBC driver, `Thread.sleep`) left inside the reactive pipeline, stalling an event-loop thread exactly like the async-Python/Node equivalent | Wrap it in `Mono.fromCallable(...).subscribeOn(Schedulers.boundedElastic())`, or replace it with a genuinely non-blocking client (R2DBC, `WebClient`) |
| Circular dependency error at startup (`BeanCurrentlyInCreationException`) after switching from field to constructor injection | A genuine A→B→A dependency cycle that field injection's three-level-cache mechanism was silently papering over | Extract a shared third collaborator to break the cycle, or deliberately `@Lazy` one side if the cycle is truly unavoidable — don't silently revert to field injection to make the error disappear |
| Integration tests pass, the same query fails or behaves differently in production Postgres | Tests ran against H2 in "Postgres compatibility mode," which doesn't faithfully implement Postgres's real SQL dialect/locking/JSON behavior | Testcontainers + `@ServiceConnection` against the real database image |
| CSRF-related 403s appear after copying a security config from a stateless-API example into a session-cookie-based app | CSRF disabled reflexively, appropriate for a JWT/OAuth2 stateless API but not for cookie-session auth, where it reopens a real CSRF vector | Enable CSRF protection for session/cookie-based auth flows; disabling it is specifically an acceptable tradeoff for stateless token auth only |
| Team migrates to Spring AI 2.0 mid-project and the build breaks across the app, not just the AI module | Spring AI 2.0 hard-requires Spring Boot 4/Framework 7 as a baseline, not an incremental add | Sequence the Boot 3→4 migration first as its own project phase before adopting Spring AI 2.0 |

---

## Tradeoffs & when NOT to use it

- **Don't adopt WebFlux by default for a new service in 2026.** With virtual threads maturing under plain Spring MVC, WebFlux's traditional "handle more concurrent I/O" justification mostly no longer applies — reserve it for genuine backpressure/streaming needs or teams already deeply invested in the reactive stack.
- **Don't half-migrate to WebFlux.** A reactive controller calling a blocking JDBC repository underneath is worse than plain MVC, not better — it pays reactive's complexity cost while still blocking event-loop threads. It's genuinely all-or-nothing per request path.
- **Don't rely on field injection for anything you'd call "core" application logic.** It hides missing dependencies until runtime, resists plain unit testing, and can mask real circular-dependency design problems behind the three-level cache instead of surfacing them at startup where they're cheap to fix.
- **Don't assume Spring Data's generated method-name queries are free of N+1 risk just because the code looks like one call.** Any lazy association accessed in a loop after the initial query is a potential N+1 — audit with a query-count test or a SQL log, not by reading the Java code alone.
- **Don't disable CSRF as a reflex to make tests/Postman easier.** It's a real security control for session/cookie-based auth; only stateless token auth (JWT/OAuth2 bearer tokens with no cookie session) makes disabling it a defensible default.
- **Don't skip Testcontainers for "just use H2, it's faster."** Faster tests that pass against behavior the production database doesn't actually have are a false economy — the failure shows up in production instead, which is strictly more expensive to debug.

---

## Interview questions

### Q1 — Explain why calling an `@Transactional` method from another method on the same class doesn't start a transaction.
**Testing:** whether the proxy mechanism is understood as the actual mechanism, not "Spring handles it."
**Answer:** `@Transactional` (like `@Async`, `@Cacheable`) works via a runtime-generated proxy (CGLIB subclass, or a JDK dynamic proxy for interface-based beans) that wraps the real bean and intercepts calls arriving from outside it. A call via `this.method()` from inside the same class goes straight to the real object, never touching the proxy, so none of the interception logic — starting a transaction, checking a cache — runs. No error is thrown; it silently behaves as if the annotation weren't there.
**Follow-up trap:** *"How would you even detect this in an existing codebase?"* — grep for annotated methods called via `this.` within the same class, or, more reliably, write a test asserting the expected transactional boundary (e.g. that a partial failure mid-batch rolls back correctly) rather than trusting a code read; the bug is invisible by inspection in a large method.

### Q2 — Walk through the Spring bean lifecycle and identify exactly where an AOP proxy gets introduced.
**Testing:** whether the lifecycle is understood as a sequence of extension points, not a black box.
**Answer:** Instantiate (constructor injection resolves dependencies here) → populate remaining properties → Aware-interface callbacks → `BeanPostProcessor.postProcessBeforeInitialization` → init callbacks (`@PostConstruct`, then `InitializingBean.afterPropertiesSet()`) → `BeanPostProcessor.postProcessAfterInitialization` → ready. The AOP proxy is typically created and swapped in during `postProcessAfterInitialization` — the bean reference the container hands out to every other bean depending on it is the proxy, not the raw object, from this point on.
**Follow-up trap:** *"Does `@PostConstruct` run on the proxy or the real bean?"* — the real bean; it runs before the proxy is typically substituted in `postProcessAfterInitialization`, so `@PostConstruct` logic calling another `@Transactional` method on `this` has the same self-invocation problem as any other internal call.

### Q3 — Constructor injection vs field injection: what's the concrete argument for constructor injection beyond style?
**Testing:** whether the reasoning goes past "it's best practice" to the actual mechanism.
**Answer:** Constructor injection makes every dependency `final` and required at construction — the object cannot exist half-wired, and a plain unit test can `new` it directly with mocks, no Spring context needed. Field injection compiles with a missing bean until the container tries to wire it at startup, needs reflection-based test tooling, and — the sharper point — its ability to "just work" around a genuine circular dependency via Spring's three-level singleton cache can mask a real design problem that constructor injection would surface immediately as a startup failure.
**Follow-up trap:** *"So is the three-level cache a bad thing?"* — no, it's a legitimate mechanism for legitimate cases (a genuinely justified cycle handled deliberately with `@Lazy`), but relying on it *by accident*, because you happened to use field injection, hides a design smell you'd rather see at startup than debug later.

### Q4 — When would you choose WebFlux over Spring MVC with virtual threads enabled, given both target the same "handle more concurrency" problem?
**Testing:** staff-level judgment on a genuinely current (2025-2026) architectural fork, not a memorized "WebFlux is for scale" answer.
**Answer:** Choose WebFlux specifically for true streaming/long-lived-connection APIs where Reactor's operators fit the data flow itself (SSE, high-volume WebSocket handling), or for workloads with a hard backpressure requirement — a slow consumer needing to signal a fast producer to slow down, which reactive streams handles natively and a virtual-thread blocking pipeline does not. For the much more common case of "many concurrent blocking I/O calls, no real backpressure need," plain Spring MVC with `spring.threads.virtual.enabled=true` now solves the original motivating problem with far simpler, more debuggable code.
**Follow-up trap:** *"Your team already has a large WebFlux codebase — do you migrate it back to virtual threads?"* — not reflexively; migration cost (rewriting Mono/Flux pipelines, replacing R2DBC, retraining the team) has to be weighed against the actual pain the reactive model is causing today. "Virtual threads exist now" isn't sufficient justification alone to rewrite a working, well-understood reactive system.

### Q5 — What's the N+1 query problem in Spring Data JPA, and why does it survive code review so often?
**Testing:** whether the mechanism and its stealth are both understood.
**Answer:** A repository method returns a list via one query, but each entity's lazily-loaded association, when accessed afterward (often in a loop, or implicitly during serialization), triggers its own separate query — for N entities, that's 1+N total round trips instead of 1 or 2. It survives review because the offending code is just `order.getItems().size()` — an ordinary-looking getter call with nothing visually wrong — and passes small-scale tests because N+1 with N=3 is invisible; it only becomes a real incident at production data volumes.
**Follow-up trap:** *"How do you catch this before production?"* — a query-count assertion in an integration test (Hibernate's statistics API, or a library like `db-util`'s `QueryCountValidator`) against a realistic-sized dataset, or routinely reviewing the SQL log for a suspicious run of near-identical queries — code review alone reliably misses it.

### Q6 — Why was `WebSecurityConfigurerAdapter` removed, and what replaced it?
**Testing:** whether current (not 2020-era) Spring Security config knowledge is present.
**Answer:** It was deprecated starting Spring Security 5.7 and removed by Spring Security 6/7 in favor of declaring one or more `SecurityFilterChain` `@Bean`s directly. The inheritance-based model only allowed one security configuration per application cleanly; the bean-based approach lets you compose multiple independently-ordered `SecurityFilterChain`s for different URL patterns (a public API chain, an admin chain, an actuator chain), each testable and configurable on its own.
**Follow-up trap:** *"Is disabling CSRF in your SecurityFilterChain always safe for a REST API?"* — no; it's a defensible default specifically for stateless, token-authenticated (JWT/OAuth2 bearer) APIs with no cookie-based session. A session-cookie-authenticated application disabling CSRF reopens a genuine cross-site request forgery vector — the decision depends on the auth mechanism, not on API-vs-not.

### Q7 — What does Testcontainers' `@ServiceConnection` actually solve that H2-in-Postgres-mode didn't?
**Testing:** understanding the real-vs-fake-database tradeoff concretely.
**Answer:** H2 running in Postgres compatibility mode doesn't faithfully implement Postgres's actual SQL dialect, JSON functions, or locking/isolation behavior — a query that passes against H2 can behave differently (or fail outright) against real Postgres in production, a class of "works in CI, breaks in prod" bug. Testcontainers runs the actual database engine in Docker for the test; `@ServiceConnection` (Spring Boot 3.1+) auto-detects the container type and wires the corresponding connection details automatically, removing the manual `@DynamicPropertySource` boilerplate earlier integration required.
**Follow-up trap:** *"What's the real cost of this approach?"* — container startup time per test run (mitigated by container reuse across a suite) and a hard Docker dependency in CI. Worth naming as a real, accepted cost rather than implying it's free — it's a good tradeoff, not a costless one.

### Q8 — Design a `SecurityFilterChain` for an API serving both a public unauthenticated endpoint and an admin-only endpoint, backed by OAuth2 JWT bearer tokens.
**Testing:** applying the filter-chain model to a concrete scenario.
**Answer:** One `SecurityFilterChain` bean using `authorizeHttpRequests` to `permitAll()` the public path pattern, require `hasRole("ADMIN")` for the admin path pattern, and `authenticated()` for everything else by default (deny-by-default is the safer posture — explicitly permit what should be open rather than explicitly deny what should be closed), with `.oauth2ResourceServer(oauth2 -> oauth2.jwt(...))` configuring JWT bearer-token validation, and CSRF disabled since this is a stateless, token-authenticated API with no cookie session to protect.
**Follow-up trap:** *"What if you need a completely different auth mechanism for one subset of paths — say, an internal admin UI using session cookies alongside the public JWT API?"* — declare a second `SecurityFilterChain` bean matched to that path pattern via `securityMatcher(...)`, with its own, independently configured chain (session-based auth, CSRF enabled) — multiple chains, ordered by specificity, is exactly the composability the bean-based model was built to support over the old single-inheritance approach.

### Q9 — What does Spring AI 2.0's hard dependency on Spring Boot 4 mean for a team currently on Boot 3.x wanting to adopt it?
**Testing:** current (2026), specific ecosystem knowledge rather than assuming frameworks are always independently adoptable.
**Answer:** They cannot adopt Spring AI 2.0 incrementally alongside their existing Boot 3.x application — Spring AI 2.0 requires the Boot 4/Framework 7 baseline, so the Boot 3→4 migration has to happen first, as its own project phase, before Spring AI 2.0 becomes available at all. This is a real, current sequencing constraint as of mid-2026, not a hypothetical — Spring Boot 3.5/Framework 6.2 reached end-of-life June 30, 2026, adding urgency to the migration independent of the Spring AI motivation.
**Follow-up trap:** *"Could they use Spring AI 1.x on Boot 3.x instead, to avoid the migration?"* — yes, that's a legitimate interim path if the team isn't ready for the Boot 4 migration, accepting Spring AI 1.x's smaller/older feature surface until the migration is scheduled; naming that tradeoff explicitly (stay on 1.x now vs. front-load the Boot 4 migration to get 2.0) is the stronger answer over treating it as a forced immediate choice.

### Q10 — A `Mono.fromCallable(() -> blockingCall())` is used without `.subscribeOn(Schedulers.boundedElastic())`. What breaks, and why?
**Testing:** the specific mechanism of the most common WebFlux production mistake.
**Answer:** Without `subscribeOn`, the blocking call executes on whatever thread the reactive chain happens to already be running on by default — commonly one of WebFlux's small, fixed set of Netty event-loop threads — which blocks that event-loop thread for the call's duration exactly like the analogous FastAPI/Node.js mistake of a blocking call inside an async handler. Since there are only a handful of event-loop threads total, this stalls a disproportionate share of the service's total request-handling capacity, producing the same symptom as any event-loop-blocking bug: throughput collapse under load with CPU appearing idle.
**Follow-up trap:** *"Why `boundedElastic` specifically, and not `parallel()`?"* — `Schedulers.parallel()` is sized for CPU-bound work (roughly core-count threads) and would itself become the bottleneck under blocking I/O; `boundedElastic` is specifically designed for exactly this case — wrapping blocking calls — with a larger, elastic (bounded but much larger than `parallel`) thread pool intended to absorb blocking work without starving the CPU-bound scheduler.

### Q11 — Why does Spring Data's method-name-derived query (`findByCustomerIdAndStatus`) sometimes get replaced with an explicit `@Query` in production code?
**Testing:** whether the limits of the convention-based approach are understood, not just its convenience.
**Answer:** Method-name derivation is readable and fast to write for simple predicates, but it can't express joins/fetch strategies (the N+1 fix requires explicit `JOIN FETCH`), complex conditional logic, database-specific functions, or projections selecting a subset of fields — and very long derived method names (`findByCustomerIdAndStatusAndCreatedAtBetweenOrderByCreatedAtDesc`) become harder to read than the equivalent JPQL. Explicit `@Query` (or `@EntityGraph` for fetch strategy alone) is reached for specifically when the query's actual requirement — eager fetching, a projection, a native SQL feature — exceeds what name-derivation can express.
**Follow-up trap:** *"Is there a performance difference between the two approaches for an equivalent simple query?"* — no meaningful difference at execution time; Spring Data compiles the derived method name into essentially the same JPQL/SQL a hand-written `@Query` would produce for a simple predicate. The choice is about expressiveness and readability, not runtime performance, for the cases where derivation is actually capable of expressing the query.

---

## Red flags that fail you

- Not knowing why `@Transactional` fails on self-invocation, or blaming it on "Spring bugs."
- Recommending WebFlux reflexively for "scale" without mentioning virtual threads have narrowed its differentiated use cases since 2023.
- Half-migrating to WebFlux (reactive controller, blocking repository underneath) and not recognizing that's worse than plain MVC.
- Missing N+1 query risk entirely when reviewing a Spring Data repository method that returns entities with lazy associations.
- Citing `WebSecurityConfigurerAdapter` as current practice (removed in Spring Security 6/7).
- Disabling CSRF reflexively without naming the stateless-token-auth condition that makes it safe.
- Recommending H2-in-compatibility-mode over Testcontainers for integration tests without acknowledging the dialect-fidelity gap.
- Assuming Spring Boot 3.x is still the current generation in mid-2026, or not knowing Spring AI 2.0 requires Boot 4.

---

## Cheat card

```
BEAN LIFECYCLE: instantiate (ctor injection resolves deps) -> populate props ->
  Aware callbacks -> BeanPostProcessor.before -> @PostConstruct/InitializingBean ->
  BeanPostProcessor.after (PROXY TYPICALLY SWAPPED IN HERE) -> ready -> @PreDestroy

PROXY: CGLIB (subclass) for concrete classes, JDK dynamic proxy for interfaces.
  Only calls from OUTSIDE the bean (through the container reference) hit the
  proxy. `this.method()` from inside = bypasses proxy = @Transactional/@Async/
  @Cacheable SILENTLY does nothing. Fix: separate bean, or self-injected ref.

DI: constructor injection preferred — final fields, plain-new()-able in tests,
  genuine cycles fail fast (BeanCurrentlyInCreationException). Field injection
  can mask real cycles via the three-level singleton cache.

MVC vs WEBFLUX: MVC = Tomcat, thread-per-request (or per-virtual-thread).
  WebFlux = Netty, small fixed event-loop pool, Mono/Flux, needs R2DBC not
  JDBC end-to-end or you reintroduce blocking on an event-loop thread (WORSE
  than plain MVC). spring.threads.virtual.enabled=true (Java21+, Boot4) now
  solves WebFlux's original "handle more I/O concurrency" case more simply.
  WebFlux's remaining real case: true streaming/backpressure, not general scale.
  Blocking call in reactive pipeline: wrap in Mono.fromCallable(...)
  .subscribeOn(Schedulers.boundedElastic()) — NOT Schedulers.parallel().

SPRING DATA N+1: findByX() returns entities; each LAZY association accessed
  in a loop = separate query. 1+N round trips, invisible in code, invisible
  at small N. Fix: JOIN FETCH / @EntityGraph / projections. Catch via query-
  count test or SQL log, not code review.

SECURITY: WebSecurityConfigurerAdapter REMOVED (Security 6/7) -> SecurityFilterChain
  @Bean only. Multiple chains via securityMatcher() for different path groups.
  CSRF disable = safe ONLY for stateless token (JWT/OAuth2) auth, NOT session-cookie.

TESTCONTAINERS: @Testcontainers + @ServiceConnection (Boot 3.1+) = real DB in
  Docker, auto-wired connection. Replaces H2-compat-mode (dialect-fidelity gap
  = works-in-CI-breaks-in-prod bug class). Cost: container startup + Docker in CI.

CURRENT VERSIONS (mid-2026): Spring Boot 4.0 GA Nov 20 2025 (Spring Framework
  7.0). Spring AI 2.0 GA June 2026 — HARD requires Boot 4, can't adopt on Boot
  3.x. Boot 3.5/Framework 6.2 EOL June 30 2026.
```

## Sources

- [Spring Boot 4.0.0 available now](https://spring.io/blog/2025/11/20/spring-boot-4-0-0-available-now/) — accessed 2026-08-03
- [Spring Framework 7.0 General Availability](https://spring.io/blog/2025/11/13/spring-framework-7-0-general-availability/) — accessed 2026-08-03
- [Spring AI 2.0.0 GA Available Now](https://spring.io/blog/2026/06/12/spring-ai-2-0-0-GA-available-now/) — accessed 2026-08-03
- [Spring AI 2.0 Is Coming Soon. Your Boot 4.0 Migration Does Not Have to Start Tomorrow — HeroDevs](https://www.herodevs.com/blog-posts/spring-ai-2-0-is-coming-soon-your-boot-4-0-migration-does-not-have-to-start-tomorrow) — accessed 2026-08-03
- [Spring Boot Versions, EOL Dates, and Latest Releases (July 2026) — HeroDevs](https://www.herodevs.com/blog-posts/spring-boot-versions-eol-dates-and-latest-releases-april-2026) — accessed 2026-08-03
- [How Spring Boot Creates Proxy Beans — Medium](https://medium.com/@AlexanderObregon/how-spring-boot-creates-proxy-beans-7a22c467898c) — accessed 2026-08-03
- [Spring MVC vs WebFlux: When to Use Which Framework? — GeeksforGeeks](https://www.geeksforgeeks.org/blogs/spring-mvc-vs-spring-web-flux/) — accessed 2026-08-03
- [Working with Virtual Threads in Spring — Baeldung](https://www.baeldung.com/spring-6-virtual-threads) — accessed 2026-08-03
- [Built-in Testcontainers Support in Spring Boot — Baeldung](https://www.baeldung.com/spring-boot-built-in-testcontainers) — accessed 2026-08-03
- [Improved Testcontainers Support in Spring Boot 3.1](https://spring.io/blog/2023/06/23/improved-testcontainers-support-in-spring-boot-3-1/) — accessed 2026-08-03

## Changelog
- 2026-08-03 — created
