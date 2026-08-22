# React Core: Reconciliation, Keys, Hooks Rules, Effects, and Why Your Component Re-Renders

> **Track:** T33 Frontend & UI Engineering · **Time:** 3.0h · **Prereqs:** T33-js-deep
> **Module id:** `T33-react-core` · **Tags:** react, critical

## The 30-second version

React re-renders by calling your component function again and diffing the new returned element tree against the previous one (reconciliation), not by mutating the DOM directly on every state change — the diff decides the minimal set of real DOM operations needed, and React 19.2 is the current stable release as of mid-2026. Reconciliation matches elements at the same tree position by type first (a `<div>` diffed against a previous `<div>` reuses the DOM node and patches attributes; a `<div>` diffed against a previous `<span>` unmounts and remounts entirely) and, for lists, by `key` — using array index as key breaks this matching the moment items are inserted, removed, or reordered, because React matches by position, not identity, so state and DOM nodes get silently reattached to the wrong logical item. Hooks rules (only call at the top level, never conditionally, never in loops) exist because hooks have no name or identifier at the call site — React tracks them by **call order** in a linked list attached to the fiber, so a hook call that's conditionally skipped on one render shifts every subsequent hook's position, corrupting all of their state. `useEffect`'s dependency array is not an optimization hint, it's a correctness contract: every reactive value read inside the effect that isn't in the array is a stale closure waiting to happen, captured at the render that scheduled the effect, not read fresh when the effect runs. The systematic method for "why did this re-render" is: a component re-renders when its own state changes, its parent re-renders (and it isn't memoized), or a subscribed context value changes — and the fix is almost never "wrap everything in memo," it's identifying which specific one of those three triggers is firing and whether it's actually necessary. The React Compiler, stable since October 2025, automates most of the manual `useMemo`/`useCallback`/`memo` work by statically analyzing and memoizing components, which changes the debugging conversation from "did you forget to memoize this" to "is the compiler's static analysis actually applying here."

## Why this gets asked

Because "my component re-renders too much" and "my list breaks when I reorder it" are two of the most common real React bugs, and both require understanding reconciliation mechanics rather than pattern-matching against Stack Overflow answers. The interviewer has debugged a form where typing in one field caused every sibling field to lose focus (usually an index-as-key bug on a dynamically added/removed field list) or spent time in the Profiler tracing an unnecessary re-render cascade through a deeply nested tree, and wants to see whether you reason from "what actually triggers a re-render" rather than reflexively wrapping components in `memo` and hoping. In 2026 specifically, interviewers push past hook syntax recall into judgment: can you explain *why* a rule exists (not just recite it), critique a `useEffect` for stale closures, and use the Profiler methodically instead of guessing.

---

## Lineage: past → present → future

**What came before.** Pre-React DOM manipulation (jQuery-style, mid-2000s to early 2010s) meant manually finding elements and mutating them in response to every state change, with no systematic relationship between "data changed" and "which DOM nodes need updating" — as an app's interactivity grew, this became genuinely unmanageable: a piece of state used in five places meant five manual update call sites to keep in sync, and forgetting one was a silent, hard-to-spot bug. React (Facebook, open-sourced 2013) introduced the idea of describing UI as a pure function of state and letting a diffing algorithm figure out the minimal DOM mutations, which was the actual innovation — not JSX (a syntax detail) but the virtual-DOM-diff-and-patch model that decoupled "what should the UI look like" from "how do I mutate the DOM to get there." Class components with lifecycle methods (`componentDidMount`, `componentDidUpdate`, `componentWillUnmount`) were the original API for handling side effects and local state, and the specific pain that killed them was logic reuse: sharing stateful logic between components required either higher-order components or render props, both of which caused real, widely-complained-about "wrapper hell" in component trees, and related lifecycle logic (subscribe in `componentDidMount`, unsubscribe in `componentWillUnmount`) was scattered across different methods instead of colocated.

