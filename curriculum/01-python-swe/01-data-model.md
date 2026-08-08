# CPython Data Model: Dunder Protocols, Descriptors, Metaclasses, and MRO

> **Track:** T01 Python & SWE Craft · **Time:** 2.5h · **Prereqs:** none · **Updated:** 2026-08-03
> **Module id:** `T01-data-model` · **Tags:** language
> **Lab:** `labs/python/01-data-model/`

## The 30-second version

Every Python object's behavior — how it's constructed, compared, hashed, iterated, indexed, or accessed via attribute lookup — is defined entirely by which dunder methods it implements, and the interpreter dispatches to these methods not through the instance's `__dict__` but through the *type's* `__dict__`, which is exactly why operator overloading works consistently even when an instance shadows a method on itself (`a + b` calls `type(a).__add__`, never `a.__dict__['__add__']`). Descriptors are the mechanism underneath `property`, `staticmethod`, `classmethod`, and ORMs' field types: any object implementing `__get__` (and optionally `__set__`/`__delete__`) placed as a *class* attribute intercepts attribute access on instances of that class, and the specific precedence rule — data descriptors (define both `__get__` and `__set__`) take priority over instance `__dict__`, which takes priority over non-data descriptors (`__get__` only) — is what makes `obj.attr = x` sometimes silently fail to do what you'd expect if `attr` is a data descriptor on the class. Metaclasses are simply "the class of a class" (`type` is the metaclass of nearly everything, and a class defined with `metaclass=Meta` has `Meta.__new__`/`__init__` control the class *creation* process itself, not instance creation), which is how ORMs, ABCs, and dataclass-like libraries register or transform class bodies at definition time before any instance ever exists. MRO (Method Resolution Order) determines which parent's implementation is used at each name lookup step in multiple inheritance, computed via the C3 linearization algorithm — not simple depth-first search — specifically because naive depth-first search violates a property called "local precedence order" that causes genuinely surprising and inconsistent method resolution in diamond inheritance hierarchies.

## Why this gets asked

Because these four mechanisms are the actual load-bearing internals behind nearly every "magic" Python library behavior a senior engineer will encounter — dataclasses, SQLAlchemy/Django ORM fields, ABCs, `functools.cached_property`, pytest fixtures' introspection — and an interviewer wants to know whether you can explain *why* a specific piece of framework magic works, not just that it does. It's also a fast, cheap way to distinguish "has used Python for years, mostly writing straightforward application code" from "has actually had to debug why a class attribute assignment silently did nothing, or why a diamond-inheritance method resolved to the wrong parent," which requires having internalized the mechanism, not just the vocabulary.

---

## Lineage: past → present → future

**What came before.** Early Python (1.x/2.x, pre-2001) had a split between built-in types (implemented in C, with a fixed, non-overridable set of behaviors) and "classic classes" (`class Foo:` with no explicit base), which had no unified data model — new-style classes (Python 2.2, PEP 252/253, unifying types and classes under a single object model rooted at `object`) introduced the modern dunder-method-based protocol system and, critically, descriptors, which didn't exist in any usable form before this unification. Multiple inheritance's method resolution order was, before Python 2.3, computed via naive depth-first, left-to-right search (the same algorithm still used by some other object-oriented languages) — this produced genuinely inconsistent and surprising results in diamond inheritance patterns (a class inheriting from two classes that share a common ancestor), which is exactly the problem C3 linearization was adopted to fix.

**Where it stands now.** The dunder-protocol/descriptor/metaclass/MRO system has been stable, essentially unchanged in its core mechanics, for two decades — this is mature, settled territory, not an area of ongoing redesign. What's changed is how much of this machinery application developers need to touch directly versus consume through higher-level abstractions: `dataclasses` (3.7+), `attrs`, and Pydantic models generate most of the dunder methods (`__init__`, `__eq__`, `__repr__`) a class needs automatically, and `property`/`functools.cached_property` cover the overwhelming majority of descriptor use cases without requiring a hand-written descriptor class — metaclasses specifically have become rarer in day-to-day application code as `__init_subclass__` (PEP 487, Python 3.6) was introduced specifically to cover many of the class-customization use cases that previously required a full custom metaclass, with a much gentler learning curve and less risk of metaclass conflicts in multiple inheritance.

