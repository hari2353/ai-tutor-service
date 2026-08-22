# Rust: Traits, Generics, Enums, Pattern Matching, Error Handling (Result/?)

> **Track:** T20 Rust · **Time:** 2.5h · **Prereqs:** `T20-rust-ownership` (ownership, borrowing, lifetimes assumed known) · **Updated:** 2026-08-05
> **Module id:** `T20-rust-types` · **Tags:** core, critical, type-system

## The 30-second version

Rust's type system is what you actually get in exchange for paying the borrow-checker tax: traits give you Java-style interfaces that you can retroactively implement on types you don't own, with the default being *static* dispatch via monomorphisation (one specialised machine-code copy per concrete type, zero indirection, fully inlinable) rather than Java's or Go's always-virtual calls. Sum types are first-class, which is why `Option<T>` and `Result<T, E>` are ordinary library enums in `core` rather than compiler magic, and why `match` exhaustiveness turns "we added a new variant" from a runtime `NullPointerException` into a compile error at every site that needs updating. Error handling is `Result<T, E>` plus the `?` operator, which desugars to an early return with a `From::from` conversion, so error types compose by declaring `impl From<Io> for MyError` once instead of writing conversion code at every call site. The rule of thumb that survives follow-ups: `thiserror` (2.0.19) in libraries because callers need to `match` on your variants, `anyhow` (1.0.104) in applications and binaries because nobody matches on a `main()` error, and `unwrap()` in a published library is a bug because it converts your caller's recoverable condition into their unrecoverable process abort. Reach for `dyn Trait` when you need heterogeneous collections or want to stop the binary growing, and reach for generics everywhere else, but measure with `cargo llvm-lines` and `cargo bloat` before claiming either is faster.

## Why this gets asked

Because ownership is the part of Rust everyone talks about and the type system is the part that decides whether a codebase is maintainable at 200k lines. An interviewer probing traits and generics is checking whether you understand *dispatch* well enough to make a design decision that's expensive to reverse: a public API that takes `impl Read` and one that takes `&mut dyn Read` are not interchangeable, and flipping between them after downstream crates depend on you is a semver-major break. The person asking has almost certainly lived through one of three specific failures. First: a compile time that crept from 40 seconds to 9 minutes because a heavily generic function was instantiated across dozens of types and nobody ran `cargo llvm-lines` until it hurt. Second: an `error[E0038]` wall on day three of a refactor, when someone tried to put `Box<dyn Storage>` in a config struct and discovered `Storage` had a generic method, so the whole trait had to be redesigned. Third, and most common in production: a library dependency that called `.unwrap()` on a parse of user-controlled input, which turned a 400-able request into a panic that unwound through a Tokio worker and either killed a task silently or, under `panic = "abort"`, took the whole process down. They ask because these are all *type-design* decisions made in week one that bill you in month six.

---

## Lineage: past → present → future

**What came before.** Two lineages collide here. On the polymorphism side, C++ templates (1990, standardised 1998) proved that compile-time monomorphisation gives you zero-overhead generic code, and also proved the cost: templates were duck-typed, so a type that failed to satisfy an unstated requirement produced errors *inside* the template body, and the resulting multi-page instantiation-backtrace error messages were a running industry joke for two decades. C++ Concepts (proposed 2003, cut from C++0x in 2009, finally shipped in C++20 in 2020) took seventeen years to fix exactly this. Java went the opposite way in Java 5 (2004): generics implemented by *erasure*, where `List<String>` and `List<Integer>` are the same class at runtime, casts are inserted by the compiler, and primitives must be boxed, so `ArrayList<Integer>` of 1,000,000 elements is 1,000,000 heap-allocated `Integer` objects with pointer chasing rather than a 4 MB contiguous `int` buffer. Erasure also meant you could not implement an interface for a type you did not own: if `java.lang.String` doesn't implement your `Serializer`, your options were a wrapper class or a visitor. Haskell type classes (Wadler and Blott, POPL 1989) had already solved the retroactive-implementation problem correctly, with dictionary passing and coherence, and Rust's traits are more or less type classes with the dictionaries specialised away. On the error side, the pain that killed the alternatives is precise: C's `errno`/return-code convention loses errors silently when a caller forgets the check, and Java's checked exceptions (1995) were an honest attempt at type-level error tracking that the ecosystem defeated in practice, because `catch (Exception e) {}` and `throws Exception` are one keystroke each, and the language gave you no way to *convert* an error to your own type without writing the wrapping code by hand. Go's `if err != nil { return nil, err }` (2009) restored explicitness at the cost of roughly 3 lines per call site and no compile-time enforcement that you checked at all until `errcheck` and vet caught up.

**Where it stands now.** Rust 1.97.1 (released 2026-07-16) ships a type system that is genuinely settled at the core and actively moving at the edges. Settled: traits with static dispatch by default, monomorphisation, associated types, blanket impls, the orphan rule and coherence, algebraic data types with exhaustive `match`, and `Result` + `?`. `core::error::Error` was stabilised in Rust 1.81 (2024-09-05), which finally let `no_std` and `std` crates agree on one error trait after roughly six years of the ecosystem maintaining polyfill crates. The `thiserror`-for-libraries / `anyhow`-for-applications split (both by dtolnay; thiserror 2.0 landed November 2024, currently 2.0.19 as of 2026-07-18; anyhow currently 1.0.104) is as close to consensus as the Rust ecosystem gets, and both crates together see north of 100 million downloads a year. The live disagreements are real and worth naming rather than papering over. The first is `dyn` versus generics as an API default: the "monomorphisation is free" position is empirically false for compile times and binary size, and there is a genuine faction (Raph Levien's 2019 "Thoughts on Rust bloat" is the canonical write-up, and the Rust standard library's own source is full of the `fn outer<P: AsRef<Path>>(p: P) { inner(p.as_ref()) }` de-monomorphisation trick) that argues public APIs should take `&dyn` more often than they do. The second is whether `anyhow` belongs anywhere near a library: the strict reading says a library that returns `anyhow::Error` has made every one of its errors unmatched-on and unhandleable, and the pragmatic reading says for an internal service crate that nobody outside your org depends on, it saves real time. The third, and the most technically contested, is error *enums* versus error *boxes*: a large `thiserror` enum with 40 variants is exhaustive and matchable but becomes a semver liability (every new variant is a breaking change unless you remember `#[non_exhaustive]`) and inflates `size_of::<Result<T, E>>()` to the size of its largest variant, which is why `Box<MyError>` in the `Err` arm shows up in hot-path code. What is actually deployed at scale, as opposed to merely argued about on internals.rust-lang.org: enum-based errors with `thiserror`, generics everywhere by default, `dyn` used deliberately at plugin boundaries and for heterogeneous collections, and `Arc<dyn Trait + Send + Sync>` as the near-universal shape for injected dependencies in async services.

**Where it's heading.** High confidence: nothing about the core trait/generics/enum surface will change under you. The Rust 2024 edition (stable since 1.85, 2025-02-20) made a handful of deliberate *restrictions* rather than additions, notably the match-ergonomics reservations from the RFC 3627 line of work, which now make it an error to write `mut`, `ref`, or `ref mut` on a binding when the default binding mode is not `move`. That was explicitly a conservative "reserve the syntax now, decide the semantics later" move, so more match-ergonomics changes are coming, but in a future edition and behind a migration lint, not silently. Medium-high confidence: trait upcasting, stabilised in Rust 1.86 (2025-04-03), unblocks the `dyn Sub -> dyn Super` coercion that people previously faked with a `fn as_any(&self) -> &dyn Any` method on every trait, and expect that pattern to disappear from new code. Medium confidence: const generics keep expanding. `min_const_generics` shipped in 1.51 (2021-03-25) and covers `struct Matrix<const N: usize>`, but `generic_const_exprs` (writing `[T; N + 1]`) has been unstable and explicitly marked incomplete for about five years, and the project's current 2026 goal is `min_generic_const_args` as a smaller stabilisable slice rather than the full feature. Do not plan a design around `N + 1` working on stable. Low confidence, explicitly speculative: `async fn` in traits has been stable for static dispatch since Rust 1.75 (2023-12-28), but `dyn`-compatible async traits are still not a thing on stable in August 2026, which is why `#[async_trait]` (which boxes every call into a `Pin<Box<dyn Future + Send + '_>>`, costing one heap allocation per invocation) is still in most async codebases. The `async fn in dyn Trait` work is on the async initiative roadmap with no stabilisation date; treat "it'll land soon" as unsupported. Also explicitly speculative: specialization (RFC 1210, opened 2015) has been unstable for over a decade with known soundness holes around lifetime-dependent specialisation, and I would not tell an interviewer it is close.

---

## Mental model

```
THE TWO AXES. Every polymorphism decision in Rust is a point on this grid.

                     STATIC (generics)          DYNAMIC (dyn Trait)
  what you write     fn f<T: Draw>(x: &T)       fn f(x: &dyn Draw)
  what's emitted     one copy per concrete T    exactly one copy, ever
  call cost          direct call, inlinable     load fn ptr from vtable,
                                                 indirect call, no inline
  pointer size       thin: 8 bytes (64-bit)     fat: 16 bytes
                                                 (data ptr + vtable ptr)
  binary size        n_types x body_size        body_size
  compile time       grows with instantiations  flat
  heterogeneity      NO. Vec<T> is one T.       YES. Vec<Box<dyn Draw>>
                                                 holds mixed types.
  requires           T: Sized (implicit)        the trait to be
                                                 dyn-compatible

  THE DEFAULT IS STATIC. You opt into dynamic, and you opt in for a
  reason: heterogeneous collection, plugin boundary, or measured bloat.


THE FAT POINTER. This is the whole of dynamic dispatch:

   let d: &dyn Draw = &circle;

   d ──┬──> [ data pointer ] ────> Circle { r: 2.0 }      (the value)
       └──> [ vtable ptr   ] ────> ┌──────────────────┐
                                   │ drop_in_place fn │   (how to drop it)
                                   │ size: 8          │   (usize)
                                   │ align: 8         │   (usize)
                                   │ Draw::draw  fn   │   (one slot per
                                   │ Draw::area  fn   │    dispatchable
                                   └──────────────────┘    method)
   The vtable is generated once per (concrete type, trait) pair and
   lives in .rodata. Layout is NOT stable/guaranteed - don't transmute it.
   A method call is: load slot, indirect call. Cheap; the real cost is
   that LLVM can no longer inline through it.


TRAIT vs JAVA INTERFACE vs GO INTERFACE - the three-way framing:

  Java interface: nominal, declared at the type's definition site.
                  You CANNOT make String implement your interface.
                  Always virtual dispatch (modulo JIT devirtualisation).
                  Generics erased -> boxing, no Vec<i32> equivalent.

  Go interface:   STRUCTURAL and implicit. A type satisfies it by
                  having the methods; nobody writes "implements".
                  Always a 2-word fat pointer - same shape as dyn Trait.
                  Accidental conformance is possible, and method-name
                  collisions across interfaces are a real hazard.

  Rust trait:     NOMINAL and explicit (`impl Draw for Circle`), but
                  the impl can live in EITHER crate (subject to the
                  orphan rule), so retroactive implementation works.
                  Static by default, dynamic on request.
                  Two traits can have a method with the same name and
                  you disambiguate with `Draw::area(&x)` / UFCS.


SUM TYPES. The thing Java/Go structurally lack:

  enum Shape { Circle { r: f64 }, Rect { w: f64, h: f64 } }
       ^ this is ONE type whose value is EXACTLY ONE of these,
         with the payload attached to the variant, and the compiler
         knows the list is closed.

  Layout: tag (discriminant) + max(payload sizes), padded to align.
  size_of::<Shape>() == 24 on 64-bit: 8 tag + 16 for Rect's two f64s.

  NICHE OPTIMISATION - why Option isn't a tax:
    size_of::<Option<&T>>()          == 8   (null is the None niche)
    size_of::<Option<Box<T>>>()      == 8
    size_of::<Option<NonZeroU32>>()  == 4   (0 is the niche)
    size_of::<Option<u8>>()          == 2   (u8 has no spare niche,
                                             so a real tag byte + pad)


ERROR FLOW. `?` is one desugaring, memorise it:

    let n = parse(s)?;
       becomes (for Result, modulo the unstable Try trait):
    let n = match parse(s) {
        Ok(v)  => v,
        Err(e) => return Err(From::from(e)),
    };
                          ^^^^^^^^^^ THE WHOLE POINT.
    Your fn's error type only needs `impl From<TheirError> for MyError`
    ONCE, and every `?` in every function converts for free.
```

