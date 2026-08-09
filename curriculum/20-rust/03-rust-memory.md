# Rust Memory: Box/Rc/Arc/RefCell, Interior Mutability, Send + Sync, Unsafe

> **Track:** T20 Rust · **Time:** 2.5h · **Prereqs:** `T20-rust-ownership` · **Updated:** 2026-08-05
> **Module id:** `T20-rust-memory` · **Tags:** core, critical, concurrency, unsafe
> **Lab:** none yet — see `labs/py/02-agent-loop/` for the pattern if you want to build one

## The 30-second version

When the borrow checker says no, Rust gives you a ladder of escape hatches and each rung costs something measurable: `Box<T>` buys heap indirection for a pointer deref and one allocation; `Rc<T>` buys shared ownership for a non-atomic counter I measured at 1.53 ns per clone-and-drop; `Arc<T>` buys the same across threads for 14.44 ns, a 9.4x tax paid entirely in `lock xadd` and cache-line ownership; `RefCell<T>` moves the borrow check from compile time to runtime, where a violation is a panic reading `RefCell already borrowed` instead of a compile error; and `Mutex<T>`/`RwLock<T>` do the same across threads, except Rust's version *owns* the data it protects, which is the one structural thing Java's `synchronized` and Go's `sync.Mutex` cannot do. `Send` and `Sync` are auto-traits the compiler derives structurally, not annotations you write: `Send` means the value can move to another thread, `Sync` means `&T` can, and `Rc` is neither because its counter isn't atomic while `MutexGuard` is `Sync` but not `Send` because POSIX requires the unlocking thread to be the locking one. `unsafe` turns off exactly five compiler checks and turns off *nothing* else, least of all the aliasing rules, and the whole discipline is that an `unsafe` block is a promise you make to the compiler, so an abstraction is sound only if no safe caller can break it. Miri is the tool that checks the promise, because rustc structurally cannot, and the aliasing model Miri checks against is still an open question with two live candidates, Stacked Borrows and Tree Borrows.

## Why this gets asked

Because this is where Rust stops being a nicer C++ and starts being a set of engineering decisions with costs, and the interviewer wants to see whether you make those decisions on purpose. Almost everyone asking has personally shipped a service that got slower after someone wrapped a hot struct in `Arc<Mutex<_>>` because it was the shape that compiled, and has then spent a week discovering the contention was a single cache line ping-ponging across 32 cores. The second thing they have lived through is a `RefCell` panic at 3am in a code path that ran a million times a day without incident, because the re-entrant borrow only happened when a callback fired during a specific error path, and the panic message told them nothing except the line number where the *second* borrow happened, not the first.

The deeper probe is `unsafe`. Interviewers at staff level are trying to find out whether you think `unsafe` means "the compiler stops complaining" or whether you understand it as a proof obligation transferred from the compiler to you, with a specific and enumerable set of conditions. The tell is whether you can state what `unsafe` does *not* turn off, whether you reach for `UnsafeCell` correctly, and whether you know that "it works in debug but crashes in release" is the signature of undefined behaviour rather than a compiler bug. If you can say "I would run that under Miri and here is exactly what Miri can and cannot prove," you have separated yourself from the majority of candidates who have written Rust for two years and never run it.

---

## Lineage: past → present → future

**What came before.** Shared mutable state in C and C++ was managed by convention and by hand: a `struct` with a `refcount` field and matching `retain`/`release` calls (the pattern that Objective-C formalized as manual reference counting in the 1990s and that CPython has used since 1991 for every single object), or `std::shared_ptr` (C++11, 2011) which finally made the counter atomic by default. The specific pain that killed the hand-rolled version is that refcount bugs are silent and delayed: one missed `release` is a leak you find weeks later in an RSS graph, one extra `release` is a use-after-free that corrupts whatever the allocator hands out next, and neither has a stack trace pointing at the responsible line. `std::shared_ptr` fixed the manual pairing but introduced its own tax that C++ shops still complain about, because the standard mandates the control block be thread-safe and there was no way to opt out for single-threaded code, so every `shared_ptr` copy in a single-threaded render loop paid for a synchronization nobody needed. Meanwhile the mutex story was worse: `pthread_mutex_t` and Java's `synchronized` and Go's `sync.Mutex` all protect a *region of code*, not a *piece of data*, so the association between "this lock" and "the fields it guards" lived only in a comment, and Java's answer to the resulting bug class was `@GuardedBy` annotations checked by an optional static analyser that most teams never ran. Go went further in the other direction and shipped a runtime race detector in Go 1.1 (2013), built on ThreadSanitizer, which is genuinely excellent but is dynamic: the Go documentation states it costs roughly 2x to 20x execution time and 5x to 10x memory, and it can only report a race that your test actually executed on that particular interleaving.

**Where it stands now.** Rust's position, stable since 1.0 in May 2015 and unchanged in its fundamentals since, is that the association between a lock and its data should be in the *type*: `Mutex<T>` owns the `T` and the only way to reach the `T` is through a guard obtained by locking, so "forgot to take the lock" is not a bug you can write. That idea is now genuinely uncontroversial and has been copied outward: Kotlin, Swift's actor isolation (SE-0306, Swift 5.5, 2021), and the C++ community's `folly::Synchronized` and the `synchronized_value` proposal all encode the same shape. The refcount split is also settled: `Rc` for single-threaded, `Arc` for cross-thread, with the compiler deciding which is legal via `Send`/`Sync` rather than leaving it to the programmer, which is exactly the opt-out that C++ never got. The live disagreements are one level deeper. First, the aliasing model: Rust has *not* stabilized a definition of undefined behaviour for references, and the two candidate models are Stacked Borrows (Jung et al., POPL 2020) and Tree Borrows (Villani, Hostert, Dreyer, Jung, PLDI 2025, one of 6 Distinguished Papers out of 89 accepted). Tree Borrows replaces the stack at the centre of the model with a tree, and evaluated over the 30,000 most-downloaded crates it rejects 54% fewer test cases than Stacked Borrows while, per the Rocq-mechanized proofs in the paper, retaining most of the optimizations Stacked Borrows enabled and adding read-read reordering. Miri implements both; Stacked Borrows is still the default and Miri's own README warns that Tree Borrows is *more* likely to accept something the eventual official model declares UB. This is not settled and you should say so if asked. Second, at the ecosystem level, the honest deployed reality is that `Arc<Mutex<T>>` is overused: it is the shape that compiles, and a large fraction of production Rust that would be better served by channels, by `Arc<T>` with `T` immutable, by sharding, or by `arc-swap`/`ArcSwap` for read-mostly config, instead pays lock and atomic costs on a hot path.

**Where it's heading.** Three directions, with confidence stated. High confidence: Miri continues to become the default expectation for any crate with `unsafe`, because the tooling gap closed: over 1500 PRs landed in Miri in the three years to December 2025, its diagnostics now point at both sides of a data race and at the allocation and free site of a use-after-free, and it no longer requires `xargo` to set up. Medium confidence: Tree Borrows becomes the model Rust eventually blesses, because the 54% reduction in false rejections is the kind of number that decides these arguments, but the Unsafe Code Guidelines work has been open since 2018 and there is no announced date, so treat "Rust will formally specify UB by version X" as speculative. Lower confidence and explicitly speculative: exhaustive concurrency checking becomes routine. The groundwork exists (GenMC integration into Miri can in principle enumerate *all* executions of a bounded concurrent program rather than the one execution Miri normally runs) but as of the December 2025 Miri update this required a custom build, was described as "highly experimental" and slow, and I would not bet a roadmap on it. Also speculative but worth naming: BorrowSanitizer, an LLVM-instrumentation project publishing monthly status updates through 2026, is trying to bring Tree-Borrows-style aliasing checks to *natively compiled* binaries at a fraction of Miri's interpretation cost, which would matter enormously because Miri cannot run code that touches the network or most FFI.

---

## Mental model

The whole topic is one ladder. Each rung buys you something the previous rung could not express, and charges for it.

```
                WHAT YOU WANT              WHAT IT COSTS (measured, x86_64,
                                            rustc 1.97.1 -O, i5-12450H)
 ┌──────────────────────────────────────────────────────────────────────┐
 │ &T / &mut T   compile-time borrow        0 ns. 0 bytes. The default.  │
 │               ~~~~~~~~~~~~~~~~~~~~       Reach for this first.        │
 ├──────────────────────────────────────────────────────────────────────┤
 │ Box<T>        heap indirection,          1 malloc + 1 pointer deref.  │
 │               one owner                  8 bytes for Sized T.         │
 │               (recursive types,          16 bytes for dyn Trait       │
 │                trait objects,            (data ptr + vtable ptr).     │
 │                large moves)                                           │
 ├──────────────────────────────────────────────────────────────────────┤
 │ Rc<T>         MANY owners,               1.53 ns per clone+drop.      │
 │               one thread                 +16 bytes header (2 usize:   │
 │                                          strong, weak). NOT Send.     │
 ├──────────────────────────────────────────────────────────────────────┤
 │ Arc<T>        MANY owners,               14.44 ns per clone+drop      │
 │               MANY threads               = 9.4x Rc. lock xadd +       │
 │                                          lock xsub + cache line       │
 │                                          ownership transfer.          │
 ├──────────────────────────────────────────────────────────────────────┤
 │ Cell<T>       mutate through &T,         ~0.25 ns (≈1 cycle). No      │
 │               no references handed out   borrow flag at all. Copy in, │
 │                                          Copy out. Only 1 thread.     │
 ├──────────────────────────────────────────────────────────────────────┤
 │ RefCell<T>    mutate through &T,         ~0.25 ns uncontended, and    │
 │               real &mut handed out       a RUNTIME PANIC if the rule  │
 │                                          is broken. +8 bytes (isize   │
 │                                          borrow flag). Only 1 thread. │
 ├──────────────────────────────────────────────────────────────────────┤
 │ Mutex<T>      mutate through &T,         13.19 ns lock+unlock         │
 │               ACROSS threads             uncontended; unbounded when  │
 │                                          contended. 8 bytes for       │
 │                                          Mutex<()> on Linux (futex).  │
 ├──────────────────────────────────────────────────────────────────────┤
 │ unsafe {}     the 5 superpowers          The compiler stops proving   │
 │ UnsafeCell<T> the ONLY legal way to      anything. You now owe the    │
 │               get &mut from &            proof. Miri is your only     │
 │                                          practical checker.           │
 └──────────────────────────────────────────────────────────────────────┘

THE TWO-AXIS TABLE. Every one of these types is one cell of a 2x2:

                    │ ONE OWNER          │ MANY OWNERS
 ───────────────────┼────────────────────┼──────────────────────────
  SINGLE-THREADED   │ Box<T>             │ Rc<T>
  interior mut →    │ Cell<T>/RefCell<T> │ Rc<RefCell<T>>
 ───────────────────┼────────────────────┼──────────────────────────
  MULTI-THREADED    │ Box<T> (moved)     │ Arc<T>
  interior mut →    │ Mutex<T>/RwLock<T> │ Arc<Mutex<T>>
                    │ Atomic*            │ Arc<AtomicUsize>

 The compiler picks the row for you. It will not let you use the top row
 across threads, because Rc is !Send and RefCell is !Sync. That refusal is
 the entire point: in Java or Go the equivalent mistake compiles.

THE SUBSTITUTION RULE that makes this memorable:

   Rc  : Arc     ::     RefCell : RwLock
   ^^^^^^^^^            ^^^^^^^^^^^^^^^^
   "shared ownership"   "shared mutation"
   non-atomic:atomic    panic-on-violation : block-on-violation

 Rc -> Arc swaps a `usize` counter for an `AtomicUsize`.
 RefCell -> RwLock swaps "panic if someone else has it" for
            "park this thread until they don't".
 That is the *entire* difference in each pair.
```

The second model, which matters for `unsafe`, is about who owes the proof:

```
 SAFE RUST:      you write code  ->  compiler proves no UB  ->  binary
                                     (if it can't prove it, it REJECTS)

 UNSAFE RUST:    you write code  ->  compiler ASSUMES no UB ->  binary
                                     ^^^^^^^^^^^^^^^^^^^^^
                                     it does not check. It OPTIMIZES
                                     on the assumption. That is why UB
                                     often only bites at -O: the
                                     optimizer is exploiting a promise
                                     you broke.

 SOUNDNESS is a property of the ABSTRACTION, not the block:
   an unsafe abstraction is SOUND iff NO safe caller, using ANY
   combination of its public API, can cause UB.
   Vec is sound. Vec is full of unsafe. Those are not in tension.
```

---

## How it actually works

All measurements below are on `rustc 1.97.1 (8bab26f4f 2026-07-14)`, `x86_64-unknown-linux-gnu`, `-O`, on a 12th Gen Intel Core i5-12450H with 2 vCPUs visible. Sizes are from `std::mem::size_of` on that target. Reproduce them before quoting them on a different machine; the ratios travel further than the absolute numbers.

### `Box<T>`: the minimum escape hatch, and the three cases that force it

`Box<T>` is a single owning pointer to a heap allocation. `size_of::<Box<u64>>() == 8`, identical to `&u64`, and `size_of::<Option<Box<u64>>>() == 8` as well because the null pointer is a niche the compiler uses for `None`. There are exactly three situations where you cannot avoid it.

**Case 1: recursive types.** `struct Node { next: Node }` has no finite size and rustc rejects it with `E0072: recursive type has infinite size`. Boxing the recursive field breaks the cycle because a pointer has a size known at compile time:

```rust
// verified: compiles on rustc 1.97.1
enum List { Cons(i32, Box<List>), Nil }
```

**Case 2: trait objects.** A `dyn Trait` is unsized, so it can only exist behind a pointer. `size_of::<Box<dyn Debug>>() == 16`: a data pointer plus a vtable pointer, which is why this is called a fat pointer. The vtable holds the destructor, the size, the alignment, and one function pointer per method, so a method call through it is a load plus an indirect call rather than a direct call, and it cannot be inlined. This is the concrete cost of `Box<dyn Trait>` over `impl Trait`.

**Case 3: moving large values.** A move in Rust is a `memcpy` of the value's stack representation. Moving a `[u8; 1_048_576]` around by value is a 1 MiB `memcpy` per move, and in a debug build the optimizer will not elide it, which is the standard cause of the "stack overflow when I `Box::new` a big array" complaint (rust-lang/rust#53827): `Box::new(x)` evaluates `x` on the stack first and only then copies it to the heap. The workaround is to build directly on the heap, e.g. `vec![0u8; 1 << 20].into_boxed_slice()`.

`Box` is also the only type in Rust with a genuinely privileged relationship to the compiler: `*boxed` can *move* the contents out, which no user-defined smart pointer can do, because `DerefMove` does not exist as a stable trait. That is worth knowing because it is the answer to "why can't I write my own `Box`."

### `Rc<T>` and `Arc<T>`: the same pointer, one instruction apart

Both are one pointer wide (`size_of::<Rc<u64>>() == size_of::<Arc<u64>>() == 8`). Both point at a heap allocation whose header is two counters ahead of the data:

```
  Rc<T> / Arc<T>  (8 bytes on the stack)
        │
        └──►  ┌──────────────┬──────────────┬─────────────┐
              │ strong: usize│ weak:  usize │  T          │
              │ (AtomicUsize │ (AtomicUsize │             │
              │  for Arc)    │  for Arc)    │             │
              └──────────────┴──────────────┴─────────────┘
              └───── 16 bytes of header on 64-bit ─────┘

  The value is dropped when strong hits 0.
  The ALLOCATION is freed when weak hits 0. (There is an implicit
  weak count of 1 held collectively by all the strong refs, which is
  why a strong-only Rc frees the allocation immediately.)
```

The mechanical difference is one instruction class. `Rc::clone` is `self.strong.set(self.strong.get() + 1)`, a plain load, add, store, no synchronization. `Arc::clone` is `self.inner().strong.fetch_add(1, Ordering::Relaxed)`, which on x86-64 lowers to `lock xadd`, a read-modify-write that must acquire exclusive ownership of the cache line.

Measured, 50,000,000 iterations of clone-then-immediately-drop:

| Operation | ns/op | Notes |
|---|---|---|
| `Rc::clone` + drop | **1.53** | non-atomic inc + dec, stays in L1 |
| `Arc::clone` + drop | **14.44** | `lock xadd` + `lock xsub`, **9.4x `Rc`** |
| bare `AtomicUsize::fetch_add(Relaxed)` | 6.04 | one `lock xadd`; two of these ≈ `Arc` |
| bare `AtomicUsize::load(Relaxed)` | 0.24 | a plain `mov` on x86; loads are cheap |
| 2 threads cloning the *same* `Arc` | 17.36 | +20% from cache-line transfer, on 2 vCPUs |

Read the last row carefully. On a 2-vCPU box the contended penalty is a mild 20%. On a 32-core, 2-socket machine, a single `Arc` cloned in a hot loop by every core is a cache line being pulled across the interconnect thousands of times a second, and that is where a 14 ns operation becomes a 100-500 ns operation. The reason this surprises people is that it does not show up in a single-threaded benchmark at all: the atomic is uncontended, it costs 14 ns, and the profile looks fine. Say this in an interview and you have described a real production failure rather than a textbook one.

The orderings in `Arc` are worth being able to recite because they are the canonical example of "why `Relaxed` is sometimes enough":

- **Clone** uses `Relaxed`. Incrementing the count creates no happens-before requirement: you already had a valid `Arc`, so the value already existed and you are not publishing anything.
- **Drop** uses `fetch_sub(1, Release)`. `Release` is required because anything you wrote through this `Arc` must be visible to whichever thread eventually runs the destructor.
- The **last** dropper, seeing the old value was 1, executes `atomic::fence(Acquire)` *before* touching the data. That `Acquire` fence pairs with every other thread's `Release` decrement, which is what makes it sound to then run `T`'s destructor with exclusive access.
- **Overflow** is handled by comparing against `MAX_REFCOUNT = isize::MAX as usize` (9,223,372,036,854,775,807 on 64-bit) and calling `abort()`, not `panic!`. It aborts rather than unwinding because a panic could be caught and the count would already be corrupt. The bound is `isize::MAX` rather than `usize::MAX` so that a burst of concurrent increments between the check and the abort still cannot wrap.

Two more facts about `Arc` that get asked. `Arc<T>` gives you shared *immutable* access; `Arc::get_mut` returns `Option<&mut T>` and only returns `Some` when strong count is 1 and weak count is 0, and `Arc::make_mut` implements copy-on-write by cloning the inner `T` when the count is above 1. And `Arc<T>: Send + Sync` requires `T: Send + Sync`, which is exactly why `Arc<RefCell<T>>` does not compile: `RefCell` is `!Sync`, so the whole `Arc` loses `Send`. That single compile error is the reason Rust programmers cannot write the "shared mutable HashMap across goroutines" bug that Go's race detector has to catch at runtime.

### Cycles, `Weak`, and the leak Rust does not prevent

Rust's memory safety guarantee does not include "no leaks." Leaking is safe: `std::mem::forget` is a safe function, and `Box::leak` is safe. `Rc`/`Arc` cycles therefore leak, and this is by design rather than an oversight, since a cycle collector would require a tracing runtime, which is precisely what Rust declined to have.

Verified behaviour, two `Rc<Node>` pointing at each other via `RefCell<Option<Rc<Node>>>`:

```
cycle with Rc <-> Rc:
  strong a=2  strong b=2
  <scope ends>
  (no Drop impls ran at all; both nodes leaked)

cycle with Rc -> Rc, back-edge as Weak:
  strong a=1  weak a=1  strong b=2
  <scope ends>
  DROP c
  DROP d
```

`Weak<T>` is the fix. It is created by `Rc::downgrade(&rc)` / `Arc::downgrade(&arc)`, it does not contribute to the strong count, and it does not keep the value alive. To use it you call `.upgrade()`, which returns `Option<Rc<T>>`, giving `None` if the value is already gone. For `Arc`, `upgrade` is a compare-exchange loop on the strong count that refuses to increment from 0, which is what makes it race-free against a concurrent last drop.

The structural rule to state in an interview: **owning edges are `Rc`/`Arc`, back-edges are `Weak`.** Parent owns child strongly, child points at parent weakly. Observer lists in an event bus hold `Weak` so an unregistered observer's memory is actually released. Caches that must not keep entries alive hold `Weak`.

The observable symptom of a cycle leak is not a crash, which is what makes it nasty: it is RSS that climbs monotonically and never returns to baseline after load stops, with the allocator's arena stats showing live allocations that no profiler attributes to a live root. In a GC'd language a cycle is collected and this bug does not exist, so an engineer arriving from Java or Go will not have the reflex. The tools that catch it: `Rc::strong_count` / `Rc::weak_count` assertions in tests, and Miri, whose leak checker reports any allocation still live at the end of `main` that is not reachable from a `static`.

### Interior mutability: `Cell`, `RefCell`, and the panic you will actually see

Interior mutability means mutating a value through a `&T`, which the borrow rules from `T20-rust-ownership` say is impossible. It is possible only because these types are built on `UnsafeCell<T>`, the single primitive in the language that is exempt from the "a `&T` implies the target is immutable" rule. Everything below is a safe wrapper over `UnsafeCell` that enforces the rule some other way.

**`Cell<T>`** enforces it by never handing out a reference at all. `get()` copies the value out (requiring `T: Copy`), `set()` copies a new one in, `replace()`/`take()`/`into_inner()` work without `Copy` because they move rather than borrow. Since no reference to the interior ever escapes, there is nothing to invalidate and no bookkeeping is needed: `size_of::<Cell<u64>>() == 8`, zero overhead versus a bare `u64`, and I measured `Cell::set` at ~0.25 ns/op, which at ~4 GHz is about one cycle. `Cell` cannot fail at runtime. If your data is `Copy` and small, `Cell` is strictly better than `RefCell` and most Rust code reaches for `RefCell` out of habit when `Cell` would do.

**`RefCell<T>`** hands out real `Ref<T>` and `RefMut<T>` guards that deref to `&T` and `&mut T`, so it must track borrows. It does so with one extra word: `size_of::<RefCell<u64>>() == 16` against 8 for the bare `u64`, and `size_of::<RefCell<()>>() == 8`, the flag alone. The flag is an `isize` in a `Cell`, with this encoding:

```
   borrow flag (isize, std::cell::BorrowFlag)
   ────────────────────────────────────────────────
     0     : not borrowed
     n > 0 : n live shared borrows (Ref)      -> borrow() increments
     n < 0 : |n| live mutable borrows (RefMut) -> borrow_mut() decrements
             (normally exactly -1; RefMut::map_split can go lower)

   borrow()      : fails if flag < 0
   borrow_mut()  : fails if flag != 0
```

