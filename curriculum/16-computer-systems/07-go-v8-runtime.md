# Go G-M-P Scheduler, Stack Growth; V8 Ignition/TurboFan

> **Track:** T16 Computer Systems: Transistor → Runtime · **Time:** 1.5h · **Prereqs:** T16-jvm-runtime · **Updated:** 2026-08-03
> **Module id:** `T16-go-v8-runtime` · **Tags:** runtime

## The 30-second version

Go's scheduler is the G-M-P model: **G**oroutines (lightweight, user-space units of work with tiny starting stacks) are scheduled onto **M**s (OS threads) via **P**s (logical processors, one per `GOMAXPROCS`, each holding a local run queue of up to 256 goroutines) — this indirection lets Go multiplex potentially millions of goroutines onto a small, bounded number of OS threads, with work-stealing between Ps' local queues keeping cores busy without a global lock on every scheduling decision. Goroutine stacks start at 2KB (versus a native OS thread's default 1-8MB) and grow via **contiguous stack copying**: when a stack-overflow check at function entry detects insufficient room, Go allocates a new, larger stack, copies the old contents over, and rewrites every pointer that referenced the old stack's addresses — a genuinely nontrivial correctness feat (Go can do this because it controls the entire call stack and knows exactly which values are pointers) that's precisely why goroutines are cheap enough to spawn by the thousands where OS threads are not. V8 (Chrome/Node.js's JS engine) runs a broadly analogous two-tier pipeline: **Ignition** is a bytecode interpreter that executes all JS initially while collecting type-feedback profiling data, and **TurboFan** is the optimizing JIT that compiles hot functions to machine code using that feedback, critically relying on **hidden classes** (V8 calls them "Maps") — an internal representation that gives JS objects with a stable, consistent shape (same properties added in the same order) fast, monomorphic property access indistinguishable in speed from a statically-typed language's field access, while objects with unstable/varying shapes fall back to slower polymorphic or megamorphic lookups and defeat TurboFan's most aggressive optimizations.

## Why this gets asked

Because "goroutines are lightweight" and "V8 is fast because JIT" are both claims candidates repeat without being able to explain the actual mechanism, and both mechanisms are directly actionable in production code: writing Go code that spawns goroutines carelessly still has a real cost curve (just a much cheaper one than threads), and writing JS/TypeScript objects with inconsistent shapes (conditionally adding properties, deleting properties, iterating them in different orders) silently defeats V8's fastest code path in a way that shows up as a real, measurable slowdown with no exception or warning. An interviewer asking this wants to know you've internalized the mechanism well enough to write code that cooperates with it, not just recite "Go has goroutines" and "V8 has a JIT."

---

## Lineage: past → present → future

**What came before.** Concurrency in most mainstream languages historically meant OS threads directly (pthreads, Java threads before Project Loom) — correct and simple to reason about at small scale, but each OS thread carries a comparatively large fixed-size stack (commonly 1-8MB, reserved even if barely used) and real kernel-level context-switch cost, which caps practical concurrency in the thousands, not millions, of simultaneous units of work. JavaScript, meanwhile, started (mid-1990s) as a purely interpreted, untyped scripting language with no JIT at all — every property access on every object went through slow, generic dictionary-style lookup, which was an acceptable cost when JS ran small page scripts but became a real bottleneck as JS applications grew in scope (particularly once Node.js proposed JS as a general-purpose server language, where V8's original browser-script-oriented performance profile faced fundamentally different demands).

**Where it stands now.** Go's G-M-P scheduler (present since Go's 2009 public release, refined substantially since, notably with cooperative-to-preemptive scheduling improvements in Go 1.14 fixing a real class of scheduling-starvation bugs from tight, non-yielding loops) is the mainstream reference implementation of user-space "green thread"/M:N scheduling done well, and container-aware `GOMAXPROCS` defaults (Go 1.25, 2025) are a direct, recent response to a real production pain point — Go processes historically defaulted `GOMAXPROCS` to the *host's* total CPU count even when running in a CPU-limited container/cgroup, causing scheduler over-subscription and throttling-induced tail latency, a well-documented Kubernetes-era gotcha now fixed by default. V8's Ignition (bytecode interpreter, replacing an earlier full-tree-walking interpreter plus a since-retired baseline JIT called "Sparkplug's predecessors") plus TurboFan (the current optimizing tier, itself a successor to an earlier optimizing compiler called Crankshaft, replaced specifically because Crankshaft's architecture didn't scale to newer JS language features cleanly) represents the settled, multi-generation-refined architecture — hidden classes and inline caches as the mechanism for fast dynamic-object property access are decades-old ideas (tracing back to Self and Smalltalk JIT research in the late 1980s/early 1990s) that V8 (and other modern JS engines, and CPython's specializing interpreter, and the JVM's polymorphic inline caches) all converged on as the answer to "how do you make a dynamically-typed language's property/attribute access fast."

