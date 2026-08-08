# Rust vs Go vs Python: The Honest Selection Criteria

> **Track:** T20 Rust · **Time:** 1.5h · **Prereqs:** `T20-rust-async`, `T20-rust-perf`, `T11-go-core` · **Updated:** 2026-08-06
> **Module id:** `T20-rust-vs-go` · **Tags:** language-selection, systems, architecture, interview-critical, closing-module

## The 30-second version

Every language moves the same total cost around; the only question is where you want to pay it. Rust charges you at authoring time (55% of Rust developers wait more than 10 seconds for an incremental rebuild, and 45% of people who *stopped* using Rust cited compile times as a reason) and gives you back p99.9 determinism and 2x to 4x lower RSS. Go charges you at runtime in a garbage collector whose stop-the-world pauses are genuinely sub-millisecond (Go's own 2018 SLO was 500 µs per cycle, with a "whisper number" of 100-200 µs) but whose real tail cost is mark assist, not the pause, plus a ~25% GC CPU budget and a heap sized at roughly 2x live; in exchange you get 8-second builds and a hiring pool of 16.4% of professional developers versus Rust's 14.8%. Python charges you at runtime (I measured `json.loads` at 40 MB/s and a 0.85x "speedup" from running two CPU-bound threads on two cores under the GIL) and in operational risk, and gives you back the only mature ML ecosystem on earth. The decision procedure is: start from Python unless a hard constraint kills it, move to Go when concurrency and ops matter more than the last 3x, and move to Rust only when you can name the specific constraint (p99.9 tail, memory per instance, no-GC embedded/kernel target, or an FFI core other languages will call) that nothing else satisfies. PostHog's Django-to-Rust flags rewrite is the honest template: p99 fell 904 ms to 85.4 ms and compute cost fell 68%, but p50 only improved 1.8x, because most of the win came from moving evaluation out of SQL, not from the language.

## Why this gets asked

Because "why did you choose X" is the cheapest available test for whether a candidate reasons about engineering constraints or recites a preference. The interviewer has almost certainly lived through one of three specific failures, and the question is a probe for which one you have also lived through.

Failure one: a team that picked Rust for a CRUD service. The service is beautiful, it uses 40 MB of RSS, and it shipped two quarters late because three of the five engineers had never written Rust, the borrow checker ate a sprint on an ownership graph that would have been a `map[string]*Thing` in Go, and CI went from 90 seconds to 11 minutes so nobody ran the full suite locally any more. Nothing about the service needed Rust. The engineering manager who lived through that asks this question to find out whether you would do it to them again.

Failure two: a Go service that met its p99 SLO for eighteen months and then missed p99.9 after a cache was introduced. The cache was correct, the allocations were low, and the latency spikes appeared every couple of minutes regardless of GOGC tuning, because the collector was scanning a multi-gigabyte live heap and the mark-assist pacer was charging the allocating goroutines for it. This is exactly Discord's Read States story, and the person asking wants to know whether you understand that "Go's GC pauses are sub-millisecond" and "Go's GC broke my tail latency" are both true statements about different parts of the same mechanism.

Failure three: a Python service that scaled fine until it did not. It was I/O-bound so asyncio worked, until someone added a synchronous rerank or a `pandas` transform into a coroutine and the event loop stalled for 400 ms per request, or until the workload genuinely became CPU-bound and the answer was "run 32 processes", each of which loaded its own 1.5 GB model into RAM. For someone whose resume already includes a Java to Python migration, a ClickHouse OOM, and LLM serving on SageMaker, this is the question where you demonstrate that you have opinions about *when the migration is worth it*, not just that you can do one.

The senior signal is refusing to have a favourite. A staff-level answer names the constraint first and the language second, states the counter-argument to its own choice, and quantifies the cost of being wrong.

---

## Lineage: past → present → future

**What came before.** The pre-2010 server-side default was a two-language split with a painful seam: C or C++ for anything that had to be fast, and Perl, PHP, Python, Ruby, or Java for everything else. The pain that killed the C++ half was not performance, it was that memory-safety bugs were unbounded liabilities. Microsoft's Security Response Center reported that roughly 70% of the CVEs they assigned annually from 2006 to 2018 were memory-safety issues, and Google reported the same ~70% figure for Chromium's high-severity bugs. That is not a code-quality problem you can train your way out of; it is a property of the language. The pain that killed the "just use Java" answer for infrastructure was different: HotSpot's JIT could inline through virtual calls better than any ahead-of-time compiler, but you paid warmup time (seconds to minutes before C2 reached peak), deoptimization cliffs, an object header on every allocation, and a garbage collector whose full-GC pauses on multi-gigabyte heaps ran into hundreds of milliseconds. Go was designed at Google in 2007-2009 explicitly against the C++ build-time and complexity pain (Rob Pike's origin story is waiting 45 minutes for a C++ binary to build), and Rust's 1.0 landed in May 2015 explicitly against the memory-safety pain, with ownership and borrowing replacing the runtime GC entirely. Python was never designed against anything; it won by being the language people already knew when NumPy (2006), scikit-learn (2010), and then PyTorch (2016) made it the ML lingua franca, and its costs (the GIL, dynamic dispatch on every attribute access, ~30x to 100x slower than C on scalar code) were accepted because the alternative was writing the numerics twice.

**Where it stands now.** All three are entrenched and none is displacing the others. Go 1.26 (February 2026) turned on the Green Tea garbage collector by default, claiming a 10-40% reduction in GC overhead on GC-heavy programs and a further ~10% on Intel Ice Lake / AMD Zen 4 and newer where it can use vector instructions for scanning small objects; Go 1.27 is at RC1 (released 2026-06-18) with generic methods and a rewritten `json/v2` engine. Rust 1.97.0 shipped 2026-07-09 with 1.97.1 as the current patch, and the ecosystem's centre of gravity for services is `tokio` plus `axum`. CPython's free-threaded build (`3.14t`) is officially supported as of Python 3.14 under PEP 779, with single-threaded overhead down to 1% on macOS aarch64 and 8% on x86-64 Linux from the ~40% of the 3.13 experiment. The live disagreements are real and you should be able to state them. First: whether Go's GC is a solved problem. The Go team's position is that sub-millisecond STW plus a good pacer means latency is no longer the issue; the counter-position, held by everyone running latency-critical caches, is that mark assist and the ~25% GC CPU budget move the cost into the request path where it shows up at p99.9 rather than in a pause you can measure. Second: whether Rust's compile times are a rounding error or a productivity tax. The Rust project's own 2025 compiler performance survey (3,700+ responses) found average build satisfaction of 6/10 and 55% waiting more than 10 seconds per incremental rebuild, which is the project itself conceding the point. Third: whether free-threaded Python changes the calculus for CPU-bound Python at all, given that the ecosystem's C extensions are still catching up and the free-threaded build uses noticeably more memory. Fourth, and least discussed honestly: whether Rust's ML story exists. It does not, for training. `candle` and `burn` are real projects, but PyTorch plus CUDA plus the Hugging Face ecosystem is where every model is written, and pretending otherwise in an interview is disqualifying.

**Where it's heading.** High confidence: the polyglot boundary hardens rather than dissolves. The dominant production shape for the next three years is Python at the top (orchestration, model code, business logic) with Rust underneath at the hot spots, reached through PyO3, and Go in the middle for network services and operators; `pydantic-core`, `tokenizers`, `polars`, `ruff`, and `uv` are all instances of this pattern already shipping, and there will be more. Medium confidence: Go closes most of the remaining latency gap for typical services. Green Tea landing by default in 1.26 with the `GOEXPERIMENT=nogreenteagc` opt-out slated for removal in 1.27 is the Go team committing, and the 10-40% GC overhead reduction is enough to move some services that were considering Rust back off the fence. Medium confidence: Rust's build times improve meaningfully but not by an order of magnitude; LLD became the default linker on `x86_64-unknown-linux-gnu` in Rust 1.90 (September 2025), and the Cranelift codegen backend and parallel frontend are the two initiatives that would actually change the story, but both have been "coming" for years. Speculative, and flag it as such in an interview: free-threaded Python becoming the default. PEP 779's phased plan has the GIL still enabled by default for another 2-3 releases (2026-2027) and disabled by default only in the 2028-2030 window, and that timeline has slipped before. Do not plan a 2027 architecture around it. Also speculative: whether the "rewrite it in Rust" wave has already peaked. The Rust survey's finding that 45% of people who stopped using Rust named compile times suggests the marginal adopter is now hitting the cost side, which is what a plateau looks like from the inside.

---

## Mental model

The whole module reduces to one diagram: every language pays the same bill, at a different time.

```
             WHERE THE COST LANDS
                                                       
  AUTHORING TIME          BUILD TIME          RUN TIME        OPS RISK
  (engineer-hours)        (wall clock)        (CPU/RAM/tail)  (3am pages)
  ---------------------------------------------------------------------
  RUST    ##########      ########            #               #
          ownership,      55% of devs         no GC,          type errors
          lifetimes,      wait >10s per       predictable     are compile
          async colour    incremental         p99.9           errors
                          rebuild
  ---------------------------------------------------------------------
  GO      ###             #                   ####            ##
          small lang,     ~8s for a           GC: 25% CPU     nil panics,
          but verbose     50-KLOC svc         budget, 2x      goroutine
          at scale        (~4 min in Rust)    heap, mark      leaks, data
                                              assist tail     races compile
  ---------------------------------------------------------------------
  PYTHON  #               0                   ##########      #####
          fastest to      none (import        GIL, 40 MB/s    typos ship,
          first draft     time only)          JSON, 30-100x   AttributeError
                                              slower scalar   at 3am
  ---------------------------------------------------------------------

  TOTAL COST IS ROUGHLY CONSTANT. YOU ARE CHOOSING WHICH COLUMN
  YOUR ORGANISATION CAN ABSORB.
```

The second diagram is the decision procedure itself. Run it top to bottom and stop at the first line that fires. If nothing fires, the answer is whatever your team already knows.

