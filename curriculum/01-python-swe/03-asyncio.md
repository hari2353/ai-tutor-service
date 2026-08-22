# Asyncio Deep Dive: Event Loop Internals, TaskGroups, Cancellation, and Backpressure

> **Track:** T01 Python & SWE Craft · **Time:** 3.5h · **Prereqs:** T01-data-model · **Updated:** 2026-08-03
> **Module id:** `T01-asyncio` · **Tags:** concurrency, critical

## The 30-second version

The asyncio event loop is a single-threaded scheduler running one coroutine at a time until it hits an `await` on something not yet ready, at which point it suspends that coroutine, registers a callback for when the awaited thing becomes ready (a socket readable, a timer firing, another task completing), and runs whatever else is ready — concurrency here means "many things in flight," never "many things executing simultaneously," which is the single fact that resolves most asyncio confusion (a CPU-bound `while True: pass` inside a coroutine blocks the entire loop, because nothing ever yields control back). `asyncio.TaskGroup` (3.11+) replaced the error-prone `asyncio.gather()` pattern with structured concurrency: every task spawned inside a `TaskGroup` is guaranteed to either complete or be cancelled before the `async with` block exits, and if any task raises, every sibling task is cancelled and all resulting exceptions are collected into a single `ExceptionGroup` rather than silently dropping all-but-one. Cancellation is cooperative, not preemptive — `task.cancel()` schedules a `CancelledError` to be raised at the task's *next* suspension point (the next `await`), meaning a task that never awaits anything cannot be cancelled at all, and cleanup code (`finally` blocks, `except CancelledError` handlers) must re-raise `CancelledError` after cleanup or the task silently appears to have completed normally instead of being cancelled — swallowing it is one of the most common and most dangerous asyncio bugs. Backpressure — the mechanism by which a fast producer is prevented from overwhelming a slow consumer — is not automatic in asyncio; an unbounded `asyncio.Queue` or an unthrottled loop of concurrent requests will happily grow memory or hammer a downstream service until something breaks, which is exactly why bounded queues, semaphores, and token-bucket rate limiting are load-bearing production patterns, not defensive-programming nice-to-haves.

## Why this gets asked

Because asyncio is the concurrency model behind nearly every production Python service doing I/O at scale — API gateways, LLM-serving proxies, agent orchestration loops — and this candidate's own resume includes production agentic systems (FastMCP, A2A, LangGraph) that live or die on getting cancellation, timeouts, and backpressure right. An interviewer who has debugged a production incident caused by a swallowed `CancelledError` masking a task that should have died, or a memory leak from an unbounded queue during a downstream slowdown, wants to know whether you've internalized asyncio's cooperative, single-threaded execution model deeply enough to reason about these failure modes before they happen, not just written `async def` and `await` correctly in the happy path.

---

## Lineage: past → present → future

**What came before.** Python concurrency for I/O-bound work before asyncio (PEP 3156, Python 3.4, 2014) meant either threads (real OS-level concurrency, but bottlenecked by the GIL for CPU-bound portions and carrying real per-thread memory/context-switch overhead that limits scaling to thousands of concurrent connections) or callback-based event loop libraries (Twisted predates asyncio by over a decade and pioneered the single-threaded reactor pattern in Python, but callback-based code suffers from "callback hell" — deeply nested, hard-to-follow control flow that obscures what would otherwise be simple sequential logic). `async`/`await` syntax (PEP 492, Python 3.5, 2015) let asyncio's event-loop model be written in a style that *looks* sequential while actually suspending and resuming at `await` points, directly solving callback hell's readability problem while keeping the single-threaded, high-concurrency-per-connection efficiency that made event loops attractive for I/O-bound workloads in the first place.

**Where it stands now.** `asyncio.TaskGroup` and `asyncio.timeout()` (both Python 3.11) represent the current consensus best practice, having replaced the earlier `asyncio.gather()`/`asyncio.wait_for()` patterns specifically because those older APIs had well-documented, easy-to-hit correctness pitfalls — `gather()` without `return_exceptions=True` cancels sibling tasks on the first exception but can silently lose exceptions from tasks that were already about to complete, and manually-written cancellation/cleanup code around `wait_for()` was a frequent source of subtle bugs. `TaskGroup`'s structured-concurrency guarantee (no task can outlive its enclosing block, exceptions are always collected, never silently dropped) is now the standard recommended pattern for any new code spawning multiple concurrent tasks, and libraries like `anyio` provide a structured-concurrency layer that works across both asyncio and `trio` (a separate, structured-concurrency-first async framework) for code that needs backend portability. The live, genuinely unsettled area is around a specific class of bugs PEP 789 addresses — cancellation interacting badly with async generators that `yield` inside a context manager or `finally` block, where a cancellation arriving at the wrong moment inside a generator's suspended state can leave cleanup code in an inconsistent position; this is an active area of ongoing CPython refinement, not settled the way `TaskGroup`'s core semantics now are.

