# JavaScript Deep: Event Loop, Microtasks, Closures, Prototypes, `this`, Modules

> **Track:** T33 Frontend & UI Engineering · **Time:** 3.0h · **Prereqs:** T33-browser-rendering
> **Module id:** `T33-js-deep` · **Tags:** language, critical

## The 30-second version

JavaScript is single-threaded with a concurrency model built on an event loop that drains two separate queues in a strict order: after each single macrotask (a `setTimeout` callback, an I/O callback, a UI event handler, or the initial script), the engine drains the **entire** microtask queue — every Promise `.then`/`.catch`/`.finally` callback and every `queueMicrotask` callback, including any new ones microtasks themselves enqueue — before it's allowed to render a frame or run the next macrotask. This is why `Promise.resolve().then(fn)` always runs before `setTimeout(fn, 0)` even scheduled first, and why a microtask that keeps re-enqueueing itself can starve rendering entirely. Closures work because a function retains a live reference to its enclosing scope's variable bindings, not a snapshot — which is why `for (var i...)` inside a `setTimeout` loop famously logs the final value while `for (let i...)` doesn't, because `let` creates a fresh binding per iteration. `this` is not determined by where a function is defined, it's determined by how it's called: implicit binding (`obj.method()`), explicit binding (`call`/`apply`/`bind`), `new` binding, or the global/undefined default — arrow functions are the sole exception, since they capture `this` lexically from their enclosing scope at creation time and cannot be rebound. Prototype-based inheritance means every object has an internal `[[Prototype]]` link forming a chain that property lookup walks until it finds a match or hits `null`; `class` syntax is sugar over exactly this mechanism, not a different inheritance model. ES modules are statically analyzable and live-bound (importing a value gives you a read-only view that updates when the source changes) while CommonJS is dynamic, synchronous, and copies values at require-time — the two systems don't interoperate cleanly, which is a real, current source of tooling pain, not a solved problem.

## Why this gets asked

Because JavaScript's concurrency model and scoping rules produce bugs that look like nondeterminism to someone who's memorized the syntax but not the mechanism, and debugging them requires reasoning from the actual queue semantics rather than pattern-matching. The interviewer has shipped a race condition caused by assuming a `.then()` runs "eventually, in some order" rather than "deterministically, before the next macrotask, no matter what" — or debugged a closure bug in a loop, or spent an afternoon on a `this` bug in an event handler passed as a callback without `.bind()`. In 2026 specifically, AI tools answer the textbook version of these questions instantly, so interviewers have pushed past "what is a closure" into "trace the exact console.log order of this 15-line snippet with nested promises and setTimeout" — the goal is seeing whether you can simulate the engine's actual queue behavior step by step, not recite a definition.

---

## Lineage: past → present → future