**Where it's heading.** This is foundational, stable CPython semantics with no significant change on the horizon — expect continued preference for `__init_subclass__` and higher-level declarative APIs (dataclasses, Pydantic, attrs) over hand-rolled metaclasses in new code, and continued reliance on the underlying dunder/descriptor/MRO machinery as the substrate those higher-level tools compile down to. The one area of genuine, ongoing evolution is performance: CPython's per-attribute-access dispatch through this machinery has been the target of substantial optimization work (the specializing adaptive interpreter introduced in 3.11+, which caches and specializes attribute lookup and method calls based on observed types at each call site) — the *semantics* of the data model haven't changed, but the CPython interpreter internals executing it have gotten meaningfully faster at doing so.

---

## Mental model

```
DUNDER DISPATCH: always via TYPE, never via instance __dict__
  a + b  ==>  type(a).__add__(a, b)   -- NOT a.__dict__.get('__add__')
  (this is why monkey-patching an INSTANCE's __add__ does nothing for `+`)

DESCRIPTOR PRECEDENCE (attribute lookup on obj.attr, attr defined on the CLASS):
  1. DATA descriptor on type(obj)   (__get__ AND __set__/__delete__)   <- WINS, always
  2. obj.__dict__['attr']            (instance dict)
  3. NON-DATA descriptor on type(obj) (__get__ only, e.g. plain functions/methods)
  4. class attribute itself (no descriptor protocol)
  5. AttributeError

  property = a DATA descriptor (has __set__ even if you didn't define a setter --
             it raises AttributeError, which IS a __set__ implementation, so it
             still outranks instance __dict__)

METACLASS: "the class of a class" -- type(int) is type, type(MyClass) is type (usually)
  class MyClass(metaclass=Meta):  ...
  Meta.__new__/__init__ run at CLASS-CREATION time (once, when the class statement
  executes), NOT at instance-creation time -- this is how ORMs register fields,
  ABCs enforce abstract methods, etc., all before any instance exists

MRO / C3 LINEARIZATION (diamond inheritance):
        A
       / \
      B   C
       \ /
        D
  MRO(D) = [D, B, C, A, object]  -- NOT naive depth-first [D, B, A, C, A, object]
  C3 guarantees: a class always appears before its parents, and if B is listed
  before C in D's bases, B precedes C in the full MRO too ("local precedence order")
```

The one-line mental model: **every "magic" behavior in Python — operator overloading, property-like attribute interception, class-creation hooks, and multiple-inheritance method lookup — is a specific, inspectable protocol dispatched through the type, not the instance, and all four mechanisms exist specifically so that libraries can customize object behavior without the language needing a special case for every possible customization.**

---

## How it actually works

### Dunder methods: dispatch through the type, and why that matters

When Python evaluates `a + b`, it does not look up `__add__` on the instance `a`; it looks it up on `type(a)` (and falls back to `type(b).__radd__` if `type(a).__add__` returns `NotImplemented`). This type-level dispatch is deliberate: it's what allows CPython to implement fast paths for built-in types (an `int.__add__` call doesn't need to check an instance dict that built-in types don't meaningfully have per-instance), and it's also precisely why assigning `a.__add__ = some_function` on an instance has zero effect on what `a + b` does — the interpreter never consults the instance's `__dict__` for dunder lookups, only the type's. This generalizes to essentially every operator and protocol: `__len__`, `__getitem__`, `__iter__`, `__enter__`/`__exit__`, `__eq__`/`__hash__` are all resolved via the type, which is a detail worth stating precisely in an interview, since "instance methods can be monkey-patched to change behavior" is true for regular methods but specifically false for dunder-triggered protocol behavior.

### Descriptors: the mechanism under `property`, and the precedence rule that trips people up

A descriptor is any object whose type defines `__get__` (a **non-data descriptor**, e.g., a plain function/method) or both `__get__` and `__set__`/`__delete__` (a **data descriptor**, e.g., `property`). When a descriptor is placed as a *class* attribute, accessing it through an instance (`obj.attr`) triggers `__get__(instance, owner_class)` rather than returning the descriptor object itself — this is exactly how methods work: a plain function is a non-data descriptor (`function.__get__` exists, producing a bound method), which is why `obj.method` returns a bound method object rather than the raw function stored on the class. The precedence rule (data descriptors win over instance `__dict__`, which wins over non-data descriptors) explains a specific, real gotcha: if a class defines `name` as a `property` with only a getter (no explicit setter), attempting `obj.name = "x"` still raises `AttributeError`, *not* silently creating an instance attribute that shadows the property — because a `property`, even a read-only one, is a **data descriptor** (it implements `__set__`, which by default raises), and data descriptors always take precedence over whatever would otherwise be written to `obj.__dict__`.

