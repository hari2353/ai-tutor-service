# Java 21/25: Records, Sealed Types, Pattern Matching, Virtual Threads

> **Track:** T11 Polyglot Backend · **Time:** 2.5h · **Prereqs:** none · **Updated:** 2026-08-03
> **Module id:** `T11-java-modern` · **Tags:** java

## The 30-second version

Modern Java (21 through 25, both LTS) is really two separate stories that get conflated. The first is data modeling: records (JEP 395, Java 16) give you immutable, `equals`/`hashCode`/`toString`-for-free carriers, sealed classes/interfaces (JEP 409, Java 17) let you say exhaustively "this type is exactly these N subtypes and no others," and pattern matching for `switch` plus record deconstruction (finalized JEP 441/440, Java 21) let the compiler enforce that exhaustiveness at every call site — together they give Java real algebraic data types and kill the instanceof-cast-castagain boilerplate that defined pre-modern Java. The second story is concurrency: virtual threads (JEP 444, Java 21) are JVM-scheduled, cheap-to-block threads — millions of them fit in memory where a few thousand platform threads would exhaust it — that let you write plain blocking, sequential code for I/O-bound work and get thread-per-request scalability back without rewriting into reactive/async style. Virtual threads fix exactly one problem, thread-per-request I/O scalability, and fix nothing about CPU-bound work; they're also not free of sharp edges — code holding a `synchronized` block or a native/JNI call **pins** the virtual thread to its OS carrier thread, defeating the whole point, though JDK 24 (JEP 491) eliminated the synchronized-block case, which was the most common one in practice. Java 25 (September 2025, current LTS) finalizes Scoped Values (JEP 506) as the ThreadLocal replacement built for virtual-thread scale, while Structured Concurrency is still in preview after six preview cycles — know that boundary, because claiming it's stable is a real interview mistake.

## Why this gets asked

Because "polyglot backend engineer who also knows modern Java" is a real, specific hiring bar now — companies running Spring/Kafka/K8s stacks want someone who isn't still writing 2015-era Java, and virtual threads specifically changed a production tradeoff (Netty-style reactive vs blocking thread-per-request) that most senior engineers have opinions about but haven't actually benchmarked. The interviewer has likely either migrated a service to virtual threads and hit the pinning problem in production (a service that looked fine in load testing until someone added a `synchronized` block deep in a logging library and throughput fell off a cliff), or reviewed a PR that used records/sealed types incorrectly (a record with a mutable field, or a sealed hierarchy someone worked around instead of extended correctly). They want to know if you understand *why* virtual threads are cheap (what a carrier thread mount/unmount actually is) rather than just that you can add `Executors.newVirtualThreadPerTaskExecutor()` to a config file.

---

## Lineage: past → present → future