**What came before.** JavaScript shipped in 10 days in 1995 with `var`'s function-scoping (not block-scoping) and prototype-based inheritance modeled loosely on Self, at a time when the language ran tiny scripts for form validation, not applications with thousands of concurrently in-flight async operations. Callbacks were the only async primitive for over a decade, and by the mid-2010s, "callback hell" — deeply nested, error-handling-inconsistent callback pyramids in real Node.js and browser code — was a widely acknowledged, specifically named pain point, not a hypothetical: error handling had no consistent convention (some libraries used `(err, result)` first-argument, some didn't), and composing multiple async operations (do A, then B using A's result, handle either failing) required manually threading callbacks with no structural help from the language.

**Where it stands now.** Promises (standardized in ES2015/ES6, 2015) gave async operations a first-class value with defined, chainable semantics, and `async`/`await` (ES2017) is now the dominant surface syntax for consuming them — it compiles down to the same Promise/microtask machinery, it's just sugar that makes asynchronous code read like synchronous code. The microtask/macrotask distinction is fully specified (HTML Living Standard for the event loop and task queues, ECMAScript spec for Promise jobs specifically) and consistent across all major engines (V8, SpiderMonkey, JavaScriptCore). ES modules are the consensus format going forward — supported natively in every current browser and in Node.js — but CommonJS is nowhere near dead: the existing npm ecosystem has decades of CJS-only packages, and the two module systems' interop (`require()`-ing an ESM package, or `import`-ing a CJS one) remains a genuinely unresolved source of real build-tool pain in 2026, not a solved historical footnote — dual-package hazard (a package instantiated twice, once via each system, breaking `instanceof` checks and shared module state) is a real, current bug class.

**Where it's heading.** TC39 continues to add ergonomic surface features on top of the same core model rather than changing the concurrency semantics — top-level `await` (stage 4, widely supported) and the `Explicit Resource Management` proposal (`using`/`await using`, stage 4 as of 2024-2025, shipping in engines through 2025-2026) are recent examples of syntax that composes with the existing event loop rather than replacing it. There's no serious proposal to change the single-threaded, queue-based execution model itself — Web Workers/`SharedArrayBuffer` remain the actual mechanism for true parallelism, deliberately kept separate from the main JS execution model rather than merged into it, because message-passing isolation is what makes the single-threaded model's guarantees (no data races on ordinary objects) hold. The realistic direction is continued convergence toward ESM as the default module format at the tooling and runtime level, with CJS interop remaining a maintained-but-friction-heavy legacy path for the foreseeable future — that's a judgment call based on ecosystem inertia, not a certainty.

---

## Mental model

```
CALL STACK          MICROTASK QUEUE         MACROTASK QUEUE
(sync code runs        (Promise.then,         (setTimeout, setInterval,
 here, LIFO)             queueMicrotask,        I/O callbacks, UI events,
                          MutationObserver)      the initial <script> run)

Event loop algorithm, simplified:
1. Run one macrotask to completion (pop from macrotask queue; empty
   stack afterward).
2. Drain the ENTIRE microtask queue — run every microtask, and if a
   microtask enqueues another microtask, run that one too, before
   moving on. Loop 2 does not stop until the queue is completely empty.
3. (Roughly once per frame, not every loop iteration) if it's time to
   paint, render.
4. Go back to step 1.

KEY RULE: microtasks ALWAYS fully drain between macrotasks — and
between a macrotask and the next paint. A microtask that keeps
scheduling more microtasks can starve rendering indefinitely.
```

Example trace, the kind an interviewer hand-writes on a whiteboard:

```js
console.log('1');                         // sync
setTimeout(() => console.log('2'), 0);    // macrotask
Promise.resolve().then(() => console.log('3'));  // microtask
console.log('4');                         // sync
// Output: 1, 4, 3, 2
// Sync code (call stack) always finishes first: 1, 4.
// Then the ENTIRE microtask queue drains before the next macrotask: 3.
// Only then does the setTimeout macrotask run: 2.
```

---

## How it actually works

### Microtasks vs macrotasks, precisely

**Macrotasks** (also called "tasks" in the HTML spec): `setTimeout`/`setInterval` callbacks, I/O completion callbacks (Node's `fs` callbacks), UI event dispatch (a click handler is a macrotask), and the initial execution of a `<script>`. Only **one** macrotask runs per iteration of the event loop's outer cycle.

**Microtasks**: Promise reaction callbacks (`.then`, `.catch`, `.finally`), `queueMicrotask()`, and (in Node.js specifically) `process.nextTick()` — which is not technically the same queue as Promise microtasks and runs with **even higher priority**, draining its own queue completely before the Promise microtask queue gets a turn, a Node-specific wrinkle worth naming if asked about Node rather than browser behavior.

The critical asymmetry: after any single macrotask finishes, the engine drains **every** microtask currently queued, and any microtask that queues *more* microtasks during that drain also gets run before control returns — the microtask queue must reach empty, not just "get one pass." This is why a recursive `.then()` chain that never stops can starve the event loop from ever reaching the next macrotask or repainting, a real, reproducible way to freeze a page that looks alive (JS is still "running") but is unresponsive to clicks and never paints.

### `async`/`await` is exactly this machinery, not new semantics

```js
async function f() {
  console.log('a');
  await null;              // suspends here, schedules continuation as a microtask
  console.log('b');
}
console.log('start');
f();
console.log('end');
// Output: start, a, end, b
// f() runs synchronously up to the first `await`. The `await null` line
// is equivalent to `Promise.resolve(null).then(() => { console.log('b') })`
// — everything after `await` is a microtask continuation, no different
// from a `.then()` callback in queue priority.
```

Anyone who can't produce `start, a, end, b` from this hasn't internalized that `await` is sugar for a `.then()`-based continuation, not a different scheduling mechanism.

### Closures — a live binding, not a snapshot

```js
function makeCounter() {
  let count = 0;                 // this binding is captured, not copied
  return { inc: () => ++count, get: () => count };
}
const c = makeCounter();
c.inc(); c.inc();
console.log(c.get());            // 2 — both closures share the SAME `count` binding
```

The classic loop bug demonstrates the same mechanism working against you:

```js
for (var i = 0; i < 3; i++) {
  setTimeout(() => console.log(i), 0);
}
// Output: 3, 3, 3 — `var` is function-scoped, so there's exactly ONE `i`
// binding shared by all three closures; by the time the callbacks run
// (after the loop finishes, all three are macrotasks queued for later),
// i is 3.

for (let j = 0; j < 3; j++) {
  setTimeout(() => console.log(j), 0);
}
// Output: 0, 1, 2 — `let` creates a NEW binding per iteration (this is
// specified behavior, not a coincidence), so each closure captures its
// own distinct `j`.
```

### Prototype chain

Every ordinary object has an internal `[[Prototype]]` slot (exposed via `Object.getPrototypeOf()`/`__proto__`, though the latter is legacy and shouldn't be used directly in new code). Property lookup walks this chain: check the object's own properties, then its prototype's, then that prototype's prototype, and so on until `null` (the end of every chain). `class` is syntax sugar over exactly this: `class Dog extends Animal {}` sets `Dog.prototype.__proto__ === Animal.prototype`, and `new Dog()` creates an object whose `[[Prototype]]` is `Dog.prototype` — `instanceof` literally walks this chain checking for a match, it isn't a separate type-tag mechanism.

```js
function Animal(name) { this.name = name; }
Animal.prototype.speak = function () { return `${this.name} makes a sound`; };
function Dog(name) { Animal.call(this, name); }
Dog.prototype = Object.create(Animal.prototype);   // this IS what `extends` automates
Dog.prototype.constructor = Dog;

const d = new Dog('Rex');
console.log(d.speak());          // "Rex makes a sound" — found via prototype chain walk
console.log(d instanceof Animal); // true — Dog.prototype's chain includes Animal.prototype
```

### `this` binding rules, in precedence order

1. **`new` binding** — `new Foo()` creates a fresh object, binds `this` to it, and returns it (unless `Foo` explicitly returns another object).
2. **Explicit binding** — `fn.call(obj, ...)`, `fn.apply(obj, [...])`, `fn.bind(obj)` — `this` is whatever object you pass.
3. **Implicit binding** — `obj.method()` — `this` is `obj`, determined by the call site (what's immediately left of the dot), **not** where the function was defined.
4. **Default binding** — a bare function call (`fn()`, no receiver) — `this` is `undefined` in strict mode (the default in ES modules and inside classes), or the global object in sloppy non-module scripts.

**Arrow functions ignore all four rules** — they have no own `this` binding at all; they capture `this` lexically from the enclosing scope at the point they're *defined*, and no amount of `call`/`apply`/`bind`/method-call syntax can change it. This is exactly why arrow functions are the standard fix for the classic "`this` is undefined inside a callback" bug: a regular function passed as an event handler or `setTimeout` callback gets `this` from *how it's invoked* (usually default binding, i.e. `undefined`/global, losing the object context), while an arrow function defined inside a method keeps the method's `this`.

```js
const obj = {
  name: 'obj',
  regular: function () { setTimeout(function () { console.log(this?.name); }, 0); },  // undefined — default binding, callback invoked bare
  arrow:   function () { setTimeout(() => { console.log(this?.name); }, 0); },        // 'obj' — arrow captures enclosing `this` lexically
};
obj.regular();  // undefined
obj.arrow();    // obj
```

### ES modules vs CommonJS — the mechanical differences, not just syntax

| | ES Modules (`import`/`export`) | CommonJS (`require`/`module.exports`) |
|---|---|---|
| Resolution | Static — imports/exports are analyzable before execution, at parse time | Dynamic — `require()` is just a function call, can be conditional/computed |
| Binding | Live, read-only bindings — importing a value gives a view that updates if the exporting module reassigns it | Value copy at `require()` time — later reassignment in the source module isn't seen by an already-`require()`'d consumer |
| Loading | Asynchronous by spec (though bundlers/browsers optimize this); supports top-level `await` | Synchronous — `require()` blocks until the module is loaded |
| `this` at module top level | `undefined` | `module.exports` object |
| Circular imports | Handled via the live-binding mechanism — a circular import can see a later update once the cycle completes | Handled by returning whatever `module.exports` looked like at the point of the circular `require()` call — often an incomplete object |

The live-binding distinction is concrete, not academic:

```js
// counter.mjs
export let count = 0;
export function inc() { count++; }

// main.mjs
import { count, inc } from './counter.mjs';
console.log(count);  // 0
inc();
console.log(count);  // 1 — the SAME imported binding reflects the source module's update
```

There's no CommonJS equivalent that does this without explicitly exporting a getter function or object — `module.exports = { count }` in CJS copies the primitive's value at that instant.

### Generators and iterators

An **iterator** is any object with a `next()` method returning `{ value, done }`. An **iterable** is any object with a `Symbol.iterator` method that returns an iterator — this is the protocol `for...of`, spread syntax, and destructuring rely on. A **generator function** (`function*`) is a convenient way to write an object that's both: calling it returns a generator object that is itself an iterator (and iterable), and `yield` pauses execution, returning a value, resuming exactly where it left off (including its local variable state — this is a real, distinguishing feature: a generator's local scope survives across `next()` calls) on the next `.next()` call.

```js
function* range(start, end) {
  for (let i = start; i < end; i++) {
    yield i;
  }
}
for (const n of range(0, 3)) console.log(n);  // 0, 1, 2 — for...of drives .next() automatically

function* idGenerator() {
  let id = 0;
  while (true) { yield id++; }   // infinite generator — lazy, only computes on demand
}
const gen = idGenerator();
console.log(gen.next().value);   // 0
console.log(gen.next().value);   // 1 — local `id` persisted across calls, this IS the closure-like behavior of generators
```

`async function*` (async generators) combine this with Promises, and `for await...of` consumes them — this is the actual mechanism behind streaming APIs (e.g., iterating chunks of a `ReadableStream`, or paginated API results) without manually managing a loop and buffering.

---

## Build it from scratch

A minimal event loop simulator, proving the microtask-drains-before-next-macrotask rule mechanically rather than by memorized example:

```js
// untested sketch — simplified single-threaded event loop simulator
class EventLoop {
  constructor() {
    this.macrotasks = [];
    this.microtasks = [];
  }
  scheduleMacrotask(fn) { this.macrotasks.push(fn); }
  scheduleMicrotask(fn) { this.microtasks.push(fn); }

  drainMicrotasks() {
    // must fully drain, including microtasks queued BY microtasks
    while (this.microtasks.length > 0) {
      const task = this.microtasks.shift();
      task();
    }
  }

  run() {
    this.drainMicrotasks();               // any microtasks queued by sync top-level code
    while (this.macrotasks.length > 0) {
      const task = this.macrotasks.shift();
      task();                              // run exactly one macrotask
      this.drainMicrotasks();              // fully drain microtasks before the next macrotask
    }
  }
}

const loop = new EventLoop();
const log = [];
log.push('1: sync');
loop.scheduleMacrotask(() => log.push('2: macrotask'));
loop.scheduleMicrotask(() => {
  log.push('3: microtask');
  loop.scheduleMicrotask(() => log.push('3b: nested microtask'));  // queued during a drain — still runs before the macrotask
});
log.push('4: sync');
loop.run();
console.log(log);
// ['1: sync', '4: sync', '3: microtask', '3b: nested microtask', '2: macrotask']
```

This mirrors the real spec closely enough to reason correctly about any trace question: the outer `while` only pops one macrotask per iteration, and `drainMicrotasks` doesn't stop until the queue is truly empty, even accounting for microtasks scheduled during the drain itself.

---

## How it's done in production

| Symptom | Cause | Fix |
|---|---|---|
| Page appears frozen — JS is clearly still executing (CPU busy) but clicks don't register and nothing repaints | A microtask chain that keeps re-enqueueing itself (e.g., a buggy recursive `.then()` with no terminating condition) never lets the loop reach the next macrotask/paint, since microtasks must fully drain first | Break the recursive chain with an actual `setTimeout(fn, 0)` or `requestAnimationFrame` boundary to yield back to the macrotask queue between iterations |
| A `console.log` inside a `setTimeout` in a loop always logs the same, final value | `var` is function-scoped — one shared binding across all loop iterations, and by the time any timeout callback runs, the loop has already finished and the variable holds its final value | Use `let` (per-iteration binding) or an IIFE that captures the value explicitly per iteration |
| `this` is `undefined` inside a callback passed to `.addEventListener`, `setTimeout`, or an array method | The function was defined as a regular (non-arrow) method and then passed by reference — the call site invoking it (`addEventListener`, `setTimeout`) has no knowledge of the original object, so default binding applies | Use an arrow function to capture `this` lexically, or explicitly `.bind(this)` the callback before passing it |
| A package works when `require()`'d but breaks (or silently uses stale state) when both `require()`'d and `import`'d in the same dependency tree | Dual-package hazard — the package gets instantiated twice, once under each module system, so `instanceof` checks and any shared module-level state diverge between the two copies | Check the package's `exports` field / dual-package guidance; prefer packages that ship proper conditional exports for both `require` and `import`, or pin the whole dependency tree to one module system where feasible |
| A `for...of` loop over what looks like an array-like object throws `is not iterable` | The object has array-like properties (`length`, indexed keys) but no `Symbol.iterator` method — iterability is a protocol, not inferred from shape | Convert with `Array.from(obj)` (which explicitly handles array-likes) or implement `[Symbol.iterator]` on the object if it's custom |
| Two Promise chains that "should" interleave predictably don't match intuition in a code review | Someone assumed Promise resolution order tracks *call* order rather than the actual microtask queue order, which depends on exactly where in the chain each `.then()` sits relative to already-resolved vs pending values | Trace the actual microtask enqueue order step by step (as in the mental-model example above) rather than reasoning informally — this is the exact skill the "trace this snippet" interview question is testing |

---

## Tradeoffs & when NOT to use it

- **Don't reach for `async`/`await` and pretend it makes concurrent work happen in parallel.** `await`ing three independent promises sequentially (`await a(); await b(); await c();`) runs them one after another, each blocking the next from *starting* until the previous resolves — if they're actually independent, `Promise.all([a(), b(), c()])` (or starting all three calls first, then awaiting) is the correct pattern, and confusing sequential-await with parallelism is a common, real performance bug in production code review.
- **Don't overuse generators for simple iteration** — a generator's lazy, pausable execution model is genuinely valuable for infinite sequences, streaming, or coroutine-style control flow, but for a fixed, already-in-memory array, a plain `.map()`/`for...of` is clearer and has no reason to reach for `function*`.
- **Don't use `process.nextTick()` (Node) without understanding it can starve I/O** — because it has even higher priority than Promise microtasks and the standard event loop phases, a recursive `process.nextTick()` chain can prevent I/O callbacks from ever running, a distinctly Node-specific footgun that doesn't exist in the browser's model.
- **Don't assume ESM/CJS interop is a solved problem you can ignore** — dual-package hazards and subtle behavior differences (synchronous vs asynchronous resolution, live bindings vs copies) are real, current sources of production bugs in mixed dependency trees, not a historical concern safely left behind.

---

## Interview questions

### Q1 — Trace the exact console.log output order: `console.log(1); setTimeout(() => console.log(2), 0); Promise.resolve().then(() => console.log(3)); console.log(4);`
**Testing:** baseline micro/macrotask ordering.
**Answer:** `1, 4, 3, 2`. Synchronous code runs to completion first (1, 4). Then the microtask queue drains fully before any macrotask runs (3). Only then does the setTimeout macrotask run (2).
**Follow-up trap:** *"What if there were two `.then()` calls instead of one?"* — both microtasks run before the setTimeout, since the entire microtask queue drains between macrotasks, not just one microtask per cycle.

### Q2 — What's the difference between a microtask and a macrotask, and name two examples of each.
**Answer:** Macrotasks: `setTimeout`/`setInterval` callbacks, UI events, I/O callbacks — only one runs per event loop iteration. Microtasks: Promise `.then`/`.catch`/`.finally`, `queueMicrotask()` — the entire queue drains completely (including newly-added ones) before the next macrotask or paint.
**Follow-up trap:** *"Where does `process.nextTick()` fit in Node?"* — higher priority than Promise microtasks; Node drains the `nextTick` queue completely before the Promise microtask queue gets a turn, a Node-specific detail distinct from browser semantics.

### Q3 — Why does this loop log 3, 3, 3 with `var` but 0, 1, 2 with `let`?
**Answer:** `var` is function-scoped, so all three `setTimeout` closures share a single `i` binding; by the time any callback runs (after the synchronous loop finishes), `i` is 3. `let` creates a fresh binding per iteration by specification, so each closure captures its own distinct value.
**Follow-up trap:** *"How would you fix the `var` version without switching to `let`?"* — wrap the loop body in an IIFE that takes `i` as a parameter, creating a new scope per iteration manually: `(function(i) { setTimeout(() => console.log(i), 0); })(i)`.

### Q4 — Explain the four `this`-binding rules and their precedence.
**Answer:** In precedence order: `new` binding (constructor call, `this` is the new object) beats explicit binding (`call`/`apply`/`bind`) beats implicit binding (`obj.method()`, `this` is `obj`) beats default binding (bare call, `this` is `undefined` in strict mode or the global object otherwise). Arrow functions ignore all four — they lexically capture `this` from their defining scope and can't be rebound.
**Follow-up trap:** *"Can `bind` override an arrow function's `this`?"* — no, calling `.bind()` on an arrow function has no effect on `this` (though it still affects arguments if used for partial application) — arrow functions have no own `this` slot to rebind at all.

### Q5 — What is the prototype chain, and how does `class` relate to it?
**Answer:** Every object has an internal `[[Prototype]]` link; property lookup walks the chain (own properties, then prototype's, then that prototype's prototype, etc.) until it finds a match or reaches `null`. `class`/`extends` is syntax sugar that sets up exactly this chain automatically (`Dog.prototype.__proto__ = Animal.prototype`) rather than introducing a separate inheritance mechanism.
**Follow-up trap:** *"What does `instanceof` actually check?"* — it walks the object's prototype chain looking for the constructor's `.prototype` object anywhere in that chain — it's not a stored type tag, which is why reassigning `Dog.prototype` after objects are already constructed can break `instanceof` for those existing instances.

### Q6 — What's the actual difference between ES modules and CommonJS beyond syntax?
**Answer:** ESM resolution is static (analyzable before execution) with live, read-only bindings — an imported value reflects later updates in the source module. CommonJS resolution is dynamic (`require()` is a real function call, can be conditional) with value-copy semantics at require-time — later reassignment in the source isn't visible to an already-required consumer. ESM is asynchronous by spec and supports top-level `await`; CommonJS is synchronous.
**Follow-up trap:** *"What's a dual-package hazard?"* — when a package gets instantiated twice in the same dependency tree, once loaded via `require()` and once via `import`, producing two separate module instances whose `instanceof` checks and shared state diverge — a real, current interop bug class, not a solved problem.

### Q7 — What's a closure, mechanically — not "a function that remembers its scope," but why does that work?
**Answer:** A closure is a function paired with a live reference to its enclosing lexical scope's variable environment, not a snapshot/copy — the engine keeps that scope's bindings alive (rather than garbage-collecting them when the enclosing function returns) as long as any closure still references them. Multiple closures created in the same scope share the same live bindings, which is why two functions returned from the same factory can both read and mutate the same private variable.
**Follow-up trap:** *"Does this mean closures can cause memory leaks?"* — yes, legitimately — a closure keeping a reference to a large object (even one small unused variable in a big scope) prevents that scope's memory from being garbage collected as long as the closure is reachable; this is a real, occasionally surprising source of memory growth in long-lived apps (e.g., event listeners never removed, each holding a closure over a large captured scope).

### Q8 — Write (or trace) code demonstrating that a generator's local state persists across multiple `.next()` calls.
**Answer:** `function* idGen() { let id = 0; while (true) { yield id++; } }` — each call to `.next()` resumes exactly where the last `yield` paused, with `id`'s value intact; the first three calls return 0, 1, 2. This is possible because the generator's execution context (including its local variables) is suspended, not discarded, between calls.
**Follow-up trap:** *"How is this different from just returning a closure with a counter?"* — a generator additionally implements the iterator protocol natively (usable directly in `for...of`, spread, destructuring) and can pause mid-expression, mid-loop, anywhere a `yield` appears — a closure-based counter only exposes whatever methods you explicitly write, and can't natively participate in iteration syntax without manually implementing `Symbol.iterator` yourself.

### Q9 — What does `await` actually desugar to in terms of the microtask queue?
**Answer:** `await expr` is equivalent to attaching a `.then()` continuation to `Promise.resolve(expr)` — everything after the `await` runs as a microtask once that promise settles. `async function` code runs synchronously up to the first `await`, at which point it returns control to the caller and schedules its continuation exactly like any other Promise reaction.
**Follow-up trap:** *"So is `await Promise.resolve(x)` literally the same priority as a hand-written `.then()`?"* — functionally yes for ordering purposes, but there can be a difference in the exact number of microtask "ticks" it takes to resolve depending on engine implementation details (historically V8 required an extra microtask tick per `await` before a 2018 spec change reduced it to match native `.then()` — worth knowing this existed as a real, fixed engine-level discrepancy, not something to assert as still true without checking current engine behavior).

### Q10 — Two independent async operations need to run concurrently. What's wrong with `await a(); await b();` and what's the fix?
**Answer:** Sequential `await` forces `b()` to not even *start* until `a()` fully resolves, even though they're independent — this serializes what should be concurrent work, directly costing latency (total time ≈ a's time + b's time instead of max(a's time, b's time)). Fix: start both calls first (`const pa = a(); const pb = b();`), then `await Promise.all([pa, pb])`, or `await` them separately after both have already started.
**Follow-up trap:** *"What does `Promise.all` do if one of them rejects?"* — it rejects immediately with the first rejection reason, without waiting for the others to settle (though they continue running in the background) — if you need to know the outcome of *all* of them regardless of individual failures, `Promise.allSettled` is the correct primitive instead.

### Q11 — Why does `console.log(this)` inside a regular (non-arrow) method passed directly as an event listener log `undefined` (in strict mode) instead of the object it was defined on?
**Answer:** `this` is determined by the call site, not the definition site — `element.addEventListener('click', obj.method)` passes a bare function reference; when the browser invokes it, it does so as `method()` with no receiver tied to `obj` (or actually binds `this` to the DOM element in the case of addEventListener specifically, which is its own related gotcha), losing the original `obj` context entirely. This is exactly the implicit-binding-lost-on-reference-passing bug.
**Follow-up trap:** *"What does addEventListener actually set `this` to, then?"* — the DOM element the listener is attached to (unless the handler is an arrow function, in which case it's whatever the enclosing lexical scope's `this` was) — a real, frequently-tested detail beyond the generic "it's undefined" answer.

### Q12 — A recursive `.then()` chain with no terminating condition freezes a page that's still visibly using CPU. Explain the mechanism.
**Answer:** Since the microtask queue must fully drain — including any new microtasks enqueued during the drain — before the event loop can proceed to the next macrotask or a repaint, a chain that keeps scheduling a new microtask from within its own `.then()` callback never lets the drain finish, starving both rendering and any pending macrotasks (click handlers, timers) indefinitely.
**Follow-up trap:** *"How would you deliberately break the chain to keep it responsive?"* — insert an actual macrotask boundary periodically, e.g. `setTimeout(next, 0)` instead of `Promise.resolve().then(next)` for the recursive step, which hands control back to the macrotask queue (and therefore to rendering) between iterations.

---

## Red flags that fail you

- Saying Promises "run in the background" as if they're on another thread — JS is single-threaded; Promises schedule callbacks on the microtask queue, they don't create concurrency.
- Not being able to trace a simple micro/macrotask ordering snippet without guessing.
- Explaining `this` as "the object the function is defined in" instead of "determined by the call site."
- Claiming `class` in JS is a fundamentally different inheritance model from prototypes rather than sugar over the same mechanism.
- Treating `require()` and `import` as interchangeable with no acknowledgment of live bindings vs value copies, or dual-package hazards.
- Writing `await a(); await b();` for two independent calls without recognizing it serializes them unnecessarily.

---

## Cheat card

```
EVENT LOOP: 1 macrotask -> drain ENTIRE microtask queue (incl. newly queued) -> maybe paint -> repeat
  macrotasks: setTimeout/setInterval, I/O callbacks, UI events, initial script
  microtasks: Promise .then/.catch/.finally, queueMicrotask()
  Node: process.nextTick() drains BEFORE Promise microtasks — higher priority, Node-only

await expr === Promise.resolve(expr).then(continuation) — sync up to first await

var = function-scoped, 1 shared binding across loop iterations -> classic setTimeout bug logs final value
let = new binding PER iteration -> setTimeout logs 0,1,2 correctly

THIS BINDING PRECEDENCE: new > explicit(call/apply/bind) > implicit(obj.method()) > default(undefined/global)
  arrow fns: NO own `this` — lexically captured from enclosing scope at definition, unbindable

PROTOTYPE CHAIN: obj lookup walks [[Prototype]] links to null. class/extends = sugar over this.
  instanceof walks the chain checking for constructor.prototype — not a type tag

ESM: static analysis, LIVE read-only bindings, async by spec, top-level await
CJS: dynamic require(), VALUE COPY at require-time, synchronous
  dual-package hazard: pkg loaded via both systems -> 2 instances, instanceof/state diverge

GENERATORS: function* returns iterator+iterable; yield pauses, LOCAL STATE PERSISTS across .next()
  for...of drives .next() automatically; async function* + for await...of for streaming

Promise.all: rejects on FIRST rejection, others keep running in background
Promise.allSettled: waits for ALL regardless of individual failure
sequential await on independent calls = accidental serialization, use Promise.all
```

## Sources

- [ECMA-262: Jobs and Job Queues (Promise microtasks)](https://tc39.es/ecma262/#sec-jobs-and-job-queues) — accessed 2026-08-02
- [HTML Living Standard: Event loops](https://html.spec.whatwg.org/multipage/webappapis.html#event-loops) — accessed 2026-08-02
- [Node.js: The Node.js Event Loop, Timers, and process.nextTick()](https://nodejs.org/en/learn/asynchronous-work/event-loop-timers-and-nexttick) — accessed 2026-08-02
- [MDN: Closures](https://developer.mozilla.org/en-US/docs/Web/JavaScript/Guide/Closures) — accessed 2026-08-02
- [Node.js: Dual package hazard](https://nodejs.org/api/packages.html#dual-package-hazard) — accessed 2026-08-02

## Changelog
- 2026-08-02 — created
