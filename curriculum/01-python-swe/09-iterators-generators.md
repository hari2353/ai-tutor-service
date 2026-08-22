# Iterators vs Generators, yield, Lazy Pipelines, itertools

> **Track:** T01 Python & SWE Craft · **Time:** 2.0h · **Prereqs:** none · **Updated:** 2026-08-01
> **Module id:** `T01-iterators-generators` · **Tags:** language,critical

## The 30-second version

Every generator is an iterator, but not every iterator is a generator: an iterator is any object implementing `__iter__` and `__next__`, and a generator is one specific, compiler-assisted way to build one, by writing a function with `yield` that CPython turns into a state machine. The reason to reach for one is memory: a `list(range(10_000_000))` holds roughly 400MB of pointers plus the int objects themselves, while `(x for x in range(10_000_000))` holds about 200 bytes regardless of N, because it computes each value on demand instead of storing all of them. The trap that catches almost everyone in an interview is that generators are one-shot — once exhausted (or after a single full `for` loop), a second iteration silently yields nothing, no error, which is a uniquely dangerous kind of bug. Reach for a generator when you stream through data once, forward-only; reach for a list when you need `len()`, random access, multiple passes, or you need to sort it.

## Why this gets asked

Because "explain generators" is table stakes, but the interviewer is actually checking whether you understand the *protocol* underneath the `yield` keyword, and whether you've been burned by exhaustion in production, usually as a `pd.DataFrame` built from an already-consumed generator that comes out empty with no error, or a retried request that silently reused a spent generator and sent zero rows downstream. They have personally chased a bug where a generator was passed to two consumers and the second one got nothing.

---

## Lineage: past → present → future

**What came before.** Python 2's `range()`, `dict.keys()`, `zip()`, and `map()` all built full lists eagerly. This was fine until people started processing files and datasets that didn't fit comfortably in memory, and PEP 255 (2001) added generators to the language specifically to let a function suspend and resume instead of materializing a full sequence. Before generators existed, the idiomatic lazy pattern was to hand-write a class with `__iter__`/`__next__` and store loop state as instance attributes, which is verbose and easy to get wrong (state leaking between calls, forgetting to raise `StopIteration`). PEP 289 (2002) then generalized the syntax to generator expressions, and Python 3 (2008) finished the job by making `range`, `zip`, `map`, `filter`, and dict views lazy/iterator-based by default instead of eager — the single biggest lineage fact interviewers expect you to know cold.

**Where it stands now.** Generators and the iterator protocol are stable, unglamorous, and everywhere: every `for` loop, every unpacking, every comprehension runs through `__iter__`/`__next__` whether or not you ever write the words. The live disagreement is stylistic, not mechanical — generator pipelines (chained `yield from` and `itertools`) versus explicit intermediate lists. The pipeline style is more memory-efficient and composable but harder to debug (you can't inspect an intermediate generator's contents without consuming it), and harder to profile because time is spent lazily, spread across every downstream `next()` call rather than concentrated in one eager step. In async code the same protocol was mirrored as `__aiter__`/`__anext__` and `async def` with `yield` (PEP 525, 2016), which is now the standard way to stream results from an async data source, and interviewers increasingly ask you to contrast the two.