**Where it's heading.** Structured concurrency (the `TaskGroup` model, and the broader idea that concurrent task lifetimes should be lexically scoped and impossible to accidentally leak) is the clear, converged direction for the ecosystem, with continued refinement of edge cases around cancellation propagation through generators and context managers (PEP 789 and related ongoing work) rather than any structural rethinking of the event-loop model itself. Interop between asyncio and free-threaded (no-GIL) Python (module `T01-gil-parallelism`) is an area to watch but not yet a settled story — asyncio's single-threaded event loop model doesn't inherently require the GIL's protection the way naive multi-threaded code does, but how asyncio-based systems should evolve to take advantage of free-threading for genuinely CPU-bound portions of an otherwise I/O-bound service is still being worked out in practice as free-threaded Python moves from officially-supported (3.14) toward being a more common production deployment target.

---

## Mental model

```
EVENT LOOP: ONE thread, ONE thing running at a time, switches ONLY at "await"

  coroutine A: ---running---[await socket.read()]---SUSPENDED-----------[resumed]---running---
  coroutine B:                                        ---running---[await]---SUSPENDED----
  coroutine C: ------------------------------------------------------------running-------

  time ------------------------------------------------------------------------------->

  "concurrency" here = MANY THINGS IN FLIGHT (suspended, waiting on I/O)
  NEVER "many things executing at the literal same instant" (that's real parallelism,
  which asyncio does NOT provide -- see gil-parallelism module)

  a CPU-bound `while True: compute()` inside a coroutine with NO await NEVER yields
  control -- it blocks the ENTIRE event loop, every other task, forever

CANCELLATION IS COOPERATIVE, NOT PREEMPTIVE:
  task.cancel()  -->  schedules CancelledError to be raised at the task's
                       NEXT suspension point (next `await`), NOT immediately
  a task that never awaits ANYTHING cannot be cancelled AT ALL until it does

  async def worker():
      try:
          await do_work()
      except asyncio.CancelledError:
          await cleanup()          # OK to await briefly for cleanup
          raise                    # <-- MUST re-raise, or task looks like it SUCCEEDED
      # swallowing CancelledError here = the #1 asyncio production bug

TASKGROUP (3.11+): structured concurrency -- ALL tasks spawned inside the `async with`
  block are guaranteed to finish OR be cancelled before the block exits
    async with asyncio.TaskGroup() as tg:
        tg.create_task(fetch_a())
        tg.create_task(fetch_b())
    # <- guaranteed: BOTH tasks done, or an ExceptionGroup raised with ALL failures
    #    (one task failing cancels its SIBLINGS automatically -- no leaked tasks, ever)

BACKPRESSURE: NOT automatic -- a fast producer + unbounded asyncio.Queue = unbounded
  memory growth. Bounded queue / semaphore / token bucket are the load-bearing fixes.
```

The one-line mental model: **asyncio gives you cheap, high-concurrency I/O multiplexing on a single thread by cooperatively switching only at `await` points — every correctness property you actually need (guaranteed cleanup, no leaked tasks, no unbounded memory growth) has to be built deliberately on top of that primitive, because none of it is automatic.**

---

## How it actually works

### The event loop's core mechanism: callbacks, futures, and the select/epoll layer underneath

At its lowest level, the asyncio event loop maintains a ready queue of callbacks to run and delegates the "is this socket/file descriptor ready yet" question to the OS's I/O multiplexing mechanism (`epoll` on Linux, `kqueue` on macOS/BSD, IOCP on Windows) — when you `await socket.recv()`, the coroutine registers interest in that socket becoming readable and suspends; the event loop's underlying `select`/`epoll` call blocks (efficiently, at the OS level, across potentially thousands of registered file descriptors simultaneously) until at least one is ready, then the loop wakes up, runs the callback associated with each newly-ready descriptor (which resumes the corresponding suspended coroutine from exactly where it left off), and the cycle repeats. A `Future` is the low-level primitive representing "a value that will be available later" — a `Task` is a `Future` specifically wrapping a coroutine's execution, and `await`ing a coroutine, a `Task`, or a `Future` all resolve to the same underlying suspend-until-ready mechanism, just at different levels of the abstraction.

### Why CPU-bound code inside a coroutine blocks everything

Because the event loop is fundamentally single-threaded and only switches execution at explicit suspension points, any code that runs for a long time *without* hitting an `await` (a tight computational loop, a synchronous blocking call like `time.sleep()` or a synchronous `requests.get()`) monopolizes the only thread the entire loop has, meaning every other task — regardless of how "concurrent" they were designed to be — simply cannot make progress until that blocking code finishes. This is the single most common asyncio production mistake for engineers coming from a threading background: calling a synchronous, blocking library function (a non-async database driver, a synchronous HTTP client) directly inside an `async def` function doesn't make it non-blocking — it silently blocks the entire event loop for the call's full duration, and the fix is either using a genuinely async-native version of that library, or explicitly offloading the blocking call to a thread pool via `loop.run_in_executor()` (or `asyncio.to_thread()`, the higher-level 3.9+ wrapper) so the event loop's own thread stays free to service other tasks while the blocking call runs elsewhere.

