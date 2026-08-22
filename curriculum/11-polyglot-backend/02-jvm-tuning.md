# JVM Memory Model, G1 vs ZGC, JIT Tiers, async-profiler/JFR, Reading a GC Log

> **Track:** T11 Polyglot Backend · **Time:** 2.5h · **Prereqs:** T11-java-modern · **Updated:** 2026-08-03
> **Module id:** `T11-jvm-tuning` · **Tags:** java, critical

## The 30-second version

The JVM heap splits into a young generation (Eden + two Survivor spaces, collected frequently and cheaply because most objects die young — the "weak generational hypothesis") and an old generation (collected rarely, expensively, holding objects that survived enough young collections); G1, the default collector since Java 9, breaks the heap into 1-32MB regions sized so the heap holds roughly 2,048 of them, and mixes young and "mixed" (young + a selected subset of old) collections to hit a target pause time (`-XX:MaxGCPauseMillis`, default 200ms) rather than a fixed generation size. ZGC takes a different bet entirely: instead of stopping the world to relocate live objects, it relocates concurrently using colored pointers and load barriers, holding pauses to sub-millisecond regardless of heap size — the tradeoff is 15-30% more memory overhead and 5-10% more CPU for that concurrency, and Generational ZGC (default since JDK 23, JEP 474) closed most of the throughput gap that made ZGC a latency-only choice before. Underneath both, the JIT doesn't compile everything at once — code starts interpreted, warms through C1 (tiers 1-3, fast compile, light optimization) and, if hot enough, gets recompiled by C2 (tier 4, slow compile, aggressive optimization: inlining, loop unrolling, escape analysis) — which is why a benchmark that doesn't warm up measures the interpreter, not your production hot path. The actual senior skill isn't memorizing flags, it's diagnosis: read a GC log to tell a young-gen problem (too-frequent, short pauses) from an old-gen problem (rare, long pauses, promotion failure) from a JIT problem (steady-state CPU that never drops after warmup), and know that G1 remains the right default for the overwhelming majority of services — you reach for ZGC only after profiling proves GC pause time, not GC frequency, is the thing violating your SLO.

## Why this gets asked

