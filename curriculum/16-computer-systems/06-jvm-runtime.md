# JVM: Class Loading, C1/C2 JIT, Escape Analysis, GC Algorithms

> **Track:** T16 Computer Systems: Transistor → Runtime · **Time:** 2.0h · **Prereqs:** T16-compilers · **Updated:** 2026-08-03
> **Module id:** `T16-jvm-runtime` · **Tags:** runtime

## The 30-second version

The JVM loads classes lazily through a delegating hierarchy of classloaders (bootstrap → platform → application, each asking its parent first before trying itself), verifies bytecode for type/stack safety before ever running it, and executes new code through a tiered pipeline: the interpreter runs everything cold, C1 (client compiler) kicks in fast with light optimization once a method gets warm, and C2 (server compiler) recompiles genuinely hot methods with aggressive optimizations — most importantly escape analysis, which proves an object never escapes its allocating method/thread and can therefore be stack-allocated (or its fields scalar-replaced into registers) instead of heap-allocated, eliminating both the allocation and its eventual GC cost entirely. Garbage collection has moved from stop-the-world mark-sweep-compact toward algorithms that trade a small amount of throughput for dramatically lower pause times: G1 (the default since Java 9) divides the heap into regions and collects the highest-garbage regions first, targeting configurable pause goals in the tens of milliseconds; ZGC, now fully generational and the default/only ZGC implementation as of Java 25 LTS, achieves sub-millisecond pauses (typically 0.1-0.5ms) regardless of heap size — even multi-terabyte heaps — by doing almost all of its work concurrently with the running application, at the cost of roughly 15-30% more memory (no compressed object pointers) and typically 5-15% lower throughput than G1 for many workloads. The practical decision in 2026 is straightforward: G1 remains the right default for most services (predictable, well-understood, resource-efficient), and generational ZGC is the right call specifically for latency-sensitive services on large heaps where sub-millisecond pause guarantees matter more than the memory/throughput cost.

## Why this gets asked

Because JVM tuning is one of the few areas where a wrong default genuinely produces a production incident (a G1 humongous-object stall, a full GC pause taking seconds on a multi-GB heap, a classloader leak from a dynamically-reloaded webapp), and the interviewer wants to know whether you've actually read a GC log or `jstat` output under pressure versus memorized "G1 is the default GC." It's also a direct test of whether tiered compilation and escape analysis — concepts that generalize to essentially every modern managed runtime, including V8 and CPython's newer JIT work — are understood mechanically rather than as buzzwords, since "the JVM is fast because of the JIT" without knowing *what* the JIT actually does is a shallow answer that doesn't survive a follow-up.

---

## Lineage: past → present → future

**What came before.** Early JVMs (mid-1990s) were pure interpreters — every bytecode instruction dispatched and executed with no compilation at all — which made "write once, run anywhere" genuinely portable but left Java meaningfully slower than natively compiled C/C++ for CPU-bound work, a real and widely cited criticism through the late 1990s. Early garbage collection was similarly simple: stop-the-world mark-sweep(-compact) across the entire heap, which is straightforward to implement correctly but means GC pause time scales with live heap size — as heaps grew from megabytes to gigabytes (and eventually terabytes) through the 2000s-2010s, full-heap stop-the-world pauses stopped being an acceptable cost for latency-sensitive services, becoming multi-second events on large heaps.

**Where it stands now.** HotSpot's tiered JIT compilation (interpreter → C1 → C2, formalized as "tiered compilation" and the default since Java 7u4) balances warmup speed against peak throughput by using increasingly aggressive, increasingly expensive-to-produce compiled code only as a method proves itself hot through actual invocation counts. On the GC side, G1 (default since Java 9, itself building on ideas from earlier incremental/regional collectors) remains the widely deployed default because it's throughput-competitive and well-understood; fully generational ZGC (default and only ZGC form as of Java 25 LTS, released 2025) represents the industry's clearest current answer to "how low can pause times go without giving up too much throughput," achieving consistent sub-millisecond pauses independent of heap size by doing marking, relocation, and remapping almost entirely concurrently with application threads using colored pointers and load barriers rather than traditional stop-the-world phases. Shenandoah (RedHat's comparable low-pause collector) occupies similar territory with different internal mechanics, and the live disagreement in 2026 is genuinely workload-dependent rather than settled: G1 for most general-purpose services, generational ZGC specifically for large-heap, latency-sensitive workloads willing to pay the memory/throughput cost.