```
  START
    |
    +-- Is there a HARD constraint? (answer yes only with a number)
    |     |
    |     +-- No GC allowed (kernel module, embedded, WASM <100 KB,
    |     |   real-time audio/control, cryptographic constant-time)
    |     |        -> RUST (or C). Nothing else qualifies.
    |     |
    |     +-- p99.9 budget < ~5 ms AND live heap > ~1 GB
    |     |        -> RUST. This is the Discord Read States case.
    |     |           Below 1 GB live heap, Go usually holds.
    |     |
    |     +-- Memory per instance is the binding cost
    |     |   (edge/sidecar/1000s of pods, pay-per-MB)
    |     |        -> RUST first, GO second. Python is 5-20x either.
    |     |
    |     +-- Must be linked INTO another language (Python ext,
    |     |   Node native module, JVM via JNI, C ABI library)
    |     |        -> RUST. cdylib + stable C ABI, no runtime to embed.
    |     |           Go's c-shared exists but drags the whole runtime.
    |     |
    |     +-- Workload is model training or research iteration
    |              -> PYTHON. Not a preference. There is no alternative.
    |
    +-- No hard constraint. Now the soft ones:
          |
          +-- Heavy fan-out concurrency, ops-owned, many contributors,
          |   needs to be boring        -> GO
          +-- I/O-bound glue, LLM calls, data work, <5k RPS
          |                              -> PYTHON (asyncio, FastAPI)
          +-- CPU-bound inner loop inside a Python service
          |                              -> PYTHON + RUST via PyO3
          +-- Nothing above fires        -> WHAT THE TEAM ALREADY KNOWS.
                                            This is the correct answer
                                            more often than any other.
```

And the sanity check that keeps you honest, phrased as the thing you say out loud in the interview:

```
  Before choosing Rust, name the constraint and the number.
  "Lower latency" is not a constraint. "p99.9 under 5 ms with a
  12 GB live cache" is. If you cannot state the number, you are
  choosing Rust for aesthetic reasons and you will pay 1-2
  quarters of velocity for it.
```

## How it actually works

Everything measured in this module was run on Python 3.10.12 (x86-64 Linux, 2 vCPU, 3.9 GB RAM) unless stated. Rust numbers marked "measured" come from the sibling module `T20-rust-perf` on rustc 1.97.1 (2026-07-14, `opt-level=3`, 12th Gen Intel Core i5-12450H). Numbers taken from vendors and published retrospectives are attributed inline, because the difference between "I measured this" and "Discord published this" is exactly the distinction an interviewer is listening for.

### Concurrency: three genuinely different machines

This is the section where most candidates hand-wave, and it is the one that separates people who have debugged a stalled event loop from people who have read a blog post.

