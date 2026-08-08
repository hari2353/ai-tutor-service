# LEGB Scoping, Closures, Late Binding, global/nonlocal

> **Track:** T01 Python & SWE Craft · **Time:** 1.5h · **Prereqs:** none · **Updated:** 2026-08-01
> **Module id:** `T01-scoping-closures` · **Tags:** language

## The 30-second version

Python resolves a name by walking four scopes in order — Local, Enclosing, Global, Built-in (LEGB) — and it decides which scope a name belongs to *statically*, at compile time, by scanning the function body for any assignment to that name; if the compiler sees an assignment anywhere in the function, that name is local for the *entire* function body, even before the assignment line, which is exactly why `UnboundLocalError` happens on a variable that looks like it should read a global just fine. Closures capture variables by reference to the enclosing scope's cell, not by value at closure-creation time, which is why `[lambda: i for i in range(3)]` produces three closures that all print `2` — they all look up the same cell `i`, and by the time any of them are called, the loop has finished and `i` is `2`. `global` and `nonlocal` exist purely to override the compiler's default "assignment makes it local" behavior, telling it to bind the name in the module scope or the nearest enclosing function scope instead.

## Why this gets asked

Because the late-binding closure trap is the most common real bug in this category — it silently produces wrong results with no exception, typically inside a loop building callbacks, event handlers, or worker functions for a thread pool — and the interviewer has spent an afternoon debugging exactly this in a list of closures that should have captured five different values but all captured the same one. They're also checking whether you understand that Python's scoping decision is made by *reading the source*, not by watching execution, because that's the piece that explains `UnboundLocalError` and makes "just use `global`" advice from panicked juniors make sense.

---

## Lineage: past → present → future

**What came before.** Python's scoping was always lexical (determined by where code is written, not by the call stack, unlike some older dynamically-scoped languages), but the language grew stricter about it over time. Python 2 had no `nonlocal` at all — modifying an enclosing (non-global) function's variable from a nested function required a workaround, usually a mutable single-element list or a dict used purely as a mutable box (`counter = [0]; counter[0] += 1`), because assignment to a bare name always created a new local. PEP 3104 (2006) added `nonlocal` for Python 3, closing that gap and making closures that mutate enclosing state straightforward to write correctly for the first time.

