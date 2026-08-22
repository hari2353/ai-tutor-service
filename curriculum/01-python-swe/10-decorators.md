# Decorators: Function, Class, functools.wraps, Parametrised, Real Uses

> **Track:** T01 Python & SWE Craft · **Time:** 2.0h · **Prereqs:** none · **Updated:** 2026-08-01
> **Module id:** `T01-decorators` · **Tags:** language,critical

## The 30-second version

A decorator is just a higher-order function: `@dec` above `def f(): ...` is exactly `f = dec(f)`, evaluated at *def time*, once, not on every call. Everything else is consequence: because `dec` returns a new callable (usually a closure wrapping the original), the original function's `__name__`, `__doc__`, and `__wrapped__` are lost unless you copy them back with `functools.wraps`, which also matters for introspection tools (`inspect.signature`, FastAPI's dependency injection, pytest fixture matching) and for pickling. Parametrised decorators just add a third level of nesting — `@dec(arg)` calls `dec(arg)` first to produce the actual decorator, which is then applied to the function — and stacked decorators apply bottom-up but execute outside-in, which is exactly the order that trips people writing `@app.route` + `@login_required` in the wrong sequence.

## Why this gets asked

Because decorators are used constantly (routing, auth, caching, retry, logging) but rarely built by hand, so most engineers can *use* `@lru_cache` without being able to explain why a decorated function's `__name__` says the wrapper's name instead of the original's, why that breaks pytest test discovery or a debugger's stack trace, or why `@lru_cache` on an instance method is a documented memory-leak footgun. The interviewer has debugged a production incident caused by exactly one of these: a decorator that silently changed a function's signature and broke a framework's introspection, or an `lru_cache`-wrapped method that kept every request object alive for the life of the process.

---

## Lineage: past → present → future

**What came before.** Before PEP 318 (2003, shipped in Python 2.4), the pattern existed but required manual reassignment: `def f(): ...` then `f = synchronized(my_lock)(f)` on the line after, which worked identically but buried the wrapping far from the definition and was easy to miss in review. The `@` syntax didn't add new semantics, it just moved an existing idiom (already common in Java annotations and Zope) to the point of definition, which is purely ergonomic but turned out to matter enormously for readability and adoption. `classmethod` and `staticmethod` existed as plain functions you called manually years before `@` syntax made them decorators; `property` followed the same path.

**Where it stands now.** Decorators are the standard extension point for cross-cutting concerns across the ecosystem: Flask/FastAPI routing, `pytest.fixture`/`pytest.mark`, `dataclasses.dataclass`, `click` CLI commands, SQLAlchemy's declarative mappings, and every retry/cache/timing library. The live disagreement is about decorators versus alternatives for the same job: `functools.singledispatch` versus a decorator-based registry pattern for dispatch, and decorators versus explicit dependency injection for things like DB sessions — decorators are terser but hide control flow (a decorated function's actual call graph isn't visible at the call site), while explicit passing is more verbose but greppable and type-checker-friendly. Type checkers (mypy, pyright) have converged on `ParamSpec` (PEP 612, Python 3.10) specifically to let a decorator preserve the wrapped function's exact parameter types, which used to be a real gap — untyped decorators silently erased argument types for years.

**Where it's heading.** Nothing structural is changing in the decorator mechanism itself; the ongoing work is entirely about typing fidelity (`ParamSpec`, `Concatenate` for decorators that inject an argument) and static-analysis tooling catching decorator misuse (Ruff's `B019` flags `lru_cache`/`cache` on instance methods specifically because of the reference-leak pattern). Expect decorators to stay exactly as they are syntactically, with the surrounding tooling continuing to close the gap between "decorators are dynamic and erase static information" and "type checkers need to see through them."

---

## Mental model

```
@dec
def f(x):
    return x

# is EXACTLY:

def f(x):
    return x
f = dec(f)          # runs ONCE, at def time (module import time), not per call
```

Nesting for a parametrised decorator — three layers, read from the inside out:

```
@dec(arg)
def f(): ...

# is:
f = dec(arg)(f)
      │       │
      │       └─ dec(arg) must return something CALLABLE — the real decorator
      └───────── dec(arg) itself runs at def time, producing that decorator
```

```
def dec(arg):              # layer 1: takes the decorator's own arguments
    def actual_decorator(func):    # layer 2: takes the function being decorated
        def wrapper(*a, **kw):     # layer 3: replaces calls to the function
            ...
            return func(*a, **kw)
        return wrapper
    return actual_decorator
```