**What came before.** Pre-records Java data classes meant writing (or generating via Lombok/IDE templates) a constructor, getters, `equals`, `hashCode`, and `toString` by hand for every immutable value type — 40+ lines of ceremony to represent `record Point(int x, int y)`'s one line, and every one of those hand-written methods was a place for a copy-paste bug (a `hashCode` that didn't match `equals` after a field was added to one but not the other). Before sealed types, "closed" type hierarchies were enforced by convention only — a `private` constructor and a comment saying "only these subclasses exist," which the compiler could not verify and any file in the same package could quietly violate. Before pattern matching for `switch`, exhaustive type-based dispatch meant a chain of `instanceof` checks each paired with a manual cast, or the classic double-dispatch Visitor pattern, both of which needed a human to remember to update every dispatch site when a new subtype was added — the compiler gave you no help. On the concurrency side, the pre-Loom answer to "how do I serve 50,000 concurrent blocking I/O calls" was either a bounded thread pool (which starves under load because a platform thread reserves roughly 1MB of stack by default and the OS scheduler degrades past a few thousand runnable/blocked threads — the same C10K wall covered in `T16-io-models`) or a full rewrite into reactive style (Netty, Project Reactor, RxJava) — correct but a genuinely different, harder-to-debug programming model with its own footguns (stack traces that don't match your code, mandatory non-blocking discipline propagating through every call in the chain).

**Where it stands now.** Records, sealed types, and pattern matching are all finalized and in wide production use — Java Code Geeks' 2025 developer survey cites 55% adoption for records, and pattern matching for switch plus record deconstruction (both finalized in Java 21) means the sealed-hierarchy-plus-exhaustive-switch combination genuinely gives Java the algebraic-data-type ergonomics that Kotlin's `sealed class` and Rust's `enum` have had for years — the switch expression won't compile if a case is missing, unlike the old `instanceof` chain. Virtual threads, also finalized in Java 21 (September 2023), are in real production use — Java Code Geeks' "two years in" retrospective covers actual war stories, not speculation — but adoption has been more cautious than records/sealed types because the pinning problem was a genuine production landmine until JDK 24 fixed the `synchronized`-block case specifically (JEP 491, "Synchronize Virtual Threads without Pinning"). The live disagreement is virtual threads vs the fully reactive/Netty model for high-throughput services: benchmarks circulating in 2025-2026 (loom-webflux-benchmarks and similar) show pure reactive Netty stacks still edging out virtual threads at the very top end of raw RPS on some workloads (one widely cited comparison put pure reactive Netty around 200K RPS against virtual-threads-on-Netty around 150K RPS and virtual-threads-on-Tomcat around 140K RPS, versus roughly 5K RPS for a traditional bounded-thread-pool blocking model on the same hardware) — the gap is real but has narrowed enough that most teams now default to virtual threads for new I/O-bound services and reserve full reactive for the small minority of services where that last 25-30% actually matters enough to justify reactive's debugging cost.

**Where it's heading.** Structured Concurrency (JEP 505, sixth preview in JDK 25) is the direction of travel for how virtual threads compose — treating a group of forked subtasks as a single unit of work with one cancellation/error-propagation boundary instead of manually tracked `Future`s — but it is *still a preview API after six rounds*, which is itself a signal: the API shape has changed release to release, and shipping production code against a preview feature means accepting it may change again before finalization. Scoped Values (JEP 506) finalized in Java 25 specifically to give virtual threads a ThreadLocal alternative that doesn't have ThreadLocal's per-thread-allocation cost at millions-of-threads scale and that composes correctly with structured concurrency's child-task inheritance model — expect ThreadLocal-heavy libraries (logging MDC, security context propagation) to migrate to Scoped Values over the next several LTS cycles, though this is a multi-year migration, not a fast one, because so much of the ecosystem (Spring Security's `SecurityContextHolder`, most APM agents) is built on ThreadLocal today. More speculatively: as virtual threads mature past their pinning issues, expect the "should this be reactive or virtual-thread blocking" decision to keep tilting toward virtual threads for anything that isn't in the top percentile of raw-throughput requirements, simply because the code is easier to write, debug, and onboard engineers into — but treat that as a trend, not a settled consensus; teams running Netty/Reactor at genuine scale are not ripping it out.

---

## Mental model

```
DATA MODELING (compiler-enforced correctness):

  record Point(int x, int y) {}
    -> constructor + accessors x()/y() + equals/hashCode/toString, ALL final fields

  sealed interface Shape permits Circle, Square, Triangle {}
    -> the compiler KNOWS this is the complete set. No 4th implementor, ever,
       outside this permits clause (or same module without permits).

  switch (shape) {                          // EXHAUSTIVE — won't compile if a
    case Circle c -> ...                    // permitted subtype is missing a case,
    case Square s -> ...                    // no `default` needed once every
    case Triangle t -> ...                  // permitted type is covered
  }

CONCURRENCY (cheap threads, not free threads):

  PLATFORM THREAD                    VIRTUAL THREAD
  1:1 with an OS thread              M:N — many virtual threads share few
  ~1MB stack reserved                "carrier" platform threads (commonly
  OS scheduler context-switches it   #carriers ≈ #CPU cores by default)
  thousands = scheduler thrash       millions fit in memory; JVM schedules

  MOUNT:   virtual thread runs ON a carrier thread while actively executing
  UNMOUNT: on a blocking call (I/O), the virtual thread detaches from its
           carrier — carrier is FREE to run a different virtual thread
  PIN:     some blocking operations (synchronized block pre-JDK24, native/
           JNI calls) can't unmount -- the carrier is stuck too, and if all
           carriers are pinned, EVERY virtual thread on this JVM stalls
```

The throughline for both halves: the compiler and the runtime take over bookkeeping that used to be the programmer's job by convention — exhaustiveness for data, and thread lifecycle for concurrency — and both only pay off if you understand the mechanism well enough to know where the abstraction leaks (an unsealed hierarchy someone widens later; a `synchronized` block someone adds inside a hot virtual-thread path).

---

## How it actually works

### Records: what you get and what you give up

```java
public record Point(int x, int y) {
    // compact constructor: validation runs BEFORE field assignment
    public Point {
        if (x < 0 || y < 0) throw new IllegalArgumentException("negative coordinate");
    }
    // you CAN add methods, static factories, additional (non-canonical) constructors
    public double distanceTo(Point other) {
        return Math.hypot(x - other.x, y - other.y);
    }
}
```

Every field is implicitly `private final`. There is no way to add a mutable field to a record — if you need mutable state, a record is the wrong tool, full stop; that's a design signal, not a limitation to work around. `equals`/`hashCode` are generated from *all* components; if two records differ only in a field you don't want compared, records are the wrong choice — don't override `equals` to special-case fields out, because deserialization and reflection-based tooling (Jackson, JPA) generally assume record equality means "same value," not "same value except this one field." Records can implement interfaces and can be part of a sealed hierarchy — `record Circle(double radius) implements Shape` is the standard pattern.

### Sealed types: exhaustiveness the compiler actually checks

```java
public sealed interface Shape permits Circle, Square, Triangle {}
public record Circle(double radius) implements Shape {}
public record Square(double side) implements Shape {}
public record Triangle(double base, double height) implements Shape {}
```

`permits` is optional if every permitted subtype is in the same source file (then the compiler infers the list). The critical property: this is checked **at compile time**, not runtime — a `switch` over `Shape` that omits `Triangle` fails to compile with "the switch statement does not cover all possible input values," not a runtime `MatchException`. This is the actual payoff versus the old convention-based "closed hierarchy": someone adding a fourth `Shape` implementor breaks the build everywhere it's switched over, forcing every dispatch site to be updated, rather than silently falling through to a `default` branch nobody remembers to fill in correctly.

### Pattern matching for switch and record deconstruction

```java
static double area(Shape shape) {
    return switch (shape) {
        case Circle c -> Math.PI * c.radius() * c.radius();
        case Square s -> s.side() * s.side();
        case Triangle(double base, double height) -> 0.5 * base * height;  // record deconstruction
        // no default needed — Shape is sealed and every permitted type is covered
    };
}

// guarded patterns: `when` clause narrows within a case
static String classify(Shape shape) {
    return switch (shape) {
        case Circle c when c.radius() > 100 -> "huge circle";
        case Circle c -> "circle";
        case Square s when s.side() == 0 -> "degenerate square";
        default -> "other";
    };
}
```

Record deconstruction (`case Triangle(double base, double height)`) binds the record's components directly as local variables in that branch — no `.base()`/`.height()` accessor calls needed. Nested deconstruction works too (`case Pair(Circle(double r), Square s)`), which is the mechanism that makes Java's pattern matching genuinely comparable to Rust/Kotlin/Scala destructuring rather than a shallow `instanceof` replacement.

### Virtual threads: mount, unmount, pin

A virtual thread is a `java.lang.Thread` object scheduled by the JVM (a `ForkJoinPool` in FIFO mode by default) onto a small pool of **carrier** platform threads, not by the OS. The core mechanism:

```java
try (var executor = Executors.newVirtualThreadPerTaskExecutor()) {
    List<Future<String>> results = urls.stream()
        .map(url -> executor.submit(() -> httpClient.send(url)))  // one virtual thread per call
        .toList();
    for (var f : results) System.out.println(f.get());
}
```

Each `submit` call spawns a new virtual thread — this is idiomatic; virtual threads are meant to be cheap enough to create one per task or even per request, not pooled and reused like platform threads. When that virtual thread hits a blocking call recognized by the JDK's virtual-thread-aware I/O (network sockets, `java.io`/`java.nio` blocking calls, `java.util.concurrent` locks), the JVM **unmounts** it from its carrier — the carrier platform thread is freed to run a different virtual thread while this one waits. When the I/O completes, the virtual thread is rescheduled onto *some* carrier (not necessarily the same one) and resumes. This is why you can have 100,000 virtual threads blocked on network calls sharing, say, 8 carrier threads (roughly one per core by default): only the virtual threads actually doing CPU work at any instant need a carrier.

**Pinning** is when a virtual thread *cannot* unmount despite blocking. Two causes:

1. **A `synchronized` block or method** — pre-JDK 24, entering `synchronized` while blocking inside it pinned the virtual thread to its carrier for the block's duration, because the JVM's monitor implementation was tied to the OS thread. **JDK 24 (JEP 491, "Synchronize Virtual Threads without Pinning") fixed this specific case** — it's the single most impactful pinning fix, because `synchronized` is everywhere in legacy code and libraries (older JDBC drivers, `java.util.logging`, plenty of Spring internals) that nobody's rewriting for virtual threads.
2. **Native method / foreign function calls (JNI, Foreign Function & Memory API)** — still pins in JDK 25, and this is unlikely to ever fully go away, because the JVM has no visibility into what a native call is doing.

The observable production symptom: throughput plateaus or falls off despite plenty of idle carrier threads reported elsewhere, and `jcmd <pid> Thread.dump_to_file` (or the JFR `jdk.VirtualThreadPinned` event, since JDK 21) shows virtual threads stuck in a pinned state far longer than their actual blocking call should take, because they're queued waiting for a carrier that other pinned virtual threads are hogging.

### Scoped Values: the ThreadLocal replacement

```java
static final ScopedValue<RequestContext> CTX = ScopedValue.newInstance();

void handleRequest(RequestContext ctx) {
    ScopedValue.where(CTX, ctx).run(() -> {
        processOrder();       // CTX.get() is visible here and in every call this makes,
    });                        // including child virtual threads forked in this scope
    // CTX is automatically unbound here — no leak, no cleanup code needed
}
```

`ScopedValue` (finalized JEP 506, Java 25) is immutable for the duration of the bound scope and is automatically unbound when `run`/`call` returns — this is the key difference from `ThreadLocal`, which requires manual `remove()` in a `finally` block or you leak state into the next task that reuses the same platform thread from a pool. At virtual-thread scale (millions of short-lived threads), `ThreadLocal`'s per-thread allocation cost and leak risk become a real problem — every new virtual thread that touches a `ThreadLocal.set()` pays an allocation, and with millions of virtual threads spun up per second in a busy service, that adds up in ways it never did with a bounded pool of a few hundred platform threads. Scoped Values also integrate with Structured Concurrency's child-task model: values bound in a parent scope are visible to forked child tasks without re-propagating them manually.

### Structured Concurrency (still preview — know the boundary)

```java
// PREVIEW API (JEP 505, 6th preview in JDK 25) — requires --enable-preview
try (var scope = StructuredTaskScope.open(Joiner.<String>allSuccessfulOrThrow())) {
    Subtask<String> user = scope.fork(() -> fetchUser(id));
    Subtask<String> orders = scope.fork(() -> fetchOrders(id));
    scope.join();                       // waits for both; on either failure, cancels the other
    return render(user.get(), orders.get());
}
```

The point: fork two subtasks, treat them as one unit — if either fails, the scope cancels the sibling and propagates the failure, instead of leaking an orphaned `Future` that keeps running after its result is no longer needed (a real bug class with manual `ExecutorService` + `Future` code, where a timeout on the parent doesn't actually stop the child task's work). Say out loud in an interview that this is *preview*, not finalized — claiming otherwise is a specific, checkable mistake.

---

## Build it from scratch

A minimal comparison worth being able to sketch: fan-out I/O with a bounded platform-thread pool versus virtual threads, to make the throughput/memory tradeoff concrete.

```java
// untested sketch — platform-thread pool: bounded concurrency, real memory cost per thread
ExecutorService pool = Executors.newFixedThreadPool(200);   // ~200MB+ just in reserved stacks
List<Future<String>> results = ids.stream()
    .map(id -> pool.submit(() -> callDownstream(id)))       // blocks a pooled thread per call
    .toList();

// untested sketch — virtual threads: one per task, no pooling needed
try (var vExec = Executors.newVirtualThreadPerTaskExecutor()) {
    List<Future<String>> results = ids.stream()
        .map(id -> vExec.submit(() -> callDownstream(id)))  // unmounts while blocked on I/O
        .toList();
}
```

With 10,000 `ids` and a downstream call taking 100ms, the pooled version is capped at `200 concurrent / 100ms ≈ 2,000 req/s` regardless of how fast the downstream actually is, and every one of those 200 threads holds its stack for the pool's lifetime. The virtual-thread version can have all 10,000 in flight simultaneously (bounded only by the downstream's own capacity and the carrier pool doing the actual scheduling work), each virtual thread costing roughly a few hundred bytes to a few KB of retained state while parked, not a megabyte-class stack. A lab measuring this directly — thread count vs memory (`jcmd <pid> GC.heap_info`) vs achieved throughput under `wrk`/a load generator — belongs in `labs/java/01-java-modern/`.

---

## How it's done in production

| Symptom | Cause | Fix |
|---|---|---|
| Virtual-thread service throughput plateaus well below expectation; carrier threads show idle time in monitoring but latency is high | Pinning — a `synchronized` block (pre-JDK 24) or native/JNI call blocking inside a hot virtual-thread path | Upgrade to JDK 24+ to eliminate the `synchronized`-block pinning case; for native calls, isolate them behind a bounded platform-thread pool instead of running them on virtual threads directly |
| `OutOfMemoryError` or severe GC pressure after migrating a caching layer to virtual threads | `ThreadLocal` used for per-request caching; millions of short-lived virtual threads each allocate their own `ThreadLocal` slot | Migrate to `ScopedValue` (Java 25+), which is bound for a scope's duration and auto-unbinds, or move the cache off thread-affinity entirely |
| A `switch` over a sealed type that compiled fine breaks the build after adding a new implementor | This is the *intended* behavior — the compiler is telling you every dispatch site needs updating | Add the missing case at each break; this is the payoff of sealed types, not a bug to route around with `default` |
| Record-based DTO fails Jackson deserialization silently (fields become default values) | Records require Jackson `jackson-module-parameter-names` or `@JsonCreator` awareness for the canonical constructor, especially on older Jackson versions | Confirm the Jackson version has native record support (2.12+ with the parameter-names module, better in 2.15+), or annotate the canonical constructor explicitly |
| Deep recursion in `equals`/`hashCode` on nested records causes `StackOverflowError` on large object graphs | Records auto-generate structural equality that recurses through every nested record component | For deeply nested or cyclic structures, records may be the wrong tool — consider identity-based equality via a wrapping class, or flatten the structure |
| Structured Concurrency code compiled against an earlier JDK 21-23 preview API fails to compile on JDK 25 | The preview API shape changed between preview rounds (5th to 6th preview) | Expected cost of building on a preview API — pin your JDK minor version if you must use it pre-finalization, and budget for a migration pass when it finalizes |

---

## Tradeoffs & when NOT to use it

- **Don't use virtual threads for CPU-bound work.** They solve blocking-I/O thread scalability specifically; a CPU-bound task still occupies its carrier thread for its full duration exactly like a platform thread would, so spinning up a million virtual threads doing matrix multiplication gets you a million threads contending for the same handful of CPU cores, with none of the benefit and extra scheduling overhead on top.
- **Don't put `synchronized` blocks in hot virtual-thread paths on JDK <24.** If you're not yet on JDK 24+, audit for `synchronized` (including inherited from libraries — JDBC drivers, older logging frameworks) before committing to virtual threads at scale; the pinning cost can silently erase the entire throughput win.
- **Don't reach for records when you need mutability or identity semantics.** A record is a value type by design — no mutable fields, structural equality. Entity classes with a lifecycle (a JPA-managed entity that's genuinely mutable and identity-compared) are the wrong fit; forcing them into records to look "modern" produces subtle correctness bugs.
- **Don't ship Structured Concurrency in code you can't afford to revisit.** It's a preview API after six rounds in JDK 25 — say this plainly if asked, and treat any production use as accepting a migration cost when it finalizes.
- **Don't assume virtual threads beat reactive/Netty at every throughput tier.** Current benchmarks (2025-2026) still show pure reactive stacks ahead by roughly 25-30% at the very top end of raw RPS on some workloads — virtual threads are the right default for *most* new I/O-bound services because the code is dramatically easier to write and debug, not because they're unconditionally faster.
- **Don't widen a sealed hierarchy just to avoid touching call sites.** If you find yourself wanting to add `default ->` to every switch over a sealed type "to be safe," you've defeated the entire point of sealing it — that's a design smell worth naming in code review, not a convenience.