### Cancellation: the exact mechanics, and why swallowing `CancelledError` is dangerous

`task.cancel()` does not immediately stop a task — it arranges for a `CancelledError` to be raised inside the coroutine at its next suspension point (the next time it reaches an `await`), which means a task's actual response to cancellation depends entirely on what code happens to be running when the cancellation request arrives, and a task performing a long synchronous computation with no intervening `await` genuinely cannot be cancelled until it next yields control. Once `CancelledError` is raised inside the coroutine, standard exception-handling semantics apply — a `try`/`finally` or `except CancelledError` block can run cleanup code — but **the coroutine must re-raise `CancelledError`** (or let it propagate un-caught) once cleanup finishes; if a coroutine catches `CancelledError` and doesn't re-raise it (returning normally instead, or raising a different exception), the enclosing `Task` reports as having completed normally (or with that different exception) rather than as cancelled, which can silently violate an caller's assumption that cancellation actually happened — this is precisely the failure mode where a "cancelled" background task keeps running invisibly, or a `TaskGroup`'s cancellation-on-sibling-failure guarantee gets quietly undermined by one task that ate its own cancellation. Since Python 3.11, a task can also be "uncancelled" (`Task.uncancel()`) — a mechanism specifically added to let structured-concurrency constructs like `TaskGroup` and `asyncio.timeout()` correctly scope cancellation to just their own block, distinguishing "this specific `asyncio.timeout()` block's deadline fired" from "someone cancelled the entire outer task," which naive cancellation handling before 3.11 could conflate.

### `asyncio.TaskGroup`: structured concurrency and the `ExceptionGroup` it produces

Before `TaskGroup`, `asyncio.gather()` was the standard way to run multiple coroutines concurrently and collect their results, but it has real, well-documented pitfalls: without `return_exceptions=True`, the first task to raise an exception causes `gather()` to re-raise that exception immediately, but the *other* tasks are not automatically cancelled by default in all versions/usages, meaning they can keep running as orphaned, un-awaited background work with no clean way to know when they finish or to collect their own exceptions if they also fail. `TaskGroup` fixes this by construction: every task created via `tg.create_task()` inside an `async with asyncio.TaskGroup() as tg:` block is tracked by the group, and the block does not exit until every task has either completed or been cancelled — if any task raises an exception (other than `CancelledError`), `TaskGroup` automatically cancels every other task still running in the group, waits for all of them to actually finish (respecting cooperative cancellation, so cleanup code still runs), and then raises a single `ExceptionGroup` (or `BaseExceptionGroup`) containing every exception that was actually raised across all the failed tasks — not just the first one, which is a genuine, structural improvement over `gather()`'s silent-loss risk for anyone who needs to know about every failure, not just the first.

### Backpressure: why it's not automatic, and the three standard mechanisms

Nothing in asyncio's core model prevents a producer from creating work faster than a consumer can process it — an unbounded `asyncio.Queue()` will accept `put()` calls indefinitely, growing memory without limit if the consumer falls behind, and a loop that fires off `asyncio.create_task()` for every incoming request with no limit will happily have thousands of tasks in flight simultaneously, each consuming memory and potentially hammering a downstream dependency with unbounded concurrent requests. Three standard mechanisms address this:
- **Bounded queues** (`asyncio.Queue(maxsize=N)`) make `put()` itself an awaitable operation that blocks (suspends the producer coroutine) once the queue is full, until the consumer drains it below the limit — this directly couples producer speed to consumer speed, which is the actual definition of backpressure.
- **Semaphores** (`asyncio.Semaphore(N)`) cap the number of concurrent operations of a specific kind (e.g., outbound HTTP requests) regardless of how many are logically "wanted" at once, providing a simple, coarse-grained concurrency limit without needing an explicit queue.
- **Token-bucket rate limiting** caps not just concurrency but *throughput over time* — a bucket holds up to `capacity` tokens, refilling at `rate` tokens per second, and each operation must acquire a token before proceeding (waiting if none are available), which is the standard mechanism for respecting a downstream API's rate limit (requests per second) as distinct from simply limiting how many requests are in flight simultaneously — a semaphore alone caps concurrency but not the *rate* at which new requests are allowed to start, which is exactly the gap token-bucket rate limiting closes.

---

## Build it from scratch

