# Mutability, Shallow vs Deep Copy, and the Aliasing Bugs They Cause

> **Track:** T01 Python & SWE Craft · **Time:** 1.5h · **Prereqs:** none · **Updated:** 2026-08-01
> **Module id:** `T01-copy-semantics` · **Tags:** language

## The 30-second version

In Python, names are labels bound to objects, and assignment (`b = a`) never copies anything — it just makes `b` point at the same object `a` already points at, so `is` (identity, same object) and `==` (equality, same value) diverge the moment two names might refer to the same object versus two equal-but-distinct ones. A shallow copy (`copy.copy`, slicing, `list(x)`, `dict(x)`) allocates a new outer container but reuses references to the same inner objects, which is exactly the trap in `[[0]*3]*3` — three "rows" that are the same list object, so mutating one mutates all three. A deep copy (`copy.deepcopy`) recursively copies every nested mutable object, correctly handling cycles via a memo dict, at a real and sometimes prohibitive cost. Small-int and short-string interning make `is` comparisons on those *look* correct by coincidence for small literals, which is precisely why relying on `is` for value equality is a bug waiting to surface the moment a number gets big enough or a string gets constructed dynamically.

## Why this gets asked

Because this is the single most common source of "it worked in the unit test with one row and broke with a thousand" bugs: someone built a nested default structure with `*`, or passed a dict/list into a function assuming it would be copied like a value type in another language, and mutated the caller's data by accident. The interviewer has personally chased a shared-mutable-default or an aliased nested-list bug through a data pipeline, and wants to see that you reach for the right depth of copy deliberately rather than sprinkling `deepcopy` everywhere out of fear.

---

## Lineage: past → present → future

**What came before.** Languages with value semantics for compound types (C structs copied by value on assignment, or C++ without explicit references) make "assignment copies" the default, and copying-by-reference is the thing you opt into. Python inverted this from the start: CPython's object model has always been "everything is an object, names are references to objects, assignment binds a name to an object" — there was never a "copy on assignment" era to move away from. What *did* evolve is the tooling around explicit copying: the `copy` module's `copy()`/`deepcopy()` distinction, and the `__copy__`/`__deepcopy__` hook protocol, were formalized early (Python's `copy` module dates to the 1.x era) precisely because "shallow vs deep" isn't a binary any real codebase can ignore once nested mutable structures show up.

**Where it stands now.** The identity/equality/copy model itself hasn't changed, but pandas gave this topic new teeth: pandas 3.0 (released January 2026) made Copy-on-Write the *only* mode — chained assignment (`df[df.x > 0]['y'] = 1`) now raises rather than silently working-or-not-working depending on whether the intermediate selection happened to be a view or a copy, which used to be one of the most notorious "it depends on internal memory layout" footguns in the ecosystem. [Pandas 3.0 Released!](https://pandas.pydata.org/community/blog/pandas-3.0.html) — accessed 2026-08-01. This is a direct descendant of the same view-vs-copy confusion this module covers at the plain-Python level, just surfaced through a DataFrame API instead of a list or dict. The live disagreement in general Python code is less about the rules (which are settled) and more about defensive style: whether functions should defensively `.copy()` inputs they don't intend to mutate (safer, costs memory and time) versus documenting "this function may mutate its argument" and trusting callers (faster, riskier).

**Where it's heading.** No change to core Python's copy semantics is anticipated; it's foundational and stable. The direction of travel is more libraries adopting explicit copy-on-write or immutable-by-default data structures (pandas 3.0's CoW, the broader industry move toward immutable/persistent data structures in functional-influenced codebases) specifically *because* shallow-copy aliasing bugs are common enough that library authors are removing the footgun at the API level rather than continuing to document around it.

---

## Mental model

```
a = [1, 2, 3]
b = a                # b is NOT a copy — same object, two names

id(a) == id(b)        # True
a is b                # True
a.append(4)
print(b)              # [1, 2, 3, 4]  <-- b "changed" because there was only ever ONE list
```

```
NAMES  ──▶  POINT TO  ──▶  OBJECTS (on the heap, refcounted)

  a ──┐
      ├──▶ [1, 2, 3, 4]   (one list object)
  b ──┘
```