**Where it's heading.** Go's scheduler and stack-growth mechanics are mature and evolving incrementally rather than architecturally (recent releases focus on tuning defaults like container-awareness rather than redesigning G-M-P itself) — a stable, settled direction. V8's direction of travel includes continued work on reducing the cost of megamorphic/polymorphic call sites and on WebAssembly as an increasingly first-class compilation target sitting alongside JS (letting performance-critical code bypass JS's dynamic-typing overhead entirely rather than trying to out-optimize it), which is real and shipping, not speculative — how much real-world JS/TS code gets rewritten in or compiled to Wasm for performance-critical paths versus how much V8's own JIT continues to close that gap for ordinary JS is a genuinely open, workload-dependent question rather than a settled trend in one direction.

---

## Mental model

Picture Go's scheduler as a small number of checkout lanes (Ps, bounded by `GOMAXPROCS`) staffed by cashiers (Ms, OS threads) serving a much larger queue of customers (Gs, goroutines) — a cashier only needs to be "on shift" (an OS thread only needs to exist) roughly in proportion to the number of lanes, not the number of customers, and a lane whose queue empties can steal customers from a busier lane's queue instead of sitting idle:

```
GOMAXPROCS=4:
  P0 [G, G, G, ...]     P1 [G, G]        P2 [G, G, G, G, G]   P3 [ ]
   |                      |                 |                    |
   M0 (OS thread)         M1 (OS thread)    M2 (OS thread)       M3 idle, steals from P2's queue
```

Picture V8's hidden-class system as a filing cabinet: two objects created with properties added in the same order (`{x: 1, y: 2}` both times) share the same "folder shape" (hidden class), so looking up `y` is a fixed-offset lookup, as fast as a struct field access. An object that instead adds `y` before `x` sometimes, or deletes a property, ends up with a *different* folder shape — and a function that handles both shapes at the same call site can no longer use one fast fixed-offset lookup, falling back to slower, more general property resolution.

---

## How it actually works

### G-M-P, concretely

- **G (goroutine):** a lightweight, user-space unit of execution — a function plus its own stack, scheduled entirely by the Go runtime, not the OS kernel. Creating one (`go f()`) is orders of magnitude cheaper than an OS thread specifically because of the small starting stack (below) and because scheduling decisions happen in user space without a kernel context switch.
- **M (machine):** an actual OS thread. Ms are the only things the kernel schedules; the Go runtime creates and destroys them somewhat dynamically (bounded by `GOMAXPROCS` for the common case, though Ms *can* exceed that count temporarily, e.g. one M per blocked syscall, discussed below).
- **P (processor):** a logical execution context, exactly `GOMAXPROCS` of them, each holding a local run queue (bounded, up to 256 goroutines) of Gs ready to run. An M must hold a P to execute Go code — this is the mechanism that actually bounds parallel Go-code execution to `GOMAXPROCS`, not the number of Ms directly.

**Work stealing:** when a P's local run queue is empty, it steals from another P's queue (taking roughly half, to amortize the cost of the steal across future scheduling decisions) rather than idling — this keeps all `GOMAXPROCS` logical processors busy under uneven workloads without needing a single global, contended run queue for every scheduling decision (a global run queue does exist as a fallback/overflow, but the local-queue-plus-stealing design is what avoids it being a bottleneck in the common case).

