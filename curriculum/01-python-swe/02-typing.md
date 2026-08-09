# Typing in Depth: Protocols, Generics, Variance, and Pydantic v2

> **Track:** T01 Python & SWE Craft · **Time:** 2h · **Prereqs:** T01-data-model · **Updated:** 2026-08-03
> **Module id:** `T01-typing` · **Tags:** language
> **Lab:** none yet — see `labs/py/02-agent-loop/` for the pattern if you want to build one

## The 30-second version

Python's type system is entirely optional and erased at runtime (no enforcement unless something explicitly checks), which makes it fundamentally a static-analysis and documentation tool, not a runtime guarantee — this single fact explains why `mypy --strict` catching a type error and Pydantic raising a `ValidationError` are solving genuinely different problems (compile-time-style structural checking versus runtime data validation at a trust boundary) rather than being two flavors of the same thing. `Protocol` (PEP 544) brought structural typing to Python — a class satisfies a `Protocol` by having the right methods/attributes, with no inheritance or explicit declaration required, mirroring how duck typing already worked at runtime but making it statically checkable, which is the correct tool whenever you want to type-hint "anything with a `.read()` method" rather than "anything inheriting from `Readable`." Generics (`TypeVar`, and Python 3.12's cleaner `class Stack[T]:` syntax) let a function or class's type signature depend on a placeholder type filled in at each call/instantiation site, and variance — covariant (`TypeVar('T', covariant=True)`, safe to substitute a subtype where a supertype is expected, correct for read-only/output positions), contravariant (safe to substitute a supertype where a subtype is expected, correct for input/consumer positions), and invariant (default, no substitution allowed either direction, required whenever a type appears in both input and output positions, like a mutable container) — is not a pedantic technicality but the exact reason `list[Dog]` is not a valid substitute for `list[Animal]` in a type-safe language, even though a `Dog` clearly *is* an `Animal`. Pydantic v2's core validation logic was rewritten in Rust (`pydantic-core`), delivering roughly 5-50x faster validation than v1 depending on the workload, and the v1-to-v2 migration changed enough API surface (validator decorators, config classes, `.dict()`/`.json()` renamed) that it's a real, non-cosmetic migration effort, not a drop-in version bump.

## Why this gets asked

Because static typing adoption is now table stakes for any serious Python codebase, and an interviewer wants to know whether you use type hints as genuine architectural communication (Protocols for structural interfaces, correctly-variant generics for container APIs) or as a superficial layer of unchecked annotations that `mypy --strict` would immediately shred. It's also asked because Pydantic sits at nearly every production Python service's trust boundary (API request parsing, config loading, LLM tool-call argument validation) and a candidate who's shipped production Python in the last few years should be able to speak concretely to v2's validation model and performance characteristics, not just "it validates data."

---

## Lineage: past → present → future

**What came before.** Python shipped with zero optional static type syntax for its first two decades — type hints didn't exist as a language feature until PEP 484 (Python 3.5, 2015), which itself was a response to large Python codebases (Dropbox, Google, and others) hitting genuine maintainability limits that dynamic typing alone couldn't address at scale — refactoring confidence, IDE autocomplete quality, and catching an entire category of "wrong type passed" bugs before runtime all degrade in large, dynamically-typed codebases without some form of static signal. Before `Protocol` (PEP 544, Python 3.8, 2019), Python's type system only supported nominal typing (an object satisfies a type only via explicit inheritance), which was a poor match for how Python code actually worked at runtime — duck typing (anything with the right methods works, no inheritance required) was the dominant runtime idiom, and nominal-only static typing couldn't express it without forcing artificial inheritance hierarchies purely for type-checking purposes. Data validation before Pydantic's rise typically meant hand-written validation functions, `jsonschema`, or `marshmallow` — all of which worked but required substantially more boilerplate to get the same combination of validation, serialization, and IDE-friendly typed access that Pydantic (built directly on top of type hints) provides in one declarative model definition.

**Where it stands now.** Type hints combined with `mypy --strict` (or increasingly `pyright`/`ty`, faster alternative type checkers) are standard practice for serious production Python codebases, and `Protocol`-based structural typing has become the preferred approach for defining interfaces in idiomatic Python specifically because it matches how the language already behaves at runtime, unlike forcing an `ABC` inheritance hierarchy purely for the type checker's benefit. Pydantic v2 (2023) rewrote its core validation engine in Rust as a separate crate (`pydantic-core`), delivering the substantial performance improvement noted above, and Pydantic v2 is now the dominant choice for typed data validation in Python across web frameworks (FastAPI), LLM tool-call argument schemas, and configuration management — as of 2026, the `pydantic-core` repository was folded back into the main `pydantic` monorepo (April 2026) while remaining actively developed, with the ecosystem fully past the v1-to-v2 migration for nearly all actively-maintained projects.