### Metaclasses: customizing class *creation*, not instance creation

`type` is itself a class — the class of nearly every class in Python (`type(int) is type`, `type(str) is type`) — and just as a class's `__new__`/`__init__` control instance creation, a **metaclass's** `__new__`/`__init__` control *class* creation: when the interpreter executes a `class Foo(Bases, metaclass=Meta):` statement, it calls `Meta.__new__(mcs, name, bases, namespace)` and `Meta.__init__(cls, name, bases, namespace)` to actually construct the `Foo` class object itself, running once at class-definition time, before any instance of `Foo` is ever created. This is the mechanism ORMs use to scan a class body for declared fields and register them, or that ABCs use to enforce that all abstract methods are overridden before allowing a concrete subclass to be instantiated — both need to inspect and potentially transform the class *itself*, which is a job dunder methods and descriptors (which operate on instances) structurally cannot do. `__init_subclass__` (a regular classmethod hook, checked automatically whenever a subclass is created) covers a large fraction of what used to require a custom metaclass, without the added complexity and metaclass-conflict risk (two base classes with incompatible metaclasses cannot always be combined) that full metaclasses introduce — this is why modern Python code reaches for `__init_subclass__` far more often than a hand-written metaclass.

### MRO and C3 linearization: why naive depth-first search is wrong