---

## How it actually works

### Monomorphisation: what the compiler literally emits

A generic function is not a function. It is a template that the compiler stamps out once per distinct set of concrete type arguments actually used, during the monomorphisation collection pass that runs after type checking and before codegen.

```rust
fn largest<T: PartialOrd + Copy>(items: &[T]) -> T {
    let mut best = items[0];
    for &x in items { if x > best { best = x; } }
    best
}

fn main() {
    println!("{}", largest(&[1i32, 5, 3]));
    println!("{}", largest(&[1.5f64, 0.2]));
}
```

After monomorphisation the compiler has produced two independent functions, roughly `largest_i32(&[i32]) -> i32` and `largest_f64(&[f64]) -> f64`, each with the comparison compiled down to the concrete `cmp` instruction for that type, each independently inlinable, each independently vectorisable. There is no dispatch at runtime, no vtable, and no boxing. This is the thing Java cannot do: `T` in Java is `Object` at runtime, so `largest` on a `List<Integer>` is a chain of pointer dereferences and `compareTo` virtual calls on boxed objects.

The bill arrives in three places, and knowing all three is the difference between a mid-level and a staff answer.

Code size is the obvious one. If the body compiles to `n` bytes and you instantiate it for `m` types, you get roughly `n × m` bytes. That is fine for a 30-byte body and catastrophic for a 4 KB body called with 60 types, which is exactly the shape of a serialisation layer. A stripped `--release` "hello world" on x86-64 Linux is typically 300-400 KB, dominated by `std`'s formatting and panic machinery; the same binary with `opt-level = "z"`, `lto = true`, `codegen-units = 1`, and `panic = "abort"` typically lands under 100 KB, and most of that delta is monomorphised generic code that LTO can now see is dead.

Compile time is the one that actually causes standups. Each instantiation is separate LLVM IR that must be optimised separately. This is why a crate can sit at 40 seconds for a year and then jump to 9 minutes after someone adds a generic parameter to a widely-called function.

Instruction cache pressure is the one people forget. Sixty copies of the same 4 KB loop, each hot in a different code path, evict each other from the L1 instruction cache (typically 32 KB on a modern x86-64 core). A single `dyn` copy that stays resident can beat sixty specialised copies that thrash, which is the entire counter-argument to "static dispatch is always faster."

### Measuring it, rather than asserting it

Three tools, in the order you should reach for them.

`cargo llvm-lines --release` prints LLVM IR line counts per function, aggregated across instantiations, sorted descending. This is the single most useful monomorphisation-bloat instrument, because it shows you *which generic function* and *how many copies*. Output looks like `Lines Copies Function name` with entries such as `112000 (4.1%) 380 core::iter::adapters::map::Map<...>::next`. Anything with more than ~100 copies of a non-trivial body is a candidate for the inner-function trick below.

`cargo bloat --release --crates` attributes the final binary's `.text` section to crates, and `cargo bloat --release -n 30` to individual symbols. Use it to answer "did my change actually shrink the binary," not to find the cause.

`cargo build --timings` emits an HTML flamegraph of per-crate compile time including the codegen split, which tells you whether your 9-minute build is monomorphisation or just too many dependencies.

For runtime, `criterion` with `black_box` around the input, and `perf stat -e instructions,branch-misses,L1-icache-load-misses` on the two builds. The specific counter that distinguishes "dyn is slow because of the indirect call" from "dyn is slow because inlining died" is `branch-misses`: an indirect call whose target is stable is predicted correctly by the indirect branch target buffer and costs a handful of cycles, while a megamorphic call site (many different concrete types flowing through the same `dyn` call) mispredicts and costs roughly 15-25 cycles on modern x86-64. In almost every real benchmark I have seen argued about, the dominant cost of `dyn` is not the indirect call at all; it is that LLVM cannot inline through it, so constant propagation, loop unrolling, and auto-vectorisation all stop at that boundary.

### The de-monomorphisation trick the standard library uses on itself

```rust
// This is (a simplification of) what std::fs::read actually does.
pub fn read<P: AsRef<Path>>(path: P) -> io::Result<Vec<u8>> {
    fn inner(path: &Path) -> io::Result<Vec<u8>> {
        // ... 60 lines of real work, compiled EXACTLY ONCE ...
        # unimplemented!()
    }
    inner(path.as_ref())
}
```

The generic wrapper is a two-line body that gets monomorphised for `&str`, `String`, `PathBuf`, `&Path`, `Cow<'_, Path>`, and anything else callers pass. The 60-line body is a single non-generic function with one copy in the binary. Callers keep the ergonomic `read("foo.txt")` API; the binary keeps one copy of the logic. This pattern belongs in any public generic function whose body is larger than a few dozen instructions.

### Dynamic dispatch, and exactly what a `dyn` value is

`dyn Trait` is an unsized type (`!Sized`), which is why you always see it behind a pointer: `&dyn Trait`, `&mut dyn Trait`, `Box<dyn Trait>`, `Rc<dyn Trait>`, `Arc<dyn Trait>`. Those pointers are *fat*: 16 bytes on a 64-bit target instead of 8, carrying the data pointer plus a pointer to a statically-generated vtable. You can confirm this in five lines:

```rust
use std::mem::size_of;
trait Draw { fn draw(&self); }
fn main() {
    assert_eq!(size_of::<&u32>(), 8);            // thin
    assert_eq!(size_of::<&dyn Draw>(), 16);      // fat
    assert_eq!(size_of::<Box<dyn Draw>>(), 16);  // also fat
    assert_eq!(size_of::<&[u32]>(), 16);         // slices are fat too:
                                                  // ptr + length
}
```

The vtable is emitted once per `(concrete type, trait)` pair into read-only data and contains, in the current implementation, a destructor pointer, the value's size, its alignment, and then one slot per dispatchable method. That layout is an implementation detail and explicitly not guaranteed, so any code that transmutes a trait object to inspect it is relying on unspecified behaviour and will break.

Note what this buys you that generics cannot: a `Vec<Box<dyn Draw>>` can hold a `Circle`, a `Square`, and a `Text` simultaneously. `Vec<T>` where `T: Draw` cannot; every element is the same `T`. If your requirement is a heterogeneous collection, generics are not an alternative you rejected, they are a thing that does not work.

### Dyn compatibility (the artist formerly known as object safety)

Not every trait can become a trait object. The compiler calls the property "dyn compatibility" now, renamed from "object safety" because the old name talked about objects when the property is entirely about traits; you will still see `error[E0038]` and older docs and Stack Overflow answers using "object safe," and both terms mean the same thing. The rules, from the Rust Reference:

A trait is dyn compatible if it has no `Self: Sized` supertrait bound, all its supertraits are themselves dyn compatible, it has no associated constants, it has no associated types with their own generic parameters, and every method is either *dispatchable* or explicitly excluded with `where Self: Sized`.

A method is dispatchable only if it has no generic type parameters (lifetime parameters are fine), does not mention `Self` anywhere except as the receiver type, has a receiver from the allowed set (`&self`, `&mut self`, `self: Box<Self>`, `self: Rc<Self>`, `self: Arc<Self>`, `self: Pin<P>` and a few more), and does not carry `where Self: Sized`.

Every one of those clauses exists for a mechanical reason, and being able to derive them from the fat-pointer diagram is the staff-level answer:

- **No generic methods.** A vtable is a fixed-size array of function pointers built at compile time. A generic method would need one slot per instantiation, and the set of instantiations is not known when the vtable is emitted. There is no finite table to build.
- **No `Self` in return position.** `fn clone(&self) -> Self` is exactly why `Clone` is not dyn compatible: the caller holding a `&dyn Clone` does not know the size of the returned value, so it cannot allocate a slot for it. This is also why `Copy`, `Sized`, `From`, and `Into` are all dyn incompatible.
- **No `Self` in argument position (other than the receiver).** `fn eq(&self, other: &Self) -> bool` on `PartialEq` means a `dyn PartialEq` would let you compare a `Circle` to a `String` through the same vtable slot, which is not type-correct. Hence no `dyn PartialEq`, no `dyn Ord`.
- **No associated constants.** Constants are not function pointers and there is nowhere in the calling convention to put them.

The escape hatch is `where Self: Sized` on the offending method, which makes that method invisible on trait objects while keeping it available on concrete types. This is exactly how `Iterator` manages to be dyn compatible despite having about 75 provided methods, many of them generic: `next` is the only required method and it is dispatchable, while `map`, `filter`, `collect`, `fold` and friends all carry `where Self: Sized`. So `Box<dyn Iterator<Item = u32>>` works, you can call `.next()` on it, and you cannot call `.map()` on it directly (you can call `.map()` on the `Box` because `Box<I>` itself implements `Iterator` and is `Sized`, which is a subtlety worth knowing).

Trait upcasting, stabilised in Rust 1.86 (2025-04-03), closed the last big gap: given `trait Sub: Super`, you can now coerce `&dyn Sub` to `&dyn Super` and `Box<dyn Sub>` to `Box<dyn Super>` directly. Before 1.86 the ecosystem workaround was to add `fn as_any(&self) -> &dyn Any` to every trait so you could downcast through `Any`; that boilerplate is now obsolete for the upcast direction.

### Associated types versus generic parameters: the "how many impls" test

This is the single most reliable staff-level discriminator in a Rust trait interview, and the rule is one sentence: **a generic parameter on a trait is an input, so a type can implement the trait many times with different arguments; an associated type is an output, so a type can implement the trait exactly once and the associated type is determined by that impl.**

```rust
// ASSOCIATED TYPE: Item is an output. One impl of Iterator per type.
trait Iterator {
    type Item;
    fn next(&mut self) -> Option<Self::Item>;
}

// GENERIC PARAMETER: T is an input. Many impls of From per type.
trait From<T> { fn from(value: T) -> Self; }
```

`String` implements `From<&str>`, `From<char>`, `From<Box<str>>`, `From<Cow<'_, str>>`, and several more. That is only possible because `T` is a generic parameter. If `From` had used an associated type, `String` could convert from exactly one source type forever.

Conversely, `Iterator` uses an associated type precisely so that inference works. With `type Item`, `let x = it.next();` infers `x: Option<u32>` with no annotation. If `Iterator<Item>` were generic, a type could in principle implement `Iterator<u32>` and `Iterator<String>`, and every single call to `.next()` would be ambiguous and require a turbofish. Every combinator signature in the standard library would need to name the item type explicitly. Associated types exist to keep inference tractable.

The decision procedure to say out loud:

1. Ask "can one type sensibly implement this trait more than once, with different type arguments?" If yes, generic parameter. If no, associated type.
2. Ask "does the caller need to *choose* this type at the use site, or is it *determined* by the implementing type?" Chosen by the caller means generic; determined by the impl means associated.
3. Ergonomics tiebreaker: associated types keep bounds short. `fn sum<I: Iterator<Item = u32>>(i: I)` versus a hypothetical `fn sum<I, T>(i: I) where I: Iterator<T>, T: Add` where every downstream signature has to thread `T` through.

Generic associated types (GATs), stabilised in Rust 1.65 (2022-11-03) after about six years in RFC and implementation, let an associated type take its own generic parameters, which is what makes lending-iterator shapes expressible:

```rust
// untested sketch
trait LendingIterator {
    type Item<'a> where Self: 'a;
    fn next(&mut self) -> Option<Self::Item<'_>>;
}
```

Note the direct consequence for dyn: a trait with a GAT is *not* dyn compatible, because "associated types with generic parameters" is on the disqualifying list. That is a real constraint on API design, not a footnote.

### Blanket impls, the orphan rule, and coherence

**Coherence** is the property that for any given trait and any given type, there is at most one applicable impl in the entire program, including all its dependencies. It is not a stylistic preference; it is what makes trait resolution deterministic and what stops two crates in your dependency graph from disagreeing about what `x.to_string()` means. Without it, adding a dependency could silently change the behaviour of unrelated code, and linking two crates that each implemented `Display for u32` would be an unresolvable conflict at link time. Haskell has the same property; C++ deliberately does not, which is why ADL-based customisation in C++ can be surprising.

Coherence is enforced by two rules. The **overlap check** rejects two impls in the same crate that could apply to the same type, producing `error[E0119]: conflicting implementations of trait`. The **orphan rule** governs cross-crate impls: `impl<P...> ForeignTrait<T1, ..., Tn> for T0` is only permitted if at least one of `T0..Tn` is a local type, and no uncovered type parameter appears before the first local type. The practical summary: **you may implement your trait for anyone's type, and anyone's trait for your type, but not someone else's trait for someone else's type.** RFC 2451 ("re-rebalancing coherence," 2018) loosened this to allow local types nested inside foreign generics in more positions, which is why `impl From<MyType> for Vec<MyType>` works.

