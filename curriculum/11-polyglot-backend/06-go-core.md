# Go: Goroutines, Channels, Select, Context, Generics, the Memory Model, pprof

> **Track:** T11 Polyglot Backend · **Time:** 3h · **Prereqs:** T16-io-models · **Updated:** 2026-08-03
> **Module id:** `T11-go-core` · **Tags:** go

## The 30-second version

Goroutines are cheap (a few KB starting stack, grown/shrunk dynamically by the runtime, versus a platform thread's ~1-8MB) because they're scheduled M:N by Go's own runtime scheduler onto a small number of OS threads (`GOMAXPROCS`, defaulting to logical CPU count and, since Go 1.25, container-aware by default rather than reading the host's full CPU count inside a cgroup-limited container) — this is the same cheap-thread bet Java's virtual threads made years later, and Go's version has been production-proven since 2012. Channels are the idiomatic synchronization primitive ("don't communicate by sharing memory; share memory by communicating"), but they are not automatically safe from leaks or deadlocks: a goroutine blocked forever on a channel send or receive with no other goroutine ever able to complete the matching operation is a **goroutine leak** — invisible in normal testing, visible only as steadily climbing goroutine count in `pprof` or `runtime.NumGoroutine()`, and Go 1.26 (February 2026, current stable) shipped a genuine goroutine leak detector specifically because this is common enough in production to need first-class tooling. `select` with a `default` case makes a channel operation non-blocking; `select` without one blocks until any case is ready, and the classic footgun is `time.After()` inside a `select` in a loop, which allocates a new timer *every iteration* that never gets garbage collected until it fires — a slow, hard-to-spot memory/goroutine leak in a hot loop. `context.Context` is how Go propagates cancellation and deadlines through a call chain — idiomatic, and unlike most languages, close to free, because it's just a struct passed as the first parameter by convention, not a language feature — but a `context.WithCancel`/`WithTimeout` whose returned `cancel()` function is never called leaks the context's internal goroutine and timer. Generics (Go 1.18, 2022) are structurally, not nominally, typed via constraint interfaces, and remain intentionally more restrained than Java/Rust generics — no runtime reflection-heavy escape hatches, no operator overloading beyond what constraints explicitly permit. The Go memory model formally guarantees specific happens-before orderings (channel send happens-before the corresponding receive completes; a goroutine's creation happens-before its execution begins) that make concurrent code *provably* correct or incorrect, not just "seems to work" — `go test -race` catches most violations empirically, but knowing the actual guarantees is what separates "I ran the race detector" from understanding why a piece of code is safe.

## Why this gets asked

Because Go's whole value proposition to a hiring team is "a small number of engineers can write reliable, fast, concurrent network services without a large runtime or a garbage-collection-tuning specialist," and that promise only holds if the person writing the Go actually understands the concurrency model rather than pattern-matching "goroutines are like threads but lighter." The interviewer has almost certainly debugged a goroutine leak in production — a service whose memory and goroutine count climb steadily under load with no crash, discovered weeks later via `pprof`'s goroutine profile showing thousands of goroutines parked on the same blocked channel operation — or watched a `context.Context` cancellation fail to propagate through a hand-rolled abstraction that swallowed it, leaving a downstream call running long after the caller gave up. They want to see you reason about *why* a specific piece of concurrent code is safe (which happens-before edge guarantees it) rather than "it passed the race detector, ship it."

---

## Lineage: past → present → future

**What came before.** Pre-Go server concurrency in C/C++/Java meant either OS threads directly (expensive per-thread memory and context-switch cost, the same C10K wall covered in `T16-io-models`) or callback-based event loops (Node.js's original model, `libevent`-based C servers) that avoided the thread cost but fragmented control flow into callbacks, making sequential-looking logic hard to write and error handling easy to get wrong. Go's designers (Rob Pike, Ken Thompson, Robert Griesemer, 2009) made a specific bet informed by Tony Hoare's Communicating Sequential Processes (CSP, 1978): give programmers cheap, M:N-scheduled goroutines that let concurrent code *read* like sequential code (no callback fragmentation), and channels as the primary safe communication primitive between them, explicitly discouraging (though not preventing) shared-memory-plus-locks as the default pattern — codified in Go's own proverb, "don't communicate by sharing memory; share memory by communicating."

**Where it stands now.** Goroutines and channels are mature, unchanged-in-fundamentals, and genuinely production-standard — Go is the dominant language for cloud infrastructure tooling (Docker, Kubernetes, Terraform, Prometheus are all written in Go specifically because of this concurrency model) and a major choice for high-throughput backend services generally. `context.Context` (added to the standard library in Go 1.7, 2016, after years as a widely-used external package first) is now the unambiguous idiomatic mechanism for cancellation/deadline/request-scoped-value propagation across API boundaries — a function accepting network or long-running work without a `context.Context` first parameter is now considered a design smell in idiomatic Go. Generics (Go 1.18, March 2022) arrived a full decade after Go 1.0, deliberately late and deliberately restrained — the Go team spent years explicitly rejecting generics designs that added complexity disproportionate to the benefit, landing on a structurally-typed constraint-interface system that avoids the runtime type-erasure surprises of Java generics and the extreme expressiveness (and complexity) of Rust's trait system. **Go 1.26 (released February 10, 2026, current stable as of this writing) is a genuinely significant release**: the Green Tea garbage collector (experimental since Go 1.25) is now enabled by default, cited at roughly 10-40% GC overhead reduction for real-world programs, cgo call overhead dropped roughly 30%, and — directly relevant to this module — Go 1.26 shipped a first-class **goroutine leak detector**, a strong signal that goroutine leaks remain a common enough production problem in 2026 to warrant dedicated tooling investment a decade-plus into the language's life.

**Where it's heading.** Container-aware `GOMAXPROCS` (Go 1.25) — defaulting to the cgroup CPU limit rather than the host's full logical CPU count — reflects the broader, ongoing direction of the runtime becoming more automatically correct in containerized/Kubernetes-default deployment environments without manual tuning, a trend likely to continue (automatic memory-limit awareness via `GOMEMLIMIT`, introduced Go 1.19, is part of the same lineage). The Green Tea GC's move from experiment to default in barely two releases signals the Go team is willing to ship real runtime architecture changes at a faster cadence than the language's historically conservative pace for anything backward-compatibility-affecting — expect continued GC/scheduler investment as the primary area of runtime evolution, with the language surface itself (syntax, generics semantics) staying comparatively stable given Go's strong, explicit backward-compatibility commitment (the Go 1 compatibility promise). The experimental `encoding/json/v2` package (Go 1.25) is a multi-release-cycle bet on fixing long-standing `encoding/json` performance and API ergonomics complaints — worth flagging as *experimental*, not yet the default, if it comes up.

---

## Mental model

```
GOROUTINE SCHEDULING (M:N, GOMAXPROCS logical CPUs by default, container-aware since 1.25):

  Goroutines (G):  g1  g2  g3  g4  g5  g6  g7  g8  ... thousands, cheap (~2KB
                    stack, grows/shrinks dynamically)
  Logical Procs (P): [P1] [P2] [P3] [P4]           <- GOMAXPROCS of these
  OS Threads (M):    M1   M2   M3   M4              <- roughly one per P when busy

  Each P runs one G at a time on its M. When a G blocks on a SYSCALL
  (not a channel op — those are runtime-managed), its M can be detached
  and a new M spun up so the P keeps running other Gs — this is why
  blocking syscalls don't stall the whole scheduler the way a naive
  thread-starved model would.

CHANNEL AS THE SAFE HANDOFF (not a queue you inspect — a rendezvous point):

  unbuffered:  send blocks until a receive is ready — a SYNCHRONIZATION
               point, not just data transfer. Send happens-before receive
               COMPLETES (Go memory model guarantee).
  buffered(N): send blocks only once N items are already queued —
               capacity, not "async," still eventually blocks.

GOROUTINE LEAK (the thing pprof's goroutine profile catches):

  producer() {
      ch := make(chan int)      // unbuffered
      go func() {
          result := computeSomething()
          ch <- result            // BLOCKS FOREVER if nobody ever receives
      }()
      if earlyReturnCondition {
          return                  // <- nobody ever does `<-ch`. Goroutine
      }                            //    above is now stuck forever, LEAKED.
      return <-ch
  }

SELECT: non-blocking with `default`, blocking (any ready case) without it.
  time.After(d) INSIDE a select in a LOOP = allocates a new timer EVERY
  iteration that isn't GC'd until it fires — classic hot-loop leak.
```

---

## How it actually works

### The scheduler: G, M, P, and why blocking syscalls don't stall everything

Go's runtime scheduler tracks three entities: **G**oroutines (the lightweight units of work), **M**achine threads (real OS threads), and **P**rocessors (logical execution contexts, capped at `GOMAXPROCS`, defaulting to the number of logical CPUs — since Go 1.25, correctly reading a container's cgroup CPU limit rather than the host's full core count, which matters directly for correctly-sized Kubernetes pods that previously over-scheduled based on host capacity they didn't actually have access to). Each P can run one G at a time on an M; a G that blocks on a **channel operation or a mutex** doesn't block its M at all — the scheduler parks the G and lets the P immediately run a different ready G, because channel/mutex blocking is runtime-managed cooperative scheduling, not a real OS-level block. A G that makes a **blocking syscall** (a network read the runtime can't make non-blocking, or certain cgo calls) *does* block its M, but the scheduler detects this and can spin up a fresh M to keep the P productive running other Gs — this is the mechanism that keeps a Go program with many concurrent blocking-looking I/O calls from grinding to a halt the way a naive thread-per-call model would in another language, conceptually similar to (and years earlier than) the carrier-thread/virtual-thread model covered in `T11-java-modern`.