Shallow vs deep, visualized on a list-of-lists:

```
original = [[0, 0], [0, 0]]

shallow = copy.copy(original)      deep = copy.deepcopy(original)

original ──▶ [ ref1, ref2 ]        original ──▶ [ ref1, ref2 ]
shallow  ──▶ [ ref1, ref2 ]        deep     ──▶ [ ref3, ref4 ]
              │      │                            │      │
              ▼      ▼                            ▼      ▼
        SAME inner lists                    NEW inner lists
   (mutating one via shallow          (fully independent —
    affects original too)             mutating deep is safe)
```

---

## How it actually works

### Names bind to objects; assignment never copies

```python
a = [1, 2, 3]
b = a
b.append(4)
print(a)        # [1, 2, 3, 4] — a and b are the same object
b = [9, 9]      # this REBINDS b to a new object — does not affect a
print(a)        # still [1, 2, 3, 4]
```
The distinction that trips people: `b.append(4)` mutates the shared object in place (visible through `a`); `b = [9, 9]` rebinds the name `b` to a different object entirely (not visible through `a`). Mutation and rebinding are different operations with different visibility.

### `is` vs `==`

```python
a = [1, 2, 3]
b = [1, 2, 3]
a == b          # True  — same VALUE
a is b          # False — different OBJECTS
c = a
c is a          # True  — same object
```
`==` calls `__eq__` (value comparison, customizable per type); `is` compares `id()` (memory identity, never customizable). The only correct uses of `is` are checking against singletons: `x is None`, `x is True`/`False`, and sentinel objects you created specifically for identity comparison.

### Small-int and string interning — why `is` "works" until it doesn't