The consequence you will actually hit: you cannot write `impl Display for Vec<u8>`, because both `Display` and `Vec` are foreign. The standard workaround is the **newtype pattern**:

```rust
struct Hex(Vec<u8>);   // local type -> orphan rule satisfied

impl std::fmt::Display for Hex {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        for b in &self.0 { write!(f, "{b:02x}")?; }
        Ok(())
    }
}
```

A newtype is a zero-cost wrapper: `size_of::<Hex>() == size_of::<Vec<u8>>() == 24` on 64-bit, and after optimisation there is no indirection at all. Add `impl Deref for Hex` if you want the inner methods to pass through, though there is a real ecosystem argument that `Deref`-for-newtypes is an abuse of a trait meant for smart pointers.

**Blanket impls** implement a trait for every type satisfying a bound:

```rust
// The real one from std, verbatim in spirit:
impl<T: fmt::Display + ?Sized> ToString for T {
    fn to_string(&self) -> String { /* ... */ }
}
```

This is why every type that implements `Display` gets `.to_string()` for free, without a single line in that type's crate. The same mechanism gives you `impl<T, U> Into<U> for T where U: From<T>`, which is why you write `From` and get `Into` free, and `impl<I: Iterator> IntoIterator for I`.

The cost of blanket impls is that they consume coherence budget permanently. Once `std` has `impl<T: Display> ToString for T`, nobody can ever write `impl ToString for MyType` with custom behaviour, because it would overlap. Adding a blanket impl to a published trait is therefore a **semver-breaking change in the general case**, even though it adds no method to any signature, because it can create an E0119 conflict in a downstream crate that already wrote its own impl. This trips up library authors constantly and is a genuinely good thing to have an opinion about in an interview.

The related pattern worth naming is the **sealed trait**: put a private supertrait in a private module so that only your crate can implement your public trait.

```rust
mod private { pub trait Sealed {} }

pub trait Encoding: private::Sealed {
    fn encode(&self) -> Vec<u8>;
}

pub struct Utf8;
impl private::Sealed for Utf8 {}
impl Encoding for Utf8 { fn encode(&self) -> Vec<u8> { Vec::new() } }
```

Downstream crates can call `Encoding` methods and use `T: Encoding` bounds, but cannot add impls, which lets you add methods to `Encoding` later without breaking semver. `std` uses this for traits like `std::os::unix::fs::FileExt` where the impl set must stay closed.

### Generics: bounds, `where` clauses, and const generics

Trait bounds are the contract, and unlike C++ templates before Concepts, they are checked at *definition* time, not instantiation time. If a generic function body calls a method not implied by its bounds, the error is on the function, with a `error[E0599]` or `E0277` pointing at the missing bound, not a page of instantiation backtrace at the call site. That property alone is worth mentioning against a C++ background.

```rust
// Inline bounds: fine when short.
fn print_all<T: std::fmt::Debug>(items: &[T]) {
    for i in items { println!("{i:?}"); }
}

// where clause: mandatory once bounds get real, and the only way to
// express bounds on associated types or on types that aren't parameters.
fn process<I, T>(iter: I) -> Vec<String>
where
    I: IntoIterator<Item = T>,
    T: std::fmt::Display + Clone,
    for<'a> &'a T: PartialEq<&'a T>,   // higher-ranked trait bound
{
    iter.into_iter().map(|t| t.to_string()).collect()
}
```

`impl Trait` appears in two positions and they mean different things. In **argument position** (`fn f(x: impl Draw)`) it is sugar for an anonymous generic parameter, with one real difference: you cannot turbofish it, so `f::<Circle>(c)` is an error. In **return position** (`fn f() -> impl Iterator<Item = u32>`, stable since Rust 1.26, 2018-05-10) it means "some single concrete type that I am not naming," which lets you return a closure or a deeply nested iterator adapter chain whose real type is unwriteable. The constraint that catches people: all `return` paths must produce the *same* concrete type, so you cannot conditionally return two different iterator types without boxing to `Box<dyn Iterator<Item = u32>>`.

Rust 1.82 (2024-10-17) added precise capturing, `-> impl Trait + use<'a, T>`, which states exactly which generic parameters the opaque type captures. Rust 2024 changed the default so that RPIT captures all in-scope generic parameters including lifetimes; before that, lifetimes were captured only if mentioned, and people faked the modern behaviour with the `Captures<'a>` trick. If you see a `Captures` helper trait in a codebase, it is pre-2024 code that `use<..>` now replaces.

Return-position `impl Trait` in traits (RPITIT) and `async fn` in traits both stabilised in Rust 1.75 (2023-12-28), which is the same feature under the hood: `async fn foo(&self) -> T` in a trait desugars to `fn foo(&self) -> impl Future<Output = T>`. The consequence, and the thing people get wrong: a trait with an RPITIT or `async fn` method is **not dyn compatible**, because the return type is an anonymous associated type whose size is unknown to the vtable. That is precisely why `#[async_trait]` still exists in 2026: it rewrites every `async fn` to return `Pin<Box<dyn Future<Output = T> + Send + '_>>`, which *is* a fixed-size dispatchable return, at a cost of one heap allocation per call.

**Const generics** parameterise over values rather than types:

```rust
struct Matrix<const R: usize, const C: usize> {
    data: [[f64; C]; R],
}

impl<const R: usize, const C: usize> Matrix<R, C> {
    fn rows(&self) -> usize { R }
}

// Dimensions are part of the TYPE. A 3x4 times a 4x2 typechecks;
// a 3x4 times a 3x2 is a compile error, not a runtime panic.
fn matmul<const M: usize, const N: usize, const P: usize>(
    a: &Matrix<M, N>, b: &Matrix<N, P>) -> Matrix<M, P> {
    # unimplemented!()   // untested sketch
}
```

`min_const_generics` shipped in Rust 1.51 (2021-03-25) and allows const parameters of integral types plus `bool` and `char`, with arguments that are literals, standalone consts, or bare const parameters. What is still *not* stable in August 2026 is arithmetic on them: `[T; N + 1]` requires `generic_const_exprs`, which has carried the `incomplete_features` warning for roughly five years, and the project's stated 2026 direction is a narrower `min_generic_const_args` rather than shipping the full feature. Do not architect around `N + 1`. The pragmatic workaround shipped by numeric crates is a trait with an associated const, or typenum-style type-level integers, both of which predate const generics and are uglier.

Two more numbers worth carrying: the default recursion limit for trait resolution and macro expansion is **128** (raise with `#![recursion_limit = "256"]`, which deeply nested generic types occasionally need), and the default `type_length_limit` that bounds monomorphised type name length was **1048576** before it was removed as a hard error, so an "overflow evaluating the requirement" message is usually a recursive bound, not a real infinite type.

### Enums as sum types, and why `Option`/`Result` are not special

A Rust enum is a tagged union: a discriminant plus a payload that varies by variant, laid out as `size = align_up(tag_size + max(payload sizes), alignment)`. Java and Go have no equivalent. Java's `enum` is a fixed set of singleton objects with no per-variant payload (sealed interfaces plus records in Java 17, 2021, get you closer, at the cost of one class per variant and pointer-chasing); Go has no sum type at all, which is why Go APIs return `(T, error)` pairs where exactly one is meaningful and nothing in the type system says so.

The load-bearing fact for interviews: `Option` and `Result` are **ordinary library enums**, defined in `core::option` and `core::result` in about ten lines each, using no syntax you cannot use yourself:

```rust
pub enum Option<T> { None, Some(T) }
pub enum Result<T, E> { Ok(T), Err(E) }
```

There is no compiler special-casing of their *semantics*. If they vanished from `core` you could define them in your own crate and everything except three conveniences would still work. Those three conveniences are the honest caveats to state before an interviewer corrects you:

1. Both are in the **prelude**, so `Some`, `None`, `Ok`, `Err` are in scope unqualified everywhere.
2. Both are `#[must_use]`, so discarding a `Result` without binding it produces `unused_must_use` warning, which is what makes Rust's error handling enforced rather than conventional. Go has nothing equivalent in the compiler; `errcheck` is a separate linter.
3. `?` works on them via the `Try` trait, which is `#[unstable(feature = "try_trait_v2")]` as of Rust 1.97, so *you* cannot make `?` work on your own type on stable. This is the one place where "not special-cased" is a slight overstatement, and saying so unprompted is a credibility win.

**Niche optimisation** is the layout property that makes this free. The compiler looks for an invalid bit pattern in the payload and uses it as the discriminant instead of adding a tag word:

```rust
use std::mem::size_of;
use std::num::NonZeroU32;
fn main() {
    assert_eq!(size_of::<&u8>(), 8);
    assert_eq!(size_of::<Option<&u8>>(), 8);          // null is the niche
    assert_eq!(size_of::<Option<Box<u8>>>(), 8);
    assert_eq!(size_of::<Option<NonZeroU32>>(), 4);   // 0 is the niche
    assert_eq!(size_of::<u32>(), 4);
    assert_eq!(size_of::<Option<u32>>(), 8);          // no niche in u32,
                                                       // tag + padding
    assert_eq!(size_of::<Option<bool>>(), 1);         // bool has 254
                                                       // spare bit patterns
}
```

So `Option<&T>` costs literally nothing over `&T`; the "null pointer" is still there in the machine representation, but the type system forces you to handle it. That is the whole argument against Tony Hoare's billion-dollar mistake in one line of `size_of`.

`std::io::Error` is worth knowing as a layout case study: on 64-bit it is **8 bytes**, because it packs an `errno` code, a `&'static` simple message, or a pointer to a heap-allocated custom error into a single tagged pointer. So `size_of::<io::Result<()>>()` is 8, not 24, and returning `Result` from I/O functions costs nothing in register pressure. A hand-rolled error enum with a `String` variant, by contrast, is at least 32 bytes, which propagates into every `Result` in the call chain. That is the concrete reason for `Result<T, Box<MyError>>` on hot paths.

### Pattern matching: exhaustiveness as a refactoring tool

The compiler proves that a `match` covers every possible value, and `error[E0004]: non-exhaustive patterns` names the specific uncovered pattern. Turn that around and you have the most underrated tool in the language:

```rust
enum Event { Click { x: i32, y: i32 }, KeyPress(char), Scroll(f64) }

fn handle(e: &Event) -> String {
    match e {
        Event::Click { x, y } => format!("click {x},{y}"),
        Event::KeyPress(c)    => format!("key {c}"),
        Event::Scroll(d)      => format!("scroll {d}"),
    }
}
```

Add `Event::Paste(String)` to the enum and this function stops compiling, along with every other `match` on `Event` in the workspace, each one pointing at the exact line to update. In Java or Go the equivalent addition compiles fine and fails in production on the branch nobody thought about. **This only works if you do not write a `_ =>` arm.** A wildcard arm on an enum you own is opting out of the guarantee, and it is the single most common way teams throw away Rust's best refactoring property. Use `_` for genuinely open sets (integers, strings, foreign `#[non_exhaustive]` enums) and enumerate variants explicitly for enums you control. `clippy::wildcard_enum_match_arm` enforces this if you want it mechanical.

`#[non_exhaustive]` is the other side of the same coin. Put it on a public enum and downstream crates are *forced* to include a `_` arm, which means you can add variants in a minor release without breaking them. Omit it and every new variant is a semver-major break. Your own crate still gets exhaustiveness checking; only foreign crates are constrained.

**Match ergonomics and binding modes** are the part that produces confused Stack Overflow questions. When you match a reference against a non-reference pattern, the compiler dereferences and flips the *default binding mode* from `move` to `ref` (or `ref mut`), so the bindings come out as references:

```rust
let v: Vec<String> = vec!["a".into()];
match v.first() {           // Option<&String>
    Some(s) => { /* s: &String, NOT String. DBM became `ref`. */ }
    None => {}
}

let opt: Option<String> = Some("a".into());
match &opt {                // &Option<String>
    Some(s) => { /* s: &String. The & was auto-dereferenced. */ }
    None => {}
}
```