**Goroutine stacks start tiny** (historically 2KB, dynamically grown by copying to a larger contiguous stack when it would overflow, and shrunk again when usage drops) — this is the concrete mechanical reason a Go program can comfortably run hundreds of thousands of goroutines where a platform-thread-per-connection model in another language would exhaust memory in the low thousands, the same C10K-scale argument as `T16-io-models` and `T11-java-modern`, arrived at independently and earlier.

### Channels: rendezvous, buffering, and ownership

```go
// unbuffered — a true rendezvous: the sender blocks until a receiver is ready
ch := make(chan Result)
go func() { ch <- doWork() }()
result := <-ch    // send happens-before this receive COMPLETES — memory model guarantee

// buffered — blocks only once the buffer is full
ch := make(chan Result, 10)
```

**Who closes a channel, and when**: the idiomatic rule is *only the sender closes, never the receiver*, and only after the sender is certain no further sends will happen — closing a channel that might still receive a send from another goroutine, or closing it twice, both panic. A closed channel's receive returns the zero value immediately with `ok == false`, which is the standard way to signal "no more values coming" to a ranging receiver (`for v := range ch`). Sending on a closed channel panics; this is a real, checkable production bug when two goroutines race to both believe they own the close.

### Goroutine leaks: the failure mode that doesn't crash