---

## Interview questions

### Q1 — What problem do virtual threads actually solve, and what do they not solve?
**Testing:** whether virtual threads are understood as a targeted fix, not a general performance upgrade.
**Answer:** They solve thread-per-request scalability for I/O-bound work — letting you write plain blocking, sequential code and still handle very high concurrency, because a virtual thread unmounts from its carrier platform thread while blocked on I/O instead of occupying an OS thread's ~1MB stack and scheduler slot for the whole wait. They do nothing for CPU-bound work — a CPU-bound virtual thread occupies its carrier for its full duration exactly like a platform thread would, so more virtual threads doing compute just contends harder for the same core count.
**Follow-up trap:** *"So should I replace my thread pool used for image processing with virtual threads?"* — no; that's CPU-bound, and virtual threads add scheduling overhead there without buying anything. Keep a bounded platform-thread (or `ForkJoinPool`-based parallel stream) pool sized to core count for CPU-bound work.

### Q2 — Explain virtual thread pinning: when does it happen, and what's the observable symptom?
**Testing:** mechanistic understanding versus name-recognition.
**Answer:** Pinning happens when a virtual thread blocks but cannot unmount from its carrier — historically inside a `synchronized` block/method, or during a native/JNI call. A pinned virtual thread keeps its carrier occupied for the whole block, so if enough virtual threads pin simultaneously, you can exhaust the carrier pool (commonly sized near CPU core count) and stall virtual threads that aren't even pinned themselves, just waiting for a free carrier. Symptom: throughput far below expectation with carriers reported idle in higher-level metrics but requests queuing, visible directly via the `jdk.VirtualThreadPinned` JFR event.
**Follow-up trap:** *"You're on JDK 25 — is the synchronized case still a risk?"* — no, JEP 491 (JDK 24) fixed the `synchronized`-block pinning case specifically, which was the most common one from legacy libraries. Native/JNI calls still pin on JDK 25 and are unlikely to ever be fully fixed, since the JVM can't see inside native code.