**Where it's heading.** Project Leyden (an active, real OpenJDK project, not speculative) targets faster startup and reduced warmup by shifting more work ahead-of-time — class-data sharing, ahead-of-time-linked/initialized classes, and eventually broader ahead-of-time compilation — specifically to address the JVM's historically weak cold-start/serverless story relative to natively compiled languages, a real and actively shipping direction rather than a promise. More speculative: how far generational ZGC-style concurrent, pause-minimizing collection becomes the default for general-purpose workloads (rather than an opt-in for latency-sensitive services specifically) depends on closing more of its throughput/memory gap with G1, which is ongoing engineering work without a committed timeline for "ZGC becomes the default default."

---

## Mental model

Picture the JVM as a three-stage refinery for both code and objects: code gets progressively recompiled as it proves itself hot, and objects get progressively promoted (or eliminated) based on how long they actually live:

```
CODE PATH:                                OBJECT/GC PATH:
bytecode                                  new Foo()
   |  interpreter (every method, cold)        |  escape analysis: does it escape
   v                                          v  the allocating method/thread?
  warm? (invocation count threshold)        NO -> stack-allocate / scalar-replace
   |  C1 (fast compile, light opt)            (never touches the heap or GC at all)
   v                                          |
  hot? (further threshold, C1-profiled)      YES -> heap-allocate in young gen (Eden)
   |  C2 (slow compile, aggressive opt,        |  survives a minor GC?
   |     inlining + escape analysis +          v
   |     speculative optimizations)          promoted to old gen
   v                                          |  old gen fills up / ZGC's concurrent
  machine code, deoptimizes back to           v  cycle triggers
  interpreter if an assumption breaks        major/full GC (or ZGC's always-concurrent cycle)
```

---

## How it actually works

### Class loading

Classes load lazily (on first active use, not eagerly at JVM startup) through a **parent-delegation hierarchy**: the bootstrap classloader (loads core `java.*` classes, implemented in native code, no Java-level parent) → the platform classloader (loads JDK-internal/extension classes) → the application classloader (loads your application's classpath). Each classloader, before attempting to load a class itself, delegates the request to its parent first — this delegation model exists specifically to prevent a malicious or accidental application-level class from shadowing a core JDK class of the same fully-qualified name (imagine an attacker shipping their own `java.lang.String` — delegation ensures the bootstrap loader's real one always wins for that namespace). Loading itself proceeds through distinct phases: **loading** (reading the `.class` bytes), **linking** (verification — a real, enforced bytecode-level type/stack-safety check that rejects malformed or type-unsafe bytecode before it ever runs, distinct from source-level compiler checks and a genuine security boundary since bytecode can come from anywhere; preparation — allocating static field storage with default values; resolution — replacing symbolic references with direct ones, often lazily), and **initialization** (running static initializers and static field assignments, triggered on first active use — a class can be loaded and linked without yet being initialized, which is exactly why static initialization order bugs can be timing-dependent).

### Interpreter → C1 → C2: tiered compilation