```python
import asyncio
import time

async def token_bucket_rate_limiter(rate: float, capacity: float):
    """Async generator-style rate limiter: acquire() blocks until a token is available.
    rate: tokens added per second. capacity: max tokens that can accumulate (burst size)."""
    tokens = capacity
    last_refill = time.monotonic()
    lock = asyncio.Lock()

    async def acquire():
        nonlocal tokens, last_refill
        while True:
            async with lock:
                now = time.monotonic()
                elapsed = now - last_refill
                tokens = min(capacity, tokens + elapsed * rate)
                last_refill = now
                if tokens >= 1:
                    tokens -= 1
                    return
                wait_time = (1 - tokens) / rate
            await asyncio.sleep(wait_time)   # release lock while waiting -- don't hold it across sleep

    return acquire

async def fetch_with_rate_limit(acquire, url: str) -> str:
    await acquire()
    # ... actual request would go here ...
    return f"fetched {url}"

async def bounded_producer_consumer(n_items: int, max_queue_size: int, n_workers: int):
    queue: asyncio.Queue[int] = asyncio.Queue(maxsize=max_queue_size)   # BOUNDED -> real backpressure

    async def producer():
        for i in range(n_items):
            await queue.put(i)     # blocks (suspends) once queue is full -- producer is throttled
        for _ in range(n_workers):
            await queue.put(None)  # sentinel to stop each worker

    async def worker(worker_id: int):
        while True:
            item = await queue.get()
            if item is None:
                break
            await asyncio.sleep(0.01)   # simulate work
            queue.task_done()

    async with asyncio.TaskGroup() as tg:
        tg.create_task(producer())
        for i in range(n_workers):
            tg.create_task(worker(i))

async def demonstrate_cooperative_cancellation():
    async def worker():
        try:
            await asyncio.sleep(10)          # suspension point -- cancellation lands HERE
        except asyncio.CancelledError:
            print("cleaning up...")
            await asyncio.sleep(0.01)        # brief cleanup is fine
            raise                             # MUST re-raise -- omitting this hides the cancellation

    task = asyncio.create_task(worker())
    await asyncio.sleep(0.1)
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        print("task was correctly reported as cancelled")

async def demonstrate_taskgroup_exception_collection():
    async def fails_after(delay, msg):
        await asyncio.sleep(delay)
        raise ValueError(msg)

    try:
        async with asyncio.TaskGroup() as tg:
            tg.create_task(fails_after(0.1, "first failure"))
            tg.create_task(fails_after(0.2, "second failure"))   # gets CANCELLED once first task raises,
                                                                   # but if it had ALREADY raised by then,
                                                                   # BOTH exceptions appear in the group
    except* ValueError as eg:
        print(f"collected {len(eg.exceptions)} exception(s)")    # except* is the ExceptionGroup handler syntax
```
The lab exercise runs the bounded producer-consumer against an unbounded (`maxsize=0`, meaning unlimited) queue variant under a slow-consumer simulation, measuring actual process memory growth over time for each — making the "unbounded queue = unbounded memory growth under backpressure" claim empirically visible rather than asserted — and separately demonstrates the swallowed-`CancelledError` bug by removing the `raise` from `demonstrate_cooperative_cancellation` and showing the task reports as completed rather than cancelled.

---

## How it's done in production

| Symptom | Cause | Fix |
|---|---|---|
| A service's event loop appears to "freeze" — no tasks make progress for a noticeable stretch, then resume all at once | A synchronous, blocking call (a non-async database driver, `time.sleep()`, a CPU-bound loop) ran inside a coroutine with no `await`, monopolizing the single event-loop thread | Replace with a genuinely async-native library, or offload the blocking call to a thread pool via `asyncio.to_thread()`/`loop.run_in_executor()` so the event loop thread stays free |
| A background task that was explicitly cancelled keeps running invisibly, or its cleanup never seems to happen | The task's `except CancelledError` block didn't re-raise (or caught a broader `Exception` that also swallowed `CancelledError`), so the task reports as completed normally rather than cancelled | Always re-raise `CancelledError` after any cleanup logic; never catch it with a bare `except Exception:` that doesn't specifically handle and re-raise `CancelledError` |
| Process memory grows steadily and unboundedly whenever a downstream dependency slows down, recovering only after the dependency speeds back up | An unbounded `asyncio.Queue()` (or unthrottled `create_task()` loop) lets a fast producer keep enqueuing work faster than a slowed consumer can drain it | Use a bounded queue (`asyncio.Queue(maxsize=N)`), a semaphore capping concurrent in-flight work, or both — making queue growth itself throttle the producer |
| Concurrent requests to a third-party API intermittently get rate-limited (HTTP 429) even though the service stays well under its own configured concurrency limit | A semaphore caps *concurrency* (how many requests are in flight at once) but not *rate* (how many new requests start per second) — a burst of requests completing quickly can still exceed a per-second rate limit even with low concurrency | Add token-bucket rate limiting specifically targeting requests-per-second, layered alongside (not instead of) a concurrency-capping semaphore |
| Using `asyncio.gather()` with several tasks, one fails, and a completely unrelated exception from another (still-running) task surfaces later, confusingly, in an unrelated part of the code | `gather()`'s default (without `return_exceptions=True`) re-raises the first exception immediately but doesn't necessarily cancel or await the other tasks cleanly, leaving them to raise their own exceptions later, orphaned from the original call site | Migrate to `asyncio.TaskGroup`, which cancels all sibling tasks on any failure and collects every exception into a single, co-located `ExceptionGroup` at the point of the `async with` block, rather than letting failures surface asynchronously and disconnectedly |

---

## Tradeoffs & when NOT to use it