Because "the service is slow" and "the service has a GC pause problem" are different diagnoses that require different evidence, and most engineers reach for `-Xmx` tuning or a collector switch before ever looking at a GC log or a flame graph. The interviewer has almost certainly debugged a service where someone doubled the heap to "fix GC pauses" and made them worse (bigger heap, more live data to scan, longer pauses), or watched a team switch to ZGC for a throughput-bound batch job where it actively hurt (paying ZGC's concurrent-relocation CPU tax for a workload that never had a latency SLO to begin with). At staff level they're checking whether you reach for measurement (JFR, async-profiler, `-Xlog:gc`) before reaching for a flag, and whether you know the actual mechanism well enough to predict a fix's second-order effect instead of pattern-matching a StackOverflow answer.

---

## Lineage: past → present → future

**What came before.** The original HotSpot collectors — Serial, Parallel (Throughput), and CMS (Concurrent Mark Sweep) — each optimized for one axis and ignored the others. Serial single-threaded everything, fine only for tiny heaps. Parallel GC maximized throughput with multi-threaded stop-the-world collection but accepted pauses that scaled with heap size — a 32GB heap under Parallel GC could pause for seconds during a full collection, which was fine for offline batch jobs and unacceptable for anything user-facing. CMS tried to fix that by doing most of old-gen collection concurrently with the application, but it never compacted the old generation concurrently, so long-running CMS services eventually suffered **fragmentation-induced concurrent mode failure**: the collector couldn't find contiguous free space for a large allocation, fell back to a full stop-the-world compaction, and produced the exact multi-second pause CMS existed to avoid — the failure mode that killed it. CMS was deprecated in Java 9 and removed in Java 14.

**Where it stands now.** G1 (Garbage First, production-ready Java 7u4, default since Java 9) replaced both Parallel and CMS as the general-purpose default by taking a fundamentally different approach: instead of fixed contiguous young/old generations, the heap is divided into many equally-sized regions, and G1 tracks how much garbage each region holds so it can *choose* the regions with the most reclaimable garbage first — "garbage first" — giving it a pause-time *target* (`MaxGCPauseMillis`) rather than a pause time that's a fixed function of generation size. This is real, deployed-everywhere technology, not a research direction — it's the collector under the overwhelming majority of production JVMs today. The live disagreement is G1 versus ZGC (and, less commonly discussed now, Shenandoah, RedHat's similar low-pause concurrent collector) for latency-sensitive services: ZGC's pauses are sub-millisecond and effectively heap-size-independent because relocation itself happens concurrently with the application using colored pointers and load barriers to keep references valid mid-move, but that concurrency isn't free — 2025-2026 comparisons consistently show ZGC costing 15-30% more memory and 5-10% more CPU than G1 for the same workload. Generational ZGC (default since JDK 23, JEP 474) narrowed the throughput gap significantly by finally giving ZGC the same young/old-generation hypothesis exploitation G1 always had, and non-generational ZGC was removed outright in a later JEP (490) because generational mode won essentially every internal and community benchmark. The practical 2026 consensus, cited across multiple sources: start with G1, and only move to ZGC after profiling proves pause time — not throughput, not GC frequency — is the actual SLO violation.

**Where it's heading.** Shenandoah remains a credible alternative with a similar concurrent-compaction philosophy to ZGC but different internals (Brooks pointers instead of colored pointers); its relative position versus Generational ZGC is a live, workload-dependent comparison rather than a settled ranking. More broadly, the direction of travel across all modern collectors is toward *concurrent* everything — G1 itself has been incrementally moving more work off the stop-the-world path release over release — because the fundamental lesson of the CMS-to-G1-to-ZGC lineage is that stop-the-world pauses that scale with heap size are the actual enemy, not garbage collection itself. Expect continued incremental G1 improvements (JDK 25 shipped real G1 gains) rather than G1 being displaced as the default; ZGC adoption will keep growing specifically for tail-latency-critical services and very large heaps (32GB+, where G1's pause times start scaling unfavorably) rather than becoming the universal default, because the memory/CPU tax is a real cost most throughput-oriented services have no reason to pay.

---

## Mental model

```
HEAP LAYOUT (conceptual — G1 implements this via regions, not fixed blocks):

  YOUNG GEN                                    OLD GEN
  ┌──────────┬────────┬────────┐              ┌─────────────────────┐
  │  Eden     │ Surv 0 │ Surv 1 │              │  long-lived objects  │
  │ (new objs)│(copied)│(copied)│   promoted   │  collected rarely,   │
  │           │        │        │ ───────────▶ │  expensively         │
  └──────────┴────────┴────────┘              └─────────────────────┘
  MINOR/YOUNG GC: frequent, cheap                FULL/OLD GC: rare, costly
  (most objects die here — the                   (G1: "mixed" GC selects
   weak generational hypothesis)                  garbage-heavy old regions)

G1 REGIONS (not fixed young/old blocks — any region can be E/S/O/Humongous):
  [E][E][S][O][O][E][H H H H][O][E][S][O] ...  ~2048 regions, 1-32MB each
  G1 tracks per-region garbage %, collects highest-garbage regions first
  ("garbage first") to hit MaxGCPauseMillis target, not a fixed heap fraction.
  HUMONGOUS (H): object > 50% of region size, allocated in contiguous regions
  directly in old-gen-like space — bypasses young gen, common Full GC trigger.

ZGC: no young/old region split visible the same way (generational ZGC still
  has a young/old split internally, but the RELOCATION itself is concurrent):
  App thread reads a reference -> load barrier checks a COLOR BIT in the
  pointer -> if object was relocated, barrier transparently redirects/fixes
  the reference on the fly -> app never sees a stale pointer, no stop-the-
  world needed to fix up references during compaction.
  Pause = only the tiny bookkeeping stop, not the actual relocation work.

JIT TIERS (interpreter -> C1 -> C2, "tiered compilation"):
  Tier 0: interpreter            (every method starts here)
  Tier 1: C1, no profiling       (rarely used directly — simple methods)
  Tier 2: C1, limited profiling
  Tier 3: C1, full profiling     <- collects data C2 will use
  Tier 4: C2, full optimization  <- inlining, loop unrolling, escape analysis
  A method promotes tiers as its invocation count crosses thresholds.
  DEOPTIMIZATION: C2 can bet wrong (e.g. assumed a call site monomorphic)
  and fall back to the interpreter, recompiling later with corrected data.
```

---

## How it actually works

### The generational hypothesis and why young GC is cheap

Empirically, most objects die within microseconds to milliseconds of allocation (a request-scoped DTO, a temporary string, a loop iterator) — this is the **weak generational hypothesis**, and every modern collector is built on exploiting it. A young/minor GC only has to scan the young generation plus a small structure tracking old→young references (the **remembered set** / **card table**) — it does *not* need to scan the entire old generation to find garbage, because objects that die young are, definitionally, mostly in Eden. This is why a young GC pause on a multi-GB heap can still be single-digit milliseconds: its cost is proportional to *live* young-gen data (which gets copied to Survivor or promoted), not total heap size.

**Promotion**: an object surviving enough young GCs (tracked via an age counter in the object header, default promotion threshold commonly 15 survivals, tunable via `-XX:MaxTenuringThreshold`) gets copied to the old generation. Promoting too eagerly (low threshold) fills old gen with objects that would have died in the next young GC anyway, forcing more expensive old-gen collections sooner. Promoting too conservatively oversizes Survivor spaces and can cause premature promotion via a different path — Survivor overflow, where Survivor is too small to hold everything that should still be surviving, so objects get pushed to old gen regardless of age.

### G1: regions, MaxGCPauseMillis, and the actual failure mode

G1's region size is `heap_size / 2048` rounded to the nearest power of two, clamped between 1MB and 32MB (`-XX:G1HeapRegionSize` overrides this). A region isn't permanently young or old — G1 relabels regions as needed, which is what lets it target a pause time instead of a fixed generation ratio: if young GCs are running under budget, G1 can grow the young generation; if they're running over, it shrinks it, all while the target stays `MaxGCPauseMillis` (default **200ms**).

**Humongous objects** — any object larger than 50% of the region size — are the sharp edge G1 users hit in production. They're allocated directly into contiguous regions outside the normal young-gen path (effectively old-gen-like from the start), which means they bypass the cheap young-GC lifecycle entirely and can only be reclaimed by an old/mixed collection. A workload allocating many large byte arrays or big collections (a service deserializing large JSON blobs, a batch job building big in-memory buffers) can fragment the heap with humongous regions and trigger **Full GCs far more often than the live data size would suggest** — the fix is either increasing `G1HeapRegionSize` so fewer objects cross the 50% threshold, or restructuring the allocation pattern to avoid huge single objects (streaming instead of buffering, chunking instead of one giant array).

**Mixed GC**, G1's other distinctive mechanism: instead of a binary young-GC/full-GC split, G1 runs young GCs that *also* include a bounded selection of old-gen regions with the highest garbage percentage — "mixed" collections — reclaiming old-gen garbage incrementally without ever needing a full stop-the-world old-gen sweep, as long as it keeps up with allocation rate. **The actual G1 failure mode**: if the application allocates faster than concurrent marking can keep up, G1 falls back to a full, stop-the-world, single-threaded-in-older-JDKs Full GC — this is the pause you see spike to multiple seconds on a large heap, and it's the single most common "G1 is slow" complaint, almost always caused by either an undersized heap for the live data set or a marking cycle that can't complete before old gen fills.

```
# Minimal, defensible G1 production flags — start here, tune from evidence
-Xms8g -Xmx8g                          # equal min/max avoids resize pauses
-XX:+UseG1GC                           # explicit even though it's default
-XX:MaxGCPauseMillis=200               # the actual default; state it, don't guess
-XX:+ParallelRefProcEnabled            # parallelize reference processing
-Xlog:gc*:file=gc.log:time,uptime,level,tags
```

### ZGC and Generational ZGC: colored pointers, load barriers, and the real cost

ZGC's core trick is encoding metadata bits (marked, remapped, finalizable) directly in the unused high bits of a 64-bit pointer — **colored pointers** — so that when the collector concurrently relocates an object, every subsequent read of a reference to it goes through a **load barrier**: a small check that inspects the color bits and, if the object moved, transparently fixes the pointer on the fly before the application code sees it. This is what makes relocation itself concurrent — the application never has to be stopped to fix up every reference to a moved object, because each reference self-heals lazily on next access. The stop-the-world component shrinks to small, roughly-constant bookkeeping pauses (root scanning) rather than anything proportional to live set size, which is the mechanism behind ZGC's headline sub-millisecond pause claim (commonly cited **0.05-0.5ms** regardless of heap size).

**Generational ZGC** (default since JDK 23, JEP 474; non-generational mode removed in a later release via JEP 490) added the same young/old-generation split G1 always had, specifically because non-generational ZGC had to treat every object uniformly — no cheap young-gen fast path — which cost real throughput versus G1 on allocation-heavy workloads. Generational ZGC is reported to cut CPU overhead by roughly **30-40%** versus non-generational ZGC for allocation-heavy workloads, which is why it displaced the older mode entirely rather than existing alongside it.

**The real, undodgeable cost**: ZGC's concurrency requires extra bookkeeping (colored pointer metadata, load barrier checks on every reference read, multi-mapped memory for the pointer coloring scheme) that shows up as **15-30% higher memory usage and 5-10% higher CPU usage** versus G1 for equivalent workloads — this is not a tuning problem to solve away, it's the structural price of concurrent relocation, and it's the number to know cold when an interviewer asks "why wouldn't you just always use ZGC."

### JIT tiers: why cold code is slow and why microbenchmarks lie

HotSpot's tiered compilation runs code through five levels: **Tier 0** interpreter (everything starts here, always correct, always slow), **Tier 1** C1 with no profiling (used for trivially simple methods C2 wouldn't improve on), **Tier 2/3** C1 with increasing profiling instrumentation (collecting branch-frequency and type data C2 will consume), **Tier 4** C2 — the aggressive optimizing compiler doing method inlining, loop unrolling, and **escape analysis** (proving an object never escapes its allocating method/thread, which lets the JIT skip heap allocation entirely and keep the object on the stack or in registers — a genuine, measurable win for short-lived objects in hot loops). A method is promoted between tiers as its invocation/branch counters cross thresholds (`-XX:CompileThreshold`, tier-specific variants), which is exactly why **a JMH-less "just time it in a loop" microbenchmark is unreliable**: the first N iterations run interpreted or C1-compiled, meaning you're measuring warm-up cost, not steady-state throughput, unless you explicitly discard a warm-up phase (this is what JMH's `@Warmup` annotation exists to enforce).