HotSpot runs bytecode in a pure interpreter initially — no compilation latency, immediate execution, but slow per-instruction dispatch, structurally similar to CPython's eval loop covered in the previous module. Every method invocation and backward branch increments counters; once a method crosses an invocation threshold (tunable, in the low thousands by default), it becomes a candidate for **C1** (the "client" compiler): a fast-to-produce, lightly-optimized compilation that still gathers **profiling data** (which branches were taken, which concrete types appeared at polymorphic call sites) as it runs. If a method compiled by C1 continues to run hot, it becomes a candidate for **C2** (the "server" compiler): a slower-to-produce but far more aggressively optimized compilation that uses the profiling data C1 gathered to make speculative optimizations — inlining virtual calls that profiling showed were actually monomorphic (always the same concrete type) or bimodal, unrolling loops, and applying escape analysis (below). This interpreter → C1 → C2 progression ("tiered compilation," the default since Java 7u4) exists specifically to balance two competing costs: pure interpretation has zero compile latency but poor throughput; jumping straight to C2-level optimization for every method would give great throughput eventually but terrible warmup latency, since C2 compilation itself is comparatively slow and expensive to produce — tiering gets a reasonable throughput improvement almost immediately (C1) while reserving the expensive optimization work for methods that have actually proven, through real invocation counts, that they're worth it (C2).

Speculative optimizations can be wrong: if a C2-compiled method's assumption breaks (a call site profiled as monomorphic actually sees a new concrete type, an inlined method's class gets redefined, an array-bounds-check-elimination assumption is violated), the JVM **deoptimizes** — discards the compiled code for that method, falls back to the interpreter for continued execution, and (depending on how the assumption broke) may eventually re-profile and recompile with updated assumptions. This deopt/reopt cycle is architecturally the same pattern as CPython's specializing adaptive interpreter's guard-and-de-specialize behavior and V8's TurboFan deoptimization, covered in the CPython and Go/V8 modules — it's a recurring pattern across essentially every modern managed runtime, not a JVM-specific quirk.

### Escape analysis

Escape analysis is C2's determination of whether an object allocated in a method can be proven to never "escape" — never be referenced by anything outside the allocating method (or, for a weaker but still useful variant, never referenced by anything outside the allocating *thread*). If an object provably doesn't escape its allocating method, the JIT can perform **scalar replacement**: instead of heap-allocating the object at all, its individual fields are treated as separate local variables/register values, entirely eliminating both the allocation and the object's eventual garbage collection cost — a genuinely free win for a category of code (small, short-lived value-like objects created and consumed entirely within one method, extremely common with things like `Optional`, small temporary records, or iterator state) that would otherwise pressure the young generation heavily. If an object escapes the method but provably not the thread, **lock elision** becomes possible: `synchronized` blocks on an object provably thread-local can have their locking entirely removed, since no other thread could ever contend for that lock — a genuinely free elimination of otherwise-real synchronization overhead. Escape analysis is unavailable to the interpreter and even to C1's lighter optimization level in practice — it's specifically a C2-tier optimization, which is one concrete reason why a method's *steady-state* performance (once fully JIT-warmed to C2) can be measurably better than its *early* performance even beyond the raw interpreter-vs-compiled-code gap, and why microbenchmarks that don't warm up the JIT (JMH exists specifically to solve this measurement problem) produce misleading numbers.

### Garbage collection: G1 and ZGC, concretely