- **Don't use asyncio for CPU-bound work expecting a concurrency speedup.** Asyncio's single-threaded model provides zero parallelism for CPU-bound code — a CPU-bound task blocks the entire event loop regardless of how many coroutines are "concurrently" defined; genuine CPU-bound parallelism requires multiprocessing or free-threaded Python (covered in the gil-parallelism module), not asyncio.
- **Don't reach for `asyncio.gather()` in new code when `TaskGroup` is available (3.11+).** `TaskGroup`'s structured-concurrency guarantees (no leaked tasks, full exception collection) directly address `gather()`'s well-documented pitfalls; there's little remaining justification for `gather()` in new code targeting 3.11+, outside of maintaining compatibility with an older Python version.
- **Don't catch `CancelledError` broadly (e.g., a bare `except Exception:` around code that might raise it) without explicit awareness that you're doing so.** This is the single most dangerous asyncio anti-pattern in this module — always ensure `CancelledError` is either allowed to propagate naturally or is explicitly caught, cleaned up after, and re-raised, never silently absorbed by a catch-all handler.
- **Don't assume a semaphore alone is sufficient rate-limiting for a downstream API with an explicit requests-per-second limit.** A semaphore controls concurrency, not throughput over time — a burst of fast-completing requests can still exceed a rate limit even under a low concurrency cap; use token-bucket rate limiting specifically when the constraint is genuinely about request *rate*, not just concurrent *count*.
- **Don't leave a queue unbounded "to be safe" against ever blocking a producer.** An unbounded queue trades a controlled, visible backpressure signal (the producer briefly waiting) for an uncontrolled, invisible one (memory growth until the process is OOM-killed) — a bounded queue with an explicit, reasoned-about size is almost always the safer production choice.

---

## Interview questions

### Q1 — Why does a synchronous, blocking function call inside an `async def` coroutine block every other task in the process, not just the calling coroutine?
**Testing:** the single-threaded, cooperative-scheduling mental model applied to the most common asyncio production mistake.
**Answer:** The event loop is single-threaded and only switches between coroutines at explicit suspension points (`await`). A synchronous blocking call (no `await` inside it) never yields control back to the loop — it runs to completion on the one thread the loop has, during which literally nothing else registered with that loop (every other task, timer, or I/O callback) can make any progress at all, regardless of how many coroutines were logically defined as "concurrent."
**Follow-up trap:** *"If the blocking call is very short (a few milliseconds), is this still a real problem in practice?"* — it's a matter of degree, not kind — a few-millisecond blocking call briefly delays every other task by that amount, which may be negligible for a low-concurrency service but becomes a serious, compounding problem at high concurrency (hundreds or thousands of tasks each briefly blocked by every other task's blocking calls) or if the "short" call occasionally has a long tail (e.g., an occasional slow disk I/O or DNS lookup) — the safe default is to never make a blocking call inside a coroutine without deliberately reasoning about this cost, not to informally judge "short enough to be fine."