**Go: goroutines on an M:N work-stealing scheduler.** A goroutine starts with a 2 KB stack (it has been 2 KB since Go 1.4; it was 8 KB before that) that grows by copying and updating pointers, which is why a Go program can hold hundreds of thousands of them where an OS-thread-per-connection design dies at a few thousand (glibc's default thread stack is 8 MiB of virtual address space, and `ulimit -v` or the 47-bit address space becomes the wall long before RAM does). The scheduler is the GMP model: G goroutines, M OS threads, P logical processors where `len(P) == GOMAXPROCS`, which since Go 1.5 defaults to the number of visible CPUs. Each P has a 256-slot local run queue, plus a global queue, plus work-stealing between Ps. Since Go 1.14 the runtime does asynchronous preemption using signals, so a goroutine running a tight loop with no function calls gets preempted after roughly 10 ms instead of hanging the P forever, which was a real and famous class of hang before that. Go 1.26 added `/sched/goroutines` metrics under `runtime/metrics` (counts by state: waiting, runnable, etc.), `/sched/threads:threads`, and a total-created counter, which is the first time the runtime exposed enough to diagnose scheduler starvation without a trace.

The thing to say out loud about Go's model: **the concurrency is invisible in the type system.** `go f()` costs one keyword, blocking is free from the programmer's perspective because the runtime turns a blocking syscall into a park-and-reschedule, and there is no function colouring. That is the single largest ergonomic advantage any of the three has. The price is that goroutine leaks are silent. A goroutine blocked forever on an unbuffered channel is invisible: it consumes 2 KB plus whatever it retains, it never logs, and it keeps its retained heap alive against the GC. Go 1.26 shipped an experimental `goroutineleak` profile (enable with `GOEXPERIMENT=goroutineleakprofile`, exposed at `/debug/pprof/goroutineleak`, contributed by Vlad Saioc at Uber, aiming for default-on in 1.27) that detects the reachability-based subset of these. That the runtime team considered this worth building tells you how common the bug is.

**Rust: poll-based futures on an executor you chose.** A Rust `async fn` compiles to a state machine implementing `Future`, and `Future::poll` is called by an executor. Nothing runs until something polls it: calling `handle(conn, db)` executes zero lines of the body, which is the highest-value contrast for anyone coming from Python (`asyncio.create_task` schedules immediately) or Go (`go f()` puts a goroutine on a run queue immediately). The consequences, in the order they bite people:

1. **Task size is the size of the largest live state across all await points**, computed at compile time. A future holding a 64 KB buffer across an `.await` costs 64 KB per in-flight task, whether or not that buffer is in use. This is why `Box::pin` on large futures is a real optimisation and why moving an allocation to *after* the last await measurably shrinks memory.
2. **`poll` must return promptly and nothing preempts it.** There is no signal-based preemption as in Go 1.14+, no GIL release point as in CPython. A `poll` that computes for 400 ms holds a Tokio worker thread for 400 ms, and with the default multi-thread runtime sizing workers to the CPU count, a handful of these stall the whole service. The mitigation is `tokio::task::spawn_blocking` (which moves the work to a separate, much larger blocking pool) or `tokio::task::yield_now()`. Every Rust async production incident I have read about is a variant of this.
3. **Lost wakeups.** If `poll` returns `Pending` without arranging for `waker.wake()`, the task is silently never polled again. No panic, no log. This is the number-one bug in hand-written `Future` impls, and the second is failing to re-store the waker on every poll (work-stealing may have migrated the task since the last poll, so the old waker wakes the wrong worker; it manifests as a hang that only appears under load).
4. **Function colouring is real and it costs you.** `async fn` and `fn` are different types, `Drop` cannot be async, and trait methods returning futures only became ergonomic with `async fn` in traits. Nobody sensible claims this is free.

**Python: asyncio, and the GIL underneath everything.** CPython's asyncio is a single-threaded event loop over `epoll`/`kqueue`; coroutines are generators, `await` is a yield up the stack to the loop. Measured on this box: **an `await` of an already-ready coroutine costs 161 ns** (300,000 iterations), and **100,000 live `asyncio` tasks cost 213,372 KB of RSS, or 2,185 bytes per task**. Compare that with a Go goroutine's 2 KB initial stack and it is roughly a wash, which surprises people; asyncio's task overhead is not the problem. The problem is that only one of those tasks runs at a time, and any of them can starve the rest.

The GIL wall, measured directly. Two CPU-bound loops of 6,000,000 iterations each, on a 2-core box:

| Execution | Wall time | Speedup |
|---|---|---|
| Serial (one after the other, one thread) | 898 ms | 1.00x baseline |
| Two `threading.Thread` in parallel | 1,062 ms | **0.85x** |

Running two CPU-bound threads on two cores made the program **18% slower than doing the work serially**. That is not a slowdown from contention on a shared data structure; the threads share nothing. It is GIL handoff overhead plus the eval-breaker check. This is the number to quote when someone says "just use threads": on the standard build, for CPU-bound work, threads are strictly negative. The only correct answers on the GIL build are `multiprocessing` (which costs you a full interpreter and a copy of every loaded model per worker), a C extension that releases the GIL (NumPy, `orjson`, `pydantic-core`), or another process in another language.

**The free-threaded situation, treated as live.** PEP 703 designed it; PEP 779 made the free-threaded build *officially supported* in Python 3.14, shipping as a separate `3.14t` binary with `Py_GIL_DISABLED=1`. The current state, from the CPython docs as of 2026-08-05:

- Single-threaded overhead on pyperformance is **about 1% on macOS aarch64 and about 8% on x86-64 Linux**, down from roughly 40% in the 3.13 experimental phase. That 8% is a real tax you pay on every single-threaded workload to get parallelism you may not use.
- Memory is higher, for named structural reasons: `None` is **32 bytes** on the free-threaded build versus **16 bytes** on the default build (the GC header moved into the object header for non-GC objects), all `sys.intern()`ed strings become immortal and never freed, the allocator is mimalloc rather than pymalloc, and QSBR defers frees so RSS lags actual liveness.
- Deallocation timing changes. Biased reference counting, deferred reference counting (module objects, top-level functions, class methods, descriptors, `threading.local`), and per-thread reference counting (heap types, code objects, module `__dict__`) all mean objects are freed later than on the GIL build, sometimes only at the next GC or when the owning thread reaches a safe point. Code that relies on `__del__` firing promptly, or on RSS dropping when a request finishes, will behave differently.
- **The GIL can silently come back.** Importing a C extension that is not marked as free-threading-compatible re-enables the GIL at runtime with a warning. Your service can be running `3.14t` and still be single-threaded because one transitive dependency was not rebuilt. `sys._is_gil_enabled()` is the check, and it belongs in your startup healthcheck, not in a comment.
- Ecosystem readiness is tracked at `py-free-threading.github.io/tracking/` and `hugovk.github.io/free-threaded-wheels/`. Check those before promising anything in a design review.

The honest verdict on free-threading in 2026: it is production-supported and it genuinely gives multi-core Python for pure-Python CPU work (reported ~4x on 4+ core multithreaded workloads, at 15-20% more memory), and it is *not yet* a reason to choose Python for a CPU-bound service, because the 8% single-thread tax, the memory increase, and the "one bad wheel re-enables the GIL" failure mode make it a per-workload experiment rather than a default. PEP 779's own roadmap has the GIL enabled by default for another 2-3 releases and disabled by default only in the 2028-2030 window.

**The one-table comparison** you should be able to draw on a whiteboard:

| | Go goroutines | Rust async (tokio) | Python asyncio |
|---|---|---|---|
| Unit cost | 2 KB initial stack, grows by copy | size of state across awaits, no stack | 2,185 B/task measured |
| Scheduling | preemptive since 1.14 (~10 ms via signals) | cooperative only, no preemption | cooperative only, no preemption |
| Parallelism | true, `GOMAXPROCS` OS threads | true, N worker threads | **none** on GIL build; true on `3.14t` |
| Blocking call in a handler | runtime parks the G, other Gs run | **stalls a worker thread** | **stalls the entire loop** |
| Function colouring | none | yes (`async fn` != `fn`) | yes (`async def` != `def`) |
| Silent failure mode | goroutine leak (invisible) | lost wakeup (task never polled) | sync call in coroutine (loop stall) |
| Diagnostic | `/debug/pprof/goroutine`, 1.26 leak profile | `tokio-console`, `RUSTFLAGS=--cfg tokio_unstable` | `loop.slow_callback_duration`, `asyncio` debug mode |
| Data races | **compile-time detected? No.** `-race` at runtime | **prevented at compile time** (`Send`/`Sync`) | GIL makes most benign; `3.14t` does not |

That last row is the one people misremember. Go's race detector is a *runtime* tool: it instruments memory accesses, costs roughly 5-10x CPU and 5-10x memory, and only finds races on code paths your tests actually execute. Rust's `Send` and `Sync` are compile-time. That difference is not a performance argument, it is a *correctness* argument, and it is the strongest honest case for Rust in a concurrent service, stronger than the latency case for most workloads.

### Latency: what Go's GC actually costs, with the real numbers

The lazy version of this argument is "Go has a GC so it has pauses". That is roughly a decade out of date and an interviewer who knows Go will end the conversation there. Here is the accurate version, sourced from the Go team's own material.

Go's collector is a **concurrent, non-generational, non-moving, tri-colour mark-sweep** collector over size-segregated spans, with the write barrier **on only during a GC cycle**. Rick Hudson's ISMM 2018 keynote is the primary source and gives the actual trajectory of stop-the-world pause times, measured by Brian Hatfield on a Twitter production server:

| Go release | Date | STW pause on that production workload |
|---|---|---|
| pre-1.5 | before Aug 2015 | 300-400 ms |
| 1.5 | Aug 2015 | 30-40 ms |
| 1.6 | Feb 2016 | 4-5 ms |
| 1.6.3 | mid 2016 | under 10 ms consistently (SLO met) |
| 1.7 | Aug 2016 | sub-10 ms on an **18 GB heap** |
| 1.8 | Mar 2017 | **sub-millisecond** (removed STW stack re-scanning) |
| 1.9 | Aug 2017 | "SLO whisper number around 100-200 µs" |

Go's stated 2018 SLO was **500 µs stop-the-world per GC cycle**, a heap at **2x live**, and GC CPU capped at **25%** of `GOMAXPROCS`. So yes: the pauses are genuinely sub-millisecond, and have been for nine years.

**And yet Discord's Read States service had latency spikes every two minutes.** Read the post rather than citing it from memory, because what it actually says is more specific and more useful than the meme. Discord's service kept billions of Read States, with an LRU cache of tens of millions of entries per server and hundreds of thousands of cache updates per second, backed by Cassandra. The spikes were every ~2 minutes because Go's runtime **forces a GC at least every 2 minutes** regardless of heap growth (`forcegcperiod`, in `runtime/proc.go`). Crucially, they said the spikes were large "not because of a massive amount of ready-to-free memory, but because the garbage collector needed to scan the entire LRU cache in order to determine if the memory was truly free from references." They tuned `SetGCPercent` on the fly and it did nothing, because they were not allocating fast enough to trigger more frequent collection. They shrank the LRU cache, which made the spikes smaller and **made p99 worse** because of the extra database loads, and they shipped that compromise and lived with it for a long time.

That is the mechanism you need to be able to explain: **the cost is proportional to the live heap being scanned, not to the garbage being collected.** A large, long-lived, pointer-rich in-memory cache is the pathological case for Go, and it is pathological in a way that GOGC tuning cannot fix. The three levers and what they actually do:

- `GOGC` (default 100) sets the heap growth target: collect when the heap reaches (1 + GOGC/100) x live. Lowering it collects more often with a smaller heap (more CPU, less RAM); raising it to 200-400 is a standard, cheap win for allocation-heavy services with RAM to spare.
- `GOMEMLIMIT` (Go 1.19+) is a **soft** limit that makes the collector work harder as you approach it rather than OOMing. The idiomatic modern configuration for a containerised service is `GOGC=off` plus `GOMEMLIMIT` set to roughly 90% of the container limit. Note "soft": if live heap genuinely exceeds it, you get a GC death spiral (100% GC CPU, no forward progress) rather than a clean OOM, which is arguably worse to debug.
- The **mark assist** is the part nobody mentions and the part that actually hurts. The pacer charges an allocating goroutine mark work proportional to its allocation. So the GC cost does not appear as a pause; it appears as *your request handler running slower*, distributed across the goroutines that allocate most. That is why the symptom is a p99.9 regression with no visible pause in the trace, and why "our STW is 200 µs" and "the GC broke our tail" are both true.

Then there is the argument that matters most and is least known, and it comes from Go's own keynote: **the tyranny of the nines.** If your GC latency SLO is "99% of cycles under 10 ms", and a user session makes 100 server requests, then only **37%** of users get a consistently sub-10ms experience across the whole session (0.99^100 = 0.366). To get 99% of *users* under that bar you need the **99.99th percentile**, not the 99th. This is why an argument that stops at p99 is an argument that has not engaged with the problem, and it is the single best thing to quote in a system design round, because it is Google's own framing of why they rebuilt the collector.

Go 1.26's Green Tea collector is the current state: enabled by default, targeting better locality and CPU scalability when marking and scanning small objects, with an expected **10-40% reduction in GC overhead** on GC-heavy programs and a further **~10%** on Ice Lake / Zen 4 and newer via vector instructions for small-object scanning. The opt-out (`GOEXPERIMENT=nogreenteagc`) is expected to be removed in 1.27. This narrows the gap; it does not close it, because the mechanism (scan the live heap) is unchanged.

**Rust's side of the ledger, honestly.** No GC means no mark assist and no whole-heap scan, so the tail is determined by your own code plus the allocator. It does not mean "no latency spikes". The real sources of Rust tail latency are: `malloc` under contention (swapping in `mimalloc` or `jemallocator` as `#[global_allocator]` routinely wins 10-30% on allocation-heavy multithreaded workloads, per the measurements in `T20-rust-perf`), a synchronous call inside an async handler stalling a worker, lock convoys on a `Mutex` held across an `.await` (a bug the type system does *not* prevent, though `tokio::sync::Mutex` versus `std::sync::Mutex` is the distinction to know), page faults on first touch, and the same TLB and cache effects everyone has. The claim you should make is precise: **Rust removes one specific, large, hard-to-control source of tail variance and leaves all the others in place.**

Real production numbers from a published retrospective, PostHog's Django-to-Rust feature-flag rewrite (October 2025), which is more useful than any benchmark because it reports p50 as well as p99:

| Percentile | Django | Rust + axum | Improvement |
|---|---|---|---|
| p50 | 21.7 ms | 11.8 ms | 1.8x |
| p90 | 160 ms | 31.2 ms | 5.1x |
| p95 | 381 ms | 42.9 ms | 8.9x |
| p99 | 904 ms | 85.4 ms | **10.6x** |

Compute: **~500k requests/minute on ~300 pods at ~$8.8k/month** became **the same ~500k req/min on ~90 pods at ~$2.8k/month**, a 68% cost reduction to 32% of the resources. Their synthetic benchmark had axum at **~32k req/s versus Django's ~1.5k**, a 21x gap that did *not* materialise as 21x in production. Read the shape of that table: **the median barely moved (1.8x) and the tail collapsed (10.6x)**, and the post is explicit that they also moved flag evaluation out of SQL into memory, added application-level cohort caching, and deleted PgBouncer. A senior candidate says: most of that win is architectural, the language enabled the architecture (in-memory parallel evaluation across cores is not available to a GIL-bound Django worker) and contributed the tail determinism and the timeout primitives, and attributing all 10.6x to "Rust is fast" would be dishonest.

### Memory footprint per service

Order of magnitude is the right resolution here; anyone quoting three significant figures for "a web service" is quoting a hello-world.

| Runtime | Bare process RSS | Typical small service RSS | Notes |
|---|---|---|---|
| Rust (axum + tokio) | ~2-5 MB | ~10-30 MB | no runtime beyond the binary; static musl builds ship in a ~5-15 MB scratch image |
| Go (net/http) | ~4-8 MB | ~20-60 MB | GC keeps roughly 2x live heap resident by default; `GOMEMLIMIT` bounds it |
| Python (uvicorn + FastAPI) | **17.3 MB measured** (bare `python3`) | ~80-200 MB per worker | I measured a bare 3.10 interpreter at 17,312 KB, and +10,720 KB after importing a modest stdlib set (`asyncio`, `http.client`, `sqlite3`, `ssl`, `xml.etree`) |

The Python numbers are the ones that bite, for a structural reason: **you multiply by worker count.** A GIL-bound Python service that needs 8 cores runs 8 processes, and each one pays the full interpreter, the full import graph, and its own copy of anything preloaded. If those workers each hold a 400 MB embedding model or a warmed tokenizer, you are at 3.2 GB for one pod to use 8 cores, where the Go or Rust equivalent is one process. That, not raw throughput, is why memory-bound Python services get expensive: my measured **500 Python threads cost 9,356 KB of RSS (about 19 KB each resident)**, which is cheap, but 500 threads buy you no CPU parallelism at all under the GIL, so the comparison that matters is 8 *processes*, not 8 threads.

Per-object overhead, measured on 3.10: `sys.getsizeof(None)` is 16 bytes, an `int` is 28 bytes, an empty `dict` is 64 bytes, an empty `list` is 56 bytes. A Rust `struct UserId(u64)` with `#[repr(transparent)]` is 8 bytes; `size_of::<Vec<T>>()` is 24 bytes and `size_of::<&[T]>()` is 16. A Go `[]byte` header is 24 bytes and an `interface{}` is 16. Ten million small records is a rounding error in Rust, a manageable heap in Go, and an OOM in Python.

And the throughput number worth memorising because it comes up in every data-pipeline discussion: I measured **`json.loads` on a 1,514 KB payload of 20,000 objects at 38.7 ms, i.e. 40.0 MB/s**. `orjson` is typically 2-5x that because it is Rust underneath; `serde_json` in release mode is commonly reported in the 300 MB/s to 1 GB/s range depending on shape. If your service's job is to parse a lot of JSON, the language *is* the architecture.

### Compile times and the iteration-speed tax

This is the cost Rust advocates routinely undersell, so state it with the Rust project's own data. The **Rust compiler performance survey 2025** collected 3,700+ responses:

- Average satisfaction with build performance: **6 out of 10**, mode 7.
- **55% of respondents wait more than 10 seconds** for an incremental rebuild after a small code change, on the project that pains them most.
- **~45% of respondents who said they had stopped using Rust** cited long compile times as at least one reason.
- **~20%** say clean builds are a significant blocker; of the 1,495 who build Rust in CI, **~25%** call CI build performance a big blocker, and **~36% of those** use no CI caching at all.
- **87%** rely on inline editor annotations as their primary error mechanism, and **~33%** consider waiting for those annotations a big blocker; **>35%** say Rust Analyzer and Cargo blocking each other on the build lock is a big problem.
- **~42% have never tried any build-performance mitigation.**

The mechanism, from the sibling module `T20-rust-perf`: monomorphisation. One 8-line generic function instantiated over 200 concrete types produced **10,847 lines of LLVM IR and a 536 ms clean rebuild**, versus **5,690 lines and 169 ms** for the single `dyn` instantiation: **3.17x compile time and 1.28x `.rlib` size** for one small function. Scale that across `serde`, `tokio`, `reqwest`, and a few derive-heavy crates and you get the observed reality that a 50-KLOC Rust service takes on the order of **4 minutes** to build clean where an equivalent Go service takes about **8 seconds**. The borrow checker is not the culprit; it is typically single-digit percent of build time. It is monomorphisation plus LLVM plus linking.

What has actually improved, with dates: **LLD became the default linker for `x86_64-unknown-linux-gnu` in Rust 1.90** (announced 2025-09-01), which is the single biggest default-path win in years because linking is the one phase that is never incremental. Dropping `debug` from full to `line-tables-only` is worth **2-30% in cycle counts** per the project's own perf runs. `cargo llvm-lines` finds the monomorphisation offenders, and the thin-generic-wrapper refactor (keep the type-parameterised surface tiny, push the body into a non-generic inner function) is the standard fix. `sccache`, `mold`, splitting large crates, and cutting default features are the rest of the toolbox.

Why it matters more than the raw number suggests: iteration speed is compounding. A 10-second edit-compile-test loop and a 90-second one are not 9x apart in productivity, they are on opposite sides of the threshold where an engineer stays in flow versus switches to Slack. This is the honest version of the "Rust makes you slower" claim, and it is not about the borrow checker, which most engineers are productive with inside 2-3 months. It is about the loop.

Go's counter-position is deliberate and structural: no header files, no template instantiation, explicit imports with no cycles, a dead-simple type system, and a compiler written to be fast rather than to produce the fastest code. Go pays for it in generated code quality (Go's compiler does far less inlining and no autovectorisation worth the name, so hot scalar loops in Go commonly run 2-5x slower than the Rust equivalent) and in expressiveness at scale, which is the next section. Python pays nothing at build time and everything at runtime, which is why it wins the first week of any project and can lose the second year.