**Where it stands now.** LEGB with `global`/`nonlocal` is stable and hasn't meaningfully changed since Python 3.0. The one recent wrinkle is PEP 709 (Python 3.12), which changed comprehensions to be *inlined* into the enclosing scope's frame rather than compiled as a genuinely separate hidden function call — a real performance win (comprehensions got measurably faster, since a full function call and frame creation used to happen for every comprehension) with a scoping consequence: comprehension internals became slightly more visible in tracebacks and to some introspection, though the *scoping rules themselves* (a comprehension's loop variable does not leak into the enclosing scope, unlike Python 2's list comprehensions) were preserved by design, not changed. [What's New In Python 3.12 — PEP 709](https://docs.python.org/3/whatsnew/3.12.html) — accessed 2026-08-01. The live disagreement in practice isn't about the rules (everyone agrees what LEGB does) but about idiom: whether the "default argument trick" (`def f(x, i=i): return i`) or an explicit `functools.partial` is the more readable fix for the late-binding trap — both are common in real codebases.

**Where it's heading.** No change to the scoping model itself is on the table; free-threaded CPython (3.13+, PEP 703) changes *concurrency* semantics around shared mutable state across threads, but not the LEGB name-resolution rules, which remain purely about lexical structure. Expect continued small interpreter-level optimizations (like PEP 709) that speed up scope resolution without altering its observable behavior.

---

## Mental model

```
 ┌─────────────────────────────────────────────┐
 │ BUILT-IN     len, range, print, ...          │
 │ ┌───────────────────────────────────────────┐│
 │ │ GLOBAL      module-level names             ││
 │ │ ┌─────────────────────────────────────────┐││
 │ │ │ ENCLOSING   names in an outer function   │││
 │ │ │ ┌───────────────────────────────────────┐│││
 │ │ │ │ LOCAL     names assigned in THIS func ││││
 │ │ │ └───────────────────────────────────────┘│││
 │ │ └─────────────────────────────────────────┘││
 │ └───────────────────────────────────────────┘│
 └─────────────────────────────────────────────┘
   lookup walks INWARD-OUT: L -> E -> G -> B, stops at first match
```

**The critical, non-obvious rule:** which scope a name belongs to is decided by the compiler scanning the *entire function body* for assignments to that name, before a single line executes. It is not "reads look outward until a write happens." If there is *any* assignment to `x` anywhere in the function, `x` is local for the whole function, full stop — including on lines textually before that assignment.

---

## How it actually works

### LEGB lookup, straightforward case

```python
x = "global"

def outer():
    x = "enclosing"
    def inner():
        print(x)     # not found locally -> found in ENCLOSING -> "enclosing"
    inner()

outer()
```

### The `UnboundLocalError` trap — assignment makes it local for the WHOLE function

```python
counter = 0

def increment():
    print(counter)      # UnboundLocalError, NOT "global"!
    counter += 1         # this line is why: it's an assignment to `counter`

increment()
```

`counter += 1` is `counter = counter + 1` — an assignment. The compiler sees an assignment to `counter` anywhere in `increment`'s body and marks `counter` local for the entire function, including the `print(counter)` line above it, which now tries to read a local that hasn't been assigned yet. This is a compile-time, static decision — the interpreter never "looks outward first, then decides" at runtime.

Fix with `global`:
```python
counter = 0

def increment():
    global counter
    print(counter)
    counter += 1
```
`global counter` tells the compiler "don't treat assignments to `counter` in this function as creating a local — bind them to the module scope instead." Now the whole function reads and writes the module-level `counter`.

### `nonlocal` — the enclosing-scope equivalent

```python
def make_counter():
    count = 0
    def increment():
        nonlocal count      # without this: UnboundLocalError on count += 1
        count += 1
        return count
    return increment

c = make_counter()
print(c(), c(), c())   # 1 2 3
```
`nonlocal` binds to the nearest *enclosing function* scope (not global) that already has that name — it will not create a new binding, and using `nonlocal x` where no enclosing function scope defines `x` is a `SyntaxError` at compile time, not a runtime error.

### The late-binding closure trap — the canonical version

```python
funcs = [lambda: i for i in range(3)]
print([f() for f in funcs])   # [2, 2, 2] -- NOT [0, 1, 2]
```

**Why:** a closure captures the *variable* (technically, a reference to the enclosing scope's cell object), not the value at the moment the lambda is created. All three lambdas share the same `i` cell, because `i` is a single loop variable reused across iterations, not a fresh binding per iteration. By the time any lambda is *called*, the loop has already finished and `i` holds its final value, `2`.

**Fix 1 — default argument trick**, which works because default argument values *are* evaluated once, at function-definition time, capturing the current value immediately rather than referencing the cell later:
```python
funcs = [lambda i=i: i for i in range(3)]
print([f() for f in funcs])   # [0, 1, 2]
```

**Fix 2 — a factory function** that creates a genuinely new scope (and thus a new cell) per call:
```python
def make_lambda(i):
    return lambda: i

funcs = [make_lambda(i) for i in range(3)]
print([f() for f in funcs])   # [0, 1, 2]
```

`functools.partial(lambda x: x, i)` is a third common variant of the same fix — bind the value as an argument at creation time rather than reading a shared enclosing variable later.

### Mutable default arguments — the same root cause, a different symptom

```python
def append_item(item, bucket=[]):    # evaluated ONCE, at def time
    bucket.append(item)
    return bucket

print(append_item(1))   # [1]
print(append_item(2))   # [1, 2]  <-- same list object reused across calls!
```
Default argument values are evaluated exactly once, when the `def` statement executes, and the resulting object is stored on the function object itself (`append_item.__defaults__`). Every call that doesn't override `bucket` shares that *same* list object across all calls, forever, for the life of the function object. This is the same "evaluated once at def time" mechanism as the default-argument fix for late binding above, just biting you instead of helping you.

**Fix:**
```python
def append_item(item, bucket=None):
    if bucket is None:
        bucket = []
    bucket.append(item)
    return bucket
```

### Class-body scope does not nest into comprehensions inside it

```python
class Config:
    values = [1, 2, 3]
    doubled = [v * 2 for v in values]        # works: `values` is looked up directly in class body
    tripled = [v * multiplier for v in values]   # NameError if `multiplier` is also a class attribute!

class Config2:
    multiplier = 3
    values = [1, 2, 3]
    tripled = [v * multiplier for v in values]   # NameError: name 'multiplier' is not defined
```
A comprehension (list/dict/set, but not a plain `for` loop) introduces its own function-like scope, and that scope's LEGB chain skips the class body entirely — class bodies are not treated as an enclosing scope for nested functions or comprehensions, by design, because that would make ordinary methods accidentally see other class attributes as bare names. The *iterable* of the outermost `for` clause is a special case: it's evaluated in the enclosing (class-body) scope before the comprehension's own scope takes over, which is why `values` in `values` works as the outer iterable but `multiplier` does not work as an *expression* inside the comprehension body.

### `__closure__` and cell objects — what a closure actually is

```python
def make_counter():
    count = 0
    def increment():
        nonlocal count
        count += 1
        return count
    return increment

c = make_counter()
print(c.__closure__)                  # (<cell at 0x...: int object at 0x...>,)
print(c.__closure__[0].cell_contents) # 0, then 1, then 2... after each call
print(c.__code__.co_freevars)         # ('count',)
```
A closure is not a copy of the enclosing variables — it's a tuple of `cell` objects, one per free variable, and each cell is a mutable box that both the enclosing function and the nested function share a reference to. `nonlocal count; count += 1` mutates the cell's contents in place, which is exactly why all lambdas sharing a loop variable's cell see the same, most-recently-mutated value — there's only one cell, shared by every closure created inside that loop.

---

## Build it from scratch

A minimal from-scratch demonstration of why the loop-variable trap happens, implemented as an explicit cell to make the sharing visible:

```python
class Cell:
    def __init__(self, value):
        self.value = value

def make_closures_broken(n):
    cell = Cell(0)                 # ONE cell, shared by every lambda below
    funcs = []
    for i in range(n):
        cell.value = i
        funcs.append(lambda: cell.value)   # all read the SAME cell
    return funcs

def make_closures_fixed(n):
    funcs = []
    for i in range(n):
        cell = Cell(i)              # a FRESH cell every iteration
        funcs.append(lambda c=cell: c.value)
    return funcs

assert [f() for f in make_closures_broken(3)] == [2, 2, 2]
assert [f() for f in make_closures_fixed(3)] == [0, 1, 2]
```

This mirrors exactly what CPython's real cell objects do — a loop variable is one cell reused across iterations unless something (a default argument, a factory call, a fresh local per iteration) forces a new binding. Lab: `labs/py/11-scoping-closures/`.

---

## How it's done in production

| Symptom | Cause | Fix |
|---|---|---|
| A list of callbacks/handlers all fire with the same, usually last, value | Late-binding closure over a loop variable | Default-argument trick, or a factory function creating a fresh scope per item |
| `UnboundLocalError: local variable 'x' referenced before assignment` on a variable that "should" read a global | Any assignment to `x` anywhere in the function makes it local for the whole function body | Add `global x` (or `nonlocal x` for an enclosing function) if mutation of the outer variable is intended; otherwise rename the local to avoid shadowing |
| A function's default list/dict argument accumulates values across unrelated calls | Mutable default evaluated once at def time, shared across all calls | Default to `None`, initialize inside the function body |
| `SyntaxError: no binding for nonlocal 'x' found` | `nonlocal x` used where no enclosing function scope (only global) defines `x` | Use `global` instead if the intended target is module scope, since `nonlocal` explicitly excludes it |
| `NameError` inside a class-body comprehension referencing another class attribute | Comprehensions introduce their own scope that does not include the class body, except for the outermost iterable expression | Pass the needed value as part of the outer iterable, or move the computation out of the comprehension into `__init__`/a classmethod |
| A `threading.Thread(target=lambda: worker(i))` loop processes the same `i` for every thread | Same late-binding trap, now with real concurrency stakes (duplicate/lost work per worker) | `Thread(target=worker, args=(i,))` — pass by argument instead of closing over the loop variable at all |

---

## Tradeoffs & when NOT to use it

- **`global` for anything beyond a small, well-contained module-level flag or counter is a maintainability liability** — it makes a function's behavior depend on invisible external state, which is exactly what makes concurrent access to it (multiple threads calling a function with `global counter; counter += 1`) a race condition, since `+=` on a plain int is not atomic in general and depends on bytecode-level interleaving.
- **Prefer explicit parameter passing or a class instance holding state over closures for anything that needs to be tested or introspected independently** — a closure's captured state is only visible via `__closure__[i].cell_contents`, which is not something you want a test suite relying on; a class with instance attributes is directly inspectable.
- **Deeply nested closures (three or more levels) hurt readability far more than the elegance they buy** — if you need `nonlocal` at more than one level, or a closure closing over another closure's result, a class or an explicit state object is almost always clearer.
- **Don't use the mutable-default-argument bug as a performance "trick" on purpose** — some code intentionally exploits def-time-evaluated defaults as a cheap memoization cache; it's fragile and surprises the next reader, and `functools.lru_cache` or an explicit module-level cache says the same thing without the trap-shaped syntax.

---

## Interview questions

### Q1 — What does LEGB stand for and in what order does Python search?
**Testing:** the baseline everyone must have cold.
**Answer:** Local, Enclosing, Global, Built-in. Name lookup walks in that order — innermost function scope first, then any enclosing function scopes (nearest first), then the module's global scope, then Python's built-ins — and stops at the first scope where the name is found.
**Follow-up trap:** *"Is a class body one of the scopes searched by a method defined inside it?"* — no. Class bodies are not part of the LEGB chain for nested functions/methods; a method must access other class attributes via `self.` or `ClassName.`, not as a bare name, precisely because the class body isn't an enclosing scope.

### Q2 — Explain the classic `[lambda: i for i in range(3)]` bug precisely — not just "it's a closure gotcha."
**Testing:** whether you can explain the *mechanism*, not just recite the symptom.
**Answer:** Every lambda in the list closes over the same variable `i` — mechanically, the same cell object — rather than capturing its value at creation time. There's one `i` binding reused across all three loop iterations, so by the time any lambda is called (after the loop has finished), every one of them reads the same cell, which holds `2`, the loop's final value.
**Follow-up trap:** *"Give two different fixes and explain why each works."* — (1) default argument `lambda i=i: i`, which works because default values are evaluated once at function-definition time, immediately capturing the current value rather than deferring to a shared cell; (2) a factory function `def make(i): return lambda: i`, which works because each call to the factory creates a genuinely new local scope (and thus a new cell) for that invocation's `i`.

### Q3 — Why does this raise `UnboundLocalError` instead of printing the global value?
```python
x = 5
def f():
    print(x)
    x = 10
```
**Testing:** the compile-time-vs-runtime distinction, the single most consequential fact in this module.
**Answer:** The compiler scans `f`'s entire body before execution and sees an assignment to `x` (`x = 10`), which marks `x` as local for the *whole function*, including the `print(x)` line that comes before the assignment textually. At runtime, `print(x)` tries to read the local `x`, which hasn't been assigned yet, raising `UnboundLocalError`. It has nothing to do with execution order — it's a static, source-scanning decision.
**Follow-up trap:** *"So how would you make this print 5 and then set the module-level x to 10?"* — add `global x` as the first line of `f`, which tells the compiler to bind all assignments to `x` in this function to the global scope instead of creating a local.

### Q4 — When would `nonlocal` raise a `SyntaxError`, and why is that different from a runtime error?
**Answer:** `nonlocal x` raises `SyntaxError: no binding for nonlocal 'x' found` at compile time if no enclosing *function* scope already defines `x` — critically, it does not fall back to global, unlike `global`, which always succeeds by creating a binding in module scope if needed. Because this check happens by scanning enclosing scopes at compile time (before the function ever runs), the error surfaces immediately on import/definition, not on some later call.
**Follow-up trap:** *"What if the variable exists at module (global) scope but not in any enclosing function?"* — still a SyntaxError. `nonlocal` explicitly means "an enclosing function's scope," never global; you'd need `global` instead if that's genuinely the target.

### Q5 — What is a closure, mechanically, in CPython terms?
**Testing:** depth beyond "a function that remembers its environment."
**Answer:** A tuple of `cell` objects (visible via `func.__closure__`), one per free variable the nested function references from an enclosing scope (`func.__code__.co_freevars` names them). Each cell is a mutable box; both the enclosing function's frame and the nested function share a reference to the *same* cell object, so mutating it via `nonlocal` in the nested function is visible to the enclosing scope and vice versa.
**Follow-up trap:** *"Why does that explain the loop-variable bug so precisely?"* — because every lambda created inside one loop iteration closes over the *same* cell for the loop variable (there's one binding, mutated each iteration, not a fresh one per iteration), so all of them observe whatever that one shared cell holds by the time they're called.

### Q6 — Why is `def f(items=[]): items.append(x); return items` a well-known bug pattern, and what's the actual root cause shared with the closure trap above?
**Answer:** Default argument values are evaluated exactly once, at `def` time, and stored on the function object; every call that doesn't override `items` reuses that same list object, so appends accumulate silently across unrelated calls. The shared root cause with the closure trap is "evaluated once, at definition time, and then reused/shared" — in the closure case that fact is exploited as the *fix* (default-argument trick), and in this case the same mechanism is the *bug*.
**Follow-up trap:** *"Is this specific to mutable defaults, or does it affect immutable ones like `def f(x=5)` too?"* — immutable defaults are also evaluated once, but since ints/strings/tuples can't be mutated in place, there's no way for one call to affect another call's default — the trap only manifests when the default is mutable and gets mutated in place rather than reassigned.

### Q7 — Why doesn't a comprehension's loop variable leak into the enclosing scope in Python 3, unlike a plain `for` loop's?
**Answer:** Comprehensions (list/dict/set/genexpr) have always introduced their own scope in Python 3 (Python 2's list comprehensions leaked their loop variable; this was one of the deliberate breaking changes made for Python 3). A plain `for i in range(3): ...` statement, in contrast, is not a comprehension and does not introduce a new scope — its loop variable `i` is an ordinary assignment in the current scope and remains accessible after the loop ends.
**Follow-up trap:** *"Since Python 3.12's PEP 709 inlines comprehensions for speed, does the loop variable now leak?"* — no, PEP 709 is a performance optimization (comprehensions no longer pay the cost of a full nested function call/frame), not a scoping change; the comprehension's variable still does not leak into the enclosing scope, by explicit design of the PEP.

### Q8 — A class body has `multiplier = 3` and `values = [v * multiplier for v in [1,2,3]]`. Does this raise `NameError`? What if it were a plain `for` loop appending to a list instead?
**Testing:** the specific, easy-to-get-wrong class-body-vs-comprehension-scope interaction.
**Answer:** Yes, `NameError: name 'multiplier' is not defined` — the comprehension's own scope does not include the class body as an enclosing scope, so `multiplier` (a class attribute, not local/enclosing/global/builtin to the comprehension) can't be found. A plain `for` loop written directly in the class body, by contrast, executes in the class body's own namespace, so it *can* see `multiplier` as a bare name there.
**Follow-up trap:** *"Why does the outermost iterable expression behave differently — `for v in values` finds `values` fine even inside the comprehension?"* — the outermost `for`'s iterable is special-cased to be evaluated in the enclosing scope (the class body, here) *before* the comprehension's own scope is entered; every other expression inside the comprehension (the output expression, any `if` filters, or nested `for` clauses) executes inside the comprehension's private scope, which cannot see the class body.

### Q9 — You spawn 5 threads in a loop, each meant to process a different index: `for i in range(5): threading.Thread(target=lambda: worker(i)).start()`. What goes wrong, and how do you fix it?
**Testing:** applying the closure trap to a real concurrency bug, which is a more serious version of the classic gotcha because it's a race, not just a display bug.
**Answer:** All five lambdas close over the same `i` cell. Because thread scheduling means `.start()` calls return quickly and the loop typically finishes before any thread actually calls the lambda, most or all threads end up calling `worker(4)` (the loop's final value) rather than `worker(0)` through `worker(4)` — and the exact outcome is timing-dependent, which is what makes it worse than the single-threaded version: it can appear correct in testing and fail under different scheduling in production.
**Follow-up trap:** *"Why is `Thread(target=worker, args=(i,))` a better fix than the lambda default-argument trick?"* — it sidesteps closures entirely: `args=(i,)` copies the current value of `i` into the `Thread` object's own storage at the moment of the call, with no shared cell in play at all, which is both correct and more idiomatic for passing per-thread arguments than wrapping in a lambda in the first place.

### Q10 — Is Python's scoping static (lexical) or dynamic? Why does the answer matter for reasoning about a function you haven't seen called yet?
**Answer:** Static/lexical — a name's scope is determined entirely by where the code is *written* (nesting of `def`/`class`/module), never by the call stack at runtime. This means you can fully determine which scope every name in a function resolves to just by reading the source, without knowing anything about who calls it or from where — a genuinely useful property for reasoning about correctness without running the code.
**Follow-up trap:** *"Where does Python's behavior look dynamic, then, and does that contradict this?"* — `global`/`nonlocal` and the "any assignment makes it local" rule can *feel* dynamic because the practical effect depends on which lines are present in the function, but the determination itself is still made once, at compile time, from the source text — not by tracing actual execution. `eval`/`exec` with a custom namespace is the one genuine way to inject truly dynamic-looking scoping in Python, and it's exactly as much of a footgun as it sounds.

---

## Red flags that fail you

- Explaining the closure loop-variable bug as "lambdas are broken" instead of naming the shared-cell mechanism.
- Not knowing why `UnboundLocalError` happens on a variable that hasn't been assigned yet in the function.
- Saying `nonlocal` and `global` do the same thing.
- Claiming a class body is an enclosing scope for methods or comprehensions inside it.
- Reaching for `global` as a default way to share state across functions.
- Not connecting the mutable-default-argument bug to "evaluated once, at def time."

---

## Cheat card

```
LEGB          Local -> Enclosing -> Global -> Built-in; class bodies are NOT in this chain for
              nested functions/comprehensions
STATIC RULE   compiler scans the WHOLE function body for assignments BEFORE running it;
              any assignment to x anywhere -> x is local for the entire function
UnboundLocalError   reading x before its (later, in-function) assignment when x is local-by-assignment
global x      assignments to x in this function bind to MODULE scope (creates binding if absent)
nonlocal x    assignments to x bind to nearest ENCLOSING FUNCTION scope; SyntaxError if none exists
              (never falls back to global)
CLOSURE       tuple of cell objects: func.__closure__; free var names: func.__code__.co_freevars
              cell is a shared mutable box between defining scope and nested function
LATE BINDING  [lambda: i for i in range(3)]() all == 2 -- one shared cell, read AFTER loop ends
  FIX 1       lambda i=i: i          (default args evaluated ONCE at def time -> captures now)
  FIX 2       def make(i): return lambda: i   (fresh scope/cell per call)
MUTABLE DEFAULT   def f(x=[]): evaluated ONCE at def time, shared across ALL calls forever
              fix: def f(x=None): x = x if x is not None else []
COMPREHENSION SCOPE   own scope since Py3; outermost `for ... in ITERABLE` evaluated in enclosing
              scope BEFORE entering it; everything else inside cannot see the class body
PEP 709 (3.12)   comprehensions inlined for speed; scoping rules unchanged by design
THREADING TRAP   Thread(target=lambda: worker(i)) shares cell across threads -> use
              Thread(target=worker, args=(i,)) instead
```

## Sources

- [PEP 3104 – Access to Names in Outer Scopes (nonlocal)](https://peps.python.org/pep-3104/) — accessed 2026-08-01
- [What's New In Python 3.12 — PEP 709: Comprehension inlining](https://docs.python.org/3/whatsnew/3.12.html) — accessed 2026-08-01
- [Python execution model — scopes and namespaces](https://docs.python.org/3/reference/executionmodel.html) — accessed 2026-08-01

## Changelog
- 2026-08-01 — created