**Where it's heading.** Python's type system continues to gain expressiveness incrementally (PEP 695's cleaner generic syntax in 3.12, `TypeVarTuple` for variadic generics, continued refinement of overload and protocol checking) rather than undergoing structural upheaval, and expect continued convergence toward faster type checkers (`ty`, `pyright`) displacing some of `mypy`'s historical dominance specifically on large-codebase check-time performance, an area where `mypy`'s pure-Python implementation has been a genuine bottleneck. Runtime validation (Pydantic-family tools) is likely to keep pushing performance further via compiled cores and to keep deepening integration with the broader typed-Python ecosystem (dataclasses interop, `TypedDict` support), while the fundamental split this module opens with — types are erased and unenforced at runtime unless something explicitly validates — remains a permanent, structural property of the language, not something any future typing enhancement is likely to change.

---

## Mental model

```
STATIC TYPES (mypy/pyright) vs RUNTIME VALIDATION (Pydantic) -- DIFFERENT PROBLEMS

  def process(user: User) -> Result:     <- mypy checks THIS AT ANALYSIS TIME, using
      ...                                   the DECLARED type -- ZERO runtime enforcement
                                             (nothing stops you calling process("not a user")
                                              at runtime; mypy just won't have APPROVED it
                                              if it could see the call site statically)

  class UserModel(BaseModel):
      name: str                          <- Pydantic checks THIS AT RUNTIME, on ACTUAL
                                             DATA crossing a trust boundary (API request,
                                             config file, LLM tool-call args) -- genuinely
                                             REJECTS bad data with a ValidationError

  mypy = "does the CODE look internally consistent, statically, before running"
  Pydantic = "is this ACTUAL DATA, right now, valid, at a boundary I don't control"

NOMINAL vs STRUCTURAL TYPING:
  NOMINAL (class MyReadable(Readable): ...) -- must EXPLICITLY inherit
  STRUCTURAL (class Protocol): -- satisfied by HAVING the right shape, no inheritance
    class Duck:
        def read(self) -> bytes: ...
    def consume(r: Readable) -> None: ...   # Readable is a Protocol with .read()
    consume(Duck())   # TYPE-CHECKS FINE -- Duck never declared "class Duck(Readable)"

VARIANCE (why list[Dog] is NOT list[Animal], even though Dog IS-A Animal):
  COVARIANT   (output/read-only position):  Iterator[Dog] IS-A Iterator[Animal]  -- SAFE
  CONTRAVARIANT (input/consumer position):  Callable[[Animal],None] IS-A Callable[[Dog],None] -- SAFE
  INVARIANT   (both read AND write, e.g. list[T]): list[Dog] is NOT list[Animal] -- UNSAFE
    (if it WERE allowed: cats.append(Cat()) via a list[Animal] alias to an actual list[Dog]
     variable would silently put a Cat in a "list of Dogs" -- type safety violated)
```

The one-line mental model: **types are a static, erased-at-runtime communication and analysis tool; Pydantic is a runtime data-validation tool built on top of that same type syntax; Protocols make structural (duck-typed) shape checkable statically instead of only at runtime; and variance rules exist purely to prevent a substitution that would let you silently smuggle the wrong type into a container through an aliased reference.**

---

## How it actually works

### Types are erased: what this means concretely, and why it matters

CPython does not read type annotations to enforce anything at runtime by default — `def f(x: int) -> str: return x` runs without error and returns whatever `x` is, even if `x` is a string, a list, or `None`, because annotations are stored (accessible via `__annotations__`) but never consulted by the interpreter's actual execution machinery. This is precisely why type checking is a separate, offline static-analysis step (`mypy`, `pyright`, `ty`) run against your source code before execution, not a runtime property of the running program — and it's exactly why a `TypeError` at runtime from a *type-annotated* function is not "the type checker doing its job at runtime"; it's either an unrelated runtime bug, or evidence the code was run without ever being type-checked, or evidence a type-check failure was ignored. Any genuine runtime enforcement of "is this data actually the right shape" requires an explicit validation step — which is exactly the gap Pydantic (and `dataclasses` with manual `__post_init__` validation, or plain assertions) fills, deliberately, as a runtime concern layered on top of, not equivalent to, static type hints.

### Protocol: structural typing, and why it matches Python's actual runtime behavior

A `Protocol` class (subclassing `typing.Protocol`) defines a *shape* — a set of methods/attributes an object must have — and any object satisfying that shape type-checks as compatible, with zero requirement to explicitly inherit from the Protocol or even be aware it exists. This directly mirrors how Python's runtime duck typing already works (any object with a `.read()` method works anywhere code calls `.read()` on it, inheritance be damned) — before `Protocol` existed, expressing this statically required either an `ABC` with explicit inheritance (forcing every conforming class to know about and inherit from a specific abstract base, an artificial constraint that doesn't match how the code actually behaves at runtime) or giving up on static checking for this kind of interface entirely. `Protocol` is the correct tool specifically when you want to type-hint "anything with this shape," and `ABC`/nominal inheritance is the correct tool when you specifically want to enforce a shared, explicit lineage (often paired with genuine shared implementation via the base class, not just a shape contract).