Stacking order:
```
@a
@b
def f(): ...
# is f = a(b(f))  — b applies FIRST (closest to the function), a wraps around it
# but at CALL time, execution order is OUTSIDE-IN: a's wrapper code runs first,
# then it calls into b's wrapper, which finally calls the real f.
```

---

## How it actually works

### The closure-based decorator, from zero

```python
import time
import functools

def timed(func):
    @functools.wraps(func)          # copies __name__, __doc__, __wrapped__, etc.
    def wrapper(*args, **kwargs):
        start = time.perf_counter()
        try:
            return func(*args, **kwargs)
        finally:
            elapsed = (time.perf_counter() - start) * 1000
            print(f"{func.__name__} took {elapsed:.2f}ms")
    return wrapper

@timed
def slow_query(n):
    """Runs a fake slow query."""
    time.sleep(n)

slow_query(0.1)              # prints "slow_query took 100.xxms"
```

`func` is captured in `wrapper`'s closure — this is the entire mechanism, no special language feature beyond "inner functions close over enclosing-scope variables."

### Why `functools.wraps` matters — the observable symptom

Without it:

```python
def timed(func):
    def wrapper(*args, **kwargs):
        return func(*args, **kwargs)
    return wrapper

@timed
def slow_query(n):
    """Runs a fake slow query."""
    ...

print(slow_query.__name__)   # 'wrapper'  <-- not 'slow_query'
print(slow_query.__doc__)    # None       <-- docstring gone
```

This isn't cosmetic. Concretely:
- **Debugging/logging**: stack traces and log lines that print `func.__name__` now all say `wrapper`, so an error log from three different decorated endpoints is indistinguishable.
- **Introspection-driven frameworks break**: `pytest` fixture matching, Click's command names, and any framework that reads `__name__` to register a route or a CLI command (`@app.route("/x")` under the hood keying off the function object, but logging/monitoring tools keyed off `__name__` misreport everything) will misbehave or collide — two different decorated functions both reporting as `wrapper` can collide in a dict keyed by name.
- **Pickling breaks**: `pickle.dumps(slow_query)` fails or pickles the wrong thing, because pickling a function by reference looks it up by `__module__` + `__qualname__`; if those aren't preserved, `pickle.loads` can't find `wrapper` back at its original location, or worse, silently resolves the wrong object if some other `wrapper` exists at that name in a different module scope re-used by another decorator.
- `functools.wraps` also sets `__wrapped__ = func`, which `inspect.signature()` and `inspect.unwrap()` use to see through the decorator to the real signature — without it, `inspect.signature(slow_query)` reports `(*args, **kwargs)` instead of `(n)`, which breaks any tool doing runtime signature validation (FastAPI's dependency resolution is the highest-profile real-world example: FastAPI reads a route function's signature to know what to inject, and an unwrapped decorator on a route handler silently breaks parameter injection).

### Parametrised decorators, worked example: retry

```python
import functools
import time

def retry(times=3, exceptions=(Exception,), backoff=0.5):
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            last_exc = None
            for attempt in range(times):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exc = e
                    time.sleep(backoff * (2 ** attempt))
            raise last_exc
        return wrapper
    return decorator

@retry(times=3, exceptions=(ConnectionError,))
def call_flaky_service():
    ...
```

Note `retry(times=3, ...)` runs immediately at def time and returns `decorator`, which is then applied to `call_flaky_service` — the `times`/`exceptions`/`backoff` values are closed over by `decorator` and, transitively, by `wrapper`.

**Making it work with or without arguments** (`@retry` and `@retry()` both valid) requires detecting whether the first positional argument is the function itself:

```python
def retry(func=None, *, times=3):
    if func is None:
        return lambda f: retry(f, times=times)
    @functools.wraps(func)
    def wrapper(*a, **kw):
        ...
    return wrapper
```

### Class decorators vs decorating classes — two different things

**A decorator applied to a class** (still a function receiving a class object and returning one):

```python
def register(cls):
    REGISTRY[cls.__name__] = cls
    return cls

REGISTRY = {}

@register
class Handler:
    ...
```

**A class *used as* a decorator** (implements `__call__`, decorates functions):