**Where it stands now.** Hooks (React 16.8, February 2019) replaced class lifecycle methods as the default API, letting related logic colocate in one function (a `useEffect` with its setup and cleanup together) and enabling custom hooks as the actual solution to the logic-reuse problem class components never solved cleanly. React 19 (December 2024) is the current major version, with 19.2 the latest stable release as of mid-2026 — its major additions were Actions (a first-class pattern for handling async transitions with pending/error state, `useActionState`, `useFormStatus`), the `use()` hook for reading promises/context conditionally, and formalized Server Components support in the core. The **React Compiler**, which auto-memoizes components and values via static analysis (eliminating most manual `useMemo`/`useCallback`/`React.memo` calls), reached **stable 1.0 in October 2025** and works back to React 17, a genuinely significant shift — Meta reports measurable production wins from it (up to roughly 12% faster initial loads/navigations on the Meta Quest Store, and notably faster interaction performance in some cases). The live disagreement in the ecosystem isn't whether hooks were the right call (settled), it's how much manual memoization discipline is still worth teaching/practicing now that the compiler exists — a real, current pedagogical question this module takes a position on: understand the manual mechanism first, because the compiler doesn't cover every case and debugging still requires the underlying model.

**Where it's heading.** The trajectory is React increasingly doing automatically what developers used to hand-optimize — the Compiler for memoization is the clearest example, and it's real and shipping, not speculative. Server Components and the broader RSC/Suspense/streaming model (covered in depth in the next module) represent the other major direction: shifting more rendering work off the client by default. What's genuinely less certain is exactly how much of the manual-optimization mental model (dependency arrays, memo boundaries) becomes purely a debugging/edge-case skill versus something written day-to-day — that's a real, ongoing shift in what "knowing React well" means, not a settled endpoint yet.

---

## Mental model

```
RECONCILIATION:  your component function runs again -> new element tree ->
                  diff against previous element tree -> minimal DOM patch

  Same type, same position  -> REUSE the DOM node, patch changed props
    <div className="a">  vs  <div className="b">   -> keep node, update className

  Different type, same position -> UNMOUNT old, MOUNT new (state is LOST)
    <div>...</div>  vs  <span>...</span>            -> full remount

  Lists: React matches by KEY, not position, when keys are present
    key="a" key="b" key="c"   (before)
    key="c" key="a" key="b"   (after reorder)
    -> React correctly recognizes these as the SAME three items, reordered,
       and moves the existing DOM nodes/state rather than recreating them

  Lists WITHOUT stable keys (index-as-key): React assumes position = identity
    index 0: <Item id="a"/>     index 0: <Item id="c"/>   <- React thinks THIS
    index 1: <Item id="b"/>     index 1: <Item id="a"/>      is still index-0's
    index 2: <Item id="c"/>     index 2: <Item id="b"/>      item, just with new
                                                              props — state (e.g.
                                                              an input's typed
                                                              value) gets silently
                                                              reattached to the
                                                              WRONG logical item
```

Hooks call-order tracking, the actual mechanism behind the rules of hooks:

```
Render 1:  useState() -> slot[0]   useEffect() -> slot[1]   useState() -> slot[2]
Render 2:  useState() -> slot[0]   useEffect() -> slot[1]   useState() -> slot[2]
           (SAME ORDER — React reads/writes each hook's state by its POSITION
            in this per-fiber linked list, not by name)

if (condition) { useState(); }   // <- BREAKS THIS: if `condition` differs
                                      between renders, every hook AFTER this
                                      one shifts position and reads/writes
                                      the WRONG stored state
```

---

## How it actually works

### The three triggers for a re-render

A component function re-runs when, and only when, one of exactly three things happens:
1. **Its own state changes** (`useState`/`useReducer` setter called with a value React considers different).
2. **Its parent re-renders**, and the component isn't memoized (`React.memo`) — by default, a parent re-render re-renders every child, regardless of whether that child's own props actually changed, because React doesn't know in advance whether they did without diffing, and the default is to just call the function again.
3. **A context value it's subscribed to (via `useContext`) changes.**

`React.memo` intercepts trigger #2: it shallow-compares the new props against the previous props, and skips re-rendering (and re-diffing that subtree) if they're referentially equal. This is exactly why passing an inline object/array/function as a prop (`<Child config={{a: 1}} />`) defeats `memo` — a new object literal is created every render, so the shallow comparison always sees a different reference even if the *contents* are identical, and `Child` re-renders anyway.