**Deoptimization** is the JIT's escape hatch when C2's aggressive, profile-guided assumptions turn out wrong — the classic case is a call site C2 compiled assuming monomorphic dispatch (one concrete implementation seen so far) that later sees a second implementation; C2's inlined, specialized code is invalid for the new case, so the JVM deoptimizes that method back to the interpreter, then eventually recompiles with corrected (now polymorphic) profile data. A service that deoptimizes the same hot method repeatedly — visible in JFR's `jdk.Deoptimization` events or `-XX:+PrintCompilation` output showing the same method compiled, discarded, recompiled in a loop — has a real, fixable performance bug, typically caused by a call site that legitimately sees more implementation variety than C2's inline cache can handle cheaply (an unbounded strategy pattern, reflection-heavy dispatch).

### Reading a GC log: the actual skill

A single G1 log line for a young collection looks roughly like:

```
[2.145s][info][gc] GC(12) Pause Young (Normal) (G1 Evacuation Pause) 512M->128M(1024M) 4.2ms
```

Decompose it: `GC(12)` is the collection's sequence number (useful for correlating with other log lines about the same event); `Pause Young (Normal)` is the collection type — watch specifically for `(Normal)` versus `(Concurrent Start)` (a young GC that also kicks off concurrent marking) versus, ominously, `Pause Full (G1 Evacuation Pause)` or `Pause Full (Allocation Failure)`, which signals the fallback-to-full-GC failure mode above; `512M->128M(1024M)` is heap-used-before → heap-used-after (total heap capacity) — a before/after gap much smaller than expected means most "garbage" wasn't actually garbage, i.e. a real memory leak or working-set growth, not a collector problem; `4.2ms` is the pause duration.