Without match ergonomics (which landed in Rust 1.26, 2018) you would have written `match &opt { &Some(ref s) => ... }`, and pre-2018 Rust code is full of that. The Rust 2024 edition added the RFC 3627 reservations: once the default binding mode is not `move`, writing an explicit `mut`, `ref`, or `ref mut` on a binding is an error, and a reference pattern (`&`/`&mut`) can only appear while the pattern prefix is still fully explicit. This deliberately outlaws the confusing half-explicit middle ground and reserves design space; the migration lint rewrites affected code automatically via `cargo fix --edition`.

The three control-flow forms and when each is right:

```rust
// if let — one interesting case, rest ignored. Right when there is
// genuinely one case you care about.
if let Some(user) = cache.get(&id) { serve(user); }

// let else — bind in the OUTER scope, or diverge. This is the
// guard-clause form, stable since Rust 1.65 (2022-11-03). The else
// block must diverge (return / break / continue / panic!), type `!`.
let Some(user) = cache.get(&id) else {
    return Err(Error::NotFound(id));
};
serve(user);              // user is in scope here, no rightward drift

// if let chains — stable in the 2024 edition from Rust 1.88
// (2025-06-26). Multiple bindings without nesting.
if let Some(user) = cache.get(&id)
    && let Some(role) = user.role.as_ref()
    && role.is_admin()
{
    grant(user);
}
```

`let else` is the one that most improves real code: the pre-1.65 alternative was `let user = match cache.get(&id) { Some(u) => u, None => return ... };`, four lines for a guard clause, and every level of nesting pushed the happy path further right. Match guards (`Some(n) if n > 10 =>`) are worth one caution: **the exhaustiveness checker cannot reason about guards**, so `match x { Some(n) if n > 0 => ..., Some(n) if n <= 0 => ..., None => ... }` fails to compile even though it is exhaustive to a human, and you need a real catch-all arm.

Other pattern forms in the working set: `@` bindings (`n @ 1..=9 => ...` binds and tests), `..` for ignoring struct fields or slice middles (`[first, .., last]`), `|` alternatives (`'a' | 'e' | 'i' => ...`), and destructuring in `let`, function parameters, and closure arguments (`|(k, v)| ...` in a `HashMap` iteration).

### Error handling: `Result`, `?`, and what `From` is doing

`?` desugars to an early return with a conversion, and this is the mechanism you must be able to write on a whiteboard:

```rust
let n = parse(s)?;
// becomes, modulo the unstable Try trait:
let n = match parse(s) {
    Ok(v)  => v,
    Err(e) => return Err(From::from(e)),
};
```

The `From::from(e)` is the entire design. Because `?` calls it, a function returning `Result<T, MyError>` can use `?` on any call returning `Result<_, E>` for which `impl From<E> for MyError` exists. You write the conversion once, per error pair, and every call site in the crate gets it. That is the thing Go's `if err != nil { return fmt.Errorf("...: %w", err) }` cannot do without repeating the wrap at every site, and the thing Java's checked exceptions cannot do at all without a try/catch/rethrow block.

Consequences to have loaded:

- `?` on `Option<T>` works too, returning `None` early, but you cannot mix: a function returning `Option` cannot `?` a `Result`. Convert with `.ok_or(err)?` / `.ok_or_else(|| err)?` in one direction and `.ok()?` in the other.
- `?` in `main` works because `fn main() -> Result<(), E>` is allowed where `E: Debug`, stable since Rust 1.26. A non-`Ok` return prints the `Debug` representation and exits with code **1**.
- `?` costs nothing at runtime beyond the branch. It is not an exception; there is no unwinding, no stack capture, no dynamic dispatch. On the `Ok` path with a niche-optimised `Result`, it typically compiles to a single test-and-branch.
- The error conversion is a *type-level* operation, so a `?` that fails to compile with `error[E0277]: the trait bound '...: From<...>' is not satisfied` is telling you exactly which `impl From` to write.

### `thiserror` versus `anyhow`: the library/application split

The rule, stated as an interviewer wants to hear it: **libraries return concrete, matchable error types; applications return opaque, contextual ones.** The reason is not taste. A library's caller must be able to distinguish "the file was missing" (retry with a default) from "the file was corrupt" (fail loudly) from "the network timed out" (retry with backoff). A `match` on your error enum is the only way to express that in the type system. If you return `anyhow::Error`, the caller's only options are string matching on the `Display` output, which is a documented-by-accident API, or `downcast_ref::<ConcreteType>()`, which requires them to depend on the concrete type anyway and silently returns `None` if you ever change it.

```rust
// LIBRARY: thiserror 2.0.19. Zero runtime cost; a proc macro that
// writes the Display, Error, and From impls you would write by hand.
use thiserror::Error;

#[derive(Debug, Error)]
#[non_exhaustive]                       // lets you add variants in a minor
pub enum ConfigError {                  // release without a semver break
    #[error("config file not found at {path}")]
    NotFound { path: std::path::PathBuf },

    #[error("failed to read config")]
    Io(#[from] std::io::Error),         // #[from] generates
                                        // `impl From<io::Error>` AND
                                        // wires up source()

    #[error("invalid TOML at line {line}")]
    Parse {
        line: usize,
        #[source] cause: toml::de::Error,   // in the chain, not in Display
    },

    #[error("unknown key `{0}`")]
    UnknownKey(String),
}
```

`#[from]` is what makes `?` work: it emits `impl From<io::Error> for ConfigError`, so `let s = fs::read_to_string(p)?;` inside a `-> Result<T, ConfigError>` function converts automatically. `#[source]` (implied by `#[from]`) implements `Error::source()`, which is what builds the **error chain** that observability tooling walks.

```rust
// APPLICATION: anyhow 1.0.104. One opaque error type, cheap context.
use anyhow::{Context, Result, bail};

fn run(path: &str) -> Result<Config> {
    let raw = std::fs::read_to_string(path)
        .with_context(|| format!("reading config from {path}"))?;
    if raw.is_empty() { bail!("config at {path} is empty"); }
    let cfg: Config = toml::from_str(&raw)
        .context("parsing config as TOML")?;
    Ok(cfg)
}
```

`anyhow::Error` is **8 bytes** on 64-bit, a single thin pointer, because it stores the vtable inside the heap allocation rather than alongside the pointer; `Box<dyn Error + Send + Sync>` is 16 bytes. It requires the inner error to be `Send + Sync + 'static`, which is what makes it usable across threads and Tokio tasks. `.context()` takes an eagerly-evaluated value and `.with_context()` a closure, so use the closure form whenever building the message allocates, which is nearly always. With `RUST_BACKTRACE=1` set, anyhow captures a `std::backtrace::Backtrace` (stabilised in Rust 1.65) at the point the error is created, and printing with `{:?}` gives you the message, the full context chain innermost-last, and the backtrace. That is the single biggest operational reason applications use it.

The middle ground that experienced teams actually ship: `thiserror` enums at every module boundary inside a service, and `anyhow::Result` only in `main`, in binaries, in tests, and in glue code where nothing downstream will ever match. `eyre`/`color-eyre` is the same shape as anyhow with customisable report handlers and prettier terminal output; `snafu` is the other serious contender, offering context selectors that make it easier to attach structured context to enum variants than `thiserror` does. Naming `snafu` and `eyre` as real alternatives rather than pretending the ecosystem is a two-horse race is a small credibility signal.

### Why `unwrap()` in a library is a bug

`unwrap()` and `expect()` convert a value the caller could have handled into a **panic**, which is a process-level event the caller did not opt into.

- Under the default `panic = "unwind"`, the panic unwinds to the nearest catch boundary. In a Tokio service, `tokio::spawn`'s `JoinHandle` catches it and returns `Err(JoinError::is_panic)`, so a panicking library call silently kills one task and, if nobody awaits the handle, disappears entirely. In an Axum or Actix handler the middleware usually converts it to a bare **500** with no structured error body.
- Under `panic = "abort"` (common in release profiles for smaller binaries and no landing pads, and mandatory in some embedded and FFI contexts), the same call aborts the entire process. Your library just took down a multi-tenant server because one request had a malformed header.
- Panicking across an `extern "C"` boundary was undefined behaviour and is now a guaranteed abort, so an `unwrap` in a library exposed over FFI is a hard process kill.
- It destroys the caller's error chain. `Result` composes; a panic does not.

The rule is not "never panic." Panic is correct for **broken invariants inside your own code**, meaning states you have proved cannot happen and would be a bug if reached: index out of bounds on a slice you just sized, a `RwLock` that was poisoned by another panic, an `unreachable!()` after an exhaustive check. Panic is wrong for anything derived from input, I/O, configuration, or the network. The mechanical test: *could a well-behaved caller passing valid arguments trigger this?* If yes, it must be a `Result`.

Practical enforcement, which is what a staff interview wants:

```toml
# In the library crate's lib.rs or Cargo.toml [lints.clippy] table:
# unwrap_used = "deny"
# expect_used = "warn"      # expect() with a real message is the
#                           # lesser evil; unwrap() gives no context
# panic = "deny"
# indexing_slicing = "warn" # a[i] panics; .get(i) returns Option
```

`clippy::unwrap_used` denied at the crate level, with per-site `#[allow]` and a comment justifying each exception, is how mature Rust libraries actually keep this honest. In tests, `unwrap()` is fine and idiomatic; the lint is normally scoped to non-test code.

---

## Build it from scratch

The exercise that teaches all five topics at once is a tiny plugin registry: a trait, both dispatch strategies side by side, an error enum with a source chain, and a measurement step. Target 60 minutes. The matching lab lives in `(lab pending)`.

**Step 1. Define the trait twice, once dyn compatible and once not, and feel the difference.**

```rust
// src/lib.rs — untested sketch, but every construct here is stable on 1.97

use std::fmt;

/// Dyn compatible: no generic methods, no Self in return position.
pub trait Transform {
    fn name(&self) -> &str;
    fn apply(&self, input: &str) -> Result<String, TransformError>;

    // Provided method excluded from the vtable so the trait stays
    // dyn compatible while still being usable on concrete types.
    fn apply_twice(&self, input: &str) -> Result<String, TransformError>
    where
        Self: Sized,
    {
        self.apply(&self.apply(input)?)
    }
}

pub struct Upper;
pub struct Reverse;
pub struct Truncate { pub max: usize }

impl Transform for Upper {
    fn name(&self) -> &str { "upper" }
    fn apply(&self, s: &str) -> Result<String, TransformError> {
        Ok(s.to_uppercase())
    }
}
impl Transform for Reverse {
    fn name(&self) -> &str { "reverse" }
    fn apply(&self, s: &str) -> Result<String, TransformError> {
        Ok(s.chars().rev().collect())
    }
}
impl Transform for Truncate {
    fn name(&self) -> &str { "truncate" }
    fn apply(&self, s: &str) -> Result<String, TransformError> {
        if self.max == 0 {
            return Err(TransformError::BadConfig {
                field: "max", value: "0".into(),
            });
        }
        Ok(s.chars().take(self.max).collect())
    }
}
```

Now write `pub trait Cloneable { fn dup(&self) -> Self; }` and try `Box<dyn Cloneable>`. You get `error[E0038]` naming `dup` and the reason: "method `dup` references the `Self` type in its return type." Do this once by hand and you never have to memorise the dyn-compatibility list; you can re-derive it from the vtable.

**Step 2. The error type, by hand first, then with `thiserror`.**

Write it manually once so you know exactly what the macro generates:

```rust
#[derive(Debug)]
pub enum TransformError {
    BadConfig { field: &'static str, value: String },
    Io(std::io::Error),
}

impl fmt::Display for TransformError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::BadConfig { field, value } =>
                write!(f, "bad config: {field} = {value}"),
            Self::Io(_) => write!(f, "io failure while transforming"),
        }
    }
}

impl std::error::Error for TransformError {
    fn source(&self) -> Option<&(dyn std::error::Error + 'static)> {
        match self {
            Self::Io(e) => Some(e),        // THIS is the chain
            Self::BadConfig { .. } => None,
        }
    }
}

impl From<std::io::Error> for TransformError {
    fn from(e: std::io::Error) -> Self { Self::Io(e) }  // THIS is what
}                                                        // makes `?` work
```

That is roughly 25 lines for two variants, and it scales linearly. The `thiserror` version is the same thing with the boilerplate generated:

```rust
use thiserror::Error;

#[derive(Debug, Error)]
#[non_exhaustive]
pub enum TransformError {
    #[error("bad config: {field} = {value}")]
    BadConfig { field: &'static str, value: String },

    #[error("io failure while transforming")]
    Io(#[from] std::io::Error),
}
```