For single inheritance, method resolution order is trivial (walk straight up the chain). For multiple inheritance, particularly diamond patterns (two classes sharing a common ancestor, both inherited by a further subclass), naive depth-first-left-to-right search produces a specific, well-known inconsistency: for `class D(B, C)` where both `B` and `C` inherit from `A`, depth-first search would produce `[D, B, A, C, A, object]` — visiting `A` *before* `C`, even though `D` explicitly listed `C` before `A` matters for what `C` might override. This violates a property called **local precedence order**: if a class lists `B` before `C` in its bases, every consistent linearization should respect that `B`'s resolution comes before `C`'s (and by extension, before anything `C` inherits that `B` doesn't override). C3 linearization (adopted in Python 2.3) computes an MRO that guarantees local precedence order and monotonicity (a subclass's MRO is consistent with each of its parents' own MRO) by merging the parents' own linearizations with the direct base list using a specific merge algorithm, producing `[D, B, C, A, object]` for the diamond above — `A` correctly appears only once, after both `B` and `C`, respecting `D`'s explicit base ordering. `ClassName.__mro__` or `ClassName.mro()` shows the actual computed order for any class, and is the correct way to answer "which parent's method actually runs" rather than reasoning it out by hand for anything beyond the simplest hierarchies.

---

## Build it from scratch

```python
class LoggedAttribute:
    """A data descriptor: logs every get/set, demonstrating __get__/__set__ precedence."""
    def __init__(self, name):
        self.name = name          # the underlying storage key on the INSTANCE dict

    def __get__(self, instance, owner):
        if instance is None:
            return self            # accessed on the class itself, e.g. MyClass.attr
        print(f"GET {self.name}")
        return instance.__dict__.get(self.name)

    def __set__(self, instance, value):
        print(f"SET {self.name} = {value!r}")
        instance.__dict__[self.name] = value

class Widget:
    color = LoggedAttribute("color")   # class-level descriptor instance

w = Widget()
w.color = "red"     # prints "SET color = 'red'" -- __set__ intercepts this, NOT instance __dict__ directly
print(w.color)       # prints "GET color", then "red" -- __get__ intercepts, reads from instance.__dict__


class RegisteringMeta(type):
    """A metaclass: registers every class using it in a global registry AT CLASS-CREATION TIME."""
    registry = {}

    def __new__(mcs, name, bases, namespace):
        cls = super().__new__(mcs, name, bases, namespace)
        if bases:                                    # skip the base class itself
            RegisteringMeta.registry[name] = cls
        return cls

class Plugin(metaclass=RegisteringMeta):
    pass

class MyPlugin(Plugin):
    pass

print(RegisteringMeta.registry)   # {'MyPlugin': <class '__main__.MyPlugin'>} -- registered at definition time


class A:
    def who(self): return "A"
class B(A):
    def who(self): return "B"
class C(A):
    def who(self): return "C"
class D(B, C):
    pass

print(D.__mro__)      # (<class D>, <class B>, <class C>, <class A>, <class object>)
print(D().who())      # "B" -- C3 linearization puts B before C before A, matching D(B, C)'s base order
```
The lab exercise extends the `LoggedAttribute` descriptor to implement a minimal version of `functools.cached_property` (compute once, cache in `instance.__dict__`, and — the subtle part — use a **non-data** descriptor, i.e., omit `__set__` entirely, specifically so that once the value is cached in the instance `__dict__`, subsequent lookups skip the descriptor's `__get__` entirely per the precedence rule, avoiding recomputation without needing any explicit caching check inside `__get__` itself) and verifies this against the real `functools.cached_property`'s documented behavior.

---

## How it's done in production

| Symptom | Cause | Fix |
|---|---|---|
| `obj.some_field = value` silently does nothing, or raises `AttributeError`, even though `some_field` looks like a normal attribute | `some_field` is a `property` (or another data descriptor) defined on the class with no setter — data descriptors always intercept `__set__`, even a read-only one that just raises | Add an explicit setter to the property, or if read-only behavior is intentional, this is expected — don't try to bypass it by writing directly to `obj.__dict__['some_field']`, which breaks the abstraction the property exists to enforce |
| A subclass in a multiple-inheritance hierarchy calls a method and gets a different parent's implementation than expected | The actual C3-computed MRO doesn't match a naive depth-first mental model of the hierarchy | Print `ClassName.__mro__` directly rather than reasoning about it by hand for any hierarchy beyond single inheritance or a simple two-level diamond |
| Combining two library base classes raises `TypeError: metaclass conflict` | The two base classes have incompatible, unrelated metaclasses, and Python cannot automatically determine which metaclass the combined subclass should use | Define an explicit metaclass that itself inherits from both conflicting metaclasses, or avoid the multiple-metaclass combination if one library offers a non-metaclass-based extension point (e.g., `__init_subclass__`-based hooks) |
| A `functools.cached_property`-decorated method recomputes every time instead of caching, despite the decorator being applied correctly | The class also defines `__slots__` without including the cached property's storage name, or the instance genuinely lacks a `__dict__` for the descriptor to cache into | `cached_property` needs a per-instance `__dict__` to store the cached value (since it's a non-data descriptor relying on precedence over `__dict__`) — classes using `__slots__` need either to add an explicit slot for the cache or avoid `cached_property` in favor of a manually-slotted caching pattern |
| A hand-written `__eq__` breaks usage in a `set` or as a `dict` key | Defining `__eq__` without also defining `__hash__` makes the class unhashable by default (Python sets `__hash__` to `None` automatically when `__eq__` is overridden and `__hash__` isn't) | Explicitly define `__hash__` consistent with the equality logic (equal objects must hash equal) whenever overriding `__eq__` on a class that needs to be hashable |

---

## Tradeoffs & when NOT to use it

- **Don't reach for a custom metaclass when `__init_subclass__` covers the need.** Metaclasses introduce genuine complexity (conflict risk when combining classes with different metaclasses, a less familiar mental model for other engineers reading the code) that `__init_subclass__` avoids entirely for the common case of "run some logic whenever a subclass is defined" — reserve metaclasses for cases that genuinely need to intercept or transform the class-creation process itself in ways `__init_subclass__`'s simpler hook can't express.
- **Don't hand-write descriptor classes for simple computed-attribute or caching needs** when `property` or `functools.cached_property` already covers it — a custom descriptor is appropriate when you need the *same* get/set logic reused across many different attributes or classes (avoiding rewriting the same property boilerplate repeatedly), not for a one-off computed attribute.
- **Don't rely on multiple inheritance and MRO for anything beyond a shallow, well-understood hierarchy** (e.g., mixins with a single, clear responsibility each) without printing and reviewing `__mro__` explicitly — deep or wide multiple-inheritance hierarchies become genuinely difficult for other engineers to reason about correctly, even when C3 linearization is technically well-defined and consistent.
- **Don't override `__eq__` (or `__hash__`) casually on a mutable class** without considering whether instances need to live safely in sets/dicts — a mutable object whose hash can change after being inserted into a set breaks that set's internal invariants, a subtle bug distinct from the unhashable-by-default gotcha above.

---

## Interview questions

### Q1 — Why does `a.__add__ = custom_func` on an instance have no effect on what `a + b` computes?
**Testing:** whether dunder dispatch through the type (not the instance) is understood precisely.
**Answer:** The `+` operator is implemented by CPython to look up `__add__` on `type(a)`, never on the instance `a` itself — assigning an attribute named `__add__` directly on the instance creates an entry in `a.__dict__`, but the interpreter's special-method dispatch for operators bypasses instance `__dict__` entirely and goes straight to the type, so the instance-level assignment is simply never consulted.
**Follow-up trap:** *"Would defining a regular (non-dunder) method on an instance work the same way, or is this specific to dunder methods?"* — no, it's specific to dunder-triggered protocol behavior; a *regular* method called explicitly as `a.some_method()` does consult the instance first (standard attribute lookup, which does check `a.__dict__` before falling back to the class), so instance-level monkey-patching works fine for ordinary method calls — the type-only dispatch rule applies specifically to the special methods invoked implicitly by language syntax and built-in functions (operators, `len()`, `iter()`, etc.), not to explicit, ordinary attribute-based method calls.

### Q2 — Why does `obj.name = "x"` raise `AttributeError` for a read-only `property`, rather than silently creating an instance attribute that shadows it?
**Testing:** the data-descriptor-precedence mechanism, precisely.
**Answer:** `property` is a **data descriptor** — it implements both `__get__` and `__set__`, even when no explicit setter function was provided (the default `__set__` for a read-only property simply raises `AttributeError`). Data descriptors always take precedence over an instance's `__dict__` during attribute *assignment* as well as lookup, so `obj.name = "x"` invokes the property's `__set__` (which raises) rather than falling through to writing `name` into `obj.__dict__`.
**Follow-up trap:** *"If you really needed to bypass this and write directly into the instance's __dict__ anyway, is that possible, and is it ever a good idea?"* — yes, `obj.__dict__['name'] = "x"` bypasses the descriptor protocol entirely since it manipulates the dict directly rather than going through attribute assignment syntax — but doing this defeats the entire purpose of the property (any validation or read-only invariant it was enforcing), and subsequent `obj.name` reads will still invoke the property's `__get__` (which likely ignores or doesn't know about this bypassed value) — this is essentially always a sign the property shouldn't have been read-only in the first place, or that the code needs a different design, not a legitimate production pattern.

### Q3 — What's the actual difference between what a metaclass's `__new__`/`__init__` control versus what a regular class's `__new__`/`__init__` control?
**Testing:** the "class of a class" framing and the timing distinction (class-creation-time vs instance-creation-time).
**Answer:** A regular class's `__new__`/`__init__` control the creation of *instances* of that class, running every time `MyClass(...)` is called. A metaclass's `__new__`/`__init__` control the creation of the *class itself* — they run exactly once, when the `class Foo(...):` statement is executed by the interpreter, constructing the `Foo` class object (which is itself an instance of the metaclass), before any instance of `Foo` has ever been created.
**Follow-up trap:** *"If you wanted to validate that every subclass of a base class defines a required attribute, would you reach for `__init_subclass__` or a metaclass, and why?"* — `__init_subclass__`, in almost all cases; it's a classmethod hook automatically invoked whenever a subclass is created, giving you the same "runs at class-definition time" capability a metaclass would provide for this specific use case, without introducing a custom metaclass and its associated conflict risk when combining with other base classes that might have their own (possibly incompatible) metaclasses — reserve actual metaclasses for cases genuinely requiring more control over the class-creation process than `__init_subclass__`'s simpler hook exposes (e.g., needing to modify the class's namespace dict before the class object is constructed, which `__init_subclass__` runs too late to do).

### Q4 — Derive why naive depth-first-left-to-right method resolution is inconsistent for the classic diamond inheritance pattern, and what C3 linearization guarantees instead.
**Testing:** the actual mechanism of MRO inconsistency, not just "C3 is better."
**Answer:** For `class D(B, C)` where both `B` and `C` inherit from `A`, depth-first-left-to-right search visits `D -> B -> A -> C -> A -> object`, meaning `A`'s methods would be found (and potentially override anything `C` defines that `B` doesn't) *before* `C` is even consulted — this violates local precedence order, since `D` explicitly listed `B` before `C`, implying `B`'s and its ancestors' resolution should take priority over `C`'s, but naive depth-first search lets an ancestor of `B` (namely `A`) jump ahead of `C` itself. C3 linearization guarantees both local precedence order (respecting the explicit base-list ordering) and monotonicity (a subclass's MRO is consistent with each parent's own independently-computed MRO), producing `[D, B, C, A, object]` for this diamond — `C` is correctly resolved before `A`, and `A` appears exactly once, at the end.
**Follow-up trap:** *"Is it possible to define a class hierarchy where C3 linearization simply fails to produce any valid MRO at all?"* — yes; if the base classes' individual orderings are genuinely contradictory (e.g., one base implies `X` should precede `Y` while another implies `Y` should precede `X`), C3 linearization cannot satisfy both constraints simultaneously and Python raises `TypeError: Cannot create a consistent method resolution order` at class-definition time — this is a real, if uncommon, error message worth recognizing as "your inheritance hierarchy has a genuine ordering contradiction," not a bug in Python's MRO algorithm.

### Q5 — Why does overriding `__eq__` without also overriding `__hash__` make a class unhashable, and what's the underlying invariant being protected?
**Testing:** the consistency requirement between equality and hashing, and why Python enforces it defensively.
**Answer:** Python's data model requires that objects considered equal (`a == b`) must have the same hash value, since dicts and sets rely on this invariant to correctly locate an existing equal key/element via its hash bucket. If you override `__eq__` without providing a matching `__hash__`, the inherited default `__hash__` (typically based on object identity) would almost certainly violate this invariant (two objects that compare equal via your custom `__eq__` but have different identity-based hashes) — so Python defensively sets `__hash__` to `None` automatically whenever `__eq__` is overridden and `__hash__` isn't explicitly also defined, making the class unhashable by default rather than silently allowing an invariant-violating configuint hash to slip through.
**Follow-up trap:** *"If you define __hash__ to always return the same constant value for every instance, is that a valid (if suboptimal) implementation?"* — technically valid (it doesn't violate the equal-objects-must-hash-equal invariant, since any hash collision is permitted, just performance-costly), but it destroys hash table performance entirely — every instance lands in the same hash bucket, degrading dict/set operations involving these objects from average `O(1)` to `O(n)` — a "valid but you should never actually do this" answer that separates candidates who understand the invariant from those who just want to make the unhashable error go away.

### Q6 — What specific problem does `functools.cached_property` solve, and why must it be implemented as a non-data descriptor (no `__set__`) for its caching to work efficiently?
**Testing:** connecting the descriptor precedence rule directly to a real, commonly-used standard-library tool's implementation choice.
**Answer:** It solves the problem of an expensive, deterministic computed property that should only be computed once per instance and then reused — implemented as a **non-data** descriptor (only `__get__`, no `__set__`) so that after the first access computes the value and manually stores it in `instance.__dict__[name]`, subsequent attribute accesses find that value in the instance `__dict__` *before* ever reaching the descriptor's `__get__` again, per the precedence rule (non-data descriptors rank below instance `__dict__`). If it were instead implemented as a data descriptor (with a `__set__`, even a no-op one), it would *always* intercept access regardless of what's in the instance `__dict__`, requiring an explicit "have I already cached this" check inside `__get__` on every single access — a real, avoidable inefficiency the non-data-descriptor design sidesteps entirely.
**Follow-up trap:** *"Why does functools.cached_property require the class to have a writable __dict__, and what breaks with __slots__?"* — it needs somewhere per-instance to store the cached value once computed, and it stores it directly in `instance.__dict__` — a class using `__slots__` (which explicitly avoids giving instances a `__dict__`, for memory savings) has no such dict for `cached_property` to write into, so combining `__slots__` with `cached_property` either raises an error or silently fails to cache (behavior that's worth verifying against the specific Python version in use) unless the slots explicitly include a slot matching the cached property's name, which requires manual, non-default handling.

### Q7 — A colleague combines two unrelated library base classes and gets `TypeError: metaclass conflict`. What's happening, and what are the options to resolve it?
**Testing:** understanding metaclass conflicts as a genuine, structural limitation, not an arbitrary error.
**Answer:** Each of the two base classes has its own metaclass (possibly each library's own custom metaclass, unrelated to the other), and Python cannot automatically determine a single, consistent metaclass for the combined subclass unless one of the two metaclasses is itself a subclass of the other (in which case Python can use the more specific one automatically). When neither metaclass is a subclass of the other, there's no unambiguous way to construct the combined class, and Python raises this error rather than guessing.
**Follow-up trap:** *"What if you can't modify either library's base classes directly — what's the actual fix available to you?"* — define your own metaclass that inherits from both conflicting metaclasses (`class CombinedMeta(MetaA, MetaB): pass`) and explicitly pass `metaclass=CombinedMeta` to your subclass — this works only if the two original metaclasses' own behaviors are compatible enough to combine sensibly (no directly conflicting `__new__`/`__init__` logic between them); if they're genuinely incompatible in behavior, not just in type hierarchy, this "fix" will run without raising an error but may produce class-creation behavior neither original library author intended or tested for, which is a real risk worth flagging rather than treating the mechanical fix as automatically safe.

### Q8 — Design question: you're building a plugin registration system where every subclass of a `Plugin` base class should automatically register itself in a global registry the moment it's defined, with no explicit registration call required. Would you use `__init_subclass__` or a metaclass, and why?
**Testing:** applying the module's core distinction to a realistic design decision, with justified reasoning rather than a default answer.
**Answer:** `__init_subclass__` — it's specifically designed for exactly this use case (a hook that runs automatically whenever a subclass is created, letting you register it, validate it, or otherwise act on its definition), requires no custom metaclass machinery, and critically avoids any risk of metaclass conflicts if a consumer of this `Plugin` base class ever needs to combine it with another base class that has its own metaclass — which is a real risk for a plugin system meant to be used broadly by other code you don't control. A metaclass would only be the better choice here if you needed to modify the class's namespace/attributes *before* the class object itself is constructed (e.g., injecting or transforming methods into the class body), which plugin registration alone doesn't require.
**Follow-up trap:** *"What if the registration logic needs to run before the class body is even fully evaluated, e.g., to inject a method that class body code references?"* — that specific requirement (needing to affect the class's own namespace/attributes *during* construction, before the class object exists) is exactly the case `__init_subclass__` cannot handle, since it runs *after* the class is already fully constructed — this would genuinely require a metaclass's `__new__` (which receives the namespace dict *before* the class object is built and can modify it), making it one of the few remaining legitimate reasons to reach for a custom metaclass instead of the simpler hook.

### Q9 — Why does CPython's specializing adaptive interpreter (3.11+) matter for the data model's performance, and does it change any of the model's semantics?
**Testing:** understanding that recent CPython performance work operates beneath the data model's stable semantics, not by changing them.
**Answer:** The specializing adaptive interpreter observes the actual types involved at a given call site (an attribute access, a binary operation) over repeated executions and specializes the bytecode to a faster path for that specific, observed type combination (e.g., a specialized, faster path for `int + int` at a specific call site, falling back to the general dispatch machinery if a different type shows up later) — this speeds up the *execution* of dunder-dispatch-based operations substantially in common, type-stable code, without changing what the data model actually specifies should happen semantically; if the specialized fast path's assumption is violated (a different type appears), CPython transparently de-specializes and falls back to the general, fully-correct dispatch path.
**Follow-up trap:** *"Could this specialization ever cause a program to behave differently than it would have on an older Python version, from a correctness standpoint?"* — no, not from a correctness standpoint — the specialization is an internal implementation optimization strictly beneath the language's observable semantics; a program's *behavior* (what value operations produce, which methods get called) is identical with or without specialization, only the *speed* differs — this is precisely the kind of change that's safe for CPython to make without being a language-semantics change, and is why the data model itself (this module's actual subject matter) has been stable for two decades even as the interpreter executing it keeps getting faster.

### Q10 — What's the difference between a data descriptor and a non-data descriptor in terms of precedence, and give a concrete example of each already present in every Python program.
**Testing:** synthesizing the precedence rule with concrete, ubiquitous examples rather than abstract description alone.
**Answer:** A data descriptor implements both `__get__` and `__set__` (or `__delete__`) and always takes precedence over an instance's `__dict__` for the attribute name it controls — `property` is the ubiquitous example, present in essentially every nontrivial Python codebase. A non-data descriptor implements only `__get__` and ranks *below* instance `__dict__` in precedence — plain functions (and therefore ordinary methods) are the ubiquitous example: every method defined in a class body is, mechanically, a non-data descriptor (functions implement `__get__`, which is what turns `obj.method` into a bound method), which is exactly why you *can* shadow a method by assigning directly into an instance's `__dict__` (`obj.__dict__['method'] = something`) — something you cannot do to override a `property`-based attribute the same way, precisely because of this precedence difference.
**Follow-up trap:** *"Given that ordinary methods are non-data descriptors, why doesn't a typo like `obj.method = lambda: None` (setting an instance attribute with the same name as a method) get overridden right back by the class's method the next time it's accessed?"* — because that assignment writes directly into `obj.__dict__['method']` via ordinary attribute-assignment semantics (not going through any descriptor's `__set__`, since the class-level method is a *non-data* descriptor with no `__set__` to intercept the assignment at all), and per the precedence rule, instance `__dict__` outranks non-data descriptors — so the very next `obj.method` lookup finds the instance-level lambda first and never reaches the class's original method, which is exactly the mechanism (not a bug) behind the common gotcha of accidentally shadowing a method with an instance attribute of the same name.

---

## Red flags that fail you

- Believes dunder methods are looked up on the instance rather than the type, or can't explain why instance-level monkey-patching of a dunder method has no effect.
- Cannot explain the data-descriptor-vs-instance-`__dict__` precedence rule, or doesn't know `property` is a data descriptor even without an explicit setter.
- Confuses metaclass `__new__`/`__init__` (class-creation time) with regular class `__new__`/`__init__` (instance-creation time).
- Believes multiple inheritance is resolved via naive depth-first search rather than C3 linearization, or has never used `__mro__` to check.
- Doesn't know why overriding `__eq__` without `__hash__` makes a class unhashable.
- Reaches for a custom metaclass without considering `__init_subclass__` first for a simple subclass-hook use case.

---

## Cheat card

```
DUNDER DISPATCH: a+b => type(a).__add__(a,b), ALWAYS via TYPE, never instance __dict__
  (instance-level a.__add__=f has NO effect on `a+b`; ordinary a.method() DOES check
  instance dict first -- rule is specific to implicitly-invoked protocol methods)

DESCRIPTOR PRECEDENCE (obj.attr, attr on the CLASS):
  DATA descriptor (__get__ + __set__/__delete__) > instance __dict__ > NON-DATA (__get__ only)
  property = DATA descriptor even w/ no setter (default __set__ raises AttributeError)
    -> obj.attr = x raises, does NOT silently write to instance __dict__
  plain functions/methods = NON-DATA descriptors -> instance __dict__ CAN shadow them
  cached_property = NON-DATA descriptor BY DESIGN -> after first compute+cache in
    instance.__dict__, later lookups skip __get__ entirely (needs instance to HAVE a __dict__,
    breaks/needs manual slot with __slots__)

METACLASS: "class of a class" -- type(MyClass) is type (usually). Meta.__new__/__init__
  run ONCE at CLASS-CREATION time (class statement executes), before ANY instance exists
  -- how ORMs/ABCs register or transform class bodies
  prefer __init_subclass__ (PEP 487, 3.6+) for simple "run logic when subclass defined"
  hooks -- avoids metaclass-conflict risk (TypeError if 2 base classes have unrelated
  metaclasses, neither a subclass of the other)

MRO / C3 LINEARIZATION (adopted Python 2.3, fixes naive depth-first's diamond-inheritance bug):
  guarantees LOCAL PRECEDENCE ORDER (D(B,C): B's own MRO precedes C's) + monotonicity
  diamond D(B,C), both(A): MRO = [D,B,C,A,object] -- NOT naive DFS's [D,B,A,C,A,object]
  ALWAYS check ClassName.__mro__ directly for anything beyond single inheritance
  "Cannot create a consistent MRO" TypeError = genuine ordering contradiction in bases

__eq__ without __hash__ -> Python sets __hash__=None automatically (unhashable) --
  protects the invariant: equal objects MUST hash equal (dict/set correctness)

CPython 3.11+ specializing adaptive interpreter: speeds up dunder dispatch via observed-
  type caching at call sites -- ZERO semantic change, pure internal execution speedup
```

## Sources

- [PEP 252 — Making Types Look More Like Classes](https://peps.python.org/pep-0252/) — accessed 2026-08-03
- [PEP 253 — Subtyping Built-in Types](https://peps.python.org/pep-0253/) — accessed 2026-08-03
- [PEP 487 — Simpler customisation of class creation (`__init_subclass__`)](https://peps.python.org/pep-0487/) — accessed 2026-08-03
- [Python Data Model — official documentation](https://docs.python.org/3/reference/datamodel.html) — accessed 2026-08-03
- [Descriptor HowTo Guide — official documentation](https://docs.python.org/3/howto/descriptor.html) — accessed 2026-08-03
- [A Monotonic Superclass Linearization for Dylan (the C3 algorithm paper) — Barrett et al. (1996)](https://www.webcitation.org/5rWvzZAWr) — accessed 2026-08-03
- [What's New in Python 3.14 — official documentation](https://docs.python.org/3/whatsnew/3.14.html) — accessed 2026-08-03

## Changelog
- 2026-08-03 — created