```jsx
// untested sketch — the memo-defeating pattern and its fix
function Parent() {
  const [count, setCount] = useState(0);
  return <Child config={{ enabled: true }} />;  // NEW object every Parent render
}
const Child = React.memo(function Child({ config }) {
  console.log("Child rendered");   // fires every time, memo does nothing
  return <div>{config.enabled ? "on" : "off"}</div>;
});

// fix: stabilize the reference
function ParentFixed() {
  const [count, setCount] = useState(0);
  const config = useMemo(() => ({ enabled: true }), []);  // stable reference across renders
  return <Child config={config} />;
}
```

### Reconciliation and keys, mechanically

React's diffing is a heuristic, not a full tree-diff algorithm (a general tree diff is O(n³), computationally infeasible for UI-sized trees) — React's actual algorithm is O(n) by making two simplifying assumptions: elements of different types produce different trees (so it never tries to diff a `<div>` against what used to be a `<span>` at that position, it just remounts), and `key` is the developer's signal for element identity across renders within a list. Without a stable key, React falls back to matching by index, and that's the entire mechanism behind the classic bug:

```jsx
// untested sketch — the index-as-key bug, concretely
function TodoList({ items }) {  // items: [{id:1, text:"a"}, {id:2, text:"b"}]
  return items.map((item, i) => (
    <li key={i}>                          {/* BUG: index as key */}
      <input defaultValue={item.text} />  {/* uncontrolled input holds its own DOM state */}
    </li>
  ));
}
// user types "aX" into the first input (index 0, currently item id:1).
// items reorders (e.g., item id:2 moves to index 0):
// React sees key=0 STILL EXISTS at index 0 -> reuses the SAME <li>/<input> DOM node
// -> the input's typed value "aX" now visually belongs to item id:2, even though
// the USER typed it while item id:1 was there. The bug is invisible in the data
// (items array is correct) — it's purely a DOM-identity mismatch.

// fix: key by stable identity
items.map((item) => (
  <li key={item.id}>
    <input defaultValue={item.text} />
  </li>
));
// now React correctly tracks each <li>/<input> as belonging to a specific item.id
// regardless of position, moving DOM nodes on reorder instead of reusing by index
```

Index-as-key is not a universal bug — for a list that's genuinely static (never reordered, items never inserted/removed from the middle, only ever appended/replaced wholesale), index and identity are the same thing and there's no actual issue. The rule is specifically about lists with insertion, deletion, or reordering.

### Rules of hooks — the actual mechanism, not just the rule

```jsx
// untested sketch — demonstrates WHY conditional hooks corrupt state
function BuggyComponent({ showExtra }) {
  const [a, setA] = useState("a");
  if (showExtra) {
    const [b, setB] = useState("b");   // RULE VIOLATION
  }
  const [c, setC] = useState("c");
  // Render with showExtra=true:  slot0=a, slot1=b, slot2=c
  // Render with showExtra=false: slot0=a, slot1=c  <- `c`'s state is now
  //   read from the slot that USED to hold `b`'s state — React has no way
  //   to know slot1 "should" have been skipped, it just reads whatever
  //   value is sitting in that position in the fiber's hook linked list.
}
```

React's hook implementation is a linked list of hook objects attached to the component's fiber, read and advanced strictly in call order on every render — there's no name-based lookup at all, which is precisely why the position must be identical across every render of a given component, and why the rule is enforced by the `eslint-plugin-react-hooks` rule (`rules-of-hooks`) rather than being something the runtime can always detect and error on cleanly for every case.

### `useEffect` dependency traps

```jsx
// untested sketch — the classic stale closure bug
function Timer() {
  const [count, setCount] = useState(0);
  useEffect(() => {
    const id = setInterval(() => {
      setCount(count + 1);   // `count` is captured from THIS render's closure —
    }, 1000);                 // every tick uses the SAME stale `count` value
    return () => clearInterval(id);
  }, []);                     // empty deps: effect runs ONCE, closure over count=0 forever
  return <div>{count}</div>;  // stuck incrementing from 0 -> 1 -> 0 -> 1 (never past 1)
}

// fix 1: use the functional updater form, no dependency on the captured value at all
useEffect(() => {
  const id = setInterval(() => setCount(c => c + 1), 1000);
  return () => clearInterval(id);
}, []);

// fix 2: include the real dependency (re-subscribes every tick — usually not what you want here)
useEffect(() => {
  const id = setInterval(() => setCount(count + 1), 1000);
  return () => clearInterval(id);
}, [count]);
```