Note what `Display` deliberately does *not* include: the inner io error's message. Each layer's `Display` describes only its own layer, and the full story comes from walking `source()`. Duplicating the inner message into the outer `Display` is the most common `thiserror` mistake and produces logs like `io failure: failed to read file: No such file or directory: No such file or directory`.

**Step 3. Write the chain walker.** This is a five-line function every Rust service should have, and writing it is what makes `source()` concrete:

```rust
pub fn chain(e: &dyn std::error::Error) -> String {
    let mut out = e.to_string();
    let mut cur = e.source();
    let mut depth = 0;
    while let Some(s) = cur {
        depth += 1;
        out.push_str(&format!("\n  {depth}: caused by: {s}"));
        cur = s.source();
    }
    out
}
```

`anyhow`'s `{:?}` formatting is essentially this plus a backtrace. Once you have written it, `anyhow` stops being magic.

**Step 4. Run both dispatch strategies over the same data.**

```rust
// Static: monomorphised, one copy per T, fully inlinable.
pub fn run_static<T: Transform>(t: &T, inputs: &[String])
    -> Result<Vec<String>, TransformError> {
    inputs.iter().map(|s| t.apply(s)).collect()
    //                               ^^^^^^^ collect::<Result<Vec<_>,_>>()
    //   short-circuits on the FIRST Err. This is the single most useful
    //   Result idiom in the language and it is easy to miss.
}

// Dynamic: one copy total, heterogeneous pipeline possible.
pub fn run_dynamic(pipeline: &[Box<dyn Transform>], input: &str)
    -> Result<String, TransformError> {
    pipeline.iter().try_fold(input.to_string(), |acc, t| t.apply(&acc))
}
```

The `collect::<Result<Vec<_>, E>>()` behaviour is worth pausing on: an iterator of `Result<T, E>` collects into `Result<Vec<T>, E>`, returning the first error and abandoning the rest. If you want all errors, `partition::<Vec<_>, _>()` on `is_ok` or collect into `(Vec<T>, Vec<E>)`.

**Step 5. Measure, do not assert.** Build both, then:

```bash
cargo llvm-lines --release | head -30      # which generic exploded
cargo bloat --release --crates             # .text by crate
cargo bloat --release -n 20                # .text by symbol
cargo build --timings                      # HTML: codegen vs frontend
cargo bench                                # criterion, with black_box
```

Then make the honest observation: on a pipeline of three transforms over 10,000 short strings, the static and dynamic versions will be within noise of each other, because the work per call (a `to_uppercase` allocation) dwarfs the dispatch. The generic version only wins when the body is small enough to inline and the surrounding loop can then be vectorised or constant-folded. Reproduce that by adding a `fn is_noop(&self) -> bool { false }` and a caller that branches on it: the static version deletes the branch entirely, the dynamic one cannot.

---

## How it's done in production

The trait/generic decisions that show up in every real Rust service, and what the ecosystem actually does:

**Dependency injection** is `Arc<dyn Trait + Send + Sync>` in almost every async service, not generics. The reason is not performance, it is that generic parameters are *viral*: making `AppState<S: Storage>` generic forces `S` through every handler signature, every extractor, every `impl` block, and every test helper, and Axum/Actix handler registration gets painful fast. One `Arc<dyn Storage + Send + Sync>` field costs one indirect call per storage operation, which is invisible next to a network round trip. Use generics for state when there is exactly one implementation and you want inlining; use `dyn` the moment there are two, or the moment tests need a mock.

**Serde** is the canonical monomorphisation case study. `#[derive(Serialize, Deserialize)]` generates a `Serializer`-generic impl per type, and `serde_json::to_string` instantiates it per `(type, format)` pair. A crate with 200 DTOs and three formats is 600 instantiations, and serde is routinely the top entry in `cargo llvm-lines` output for API services. The mitigations that work: `serde_json::to_writer` against a single concrete writer rather than generic ones, feature-gating formats you do not ship, and `#[serde(skip)]` on fields you never serialise.

**Axum, Tower, and Tokio** lean hard on traits with associated types. `tower::Service<Request>` has `type Response`, `type Error`, `type Future: Future<Output = Result<Self::Response, Self::Error>>`, which is a textbook associated-type design: a service produces exactly one response type, so it is an output. `Request` is a generic parameter because one service can handle several request types. Axum handlers use a blanket impl over function signatures with `FromRequest` extractors, which is why "the trait bound `fn(...) -> ...: Handler<_, _>` is not satisfied" is Axum's most infamous error message: the blanket impl failed to apply, and the compiler cannot tell you which extractor was the problem.

**`#[async_trait]`** is still in most codebases even though `async fn` in traits has been stable since 1.75, for exactly one reason: the built-in version is not dyn compatible, and services need `Arc<dyn Repository + Send + Sync>`. The macro boxes every call as `Pin<Box<dyn Future<Output = T> + Send + '_>>`, so budget one heap allocation per method call. For a repository method that then does a Postgres round trip at 0.5-5 ms, that allocation is roughly 0.01% of the cost and nobody should care; for a hot in-memory trait called millions of times per second, it matters and you should use static dispatch or an enum.

**Enum dispatch** is the third option people forget. When the set of implementations is closed and known at compile time, an enum with one variant per implementation gives you a heterogeneous collection *and* static dispatch, at the cost of every value being as large as the largest variant. The `enum_dispatch` crate generates the delegating `match` automatically. This is often the right answer for state machines and for a small fixed set of codecs or backends, and knowing it exists distinguishes people who have shipped Rust from people who have read about it.

**Error observability** in production means walking `source()`. `tracing`'s `error!(error = ?e, "…")` records the `Debug` form; for a `thiserror` enum that is only the top layer, so services typically log `error = %chain(&e)` with the walker from the lab, or use `tracing-error`'s `SpanTrace`. `anyhow`'s `{:?}` already includes the chain and the backtrace. The failure to name here: logging only `e.to_string()` on a `thiserror` enum, which throws away every layer below the top and produces alerts that say "database error" with no cause.

### Failure-mode table

| Symptom | Cause | Fix |
|---|---|---|
| `error[E0038]: the trait 'Storage' is not dyn compatible` (older toolchains: "cannot be made into an object"), with a note pointing at a specific method | A method is not dispatchable: it has a generic type parameter, mentions `Self` outside the receiver position, returns `impl Trait`/is an `async fn`, or the trait has an associated const | Add `where Self: Sized` to the offending method to exclude it from the vtable; or erase the generic (`fn write(&self, w: &mut dyn Write)` instead of `fn write<W: Write>(&self, w: W)`); or for `async fn`, apply `#[async_trait]` so the return becomes `Pin<Box<dyn Future + Send + '_>>` |
| `error[E0119]: conflicting implementations of trait 'MyTrait' for type 'Foo'` after adding a blanket impl or an upstream dependency bump | Two impls could apply to the same type. Commonly a local `impl MyTrait for Foo` overlapping a `impl<T: Bound> MyTrait for T`, or an upstream crate adding a blanket impl in a "minor" release | Drop the blanket impl and write per-type impls, or narrow the blanket impl's bound so it cannot cover `Foo`, or wrap in a newtype. There is no `specialization` on stable to break the tie; do not plan on it |
| `error[E0117]: only traits defined in the current crate can be implemented for types defined outside of the crate` | Orphan rule: both the trait and the type are foreign (e.g. `impl Display for Vec<u8>`) | Newtype wrapper (`struct Hex(Vec<u8>)`), which is zero-cost; or define your own local trait and implement it for the foreign type, which the orphan rule permits |
| `error[E0207]: the type parameter 'T' is not constrained by the impl trait, self type, or predicates` | A type parameter on an `impl` block appears nowhere in the trait being implemented or the self type, so the compiler cannot infer it and multiple impls would be indistinguishable | Add a `PhantomData<T>` field to the self type so `T` appears in it; or move `T` from the `impl` to the individual method; or convert `T` into an associated type on the trait |
| `error[E0282]: type annotations needed` or `error[E0283]: type annotations needed... multiple 'impl's satisfying '_: FromStr'` on a `.parse()` or `.collect()` | Inference has no way to pick the output type; `collect` and `parse` are generic over their return | Turbofish at the call: `.parse::<i32>()`, `.collect::<Vec<_>>()`, `.collect::<HashMap<String, u64>>()`; or annotate the binding: `let v: Vec<_> = it.collect();`. Both are equivalent; turbofish reads better mid-chain |
| `error[E0277]: '?' couldn't convert the error to 'MyError'` / "the trait bound `MyError: From<io::Error>` is not satisfied" | `?` calls `From::from` on the error and no such impl exists | Add a variant with `#[from]` on the inner error, or write `impl From<io::Error> for MyError` by hand, or `.map_err(MyError::Io)?` at the single call site if a global conversion is wrong |
| `error[E0004]: non-exhaustive patterns: 'Event::Paste(_)' not covered` after adding an enum variant | Exhaustiveness checking doing its job across the whole workspace | Handle the new variant at each site. Do not "fix" it by adding `_ => {}`; that permanently disables the check for that match |
| `error[E0599]: no method named 'to_bytes' found for struct 'Frame'` even though the impl clearly exists | The trait providing the method is not in scope. Trait methods require the trait to be imported | `use crate::codec::Encode;` at the call site. This is the most common false "the method doesn't exist" in Rust and the compiler's note usually names the candidate trait |
| Compile time jumps from ~40s to several minutes after a seemingly small change; `cargo build --timings` shows codegen dominating | A widely-called function became generic, or a generic body grew, multiplying instantiations | `cargo llvm-lines --release` to find the top instantiation count; apply the inner-function trick (`fn outer<P: AsRef<Path>>(p: P) { inner(p.as_ref()) }`) so the big body compiles once; or switch that boundary to `&dyn` |
| Release binary grew by several MB after adding a generic abstraction; `cargo bloat --release --crates` attributes it to one crate | Monomorphisation bloat, plus loss of dead-code elimination | Same fix as above, plus `lto = "fat"`, `codegen-units = 1`, `panic = "abort"`, `opt-level = "z"` in the release profile; measure each independently |
| Service returns bare 500s with no body; logs show `task ... panicked at 'called Option::unwrap() on a None value'` | A library or handler called `unwrap()`/`expect()` on input-derived data. Tokio caught the unwind at the task boundary; nothing propagated a typed error | Replace with `ok_or(Error::Missing)?` or `let ... else { return Err(...) }`; deny `clippy::unwrap_used` and `clippy::indexing_slicing` at the crate root of libraries |
| Whole process exits on one malformed request, no unwind, `SIGABRT` | Same `unwrap` but the release profile has `panic = "abort"`, or the panic crossed an `extern "C"` boundary (guaranteed abort) | Same fix. Additionally, wrap any FFI entry point in `std::panic::catch_unwind` and convert to an error code; never let a panic reach the boundary |
| Alert says "database error" with no cause; the underlying `sqlx` message is nowhere in the logs | Logged `e.to_string()` on a `thiserror` enum, which renders only the top layer's `#[error(...)]` string | Walk `Error::source()` when logging (`error = %chain(&e)`), or use `anyhow`'s `{:?}`, or `tracing-error`. Also check the enum does not duplicate the inner message into its own `Display` |
| Downstream crates break on every minor release because you added an enum variant | Public enum without `#[non_exhaustive]`, so their exhaustive `match` stopped compiling | Add `#[non_exhaustive]` to public error and event enums from day one. It is a one-line, semver-major-once change that buys unlimited future variants |
| `Result<T, E>` return values are unexpectedly large in profiles; a hot function spills to the stack | `size_of::<Result<T, E>>() == max(size_of::<T>(), size_of::<E>()) + tag`, and a `thiserror` enum with a `String` or a nested error is easily 48-64 bytes | `Box` the error: `Result<T, Box<MyError>>`, making the `Err` arm 8 bytes. `std::io::Error` already does exactly this internally, which is why it is 8 bytes on 64-bit |

---

## Tradeoffs & when NOT to use it

**Do not default to generics on a public API boundary you cannot change later.** `fn process(r: impl Read)` and `fn process(r: &mut dyn Read)` look interchangeable and are not: the first is monomorphised into the caller's crate, cannot be stored in a struct field without threading the parameter through, and cannot be part of a `dyn`-compatible trait. Switching from one to the other after publication is a semver-major break. If the function is called once per request and does I/O, the `dyn` version costs an indirect call, saves you every instantiation, and keeps the option of a trait object open. The generic version is right when the body is small and hot enough that inlining matters, which is a claim you should have `criterion` numbers for before making it.