```python
class CountCalls:
    def __init__(self, func):
        functools.update_wrapper(self, func)   # class equivalent of functools.wraps
        self.func = func
        self.count = 0

    def __call__(self, *args, **kwargs):
        self.count += 1
        return self.func(*args, **kwargs)

@CountCalls
def greet():
    print("hi")

greet(); greet()
print(greet.count)   # 2
```

Class-based decorators are useful when the decorator needs to hold non-trivial state or expose extra methods (`.count`, `.reset()`) beyond just wrapping calls — a closure can hold state too (via `nonlocal` or a mutable default), but exposing it cleanly to the caller is awkward.

### `functools.lru_cache` / `cache` — the two traps

**Trap 1: unhashable / mutable arguments.**
```python
from functools import lru_cache

@lru_cache
def process(items: list): ...   # TypeError: unhashable type: 'list'
```
The cache key is built from the arguments via hashing, so mutable containers (`list`, `dict`, `set`) can't be arguments at all. This is a feature, not a bug to work around by hashing contents yourself: a genuinely mutable argument being used as a cache key is a correctness bug waiting to happen, because a cached result for `[1, 2, 3]` would silently stay valid even if that same list object were mutated in place elsewhere.

**Trap 2: memory leak on instance methods.**
```python
class Model:
    @lru_cache(maxsize=None)
    def predict(self, x):
        ...
```
The cache is attached to the *function object* (shared across all instances, since methods are just functions looked up on the class), and its keys include `self`. Every `Model` instance that ever calls `.predict()` is kept alive forever by the cache's internal reference to it as part of the key — instances become uncollectable for the lifetime of the process, because the cache holding a reference to `self` prevents refcount from ever reaching zero. This is exactly what Ruff's `B019` rule (`cached-instance-method`) flags. [cached-instance-method (B019) — Ruff docs](https://docs.astral.sh/ruff/rules/cached-instance-method/) — accessed 2026-08-01. Fix: use `functools.cached_property` for a single per-instance value, cache on a module-level function that doesn't take `self`, or store a private cache dict directly on the instance so it's garbage collected along with it.

### `property`, `staticmethod`, `classmethod`

```python
class Circle:
    def __init__(self, r):
        self._r = r

    @property
    def area(self):                    # computed attribute, accessed w/o ()
        return 3.14159 * self._r ** 2

    @staticmethod
    def unit():                        # no self, no cls — just namespaced
        return Circle(1)

    @classmethod
    def from_diameter(cls, d):         # receives the class, not an instance
        return cls(d / 2)
```

`staticmethod` takes neither `self` nor `cls` — it's a plain function that happens to live in the class's namespace, useful for a helper that's conceptually related but needs no instance or class state. `classmethod` receives `cls`, which is what makes alternate-constructor patterns (`from_diameter`) work correctly under inheritance — `cls` is the *actual* subclass the method was called on, not hardcoded to `Circle`.

### Stacking order

```python
@app.route("/x")
@login_required
def handler(): ...

# equivalent to: handler = app.route("/x")(login_required(handler))
```
`login_required` wraps `handler` first (innermost/closest), then `app.route` wraps the result. At request time, `app.route`'s wrapper (outermost) runs first — meaning routing/dispatch happens before the auth check executes, which is usually fine, but reversing the stack order (`login_required` on top) would mean the framework never even sees the route registered correctly if `login_required`'s wrapper doesn't preserve what `app.route` needs to introspect. Getting stacking order backwards is a real, easy-to-make bug: decorators that must run first (validation, auth) belong closer to the function; decorators that need the final, fully-wrapped behavior (metrics around the whole call including auth) belong on top.

### Decorators that break signatures and type checkers

```python
def logged(func):
    def wrapper(*args, **kwargs):     # signature erased to (*args, **kwargs)
        return func(*args, **kwargs)
    return wrapper

@logged
def add(x: int, y: int) -> int:
    return x + y

add("a", "b")   # mypy: no error! wrapper's signature is (*args, **kwargs) -> Any
```
Without `ParamSpec`, a decorator that doesn't specifically preserve types loses the wrapped function's signature for static analysis, even with `functools.wraps` applied (`wraps` fixes runtime introspection, not static types). The fix uses `ParamSpec` and `TypeVar`:
```python
from typing import ParamSpec, TypeVar, Callable
P = ParamSpec("P")
R = TypeVar("R")

def logged(func: Callable[P, R]) -> Callable[P, R]:
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
        return func(*args, **kwargs)
    return wrapper
```
Now mypy correctly flags `add("a", "b")`.

---

## Build it from scratch

Minimal auth decorator with parametrisation and correct `wraps` usage — a realistic interview whiteboard ask:

```python
import functools

class Unauthorized(Exception): ...

def require_role(role):
    def decorator(func):
        @functools.wraps(func)
        def wrapper(user, *args, **kwargs):
            if role not in user.roles:
                raise Unauthorized(f"{user} lacks role {role!r}")
            return func(user, *args, **kwargs)
        return wrapper
    return decorator

class User:
    def __init__(self, name, roles):
        self.name, self.roles = name, roles
    def __str__(self):
        return self.name

@require_role("admin")
def delete_account(user, account_id):
    print(f"{user} deleted {account_id}")

admin = User("alice", {"admin"})
guest = User("bob", set())
delete_account(admin, 42)          # works
delete_account(guest, 42)          # raises Unauthorized
```

Lab: `labs/py/10-decorators/`.

---

## How it's done in production

| Real use | Library | What it adds over hand-rolled |
|---|---|---|
| Retry | `tenacity` | Configurable backoff strategies, jitter, retry-on-exception-type or -result-predicate, async support |
| Caching | `functools.lru_cache`/`cache`, `cachetools` | TTL eviction, size-bounded LRU, thread-safety (`cachetools` adds these; stdlib `lru_cache` has none) |
| Timing/metrics | `opentelemetry`'s `@tracer.start_as_current_span` | Distributed trace context propagation, not just local `time.perf_counter()` |
| Auth | Framework-native (`FastAPI` `Depends`, `Flask-Login`'s `@login_required`) | Integration with the request/session lifecycle, not just a bare exception |
| Registration | `click.command`, `pytest.fixture`, `dataclasses.dataclass` | Ties into a discovery/collection mechanism (CLI parser, test collector, `__init__` generation) |

| Symptom | Cause | Fix |
|---|---|---|
| `func.__name__` prints `wrapper` in logs; stack traces show the wrong function name | Missing `functools.wraps` | Add `@functools.wraps(func)` to the inner wrapper |
| `pickle.dumps(decorated_func)` fails or resolves to the wrong object | Wrapper's `__module__`/`__qualname__` don't match the original | `functools.wraps` restores these |
| FastAPI/pydantic route stops receiving injected params correctly after adding a decorator | Decorator erased the real signature; framework does runtime introspection via `inspect.signature` | Use `functools.wraps` (sets `__wrapped__`, which `inspect.signature` follows) or preserve the signature explicitly |
| Instances of a class never get garbage collected; memory grows unbounded over the process lifetime | `@lru_cache`/`@cache` applied directly to an instance method, keeping `self` alive in cache keys forever | `functools.cached_property` for one cached value per instance, or cache on a standalone function taking only hashable, non-instance arguments |
| `TypeError: unhashable type: 'list'` on a cached function | Mutable argument passed to an `lru_cache`d function | Convert to a hashable type (`tuple`, frozenset) at the call site, or don't cache that argument shape |
| mypy passes obviously wrong argument types to a decorated function with no error | Decorator's inner `wrapper(*args, **kwargs)` erased the real parameter types | Type the decorator with `ParamSpec`/`TypeVar` instead of bare `*args, **kwargs` |
| Auth check never runs even though `@login_required` is present | Stacking order backwards relative to the framework's routing decorator | Innermost decorator (closest to `def`) runs first at call time from outside-in — verify which decorator needs to see the raw function vs. the already-wrapped one |

---

## Tradeoffs & when NOT to use it

- **Decorators hide control flow.** Reading `def handler(): ...` at a glance doesn't show you that three decorators run first — for complex cross-cutting logic (multi-step validation with branching), explicit calls in the function body are more debuggable than a stack of decorators whose interaction order matters.
- **Don't decorate for one-off behavior.** If a wrapper is used exactly once, inlining the logic is clearer than defining, naming, and applying a decorator that adds a layer of indirection for no reuse benefit.
- **Avoid decorators that mutate arguments or return different types depending on runtime state** in ways not visible from the decorator's name — `@maybe_cache` that sometimes returns a cached stale object and sometimes a fresh one, silently, based on some global flag, is a debugging nightmare.
- **`lru_cache` is the wrong tool for anything needing eviction by time, not just by LRU order, or thread-safe mutation of the cache from multiple threads under high contention** — reach for `cachetools.TTLCache` or an external cache (Redis) instead.
- **Stacking many decorators degrades traceback readability and can hurt performance** — each layer is a Python function call; a hot path decorated five deep (logging, timing, retry, auth, tracing) adds real per-call overhead (each wrapper frame is on the order of 50-100ns of pure call overhead in CPython, which compounds if the underlying function itself is cheap and called millions of times) — profile before stacking decorators onto a genuinely hot inner loop.

---

## Interview questions

### Q1 — What does `@dec` above a function definition actually do?
**Testing:** the mechanical baseline.
**Answer:** `@dec\ndef f(): ...` is exactly `def f(): ...` followed by `f = dec(f)`, executed once at definition time (module import), not per call. `dec` must return something callable, which replaces the name `f` in the enclosing scope.
**Follow-up trap:** *"So does the original `f` still exist anywhere?"* — only if `dec`'s returned wrapper holds a reference to it (typically as a closure variable), which is exactly what `functools.wraps` exposes via `__wrapped__`.

### Q2 — Why does `functools.wraps` matter, concretely — what breaks without it?
**Testing:** whether you can name observable symptoms, not just "it copies metadata."
**Answer:** Without it, `__name__` and `__doc__` become the wrapper's, not the original's — logs and stack traces show `wrapper` for every decorated function, `inspect.signature()` reports `(*args, **kwargs)` instead of the real parameters (breaking frameworks like FastAPI that introspect signatures for dependency injection), and `pickle` can fail or resolve to the wrong object because `__module__`/`__qualname__` no longer point at the real function's location.
**Follow-up trap:** *"Does `functools.wraps` fix the mypy signature-erasure problem too?"* — no. `wraps` only fixes runtime introspection; static type checkers need `ParamSpec`/`TypeVar` on the wrapper's own signature, which `wraps` does not provide.

### Q3 — Explain the three levels of nesting in a parametrised decorator.
**Testing:** whether the `@dec(arg)` case is understood as a distinct mechanism from plain `@dec`.
**Answer:** `@dec(arg)` means `dec(arg)` is called first, at def time, and must itself return the *actual* decorator (a callable taking the function). That decorator then wraps the function in a third, innermost function (the `wrapper`) that runs on every call. So there are three functions: the outer factory (`dec`), the middle decorator (`dec`'s return value), and the innermost wrapper (what actually replaces calls to `f`).
**Follow-up trap:** *"How do you support both `@retry` and `@retry()` on the same decorator?"* — detect whether the first positional argument is the function itself (`func=None` sentinel pattern) and branch: if it's the function, decorate immediately; if not, return a `lambda f: retry(f, **kwargs)`.

### Q4 — What's wrong with putting `@lru_cache` on an instance method?
**Testing:** the memory-leak trap, high-signal because it's subtle and real.
**Answer:** The cache lives on the function object shared by the class, and its keys include `self`, so every instance that ever calls the cached method is kept referenced by the cache for the life of the process — instances become uncollectable garbage even after all your own references to them are gone. Ruff flags this as `B019`.
**Follow-up trap:** *"What's the fix if I need per-instance memoization of one value?"* — `functools.cached_property`, which stores the cached value directly in the instance's `__dict__`, so it's garbage collected along with the instance rather than living in a class-level structure.

### Q5 — Why does `@lru_cache` raise `TypeError: unhashable type: 'list'` if you pass a list argument?
**Testing:** understanding the cache-key mechanism, not just memorizing the error.
**Answer:** The cache builds its key from the function's arguments via hashing (roughly, a tuple of the args), and `list`/`dict`/`set` aren't hashable. This is deliberate: a mutable argument used as a cache key would be a correctness hazard even if it could be hashed, because mutating the object after caching wouldn't invalidate the stale cached result.
**Follow-up trap:** *"How would you cache a function that takes a list?"* — convert to an immutable form at the call boundary (`tuple(items)`), or, if the list represents a genuinely mutable/streaming input, don't cache on it at all — cache on a derived hashable key like a content hash if repeats are common.

### Q6 — What order do stacked decorators apply in, and what order do they execute in at call time?
**Testing:** the classic gotcha, phrased two ways in the same question to catch people who only memorized one direction.
**Answer:** `@a` above `@b` above `def f` builds `f = a(b(f))` — `b` is applied first (closest to the function). But at *call* time, execution is outside-in: `a`'s wrapper code runs first (since it's now the outermost callable), and it calls into `b`'s wrapper, which finally calls the real `f`.
**Follow-up trap:** *"Given `@app.route(...)` above `@login_required`, does the auth check happen before or after the framework's routing logic runs?"* — the framework's routing wrapper (outermost, applied last, "on top") runs first at call time, then calls into `login_required`'s wrapper. Whether that's correct depends on what each decorator needs to see — a common real bug is a metrics/timing decorator placed *inside* an auth decorator when it was meant to time the whole request including the auth check.

### Q7 — Difference between `staticmethod`, `classmethod`, and a plain instance method?
**Answer:** An instance method receives `self` (the instance) automatically as the first argument. `classmethod` receives `cls` (the class the method was actually called on, respecting subclassing) instead of an instance — used for alternate constructors. `staticmethod` receives neither; it's a plain function namespaced under the class for organizational purposes only.
**Follow-up trap:** *"Why does `classmethod` matter for inheritance in a way `staticmethod` doesn't?"* — `cls` in a classmethod is resolved dynamically to the actual subclass at call time (`Subclass.from_x(...)` gets `cls=Subclass`), so alternate constructors written on a base class correctly construct subclass instances when called via the subclass. A `staticmethod` referencing the base class by name hardcodes it and breaks this.

### Q8 — Write a decorator that only logs a function's arguments and return value if a module-level DEBUG flag is True, without adding overhead when it's False.
**Testing:** applied synthesis plus awareness of overhead.
**Answer:**
```python
DEBUG = False

def debug_log(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        if not DEBUG:
            return func(*args, **kwargs)
        result = func(*args, **kwargs)
        print(f"{func.__name__}({args!r}, {kwargs!r}) -> {result!r}")
        return result
    return wrapper
```
**Follow-up trap:** *"This still pays a wrapper-call overhead even when DEBUG is False. How would you avoid that entirely?"* — decorate conditionally at definition time: `f = debug_log(f) if DEBUG else f`, so when DEBUG is off there's no wrapper at all, at the cost of DEBUG needing to be known at import time rather than toggleable at runtime.

### Q9 — Your decorator wraps a function and calls it with `*args, **kwargs`. A type checker doesn't catch a caller passing the wrong argument types. Why, and how do you fix it?
**Testing:** typing depth beyond `functools.wraps`.
**Answer:** `wrapper(*args, **kwargs)` has an erased signature `(*Any, **Any) -> Any` from the type checker's point of view; `functools.wraps` only fixes runtime `__name__`/`__doc__`/`inspect.signature`, not the static type of `wrapper` itself. Fix with `ParamSpec` (`P = ParamSpec("P")`) and type the wrapper as `Callable[P, R]`, typing `*args: P.args, **kwargs: P.kwargs`.
**Follow-up trap:** *"Does this work for a decorator that changes the return type (e.g. wraps the result in a Result[T] type)?"* — yes, but then the wrapper's return annotation should be `Result[R]`, not `R`; `ParamSpec` only needs to match the parameters, the return type is a separate `TypeVar` you control independently.

### Q10 — Class decorator vs. a class used as a decorator — what's the difference?
**Testing:** terminology precision that's easy to conflate.
**Answer:** A class decorator is a function applied to a class (`@register` above `class Handler`), receiving and returning a class object — used for registration patterns. A class *used as* a decorator implements `__call__` and is applied to a function, becoming the replacement callable — useful when the decorator needs to hold and expose state (a call counter, an internal cache with methods) beyond a plain closure.
**Follow-up trap:** *"Can a class-based decorator support being used on methods, not just plain functions?"* — this is the descriptor-protocol trap: a class instance used as a decorator doesn't automatically become a bound method when accessed via an instance, because it isn't itself a function (which implements `__get__`). You need to implement `__get__` on the decorator class yourself to make it behave correctly as a method.

### Q11 — Give three real production uses of decorators and what each buys you over writing the logic inline every time.
**Answer:** Retry (`tenacity`) centralizes backoff/jitter policy so every call site doesn't reimplement it inconsistently. Auth (`@login_required`, FastAPI `Depends`) keeps access control declarative and auditable at a glance rather than buried in `if` statements per handler. Registration (`@app.route`, `pytest.fixture`, `click.command`) turns "define this thing" into "define and simultaneously register this thing with a framework," removing a whole class of "I forgot to register the handler" bugs.
**Follow-up trap:** *"When would you NOT use a decorator for auth?"* — when the authorization logic depends on data only available deep inside the function body (e.g., a row-level check that requires a DB read the function itself performs), a blanket decorator applied at the function boundary can't express it cleanly — that belongs as an explicit check inline, or as a dependency injected into the function rather than wrapped around it.

### Q12 — A decorated function suddenly can't be pickled after adding a decorator, breaking a multiprocessing job. Diagnose it.
**Testing:** staff-level, ties decorators to a real infra failure mode (multiprocessing needs pickling).
**Answer:** Two likely causes: (1) missing `functools.wraps`, so the function's `__module__`/`__qualname__` point at `wrapper` instead of the original, and pickle's by-reference lookup can't resolve it correctly at unpickling time in the worker process; (2) the decorator wraps the function in a closure that captures something unpicklable (a lock, an open file, a lambda) — closures themselves are generally unpicklable regardless of `wraps`, since `pickle` for functions works by reference (module + qualname), not by serializing the closure's contents, so a *locally defined* wrapper function (as opposed to one at module scope) is often the real, harder-to-spot culprit in a multiprocessing context.
**Follow-up trap:** *"So does `functools.wraps` make any decorated function picklable?"* — no. It fixes the by-reference lookup for functions decorated with a `wraps`-using decorator that still resolves to a real module-level name; it does nothing for genuinely local/nested functions or for decorators that replace the function with a class instance holding unpicklable state.

---

## Red flags that fail you

- Not knowing `@dec` is just `f = dec(f)` at def time.
- Saying `functools.wraps` is "just cosmetic."
- Not recognizing `@lru_cache` on an instance method as a memory-leak pattern.
- Getting stacking order backwards and not noticing when asked to trace it.
- Confusing `staticmethod` and `classmethod`.
- Claiming a decorated function's static type is automatically preserved just because `functools.wraps` was used.

---

## Cheat card

```
MECHANISM     @dec above def f(): ... == f = dec(f), runs ONCE at def time
PARAMETRISED  @dec(arg) above def f(): ... == f = dec(arg)(f)  — 3 nested functions
STACKING      @a \n @b \n def f == f = a(b(f)); b applies first, but a's wrapper RUNS FIRST at call time
wraps         functools.wraps(func) on the inner wrapper — copies __name__/__doc__, sets __wrapped__
  WITHOUT IT: __name__ says 'wrapper' in logs/tracebacks; inspect.signature() shows (*args,**kwargs);
              FastAPI-style signature-based DI breaks; pickle can fail or resolve wrong object
lru_cache trap 1   unhashable arg (list/dict/set) -> TypeError
lru_cache trap 2   on an instance method -> self kept alive forever in cache key -> instances never GC'd
                   fix: functools.cached_property, or cache a standalone fn w/o self
property/staticmethod/classmethod   property=computed attr, no (); staticmethod=no self/cls;
                                     classmethod=receives cls (respects subclass), for alt constructors
TYPING        bare *args,**kwargs erases signature for type checkers even w/ wraps
              fix: ParamSpec P + Callable[P, R], type wrapper as (*args: P.args, **kwargs: P.kwargs) -> R
CLASS DECORATOR vs CLASS-AS-DECORATOR   @register on a class (fn->class) vs a class w/ __call__ (fn wrapper w/ state)
REAL USES     retry (tenacity), cache (lru_cache/cachetools), auth (login_required/Depends),
              timing (perf_counter/OTel spans), registration (route/fixture/command)
OVERHEAD      each wrapper layer ~ real per-call cost; don't stack 5 deep on a hot inner loop w/o profiling
```

## Sources

- [PEP 318 – Decorators for Functions and Methods](https://peps.python.org/pep-0318/) — accessed 2026-08-01
- [PEP 612 – Parameter Specification Variables (ParamSpec)](https://peps.python.org/pep-0612/) — accessed 2026-08-01
- [cached-instance-method (B019) — Ruff Docs](https://docs.astral.sh/ruff/rules/cached-instance-method/) — accessed 2026-08-01
- [Don't wrap instance methods with functools.lru_cache — Redowan's Reflections](https://rednafi.com/python/lru-cache-on-methods/) — accessed 2026-08-01
- [functools — Python 3.14 documentation](https://docs.python.org/3/library/functools.html) — accessed 2026-08-01

## Changelog
- 2026-08-01 — created