The dependency array isn't a performance knob, it's the mechanism that tells React when the closure captured inside the effect is stale and needs to be recreated. Omitting a value that's actually used inside the effect (what `exhaustive-deps` lint rule catches) means the effect keeps running with whatever value was captured at the render that last (re-)scheduled it — which is exactly the `setInterval` bug above, and the reason "just disable the lint rule" is a real production bug generator, not a harmless suppression.

### The systematic method for "why did this re-render"

1. **Open React DevTools Profiler**, record an interaction, and look at which components actually re-rendered (highlighted, with a render duration) versus which didn't.
2. For each unexpectedly-re-rendered component, check the Profiler's "why did this render" indicator (available in the Profiler's ranked/flamegraph view) — it names the specific trigger: props changed, state changed, hooks changed, or parent re-rendered.
3. If it's "parent re-rendered" and props are referentially stable, that's a `memo` opportunity. If props aren't stable (a new object/function every render), trace *why* — usually an inline literal or an unmemoized callback — and fix the reference stability at the source rather than reaching for `memo` first.
4. If it's a context value change, check whether the consuming component actually needs the *whole* context value or just a slice of it — a single context object containing many unrelated fields means any field changing re-renders every consumer, regardless of which field they actually read.

This is deliberately not "wrap everything in `memo`/`useMemo`/`useCallback` defensively" — that has a real cost (memory for cached values, comparison overhead every render) and, pre-Compiler, was frequently applied without profiling evidence it was needed, producing code that's harder to read for no measured benefit. Post-Compiler, much of this manual work is handled automatically for eligible components, but the profiling-first diagnostic method is unchanged — the Compiler changes what fix you reach for, not how you find the problem.

---

## Build it from scratch

A minimal reconciler proving the type-then-key matching model, not a full React implementation:

```js
// untested sketch — simplified reconciliation: matches by type, then by key
function diff(oldTree, newTree) {
  if (!oldTree) return { type: "CREATE", node: newTree };
  if (!newTree) return { type: "REMOVE" };
  if (oldTree.type !== newTree.type) return { type: "REPLACE", node: newTree };  // different type -> full remount
  return { type: "UPDATE", props: newTree.props };  // same type at this position -> patch props
}

function diffChildren(oldChildren, newChildren) {
  // match by key first (stable identity across reorders), fall back to index
  const oldByKey = new Map(oldChildren.map((c, i) => [c.key ?? i, c]));
  return newChildren.map((newChild, i) => {
    const matchKey = newChild.key ?? i;          // no key -> falls back to POSITION as identity
    const oldChild = oldByKey.get(matchKey);
    return diff(oldChild, newChild);
  });
}

const oldList = [{ key: "a", type: "li", props: { text: "A" } }, { key: "b", type: "li", props: { text: "B" } }];
const newList = [{ key: "b", type: "li", props: { text: "B" } }, { key: "a", type: "li", props: { text: "A" } }];
console.log(diffChildren(oldList, newList));
// both come back as UPDATE (matched by key despite reordering) — this IS why
// stable keys let React move/reuse DOM nodes instead of recreating them
```

---

## How it's done in production