**Do not use `dyn Trait` when you need any of: `Clone`, `PartialEq`, `Default`, a generic method, an associated function without a receiver, or a return of `Self`.** These are not dyn compatible and the workarounds are all ugly: `Box<dyn Trait>` plus a `fn clone_box(&self) -> Box<dyn Trait>` method on the trait, or the `dyn-clone` crate, both of which are boilerplate you are paying to work around a design that wanted an enum. If the implementation set is closed, an enum with `enum_dispatch` gives you heterogeneity, `Clone`, `PartialEq`, exhaustive matching, and static dispatch simultaneously, at the cost of every value being sized to the largest variant and of the enum living in one crate (so plugins from other crates cannot join). Closed set means enum; open set means `dyn`.

**Do not put `anyhow` in a library's public API.** The moment `pub fn parse(&self) -> anyhow::Result<Config>` ships, every caller who needs to distinguish "file missing" from "syntax error" is reduced to `downcast_ref` against a type you did not document, or to matching on `Display` strings. It also forces your `anyhow` version on downstream crates as a public dependency, so an `anyhow` 2.0 becomes a breaking change for everyone. The legitimate exceptions: internal-only crates within one workspace where you control every caller, and binaries. When in doubt, `thiserror`, because converting a `thiserror` enum into `anyhow` at the application layer is one `?` away and the reverse is impossible.

**Do not build a 40-variant error enum for an application.** Exhaustive matchability is only valuable if someone actually matches. In application code the overwhelmingly common handling is "log it with context and return 500," and a large enum then costs you: a `Display` impl per variant, a `From` per source, a semver hazard per addition, and a `size_of` inflated to the largest variant that propagates into every `Result` up the stack. This is the argument for `anyhow` in applications and it is a genuinely contested one; the counter-position, which is also defensible, is that a service with well-defined failure modes benefits from an enum precisely because it forces you to enumerate them. State both.

**Do not add a blanket impl to a published trait.** It reads as a pure addition and is not: any downstream crate that already wrote its own impl for a covered type now gets `E0119` and cannot compile. There is no way to opt out and no `specialization` on stable to break the tie. If you want the ergonomics of a blanket impl in a library that already has users, ship it behind a new trait instead, or accept it as a major version.

**Do not use `#[async_trait]` reflexively.** It exists to solve dyn compatibility. If your trait is only ever used with static dispatch (which is most internal traits), native `async fn` in traits, stable since Rust 1.75, is free and the macro costs you a `Pin<Box<dyn Future>>` allocation per call plus worse error messages plus a proc-macro dependency in your compile graph. Check whether anything actually stores your trait behind an `Arc<dyn _>` before reaching for it.

**Do not use `?` where the caller needs the error to be actionable and it isn't.** `?` with a `#[from]` conversion silently discards context: which file, which key, which retry attempt. A function that opens 12 different files and `?`s all of them produces an error that says "No such file or directory" and nothing else. Either add `.with_context(...)` at each site (anyhow), or make the variant carry the context (`NotFound { path: PathBuf }` rather than `Io(io::Error)`). The failure mode is a 3 AM page with an unactionable message, and it is the most common real-world cost of a naive `#[from]`-everywhere error type.

**Do not reach for const generics to encode dimensions unless the sizes are genuinely compile-time constant.** Matrix shapes checked at compile time are lovely until the shapes come from a config file or a model checkpoint, at which point you need runtime dimensions anyway and now maintain both paths. `ndarray` and every serious numeric crate use runtime dimensions for exactly this reason. Const generics are right for fixed-size cryptographic buffers, SIMD lane counts, and ring-buffer capacities, not for tensors whose shape is data.

**Do not treat exhaustive matching as free.** It is the best refactoring tool in the language *and* it means every enum variant addition is a workspace-wide edit. For an enum with 30 variants matched in 40 places, that is 1,200 potential sites. `#[non_exhaustive]` on the public boundary and a deliberate decision about which internal matches use `_` is the balance; blanket `_` arms everywhere throws away the benefit, and zero `_` arms anywhere makes evolution expensive.

---

## Interview questions

### Q1 — What is the difference between `impl Trait` in argument position and `dyn Trait`, and which is the default?

**Testing:** whether static versus dynamic dispatch is understood mechanically rather than as a slogan.
**Answer:** `fn f(x: impl Draw)` is sugar for `fn f<T: Draw>(x: T)`: the compiler monomorphises, emitting one specialised copy of `f` per concrete type used, with direct, inlinable calls and a thin 8-byte pointer if you pass a reference. `fn f(x: &dyn Draw)` emits exactly one copy of `f`; the argument is a 16-byte fat pointer carrying the data pointer plus a pointer to a per-(type, trait) vtable in `.rodata`, and each method call loads a function pointer from that table and calls indirectly. Static is the default in Rust; you opt into `dyn` explicitly. The real tradeoff is binary size and compile time versus inlining: `n` instantiations of an `m`-byte body cost roughly `n × m` bytes, and the dominant runtime cost of `dyn` is usually not the indirect call (a few cycles on a predicted target) but that LLVM cannot inline through it, which kills constant propagation and auto-vectorisation.
**Follow-up trap:** *"So generics are always faster?"* No, and asserting it is the trap. Sixty monomorphised copies of a 4 KB loop compete for a 32 KB L1 instruction cache; one `dyn` copy that stays resident can win. The correct answer is that it is measurable and you measure it: `cargo llvm-lines --release` for instantiation counts, `cargo bloat` for binary attribution, `criterion` plus `perf stat -e branch-misses,L1-icache-load-misses` for runtime. Say "I'd measure" and then name the tools, or the interviewer concludes you have never actually done it.

### Q2 — When would you use an associated type instead of a generic type parameter on a trait?

**Testing:** the single most reliable staff-level discriminator in a Rust trait interview.
**Answer:** A generic parameter is an *input*, so one type can implement the trait many times with different arguments; an associated type is an *output*, determined by the impl, so one type implements the trait exactly once. `From<T>` uses a generic parameter because `String` legitimately converts from `&str`, `char`, `Box<str>`, and `Cow<'_, str>`. `Iterator` uses `type Item` because a type iterates one way, and because if `Iterator<T>` were generic, every single `.next()` call would be ambiguous and need a turbofish, and every combinator signature in `std` would have to thread the item type through. The decision procedure: can one type sensibly implement this more than once with different arguments? Yes means generic parameter, no means associated type.
**Follow-up trap:** *"Can you have both on the same trait?"* Yes, and `tower::Service<Request>` is the production example: `Request` is a generic parameter because one service can accept several request types, while `Response`, `Error`, and `Future` are associated types because they are determined by the impl. The follow-up under that one is generic associated types, stable since Rust 1.65 (2022-11-03), which let an associated type take its own parameters (`type Item<'a> where Self: 'a`) and thereby express lending iterators. The gotcha to volunteer: a trait with a GAT is not dyn compatible, because associated types with generic parameters are on the disqualifying list.

### Q3 — Why can't you call `Box<dyn Clone>`? Derive the rule, don't recite it.

**Testing:** whether dyn compatibility is understood from the vtable up.
**Answer:** `Clone::clone` has signature `fn clone(&self) -> Self`. A caller holding a `&dyn Clone` has erased the concrete type, so it does not know the size or alignment of the value that method would return and cannot allocate a stack slot for it. The vtable slot would have to return something of unknown size, which the calling convention cannot express. Generalising from the fat-pointer picture gives you the whole rule set: no generic methods, because a vtable is a fixed-size array built at compile time and the set of instantiations is unbounded; no `Self` in return position, for the size reason above (this is why `Clone`, `Copy`, `Default`, `From`, and `Into` are all dyn incompatible); no `Self` in argument position other than the receiver, because `fn eq(&self, other: &Self)` through a shared vtable would let you compare a `Circle` to a `String` (hence no `dyn PartialEq`, no `dyn Ord`); and no associated constants, because there is nowhere in the calling convention to put a non-function value.
**Follow-up trap:** *"How does `Iterator` manage to be dyn compatible when it has 70-odd methods, many of them generic?"* Every provided method that is generic carries `where Self: Sized`, which excludes it from the vtable while keeping it callable on concrete types. Only `next` is required and it is dispatchable, so `Box<dyn Iterator<Item = u32>>` works and you can call `.next()` on it. The subtlety underneath: you *can* still call `.map()` on that `Box`, because `Box<I>` where `I: Iterator + ?Sized` itself implements `Iterator` and `Box` is `Sized`. If the interviewer asks "so how do I make my trait dyn compatible," the answer is the same mechanism: `where Self: Sized` on the offending methods, or erase the generic (`&mut dyn Write` instead of `W: Write`).

### Q4 — Explain the orphan rule and why it exists. When has it blocked you?

**Testing:** whether coherence is understood as a system property, not a compiler annoyance.
**Answer:** Coherence is the guarantee that for any trait and any type there is at most one applicable impl across the entire program including all transitive dependencies. Without it, two crates in your dependency graph could each define `impl Display for u32` and linking them would be unresolvable, or worse, adding an unrelated dependency could silently change what `x.to_string()` does. The orphan rule enforces this across crate boundaries: `impl ForeignTrait<T1..Tn> for T0` is only allowed if at least one of `T0..Tn` is local and no uncovered type parameter appears before the first local type. Practically: your trait for anyone's type, yes; anyone's trait for your type, yes; someone else's trait for someone else's type, no. It blocks you at `impl Display for Vec<u8>`, and the standard fix is a newtype (`struct Hex(Vec<u8>)`), which is zero-cost because a single-field tuple struct has identical layout to its field.
**Follow-up trap:** *"Is adding a blanket impl to an existing published trait a breaking change?"* Yes, in the general case, and most people say no. `impl<T: Display> MyTrait for T` will produce `error[E0119]` in any downstream crate that already wrote `impl MyTrait for TheirType` where `TheirType: Display`. It adds no method to any signature, so it looks additive, but it consumes coherence budget permanently and there is no `specialization` on stable to break the tie (RFC 1210 has been unstable since 2015 with known soundness holes around lifetime-dependent specialisation). The related pattern worth naming: sealing a trait with a private supertrait in a private module, so only your crate can implement it and you can add methods later without a semver break.

### Q5 — Walk me through exactly what `?` desugars to.

**Testing:** whether the `From` conversion is understood, which is the whole design.
**Answer:** `let n = f()?;` becomes `let n = match f() { Ok(v) => v, Err(e) => return Err(From::from(e)) };`, modulo the `Try` trait indirection. The `From::from` is the entire point: a function returning `Result<T, MyError>` can `?` any call returning `Result<_, E>` for which `impl From<E> for MyError` exists, so you write each conversion once and every call site in the crate gets it free. This is what Go's `if err != nil { return fmt.Errorf("%w", err) }` cannot do without repeating the wrap at every site. It costs nothing at runtime beyond a branch: no unwinding, no stack capture, no allocation, and with a niche-optimised `Result` it typically compiles to a test and a conditional branch. `?` also works on `Option`, returning `None` early, but you cannot mix the two in one function; convert with `.ok_or(e)?` and `.ok()?`.
**Follow-up trap:** *"Can you make `?` work on your own type?"* Not on stable as of Rust 1.97. The `Try` trait is `#[unstable(feature = "try_trait_v2")]`, so `?` is limited to `Result`, `Option`, `ControlFlow`, and `Poll`-wrapped variants. This is the one honest exception to "`Option` and `Result` are not special-cased." The rest of the claim holds: both are plain library enums in `core::option`/`core::result`, defined in about ten lines using no syntax you cannot use; what makes them feel special is that they are in the prelude and are `#[must_use]`.

### Q6 — `thiserror` or `anyhow`? Defend the choice.

**Testing:** whether the library/application split is understood as a *type-system* argument rather than a style preference.
**Answer:** Libraries return concrete matchable errors, applications return opaque contextual ones, and the reason is the caller's decision procedure. A library caller must distinguish "file missing, use a default" from "file corrupt, fail loudly" from "network timeout, retry with backoff"; `match` on an error enum is the only way to express that in the type system. `thiserror` 2.0.19 is a pure proc macro that writes the `Display`, `Error`, and `From` impls you would write by hand, with zero runtime cost and no runtime dependency. `anyhow` 1.0.104 gives you one opaque type, 8 bytes on 64-bit (it stores the vtable inside the allocation rather than beside the pointer, versus 16 bytes for `Box<dyn Error + Send + Sync>`), plus `.context()`/`.with_context()` chaining and a backtrace captured when `RUST_BACKTRACE=1`. In an application, where the handling is almost always "log with context, return 500," a 40-variant enum buys nothing and costs a `Display` impl per variant, a semver hazard per addition, and a `size_of` inflated to the largest variant. What teams actually ship: `thiserror` at module boundaries inside a service, `anyhow::Result` in `main`, binaries, tests, and glue.
**Follow-up trap:** *"What breaks if a library returns `anyhow::Error`?"* Three things. Callers lose matchability and are reduced to `downcast_ref` against a concrete type you never documented, which silently returns `None` the day you change it, or to string-matching your `Display` output, which makes your log messages a de facto API. Second, `anyhow` becomes a public dependency, so an `anyhow` 2.0 is a breaking change for every downstream crate. Third, the conversion is one-way: `thiserror` into `anyhow` is one `?`, and the reverse is impossible. Mention `snafu` and `eyre`/`color-eyre` as real alternatives rather than presenting a two-horse race; `snafu`'s context selectors attach structured context to enum variants more cleanly than `thiserror` does.