**G1 (Garbage-First, default since Java 9)** divides the heap into many fixed-size regions (rather than one contiguous young/old generation) and tracks the live-data ratio per region, prioritizing collection of the regions with the most garbage first (hence "garbage-first") to reclaim the most space for the least work — this is what lets G1 target a configurable pause-time goal (`-XX:MaxGCPauseMillis`, commonly tuned to the tens-of-milliseconds range) rather than guaranteeing a fixed pause, by choosing how many regions to collect in a given pause to stay within budget. G1 still has stop-the-world phases (young collections, and occasionally more expensive mixed/full collections if the pause-time goal can't be met), and one specific, real failure mode is **humongous object allocation**: an object larger than 50% of a region size is allocated specially across contiguous regions, and workloads that frequently allocate such large objects (large byte arrays, big collections) can suffer additional GC pressure and fragmentation specifically from humongous allocation handling — a concrete, quotable G1 gotcha.

**ZGC**, now **fully generational** (Java 25 LTS is the first LTS release where generational ZGC is the sole ZGC implementation — the older single-generation ZGC has been retired), achieves consistent **sub-millisecond pause times (commonly 0.1-0.5ms) regardless of heap size**, including multi-terabyte heaps, by doing nearly all of its work — marking, relocating, and remapping references — **concurrently** with running application threads, using **colored pointers** (metadata bits embedded directly in unused bits of 64-bit object references, tracking an object's GC-relevant state without a separate side table) and **load barriers** (a small check inserted on every reference load that can transparently redirect access to an object mid-relocation, so the application never observes a stale or half-moved reference). The generational split (young/old, added to ZGC more recently, mirroring G1's long-standing generational design) specifically improves ZGC's throughput versus its original single-generation form by collecting the young generation — where most garbage is generated and most objects die quickly, the well-established "weak generational hypothesis" — far more frequently and cheaply than scanning the whole heap every cycle, closing much of ZGC's throughput gap with G1 (from a larger deficit down to roughly 5-15% versus G1 for many workloads as of current generational ZGC). The costs that remain real: ZGC does not support compressed object pointers (a memory-saving technique G1 and other collectors use for heaps under ~32GB), increasing memory consumption by roughly 15-30% versus G1 for comparable workloads, and the concurrent load-barrier mechanism itself has a small, real per-access cost that contributes to ZGC's remaining throughput gap.

---

## Build it from scratch

The most instructive from-scratch exercise here is observing escape analysis and deoptimization directly, since both are otherwise invisible without the right flags:

```java
// untested sketch — compile and run with JIT diagnostics enabled to observe escape analysis
public class EscapeDemo {
    static long sink;  // prevents dead-code elimination of the result

    // a Point that, if EA proves it doesn't escape, gets scalar-replaced (no heap alloc)
    static long distanceSquared(int x1, int y1, int x2, int y2) {
        Point a = new Point(x1, y1);   // candidate for scalar replacement
        Point b = new Point(x2, y2);   // candidate for scalar replacement
        long dx = a.x - b.x, dy = a.y - b.y;
        return dx * dx + dy * dy;
    }

    static class Point { int x, y; Point(int x, int y) { this.x = x; this.y = y; } }

    public static void main(String[] args) {
        for (int i = 0; i < 5_000_000; i++) {   // warm up past C2's threshold
            sink += distanceSquared(i, i + 1, i + 2, i + 3);
        }
        System.out.println(sink);
    }
}
```

```bash
# run with escape-analysis and inlining diagnostics (JDK debug/diagnostic build or
# -XX:+UnlockDiagnosticVMOptions on a standard build):
java -XX:+PrintCompilation -XX:+UnlockDiagnosticVMOptions -XX:+PrintEscapeAnalysis \
     -XX:+PrintEliminateAllocations EscapeDemo
```

The expected observation: early iterations show interpreter/C1-tier compilation events in `-XX:+PrintCompilation` output; once `distanceSquared` crosses the C2 threshold, `-XX:+PrintEliminateAllocations` (on a debug JVM build, or via async-profiler/JFR allocation profiling on a production build) shows the `Point` allocations being eliminated — the point of running this yourself is confirming, with real flags and real output, that "escape analysis eliminates the allocation" isn't just a claim from a slide but an observable compiler decision on a specific method.

---

## How it's done in production

| Symptom | Cause | Fix |
|---|---|---|
| GC log shows occasional multi-second "Full GC" pauses on a G1-tuned service, despite a configured pause-time goal | G1 couldn't meet its pause-time goal with incremental/mixed collections (often from allocation rate outpacing collection, or heap fragmentation from humongous objects) and fell back to a full stop-the-world collection | Increase heap size or reduce allocation rate, tune `-XX:G1HeapRegionSize` for workloads with many humongous objects, or evaluate generational ZGC if pause-time consistency matters more than the memory/throughput tradeoff |
| A microbenchmark shows wildly different numbers run-to-run, or "gets faster" the longer it runs | JIT warmup — early iterations run interpreted/C1-compiled, later iterations run C2-optimized with escape analysis and speculative inlining applied; naive timing loops conflate warmup cost with steady-state performance | Use JMH (Java Microbenchmark Harness), which explicitly separates warmup iterations from measurement iterations, rather than hand-rolled timing loops |
| A hot method's performance regresses sharply and permanently mid-run in production, visible as a step-change in latency | C2 deoptimized the method (a speculative assumption broke — e.g. a previously-monomorphic call site became polymorphic, or a class was redefined) and fell back to the interpreter; if the workload pattern that caused deopt persists, the method may thrash between compilation and deopt ("deopt storm") | Check JFR (Java Flight Recorder) or `-XX:+PrintCompilation`/`-XX:+TraceDeoptimization` for deopt events correlated with the regression; the fix is usually addressing the polymorphism at the call site (e.g. via `sealed` types or splitting the method) rather than JVM flags |
| Application classloader-related `OutOfMemoryError: Metaspace` in a service that dynamically loads/reloads classes (plugins, hot-reloading web frameworks) | Classloader leak — old classloaders (and every class they loaded) can't be garbage collected because something still references an instance, a static field, or a thread from that classloader, keeping the entire loaded-class graph alive indefinitely | Audit for retained references crossing classloader boundaries (ThreadLocals holding instances from a redeployed webapp are a classic culprit); use a heap dump plus a classloader-leak-aware tool to trace exactly what's pinning the old classloader |
| Escape analysis "should" eliminate an allocation per the source code shape, but profiling shows it's still heap-allocating | The object actually escapes in a way not obvious from a quick read — passed to a logging call, stored in a collection even conditionally, captured by a lambda/closure that itself escapes, or the method wasn't C2-compiled yet (didn't reach the invocation threshold) | Confirm C2 compilation actually happened (`-XX:+PrintCompilation`), then check every code path for an escape the source doesn't make obvious — even one rarely-executed escaping path defeats scalar replacement for the whole allocation site |

---

## Tradeoffs & when NOT to use it

- **Don't switch to ZGC by default for every service.** Generational ZGC's sub-millisecond pauses come with a real, measured cost (15-30% more memory, commonly 5-15% lower throughput than G1) — appropriate specifically for large-heap, latency-sensitive services where pause-time consistency genuinely matters more than raw throughput or memory efficiency (e.g. trading-adjacent systems, latency-SLO-bound user-facing services on large heaps), not a blanket upgrade for every JVM workload.
- **Don't hand-optimize for escape analysis by manually inlining code or avoiding small object allocations preemptively.** Escape analysis is specifically a C2-tier optimization that requires the method to actually get hot first — premature manual restructuring for allocations that were never going to be a measured bottleneck adds complexity for a benefit that may not exist for that code path at all; profile first.
- **Don't assume tiered compilation means "the JVM is always warmed up."** For genuinely short-lived processes (CLI tools, serverless functions with cold starts, batch jobs that finish before reaching C2 thresholds), the JVM never gets past interpreter/C1-tier performance for most of its execution — this is exactly the gap Project Leyden's ahead-of-time work targets, and it's a real, current limitation worth naming rather than assuming "JIT makes Java fast" unconditionally.
- **Don't treat GC tuning flags as a substitute for fixing allocation-heavy code.** Reducing allocation rate (object pooling where it genuinely helps, avoiding unnecessary boxing, escape-analysis-friendly code shapes) reduces GC pressure at the source; tuning collector flags manages symptoms of a high allocation rate rather than addressing it, and is a reasonable second step, not a first one.
- **This module's tiered-JIT/GC vocabulary is JVM-specific in its exact names but not in its concepts.** The interpreter→JIT progression, deoptimization, and generational garbage collection all have close analogues in V8 and increasingly in CPython (covered in the adjacent runtime modules) — treating JVM tuning knowledge as inapplicable outside Java misses that the underlying tradeoffs recur across every managed runtime.

---

## Interview questions

### Q1 — Explain the class loading delegation model and why it exists.
**Testing:** whether the security/correctness motivation is understood, not just the mechanism.
**Answer:** Classloaders form a hierarchy (bootstrap → platform → application), and each classloader delegates a load request to its parent first before attempting to load the class itself. This exists to guarantee that core JDK classes (`java.lang.String`, etc.) always resolve to the trusted bootstrap-loaded version regardless of what an application or third-party library on the classpath might define with the same fully-qualified name — without delegation, a malicious or accidental class shadowing a core JDK class could substitute itself in, a real security and correctness boundary.
**Follow-up trap:** *"What's a legitimate reason to break strict parent-delegation, and how is it done safely?"* — application servers hosting multiple independent web applications (each needing potentially different versions of the same library) use child-first (or per-webapp isolated) classloading specifically so each application's classpath can be independent, which requires deliberately structured classloader hierarchies (not literally reversing bootstrap delegation for core classes) — this is exactly the mechanism behind classloader-leak bugs when those per-application classloaders aren't fully released on redeploy.

### Q2 — Walk through tiered compilation: interpreter, C1, C2. Why not just always use C2?
**Answer:** The interpreter runs any bytecode immediately with zero compile latency but slow per-instruction execution. C1 compiles quickly with light optimization once a method crosses a low invocation threshold, giving a real throughput improvement almost immediately while also gathering profiling data (branch outcomes, concrete types at call sites). C2 recompiles genuinely hot methods (a higher threshold, informed by C1's profiling) with aggressive, slower-to-produce optimizations including escape analysis and speculative inlining. Always using C2 would give the best eventual throughput but terrible warmup latency, since C2 compilation itself is comparatively slow and every method — including ones invoked only a handful of times — would pay that cost regardless of whether it's ever actually hot.
**Follow-up trap:** *"What happens when a C2-compiled method's speculative assumption is later violated?"* — deoptimization: the JVM discards the compiled code, falls back to interpreting that method, and depending on why the assumption broke, may eventually re-profile and recompile with corrected assumptions — this can thrash ("deopt storm") if the underlying code pattern is genuinely unstable (e.g. a call site alternating between many concrete types), which is a real production performance cliff distinct from ordinary warmup.

### Q3 — What is escape analysis, and give a concrete example of what it enables beyond avoiding a heap allocation.
**Answer:** Escape analysis proves whether an allocated object can ever be referenced outside its allocating method (or thread). If it provably can't escape the method, the JIT can scalar-replace it — treat its fields as local variables/registers instead of a heap object, eliminating the allocation and its GC cost entirely. If it escapes the method but provably not the thread, lock elision becomes possible: `synchronized` blocks on a thread-local object can have their locking entirely removed, since no other thread could ever contend for it, eliminating otherwise-real synchronization overhead.
**Follow-up trap:** *"Why is escape analysis only available at the C2 tier, not the interpreter or C1?"* — escape analysis requires whole-method (and often cross-call, with inlining) data-flow analysis to prove non-escape, which is exactly the kind of expensive, slow-to-produce analysis C2's optimization budget is reserved for; the interpreter does no compilation at all, and C1 prioritizes fast compile time over this class of deep analysis — which is precisely why a method's steady-state (C2-warmed) performance can measurably exceed its early performance beyond the raw interpreted-vs-compiled gap.

### Q4 — Compare G1 and generational ZGC: pause time, throughput, memory, and when you'd choose each.
**Answer:** G1 divides the heap into regions, prioritizes collecting the highest-garbage regions first, and targets a configurable pause-time goal (commonly tens of milliseconds) but still has real stop-the-world phases and can fall back to full GC under pressure. Generational ZGC achieves consistent sub-millisecond pauses (0.1-0.5ms) regardless of heap size by doing marking/relocation/remapping almost entirely concurrently via colored pointers and load barriers, at the cost of no compressed object pointers (15-30% more memory) and typically 5-15% lower throughput than G1. Choose G1 as the default for most general-purpose services; choose generational ZGC specifically for large-heap, latency-sensitive services where consistent sub-millisecond pauses matter more than the memory/throughput cost.
**Follow-up trap:** *"Is ZGC's pause time actually independent of heap size, or does that break down somewhere?"* — it's a genuinely load-bearing, correctly-cited claim (ZGC's design goal and observed behavior specifically decouples pause time from heap size, unlike traditional stop-the-world collectors where pause time scales with live-set size) — but "pause time" independent of heap size doesn't mean "GC has zero cost independent of heap size"; the concurrent work (marking, relocating) still consumes CPU proportional to live data and allocation rate, which is exactly where ZGC's throughput cost comes from even though it never manifests as a long stop-the-world pause.

### Q5 — What's a humongous object in G1, and why can frequent large allocations hurt G1 specifically?
**Answer:** G1 allocates objects larger than 50% of a region size specially, across contiguous regions, rather than fitting them into a normal region alongside other objects. Workloads that frequently allocate such large objects (big byte arrays, large collections) can suffer additional GC pressure and heap fragmentation specifically from this special-cased handling, since finding enough contiguous free regions for a humongous allocation is a harder bin-packing problem than normal regional allocation.
**Follow-up trap:** *"How would you tune around this without switching collectors?"* — increasing `-XX:G1HeapRegionSize` raises the humongous-object threshold (since it's defined relative to region size), which can convert previously-humongous allocations into normal regional ones if the region size increase is large enough — a real, workload-specific tuning lever, though not a universal fix if object sizes vary widely enough that no single region size avoids the humongous path for the largest allocations.

### Q6 — A microbenchmark shows a method "getting faster" over the first several thousand calls, then stabilizing. Is this a bug, and how should you actually measure it?
**Answer:** Not a bug — this is JIT warmup, exactly matching the interpreter→C1→C2 progression: early calls run interpreted or C1-compiled (slower), and once the method crosses C2's invocation threshold and gets recompiled with aggressive optimization (potentially including escape analysis and speculative inlining), it stabilizes at its steady-state, C2-optimized performance. A naive hand-rolled timing loop conflates this warmup cost with steady-state performance, producing misleading numbers.
**Follow-up trap:** *"How does JMH specifically solve this, mechanically?"* — JMH explicitly separates warmup iterations (run and discarded, specifically to let the JIT reach steady state) from measurement iterations (only counted after warmup completes), and additionally guards against related measurement pitfalls like dead-code elimination (optimizing away a benchmark's "useless" computed result, which JMH prevents via blackholes) and constant-folding of benchmark inputs — none of which a hand-written `System.nanoTime()` loop guards against by default.

### Q7 — Staff-level: your service on G1 shows acceptable average latency but a p99.9 tail with occasional 200-400ms spikes correlated with GC logs. Walk through your diagnosis and options.
**Answer:** Correlate the spikes precisely against GC log timestamps (`-Xlog:gc*` or equivalent) to confirm whether they're young collections (should be short, tens of ms typically), mixed collections, or full GCs (the likeliest culprit for 200-400ms+ pauses) — and check for humongous-object allocation patterns or heap fragmentation contributing to full-GC fallback. Options, roughly in order of invasiveness: first, tune G1 (raise `-XX:MaxGCPauseMillis` expectations realistically, adjust heap sizing/region size, address any humongous-allocation pattern); if G1 tuning can't close the gap and the tail latency genuinely violates an SLO, evaluate generational ZGC specifically for its sub-millisecond pause guarantee, accepting the throughput/memory tradeoff; in parallel, investigate whether allocation rate itself can be reduced (object pooling, escape-analysis-friendly code shapes, avoiding unnecessary large allocations) since lower allocation pressure helps under either collector.
**Follow-up trap:** *"Would you recommend just switching to ZGC immediately as the fast fix?"* — only after confirming G1 tuning genuinely can't meet the SLO and that the workload can absorb ZGC's real memory/throughput cost — jumping to a collector switch without first correlating the actual pause cause (is it really full GC, or something else entirely, like a downstream dependency timeout that merely correlates coincidentally with a GC log timestamp) risks solving the wrong problem or paying ZGC's cost for a gain that a simpler G1 tuning change would have delivered.

---

## Red flags that fail you

- Claiming "the JIT" as a monolithic thing without distinguishing C1 from C2 or explaining tiered compilation's actual purpose.
- Describing escape analysis as "the JVM being smart about memory" without the specific mechanism (proving non-escape, enabling scalar replacement/lock elision).
- Claiming ZGC has zero cost relative to G1, or that its sub-millisecond pause guarantee means GC work itself is free.
- Not knowing that ZGC is now generational and is the default/only ZGC form as of Java 25 LTS, or citing pre-generational ZGC throughput numbers as current.
- Benchmarking JVM code with a naive hand-rolled timing loop and treating the result as reliable steady-state performance.
- Recommending a GC algorithm switch as a first response to a latency problem without first confirming via GC logs that GC is actually the cause.

---

## Cheat card

```
CLASS LOADING: bootstrap -> platform -> application, PARENT-DELEGATION (child asks
  parent first) -- prevents shadowing core JDK classes. Phases: load -> link (verify,
  prepare, resolve) -> initialize (lazy, on first active use).
TIERED COMPILATION: interpreter (0 compile latency, slow dispatch) -> C1 (fast compile,
  light opt, gathers profiling data) -> C2 (slow compile, aggressive opt: inlining,
  escape analysis, speculative optimization using C1's profile data). Default since 7u4.
DEOPTIMIZATION: speculative C2 assumption breaks (call site polymorphism, class redef)
  -> discard compiled code, fall back to interpreter, may re-profile/recompile.
  "Deopt storm" = thrashing if the pattern is genuinely unstable.
ESCAPE ANALYSIS (C2-only): proves object never escapes method -> SCALAR REPLACEMENT
  (fields become locals/registers, zero heap alloc, zero GC cost). Proves no escape past
  thread -> LOCK ELISION (synchronized removed, no possible contention).
G1 (default since Java 9): region-based heap, collects highest-garbage regions first.
  Configurable pause goal (-XX:MaxGCPauseMillis, commonly tens of ms). HUMONGOUS OBJECT:
  >50% of region size, special contiguous-region handling -> real fragmentation/GC-
  pressure gotcha for workloads with frequent large allocations.
ZGC (generational, default/only form as of Java 25 LTS): sub-ms pauses (~0.1-0.5ms)
  INDEPENDENT of heap size (even multi-TB), via concurrent marking/relocation/remapping
  using colored pointers + load barriers. Cost: no compressed oops (~15-30% more memory),
  ~5-15% lower throughput than G1. Generational split closed most of the throughput gap
  vs original single-gen ZGC.
DEFAULT GUIDANCE 2026: G1 for most services. Generational ZGC specifically for
  large-heap + latency-SLO-bound workloads where sub-ms pause consistency > throughput/memory.
BENCHMARKING: use JMH (separates warmup from measurement, guards dead-code elimination/
  constant-folding) -- never trust a naive hand-rolled timing loop for JIT-warmed code.
```

## Sources

- [The JVM Garbage Collector Decision in 2026: G1 vs ZGC vs Shenandoah — Java Code Geeks](https://www.javacodegeeks.com/2026/04/the-jvm-garbage-collector-decision-in-2026-g1-vs-zgc-vs-shenandoah-for-real-workloads.html) — accessed 2026-08-03
- [ZGC vs G1GC in Java 26: Which GC Should You Actually Use? — Java Code Geeks](https://www.javacodegeeks.com/2026/06/zgc-vs-g1gc-in-java-26-which-gc-should-you-actually-use.html) — accessed 2026-08-03
- [Pauseless Garbage Collection in Java 25: ZGC Deep Dive — Andrew Baker](https://andrewbaker.ninja/2025/12/03/deep-dive-pauseless-garbage-collection-in-java-25/) — accessed 2026-08-03
- JEP 439 — Generational ZGC (OpenJDK)
- JEP 248 / JEP 344 — G1 as default collector, and G1 abortable mixed collections
- OpenJDK Project Leyden — accessed 2026-08-03, referenced for ahead-of-time/startup direction
- Oracle, "The Java HotSpot Performance Engine Architecture" — canonical primary source for tiered compilation architecture

## Changelog
- 2026-08-03 — created