A goroutine leak is a goroutine that blocks forever — on a channel send/receive with no matching operation ever happening, on a mutex nobody ever releases, or in an infinite loop with no exit condition — and Go's garbage collector **does not collect leaked goroutines**, because a blocked goroutine still holds a live reference to its stack and any captured variables; nothing about it looks unreachable to the GC. The production symptom is specific and worth knowing cold: goroutine count and memory climb steadily under sustained traffic with **no crash, no error log, no obvious symptom** until memory pressure eventually triggers OOM or GC pause times degrade from scanning an ever-growing goroutine count — and it's discovered via `pprof`'s goroutine profile showing thousands of goroutines parked at the identical stack trace (the same blocked channel operation), or via `runtime.NumGoroutine()` trending upward in a dashboard over days.

```go
// LEAK: if the consumer stops reading (context canceled, error path, timeout),
// the producer goroutine blocks forever on the unbuffered send, forever.
func stream(ctx context.Context) <-chan int {
    ch := make(chan int)
    go func() {
        for i := 0; ; i++ {
            ch <- i   // blocks forever once nobody's left reading
        }
    }()
    return ch
}

// FIX: select on ctx.Done() alongside the send, so the producer can exit
func stream(ctx context.Context) <-chan int {
    ch := make(chan int)
    go func() {
        defer close(ch)
        for i := 0; ; i++ {
            select {
            case ch <- i:
            case <-ctx.Done():
                return   // producer exits cleanly when the consumer stops caring
            }
        }
    }()
    return ch
}
```

Go 1.26's built-in goroutine leak detector (integrated with `testing`/`synctest`) is a direct, recent response to how common this bug class is — it can flag, in a test, goroutines still running after the test that spawned them has completed, catching the leak at test time instead of relying on production `pprof` discovery weeks later.

### select: blocking, non-blocking, and the time.After trap

```go
// blocking select — waits until ANY case is ready
select {
case v := <-ch1:
    handle(v)
case err := <-errCh:
    handleErr(err)
}

// non-blocking — default fires immediately if nothing else is ready
select {
case v := <-ch:
    handle(v)
default:
    // nothing ready right now, don't block
}

// THE TRAP: time.After() inside a loop's select ALLOCATES A NEW TIMER
// every single iteration, and that timer isn't garbage-collected until
// it actually fires — in a hot loop with a long timeout, this leaks
// memory steadily and creates GC pressure from a huge number of live
// but never-firing timers
for {
    select {
    case msg := <-msgCh:
        process(msg)
    case <-time.After(30 * time.Second):   // NEW timer allocated EVERY iteration
        log.Println("idle timeout check")
    }
}

// FIX: create the timer ONCE outside the loop, Reset() it instead
timer := time.NewTimer(30 * time.Second)
defer timer.Stop()
for {
    select {
    case msg := <-msgCh:
        process(msg)
        if !timer.Stop() {
            <-timer.C
        }
        timer.Reset(30 * time.Second)
    case <-timer.C:
        log.Println("idle timeout check")
        timer.Reset(30 * time.Second)
    }
}
```

### context.Context: cancellation and deadlines as a first-class value

```go
func handleRequest(ctx context.Context, req Request) (Response, error) {
    ctx, cancel := context.WithTimeout(ctx, 2*time.Second)
    defer cancel()   // ALWAYS defer cancel(), even if you also expect the
                      // timeout to fire — omitting it leaks the internal
                      // timer/goroutine until the parent context itself
                      // is done, not until THIS function returns

    result, err := downstreamCall(ctx, req)
    if err != nil {
        if ctx.Err() == context.DeadlineExceeded {
            return Response{}, fmt.Errorf("downstream timed out: %w", err)
        }
        return Response{}, err
    }
    return result, nil
}
```