### Q7 — Why is `unwrap()` in a library a bug, and when is panicking correct?

**Testing:** whether the candidate distinguishes recoverable from unrecoverable and knows the process-level consequences.
**Answer:** `unwrap()` converts something the caller could have handled into a process-level event they never opted into. Under the default `panic = "unwind"` in a Tokio service, the unwind stops at the task boundary and surfaces as `JoinError::is_panic`, so one malformed input silently kills one task, and if nobody awaits the handle it vanishes entirely; in an Axum or Actix handler the middleware turns it into a bare 500 with no structured body. Under `panic = "abort"`, common in release profiles for smaller binaries and mandatory in some embedded contexts, the same call kills the whole multi-tenant process. Across an `extern "C"` boundary it is a guaranteed abort. And it destroys the error chain: `Result` composes, a panic does not. Panicking is correct for broken invariants inside your own code, states you have proved unreachable: indexing a slice you just sized, a poisoned lock, an `unreachable!()` after an exhaustive check. The mechanical test is "could a well-behaved caller passing valid arguments trigger this?" If yes, it must be a `Result`.
**Follow-up trap:** *"How do you enforce that across a team?"* Deny `clippy::unwrap_used` and `clippy::panic` at the library crate root, warn on `clippy::expect_used` and `clippy::indexing_slicing` (`a[i]` panics, `a.get(i)` returns `Option`), scoped to non-test code because `unwrap()` in tests is idiomatic. Each exception gets a per-site `#[allow]` with a comment justifying why the state is unreachable, which turns "we don't unwrap" from a wiki page into a CI gate. The second-order trap: someone will point out that `expect("...")` is not better than `unwrap()`. It is marginally better because the message names the violated invariant, but it is the same failure mode, so it is a `warn`, not an `allow`.

### Q8 — Your compile time went from 40 seconds to 9 minutes after a small change. Diagnose it.

**Testing:** whether monomorphisation is understood as an operational cost with a diagnostic procedure.
**Answer:** First check `cargo build --timings`, which produces an HTML flamegraph splitting frontend from codegen per crate; if codegen dominates one crate, it is monomorphisation. Then `cargo llvm-lines --release | head -30`, which reports LLVM IR line counts aggregated per generic function along with the number of copies. The signature finding is a function with a large body and a high copy count, typically because someone added a generic parameter to a widely-called function, or because a serde-derived impl is now instantiated across many more types. The fix is the de-monomorphisation trick that `std` uses on itself: keep the ergonomic generic wrapper two lines long and move the real body into a non-generic inner function, `fn read<P: AsRef<Path>>(p: P) { fn inner(p: &Path) { /* 60 lines */ } inner(p.as_ref()) }`. The wrapper gets stamped out per caller type; the body compiles exactly once. If that is not enough, move the boundary to `&dyn`.
**Follow-up trap:** *"What if the binary also grew by 4 MB?"* Same root cause and same first fix, then a separate measurement: `cargo bloat --release --crates` for per-crate `.text` attribution and `cargo bloat --release -n 20` for symbols. The release-profile knobs are `lto = "fat"`, `codegen-units = 1`, `panic = "abort"`, `opt-level = "z"`, and `strip = true`, and the trap is applying all five and reporting the aggregate: measure each independently, because `panic = "abort"` also changes semantics (no unwinding, so no `catch_unwind`, and Tokio task panics become process aborts), which is a correctness decision, not a size knob.

### Q9 — What does `#[non_exhaustive]` do and when do you put it on?

**Testing:** semver awareness, which separates people who have published crates from people who have written them.
**Answer:** On a public enum, `#[non_exhaustive]` forces downstream crates to include a wildcard arm in any `match`, which means you can add variants in a minor release without breaking them. Your own crate still gets full exhaustiveness checking; only foreign crates are constrained. On a struct it prevents downstream functional-update and literal construction, forcing them through your constructor. Without it, every new enum variant is a semver-major break, because every downstream exhaustive `match` stops compiling. Put it on public error enums and public event enums from day one: it is a one-line change that is major exactly once and buys unlimited future variants.
**Follow-up trap:** *"Doesn't that throw away the exhaustiveness guarantee you just called Rust's best refactoring tool?"* For your consumers, yes, deliberately, and that is the trade: they give up compile-time notification of new variants in exchange for not being broken by them. Inside your own crate nothing is lost. The related judgement call is where to use `_` arms internally: on an enum you own, a `_` arm permanently opts that site out of the check, so use explicit variants for enums you control and reserve `_` for genuinely open sets (integers, strings, foreign `#[non_exhaustive]` enums). `clippy::wildcard_enum_match_arm` makes that mechanical.

### Q10 — What are match ergonomics, and what changed in the 2024 edition?

**Testing:** current-language awareness and whether the candidate understands binding modes rather than pattern-matching by trial and error.
**Answer:** When you match a reference against a non-reference pattern, the compiler auto-dereferences and flips the *default binding mode* from `move` to `ref` (or `ref mut`), so bindings come out as references. `match &opt { Some(s) => ... }` binds `s: &String`, and before match ergonomics landed in Rust 1.26 you had to write `match &opt { &Some(ref s) => ... }`. The 2024 edition (stable from Rust 1.85, 2025-02-20) added the RFC 3627 reservations: once the default binding mode is not `move`, writing an explicit `mut`, `ref`, or `ref mut` on a binding is an error, and reference patterns (`&`, `&mut`) may only appear while the pattern prefix is still fully explicit. That deliberately outlaws the confusing half-explicit middle ground and reserves design space for a fuller proposal in a later edition. `cargo fix --edition` migrates affected code.
**Follow-up trap:** *"Why not just fix match ergonomics properly in 2024 instead of reserving?"* Because the full RFC 3627 semantics were still contested and an edition is the only place you can change pattern behaviour without breaking existing code, so the team shipped what is informally called "RFC 3627-nano," the minimal restriction that is forward-compatible with every candidate proposal. This is worth knowing as a general pattern in Rust's evolution: editions reserve syntax first, then decide. The adjacent thing to know cold is `let ... else`, stable since Rust 1.65 (2022-11-03), whose `else` block must diverge (type `!`), and if-let chains, stable in the 2024 edition from Rust 1.88 (2025-06-26).

### Q11 — You need a collection of mixed types implementing one trait. Walk me through the options and pick one.

**Testing:** whether the candidate knows there are three options, not two.
**Answer:** Generics do not solve this at all: `Vec<T>` where `T: Draw` holds one concrete `T`, so it is not an alternative that was rejected, it is a thing that does not work. That leaves `Vec<Box<dyn Draw>>`, which handles an open set (implementations can live in other crates, including ones that do not exist yet), costs 16 bytes per element plus one heap allocation each plus an indirect call per method, and requires `Draw` to be dyn compatible, so no `Clone`, no `PartialEq`, no generic methods, no `async fn`. Or an enum with one variant per implementation, which handles a closed set only, gives you static dispatch through an exhaustive `match`, derives `Clone`/`PartialEq`/`Debug` freely, and requires no heap allocation, at the cost of every value being sized to the largest variant. The `enum_dispatch` crate generates the delegating match. Decision rule: closed and known at compile time means enum; open or plugin-shaped means `dyn`.
**Follow-up trap:** *"You picked `dyn`, and now you need to clone the collection."* `Clone` is not dyn compatible because `fn clone(&self) -> Self` returns an unsized-to-the-caller type, so you add `fn clone_box(&self) -> Box<dyn Draw>` to the trait and implement it as `Box::new(self.clone())` in each impl, or use the `dyn-clone` crate which generates that. But the honest senior answer is that needing `Clone`, `PartialEq`, and `Default` on a trait object is a strong signal the set was actually closed and should have been an enum. Recognising the smell beats knowing the workaround.

### Q12 — Why does `"42".parse()` sometimes need a turbofish, and what error do you get?

**Testing:** inference literacy, and whether E0282/E0283 are recognised on sight.
**Answer:** `str::parse` is `fn parse<F: FromStr>(&self) -> Result<F, F::Err>`, generic over its *return* type, so nothing in the call constrains `F` unless the binding is annotated or the value flows into a typed context. With no constraint you get `error[E0282]: type annotations needed`, or `error[E0283]` when several impls could apply and the message lists candidates. Fix with a turbofish at the call, `"42".parse::<i32>()?`, or by annotating the binding, `let n: i32 = "42".parse()?;`. They are equivalent; turbofish reads better mid-chain. `collect` is the same shape and the far more common source: `.collect::<Vec<_>>()`, `.collect::<HashMap<String, u64>>()`, and the underrated `.collect::<Result<Vec<_>, E>>()`, which turns an iterator of `Result` into a `Result` of `Vec` and short-circuits on the first error.
**Follow-up trap:** *"What about `error[E0207]: the type parameter 'T' is not constrained by the impl trait, self type, or predicates`?"* Different failure, and people conflate them. E0282 is inference having no information; E0207 is an `impl` block declaring a type parameter that appears nowhere in the trait being implemented or in the self type, so two impls differing only in `T` would be indistinguishable and the compiler rejects the impl outright rather than at use. The three fixes: add a `PhantomData<T>` field so `T` appears in the self type, move `T` from the impl block down to individual methods, or turn `T` into an associated type on the trait. Reaching for `PhantomData` without being able to say *why* it fixes it is the tell.

### Q13 — How do you get the root cause into your logs when a `thiserror` enum wraps three layers of failure?

**Testing:** production error observability, which almost nobody prepares for.
**Answer:** `Error::source()` is the chain, and `#[from]` (or an explicit `#[source]`) on a `thiserror` variant is what implements it. The bug is that `e.to_string()` and `tracing`'s `error = ?e` render only the top layer's `#[error("...")]` string, so you get "database error" in the alert and nothing about the connection refusal underneath. The fix is a five-line walker that loops on `source()` accumulating messages, logged as `error = %chain(&e)`; `anyhow`'s `{:?}` formatting already does exactly this plus a `std::backtrace::Backtrace` (stabilised Rust 1.65) when `RUST_BACKTRACE=1`. `tracing-error` adds `SpanTrace` so you also get the span context the error passed through, which is usually more useful than a raw stack in async code because the stack is a Tokio poll frame, not your call path.
**Follow-up trap:** *"Should the outer `Display` include the inner error's message?"* No, and this is the most common `thiserror` mistake. Each layer's `Display` describes only its own layer; the chain supplies the rest. Writing `#[error("io failure: {0}")]` on a `#[from]` variant produces logs like `io failure: No such file or directory: No such file or directory` once the walker also prints the source. `thiserror` will not stop you, so it is a review item.

### Q14 — Compare Rust generics to Java generics and Go interfaces for someone coming from both.

**Testing:** whether the candidate can locate Rust's design in a landscape rather than describing it in isolation.
**Answer:** Against Java: Java erases, so `List<String>` and `List<Integer>` are one class at runtime with compiler-inserted casts, primitives must be boxed (an `ArrayList<Integer>` of 1,000,000 elements is 1,000,000 heap objects with pointer chasing, versus a contiguous 4 MB buffer for `Vec<i32>`), and you cannot make a type you do not own implement your interface. Rust monomorphises, so `Vec<i32>` is genuinely a contiguous `i32` buffer, and the orphan rule permits `impl MyTrait for String` because your trait is local. Bounds are also checked at *definition* time, not instantiation time, so a missing capability is an `E0277` on your generic function, not a page of instantiation backtrace at the call site, which is the C++-before-Concepts failure mode. Against Go: Go interfaces are structural and implicit, satisfied by having the methods, so accidental conformance and cross-interface method-name collisions are real hazards; Rust traits are nominal and explicit, you write `impl Draw for Circle`, and two traits may share a method name because you disambiguate with `Draw::area(&x)`. Go's interface value is a two-word fat pointer, structurally identical to `&dyn Trait`, and Go's dispatch is always dynamic where Rust's default is static.
**Follow-up trap:** *"Given Go's generics since 1.18, isn't this the same thing now?"* No, and the mechanism is the interesting part. Go implements generics with GC shape stenciling plus dictionaries, generating one copy per memory-layout class rather than per type, with a dictionary passed at runtime for type-specific operations. That is a deliberate compromise: less code bloat and faster compiles than full monomorphisation, but dispatch through the dictionary for many operations, so you do not get Rust's full inlining. Naming that tradeoff, rather than saying "Go has generics too now," is the answer that lands. Also worth noting: Go's error handling is still convention (`if err != nil`), with no compiler enforcement, while Rust's `Result` is `#[must_use]` so ignoring one is a warning out of the box.