```python
a = 100
b = 100
a is b          # True — CPython caches small ints [-5, 256] as singletons

x = 1000
y = 1000
x is y          # False (typically) — outside the cached range, two separate objects
                # NOTE: this is a CPython implementation detail, not a language guarantee

s1 = "hello"
s2 = "hello"
s1 is s2        # True — CPython interns string literals that look like identifiers

s3 = "".join(["h", "e", "l", "l", "o"])
s3 is s1        # False — dynamically built, not interned automatically
s3 == s1        # True
```
This is the trap: code that does `if x is 100:` or `if name is "admin":` can appear to work correctly through testing with small literals, then silently fail once a value crosses the small-int cache boundary or a string is built dynamically instead of typed as a literal — and because `is` just does a pointer comparison, there is no exception, just a wrong (usually `False`) answer. **Never use `is` for value comparison of ints, strings, or any non-singleton value.** [Data model — Python 3.14 documentation](https://docs.python.org/3/reference/datamodel.html) — accessed 2026-08-01.

### Shallow copy — `copy.copy`, slicing, `list()`, `dict()`

```python
import copy

original = [[1, 2], [3, 4]]
shallow = copy.copy(original)          # or original[:], or list(original)

shallow.append([9, 9])                 # new OUTER list is independent
print(original)                        # [[1, 2], [3, 4]] — unaffected

shallow[0].append(99)                  # mutating an INNER (shared) list
print(original)                        # [[1, 2, 99], [3, 4]] — original changed too!
```
A shallow copy makes a new container, but every element inside it is the *same* object reference as in the original. Appending to the outer shallow copy doesn't touch the original (different outer container). Mutating an element that is itself mutable (a nested list, dict, or custom object) *does* affect the original, because both containers hold a reference to the identical inner object.

### The nested-list aliasing bug — `[[0]*3]*3`

```python
grid = [[0] * 3] * 3
print(grid)             # [[0, 0, 0], [0, 0, 0], [0, 0, 0]] — looks fine
grid[0][0] = 1
print(grid)             # [[1, 0, 0], [1, 0, 0], [1, 0, 0]] — all three rows changed!
```
`[0] * 3` creates one list, `[0, 0, 0]`. The outer `* 3` then creates a *new outer list* containing three references to that *same* inner list object — it does not call the inner expression three times. There is exactly one row object, referenced three times. This is a shallow-copy-by-construction bug, not even involving `copy.copy` explicitly, which is what makes it so easy to write by accident.

**Correct construction:**
```python
grid = [[0] * 3 for _ in range(3)]     # the list comprehension evaluates [0]*3 fresh, 3 times
grid[0][0] = 1
print(grid)                            # [[1, 0, 0], [0, 0, 0], [0, 0, 0]] — correct
```

### Deep copy — `copy.deepcopy`

```python
import copy

original = [[1, 2], [3, 4]]
deep = copy.deepcopy(original)
deep[0].append(99)
print(original)         # [[1, 2], [3, 4]] — fully unaffected
```
`deepcopy` recursively walks the object graph, copying every mutable object it finds, and uses an internal `memo` dict (keyed by `id()` of already-copied objects) specifically to handle **cycles** correctly — `a = []; a.append(a); copy.deepcopy(a)` does not infinite-loop, because the second time `deepcopy` encounters the same object `id()`, it reuses the already-created copy from the memo instead of recursing again.

**Cost**: deepcopy is O(size of the entire reachable object graph), not O(top-level container size). Deep-copying a DataFrame-like nested structure with a million leaf objects walks all million of them, allocating a million new objects — this is measured in the tens to low hundreds of milliseconds even for moderately sized nested structures (a few hundred thousand objects), and grows linearly, unlike a shallow copy which is O(top-level size only) and typically sub-millisecond for the same structure.

### `__copy__` and `__deepcopy__` — customizing the protocol

```python
class Node:
    def __init__(self, value, parent=None):
        self.value = value
        self.parent = parent          # a reference we deliberately do NOT want deep-copied

    def __deepcopy__(self, memo):
        new = Node.__new__(Node)
        memo[id(self)] = new                       # register BEFORE recursing, for cycle safety
        new.value = copy.deepcopy(self.value, memo)
        new.parent = self.parent                    # keep the SAME parent reference on purpose
        return new
```
Implementing `__deepcopy__` lets a class opt out of copying specific attributes (a parent pointer, a cache, a DB connection) that should remain shared rather than duplicated. Registering `memo[id(self)] = new` *before* recursing into attributes is what makes self-referential or mutually-referential structures copy correctly instead of infinite-looping or double-copying.

### Mutable default arguments, from this angle

```python
def add_tag(tags=[]):     # the SAME list object is the default for every call
    tags.append("new")
    return tags
```
This is the identical "assignment never copies, and a default is created once" mechanism covered in the scoping module, viewed from the copy-semantics side: the bug isn't about scoping, it's that `[]` is evaluated once at def time and every caller who doesn't pass their own `tags` shares that one mutable object by reference — an aliasing bug with a def-time twist rather than an assignment-time one. Fix identically: default to `None`, construct fresh inside the function body.

---

## Build it from scratch

A minimal `deepcopy` that demonstrates the memo-for-cycles mechanism without using the `copy` module:

```python
def my_deepcopy(obj, memo=None):
    if memo is None:
        memo = {}
    if id(obj) in memo:
        return memo[id(obj)]           # already copying this object -- reuse, breaks cycles

    if isinstance(obj, list):
        new = []
        memo[id(obj)] = new            # register BEFORE recursing
        new.extend(my_deepcopy(item, memo) for item in obj)
        return new
    if isinstance(obj, dict):
        new = {}
        memo[id(obj)] = new
        for k, v in obj.items():
            new[my_deepcopy(k, memo)] = my_deepcopy(v, memo)
        return new
    if isinstance(obj, (int, float, str, bool, type(None), tuple)):
        return obj                     # immutable — safe to share, no need to copy
    raise TypeError(f"my_deepcopy: unsupported type {type(obj)}")

cyclic = []
cyclic.append(cyclic)
copied = my_deepcopy(cyclic)
assert copied[0] is copied             # cycle preserved correctly, no infinite recursion
```

Note immutable types (`int`, `str`, `tuple` of immutables) are returned as-is rather than copied — there's no aliasing hazard to guard against for something that can't be mutated in place, which is exactly why `copy.deepcopy` on a tuple of ints is nearly free. Lab: `(lab pending)`.

---

## How it's done in production

| Symptom | Cause | Fix |
|---|---|---|
| Mutating one "row" of a grid changes every row | `[[0]*n]*n` — outer multiplication repeats references to one inner list | `[[0]*n for _ in range(n)]`, evaluating the inner expression fresh each time |
| A function's caller sees their input dict/list mutated after calling a "read-only"-looking function | Function mutated its argument in place instead of working on a copy, and the argument was passed by reference (as everything is) | `.copy()` (or `deepcopy` if nested) at the top of the function if mutation must be avoided, or document the mutation explicitly as part of the contract |
| Deep-copying a large object graph takes hundreds of milliseconds to seconds and shows up in a profiler | `deepcopy` is O(size of the full reachable graph); called on something bigger than intended, or called in a hot loop | Copy only the subset that needs isolation, cache/reuse immutable substructure, or restructure to avoid needing a full deep copy at all |
| `copy.deepcopy()` raises or hangs on an object holding a file handle, socket, or DB connection | Deepcopy tries to recursively copy every attribute, including unpicklable/uncopyable resource handles | Implement `__deepcopy__` to special-case those attributes (keep the same reference, or exclude them, or reconnect fresh) |
| `if x is 1000:` sometimes true, sometimes false depending on unrelated code changes | Relying on CPython's small-int interning ([-5, 256]) as if it were guaranteed value equality | Use `==` for value comparison; reserve `is` for `None`/`True`/`False`/sentinels only |
| A cached/memoized structure silently shares state across supposedly-independent test cases | A shallow copy (or no copy) of a fixture object handed to multiple tests, with one test mutating shared nested state | Deep-copy fixtures that are mutated by tests, or rebuild fresh per test |

---

## Tradeoffs & when NOT to use it

- **`deepcopy` is the wrong tool for large object graphs where only isolation of the top level is actually needed.** If you're about to mutate only the outer container (append/remove elements) and never touch nested mutable elements, a shallow copy is correct and orders of magnitude cheaper.
- **`deepcopy` cannot sensibly copy file handles, sockets, DB connections, locks, or anything representing a live external resource** — it will either raise (many such objects implement `__deepcopy__` to refuse, or override `__reduce__` in ways that break naive copying) or, worse, silently produce a broken duplicate handle that doesn't actually represent an independent connection. Exclude these via a custom `__deepcopy__`, or restructure so the resource lives outside the copied object entirely (dependency injection instead of ownership).
- **Don't defensively `deepcopy` "just in case" on every function boundary in a hot path.** This is a common overreaction to having been bitten once; profile first — a targeted `.copy()` at the one boundary that actually needs isolation is almost always sufficient and far cheaper than blanket deep copying.
- **`is` for value comparison is never correct, even when it happens to work in testing** — the small-int/string interning behavior is a CPython implementation detail, not a language guarantee, and even within CPython it's scoped to specific ranges and literal forms that are easy to accidentally step outside of.
- **Immutable data structures (tuples, frozenset, `NamedTuple`, frozen dataclasses) sidestep this entire category of bug by construction** — when the aliasing risk of a specific field is the actual concern (not performance), consider whether it should be immutable instead of correctly-but-defensively copied.

---

## Interview questions

### Q1 — What does `b = a` do when `a` is a list? Does it copy?
**Testing:** the absolute baseline; anyone missing this fails immediately.
**Answer:** No copy happens. `b` becomes a second name bound to the exact same list object `a` already refers to. Mutating through either name (`a.append(x)` or `b.append(x)`) is visible through both, because there was only ever one object; rebinding one name (`b = [...]`) does not affect the other, because that creates a new object and points only `b` at it.
**Follow-up trap:** *"Does this apply to ints and strings the same way?"* — yes, the binding mechanism is identical for every type; the *appearance* of difference comes from ints and strings being immutable, so there's no operation that mutates them in place to reveal the shared reference — any apparent "change" to an int/string name is always a rebind, never a mutation.

### Q2 — Difference between `is` and `==`, and when is `is` ever correct to use?
**Answer:** `==` calls `__eq__` and compares value/content (customizable per type); `is` compares object identity via `id()` and is never customizable. `is` is correct specifically for singleton checks: `x is None`, `x is True`, `x is False`, and comparisons against sentinel objects created for that exact purpose. Using `is` for general value comparison (numbers, strings, custom objects with meaningful `__eq__`) is a bug.
**Follow-up trap:** *"Why does `if x is None` work fine but `if x is 100` is a landmine?"* — `None` is a true language-level singleton; there is exactly one `None` object ever, guaranteed. `100` being cached is a CPython implementation detail (small-int caching for [-5, 256]) that happens to make `is` look correct for small literals but is not guaranteed by the language and doesn't extend to arbitrary integers.

### Q3 — Explain `[[0]*3]*3` precisely — why does mutating one row affect all three?
**Testing:** the canonical shallow-aliasing bug, always asked as a trace-the-output question.
**Answer:** `[0]*3` evaluates once, producing one list object `[0, 0, 0]`. The outer `* 3` then builds a new outer list containing three references to that *same* inner list object — it does not re-evaluate `[0]*3` three separate times. So `grid[0]`, `grid[1]`, and `grid[2]` are the identical object; mutating any one of them via index assignment mutates the object all three names point to.
**Follow-up trap:** *"How do you fix it, and why does the fix actually create three distinct objects?"* — `[[0]*3 for _ in range(3)]`. A list comprehension evaluates its expression fresh on every iteration of the loop, so `[0]*3` runs three separate times, producing three distinct list objects.

### Q4 — What's the difference between a shallow copy and a deep copy, mechanically?
**Answer:** A shallow copy (`copy.copy`, slicing, `list(x)`, `dict(x)`) creates one new outer container but populates it with references to the *same* inner objects as the original — safe if you only ever mutate the outer container, unsafe if any element is itself mutable and gets mutated. A deep copy (`copy.deepcopy`) recursively copies every nested mutable object it finds, producing a fully independent object graph, at the cost of walking (and allocating for) the entire reachable structure.
**Follow-up trap:** *"Give a concrete case where a shallow copy is actually the correct choice, not just the cheap one."* — copying a list of tuples (or any list of immutable elements) — since the elements can't be mutated in place regardless, a shallow copy provides exactly the same safety as a deep copy at a fraction of the cost, so reaching for `deepcopy` there is pure waste.

### Q5 — How does `copy.deepcopy` avoid infinite recursion on a self-referential structure like `a = []; a.append(a)`?
**Testing:** whether "deepcopy just recurses" is understood at the mechanism level.
**Answer:** `deepcopy` maintains a `memo` dict keyed by `id()` of objects already being copied. Before recursing into an object's contents, it registers the new (still-being-built) copy in the memo under the original's id. If it encounters the same object again during recursion (as happens immediately with a self-referential list), it finds the id already in the memo and returns the existing partial copy instead of recursing again, terminating what would otherwise be infinite recursion.
**Follow-up trap:** *"Does this mean the copy correctly preserves the cycle structure, or does it break the cycle?"* — it correctly preserves it: `copy.deepcopy(a)[0] is copy.deepcopy(a)` reproduces the same self-reference in the new object, not a broken/flattened version, because the memo returns the *actual* new object being constructed, not a placeholder.

### Q6 — When is `deepcopy` the wrong tool, even though it's "always correct"?
**Testing:** the "when NOT to use it" checklist item — most candidates only know deepcopy is safer, not when that safety is wasted or actively harmful.
**Answer:** Three cases: (1) large object graphs where only top-level isolation is needed — the cost is O(entire reachable graph), not O(top level), so this can be orders of magnitude more expensive than necessary; (2) objects holding live external resources (file handles, sockets, DB connections, locks) — these can't be meaningfully duplicated, and naive deepcopy either raises or produces a broken duplicate; (3) hot paths, where blanket defensive deepcopying at every function boundary (a common overreaction after being bitten once) shows up as real, measurable overhead in a profiler.
**Follow-up trap:** *"How would you copy an object that has both plain data and a DB connection attribute?"* — implement `__deepcopy__` on that class: deep-copy the plain-data attributes normally, and either keep the same connection reference (shared, intentionally) or explicitly reconnect, rather than letting the default recursive walk attempt to copy the connection object.

### Q7 — Why does relying on `is` for integer or string equality sometimes "work" in tests and then fail in production?
**Answer:** CPython caches small integers in the range [-5, 256] as singletons and interns string literals that look like identifiers, so `is` comparisons on values in those ranges/forms happen to return the same answer as `==` by coincidence of implementation. Once a value falls outside the cached range (a count that grows past 256, an ID read from a database) or a string is constructed dynamically (`"".join(...)`, string formatting) rather than typed as a literal, that coincidence disappears and `is` silently returns `False` for equal values, with no error to signal the mistake.
**Follow-up trap:** *"Is this caching behavior something you can rely on for any performance reason, like deduplication?"* — no, it's a CPython implementation detail (not part of the language spec, and other implementations like PyPy may cache differently), so code should never depend on it for correctness, and using it deliberately for memory savings is fragile and non-portable.

### Q8 — A function receives a dict, modifies it internally to build a result, and returns it. The caller is surprised their original dict changed. What happened, and what are the two ways to prevent it?
**Testing:** applied version of "assignment never copies," at a function-boundary scale relevant to real APIs.
**Answer:** The function received a reference to the caller's exact dict object (not a copy — Python always passes object references), and mutated it in place (e.g., `d["result"] = ...`) rather than building a new dict. Prevention: (1) the function defensively copies at the top (`d = dict(original)` for a shallow copy, or `copy.deepcopy` if nested structures are also mutated) before touching it; (2) the function's contract explicitly documents that it mutates its argument, and the caller is responsible for copying beforehand if they need to preserve the original.
**Follow-up trap:** *"Which of those two is the better default for a public library API, and why?"* — defensive copying inside the function, because it makes the function's behavior predictable regardless of caller discipline; mutating shared arguments silently is a common source of hard-to-trace bugs specifically because most callers assume value-like behavior by habit from other languages, even though Python never provides it by default.

### Q9 — Implement `__deepcopy__` for a `TreeNode` class with a `parent` reference, such that deep-copying a subtree doesn't try to deep-copy the entire tree upward through `parent`.
**Testing:** whether you can apply the memo/exclusion pattern to a realistic structure (this is a common real bug: naive deepcopy on a tree with parent pointers walks the whole tree, not just the subtree).
**Answer:**
```python
class TreeNode:
    def __init__(self, value, parent=None):
        self.value = value
        self.children = []
        self.parent = parent

    def __deepcopy__(self, memo):
        new = TreeNode.__new__(TreeNode)
        memo[id(self)] = new
        new.value = copy.deepcopy(self.value, memo)
        new.children = copy.deepcopy(self.children, memo)
        new.parent = self.parent          # deliberately NOT deep-copied
        return new
```
Without the custom hook, `deepcopy(some_node)` would follow `.parent` upward, then `.children` back down from the parent, potentially walking and copying the entire tree instead of just the intended subtree — and if the tree is large, this is a real performance bug, not just a correctness nuance.
**Follow-up trap:** *"What if two sibling nodes share a common ancestor also being deep-copied in the same operation — does the memo still work correctly here?"* — yes, as long as they're copied via a single top-level `deepcopy` call sharing one memo dict; if a shared ancestor were reachable and copied through both children's `parent`-independent paths, the memo ensures it's only actually copied once, with both children's copies referencing the same new object — but since `parent` is deliberately excluded here, this scenario doesn't arise for upward references at all.

### Q10 — How does pandas 3.0's Copy-on-Write model relate to shallow-copy aliasing bugs at the Python-object level?
**Testing:** connecting general language semantics to a library-specific, currently relevant change — tests whether the candidate tracks version-dependent ecosystem shifts.
**Answer:** Pre-3.0 pandas, indexing operations (`df[df.x > 0]`) sometimes returned a view (sharing underlying memory with the original, a shallow-copy-like relationship) and sometimes a copy, depending on internal memory layout that wasn't part of the documented API — so `df[df.x > 0]['y'] = 1` (chained assignment) might silently mutate the original DataFrame, or might silently do nothing, and you couldn't tell which without knowing pandas internals. Pandas 3.0 (Jan 2026) made Copy-on-Write the only mode: every operation behaves as if it returns an independent copy (correctness first), while the implementation still shares memory underneath until a write actually happens, at which point it copies — and chained assignment like the example above now raises explicitly instead of silently doing the wrong thing. [Pandas 3.0 Released!](https://pandas.pydata.org/community/blog/pandas-3.0.html) — accessed 2026-08-01.
**Follow-up trap:** *"Does CoW mean pandas never copies data anymore?"* — no, it means pandas defers the copy until a mutation actually requires one (hence "copy-on-write"), which is a performance optimization on top of guaranteed-correct semantics, not an elimination of copying — mutating a CoW-backed DataFrame still triggers a real copy at that point, same underlying cost, just deferred and always logically correct.

---

## Red flags that fail you

- Saying `b = a` copies the list.
- Using `is` to compare integers or strings for equality without qualifying that it's unsafe.
- Not being able to explain why `[[0]*3]*3` aliases its rows.
- Claiming `deepcopy` is always the "safe default" with no cost tradeoff.
- Not knowing `deepcopy` uses a memo dict to handle cycles.
- Confusing mutation (visible through all references) with rebinding (visible through only the rebound name).

---

## Cheat card

```
ASSIGNMENT    b = a NEVER copies; b becomes a second name bound to the SAME object
MUTATION vs REBIND   a.append(x) mutates shared object (visible via all names)
                     a = [...] rebinds ONE name to a new object (not visible via others)
is vs ==      == calls __eq__ (value); is compares id() (identity) — never customizable
              ONLY correct is-uses: x is None / True / False / sentinel objects
INTERNING     small ints [-5,256] cached as singletons; literal-like strings interned
              -- CPython implementation detail, NOT a language guarantee; breaks outside these ranges
SHALLOW COPY  copy.copy(x), x[:], list(x), dict(x) -- new OUTER container, SAME inner object refs
DEEP COPY     copy.deepcopy(x) -- recursively copies every nested mutable object
              cost: O(full reachable graph), not O(top level) -- can be ms to seconds on large graphs
[[0]*3]*3     ONE inner list, referenced 3x by the outer list -- mutating grid[0][0] changes all rows
              FIX: [[0]*3 for _ in range(3)] -- comprehension evaluates fresh each iteration
CYCLES        deepcopy uses a memo dict keyed by id(); registers copy BEFORE recursing -> no infinite loop
__copy__ / __deepcopy__(self, memo)   opt a class attribute OUT of copying (e.g. parent ptr, DB conn)
                                       must write memo[id(self)] = new BEFORE recursing, for cycle safety
MUTABLE DEFAULT   def f(x=[]): evaluated ONCE at def time; shared across every call that omits x
WRONG TOOL WHEN   only top-level isolation needed (shallow suffices) · object holds a live resource
                  (file/socket/DB conn/lock) · hot path where blanket deepcopy shows up in a profiler
PANDAS 3.0 (Jan 2026)   Copy-on-Write is the ONLY mode; chained assignment now RAISES instead of
                        silently working/not-working depending on view-vs-copy internals
```

## Sources

- [Data model — Python 3.14 documentation (object identity, is, small-int caching)](https://docs.python.org/3/reference/datamodel.html) — accessed 2026-08-01
- [copy — Shallow and deep copy operations — Python 3.14 documentation](https://docs.python.org/3/library/copy.html) — accessed 2026-08-01
- [Pandas 3.0 Released! — Copy-on-Write becomes the only mode](https://pandas.pydata.org/community/blog/pandas-3.0.html) — accessed 2026-08-01
- [What's new in 3.0.0 (January 21, 2026) — pandas documentation](https://pandas.pydata.org/docs/whatsnew/v3.0.0.html) — accessed 2026-08-01

## Changelog
- 2026-08-01 — created