### Q3 — Why does the compiler reject a `switch` over a sealed type that's missing a case, and what did people do before this existed?
**Testing:** whether exhaustiveness is understood as a compile-time guarantee, not a style convention.
**Answer:** A `sealed` type declares its complete, closed set of permitted implementors (`permits X, Y, Z`), checked and enforced at compile time — nothing outside that set can implement it (barring same-file/module inference cases). A `switch` over that type can therefore be verified exhaustive by the compiler: every permitted case must be present or the build fails, with no `default` required once all cases are covered. Before this, closed hierarchies were convention-only (a `private` constructor and a comment), and exhaustive dispatch meant `instanceof`-cast chains or the Visitor pattern, neither of which the compiler checked — adding a new subtype silently fell through to whatever `default`/`else` branch existed, or worse, an unhandled case.
**Follow-up trap:** *"What happens if I add `default ->` to that switch anyway?"* — you silently reopen the hole: a future fourth implementor now falls into `default` instead of failing the build, defeating the reason to seal the hierarchy in the first place. Leave it exhaustive; that's the entire value proposition.

### Q4 — Records auto-generate `equals`/`hashCode`/`toString` from every component. Where does that bite you?
**Testing:** whether "records are just less boilerplate" is understood with its real edge cases.
**Answer:** Two places: first, deep/nested record graphs recurse through every component for equality and hashing, which is correct but can be a real cost (or even `StackOverflowError` risk on cyclic/very deep structures) that a hand-written `equals` might have avoided by using identity or a subset of fields. Second, you cannot special-case a field out of equality without breaking the "records are pure value types" contract that deserialization and ORM tooling assumes — if you need a field excluded from equality, that's a signal the type shouldn't be a record, not a signal to override `equals`.
**Follow-up trap:** *"Can you add a mutable field to a record for caching a derived value?"* — no, every component is implicitly `final`; a record literally cannot have a mutable field. If you want a lazily computed, cached derived value, you compute it outside the record (a separate cache keyed by the record's value, since records are structurally comparable and hashable) rather than trying to add mutable state inside it.

### Q5 — Compare `ThreadLocal` and `ScopedValue` for propagating request context. Why does virtual-thread scale specifically motivate the change?
**Testing:** whether the JDK's own migration story is understood, not just the syntax difference.
**Answer:** `ThreadLocal` requires manual `set`/`remove` discipline — forget `remove()` in a `finally` and, with pooled platform threads, you leak state into whatever task runs next on that reused thread. `ScopedValue` is bound only for the duration of a `run`/`call` block and automatically unbinds when it returns — no leak risk by construction. At virtual-thread scale specifically, millions of short-lived virtual threads each touching a `ThreadLocal.set()` means millions of per-thread allocations, a real, measurable cost that didn't matter with a few hundred long-lived pooled platform threads; `ScopedValue` avoids that per-thread-instance allocation pattern and also composes cleanly with Structured Concurrency's child-task inheritance, where forked subtasks see the parent's bound values automatically.
**Follow-up trap:** *"Is ScopedValue a drop-in replacement for every ThreadLocal use case?"* — no; ScopedValue is immutable within its scope by design, so any use case that genuinely needs a thread-local *mutable* cell (rather than propagated immutable context) doesn't map onto it. Most request-context/MDC-style propagation does map cleanly; some caching patterns don't.

### Q6 — Design an I/O-heavy service: virtual threads with blocking clients, or Reactor/Netty fully reactive? Walk through the decision.
**Testing:** staff-level judgment on a genuinely live 2026 disagreement, not a reflexive "virtual threads always win" answer.
**Answer:** Default to virtual threads with blocking-style clients (blocking JDBC, `RestClient`, blocking `WebClient` calls) for the large majority of I/O-bound services — the code is plain, sequential, debuggable with normal stack traces, and onboarding is trivial compared to reactive's operator-chain style. Reach for full reactive/Netty specifically when the measured requirement is at the very top of the throughput tier, where current benchmarks still show a real gap (cited figures put pure reactive Netty around 200K RPS versus roughly 140-150K RPS for virtual-thread-based stacks on comparable hardware) — and even then, only after confirming the workload is genuinely throughput-bound rather than the team defaulting to reactive out of habit or resume-driven development.
**Follow-up trap:** *"Your load test shows virtual threads 25% slower than your team's existing Reactor codebase — do you migrate back?"* — not automatically; ask whether that 25% is actually the bottleneck given the service's real traffic and SLOs, and weigh it against the ongoing cost of onboarding engineers into reactive debugging. A 25% throughput gap that never gets exercised in production isn't worth the maintainability cost; a 25% gap on a service running at capacity limits is a real reason to stay reactive.

### Q7 — What's the difference between Structured Concurrency and just using an `ExecutorService` with `Future.get()` in a loop?
**Testing:** whether the actual bug class Structured Concurrency fixes is understood.
**Answer:** Manual `Future`-based fan-out has no enforced relationship between the parent task and the children it spawned — if the parent times out or the caller stops caring, nothing automatically cancels the still-running child tasks, so they keep consuming resources (a connection, a CPU-bound loop) for work whose result will never be used, a real and common leak. Structured Concurrency's `StructuredTaskScope` ties subtask lifetimes to the enclosing scope: exiting the `try`-with-resources block (normally, by exception, or by a joiner deciding to fail-fast) cancels any subtasks still running, so "the parent is done" and "the children are done" can't drift apart.
**Follow-up trap:** *"Is this safe to ship in production today?"* — it's a preview API in JDK 25 (JEP 505, sixth preview) — say this plainly. Shipping it means accepting the API surface may still change before finalization; some teams do this deliberately behind `--enable-preview` for internal services, but it's a stated risk, not a default recommendation.

### Q8 — A colleague says "virtual threads make thread pools obsolete." Do you agree?
**Testing:** whether the CPU-bound/I/O-bound distinction is applied correctly under a leading, slightly wrong prompt.
**Answer:** Partially — obsolete for the specific pattern of pooling platform threads to bound concurrent *I/O-bound* work, since virtual threads make "one thread per task, no pooling" both correct and cheap for that case. Not obsolete for CPU-bound work, where you still want a bounded pool sized near core count (a `ForkJoinPool` or fixed platform-thread pool) because more concurrent threads than cores doesn't create more compute capacity, just more contention and context-switch overhead. Also not obsolete as a rate-limiting/backpressure mechanism — a "virtual thread per task with no bound at all" can still overwhelm a downstream dependency or exhaust carrier-adjacent resources (DB connection pool size doesn't change just because the thread model did), so you often still want a `Semaphore` or bulkhead-style limiter even with virtual threads.
**Follow-up trap:** *"So what bounds concurrency if not the thread pool size?"* — the downstream's actual capacity (DB connection pool, external API rate limit) — with virtual threads, the thread count is no longer the natural throttle it used to be, so you have to add explicit backpressure (a semaphore, a bulkhead — see `T11-resilience4j`) where a small platform-thread pool used to provide it as an accidental side effect.