---

## Red flags that fail you

- Saying "generics are zero-cost so they're always faster than `dyn`" without naming compile time, binary size, or instruction-cache pressure, and without being able to name a single tool that would measure it.
- Not knowing what a trait object actually is at the machine level. If you cannot say "fat pointer, data pointer plus vtable pointer, 16 bytes on 64-bit," you have not looked.
- Reciting the dyn-compatibility rules as a memorised list without being able to derive any of them from the vtable, and in particular being unable to say why `Clone` fails.
- Claiming `Option` and `Result` are compiler built-ins, or conversely claiming nothing about them is special without mentioning the prelude, `#[must_use]`, and the unstable `Try` trait.
- Describing `?` as "like exceptions but nicer." It is an early return plus a `From` conversion, with no unwinding, no stack capture, and no dynamic dispatch. Getting this wrong signals you have never read the desugaring.
- Being unable to state the `From::from` step in the `?` desugaring, which is the single mechanism that makes error composition work.
- Using `anyhow` in a library's public API and not being able to name what it costs the caller.
- Defending `unwrap()` in library code with "but it can't fail here" and no invariant argument, or not knowing the difference between `panic = "unwind"` and `panic = "abort"` for the caller.
- Not knowing that an enum variant addition is a semver-major break, or never having heard of `#[non_exhaustive]`.
- Reaching for `_ => {}` on an enum you own, which silently disables the exhaustiveness guarantee you just described as Rust's best refactoring tool.
- Saying associated types and generic parameters are "basically the same" or "a style choice." The "how many impls per type" distinction is load-bearing.
- Not knowing that a blanket impl on a published trait can break downstream crates, or believing `specialization` will save you.
- Suggesting `#[async_trait]` for a trait that is only ever used with static dispatch, or not knowing why it exists (dyn compatibility) and what it costs (one `Pin<Box<dyn Future>>` allocation per call).
- Confusing `error[E0282]` (inference has no information) with `error[E0207]` (an impl parameter is unconstrained), or fixing E0207 with `PhantomData` without being able to explain why that works.
- Logging `e.to_string()` on a nested error type and being surprised the root cause is missing.

## Cheat card

```
DISPATCH. Static = generics = monomorphisation: one machine-code copy
  per concrete T, direct + inlinable, thin 8-byte ptr. Size ~ n_types
  x body. Dynamic = dyn Trait: ONE copy, fat 16-byte ptr (data +
  vtable), indirect call, no inlining through it. Static is the
  DEFAULT; opt into dyn. Measure: cargo llvm-lines, cargo bloat,
  cargo build --timings, criterion + perf stat.

VTABLE. Emitted once per (concrete type, trait) into .rodata:
  drop_in_place ptr, size, align, then one slot per dispatchable
  method. Layout NOT guaranteed - never transmute it.

DYN COMPATIBILITY (was "object safety", E0038). Trait qualifies if:
  no Self: Sized supertrait, all supertraits dyn compatible, no
  assoc consts, no assoc types with generics (so NO GATs).
  Method dispatchable if: no generic type params (lifetimes ok),
  no Self except as receiver, receiver in {&self, &mut self,
  Box/Rc/Arc/Pin<Self>}, no where Self: Sized.
  => Clone/Copy/Default/From/Into (Self in return), PartialEq/Ord
  (Self in arg) are NOT dyn compatible. Escape hatch: put
  `where Self: Sized` on the method (how Iterator stays dyn-safe:
  only next() is in the vtable). Trait upcasting: stable 1.86
  (2025-04-03), &dyn Sub -> &dyn Super.

ASSOC TYPE vs GENERIC PARAM. Generic param = INPUT, many impls per
  type (From<T>: String has From<&str>, From<char>, ...).
  Assoc type = OUTPUT, exactly ONE impl per type (Iterator::Item;
  makes .next() inferable without turbofish). tower::Service<Req>
  uses both. GATs stable 1.65 (2022-11-03).

COHERENCE. At most one impl per (trait, type) program-wide.
  Overlap check -> E0119. Orphan rule -> E0117: impl allowed if the
  trait OR one of the types is local. YOUR trait for THEIR type: ok.
  THEIR trait for YOUR type: ok. Theirs for theirs: no -> newtype
  (struct Hex(Vec<u8>), zero-cost). Blanket impl (impl<T: Display>
  ToString for T) is a SEMVER-BREAKING addition to a published trait.
  Sealed trait = private supertrait in private module.

GENERICS. Bounds checked at DEFINITION time (not C++ instantiation
  time). `impl Trait` arg position = anon generic, NO turbofish.
  Return position (1.26): one concrete type on all paths; box to
  return two. Precise capturing `+ use<'a, T>` since 1.82
  (2024-10-17); 2024 edition captures all params by default.
  RPITIT + async fn in traits: stable 1.75 (2023-12-28), NOT dyn
  compatible -> #[async_trait] boxes to Pin<Box<dyn Future + Send>>,
  1 heap alloc per call. const generics: min_const_generics 1.51
  (2021-03-25); `[T; N+1]` needs generic_const_exprs, still unstable
  + incomplete in 2026. recursion_limit default 128.

ENUMS. Tagged union: tag + max(payload), padded. Option/Result are
  ORDINARY enums in core::option/core::result. Special only via:
  prelude, #[must_use], and `?` (Try trait still unstable, so you
  can't make ? work on your type). Niche opt:
    size_of::<Option<&T>>()         == 8   (null is the niche)
    size_of::<Option<NonZeroU32>>() == 4
    size_of::<Option<u32>>()        == 8   (no niche -> real tag)
    size_of::<Option<bool>>()       == 1
    size_of::<std::io::Error>()     == 8   (tagged ptr, 64-bit)

MATCHING. E0004 non-exhaustive = your refactoring tool: adding a
  variant breaks every match. `_ =>` on an enum you OWN throws that
  away (clippy::wildcard_enum_match_arm). #[non_exhaustive] forces
  downstream `_` so you can add variants in a MINOR release.
  Match ergonomics: matching a ref against a non-ref pattern flips
  default binding mode to `ref`. Rust 2024 (1.85, 2025-02-20):
  RFC 3627 reservations - no explicit mut/ref/ref mut once DBM != move.
  let-else stable 1.65, else block must diverge (type !).
  if-let chains stable in 2024 edition from 1.88 (2025-06-26).
  Guards defeat exhaustiveness checking - you still need a catch-all.

? DESUGARING (memorise):
    let n = f()?;
  == match f() { Ok(v) => v, Err(e) => return Err(From::from(e)) }
                                                  ^^^^^^^^^^ the design.
  Write `impl From<E> for MyError` once; every ? converts free.
  Works on Option (early None) but can't mix - use .ok_or(e)? / .ok()?.
  fn main() -> Result<(), E: Debug> is allowed; Err exits with code 1.
  Zero runtime cost: no unwind, no stack capture, one branch.

ERRORS. LIBRARY -> thiserror 2.0.19: proc macro writing Display +
  Error + From. #[from] generates the From impl AND sets source().
  #[source] for chain-without-Display. Put #[non_exhaustive] on it.
  APPLICATION -> anyhow 1.0.104: opaque, 8 bytes on 64-bit (vtable
  inside the allocation; Box<dyn Error + Send + Sync> is 16).
  .context() eager / .with_context() lazy. {:?} prints chain +
  backtrace when RUST_BACKTRACE=1. Requires Send + Sync + 'static.
  Alternatives worth naming: snafu (context selectors), eyre/color-eyre.
  core::error::Error stable since 1.81 (2024-09-05) -> no_std works.
  Each layer's Display describes ONLY its layer; walk source() when
  logging or the root cause is missing from the alert.

UNWRAP IN A LIBRARY = BUG. unwind -> Tokio JoinError, task dies
  silently, bare 500. abort -> whole process dies. Across extern "C"
  -> guaranteed abort. Panic is for YOUR broken invariants only.
  Test: "could a valid caller trigger this?" yes -> Result.
  Enforce: deny clippy::unwrap_used + clippy::panic at the lib root,
  warn expect_used + indexing_slicing, non-test only.

CURRENT (2026-08-05): rustc 1.97.1 (2026-07-16), edition 2024
  (since 1.85). thiserror 2.0.19, anyhow 1.0.104.
  Still unstable: specialization (RFC 1210, since 2015),
  generic_const_exprs, try_trait_v2, async fn in dyn Trait.
```

## Sources

- [The Rust Reference — Traits (dyn compatibility rules)](https://doc.rust-lang.org/reference/items/traits.html) — accessed 2026-08-05
- [The Rust Reference — Implementations (orphan rule, coherence)](https://doc.rust-lang.org/reference/items/implementations.html) — accessed 2026-08-05
- [Rust Release Notes / releases.rs — version and date index](https://releases.rs/) — accessed 2026-08-05
- [Announcing Rust 1.86.0 — trait upcasting stabilisation](https://blog.rust-lang.org/2025/04/03/Rust-1.86.0/) — accessed 2026-08-05
- [The Rust Edition Guide — Rust 2024: match ergonomics reservations](https://doc.rust-lang.org/edition-guide/rust-2024/match-ergonomics.html) — accessed 2026-08-05
- [The Rust Edition Guide — Rust 2024: RPIT lifetime capture rules](https://doc.rust-lang.org/edition-guide/rust-2024/rpit-lifetime-capture.html) — accessed 2026-08-05
- [RFC 3627 — Match ergonomics 2024](https://rust-lang.github.io/rfcs/3627-match-ergonomics-2024.html) — accessed 2026-08-05
- [RFC 2451 — Re-rebalancing coherence](https://rust-lang.github.io/rfcs/2451-re-rebalancing-coherence.html) — accessed 2026-08-05
- [RFC 3617 — Precise capturing (`use<..>` bounds)](https://rust-lang.github.io/rfcs/3617-precise-capturing.html) — accessed 2026-08-05
- [core::error — Rust standard library docs (`Error` in core, stable 1.81)](https://doc.rust-lang.org/stable/core/error/index.html) — accessed 2026-08-05
- [thiserror on crates.io — 2.0.19, published 2026-07-18](https://crates.io/crates/thiserror) — accessed 2026-08-05
- [anyhow on crates.io — 1.0.104](https://crates.io/crates/anyhow) — accessed 2026-08-05
- [dtolnay/async-trait — boxing `async fn` for dyn compatibility](https://github.com/dtolnay/async-trait) — accessed 2026-08-05
- [Async fn in dyn Trait — async fn fundamentals initiative](https://rust-lang.github.io/async-fundamentals-initiative/explainer/async_fn_in_dyn_trait.html) — accessed 2026-08-05
- [The Rust Unstable Book — generic_const_exprs](https://doc.rust-lang.org/beta/unstable-book/language-features/generic-const-exprs.html) — accessed 2026-08-05
- [Full Const Generics — Rust Project Goals 2026](https://rust-lang.github.io/rust-project-goals/2026/const-generics.html) — accessed 2026-08-05
- [Raph Levien — Thoughts on Rust bloat (monomorphisation and binary size)](https://raphlinus.github.io/rust/2019/08/21/rust-bloat.html) — accessed 2026-08-05
- [rust-lang/rust issue #65991 — tracking issue for dyn upcasting coercion](https://github.com/rust-lang/rust/issues/65991) — accessed 2026-08-05
- [Ixrec/rust-orphan-rules — the orphan rule and coherence, explained](https://github.com/Ixrec/rust-orphan-rules/blob/master/README.md) — accessed 2026-08-05
- [rustc dev guide — Const Generics](https://rustc-dev-guide.rust-lang.org/const-generics.html) — accessed 2026-08-05

## Changelog
- 2026-08-05 — created
