# Production Debugging: Core Dumps, Thread Dumps, Heap Dumps, Live Profiling

> **Track:** T27 Tooling & Debugging · **Time:** 3h · **Prereqs:** T27-08-debug-methodology, T27-09-debug-any-language
> **Module id:** `T27-prod-debugging` · **Tags:** debugging, jvm, python, profiling, observability
> **Lab:** none yet — see `labs/py/02-agent-loop/` for the pattern if you want to build one

## The 30-second version

When a process crashes or hangs in production, you cannot attach an interactive debugger — you need a point-in-time snapshot you can analyze after the fact, and which snapshot you need depends on the symptom: a **core dump** (a full memory image on crash, controlled by `ulimit -c` and the kernel's `core_pattern`, inspected with `gdb`) answers "what was the C/C++/native process doing at the exact instant it crashed"; a **JVM thread dump** (`jstack <pid>` or `jcmd <pid> Thread.print`) answers "what is every thread doing right now, and is anything deadlocked" (jstack auto-detects and reports deadlocks at the end of its output); a **JVM heap dump** (`jmap -dump:live` or `jcmd <pid> GC.heap_dump`, analyzed in Eclipse MAT via its Dominator Tree and Leak Suspects Report) answers "what's actually retaining memory and why isn't it collected"; and **py-spy** does the equivalent for Python — `py-spy dump --pid <pid>` prints every thread's current Python call stack with zero instrumentation and no process restart, because it reads the interpreter's memory directly from outside the process via OS-level inspection, and `py-spy record` produces a flamegraph the same way. All of these are point-in-time captures — they tell you the state at one moment, not the pattern over time — which is the gap **continuous profiling** (Pyroscope, Parca, Google's Cloud Profiler) fills: always-on, low-overhead (eBPF-based tools like Parca report under 1% overhead; sampling profilers like Pyroscope commonly sample at 100Hz with 1-3% overhead) background sampling that lets you query "what was CPU/memory doing at 3:47am last Tuesday" after the fact, without having needed to know in advance that 3:47am last Tuesday would matter.

## Why this gets asked