### Generics and variance, derived from a concrete substitution-safety argument

A generic class or function's type signature depends on a placeholder (`TypeVar`, or Python 3.12+'s `class Stack[T]:` syntax) filled in per use. Variance answers: if `Dog` is a subtype of `Animal`, is `Container[Dog]` a subtype of `Container[Animal]`? The answer depends entirely on *how* the container is used:
- **Covariant** (`Iterator[Dog]` is safely a subtype of `Iterator[Animal]`): an iterator only ever *produces* values — if you only ever read `Animal`-typed values out of it, it doesn't matter that they're actually all `Dog`s, since every `Dog` genuinely is a valid `Animal` to receive. This is safe precisely because the type parameter only ever appears in output/return positions.
- **Contravariant** (`Callable[[Animal], None]` is safely a subtype of `Callable[[Dog], None]`): a function that can handle *any* `Animal` can certainly be used wherever a function handling only `Dog`s is expected (it handles a strictly larger set of inputs than required) — the reverse would be unsafe (a function only equipped to handle `Dog` cannot safely be used where any `Animal` might be passed). This is safe because the type parameter only appears in input/consumer positions.
- **Invariant** (default; `list[Dog]` is *not* a subtype of `list[Animal]`, in either direction): a mutable `list[T]` allows both reading and writing `T`-typed values — if `list[Dog]` were treated as a valid `list[Animal]`, code holding the `list[Animal]`-typed reference could legally `.append(Cat())` (a `Cat` genuinely is an `Animal`), silently inserting a `Cat` into what's actually, underneath, a `list[Dog]` at runtime — violating the invariant the original `list[Dog]` was supposed to guarantee. Because the type parameter appears in *both* read and write positions, no substitution direction is safe, which is exactly why mutable generic containers are invariant by default and immutable/read-only ones (like `Sequence[T]` or `Iterator[T]`) can be declared covariant.

### Pydantic v2: validation architecture and the v1 migration