### Q9 — Walk through what a `record` compiles down to, and why that matters for a library doing reflection or bytecode manipulation.
**Testing:** one level below the syntax — whether the runtime representation is understood.
**Answer:** A record compiles to a final class extending `java.lang.Record`, with private final fields for each component, a canonical constructor, accessor methods matching the component names (not `getX()` — just `x()`), and compiler-synthesized `equals`/`hashCode`/`toString` using an `invokedynamic`-based bootstrap (`ObjectMethods`) rather than naively generated bytecode per method, which keeps generated code compact. Reflection-based libraries (older Jackson, some ORMs, ASM-based tooling) written before records existed often assumed JavaBean-style `getX()` accessors and needed explicit record support added — this is why "does my serialization library actually support records natively, or does it silently fail on them" is a real, checkable production question, not a hypothetical.
**Follow-up trap:** *"Does a record support inheritance?"* — a record can implement interfaces (including being part of a sealed hierarchy) but cannot extend another class (all records implicitly extend `java.lang.Record`) and cannot itself be extended (implicitly final). This is deliberate — records are meant to be leaf value types, not a base for further subclassing.

### Q10 — Your team profiles a virtual-thread-based service and finds carrier threads spending significant time in `synchronized`. What do you check first?
**Testing:** practical incident-response instinct on the single most common real virtual-thread production issue.
**Answer:** First, the JDK version — if it's pre-24, this is almost certainly the known `synchronized`-block pinning issue, and the fastest fix is upgrading to JDK 24+ where JEP 491 removed that pinning case entirely. If already on JDK 24+, check for native/JNI calls inside the `synchronized` block instead, since that pinning case is unfixed regardless of JDK version, and the fix there is isolating the native call behind a small dedicated platform-thread pool rather than running it inline on a virtual thread.
**Follow-up trap:** *"The JDK is 25 and there's no native code — what else could cause it?"* — check whether the `synchronized` block itself is doing something CPU-heavy or lock-contended rather than actually blocking — pinning specifically describes the unmount failure during a *blocking* operation; a `synchronized` block that's simply CPU-bound and lock-contended is a normal concurrency bottleneck unrelated to virtual threads at all, and the fix is standard lock-contention reduction (smaller critical sections, finer-grained locks), not a virtual-thread-specific one.