**Blocking syscalls:** when a goroutine makes a blocking syscall (e.g. a blocking file read), the M executing it would otherwise sit idle holding its P hostage — instead, the Go runtime detaches the P from that M (handing the P to another available or newly-spun-up M so other goroutines on that P's queue keep running) and reattaches once the syscall returns, which is exactly why blocking syscalls in Go don't stall the whole scheduler the way they would in a naive one-thread-per-core model, and why the number of live Ms can temporarily exceed `GOMAXPROCS` under heavy blocking-syscall load.

**Preemption:** prior to Go 1.14, the scheduler was cooperative at safe points (function calls, essentially) — a goroutine running a tight loop with no function calls could starve other goroutines on its P indefinitely, a real, documented class of bug. Go 1.14 introduced **asynchronous preemption** using OS signals to interrupt a running goroutine at arbitrary points (not just function-call safe points), closing that starvation gap — a genuine architectural fix, not a tuning parameter.

### Stack growth

A goroutine's stack starts at **2KB** (Go 1.4+; it was 8KB briefly in Go 1.2-1.3, and 4KB before that — the number has moved historically, 2KB is current) — dramatically smaller than an OS thread's typical 1-8MB default, which is the single biggest reason spawning 100,000 goroutines is routine in Go while spawning 100,000 OS threads is not (memory alone: 100,000 × 2KB ≈ 200MB versus 100,000 × 2MB ≈ 200GB). Every function prologue includes a cheap check (comparing the stack pointer against a per-goroutine limit stored in the G's stack-bounds metadata) — if the check shows insufficient room for the function's stack frame, the runtime triggers a **stack growth**: allocate a new stack (typically double the old size), copy the old stack's contents into the new one, and — critically — **adjust every pointer in the copied stack that pointed into the old stack's address range** to point into the new one instead. This pointer-rewriting step is only safe because Go's runtime has precise knowledge of which stack words are pointers (from compiler-generated stack maps), which is exactly why this technique isn't available to a language/runtime without that same precise pointer information (C's stacks, for instance, can't be relocated this way because a C runtime generally can't reliably distinguish a pointer-valued stack word from an integer that merely looks like one). Stacks can also **shrink** (the runtime periodically checks if a goroutine's stack is far larger than its actual current usage and copies it down to a smaller allocation) to avoid a goroutine that briefly needed a large stack permanently pinning that memory. The default maximum stack size is large (1GB on 64-bit platforms, tunable via `debug.SetMaxStack`) specifically as a safety net against unbounded/runaway recursion rather than a size any goroutine is expected to approach in normal operation.

### V8: Ignition and TurboFan

**Ignition** is V8's bytecode interpreter — all JavaScript execution starts here, with Ignition both executing the bytecode and recording **type feedback** at each polymorphic operation site (property accesses, function calls, arithmetic operations) into a per-function **FeedbackVector**, a structure with one slot per observed call/access site tracking which concrete object shapes (hidden classes) and value types have actually appeared there. **TurboFan** is V8's optimizing JIT: once a function is identified as hot (based on invocation counts, similar in spirit to the JVM's C1→C2 progression covered in the previous module), TurboFan compiles it to native machine code, using the FeedbackVector's accumulated type feedback to generate **speculative, type-specialized code** — if a call site has only ever seen one hidden class, TurboFan can emit code that assumes that shape directly, skipping the general property-resolution machinery entirely.

### Hidden classes and inline caches

A JavaScript object is not, internally, a plain hash map the way its dynamic-typing surface semantics might suggest — V8 tracks each object's **hidden class** (internally called a **Map**, unrelated to the JS `Map` type), which encodes the object's current set of properties and their storage offsets. Two objects built with properties added in the same order end up sharing the same hidden class, and property access against a known hidden class becomes a fixed-offset memory read, as fast as a compiled language's struct field access — this is the mechanism, not "the JIT is smart," that gives well-shaped JS objects console-native-code-like property access speed.

**Inline caches (ICs)** are the call-site-level mechanism that exploits this: each property-access or method-call site in the bytecode has an associated IC slot in the FeedbackVector that remembers the hidden class(es) seen there. A **monomorphic** IC (one hidden class ever observed at that site) is the fastest case — a single cached offset, no branching. A **polymorphic** IC (a small, bounded number of distinct hidden classes, commonly up to 4) still gets reasonably fast code via a small dispatch table. A **megamorphic** IC (more distinct shapes than the polymorphic cache can hold) gives up on the fast path entirely and falls back to a generic, slower property-lookup mechanism for that site — and TurboFan, seeing a megamorphic IC in the feedback data, will decline to generate the fast type-specialized code for that site at all, since there's no longer a stable shape assumption worth speculating on.

**Deoptimization:** if TurboFan compiled a function assuming a stable hidden class (or other speculative assumption, e.g. a value always being an integer never a float) and that assumption is later violated at runtime by an object with a genuinely new shape, V8 discards the optimized machine code, reconstructs an equivalent interpreter-level stack frame, and resumes execution in Ignition — architecturally identical in spirit to the JVM's deoptimization and CPython's specializing-interpreter de-specialization covered in the adjacent modules, all converging on the same "speculate aggressively, but always have a safe, correct fallback" pattern.

---

## Build it from scratch

A minimal work-stealing scheduler simulator and a minimal hidden-class-shape tracker both prove their respective mechanisms are understood rather than memorized as buzzwords:

```go
// untested sketch — toy work-stealing scheduler shape, not a real Go runtime reimplementation
package main

import (
	"fmt"
	"sync"
)

type Task func()

type P struct {
	id    int
	queue []Task
	mu    sync.Mutex
}

func (p *P) push(t Task) { p.mu.Lock(); p.queue = append(p.queue, t); p.mu.Unlock() }

func (p *P) pop() (Task, bool) {
	p.mu.Lock(); defer p.mu.Unlock()
	if len(p.queue) == 0 {
		return nil, false
	}
	t := p.queue[len(p.queue)-1]
	p.queue = p.queue[:len(p.queue)-1]
	return t, true
}

// steal takes roughly half of victim's queue
func (p *P) steal(victim *P) bool {
	victim.mu.Lock(); defer victim.mu.Unlock()
	n := len(victim.queue) / 2
	if n == 0 {
		return false
	}
	p.mu.Lock()
	p.queue = append(p.queue, victim.queue[:n]...)
	p.mu.Unlock()
	victim.queue = victim.queue[n:]
	return true
}

func main() {
	ps := []*P{{id: 0}, {id: 1}, {id: 2}, {id: 3}}
	for i := 0; i < 40; i++ {
		n := i
		ps[0].push(func() { fmt.Println("work", n) }) // dump everything on P0, like an imbalanced load
	}
	var wg sync.WaitGroup
	for _, p := range ps {
		wg.Add(1)
		go func(p *P) {
			defer wg.Done()
			for {
				t, ok := p.pop()
				if !ok {
					stole := false
					for _, victim := range ps {
						if victim != p && p.steal(victim) {
							stole = true
							break
						}
					}
					if !stole {
						return
					}
					continue
				}
				t()
			}
		}(p)
	}
	wg.Wait()
}
```

```javascript
// untested sketch — demonstrates hidden-class instability defeating fast property access
function Point(x, y) {
  this.x = x;
  this.y = y;
}
// stable shape: every Point built the same way shares one hidden class -> fast, monomorphic
const stable = [];
for (let i = 0; i < 1e6; i++) stable.push(new Point(i, i));

// unstable shape: sometimes x-then-y, sometimes y-then-x -> two different hidden classes
const unstable = [];
for (let i = 0; i < 1e6; i++) {
  const p = {};
  if (i % 2 === 0) { p.x = i; p.y = i; } else { p.y = i; p.x = i; }
  unstable.push(p);
}
// benchmark summing .x across `stable` vs `unstable` and observe the measurable gap --
// full walkthrough with expected relative timing lives in the lab.
```

Full walkthroughs for both, including a `GODEBUG=schedtrace=1000` run showing real P/M/G counts and a Node.js `--trace-deopt` run showing an actual deoptimization event, live in `labs/go/07-scheduler-and-shapes/`.

---

## How it's done in production

| Symptom | Cause | Fix |
|---|---|---|
| A Go service in a Kubernetes pod with a 2-core CPU limit shows high scheduling latency/throttling despite low reported CPU usage | Pre-Go-1.25, `GOMAXPROCS` defaulted to the *host's* full core count, not the container's cgroup CPU limit, causing the scheduler to oversubscribe Ps relative to the actually-available CPU quota, triggering cgroup CFS throttling | Upgrade to Go 1.25+ (container-aware `GOMAXPROCS` by default) or explicitly set `GOMAXPROCS` (or use `uber-go/automaxprocs` on older Go versions) to match the container's actual CPU limit |
| A goroutine-heavy service shows one goroutine effectively starving others intermittently | A tight loop with no function calls or channel operations on an older Go version (pre-1.14) hit the cooperative-scheduling gap | Confirm Go version is 1.14+ (async preemption should prevent this categorically); if it persists on a modern Go version, suspect something else entirely (e.g. a goroutine holding a lock for pathologically long, not a scheduling starvation issue) |
| Memory usage spikes unexpectedly correlated with specific request patterns in a goroutine-per-request Go service | A subset of requests trigger deep recursion or large local buffers, causing many goroutines to grow their stacks substantially and simultaneously — the *aggregate* stack memory across many concurrently-large-stacked goroutines can be a real, measurable cost even though no single goroutine approaches the 1GB default max | Profile with `pprof`'s goroutine/heap profiles during the spike; consider whether the deep-recursion or large-local-buffer pattern can be restructured (iterative instead of recursive, or a pooled/reused buffer instead of a large per-call local) |
| A hot JS/Node.js function's performance degrades sharply and unpredictably in production despite no code change | An inline cache at a hot property-access site went from monomorphic/polymorphic to megamorphic because objects with varying shapes started flowing through that call site (e.g. objects from different sources with inconsistent property-addition order, or objects with properties added conditionally) | Run with `--trace-ic` (V8 flag) or use Node's `--prof`/Chrome DevTools to identify the specific megamorphic site; restructure object construction to consistently initialize the same properties in the same order (ideally in a constructor/factory function, not ad hoc object literals built incrementally) |
| Node.js function marked as previously fast suddenly slows down after a specific input pattern starts appearing | TurboFan deoptimized the function because a speculative type assumption broke (e.g. a value that was always an integer arrived as a float, or `arguments` object usage patterns that block certain optimizations were hit) | Run with `--trace-deopt` to see the specific deopt reason and bailout location; the fix is almost always restructuring the JS to keep types and object shapes stable at that site, not a V8 flag |

---

## Tradeoffs & when NOT to use it

- **Don't spawn unbounded goroutines per unit of incoming work without a limit.** Goroutines are cheap, not free — a service spawning one goroutine per incoming request with no concurrency cap can still exhaust memory or downstream resources under load; use a worker pool or a semaphore (`golang.org/x/sync/semaphore`, or a buffered channel used as a limiter) for genuinely unbounded input sources.
- **Don't assume `GOMAXPROCS` should always equal the container's CPU limit exactly.** For I/O-heavy workloads with many goroutines blocked on network calls rather than CPU-bound work, a `GOMAXPROCS` matching the CPU limit is usually right, but some workloads benefit from measuring rather than assuming — container-aware defaults get this right automatically in most cases as of Go 1.25, which is precisely why upgrading is usually simpler than hand-tuning.
- **Don't build JS objects with unstable property-addition order as a matter of course, but also don't over-engineer object construction for shape-stability in code that isn't hot.** The hidden-class/IC mechanism only matters for genuinely hot property-access call sites (tight loops over large arrays of similarly-shaped objects, hot request-handling paths); restructuring every object literal in a codebase for shape-consistency is unnecessary ceremony for code that runs once per request or isn't performance-sensitive.
- **Don't chase V8 deoptimization events as bugs to eliminate entirely.** Some deoptimization is normal and expected (a function genuinely handling multiple types correctly should see some polymorphic dispatch cost); the goal is avoiding *pathological*, sustained megamorphic/deopt-thrashing patterns on genuinely hot paths, not achieving zero deoptimization anywhere in an application.
- **This module's specific mechanisms (G-M-P, hidden classes) are Go- and V8-specific in their exact names, but the underlying pattern — lightweight user-space scheduling with work stealing, and shape/type speculation with a safe deopt fallback — recurs across runtimes** (Java's virtual threads/Project Loom for the former, the JVM's polymorphic inline caches and CPython's adaptive interpreter for the latter), so the concepts transfer even where the specific terminology doesn't.

---

## Interview questions

### Q1 — Explain the G-M-P model and specifically what bounds the number of goroutines that can run truly in parallel at any instant.
**Testing:** whether "GOMAXPROCS controls goroutines" (too vague/wrong) or the precise mechanism (Ps bound parallel execution, Ms are OS threads, Gs are the work) is understood.
**Answer:** G = goroutine (lightweight unit of work), M = OS thread (what the kernel actually schedules), P = logical processor context, exactly `GOMAXPROCS` of them, each with a local run queue. An M must hold a P to execute Go code, so the number of Ps — not the number of Ms, which can temporarily exceed `GOMAXPROCS` under blocking syscalls — is what bounds truly parallel Go-code execution at any instant.
**Follow-up trap:** *"If GOMAXPROCS=4, can more than 4 OS threads exist simultaneously in the process?"* — yes; when a goroutine makes a blocking syscall, its M's P is handed off to another M so other goroutines keep running, meaning the live M count can temporarily exceed `GOMAXPROCS` — the invariant is on concurrently-Go-code-executing Ps, not total OS thread count.

### Q2 — How does goroutine stack growth work, and why is this technique unavailable to a naive C runtime?
**Answer:** A goroutine's stack starts small (2KB); a cheap check at function entry detects insufficient room and triggers allocating a new, larger stack, copying the old contents over, and rewriting every pointer within the copied data that referenced the old stack's addresses to point into the new stack instead. This is only safe because the Go compiler generates precise stack maps telling the runtime exactly which stack words are pointers versus non-pointer data — a C runtime generally lacks that precise distinction (a stack word that looks like a valid pointer might just be an integer with a coincidentally pointer-like value), so blind pointer rewriting isn't safely possible without that type information.
**Follow-up trap:** *"Does this mean a pointer *into* a goroutine's stack, held by another goroutine, would break after a stack grow?"* — this is exactly why Go's runtime restricts and carefully manages cross-goroutine pointers into stack memory; in practice, the language and runtime are designed so this scenario is either disallowed or handled by the same stack-scanning/rewriting machinery, and it's precisely the kind of subtlety that makes stack-copying growth a genuinely hard correctness problem, not a trivial "just memcpy and resize" operation.

### Q3 — What changed in Go 1.14's scheduler, and what specific bug class did it fix?
**Answer:** Prior to 1.14, the scheduler was cooperative at safe points — essentially function calls — so a goroutine running a tight loop with no function calls (e.g. a pure numeric loop with no I/O or calls) could never be preempted, starving other goroutines scheduled on the same P indefinitely. Go 1.14 introduced asynchronous preemption using OS signals to interrupt a running goroutine at arbitrary points, not just safe points, closing that starvation gap categorically.
**Follow-up trap:** *"If you see apparent goroutine starvation on a modern (1.14+) Go version, what's your new hypothesis?"* — not a scheduling-cooperation gap (that's fixed); more likely a goroutine holding a lock or blocking resource for a pathologically long time (a genuine application-level bottleneck, not a scheduler limitation), or a `GOMAXPROCS` misconfiguration relative to actual available CPU (e.g. the container-limit mismatch described in the production table) — the diagnosis shifts entirely once the pre-1.14 cooperative-scheduling explanation is ruled out by version.

### Q4 — What is a V8 hidden class, and why does property-addition order matter for performance?
**Answer:** A hidden class (V8's internal "Map") encodes an object's current property set and their storage offsets; two objects built by adding properties in the same order end up sharing the same hidden class, making subsequent property access a fixed-offset read — as fast as a compiled struct field access. Objects that add the same properties in different orders (or add/delete properties conditionally) end up with different hidden classes despite having "the same" properties from a JS-semantics point of view, and a call site handling both shapes can no longer use one fast, fixed-offset lookup.
**Follow-up trap:** *"Are two objects with the exact same current property set but built via different code paths (different addition orders) considered the same shape by V8?"* — no; hidden classes are determined by the transition history (the sequence of property additions), not just the final property set, so `{x:1,y:2}` built via `p.x=1;p.y=2` and the same final object built via `p.y=2;p.x=1` generally end up as two distinct hidden classes despite looking identical from JS code's perspective — this exact subtlety is why "just have the same properties" isn't sufficient advice; consistent *construction order* (ideally via a shared constructor/factory) is what actually matters.

### Q5 — Explain monomorphic, polymorphic, and megamorphic inline caches, and what happens to TurboFan's optimization when a site becomes megamorphic.
**Answer:** Monomorphic: an IC site has only ever observed one hidden class — fastest case, a single cached fixed-offset access with no branching. Polymorphic: a small, bounded number of distinct hidden classes (commonly up to around 4) — still reasonably fast via a small dispatch table checking which of the known shapes applies. Megamorphic: more distinct shapes than the polymorphic cache can hold — the IC gives up on the fast path entirely, falling back to generic, slower property lookup for that site, and TurboFan, seeing a megamorphic feedback signal, declines to generate type-specialized fast code for that site since there's no longer a stable shape assumption worth speculating on.
**Follow-up trap:** *"Is polymorphic inline caching unique to V8?"* — no; polymorphic inline caches trace back to Self and Smalltalk JIT research from the late 1980s/early 1990s and are used in some form by essentially every modern dynamic-language JIT, including the JVM's own polymorphic inline caches for interface/virtual dispatch and, conceptually, CPython's 3.11+ specializing adaptive interpreter's per-site type guards — this is a convergent, cross-runtime pattern, not a V8-specific invention.

### Q6 — A Node.js function that was previously fast suddenly slows down under production load with no code change. Walk through your diagnostic process.
**Answer:** Suspect a deoptimization or a shift from monomorphic to megamorphic inline caches at a hot call site, likely triggered by a change in the *data* flowing through the function (a new upstream source producing objects with different property-addition order, or values shifting from consistently-integer to sometimes-float) rather than a code change. Diagnose with `--trace-deopt` (shows specific deopt events, reasons, and locations) and `--trace-ic` or Chrome DevTools' profiler (shows IC state transitions) rather than guessing; the fix is almost always restructuring object construction or value handling for consistency, not a V8 flag or version change.
**Follow-up trap:** *"Could this be a garbage collection issue instead, and how would you rule that out first?"* — yes, worth ruling out in parallel — a sudden latency regression can also stem from GC pressure changes (V8's own generational collector, conceptually similar to the JVM's, covered in the previous module's broader pattern) rather than JIT deoptimization; checking `--trace-gc` output alongside `--trace-deopt` for correlated timing is the correct way to distinguish the two rather than assuming one cause without evidence.

### Q7 — Staff-level: your team is deciding between spawning one goroutine per incoming request (unbounded) versus a fixed worker pool for a high-throughput ingestion service. Make the case for each and state your recommendation.
**Answer:** Unbounded per-request goroutines: simplest code, and genuinely fine up to the point where incoming request rate times average goroutine lifetime doesn't exceed what downstream resources (database connections, memory, file descriptors) and the process's own memory budget can sustain — goroutines being cheap doesn't make downstream dependencies infinitely scalable. A fixed worker pool (or a semaphore-bounded concurrency limit) trades a small amount of code complexity for a hard, predictable ceiling on concurrent work, protecting downstream resources and providing natural backpressure (requests queue or are rejected once the pool is saturated, rather than the process silently accumulating unbounded in-flight work and its associated memory/goroutine-stack footprint). Recommendation: for a genuinely high-throughput ingestion service specifically (the scenario given), a bounded worker pool or explicit concurrency limiter is the safer default — the failure mode of unbounded goroutines under a traffic spike (memory exhaustion, downstream connection pool exhaustion) is a real, common production incident pattern, not a hypothetical risk.
**Follow-up trap:** *"Doesn't a worker pool risk underutilizing available concurrency for I/O-bound work?"* — yes, that's the real cost side of the tradeoff, and it argues for sizing the pool/limiter generously relative to actual downstream capacity (not artificially small) rather than avoiding bounding altogether — the goal is a ceiling matched to what downstream systems can actually absorb, not an arbitrarily restrictive one, and getting that number right requires actually measuring downstream capacity rather than guessing.

---

## Red flags that fail you

- Claiming `GOMAXPROCS` controls the total number of goroutines that can exist, rather than the number that can execute Go code truly in parallel at once.
- Claiming stack growth in Go is "just like" a C stack growing, missing that pointer rewriting via compiler-generated stack maps is the actual, nontrivial mechanism that makes it possible.
- Believing pre-1.14 cooperative-scheduling starvation is still a risk on a modern Go version.
- Claiming two JS objects with "the same properties" always share a hidden class, missing that construction/addition order matters.
- Confusing polymorphic (bounded, still reasonably fast) with megamorphic (fast path abandoned) inline cache states.
- Treating any JIT deoptimization as inherently a bug to eliminate rather than distinguishing normal, bounded polymorphism from pathological deopt-thrashing.

---

## Cheat card

```
G-M-P: G=goroutine (user-space, cheap) M=OS thread (kernel-scheduled) P=logical proc
  context (exactly GOMAXPROCS, local run queue up to 256). M needs a P to run Go code
  -> P count bounds true parallelism, NOT M count (M count can exceed GOMAXPROCS under
  blocking syscalls -- P detaches from blocked M, reattaches to another).
WORK STEALING: idle P steals ~half another P's queue instead of idling. Global run queue
  = fallback/overflow only, not the common path.
PREEMPTION: cooperative pre-1.14 (safe points = function calls only) -> tight loops with
  no calls could starve peers. 1.14+ = async preemption via OS signals, fixed categorically.
STACK GROWTH: starts 2KB (vs OS thread's 1-8MB). Function-entry check -> insufficient
  room -> alloc bigger stack, COPY old contents, REWRITE every pointer into old stack's
  range to point into new stack (only safe via compiler-generated precise stack maps).
  Also SHRINKS if oversized. Default max 1GB (64-bit), tunable via debug.SetMaxStack.
GOMAXPROCS: container-aware by default since Go 1.25 -- pre-1.25 defaulted to HOST core
  count even under a cgroup CPU limit, causing throttling/tail-latency in containers.
V8 IGNITION: bytecode interpreter, all JS starts here, records type feedback per call/
  access site into a per-function FeedbackVector.
V8 TURBOFAN: optimizing JIT, compiles hot functions using FeedbackVector data into
  speculative type-specialized machine code.
HIDDEN CLASSES (Maps): object shape = property set + ADDITION ORDER (not just final
  properties). Same shape -> fixed-offset access, struct-field-fast.
INLINE CACHES: monomorphic (1 shape, fastest) -> polymorphic (few shapes, small dispatch
  table, still fast) -> megamorphic (too many shapes, fast path abandoned, TurboFan
  won't specialize that site).
DEOPT: speculative assumption breaks (new shape, type change) -> discard optimized code,
  reconstruct interpreter frame, resume in Ignition. Same pattern as JVM C2 deopt and
  CPython adaptive-interpreter de-specialization.
```

## Sources

- [Container-aware GOMAXPROCS — The Go Programming Language](https://go.dev/blog/container-aware-gomaxprocs) — accessed 2026-08-03
- [Maps (Hidden Classes) in V8 — v8.dev](https://v8.dev/docs/hidden-classes) — accessed 2026-08-03
- [V8 Hidden Classes Explained: Object Shapes & Deopt Guide — Kislay Vats](https://kislayvats.com/blogs/v8-hidden-classes-optimizing-object-shapes) — accessed 2026-08-03
- Go source, `runtime/proc.go`, `runtime/stack.go` (github.com/golang/go) — primary source for G-M-P and stack growth implementation
- The Go Blog, "Go 1.14 Is Released" — asynchronous preemption
- V8 blog, "Ignition: An Interpreter for V8" — accessed 2026-08-03
- Chambers, Ungar, Lee, "An Efficient Implementation of SELF, a Dynamically-Typed Object-Oriented Language Based on Prototypes," OOPSLA 1989 — original hidden-class/polymorphic-IC research lineage

## Changelog
- 2026-08-03 — created