Pydantic v2's validation logic runs through `pydantic-core`, a separate validation/serialization engine written in Rust that compiles each model's type annotations into a schema of composable validators, executed without the per-field Python-level overhead v1's pure-Python validation incurred — this is the direct source of the reported 5-50x speedup over v1, most pronounced on large, deeply-nested JSON payloads where v1's per-field Python overhead compounded the most ([Pydantic v2 announcement](https://pydantic.dev/articles/pydantic-v2) — accessed 2026-08-03). The migration from v1 to v2 changed real API surface, not just internals: validator decorators (`@validator` → `@field_validator`/`@model_validator`), config (`class Config:` inner class → `model_config = ConfigDict(...)`), serialization methods (`.dict()`/`.json()` → `.model_dump()`/`.model_dump_json()`), and stricter default validation behavior in several cases (v2 is less permissive about implicit type coercion in some scenarios than v1 was by default) — teams migrating a nontrivial v1 codebase should expect genuine, non-mechanical review of custom validators and config usage, not a pure find-and-replace. As of 2026, the `pydantic-core` Rust crate's development has been folded back into the main `pydantic` monorepo while remaining under active development ([pydantic-core GitHub](https://github.com/pydantic/pydantic-core) — accessed 2026-08-03).

### `TypeVar` scoping and the Python 3.12 generic syntax cleanup

Before Python 3.12, generics required explicitly declaring a `TypeVar` at module scope (`T = TypeVar('T')`) before using it in a `class Stack(Generic[T]):` or `def first(items: list[T]) -> T:` — functional, but verbose and prone to accidental `TypeVar` reuse/scoping confusion across unrelated generic definitions in the same module. PEP 695 (Python 3.12) introduced native generic syntax (`class Stack[T]:`, `def first[T](items: list[T]) -> T:`) that scopes the type parameter directly to the class/function definition, eliminating the separate module-level `TypeVar` declaration and the scoping ambiguity that came with reusing the same `TypeVar` name across different generic definitions in a codebase.

---

## Build it from scratch

```python
from typing import Protocol, TypeVar, Generic, Iterator

class Readable(Protocol):
    def read(self, size: int = -1) -> bytes: ...    # structural: ANY object with this method matches

def consume_all(source: Readable) -> bytes:
    return source.read()

class FileLike:                                      # never declares "class FileLike(Readable)"
    def read(self, size: int = -1) -> bytes:
        return b"structural typing works"

consume_all(FileLike())    # type-checks fine under mypy/pyright -- shape match, no inheritance


T = TypeVar('T')
T_co = TypeVar('T_co', covariant=True)      # for read-only/output positions
T_contra = TypeVar('T_contra', contravariant=True)   # for input/consumer positions

class ReadOnlyBox(Generic[T_co]):
    def __init__(self, value: T_co) -> None:
        self._value = value
    def get(self) -> T_co:                   # T_co ONLY appears in an output position -> safe to be covariant
        return self._value

class Stack(Generic[T]):                     # T appears in BOTH push (input) and pop (output) -> INVARIANT
    def __init__(self) -> None:
        self._items: list[T] = []
    def push(self, item: T) -> None:
        self._items.append(item)
    def pop(self) -> T:
        return self._items.pop()


# Python 3.12+ native generic syntax -- equivalent to the Stack class above, no TypeVar declaration needed
class Stack312[T]:
    def __init__(self) -> None:
        self._items: list[T] = []
    def push(self, item: T) -> None:
        self._items.append(item)
    def pop(self) -> T:
        return self._items.pop()


from pydantic import BaseModel, field_validator, ValidationError

class UserRequest(BaseModel):
    name: str
    age: int

    @field_validator("age")
    @classmethod
    def age_must_be_reasonable(cls, v: int) -> int:
        if not (0 <= v <= 150):
            raise ValueError("age out of plausible range")
        return v

try:
    UserRequest(name="Hari", age=200)
except ValidationError as e:
    print(e.errors())    # structured, machine-readable list of validation failures -- not just a string
```
The lab exercise runs `mypy --strict` against a deliberately variance-violating snippet (a function typed to accept `list[Animal]` called with an actual `list[Dog]` variable, then mutated by appending a `Cat`) to see mypy reject it at the call site, then fixes it by switching the parameter type to `Sequence[Animal]` (covariant, read-only) where mutation isn't needed — making the invariance/covariance tradeoff concrete rather than asserted, plus a benchmark comparing Pydantic v2 model validation throughput against an equivalent hand-written validation function on a batch of nested JSON payloads.

---

## How it's done in production

| Symptom | Cause | Fix |
|---|---|---|
| A function passes `mypy --strict` cleanly but crashes at runtime with a `TypeError` on bad input from an external API/user | Type hints are erased at runtime and were never actually enforced against the real incoming data — mypy only validated the code's internal consistency assuming the declared types were true | Add a genuine runtime validation layer (Pydantic model, explicit `isinstance` checks) at every trust boundary where data enters from outside your own type-checked code, not just internal function calls |
| `mypy` rejects a function call passing a `list[Dog]` where `list[Animal]` is the declared parameter type, even though the function never mutates the list | The parameter is typed as the invariant `list[Animal]` when the function's actual usage is read-only | Change the parameter type to `Sequence[Animal]` (covariant) or `Iterable[Animal]`, matching the function's true (read-only) usage instead of over-specifying with the invariant, mutation-permitting `list` type |
| A Pydantic v1-based codebase fails to import or raises deprecation errors after a naive `pip install --upgrade pydantic` | Pydantic v2 changed real API surface (`@validator` → `@field_validator`, `class Config` → `model_config`, `.dict()` → `.model_dump()`) — this isn't a drop-in upgrade | Use Pydantic's official migration guide and the `bump-pydantic` automated migration tool for the mechanical renames, but manually review custom validators and config for the v2 stricter-coercion behavior changes that automated tools can't safely infer |
| A large codebase's `mypy --strict` run takes minutes and slows CI meaningfully | `mypy`'s pure-Python implementation has genuine performance limits on very large codebases | Evaluate `pyright` or the newer Rust-based `ty` type checker for check-time performance, and use `mypy`'s incremental caching mode if staying on `mypy`, to avoid re-checking the entire codebase on every CI run |
| A `Protocol`-typed parameter accepts an object that "shouldn't" satisfy it, silently, according to a reviewer's expectations | Structural typing means *any* object with the right method signatures satisfies the `Protocol`, regardless of the object's actual semantic intent — this is working as designed, not a bug | If genuinely nominal, explicit-inheritance-based typing is intended (not just shape-matching), use an `ABC` instead of a `Protocol`, since `Protocol`'s entire point is permissive structural matching |

---

## Tradeoffs & when NOT to use it

- **Don't treat a `mypy --strict`-clean codebase as having runtime type safety.** Static type checking and runtime data validation solve different problems; any data crossing a trust boundary (API input, config files, deserialized data, LLM tool-call arguments) needs explicit runtime validation regardless of how clean the static type-checking result looks, since mypy's guarantees only hold if the *actual runtime data* matches the declared types, which mypy cannot verify for data it didn't statically trace.
- **Don't use `Protocol` when you specifically want to enforce a shared implementation or a deliberate, explicit lineage relationship, not just a shape match.** `ABC` (or plain inheritance) is the correct tool when you want subclasses to genuinely share behavior and explicitly opt into a contract, not merely happen to have matching method signatures.
- **Don't make a generic container covariant just because it would make a specific call site type-check more conveniently**, if the container genuinely supports mutation through that type parameter — this reintroduces the exact type-safety hole (silently inserting a wrong-subtype value through an aliased reference) invariance exists to prevent; only make something covariant if it's genuinely read-only in that position, or contravariant if genuinely write/consume-only.
- **Don't assume a Pydantic v1 codebase can be upgraded to v2 by simply bumping the version pin.** The real API changes (validator decorators, config, serialization methods) and the stricter default validation behavior mean a genuine migration effort — budget real review time for custom validators specifically, where automated migration tooling is least reliable.

---

## Interview questions

### Q1 — Why does a function with clean, fully-annotated type hints still raise a `TypeError` at runtime when called with bad data from an external API?
**Testing:** the erasure fact, stated precisely, and its production consequence.
**Answer:** Type annotations are not enforced by the CPython runtime by default — `mypy`/`pyright` check the code's internal consistency statically, assuming the declared types are accurate, but nothing in the running program verifies that assumption against actual incoming data unless something explicitly does so (a Pydantic model, an `isinstance` check). Data arriving from outside the type-checked codebase (an external API response, user input, a config file) has no guarantee of matching the declared types, so a runtime `TypeError` here reflects a missing *validation* layer, not a failure of the type checker, which was never designed to provide runtime enforcement in the first place.
**Follow-up trap:** *"If mypy 'passed,' doesn't that mean the code is provably free of type errors?"* — it means the code is free of type errors **under the assumption that every value actually has the type it was declared or inferred to have** — if that assumption is false anywhere (external data, an `Any`-typed escape hatch, a deliberately unsafe cast), mypy's guarantee simply doesn't extend to that portion of the program, and this gap is exactly where runtime validation earns its keep.

### Q2 — Explain structural versus nominal typing with a concrete example, and state precisely when `Protocol` is the wrong tool.
**Testing:** the actual distinction, plus recognizing Protocol's limits.
**Answer:** Nominal typing requires explicit inheritance/declaration (`class Duck(Readable):`) for a class to satisfy a type; structural typing (`Protocol`) is satisfied purely by having the right shape (method signatures), with zero inheritance required — a `Duck` class with a `.read()` method satisfies a `Readable` `Protocol` even if it never mentions `Readable` anywhere. `Protocol` is the wrong tool when you specifically need shared implementation or an explicit, intentional contract that shouldn't be satisfiable "by accident" — two unrelated classes that happen to both define a method named `close()` with a compatible signature but entirely different semantic meaning would both satisfy a `Closeable` Protocol even if that's not actually desired, which an `ABC`'s explicit-inheritance requirement would prevent.
**Follow-up trap:** *"Could two completely unrelated classes accidentally satisfy the same Protocol without either author intending it, and is that actually a problem in practice?"* — yes, this can happen (e.g., a class with a coincidental `.close()` method for an unrelated reason satisfying a `Closeable` Protocol) — whether it's a practical problem depends on how generic/common the method name and signature are; for a Protocol with a distinctive, multi-method shape, accidental satisfaction is rare in practice, but for a Protocol built around one very common method name, this is a real, if usually harmless, possibility worth being aware of when choosing Protocol versus ABC for a given interface.

### Q3 — Derive, with a concrete unsafe scenario, why `list[T]` must be invariant while `Iterator[T]` can safely be covariant.
**Testing:** the actual substitution-safety argument, not a memorized rule.
**Answer:** If `list[Dog]` were treated as a valid substitute for `list[Animal]` (covariant), code holding that `list[Animal]`-typed reference could legally call `.append(Cat())` (since a `Cat` genuinely satisfies `Animal`), silently inserting a `Cat` into what is, underneath, an actual `list[Dog]` — violating the invariant the original variable's true type was supposed to guarantee, a genuine type-safety hole. `Iterator[T]` only ever *produces* `T`-typed values (no `.append`-equivalent that accepts a `T` as input) — so `Iterator[Dog]` can safely substitute for `Iterator[Animal]`, since every value it ever yields (a `Dog`) is validly usable wherever an `Animal` is expected, with no way to insert a wrong-subtype value through it.
**Follow-up trap:** *"Why does typing.Sequence[T] get to be covariant while list[T] (which is also indexable/iterable) is invariant?"* — `Sequence` is explicitly the read-only supertype of `list` in the typing hierarchy — it excludes mutating operations like `.append()`, so it only exposes `T` in output positions, making covariance safe; `list` includes mutation, so it must remain invariant — this is precisely why the standard idiom for a function that only reads from a list parameter is to type it as `Sequence[T]` rather than `list[T]`, gaining safe covariant substitutability by declaring only the capability actually needed.

### Q4 — Why is `Callable[[Animal], None]` a safe substitute for `Callable[[Dog], None]`, and why does this direction feel counterintuitive at first?
**Testing:** contravariance, precisely, and its intuition-defying direction.
**Answer:** A `Callable[[Animal], None]` (a function accepting any `Animal`) can safely be used wherever a `Callable[[Dog], None]` is expected, because it can handle everything a `Dog`-only-accepting function can handle, and more — every actual call site expecting to pass a `Dog` remains satisfied. The reverse (using a `Dog`-only function where any `Animal` might be passed) would be unsafe, since a `Cat` passed to it would violate its `Dog`-only assumption. This feels counterintuitive because it inverts the "more specific is safer" intuition that holds for covariant positions — for function *parameters* specifically, accepting a *broader* set of inputs is what makes a substitution safe, the opposite direction from output/return-type substitutability.
**Follow-up trap:** *"Does this mean a function type with BOTH a parameter and a return type should be treated as both covariant and contravariant simultaneously?"* — yes, exactly — `Callable[[Arg], Ret]` is contravariant in `Arg` (input position) and covariant in `Ret` (output position) simultaneously, which is a real, correctly-modeled case of mixed variance within a single generic type, not a contradiction — Python's type system does model this correctly for `Callable`, and it's worth being able to state both halves precisely rather than just picking one.

### Q5 — What specific problem does Pydantic solve that plain Python type hints alone do not, even under `mypy --strict`?
**Testing:** the static-versus-runtime distinction applied specifically to Pydantic's value proposition.
**Answer:** Type hints alone provide zero runtime enforcement — they're erased and unchecked unless something explicitly validates against them. Pydantic provides genuine runtime data validation: given actual incoming data (a JSON request body, a config file, deserialized data of unknown provenance), it checks that data really does conform to the declared model shape and types, coercing where reasonable and raising a structured `ValidationError` with precise, machine-readable failure details when it doesn't — solving the "is this actual data trustworthy" problem that static type checking, by design, cannot address for data whose origin is outside the statically-analyzed code.
**Follow-up trap:** *"If Pydantic validates at runtime, doesn't that make plain type hints and mypy redundant once you're using Pydantic everywhere?"* — no; Pydantic validates data specifically at the boundaries where it's applied (model instantiation), while `mypy`/type hints continue to provide value for *all* the internal code between those boundaries — catching passing a `str` where an `int` was expected in ordinary internal function calls, refactoring safety, and IDE support — Pydantic and static type checking are complementary, addressing different layers (data-boundary validation versus internal code consistency), not substitutes for each other.

### Q6 — What are the three concrete, non-cosmetic API changes a team must handle when migrating a real Pydantic v1 codebase to v2, and why can't this be a pure find-and-replace?
**Testing:** genuine familiarity with the migration's substance, not just "there was a big version bump."
**Answer:** Validator decorators changed (`@validator` → `@field_validator`/`@model_validator`, with different signature conventions), configuration changed (the inner `class Config:` pattern → a `model_config = ConfigDict(...)` class attribute), and serialization method names changed (`.dict()`/`.json()` → `.model_dump()`/`.model_dump_json()`). It can't be a pure find-and-replace because v2 also changed default validation strictness in several cases (less permissive implicit type coercion than v1's default behavior), meaning some code that worked correctly under v1's more lenient defaults may now raise validation errors it didn't before, requiring genuine review of custom validator logic and any code relying on v1's specific coercion behavior, not just mechanical renaming.
**Follow-up trap:** *"Is there tooling that automates this migration, and how far can you trust it?"* — yes, `bump-pydantic` (an official-ecosystem automated migration tool) handles much of the mechanical renaming reliably, but it cannot safely infer intent behind custom validator logic that depended on v1's specific coercion behavior — the mechanical rename portion is trustworthy to automate, while the semantic-behavior-change portion (stricter validation defaults) requires manual review and testing, and treating the whole migration as "just run the tool" risks silently introducing new validation failures in production that weren't caught by an incomplete test suite.

### Q7 — Why did Python 3.12's native generic syntax (`class Stack[T]:`) get introduced when `TypeVar`-based generics already worked?
**Testing:** understanding the specific pain point (module-level scoping) the new syntax addresses, not just "it's shorter."
**Answer:** Pre-3.12 generics require declaring a `TypeVar` at module scope (`T = TypeVar('T')`) before use, and that same module-level `TypeVar` object could be (and often was) reused across multiple, semantically-unrelated generic class/function definitions in the same module, creating a real scoping ambiguity risk — nothing prevented accidentally using the same `TypeVar` in contexts that should be treated as logically distinct type parameters. PEP 695's native syntax (`class Stack[T]:`, `def first[T](...):`) scopes `T` directly to that specific class or function definition, eliminating both the separate declaration boilerplate and the cross-definition reuse ambiguity entirely.
**Follow-up trap:** *"Does adopting the new 3.12 syntax change anything about variance declarations (covariant=True/contravariant=True)?"* — the new syntax still needs a mechanism to express variance where required (PEP 695 supports inferring variance automatically in many cases based on how the type parameter is actually used within the class, reducing the need to explicitly declare `covariant=True`/`contravariant=True` as often as the old `TypeVar`-based syntax required) — but explicit variance annotation is still available and sometimes still necessary when the automatic inference doesn't match the intended usage, so the new syntax simplifies but doesn't entirely eliminate variance as an explicit concept engineers need to understand.

### Q8 — A code reviewer flags a function parameter typed as `list[Animal]` because the caller is passing an actual `list[Dog]]` variable, and mypy rejects the call. The function body never mutates the list. What's the fix and why does it work?
**Testing:** applying the covariance/invariance distinction to a concrete, realistic mypy error.
**Answer:** Change the parameter's declared type from `list[Animal]` to `Sequence[Animal]` (or `Iterable[Animal]` if no indexing is needed) — `Sequence` is the read-only, covariant supertype in the typing hierarchy, so `Sequence[Dog]` (which `list[Dog]` satisfies) is a valid substitute for `Sequence[Animal]`, correctly reflecting that the function only reads from the collection and never needs `list`'s mutating capability that made the original `list[Animal]` parameter type invariant and therefore incompatible with a `list[Dog]` argument.
**Follow-up trap:** *"What if the function DOES need to call .append() on the parameter, just never with anything other than the original element type?"* — then `list[Animal]` genuinely is the correct type (mutation requires invariance, no way around it safely), and the caller passing a `list[Dog]` is a genuine type error that mypy is correctly catching, not a false positive to be "fixed" by loosening the type — the correct resolution in that case is for the caller to either pass a genuinely `list[Animal]`-typed list, or for the function's design to be reconsidered if it shouldn't actually need to accept arbitrary `Animal` subtypes for mutation.

### Q9 — Why is Pydantic v2's Rust-based `pydantic-core` meaningfully faster than v1's pure-Python validation specifically for large, deeply-nested JSON payloads?
**Testing:** connecting the architectural change (compiled core, schema-based validators) to the specific workload where the speedup is most pronounced.
**Answer:** v1's validation logic ran per-field Python code with real per-call interpreter overhead (function call overhead, dynamic dispatch, Python-level type checking) that compounds significantly across deeply-nested structures with many fields — v2 compiles each model's type annotations once into a schema of composable Rust validators executed largely outside the Python interpreter's per-field overhead, so the relative speedup grows with how much per-field validation work there is to do, which is exactly why large, deeply-nested payloads show the largest reported gains (5-50x depending on workload) versus simpler, shallow models where the relative overhead being eliminated is smaller to begin with.
**Follow-up trap:** *"Does this mean Pydantic v2 validation has effectively zero runtime cost regardless of model complexity?"* — no; it's dramatically faster than v1, not free — validation cost still scales with the amount and complexity of data being validated, and a genuinely enormous or extremely deeply-nested payload will still take measurably longer to validate than a small one, even under v2's compiled core — "much faster than v1" and "effectively free" are different claims, and conflating them risks under-provisioning for validation cost in a genuinely high-throughput or large-payload production service.

### Q10 — Design question: you're building a library function that should accept "anything file-like" as an argument (has `.read()` and `.close()`), used by many different callers across a large codebase, some of whom you don't control. Would you type this parameter with a `Protocol` or require inheritance from an `ABC`, and why?
**Testing:** staff-level judgment applying structural-vs-nominal typing tradeoffs to a realistic library-design decision.
**Answer:** `Protocol` — since the function only genuinely needs "an object with `.read()` and `.close()` methods of the right signature," not any specific shared implementation or explicit lineage, a `Protocol` lets any caller pass a compatible object (a real file, a `BytesIO`, a custom test double, a third-party library's file-like object) without needing to modify that object's class to explicitly inherit from your library's base class — which matters specifically because some callers are outside your control and can't be expected to retrofit inheritance from your specific `ABC` just to satisfy your function's type signature. This mirrors exactly how Python's actual runtime duck-typing already permits calling `.read()`/`.close()` on any object with those methods, regardless of its actual class hierarchy.
**Follow-up trap:** *"If you later need to add a genuinely shared default implementation (e.g., a mixin providing a default `.close()` that calls `.read()` internally for cleanup), does Protocol still work?"* — no, not for that specific need; `Protocol` only describes a shape, it provides no mechanism for shared implementation code to be inherited — if genuine shared behavior (not just a shape contract) is needed, that requires an actual base class (possibly an `ABC`) that callers explicitly inherit from to get the shared implementation, which is a fundamentally different requirement than type-checking compatibility alone, and conflating "I want type compatibility" with "I want shared implementation" is exactly the mistake this question is designed to catch.

---

## Red flags that fail you

- Believes a `mypy --strict`-clean codebase has runtime type enforcement, or can't explain that types are erased at runtime.
- Cannot explain the difference between structural (`Protocol`) and nominal (`ABC`) typing with a concrete example.
- Cannot derive why mutable generic containers must be invariant, using an actual unsafe-substitution scenario, not just stating the rule.
- Confuses covariance and contravariance direction, especially for function parameter types.
- Treats a Pydantic v1-to-v2 upgrade as a simple version bump with no real migration effort.
- Cannot articulate what problem Pydantic solves that static type hints alone do not.

---

## Cheat card

```
TYPES ARE ERASED AT RUNTIME: mypy/pyright check STATICALLY, assuming declared types are
  true -- ZERO runtime enforcement unless something explicitly validates (Pydantic,
  isinstance). "mypy passed" != "runtime data is guaranteed correct" for external data.

PROTOCOL (PEP 544, 3.8+) = STRUCTURAL typing: satisfied by SHAPE (right methods/attrs),
  NO inheritance required -- matches Python's actual runtime duck typing
  ABC = NOMINAL typing: requires EXPLICIT inheritance -- use when you need shared
  implementation or a deliberate, non-accidental contract

VARIANCE (why list[Dog] is NOT list[Animal] even though Dog IS-A Animal):
  COVARIANT (output/read-only, e.g. Iterator[T], Sequence[T]): Dog-typed IS-A Animal-typed
    -- safe, T only ever PRODUCED
  CONTRAVARIANT (input/consumer, e.g. Callable[[T],R] in T): Callable[[Animal],_] IS-A
    Callable[[Dog],_] -- safe, handles a BROADER input set than required
  INVARIANT (default; BOTH read+write, e.g. list[T]): no substitution either direction --
    covariant list would let .append(Cat()) via an aliased list[Animal] ref smuggle a
    Cat into an actual list[Dog] -- type safety violated
  Callable[[Arg],Ret]: CONTRAVARIANT in Arg, COVARIANT in Ret, simultaneously

PYTHON 3.12 (PEP 695): class Stack[T]: / def first[T](...): -- scopes T to the definition,
  no module-level TypeVar declaration, avoids cross-definition TypeVar reuse ambiguity
  often auto-infers variance from usage, but explicit variance still sometimes needed

PYDANTIC != TYPE HINTS: Pydantic validates ACTUAL DATA at RUNTIME at a trust boundary
  (API request, config, LLM tool-call args) -- complementary to, not redundant with, mypy
PYDANTIC V2: core rewritten in Rust (pydantic-core) -- 5-50x faster than v1, most
  pronounced on large/deeply-nested JSON (per-field Python overhead eliminated)
  V1->V2 migration is REAL: @validator->@field_validator/@model_validator,
  class Config->model_config=ConfigDict(...), .dict()/.json()->.model_dump()/.model_dump_json()
  + STRICTER default coercion in v2 -- bump-pydantic automates renames, NOT behavior review
```

## Sources

- [PEP 484 — Type Hints](https://peps.python.org/pep-0484/) — accessed 2026-08-03
- [PEP 544 — Protocols: Structural subtyping (static duck typing)](https://peps.python.org/pep-0544/) — accessed 2026-08-03
- [PEP 695 — Type Parameter Syntax](https://peps.python.org/pep-0695/) — accessed 2026-08-03
- [Introducing Pydantic V2 — pydantic.dev](https://pydantic.dev/articles/pydantic-v2) — accessed 2026-08-03
- [pydantic-core — GitHub](https://github.com/pydantic/pydantic-core) — accessed 2026-08-03
- [Pydantic: Migration Guide — official documentation](https://docs.pydantic.dev/latest/migration/) — accessed 2026-08-03
- [mypy documentation: Protocols and structural subtyping](https://mypy.readthedocs.io/en/stable/protocols.html) — accessed 2026-08-03

## Changelog
- 2026-08-03 — created
