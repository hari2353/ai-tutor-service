# TypeScript: Structural Typing, Generics, Narrowing, Utility Types, and Where It Lies to You

> **Track:** T33 Frontend & UI Engineering · **Time:** 2.5h · **Prereqs:** T33-js-deep
> **Module id:** `T33-typescript` · **Tags:** language

## The 30-second version

TypeScript's type system is **structural**, not nominal: two types are compatible if their shapes match, regardless of name or declared inheritance, which is why an object literal satisfies an interface it never declared implementing. It's also **erased entirely at compile time** — every type annotation, generic parameter, and interface is deleted before the code runs, which means TypeScript can guarantee nothing at runtime, only at the boundary of what you told the compiler. Generics let you write functions/types parameterized over a type variable while preserving the specific type through the call (`function identity<T>(x: T): T`), and variance governs whether `Container<Dog>` can substitute for `Container<Animal>` — TypeScript defaults to structural, largely covariant-in-practice checking for most positions rather than strict variance enforcement, which is intentionally unsound in specific documented cases (function parameter bivariance under `strictFunctionTypes` being the classic one) for pragmatic ergonomics. Narrowing lets the compiler refine a union type based on runtime checks (`typeof`, `in`, discriminated union tags, custom type guards), and a discriminated union with a shared literal-typed tag field is the single most useful pattern for making illegal states unrepresentable. `unknown` is the type-safe counterpart to `any`: both accept anything, but `unknown` forces you to narrow before you can do anything with the value, while `any` opts an entire subtree of code out of type checking silently. And TypeScript genuinely lies to you in specific, nameable ways: `as` type assertions don't check anything at runtime (they're a compile-time-only claim you're making to the compiler, and a wrong one produces a runtime crash with zero warning), non-null assertions (`!`) are the same lie about nullability, and declaration merging plus structural typing together mean the type system can be "correct" at the type level while the actual runtime value silently satisfies zero of your assumptions if it crossed an unchecked boundary (an API response cast with `as`, a `JSON.parse()` result typed by hand).

## Why this gets asked

Because "I know TypeScript" usually means "I can write interfaces and generics," and the interviewer wants to know if you understand where the type system's guarantees actually stop — which is exactly where production bugs happen, because that's where nobody's watching. They've shipped (or debugged) a runtime crash caused by an `as` assertion on an API response that silently changed shape, or a `!` non-null assertion on a value that actually was null in some edge case the type checker couldn't see, and they want to know if you reach for those tools carelessly or as a last resort with eyes open. The other thing being tested is whether you can use the type system as a design tool — discriminated unions to make illegal states unrepresentable, `unknown` instead of `any` at trust boundaries — rather than just decorating existing JavaScript with type annotations after the fact.

---

## Lineage: past → present → future