The check is a load, a compare, a branch, and a store, so uncontended it costs about what `Cell` costs (I measured ~0.23 ns for `borrow()` and ~0.25 ns for `borrow_mut()`, both including the guard's `Drop`). The cost is not the cycles. The cost is that the failure is a **panic at runtime**, and here is the exact text as of 1.97.1, which is *not* what most blog posts say:

```
thread 'main' (21) panicked at b.rs:5:16:
RefCell already borrowed              <- borrow_mut() while a Ref is live
                                         (the error type is BorrowMutError)

thread 'main' (23) panicked at b.rs:10:16:
RefCell already mutably borrowed      <- borrow() while a RefMut is live
                                         (the error type is BorrowError)
```

Older material, and the `Display` impl of these errors in older releases, phrased these as `already borrowed: BorrowMutError` and `already mutably borrowed: BorrowError`. Recognize both spellings; the *type names* `BorrowMutError` and `BorrowError` are stable and are what `try_borrow_mut()` / `try_borrow()` return in the `Err` arm. Verified on 1.97.1: `BorrowMutError` has `Display == "RefCell already borrowed"` and `Debug == "BorrowMutError"`.

Two properties of that panic make it a genuinely bad production failure and are the reason interviewers ask about it.

**Test 1. The message points at the wrong borrow.** The line number in the panic is where the *second* borrow was attempted, not where the still-live first borrow was taken. If the first borrow is a `Ref` held across a function call three frames up, the panic tells you nothing about it. The mitigation is `try_borrow_mut()` at the boundary so you get an `Err` you can log with your own context, plus the discipline of never holding a `Ref` across a call that could re-enter.

**Test 2. It is a re-entrancy bug, so it is rare and load-dependent.** The classic shape is an observer or callback registry: you `borrow()` the list of listeners to iterate it, and one listener's handler calls back into the same structure and does `borrow_mut()` to unsubscribe itself. That path may execute once in ten million requests. The fix is to restructure so the borrow ends before dispatch:

```rust
// The bug (untested sketch, but this is the shape):
for l in self.listeners.borrow().iter() {   // Ref alive for the whole loop
    l.on_event(&ev);                        // if this re-enters -> PANIC
}

// The fix: end the borrow before you call out.
let snapshot: Vec<_> = self.listeners.borrow().iter().cloned().collect();
for l in snapshot { l.on_event(&ev); }      // no borrow held during dispatch
```

The framing for someone coming from Java or Go: `RefCell` is the piece of Rust's guarantee that did *not* move to compile time. Everything else in the borrow checker is static; `RefCell` is the explicit, opt-in, marked-in-the-type-signature admission that this particular aliasing pattern could not be proven statically, so the check happens at runtime instead. That is a much better position than Java's, where the check does not happen at all, but it is not free and it is not a compile error, and pretending otherwise is the mistake.

### `Mutex<T>` and `RwLock<T>`: the same idea, across threads, and why Rust's owns the data

`Mutex<T>` is `RefCell<T>` with "park the thread" instead of "panic", plus the memory-ordering guarantees that make it legal across threads. Structurally it is `struct Mutex<T> { inner: sys::Mutex, poison: poison::Flag, data: UnsafeCell<T> }`. On Linux since Rust 1.62.0 (June 2022) `sys::Mutex` is a futex-based `AtomicU32` rather than a boxed `pthread_mutex_t`, which is why `size_of::<Mutex<()>>() == 8` and `size_of::<Mutex<u64>>() == 16` on this target. `RwLock` needs more state: `size_of::<RwLock<()>>() == 12`, `size_of::<RwLock<u64>>() == 24`.

Measured, uncontended, 30,000,000 iterations:

| Operation | ns/op |
|---|---|
| `Mutex::lock` + write + guard drop | **13.19** |
| `RwLock::read` + read + guard drop | **15.12** |
| `RwLock::write` + write + guard drop | **13.34** |
| `AtomicUsize::fetch_add(Relaxed)` | 6.04 |
| `RefCell::borrow_mut` + write + drop | 0.25 |

Two conclusions. First, an uncontended `Mutex` is about two atomic RMWs, roughly 13 ns, which is 50x more expensive than a `RefCell` and about the same as an `Arc` clone. Second, `RwLock::read` is *not* cheaper than `Mutex::lock` here; it was 15% more expensive. `RwLock` only wins when you have genuinely many concurrent readers and long critical sections, because a read lock still performs an atomic RMW to register the reader, so N readers still contend on the same cache line. The common production mistake is swapping `Mutex` for `RwLock` in a read-heavy path with 50 ns critical sections and finding it got slower.

The structural difference from every other mainstream language is worth stating precisely, because this is where an interviewer with a Java or Go background is listening:

```
 JAVA:                          GO:                        RUST:
 private final Object lock;     var mu sync.Mutex          struct S {
 private Map<K,V> map;          var m map[K]V                m: Mutex<HashMap<K,V>>
 // @GuardedBy("lock") — a                                 }
 // COMMENT. Nothing enforces   // Nothing associates mu
 // it. Forgetting synchronized // with m. Forgetting        // The ONLY way to touch
 // compiles and ships.         // mu.Lock() compiles.       // the HashMap is
                                                             // s.m.lock().unwrap(),
                                                             // which RETURNS a guard.
                                                             // Forgetting is not
                                                             // expressible.
```

Java's `synchronized` and `ReentrantLock` guard a block; the mapping from lock to guarded fields lives in a `@GuardedBy` annotation checked only by optional tools like the Error Prone checker. Go's `sync.Mutex` is a bare struct field with no type-level relationship to what it protects, which is why Go shipped a runtime race detector (Go 1.1, 2013), the ThreadSanitizer-based detector that the Go docs peg at 2x-20x execution time and 5x-10x memory, and which by construction only reports races that actually occurred on the interleaving your test happened to run. Rust needs no such detector for safe code because the failure is not expressible: `HashMap` inside a `Mutex` cannot be reached without the guard, and the guard's `Deref` is what produces the `&mut HashMap`.

Three specifics that come up as follow-ups:

**Poisoning.** If a thread panics while holding a `std::sync::Mutex` guard, the mutex is marked poisoned and every subsequent `lock()` returns `Err(PoisonError)`. This is why `lock()` returns a `LockResult` and why real code is littered with `.unwrap()`. The rationale is that a panic mid-mutation may have left the data in a half-updated state. `PoisonError::into_inner()` gives you the guard anyway if you decide the state is fine. `parking_lot::Mutex` deliberately omits poisoning (and is 1 byte instead of 8), which is the main reason people use it.

**Non-reentrancy.** `std::sync::Mutex` is not reentrant. Java's `synchronized` and `ReentrantLock` are. The std docs state that locking a mutex in a thread that already holds it has *unspecified* behaviour, and that the call will not return: it may deadlock or panic. That difference bites hardest for people porting Java: a recursive helper that locks the same object twice is fine in Java and hangs forever in Rust. The observable symptom is a thread stuck in `futex_wait` with no CPU usage and no log lines, which you diagnose by attaching `gdb`/`lldb` and reading `thread apply all bt`, or with `tokio-console` for async tasks.

**Deadlock is still possible.** The borrow checker prevents *data races*, not *deadlocks*. Two `Mutex`es acquired in inconsistent order across two threads deadlock in Rust exactly as they do in C. Rust gives you nothing here beyond the discipline you would use anywhere: a global lock ordering, or `try_lock` with backoff, or restructuring so only one lock is ever held.

### `Send` and `Sync`: two sentences, then the mechanism

`Send` means: **it is safe to move this value to another thread.** `Sync` means: **it is safe to share `&T` with another thread**, and the formal definition in the standard library is exactly `T: Sync` if and only if `&T: Send`. Those two sentences are the whole semantic content; everything else is derivation.

They are **auto traits**. You do not implement them. The compiler implements them structurally: a struct is `Send` if all of its fields are `Send`, and `Sync` if all of its fields are `Sync`. This recursion bottoms out at a handful of hand-written `impl`s and negative `impl`s in `std`. That means adding one `Rc<T>` field to a struct silently makes the whole struct `!Send`, and the error surfaces hundreds of lines away at a `thread::spawn` or `tokio::spawn`, which is one of the more confusing Rust error experiences and worth naming.

Verified on 1.97.1, with the negatives being actual compile errors:

| Type | `Send` | `Sync` | Why |
|---|---|---|---|
| `Rc<T>` | no | no | counter is a plain `usize`; two threads incrementing it race, count goes wrong, double-free or leak |
| `Arc<T>` where `T: Send + Sync` | yes | yes | counter is `AtomicUsize` |
| `Arc<T>` where `T: !Sync` | no | no | sharing the `Arc` would share `&T` |
| `Cell<T>` / `RefCell<T>` where `T: Send` | **yes** | **no** | moving the whole cell is fine; two threads sharing `&RefCell` would race on the borrow flag |
| `Mutex<T>` where `T: Send` | yes | yes | the lock provides the synchronization `RefCell` lacks |
| `MutexGuard<'_, T>` where `T: Sync` | **no** | **yes** | see below |
| `&T` where `T: Sync` | yes | yes | that is the definition of `Sync` |
| `*const T` / `*mut T` | no | no | raw pointers are `!Send`/`!Sync` by fiat, forcing you to write an explicit `unsafe impl` |

The exact compiler errors, which are worth recognizing on sight:

```
error[E0277]: `Rc<i32>` cannot be sent between threads safely
error[E0277]: `RefCell<i32>` cannot be shared between threads safely
error[E0277]: `std::sync::MutexGuard<'static, i32>` cannot be sent between threads safely
```

**Why `Rc` is neither.** `!Send` because if two threads each held an `Rc` to the same allocation, their non-atomic increments would interleave and lose an update: the count reads low, the value drops while a live `Rc` still points at it, and you get a use-after-free. `!Sync` follows: if `&Rc<T>` could be shared, both threads could clone from it, which is the same race. Note that a shared `&Rc<T>` alone would be harmless if you could only read; it is `clone` that makes it unsound, and the auto-trait system has no way to express "shared but only for these methods," so `Rc` is `!Sync` outright.

**Why `MutexGuard` is `Sync` but not `Send`.** This is the question that separates people who memorized the table from people who understand it. `MutexGuard<'_, T>` is `!Send` because unlocking must happen on the locking thread: POSIX declares `pthread_mutex_unlock` from a thread that does not own the mutex to be undefined behaviour, and even on futex implementations, sending the guard elsewhere would let thread B run the `Drop` that releases a lock thread A acquired. Since `Drop` is what unlocks, and the guard could be moved and then dropped anywhere, `Send` must be denied. But `MutexGuard<'_, T>: Sync` when `T: Sync` is fine, because a `&MutexGuard<T>` only gives you `&T`, and `&T` is safe to share exactly when `T: Sync`. Sharing a reference to the guard never moves the guard and therefore never moves the unlock.

The practical consequence lands in async: holding a `std::sync::MutexGuard` across an `.await` makes the whole future `!Send`, which makes it unusable with `tokio::spawn`, and the error message names the guard type. The fix is either to end the guard's scope before the `.await` (drop it explicitly or use a block) or to use `tokio::sync::Mutex`, whose guard *is* `Send` and whose `lock()` is itself `.await`-able. See `T20-rust-async`.

**When you write `unsafe impl Send`.** You do this when you have a type containing a raw pointer and you know, but the compiler cannot, that moving it across threads is sound. The obligation you are taking on is real and the correct discipline is a `// SAFETY:` comment stating exactly why. A typical honest one: "SAFETY: this raw pointer is the sole owner of a heap allocation that is never aliased, and no other thread holds a pointer into it; it behaves as `Box<T>` and is `Send` for the same reason." A typical dishonest one is no comment at all, which is what code review should catch.

### `unsafe`: the five superpowers, and everything it does not turn off

`unsafe` is the smallest keyword in Rust with the largest misconception attached. It unlocks exactly five things and nothing else. From the Rust Reference and the Book:

1. Dereference a raw pointer (`*const T`, `*mut T`).
2. Call an `unsafe fn` or `unsafe` method.
3. Access or modify a mutable `static`.
4. Implement an `unsafe trait` (`Send`, `Sync`, `GlobalAlloc`, ...).
5. Access the fields of a `union`.

Everything else stays on. In an `unsafe` block the borrow checker still runs on references. Lifetimes are still checked. Move semantics still apply. Type checking is unchanged. `Drop` still fires. The only difference is that these five operations become expressible, and rustc stops asking you to prove they are safe. It does not become permissive; it becomes *silent*, and then the optimizer proceeds on the assumption that you were right.

There are two directions to the keyword, and being able to name both is a real signal:

- `unsafe { ... }` on a block means "**I am discharging** an obligation. I have checked the preconditions."
- `unsafe fn f()` means "**I am imposing** an obligation on my callers. Read my `# Safety` doc comment."

Rust 2024 edition (shipped with 1.85.0, 2025-02-20) sharpened this. `unsafe_op_in_unsafe_fn` is warn-by-default in edition 2024, so the body of an `unsafe fn` is no longer implicitly an `unsafe` block and you must write the inner `unsafe {}` explicitly, forcing the two meanings apart. Edition 2024 also requires `unsafe extern "C" { ... }` blocks and `unsafe` attributes such as `#[unsafe(no_mangle)]`, and promotes `static_mut_refs` (taking a reference to a mutable static) from a warning to deny-by-default, because `&mut SOME_STATIC` is the single easiest way to create two aliasing `&mut` accidentally.

### Undefined behaviour, and why `--release` is where it bites

Undefined behaviour is not "a crash" and it is not "an unspecified result." It is a state in which the compiler's assumptions have been violated and therefore *no* guarantee about the program holds, including guarantees about code that ran before the UB. The Rust Reference maintains the authoritative list: dereferencing dangling or unaligned pointers, data races, breaking pointer aliasing rules, producing invalid values (a `bool` that is not 0 or 1, an out-of-range enum discriminant, a `&T` that is null or dangling), calling a function with the wrong ABI, and executing `unreachable_unchecked`.

The reason UB is a `--release` phenomenon in practice is mechanical, not mystical: at `-O0` the optimizer does almost nothing, so a broken assumption often has no consequence. At `-O` the optimizer *uses* the assumption. Here is a verified pair of runs of the same binary source, `rustc 1.97.1`:

```rust
// ub.rs (verified): this is real, do not run it expecting a stable result
use std::mem::MaybeUninit;

#[inline(never)]
fn read_uninit() -> bool {
    unsafe { MaybeUninit::<bool>::uninit().assume_init() }   // UB: invalid value
}

fn main() {
    let x = read_uninit();
    print!("uninit bool: ");
    if x  { print!("saw-true ");  }
    if !x { print!("saw-false "); }
    println!();
}
```

```
$ rustc -o ubd ub.rs && ./ubd            # debug
uninit bool: saw-false
$ echo $?
0

$ rustc -O -o ubr ub.rs && ./ubr         # release
Illegal instruction (core dumped)
$ echo $?
132
```

Same source, same compiler, same machine. Debug prints a plausible answer and exits 0. Release emits `ud2` and the process dies with SIGILL. rustc even warns at compile time here (`warning: the type 'bool' does not permit being left uninitialized`), which is a good reminder that rustc catches some of this, but it catches it *lexically* and cannot catch it through a function pointer, an FFI boundary, or a raw-pointer read. If your only evidence that unsafe code is correct is "the tests pass in debug," you have no evidence.

### `UnsafeCell<T>`: the one legal door

`UnsafeCell<T>` is not a convenience wrapper. It is the *only* legal way in the entire language to obtain a `&mut T` from a `&T`, and this is enforced by the compiler's own optimizer, not by convention. rustc tells LLVM that `&T` points to memory that will not change (`noalias`, and `readonly` where applicable) for the reference's lifetime. `UnsafeCell` is the marker that suppresses that annotation. Mutating through a `&T` that does not go through an `UnsafeCell` is undefined behaviour even if you never observe a wrong answer, because LLVM has already been told it may cache the load.

This is the load-bearing fact behind everything above. `Cell`, `RefCell`, `Mutex`, `RwLock`, `AtomicUsize`, `OnceCell`, `LazyLock` all contain an `UnsafeCell` at the bottom and differ only in the discipline they wrap around it:

```
   UnsafeCell<T>            "mutation through &T is permitted here"
        │                    (no checks; the ONLY primitive)
        ├── Cell<T>          never hand out a reference        -> can't fail
        ├── RefCell<T>       runtime borrow flag               -> PANICS
        ├── Mutex<T>         futex; blocks the thread          -> BLOCKS/deadlocks
        ├── RwLock<T>        futex; N readers XOR 1 writer     -> BLOCKS
        ├── AtomicU*/I*      hardware RMW instructions         -> can't fail
        └── OnceCell/OnceLock  write-once, then read-only      -> can't fail twice
```

`UnsafeCell<T>` is `#[repr(transparent)]`, so it adds zero bytes: `size_of::<UnsafeCell<u64>>() == 8`. It is `!Sync` (which is why `Cell` and `RefCell` are `!Sync`, and why `Mutex` has to `unsafe impl Sync` explicitly once it has the lock).

### Soundness: the actual obligation

An unsafe abstraction is **sound** if and only if no safe caller, using any combination of its public API in any order, can cause undefined behaviour. That definition has three teeth people miss.

- **Any combination, any order.** A method that is safe on its own may be unsound in combination with another. The classic real bug: a `Vec`-like type with `set_len(usize)` as a *safe* method is unsound, because a caller can set the length past the initialized region and then index, reading uninitialized memory. `Vec::set_len` is correctly an `unsafe fn` for exactly this reason.
- **Including with other sound code.** Your type must remain sound when composed with any other sound crate. This is what makes `unsafe impl Send` so consequential: you are asserting a property that arbitrary third-party threading code will rely on.
- **Panics count.** If your unsafe code leaves an object in a temporarily invalid state and then calls a user closure that panics, unwinding runs `Drop` on the invalid object. This is the "exception safety" problem, and Miri has caught real instances of it in `std` (`Vec` and `BTreeMap` leaking memory under panicky conditions, per Miri's own bug list).

The practical shape of a sound abstraction is: a small, contiguous, heavily commented `unsafe` core with invariants written down; a safe public API that makes the invariants unbreakable; `# Safety` doc sections on every `unsafe fn`; and `// SAFETY:` comments on every `unsafe` block. `clippy::undocumented_unsafe_blocks` and `clippy::missing_safety_doc` enforce the last two mechanically. Turn them on.

### Miri, and the live disagreement about the aliasing model

Miri is an interpreter for Rust's MIR that executes your test suite and checks, at every step, the things rustc structurally cannot. It requires nightly (`rustup +nightly component add miri`, then `cargo +nightly miri test`). What it catches:

- out-of-bounds accesses and use-after-free
- reads of uninitialized memory
- misaligned pointer accesses and misaligned references
- invalid values (a `bool` that is not 0 or 1, an invalid enum discriminant)
- violated intrinsic preconditions (`unreachable_unchecked` reached, `copy_nonoverlapping` with overlapping ranges)
- **data races**, plus emulation of some weak-memory effects, so an atomic load can return a stale value
- **memory leaks**: anything still allocated at the end of execution and not reachable from a `static`
- **aliasing violations**, under Stacked Borrows (default) or Tree Borrows (`-Zmiri-tree-borrows`)

What it fundamentally cannot do, and you must say this part in an interview or you sound naive. Miri executes *one* interleaving of a nondeterministic program; the default seed is 0, and `-Zmiri-many-seeds` explores a range (defaulting to 0..64) but never exhaustively. Miri's default preemption rate is 1% per basic block, address reuse rate 0.5, cross-thread address reuse 0.1, and `compare_exchange_weak` is made to fail 80% of the time, all deliberate nondeterminism knobs to shake out bugs, none of them a proof. Miri reports `-Zmiri-num-cpus` as 1 by default. It has no networking, limited FFI, and it is an interpreter, so it is orders of magnitude slower than native. Most importantly: **Miri finding no UB is not a soundness proof.** Miri tells you that *this execution* of *this test* had no UB. Soundness is a claim about all possible safe callers, which is a proof obligation no testing tool discharges. Miri's own README says this explicitly.

Real Miri diagnostics, quoted from the project's own documentation, so you recognize the shapes:

```
error: Undefined Behavior: Data race detected between (1) non-atomic read on
thread `unnamed-1` and (2) non-atomic write on thread `unnamed-2` at alloc87
   |
24 | ...   *c.0 = 64;
   |       ^^^^^^^^^ (2) just happened here
help: and (1) occurred earlier here
   |
19 |             let _val = *c.0;
   |                        ^^^^
```

```
error: Undefined Behavior: memory access failed: alloc194 has been freed,
so this pointer is dangling
9 |     let x = unsafe { *p };
  |                      ^^ Undefined Behavior occurred here
help: alloc194 was allocated here:  ... Box::new(42)
help: alloc194 was deallocated here: ...
```

```
error: Undefined Behavior: attempting a write access using <254> at
alloc115[0x0], but that tag does not exist in the borrow stack for this location
8 |     unsafe { *target2 = 13 };
  |              ^^^^^^^^^^^^^ this error occurs as part of an access at alloc115[0x0..0x4]
help: <254> was created by a SharedReadWrite retag at offsets [0x0..0x4]
help: <254> was later invalidated at offsets [0x0..0x4] by a Unique retag
```

That third one is the aliasing-model error, and it is where the genuine live disagreement lives. **Present both sides.**

**Stacked Borrows** (Jung, Dang, Kang, Dreyer; POPL 2020) models each memory location as a *stack* of borrow tags. Creating a reference pushes a tag; using a pointer whose tag is not on the stack, or using a tag that has been popped by a later reborrow, is UB. It is strict, it justifies aggressive `noalias` optimizations, and it is Miri's default today. Its problem is that it rejects a lot of real, widely deployed unsafe code that nobody believes is actually buggy.

**Tree Borrows** (Villani, Hostert, Dreyer, Jung; PLDI 2025, Distinguished Paper, 6 of 89 accepted) replaces the stack with a *tree* that mirrors the actual reborrow structure, tracking per-location permissions on each node. It is strictly more permissive in the cases that matter: evaluated on the 30,000 most-downloaded crates, it rejected 54% fewer test cases than Stacked Borrows. The paper's Rocq-mechanized results show it retains most of the optimizations Stacked Borrows enabled and additionally licenses read-read reordering, which Stacked Borrows did not. Miri gained `-Zmiri-tree-borrows` and, as of the December 2025 update, Tree Borrows now tracks `UnsafeCell` at byte granularity as precisely as Stacked Borrows and supports wildcard provenance for integer-to-pointer casts.

The disagreement is not "which is correct" but **which direction Rust should err in while the question is open**, and Miri's README states the tradeoff bluntly: Tree Borrows is more experimental, and while it is sound in the sense of catching everything today's compiler might exploit, the eventual official model is *likely to be stricter than Tree Borrows*, so code that Tree Borrows accepts today may be declared UB later, a risk that is much lower with Stacked Borrows. The practical advice that falls out: run Stacked Borrows in CI; if it flags something you are confident is fine, re-run with `-Zmiri-tree-borrows` to learn whether you are hitting a known Stacked Borrows over-restriction or a real bug. Do not use Tree Borrows to silence a Stacked Borrows error you have not understood.

Adjacent tooling worth naming so you do not sound like Miri is the only option: **Loom** exhaustively explores interleavings for small concurrent data structures (Miri's own README points you at it for "really sure about complicated atomic code"); **ThreadSanitizer** via `-Zsanitizer=thread` on nightly instruments a native binary and is what Go's race detector is built on; **AddressSanitizer** via `-Zsanitizer=address` catches out-of-bounds and use-after-free natively at ~2x cost; **`cargo-fuzz`** and **`proptest`** generate the inputs Miri then executes; and **BorrowSanitizer** is an in-progress project (monthly status updates through 2026) aiming to bring Tree-Borrows-style checks to natively compiled binaries, which would close Miri's biggest gap, which is that Miri cannot run anything touching the network.

---

## Build it from scratch

The exercise that teaches this module is writing `Rc` yourself. It is about 60 lines and it forces you through the header layout, the `Weak` invariant, the `Deref`, and the `Drop` ordering. Reference implementation and tests belong in `labs/rust/03-rust-memory/`.

```rust
// untested sketch: a single-threaded Rc, deliberately without Weak.
// Compare against std's alloc::rc, and run it under `cargo +nightly miri test`.
use std::cell::Cell;
use std::ops::Deref;
use std::ptr::NonNull;

struct RcInner<T> {
    strong: Cell<usize>,   // NOT AtomicUsize: this is the Rc, not the Arc
    value: T,
}

pub struct MyRc<T> {
    ptr: NonNull<RcInner<T>>,   // NonNull, so Option<MyRc<T>> is still 8 bytes
    _marker: std::marker::PhantomData<RcInner<T>>,  // tells dropck we own a T
}

impl<T> MyRc<T> {
    pub fn new(value: T) -> Self {
        let boxed = Box::new(RcInner { strong: Cell::new(1), value });
        MyRc {
            // SAFETY: Box::into_raw never returns null.
            ptr: unsafe { NonNull::new_unchecked(Box::into_raw(boxed)) },
            _marker: std::marker::PhantomData,
        }
    }
    fn inner(&self) -> &RcInner<T> {
        // SAFETY: ptr is valid for as long as self is alive, because self
        // holds one strong count and the allocation lives while strong > 0.
        unsafe { self.ptr.as_ref() }
    }
    pub fn strong_count(this: &Self) -> usize { this.inner().strong.get() }
}

impl<T> Clone for MyRc<T> {
    fn clone(&self) -> Self {
        let c = self.inner().strong.get();
        self.inner().strong.set(c + 1);        // one non-atomic increment
        MyRc { ptr: self.ptr, _marker: std::marker::PhantomData }
    }
}

impl<T> Deref for MyRc<T> {
    type Target = T;
    fn deref(&self) -> &T { &self.inner().value }
}

impl<T> Drop for MyRc<T> {
    fn drop(&mut self) {
        let c = self.inner().strong.get();
        self.inner().strong.set(c - 1);
        if c == 1 {
            // SAFETY: strong just hit 0, so we are the last owner and no
            // other MyRc can observe this allocation again.
            unsafe { drop(Box::from_raw(self.ptr.as_ptr())); }
        }
    }
}
// NOTE: MyRc is automatically !Send and !Sync because NonNull<T> is a raw
// pointer, which is !Send/!Sync by fiat. That is not an accident; it is
// exactly the property we want, and we get it for free.
```

Four deliberate exercises on top of it, each of which teaches one thing this module claims:

**Step 1.** Add `MyWeak<T>` with a second `weak: Cell<usize>` counter. Get the invariant right: the strong refs collectively hold *one* weak count, so the value drops at `strong == 0` but the *allocation* is freed only at `weak == 0`. Getting this wrong is the standard way to write a use-after-free, and Miri will find it.

**Step 2.** Swap `Cell<usize>` for `AtomicUsize` and add `unsafe impl<T: Send + Sync> Send for MyArc<T>`. Now write a test that spawns 8 threads each cloning and dropping 100,000 times, assert the final count is 1, and run it under `cargo +nightly miri test -- --test-threads=1` with `MIRIFLAGS="-Zmiri-many-seeds"`. Then deliberately weaken the drop to `fetch_sub(1, Relaxed)` with no `Acquire` fence and see whether Miri catches it.

**Step 3.** Build the failure. Write the observer-registry shape from the `RefCell` section, with a listener that unsubscribes itself during dispatch, and confirm you get `RefCell already borrowed`. Then fix it with the snapshot pattern and confirm the panic is gone.

**Step 4.** Build the leak. Two nodes with `RefCell<Option<Rc<Node>>>` pointing at each other, `Drop` impls that print, and a `main` that runs them in a scope. Confirm nothing prints. Run `cargo +nightly miri test` and read the leak report. Then convert one edge to `Weak` and confirm both destructors fire. This is the fastest way to internalize that Rust does not prevent leaks.

---

## How it's done in production

The std types are the production types. There is no framework layer here the way there is for HTTP or serialization; what production adds is a small set of crates that fix specific std shortcomings, and a CI discipline.

| Crate | What it replaces | What it actually buys | Cost |
|---|---|---|---|
| `parking_lot` | `std::sync::Mutex`/`RwLock` | 1-byte `Mutex` (vs 8), no poisoning, no `unwrap()` at every call site, fair unlocking option, `try_lock_for` with timeout | not in std, so guard types differ; no poisoning means a panic mid-mutation leaves observable half-state |
| `arc-swap` | `RwLock<Arc<T>>` for read-mostly config | reads become an atomic pointer load with no lock at all; the standard answer for hot-reloadable config | writers pay more; only correct when you replace the whole value, not mutate in place |
| `crossbeam` | `Arc<Mutex<VecDeque<T>>>` | lock-free MPMC channels and epoch-based reclamation | a different, harder-to-reason-about concurrency model |
| `dashmap` | `Arc<RwLock<HashMap<K,V>>>` | sharded locking, so N writers on different keys do not serialize; typically 16-64 shards | iteration semantics are weaker; deadlocks if you hold two entries |
| `once_cell` / std `OnceLock`, `LazyLock` | `Mutex<Option<T>>` for lazy init | write-once then lock-free reads; `LazyLock` stabilized in Rust 1.80.0 (2024) | none worth naming; use these |
| `slotmap` / `petgraph` / `typed-arena` | `Rc<RefCell<Node>>` graphs | arena plus integer indices; no refcount, no cycles, contiguous storage, better cache locality | indices can dangle logically (stale index into a reused slot), which `slotmap`'s generation counters exist to catch |
| `loom` | nothing | exhaustive interleaving exploration for small lock-free structures | combinatorial blowup; only viable for tiny models |

The CI discipline that separates teams that ship sound unsafe code from teams that get lucky:

```yaml
# The four gates. Any crate with `unsafe` should have all four.
- cargo clippy -- -D warnings \
    -W clippy::undocumented_unsafe_blocks -W clippy::missing_safety_doc
- cargo test                                   # native, -O and debug
- rustup toolchain install nightly --component miri
  MIRIFLAGS="-Zmiri-many-seeds=0..16" cargo +nightly miri test
- RUSTFLAGS="-Zsanitizer=address" cargo +nightly test   # what Miri can't run
```

Two notes on that. Miri's slowdown makes it impractical to run the full suite on every PR for a large crate, so the common pattern is a nightly cron job plus a fast `cargo miri test <unsafe-module>` on PRs that touch `unsafe`. And `#[cfg_attr(miri, ignore)]` is the escape hatch for tests that do networking or FFI that Miri cannot execute; used honestly it is fine, used to hide a failing test it is how unsound code ships.

### Failure-mode table

| Symptom | Cause | Fix |
|---|---|---|
| `thread '...' panicked at src/bus.rs:88: RefCell already borrowed` (older wording: `already borrowed: BorrowMutError`), rare, load-dependent, and the line number is the *second* borrow not the first | Re-entrant `borrow_mut()` while a `Ref` from an outer frame is still alive. Classic shape: iterating `listeners.borrow()` and a handler calls back in to unsubscribe | End the borrow before dispatch — clone a snapshot `Vec` out of the `RefCell`, drop the guard, then iterate. Where you cannot restructure, use `try_borrow_mut()` and log with your own context. Long term, prefer `Cell` (cannot panic) or an arena+index design over `Rc<RefCell<_>>` |
| RSS climbs monotonically under steady load and never returns to baseline; heap profiler shows live allocations with no live root; no crash, no error, nothing in logs | `Rc`/`Arc` reference cycle. Rust has no cycle collector and leaking is safe | Make every back-edge a `Weak`. Owning direction is `Rc`/`Arc`, back-reference direction is `Weak` + `.upgrade()`. Assert `Rc::strong_count`/`weak_count` in unit tests. `cargo +nightly miri test` reports the leaked allocation |
| A thread is parked forever, 0% CPU, no log output; `gdb -p <pid>` then `thread apply all bt` shows it in `futex_wait` inside `std::sys::sync::mutex`; the request times out at the load balancer | Re-entrant lock. `std::sync::Mutex` is **not** reentrant (unlike Java's `synchronized`/`ReentrantLock`); std documents the second lock as unspecified and states it will not return. Or: two mutexes acquired in different orders on two threads | Restructure so the lock is taken exactly once per call path — pass `&mut T` down from the guard instead of re-locking in the callee. For multi-lock code, impose and document a global lock order, or use `try_lock` with backoff. `parking_lot::ReentrantMutex` exists but is usually treating the symptom |
| Every `lock()` returns `Err(PoisonError)` after one bad request; all subsequent requests fail with the same error | A thread panicked while holding the guard; std `Mutex` marks itself poisoned permanently | Decide deliberately: `PoisonError::into_inner()` if the data is still consistent, or rebuild the state, or switch to `parking_lot::Mutex` which does not poison. Do not blanket-`unwrap()` and hope |
| Tests pass in debug, `cargo test --release` crashes with `SIGILL (Illegal instruction)`, or a branch that obviously should be taken is skipped, or a `bool` prints as neither true nor false | Undefined behaviour. The optimizer is exploiting an assumption your `unsafe` code broke. Verified example above: reading an uninitialized `bool` prints `saw-false` at `-O0` and dies with SIGILL at `-O` on the same rustc | Do not "fix" it by adding `black_box` or reordering statements — that hides it. Find the actual UB: `cargo +nightly miri test`, plus `-Zsanitizer=address` for the parts Miri cannot run. Then fix the invariant, add a `// SAFETY:` comment stating it, and add a regression test |
| `error: Undefined Behavior: attempting a write access using <254> ... but that tag does not exist in the borrow stack for this location` | Stacked Borrows aliasing violation: a raw pointer derived from a reference was used after a later reborrow invalidated it. Extremely common in hand-rolled linked lists and split-borrow helpers | Re-run with `MIRIFLAGS="-Zmiri-tree-borrows"`. If Tree Borrows also rejects it, it is a real bug — rederive the raw pointer from the live reference at each use, or restructure with `UnsafeCell`/`NonNull` so the provenance chain is unbroken. If only Stacked Borrows rejects it, you have hit a known over-restriction; document it, keep the code, and track the model discussion. **Do not** just switch CI to Tree Borrows |
| `error: Undefined Behavior: Data race detected between (1) non-atomic read on thread 'unnamed-1' and (2) non-atomic write on thread 'unnamed-2'` under Miri, in code that has never failed in production | Miri's data race detector plus its 1%-per-basic-block preemption found an interleaving your hardware has not produced yet. On x86 with its strong memory model, many of these are invisible until you port to aarch64 | Fix it. This is Miri doing exactly its job; "it works on x86" is not a defence. Add the missing `Acquire`/`Release`, or put the data behind a `Mutex`. Re-run with `-Zmiri-many-seeds` to confirm |
| `error[E0277]: 'Rc<T>' cannot be sent between threads safely` pointing at a `tokio::spawn` hundreds of lines from the `Rc` | One `Rc` (or `RefCell`, or raw pointer) field deep inside a struct made the whole aggregate `!Send`, because `Send` is an auto trait derived structurally | Read the error's `note:` chain, which names the offending field path. Swap `Rc`→`Arc` and `RefCell`→`Mutex`, or keep the type thread-local and send a message instead of the value |
| Future is `!Send`, `tokio::spawn` refuses it, error names `std::sync::MutexGuard` | A `std::sync::MutexGuard` is held across an `.await`. `MutexGuard` is `Sync` but `!Send`, because the unlock must happen on the locking thread | Scope the guard so it drops before the `.await` (`{ let g = m.lock().unwrap(); *g += 1; }` then await), or use `tokio::sync::Mutex` whose guard is `Send` and whose `lock()` is awaitable. The std mutex is usually the better choice with a tighter scope |
| Service p99 doubles after a deploy that added a shared counter; `perf` shows time in `lock xadd`; the single-threaded benchmark is unchanged | A single `Arc` or `AtomicUsize` cloned/incremented by every core is one cache line ping-ponging across the interconnect. Uncontended it is 6-14 ns; contended across sockets it is hundreds | Shard it (one counter per core/shard, summed on read), or batch (increment a thread-local and flush every N), or hold the `Arc` once outside the hot loop instead of cloning per iteration. Most `Arc::clone` in hot loops is unnecessary — pass `&Arc<T>` or `&T` |

---

## Tradeoffs & when NOT to use it

**Do not reach for `Rc<RefCell<T>>` as the default shape for graphs and trees.** It is the shape that compiles fastest and it is usually the wrong one. You pay a refcount on every clone, an 8-byte borrow flag per node, pointer-chasing with terrible cache locality, the runtime panic risk, and the cycle-leak risk, all at once. An arena (`Vec<Node>` plus `usize` or `slotmap::Key` indices) removes every one of those: no refcount, no borrow flag, no cycles possible, contiguous storage. `petgraph` and rustc's own data structures work this way. The honest counter-argument, which you should state rather than pretend does not exist: arena indices can go logically stale when a slot is reused, producing a wrong-node bug rather than a crash, which is why `slotmap` adds generation counters. Reach for `Rc<RefCell<_>>` when ownership genuinely is dynamic and shared across subsystems that cannot share an arena.

**Do not use `Arc` where `Rc` suffices, and do not use either where a reference suffices.** The measured penalty is 9.4x per clone. More importantly, most `Arc::clone` calls in real code are inside a loop and are unnecessary: the `Arc` was already available by reference. `clippy::redundant_clone` catches some of these. The test to apply: does this value need to outlive the current scope, or be owned by another thread? If not, pass `&T`.

**Do not use `Arc<Mutex<T>>` as the default concurrency primitive.** It is Rust's `synchronized` and it is overused for the same reason. Before reaching for it, check three alternatives. If the data is read-mostly and replaced wholesale, `arc-swap` turns reads into an atomic pointer load. If the data is a counter or a flag, an `Atomic*` type is 6 ns instead of 13 and cannot deadlock. If ownership can be *moved* between stages, a channel (`std::sync::mpsc`, `crossbeam-channel`, `tokio::sync::mpsc`) is usually both faster and easier to reason about, and it is what Go's culture gets right. `Arc<Mutex<T>>` is correct for genuinely shared, genuinely mutable, genuinely fine-grained state.

**Do not use `RwLock` reflexively for read-heavy workloads.** I measured `RwLock::read` at 15.12 ns against `Mutex::lock` at 13.19 ns uncontended; the read lock was *slower*. A read lock still performs an atomic RMW, so N concurrent readers still fight over the same cache line; `RwLock` only wins when critical sections are long enough that parallel reader execution dominates the acquisition cost. Below roughly a few hundred nanoseconds of work inside the lock, `Mutex` is typically the better choice. Measure it; do not assume.

**Do not write `unsafe` to make an error go away.** The only good reasons are: a shape that safe Rust genuinely cannot express (intrusive lists, self-referential structures, custom allocators), an FFI boundary, or a measured hot path where the safe version's bounds checks or refcounts are demonstrably the bottleneck, and "demonstrably" means a profile, not an intuition. If you write `unsafe`, you owe: a written invariant, a `// SAFETY:` comment per block, `# Safety` docs on every `unsafe fn`, a Miri job in CI, and a small blast radius. If you cannot commit to all five, the safe version with an extra allocation is the correct engineering answer.

**Do not treat Miri as a proof.** Passing Miri means one execution of your tests had no UB. It says nothing about inputs you did not test, interleavings you did not schedule, or safe callers you did not imagine. Teams that say "we're Miri-clean, we're sound" have made a category error. Miri is the best UB *testing* tool that exists for any language, and testing is not verification.

**Do not port Java lock idioms directly.** Java's `synchronized` is reentrant, Rust's `Mutex` is not and will hang. Java's locks guard blocks, Rust's own data. Java has no `Send`/`Sync`, so patterns that pass objects between threads freely will hit compile errors that are correct and that you should fix by changing the design rather than by reaching for `unsafe impl Send`.

**Where Rust genuinely cannot help, and you must say so.** Deadlocks: not prevented, at all. Logical race conditions (memory-safe but wrong-order operations): not prevented. Leaks: not prevented, and `mem::forget` is safe. Priority inversion, lock convoying, and unbounded queue growth: all still yours. `Send`/`Sync` prevents *data races* specifically, which is a narrower and more precise claim than "Rust prevents concurrency bugs." Making that distinction unprompted is the single clearest staff-level signal in this topic.

---

## Interview questions

### Q1 — When do you actually need `Box<T>`?
**Testing:** whether you know the three forcing cases or just think of `Box` as "put it on the heap."
**Answer:** Three cases force it. Recursive types, because `struct Node { next: Node }` has no finite size and rustc emits `E0072: recursive type has infinite size`; boxing the field makes it a fixed 8 bytes. Trait objects, because `dyn Trait` is unsized and can only exist behind a pointer; `size_of::<Box<dyn Debug>>()` is 16 bytes, a data pointer plus a vtable pointer. And large moves, because a move is a `memcpy` of the stack representation, so passing a `[u8; 1<<20]` by value is a 1 MiB copy per move that the optimizer will not elide in a debug build. Outside those three, `Box` is usually unnecessary: an owned `Vec`, `String`, or plain value is already heap-backed or already cheap.
**Follow-up trap:** *"Does `Box::new(big_array)` allocate on the heap directly?"* — no. `Box::new(x)` evaluates `x` first, which means it is constructed on the stack and then copied to the heap, which is rust-lang/rust#53827 and the standard cause of stack overflow when boxing large arrays in debug builds. The optimizer often elides it at `-O` but you cannot rely on that. The reliable fix is to build directly on the heap, e.g. `vec![0u8; 1 << 20].into_boxed_slice()`.

### Q2 — What is the actual cost difference between `Rc` and `Arc`, and where does it come from?
**Testing:** numbers, and whether you understand the cache-line story rather than just "atomics are slower."
**Answer:** `Rc::clone` is a non-atomic load-add-store on a `usize`. `Arc::clone` is `fetch_add(1, Relaxed)`, which on x86-64 lowers to `lock xadd` and requires exclusive ownership of the cache line. I measured clone-then-drop over 50M iterations on rustc 1.97.1 `-O`: `Rc` at 1.53 ns/op, `Arc` at 14.44 ns/op, a 9.4x ratio; a bare `AtomicUsize::fetch_add(Relaxed)` was 6.04 ns, and `Arc` is two of those plus a branch, which reconciles. Both types are 8 bytes on the stack and both add a 16-byte header, two counters, ahead of the value. The part that matters in production is that those numbers are *uncontended*. Under contention the cost is not the instruction, it is the cache line moving between cores; on my 2-vCPU test box two threads on one `Arc` went to 17.36 ns, but on a 32-core two-socket machine the same pattern is hundreds of nanoseconds.
**Follow-up trap:** *"Why does `Arc::clone` use `Relaxed` but `drop` use `Release`?"* — cloning publishes nothing: you already had a valid `Arc`, so the value already exists and no other memory needs to become visible, which makes `Relaxed` sufficient. Dropping must be `Release` because writes you made through this `Arc` have to be visible to whichever thread runs the destructor; the last dropper, on seeing the old count was 1, then executes `atomic::fence(Acquire)` before touching the data, and that fence pairs with every other thread's `Release` decrement to establish exclusive access.

### Q3 — Why is `Rc<T>` neither `Send` nor `Sync`?
**Testing:** whether you can derive it rather than recite it.
**Answer:** `!Send` because the strong count is a plain `usize`, not an `AtomicUsize`. If two threads each held an `Rc` into the same allocation, their read-modify-write increments would interleave and lose an update; the count reads lower than reality, the value gets dropped while a live `Rc` still points at it, and you have a use-after-free. `!Sync` follows for the same reason via `&Rc<T>`: any thread with a shared reference can call `clone()`, which is the same non-atomic increment. Note that the compiler does not reason about this — `Send`/`Sync` are auto traits derived structurally, and `Rc` gets its negative status from an explicit negative impl in `std`. The compile error you actually see is `error[E0277]: 'Rc<i32>' cannot be sent between threads safely`.
**Follow-up trap:** *"So could `Rc` be `Sync` if you removed `clone`?"* — semantically a read-only `Rc` would be harmless to share, but the auto-trait system cannot express "shared, but only for these methods," so `Sync` is an all-or-nothing property of the type. That is exactly why the split is `Rc` versus `Arc` as two types rather than one type with a flag: the decision has to be encoded in the type for the compiler to check it.

### Q4 — Explain `Send` and `Sync` in one sentence each, then tell me why `MutexGuard` is `Sync` but not `Send`.
**Testing:** the definitions, and then the one example that proves you understand them as separate properties.
**Answer:** `Send` means the value can be moved to another thread. `Sync` means `&T` can be shared with another thread, and the formal definition is literally `T: Sync` iff `&T: Send`. `MutexGuard<'_, T>` is `!Send` because unlocking has to happen on the thread that locked: POSIX makes `pthread_mutex_unlock` from a non-owning thread undefined behaviour, and since the guard's `Drop` is what unlocks, allowing the guard to move to another thread would allow the unlock to happen there. `MutexGuard<'_, T>: Sync` when `T: Sync` is fine, because a `&MutexGuard<T>` only yields `&T`, and sharing a `&T` is precisely what `T: Sync` licenses; sharing a reference to the guard never moves the guard, so the unlock stays put. The compile error is `error[E0277]: 'std::sync::MutexGuard<'static, i32>' cannot be sent between threads safely`.
**Follow-up trap:** *"Where does this bite in real code?"* — async. Holding a `std::sync::MutexGuard` across an `.await` makes the whole future `!Send`, and `tokio::spawn` requires `Send`, so you get a confusing error naming the guard type at the spawn site. Fix by scoping the guard so it drops before the await, or switch to `tokio::sync::Mutex` whose guard is `Send` and whose `lock()` is awaitable. Most of the time the std mutex with a tighter scope is the better answer, because `tokio::sync::Mutex` is meaningfully slower and is only needed when the lock must genuinely be held across a suspension point.

### Q5 — What is the exact difference between `Cell<T>` and `RefCell<T>`, and when is `Cell` the right choice?
**Testing:** whether you default to `RefCell` out of habit.
**Answer:** `Cell<T>` never hands out a reference to its interior — `get()` copies out (requires `T: Copy`), `set()` copies in, `replace()`/`take()` move — so there is nothing to invalidate, no bookkeeping, zero overhead (`size_of::<Cell<u64>>()` is 8, same as `u64`), and it *cannot panic*. `RefCell<T>` hands out real `Ref`/`RefMut` guards that deref to `&T`/`&mut T`, so it must track live borrows in an extra `isize` flag: `size_of::<RefCell<u64>>()` is 16 versus 8, and violating the rule is a runtime panic. Both cost about the same in cycles, ~0.25 ns/op in my measurement. So: if the data is small and `Copy` and you only need get/set, `Cell` is strictly better and removes a whole class of runtime failure. Most code that reaches for `RefCell` on a `u64` or a `bool` should be using `Cell`.
**Follow-up trap:** *"What's the borrow flag's encoding, and can it hold more than one mutable borrow?"* — 0 means unborrowed, a positive `n` means `n` live shared borrows, a negative value means mutably borrowed. Normally it is exactly -1, but it can go further negative because `RefMut::map_split` splits one `RefMut` into two disjoint ones, which is sound because the two halves cover non-overlapping parts of the value.

### Q6 — What does a `RefCell` violation actually look like in production, and how do you debug it?
**Testing:** whether you have seen it, and whether you know the message points at the wrong place.
**Answer:** A panic. On rustc 1.97.1 the text is `RefCell already borrowed` when `borrow_mut()` fails, and `RefCell already mutably borrowed` when `borrow()` fails; older releases and most blog posts phrase these as `already borrowed: BorrowMutError` and `already mutably borrowed: BorrowError`, and the error *types* `BorrowMutError`/`BorrowError` are what `try_borrow_mut`/`try_borrow` return. Two things make it nasty. First, the line number is where the *second* borrow was attempted, not where the still-live first borrow was taken, so if the first borrow is a `Ref` held three frames up you learn nothing from the trace. Second, it is a re-entrancy bug, so it is rare and load-dependent — the canonical shape is iterating `listeners.borrow()` and having one handler call back in to unsubscribe itself, a path that may fire once in ten million requests. The fix is to end the borrow before you call out: collect a snapshot `Vec` from the `RefCell`, drop the guard, then dispatch. Where you cannot restructure, `try_borrow_mut()` gives you an `Err` you can log with your own context instead of a bare panic.
**Follow-up trap:** *"Isn't this just Rust admitting the borrow checker failed?"* — yes, and you should say so plainly rather than defend it. `RefCell` is the explicit, opt-in, visible-in-the-type-signature admission that this aliasing pattern could not be proven statically, so the check moved to runtime. That is still better than Java or Go, where the check does not exist at all and the equivalent mistake is silent corruption, but it is not a compile-time guarantee and calling it one is wrong.

### Q7 — How does Rust's `Mutex<T>` differ from Java's `synchronized` and Go's `sync.Mutex`?
**Testing:** the structural point, which is the one thing about Rust concurrency a polyglot engineer should be able to explain in ten seconds.
**Answer:** Rust's `Mutex<T>` *owns* the `T`. The only way to reach the data is `m.lock()`, which returns a `MutexGuard` that derefs to `&mut T`, so "forgot to take the lock" is not expressible. Java's `synchronized` and `ReentrantLock` guard a *block*; the association between a lock and the fields it protects lives in a `@GuardedBy` comment or annotation, enforced only by optional tools like Error Prone. Go's `sync.Mutex` is a bare struct field with no type-level connection to the map or slice next to it, which is exactly why Go shipped a ThreadSanitizer-based race detector in Go 1.1 (2013) — its own docs put the cost at 2x-20x execution time and 5x-10x memory, and it is dynamic, so it only reports races that actually occurred on the interleaving your test ran. Rust needs no detector for safe code because the type system already rejected the program.
**Follow-up trap:** *"So Rust's mutex is strictly better?"* — no, and two specific regressions catch Java people. Rust's `std::sync::Mutex` is **not reentrant**: std documents locking it twice on one thread as unspecified behaviour that will not return, so a recursive helper that is fine in Java hangs in Rust, and the symptom is a thread parked in `futex_wait` with 0% CPU and no logs. And it *poisons*: a panic while holding the guard makes every subsequent `lock()` return `Err(PoisonError)` forever, which is why real code is full of `.unwrap()`. `parking_lot::Mutex` drops poisoning and is 1 byte instead of 8, which is the main reason people use it.

### Q8 — You wrap a hot shared counter in `Arc<Mutex<u64>>` and p99 latency doubles after deploy. Walk me through it.
**Testing:** whether you can connect a type choice to a production symptom and to a fix that is not "add more cores."
**Answer:** The counter is one cache line and every core is writing to it, so it ping-pongs across the interconnect; `perf` will show time in `lock cmpxchg`/`lock xadd` and in `futex` syscalls once threads start actually blocking. Uncontended the numbers are unthreatening — I measured `Mutex` lock+unlock at 13.19 ns and a bare `AtomicUsize::fetch_add` at 6.04 ns — which is exactly why the single-threaded benchmark showed nothing. Three fixes in order of preference. Drop the mutex: a counter needs `Arc<AtomicU64>` with `fetch_add(1, Relaxed)`, which halves the cost and cannot deadlock. Shard it: one padded counter per core or per N shards, summed on read, which removes the contention entirely at the cost of a non-atomic total. Batch it: increment a thread-local and flush every 1,000 events, which is what most metrics libraries do. Also check whether `Arc::clone` is being called inside the loop at all — passing `&Arc<T>` or `&T` is usually enough and saves 14 ns per iteration.
**Follow-up trap:** *"Would `RwLock` help, since most operations are reads?"* — usually not. A read lock still performs an atomic read-modify-write to register the reader, so N readers still contend on the same line; I measured `RwLock::read` at 15.12 ns against `Mutex::lock` at 13.19 ns uncontended, so the read lock was *slower*. `RwLock` wins only when critical sections are long enough that parallel reader execution dominates acquisition cost, roughly hundreds of nanoseconds and up. For read-mostly data that is replaced wholesale, `arc-swap` is the right answer: reads become a plain atomic pointer load with no lock at all.

### Q9 — Your service's RSS grows monotonically under steady load and never drops. No crash, nothing in the logs. What do you check?
**Testing:** whether you know Rust does not prevent leaks, and whether you have the diagnostic path.
**Answer:** First rule out unbounded queues and caches, then check for an `Rc`/`Arc` cycle, because Rust's memory-safety guarantee explicitly does not include leak freedom — `mem::forget` and `Box::leak` are both safe functions, and there is no cycle collector because that would require a tracing runtime. Two nodes holding strong references to each other never reach count 0, so their `Drop` impls never run; I verified this with printing destructors and got zero output at scope exit. The diagnostic path: assert `Rc::strong_count`/`weak_count` in unit tests around the suspect structure, run `cargo +nightly miri test`, whose leak checker reports any allocation still live at the end of execution that is not reachable from a `static`, and use a heap profiler to find allocations with no live root. The fix is structural: owning edges are `Rc`/`Arc`, back-edges are `Weak`, upgraded with `.upgrade()` which returns `Option` and yields `None` once the target is gone.
**Follow-up trap:** *"Why doesn't `Weak` keep the object alive, and what is the weak count actually for?"* — `Weak` does not contribute to the strong count, so it cannot keep the *value* alive, but it does contribute to the weak count, which keeps the *allocation* alive so that `upgrade()` has something valid to read the counters from. The value is dropped when strong hits 0; the allocation is freed when weak hits 0. All the strong references collectively hold one implicit weak count, which is why an `Rc` with no `Weak`s frees its allocation immediately at strong 0. For `Arc`, `upgrade` is a compare-exchange loop that refuses to increment from 0, which makes it race-free against a concurrent last drop.

### Q10 — What exactly does `unsafe` turn off?
**Testing:** the single most reliable filter question in this topic.
**Answer:** It enables exactly five operations and disables nothing else: dereference a raw pointer, call an `unsafe fn`, access or modify a mutable `static`, implement an `unsafe trait`, and access union fields. The borrow checker still runs inside an `unsafe` block. Lifetimes are still checked. Move semantics, type checking, and `Drop` are unchanged. What actually changes is that the compiler stops *asking you to prove* these five things are safe and starts *assuming* you were right, then optimizes on that assumption. That is why `unsafe` is not "permissive mode," it is "silent mode," and why the failure surfaces as miscompiled output rather than a compiler complaint.
**Follow-up trap:** *"What's the difference between `unsafe fn` and an `unsafe` block?"* — opposite directions. An `unsafe` block *discharges* an obligation: "I checked the preconditions." An `unsafe fn` *imposes* one on callers: "read my `# Safety` doc." Rust 2024 edition, shipped in 1.85.0 in February 2025, made this explicit by turning `unsafe_op_in_unsafe_fn` on by default, so the body of an `unsafe fn` is no longer implicitly unsafe and you have to write the inner block. Edition 2024 also requires `unsafe extern "C"` blocks and `#[unsafe(no_mangle)]`, and makes `static_mut_refs` deny-by-default because `&mut SOMESTATIC` is the easiest accidental route to two aliasing `&mut`.

### Q11 — Why is `UnsafeCell` special, and what happens if you mutate through a `&T` without it?
**Testing:** whether you know interior mutability is a compiler-level fact, not a library convention.
**Answer:** `UnsafeCell<T>` is the only construct in the language that legally permits obtaining a `&mut T` from a `&T`. rustc tells LLVM that a `&T` points at memory that will not change for the reference's lifetime — `noalias`, plus `readonly` where applicable — and `UnsafeCell` is the marker that suppresses that annotation. Mutating through a `&T` that is not inside an `UnsafeCell` is undefined behaviour *even if you observe the correct answer*, because LLVM has already been licensed to cache the load, hoist it out of a loop, or reorder around it. Every interior-mutability type bottoms out here: `Cell`, `RefCell`, `Mutex`, `RwLock`, the `Atomic*` family, `OnceCell`, `LazyLock`. They differ only in the discipline layered on top — no references at all, a runtime borrow flag, a futex, or a hardware RMW. `UnsafeCell` is `#[repr(transparent)]` so it costs zero bytes, and it is `!Sync`, which is where `Cell`'s and `RefCell`'s `!Sync` comes from.
**Follow-up trap:** *"So could you implement `Mutex` with just a raw pointer cast instead of `UnsafeCell`?"* — no. Casting `&T` to `*mut T` and writing through it is UB regardless of how the pointer was obtained, because the UB is a property of the `&T` reference existing over that memory, not of the syntax you used to write. That is also why `Mutex` needs `unsafe impl Sync` explicitly: `UnsafeCell` is `!Sync`, so `Mutex` has to assert the property back after adding the lock that justifies it.

### Q12 — Code passes all tests in debug and crashes with SIGILL in release. What is happening and how do you find it?
**Testing:** whether "works in debug, breaks in release" registers as UB rather than as a compiler bug.
**Answer:** That is the signature of undefined behaviour. At `-O0` the optimizer does almost nothing, so a broken assumption often has no visible consequence; at `-O` the optimizer *uses* the assumption, and when the assumption is false it can emit `ud2`, delete a branch it proved unreachable, or produce a value that is simultaneously true and false. I verified the minimal case on rustc 1.97.1: reading an uninitialized `bool` via `MaybeUninit::uninit().assume_init()` prints `saw-false` and exits 0 in debug, and dies with `Illegal instruction (core dumped)`, exit status 132, at `-O`, from the same source on the same machine. The diagnostic path is `cargo +nightly miri test`, which catches uninitialized reads, out-of-bounds, use-after-free, misalignment, invalid values, data races, leaks, and aliasing violations. For anything Miri cannot execute (networking, most FFI), use `-Zsanitizer=address` and `-Zsanitizer=thread` on nightly. What you must not do is make the symptom go away by reordering statements or inserting `black_box` — that hides UB rather than fixing it, and it will return on the next compiler upgrade.
**Follow-up trap:** *"Is integer overflow one of these? It panics in debug and wraps in release."* — no, and this is the distinction to draw. Overflow is *defined* behaviour in both modes: `debug_assertions` enables an overflow check that panics, and without it arithmetic wraps two's-complement. That is a deliberate, specified difference controlled by `-C overflow-checks`, not UB. Conflating "differs between profiles" with "undefined" is the error; UB means no guarantee holds at all, including about code that already ran.

### Q13 — What does it mean for an unsafe abstraction to be sound, and how do you know `Vec` is sound when it is full of `unsafe`?
**Testing:** staff-level. Whether soundness is understood as a property of the API surface rather than of individual blocks.
**Answer:** An abstraction is sound if and only if no safe caller, using any combination of its public API in any order, can cause undefined behaviour. `Vec` is full of `unsafe` internally and is sound because its public API makes the internal invariants — `len <= cap`, the first `len` elements are initialized, the pointer is valid for `cap` elements — unbreakable from outside. The proof that this is load-bearing is `set_len`: if it were a safe method, a caller could set `len` past the initialized region and then index, reading uninitialized memory, so `set_len` is correctly an `unsafe fn` with a documented `# Safety` contract. Three teeth people miss. "Any combination" means two individually safe methods can be jointly unsound. "Composed with other sound code" is why `unsafe impl Send` is so consequential — you are asserting a property arbitrary third-party threading code will rely on. And panics count: if your unsafe code leaves an object temporarily invalid and then calls a user closure that panics, unwinding will run `Drop` on the invalid object. Miri has caught exactly that shape in `std` itself, including `Vec` and `BTreeMap` leaking under panicky conditions.
**Follow-up trap:** *"If your crate passes Miri with no errors, is it sound?"* — no, and this is the answer that matters. Miri tells you that the particular executions of the particular tests you ran contained no UB. Soundness quantifies over all possible safe callers and all interleavings, which no testing tool discharges — Miri's own README states this. Miri runs one interleaving by default (seed 0), `-Zmiri-many-seeds` explores a bounded range defaulting to 0..64, preemption is 1% per basic block, and it cannot execute code that touches the network. Getting to actual verification means model checking or deductive verification; the RustBelt project did that for the core type system and for a handful of `std` types, not for your crate.

### Q14 — What is the current status of Rust's aliasing model, and how would you handle a Stacked Borrows error in CI?
**Testing:** whether you know this is genuinely unsettled and can hold both positions without picking one glibly.
**Answer:** Rust has not stabilized a definition of undefined behaviour for references; there are two candidate models and Miri implements both. Stacked Borrows (Jung et al., POPL 2020) models each location as a stack of borrow tags — creating a reference pushes a tag, a later reborrow pops the ones above it, and using a popped tag is UB. It is strict, it justifies aggressive `noalias` optimization, and it is Miri's default. Tree Borrows (Villani, Hostert, Dreyer, Jung; PLDI 2025, a Distinguished Paper, 6 of 89 accepted) replaces the stack with a tree mirroring the actual reborrow structure. Evaluated over the 30,000 most-downloaded crates it rejects 54% fewer test cases, and its Rocq-mechanized proofs show it retains most Stacked Borrows optimizations while additionally licensing read-read reordering. So the practical procedure: run Stacked Borrows in CI. If it flags something you believe is fine, re-run with `MIRIFLAGS="-Zmiri-tree-borrows"`. If Tree Borrows also rejects it, it is a real bug — rederive the raw pointer from the live reference at each use rather than caching it across a reborrow. If only Stacked Borrows rejects it, you have hit a known over-restriction; document it and track the model discussion.
**Follow-up trap:** *"So should you just switch CI to Tree Borrows and be done with it?"* — no, and the reason is in Miri's own README. Tree Borrows is more experimental, and while it is sound against what today's compiler exploits, the eventual official model is *likely to be stricter than Tree Borrows*, so code Tree Borrows accepts today could be declared UB later. That risk is much lower with Stacked Borrows. Using Tree Borrows to silence an error you have not understood is trading a compile-time-ish signal for a future miscompilation. Keep Stacked Borrows as the gate and Tree Borrows as the diagnostic.

---

## Red flags that fail you

- Saying `unsafe` "turns off the borrow checker." It does not. It enables five operations and changes nothing else about compilation.
- Reaching for `Arc<Mutex<T>>` as the first answer to every shared-state question without naming channels, `Atomic*`, `arc-swap`, or sharding as alternatives.
- Claiming Rust prevents memory leaks. It does not; `mem::forget` and `Box::leak` are safe, and `Rc`/`Arc` cycles leak by design.
- Claiming Rust prevents all concurrency bugs. It prevents *data races*. Deadlocks, logical races, priority inversion, and unbounded queues are all still yours.
- Not knowing that `std::sync::Mutex` is non-reentrant, especially after mentioning a Java background.
- Being unable to say what `Sync` means beyond "thread safe." The definition is `T: Sync` iff `&T: Send`.
- Thinking `Send`/`Sync` are traits you implement rather than auto traits the compiler derives structurally from fields.
- Saying `RwLock` is always better than `Mutex` for read-heavy workloads without qualifying it by critical-section length.
- Treating "passes Miri" as "is sound." Miri tests executions; soundness quantifies over all safe callers.
- Not knowing that mutating through a `&T` requires `UnsafeCell`, and thinking a raw-pointer cast is an equivalent workaround.
- Explaining "works in debug, crashes in release" as a compiler bug rather than as the signature of undefined behaviour.
- Reflexively using `Rc<RefCell<T>>` for every graph or tree without mentioning arena-plus-indices.

## Cheat card

```
LADDER (cost, x86_64, rustc 1.97.1 -O, i5-12450H, measured):
  &T / &mut T ......... 0 ns, 0 bytes. Default. Try this first.
  Box<T> .............. 8 B; Box<dyn Trait> = 16 B (data ptr + vtable).
  Rc::clone+drop ...... 1.53 ns. usize counter. !Send, !Sync.
  Arc::clone+drop ..... 14.44 ns = 9.4x Rc. lock xadd. Send+Sync if T is.
  AtomicUsize fetch_add  6.04 ns  | Atomic load(Relaxed) 0.24 ns
  Cell / RefCell ...... ~0.25 ns. Cell=8 B, RefCell=16 B (isize flag).
  Mutex lock+unlock ... 13.19 ns | RwLock read 15.12 | RwLock write 13.34
  Mutex<()> = 8 B (futex since 1.62) | RwLock<()> = 12 B
  2 threads, one Arc .. 17.36 ns (2 vCPU). Cross-socket: 10x worse.

2x2:  one owner / many owners  x  1 thread / N threads
  Box | Rc          ·  interior mut: Cell,RefCell | Rc<RefCell<T>>
  Box | Arc         ·  interior mut: Mutex,RwLock,Atomic* | Arc<Mutex<T>>
  Rc:Arc :: RefCell:RwLock. Second of each pair = atomic / blocking.

Rc/Arc HEADER: 16 B = strong + weak. Value drops at strong==0;
  ALLOCATION freed at weak==0. Arc: clone=Relaxed, drop=Release,
  last dropper does fence(Acquire). MAX_REFCOUNT=isize::MAX -> abort().
CYCLES LEAK. Owning edge = Rc/Arc. Back-edge = Weak + .upgrade()->Option.

REFCELL PANIC (1.97.1 wording): "RefCell already borrowed" (BorrowMutError)
  / "RefCell already mutably borrowed" (BorrowError). Older: "already
  borrowed: BorrowMutError". Line = the SECOND borrow, not the first.
  Flag: 0=free, n>0 = n shared, n<0 = mutable. try_borrow_mut() -> Result.

SEND = movable to another thread. SYNC = &T movable, i.e. T:Sync iff &T:Send.
  AUTO TRAITS: derived structurally from fields. One Rc field poisons a struct.
  Rc: !Send !Sync (non-atomic count -> lost update -> use-after-free)
  RefCell/Cell: Send YES, Sync NO   |   Mutex<T:Send>: Send+Sync
  MutexGuard: Sync YES, Send NO (unlock must run on the locking thread)
  *const/*mut T: !Send !Sync by fiat -> forces explicit unsafe impl.
  MutexGuard across .await => future is !Send => tokio::spawn rejects it.

UNSAFE = 5 SUPERPOWERS, nothing else:
  1 deref raw ptr  2 call unsafe fn  3 mutable static  4 impl unsafe trait
  5 union field.  Borrowck/lifetimes/types/Drop ALL still on.
  unsafe {} = I discharge an obligation. unsafe fn = I impose one.
  Edition 2024 (1.85.0, Feb 2025): unsafe_op_in_unsafe_fn warn-by-default,
  unsafe extern "C", #[unsafe(no_mangle)], static_mut_refs deny.

UNSAFECELL = the ONLY legal way to get &mut from &. repr(transparent),
  0 bytes, !Sync. Suppresses LLVM noalias. Everything else is built on it.
SOUND = no safe caller, in ANY API combination, can cause UB. Panics count.
UB SIGNATURE: passes debug, SIGILL/wrong branch at -O. Verified: uninit
  bool prints "saw-false" at -O0, dies exit 132 at -O, same source.
  Overflow is NOT UB: it panics with debug_assertions, wraps without.

MIRI: nightly only. cargo +nightly miri test. Catches OOB, UAF, uninit
  reads, misalignment, invalid values, DATA RACES, LEAKS, aliasing.
  Defaults: seed 0, many-seeds 0..64, preemption 1%/basic block,
  cmpxchg_weak fails 80%, num-cpus 1, provenance GC every 10k blocks.
  Miri clean != sound. No networking, limited FFI.
ALIASING MODEL IS UNSETTLED. Stacked Borrows (POPL 2020) = default, strict.
  Tree Borrows (PLDI 2025, Distinguished, 6/89) = -Zmiri-tree-borrows,
  54% fewer rejections over the top 30k crates. README warns the FINAL
  model is likely STRICTER than TB. Gate on SB; use TB to diagnose.

RUST DOES NOT PREVENT: leaks, deadlocks, logical races, lock convoys.
  It prevents DATA RACES. Say the narrow claim; it is the senior signal.
```

## Sources

- [The Rust Reference — Behavior considered undefined](https://doc.rust-lang.org/reference/behavior-considered-undefined.html) — accessed 2026-08-05
- [The Rustonomicon — Send and Sync](https://doc.rust-lang.org/nomicon/send-and-sync.html) — accessed 2026-08-05
- [The Rustonomicon — Implementing Arc](https://doc.rust-lang.org/nomicon/arc-mutex/arc.html) — accessed 2026-08-05
- [`std::sync::Arc` documentation](https://doc.rust-lang.org/std/sync/struct.Arc.html) — accessed 2026-08-05
- [`std::rc` module documentation (Rc, Weak, cycles)](https://doc.rust-lang.org/std/rc/index.html) — accessed 2026-08-05
- [`std::cell` module documentation (Cell, RefCell, UnsafeCell)](https://doc.rust-lang.org/std/cell/index.html) — accessed 2026-08-05
- [`std::sync::Mutex` documentation (poisoning, non-reentrancy)](https://doc.rust-lang.org/std/sync/struct.Mutex.html) — accessed 2026-08-05
- [Miri README — flags, defaults, capabilities, and the Tree Borrows warning](https://github.com/rust-lang/miri/blob/master/README.md) — accessed 2026-08-05
- [Ralf Jung — What's "new" in Miri (and also, there's a Miri paper!), 2025-12-22](https://www.ralfj.de/blog/2025/12/22/miri.html) — accessed 2026-08-05
- [Miri: Practical Undefined Behavior Detection for Rust (POPL 2026)](https://plf.inf.ethz.ch/research/popl26-miri.html) — accessed 2026-08-05
- [Tree Borrows (PLDI 2025, Distinguished Paper) — ETH Zurich PLF](https://plf.inf.ethz.ch/research/pldi25-tree-borrows.html) — accessed 2026-08-05
- [Stacked Borrows: An Aliasing Model for Rust (POPL 2020)](https://plv.mpi-sws.org/rustbelt/stacked-borrows/) — accessed 2026-08-05
- [Ralf Jung — From Stacks to Trees: a new aliasing model for Rust](https://www.ralfj.de/blog/2023/06/02/tree-borrows.html) — accessed 2026-08-05
- [rust-lang/unsafe-code-guidelines — the open UB specification work](https://github.com/rust-lang/unsafe-code-guidelines) — accessed 2026-08-05
- [releases.rs — Rust version status (stable 1.97.1; 1.98.0 beta due 2026-08-20)](https://releases.rs/) — accessed 2026-08-05
- [The Rust Edition Guide — Rust 2024 (unsafe_op_in_unsafe_fn, unsafe extern, static_mut_refs)](https://doc.rust-lang.org/edition-guide/rust-2024/index.html) — accessed 2026-08-05
- [Go — Data Race Detector (2x-20x execution, 5x-10x memory)](https://go.dev/doc/articles/race_detector) — accessed 2026-08-05
- [rust-lang/rust#53827 — Box::new(large) constructs on the stack first](https://github.com/rust-lang/rust/issues/53827) — accessed 2026-08-05
- [BorrowSanitizer — monthly status updates, 2026](https://borrowsanitizer.com/status/march_2026.html) — accessed 2026-08-05
- [parking_lot documentation](https://docs.rs/parking_lot/latest/parking_lot/) — accessed 2026-08-05

## Changelog
- 2026-08-05 — created