**The triage table** (translate a log pattern into a diagnosis before touching a flag):

| Log pattern | Diagnosis | Where to look next |
|---|---|---|
| Frequent young GCs (every few hundred ms), each short (<10ms) | Normal for an allocation-heavy service; usually fine | Only a problem if aggregate GC time (`-Xlog:gc` totals) exceeds a few percent of wall time |
| Young GC frequency climbing over time, pause length also climbing | Working set growing — objects surviving longer than expected | Check for a cache without eviction, a growing collection, a leak — heap-used-after should plateau, not trend up |
| `Pause Full (Allocation Failure)`, multi-second pause | G1 couldn't reclaim old gen fast enough; classic G1 failure mode | Heap undersized for live data, or marking cycle (`InitiatingHeapOccupancyPercent`, default 45%) starting too late |
| Many `Pause Young` logs mentioning humongous allocation, or frequent Full GCs with a modest live set | Humongous object fragmentation | Increase `G1HeapRegionSize`, or restructure large-object allocation patterns |
| `heap-used-before -> heap-used-after` gap shrinking release over release with no code change | Slow leak — less is reclaimed each cycle as more stays permanently live | Heap dump + retained-size analysis (Eclipse MAT, JFR leak profiler), not GC tuning |

---

## Build it from scratch

A minimal, runnable measurement loop — capturing a GC log and a JFR recording on a real allocation-heavy workload, then reading both — is the actual skill, more than any code sample. The pattern to be able to describe cold:

```bash
# untested sketch — run with GC logging and a continuous low-overhead JFR recording
java -Xms4g -Xmx4g -XX:+UseG1GC -XX:MaxGCPauseMillis=200 \
     -Xlog:gc*:file=gc.log:time,uptime,level,tags \
     -XX:StartFlightRecording=filename=recording.jfr,duration=300s,settings=profile \
     -jar service.jar

# async-profiler: sample the SAME running process without a restart, flamegraph output
./profiler.sh -d 60 -e cpu -f flamegraph.html <pid>          # CPU flamegraph
./profiler.sh -d 60 -e alloc -f alloc-flamegraph.html <pid>  # allocation profiling
```

Reading the resulting artifacts: `gc.log` gives the triage table above directly. JFR's `jdk.ExecutionSample` events, aggregated, are effectively a lower-overhead CPU profile comparable to async-profiler's; JFR additionally gives `jdk.ObjectAllocationSample` for allocation hot spots and `jdk.Deoptimization` for JIT bailouts, all from one always-on recording. async-profiler's advantage is that it samples using `perf_events`/`AsyncGetCallTrace` outside the JVM's own instrumentation, which means it can see native frames (JNI, native library calls) that JFR's pure-JVM instrumentation misses — the two are complementary, not competing, and a full incident investigation typically pulls both. A lab building a small allocation-heavy service, deliberately introducing a humongous-object fragmentation bug and a promotion-too-eager bug, then diagnosing each from its GC log, belongs in `labs/java/02-jvm-tuning/`.

---

## How it's done in production