`context.Context` is idiomatic, convention-based (the first parameter of any function doing I/O or long-running work, by strong community convention, not a compiler-enforced rule) cancellation/deadline/request-scoped-value propagation. **The specific, checkable trap**: `context.WithCancel`/`WithTimeout`/`WithDeadline` all return a `cancel` function that must be called (typically via `defer cancel()`) even when you expect the context to be canceled or time out on its own — failing to call it leaks the internal goroutine/timer the context package spins up to watch for the deadline, held alive until the *parent* context is eventually canceled, which in a long-lived parent (a top-level server context) could be effectively forever. `context.Value` for passing request-scoped data (a request ID, an auth principal) is idiomatic but deliberately discouraged for anything that isn't genuinely request-scoped cross-cutting metadata — using it as a general-purpose dependency-injection mechanism is a common anti-pattern flagged in code review, because it defeats static typing (values are `any`, retrieved by an untyped key) and makes a function's real dependencies invisible from its signature.

### Generics: structural constraints, not nominal typing

```go
type Number interface {
    ~int | ~int32 | ~int64 | ~float32 | ~float64
}

func Sum[T Number](items []T) T {
    var total T
    for _, v := range items {
        total += v
    }
    return total
}

// the ~ before a type means "this constraint also matches any type whose
// UNDERLYING type is int" — so a custom `type Meters int` also satisfies
// `~int`, which plain `int` in the constraint would NOT permit
```

Go generics (1.18, 2022) use **constraint interfaces** to describe what operations a type parameter must support — structural, checked at compile time, with no runtime type erasure surprises (unlike Java, where `List<T>` loses `T` at runtime without reified generics) and no operator-overloading-via-traits complexity (unlike Rust). The `~` (tilde) prefix in a constraint is specifically for allowing named types with a given underlying type, not just the exact predeclared type — a common, checkable gap in understanding when someone writes a constraint that unexpectedly rejects a custom type built on a permitted underlying type. Go's generics deliberately don't support specialization, operator overloading beyond what's built into a constraint's permitted types, or higher-kinded types — a conscious simplicity tradeoff the Go team has defended explicitly, not an oversight.

### The Go memory model: what's actually guaranteed

The formal Go memory model specifies exact happens-before edges, and reasoning from them (rather than "it worked when I tested it") is what separates provably-correct concurrent Go from code that merely hasn't been caught racing yet:

- A goroutine's creation (`go f()`) happens-before `f`'s execution begins.
- A send on a channel happens-before the corresponding receive **completes** (not just starts).
- Closing a channel happens-before a receive that returns because the channel was closed.
- A `sync.Mutex`/`sync.RWMutex` unlock happens-before a subsequent lock acquisition of the same mutex.
- A `sync.Once.Do(f)` call's completion happens-before any other call to `Do` on the same `Once` returns.

Anything not covered by one of these guarantees is a **data race** if two goroutines access the same memory without synchronization and at least one is a write — and a data race in Go is undefined behavior, not "probably fine in practice," which is why `go test -race` (the built-in race detector, instrumenting memory accesses at compile time) is a non-negotiable part of any serious Go test suite, not an optional extra. The race detector catches races that actually occurred during the specific test run — it cannot prove the *absence* of a race in code paths the test didn't exercise, which is the honest caveat to state if asked whether passing `-race` means the code is race-free.

### pprof: the actual production diagnostic loop

```go
import _ "net/http/pprof"   // registers /debug/pprof/* handlers as a side effect
// then: go func() { log.Println(http.ListenAndServe("localhost:6060", nil)) }()
```

```bash
go tool pprof http://localhost:6060/debug/pprof/goroutine   # goroutine count + stacks
go tool pprof http://localhost:6060/debug/pprof/heap        # memory allocation profile
go tool pprof http://localhost:6060/debug/pprof/profile?seconds=30   # CPU profile, 30s sample
```

A goroutine leak's specific `pprof` signature: the goroutine profile shows a very large count of goroutines sharing the **identical stack trace**, parked at the same blocked line (a channel receive, a mutex lock) — that repetition across thousands of goroutines is the diagnostic tell, distinct from a genuinely busy server with many *different* goroutines doing *different* active work. A CPU profile's flame graph pointing at unexpectedly large time in `runtime.mallocgc` often traces back to **escape analysis** failing to keep a value on the stack — the Go compiler's escape analysis determines at compile time whether a variable's lifetime can be proven to not outlive its declaring function (stack-allocatable, fast, no GC involvement) or whether a reference to it could escape (returned, stored in a longer-lived structure, passed to an interface method preventing static analysis) forcing heap allocation; `go build -gcflags="-m"` prints the compiler's actual escape decisions per variable, and a hot path unexpectedly heap-allocating on every call (visible as GC pressure in `pprof`'s heap profile) is frequently traceable to a specific escape decision reviewable this way.

---

## Build it from scratch

A minimal worker-pool pattern demonstrating channels, `context` cancellation, and correct goroutine lifecycle together — the piece most worth being able to write cold:

```go
// untested sketch — bounded worker pool with cancellation
func processAll(ctx context.Context, items []Item, workers int) ([]Result, error) {
    itemCh := make(chan Item)
    resultCh := make(chan Result, len(items))
    errCh := make(chan error, 1)

    var wg sync.WaitGroup
    for i := 0; i < workers; i++ {
        wg.Add(1)
        go func() {
            defer wg.Done()
            for {
                select {
                case item, ok := <-itemCh:
                    if !ok {
                        return   // channel closed, no more work, exit cleanly
                    }
                    result, err := process(ctx, item)
                    if err != nil {
                        select {
                        case errCh <- err:
                        default:   // don't block forever if errCh already has one
                        }
                        return
                    }
                    resultCh <- result
                case <-ctx.Done():
                    return   // caller gave up — exit instead of leaking
                }
            }
        }()
    }

    go func() {
        defer close(itemCh)
        for _, item := range items {
            select {
            case itemCh <- item:
            case <-ctx.Done():
                return
            }
        }
    }()

    go func() { wg.Wait(); close(resultCh) }()

    var results []Result
    for r := range resultCh {
        results = append(results, r)
    }
    select {
    case err := <-errCh:
        return results, err
    default:
        return results, ctx.Err()
    }
}
```

Every goroutine here has an explicit exit path — the closed-channel `ok` check, or `ctx.Done()` — which is the actual discipline that prevents leaks; a fuller lab with a deliberately broken version (missing the `ctx.Done()` case) demonstrated leaking under `pprof`, then fixed, belongs in `(lab pending)`.

---

## How it's done in production

| Symptom | Cause | Fix |
|---|---|---|
| Goroutine count and memory climb steadily under sustained load, no crash, no error log | A goroutine leak — blocked forever on a channel op or lock with no matching operation ever completing | `pprof`'s goroutine profile — look for a large count sharing an identical blocked stack trace; add the missing `ctx.Done()` exit path or fix channel ownership |
| Memory/GC pressure climbs steadily in a hot loop with no obvious allocation in the code | `time.After()` called inside a `select` in a loop, allocating a new timer every iteration that isn't GC'd until it fires | Create a `time.NewTimer` once outside the loop and `Reset()` it, per the pattern above |
| A downstream call keeps running well after the caller gave up or timed out | `context` cancellation not actually propagated — a hand-rolled wrapper swallowed the context, or a `cancel()` was never called/deferred | Thread `ctx` explicitly through every layer as the first parameter; always `defer cancel()` even when a timeout is also expected to fire |
| `go test -race` passes locally but a data race still ships to production | The race detector only catches races that actually occur during the instrumented run — untested code paths give it nothing to catch | Race detector coverage is only as good as test coverage of the actual concurrent paths; don't treat a clean `-race` run as proof of absence for paths never exercised |
| A hot path shows unexpectedly high `runtime.mallocgc` time in a CPU profile | Escape analysis determined a value must be heap-allocated (returned by pointer, stored in a longer-lived structure, passed through an interface boundary) when a stack allocation was expected | `go build -gcflags="-m"` to see the compiler's actual escape decisions; restructure to keep the value's lifetime provably local if the allocation is avoidable |
| Sending on a channel panics intermittently under load | Two goroutines race to both believe they own closing the channel, or a send happens after close | Enforce the single-owner-closes convention explicitly; consider a `sync.Once`-guarded close if genuinely multiple goroutines could reach the close path |
| Pod is scheduled with far more parallelism than the container's actual CPU allocation, causing throttling | Pre-1.25 `GOMAXPROCS` read the host's full logical CPU count rather than the cgroup limit, over-scheduling relative to actual available CPU | Upgrade to Go 1.25+ for container-aware `GOMAXPROCS` by default, or set `GOMAXPROCS` explicitly to match the container's CPU limit on older versions |

---

## Tradeoffs & when NOT to use it

- **Don't assume a goroutine will be garbage-collected just because nothing references it externally.** A blocked goroutine holding a live stack is never GC'd regardless of external reachability — every `go func()` needs an explicit, reasoned exit path, not an assumption the runtime cleans it up.
- **Don't call `time.After()` inside a loop's `select` without understanding the per-iteration allocation cost.** It's fine for a one-shot timeout outside a loop; inside a hot loop, it's a specific, well-known leak pattern with a known fix (`time.NewTimer` + `Reset`).
- **Don't skip `defer cancel()` because you expect the context to time out on its own anyway.** The leaked resource (an internal goroutine/timer) is real and cumulative even when the timeout path is the common case.
- **Don't use `context.Value` as a general dependency-injection mechanism.** It's for genuinely request-scoped cross-cutting metadata (request ID, tracing span) — using it to pass business dependencies defeats static typing and hides a function's real requirements from its signature.
- **Don't treat a clean `go test -race` run as proof a codebase is race-free.** It only proves the specific paths exercised during that run were race-free during that run; race detector coverage is bounded by test coverage of concurrent paths.
- **Don't reach for goroutines-and-channels as the default answer to every concurrency need.** For simple mutual exclusion around a shared counter or map, a plain `sync.Mutex` is often clearer and cheaper than building a channel-based actor pattern around it — Go's proverb about communicating by sharing memory is a strong default, not an absolute rule, and the standard library itself uses mutexes where they're the simpler fit.

---

## Interview questions