### Q2 — Precisely, what does `task.cancel()` do, and why can a task that never awaits anything be uncancellable in practice?
**Testing:** cooperative vs. preemptive cancellation, stated with the exact mechanism.
**Answer:** `task.cancel()` schedules a `CancelledError` to be raised inside the task's coroutine at its *next* suspension point — it does not stop execution immediately or from the outside. If the coroutine's code never reaches another `await` (e.g., it's stuck in a long synchronous computation, or an infinite loop with no `await` inside it), there is no suspension point for the scheduled cancellation to actually take effect at, so the task continues running uninterrupted despite `cancel()` having been called — cancellation is fundamentally cooperative, requiring the coroutine to periodically yield control for it to actually take effect.
**Follow-up trap:** *"If you suspect a coroutine might run for a long time without an await, what would you add to make it genuinely cancellable?"* — add explicit `await asyncio.sleep(0)` calls (which yield control back to the event loop without actually delaying, giving cancellation a chance to be delivered) at reasonable intervals within a long-running loop, or restructure the work to run in a thread pool (`asyncio.to_thread()`) where the parent task awaiting it remains genuinely cancellable even if the underlying thread itself can't be interrupted mid-computation — the underlying thread-pool work still can't be forcibly killed, but the *awaiting* coroutine's cancellation semantics remain correct.

### Q3 — Why is silently swallowing `CancelledError` (catching it without re-raising) considered one of the most dangerous asyncio bugs, mechanically?
**Testing:** the specific, concrete consequence of this bug, not just "it's bad practice."
**Answer:** If a coroutine catches `CancelledError` and doesn't re-raise it (letting the function return normally, or return some other value/raise a different exception instead), the enclosing `Task` object reports its final state as completed successfully (or with that different exception), not as cancelled — any caller checking `task.cancelled()` or awaiting the task expecting a `CancelledError` to propagate will be wrong about what actually happened, and any structured-concurrency construct (like `TaskGroup`) relying on cancellation propagating correctly to know a task is genuinely done can have its own guarantees quietly undermined by this one misbehaving task.
**Follow-up trap:** *"Is it ever correct to catch CancelledError without immediately re-raising it?"* — yes, but only if cleanup code needs to run first (a `finally`-equivalent use), and the re-raise must still happen after that cleanup completes — the only legitimate reason to catch `CancelledError` at all is to run cleanup logic before letting the cancellation continue to propagate, never to suppress the cancellation itself; any code path that catches it and doesn't eventually re-raise (or let it propagate) is presumptively a bug, not a legitimate design choice, absent a very specific and unusual justification.

### Q4 — What specific guarantee does `asyncio.TaskGroup` provide that `asyncio.gather()` does not, and why does that guarantee matter for exception handling specifically?
**Testing:** the structured-concurrency improvement, precisely, not just "TaskGroup is newer/better."
**Answer:** `TaskGroup` guarantees that every task created inside its `async with` block either completes or is cancelled before the block exits, and if any task raises an exception, every other task in the group is automatically cancelled and the block waits for all of them to actually finish before proceeding — collecting *every* exception raised across all failed tasks into a single `ExceptionGroup`. `gather()` (without careful, explicit `return_exceptions=True` handling) re-raises only the first exception encountered and does not, by default, guarantee the other tasks are cleanly cancelled and awaited — meaning additional failures from other tasks can be silently lost, or those tasks can continue running as orphaned background work with no clear point where their completion (or further failure) is accounted for.
**Follow-up trap:** *"If you use gather() with return_exceptions=True, doesn't that solve the same problem?"* — it solves the "don't lose exceptions" part (every task's result or exception is collected into the returned list rather than the first one short-circuiting), but it does *not* provide TaskGroup's automatic sibling-cancellation-on-failure behavior — with `return_exceptions=True`, every task runs to completion regardless of whether a sibling failed, which may be the wrong behavior if a failure in one task means the others' results are no longer needed and should be cancelled promptly to save resources — `gather(return_exceptions=True)` and `TaskGroup` make genuinely different tradeoffs, not the same guarantee via a different API.

### Q5 — Explain why a semaphore alone is insufficient to respect a downstream API's requests-per-second rate limit, and what token-bucket rate limiting adds.
**Testing:** the concurrency-versus-rate distinction, concretely.
**Answer:** A semaphore caps how many operations can be *in flight simultaneously* — it says nothing about how quickly new operations are allowed to *start*. If requests complete quickly (fast round-trip time), a semaphore with a modest concurrency limit can still allow far more than the target requests-per-second to actually start and complete within a given second, exceeding a rate limit defined in terms of throughput over time, not concurrent count. Token-bucket rate limiting directly caps the *rate* new operations can start (tokens refill at a fixed rate per second, and an operation must acquire a token before proceeding), which is the actual dimension a requests-per-second limit constrains.
**Follow-up trap:** *"If you set a token bucket's capacity very high relative to its refill rate, does it still enforce a meaningful rate limit?"* — the capacity parameter controls allowed *burst* size (how many tokens can accumulate during idle periods, permitting a short burst of requests faster than the steady-state rate), while the refill rate controls the actual sustained long-run rate — a very high capacity relative to rate allows large bursts that could still trigger a downstream rate limit if the downstream service enforces its limit over a short window, so capacity needs to be chosen with the downstream system's actual enforcement window in mind, not just "higher capacity is more permissive and therefore safer."

### Q6 — Why does `Task.uncancel()` exist, and what specific problem did it solve that pre-3.11 cancellation handling couldn't address cleanly?
**Testing:** understanding the scoped-cancellation problem `uncancel()` and structured concurrency constructs solve together.
**Answer:** Before this mechanism, there was no clean way to distinguish "this specific `asyncio.timeout()` block's deadline expired, so only this block's work should stop" from "someone cancelled the entire outer task for an unrelated reason" — both manifested as the same `CancelledError` propagating up, and code couldn't reliably tell which had happened or correctly scope its response to just the relevant block. `Task.uncancel()` lets constructs like `asyncio.timeout()` and `TaskGroup` internally track and reverse a cancellation request that was scoped specifically to their own block, allowing the surrounding code (and any code outside that specific `async with` block) to continue running normally rather than treating a scoped timeout as if the entire task had been externally cancelled.
**Follow-up trap:** *"Does this mean nested asyncio.timeout() blocks now compose correctly, where a pre-3.11 naive implementation might not have?"* — yes, this is exactly the composability problem `uncancel()` and the related cancellation-scoping mechanism were introduced to solve — nested timeout blocks (an outer, longer timeout wrapping an inner, shorter one) can now correctly determine which specific timeout fired without the inner timeout's cancellation being mistaken for (or bleeding into) the outer scope's cancellation state, which was a genuine, hard-to-work-around limitation before this mechanism existed.

### Q7 — A production service's memory usage grows steadily during a downstream dependency's slowdown and doesn't recover until the dependency speeds back up. Diagnose the likely asyncio-specific cause and the fix.
**Testing:** connecting an observable production symptom to the specific backpressure mechanism failure.
**Answer:** Almost certainly an unbounded (or effectively unbounded) `asyncio.Queue`, or an unthrottled loop creating new tasks for incoming work faster than the slowed-down downstream dependency can be consumed — every unit of incoming work keeps getting enqueued/spawned regardless of how far behind processing has fallen, so memory grows in direct proportion to how much backlog has accumulated, only shrinking once the downstream dependency catches back up and the backlog drains. Fix: switch to a bounded `asyncio.Queue(maxsize=N)` so `put()` itself becomes a backpressure signal (the producer coroutine suspends once the queue is full, naturally throttling ingestion to match actual processing capacity), and/or cap concurrent in-flight work with a semaphore.
**Follow-up trap:** *"If the queue is already bounded but memory still grows under the same slowdown scenario, what else could be the cause?"* — check for a separate unbounded resource accumulating independently of the queue itself — e.g., an unbounded number of concurrently-created tasks each holding onto per-task memory (large request payloads, open connections) even while genuinely waiting on the bounded queue's `put()`, or a connection pool that isn't itself capped and keeps opening new connections to compensate for slow ones rather than reusing/limiting them — a bounded queue addresses one specific backpressure point, not every possible unbounded-resource-growth path in a complex service.

### Q8 — Why does the exact timing of when a `CancelledError` is delivered matter for correctly writing cleanup code, and what's a concrete scenario where naive cleanup code breaks?
**Testing:** the subtlety of cancellation landing mid-operation, connecting to real cleanup-code bugs.
**Answer:** Because cancellation can be delivered at *any* `await` point, cleanup code inside an `except CancelledError:` or `finally:` block that itself contains an `await` (e.g., an async cleanup call like closing a connection) is *also* a suspension point where a second cancellation (or the same cancellation being redelivered) could interrupt the cleanup itself before it finishes — naive cleanup code that assumes it will run to completion once entered can be left half-finished if it awaits something and gets interrupted again, e.g., a cleanup routine that awaits releasing a lock but gets cancelled again before that release completes, leaving the lock held indefinitely.
**Follow-up trap:** *"What's a practical mitigation for cleanup code that itself needs to await something, given this risk?"* — use `asyncio.shield()` around the specific cleanup operation that must not be interrupted (shielding it from a second, in-flight cancellation while still allowing the outer cancellation itself to have been correctly received and eventually re-raised after cleanup completes), or restructure cleanup to avoid awaiting anything cancellable at all where possible (e.g., a synchronous, fast resource-release call instead of an async one) — `asyncio.shield()` itself requires careful use, since shielding the wrong scope can accidentally prevent a cancellation from ever completing if misapplied, so this is a case where the fix itself needs to be reasoned about carefully, not applied reflexively.

### Q9 — Design question: you're building an LLM-serving proxy that fans out a single incoming request to three backend model providers concurrently and returns the first successful response, cancelling the other two. Walk through how you'd implement this correctly with asyncio, and what specifically could go wrong with a naive implementation.
**Testing:** synthesizing TaskGroup-style structured concurrency, cancellation correctness, and a "first success wins" race pattern.
**Answer:** Use `asyncio.wait()` with `return_when=FIRST_COMPLETED` (or a manually-managed set of tasks) to race the three provider calls, and upon the first successful completion, explicitly call `.cancel()` on the remaining pending tasks and `await` them (catching and discarding their eventual `CancelledError`) to ensure they're cleanly finished before returning — a naive implementation that simply returns as soon as the first result arrives, without explicitly cancelling and awaiting the other two tasks, leaves them running as orphaned background work that continues consuming resources (holding open connections, consuming rate-limit budget with the other providers) with no clear point where they're accounted for or cleaned up. Each provider call itself needs correct cancellation handling internally (any `except CancelledError` in that call's own code must re-raise after cleanup, per the earlier discussion) for the cancellation to actually terminate the underlying HTTP request/connection rather than leaving it running server-side.
**Follow-up trap:** *"What if one of the 'losing' provider calls has already committed a side effect (e.g., started a billable operation) by the time it gets cancelled?"* — cancellation only stops the *client-side* coroutine's further execution; it does not undo any side effect that had already occurred on the provider's server before the cancellation was delivered — if the fan-out pattern risks triggering costly or non-idempotent side effects on "losing" branches, the design needs an explicit accounting/reconciliation mechanism (logging which providers were invoked regardless of outcome, potentially a compensating cleanup call to the provider) rather than assuming client-side cancellation alone makes a losing branch's side effects disappear — this is a real, common gap in naive "race and cancel the losers" implementations.

### Q10 — Why doesn't asyncio provide any parallelism speedup for CPU-bound work, and what would you actually recommend to a teammate who wants to "parallelize" a CPU-bound computation using asyncio?
**Testing:** the fundamental limit of asyncio's concurrency model and the correct redirection to the right tool.
**Answer:** Asyncio's concurrency comes entirely from suspending at `await` points while waiting on I/O — it runs on a single thread, so CPU-bound code (which never awaits, since there's no I/O to wait on) simply runs to completion on that one thread with zero speedup from having "many" coroutines defined, exactly like the blocking-call problem in Q1, just framed as an intentional (mistaken) parallelization attempt rather than an accidental blocking call. For genuine CPU-bound parallelism, the correct tools are `multiprocessing` (separate processes, real parallel execution, sidesteps the GIL entirely at the cost of inter-process communication overhead) or, increasingly, free-threaded Python (3.13+ officially supported in 3.14, covered in the gil-parallelism module) for genuinely parallel *threads* without the GIL's historical single-thread-at-a-time constraint — asyncio itself is simply the wrong tool for this problem regardless of how it's used.
**Follow-up trap:** *"If the CPU-bound work needs to happen alongside a lot of existing async I/O code, what's the practical integration pattern, rather than a full rewrite?"* — use `loop.run_in_executor()` with a `ProcessPoolExecutor` (not the default `ThreadPoolExecutor`, which doesn't help with CPU-bound work due to the GIL under a standard, non-free-threaded build) to offload specifically the CPU-bound portions to separate worker processes while the surrounding async I/O code continues to run on the event loop normally, awaiting the executor's future — this integrates genuine parallelism into an otherwise asyncio-based codebase without requiring a full architectural rewrite, and is the standard practical pattern for exactly this common request.

---

## Red flags that fail you

- Believes asyncio provides real parallelism for CPU-bound code, or doesn't know a blocking synchronous call inside a coroutine freezes the entire event loop.
- Cannot explain why `task.cancel()` doesn't stop execution immediately, or doesn't know cancellation only takes effect at the next `await`.
- Swallows `CancelledError` without re-raising in example code, or doesn't recognize this as a serious bug when shown it.
- Cannot explain what specific guarantee `TaskGroup` provides over `gather()`, or thinks they're interchangeable.
- Treats backpressure as automatic in asyncio, or doesn't know an unbounded queue can cause unbounded memory growth.
- Confuses a semaphore (concurrency limit) with a rate limiter (throughput-over-time limit) as solving the same problem.

---

## Cheat card

```
EVENT LOOP: single thread, switches ONLY at await -- "concurrency" = many things IN
  FLIGHT (suspended on I/O), NEVER simultaneous execution. CPU-bound code w/ no await
  BLOCKS THE ENTIRE LOOP, every other task, until it finishes.
  fix for blocking sync calls: asyncio.to_thread() / loop.run_in_executor()

CANCELLATION IS COOPERATIVE: task.cancel() schedules CancelledError at the NEXT await,
  NOT immediate. A task with no await is UNCANCELLABLE until it hits one.
  MUST re-raise CancelledError after cleanup, or the task silently reports as
  COMPLETED NORMALLY -- the #1 asyncio production bug (swallowed cancellation)
  Task.uncancel() (3.11+): lets TaskGroup/asyncio.timeout() scope cancellation to
  their OWN block, distinguishing "this timeout fired" from "whole task cancelled"

TASKGROUP (3.11+) vs gather(): TaskGroup guarantees EVERY task finishes or is
  cancelled before the `async with` exits; one failure auto-cancels ALL siblings;
  ALL exceptions collected into one ExceptionGroup (except* to handle).
  gather() (no return_exceptions=True): first exception re-raises immediately,
  other tasks NOT guaranteed cancelled/awaited -> can silently orphan/lose exceptions
  gather(return_exceptions=True): collects all results/exceptions but does NOT
  auto-cancel siblings on failure -- different tradeoff, not the same guarantee

BACKPRESSURE IS NOT AUTOMATIC:
  unbounded asyncio.Queue() / unthrottled create_task() loop = UNBOUNDED memory growth
  under a slow consumer/downstream dependency
  BOUNDED QUEUE (maxsize=N): put() itself suspends producer once full -- real backpressure
  SEMAPHORE(N): caps CONCURRENCY (in-flight count), NOT rate/throughput over time
  TOKEN BUCKET: caps RATE (tokens refill at rate/sec, capacity=max burst) -- needed
  specifically for a downstream requests-per-second limit, which a semaphore alone can't enforce

CPU-BOUND WORK: asyncio gives ZERO parallelism speedup (single thread, no I/O to await on)
  -> use ProcessPoolExecutor via run_in_executor(), or free-threaded Python (gil-parallelism module)
```

## Sources

- [PEP 3156 — Asynchronous IO Support Rebooted](https://peps.python.org/pep-3156/) — accessed 2026-08-03
- [PEP 492 — Coroutines with async and await syntax](https://peps.python.org/pep-0492/) — accessed 2026-08-03
- [PEP 789 — Preventing task-cancellation bugs by limiting yield in async generators](https://peps.python.org/pep-0789/) — accessed 2026-08-03
- [asyncio: Coroutines and Tasks — official documentation](https://docs.python.org/3/library/asyncio-task.html) — accessed 2026-08-03
- [What's New in Python 3.11 — TaskGroup and asyncio.timeout()](https://docs.python.org/3/whatsnew/3.11.html) — accessed 2026-08-03
- [Modern AsyncIO Patterns in Python — TaskGroup, anyio, and What Changed (2026)](https://blog.rajpoot.dev/posts/python/asyncio-patterns-taskgroup-anyio-2026/) — accessed 2026-08-03

## Changelog
- 2026-08-03 — created