| Symptom | Cause | Fix |
|---|---|---|
| p99 latency spikes correlate exactly with `Pause Full` log entries, multi-second | G1's fallback-to-Full-GC failure mode — allocation outpacing concurrent marking, or heap undersized for live data | Increase heap if live-data-driven; lower `InitiatingHeapOccupancyPercent` so marking starts earlier; if pauses are the actual SLO violation (not just occasional), evaluate Generational ZGC |
| Frequent Full GCs despite a modest measured live-object set | Humongous object fragmentation — many allocations exceeding 50% of region size | `-XX:G1HeapRegionSize` increase, or restructure to avoid single huge allocations (stream instead of buffer) |
| CPU pegged near 100% steady-state, throughput below expectation, no obvious GC issue in the log | JIT never reaching C2 for hot methods, or repeated deoptimization thrashing a hot method back to the interpreter | `-XX:+PrintCompilation` or JFR `jdk.Deoptimization` events; look for a hot call site with unexpectedly high polymorphism (unbounded strategy pattern, heavy reflection) |
| Service moved to ZGC for a batch/throughput job, overall job time got worse | ZGC's 5-10% CPU / 15-30% memory tax paid for a workload with no actual pause-time SLO | Move back to G1 — ZGC only pays off when pause time itself is the metric that matters |
| Heap-used-after climbs release over release with identical traffic, eventually OOMs | Genuine memory leak (unbounded cache, listener registration without deregistration) misdiagnosed as "needs more heap" | Heap dump + retained-size analysis (Eclipse MAT), not a bigger `-Xmx` — a bigger heap just delays the OOM and makes each Full GC pause longer when it finally happens |
| Microbenchmark shows a "fix" is 3x faster locally, production shows no change | Benchmark measured interpreter/C1 warm-up cost, not C2 steady state — no proper warm-up phase | Rerun with JMH and its warm-up iterations, or manually discard the first N seconds of a load test before measuring |

---

## Tradeoffs & when NOT to use it

- **Don't switch to ZGC without a measured pause-time SLO violation.** ZGC's 15-30% memory and 5-10% CPU tax is real and permanent, not a tuning artifact — paying it for a throughput-bound batch job or an internal service with no latency SLA is a straightforward regression, and it's a common one people make reflexively because ZGC "sounds better."
- **Don't grow the heap to fix GC pauses without checking whether the pauses are frequency-driven or scan-cost-driven.** A bigger heap can make Full GC pauses *worse* (more live data to scan and compact) even while reducing how *often* they happen — the right fix depends on which one is actually hurting you, which the GC log tells you and intuition does not.
- **Don't tune G1 with more than `-Xmx`/`-Xms` and `MaxGCPauseMillis` until you have log evidence for the specific problem.** G1 is explicitly designed to need minimal tuning; touching `G1HeapRegionSize`, `InitiatingHeapOccupancyPercent`, or `MaxTenuringThreshold` without log evidence for the specific failure mode they address is guessing, and guessing on GC flags produces subtle regressions that are hard to attribute later.
- **Don't trust a benchmark without a stated warm-up phase.** Any Java performance claim — yours or someone else's — that doesn't mention discarding a warm-up period is measuring the interpreter and C1, not the JIT-optimized steady state your production traffic actually runs under.
- **Don't reach for CMS.** It's removed (Java 14+); if you see it recommended anywhere current, the source is stale.
- **Don't treat a heap dump as a last resort.** Waiting until an OOM to take a heap dump means you're debugging under production pressure with a huge, noisy dump; proactively capturing one during a controlled load test when memory growth is first suspected is cheaper and faster to analyze.

---

## Interview questions

### Q1 — Explain the weak generational hypothesis and why it makes young GC cheap.
**Testing:** whether the foundational assumption every modern collector relies on is understood, not just named.
**Answer:** Most objects die very shortly after allocation — a request-scoped DTO, a loop temporary, a string built and discarded. A young/minor GC only needs to scan the young generation plus a remembered set tracking old→young references, not the entire heap, so its cost scales with *live* young-gen data, not total heap size — which is why a multi-GB heap can still see single-digit-millisecond young GC pauses.
**Follow-up trap:** *"What happens when that hypothesis is wrong for a specific workload?"* — a workload that creates many medium-lived objects (surviving several young GCs but not truly long-lived) causes excessive copying between Survivor spaces and premature promotion, filling old gen with objects that would eventually have died — a real, named failure pattern sometimes called "premature promotion" or Survivor overflow, fixable by tuning `MaxTenuringThreshold` and Survivor sizing, but only after confirming the pattern in a GC log.

### Q2 — What does `MaxGCPauseMillis` actually control, and what happens if you set it unrealistically low?
**Testing:** whether it's understood as a soft target, not a guarantee.
**Answer:** It's a *target*, not a hard limit — G1 uses it to decide how much young-gen and mixed-collection work to attempt per pause, sizing the young generation and choosing how many old-gen regions to include in a mixed GC to try to hit that budget. Set it unrealistically low (e.g. 10ms on a large heap with a high allocation rate) and G1 shrinks the young generation aggressively to stay under budget, which increases GC *frequency* sharply — you trade fewer, longer pauses for many more, shorter ones, and if the allocation rate is high enough, G1 may still blow the target anyway or start falling behind on old-gen reclamation, risking the Full GC fallback.
**Follow-up trap:** *"So lower is always safer?"* — no; past a point it just increases GC frequency and CPU overhead without honoring the target, and can indirectly make old-gen collection worse by delaying it. The right way to find the number is a load test with the real allocation rate, not a guess.