### Q1 — What makes a goroutine cheaper than an OS thread, mechanically?
**Testing:** whether the M:N scheduling model is understood, not just "goroutines are lightweight."
**Answer:** Goroutines start with a small stack (historically ~2KB) that the runtime dynamically grows and shrinks by copying to a larger/smaller contiguous allocation as needed, versus an OS thread's fixed, much larger reserved stack (commonly 1-8MB). They're scheduled M:N by Go's own runtime scheduler onto a small, `GOMAXPROCS`-bounded number of OS threads, rather than each goroutine mapping 1:1 to an OS thread — so blocking on a channel or mutex parks the goroutine and lets the scheduler immediately run a different one on the same OS thread, with no OS-level context switch involved.
**Follow-up trap:** *"Does a goroutine blocked on a network read behave the same way?"* — a blocking syscall (which some network I/O can be, depending on the runtime's internal netpoller usage) does block the underlying OS thread (M), but the scheduler detects this and can spin up a replacement M so the logical processor (P) keeps running other goroutines — the netpoller specifically avoids this for most network I/O by using non-blocking syscalls under the hood, similar in spirit to epoll (`T16-io-models`), so in practice most network-bound goroutines don't even hit the blocking-syscall path.

### Q2 — Explain a goroutine leak: what causes it, and why doesn't the garbage collector clean it up?
**Testing:** the actual mechanism, since "goroutine leak" is often named without being explained.
**Answer:** A goroutine leak is a goroutine blocked forever — on a channel send/receive with no matching operation ever occurring, on a lock nobody releases, or an infinite loop with no exit. The GC doesn't collect it because the blocked goroutine's stack and any captured variables are still live and referenced by the runtime's scheduler bookkeeping — nothing about a parked goroutine looks unreachable to the collector, unlike an object with no remaining references.
**Follow-up trap:** *"What's the actual production symptom, before you know the cause?"* — goroutine count and memory climbing steadily under sustained traffic with no crash and no error log, discovered via `pprof`'s goroutine profile showing a large number of goroutines sharing an identical blocked stack trace, or `runtime.NumGoroutine()` trending upward over hours/days in a dashboard — it's specifically silent until memory pressure eventually causes real problems.

### Q3 — What's the `time.After()`-in-a-loop trap, specifically?
**Testing:** a concrete, well-known, checkable footgun.
**Answer:** `time.After(d)` allocates a new `*time.Timer` internally every time it's called, and that timer isn't eligible for garbage collection until it actually fires (its internal goroutine/channel machinery stays alive). Calling it inside a `select` inside a loop allocates a brand new timer every single iteration — in a hot loop with a long duration, this produces steadily accumulating memory and GC pressure from a large number of live-but-never-fired timers.
**Follow-up trap:** *"What's the fix, and why does it avoid the problem?"* — create a single `time.NewTimer(d)` once, outside the loop, and call `.Reset(d)` on it after each relevant event instead of creating a new timer — this reuses the same underlying timer resource rather than allocating fresh ones, though `Reset` itself has a documented subtlety (drain the channel with a non-blocking receive before resetting if the timer might have already fired) worth knowing if pressed further.

### Q4 — Why must you `defer cancel()` even when you expect a `context.WithTimeout`'s deadline to fire on its own?
**Testing:** the specific resource-leak mechanism behind a very common code-review nit.
**Answer:** `context.WithTimeout`/`WithCancel`/`WithDeadline` spin up internal bookkeeping (a timer, and a goroutine watching for cancellation) tied to the *parent* context's lifetime by default — if you never call the returned `cancel` function, that internal resource stays alive until the parent context itself is eventually canceled, which for a long-lived parent (a top-level request or server context) could be effectively the lifetime of the whole request chain or longer, even after the specific function that created the child context has already returned.
**Follow-up trap:** *"If the timeout does fire naturally, is calling cancel() afterward still necessary?"* — yes, and it's cheap/idempotent — calling `cancel()` after the context is already done is a no-op, so `defer cancel()` unconditionally, immediately after creation, is the correct habit regardless of which path actually ends the context.

### Q5 — What's the Go memory model's guarantee about a channel send and its corresponding receive?
**Testing:** whether "channels are safe" is backed by the actual formal guarantee.
**Answer:** A send on a channel happens-before the corresponding receive **completes** — not merely starts. This is the specific guarantee that makes using a channel as a synchronization handoff safe: any memory writes a goroutine made before sending are guaranteed visible to the goroutine that receives, once the receive has fully completed, without needing any additional explicit synchronization.
**Follow-up trap:** *"Does that guarantee extend to a buffered channel the same way?"* — yes, the happens-before relationship holds for buffered channels too, between a specific send and its corresponding receive (the k-th receive corresponds to the k-th send in FIFO order) — buffering changes when blocking occurs, not the fundamental happens-before guarantee between a matched send/receive pair.

### Q6 — Does passing `go test -race` prove a codebase has no data races?
**Testing:** whether the race detector's actual scope and limits are understood, not treated as a magic proof.
**Answer:** No — it proves the specific concurrent code paths actually exercised during that test run were race-free during that run. The race detector instruments memory accesses and reports a race only when it actually observes two conflicting unsynchronized accesses happening during execution; it cannot detect a race in a code path the test suite never triggered, or one that depends on a specific, rare interleaving the test run happened not to hit.
**Follow-up trap:** *"So is running -race in CI still worth it, given that limitation?"* — absolutely, and it should be non-negotiable for any concurrent Go code — it catches a large fraction of real races cheaply and continuously, the limitation is about completeness of proof, not usefulness of the tool; the honest framing for an interview is "necessary but not sufficient."

### Q7 — Explain escape analysis and how you'd diagnose a hot path unexpectedly heap-allocating.
**Testing:** whether GC-pressure debugging skill extends beyond "run pprof and look confused."
**Answer:** Escape analysis is the compiler's compile-time determination of whether a variable's lifetime can be proven to stay within its declaring function (safe to stack-allocate — fast, no GC involvement) or whether a reference to it could outlive the function (returned by pointer, stored in a longer-lived structure, passed through an interface method boundary the compiler can't statically resolve) forcing heap allocation instead. To diagnose, `go build -gcflags="-m"` prints the compiler's actual per-variable escape decisions, and a `pprof` CPU profile showing unexpectedly high time in `runtime.mallocgc` on a hot path is the production signal pointing back to exactly this.
**Follow-up trap:** *"Is heap allocation always something to eliminate?"* — no; the goal is not zero heap allocation everywhere, it's understanding *why* a specific hot-path allocation is happening and whether it's avoidable without contorting the code — some escapes are inherent to genuinely needed dynamic lifetimes (returning a pointer to newly constructed data is completely normal and correct), and chasing stack-allocation for its own sake on a cold path is a waste of effort.

### Q8 — What's the `~` (tilde) prefix mean in a Go generic constraint, and what breaks if you forget it?
**Testing:** a specific, checkable generics detail beyond "generics exist since 1.18."
**Answer:** `~int` in a constraint means "any type whose underlying type is `int`," not just the exact type `int` — so a custom named type (`type Meters int`) satisfies `~int` but would NOT satisfy a constraint written as plain `int` (which only permits that exact type). Forgetting the tilde produces a constraint that unexpectedly rejects any named/derived type built on the permitted underlying type, a real, common source of "why won't my generic function accept this type" confusion.
**Follow-up trap:** *"Why would you deliberately NOT use the tilde in a constraint?"* — when you specifically want to restrict a generic function to the exact predeclared type and intentionally exclude named types built on it, because the named type might carry semantics (validation invariants, different string formatting) that make treating it identically to the raw underlying type incorrect for that specific function's purpose.

### Q9 — Design a fan-out/fan-in worker pool that correctly handles both context cancellation and worker errors. What goes wrong if you get the channel closing order wrong?
**Testing:** applying multiple concepts together in a realistic, checkable pattern — the actual interview-favorite Go design question.
**Answer:** Workers read from a shared input channel and select on `ctx.Done()` alongside the read so they exit cleanly on cancellation; only the single goroutine feeding the input channel closes it (never a worker, since multiple workers racing to close the same channel panics); a separate goroutine `wg.Wait()`s on all workers before closing the results channel, since closing results early would either panic on a still-in-flight worker's send or silently drop results depending on exact timing. Getting the order wrong — closing the results channel before all workers have finished sending — is a classic panic (`send on closed channel`) that only manifests under real concurrent timing, often passing in a quick manual test and failing intermittently under load.
**Follow-up trap:** *"How would an error from one worker propagate without blocking or getting lost?"* — a buffered error channel sized to avoid blocking a worker that hits an error while another error is already pending (a `select` with a `default` case on the error send, as in the build-it-from-scratch example above), or aggregating all errors via `errgroup.Group` from `golang.org/x/sync/errgroup`, which handles exactly this coordination (first error wins, propagates a shared cancellation context to sibling goroutines) as a well-tested library rather than hand-rolled channel plumbing.

### Q10 — A service's `GOMAXPROCS` was left at its default inside a Kubernetes pod limited to 2 CPUs, on Go 1.24. What goes wrong, and what changed in Go 1.25?
**Testing:** current, specific runtime-scheduling knowledge tied to a real deployment gotcha.
**Answer:** Pre-1.25, `GOMAXPROCS` defaults to the number of logical CPUs the runtime detects on the *host*, not the cgroup-limited allocation actually available to the container — on a large host node running a pod capped at 2 CPUs by Kubernetes resource limits, the runtime could schedule far more parallelism than it actually has CPU access to, causing CPU throttling (visible as `container_cpu_cfs_throttled_periods_total` climbing) and degraded, spiky latency despite metrics showing "only" moderate CPU usage. Go 1.25 made `GOMAXPROCS` container-aware by default, correctly reading the cgroup limit instead.
**Follow-up trap:** *"What's the fix on Go versions before 1.25?"* — set `GOMAXPROCS` explicitly to match the container's CPU limit (via the `GOMAXPROCS` environment variable, or the community `uber-go/automaxprocs` library that was the de facto standard workaround before this became a built-in runtime default).

---

## Red flags that fail you

- Claiming goroutines are garbage-collected once nothing references them, without the caveat that a blocked/leaked goroutine's live stack prevents exactly that.
- Not knowing `time.After()` inside a loop's `select` allocates a new timer every iteration.
- Forgetting or not knowing why `defer cancel()` is required even when a timeout is expected to fire naturally.
- Treating a clean `go test -race` run as proof of the absence of races, rather than proof only for the paths exercised.
- Confusing Go's structural, constraint-interface generics with Java's type-erased or Rust's trait-based generics without being able to name the actual difference.
- Not knowing which side of a channel is responsible for closing it, or that closing twice / sending on a closed channel panics.
- Recommending channels-and-goroutines reflexively for simple mutual exclusion where a plain `sync.Mutex` is clearer.
- Being unaware Go 1.26 (Feb 2026) is current and shipped a goroutine leak detector, or claiming generics are a very recent addition when they landed in 2022.

---

## Cheat card

```
SCHEDULING: M:N — Goroutines (G) run on logical Processors (P, count =
  GOMAXPROCS, default = logical CPUs, CONTAINER-AWARE cgroup-limit-based
  since Go 1.25) mapped onto OS threads (M). Blocking on a channel/mutex
  parks the G, no OS context switch. Blocking SYSCALL blocks the M, but
  scheduler spins up a replacement M so the P stays productive.
  Goroutine stack: starts ~2KB, grows/shrinks dynamically (vs OS thread's
  fixed 1-8MB reserved stack) — why 100K+ goroutines is normal.

GOROUTINE LEAK: blocked forever (channel op / lock / infinite loop, no
  exit). GC does NOT collect it — live stack, still referenced by runtime.
  Symptom: goroutine count + memory climb steadily, NO crash, NO error log.
  Diagnose: pprof goroutine profile — many goroutines, IDENTICAL blocked
  stack trace. Go 1.26 (Feb 2026, current) shipped a built-in leak detector.

CHANNELS: unbuffered = true rendezvous (send blocks til receive ready).
  buffered(N) = blocks once N queued. ONLY sender closes, never receiver.
  Send on closed = panic. Double close = panic.
  MEMORY MODEL: send happens-before the CORRESPONDING receive COMPLETES.
  go f() creation happens-before f's execution begins.
  Mutex unlock happens-before next lock of same mutex.
  sync.Once.Do completion happens-before any other Do() call returns.
  Anything NOT covered by a happens-before edge + concurrent read/write
  (>=1 write) = DATA RACE = undefined behavior. go test -race catches
  races that OCCURRED in the run — proves nothing about untested paths.

SELECT: blocking (any ready case) or non-blocking (with `default`).
  time.After() INSIDE a loop's select = new timer allocated EVERY
  iteration, not GC'd til it fires = hot-loop leak. Fix: time.NewTimer
  once + .Reset() instead.

CONTEXT: first-param convention (not compiler-enforced) for cancellation/
  deadline/request-scoped values. defer cancel() ALWAYS — even if timeout
  expected to fire naturally — or you leak the internal timer/goroutine
  until the PARENT context ends. context.Value: request-scoped metadata
  only, NOT general DI (defeats static typing, hides real dependencies).

GENERICS (Go 1.18, 2022): structural constraint interfaces, NOT nominal
  typing, no runtime type erasure. `~int` = matches any type whose
  UNDERLYING type is int (named types included); plain `int` = exact
  type only. No specialization, no operator overloading beyond constraints.

PPROF: /debug/pprof/goroutine (leak diagnosis — look for identical stacks
  repeated many times), /heap (allocation profile), /profile?seconds=N
  (CPU). go build -gcflags="-m" shows escape analysis decisions per
  variable — hot-path runtime.mallocgc time traces back to an escape.

GO 1.26 (Feb 10 2026, current stable): Green Tea GC now DEFAULT (~10-40%
  GC overhead reduction), cgo overhead down ~30%, goroutine leak detector,
  generic types can self-reference in their own type param list.
```

## Sources

- [Go 1.26 is released — The Go Programming Language](https://go.dev/blog/go1.26) — accessed 2026-08-03
- [Go 1.26 Release Notes — The Go Programming Language](https://go.dev/doc/go1.26) — accessed 2026-08-03
- [Go 1.25 is released — The Go Programming Language](https://go.dev/blog/go1.25) — accessed 2026-08-03
- [Detecting goroutine leaks with synctest/pprof](https://antonz.org/detecting-goroutine-leaks/) — accessed 2026-08-03
- [Senior Golang Interview Questions: Advanced Concurrency and Performance — CodeForGeek](https://codeforgeek.com/senior-golang-interview-questions/) — accessed 2026-08-03
- [How to Detect and Fix Goroutine Leaks in Go — knowledgelib.io](https://knowledgelib.io/software/debugging/go-goroutine-leak/2026) — accessed 2026-08-03
- [Go Interview Questions: 30 Questions on Concurrency, Channel, GC, and Escape Analysis — Gank Interview](https://www.gankinterview.com/en/blog/golang-interview-questions-30-questions-on-concurrency-channel-gc-and-escape-ana) — accessed 2026-08-03

## Changelog
- 2026-08-03 — created