### Hiring and team throughput as a first-class engineering constraint

Treating "can we staff this" as a non-engineering concern is the single most common junior mistake in a system design round. It is a constraint with a number attached, exactly like a latency budget.

Stack Overflow's 2025 Developer Survey (89,000+ respondents) on languages used in the past year: **Python 57.9%, Java 29.4%, Go 16.4%, Rust 14.8%**, with JavaScript at 66%+. Rust has been the **most admired language for ten consecutive years (72% in 2025)**, which measures desire, not supply. The two facts together are the whole argument: lots of people *want* to write Rust, roughly one in seven has written any in the past year, and the number who have shipped and operated a production Rust service is far smaller than that.

The counter-argument, which you should raise yourself before the interviewer does, is Google's data: Lars Bergstrom (Director of Engineering) reported at Rust Nation UK 2024 that in every measured case, rewriting a C++ service in Rust cut the effort to build and maintain it by **more than 2x**, that retraining time from C++ to Rust was comparable to Java to Kotlin, and, importantly for this module, that **Go and Rust teams finished the same rewrite task at the same speed** while the C++ team took twice as long. That last clause is the honest one and it is usually omitted when this study is quoted. Google's finding is that Rust beats C++ on productivity; it is *not* that Rust beats Go.

So the defensible framing:

| Constraint | Rust | Go | Python |
|---|---|---|---|
| Candidates available | scarcest of the three | moderate | largest pool by a wide margin |
| Time to first useful PR | 4-8 weeks typical | 3-7 days (the language is small on purpose) | day one |
| Time to competent | ~2-3 months, and Google reports comparable to Java to Kotlin | ~2-4 weeks | ongoing (the language is easy, the ecosystem is not) |
| Review cost | high early (lifetimes, `unsafe`, async) then low | low and uniform | low per-PR, high in aggregate because types are optional |
| Bus factor risk | real: one Rust expert on a team of five is a single point of failure | low | low |
| What the compiler buys the team | data races, use-after-free, null, and most refactoring hazards are compile errors | nil panics and races are runtime | nothing without mypy/pyright, and even then optional |

The senior move in an interview is to make the last row load-bearing. Rust's cost is front-loaded onto a small number of engineers; its benefit is spread across everyone who ever refactors the service. That trade is excellent for a component with a 5-year life and a stable team, and terrible for a service whose requirements will be rewritten twice in eighteen months by whoever is on-call.

### Ecosystem maturity by domain

Averages are useless here. Go domain by domain.