### Q3 — Why did CMS get deprecated and removed? What specific failure mode killed it?
**Testing:** knowledge of the actual lineage, not just "it's old."
**Answer:** CMS collected old gen concurrently with the application but never compacted concurrently — it left the old generation fragmented after each cycle. Eventually a large allocation couldn't find contiguous free space despite there being enough *total* free space, forcing a fallback to a full, single-threaded, stop-the-world compaction — "concurrent mode failure" — which produced exactly the multi-second pause CMS existed to avoid, and often at the worst possible time (under memory pressure). Deprecated in Java 9, removed in Java 14.
**Follow-up trap:** *"Doesn't G1 have a similar fallback-to-Full-GC failure mode?"* — yes, and naming that parallel is the stronger answer: G1's Full GC fallback (allocation outpacing concurrent marking) is a direct descendant of the same underlying problem — a concurrent collector that can't keep up degrades to a stop-the-world pause. The difference is G1 compacts as part of its normal mixed-GC cycle, so fragmentation-specific failure is less common than CMS's, but the class of failure — concurrent collector falls behind, stops the world — is the same lineage.

### Q4 — What is a humongous object in G1, and why does allocating many of them cause more Full GCs than the live data size would suggest?
**Testing:** a specific, checkable G1 mechanism most people who've only read the marketing page don't know.
**Answer:** Any object larger than 50% of the region size. G1 allocates it directly into contiguous regions, bypassing the normal young-gen allocate-then-maybe-promote lifecycle — it behaves like old-gen data from the moment it's allocated. A workload allocating many humongous objects (large deserialized blobs, big buffers) fragments the heap with these regions and can only reclaim them via old/mixed collection, not cheap young GC, so Full GC frequency rises even though the *true* live-data footprint might be modest.
**Follow-up trap:** *"What's the fix, concretely?"* — either raise `-XX:G1HeapRegionSize` so fewer allocations cross the 50%-of-region threshold, or change the allocation pattern (stream large payloads instead of buffering them fully in memory, chunk big collections). Just adding heap doesn't fix the underlying fragmentation pattern, only delays hitting it.

### Q5 — Why does ZGC achieve sub-millisecond pauses regardless of heap size, mechanically?
**Testing:** whether colored pointers/load barriers are understood as a mechanism, not a marketing bullet.
**Answer:** ZGC encodes object state (marked, remapped) in unused high bits of the 64-bit pointer itself — colored pointers — and every reference read goes through a load barrier that checks those bits; if the object has moved, the barrier transparently fixes the reference on the spot before the application sees it. This means relocation happens *concurrently* with the application running — the collector doesn't need a stop-the-world pause to fix up every existing reference to a moved object, because references self-heal lazily on next access. The stop-the-world component shrinks to small, roughly heap-size-independent bookkeeping (root scanning), which is the actual source of the sub-millisecond claim.
**Follow-up trap:** *"If it's that good, why isn't it the default?"* — the concurrency isn't free: colored pointer metadata, per-reference load barrier checks, and multi-mapped memory for the coloring scheme cost roughly 15-30% more memory and 5-10% more CPU than G1 for equivalent workloads. That's a real, permanent tax most throughput-bound services have no SLO reason to pay, which is why G1 remains the default and ZGC is an opt-in for pause-sensitive services specifically.

### Q6 — What changed with Generational ZGC, and why was non-generational ZGC removed rather than kept alongside it?
**Testing:** whether the 2023-2024 timeline and rationale is known, not just "ZGC got generations."
**Answer:** Non-generational ZGC treated every object uniformly regardless of age — no cheap young-gen fast path like G1's — which cost real throughput on allocation-heavy workloads since every object paid the same relocation/barrier overhead whether it lived microseconds or hours. Generational ZGC (default since JDK 23, JEP 474) added the young/old split, reported to cut CPU overhead roughly 30-40% for allocation-heavy workloads versus non-generational mode. Because it won essentially every internal and community benchmark, non-generational mode was deprecated and later removed entirely (JEP 490) rather than maintained as a second mode — reducing long-term maintenance burden for a mode nobody had a reason to prefer anymore.
**Follow-up trap:** *"Does Generational ZGC close the throughput gap with G1 completely?"* — no; it narrowed it significantly but ZGC's structural 15-30% memory / 5-10% CPU cost versus G1 is still cited in current (2025-2026) comparisons. "Narrowed, not eliminated" is the accurate claim.

### Q7 — Explain tiered compilation and why a naive "time it in a loop" Java microbenchmark is unreliable.
**Testing:** whether JIT warm-up is understood well enough to distrust bad benchmarks on sight.
**Answer:** Every method starts interpreted (Tier 0), profiles through C1 (Tiers 1-3, collecting branch and type data), and — if it's hot enough — gets recompiled by C2 (Tier 4) with aggressive optimizations like inlining and escape analysis, which can be an order of magnitude faster than interpreted execution for hot code. A loop that just times N iterations includes the interpreter and C1 phases in its measurement — for anything but a very large N, that warm-up cost dominates or meaningfully skews the result, so the benchmark is measuring compilation behavior, not steady-state throughput.
**Follow-up trap:** *"How would you fix the benchmark?"* — use JMH with an explicit `@Warmup` phase discarded before measurement, or in a load test, discard the first several seconds/minutes of results before computing throughput/latency numbers, giving the JIT time to reach steady state on the actual hot paths.