**What came before.** JavaScript shipped with no static type system at all, and by the early 2010s, large JS codebases (Microsoft's own internal tools among them) were hitting a specific, well-documented pain: refactoring confidence collapsed past a certain codebase size, because nothing caught a typo'd property name or a function called with the wrong argument shape until runtime, often in production. Competing answers existed simultaneously — Facebook's Flow (2014) took a similar structural-typing approach with different tooling and inference tradeoffs, and Google's Closure Compiler used JSDoc-based annotations for a type-checked subset of JS. TypeScript (Microsoft, first public release October 2012) won the ecosystem battle not primarily on type-system sophistication but on being a **strict superset of JavaScript with erasure-based compilation** — any valid JS is (almost) valid TS, and the emitted output is just JS with the types stripped, which made incremental adoption in existing codebases dramatically lower-friction than Flow's more invasive tooling story turned out to be in practice.

**Where it stands now.** TypeScript is the de facto standard for any JS codebase past a small size — virtually all major frontend frameworks (React, Vue, Angular, Svelte) and their ecosystems ship first-class TS support, and `strict` mode (bundling `strictNullChecks`, `noImplicitAny`, `strictFunctionTypes`, and others) is now the default recommendation for new projects rather than an opt-in extra. TypeScript 6.0 (shipped March 23, 2026) was explicitly positioned as the **last release built on the original JavaScript-based compiler** — a deliberate bridge release, flipping several long-standing defaults on (stricter mode defaults, ESM as the default module system, an `es2025` target) and removing legacy compiler options, in preparation for the next architectural shift. The live disagreement in the ecosystem isn't "should you use TypeScript" (settled) but how strict to run it — full `strict` plus `noUncheckedIndexedAccess` catches real bugs but has real friction cost in codebases with heavy dynamic object access, and teams genuinely differ on where that line sits.

**Where it's heading.** The major, concrete, already-in-motion change is **TypeScript 7.0**, a from-scratch rewrite of the compiler and language service in Go rather than TypeScript/JavaScript, reported at roughly **10x faster** compilation and type-checking. It reached beta in April 2026 and Release Candidate on June 18, 2026, shipping shortly after. This isn't speculative — it's a Microsoft-announced, actively-shipping migration, and the practical implication for any team is that project references, build times, and editor responsiveness on large codebases are about to change materially, without the *type system semantics* themselves changing (7.0 is a reimplementation of the same language, not a new language). What's more genuinely uncertain is how quickly the ecosystem (bundlers, IDE plugins, third-party tools that shell out to `tsc`) fully migrates to the Go-based toolchain versus continuing to support both for a transition period — that's a real open question, not a confident prediction.

---

## Mental model

```
STRUCTURAL TYPING:                    NOMINAL TYPING (Java/C#, for contrast):
  type Point = {x:number, y:number}     class Point { x:number; y:number }
  function log(p: Point) {...}          void log(Point p) {...}
  log({x:1, y:2, z:3})  // OK!          log(new Object() {...})  // ERROR
  // shape matches -> compatible          // must be declared Point, name matters
  // (excess property check only
  //  fires on OBJECT LITERALS
  //  passed directly, not on
  //  variables holding the object)

ERASURE:  source.ts  --tsc-->  source.js  (types deleted, ZERO runtime trace)
  const x: number = "5" as unknown as number;  // compiles fine, types erased
  console.log(x);                               // runtime: "5" (a string!) — the
                                                  // type system was WRONG and nothing
                                                  // at runtime knows or cares
```

The one sentence that matters: TypeScript checks that your code is *consistent with the types you wrote*, not that your types are *true*. Every unchecked boundary — API responses, `JSON.parse`, `as`, `!`, third-party `.d.ts` files — is a place where those two things can silently diverge.

---

## How it actually works

### Structural typing, concretely

```ts
interface Point { x: number; y: number; }

function distance(p: Point): number {
  return Math.sqrt(p.x ** 2 + p.y ** 2);
}

const literal = { x: 3, y: 4 };
distance(literal);              // OK — shape matches, no declared relationship to Point

const withExtra = { x: 3, y: 4, z: 5 };
distance(withExtra);            // OK — extra properties on a VARIABLE are fine

distance({ x: 3, y: 4, z: 5 }); // ERROR — excess property check fires on object
                                 // LITERALS passed directly, specifically to catch typos
                                 // like { x: 3, y: 4, zz: 5 } that would otherwise
                                 // silently pass structural compatibility
```

The excess-property-check asymmetry (literal vs. variable) is a real, frequently-tested gotcha: it exists specifically because a mistyped property name in an object literal (`{ nam: "x" }` instead of `{ name: "x" }`) would otherwise satisfy an interface structurally (both are "objects with at least the required properties," since the extra mistyped property doesn't remove the fact that required properties might be *missing* and TS needs to catch that some other way) — but the check is deliberately narrow so that passing an already-existing object with genuinely extra properties (a common, legitimate pattern) isn't broken.

### Generics and variance

```ts
function identity<T>(x: T): T { return x; }
const n = identity(5);        // T inferred as number
const s = identity("hi");     // T inferred as string

interface Box<T> { value: T; }
declare const dogBox: Box<Dog>;
declare const animalBox: Box<Animal>;
function useAnimal(b: Box<Animal>) { /* ... */ }
useAnimal(dogBox);   // OK if Dog extends Animal — Box<T> is covariant here because
                      // TS structurally checks Box<Dog>'s `value: Dog` against
                      // Box<Animal>'s `value: Animal`, and Dog is assignable to Animal
```

**Variance in TypeScript is mostly structural and mostly covariant by default for property positions**, which is technically unsound for mutable containers (assigning a `Cat` into a `Box<Animal>` reference that's actually holding a `Box<Dog>` at runtime is a real hole) but is a deliberate ergonomics tradeoff most languages with structural typing make. The one place TypeScript is explicitly, documented-unsound by default is **function parameter bivariance**: without `strictFunctionTypes` enabled, a function type `(x: Dog) => void` is considered assignable to `(x: Animal) => void` and vice versa, even though only the first direction (contravariance in parameters) is actually type-safe — `strictFunctionTypes` (part of `strict` mode) tightens this to correct contravariant checking for standalone function types, though method syntax specifically (`interface Foo { method(x: Dog): void }` as opposed to a function-typed property) is still bivariant even under strict mode, a genuinely obscure but real, occasionally interview-relevant carve-out.

### Narrowing and discriminated unions

```ts
type Shape =
  | { kind: "circle"; radius: number }
  | { kind: "rectangle"; width: number; height: number };

function area(s: Shape): number {
  switch (s.kind) {                       // narrowing on the literal-typed tag field
    case "circle": return Math.PI * s.radius ** 2;      // s narrowed to the circle branch
    case "rectangle": return s.width * s.height;         // s narrowed to the rectangle branch
    default: {
      const _exhaustive: never = s;       // compile error if a Shape variant is unhandled —
      throw new Error(`unhandled: ${_exhaustive}`);  // this IS the exhaustiveness check pattern
    }
  }
}
```

The `never`-typed exhaustiveness check is the actual mechanism, not a convention: if a new variant is added to `Shape` and this `switch` isn't updated, `s` in the `default` branch is no longer assignable to `never`, and the compiler errors at the assignment — this turns "did you handle every case" from a code-review hope into a build failure, and it's the single most concrete argument for discriminated unions over a loose `{kind: string, ...}` shape with optional fields.

### `unknown` vs `any`

```ts
function handleAny(x: any) {
  x.toUpperCase();          // compiles — ANY property access/call is allowed, no checking at all
}
function handleUnknown(x: unknown) {
  x.toUpperCase();          // ERROR — must narrow first
  if (typeof x === "string") {
    x.toUpperCase();        // OK — narrowed to string
  }
}
```

`any` isn't just "loosely typed," it actively **disables type checking for everything that value touches**, including silently propagating to anything derived from it — `const y = (x as any).foo.bar.baz` type-checks with zero errors no matter how wrong it is. `unknown` accepts anything (like `any`) but forces explicit narrowing before any operation, which is exactly the correct type for "data I don't control yet" — API responses, `JSON.parse()` results, `catch` clause error variables (TypeScript 4.4+ types caught errors as `unknown` by default under `useUnknownInCatchVariables`, replacing the historical `any`, specifically because a thrown value's type is never actually knowable).

### Declaration merging

```ts
interface Window { myGlobal: string; }   // augments the existing global Window interface
// elsewhere, unrelated file:
interface Window { anotherGlobal: number; }
// both merge into ONE Window interface with both properties — this is intentional,
// used heavily for augmenting third-party/global types (e.g., adding a property
// a library attaches to `window` at runtime), but it means a type's full shape
// can be scattered across files with no single source of truth, and a
// declaration-merged addition compiles fine even if nothing at runtime actually
// sets `window.anotherGlobal` — the type system has no way to verify that
```

Declaration merging is a real, useful feature (module augmentation for extending third-party library types without forking them) and a real, nameable trust hazard: it lets you *declare* a runtime shape exists without any corresponding guarantee that it does.

### Utility types — the ones worth deriving, not memorizing

```ts
interface User { id: string; name: string; email: string; }

type PartialUser = Partial<User>;          // { id?: string; name?: string; email?: string }
type UserPreview = Pick<User, "id" | "name">;  // { id: string; name: string }
type UserNoEmail = Omit<User, "email">;    // { id: string; name: string }
type ReadonlyUser = Readonly<User>;        // all properties readonly
type UserRecord = Record<string, User>;    // { [key: string]: User }

// derived, not built-in — this is the actual skill: composing mapped types
type Nullable<T> = { [K in keyof T]: T[K] | null };
type UserWithNullableEmail = Omit<User, "email"> & { email: string | null };
```

`Partial`, `Pick`, `Omit`, `Readonly`, `Record` are all themselves implemented as small mapped types over `keyof`/index signatures in TypeScript's own standard library — knowing you can write `Pick`'s definition (`type Pick<T, K extends keyof T> = { [P in K]: T[P] }`) rather than just having memorized its behavior is the actual signal of generics fluency.

### Where TypeScript lies to you — the honest list

1. **`as` type assertions perform zero runtime checking.** `const n = value as number` compiles regardless of what `value` actually is at runtime; if it's a string, `n` is typed `number` but *is* a string, and every downstream operation assuming numeric behavior is now silently wrong until it crashes somewhere unrelated to the actual bug's origin.
2. **Non-null assertions (`!`) are the same lie about nullability.** `const el = document.getElementById("x")!` tells the compiler "trust me, this isn't null" — if the element doesn't exist, this is a runtime `null` that the type system now claims can never be null, and the crash happens wherever that value is later dereferenced, not at the assertion site.
3. **Types are fully erased — nothing is checked at runtime, ever, by TypeScript itself.** A function typed to accept `User` will happily execute against literally any object shape at runtime if that object arrived from an unchecked boundary (an untyped JS import, a `JSON.parse` result cast with `as`, a third-party library with an inaccurate `.d.ts`) — this is why runtime validation libraries (Zod, io-ts, valibot) exist as a *complement* to TypeScript, not a redundancy: they check shape at the actual boundary where data enters the system, which TS structurally cannot do.
4. **Third-party `.d.ts` files can simply be wrong**, hand-written or generated from an older/different version of the library than what's actually installed — the type checker trusts them completely, with no mechanism to detect drift between the declared types and the actual runtime behavior of the library.
5. **`any` in a dependency propagates silently.** One `any`-typed value anywhere in a call chain can make everything downstream of it effectively untyped, and because there's no visual marker once it's been reassigned to a differently-named variable, it's easy to lose track of exactly where type safety quietly stopped.

---

## Build it from scratch

The generics/variance mental model is best proven by implementing a small piece of the type system's actual behavior — a minimal discriminated-union-driven state machine, the pattern the "making illegal states unrepresentable" argument is really about:

```ts
// untested sketch — a fetch-state machine where invalid combinations
// (e.g., "loading" AND has "data") are structurally impossible to construct
type FetchState<T> =
  | { status: "idle" }
  | { status: "loading" }
  | { status: "success"; data: T }
  | { status: "error"; error: string };

function render<T>(state: FetchState<T>, formatData: (d: T) => string): string {
  switch (state.status) {
    case "idle": return "Not started";
    case "loading": return "Loading...";
    case "success": return formatData(state.data);   // `state.data` only exists in this branch
    case "error": return `Error: ${state.error}`;     // `state.error` only exists in this branch
    default: {
      const _exhaustive: never = state;
      throw new Error(`unhandled state: ${JSON.stringify(_exhaustive)}`);
    }
  }
}

// The bug this PREVENTS, structurally, at compile time:
// const bad = { status: "loading", data: someData };  // this compiles as a valid object,
// but passing it to render() as FetchState<T> fails: "loading" branch never had a `data`
// field in its type, so nothing downstream can accidentally read stale/wrong data —
// contrast with a single flat interface `{status: string, data?: T, error?: string,
// loading?: boolean}` where `loading: true` and `data: someOldData` coexisting is
// perfectly legal and a REAL, common source of stale-UI bugs in untyped/loosely-typed state.
render({ status: "success", data: 42 }, d => `Value: ${d}`);  // "Value: 42"
```

---

## How it's done in production

Real projects lean on `strict` mode plus a handful of specific flags (`noUncheckedIndexedAccess`, `exactOptionalPropertyTypes`) and, increasingly, a **runtime validation layer at every trust boundary** rather than trusting `as`.

```ts
// untested sketch — Zod at the API boundary, the actual production pattern
import { z } from "zod";
const UserSchema = z.object({ id: z.string(), name: z.string(), email: z.string().email() });
type User = z.infer<typeof UserSchema>;   // derive the TS type FROM the runtime schema,
                                            // not the other way around — one source of truth
async function fetchUser(id: string): Promise<User> {
  const res = await fetch(`/api/users/${id}`);
  const json = await res.json();          // json is `any` here — the actual unchecked boundary
  return UserSchema.parse(json);          // throws at runtime if the shape doesn't match —
                                            // this is the check `as User` could never provide
}
```

| Symptom | Cause | Fix |
|---|---|---|
| Runtime crash deep in unrelated code, stack trace points nowhere near the actual bad data | An `as` assertion or `!` non-null assertion lied about a value's shape/nullability at some earlier point, and the mismatch only surfaces when the wrongly-typed value is finally used in a way that breaks | Replace the assertion with actual runtime validation (Zod/io-ts) at the boundary where the data entered the system, so the failure surfaces at the source, not downstream |
| A refactor renames/removes a field, `tsc` reports zero errors, production breaks | The field was accessed through an `any`-typed intermediate (a third-party callback, an untyped JSON blob, a loosely-typed Redux action) that silently opted that access out of checking | Audit for `any` leakage along the affected path; replace with `unknown` + explicit narrowing, or a proper generic type, so a rename actually triggers a compiler error |
| A `switch` on a discriminated union compiles fine after adding a new variant, but the new case is silently unhandled at runtime | No `never`-typed exhaustiveness check in the `default`/fallback branch | Add `const _exhaustive: never = value;` in the fallback branch — this converts "forgot to handle a new case" into a build failure |
| Editor autocomplete/type-checking is noticeably slow on a large monorepo, `tsc --noEmit` takes minutes | The JS-based `tsc` compiler (pre-7.0) doing full type inference across a large project graph without adequate project references / incremental build config | Set up TypeScript project references for incremental builds; longer-term, TypeScript 7.0's Go-based compiler (RC as of June 2026, reported ~10x faster) directly targets this class of problem |
| A third-party library's types don't match its actual runtime behavior (e.g., claims a field is required but it's sometimes absent) | The `.d.ts` file (bundled or from `@types/*`) is stale, hand-written incorrectly, or written against a different library version than what's installed | Patch locally with `declare module` augmentation as a stopgap; file/fix upstream; never trust a `.d.ts` file's accuracy more than you'd trust the library's actual documented runtime behavior |

---

## Tradeoffs & when NOT to use it

- **Don't reach for `as any` or `as unknown as X` to silence an error you don't understand.** Both are real, if the type error reflects an actual runtime possibility (the value genuinely can be something else), you've just moved the bug from compile time to an unpredictable runtime crash; the correct move is almost always to understand *why* the checker is complaining before overriding it.
- **Don't chase 100% strictness in every codebase indiscriminately.** `strict` mode plus `noUncheckedIndexedAccess` catches real bugs but has genuine friction in codebases with heavy dynamic property access (e.g., wrapping loosely-typed legacy APIs) — the senior judgment call is knowing which flags earn their keep in a given codebase versus which just generate noisy assertions that get reflexively silenced.
- **Don't treat TypeScript as a substitute for runtime validation at trust boundaries.** Types are erased; anything crossing a boundary you don't control (API responses, environment variables, file contents, `JSON.parse`) needs an actual runtime check, not just a type annotation asserting what you hope is true.
- **Don't over-engineer generic types for their own sake.** Deeply nested conditional/mapped types that infer complex shapes can become nearly unreadable in error messages and genuinely slow down the compiler on large codebases — a straightforward, slightly-more-verbose type is often the better production choice over a "clever" one, especially since TS 6.0's stricter defaults already surface more errors that need clear messages to act on.

---

## Interview questions

### Q1 — Explain structural vs nominal typing, and why an object literal can satisfy an interface it never declared.
**Testing:** baseline understanding of TS's actual type-compatibility model.
**Answer:** TypeScript checks whether a value's *shape* is compatible with a target type — same or superset of required properties with compatible types — regardless of any declared name or inheritance relationship. An object literal satisfies an interface purely by having the right shape; there's no `implements` requirement anywhere in the assignment path.
**Follow-up trap:** *"Then why does `distance({x:3,y:4,z:5})` error but `distance(someVarWithExtraProps)` doesn't?"* — excess property checks fire specifically on object literals passed directly, to catch likely typos, but don't apply to variables holding an object with genuinely extra properties, which is a deliberately narrower check than full structural strictness would imply.

### Q2 — What does "types are erased" actually mean, and what's the practical consequence?
**Answer:** Every type annotation, interface, and generic parameter is deleted during compilation to JS — the emitted JavaScript has zero runtime trace of the type system. The consequence: TypeScript can never enforce anything at runtime; a value crossing an unchecked boundary (an `as` assertion, an untyped import, a stale third-party `.d.ts`) can be structurally wrong at runtime while the type checker reports everything as fine.
**Follow-up trap:** *"So how do you get runtime type safety at all?"* — a separate runtime validation library (Zod, io-ts, valibot) that checks actual shape at the boundary and can derive the static TS type from the same schema (`z.infer<typeof Schema>`), giving one source of truth instead of maintaining a type and a validator separately that can drift apart.

### Q3 — What's the difference between `unknown` and `any`, mechanically?
**Answer:** Both accept any value being assigned to them. The difference is what you can do with the value afterward: `any` disables type checking entirely for anything the value touches — property access, calls, arithmetic all compile with zero checks. `unknown` requires explicit narrowing (a `typeof` check, an `instanceof` check, a custom type guard) before any operation is permitted.
**Follow-up trap:** *"Where does TypeScript itself default to `unknown` over `any` as of 4.4+?"* — caught errors in a `catch` clause, under `useUnknownInCatchVariables` (on by default in `strict` mode) — because a thrown value's actual type is never knowable ahead of time, `unknown` is the honest type, replacing the historically incorrect default of `any`.

### Q4 — Write a discriminated union for a fetch state (idle/loading/success/error) and explain why it's better than one flat interface with optional fields.
**Answer:** `type FetchState<T> = {status:"idle"} | {status:"loading"} | {status:"success", data:T} | {status:"error", error:string}`. A flat interface with `data?: T`, `error?: string`, `loading?: boolean` allows illegal combinations to compile — `{loading: true, data: staleData}` is perfectly legal, and stale-data-while-loading is a real, common bug class. The discriminated union makes that combination structurally impossible: `data` doesn't exist as a field in the `loading` branch's type at all.
**Follow-up trap:** *"How do you force the compiler to catch a missed case if a new variant is added later?"* — the `never`-typed exhaustiveness check: `const _exhaustive: never = state` in the default/fallback branch of a switch — if a new variant isn't handled, `state` in that branch is no longer assignable to `never`, and it's a compile error, not a runtime surprise.

### Q5 — What's a type assertion (`as`), and why is it dangerous?
**Answer:** `value as Type` tells the compiler "trust me, treat this as `Type`" with zero runtime verification — if `value` isn't actually shaped like `Type`, the assertion compiles fine and the mismatch surfaces later, at whatever point downstream code actually uses the value in a way that breaks, often far from the assertion's location, making it hard to trace back to the actual bad assumption.
**Follow-up trap:** *"When is `as` actually legitimate to use?"* — narrowing a type the compiler can't infer but you can prove is safe from context it doesn't have visibility into (e.g., asserting a `document.querySelector` result's more specific element type when you control the DOM structure), not as a way to silence an error whose underlying concern is real.

### Q6 — Explain generics with a real example, and what "variance" means in that context.
**Answer:** Generics parameterize a function/type over a type variable while preserving the specific type through the call — `function identity<T>(x: T): T` returns exactly the type passed in, not a widened `any`. Variance is about whether a generic type parameterized over a subtype can substitute for one parameterized over its supertype — e.g., is `Box<Dog>` assignable where `Box<Animal>` is expected?
**Follow-up trap:** *"Is this always safe in TypeScript?"* — no — TypeScript's structural, largely-covariant defaults for property positions are technically unsound for genuinely mutable containers (you could assign a `Cat` into a reference typed `Box<Animal>` that's actually holding a `Box<Dog>` at runtime), a deliberate ergonomics-over-strict-soundness tradeoff, and function parameters specifically are bivariant by default unless `strictFunctionTypes` is enabled.

### Q7 — What's function parameter bivariance, and what turns it off?
**Answer:** Without `strictFunctionTypes`, TypeScript allows a function type `(x: Dog) => void` to be assignable to `(x: Animal) => void` and vice versa, even though only contravariance (accepting a *wider* parameter type is safe, narrower isn't) is actually type-safe. `strictFunctionTypes` (part of `strict` mode) tightens standalone function type checks to correct contravariant behavior.
**Follow-up trap:** *"Does `strictFunctionTypes` fix this for methods too?"* — no — method syntax (`interface Foo { method(x: Dog): void }`) remains bivariant even under strict mode, a deliberate, documented carve-out for compatibility with common OOP override patterns, and it's a genuinely obscure detail most candidates miss.

### Q8 — What is declaration merging, and name a real, legitimate use for it.
**Answer:** Multiple `interface` declarations with the same name across different files automatically merge into one combined interface. Legitimate use: augmenting a global or third-party type (e.g., adding a custom property that a library attaches to `window` at runtime, or extending Express's `Request` type with a custom `user` property added by auth middleware) without forking the library's own type definitions.
**Follow-up trap:** *"What's the risk?"* — declaration merging lets you *declare* that a runtime shape exists with zero verification that anything actually sets it — if the middleware that's supposed to attach `req.user` doesn't run on a particular route, the type system still claims `req.user` exists, and the resulting `undefined` access crashes at runtime with no compile-time warning.

### Q9 — Implement `Pick<T, K>` yourself without using the built-in utility type.
**Answer:** `type MyPick<T, K extends keyof K> = { [P in K]: T[P] }` (constraining `K extends keyof T` in the real signature) — a mapped type iterating over the keys in `K` and pulling each corresponding property type from `T`.
**Follow-up trap:** *"Now implement `Partial<T>`."* — `type MyPartial<T> = { [P in keyof T]?: T[P] }` — the `?` modifier applied during the mapped-type iteration; the ability to derive these from first principles rather than reciting their behavior is the actual signal being tested.

### Q10 — A `.d.ts` file for a third-party library claims a field is always present, but in production it's sometimes `undefined`. How did this happen, and what does it tell you about trusting third-party types?
**Answer:** The `.d.ts` (bundled with the library or from a separate `@types/*` package) was written by hand or generated against a different version/behavior than what's actually shipping, and TypeScript has no mechanism to verify a `.d.ts` file's accuracy against the actual runtime behavior of the JS it describes — it's trusted completely, the same as your own hand-written types. It tells you third-party types are documentation with the syntax of a guarantee, not an actual guarantee.
**Follow-up trap:** *"What's the fix without waiting for an upstream patch?"* — locally patch the type via `declare module` augmentation to reflect the actual observed behavior (e.g., mark the field optional), and treat any value from that boundary defensively (optional chaining, explicit runtime checks) regardless of what the stale type claims.

### Q11 — What changed in TypeScript 6.0 (March 2026), and why does it matter that it's "the last JS-based release"?
**Answer:** TypeScript 6.0 flipped several defaults toward stricter behavior (broader strict-mode defaults, ESM as the default module system, an `es2025` target) and removed a batch of legacy compiler options, positioned explicitly as a deliberate bridge release before the next architectural shift — TypeScript 7.0, a from-scratch rewrite of the compiler in Go rather than continuing on the original TS/JS-based implementation.
**Follow-up trap:** *"Does the Go rewrite change the language semantics?"* — no — 7.0 (beta April 2026, RC June 18, 2026) is a reimplementation targeting roughly 10x faster compilation/type-checking, not a new language; the type system's rules stay the same, but build times, editor responsiveness, and tooling that shells out to `tsc` are the things materially affected.

---

## Red flags that fail you

- Describing TypeScript's typing as nominal ("it checks the interface name") instead of structural.
- Claiming `as` assertions perform any runtime check.
- Using `any` reflexively to silence errors without acknowledging the propagation risk or considering `unknown` instead.
- Not knowing that types are fully erased at compile time — implying TypeScript enforces anything at runtime by itself.
- Writing a discriminated union `switch` with no exhaustiveness check and no awareness that adding a new variant later would silently fall through.
- Treating a third-party `.d.ts` file's claims as a guaranteed contract rather than unverified documentation.

---

## Cheat card

```
STRUCTURAL TYPING: shape match = compatible, name/declared inheritance irrelevant
  excess property check: fires on OBJECT LITERALS passed directly only, not variables

ERASURE: all types deleted at compile time -> ZERO runtime enforcement by TS itself
  runtime validation (Zod/io-ts) needed at every trust boundary (API, JSON.parse, env)

GENERICS: function identity<T>(x:T):T preserves specific type through the call
VARIANCE: TS mostly covariant/structural by default for properties (technically unsound
  for mutable containers) — deliberate ergonomics tradeoff
  FUNCTION PARAM BIVARIANCE: unsafe by default, strictFunctionTypes fixes standalone
  function types but NOT method syntax (still bivariant even under strict)

DISCRIMINATED UNIONS: shared literal tag field -> illegal states unrepresentable
  exhaustiveness: const _exhaustive: never = x  in default branch -> compile error
  if a new variant is unhandled

unknown vs any: BOTH accept anything IN. any = no checks on use, EVER (propagates
  silently). unknown = must narrow (typeof/instanceof/guard) before any operation.
  TS 4.4+: caught errors default to `unknown` under useUnknownInCatchVariables

DECLARATION MERGING: same-name interfaces across files auto-combine — real use:
  augmenting global/3rd-party types (Window, Express Request) — but declares a
  shape with ZERO runtime verification anything actually sets it

WHERE TS LIES: `as` = 0 runtime check. `!` = same lie about nullability.
  3rd-party .d.ts = trusted completely, no drift detection vs actual runtime behavior.
  one `any` in a chain = silently untyped downstream, easy to lose track of

Pick<T,K> = {[P in K]: T[P]}   Partial<T> = {[P in keyof T]?: T[P]}
  (know how to derive these, not just recite behavior)

TS 6.0 (Mar 2026): last JS-based compiler release, stricter defaults, ESM default
TS 7.0: Go rewrite, ~10x faster, RC June 2026 — same language semantics, faster tooling
```

## Sources

- [TypeScript Handbook: Everyday Types, Narrowing, Generics — TypeScript](https://www.typescriptlang.org/docs/handbook/2/everyday-types.html) — accessed 2026-08-02
- [Announcing TypeScript 6.0 — Microsoft DevBlogs](https://devblogs.microsoft.com/typescript/announcing-typescript-6-0/) — accessed 2026-08-02
- [TypeScript 7.0 Beta / Go-native rewrite — Visual Studio Magazine](https://visualstudiomagazine.com/articles/2026/04/21/typescript-7-0-beta-arrives-on-go-based-foundation-with-10x-speed-claim.aspx) — accessed 2026-08-02
- [TypeScript 6.0 as final JS-based release — Visual Studio Magazine](https://visualstudiomagazine.com/articles/2026/03/23/typescript-6-0-ships-as-final-javascript-based-release-clears-path-for-go-native-7-0.aspx) — accessed 2026-08-02
- [Zod — TypeScript-first schema validation](https://zod.dev) — accessed 2026-08-02

## Changelog
- 2026-08-02 — created