| Symptom | Cause | Fix |
|---|---|---|
| Typing in one input in a dynamic list clears/corrupts a different item's input | Index-as-key on a list that gets reordered/inserted/deleted, causing DOM nodes (and their uncontrolled input state) to be reused for the wrong logical item | Key by stable, unique item identity (`item.id`), never array index, for any list that isn't strictly append-only/static |
| A deeply nested component tree re-renders entirely on every keystroke in an unrelated top-level input | State lives too high in the tree (often a single large "app state" object at the root), so any update re-renders every descendant that isn't memoized | Move state down closer to where it's used ("state colocation"), split large context objects into narrower ones, or memoize the expensive subtree with `React.memo` once profiling confirms it's the actual cost |
| An interval/timeout callback inside `useEffect` uses a stale value that never updates | Missing dependency in the effect's dependency array — the closure captured the value from the render that scheduled the effect, and the empty/incomplete deps array means it never gets recreated | Add the real dependency (accepting the effect re-runs/re-subscribes), or use the functional updater form (`setState(c => c + 1)`) to avoid depending on the stale value entirely |
| `React.memo` on a component has no effect — it re-renders every time its parent does | A prop is a new object/array/function reference every render (inline literal, unmemoized callback) even if its contents are unchanged, so memo's shallow comparison always sees a difference | Stabilize the reference with `useMemo`/`useCallback` at the source, or (post React Compiler) let the compiler auto-memoize it if the component and its dependencies are eligible for compiler optimization |
| ESLint's `exhaustive-deps` warning gets disabled to "fix" a bug, and a different bug appears later | Suppressing the lint rule instead of fixing the actual stale-closure cause just hides the symptom; the effect still runs with outdated captured values | Address the root cause (functional updater, `useRef` for values that shouldn't trigger effect re-runs, or genuinely including the dependency) rather than suppressing the warning |
| A component using `useContext` re-renders on every unrelated field change in a large shared context object | The context value is one large object; React re-renders every consumer whenever the context's *reference* changes, regardless of which fields a given consumer actually reads | Split the context into multiple narrower contexts by concern, or use a selector-based state library (see the state management module) for high-frequency-changing shared state instead of raw Context |

---

## Tradeoffs & when NOT to use it

- **Don't reach for `React.memo`/`useMemo`/`useCallback` defensively without profiling evidence.** Every memoization has a real cost (comparison overhead every render, memory for cached values), and applying it everywhere "just in case" pre-Compiler was a common source of code that's harder to read with no measured benefit — profile first, memoize the specific bottleneck the Profiler actually identifies.
- **Don't rely on the React Compiler as a substitute for understanding the underlying model.** It's stable and real, but it has documented eligibility rules (certain patterns opt components out of compilation, e.g. some dynamic property access patterns or violating the Rules of Hooks/React itself), and debugging why the compiler *didn't* optimize a component you expected it to still requires knowing what it's doing under the hood.
- **Don't use index-as-key reflexively "because it's simpler" without checking whether the list can actually reorder/insert/delete.** For genuinely static, append-only, or replace-wholesale lists it's harmless; for anything else it's a real, often silent bug (state misattachment) that doesn't show up in casual testing unless you specifically test reordering with stateful list items.
- **Don't put every piece of application state in one large context or top-level state object "for simplicity."** It's the single most common cause of unnecessary re-render cascades in React apps, and the fix (colocation, narrower contexts, or a proper state management tool per the next module) is architectural, not a performance micro-optimization applied after the fact.

---

## Interview questions

### Q1 — What are the three things that cause a React component to re-render?
**Testing:** baseline mental model of the re-render trigger set.
**Answer:** Its own state changes (`useState`/`useReducer`), its parent re-renders and it isn't memoized, or a context value it subscribes to via `useContext` changes.
**Follow-up trap:** *"Does a prop changing cause a re-render on its own, independent of the parent re-rendering?"* — no — a prop can only change *because* the parent re-rendered and passed a new value; "props changed" isn't a fourth independent trigger, it's a description of what happens during trigger #2.

### Q2 — Why does using array index as `key` break state when a list is reordered?
**Answer:** React matches list children by key across renders to decide whether to reuse an existing DOM node/component instance or create a new one. With index as key, the key for "whatever item is now at position 0" is always `0`, regardless of which logical item that actually is after a reorder — React sees the same key at that position and reuses the DOM node (including any uncontrolled input state it holds), silently reattaching that state to the wrong logical item.
**Follow-up trap:** *"Is index-as-key always wrong?"* — no — for a list that's genuinely static or only ever appended-to/replaced-wholesale (never reordered, no mid-list insertion/deletion), index and identity coincide and there's no actual bug; the rule specifically applies to lists with reordering/insertion/deletion.

### Q3 — Why must hooks be called unconditionally, in the same order, on every render?
**Answer:** React tracks each hook's state by its position in a linked list attached to the component's fiber, not by name — there's no identifier at the call site to match against. A conditionally-skipped hook shifts every subsequent hook's position on that render, so React reads/writes the wrong stored state for all of them.
**Follow-up trap:** *"How is this enforced — a runtime check, or something else?"* — largely by the `eslint-plugin-react-hooks` `rules-of-hooks` lint rule at development time; React itself can detect *some* violations at runtime (a mismatched hook count/type between renders) and will warn or error, but not all violations are cleanly catchable at runtime, which is exactly why the lint rule (not just runtime detection) is the primary enforcement mechanism.