### Q8 — A hot method keeps getting deoptimized and recompiled in a loop. What's the likely cause and how do you confirm it?
**Testing:** a specific, diagnosable production symptom rather than "the JIT is being weird."
**Answer:** C2 compiled the method with an optimistic assumption — commonly monomorphic dispatch at a call site, assumed from profiling data collected by C1 — that later turns out wrong when a second concrete implementation shows up at that call site. The inlined, specialized C2 code becomes invalid for the new case, so the JVM deoptimizes back to the interpreter and eventually recompiles with corrected, now-polymorphic profile data; if the call site keeps flipping between few and many implementations, this thrashes repeatedly. Confirm via JFR's `jdk.Deoptimization` events or `-XX:+PrintCompilation`/`-XX:+TraceDeoptimization` output showing the same method compiled, discarded, and recompiled.
**Follow-up trap:** *"What's the actual code-level fix?"* — reduce polymorphism at the hot call site if possible (bounding an unbounded strategy/plugin pattern, avoiding reflection-heavy dispatch on the hot path), or accept the cost if the polymorphism is inherent to the design — deoptimization thrashing is a real but sometimes irreducible cost of legitimately polymorphic hot paths.

### Q9 — Walk through a G1 GC log line and extract the diagnosis.
**Testing:** the concrete triage skill, not just terminology recall.
**Answer:** `Pause Young (Normal) (G1 Evacuation Pause) 512M->128M(1024M) 4.2ms` — a normal young collection, heap used dropped from 512M to 128M out of a 1024M total capacity, taking 4.2ms; healthy. Contrast with `Pause Full (Allocation Failure)` at multiple seconds — G1's fallback-to-Full-GC failure mode, meaning concurrent marking couldn't keep pace with allocation. Also watch the before→after gap trend across many log lines: a shrinking reclaim ratio release over release (more staying live each cycle, less garbage collected) is the signature of a slow leak, not a GC tuning problem.
**Follow-up trap:** *"The pause type says Normal but pauses are getting longer over weeks of uptime with flat traffic."* — that's the leak signature specifically: the *pattern* (Normal, not Full) says the collector is working correctly, but growing live-set size means more to scan/copy every cycle even in a routine young GC. The fix is a heap dump and retained-size analysis, not a GC flag.

### Q10 — When would you deliberately choose G1 over ZGC even for a latency-sensitive service?
**Testing:** staff-level judgment against the reflexive "always pick the lower-pause collector" answer.
**Answer:** When the service's actual heap is small to moderate (well under the 32GB range where G1's pause times start scaling unfavorably) and its p99 latency SLO is already comfortably met by G1's typical tens-to-low-hundreds-of-ms pauses — paying ZGC's 15-30% memory and 5-10% CPU tax for a pause-time budget you already have headroom on is pure cost with no benefit. Also when the workload is throughput-bound with a generous or nonexistent latency SLO (batch processing, an internal reporting service) — ZGC's whole value proposition is irrelevant there.
**Follow-up trap:** *"What's the actual heap-size threshold where you'd reconsider?"* — there's no fixed universal number; the honest answer is "measure G1's actual pause times under real load against the real SLO first," since G1's JDK 25 improvements have pushed the point where ZGC clearly wins higher than older folk wisdom suggests. Citing a specific number without having measured it is the wrong instinct to signal.

### Q11 — Distinguish what JFR and async-profiler each give you that the other doesn't.
**Testing:** whether these are understood as complementary tools rather than interchangeable ones.
**Answer:** JFR is built into the JVM, always-on-capable at sub-1% overhead, and captures a wide range of JVM-internal event types in one recording — GC pauses, allocation samples (`jdk.ObjectAllocationSample`), deoptimizations, thread contention, safepoints — correlated on one shared timeline, which is invaluable for tying a GC pause to what the application was doing at that exact moment. async-profiler samples via `perf_events`/`AsyncGetCallTrace` outside the JVM's own instrumentation, which lets it see native frames — JNI calls, native library stack frames — that JFR's pure-JVM view misses, and it produces flamegraphs directly, which is often the fastest way to spot an unexpected hot method visually.
**Follow-up trap:** *"If you could only run one in a production incident, which?"* — JFR, because it's typically already running (or trivially attachable without a restart) and gives correlated GC/allocation/thread context in one place; async-profiler is the follow-up tool once you need native-frame visibility or a flamegraph for a specific narrow window, not the first thing you reach for blind.

---

## Red flags that fail you

- Recommending CMS (removed since Java 14).
- Switching to ZGC as a reflexive fix for "GC pauses" without checking whether pause time or pause frequency is the actual SLO violation.
- Growing the heap to fix a GC problem without distinguishing a frequency issue from a scan-cost issue.
- Not knowing what a humongous object is or why it bypasses the cheap young-gen path.
- Trusting a "time it in a loop" microbenchmark with no stated warm-up phase.
- Claiming ZGC has no cost versus G1 — the 15-30% memory / 5-10% CPU tax is real and worth stating unprompted.
- Confusing deoptimization (JIT bailing back to the interpreter on a bad assumption) with a GC event — they're unrelated subsystems.
- Reading a GC log's "before -> after" heap numbers without checking the trend across many collections for a leak signature.