### Q11 — When is Java 21 the right LTS target over Java 25, given both are LTS?
**Testing:** whether "always use the latest LTS" is a reflex or a considered call.
**Answer:** Java 21 (September 2023) is the right target when the ecosystem you depend on (a specific application server, a legacy framework version, an enterprise vendor's supported-JDK matrix) hasn't certified Java 25 yet, or when you specifically need to avoid the synchronized-pinning-fixed-in-24 behavior change because some code relies on the old pinning-as-a-side-effect serialization (rare, but real in code that accidentally used pinning as an implicit lock). Otherwise Java 25 is the better default for new services: it has three additional years of JIT/GC improvements, the Scoped Values finalization, and the synchronized-pinning fix baked in, all with the same LTS support commitment.
**Follow-up trap:** *"What's Java 25's actual support timeline versus 21's?"* — both are LTS releases with long support windows from Oracle/the OpenJDK ecosystem (typically multi-year, vendor-dependent); the honest answer if you don't have the exact end-of-support date memorized is to say you'd check the specific vendor's (Oracle, Adoptium/Temurin, Amazon Corretto) published support matrix rather than guess a number, since it varies by distribution.

---

## Red flags that fail you

- Claiming virtual threads improve CPU-bound throughput.
- Describing pinning as fixed in general, without knowing the `synchronized`-block fix landed specifically in JDK 24 (JEP 491) and that native/JNI pinning is still unfixed.
- Claiming Structured Concurrency is a finalized, stable API in JDK 25.
- Adding `default ->` to an exhaustive switch over a sealed type "to be safe" and not recognizing that defeats the point of sealing it.
- Trying to add a mutable field to a record, or overriding `equals` to exclude a component instead of reconsidering whether the type should be a record at all.
- Recommending pooled `ThreadLocal`-per-virtual-thread caching without mentioning the allocation cost at scale or the `ScopedValue` alternative.
- Treating "virtual threads vs reactive" as a settled, one-sided question instead of naming the real 2025-2026 benchmark gap.

---

## Cheat card

```
RECORDS (JEP 395, Java 16): all fields implicit private final; auto equals/hashCode/
  toString from ALL components; compact constructor validates before assignment;
  cannot add mutable fields; cannot extend a class; implicitly final (no subclassing)

SEALED (JEP 409, Java 17): `sealed ... permits A,B,C` — compiler-enforced closed set,
  not convention. permits inferred if all subtypes in same file.

PATTERN MATCHING SWITCH (JEP 441, Java 21) + RECORD PATTERNS (JEP 440, Java 21):
  switch over a sealed type is EXHAUSTIVE — won't compile if a permitted case
  is missing, no default needed. `case Triangle(double b, double h) ->` destructures
  directly. `when` clause = guarded pattern, narrows within a case.

VIRTUAL THREADS (JEP 444, Java 21, finalized Sept 2023):
  M:N — many virtual threads share few "carrier" platform threads (~= core count)
  MOUNT while running; UNMOUNT while blocked on recognized I/O -- carrier freed
  PIN = can't unmount: synchronized block (FIXED in JDK 24, JEP 491) or
        native/JNI call (still pins on JDK 25)
  fixes: I/O-bound thread-per-request scalability. fixes NOTHING for CPU-bound.
  jdk.VirtualThreadPinned JFR event / jcmd Thread.dump_to_file to diagnose

SCOPED VALUES (JEP 506, FINALIZED Java 25): immutable per-scope, auto-unbind on
  scope exit (no leak by construction, unlike ThreadLocal's manual remove()).
  Built for VT scale: avoids per-thread ThreadLocal allocation at millions of
  short-lived threads. Composes with Structured Concurrency child-task inheritance.

STRUCTURED CONCURRENCY (JEP 505): STILL PREVIEW in Java 25 (6th preview round).
  StructuredTaskScope ties subtask lifetime to parent scope — exit cancels
  still-running children. Do NOT claim this is finalized/stable.

BENCHMARKS (2025-2026, workload-dependent): pure reactive Netty ~200K RPS >
  VT-on-Netty ~150K RPS ≈ VT-on-Tomcat ~140K RPS >> bounded platform-thread
  pool ~5K RPS. Default to virtual threads; reach for reactive only at the
  genuine top throughput tier after measuring, not by habit.

JDK 25 = current LTS, released Sept 16 2025. JDK 21 = prior LTS, Sept 2023.
```

## Sources

- [JEP 505: Structured Concurrency (Sixth Preview)](https://openjdk.org/jeps/505) — accessed 2026-08-03
- [JDK 25 project page — OpenJDK](https://openjdk.org/projects/jdk/25/) — accessed 2026-08-03
- [What's New With Java 25 — JRebel](https://www.jrebel.com/blog/java-25) — accessed 2026-08-03
- [Virtual Threads Two Years In: Production War Stories, the Pinning Edge Cases, and What JDK 25 Fixed — Java Code Geeks](https://www.javacodegeeks.com/2026/05/virtual-threads-two-years-in-production-war-stories-the-pinning-edge-cases-and-what-jdk-25-fixed.html) — accessed 2026-08-03
- [Java Virtual Threads: The Pinning Problem, the Deadlock, and the Fix in Java 24](https://shbhmrzd.github.io/java/concurrency/virtual-threads/2026/04/25/java-virtual-threads-pinning-and-the-deadlock-problem.html) — accessed 2026-08-03
- [Structured Concurrency and Scoped Values in Java — SoftwareMill](https://softwaremill.com/structured-concurrency-and-scoped-values-in-java/) — accessed 2026-08-03
- [Modern Java Language Features: Records, Sealed Classes, Pattern Matching — Java Code Geeks](https://www.javacodegeeks.com/2025/12/modern-java-language-features-records-sealed-classes-pattern-matching.html) — accessed 2026-08-03
- [loom-webflux-benchmarks — GitHub](https://github.com/chrisgleissner/loom-webflux-benchmarks) — accessed 2026-08-03

## Changelog
- 2026-08-03 — created