### Q4 — Trace the bug: a `setInterval` inside a `useEffect` with an empty dependency array, updating a counter via `setCount(count + 1)`, appears stuck alternating between two values instead of incrementing.
**Answer:** The effect runs once (empty deps), and the `setInterval` callback closes over `count` as it was during that one render — every tick calls `setCount(0 + 1)` using the same stale captured `0`, so the state goes 0 to 1 and then every subsequent tick sets it back to `1` again (`0 + 1`), never incrementing further, because the closure was never recreated with an updated `count`.
**Follow-up trap:** *"Two ways to fix it — what's the tradeoff between them?"* — the functional updater `setCount(c => c + 1)` avoids depending on `count` entirely (no re-subscription needed, effect stays `[]`); adding `count` to the dependency array fixes correctness too but re-runs the effect (clearing and resetting the interval) every tick, which is usually wasteful for something like a fixed-interval timer — the functional updater is the better fix for this specific case.

### Q5 — `React.memo` is applied to a child component, but it still re-renders every time its parent does. Diagnose.
**Answer:** `memo` does a shallow comparison of props; if any prop is a new object/array/function reference every render (an inline literal like `{{a:1}}`, or an unmemoized callback defined inline), the shallow comparison sees a different reference even though the contents are identical, and the component re-renders anyway.
**Follow-up trap:** *"Does the React Compiler fix this automatically?"* — for eligible components, yes — the compiler can auto-memoize both the component and the values/functions it depends on, effectively achieving reference stability without manual `useMemo`/`useCallback`; but eligibility isn't universal (specific patterns opt a component out of compilation), so verifying the compiler is actually applying to a given component (rather than assuming it always does) is the honest answer.

### Q6 — Describe your systematic method for figuring out why a component is re-rendering unexpectedly.
**Answer:** Open the React DevTools Profiler, record the interaction, identify which components rendered and use the "why did this render" indicator to see the specific trigger (props/state/hooks changed, or parent re-rendered). If it's an unmemoized parent re-render with stable props, that's a genuine `memo` candidate; if props aren't actually stable, trace the reference instability to its source (usually an inline object/callback) rather than reaching for `memo` on the child first.
**Follow-up trap:** *"What if the Profiler shows it's a context re-render?"* — check whether the consumer needs the whole context value or just one field of it — a single large context object means any field changing re-renders every consumer regardless of which fields they read; the fix is splitting the context or moving to a selector-based external store for high-churn shared state.

### Q7 — Why is React's reconciliation algorithm O(n) instead of the general tree-diff problem's O(n³)?
**Answer:** React makes two simplifying heuristic assumptions instead of solving general tree diff: elements of different types at the same position are assumed to produce entirely different subtrees (so it never tries to diff across a type change, just remounts), and `key` is trusted as the developer-provided signal for element identity within a list, avoiding the need to compute an actual minimal-edit-distance match between old and new children.
**Follow-up trap:** *"What's the failure mode of trusting key blindly?"* — if a key is reused for a genuinely different logical item (e.g., recycling keys after deletion in a way that collides with a new item), React will incorrectly treat them as the same element and reuse state/DOM that shouldn't be reused — the heuristic's correctness entirely depends on keys accurately representing identity, which is on the developer to guarantee.

### Q8 — What does the React Compiler actually do, and since when has it been stable?
**Answer:** It statically analyzes component code and automatically inserts memoization (equivalent to what `useMemo`/`useCallback`/`React.memo` would do by hand) for values, functions, and components where it determines it's safe and beneficial, without requiring the developer to write those calls manually. It reached stable 1.0 in October 2025 and works back to React 17, not just React 19.
**Follow-up trap:** *"Does it replace the Rules of Hooks?"* — no — the compiler actually depends on code following the Rules of Hooks and other React rules (no mutating props/state directly, etc.) to safely analyze and transform it; violating those rules can cause a component to be silently skipped by the compiler (falling back to normal, unoptimized behavior) rather than the compiler "fixing" the violation.