---

## Cheat card

```
GENERATIONS   Eden+2 Survivor (young, cheap, frequent) -> promotion (age counter,
              default threshold ~15 survivals, -XX:MaxTenuringThreshold) -> Old
              (rare, expensive). Weak generational hypothesis: most objects die young.

G1 (default since Java 9): region-based, 1-32MB regions, ~2048 regions/heap
  -XX:G1HeapRegionSize = heap/2048, rounded to power of 2
  -XX:MaxGCPauseMillis  default 200ms — a TARGET, not a guarantee
  HUMONGOUS: object > 50% region size -> allocated old-gen-like, bypasses young
  gen, common Full GC trigger. Fix: bigger region size or avoid huge single allocs.
  MIXED GC: young + highest-garbage old regions, incremental old-gen reclaim
  FAILURE MODE: allocation outpaces concurrent marking -> Full GC fallback,
  multi-second pause. Same lineage as CMS's "concurrent mode failure" (removed Java 14).

ZGC: colored pointers (state bits in the 64-bit pointer) + load barriers ->
  relocation happens CONCURRENTLY, pause shrinks to small heap-size-independent
  bookkeeping. Sub-ms pauses (~0.05-0.5ms cited). COST: 15-30% more memory,
  5-10% more CPU vs G1 — real, permanent, not tunable away.
  GENERATIONAL ZGC: default since JDK 23 (JEP 474). Non-gen mode REMOVED (JEP 490).
  Cuts CPU ~30-40% vs non-gen ZGC for allocation-heavy workloads.

DECISION: default G1. Switch to ZGC only after log/JFR evidence PAUSE TIME
  (not frequency, not throughput) violates the actual SLO.

JIT TIERS: 0=interpreter, 1=C1 no profile, 2/3=C1 w/ profiling, 4=C2 full opt
  (inlining, loop unrolling, escape analysis). Escape analysis: proves object
  never escapes method/thread -> stack-allocate, skip heap entirely.
  DEOPT: C2's assumption (e.g. monomorphic call site) proven wrong -> falls
  back to interpreter, recompiles w/ corrected profile. Repeated deopt on one
  method = thrashing, usually from unexpected call-site polymorphism.
  Microbenchmarks WITHOUT a warm-up phase measure the interpreter, not C2.

GC LOG: "Pause Young (Normal) 512M->128M(1024M) 4.2ms" = before->after(capacity) dur
  Watch for: Pause Full (Allocation Failure) = the fallback failure mode.
  Shrinking before->after gap over time w/ flat traffic = leak, not GC tuning.

TOOLS: JFR = always-on, low overhead, correlated GC+alloc+deopt+thread events
  in one recording. async-profiler = perf_events/AsyncGetCallTrace, sees NATIVE
  frames JFR misses, direct flamegraphs. Complementary, not either/or.
```

## Sources

- [The JVM Garbage Collector Decision in 2026: G1 vs ZGC vs Shenandoah for Real Workloads — Java Code Geeks](https://www.javacodegeeks.com/2026/04/the-jvm-garbage-collector-decision-in-2026-g1-vs-zgc-vs-shenandoah-for-real-workloads.html) — accessed 2026-08-03
- [ZGC vs G1GC in Java 26: Which GC Should You Actually Use? — Java Code Geeks](https://www.javacodegeeks.com/2026/06/zgc-vs-g1gc-in-java-26-which-gc-should-you-actually-use.html) — accessed 2026-08-03
- [JEP 474: ZGC: Generational Mode by Default](https://openjdk.org/jeps/474) — accessed 2026-08-03
- [JEP 490: ZGC: Remove the Non-Generational Mode](https://openjdk.org/jeps/490) — accessed 2026-08-03
- [Introducing Generational ZGC — Inside.java](https://inside.java/2023/11/28/gen-zgc-explainer/) — accessed 2026-08-03
- [G1GC Tuning — F Notes, Medium](https://fnote.medium.com/g1gc-tuning-ec78d40861d) — accessed 2026-08-03
- [To tune or not to tune? G1GC vs humongous allocation](https://krzysztofslusarski.github.io/2020/11/10/humongous.html) — accessed 2026-08-03
- [How the JVM Decides What to Compile: Inside the JIT Tier System and Profiling Pipeline — Java Code Geeks](https://www.javacodegeeks.com/2026/07/how-the-jvm-decides-what-to-compile-inside-the-jit-tier-system-and-profiling-pipeline.html) — accessed 2026-08-03
- [HotSpot Virtual Machine Garbage Collection Tuning Guide — Oracle](https://docs.oracle.com/en/java/javase/11/gctuning/garbage-first-garbage-collector-tuning.html) — accessed 2026-08-03

## Changelog
- 2026-08-03 — created