**Where it's heading.** No major protocol change is coming; the iterator protocol is 25 years stable and this is a feature, not stagnation. What is evolving is standard-library ergonomics: `itertools.batched` shipped in 3.12 to replace a decade of hand-rolled chunking recipes, and `itertools.pairwise` was promoted from a documented recipe to a real function in 3.10, both signals that the stdlib keeps absorbing common lazy-pipeline idioms rather than replacing the core protocol. Expect more of this — small, targeted `itertools` additions — rather than any rethink of `yield` itself. [What's New In Python 3.12](https://docs.python.org/3/whatsnew/3.12.html) — accessed 2026-08-01.

---

## Mental model

```
ITERABLE            has __iter__() -> returns an ITERATOR
   │
   ▼
ITERATOR            has __iter__() -> returns self
                     has __next__() -> next value, or raises StopIteration
   │
   │   one specific way to build an iterator:
   ▼
GENERATOR            a function containing `yield`
                     calling it does NOT run the body — it returns a generator
                     object immediately; the body runs only on next()/for
```

```
gen = my_gen()                # body has NOT executed yet
next(gen)   ──▶ runs until first `yield`, suspends, returns value
next(gen)   ──▶ resumes right after that yield, runs to next `yield`
next(gen)   ──▶ ... eventually runs off the end or hits `return`
                 -> raises StopIteration (return value becomes .value on it)
```

The suspension point is real: CPython freezes the frame (locals, instruction pointer, the evaluation stack) inside a `PyGenObject`. That frame is the entire "state machine" — there's no hidden magic beyond "the interpreter kept your stack frame alive and un-popped it."

---

## How it actually works

### The protocol, precisely

```python
class Countdown:
    def __init__(self, n):
        self.n = n

    def __iter__(self):
        return self          # I am my own iterator

    def __next__(self):
        if self.n <= 0:
            raise StopIteration
        self.n -= 1
        return self.n + 1
```

`for x in obj:` desugars to:

```python
it = iter(obj)          # calls obj.__iter__()
while True:
    try:
        x = next(it)     # calls it.__next__()
    except StopIteration:
        break
    ...body...
```

`StopIteration` is not an error in the exceptional sense, it's the protocol's normal termination signal — and this is precisely why, since PEP 479 (enforced by default since Python 3.7), a `StopIteration` raised *inside* a generator body (e.g. by calling `next()` on an exhausted sub-iterator without catching it) is converted into a `RuntimeError`. Before PEP 479, a stray `StopIteration` bubbling out of a generator would silently truncate whichever `for` loop was consuming it — a real, hard-to-find production bug class that motivated the change.

**Generator vs iterator, stated precisely, because interviewers grade this exactly:**
- Every generator object satisfies the iterator protocol (`__iter__` returns self, `__next__` exists) → every generator *is* an iterator.
- Not every iterator is a generator: `Countdown` above is an iterator with zero `yield` statements. So is a `zip` object, a file object, a database cursor.
- A generator is specifically the object produced by calling a function containing `yield`, or a generator expression `(x for x in ...)`.

### Memory profile, with real numbers

| Structure | Approx. memory | Notes |
|---|---|---|
| `list(range(10_000_000))` | ~85MB for the list's pointer array (8 bytes × 10M) **plus** ~280MB for the boxed int objects (small ints below 256 are cached and shared; larger ones cost 28 bytes each) → **~350-400MB total** | Fully materialized, random access, `len()` works |
| `range(10_000_000)` | 48 bytes, constant | Not a generator — a lazy sequence object; supports `len()` and indexing in O(1) via arithmetic |
| `(x for x in range(10_000_000))` | ~200 bytes, constant regardless of N | A genuine generator: no `len()`, no indexing, forward-only |
| `[x*x for x in range(10_000_000)]` | Similar to the list case above, computed eagerly | The classic "I wrote brackets when I meant parens" memory bug |

A single Python `int` object is at least 28 bytes on CPython (a `PyObject` header plus the digit array), which is why "10M ints" is not "10M × 8 bytes" the way it would be in a C array — this is the number to cite when someone asks why Python integers are expensive. [Massive memory overhead: Numbers in Python — Python⇒Speed](https://pythonspeed.com/articles/python-integers-memory/) — accessed 2026-08-01.

### `yield` as suspension, and generator state

```python
def gen():
    print("start")
    x = yield 1
    print("received", x)
    y = yield 2
    print("received", y)

g = gen()
next(g)          # prints "start", returns 1 — body paused AT the yield
g.send("a")      # prints "received a", returns 2 — resumes, runs to next yield
```

`yield` is an expression, not a statement — it evaluates to whatever is passed via `.send()`. This is what makes generators usable as coroutines, not just producers.

### Generators as coroutines: `send`, `throw`, `close`

```python
def logger(prefix):
    try:
        while True:
            msg = yield
            print(f"{prefix}: {msg}")
    except GeneratorExit:
        print(f"{prefix}: closing")

g = logger("INFO")
next(g)                 # prime it — must advance to the first yield before send()
g.send("started")       # INFO: started
g.throw(ValueError("boom"))   # raises ValueError at the yield point inside the generator
```

- `.send(value)` resumes the generator, making `value` the result of the paused `yield` expression. Must be primed with a `next()` or `.send(None)` first, or you get `TypeError: can't send non-None value to a just-started generator`.
- `.throw(exc)` raises `exc` at the suspended `yield` — used to inject cancellation or errors into a running pipeline stage.
- `.close()` raises `GeneratorExit` inside the generator at the suspend point; if the generator doesn't catch it (or catches it and doesn't yield again), it exits cleanly. Garbage collection calls `.close()` implicitly when a generator is dropped, which is how `finally` blocks in generators (e.g. closing a file) actually run.

### `yield from` — delegation, not iteration

```python
def inner():
    yield 1
    yield 2
    return "inner done"

def outer():
    result = yield from inner()   # transparently re-yields 1, 2
    print(result)                 # "inner done" — return value of inner() surfaces here
    yield 3
```

`yield from sub` is not sugar for `for x in sub: yield x` — that simpler form loses three things `yield from` preserves: the sub-generator's return value (captured as the expression's result), and transparent forwarding of `.send()`/`.throw()`/`.close()` calls from the caller straight into the sub-generator. This is exactly why recursive generator flattening and generator-based coroutine chaining (pre-`asyncio.gather` era, and still inside `asyncio`'s internals) use `yield from`, not a manual loop.

### The one-shot exhaustion trap

```python
gen = (x for x in range(3))
print(list(gen))   # [0, 1, 2]
print(list(gen))   # [] <-- no error, silently empty
```

A generator (and any iterator without a way to reset itself) can only be walked once. There is no exception, no warning — `for` and `list()` on an exhausted iterator simply produce zero items, because `__next__` raises `StopIteration` immediately. This is the single most common real-world bug in this area: a generator gets passed into two functions (say, a validation pass and a processing pass), the first consumes it fully, the second sees nothing and no error is raised anywhere. **Observable symptom:** downstream code that "worked in testing" (small data, single consumer) silently processes 0 rows in production once a second consumer or a retry re-reads the same object. Fix: materialize to a list if you need multiple passes, or use `itertools.tee` (see below), or re-derive a fresh generator per consumer via a factory function.

### `itertools`, the ones that actually come up

```python
from itertools import islice, chain, groupby, tee

# islice — slice a generator without indexing (generators don't support gen[3:10])
first_10 = list(islice(big_gen(), 10))
skip_then_take = list(islice(big_gen(), 100, 110))   # skip 100, take 10

# chain — flatten multiple iterables lazily, no intermediate list
for row in chain(file1_rows(), file2_rows(), file3_rows()):
    process(row)

# groupby — REQUIRES pre-sorted input on the key, or it silently "misgroups"
data = [("a", 1), ("b", 2), ("a", 3)]   # NOT sorted by key
for key, group in groupby(data, key=lambda t: t[0]):
    print(key, list(group))
# a [('a', 1)]      <- a fresh group every time the key changes, even back to "a"
# b [('b', 2)]
# a [('a', 3)]
# correct usage: sort first
for key, group in groupby(sorted(data, key=lambda t: t[0]), key=lambda t: t[0]):
    ...

# tee — split one iterator into N independent ones; NOT free
a, b = tee(range(1_000_000), 2)
```

`groupby` groups **consecutive** runs of equal keys, exactly like Unix `uniq`, not "all items with this key" — this is arguably the single most common `itertools` interview trap, because the API looks like a `groupby` from pandas/SQL and behaves nothing like it unless the input is already sorted by that key.

`tee` buffers: if one of the two resulting iterators is consumed faster than the other, `tee` internally queues every element the slow consumer hasn't reached yet, so in the worst case (one branch fully consumed before the other starts) memory cost approaches that of materializing the whole thing as a list — it does **not** give you two free independent passes over an unbounded stream. Use it only when both consumers advance at roughly the same pace.

### Lazy pipeline over a large file

```python
def read_large_log(path):
    with open(path) as f:                 # file object is itself an iterator
        for line in f:                    # reads one line at a time, not the whole file
            yield line.rstrip("\n")

def parse(lines):
    for line in lines:
        ts, level, msg = line.split(" ", 2)
        yield {"ts": ts, "level": level, "msg": msg}

def errors_only(records):
    return (r for r in records if r["level"] == "ERROR")

# nothing has executed yet — this whole chain is O(1) memory until consumed
pipeline = errors_only(parse(read_large_log("app.log")))
for err in pipeline:
    handle(err)          # each line flows through the full pipeline before the next is read
```

Peak memory is one line (plus one record) at a time, regardless of whether the file is 10MB or 100GB, because each stage pulls from the one before it on demand rather than each stage running to completion before the next starts.

---

## Build it from scratch

A minimal hand-rolled generator-equivalent, to show what `yield` compiles away:

```python
class ManualRange:
    """Reimplementation of (x for x in range(n)) without `yield`."""
    def __init__(self, n):
        self.n = n
        self.i = 0

    def __iter__(self):
        return self

    def __next__(self):
        if self.i >= self.n:
            raise StopIteration
        val = self.i
        self.i += 1
        return val

assert list(ManualRange(5)) == list(x for x in range(5))
```

The generator version is exactly this, minus the boilerplate: the compiler stores `self.i`-equivalent state as local variables inside a saved frame, and `StopIteration` is raised automatically when the function returns. Lab: `(lab pending)`.

---

## How it's done in production

**Framework-level laziness that matters day to day:**
- Pandas `pd.read_csv(path, chunksize=100_000)` returns an iterator of DataFrames — a generator-shaped API for exactly the memory reason above.
- SQLAlchemy's `Result.yield_per(n)` and psycopg's server-side cursors stream rows instead of buffering the whole result set client-side.
- `asyncio` async generators (`async def f(): yield x`) are the standard way to stream chunks from a network response without buffering the whole body.

| Symptom | Cause | Fix |
|---|---|---|
| Second call to `list(my_gen)` (or a retry) returns `[]` with no error | Generator already exhausted by an earlier pass | Materialize once and reuse the list, wrap in a factory `def make_gen(): return (...)`, or use `itertools.tee` if consumers run concurrently |
| `RuntimeError: generator raised StopIteration` | A sub-iterator's `StopIteration` leaked out of a generator body (PEP 479, enforced since 3.7) | Catch the sub-iterator's exhaustion explicitly, or use `yield from` which handles it correctly |
| `groupby` produces many tiny groups with repeated keys instead of one group per key | Input wasn't sorted by the grouping key first | `sorted(data, key=key_fn)` before `groupby` |
| Memory spikes unexpectedly when using `tee` | One of the two `tee` branches is far behind the other, so the internal buffer grows to hold everything the slow branch hasn't consumed | Consume both branches at similar rates, or materialize to a list instead if buffering is unavoidable anyway |
| `TypeError: can't send non-None value to a just-started generator` | Called `.send(x)` before priming with `next()` | `next(g)` (or `g.send(None)`) once before the first real `.send()` |
| A `with open(...)` file inside a generator never gets closed | Generator abandoned mid-iteration (e.g. `break`'d out of a `for` loop) without being garbage-collected promptly, or held alive by a reference cycle | Wrap consumption in `contextlib.closing`, or explicitly `.close()` the generator, or use `try/finally` inside it |

---

## Tradeoffs & when NOT to use it

Generators are the wrong choice when you need any of the following, and reaching for one anyway is a real production mistake, not just a style nit:

- **You need `len()`.** A generator can't tell you its length without being consumed. If you need to report progress ("processing item 4 of 10,000") or preallocate a buffer, use a list or `range`.
- **You need random access or slicing by index.** `gen[5]` doesn't work; `islice` only *skips forward*, it can't seek backward or re-read.
- **You need to iterate more than once.** Retries, multi-pass algorithms (two statistics passes over the same data), or passing the same data to two independent consumers all break silently with a plain generator — see the exhaustion trap above.
- **The data is small and the win is imaginary.** For a few thousand items that comfortably fit in memory, a generator buys you nothing and costs you debuggability (`print(list(gen))` for inspection consumes it).
- **You need to sort it.** `sorted()` on a generator works but must fully materialize internally anyway — there is no laziness benefit, and you've hidden the O(n) memory cost from readers who see a generator and assume it's cheap.

---

## Interview questions

### Q1 — What's the difference between an iterator and a generator?
**Testing:** whether you have the precise containment relationship or a hand-wavy "they're basically the same."
**Answer:** An iterator is any object with `__iter__` (returning self) and `__next__` (returning the next value or raising `StopIteration`). A generator is one specific way to produce an iterator: a function with `yield`, or a generator expression. Every generator is an iterator; a hand-written class implementing the protocol, a `zip` object, or a file object are iterators that are not generators.
**Follow-up trap:** *"Is `range(10)` an iterator?"* — no. `range` is an iterable (and a lazy sequence with O(1) `len()` and indexing), but calling `iter()` on it produces a `range_iterator` object, which is the actual iterator. `range` itself lacks `__next__`.

### Q2 — Why would you use a generator instead of a list?
**Testing:** whether you can quantify it rather than just say "memory efficient."
**Answer:** Constant memory regardless of size — a generator over 10M items costs ~200 bytes versus ~350-400MB for a materialized list of 10M ints — plus the ability to start producing output before the whole input is available (streaming). The cost is losing `len()`, indexing, multi-pass iteration, and easy debugging.
**Follow-up trap:** *"Give me a case where a generator is objectively worse."* — anything requiring more than one pass: computing mean and then variance in two separate loops over the same generator silently processes zero items on the second pass. You'd need to either materialize once or restructure into a single pass.

### Q3 — What does `yield` actually do to the function containing it?
**Testing:** whether you understand suspension versus "it's like return."
**Answer:** Any function containing `yield` anywhere in its body becomes a generator function: calling it does not execute any code, it returns a generator object immediately. Execution only happens on `next()`/iteration, running until the next `yield`, at which point the entire frame (locals, instruction pointer) is frozen and returned to the caller, to be resumed exactly there on the next `next()` call.
**Follow-up trap:** *"So does the function run at all if I never call `next()`?"* — no, not a single line, not even code before the first `yield`. This trips people writing generator functions with validation logic at the top expecting it to run eagerly at call time.

### Q4 — What happens if you iterate an already-exhausted generator?
**Testing:** the exhaustion trap, almost always asked as a "spot the bug" snippet.
**Answer:** It raises `StopIteration` immediately on the first `next()`, which a `for` loop or `list()` call interprets as "zero items" — no exception surfaces, no warning. This is silent by design, which is exactly what makes it dangerous: a generator passed to two consumers, or re-read on a retry, produces an empty result for the second reader with no signal anything went wrong.
**Follow-up trap:** *"How do you defend against this in a code review?"* — never pass a generator across a function boundary if it might be consumed twice; either materialize to a list explicitly at the boundary, or pass a zero-argument callable/factory that produces a fresh generator each time it's called.

### Q5 — Explain `yield from` and why it's not just a loop with `yield` in it.
**Testing:** depth beyond "it flattens nested generators."
**Answer:** `yield from sub` delegates fully to `sub`: it forwards every value `sub` yields, forwards `.send()`/`.throw()`/`.close()` calls made on the outer generator straight into `sub`, and captures `sub`'s `return` value as the value of the `yield from` expression itself. A hand-written `for x in sub: yield x` does none of the last two — it silently drops the sub-generator's return value and can't propagate `send`/`throw` into it correctly.
**Follow-up trap:** *"Where does this matter in real code?"* — coroutine-style generator chains (pre-`async`/`await`, and still under the hood of `asyncio`) rely on `yield from` precisely because cancellation (`throw`) and results (`send`, return value) need to travel through every level of delegation transparently.

### Q6 — What's `send()` for, and what happens if I call it on a freshly created generator?
**Testing:** coroutine mechanics, priming.
**Answer:** `send(value)` resumes a suspended generator and makes `value` the result of the paused `yield` expression, letting you push data *into* a running generator rather than only pull data out. Calling `.send(non_none_value)` before the generator has run at least once via `next()` raises `TypeError`, because there's no suspended `yield` expression yet to receive the value — you can only `send(None)` (equivalent to priming with `next()`) on a fresh generator.
**Follow-up trap:** *"Why does Python enforce priming instead of just discarding the first sent value?"* — silently discarding would hide a bug (you think you sent data in, nothing happened) — raising is the more honest failure.

### Q7 — Does `itertools.groupby` group all matching items together, like SQL `GROUP BY`?
**Testing:** the single most common `itertools` trap.
**Answer:** No — it groups **consecutive runs** of equal keys, like Unix `uniq -c`. `groupby([("a",1),("b",2),("a",3)], key=lambda t: t[0])` yields three groups — `a`, `b`, `a` — not two, because the second `"a"` isn't adjacent to the first. It only behaves like SQL `GROUP BY` if you sort by the key first.
**Follow-up trap:** *"Why doesn't groupby just sort internally for you?"* — because that would make it O(n log n) and force full materialization, defeating the point of an iterator-based tool designed to work on unbounded streams; the library trusts you to pre-sort (or to already have sorted/grouped data, e.g. from an `ORDER BY` query) if you want true grouping.

### Q8 — What does `itertools.tee` cost, and when does it stop being "free"?
**Testing:** whether you know tee isn't a free duplication of an iterator.
**Answer:** `tee(it, n)` returns `n` independent iterators over the same source, but under the hood it buffers every element that the slowest of the `n` consumers hasn't reached yet. If one branch is fully consumed before the other starts at all, the buffer grows to hold the entire sequence, i.e. tee's worst case is exactly the memory cost of a materialized list — it doesn't magically give you cheap replay of an unbounded stream.
**Follow-up trap:** *"So when is tee actually the right tool?"* — when the two (or more) consumers advance at roughly the same pace, e.g. computing two different running statistics over the same stream concurrently in a pipeline. If one consumer needs to finish entirely before the other starts, just materialize a list — it's the same memory cost with none of `tee`'s bookkeeping.

### Q9 — When is a generator the *wrong* choice? Give three concrete cases.
**Testing:** the "when NOT to use it" the checklist demands — most candidates only argue for generators.
**Answer:** (1) You need `len()` up front — for progress bars, preallocating buffers, or validating input size before processing. (2) You need random access or to re-iterate — retries, multi-pass statistics, or handing the same data to two independent consumers. (3) The dataset is small enough that materializing costs nothing, and the generator only adds debugging friction (you can't `print()` a generator's contents without consuming it).
**Follow-up trap:** *"What about sorting a generator — is that lazy?"* — no, `sorted()` must see every element before it can emit the first one, so it fully materializes internally regardless of what you pass it; wrapping an eager operation in a generator upstream just hides the memory cost from the next reader of the code.

### Q10 — Write a generator-based pipeline to find the first error in a 50GB log file without loading it into memory.
**Testing:** applied synthesis under a size constraint.
**Answer:**
```python
def read_lines(path):
    with open(path) as f:
        for line in f:
            yield line

def find_first_error(lines):
    for line in lines:
        if "ERROR" in line:
            return line
    return None

first_error = find_first_error(read_lines("huge.log"))
```
Peak memory is one line at a time; the function returns as soon as it finds a match, so on a file where the error is near the top it never reads the rest — a plain `f.readlines()` would have to load the entire file first regardless of where the match is.
**Follow-up trap:** *"What if the file has Windows line endings and mixed encoding?"* — `open(path, encoding="utf-8", errors="replace")` and consider that `for line in f` splits on `\n` (universal newlines mode handles `\r\n` transparently by default in text mode) — but a truly malformed file can still break naive line-based streaming, which is when you'd drop to reading fixed-size byte chunks manually.

### Q11 — What does `close()` do, and why does it matter for resource cleanup?
**Testing:** whether you know generators participate in cleanup, not just production of values.
**Answer:** `.close()` raises `GeneratorExit` at the generator's current suspend point. If the generator has a `finally` block (e.g. wrapping a `with open(...)` or a DB cursor), that cleanup code runs at that moment. CPython calls `.close()` automatically when a generator object is garbage collected, which is why `finally`/`with` inside a generator function reliably runs even if the caller `break`s out of the loop early — but *only* once the generator is actually collected, which in the presence of reference cycles or another live reference may be later than you expect.
**Follow-up trap:** *"So can I rely on GC to always clean up a generator's file handle?"* — not reliably in code you care about; on CPython's refcounting GC it usually happens immediately when the last reference drops, but that's an implementation detail, not a language guarantee (PyPy's GC doesn't collect this promptly). Use `contextlib.closing()` or an explicit `try/finally` around consumption for anything holding a real resource.

### Q12 — Contrast a synchronous generator with an async generator. When do you need the latter?
**Testing:** whether concurrency changes your answer, common at principal level given async-heavy backends.
**Answer:** A sync generator (`def f(): yield x`) suspends only at `yield` and is driven by `next()`; an async generator (`async def f(): yield x`) can also suspend at `await` points inside its body, and is driven by `__anext__` via `async for`. You need the async form specifically when producing each item involves I/O — e.g. streaming paginated results from an API where each page requires an awaited HTTP call between yields — because a sync generator has no way to yield control to the event loop mid-production without blocking it.
**Follow-up trap:** *"Can you `send()` into an async generator?"* — `asend()` is the async equivalent and exists, but it's rare in practice; most async generator usage in production code is one-directional streaming (`async for`), not bidirectional coroutine-style communication.

---

## Red flags that fail you

- Saying "generators and iterators are the same thing."
- Not knowing that a generator can only be iterated once.
- Claiming `itertools.groupby` groups all matching keys regardless of order.
- Writing `sorted(my_generator())` and calling it "still lazy."
- Not knowing why a function with `yield` doesn't execute anything when called.
- Treating `tee` as a free way to replay an unbounded stream.

---

## Cheat card

```
PROTOCOL     __iter__() -> iterator; iterator.__iter__() -> self; __next__() -> value | StopIteration
GENERATOR    a function w/ yield, or (x for x in ...); calling it runs ZERO code, returns object
             every generator IS an iterator; not every iterator is a generator
MEMORY       list of 10M ints ≈ 350-400MB · range(10M) = 48 bytes · gen over 10M ≈ 200 bytes (constant)
EXHAUSTION   one-shot; 2nd full pass over a used-up generator returns [] SILENTLY, no error
yield        expression, not statement; x = yield v -> x is set by caller's .send(x)
send/throw/close   send(v) resumes, v becomes yield's value; must prime w/ next() first or TypeError
             throw(exc) raises exc at suspend point; close() raises GeneratorExit, runs finally blocks
yield from   delegates fully: forwards values + send/throw/close, captures sub-generator's return value
PEP 479      StopIteration leaking from inside a generator body -> RuntimeError (since Python 3.7)
groupby      groups CONSECUTIVE equal keys only, like uniq — sort first or it silently "misgroups"
tee(it, n)   buffers whatever the slowest consumer hasn't read; worst case = cost of a full list
islice       forward-only skip+take on a generator; can't seek backward
WRONG TOOL WHEN   need len() · need random access/slicing · need >1 pass · dataset is small anyway
```

## Sources

- [What's New In Python 3.12 — itertools.batched](https://docs.python.org/3/whatsnew/3.12.html) — accessed 2026-08-01
- [Massive memory overhead: Numbers in Python and how NumPy helps — Python⇒Speed](https://pythonspeed.com/articles/python-integers-memory/) — accessed 2026-08-01
- [itertools — Python 3.14 documentation](https://docs.python.org/3/library/itertools.html) — accessed 2026-08-01
- [PEP 479 – Change StopIteration handling inside generators](https://peps.python.org/pep-0479/) — accessed 2026-08-01

## Changelog
- 2026-08-01 — created