Because "the debugger isn't attached and you can't attach one" is the actual condition of every serious production incident, and the interviewer has near-certainly lived through the specific failure of not knowing which snapshot to take: paging in at 3am to a hung JVM service, taking a heap dump first (the wrong tool — the service wasn't leaking memory, it was deadlocked) and burning twenty minutes analyzing gigabytes of retained objects before someone finally ran `jstack` and saw two threads holding each other's locks in the first ten lines. Or a Python worker pool silently going idle-forever with no logs, no crash, no error — where restarting fixes it temporarily but destroys the only evidence of the actual bug, and `py-spy dump` (which doesn't touch the process at all) would have shown the exact hung stack. They want to see you match tool to symptom instantly — crash vs hang vs slow vs leak are four different questions requiring four different captures — and know the actual commands and file locations cold, not "I'd Google it," because in a live incident there is no time to look up syntax.

---

## Lineage: past → present → future

**What came before.** Pre-core-dump-tooling debugging of a crashed process meant relying entirely on whatever the process had already logged before dying — genuinely worse, because a crash by definition happens at the moment the program's own logging can no longer be trusted to have captured the relevant state. Unix core dumps date to the earliest Unix systems (the kernel writing a process's memory image to disk on fatal signals like `SIGSEGV`/`SIGABRT` is decades old), and `gdb` (GNU Debugger, 1986) becoming the standard tool to load and inspect that image post-mortem was the first real answer to "reconstruct what a crashed native process was doing." For managed runtimes, the JVM shipped `jstack` and `jmap` as separate, purpose-built command-line tools for years — the pain this created was tool fragmentation (a different command, with different flags and output formats, for every diagnostic need) and, notably, `jmap`'s full heap dump historically requiring the JVM to pause all application threads for the duration of the dump (a stop-the-world pause that could itself cause a production incident on a large heap), which is why Oracle's own tooling guidance now steers people toward `jcmd` as the unified, lower-overhead successor. Python had no equivalent production-safe live-inspection story for a long time — the standard approach to "what is this hung Python process doing" was either adding print statements and redeploying (destroying the evidence) or attaching `gdb` to the Python interpreter's C-level process directly, which required deep CPython internals knowledge most engineers didn't have.

**Where it stands now.** `jcmd` is the current recommended unified JVM diagnostic tool (Oracle's own documentation explicitly recommends it over the older single-purpose `jstack`/`jmap` for reduced overhead and broader capability), though `jstack`/`jmap` remain extremely widely used in practice and still work identically well for the core thread-dump/heap-dump use cases. Eclipse MAT (Memory Analyzer Tool) is the dominant heap dump analysis tool, with a well-established workflow (Histogram to spot which classes dominate memory, Dominator Tree to see what's retaining what, Leak Suspects Report as an automated first pass, Path to GC Roots to confirm the actual reference chain keeping an object alive). `py-spy` (written in Rust, reading a target Python interpreter's stack via OS-level process inspection with no instrumentation, no code changes, and no restart) is now the standard tool for live Python production profiling and stack dumping, genuinely production-safe because it doesn't pause or slow the target process. The live disagreement in continuous profiling is architectural: **eBPF-based** collection (Parca's approach) samples any process at the kernel level with no per-language SDK or instrumentation required and reports under 1% overhead, versus **language-runtime sampling profilers** (Pyroscope's original approach, and most APM vendors' agents) which need a per-language integration but can capture richer, language-aware stack information (Python/Ruby/Java-specific frame detail an eBPF stack walk may not resolve as cleanly) — real production benchmarks report both approaches costing only a few percentage points of throughput/latency, so the choice is more about operational fit (do you want per-language agents, or one eBPF collector across a polyglot fleet) than a clear efficiency winner.

**Where it's heading.** High confidence: continuous, always-on profiling in production is becoming a default expectation for any serious platform team, the same trajectory distributed tracing went through a decade earlier — the cost of always-on low-overhead sampling has dropped enough (sub-1% to low-single-digit percent overhead) that "we'll profile if something looks slow" is increasingly seen as leaving cheap, always-available diagnostic data on the table. Moderate confidence: eBPF-based zero-instrumentation profiling (Parca's model) is likely to keep gaining share specifically for polyglot fleets where maintaining per-language profiling agents across many services is genuine operational overhead, though language-specific profilers retain a real edge in stack-frame fidelity for languages where eBPF's stack-walking has known gaps (deeply optimized/JIT-compiled code, some interpreter internals). Speculative: tighter integration between continuous profiling data and distributed tracing (so a slow trace span can be directly correlated with the exact profiling sample from that time window on that host) is an active vendor direction but not yet a universally solved, standardized workflow.

---

## Mental model

```
MATCH THE SYMPTOM TO THE TOOL:

  Process CRASHED (segfault, abort)         -> CORE DUMP + gdb
  Process HUNG / no progress, still alive   -> THREAD DUMP (jstack/jcmd, py-spy dump)
  Process using too much MEMORY, not crashed -> HEAP DUMP (jmap/jcmd + Eclipse MAT)
  Process SLOW, need to know WHERE time goes -> LIVE PROFILE (py-spy record, async-profiler)
  "What was happening at 3am last Tuesday?"  -> CONTINUOUS PROFILING (Pyroscope/Parca)
                                                 (the other four are ALL point-in-time --
                                                 useless if you didn't capture at the
                                                 right moment; this is the only one that's
                                                 ALWAYS already recording)

CORE DUMP PIPELINE (Linux, native processes):

  process crashes (SIGSEGV/SIGABRT)
         |
         v
  kernel checks ulimit -c (soft limit, per-process, `ulimit -c unlimited` to enable)
         |
         v
  kernel writes memory image per core_pattern (/proc/sys/kernel/core_pattern,
    e.g. "core.%e.%p.%t" = core.<progname>.<pid>.<timestamp>, or piped to
    a handler like systemd-coredump)
         |
         v
  gdb <binary> <corefile>  -->  `bt` (backtrace) at the moment of the crash

JVM THREAD DUMP (hang / deadlock):

  jstack <pid>  or  jcmd <pid> Thread.print
         |
         v
  every thread's current stack, states (RUNNABLE, BLOCKED, WAITING),
  and -- critically -- jstack AUTO-DETECTS deadlocks and prints them
  explicitly at the end of the dump: "Found one Java-level deadlock"

JVM HEAP DUMP (memory growth / OOM):

  jmap -dump:live,format=b,file=heap.hprof <pid>   (or jcmd <pid> GC.heap_dump)
         |
         v
  Eclipse MAT: Leak Suspects Report (automated first pass)
             -> Histogram (which CLASSES dominate)
             -> Dominator Tree (what's RETAINING what -- the actual answer)
             -> Path to GC Roots (confirm the exact reference chain)

PYTHON (py-spy -- no JVM equivalent instrumentation needed):

  py-spy dump --pid <pid>     -> every thread's CURRENT Python stack, instantly,
                                   NO restart, NO code changes, reads process
                                   memory from OUTSIDE it (Rust, OS-level)
  py-spy record -o out.svg --pid <pid>   -> flamegraph over a sampling window
  py-spy top --pid <pid>                  -> live top-style view

CONTINUOUS PROFILING (always recording, query afterward):
  Parca: eBPF, kernel-level, ANY process, no per-language SDK, <1% overhead
  Pyroscope: language-runtime sampling (~100Hz), per-language agent, 1-3% overhead
```

---

## How it actually works

### Core dumps: enabling them, and what gdb actually shows you

By default on most distributions, `ulimit -c` is **0** — the kernel will not write a core file at all when a process crashes, specifically to avoid unexpectedly filling disk with large memory images on every crash in normal operation. Enabling it is a soft-limit change: `ulimit -c unlimited` in the shell that launches the process (or, for a systemd service, `LimitCORE=infinity` in the unit file) raises the soft limit up to whatever the hard limit allows. Where the resulting file goes is controlled by the kernel parameter `kernel.core_pattern` (readable/writable at `/proc/sys/kernel/core_pattern`), which supports format specifiers — `%e` (executable name), `%p` (PID), `%t` (timestamp) — so a pattern like `core.%e.%p.%t` produces a distinct file per crash; many modern distributions instead pipe core dumps to `systemd-coredump` (a `core_pattern` starting with `|`), which manages storage and lets you retrieve dumps later via `coredumpctl`. Once you have the file, `gdb <binary> <corefile>` loads both the original executable and the memory image, and the single most useful first command is `bt` (backtrace) — the call stack at the exact instant of the crash, which in a well-symbolized build (debug symbols present, not stripped) shows the actual function names and line numbers where the fault occurred, versus raw addresses in a stripped binary that require manual symbol resolution to be useful at all.

### JVM thread dumps: reading a real deadlock

```
"http-nio-8080-exec-3" #47 daemon prio=5 os_prio=0 tid=0x... nid=0x2a13 waiting for monitor entry [0x...]
   java.lang.Thread.State: BLOCKED (on object monitor)
        at com.example.OrderService.reserveInventory(OrderService.java:88)
        - waiting to lock <0x000000076ab12345> (a com.example.InventoryLock)
        - locked <0x000000076ab67890> (a com.example.OrderLock)

"http-nio-8080-exec-7" #51 daemon prio=5 os_prio=0 tid=0x... nid=0x2a17 waiting for monitor entry [0x...]
   java.lang.Thread.State: BLOCKED (on object monitor)
        at com.example.InventoryService.reserveOrder(InventoryService.java:112)
        - waiting to lock <0x000000076ab67890> (a com.example.OrderLock)
        - locked <0x000000076ab12345> (a com.example.InventoryLock)

Found one Java-level deadlock:
=============================
"http-nio-8080-exec-3":
  waiting to lock monitor 0x... (object 0x000000076ab12345, a com.example.InventoryLock),
  which is held by "http-nio-8080-exec-7"
"http-nio-8080-exec-7":
  waiting to lock monitor 0x... (object 0x000000076ab67890, a com.example.OrderLock),
  which is held by "http-nio-8080-exec-3"
```

`jstack <pid>` (or the equivalent, lower-overhead `jcmd <pid> Thread.print`) dumps every live thread's name, state (`RUNNABLE`, `BLOCKED`, `WAITING`, `TIMED_WAITING`), and full stack trace at the instant of capture — and critically, `jstack` explicitly detects lock-cycle deadlocks and prints a "Found one Java-level deadlock" section naming exactly which threads hold which monitors and are waiting on which others, meaning the diagnosis is often already fully done for you in the output, not something you have to reconstruct by manually cross-referencing dozens of thread stacks. The practical read-order under time pressure: search the dump for "deadlock" first (an explicit, fast win if present), then look for threads in `BLOCKED` state waiting on the same lock object address even without a formal cycle (contention, not necessarily deadlock), then look for a large cluster of threads sharing an identical stack trace (the JVM analog of a goroutine leak's diagnostic signature — many threads stuck at the same blocking call usually means one specific downstream dependency is slow or hung, not a code bug in the threads themselves).

### JVM heap dumps: why "retained size" is the number that matters

`jmap -dump:live,format=b,file=heap.hprof <pid>` (or `jcmd <pid> GC.heap_dump filename=heap.hprof`) forces a full GC first (`live` triggers this) then writes every currently-reachable object to a binary `.hprof` file — a genuinely expensive operation on a large heap (multi-GB heaps can mean the dump itself takes tens of seconds to minutes, and older `jmap` full dumps historically paused the application during the dump, which is part of why `jcmd`/newer tooling is now recommended for reduced impact). A cheaper, often-sufficient alternative for a first look: `jmap -histo:live <pid>` prints a live object histogram (class name, instance count, total bytes) without writing a full dump file, frequently enough to spot an obviously runaway allocation (a class with millions of live instances that shouldn't have more than a few thousand) without the cost of a full heap capture. Once you have a full `.hprof`, Eclipse MAT's actual useful workflow is not "browse every object" — it's, in order: the **Leak Suspects Report** (MAT's automated heuristic first pass, often correctly identifying the dominant suspicious retention pattern immediately), the **Histogram** (which classes hold the most aggregate bytes), the **Dominator Tree** (the genuinely important view — it shows, for each object, its **retained size**: the total memory that would be freed if this object became unreachable, which is different from and more useful than an object's own shallow size, because a single small `HashMap` instance retaining millions of cached entries has a tiny shallow size but a massive retained size, and retained size is what actually tells you where the memory is really going), and **Path to GC Roots** (confirming exactly which reference chain — a static field, a `ThreadLocal`, a listener registered and never unregistered — is keeping an object alive when it should have been collected).

### py-spy: reading a live Python process from the outside

```bash
py-spy dump --pid 12345           # every thread's CURRENT Python stack, right now
py-spy record -o profile.svg --pid 12345 --duration 30   # flamegraph, 30s sample
py-spy top --pid 12345            # live top-style view, updates continuously
```

py-spy is written in Rust specifically for this use case: it attaches to a running Python process from outside it (reading the target interpreter's process memory directly via OS-level facilities — `ptrace` on Linux, equivalent mechanisms on macOS/Windows) to reconstruct the current Python-level call stack of every thread, without injecting code, without requiring the target process to have any profiling hooks pre-installed, and — the property that makes it genuinely production-safe — **without pausing or measurably slowing the target process** for a `dump`. This means the workflow for "a worker process appears hung, no logs, no crash" is: run `py-spy dump --pid <pid>` immediately, see every thread's exact current line of Python code, and diagnose without ever restarting the process (which would destroy the exact evidence you need) and without needing to have instrumented the code with profiling decorators in advance. `py-spy record` runs a sampling profiler over a time window and produces a flamegraph, the live-Python equivalent of a JVM CPU profile — useful for "this endpoint is slow, where's the time going" rather than "this process is stuck."

### Continuous profiling: the difference between "point-in-time" and "always recording"

Every tool above shares one limitation: it's a snapshot, and it only helps if you capture it during or immediately after the problem. **Continuous profiling** (Pyroscope, Parca, Google Cloud Profiler) is architecturally different — it runs a low-overhead sampler constantly, in the background, on production traffic, storing compressed profile data continuously so that "what was this service's CPU doing at 3:47am last Tuesday, during the exact latency spike we only noticed the next morning from a dashboard" is an answerable, retroactive query rather than a missed opportunity. The two dominant architectural approaches genuinely differ: **Parca** uses eBPF to sample any process at the kernel level, requiring no per-language SDK or code changes at all, reported at under 1% overhead; **Pyroscope**'s original design uses language-runtime sampling profilers (commonly sampling stacks at 100Hz) requiring a per-language agent/integration, reported at roughly 1-3% overhead, trading a small amount of additional overhead and integration work for richer, language-aware stack detail that a generic eBPF stack walk can have more trouble resolving cleanly (especially in JIT-compiled or heavily optimized code paths). Both are legitimately low enough overhead that real production benchmarks report only a few percentage points of impact on throughput and latency — the actual practical choice is more about fleet composition (a single eBPF collector is operationally simpler across a polyglot fleet of many languages; a language-specific agent can give a Python or JVM team richer frame-level detail) than a clear universal winner.

---

## Build it from scratch

A minimal illustration of the actual failure mode a thread dump diagnoses — a genuine two-lock deadlock — and the exact commands used to capture and read it, worth being able to reproduce and narrate cold:

```java
// untested sketch — deliberately deadlocking two threads via inconsistent lock order
public class DeadlockDemo {
    private static final Object orderLock = new Object();
    private static final Object inventoryLock = new Object();

    public static void main(String[] args) throws InterruptedException {
        Thread t1 = new Thread(() -> {
            synchronized (orderLock) {
                sleep(100);
                synchronized (inventoryLock) {  // t1 wants inventoryLock while holding orderLock
                    System.out.println("t1 done");
                }
            }
        });
        Thread t2 = new Thread(() -> {
            synchronized (inventoryLock) {
                sleep(100);
                synchronized (orderLock) {      // t2 wants orderLock while holding inventoryLock
                    System.out.println("t2 done");
                }
            }
        });
        t1.start(); t2.start();
        // both threads now permanently blocked -- process is HUNG, not crashed,
        // still shows as "alive" to any health check that just pings the port
    }

    private static void sleep(long ms) {
        try { Thread.sleep(ms); } catch (InterruptedException ignored) {}
    }
}
```

```bash
# capture the deadlock while the process hangs:
jps                          # find the PID
jstack <pid> > dump.txt      # or: jcmd <pid> Thread.print > dump.txt
grep -A 20 "Found one Java-level deadlock" dump.txt
```

The equivalent Python illustration — two threads acquiring two `threading.Lock` objects in opposite order, then `py-spy dump --pid <pid>` showing both stacks parked on `acquire()` at the exact conflicting lines (Python's own tooling, unlike jstack, does **not** auto-detect the deadlock cycle for you — you have to read both stacks and reason about the lock order yourself, a real, checkable difference between the two ecosystems' tooling maturity) — belongs in `labs/python/10-prod-debugging/` alongside a from-scratch heap-growth demo (a Python list appended to inside a long-lived object, dumped and inspected) for the memory-leak side of this module.

---

## How it's done in production

| Symptom | Cause | Fix |
|---|---|---|
| A native (C/C++/Rust-extension) process crashes intermittently with no useful log output | Segfault or abort with no core dump captured, because `ulimit -c` defaults to 0 on most systems | Set `ulimit -c unlimited` (or `LimitCORE=infinity` in the systemd unit) before the crash occurs, confirm `kernel.core_pattern` writes somewhere retrievable (or is piped to `systemd-coredump`), then `gdb <binary> <corefile>` and `bt` for the crash-time call stack |
| A JVM service's health check still passes but request latency has climbed to timeout and stayed there | Threads are alive but blocked/deadlocked, not crashed — a `curl /health` that only checks "is the port open" won't detect this | `jstack <pid>` or `jcmd <pid> Thread.print`; search for "Found one Java-level deadlock" first, then for clusters of `BLOCKED` threads on the same lock or identical stack traces pointing at one slow downstream dependency |
| A JVM service's memory grows steadily and eventually OOMs, with no obvious cause in the code | A real memory leak — something is retained that should have been collected (a static collection, an unregistered listener, a `ThreadLocal` never cleared) | `jmap -histo:live <pid>` for a cheap first look at which classes have abnormal instance counts; if needed, a full heap dump (`jmap -dump:live` or `jcmd ... GC.heap_dump`) analyzed in Eclipse MAT's Dominator Tree (retained size, not shallow size) and Path to GC Roots to find the actual holding reference |
| A Python worker process stops making progress, no crash, no error log, restarting "fixes" it temporarily | The process is hung (blocked on a lock, a network call with no timeout, or an infinite loop with no progress) — restarting destroys the exact evidence needed to diagnose it | `py-spy dump --pid <pid>` immediately, before restarting — shows every thread's exact current Python stack with zero instrumentation and no process interruption |
| An endpoint is slow but not hung — requests complete, just take too long | Unclear where time is actually going without instrumentation added in advance | `py-spy record -o profile.svg --pid <pid> --duration 30` for Python (or `async-profiler`/JFR for the JVM) to get a flamegraph over a real sampling window without redeploying with new instrumentation |
| A production incident happened overnight, discovered from a dashboard the next morning, and nobody captured a dump at the time | Every tool above is point-in-time — if you didn't know to capture at 3:47am, the moment is gone | Continuous profiling (Pyroscope or Parca) running always-on in production means the profile data for that exact window already exists and can be queried retroactively, without having needed to predict the incident in advance |
| A full `jmap -dump:live` heap dump on a large production JVM causes a multi-second-to-minute application pause during capture | Full live heap dumps trigger a forced GC and, on older tooling especially, can pause application threads for the dump's duration — expensive on large heaps | Prefer `jmap -histo:live` (a cheap live histogram, no full dump) for a first look; use `jcmd`'s heap dump path (generally lower overhead than legacy `jmap -dump`) when a full dump is genuinely needed; schedule full dumps for low-traffic windows where possible |

---

## Tradeoffs & when NOT to use it

- **Don't reach for a heap dump when the symptom is a hang, not memory growth.** A heap dump answers "what's retaining memory," not "why is nothing progressing" — taking one for a deadlocked-but-not-leaking process wastes the time a thread dump would have resolved in seconds, and on a large heap that wasted time is itself costly (a multi-GB heap dump can take real minutes to capture and load into MAT).
- **Don't leave `ulimit -c` at 0 in production and assume you'll enable it "if needed."** By the time a native crash happens, it's too late to retroactively capture the core dump you didn't have configured — this needs to be a deliberate, advance decision, weighed against the real disk-space cost of potentially large core files on every crash in a system that crashes somewhat regularly.
- **Don't treat a point-in-time capture (any of core/thread/heap dump, or a one-off py-spy run) as a substitute for continuous profiling if incidents recur at unpredictable times.** These tools require you to be present and capturing at the right moment; if the actual pattern is "intermittent slowness nobody can catch in the act," always-on continuous profiling is the correct investment, not repeatedly trying to get lucky with a manual capture.
- **Don't restart a hung process before capturing its state, even under pressure to restore service quickly.** Restarting a hung Python worker or JVM service destroys the exact evidence (`py-spy dump`, `jstack`) that would have taken seconds to capture and would have made the difference between a five-minute root cause and a recurring, never-diagnosed incident — capture first, then restart, unless the outage cost genuinely outweighs ever understanding the cause (a real, defensible tradeoff in some contexts, but a deliberate one, not a default).
- **Don't run continuous profiling everywhere with zero consideration of overhead or storage cost, assuming "it's basically free."** Even at under 1-3% overhead, that's a real, nonzero cost multiplied across an entire fleet, and profile data storage grows continuously — scope continuous profiling deliberately (production services where intermittent, hard-to-reproduce issues are a genuine recurring pain) rather than blanket-enabling it everywhere with no cost/benefit thought at all.

---

## Interview questions

### Q1 — A JVM service's health check passes but latency is at timeout. Walk through your first three commands.
**Testing:** whether tool-to-symptom matching is instant and correct, the core skill this module tests.
**Answer:** First, `jstack <pid>` (or `jcmd <pid> Thread.print`) to capture every thread's current state and stack — a health check that only pings the port won't detect blocked/deadlocked threads. Second, grep the dump for "Found one Java-level deadlock" — jstack auto-detects and names lock cycles explicitly, often resolving the diagnosis immediately if present. Third, if no formal deadlock is reported, scan for clusters of `BLOCKED` threads waiting on the same lock, or many threads sharing an identical stack trace pointing at one slow downstream call, which usually means a single hung dependency rather than a code bug in the threads themselves.
**Follow-up trap:** *"What if jstack itself hangs or the process doesn't respond?"* — that can itself indicate the JVM is in a state where even signal-based dump requests aren't being serviced (extreme GC pressure, or the JVM process itself is stuck at a lower level); at that point a forced thread dump via `kill -3 <pid>` (sends SIGQUIT, which a JVM traps and dumps to stdout/log by default) or, as a last resort, a core dump of the JVM process itself for post-mortem `gdb`/JVM-aware tooling analysis is the fallback.

### Q2 — Explain why `ulimit -c` defaults to 0 on most systems, and what you need to change (and where) to actually get a core dump.
**Testing:** the specific, checkable configuration chain, not just "core dumps exist."
**Answer:** It defaults to 0 specifically to avoid every crash silently consuming disk space with a large memory image, which would be a surprising default behavior in normal operation. To enable it: raise the soft limit with `ulimit -c unlimited` (for a systemd-managed service, set `LimitCORE=infinity` in the unit file instead, since `ulimit` set in an interactive shell won't apply to a service), and separately confirm `kernel.core_pattern` (via `/proc/sys/kernel/core_pattern`, made persistent via `sysctl`) points somewhere retrievable — many modern distributions pipe it to `systemd-coredump`, retrievable later via `coredumpctl`.
**Follow-up trap:** *"If ulimit is set correctly but you still get no core file, what else could be wrong?"* — the process may not have write permission to the `core_pattern` target directory, the filesystem may be full or read-only, or (for a containerized process) the container's own resource limits or a restrictive security profile (seccomp, some container runtimes disabling core dumps by default) can silently suppress it even when the in-process `ulimit` looks correct — containerized core dump configuration is a real, distinct gotcha worth naming.

### Q3 — What does "retained size" mean in a heap dump analysis, and why is it more useful than an object's own (shallow) size?
**Testing:** the specific Eclipse MAT concept that separates real heap-dump competence from having merely opened MAT once.
**Answer:** Shallow size is the memory the object itself occupies (its own fields, not what it points to). Retained size is the total memory that would become collectible if that object became unreachable — meaning the object plus everything it exclusively keeps alive. A small `HashMap` instance with a tiny shallow size can have a massive retained size if it holds millions of cached entries, and it's the retained size, viewed via MAT's Dominator Tree, that actually tells you where memory is going, since shallow size alone would make that same `HashMap` look completely unremarkable.
**Follow-up trap:** *"How do you find WHY that object is still reachable at all, once you've identified it via retained size?"* — MAT's Path to GC Roots feature, run on the suspect object, traces the actual reference chain (a static field, a registered-but-never-unregistered listener, a `ThreadLocal` never cleared) keeping it alive — retained size tells you *what* is leaking, Path to GC Roots tells you *why* it can't be collected.

### Q4 — Why is `py-spy dump` considered safe to run against a production process, and what's the underlying mechanism that makes this true?
**Testing:** the actual technical property, not just "it's a popular tool so it must be safe."
**Answer:** py-spy attaches to the target process from outside it, reading the Python interpreter's memory directly via OS-level process inspection (`ptrace` on Linux and equivalents elsewhere) to reconstruct each thread's current call stack, rather than injecting code into the running process or requiring it to have been started with profiling hooks. Because it's an external, read-only inspection rather than in-process instrumentation, it doesn't pause or measurably slow the target process for a `dump` operation, which is the specific property that makes it safe to run against live production traffic on demand.
**Follow-up trap:** *"Does the same 'safe to attach without cost' property hold for `py-spy record`, which runs continuously over a duration?"* — recording does add sampling overhead since it's repeatedly reading the process's stack over the sampling window (commonly reported as low-single-digit-percent, not literally zero), a real but small cost distinct from `dump`'s effectively-instantaneous single read — worth distinguishing "a one-off dump is essentially free" from "a sustained recording session has a small, nonzero, real cost."

### Q5 — A Python worker process is hung with no crash, no error log. What's wrong with restarting it immediately to restore service, and what should happen first?
**Testing:** the discipline of evidence preservation under incident pressure, a real staff-level judgment call.
**Answer:** Restarting destroys the exact evidence (the hung process's current stack state) that would let you actually diagnose the root cause — after a restart, you're back to "it might happen again" with zero additional information gained. `py-spy dump --pid <pid>` takes effectively no time and no risk to the running process, and should be run before any restart decision, since it costs nothing and provides the only chance to see exactly what the process was doing at the moment of the hang.
**Follow-up trap:** *"What if the outage is customer-facing and every second of downtime has real cost — is capturing evidence still worth the delay?"* — `py-spy dump` takes on the order of milliseconds to seconds, not minutes, so it's essentially never the case that evidence capture meaningfully extends outage duration; the honest, defensible answer is that this specific tradeoff (capture-first-then-restart) is nearly always correct given how cheap the capture is, and choosing to skip it under pressure usually reflects not knowing the tool exists rather than a genuine cost-benefit tradeoff.

### Q6 — Contrast Parca's and Pyroscope's approaches to continuous profiling. What's the actual tradeoff, with real overhead numbers?
**Testing:** whether the candidate can go beyond "there are continuous profiling tools" to the specific architectural difference and its cost.
**Answer:** Parca uses eBPF to sample any process at the kernel level, requiring no per-language SDK or code integration, reported at under 1% overhead. Pyroscope's original design uses language-runtime sampling profilers (commonly ~100Hz sampling) requiring a per-language agent, reported at roughly 1-3% overhead but with richer, language-aware stack-frame detail that a generic eBPF stack walk can sometimes struggle to resolve cleanly, especially in JIT-compiled or heavily optimized code. Both are low enough overhead in practice (real benchmarks report only a few percentage points of throughput/latency impact) that the actual choice is more about fleet composition than a clear efficiency winner.
**Follow-up trap:** *"Which would you pick for a polyglot fleet with Go, Python, and Java services?"* — eBPF-based collection (Parca) is operationally simpler across a polyglot fleet specifically because it avoids maintaining three separate per-language profiling agents and their respective configuration/version-compatibility overhead, though a team already deep in a single-language ecosystem with strong Grafana/Prometheus tooling investment might reasonably prefer Pyroscope for its richer language-specific detail and tighter existing-stack integration — there's a legitimate case either way depending on existing tooling investment, not a universally correct answer.

### Q7 — Why does `jstack` auto-detect and report deadlocks, but the equivalent Python thread-dump tooling (py-spy) does not?
**Testing:** a specific, checkable cross-ecosystem tooling gap — tests real hands-on experience versus surface familiarity with "both languages have dump tools."
**Answer:** The JVM has first-class, structured knowledge of its own `synchronized` monitor locks and can walk the held-by/waiting-for graph across all threads to detect a genuine cycle programmatically, which is exactly what `jstack`'s deadlock detection does. Python's `threading.Lock` (and most Python-level locking primitives) has no equivalent centralized, interpreter-level bookkeeping that a stack-dumping tool like py-spy can query the same way — py-spy shows you every thread's current stack (including that it's blocked in `acquire()`), but reconstructing the actual lock-cycle graph from that requires a human to manually cross-reference which locks each blocked thread is waiting on and which thread currently holds them.
**Follow-up trap:** *"Does this mean Python deadlocks are fundamentally harder to detect than Java ones?"* — harder to detect *automatically* with existing standard tooling, yes, but not fundamentally undiagnosable — the actual reasoning process (find each blocked thread's target lock, find who holds it, check for a cycle) is exactly the same manual process jstack automates away for you in Java; it's a tooling maturity gap specific to this ecosystem, not an inherent limitation of Python's threading model.

### Q8 — When would `jmap -histo:live` be the better first move over a full `jmap -dump:live` heap dump?
**Testing:** cost-awareness and knowing there's a cheaper intermediate diagnostic step, a real production-judgment signal.
**Answer:** `-histo:live` prints a live object histogram (class name, instance count, aggregate bytes) without writing a full `.hprof` file, and is frequently sufficient on its own to spot an obviously runaway allocation (a class with millions of live instances where a few thousand would be expected) — at a fraction of the cost of a full heap dump, which on a large multi-GB heap can take real minutes to capture and load into an analyzer, and historically could pause the application for that duration on older tooling. Reach for the full dump only when the histogram doesn't make the culprit obvious and you genuinely need reference-chain-level detail (Dominator Tree, Path to GC Roots) to find *why* something's retained, not just *what* is large.
**Follow-up trap:** *"What's a case where the histogram alone would be misleading?"* — a leak where many small objects of an unremarkable-looking, widely-used class (say, `String` or a common DTO type) are the actual leak, since a high instance count of a common class is much less immediately suspicious than an unusual custom class dominating the histogram — in that case the aggregate byte count and, more importantly, retained-size analysis via a full dump's Dominator Tree becomes necessary to separate "this class is just widely used everywhere" from "this specific reference chain is holding millions of them alive that should have been collected."

### Q9 — Design the debugging plan for an intermittent production issue that happens roughly once a week, at unpredictable times, and is gone by the time anyone looks.
**Testing:** whether the candidate reaches for continuous profiling as the correct category of tool rather than repeatedly trying manual point-in-time captures.
**Answer:** Every point-in-time tool (core/thread/heap dump, a one-off py-spy run) requires being present and capturing during or immediately after the incident — for a once-a-week, unpredictable-timing issue, that means either getting lucky or setting up alerting tight enough to trigger a capture in the narrow window before the symptom resolves itself, which is fragile. The correct investment is continuous profiling (Pyroscope or Parca) running always-on in production, so that once the next occurrence is noticed (even hours later, from a dashboard), the actual profile data for that exact time window already exists and can be queried retroactively without having predicted it in advance.
**Follow-up trap:** *"What if the issue is a hang/deadlock rather than something CPU-profiling would show, since continuous profilers are typically CPU/memory samplers, not thread-state/lock-cycle detectors?"* — that's a real gap — continuous profiling is excellent for "where is CPU/memory time going," not necessarily for capturing a full thread-dump-style lock-state snapshot at the exact right moment; for a suspected intermittent deadlock specifically, pairing continuous profiling with an automated, alerting-triggered thread dump capture (a script that runs `jstack`/`jcmd` automatically when a latency alert fires) closes that gap better than continuous profiling alone.

### Q10 — A candidate says "I always take a heap dump first when something's wrong with a JVM service, since it gives the most information." What's wrong with this as a default strategy?
**Testing:** whether the candidate can critique a plausible-sounding but wrong default, a real interview trap question in its own right.
**Answer:** A full heap dump is the most expensive of the standard captures (potentially a multi-second-to-minute application impact on a large heap, and historically a full pause on older tooling) and it answers a specific question — what's retaining memory — that's irrelevant if the actual symptom is a hang, a deadlock, or plain CPU-bound slowness with no memory growth at all. Defaulting to the most expensive tool regardless of symptom wastes time and adds unnecessary load to an already-struggling production process; the correct default is diagnosing which category of symptom you have first (crash / hang / memory growth / slow-but-progressing) and picking the cheapest tool that actually answers that specific question.
**Follow-up trap:** *"Is there ever a case where taking a heap dump 'just in case' alongside a thread dump is reasonable, even without clear memory-related symptoms?"* — yes, if the incident is severe enough and re-occurrence risk high enough that you'd rather have both captures than need a second incident to get the one you skipped — but that's a deliberate, cost-aware decision under specific circumstances, not a default "always heap dump first" habit applied without regard to symptom or cost.

---

## Red flags that fail you

- Defaulting to a heap dump for every JVM issue regardless of symptom, without checking whether the actual problem is a hang/deadlock a thread dump would resolve faster and cheaper.
- Not knowing `ulimit -c` defaults to 0, or being unable to name where `core_pattern` output actually goes.
- Restarting a hung process before attempting any point-in-time capture, destroying the only evidence available.
- Confusing shallow size and retained size in heap dump analysis, or not knowing what Eclipse MAT's Dominator Tree actually shows.
- Claiming py-spy requires code instrumentation or a restart — it explicitly requires neither, and that's its entire value proposition.
- Treating continuous profiling and point-in-time dumps as interchangeable, rather than understanding continuous profiling specifically solves the "didn't know to capture at the right moment" problem the others can't.
- Not knowing jstack auto-detects and reports deadlocks explicitly, forcing a manual reconstruction of something the tool already does for you.
- Being unable to give even an approximate overhead number for continuous profiling (sub-1% to low-single-digit percent) when asked whether it's safe to run always-on in production.

---

## Cheat card

```
MATCH SYMPTOM -> TOOL:
  CRASHED (native)  -> core dump + gdb
  HUNG (alive, stuck) -> thread dump (jstack/jcmd; py-spy dump for Python)
  MEMORY GROWTH/OOM -> heap dump (jmap/jcmd) + Eclipse MAT
  SLOW (progressing) -> live profile (py-spy record; async-profiler/JFR on JVM)
  "what happened last Tue 3am?" -> CONTINUOUS profiling (only always-recording one)

CORE DUMP: ulimit -c defaults to 0 (no dump written). `ulimit -c unlimited`
  or systemd `LimitCORE=infinity`. Output location: kernel.core_pattern
  (/proc/sys/kernel/core_pattern), often piped to systemd-coredump
  (retrieve via coredumpctl). gdb <binary> <core> -> `bt` for backtrace
  at crash instant.

JVM THREAD DUMP: jstack <pid> or jcmd <pid> Thread.print (jcmd = current
  recommended, lower overhead). AUTO-DETECTS deadlocks -- search dump for
  "Found one Java-level deadlock" FIRST. States: RUNNABLE, BLOCKED,
  WAITING, TIMED_WAITING. Many threads w/ IDENTICAL stack = one slow
  downstream dependency, not a code bug in the threads themselves.

JVM HEAP DUMP: jmap -dump:live,format=b,file=x.hprof <pid> (or jcmd
  GC.heap_dump) -- forces full GC, expensive on large heaps (mins,
  historically pauses app). CHEAPER first look: jmap -histo:live <pid>
  (live object histogram, no full dump file).
  ECLIPSE MAT workflow: Leak Suspects Report (auto first pass) ->
  Histogram (which classes dominate) -> DOMINATOR TREE (RETAINED size --
  the real answer, not shallow size) -> Path to GC Roots (confirm WHY
  it's held: static field, ThreadLocal, unregistered listener).

PY-SPY: reads process memory from OUTSIDE via OS-level inspection
  (ptrace-equivalent) -- NO instrumentation, NO restart, NO code change.
  `py-spy dump --pid X` = every thread's current Python stack, instantly.
  `py-spy record -o out.svg --pid X --duration 30` = flamegraph.
  `py-spy top --pid X` = live view. Does NOT auto-detect deadlocks
  (unlike jstack) -- Python has no interpreter-level lock-cycle
  bookkeeping to query; manual cross-reference of blocked stacks needed.

CONTINUOUS PROFILING (always-on, query retroactively -- the ONLY one of
  these tools that doesn't require capturing at the right moment):
  Parca: eBPF, kernel-level, ANY process, no SDK, <1% overhead.
  Pyroscope: language-runtime sampling (~100Hz), per-lang agent,
    1-3% overhead, richer language-aware frame detail.
  Real benchmarks: both cost only a few % of throughput/latency --
  choice is about fleet composition (polyglot -> eBPF simpler),
  not a clear efficiency winner.
```

## Sources

- [How to get a core dump for a segfault on Linux — Julia Evans](https://jvns.ca/blog/2018/04/28/debugging-a-segfault-on-linux/) — accessed 2026-08-03
- [Core dump — ArchWiki](https://wiki.archlinux.org/title/Core_dump) — accessed 2026-08-03
- [2 Diagnostic Tools — Oracle Java SE Troubleshooting Guide](https://docs.oracle.com/en/java/javase/21/troubleshoot/diagnostic-tools.html) — accessed 2026-08-03
- [Comprehensive Guide to Heap Dump Analysis — Medium](https://medium.com/@santhoshjsh/comprehensive-guide-to-heap-dump-analysis-ea87de59b24a) — accessed 2026-08-03
- [Diagnosing OOM Error Using Thread and Heap Dumps — Medium](https://medium.com/@santhoshjsh/diagnosing-oom-error-using-thread-and-heap-dumps-bd46321e36c2) — accessed 2026-08-03
- [GitHub - benfred/py-spy: Sampling profiler for Python programs](https://github.com/benfred/py-spy) — accessed 2026-08-03
- [Profiling Python in production with py-spy — Stack Harbor](https://stackharbor.com/en/knowledge-base/python-pyspy-profiling-prod/) — accessed 2026-08-03
- [Pyroscope vs Parca vs Grafana Pyroscope: Which Continuous Profiling Tool in 2026? — DevOpsBoys](https://devopsboys.com/blog/pyroscope-vs-parca-vs-grafana-pyroscope-profiling-2026) — accessed 2026-08-03
- [Continuous profiling in production: A real-world example to measure benefits and costs — Grafana Labs](https://grafana.com/blog/continuous-profiling-in-production-a-real-world-example-to-measure-benefits-and-costs/) — accessed 2026-08-03
- [Compare Parca vs. Pyroscope in 2026 — Slashdot](https://slashdot.org/software/comparison/Parca-vs-Pyroscope/) — accessed 2026-08-03

## Changelog
- 2026-08-03 — created