| Domain | Rust | Go | Python |
|---|---|---|---|
| HTTP services | mature (`axum`, `actix-web`, `tokio`, `tower`) | **best in class**; `net/http` in stdlib is production-grade | mature (`FastAPI`, `Starlette`); needs a process manager |
| gRPC | good (`tonic`), some rough edges | **reference implementation**, gRPC-Go is the canonical one | good (`grpcio`), C-extension heavy |
| Kubernetes / cloud-native | growing (`kube-rs`) | **overwhelming**: k8s, etcd, Docker, Prometheus, Terraform, Consul are all Go | client libraries only |
| Data / analytics | strong and rising (`polars`, `arrow-rs`, `datafusion`) | weak | **dominant** (pandas, PySpark, Arrow, DuckDB bindings) |
| ML training | **effectively nonexistent** for real work | nonexistent | **the only answer**: PyTorch, JAX, HF |
| ML inference serving | strong for the serving layer, none for the kernels | usable as a proxy/router tier | **dominant**: vLLM, TGI, TensorRT-LLM are Python-fronted |
| CLI tools | **best in class** (`clap`, single static binary, `ripgrep`/`fd`/`bat`/`uv`/`ruff`) | excellent (`cobra`, single static binary) | poor distribution story; `uv`/`pipx` help but a Python CLI needs Python |
| Embedded / no_std | **only viable safe option** | no (needs a runtime and a GC) | MicroPython exists, is not the same thing |
| WASM | **best in class**, `wasm32-unknown-unknown` is first-class | possible; TinyGo or a large `syscall/js` binary | Pyodide, tens of MB |
| Databases / storage engines | strong and growing (TiKV, Neon, ScyllaDB's Rust driver, S3 ShardStore) | strong (etcd, InfluxDB, CockroachDB, Dolt) | wrappers only |
| Cryptography | strong (`ring`, `RustCrypto`), used in production TLS stacks | strong; stdlib `crypto/*` is excellent and Go 1.26 added `crypto/hpke` and post-quantum hybrid KEMs on by default in TLS | wrappers around C |
| Observability | improving (`tracing`, OTel) but less mature | **best** (pprof is built in, OTel is native) | good (OTel), but profiling is weaker |

The row that decides most AI-engineering architectures is "ML training" and "ML inference serving". If your service loads a model and runs it, Python is where the model is, and any argument that ends in "so we rewrote the inference server in Rust" needs to explain how it calls into CUDA kernels that only have Python bindings. The realistic Rust role in ML serving is the *layer around* the model: request batching, routing, tokenisation (`tokenizers` is Rust already), admission control, and the KV-cache-aware proxy. That is a genuinely good use of Rust and it is what you should propose, rather than proposing to replace vLLM.

### FFI and polyglot boundaries

This is where the "pick one language" framing dies, and where a principal engineer earns the title.

**Rust into Python via PyO3** is the highest-leverage pattern in the industry right now, and the evidence is that it has already happened to your dependency tree: `pydantic-core`, `tokenizers`, `polars`, `orjson`, `cryptography`, `ruff`, and `uv` are all Rust behind a Python API. The mechanics: `maturin` builds the wheel, `#[pyfunction]` and `#[pymodule]` define the surface, and crucially `py.allow_threads(|| ...)` releases the GIL for the duration of the Rust computation, which is how a Rust extension gives a GIL-bound Python process real parallelism. The costs are real: you now have a build matrix (`manylinux`, macOS x86-64 and aarch64, Windows), a second language in CI, and a per-call boundary cost of roughly 100-200 ns for a trivial call plus whatever conversion your arguments need, which means the boundary must be *coarse*. Calling into Rust once per request to process 10,000 rows is excellent. Calling into Rust 10,000 times per request is worse than pure Python.

**Rust into anything via the C ABI** is the general case: `crate-type = ["cdylib"]`, `#[no_mangle] pub extern "C"`, and `cbindgen` to generate the header. This works for Node (via napi-rs), the JVM (via JNI or the newer FFM API), Go (via cgo), Ruby, and C++. Rust is uniquely good at this among the three because **it has no runtime to initialise**: no GC to start, no interpreter to embed, no scheduler that assumes it owns the process.

**Go's FFI story is the weak one** and you should know why. Calling C from Go via cgo means crossing from a goroutine stack to a system stack, which historically cost hundreds of nanoseconds per call and is why "cgo is not Go" became a proverb; Go 1.26 reduced the baseline cgo call overhead by **~30%**, which is a meaningful improvement but does not change the shape. In the other direction, `-buildmode=c-shared` produces a library that drags the entire Go runtime, including its GC and its scheduler and its signal handlers, into the host process, which conflicts badly with anything else that wants signals. Embedding Go into Python is a thing people do once.

**Python's FFI** is the C API (fastest, most painful, and now has a free-threading variant to support), `ctypes` (slowest, no build step), and `cffi` (the sane middle). The important 2026 detail is that a C extension not explicitly marked free-threading-compatible **re-enables the GIL** on `3.14t`, which makes ecosystem readiness a hard dependency of any free-threading plan.

The practical architecture that falls out, and the one to draw when asked "how would you build this":

```
   +--------------------------------------------------+
   |  PYTHON  (orchestration, model code, business)   |
   |  FastAPI / LangGraph / PyTorch                   |
   +--------------------------------------------------+
        |  PyO3, coarse-grained calls, GIL released
        v
   +--------------------------------------------------+
   |  RUST  (hot kernels: parse, rank, tokenize,      |
   |  vector math, anything called >10k times/req)    |
   +--------------------------------------------------+

   +--------------------------------------------------+
   |  GO  (the network tier: gateways, sidecars,      |
   |  k8s operators, high-fan-out fetchers)           |
   +--------------------------------------------------+
        |  gRPC / HTTP over the wire. NOT FFI.
        v                 ^
   ------------------------
   Rule: cross language over a NETWORK boundary by default.
   Cross via FFI only when the call is hot enough that a
   network hop dominates, and then make the boundary coarse.
```

## Build it from scratch

The deliverable of this module is not code, it is a procedure you can run out loud in a design round in under three minutes. Write it down, run it against a service you have actually shipped, and check whether it reproduces the decision you made.

**Step 1. Write the constraint as a number, or admit there is not one.** Not "it needs to be fast". One of: a p99.9 budget in milliseconds, a memory ceiling per instance in MB, a throughput floor in RPS with an instance count, a binary size ceiling, a startup-time ceiling (cold start), or a compliance/target constraint (no GC, `no_std`, kernel, WASM). If you cannot fill in a number, skip to Step 6.

**Step 2. Check the hard disqualifiers.** These are the only cases where the choice is forced.

```
no GC allowed (kernel, embedded, hard-real-time, constant-time crypto)  -> Rust or C
must be a native extension loaded into another runtime                  -> Rust
p99.9 < ~5 ms with a live heap in the GBs                               -> Rust
model training or research iteration                                    -> Python
Kubernetes controller / operator / CNI / CSI plugin                     -> Go (the ecosystem is Go)
```

**Step 3. Estimate the runtime cost gap, and be suspicious of it.** Rough, defensible multipliers for *service* code, not microbenchmarks: Go is typically within **1x to 3x** of Rust on throughput for I/O-bound HTTP work (both are usually bound by syscalls, TLS, and the database), and **2x to 5x** slower on hot scalar or allocation-heavy loops. Python is typically **10x to 100x** slower than either on pure-Python CPU work and **roughly comparable** on work that is 95% inside NumPy or a C extension. Then apply the correction that most people skip: multiply by the fraction of wall time your service actually spends in your code. If 80% of your p99 is Postgres and the LLM call, a 20x faster language buys you 0.8x to 1.0x on the metric that matters.

**Step 4. Price the team cost.** Engineers on the team who have shipped production code in the candidate language, divided by team size. Below 40%, add one quarter of ramp to your estimate and name it in the design doc. Below 20%, the choice is a bet on hiring, and you should say so in those words.

**Step 5. Price the iteration cost.** Estimate the edit-compile-test loop. Above ~60 seconds, budget for the behavioural consequence (people stop running tests locally) and plan the mitigations up front: `cargo check` in the editor, `sccache`, LLD or `mold`, `debug = "line-tables-only"`, splitting the workspace, and CI caching. Recall that ~36% of Rust developers who call CI build time a big blocker are not caching at all, which means a meaningful fraction of the complaint is self-inflicted and fixable.

**Step 6. If nothing above fires, choose what the team already runs.** This is the correct answer more often than any other, and saying it confidently is a stronger signal than any technical argument in this module. The counter-argument, which you should acknowledge: a team that only ever picks what it already knows never acquires a capability it will eventually need, so the right frame is portfolio-level. Introduce a new language on a small, self-contained, non-critical-path service first (which is exactly what Discord did with Read States: "small and self-contained"), and only then on something load-bearing.

**Step 7. Write down the falsification condition.** "We chose Rust because our p99.9 must be under 5 ms with a 12 GB cache. If, after the Go prototype, p99.9 comes in under 4 ms, we use Go." A decision with no falsification condition is a preference.

A useful drill: score three services you have shipped against this and see how many would have come out differently. If the procedure retroactively endorses every choice you have ever made, you have written a rationalisation, not a procedure.

## How it's done in production

The two retrospectives worth knowing cold, with their caveats intact, because the caveats are what the follow-up questions target.

**Discord, Go to Rust, Read States (ported May 2019, published February 2020).** What the post actually says, beyond the headline: the service tracks per-user-per-channel read state, billions of them, with tens of millions cached per server in an LRU and hundreds of thousands of updates per second. Latency spiked every ~2 minutes. The cause was the forced-GC interval combined with the collector having to scan the whole LRU cache to prove liveness. `SetGCPercent` tuning did nothing. Shrinking the cache reduced spikes but raised p99 via cache misses. The Rust port matched Go's latency **with only basic optimisation**, then beat it on latency, CPU and memory after three specific changes: `BTreeMap` instead of `HashMap` in the LRU for memory, a metrics library using modern Rust concurrency, and fewer memory copies. Afterwards they raised the cache to **8 million Read States** and reported average times in **microseconds** with max @mention latency in **milliseconds**. The upgrade from tokio 0.1 to 0.2 gave a further CPU reduction for free.

Now the caveats, which are the interesting part and which most people who cite this post have never read. The Go version was **Go 1.9.2**, and they note they tried 1.8, 1.9 and 1.10 with no improvement; that is a 2017-2018 collector, before the sub-millisecond STW work fully landed and eight releases before `GOMEMLIMIT` existed. They committed to **nightly Rust** for async, and explicitly framed that as an acceptable-risk bet consistent with having previously adopted Elixir, React Native and Scylla early, backed by an engineering culture of fewer than 50 engineers serving 250M+ users. And footnote 2 says, in the authors' own words, "To be clear, we don't think you should rewrite everything in rust just because." If an interviewer cites Discord at you, the highest-value response is to cite footnote 2 back.

**PostHog, Django to Rust, feature flags (October 2025).** Covered numerically above. The parts to internalise: they explicitly evaluated **async FastAPI** (rejected: easiest migration, limited performance gain, still no good timeout primitives) and **Node with HyperExpress** (rejected: C++ binding, 1.3k-star project, maintenance risk) before choosing Rust plus axum. They cite **code-level timeout primitives** as a decisive factor, not raw speed, which is a reliability argument rather than a performance one. They also deleted PgBouncer and moved evaluation out of SQL in the same change, so the language and the architecture are confounded. They reported zero flag outages in the three months after migration, and then appended a footnote linking to the postmortem for the outage they had the week the post went up, which is the most honest sentence in either retrospective.

**The third case, which is the one nobody publishes: the successful non-migration.** Most services that considered Rust and stayed on Go or Python were right to. There is no blog post about it, which systematically biases the literature you are quoting from. Say this in an interview. It is the most senior sentence available on this topic.

### Failure-mode table: how language *selection* fails

| Symptom | Cause | Fix |
|---|---|---|
| Feature velocity drops ~40-60% for 1-2 quarters after a Rust rewrite; PR cycle time doubles; the same two engineers review everything | Team-competence cost was never priced. 2 of 7 engineers are fluent; the rest self-censor rather than ship code in a language they are shaky in | Do not rewrite. Extract only the hot component (the PyO3 or gRPC boundary), keep the rest. If already committed: pair-program, mandate `#[deny(clippy::pedantic)]` off, buy training, and accept the quarter explicitly in the roadmap rather than pretending |
| CI wall time went 90 s to 11 min; developers stop running the full suite locally; regressions reach staging | Monomorphisation plus LLVM plus linking, with no caching. ~36% of Rust teams that complain about CI build time use no cache at all | `sccache` or the Cargo cache action; LLD (default on `x86_64-unknown-linux-gnu` since 1.90) or `mold`; `debug = "line-tables-only"` (2-30% cycles); `cargo llvm-lines` then the thin-generic-wrapper refactor; split the workspace; `cargo check` in the editor with a separate target dir so Rust Analyzer and Cargo stop fighting over the build lock |
| Go service meets p99 for months, then misses p99.9 after adding a cache. No visible STW pause in the trace. Spikes roughly every 2 minutes | Mark assist plus whole-live-heap scanning. `forcegcperiod` triggers a GC at least every 2 min regardless of allocation rate; cost is proportional to live heap, not garbage. This is Discord's exact bug | First: raise `GOGC` to 200-400 or set `GOMEMLIMIT` near the container limit with `GOGC=off`. Then: get the cache off the Go heap (`freecache`/off-heap arena, or an external Redis/memcached) so there are no pointers for the collector to trace. Only if both fail is the language the problem |
| Go service pegs 100% CPU in GC, makes no forward progress, never OOMs | `GOMEMLIMIT` is a **soft** limit and live heap exceeded it. The collector runs continuously trying to reach a target it cannot reach | Set `GOMEMLIMIT` with headroom (~90% of container limit) *and* keep a real memory limit so the container is killed and restarted instead of thrashing. Alert on `/gc/cycles/total:gc-cycles` rate, not just on RSS |
| Python service p99 is 20x p50, with the spike uncorrelated with load | A synchronous call inside a coroutine (a `requests` call, a `pandas` transform, a sync DB driver) stalling the single event loop for every concurrent request | `asyncio` debug mode plus `loop.slow_callback_duration = 0.1` to find it; move it to `run_in_executor`/`asyncio.to_thread`; ban sync clients in the async path via a lint rule |
| Python service saturates one core; adding threads makes it slower; adding processes multiplies memory by N | The GIL. Measured: 2 CPU-bound threads on 2 cores ran at **0.85x** of serial. Processes are the only parallelism on the standard build, and each pays a full interpreter plus a copy of every preloaded model | In order: move the hot loop into NumPy/`orjson`/`pydantic-core` (C or Rust that releases the GIL); then a PyO3 extension with `py.allow_threads`; then a separate service in Go or Rust. Consider `3.14t` only after checking every C extension on the free-threading trackers and adding `sys._is_gil_enabled()` to the healthcheck |
| Service on `3.14t` shows no multi-core speedup and single-thread throughput is 8% worse than before | One transitive C extension is not marked free-threading-compatible, so the runtime re-enabled the GIL at import with a warning nobody read. You are now paying the free-threaded overhead for zero parallelism | Assert `sys._is_gil_enabled() is False` at startup and fail hard; bisect imports to find the offender; pin to the GIL build until its wheel lands |
| A Rust rewrite improved p99 10x but p50 barely moved, and leadership expected the benchmark's 21x | The benchmark measured the framework; production measures the database, TLS, and the network. Amdahl applies to language choice like everything else | Before the rewrite, measure the fraction of p50 and p99 spent in *your* code. Promise improvements only on that fraction. PostHog's own numbers (1.8x at p50, 10.6x at p99, against a 21x synthetic) are the reference shape |
| Rust async service has one endpoint that intermittently hangs all other requests under load | A blocking call, a long CPU loop, or a `std::sync::Mutex` held across an `.await` inside a handler. There is no preemption; the worker thread is gone until `poll` returns | `tokio-console` to find the task with high poll duration; `spawn_blocking` for blocking work; `yield_now()` in long loops; `tokio::sync::Mutex` when a guard must cross an await, and prefer restructuring so it does not |
| "We'll use Go for everything" org hits a wall on the data/ML platform | Go has effectively no data-frame, numerical or ML ecosystem. The wall is not performance, it is that the libraries do not exist | Accept the polyglot boundary. Go for the network tier, Python for data and models, gRPC between them. Fighting this costs more than the boundary does |

## Tradeoffs & when NOT to use it

### When NOT to use Rust (the section that matters)

Most services do not need Rust, and choosing it can be a net negative for the business. Concretely:

**Do not use Rust when the service is dominated by I/O you do not control.** If p99 is 40 ms of which 34 ms is Postgres and an outbound HTTP call, the theoretical ceiling of a rewrite is a 15% improvement, and you will spend two quarters to get it. Compute this number before the design review, not after.

**Do not use Rust when requirements are still moving.** Rust's cost curve is front-loaded: you pay to get the ownership model right, and you are rewarded when the code stops changing. A service whose data model will be rewritten twice this year inverts that trade. Python's dynamism is genuinely the right tool for the first six months of an uncertain product, and pretending otherwise is dogma.

**Do not use Rust when fewer than roughly 40% of the team can review it.** Code that only two people can review is code with a bus factor of two and a review queue of one. This is the failure that actually kills teams, not compile times.

**Do not use Rust for a Kubernetes operator, a CNI plugin, a Prometheus exporter, or anything else where the entire ecosystem is Go.** You will reimplement client-go badly. The library gravity is a stronger force than the language's merits.

**Do not use Rust for ML training or for the model layer of inference.** The kernels are CUDA with Python bindings. Rust's role in ML serving is the layer around the model, not the model.

**Do not use Rust because the p99 is bad when you have not checked whether the p99 is bad for a GC reason.** Most bad tails are a slow query, a missing index, a retry storm, an unbounded queue, a cold cache, or a noisy neighbour. Rust fixes none of those.

**Do not use Rust when startup time or deployment simplicity is the constraint and you have not measured.** Rust wins cold start comfortably (a static binary starting in single-digit milliseconds versus a JVM's hundreds), but a Go binary starts just as fast, so this is rarely a Rust-versus-Go discriminator.

The strongest single argument against Rust for a typical service, stated plainly: **you will pay roughly one to two quarters of team velocity, and you will get back a constant-factor improvement on a metric that is probably not your bottleneck, plus a class of bug (data races, use-after-free) that Go's runtime and Python's GIL already made rare in practice for your workload.** If you cannot articulate why that trade is positive for *this* service, it is not.

The honest counter-argument, which you should give equal time: the compile-time and hiring costs are one-time and amortising, while the safety and determinism benefits accrue for the life of the service. Google's data shows Rust cutting effort by 2x versus C++ and matching Go. `ripgrep`, `uv`, `ruff` and `polars` did not win because Rust is fashionable; they won because a 10x to 100x tool is a different product. If your component is genuinely long-lived infrastructure with a stable spec (a proxy, a storage engine, a parser, a tokenizer, a codec), the trade flips and Rust is straightforwardly correct.

### When NOT to use Go

**Not for CPU-bound numerical work.** Go's compiler does far less inlining than LLVM and essentially no autovectorisation; the experimental `simd/archsimd` package arrived in Go 1.26 behind `GOEXPERIMENT=simd`, is amd64-only, and is explicitly not stable. Hot scalar loops in Go run commonly 2-5x slower than Rust and cannot be rescued the way Rust's can.

**Not when the live heap is large, pointer-rich, and latency-critical.** That is the Discord case and the mechanism has not changed even with Green Tea.

**Not when you need real expressiveness at scale.** Go's deliberate minimalism becomes a tax in large codebases: generics arrived only in 1.18 (2022), generic *methods* only in 1.27 (2026), the error-handling story is still `if err != nil` at every call site, and there are no sum types, so "this is either A or B" is modelled with an interface plus a type switch that the compiler cannot check for exhaustiveness. The counter-argument, which is strong: this minimalism is exactly why a new hire is productive in a week and why every Go codebase looks the same. Reasonable senior engineers land on opposite sides of this and you should present it that way.

**Not for data science, ML, or anything numerical.** The libraries do not exist.

### When NOT to use Python

**Not when the work is CPU-bound and cannot be pushed into a C or Rust extension.** The measured 0.85x from threading is the whole argument.

**Not when memory per instance is the binding constraint**, because the GIL forces a process-per-core multiplication of the interpreter and every preloaded artefact.

**Not for anything you must distribute as a binary to users who do not have Python.**

**Not when the operational risk of dynamic typing exceeds your tolerance.** This is the underrated one. A typo in a rarely-taken error branch is a `NameError` at 3 a.m. in production. Strict `mypy`/`pyright` plus Pydantic at the boundaries closes most of it, and if you are running Python at scale without those you are choosing the risk, not inheriting it.

**And the counter-argument, which is decisive more often than the rest of this module combined:** for the overwhelming majority of AI and backend services, Python is *fast enough*, ships fastest, hires easiest, and puts you inside the only ecosystem where the models actually live. The correct default is Python, with Rust surgically applied at the hot spots and Go where the operational ecosystem demands it. A candidate who reaches that conclusion by reasoning, having genuinely considered the alternatives, reads as senior. A candidate who reaches it by habit reads as junior. The reasoning is the deliverable.

### The verdict by workload

| Workload | First choice | Defensible second | Do not |
|---|---|---|---|
| CLI tool, distributed to users | **Rust** (single static binary, `clap`, and the fastest tools in the category are all Rust) | Go (equally good distribution, faster to write) | Python (distribution is the whole problem) |
| Internal web service / CRUD API | **Go**, or Python if the team is Python | Rust only with a named constraint | Rust by default |
| High-fan-out gateway / proxy / sidecar | **Go** (goroutines make fan-out trivial) or **Rust** if memory per pod or p99.9 binds | either | Python |
| Data pipeline, batch | **Python** (PySpark, pandas, Arrow) | Rust for a specific hot transform via PyO3 or a DataFusion job | Go (no libraries) |
| Data pipeline, streaming, high volume | **Rust** or **Go** at the ingest/transform tier | Python with `orjson` + `polars` if volume is moderate | pure-Python row-at-a-time |
| ML training | **Python**. There is no second choice | none | anything else |
| ML inference serving | **Python** for the model tier (vLLM, TGI), **Rust** for the surrounding tier (router, batcher, tokenizer, admission control) | Go for the routing tier | Rust for the kernels |
| Systems software (storage engine, DB, kernel, hypervisor) | **Rust** (Firecracker, S3 ShardStore, TiKV, Linux kernel modules) | Go for higher-level infra (etcd, CockroachDB) | Python |
| Embedded / `no_std` / real-time | **Rust**. The only safe option with no runtime | C | Go, Python |
| Kubernetes operator / cloud-native plugin | **Go**. Non-negotiable, the ecosystem is Go | none | Rust (you will rewrite client-go) |
| WASM in the browser or at the edge | **Rust** | Go via TinyGo, with caveats | Python (Pyodide is tens of MB) |
| Agentic AI / LLM orchestration | **Python** (the SDKs, the frameworks, the eval tooling) | TypeScript | Rust or Go, unless you are building the serving substrate |

---

## Interview questions

### Q1 — We're building a new internal service. Rust, Go, or Python?

**Testing:** whether you ask for constraints before answering. This is a trap question and the wrong move is to pick.

**Answer:** "Default Python unless something disqualifies it, because it ships fastest and hires easiest, and for an internal service those usually dominate. To move off that default I need a number: a p99.9 budget, a memory ceiling per instance, a throughput floor, or a target that has no runtime. Give me the traffic shape and the SLO and I'll tell you. If it's a Kubernetes-adjacent component I'd say Go without hesitating, because the ecosystem is Go and I'd otherwise reimplement client-go badly."

**Follow-up trap:** "Assume no constraints at all. Now pick." The trap is that "it depends" twice in a row reads as evasion. Commit: "Then it's whatever the team already runs, because the switching cost is real and the benefit is zero by construction. If the team is Python and the service is I/O-bound, Python with FastAPI, strict pyright, and Pydantic at the boundaries."

### Q2 — Go's GC pauses are sub-millisecond. So why did Discord move to Rust?

**Testing:** whether you know that STW pause and GC latency cost are different things.

**Answer:** "Both are true. Go's STW has been sub-millisecond since 1.8 in March 2017, and Go's own 2018 SLO was 500 µs per cycle with a whisper number of 100-200 µs. Discord's problem wasn't the pause. They had tens of millions of Read States in an LRU cache per server, and the collector had to trace that entire live heap to prove it was reachable. The forced-GC interval fires at least every 2 minutes regardless of allocation rate, so they got a spike every 2 minutes. `SetGCPercent` did nothing because they weren't allocating fast enough for it to matter. The cost is proportional to live heap scanned, not garbage freed, and it lands as mark assist charged to the allocating goroutines, which is why it shows up as a p99.9 regression rather than a pause in the trace."

**Follow-up trap:** "That post is from 2020. Does it still apply?" Partly, and saying so is the point. Their Go version was **1.9.2**; `GOMEMLIMIT` did not exist until 1.19, and Green Tea shipped by default in 1.26 with a claimed 10-40% GC overhead reduction. The mechanism (scan the live heap) is unchanged, so the conclusion holds for large pointer-rich caches, but a 2026 team should first try `GOMEMLIMIT` plus moving the cache off-heap before concluding they need a rewrite. Also cite footnote 2 of the post: Discord themselves wrote "we don't think you should rewrite everything in rust just because."

### Q3 — Compare the three concurrency models.

**Testing:** depth. Most candidates say "goroutines are lightweight threads and asyncio is single-threaded" and stop.

**Answer:** Give the three machines. Go: M:N work-stealing scheduler, G/M/P, 2 KB initial goroutine stack grown by copying, 256-entry local run queues, `GOMAXPROCS` defaults to CPU count, asynchronous signal-based preemption since 1.14 at roughly 10 ms, no function colouring, blocking is free from the programmer's view. Rust: poll-based futures compiled to state machines; nothing runs until polled; task size equals the largest live state across await points; **no preemption at all**, so a 400 ms `poll` holds a worker thread for 400 ms; `Send`/`Sync` make data races a compile error. Python: single-threaded event loop over epoll; I measured 2,185 bytes per asyncio task and 161 ns per await of a ready coroutine; the GIL means CPU-bound threads do not scale, and I measured two threads on two cores at 0.85x of serial, i.e. slower than not threading.

**Follow-up trap:** "Which one detects a blocking call in a handler?" None of them, automatically, and the failure modes differ: Go's runtime parks the goroutine so a blocking *syscall* is fine, but a tight CPU loop before 1.14 hung the P; Rust stalls one worker thread; Python stalls the entire process. The tooling answers are `tokio-console` for Rust, `asyncio` debug mode with `loop.slow_callback_duration` for Python, and `runtime/trace` plus the new 1.26 `/sched/goroutines` metrics for Go.

### Q4 — Is the GIL still a problem in 2026?

**Testing:** whether you track the free-threading rollout accurately or repeat headlines.

**Answer:** "Yes, for the default build, and the free-threaded build is officially supported but not the default. PEP 703 designed it, PEP 779 made `3.14t` officially supported in 3.14. Single-thread overhead is about 1% on macOS aarch64 and 8% on x86-64 Linux, down from ~40% in the 3.13 experiment. Memory is higher for structural reasons: `None` is 32 bytes instead of 16, interned strings are immortal, the allocator is mimalloc instead of pymalloc, and QSBR defers frees. The failure mode I'd guard against is that importing a C extension not marked free-threading-compatible silently re-enables the GIL at runtime, so you pay the overhead and get no parallelism. I'd assert `sys._is_gil_enabled() is False` at startup."

**Follow-up trap:** "So should we plan to move our CPU-bound service to free-threaded Python next year?" No, and the reason is a roadmap fact: PEP 779's phased plan has the GIL enabled by default for another 2-3 releases through 2026-2027, and disabled by default only in the 2028-2030 window. Do not architect against a default that does not exist yet. Check `py-free-threading.github.io/tracking/` for your actual dependency set and treat it as a per-workload experiment.

### Q5 — Our Go service just missed its p99.9 SLO. Walk me through what you do.

**Testing:** whether you reach for tuning before rewriting.

**Answer:** In order. First confirm it is GC at all: `GODEBUG=gctrace=1`, `runtime/metrics` for `/gc/pauses:seconds` and cycle rate, and check whether the spikes correlate with GC cycles or with something else (a slow query, a retry storm, an unbounded queue, a noisy neighbour). If it is GC: raise `GOGC` from 100 to 200-400, or better, set `GOMEMLIMIT` to ~90% of the container limit with `GOGC=off`. Then attack the live heap, because that is what the collector scans: get large caches off the Go heap entirely, reduce pointer density (values and indices instead of pointers, `[]T` instead of `[]*T`), and check `runtime/pprof` heap profiles for retained objects. Confirm you are on Go 1.26 for Green Tea's 10-40%. Only after all of that is the language the problem.

**Follow-up trap:** "You set `GOMEMLIMIT` and now the service pegs 100% CPU and never recovers." That is the GC death spiral: `GOMEMLIMIT` is a **soft** limit, so if live heap genuinely exceeds it the collector runs continuously chasing a target it cannot reach, and you never get a clean OOM. Fix: keep a real container memory limit so the pod is killed and restarted, alert on GC cycle *rate* rather than RSS, and treat `GOMEMLIMIT` as a pacing hint, not a guarantee.

### Q6 — Justify a Rust rewrite to a VP who wants features shipped.

**Testing:** whether you can talk about engineering cost in business terms, and whether you would even make the argument.

**Answer:** "Usually I'd argue the other side. The honest cost is one to two quarters of reduced feature velocity while the team ramps, plus a longer CI loop, in exchange for a constant-factor improvement on a metric that is often not the bottleneck. I'd only bring this proposal if I had three numbers: the fraction of p99 spent in our own code, the instance-count or cost reduction (PostHog got 300 pods to 90 and $8.8k/month to $2.8k for identical traffic), and the fraction of the team that could review it. And I'd propose extracting the single hot component rather than rewriting the service, because that gets most of the benefit at a fraction of the risk."

**Follow-up trap:** "The benchmark says 21x. Why are you only promising 2x?" Because the benchmark measures the framework and production measures the database, TLS, and the network. PostHog's own synthetic was axum ~32k req/s versus Django ~1.5k, a 21x, and the production result was 1.8x at p50 and 10.6x at p99. Amdahl applies to language choice. Promise improvement only on the fraction of latency that is actually your code, and say which fraction that is.

### Q7 — When is Rust the wrong choice? Be specific.

**Testing:** the single highest-signal question in this module.

**Answer:** Give five, fast, with mechanisms. (1) I/O-dominated services, because a 20x faster language on 15% of the latency buys 3%. (2) Requirements still moving, because Rust's cost is front-loaded onto getting the ownership model right and is repaid only when the code stops changing. (3) Fewer than ~40% of the team can review it, so the review queue becomes one person. (4) Anything Kubernetes-adjacent, because the ecosystem gravity is Go and you will reimplement client-go badly. (5) ML training and the model layer of inference, because the kernels are CUDA with Python bindings.

**Follow-up trap:** "So you're anti-Rust?" No, and having the counter-argument ready is the actual test. Rust's costs are one-time and amortising; its benefits accrue for the service's life. Google reported >2x effort reduction rewriting C++ services in Rust, and, importantly, that Go and Rust teams finished the same task at the same speed, so the study supports Rust over C++ and not Rust over Go. For long-lived infrastructure with a stable spec (proxy, storage engine, parser, tokenizer, codec) Rust is straightforwardly correct, and `ripgrep`, `uv`, `ruff` and `polars` are the proof.

### Q8 — Your Python inference service is CPU-bound. Options?

**Testing:** whether you escalate in cost order or jump to a rewrite.

**Answer:** Cheapest first. (1) Confirm it is really CPU-bound in *Python* rather than in a C extension already: `py-spy top --native` for a few minutes. (2) Move the hot loop into something that releases the GIL: NumPy, `orjson`, `pydantic-core`. (3) If it is bespoke logic, a PyO3 extension with `py.allow_threads`, keeping the boundary coarse (once per request over 10k rows, never 10k calls). (4) Process-based parallelism, accepting the memory multiplication. (5) Only then a separate service in Go or Rust behind gRPC. (6) Evaluate `3.14t` as an experiment, after checking every C extension for free-threading wheels.

**Follow-up trap:** "Why not just add threads?" Because on the GIL build they make it worse. I measured two CPU-bound threads on two cores at 1,062 ms against 898 ms serial: **0.85x**, an 18% regression, from GIL handoff and eval-breaker overhead alone. Threads in Python help only when the work releases the GIL, which means I/O or a C extension.

### Q9 — Compare memory footprint across the three for the same service.

**Testing:** whether you know why, not just what.

**Answer:** "Order of magnitude: Rust and Go are both single-digit to low-tens of MB for a small service, with Go typically 2-4x Rust because the collector keeps roughly 2x live heap resident by default. Python is the outlier and the reason is structural, not per-object: a GIL-bound service that needs 8 cores runs 8 processes, and each pays the full interpreter plus every preloaded artefact. I measured a bare 3.10 interpreter at 17.3 MB and +10.7 MB after a modest set of stdlib imports. If each worker also holds a 400 MB model, you're at 3.2 GB for one pod to use 8 cores."

**Follow-up trap:** "Doesn't `fork` share memory copy-on-write?" Initially, yes, but CPython's reference counting writes to the object header on every access, so shared pages get dirtied and copied almost immediately. `gc.freeze()` before forking helps by moving long-lived objects out of the GC's generational lists, and immortal objects in 3.12+ help more, but the practical answer is to assume little sharing and measure PSS rather than RSS.

### Q10 — Two languages benchmark within 10% of each other. Now what?

**Testing:** whether you can articulate that performance is often the least important axis.

**Answer:** "Then performance is not the deciding factor and I stop talking about it. The remaining axes, in the order I'd weight them: who can review it (bus factor), ecosystem gravity for this domain, operational tooling (Go's built-in pprof and native OTel versus Rust's improving-but-younger `tracing`), iteration speed, and what failure modes the compiler eliminates. That last one is where Rust's real argument lives: `Send`/`Sync` make data races a compile error, whereas Go's `-race` is a runtime detector that costs 5-10x CPU and only finds races on paths your tests exercise."

**Follow-up trap:** "You said benchmarks don't matter, but you quoted a lot of numbers." The distinction is production retrospectives versus benchmark-game numbers. The benchmarks game measures hand-tuned microbenchmarks by different authors with different effort budgets and generalises badly. PostHog's p50/p90/p95/p99 table under identical production traffic is a measurement of the thing you care about. Cite the second kind and be explicit about which kind you are citing.

### Q11 — Design the inference-serving stack for a multi-tenant LLM product. Language choices and why?

**Testing:** whether you apply the framework to your actual domain rather than reciting it.

**Answer:** "Python for the model tier because vLLM, TGI and TensorRT-LLM are where continuous batching and paged attention actually live, and rewriting that is not a serious proposal. Rust for the tier around the model: the router, admission control, the KV-cache-aware load balancer, tokenisation, and request/response streaming, because that tier is CPU-bound, latency-sensitive, memory-per-pod sensitive, and has a stable spec, which is exactly Rust's profile. Note that `tokenizers` is already Rust, so half of this argument is already true in your stack. Go for the control plane, the operator, and anything talking to Kubernetes. Cross language over gRPC, not FFI, except at the tokenizer where PyO3 already does it."

**Follow-up trap:** "Why not Rust for the model tier too, since candle and burn exist?" Because they exist and are not where the models are. Every new architecture ships as PyTorch with CUDA kernels; the Rust ML crates lag by months to years and lack the operator coverage. The honest framing is that Rust's ML story is real for *inference of a fixed, simple model* on CPU or a narrow accelerator path, and absent for general serving of frontier models. Saying otherwise in an interview is disqualifying.

### Q12 — What would make you reverse a language decision after the fact?

**Testing:** intellectual honesty and whether you write falsifiable design docs.

**Answer:** "I write the falsification condition into the design doc. For a Rust choice: if the Go prototype's p99.9 comes in under the SLO, we use Go. Post-launch, the reversal triggers I'd watch are PR cycle time doubling and staying doubled after two months, review concentrating on fewer than three people, CI wall time crossing about 10 minutes without a caching fix available, and the measured production improvement coming in under half of what was promised. Any two of those and I'd escalate rather than sink cost."

**Follow-up trap:** "You're two quarters in and three of those fired. Do you actually revert?" Usually no, and pretending otherwise is naive: reverting costs another quarter and burns the team's confidence. The realistic move is to stop *expanding* the footprint, freeze the Rust component at its current scope, ship new work in the language the team is fluent in, and staff a second reviewer onto the Rust component. Containment beats reversion. Say that out loud, because it is what actually happens.

### Q13 — How do compile times affect a team's ability to ship, quantitatively?

**Testing:** whether you treat build time as an engineering metric or a gripe.

**Answer:** "The Rust project's own 2025 compiler performance survey, 3,700+ responses: average build satisfaction 6/10, 55% waiting over 10 seconds per incremental rebuild, ~20% blocked by clean builds, ~25% of CI users blocked by CI build time, and about 45% of people who *stopped* using Rust cited compile times. The mechanism is monomorphisation plus LLVM plus linking, and the sibling measurement is that 200 instantiations of one 8-line generic function cost 3.17x the compile time of a single `dyn` version. The behavioural consequence is the real cost: past roughly 60 seconds, engineers stop running the full suite locally and defects move to CI or staging."

**Follow-up trap:** "So is it improving or not?" Both, and be specific. Improving: LLD became the default linker on `x86_64-unknown-linux-gnu` in Rust 1.90 (September 2025), which matters because linking is the one phase that is never incremental; `line-tables-only` debuginfo is worth 2-30% in cycles; Rust Analyzer got 15-20% from PGO. Not improving fast: the two changes that would be transformative, the Cranelift codegen backend and the parallel frontend, are both still project goals rather than stable defaults, and the project itself says large structural changes need concentrated effort and funding it does not have. Note also that ~42% of respondents have tried no mitigation at all, so part of the complaint is self-inflicted.

### Q14 — What's the strongest argument *against* the position you just took?

**Testing:** the staff-level question. Interviewers ask it to see whether you hold positions or are held by them.

**Answer, if you argued for Rust:** "That most of my gain is architectural, not linguistic. PostHog got 10.6x at p99 but only 1.8x at p50, and in the same change they moved evaluation out of SQL, added cohort caching and deleted PgBouncer. A disciplined Go or even Python rewrite with the same architecture would have captured a large share of that. I should test the architecture change first, in the current language, before attributing the win to Rust."

**Answer, if you argued for Go or Python:** "That I'm optimising for the next two quarters and this component will outlive them. Compile-time and hiring costs are one-time; the safety and determinism benefits compound over the service's life, and the class of bug Rust eliminates (data races, use-after-free) is exactly the class that takes days to diagnose at 3 a.m."

**Follow-up trap:** "Then how do you decide?" With a falsification condition and a small first bet. Extract the smallest self-contained component, ship it in the candidate language, measure the promised metric against the promised number, and measure PR cycle time on that component versus the rest of the repo. That is exactly what Discord did (Read States was chosen because it was "small and self-contained"), and it is what makes the decision reversible instead of a one-way door.

## Red flags that fail you

- "Rust is just better." Any unqualified superiority claim ends the conversation. So does "Go is a toy language" and "Python doesn't scale."
- Citing the benchmarks game as evidence about production. Different authors, different effort budgets, hand-tuned microbenchmarks. Cite production retrospectives.
- Citing Discord without knowing it was **Go 1.9.2**, in **2019**, or without knowing footnote 2 says not to rewrite everything in Rust.
- "Go has GC pauses so the tail is bad." Sub-millisecond since 1.8, March 2017. If you cannot say "mark assist" and "live heap scanning," you do not know why Discord's tail was bad.
- "Free-threaded Python removed the GIL, so Python is parallel now." The GIL build is still the default, the free-threaded build costs ~8% single-threaded on x86-64 Linux, and one non-compatible C extension silently turns the GIL back on.
- Proposing a rewrite without having measured what fraction of latency is in your own code.
- Ignoring hiring and review capacity, or calling them "not engineering concerns."
- Proposing Rust for ML training, or claiming `candle`/`burn` are ready to replace PyTorch.
- Proposing Rust or Python for a Kubernetes operator.
- Never stating a counter-argument to your own position.
- Answering "it depends" twice without ever committing to a recommendation.
- Quoting Google's "Rust is 2x more productive" without the clause that Go and Rust teams finished the same task at the same speed.

## Cheat card

```
COST LOCATION:  Rust = authoring+build | Go = runtime GC + expressiveness | Py = runtime + ops risk
GO GC:          concurrent tri-colour, NON-generational, NON-moving. Write barrier on only during GC.
GO STW:         300-400ms (pre-1.5) -> 30-40ms (1.5) -> 4-5ms (1.6) -> sub-ms (1.8, Mar 2017)
GO SLO 2018:    500 us STW/cycle | heap 2x live | GC CPU <= 25% | whisper number 100-200 us
GO REAL COST:   mark assist (charged to allocating goroutine) + scan of LIVE heap, not garbage
GO FORCED GC:   at least every 2 min regardless of allocation (forcegcperiod) <- Discord's spikes
GO KNOBS:       GOGC=100 default (collect at 2x live) | GOMEMLIMIT (1.19+) is SOFT -> death spiral risk
GO 1.26:        Green Tea GC default, 10-40% less GC overhead, +10% on Ice Lake/Zen 4; cgo -30% overhead
TYRANNY OF 9s:  99% of GC cycles <10ms => only 37% of 100-request sessions are consistently <10ms
GOROUTINE:      2 KB initial stack | GMP, 256-slot local runq | async preemption since 1.14 (~10ms)
RUST ASYNC:     poll-based, inert until polled, NO preemption. 400ms poll = 400ms dead worker thread.
RUST SAFETY:    Send/Sync = data races are COMPILE errors. Go's -race is runtime, 5-10x CPU.
PYTHON GIL:     measured 2 CPU threads / 2 cores = 0.85x of SERIAL (898ms -> 1062ms)
PYTHON ASYNCIO: measured 2,185 B/task (100k tasks) | 161 ns per await of ready coroutine
PYTHON MEM:     bare 3.10 interpreter 17.3 MB | +10.7 MB stdlib imports | json.loads = 40.0 MB/s
FREE-THREAD:    3.14t, PEP 703 + PEP 779. 1% (macOS arm64) to 8% (x86-64 Linux) single-thread cost.
                None = 32 B vs 16 B. Bad C ext silently RE-ENABLES GIL. Check sys._is_gil_enabled().
                GIL default-off not before 2028-2030.
RUST BUILD:     55% wait >10s incremental | 45% of quitters cited compile time | satisfaction 6/10
                200 monomorph instantiations = 3.17x compile time vs 1 dyn | 50-KLOC: ~4 min vs Go ~8 s
                LLD default on x86_64-linux-gnu since 1.90 | line-tables-only = 2-30% cycles
HIRING (SO'25): Python 57.9% | Java 29.4% | Go 16.4% | Rust 14.8% | Rust most admired 72%, 10 yrs
GOOGLE DATA:    Rust >2x less effort than C++; Rust and Go finished the SAME task at the SAME speed
POSTHOG:        p50 1.8x | p90 5.1x | p95 8.9x | p99 10.6x (904->85.4ms) | 300->90 pods | $8.8k->$2.8k
                synthetic was 21x (32k vs 1.5k rps). Architecture, not just language.
DISCORD:        Go 1.9.2, ported May 2019. Cache scan, not pause. Footnote 2: don't rewrite just because.
VERSIONS:       Rust 1.97.1 (2026-07) | Go 1.26 (Feb 2026), 1.27 at RC1 | Python 3.14 / 3.14t
DECISION RULE:  name the constraint AND the number, or default to what the team already runs.
```

## Sources

- [Go 1.26 Release Notes](https://go.dev/doc/go1.26) — accessed 2026-08-05
- [Go 1.27 Release Notes](https://go.dev/doc/go1.27) — accessed 2026-08-05
- [Getting to Go: The Journey of Go's Garbage Collector (Rick Hudson, ISMM 2018 keynote)](https://go.dev/blog/ismmkeynote) — accessed 2026-08-05
- [A Guide to the Go Garbage Collector](https://go.dev/doc/gc-guide) — accessed 2026-08-05
- [Why Discord is switching from Go to Rust](https://discord.com/blog/why-discord-is-switching-from-go-to-rust) — accessed 2026-08-05
- [Python support for free threading (CPython 3.14 HOWTO)](https://docs.python.org/3/howto/free-threading-python.html) — accessed 2026-08-05
- [PEP 703: Making the Global Interpreter Lock Optional in CPython](https://peps.python.org/pep-0703/) — accessed 2026-08-05
- [PEP 779: Criteria for supported status for free-threaded Python](https://peps.python.org/pep-0779/) — accessed 2026-08-05
- [Announcing Rust 1.97.0](https://blog.rust-lang.org/2026/07/09/Rust-1.97.0/) — accessed 2026-08-05
- [Rust compiler performance survey 2025 results](https://blog.rust-lang.org/2025/09/10/rust-compiler-performance-survey-2025-results/) — accessed 2026-08-05
- [The LLD linker is now the default on x86_64-unknown-linux-gnu (Rust 1.90)](https://blog.rust-lang.org/2025/09/01/rust-lld-on-1.90.0-stable/) — accessed 2026-08-05
- [Stack Overflow Developer Survey 2025: Technology](https://survey.stackoverflow.co/2025/technology) — accessed 2026-08-05
- [PostHog: How we made feature flags even faster and more reliable](https://posthog.com/blog/even-faster-more-reliable-flags) — accessed 2026-08-05
- [py-free-threading: compatibility tracking for free-threaded Python](https://py-free-threading.github.io/tracking/) — accessed 2026-08-05
- [Rust developers at Google are twice as productive as C++ teams (Lars Bergstrom, Rust Nation UK)](https://www.theregister.com/2024/03/31/rust_google_c/) — accessed 2026-08-05
- [PyO3 user guide: parallelism and releasing the GIL](https://pyo3.rs/) — accessed 2026-08-05

## Changelog

- 2026-08-06 — created. Track T20 closing module. Go GC numbers taken from the Go team's own ISMM 2018 keynote and the 1.26 release notes; Python concurrency and memory numbers measured locally on 3.10.12 (x86-64 Linux, 2 vCPU) and labelled as such; Rust compile-time numbers from the Rust project's 2025 compiler performance survey and from the sibling module `T20-rust-perf` on rustc 1.97.1.
