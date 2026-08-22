# Rust async/await, Futures, Tokio, Channels, Cancellation

> **Track:** T20 Rust · **Time:** 2.5h · **Prereqs:** `T20-rust-ownership` (ownership, borrowing, lifetimes assumed known), `T01-python-asyncio` (Python's event loop as the contrast case) · **Updated:** 2026-08-05
> **Module id:** `T20-rust-async` · **Tags:** core, critical, concurrency

## The 30-second version

A Rust `Future` is a lazy, poll-based state machine: `async fn` compiles into a generated enum whose `poll(self: Pin<&mut Self>, cx: &mut Context) -> Poll<T>` method is called by an executor, and it does exactly nothing until something polls it, which is the opposite of Python's `asyncio.create_task` or a Go goroutine, both of which start running the moment you create them. There is no runtime in `std`: `std::future::Future`, `Waker`, and `Poll` are the vocabulary types, and Tokio (1.53.1 as of 20 July 2026) supplies the scheduler, the I/O reactor, and the timer, which is why "async Rust" in practice means "Tokio", and why blocking one of its worker threads (one per core by default) is the single most common production incident on the platform. Because a future is just a value, cancellation is `drop`: you cancel by dropping the future, there is no `CancelledError` to catch and no unwinding through the async frames, which makes `tokio::select!` both the most useful and the most dangerous macro in the ecosystem, since it drops every losing branch at whatever `.await` point it had reached. `Pin` exists because the generated state machine holds references into its own locals across `.await` points, making it self-referential and therefore illegal to move once polled. The three things to get right in production are: never block a worker thread (use `spawn_blocking`, whose pool defaults to a 512-thread cap), never use an unbounded channel where a producer can outpace a consumer, and never call a non-cancellation-safe method inside a `select!` loop.

## Why this gets asked

Async Rust is where a strong systems engineer separates from someone who has read the book. Ownership and borrowing you can pass by reciting rules; async you cannot, because the surprises are all second-order consequences of laziness and poll-based scheduling, and reciting "futures are lazy" without being able to derive what that implies about cancellation, `Pin`, or `Send` bounds is transparent within two follow-ups. The interviewer asking has almost certainly lived one of two incidents. The first is a p99 latency cliff after someone dropped a `std::fs::read_to_string`, a `reqwest::blocking` call, a `rusqlite` query, or a synchronous `bcrypt` hash into an `async fn`: throughput looks fine at low load, then at some concurrency the service falls off a cliff, worker threads sit parked in a syscall, `tokio_console` shows every worker busy and a growing queue, and healthchecks time out because the healthcheck task never gets polled. The second is silent data loss from a `select!` loop that called `read_exact` or `write_all` in a branch, where the loop dropped a half-completed read on every iteration where the other branch fired, corrupting a framed protocol in a way that shows up as sporadic parse errors under load and is unreproducible locally. They want to know whether you can name the mechanism, not just the mitigation.

---

## Lineage: past → present → future

**What came before.** The first serious Rust async story was `futures 0.1` plus `tokio-core` (2016), built on a combinator model borrowed from Scala/Finagle: you built pipelines with `.and_then()`, `.map()`, `.select()`, and the compiler saw a deeply nested generic type like `AndThen<Map<Select<...>>>`. It worked, and it was fast, but the pain that killed it was concrete and well documented. Error types had to unify across every combinator in a chain, so a five-stage pipeline produced type errors hundreds of lines long that named types no human had written. You could not hold a borrow across an asynchronous step at all, because each combinator closure was a separate `'static` unit, so every stage that needed shared state either cloned it or went through an `Arc<Mutex<_>>`, and loops with conditional continuation had to be expressed as `loop_fn` with an explicit `Loop::Continue`/`Loop::Break` enum. The Rust survey feedback of 2017-2018 was blunt: futures 0.1 was the most-cited source of "I gave up." Before that, and outside Rust, the alternatives an engineer at this level already knows are the thread-per-connection model (simple, and fine until roughly 10k-50k concurrent connections where 8 MiB of default stack per thread and kernel scheduler overhead dominate), callback-based reactors (libevent, Node's original design, with the inversion-of-control problem), and green threads: Rust actually shipped green threads with a segmented-stack M:N runtime up to 2014 and removed them in RFC 230 before 1.0, because a mandatory runtime made Rust unusable for embedding in C programs and for `#![no_std]`, and because segmented stacks caused "stack thrashing" when a hot loop straddled a stack boundary. That removal is the reason `std` has no executor today; it is a deliberate 2014 decision, not an oversight.

**Where it stands now.** `std::future::Future`, `Waker`, `Poll`, and `Context` stabilized in Rust 1.36.0 (4 July 2019); `async`/`await` syntax stabilized in 1.39.0 (7 November 2019); `Pin` had landed earlier in 1.33.0 (28 February 2019). The design that won is poll-based and lazy, chosen over the completion-based/eager design (the one C# `Task` and JavaScript `Promise` use) explicitly to make zero-allocation, zero-cost cancellation possible: a poll-based future is a plain value the caller owns, so composing N of them costs one flat state machine rather than N heap-allocated task objects, and dropping one is a `Drop` call rather than a cooperative cancellation protocol. The current consensus is that the core model is right and the ergonomics around it are the problem. Tokio has effectively won the runtime question: it is the async runtime for `hyper`, `axum`, `tonic`, `reqwest`, `sqlx`, the AWS SDK for Rust, Deno, and Linkerd's `linkerd2-proxy`, and its 1.x line has been API-stable since December 2020 with a stated minimum-5-year support commitment. The live disagreements are real and worth naming. First, whether the runtime-agnostic dream is achievable at all: `async-std` was archived in 2024 and its maintainers told users to move to `smol` or Tokio, `smol` and `glommio` (thread-per-core, `io_uring`) persist as genuine alternatives with different tradeoffs, and the practical fact is that most libraries have Tokio-specific traits (`tokio::io::AsyncRead` differs from `futures::io::AsyncRead`) so runtime portability costs a compat shim. Second, whether `Pin` was a design mistake: `withoutboats`, who designed much of it, and Yoshua Wuyts have both written at length about alternatives ("Pin ergonomics", the "unsafe fields"/`&move` proposals), and there is no consensus that the current surface is final. Third, and most contested, is cancellation: dropping a future is cheap and composable but it is also *unbounded*, in that a future can be dropped at any `.await`, and there is no async destructor to run cleanup that itself needs to await, so patterns like "flush the buffer before dying" have no first-class expression. Async drop is still not stable in Rust 1.97.1 (16 July 2026).

**Where it's heading.** High confidence: `async fn` in traits and return-position `impl Trait` in traits (RPITIT) stabilized in Rust 1.75.0 (28 December 2023) and are now the default way to write async traits with static dispatch, and `async-trait` (the proc macro that desugars to `Box<dyn Future + Send + 'a>`, costing one heap allocation per call) should now be reached for only when you genuinely need `dyn Trait`. Async closures (`async |x| { ... }`) with the `AsyncFn`/`AsyncFnMut`/`AsyncFnOnce` trait family stabilized in 1.85.0 (20 February 2025) alongside the Rust 2024 edition, closing the long-standing hole where a closure returning a future could not borrow from its arguments. Medium confidence: `dyn` compatibility for async traits is the most likely next big unblock, with `async_fn_in_dyn_trait` still an incomplete nightly feature as of August 2026; expect it eventually, not soon, and do not claim it shipped. Lower confidence, explicitly speculative: `AsyncIterator` (the `Stream` trait) has been tracked since issue #79024 in 2020 and is still unstable because a faction wants to replace the `poll_next` design with an `async fn next` design before committing; async generators (`gen`/`async gen` blocks) depend on the same decision. Async `Drop` is a genuine open research problem, since running arbitrary async code during unwinding interacts badly with cancellation, and I would not bet on stabilization inside two years. `io_uring` support inside Tokio is real and advancing (Tokio 1.53.1 carries an optional `io-uring 0.7.11` dependency) but is not the default path, and the honest current statement is "opt-in, Linux-only, and the completion-based model fights the poll-based `Future` interface at the buffer-ownership boundary."

---

## Mental model

```
PYTHON asyncio                          RUST async
--------------                          ----------
asyncio.create_task(coro())             let fut = do_thing();
  -> task is SCHEDULED, it WILL run       -> NOTHING HAPPENS. fut is a value
                                             sitting on the stack, inert.

await coro()                            fut.await
  -> drives it now                        -> drives it now (polls it)

                                        tokio::spawn(do_thing())
                                          -> NOW it is a task, NOW it runs

  "eager"                                 "lazy"


THE WHOLE MODEL IN ONE TRAIT:

    pub trait Future {
        type Output;
        fn poll(self: Pin<&mut Self>, cx: &mut Context<'_>) -> Poll<Self::Output>;
    }                //   ^^^^^^^^^^^        ^^^^^^^ carries the Waker
    enum Poll<T> { Ready(T), Pending }

THE CONTRACT (memorize this, it explains every surprise):

  poll() is called. It runs synchronously until it either:
    (a) finishes            -> returns Poll::Ready(value)
    (b) hits something not-yet-ready. Before returning Poll::Pending it
        MUST register cx.waker().clone() somewhere (epoll registration,
        a channel's wait list, a timer wheel slot) so that whoever makes
        it ready will call waker.wake().
  If it returns Pending WITHOUT registering a waker -> the task is lost
  forever. It will never be polled again. This is a "lost wakeup".
  If it never returns Pending at all -> it monopolizes the worker thread.


THE LOOP, END TO END:

  tokio::spawn(fut)
        |
        v
   +-------------+  poll(cx)   +--------+  Pending, waker stashed  +--------+
   |  scheduler  | ----------> | future | -----------------------> | epoll  |
   |  (N workers)|             +--------+                          | timer  |
   +-------------+                                                 | chan   |
        ^                                                          +--------+
        |                        waker.wake()                          |
        +--------------------------------------------------------------+
                     (task pushed back onto a run queue)


WHY Pin: `async fn` becomes a generated enum. Locals that are live
across an .await become FIELDS of that enum. If one of those locals is
a reference to another one of them, the struct points into ITSELF:

    async fn f() {
        let buf = [0u8; 1024];
        let slice = &buf[..];      // <-- borrows a local
        io.read(slice).await;      // <-- ...held ACROSS an await
    }

    generated:  enum F { Start, AtAwait { buf: [u8;1024],
                                          slice: *const u8 /* -> &self.buf */ },
                         Done }

    Move that value in memory and `slice` dangles. Rust's whole model
    says values are freely movable (memcpy). Pin<&mut T> is the type-level
    "I promise not to move this again", and it is required by poll()
    precisely so an executor cannot move a half-run state machine.


CANCELLATION IS drop(). There is no CancelledError. There is no
"cancel token" in the language. You cancel by dropping the future:

    let x = timeout(Duration::from_secs(1), slow_thing()).await;
    // if the timer wins, slow_thing()'s future is DROPPED, right where
    // it was. Its Drop impls run. Its in-flight state evaporates.
```

---

## How it actually works

### The `Future` trait, derived rather than asserted

The entire async model is four items in `std`, all stabilized in Rust 1.36.0:

```rust
// std::future::Future
pub trait Future {
    type Output;
    fn poll(self: Pin<&mut Self>, cx: &mut Context<'_>) -> Poll<Self::Output>;
}

// std::task::Poll
pub enum Poll<T> { Ready(T), Pending }
```

Ask why `poll` takes a `Context` rather than returning a "not ready, call me back in 10ms" hint, and you derive the `Waker`. A busy-poll executor that retries every pending future in a loop burns 100% of a core doing nothing; an executor that sleeps for a fixed interval adds that interval to every latency. So the future must tell the executor how to be woken. `Context` carries exactly one thing that matters: `cx.waker()`, a `&Waker`, which is a fat pointer plus a manually-constructed vtable (`clone`, `wake`, `wake_by_ref`, `drop`). `Waker` is `Send + Sync + Clone`, which is what lets a leaf future hand a clone to an epoll registration on another thread or to an interrupt handler.

The contract has two halves and both are enforced by convention, not by the compiler:

**Rule 1.** If `poll` returns `Pending`, it must first have arranged for `waker.wake()` to be called when progress becomes possible. Violate it and the task is silently lost: no panic, no log, the task just never runs again. This is the "lost wakeup" bug, and it is the number-one bug in hand-written `Future` impls.

**Rule 2.** `poll` must return promptly. Nothing preempts it. There is no signal, no timer interrupt, no GIL release point. A `poll` that loops for 400ms holds a Tokio worker thread for 400ms.

A leaf future (the ones that actually touch the OS) is where the waker is registered. Everything above it is a composition. `tokio::net::TcpStream::read` bottoms out in a `poll_read` that, on `EWOULDBLOCK`, stores `cx.waker().clone()` in the `ScheduledIo` slab entry for that file descriptor and returns `Pending`; Tokio's I/O driver thread runs `epoll_wait`, gets the readiness event, looks up the slab entry, and calls `wake()`, which pushes the task back onto a run queue.

Here is the whole thing, hand-written, so the magic disappears:

```rust
// untested sketch (no rustc available in this session); compiles against
// std only, tokio 1.53 for the runtime.
use std::future::Future;
use std::pin::Pin;
use std::sync::{Arc, Mutex};
use std::task::{Context, Poll, Waker};
use std::time::{Duration, Instant};

struct SharedState { done: bool, waker: Option<Waker> }

pub struct Sleep { shared: Arc<Mutex<SharedState>> }

impl Sleep {
    pub fn new(dur: Duration) -> Self {
        let shared = Arc::new(Mutex::new(SharedState { done: false, waker: None }));
        let s2 = Arc::clone(&shared);
        // A real runtime uses a hierarchical timer wheel; one OS thread per
        // sleep is only acceptable in a teaching example.
        std::thread::spawn(move || {
            std::thread::sleep(dur);
            let mut g = s2.lock().unwrap();
            g.done = true;
            if let Some(w) = g.waker.take() { w.wake(); }   // <-- RULE 1
        });
        Sleep { shared }
    }
}

impl Future for Sleep {
    type Output = ();
    fn poll(self: Pin<&mut Self>, cx: &mut Context<'_>) -> Poll<()> {
        let mut g = self.shared.lock().unwrap();
        if g.done {
            Poll::Ready(())
        } else {
            // Re-store the waker on EVERY poll. The task may have been
            // moved to a different worker thread by work-stealing since
            // the last poll, in which case the old Waker wakes the wrong
            // scheduler slot. `Waker::will_wake` lets you skip the clone
            // when it is provably the same waker.
            g.waker = Some(cx.waker().clone());
            Poll::Pending
        }
    }
}
```

The comment about re-storing the waker on every poll is not pedantry; it is the second-most-common hand-rolled-future bug after lost wakeups, and it manifests as a task that hangs only under load, because only under load does work-stealing actually migrate it.

### `async fn` desugars to a generated state machine

`async fn foo() -> T` is sugar for `fn foo() -> impl Future<Output = T>`. The compiler builds an anonymous type (a *coroutine*, in `rustc` internals, formerly called a generator) whose variants are the await points:

```rust
async fn handle(conn: &mut TcpStream, db: &Pool) -> Result<usize, Error> {
    let mut buf = vec![0u8; 4096];
    let n = conn.read(&mut buf).await?;           // await point 1
    let row = db.fetch(&buf[..n]).await?;         // await point 2
    conn.write_all(&row).await?;                  // await point 3
    Ok(n)
}
```

conceptually becomes (this is illustrative, not the real MIR):

```rust
// untested sketch: illustrative desugaring only
enum HandleFuture<'a> {
    Start { conn: &'a mut TcpStream, db: &'a Pool },
    AwaitingRead  { conn: &'a mut TcpStream, db: &'a Pool,
                    buf: Vec<u8>, inner: ReadFuture<'a> },
    AwaitingFetch { conn: &'a mut TcpStream,
                    buf: Vec<u8>, n: usize, inner: FetchFuture<'a> },
    AwaitingWrite { row: Row, inner: WriteAllFuture<'a>, n: usize },
    Done,
}
```

Four properties fall directly out of this shape and they explain most of what confuses people:

**Step 1.** *Every local live across an `.await` becomes a field.* The size of the future is therefore roughly the sum of the largest simultaneously-live set of locals, plus the nested futures' sizes. `rustc` does apply variant overlap since the 1.65-era layout work, but it is not perfect: a 4096-byte stack buffer held across an await makes your future at least 4 KiB, and if you `tokio::spawn` it, that 4 KiB is heap-allocated per task. Services that spawn 100,000 tasks each holding a 64 KiB buffer across an await are allocating 6.4 GiB before they have processed a byte. The fix is to `Box::pin` large futures at the spawn site or (better) shrink the buffer live-range.

**Step 2.** *Locals not live across an await are ordinary stack locals inside `poll`*, cost nothing, and are invisible in the future's size. This is why moving a big allocation to *after* the last await, or scoping it in a block that ends before an await, is a real and measurable optimization.

**Step 3.** *A borrow held across an await is a self-reference.* `&buf[..n]` in the example above is a reference into `buf`, which is itself a field of the same enum. That is the entire reason `Pin` exists.

**Step 4.** *The future is inert until polled.* Calling `handle(conn, db)` runs zero lines of the body. It constructs `HandleFuture::Start` and returns. Python's `asyncio.create_task` schedules; Go's `go f()` starts a goroutine on the run queue; Rust's `handle(...)` does neither. This is the single highest-value contrast for someone coming from asyncio, and it is why `#[must_use]` is on `Future` and why the `unused_must_use` lint firing on an async call is almost always a real bug.

### `Pin`, properly

`Pin<P>` where `P: Deref` is a wrapper that removes the ability to get a `&mut P::Target` out (which is what you would need to `mem::swap`, `mem::replace`, or move the value) unless `P::Target: Unpin`. `Unpin` is an auto trait implemented for almost everything: every primitive, every struct of `Unpin` fields, `Box<T>`, `Vec<T>`, `&mut T`. The types that are *not* `Unpin` are precisely the compiler-generated coroutines (and anything containing one, and `PhantomPinned`).

So the rule is: `Pin<&mut T>` is a no-op wrapper for the 99% of types that are `Unpin`, and a genuine movement prohibition for the compiler-generated async state machines that need it. Read it as "this value is now at a stable address and will stay there until it is dropped."

The pinning contract, stated as an invariant: once a value has been observed through a `Pin<P>` where `P::Target: !Unpin`, it must not move again, and its memory must not be invalidated or reused until its `Drop` runs. That second clause is the *drop guarantee*, and it is why `Pin` is a `unsafe`-to-construct-from-a-reference type (`Pin::new_unchecked`) while `Pin::new` is safe only for `Unpin` targets.

Two safe ways to pin in practice:

```rust
// untested sketch
use std::pin::pin;

// 1. Heap pinning. One allocation, the future gets a stable heap address,
//    and `Pin<Box<F>>` is itself movable (you move the Box, not the F).
let mut fut = Box::pin(some_async_fn());

// 2. Stack pinning via the `pin!` macro (std, stabilized 1.68.0, March 2023).
//    Zero allocation. Shadows the binding so you cannot move the original.
let mut fut = pin!(some_async_fn());

// Both give you something you can pass to `Pin::as_mut()` and poll,
// or `.await` in a loop, or hand to select! repeatedly.
```

`.await` on a local future does not require you to pin anything by hand, because the enclosing `async` block pins it structurally: it becomes a field of the outer state machine, and the outer machine is itself pinned by whoever polls it. You only reach for `Box::pin`/`pin!` when you need to poll a future *by hand*, store a `dyn Future`, hold a future across loop iterations (the `select!`-in-a-loop pattern), or break a recursive `async fn` (which is otherwise an infinitely-sized type, and the compiler tells you exactly this: "recursion in an async fn requires boxing").

The practical `Pin` diagnostics you should recognize on sight: `` `dyn Future<Output = T>` cannot be unpinned `` and `` the trait bound `F: Unpin` is not satisfied `` almost always mean "add `Box::pin` or `pin!`", and `` cannot borrow data in dereference of `Pin<&mut ...>` as mutable `` means you need `Pin::as_mut()` rather than `&mut *pinned`.

### Executors: what Tokio actually does with your future

Tokio 1.53.1 (published 20 July 2026) ships three flavours, selected by `Runtime::Builder` or by `#[tokio::main(flavor = "...")]`:

| Flavour | Threads | Work-stealing | `!Send` futures | Use when |
|---|---|---|---|---|
| `new_multi_thread` (default) | `worker_threads`, default = number of CPU cores, override with `TOKIO_WORKER_THREADS` | yes | no (`spawn` requires `Send`) | servers, anything CPU-parallel |
| `new_current_thread` | 1 | n/a | via `spawn_local` in a `LocalSet` | CLIs, tests, embedded, per-core sharding |
| `LocalRuntime` | 1 | n/a | yes, `spawn` accepts `!Send` directly | single-threaded code with `Rc`/`RefCell` throughout |

The multi-threaded scheduler is a work-stealing design; the documented behaviour "at the time of writing" in the `tokio::runtime` module docs is precise enough to quote in an interview:

- One **global injection queue** plus one **local queue per worker thread**. The local queue is a fixed-size ring holding **at most 256 tasks**; overflow moves **half** of them (128) to the global queue.
- A worker prefers its local queue, and checks the global queue every `global_queue_interval` local pops. For the **current-thread** scheduler that interval defaults to **31**. For the **multi-thread** scheduler, if you do not set it explicitly, Tokio computes it dynamically from the `worker_mean_poll_time` metric, targeting a global-queue check roughly every **10ms**.
- Every **61** consecutive task polls (`event_interval`, same default for all schedulers), or whenever the run queues are empty, the worker parks in `epoll_wait`/`kqueue`/IOCP to pick up I/O and timer readiness.
- If both queues are empty, the worker **steals half** the tasks from a randomly-chosen peer's local queue. If stealing fails, it parks.
- The **LIFO slot**: when a running task wakes another task, the woken task goes into a single-slot LIFO register rather than the queue, and is polled immediately next. This is a latency optimization for request/response ping-pong (the wake-ee's data is hot in cache). It is bounded: after **3 consecutive** LIFO-slot uses the slot is temporarily disabled so the worker cannot starve its queue, and the task in the LIFO slot **cannot be stolen** by other workers. Disable it with `disable_lifo_slot()` if you have a bimodal workload where the ping-pong partner is expensive.
- A task woken from a **non-worker** thread always goes to the global queue.

The rewrite that produced this scheduler is documented in Tokio's own October 2019 post, with numbers you can quote: `chained_spawn` went from 2,019,796 ns/iter to 168,854 ns/iter (about 12x), `ping_pong` from 1,279,948 to 562,659 ns/iter (2.3x), `spawn_many` from 10,283,608 to 7,320,737 ns/iter (1.4x), `yield_many` from 21,450,748 to 14,638,563 ns/iter (1.5x). The end-to-end number that matters more: a `hyper` "Hello World" benchmark went from 113,923 to 152,258 requests/sec, a 34% improvement, and `tonic` gained roughly 10%.

**Cooperative budgeting.** Tokio gives each task a budget of **128** operations per poll (`Budget(Some(128))` in `tokio::task::coop`). Tokio's own resource futures (channel `recv`, socket `read`, mutex `lock`) decrement it, and when it hits zero they return `Pending` *and immediately wake themselves*, forcing a yield back to the scheduler. This is what stops `while let Some(x) = rx.recv().await {}` on an always-ready unbounded channel from monopolizing a worker forever. It only works for futures that participate; a hand-written future or a pure-compute loop is invisible to it. `tokio::task::coop::unconstrained(fut)` opts out, and `tokio::task::yield_now().await` yields manually.

### `spawn` vs `spawn_blocking` vs `block_in_place`

```rust
// untested sketch
tokio::spawn(async move { ... });                 // async work, worker pool
tokio::task::spawn_blocking(move || { ... });     // sync work, BLOCKING pool
tokio::task::block_in_place(move || { ... });     // sync work, THIS worker,
                                                  // after handing off its queue
```

`tokio::spawn` takes a `Future + Send + 'static` and returns a `JoinHandle<T>` which is itself a future resolving to `Result<T, JoinError>`. Two behaviours to know cold: the task starts running immediately (this is the one place Rust is eager, because `spawn` hands the future to the scheduler), and **dropping the `JoinHandle` does not cancel the task**, it detaches it. To cancel you call `handle.abort()`, which schedules the task to be dropped at its next `.await` point; `abort()` on a task that is currently inside a long synchronous stretch does nothing until it yields.

`spawn_blocking` moves a closure to a separate pool. The defaults, from `runtime::Builder`:

- `max_blocking_threads` default is **512**. It is a cap, not a preallocation: threads are created on demand and exit when idle.
- `thread_keep_alive` default is **10 seconds** of idleness before a blocking thread exits.
- The blocking pool count is **separate from and does not include** the async worker threads.
- Beyond the cap, `spawn_blocking` calls queue.
- Blocking tasks **cannot be aborted** once started. `handle.abort()` on a `spawn_blocking` task is a no-op. Runtime shutdown waits for them indefinitely unless you use `Runtime::shutdown_timeout`.
- On a `current_thread` runtime, `spawn_blocking` still spawns real OS threads; the single scheduler thread is only for async code.

That 512 default is tuned for **I/O** blocking (a `std::fs` read, a blocking Postgres driver), where threads spend their time parked in a syscall. For **CPU-bound** work it is far too high: 512 threads doing SIMD on a 16-core box is a 32x oversubscription and you will see context-switch storms in `pidstat -w` and a p99 that scales with the oversubscription factor. Gate CPU work behind a `Semaphore` sized to core count, or use `rayon` and bridge with a `oneshot` channel.

`block_in_place` is the escape hatch when the blocking work is *inside* a task you cannot easily restructure: it tells the current worker "I am about to block", the worker hands its local queue and LIFO slot to another thread (spawning one if needed), then runs the closure inline. Three constraints: it **panics on a `current_thread` runtime** (there is no peer to hand off to), it does not help anything running concurrently *within the same task* (a `join!` sibling is stuck), and it cannot be cancelled.

The decision table:

| Work | Duration | Use |
|---|---|---|
| async I/O | any | `tokio::spawn` |
| blocking I/O (file, sync DB driver) | short, bounded | `spawn_blocking` |
| blocking I/O | long-lived/infinite loop | `std::thread::spawn` + a channel; do not occupy a pool slot forever |
| CPU-bound | < ~100µs | just do it inline, the yield overhead is not worth it |
| CPU-bound | 100µs to ~10ms | `spawn_blocking` + `Semaphore(num_cpus)`, or chunk it with `yield_now()` |
| CPU-bound | > 10ms, parallelizable | `rayon` pool, bridged by `oneshot` |
| sync code you cannot move, already in a task | short | `block_in_place` (multi-thread runtime only) |

### The blocking-the-executor failure, with symptoms

This is the interview answer they are fishing for, so know the observable signature and not just the rule.

```rust
// The bug. Looks completely innocent in review.
async fn handler(req: Request) -> Response {
    let cfg = std::fs::read_to_string("/etc/app/policy.json").unwrap(); // 3ms on a cold page cache
    let hash = bcrypt::hash(&req.password, 12).unwrap();                // ~250ms at cost factor 12
    ...
}
```

On an 8-core box, the multi-thread runtime has 8 worker threads. Each `bcrypt` call at cost factor 12 pins one worker for ~250ms. With 8 concurrent requests every worker is occupied; the ninth request's task sits in a run queue and is not polled at all. The characteristic symptoms, in the order you will see them:

- **A latency cliff, not a slope.** Throughput and p99 look flat and healthy up to concurrency 8, then p99 jumps from ~5ms to 250ms, then 500ms, then 750ms, in clean 250ms steps as queue depth grows. A gradual degradation curve means contention; clean quantized steps mean a fixed-cost blocking call times queue position.
- **Low CPU with high latency**, if the blocker is I/O rather than compute: all 8 workers are in `D` state or parked in a `read()` syscall, load average is 8, CPU utilization is 4%.
- **Timers fire late.** `tokio::time::sleep(Duration::from_millis(10))` returns after 260ms, because the timer's `wake()` landed but nothing polled the task. This is the tell that distinguishes "the executor is blocked" from "the downstream is slow": your own internal timeouts blow through their deadlines.
- **Healthchecks fail while the service is up.** The `/healthz` task cannot be polled, so an orchestrator kills a pod that is actually fine, which is how a latency problem becomes a crash-loop.
- **`tokio-console` shows it directly.** The task list shows non-zero "busy" duration with a long poll time; the `warn` for "task has been busy for N ms" fires. `RUSTFLAGS="--cfg tokio_unstable"` plus the `console-subscriber` crate is the tool; `RuntimeMetrics::worker_mean_poll_time` and `injection_queue_depth` are the two metrics to alert on.
- **A stack dump shows the smoking gun.** `gdb -p $PID -ex "thread apply all bt"` or `tokio_unstable`'s taskdump shows every `tokio-runtime-worker` thread inside `__libc_read` or a crypto routine rather than `epoll_wait`.

The threshold to state in an interview: **any synchronous operation that can exceed 10-100µs should not run on a worker thread.** Tokio's own guidance is around 10-100µs; treat 100µs as the "measure it" line and 1ms as the "definitely move it" line.

### `Send` bounds, and why `RefCell` across an `.await` fails to compile

`tokio::spawn` requires `F: Future + Send + 'static`. `Send` on a future means "the generated state machine is safe to move between threads", which the compiler computes structurally: the future is `Send` iff **every field**, which is to say every local held across an `.await`, is `Send`.

```rust
// untested sketch
use std::cell::RefCell;
use std::rc::Rc;

async fn bad(state: Rc<RefCell<Vec<u8>>>) {
    let mut guard = state.borrow_mut();     // guard: RefMut<'_, Vec<u8>>  -> !Send
    guard.push(1);
    tokio::time::sleep(Duration::from_millis(1)).await;   // guard is LIVE here
    guard.push(2);
}

tokio::spawn(bad(rc));   // error: future cannot be sent between threads safely
                         // note: future is not `Send` as this value is used
                         //       across an await
                         // note: `RefCell<Vec<u8>>` is not `Sync`
```

`RefMut` is `!Send` because `RefCell`'s borrow flag is a plain `Cell<isize>` with no atomics; if the guard moved to another thread, two threads could decrement the flag concurrently and the "exclusive borrow" invariant would be a data race rather than a panic. The compiler is not being fussy: it is telling you that a work-stealing scheduler may move this task to another worker at exactly this `.await`, so the guard would cross a thread boundary.

The four real fixes, in order of preference:

1. **Shrink the borrow's live range** so it does not cross the await. Adding a block, or `drop(guard)` before the await, fixes it with zero cost and is right about 70% of the time.
2. **Use `tokio::sync::Mutex`** if you genuinely need to hold the lock across an await. Its guard is `Send`, and its `lock()` is async so it yields rather than blocking a worker. It is roughly an order of magnitude slower than `std::sync::Mutex` in the uncontended case, so use it only for this case.
3. **Use `std::sync::Mutex` (or `parking_lot`) and never hold it across an await.** For short critical sections this is the correct default and Tokio's own docs recommend it. `std::sync::MutexGuard` is `Send` since Rust 1.19 if `T: Send`, but holding a *blocking* mutex across an await risks a deadlock: worker A holds the lock and yields, worker B blocks on the lock, and if every worker ends up blocking on it, nobody can ever poll the task that holds it.
4. **Restructure to message passing** (`mpsc` to an owning actor task), which removes the shared-mutable-state question entirely and is the idiomatic Rust answer at scale.

If the future genuinely must be `!Send`, `tokio::task::spawn_local` inside a `LocalSet`, or the `LocalRuntime` flavour, will run it on one thread.

`'static` on the spawn bound is the same story as `thread::spawn`: the task may outlive the caller's stack frame, so it cannot hold a borrow of a local. This forces `Arc` for shared state, or `move` of owned data. Scoped async tasks (the `async` analogue of `std::thread::scope`) are a genuine gap in the ecosystem; `tokio::task::JoinSet` plus `Arc` is the practical workaround, and `async_scoped` exists but requires `unsafe` reasoning about forgotten futures.

---

## Build it from scratch

The exercise that makes the model click is writing an executor in about 80 lines. It fits in one file and there is nothing hidden.

```rust
// untested sketch (no rustc in this session). Deps: futures = "0.3" for
// ArcWake only; everything else is std. Lab: (lab pending)
use std::future::Future;
use std::pin::Pin;
use std::sync::mpsc::{sync_channel, Receiver, SyncSender};
use std::sync::{Arc, Mutex};
use std::task::Context;
use futures::task::{waker_ref, ArcWake};

// A task = a pinned, boxed, type-erased future + the channel it re-queues on.
struct Task {
    future: Mutex<Option<Pin<Box<dyn Future<Output = ()> + Send>>>>,
    sender: SyncSender<Arc<Task>>,
}

// This IS the Waker. wake() means "put me back on the run queue".
impl ArcWake for Task {
    fn wake_by_ref(arc_self: &Arc<Task>) {
        arc_self.sender.send(arc_self.clone()).expect("run queue full");
    }
}

pub struct Executor { ready: Receiver<Arc<Task>> }
pub struct Spawner  { sender: SyncSender<Arc<Task>> }

pub fn new_executor_and_spawner() -> (Executor, Spawner) {
    const MAX_QUEUED: usize = 10_000;          // BOUNDED on purpose. See below.
    let (sender, ready) = sync_channel(MAX_QUEUED);
    (Executor { ready }, Spawner { sender })
}

impl Spawner {
    pub fn spawn(&self, fut: impl Future<Output = ()> + Send + 'static) {
        let task = Arc::new(Task {
            future: Mutex::new(Some(Box::pin(fut))),   // <-- pinned ONCE, here
            sender: self.sender.clone(),
        });
        self.sender.send(task).expect("run queue full");
    }
}

impl Executor {
    pub fn run(&self) {
        while let Ok(task) = self.ready.recv() {
            let mut slot = task.future.lock().unwrap();
            if let Some(mut fut) = slot.take() {
                let waker = waker_ref(&task);
                let mut cx = Context::from_waker(&waker);
                // THE ENTIRE RUNTIME IS THIS LINE.
                if fut.as_mut().poll(&mut cx).is_pending() {
                    *slot = Some(fut);   // not done: keep it, wait for wake()
                }
                // if Ready: we dropped `fut`, the task is complete and freed.
            }
        }
    }
}
```

Run it with the `Sleep` future from earlier and you have a working single-threaded runtime with real timers. What you should notice while writing it:

- **`Box::pin` happens exactly once, at spawn.** After that the future never moves; the executor only ever takes a `Pin<&mut>` to it via `as_mut()`. That is the pinning contract made concrete.
- **`wake()` is just "push onto a queue".** There is no magic and no compiler involvement. Tokio's version pushes onto a worker's local queue or the LIFO slot instead of an `mpsc`, and that difference is the entire scheduler.
- **The run queue must be bounded** or the executor is a memory leak under a wake storm. Tokio solves this differently (fixed 256-slot local queues that spill to the global queue), but the pressure is the same.
- **Nothing preempts `poll`.** Put a `std::thread::sleep(Duration::from_secs(1))` inside one of your futures and watch every other task stall for a second. That is the executor-blocking incident, reproduced in five lines.

Three extensions worth doing in the lab, each of which teaches one production concept:

**Test 1.** Make the executor multi-threaded (N threads all `recv`ing from a crossbeam channel) and observe that your futures now need `Send`, and that an `Rc` in one of them fails to compile. That is `T20-rust-async`'s `Send` bound, discovered rather than memorized.

**Test 2.** Implement `select2(a, b)`: poll `a`, if `Pending` poll `b`, return whichever is `Ready`, and drop the other. Then run it with a future that logs in its `Drop` impl and watch the losing branch die mid-flight. That is cancellation, and it is where cancellation-safety stops being abstract.

**Test 3.** Implement the coop budget: a thread-local counter decremented on each `poll` of your `Sleep`, returning `Pending` plus a self-wake at zero. Then remove it and starve the executor with a `ready!`-immediately future to see why 128 exists.

---

## How it's done in production

### Channels: pick the right one, and bound it

Tokio ships four channel types in `tokio::sync`. They are not interchangeable and the choice is a design decision, not a preference.

| Channel | Shape | Capacity | Cancellation-safe `recv`? | Use for |
|---|---|---|---|---|
| `mpsc::channel(n)` | multi-producer, single-consumer | bounded, `n` (panics if `n == 0`) | yes | work queues, actor inboxes, backpressure |
| `mpsc::unbounded_channel()` | multi-producer, single-consumer | unbounded | yes | only when the producer is provably rate-limited |
| `oneshot::channel()` | one value, once | 1 | yes | request/response, "call me back with the result" |
| `broadcast::channel(n)` | multi-producer, multi-consumer, every receiver sees every value | bounded ring, rounded **up to the next power of two** | yes (returns `Lagged`, does not close) | shutdown fan-out, pub/sub, config change events |
| `watch::channel(init)` | multi-producer, multi-consumer, **only the latest value is retained** | 1 | `changed()` is cancel-safe | config reload, health state, shutdown flags |

Details worth knowing exactly, because they are the follow-up questions:

- `mpsc::channel(n)` gives you `n` buffered messages **plus** one reserved slot per outstanding `Sender` permit, so the true high-water mark is `n + number_of_senders` in the worst case. `Sender::send().await` waits for capacity, which is exactly the backpressure you want. `try_send` returns `TrySendError::Full` immediately, which is what you want at an ingress boundary where shedding beats queueing.
- `broadcast::channel(3)` allocates a ring of length **4**, and a receiver is only marked `Lagged` once it falls more than 4 messages behind. `Lagged(n)` does **not** close the receiver: the cursor jumps forward to the oldest retained value and the next `recv()` succeeds. A `broadcast` receiver loop that treats `Lagged` as fatal and returns is a bug that shows up as subscribers silently vanishing under burst load.
- `watch` marks the initial value as **seen**, so `changed()` will not return until a *subsequent* send. Use `borrow_and_update()` to read and mark seen; `borrow()` reads without marking. A `watch` receiver holding a `Ref` from `borrow()` across an `.await` blocks all senders, because `borrow()` takes a read lock on an `RwLock`; this is a classic self-inflicted deadlock.
- `oneshot::Sender::send` is **not** async and returns `Result<(), T>` giving your value back if the receiver is gone. `oneshot::Receiver` implements `Future` directly and is cancel-safe. Dropping the `Sender` makes the `Receiver` resolve to `Err(RecvError)`, which is the standard way to signal "the worker died".

**Why unbounded channels are a memory leak waiting to happen.** `unbounded_channel().send()` is synchronous and infallible-while-open. It cannot apply backpressure, by construction. If your producer is a network listener and your consumer does 3ms of work per message, then at 1,000 messages/sec ingress and 333 messages/sec service rate the queue grows by 667 messages/sec forever. At 4 KiB per message that is 2.7 MiB/sec, so a 4 GiB container OOMs in about 25 minutes. Two things make it worse than a plain leak: first, latency degrades before memory does, since queue depth *is* latency by Little's Law (a 100,000-deep queue at 333/sec service rate is a 300-second delay, so every message that comes out is already past its deadline); second, the OOM kill is attributed to the consumer, not the producer, so the postmortem chases the wrong service. Bounded channels turn an unbounded latency problem into an immediate, visible, local error at the producer, which is the whole point. The narrow legitimate uses of unbounded are: sending from sync code where you cannot await (though `blocking_send` on a bounded channel is usually better), a strictly rate-limited producer such as a timer tick, and avoiding a deadlock cycle where a bounded send could block the very task that drains the channel. Anything else, bound it and instrument `Sender::capacity()`.

### Cancellation, in three layers

**Layer 1: drop is cancel.** There is no other mechanism in the language. `tokio::time::timeout(dur, fut)` is a future that polls `fut` and a `Sleep`; when the `Sleep` wins, `timeout` returns `Err(Elapsed)` and `fut` is dropped where it stood. What that means for in-flight I/O is precise and important: for a `TcpStream::read`, the syscall has already returned or has not been issued, so dropping loses at most a partial buffer held in the future's state, and the socket itself is untouched (the `TcpStream` is borrowed, not owned by the read future). For a `write_all` that has issued three of five `write` syscalls, **the first three bytes are on the wire and the peer has them**; dropping does not un-send them, so the connection is now in an undefined protocol state and the only correct recovery is to close it. For an HTTP client request, dropping the future closes the connection, but the server may already have executed the request: a cancelled `POST /charge` may still have charged the card. Cancellation is not rollback, and saying so is the senior signal.

**Layer 2: cancellation safety and `select!`.** The definition from the Tokio docs is exact: a future is cancellation-safe if dropping it before completion and recreating it is a no-op, meaning no progress is lost. `tokio::select!` polls all branches on the current task, returns the first that completes, and **drops all the others**. In a loop, that means the losing branches are recreated from scratch on every iteration. So:

Cancel-safe, per the `select!` docs, and therefore fine in a loop: `mpsc::Receiver::recv`, `UnboundedReceiver::recv`, `broadcast::Receiver::recv`, `watch::Receiver::changed`, `TcpListener::accept`, `UnixListener::accept`, `signal::unix::Signal::recv`, `AsyncReadExt::read`, `read_buf`, `AsyncWriteExt::write`, `write_buf`, and `StreamExt::next` from both `tokio_stream` and `futures`.

**Not** cancel-safe, and a data-loss bug in a `select!` loop: `AsyncReadExt::read_exact`, `read_to_end`, `read_to_string`, `AsyncWriteExt::write_all`. Each of these holds partial progress in the future's own state; drop it and those bytes are gone from your buffer but consumed from (or written to) the socket.

Not cancel-safe for a different reason, queue position: `tokio::sync::Mutex::lock`, `RwLock::read`, `RwLock::write`, `Semaphore::acquire`, `Notify::notified`. These use a fair FIFO wait queue, so cancelling loses your place. That is not data loss, but it is a starvation hazard if you `select!` on a lock in a hot loop.

The sharp edge in code:

```rust
// untested sketch: BROKEN. Loses bytes.
loop {
    tokio::select! {
        res = socket.read_exact(&mut header) => { handle(res?)?; }
        _   = shutdown.recv() => break,
    }
}
// If `shutdown` fires while read_exact has consumed 3 of 8 header bytes,
// those 3 bytes are gone from the socket and absent from `header`.
// Worse: if this loop runs many iterations and `shutdown` is a broadcast
// that fires spuriously, the stream desynchronizes silently and you get
// "invalid frame" errors minutes later, far from the cause.

// FIX 1: hoist the future out of the loop so it is not recreated.
let mut read = Box::pin(socket.read_exact(&mut header));   // or pin!()
loop {
    tokio::select! {
        res = &mut read => { ... }         // survives across iterations
        _   = shutdown.recv() => break,
    }
}

// FIX 2 (usually better): only put cancel-safe operations in select!,
// and do the non-cancel-safe work outside it.
loop {
    tokio::select! {
        n = socket.read(&mut buf) => { accumulate(n?); if have_frame() { ... } }
        _ = shutdown.recv() => break,
    }
}

// FIX 3: move the connection into its own task and cancel the whole task.
```

Two more `select!` facts to have ready. Branch order is **randomized by default** to provide fairness across always-ready branches, and the RNG has a non-zero CPU cost; `biased;` at the top of the macro polls top to bottom in order, which is what you want when a shutdown branch must never be starved by a saturated stream, but then branch fairness becomes your responsibility. And `select!` **panics** if all branches are disabled by `if` preconditions or non-matching patterns and there is no `else` branch, which is a genuinely surprising production panic.

**Layer 3: explicit cancellation with `CancellationToken`.** Drop-cancellation is immediate and gives you no chance to clean up. `tokio_util::sync::CancellationToken` inverts it: the task selects on `token.cancelled()` and then runs its own shutdown path (flush a buffer, send a `Bye` frame, commit a transaction) before returning. Tokens form a tree via `child_token()`, so cancelling a parent cancels every descendant, which is how you express "kill this subsystem". `drop_guard()` gives you a guard that cancels on drop, which is how you make a supervisor's death propagate.

```rust
// untested sketch: the shape you want in production
let token = CancellationToken::new();
let tracker = TaskTracker::new();          // tokio_util::task::TaskTracker

for conn in conns {
    let t = token.child_token();
    tracker.spawn(async move {
        tokio::select! {
            biased;
            _ = t.cancelled() => { conn.flush_and_close().await; }   // graceful
            r = serve(conn)   => { r }
        }
    });
}

tokio::signal::ctrl_c().await?;
token.cancel();
tracker.close();
// Bound the wait. Never wait forever on shutdown.
tokio::time::timeout(Duration::from_secs(30), tracker.wait()).await.ok();
```

`TaskTracker` is the "wait for N spawned tasks" primitive that, unlike `JoinSet`, lets you keep spawning while waiting and does not hold each task's output.

**Structured concurrency with `JoinSet`.** `tokio::task::JoinSet<T>` owns a set of spawned tasks and gives you `join_next().await -> Option<Result<T, JoinError>>`, completions in arbitrary order. The property that matters: **dropping the `JoinSet` aborts every task in it**, so you cannot leak a task by dropping the handle, which is exactly the guarantee bare `tokio::spawn` does not give you. `abort_all()` does it explicitly; `spawn_blocking` members are the exception since they cannot be aborted once started. Prefer `JoinSet` to a `Vec<JoinHandle<_>>` for anything with a scoped lifetime, and prefer `try_join!`/`join!` only for a small fixed set of futures on the *same* task (they do not spawn, so they give concurrency without parallelism).

`JoinError` distinguishes `is_panic()` from `is_cancelled()`, and `into_panic()` gives you the payload for re-panicking. This matters because a panic in a spawned task does **not** kill the process by default: it kills the task, the `JoinHandle` resolves to `Err`, and if nobody joins it the panic is invisible. Set `Builder::unhandled_panic(UnhandledPanic::ShutdownRuntime)` (`tokio_unstable`) or join every handle, or you will ship a service where a subset of requests silently do nothing.

### Async traits, current status

Since Rust 1.75.0 (28 December 2023) you can write this directly:

```rust
trait Store {
    async fn get(&self, k: &str) -> Result<Vec<u8>, Error>;      // AFIT
    fn stream(&self) -> impl Stream<Item = u8> + Send;            // RPITIT
}
```

The desugaring is RPITIT: `async fn get` becomes `fn get(&self, k: &str) -> impl Future<Output = ...> + '_`, monomorphized per impl, with **zero allocation and static dispatch**. Two live limitations you must be able to state:

1. **Not `dyn`-compatible.** `Box<dyn Store>` does not compile when `Store` has an `async fn`, because each impl's returned future is a different, unnameable, differently-sized type. The nightly `async_fn_in_dyn_trait` feature is marked incomplete as of August 2026. When you need dynamic dispatch, use `#[async_trait]` (which rewrites the method to return `Pin<Box<dyn Future + Send + 'a>>`, one heap allocation per call, roughly 20-50ns plus allocator pressure) or return `Pin<Box<dyn Future>>` by hand.
2. **No way to bound the returned future as `Send` from the trait definition.** The returned `impl Future` is anonymous, so a generic caller cannot write `where T::get(..): Send`. In practice this means a generic function that spawns `store.get(k)` may fail to compile for reasons the trait author cannot fix. The stopgap is `trait_variant::make(Store: Send)` from the `trait-variant` crate, which generates a parallel `Send`-bounded trait, or `#[async_trait]` which bakes `+ Send` into the box. Return-type notation (`T::get(..): Send`) is the accepted long-term fix and is still unstable.

Rule of thumb: use native `async fn` in traits for internal, statically-dispatched abstractions (the common case); use `#[async_trait]` when you need `dyn`; use `trait-variant` when you need `Send` bounds across a generic boundary.

### Failure modes

| Symptom | Cause | Fix |
|---|---|---|
| p99 jumps in clean quantized steps (5ms → 250ms → 500ms) under load; CPU pegged | Blocking CPU work (bcrypt, JSON of a 50 MiB body, image resize) in an `async fn`, pinning a worker thread | `spawn_blocking` gated by a `Semaphore(num_cpus)`, or `rayon` + `oneshot` bridge |
| Load average = worker count, CPU utilization near 0%, latency climbing | Blocking **I/O** (`std::fs`, `reqwest::blocking`, a sync DB driver) on worker threads; all workers parked in a syscall | `tokio::fs`, an async driver, or `spawn_blocking`; check `worker_mean_poll_time` |
| `tokio::time::sleep(10ms)` returns after 250ms; internal timeouts fire late | Executor is blocked, so the timer's `wake()` lands but nothing polls the task | Same as above. Late timers are the diagnostic that separates "our executor" from "their service" |
| `/healthz` times out and the orchestrator kills a pod that is serving traffic fine | Healthcheck task starved on a saturated worker pool | Fix the blocking; as a stopgap run the healthcheck on a dedicated `current_thread` runtime on its own thread |
| RSS grows linearly, OOMKilled ~25 min after deploy, consumer service blamed | `mpsc::unbounded_channel` with producer rate > consumer rate | Bounded `mpsc::channel(n)`; export `Sender::capacity()` as a gauge and alert when it hits 0 |
| Sporadic "invalid frame" / protocol desync minutes after a burst; unreproducible locally | `read_exact`/`write_all` in a `tokio::select!` branch, dropped mid-operation | Hoist the future with `pin!` and `&mut`, or use cancel-safe `read`/`write` and buffer manually |
| Subscribers silently stop receiving after a traffic burst | `broadcast::Receiver` loop treats `RecvError::Lagged` as fatal and returns | Log and continue; `Lagged` does not close the channel. Size the ring for burst depth (rounded up to a power of two) |
| A task hangs forever, never polled again, no error anywhere | Lost wakeup: a hand-written `poll` returned `Pending` without registering `cx.waker()`, or stored a stale waker from a previous poll | Always `cx.waker().clone()` (or check `will_wake`) on **every** `Pending` return |
| `future cannot be sent between threads safely ... value is used across an await` | `Rc`, `RefCell` guard, `MutexGuard` from a `!Send` lock, or a raw pointer held across `.await` | Drop the guard before the await, switch to `tokio::sync::Mutex`, or `spawn_local` on a `LocalSet` |
| Whole runtime deadlocks under load, no CPU, no progress | `std::sync::Mutex` held across an `.await`; every worker blocked waiting on the lock held by an unpolled task | Never hold a blocking mutex across an await; use `tokio::sync::Mutex` or shrink the critical section |
| `Cannot start a runtime from within a runtime` panic | `Handle::block_on`/`Runtime::block_on` called from inside an async context (often via a sync wrapper in a library) | `block_in_place` + `Handle::current().block_on(...)`, or restructure to `.await` |
| `spawn_blocking` calls queue and latency spikes at ~512 concurrent | Hit `max_blocking_threads`, default 512 | Raise the cap for I/O, or (correct for CPU work) lower effective concurrency with a semaphore |
| Shutdown hangs forever; SIGTERM does nothing; orchestrator SIGKILLs after 30s | Runtime waits indefinitely for `spawn_blocking`/`block_in_place` work, which cannot be aborted | `Runtime::shutdown_timeout(Duration)`; make blocking work check a cancellation flag itself |
| A panic in one request handler produces no log and no alert; a fraction of requests do nothing | Panic in a spawned task kills only the task; nobody joins the `JoinHandle` | Join every handle (or use `JoinSet`) and inspect `JoinError::is_panic()`; consider `unhandled_panic(ShutdownRuntime)` |
| Async fn returns instantly and nothing happens | Future created but never awaited or spawned; `unused_must_use` warning ignored | Deny `unused_must_use`; remember creation is not execution |
| Latency fine at 1 QPS, terrible at 1000, and `tokio-console` shows one task with a huge poll time | A single long-running task without yield points (a tight parse loop, `unconstrained`, or a non-Tokio-aware future) exhausting nothing because it never participates in the 128-op budget | Insert `tokio::task::yield_now().await` every N iterations, or move the loop to `spawn_blocking` |

---

## Tradeoffs & when NOT to use it

**Do not use async Rust for a CPU-bound workload.** Async solves *waiting*, not *computing*. If your service spends 95% of its wall time in matrix multiplies or tokenization, a thread pool sized to core count (or `rayon`) is simpler, faster, and free of every hazard in this module. Async buys you the ability to hold 100,000 idle connections at roughly 64 bytes to a few KiB of state each instead of 100,000 threads at 8 MiB of default stack; if you have 32 concurrent units of work, that trade is worthless and you have imported `Pin`, `Send` bounds, and cancellation safety for nothing.

**Do not use async for a CLI or a batch job.** `#[tokio::main]` on a tool that makes six sequential HTTP calls adds a dependency tree of roughly 25-30 crates, several hundred milliseconds of compile time per incremental build, and a runtime startup cost, in exchange for nothing, since the calls are sequential anyway. Use `ureq` or `reqwest::blocking`. If you need async for one library, `#[tokio::main(flavor = "current_thread")]` is the cheap version.

**Do not reach for async when threads are enough.** The crossover point where thread-per-connection stops working on Linux is empirically in the 10,000 to 50,000 concurrent connection range, driven by memory (default 8 MiB stack reservation, though only touched pages are resident) and scheduler overhead. Below a few thousand connections a thread-per-connection Rust server is simpler, has better tail latency (the kernel scheduler preempts; Tokio cannot), and debugs with an ordinary stack trace. Discord's well-known Go-to-Rust migration was about GC tail latency, not about async.

**Be honest about the debugging cost.** A Rust async stack trace is a trace of the *executor*, not of your logical call chain: you see `tokio::runtime::scheduler::multi_thread::worker::run` and a pile of `poll` frames, and the logical "who called this" is gone. `tokio-console` and `tracing` with `#[instrument]` recover most of it, but they are extra tooling you must set up in advance, and `tokio-console` requires `RUSTFLAGS="--cfg tokio_unstable"` which means a separate build. Budget for this before you commit a team to async.

**The ecosystem lock-in is real.** `tokio::io::AsyncRead` and `futures::io::AsyncRead` are different traits; `tokio-util`'s `Compat` adapters bridge them at a small cost and real friction. Libraries that spawn onto `Handle::current()` panic outside a Tokio context. "Runtime-agnostic" is achievable for leaf libraries that only use `std::future`, and mostly a fiction for anything that touches I/O or timers. Pick Tokio and stop paying for optionality you will not use.

**Async traits still leak.** If your abstraction must be `dyn`, you are paying a `Box<dyn Future>` allocation per call, and if it must be generic *and* `Send`, you are in `trait-variant` territory. For a plugin-style architecture where every call is dynamically dispatched and allocation-sensitive, consider an enum dispatch or a message-passing design instead of a trait.

**When async is unambiguously right:** proxies and gateways (Linkerd's `linkerd2-proxy`, Cloudflare's Pingora, though Pingora deliberately uses a thread-per-core-ish arrangement), API servers with high connection counts and low per-request CPU, anything fan-out-heavy (an agent orchestrator issuing 50 concurrent LLM calls, where `JoinSet` plus a `Semaphore` is exactly the right shape), and streaming/long-poll workloads where connections vastly outnumber active requests.

---

## Interview questions

### Q1 — You come from Python. What is the single biggest difference between an `asyncio` coroutine and a Rust `Future`?
**Testing:** whether laziness is understood as the root property, and whether the candidate can reason from it rather than recite it.
**Answer:** Eagerness. `asyncio.create_task(coro())` schedules the coroutine on the loop and it will run whether or not you await the task; in Rust, calling `async fn foo()` executes zero lines of the body, it just constructs a state machine value on the stack. Nothing runs until an executor calls `poll` on it, which happens when you `.await` it (the enclosing future drives it) or `tokio::spawn` it (the scheduler drives it). The consequence chain is what matters: because a future is an inert value the caller owns, composing ten of them costs one flat state machine rather than ten heap-allocated task objects, cancellation is just `drop` with no cooperative protocol, and forgetting to await means literally nothing happens, which is why `Future` is `#[must_use]`.
**Follow-up trap:** *"So is `tokio::spawn` lazy too?"* No, and this is the one exception people miss: `spawn` hands the future to the scheduler immediately and it starts running before you await the `JoinHandle`. The second half of the trap is that dropping the `JoinHandle` does **not** cancel the task, it detaches it; you need `handle.abort()` or a `JoinSet` (which aborts everything it owns on drop) if you want cancellation.

### Q2 — Write the `Future` trait from memory and explain what `Context` is for.
**Testing:** whether the mechanism is actually understood or just used.
**Answer:** `trait Future { type Output; fn poll(self: Pin<&mut Self>, cx: &mut Context<'_>) -> Poll<Self::Output>; }` with `enum Poll<T> { Ready(T), Pending }`. `Context` exists to carry the `Waker`. Without it the executor would have to busy-poll every pending future (burning a core) or poll on a fixed interval (adding that interval to every latency). Instead the contract is: if `poll` returns `Pending`, it must first have stashed `cx.waker().clone()` somewhere that will call `wake()` when progress is possible, typically an epoll registration keyed by fd, a timer wheel slot, or a channel's waiter list. `Waker` is a fat pointer plus a manual vtable of `clone`/`wake`/`wake_by_ref`/`drop`, and it is `Send + Sync` so a leaf future can hand it across threads. All of this stabilized in Rust 1.36.0 in July 2019; `async`/`await` syntax followed in 1.39.0 in November 2019.
**Follow-up trap:** *"What happens if you return `Pending` without registering the waker?"* The task is silently lost forever. No panic, no log, no timeout, it is just never polled again, and you find it as a request that hangs until the client times out. The subtler variant, which is the actual production bug, is storing the waker **once** on the first poll and not refreshing it: work-stealing may migrate the task to another worker between polls, so the stale waker wakes the wrong scheduler slot and the task hangs only under load. Always re-store on every `Pending`, or gate with `Waker::will_wake`.

### Q3 — Why does `Pin` exist? Answer without saying "self-referential" as a magic word.
**Testing:** whether the candidate can derive it from the desugaring.
**Answer:** `async fn` compiles to a generated enum where every local that is live across an `.await` becomes a field of that enum. If one of those locals is a reference to another, for example `let buf = [0u8; 1024]; let s = &buf[..]; io.read(s).await;`, then the enum contains a pointer into itself. Rust's entire model assumes values are freely movable with a `memcpy`, so moving that enum would leave the internal pointer aimed at the old address. `Pin<P>` is the type-level fix: it withholds `&mut Target` unless `Target: Unpin`, and the compiler-generated coroutine types are exactly the types that are `!Unpin`. Because `poll` takes `self: Pin<&mut Self>`, an executor structurally cannot move a half-run state machine. For every other type in the language `Pin` is a no-op wrapper, since `Unpin` is an auto trait that almost everything gets.
**Follow-up trap:** *"Then why does `Box::pin` cost an allocation if `Pin` is 'just a wrapper'?"* Because `Pin` is a *promise*, not a mechanism; something has to actually guarantee a stable address. `Box::pin` buys that with a heap allocation, and the resulting `Pin<Box<F>>` is itself movable because you move the `Box`, not the `F`. The zero-allocation alternative is `std::pin::pin!` (stabilized 1.68.0, March 2023), which pins to the current stack frame by shadowing the binding so you cannot move the original. Use `pin!` for a future you poll in a loop on the same frame; use `Box::pin` when the future must be stored, type-erased as `dyn`, or when it is large enough that copying it around costs more than the allocation.

### Q4 — A colleague adds `bcrypt::hash(pw, 12)` to an axum handler. Describe exactly what you will see in production.
**Testing:** whether they know the symptom signature, not just the rule.
**Answer:** `bcrypt` at cost factor 12 is roughly 250ms of pure CPU with no yield points, so it holds a Tokio worker thread for 250ms. On an 8-core box the default multi-thread runtime has 8 workers. Up to 8 concurrent requests everything looks fine. At 9 the ninth task is not polled at all. The signature is a **latency cliff with quantized steps**, p99 going 5ms, then 250ms, then 500ms, then 750ms as queue depth grows, rather than the smooth degradation curve you get from contention. Second tell: **your own timers fire late**, `sleep(10ms)` returning after 260ms, because the timer's `wake()` landed but nothing polled the task, and that is what distinguishes "our executor is blocked" from "the downstream is slow". Third: `/healthz` times out and the orchestrator kills a pod that is actually healthy, converting a latency incident into a crash loop. Confirm with `tokio-console` (the "task has been busy for N ms" warning, plus `worker_mean_poll_time`) or `gdb -p $PID -ex 'thread apply all bt'` showing every `tokio-runtime-worker` inside the crypto routine instead of `epoll_wait`.
**Follow-up trap:** *"Fine, wrap it in `spawn_blocking` and ship it."* That fixes the worker starvation but introduces a second problem: `max_blocking_threads` defaults to **512**, which is sized for I/O blocking where threads park in a syscall, not for CPU work. 512 threads doing bcrypt on 16 cores is a 32x oversubscription, you get a context-switch storm visible in `pidstat -w`, and p99 degrades roughly linearly with the oversubscription. The correct shape is `spawn_blocking` behind a `Semaphore` sized to core count, or a `rayon` pool bridged with a `oneshot`. And note `spawn_blocking` tasks cannot be aborted once started, so they also make your shutdown path hang unless you use `Runtime::shutdown_timeout`.

### Q5 — What is the difference between `spawn_blocking` and `block_in_place`?
**Testing:** operational depth on the runtime API surface.
**Answer:** `spawn_blocking` moves the closure to a **different** thread from the blocking pool and returns a `JoinHandle`, so the current task keeps its worker and can await the result. `block_in_place` runs the closure on the **current** worker thread, but first tells the scheduler to hand this worker's local queue and LIFO slot off to another thread (spawning one if needed) so the rest of the runtime keeps making progress. Use `block_in_place` when the blocking work needs borrowed, non-`'static`, or `!Send` data from the current task and you cannot restructure; use `spawn_blocking` otherwise, because it is strictly safer. Three constraints on `block_in_place`: it **panics** on a `current_thread` runtime, since there is no peer to hand off to; it does not help anything running concurrently *within the same task*, so a `join!` sibling is still stuck; and it cannot be cancelled, so shutdown waits for it.
**Follow-up trap:** *"When is `std::thread::spawn` the right answer instead of either?"* When the blocking work is **long-lived or unbounded**: a background worker loop, a file tailer, a persistent consumer thread. `spawn_blocking` occupies a pool slot for its whole duration, so N long-lived tasks permanently reduce the pool's effective capacity from 512 to 512 minus N and eventually queue everything else. Tokio's own docs draw the line at "short-lived blocking operations use `spawn_blocking`, long-lived or persistent workloads use a dedicated thread", and bridge with `mpsc`'s `blocking_send`/`blocking_recv`.

### Q6 — Why won't this compile: an `async fn` that does `state.borrow_mut()` on an `Rc<RefCell<T>>` and then awaits?
**Testing:** whether `Send` bounds are understood as a structural property of the generated state machine.
**Answer:** `tokio::spawn` requires `F: Future + Send + 'static`, and the compiler computes `Send` for a generated coroutine structurally: the future is `Send` only if every field is `Send`, and the fields are exactly the locals live across `.await` points. `RefMut<'_, T>` is `!Send` because `RefCell`'s borrow counter is a plain `Cell<isize>` with no atomics, so two threads decrementing it concurrently would be a data race rather than a `BorrowMutError` panic. Holding that guard across the await makes it a field, so the future is `!Send`, so `spawn` rejects it. The compiler even tells you which value and which await, in the "future is not `Send` as this value is used across an await" note. This is not pedantry: a work-stealing scheduler genuinely may migrate the task to another worker at that exact suspension point.
**Follow-up trap:** *"So swap `RefCell` for `std::sync::Mutex` and it compiles. Are you done?"* It compiles, because `MutexGuard<T>` is `Send` when `T: Send`, and that is precisely the dangerous case. Holding a **blocking** mutex across an `.await` risks a full-runtime deadlock: worker A holds the lock and suspends, workers B through H all block on the lock, and now no thread is left to poll the task that would release it. Under load the service goes to zero CPU and zero progress. The three correct answers are: drop the guard before the await (right about 70% of the time and free), use `tokio::sync::Mutex` whose guard is `Send` and whose `lock()` is async (roughly an order of magnitude slower uncontended, so only for this case), or restructure to an actor holding the state behind an `mpsc`.

### Q7 — Explain cancellation in async Rust and what it means for in-flight I/O.
**Testing:** whether they understand cancel-by-drop and its limits, not just "you drop the future".
**Answer:** There is no cancellation mechanism in the language beyond dropping the future. `tokio::time::timeout(dur, fut)` is itself a future that polls `fut` and a `Sleep`; when the sleep wins, `fut` is dropped exactly where it was suspended, its `Drop` impls run, and its state evaporates. There is no `CancelledError` propagating up, no unwinding through async frames, and no async cleanup hook, because async `Drop` is still not stable in Rust 1.97.1. For in-flight I/O the consequences differ by direction. A dropped `read` loses at most a partial buffer held in the future's state, and the socket is untouched because the read future only borrows the `TcpStream`. A dropped `write_all` that already issued three of five `write` syscalls has **already put those bytes on the wire**, so the peer has them and the protocol is now desynchronized; the only safe recovery is to close the connection. A dropped HTTP request closes the connection but the server may have already executed it, so a cancelled `POST /charge` may still have charged the card. Cancellation is not rollback.
**Follow-up trap:** *"How do you get a chance to clean up, then?"* You invert it: instead of being dropped, the task selects on `tokio_util::sync::CancellationToken::cancelled()` and runs its own shutdown path (flush, send a close frame, commit) before returning. Tokens form a tree via `child_token()` so cancelling a parent cancels every descendant, and `drop_guard()` propagates a supervisor's death. Pair it with `TaskTracker` to wait for the tasks, and always bound that wait with a `timeout`, because a shutdown that waits forever is how you get SIGKILLed at 30 seconds with in-flight work lost anyway.

### Q8 — What is cancellation safety, and give me a concrete `select!` bug.
**Testing:** the highest-signal question on this topic. Most candidates know `select!` exists; few can state the hazard precisely.
**Answer:** A future is cancellation-safe if dropping it before completion and recreating it loses no progress, that is, dropping it is a no-op. This matters because `tokio::select!` polls all branches on the current task, returns the first to complete, and **drops every other branch**; in a loop, the losers are reconstructed from scratch each iteration. So any future that holds partial progress in its own state is unsafe there. The concrete bug: `select! { r = socket.read_exact(&mut header) => ..., _ = shutdown.recv() => break }` in a loop. `read_exact` accumulates bytes in the future's state, so if the other branch fires after it has consumed 3 of 8 header bytes, those 3 bytes are gone from the socket and absent from `header`. The stream desynchronizes and you get "invalid frame" parse errors minutes later, far from the cause and unreproducible locally. The documented not-cancel-safe list is `read_exact`, `read_to_end`, `read_to_string`, `write_all`; the safe list includes `mpsc::Receiver::recv`, `broadcast::Receiver::recv`, `watch::Receiver::changed`, `TcpListener::accept`, and `AsyncReadExt::read`.
**Follow-up trap:** *"Are `Mutex::lock` and `Semaphore::acquire` cancel-safe?"* No, but for a different reason, and knowing the distinction is the signal. They are not data-lossy; they use a **fair FIFO wait queue**, so cancelling loses your place in line. In a `select!` loop that repeatedly re-acquires, a task can be starved indefinitely while it keeps getting sent to the back of the queue. Same for `RwLock::read`/`write` and `Notify::notified`. The fix for both categories is the same shape: hoist the future out of the loop with `pin!` and select on `&mut fut` so it survives iterations, or keep only cancel-safe operations inside `select!` and do the rest outside.

### Q9 — Walk me through Tokio's multi-threaded scheduler.
**Testing:** whether they have read the runtime docs or only used the runtime.
**Answer:** Work-stealing, N workers where N defaults to the CPU core count and is overridable via `worker_threads()` or the `TOKIO_WORKER_THREADS` environment variable. There is one global injection queue plus one local queue per worker; the local queue is a fixed ring holding at most **256** tasks, and overflow pushes **half** of them (128) to the global queue. A worker prefers its own local queue and checks the global queue every `global_queue_interval` pops, which defaults to **31** on the current-thread scheduler and is computed dynamically on the multi-thread scheduler from the `worker_mean_poll_time` metric, targeting a global-queue check about every **10ms**. Every **61** consecutive polls (`event_interval`), or whenever both queues are empty, the worker parks in `epoll_wait` to pick up I/O and timer readiness. Empty workers **steal half** a randomly-chosen peer's local queue. Finally the **LIFO slot**: when a running task wakes another, the woken task goes into a single-slot register and is polled immediately next, which is a cache-locality win for request/response ping-pong; it is bounded to **3 consecutive** uses before being temporarily disabled so it cannot starve the queue, and the task in the slot **cannot be stolen**.
**Follow-up trap:** *"When would you turn off the LIFO slot?"* When the wake-ee is expensive and the wake-er is latency-sensitive, or in a bimodal workload where you would rather the woken task be stealable by an idle worker than pinned to a busy one; `disable_lifo_slot()` on the builder. The related trap is that the coop budget is **not reset** when a task comes from the LIFO slot, precisely so a two-task ping-pong pair cannot mutually re-arm each other's 128-operation budget forever and starve the rest of the worker.

### Q10 — Why is an unbounded channel usually a bug?
**Testing:** backpressure reasoning, which is the systems-design half of this topic.
**Answer:** `unbounded_channel().send()` is synchronous and cannot fail while the channel is open, so by construction it cannot apply backpressure. If the producer's rate exceeds the consumer's service rate by any margin, the queue grows without bound. Concretely: 1,000 messages/sec in, 333/sec out at 3ms of work each, 4 KiB per message, gives 2.7 MiB/sec of growth, so a 4 GiB container OOMs in about 25 minutes. Two things make it worse than a plain leak. First, latency degrades long before memory does, because by Little's Law queue depth **is** latency: a 100,000-deep queue draining at 333/sec means every message that emerges is already 300 seconds stale, so you are burning CPU on work whose deadline has passed. Second, the OOM kill is attributed to the consumer process, so the postmortem investigates the wrong service. A bounded `mpsc::channel(n)` converts an invisible unbounded latency problem into an immediate, local, observable stall or error at the producer.
**Follow-up trap:** *"So bound everything?"* Almost, but there are three legitimate uses of unbounded and you should name them: sending from synchronous code that cannot await (though `blocking_send` on a bounded channel is usually better), a producer that is provably rate-limited by something else such as a timer tick or a fixed-size input set, and breaking a deadlock cycle where a bounded `send().await` could block the very task responsible for draining that channel. Also note the accounting detail: `mpsc::channel(n)` is not exactly `n`, because each `Sender` can hold a reserved permit, so the worst-case high-water mark is `n` plus the number of senders, and `channel(0)` panics rather than giving you a rendezvous channel.

### Q11 — `mpsc`, `oneshot`, `broadcast`, `watch`: when do you pick each?
**Testing:** whether channel selection is a considered design decision.
**Answer:** `mpsc` for work queues and actor inboxes, many producers and one consumer, bounded so you get backpressure. `oneshot` for a single request/response handoff, which is how you get a reply out of an actor and how you bridge a `rayon` computation back into async; its `send` is not async and hands your value back in the `Err` if the receiver is gone, and dropping the sender resolves the receiver to `Err(RecvError)`, which is the idiomatic "the worker died" signal. `broadcast` when every consumer must see every message, such as shutdown fan-out or pub/sub; it is a bounded ring whose capacity is rounded **up to the next power of two**, so `channel(3)` gives you a 4-slot ring and a receiver only lags once it falls more than 4 behind. `watch` when only the latest value matters, such as config reload or a health flag; it retains exactly one value, and the initial value is marked **seen** so `changed()` will not return until a subsequent send.
**Follow-up trap:** *"A `broadcast` subscriber stops receiving after a traffic burst. What happened?"* It got `RecvError::Lagged(n)` and the loop treated it as fatal and returned. `Lagged` does **not** close the channel: the receiver's cursor is advanced to the oldest still-retained value and the next `recv()` succeeds. The correct handling is to log the count of dropped messages, emit a metric, and continue. The related `watch` trap is holding the `Ref` from `borrow()` across an `.await`: `borrow()` takes a read lock on an internal `RwLock`, so all senders block until you drop it, which is a self-inflicted deadlock that looks like a stalled config pipeline.

### Q12 — What is `JoinSet` and why prefer it to `Vec<JoinHandle<T>>`?
**Testing:** structured-concurrency instinct.
**Answer:** `JoinSet<T>` owns a set of spawned tasks and yields completions in arbitrary order via `join_next().await -> Option<Result<T, JoinError>>`. The property that matters is that **dropping the `JoinSet` aborts every task in it**, so you structurally cannot leak a task by dropping the handle, which is exactly the guarantee bare `tokio::spawn` does not give you (dropping a `JoinHandle` detaches the task, it keeps running). It also gives you completion-order results, so you can process the first of 50 concurrent LLM calls to return rather than waiting for the slowest, and `abort_all()` for explicit teardown. `JoinError` distinguishes `is_panic()` from `is_cancelled()` and `into_panic()` returns the payload.
**Follow-up trap:** *"So `JoinSet` gives you structured concurrency, like `std::thread::scope`?"* Close but not equal, and the gap is the interesting part: `tokio::spawn` and `JoinSet::spawn` both require `'static`, so you still cannot borrow a local across the spawn boundary the way `std::thread::scope` lets you. Scoped async tasks are a genuine unsolved gap, because a future can be `mem::forget`ed rather than dropped, so the compiler cannot prove the scope actually waits. The practical workaround is `Arc` plus `JoinSet`, or `async_scoped` with explicit `unsafe`. The second half of the trap is that `spawn_blocking` members of a `JoinSet` cannot be aborted once started, so drop-aborts-everything has an exception.

### Q13 — What is the current status of `async fn` in traits?
**Testing:** whether they are current, and whether they will overclaim.
**Answer:** Stable since Rust 1.75.0 in December 2023, along with return-position `impl Trait` in traits, which is the desugaring: `async fn get(&self)` becomes `fn get(&self) -> impl Future<Output = ...> + '_`, monomorphized per impl with **zero allocation and static dispatch**. Two limitations remain as of Rust 1.97.1 in August 2026. First, the trait is **not `dyn`-compatible**, because each impl returns a different unnameable type of a different size, so `Box<dyn Store>` does not compile; the `async_fn_in_dyn_trait` nightly feature is still marked incomplete. Second, you cannot bound the returned future as `Send` from the trait definition, since it is anonymous, so a generic function that spawns `t.get(k)` can fail to compile in a way the trait author cannot fix. The workarounds are `#[async_trait]` (rewrites to `Pin<Box<dyn Future + Send + 'a>>`, one heap allocation per call) when you need `dyn`, and `trait_variant::make(Store: Send)` when you need `Send` across a generic boundary. Return-type notation is the accepted long-term fix and is not stable.
**Follow-up trap:** *"So `async-trait` is dead?"* No, and saying so is the overclaim they are listening for. Native AFIT covers the common statically-dispatched case and should be the default, but `#[async_trait]` is still the answer whenever you need `dyn Trait`, which includes most plugin architectures, most `Box<dyn Repository>` dependency-injection patterns, and any heterogeneous collection of implementations. The cost is real but small: one `Box` allocation per call, on the order of tens of nanoseconds plus allocator pressure, which is irrelevant next to a database round trip and very relevant in a hot in-memory path.

### Q14 — Your service's p99 is fine at 1 QPS and terrible at 1,000, but CPU sits at 15% and the downstream is fast. Debug it.
**Testing:** end-to-end diagnostic reasoning under the runtime model.
**Answer:** Low CPU with high latency and a fast downstream points at workers that are parked rather than working, so the hypothesis is blocking I/O on worker threads: `std::fs`, `reqwest::blocking`, a synchronous database or DNS resolver dragged in transitively. **Step 1:** check whether load average approximates the worker count while utilization is near zero, which is the signature of every worker sitting in a `read()` syscall. **Step 2:** instrument internal timers, because `sleep(10ms)` returning in 250ms proves the executor is starved rather than the peer being slow. **Step 3:** run with `RUSTFLAGS="--cfg tokio_unstable"` and `console-subscriber`, and look at `worker_mean_poll_time` and `injection_queue_depth`; a mean poll time in the milliseconds is definitive. **Step 4:** `gdb -p $PID -ex 'thread apply all bt'` and confirm the `tokio-runtime-worker` threads are inside `__libc_read` or similar rather than `epoll_wait`. Then move the offender to `spawn_blocking` or an async driver. If instead everything is in one long `poll`, the cause is a compute loop with no yield points, and the fix is `yield_now().await` every N iterations or `spawn_blocking`.
**Follow-up trap:** *"What if `worker_mean_poll_time` is low and the queue is still deep?"* Then it is not blocking, it is genuine saturation or a fairness problem: either you need more workers or you have a task that participates in nothing, such as one wrapped in `task::coop::unconstrained` or a hand-written future that never decrements the 128-operation coop budget, monopolizing a worker without any single poll being long. The other candidate is lock convoy on a `tokio::sync::Mutex` with a FIFO wait queue, where mean poll time is small but every task spends its life in the queue.

### Q15 — Design the concurrency for a service that fans out to 50 LLM providers per request, with a 5-second budget and graceful shutdown.
**Testing:** whether all of this composes into a design, which is the staff/principal bar.
**Answer:** One `JoinSet` per request so that dropping it on any early return aborts all 50 in-flight calls with no leak. A process-wide `Semaphore` sized to the provider's actual rate limit, acquired **inside** each task rather than before spawn, so the queue is in the semaphore rather than in a channel. `tokio::time::timeout(Duration::from_secs(5), ...)` wrapped around the whole `join_next` loop, not around each call, so the budget is end-to-end; per-call timeouts go inside at a smaller value, say 4 seconds, so a straggler cannot consume the whole budget. Results collected as they complete via `join_next`, so you can return early once you have enough. For shutdown, a `CancellationToken` tree with a child per request, plus a `TaskTracker` at the top level, and a bounded `timeout(Duration::from_secs(30), tracker.wait())` so shutdown cannot hang. Every `JoinError` inspected for `is_panic()` and logged, because otherwise a panicking provider adapter silently returns nothing for a subset of requests. No unbounded channels anywhere; the ingress queue is a bounded `mpsc` whose `try_send` sheds load rather than queueing past the deadline.
**Follow-up trap:** *"What happens to the HTTP connections of the 45 calls you abandon when 5 answers are enough?"* They are dropped mid-flight, which closes the connections, which means (a) you lose the pooled keep-alive connection and pay a TLS handshake next time, roughly 1 to 3 RTTs, so you want the client pool sized with that in mind, and (b) the providers may still have executed and will still bill you, since cancellation is not rollback. If the calls have side effects or cost money, cancel-by-drop is the wrong tool and you should let them finish into a `oneshot` you ignore, or use a `CancellationToken` so the adapter can complete its accounting before returning.

---

## Red flags that fail you

- Saying "futures are lazy" but then describing `tokio::spawn` as if the future only starts when you await the `JoinHandle`, or claiming that dropping a `JoinHandle` cancels the task.
- Describing `Pin` as "it pins memory so the GC can't move it" or otherwise implying a runtime mechanism. `Pin` is a type-level promise with no runtime representation.
- Not knowing that blocking a worker thread is the canonical async Rust failure, or knowing the rule but being unable to name a single observable symptom.
- Answering "just use `spawn_blocking`" for CPU-bound work without mentioning that the pool cap is 512 and that CPU work needs a semaphore.
- Claiming `tokio::select!` is safe to use with anything, or not knowing that losing branches are dropped.
- Treating cancellation as rollback: "we cancel the request so the charge doesn't go through."
- Using `unbounded_channel` by default and describing bounded channels as "an optimization" rather than as the backpressure mechanism.
- Claiming async traits are fully solved and `dyn` works, or claiming `async-trait` is obsolete.
- Saying async Rust is "faster than threads" as a blanket statement, with no mention that it is about connection scaling and idle memory, not about compute throughput.
- Not being able to state what `Send` means for a future (structural over locals held across awaits) or why `RefCell` breaks it.
- Believing `std::sync::Mutex` across an `.await` is fine because it compiles.
- Confusing concurrency and parallelism when describing `join!` (same task, concurrent, not parallel) versus `spawn` (separate tasks, potentially parallel).

---

## Cheat card

```
FUTURE:  trait Future { type Output;
           fn poll(self: Pin<&mut Self>, cx: &mut Context) -> Poll<Output> }
         Poll::{Ready(T), Pending}. std 1.36.0 (Jul 2019);
         async/await syntax 1.39.0 (Nov 2019); Pin 1.33.0 (Feb 2019).

LAZY:    async fn foo() runs ZERO lines until polled. Contrast asyncio
         create_task (eager) and Go `go f()` (eager). tokio::spawn is the
         one eager exception. Dropping a JoinHandle DETACHES, not cancels.

WAKER:   Pending MUST register cx.waker().clone() or the task is lost
         forever (silent hang). Re-store on EVERY Pending: work-stealing
         may have migrated the task. Waker is Send+Sync, fat ptr + vtable.

PIN:     locals live across .await become FIELDS of the generated enum;
         a borrow among them makes it self-referential -> !Unpin -> must
         not move. Box::pin (1 alloc, movable handle) or std::pin::pin!
         (1.68.0, zero alloc, stack). Everything else is Unpin (no-op).

TOKIO 1.53.1 (20 Jul 2026) MULTI-THREAD SCHEDULER:
  workers = num CPU cores (TOKIO_WORKER_THREADS / worker_threads())
  local queue = 256 tasks; overflow moves HALF (128) to global queue
  global_queue_interval: 31 (current_thread); dynamic ~10ms target (MT)
  event_interval = 61 polls -> park in epoll for I/O + timers
  steal HALF of a random peer's local queue when idle
  LIFO slot: waker->wakee polled next; disabled after 3 in a row; NOT
    stealable; coop budget NOT reset through it
  coop budget = 128 ops/poll (tokio::task::coop); unconstrained() opts out

BLOCKING POOL: max_blocking_threads default 512, thread_keep_alive 10s,
  separate from workers, tasks queue past the cap, CANNOT be aborted once
  started, shutdown waits forever -> Runtime::shutdown_timeout.
  >10-100us of sync work must leave the worker thread.

spawn (async, Send + 'static) | spawn_blocking (other thread, short sync
  work) | block_in_place (this worker, hands off queue; PANICS on
  current_thread) | std::thread::spawn (long-lived blocking loops)
  CPU-bound: spawn_blocking + Semaphore(num_cpus), or rayon + oneshot.

BLOCKED-EXECUTOR SYMPTOMS: quantized p99 steps (5->250->500ms), low CPU
  with load avg == worker count, YOUR OWN timers late (sleep 10ms -> 260ms),
  /healthz timeout -> pod killed, tokio-console worker_mean_poll_time high,
  all tokio-runtime-worker threads in a syscall not epoll_wait.

SEND: future is Send iff every local held across .await is Send. Rc/RefMut
  are !Send. std::sync::MutexGuard IS Send but holding it across .await
  can deadlock the whole runtime. Fixes: drop before await > tokio::sync::
  Mutex > actor+mpsc. !Send futures: spawn_local+LocalSet or LocalRuntime.

CHANNELS: mpsc::channel(n) bounded, backpressure, channel(0) PANICS, true
  cap = n + #senders | mpsc::unbounded = memory leak + latency (Little's
  Law) | oneshot = 1 value, send is sync, returns value on Err | broadcast
  (n) = ring rounded UP to power of 2, Lagged(k) is RECOVERABLE not fatal |
  watch = latest value only, initial value counts as SEEN, don't hold
  borrow() across .await (blocks all senders).

CANCEL = drop(). No CancelledError. No async Drop (unstable in 1.97.1).
  Dropped write_all: bytes ALREADY on the wire. Cancel is not rollback.
  select! drops ALL losing branches; branch order RANDOM by default,
  `biased;` for top-down; PANICS if all branches disabled and no else.
  NOT cancel-safe: read_exact, read_to_end, read_to_string, write_all
  (data loss); Mutex::lock, RwLock::*, Semaphore::acquire, Notify::notified
  (lose FIFO queue position). Safe: recv, changed, accept, read, write, next.
  Fix: pin! the future outside the loop and select on &mut it.

STRUCTURED: JoinSet (drop ABORTS all members; join_next in completion
  order) > Vec<JoinHandle>. CancellationToken (tree via child_token,
  drop_guard) for graceful cleanup. TaskTracker to wait. ALWAYS bound
  shutdown with timeout(). Panic in a spawned task kills only the task.

ASYNC TRAITS: AFIT + RPITIT stable 1.75.0 (Dec 2023), static dispatch,
  zero alloc. NOT dyn-compatible (async_fn_in_dyn_trait still incomplete).
  Can't express Send on the returned future -> trait-variant crate.
  #[async_trait] = Pin<Box<dyn Future + Send>>, 1 alloc/call, still the
  answer for dyn. async closures + AsyncFn* stable 1.85.0 (Feb 2025).
  Stream/AsyncIterator still UNSTABLE (issue #79024, since 2020).

DON'T USE ASYNC FOR: CPU-bound work, CLIs/batch jobs, <few-thousand
  connections. Threads: 8 MiB default stack, fine to ~10k-50k conns.
```

## Sources

- [std::future::Future — Rust std docs (1.97.1)](https://doc.rust-lang.org/std/future/trait.Future.html) — accessed 2026-08-05
- [std::pin — pinning, Unpin, and the drop guarantee](https://doc.rust-lang.org/std/pin/index.html) — accessed 2026-08-05
- [std::pin::pin! macro (stable since 1.68.0)](https://doc.rust-lang.org/std/pin/macro.pin.html) — accessed 2026-08-05
- [std::task::Waker (stable since 1.36.0)](https://doc.rust-lang.org/std/task/struct.Waker.html) — accessed 2026-08-05
- [tokio::runtime module docs — scheduler behaviour, local queue 256, event_interval 61, LIFO slot (tokio 1.53.1)](https://docs.rs/tokio/latest/tokio/runtime/index.html) — accessed 2026-08-05
- [tokio::runtime::Builder — worker_threads, max_blocking_threads (512), thread_keep_alive (10s), global_queue_interval, event_interval](https://docs.rs/tokio/latest/tokio/runtime/struct.Builder.html) — accessed 2026-08-05
- [tokio::select! — fairness, `biased;`, and the cancellation-safety lists](https://docs.rs/tokio/latest/tokio/macro.select.html) — accessed 2026-08-05
- [tokio::task::spawn_blocking — pool semantics, abort behaviour, dedicated-thread guidance](https://docs.rs/tokio/latest/tokio/task/fn.spawn_blocking.html) — accessed 2026-08-05
- [tokio::task::block_in_place — hand-off semantics and the current_thread panic](https://docs.rs/tokio/latest/tokio/task/fn.block_in_place.html) — accessed 2026-08-05
- [tokio::task::coop — cooperative budgeting (128 ops/poll)](https://docs.rs/tokio/latest/tokio/task/coop/index.html) — accessed 2026-08-05
- [tokio::sync::mpsc — bounded vs unbounded, backpressure, blocking_send](https://docs.rs/tokio/latest/tokio/sync/mpsc/index.html) — accessed 2026-08-05
- [tokio::sync::broadcast — power-of-two ring, Lagged semantics](https://docs.rs/tokio/latest/tokio/sync/broadcast/index.html) — accessed 2026-08-05
- [tokio::sync::watch — latest-value-only, seen semantics, borrow_and_update](https://docs.rs/tokio/latest/tokio/sync/watch/index.html) — accessed 2026-08-05
- [tokio_util::sync::CancellationToken](https://docs.rs/tokio-util/latest/tokio_util/sync/struct.CancellationToken.html) — accessed 2026-08-05
- [tokio_util::task::TaskTracker](https://docs.rs/tokio-util/latest/tokio_util/task/task_tracker/struct.TaskTracker.html) — accessed 2026-08-05
- [Tokio topic: Graceful Shutdown](https://tokio.rs/tokio/topics/shutdown) — accessed 2026-08-05
- [Tokio tutorial: Async in depth (poll, Waker, mini-Delay)](https://tokio.rs/tokio/tutorial/async) — accessed 2026-08-05
- [Tokio tutorial: Select (cancellation safety in loops)](https://tokio.rs/tokio/tutorial/select.html) — accessed 2026-08-05
- [Making the Tokio scheduler 10x faster — Tokio blog, October 2019 (chained_spawn 2,019,796 → 168,854 ns/iter; hyper 113,923 → 152,258 req/s)](https://tokio.rs/blog/2019-10-scheduler) — accessed 2026-08-05
- [Announcing `async fn` and return-position `impl Trait` in traits — Rust blog, 21 Dec 2023 (stabilized in 1.75.0)](https://blog.rust-lang.org/2023/12/21/async-fn-rpit-in-traits.html) — accessed 2026-08-05
- [Tracking issue for `#![feature(async_iterator)]` (#79024) — Stream/AsyncIterator still unstable](https://github.com/rust-lang/rust/issues/79024) — accessed 2026-08-05
- [Rust release notes / releases.rs — 1.97.1 current stable, 1.85.0 async closures + Rust 2024 edition](https://releases.rs/) — accessed 2026-08-05
- [Asynchronous Programming in Rust (the async book) — executor, waker, and Pin chapters](https://rust-lang.github.io/async-book/) — accessed 2026-08-05
- [RFC 230: Remove runtime — why Rust dropped green threads in 2014](https://github.com/rust-lang/rfcs/blob/master/text/0230-remove-runtime.md) — accessed 2026-08-05
- [Cancelling async Rust — sunshowers (cancel-by-drop and its consequences)](https://sunshowers.io/posts/cancelling-async-rust/) — accessed 2026-08-05
- [async-trait crate docs — Box<dyn Future> desugaring and when it is still required](https://docs.rs/async-trait) — accessed 2026-08-05
- [tokio crate on docs.rs — version 1.53.1, published 20 July 2026](https://docs.rs/crate/tokio/latest) — accessed 2026-08-05

## Changelog
- 2026-08-05 — created