### Q9 — Why does putting all application state in one large top-level object/context tend to cause performance problems as an app grows?
**Answer:** Any update to any field in that object changes its reference, and every component subscribed to it (via context, or via being a descendant that isn't memoized) re-renders — regardless of whether the specific field that changed is one they actually read. This turns an update to one small, localized piece of state into a re-render cascade through everything downstream that touches the shared state object.
**Follow-up trap:** *"Is splitting into multiple contexts always sufficient, or when do you need an external store?"* — splitting contexts helps but doesn't fully solve high-frequency updates (e.g., state that changes many times per second, like a text input value shared broadly) — libraries with built-in selector subscriptions (Zustand, Jotai — covered in the state management module) let consumers subscribe to just the slice they read, re-rendering only when *that* slice changes, which plain Context cannot do natively.

---

## Red flags that fail you

- Explaining re-renders as "React updates the DOM whenever state changes" with no mention of the function-re-execution-then-diff model.
- Recommending index-as-key for any dynamic list without checking whether it reorders/inserts/deletes.
- Not knowing the actual mechanism behind the Rules of Hooks (call-order tracking via a linked list) — treating it as an arbitrary style rule.
- Adding `useMemo`/`useCallback`/`memo` everywhere reflexively with no profiling evidence, or as a first response before checking if the re-render is actually a measured problem.
- Fixing a stale-closure `useEffect` bug by disabling the `exhaustive-deps` lint rule instead of addressing the actual dependency issue.
- Claiming the React Compiler eliminates the need to ever understand manual memoization or the underlying re-render model.

---

## Cheat card

```
3 RE-RENDER TRIGGERS: own state change | parent re-renders (unmemoized) | subscribed
  context value changes. "Props changed" is NOT independent — it's #2's mechanism.

RECONCILIATION: same type+position -> reuse DOM node, patch props
  different type+position -> unmount old, mount new (state LOST)
  O(n) heuristic, not general tree diff (which is O(n^3))

KEYS: React matches list children by key. index-as-key = position IS the key ->
  breaks the moment list reorders/inserts/deletes (state/DOM reattaches to wrong item)
  fine for static/append-only/replace-wholesale lists only

HOOKS RULE MECHANISM: hooks stored in a per-fiber LINKED LIST, read/written by
  CALL ORDER not name. Conditional hook call shifts every later hook's slot ->
  corrupts their stored state. Enforced by eslint-plugin-react-hooks primarily.

useEffect deps = correctness contract, not perf knob. Missing dep = stale closure
  captured at the render that scheduled the effect. exhaustive-deps warns on this —
  disabling it hides the bug, doesn't fix it.
  FIX for interval/stale-value bugs: functional updater setState(c => c+1)

React.memo: shallow prop comparison, skips re-render if refs equal.
  DEFEATED BY: inline object/array/function literal props (new ref every render)
  FIX: useMemo/useCallback at the source, or let Compiler handle it if eligible

DEBUG METHOD: DevTools Profiler -> record -> "why did this render" indicator ->
  identify actual trigger -> fix at the SOURCE (reference instability, state
  location, context granularity), don't reflexively wrap in memo first

REACT COMPILER: stable 1.0 since Oct 2025, works back to React 17. Auto-memoizes
  via static analysis. REQUIRES Rules of Hooks compliance to analyze safely —
  violations can cause silent bailout to unoptimized behavior, not auto-fix.

CURRENT: React 19.2.x stable (mid-2026). React 19 (Dec 2024) added Actions,
  useActionState, useFormStatus, use() hook, formalized RSC support.
```

## Sources

- [React docs: Rendering and Committing](https://react.dev/learn/render-and-commit) — accessed 2026-08-02
- [React docs: Rules of Hooks](https://react.dev/reference/rules/rules-of-hooks) — accessed 2026-08-02
- [React docs: Rendering Lists (keys)](https://react.dev/learn/rendering-lists) — accessed 2026-08-02
- [React Compiler docs](https://react.dev/learn/react-compiler) — accessed 2026-08-02
- [React 19: What's New for Developers — Scrimba](https://scrimba.com/articles/react-19-whats-new-for-developers/) — accessed 2026-08-02
- [React Versions — react.dev](https://react.dev/versions) — accessed 2026-08-02

## Changelog
- 2026-08-02 — created
