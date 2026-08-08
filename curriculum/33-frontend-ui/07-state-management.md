# State: Local vs Server vs URL vs Global; TanStack Query, Zustand, Redux, and When None

> **Track:** T33 Frontend & UI Engineering · **Time:** 2.5h · **Prereqs:** T33-react-core
> **Module id:** `T33-state-management` · **Tags:** react, critical

## The 30-second version

There are four genuinely distinct kinds of state, and most state-management pain in React apps comes from treating them as one kind: **local state** (owned entirely by one component, never needed elsewhere — `useState` is correct and sufficient), **server state** (data that actually lives on a server, is fetched asynchronously, can go stale, and needs caching/revalidation/dedup logic — this is not application state you own, it's a cached copy of someone else's data), **URL state** (state that should survive a refresh and be shareable/bookmarkable — the current filter, the selected tab, the page number — belongs in the URL, not in a store), and **global client state** (state genuinely shared across unrelated parts of the UI that isn't server data and isn't naturally URL-representable — a shopping cart before checkout, a theme preference, an open/closed modal stack). The single most important architectural argument in this space, and the one that actually resolves most "which state library" debates, is that **the majority of what gets reached for as "global state" is actually mismanaged server state** — a `users` array fetched from an API and stuffed into Redux/Zustand is server state wearing a global-state costume, and every manual loading flag, error flag, and stale-cache bug that follows is the cost of re-implementing what a server-state library already solved. TanStack Query (formerly React Query) is the dominant tool for server state specifically — caching, background refetching, deduplication, stale-while-revalidate — and it is explicitly not a replacement for client state management, it solves a different problem entirely. Zustand and Jotai are the dominant lightweight tools for genuine global client state in 2026, both offering selector-based subscriptions so a component only re-renders when the specific slice it reads changes, unlike plain React Context. Redux (with Redux Toolkit) is still the right choice when you need strict, centralized, time-travel-debuggable state transitions with a large team and complex cross-cutting update logic — not because it's outdated, but because most apps' actual state complexity doesn't warrant its ceremony once server state is properly separated out.

## Why this gets asked

Because "what state management library do you use" is a question that reveals whether a candidate has an actual mental model of state or just a library preference. The interviewer has worked on a codebase where server data was manually synced into Redux with hand-rolled loading/error/stale logic that quietly drifted out of sync with the actual server, or debugged a bug where the current filter/tab selection lived in `useState` and vanished on refresh when it should have been a URL parameter the whole time. In 2026, with TanStack Query + Zustand/Jotai as the dominant non-Redux pattern and the "most global state is misplaced server state" argument now widely accepted as the correct default framing, interviewers are testing whether you can categorize a piece of state correctly before reaching for any tool at all — the tool choice is downstream of that categorization, not the first decision.

---

## Lineage: past → present → future

**What came before.** Early large-scale React apps (2015-2016 era) had no consensus answer for cross-component state — prop drilling (passing data down through many intermediate components that don't use it themselves, purely to reach a deeply nested consumer) was the default, and it was a genuine, widely-complained-about maintenance problem: a piece of state needed three levels down meant three components in between had to accept and forward a prop they never used. Redux (2015) answered this with a single centralized store, unidirectional data flow, and pure reducer functions — a real, principled solution to prop drilling and inconsistent update logic, and it became the default answer for "how do I manage state in React" for years, including for data that had nothing to do with cross-cutting concerns. The specific pain that eventually pushed back against Redux-for-everything was boilerplate and a category error: teams were putting server-fetched data (API responses) into Redux, and then hand-writing the loading/error/success action types, reducers, and cache-invalidation logic that a purpose-built server-state library would have handled automatically — Redux is a general state container, not a data-fetching/caching library, and using it as one meant reinventing caching logic per-team, inconsistently, with real staleness bugs when nobody remembered to invalidate a cached list after a mutation.

**Where it stands now.** React Query (renamed TanStack Query with v4, now spanning multiple frameworks) popularized the "separate server state from client state" framing explicitly, and by 2024-2026 this is the dominant consensus pattern in new React codebases: server state in TanStack Query (handling caching, background refetching, deduplication, stale-while-revalidate semantics out of the box), client state in a lightweight store (Zustand or Jotai), with the two layers deliberately not needing to know about each other. Zustand (486 bytes gzipped as of its 5.0.x line) and Jotai are both mature, widely-adopted, and offer selector-based subscriptions — a component subscribes to a specific slice of the store and only re-renders when that slice changes, which plain React Context cannot do (any context value change re-renders every consumer regardless of which field they read). Redux Toolkit (the current, official, opinionated way to write Redux, addressing the original boilerplate complaints directly) remains actively used and is not obsolete — RTK Query (Redux's own server-state solution, shipped alongside RTK) gives teams already invested in Redux's centralized-store model a server-state layer that shares the same store, which is a legitimate, still-current architecture for large, complex apps with a big team that benefits from Redux's strict unidirectional flow and DevTools time-travel debugging.

**Where it's heading.** The trend is continued separation of concerns rather than convergence on a single tool: URL state as its own explicit category (via routing libraries' search-param APIs, or dedicated hooks) is increasingly treated as a first-class, deliberate choice rather than an afterthought, and server-state libraries keep absorbing more of what used to require manual optimistic-update code (TanStack Query's mutation/optimistic-update APIs have matured significantly). What's more genuinely open is whether React's own built-in primitives (Context plus `useSyncExternalStore`, `use()` for reading promises/context conditionally) reduce the need for external libraries over time for simpler apps — the building blocks exist in core React now, but the ergonomics and selector-subscription performance of purpose-built libraries like Zustand still meaningfully outperform hand-rolled Context-based solutions for anything beyond simple cases, and that gap hasn't closed as of 2026.

---

## Mental model

```
FOUR KINDS OF STATE:                          WHERE IT SHOULD LIVE:

LOCAL          "is this dropdown open?"         useState in that component,
               (nobody else needs it)            never lifted higher than needed

SERVER         "what are this user's orders?"   TanStack Query (or equivalent) —
               (lives on a server, can go        NOT useState+useEffect+manual
                stale, other users can            loading flags, NOT Redux/Zustand
                change it too)

URL            "which tab is selected?"         URL search params / route segment —
               "what's the current filter?"      survives refresh, is shareable,
               (should survive a refresh,         browser back/forward works for free
                should be shareable/bookmarkable)

GLOBAL CLIENT  "what's in the cart before        Zustand / Jotai (selector-based,
               checkout?" "is the command          only re-renders subscribers of
               palette open?"                      the specific slice that changed)
               (shared across unrelated parts
                of the UI, not server data,
                not naturally URL-representable)

THE ACTUAL BUG PATTERN, most common in the wild:
  const [users, setUsers] = useState([]);        <- SERVER state, forced into LOCAL
  const [loading, setLoading] = useState(false);  <- hand-rolled, no dedup, no cache,
  const [error, setError] = useState(null);          no background refetch, no stale
  useEffect(() => { /* fetch, set all three */ }, []);  invalidation after a mutation
  // multiplied across every component that needs "users" independently fetching
  // the SAME data, with NO shared cache between them
```

---

## How it actually works

### The categorization test, applied concretely

Ask, in order: **Does this data live on a server and can it change independently of this client?** If yes, it's server state — TanStack Query (or equivalent), full stop, regardless of how "simple" the fetch looks. **Would refreshing the page or sharing the URL reasonably be expected to preserve this?** If yes, it's URL state. **Is it used by exactly one component subtree and nothing else needs it?** If yes, it's local state, `useState`/`useReducer`. **Otherwise**, it's genuine global client state, and a selector-based store is the right tool.

```jsx
// untested sketch — the categorization applied to a realistic page
function ProductListPage() {
  const [searchParams, setSearchParams] = useSearchParams();      // URL state
  const sort = searchParams.get("sort") ?? "relevance";
  const page = Number(searchParams.get("page") ?? 1);

  const { data: products, isLoading } = useQuery({                // SERVER state
    queryKey: ["products", sort, page],
    queryFn: () => fetchProducts({ sort, page }),
  });

  const cart = useCartStore(state => state.items);                 // GLOBAL client state,
                                                                      // selector: only re-renders
                                                                      // if `items` specifically changes
  const [isFilterPanelOpen, setFilterPanelOpen] = useState(false);  // LOCAL state
  // ...
}
```

### TanStack Query — what it actually does beyond "fetch and store"

```jsx
// untested sketch — the actual value proposition, not just data fetching
const { data, isLoading, isError } = useQuery({
  queryKey: ["user", userId],
  queryFn: () => fetchUser(userId),
  staleTime: 60_000,          // data is considered fresh for 60s — no refetch even if remounted
});
```

The mechanics that matter: **deduplication** — if two components independently call `useQuery` with the same `queryKey` at the same time, only one network request fires, and both components share the cached result. **Background refetching** — TanStack Query refetches stale data on window refocus, network reconnect, or a configured interval by default, keeping displayed data fresh without the user manually reloading. **Cache invalidation on mutation**:

```jsx
const queryClient = useQueryClient();
const { mutate } = useMutation({
  mutationFn: updateUser,
  onSuccess: () => {
    queryClient.invalidateQueries({ queryKey: ["user", userId] });  // marks cached data stale,
  },                                                                   // triggers a refetch —
});                                                                     // this is the mechanism
                                                                          // that keeps UI consistent
                                                                          // after a write, which
                                                                          // hand-rolled fetch+useState
                                                                          // code has to reimplement
                                                                          // manually and often forgets
```

This is the concrete, mechanical version of "server state needs its own solution": every one of these behaviors (dedup, background refresh, stale-triggered refetch, invalidation-on-mutation) is either skipped entirely or hand-rolled, inconsistently, per-team, when server data is instead stuffed into `useState`/Redux/Zustand as if it were regular client-owned state.

### Zustand — selector subscriptions, mechanically

```jsx
// untested sketch — Zustand store with selector-based subscription
import { create } from "zustand";

const useCartStore = create((set) => ({
  items: [],
  addItem: (item) => set((state) => ({ items: [...state.items, item] })),
  itemCount: 0,   // imagine this is derived/updated alongside items
}));

function CartBadge() {
  const itemCount = useCartStore((state) => state.itemCount);  // SELECTOR — only re-renders
  return <span>{itemCount}</span>;                                // if itemCount specifically changes,
}                                                                    // NOT on every store update

function CartPanel() {
  const items = useCartStore((state) => state.items);           // different selector, different
  return <ul>{items.map(i => <li key={i.id}>{i.name}</li>)}</ul>;  // subscription — independent
}
```

This is the mechanical reason Zustand outperforms plain Context for this use case: Context's `useContext` subscribes to the *entire* context value — any change to any field re-renders every consumer. Zustand's `useCartStore(selector)` subscribes to just the selector's output, using reference-equality checking on the selected slice specifically, so `CartBadge` doesn't re-render when `items` changes unless `itemCount` also happens to change as part of the same update.

### Redux (Toolkit) — when the ceremony is actually earning its keep

```jsx
// untested sketch — Redux Toolkit slice, illustrating what it buys you
const cartSlice = createSlice({
  name: "cart",
  initialState: { items: [] },
  reducers: {
    addItem: (state, action) => { state.items.push(action.payload); },  // "mutating" syntax,
  },                                                                       // actually Immer-based
});                                                                         // immutable updates
                                                                              // under the hood
```

What Redux (via Redux Toolkit) genuinely provides that Zustand/Jotai don't emphasize as strongly: **time-travel debugging** (Redux DevTools can replay every action in sequence, invaluable for debugging a complex multi-step user flow after the fact), **strict unidirectional flow enforced by convention across a large team** (every state change is an explicit, named, serializable action, which matters a lot when many engineers are touching the same state and need a consistent, auditable pattern), and **RTK Query** as a server-state solution that shares the same store/DevTools story if a team wants everything — server and client state — visible in one place.

---

## Build it from scratch

A minimal selector-based store, proving the actual subscription mechanism Zustand/Jotai rely on rather than treating it as magic:

```js
// untested sketch — minimal selector-subscription store
function createStore(initialState) {
  let state = initialState;
  const listeners = new Set();

  function getState() { return state; }
  function setState(partial) {
    state = { ...state, ...(typeof partial === "function" ? partial(state) : partial) };
    listeners.forEach((listener) => listener(state));
  }
  function subscribe(listener) {
    listeners.add(listener);
    return () => listeners.delete(listener);
  }
  return { getState, setState, subscribe };
}

// React binding with a selector — the actual mechanism behind "only re-render on the slice you read"
function useStore(store, selector) {
  const [selected, setSelected] = React.useState(() => selector(store.getState()));
  React.useEffect(() => {
    return store.subscribe((state) => {
      const next = selector(state);
      setSelected((prev) => (Object.is(prev, next) ? prev : next));  // bail out if the SELECTED
    });                                                                 // slice didn't actually change
  }, [store, selector]);
  return selected;
}

const cartStore = createStore({ items: [], itemCount: 0 });
// component A: useStore(cartStore, s => s.itemCount)   — only re-renders when itemCount changes
// component B: useStore(cartStore, s => s.items)        — only re-renders when items changes
// updating ONLY itemCount does not re-render component B, and vice versa — this
// IS the mechanism, proven by the Object.is bail-out check inside the subscription
```

---

## How it's done in production

| Symptom | Cause | Fix |
|---|---|---|
| Two components fetching "the same" data show inconsistent values, or the same data is fetched redundantly multiple times | Server data manually fetched into local `useState` per-component with no shared cache — each fetch is independent, unaware of any other component's copy | Move to TanStack Query (or equivalent) with a shared `queryKey` — deduplication and shared caching are handled automatically for identical keys |
| UI shows stale data after a user performs an action that should have updated it (e.g., edits their profile, list elsewhere still shows the old value) | No cache invalidation logic connecting the mutation to the cached read — a common gap in hand-rolled fetch+useState code, since nobody wrote the "and now go tell every other place displaying this data to refetch" logic | Use `useMutation`'s `onSuccess` to call `queryClient.invalidateQueries()` (or the equivalent in whatever server-state library is in use) targeting the affected query keys |
| A filter/tab/page selection resets to default on every page refresh, frustrating users who expect their view to persist or be shareable via link | The state was implemented as component `useState` instead of URL state | Move it into the URL via search params (`useSearchParams` or the router's equivalent), reading initial state from the URL and writing back on change |
| A component re-renders on every unrelated state change in a shared global store/context | Using plain Context for high-frequency-changing shared state (Context subscribes to the whole value, not a slice), or a store without selector-based subscriptions | Switch to a selector-subscription store (Zustand/Jotai) where components subscribe to just the slice they read |
| A large team's state updates become hard to trace/debug after a complex multi-step flow goes wrong in production, hard to reproduce locally | No centralized, replayable action log for state changes — each store's updates happen via arbitrary function calls with no consistent, inspectable trail | Redux (with Redux Toolkit) plus Redux DevTools' time-travel debugging gives an explicit, serializable, replayable action sequence — a legitimate reason to choose Redux specifically for this debugging affordance at scale |
| "Loading" spinners flash briefly on every navigation back to a page the user already visited, even though the data hasn't meaningfully changed | No `staleTime` configured (or equivalent) — the server-state library is treating every mount as needing a fresh fetch instead of trusting recently-fetched data | Configure `staleTime` appropriately for data that doesn't need to be refetched on every single mount, letting cached data render immediately while an optional background refresh happens silently |

---

## Tradeoffs & when NOT to use it

- **Don't put server data into Zustand/Redux/Context "for simplicity" on a small feature.** Even a small feature accumulates the same missing dedup/staleness/invalidation problems as it grows, and retrofitting a proper server-state library later means rewriting the data-fetching layer rather than the (much smaller) cost of using the right tool from the start.
- **Don't reach for Redux by default in 2026 without a specific reason.** For most apps, the actual state complexity that remains after correctly separating out server state (via TanStack Query) and URL state doesn't warrant Redux's ceremony — Zustand/Jotai cover the remaining genuine global-client-state cases with dramatically less boilerplate. Redux earns its place specifically for large teams needing enforced unidirectional flow and time-travel debugging on complex, cross-cutting state logic — not as a default starting point.
- **Don't put genuinely URL-appropriate state in a client store just because it's more convenient to wire up initially.** The cost (broken back/forward navigation, unshareable links, state lost on refresh) is a real, user-visible product defect, not just an internal code-quality concern — this is a case where the "wrong" choice has externally visible consequences, not just harder-to-maintain code.
- **Don't over-fragment truly local state into a global store "in case something else needs it later."** Premature globalization of state that's genuinely local adds unnecessary re-render surface area and indirection for a need that may never materialize — YAGNI applies to state architecture as much as anywhere else.

---

## Interview questions

### Q1 — Name the four kinds of state and give a one-line example of each.
**Testing:** baseline categorization framework.
**Answer:** Local (a dropdown's open/closed state — `useState`), server (a user's order history, fetched from an API — TanStack Query), URL (the current filter/sort/tab selection — search params), global client (a shopping cart before checkout, shared across unrelated UI — Zustand/Jotai).
**Follow-up trap:** *"Is a logged-in user's profile data local, server, or global state?"* — server state, even though it's often treated as "global" in codebases — it lives on a server, can go stale, and needs the caching/revalidation behavior a server-state library provides, not just broad accessibility.

### Q2 — What's the argument that "most global state is actually misplaced server state," and why does it matter practically?
**Answer:** Data fetched from an API and stuffed into a general-purpose global store (Redux/Zustand/Context) is server state wearing a global-state costume — it needs caching, deduplication, background refetching, and invalidation-on-mutation, none of which a generic state container provides out of the box, so teams end up hand-rolling loading/error/stale logic per-feature, inconsistently, with real staleness bugs. It matters practically because the fix isn't "pick a different global-state library," it's recognizing the data doesn't belong in general client-state management at all.
**Follow-up trap:** *"Does this mean you never need global client state at all?"* — no — genuine global client state (a cart before checkout, UI state like an open command palette) still exists and still needs a proper tool; the argument is specifically that a large fraction of what gets *labeled* global state is actually mis-categorized server state, not that global client state doesn't exist.

### Q3 — What does TanStack Query provide beyond `useState` + `useEffect` for data fetching?
**Answer:** Deduplication (identical concurrent queries for the same key share one network request and cached result), background refetching (stale data refreshes automatically on window refocus/reconnect/interval without user action), stale-while-revalidate semantics (cached data renders immediately while a background refresh happens), and cache invalidation tied to mutations (`invalidateQueries` after a successful mutation, keeping displayed data consistent after a write).
**Follow-up trap:** *"If two components independently `useQuery` the same key at the same time, how many network requests fire?"* — one — TanStack Query deduplicates identical in-flight queries by key and shares the result across all subscribing components, which naive per-component `useEffect` fetching cannot do without manual coordination.

### Q4 — Why does Zustand avoid unnecessary re-renders that plain React Context causes?
**Answer:** `useContext` subscribes to the entire context value — any change to any field triggers a re-render in every consuming component, regardless of which field it actually reads. Zustand's hook takes a selector function and subscribes only to that selector's output, using reference-equality checking on the selected slice, so a component reading only `itemCount` doesn't re-render when an unrelated field like `items` changes.
**Follow-up trap:** *"Can you fix Context's over-rendering problem without switching libraries?"* — partially, by splitting one large context into multiple narrower contexts by concern, but Context still has no built-in mechanism for a component to subscribe to a *computed selection* of a value the way a selector function can — for high-frequency-changing state, this remains a real limitation Context alone doesn't solve.

### Q5 — When is Redux (with Redux Toolkit) still the right choice in 2026, given TanStack Query + Zustand/Jotai's dominance?
**Answer:** When a large team needs strict, enforced unidirectional data flow with every state change as an explicit, named, serializable action (auditability/consistency across many engineers touching shared state), and/or genuinely benefits from Redux DevTools' time-travel debugging for complex, multi-step state transitions that are hard to reproduce and need to be replayed step by step during debugging. RTK Query additionally lets teams already invested in Redux get a server-state layer sharing the same store/DevTools story.
**Follow-up trap:** *"Isn't this just legacy inertia — would you actually choose Redux fresh, today, for a new project?"* — legitimately, yes, for a specific profile: large team, complex cross-cutting client-state logic (not server state, which still belongs in TanStack Query or RTK Query specifically), where the debugging/audit affordances are worth the added ceremony — the honest answer distinguishes "sometimes actually still correct" from "only there for legacy reasons," which not every candidate does.

### Q6 — A filter/sort selection is implemented with `useState` and resets every time the user refreshes the page. What's wrong, and what's the fix?
**Answer:** This state should be URL state — anything a user would reasonably expect to survive a refresh or be shareable via a copied link belongs in the URL, not component state. Fix: read the initial value from `useSearchParams` (or the router's equivalent), and update the URL (not just local state) whenever the filter/sort changes.
**Follow-up trap:** *"What does URL state additionally give you for free that useState doesn't?"* — browser back/forward navigation working correctly (each filter change becomes a navigable history entry, or can be configured to replace rather than push depending on desired UX), and the state being shareable/bookmarkable — both are real product behaviors, not implementation details, that a client-only `useState` implementation structurally cannot provide.

### Q7 — Explain `staleTime` in TanStack Query and the UX problem it solves.
**Answer:** `staleTime` controls how long fetched data is considered fresh before TanStack Query will refetch it on a trigger like remount or window refocus — during that window, cached data is served immediately with no network request, avoiding an unnecessary loading flash on every return to a page the user recently visited, while still eventually refreshing data that's actually gone stale.
**Follow-up trap:** *"What's the risk of setting `staleTime` too high globally?"* — data can visibly lag behind real server state for longer than acceptable for that specific use case (e.g., a live order status shouldn't have a long staleTime, while a rarely-changing settings list can) — `staleTime` should be tuned per-query based on how frequently that specific data actually changes, not set as one global default for everything.

### Q8 — A mutation succeeds, but a list displayed elsewhere in the app still shows the pre-mutation data until the user manually refreshes. Diagnose.
**Answer:** Missing cache invalidation connecting the mutation to the affected cached query — the mutation succeeded on the server, but nothing told the client's cached copy of the list that it's now stale. Fix: in the mutation's `onSuccess` (or equivalent), call `queryClient.invalidateQueries({queryKey: [...]})` targeting the specific query key(s) that display the now-outdated data, triggering an automatic refetch.
**Follow-up trap:** *"What's the tradeoff of `invalidateQueries` (refetch) vs. directly writing the new value into the cache (`setQueryData`)?"* — `invalidateQueries` guarantees correctness by re-fetching the true server state but costs an extra network round trip and a brief stale/loading window; `setQueryData` updates the cache instantly (better perceived performance) but only as correct as your manual update logic — using it incorrectly can introduce exactly the kind of drift-from-server-truth bug server-state libraries exist to prevent.

### Q9 — Design the state architecture for a product listing page: search/filter/sort controls, the product list itself, and a "recently viewed" widget shared with other pages. Categorize each piece.
**Answer:** Search/filter/sort selections: URL state (shareable, survives refresh, back/forward should step through filter changes). Product list data: server state via TanStack Query, keyed by the filter/sort/page URL values so changing them naturally produces a new cache entry (and reverting a filter can hit an already-cached result). "Recently viewed" (shared across pages, client-tracked, not server-authoritative in this design): global client state via Zustand/Jotai, likely persisted to `localStorage`.
**Follow-up trap:** *"What if 'recently viewed' actually needs to sync across the user's devices?"* — then it's genuinely server state (it lives on a server, associated with the user's account, not just this browser), and belongs in TanStack Query with a mutation to record views and a query to read them — the moment cross-device consistency matters, "client-tracked" stops being an accurate categorization and the architecture needs to change accordingly.

### Q10 — A "like" button should feel instant, but the actual mutation is a real network request that can fail. Design the optimistic-update flow with TanStack Query, including what happens on failure.
**Testing:** the specific mechanics of optimistic updates and rollback, a genuinely common real pattern distinct from the cache-invalidation material already covered.
**Answer:** In the mutation's `onMutate` callback (which runs synchronously before the network request fires), cancel any in-flight queries for the affected data (`queryClient.cancelQueries`) to prevent a race where a background refetch overwrites the optimistic value, snapshot the current cache value (for rollback), then write the optimistic new value directly into the cache (`queryClient.setQueryData`) so the UI updates immediately — the user sees the "liked" state before the network round-trip completes. Return the snapshot from `onMutate` so it's available in `onError`. If the mutation fails, `onError` restores the cache to the snapshotted pre-mutation value, and `onSettled` (running on either success or failure) triggers a real refetch to reconcile the cache with the server's actual authoritative state, correcting for any case where the optimistic guess and the real outcome diverged in a way rollback-to-snapshot alone wouldn't catch.
**Follow-up trap:** *"Why refetch in onSettled even after a successful mutation, if the optimistic value was presumably correct?"* — the optimistic value was a *guess* at what the server would do, not a guarantee — a like-count mutation might trigger server-side side effects (a concurrent like from another user changing the actual count, a server-computed field the optimistic update couldn't have known) that the client's optimistic guess didn't and couldn't account for, so reconciling with a real refetch even after success is what keeps the cache from silently drifting from server truth over many optimistic mutations compounding small inaccuracies.

---

## Red flags that fail you

- Treating all non-local state as "just global state" with no distinction between server, URL, and genuine client state.
- Putting server-fetched data directly into `useState`/Redux/Zustand with hand-rolled loading/error flags and no mention of caching/staleness/dedup as a real concern.
- Recommending Redux by default without acknowledging that most apps' remaining state complexity (after correctly extracting server state) rarely warrants it.
- Implementing filter/tab/sort selections as component state with no consideration of URL state and its refresh/shareability implications.
- Not knowing that Context re-renders every consumer on any value change, regardless of which field a given consumer reads.
- Claiming TanStack Query and Zustand/Jotai are competitors/alternatives to each other rather than solving different categories of state.

---

## Cheat card

```
4 KINDS OF STATE:
  LOCAL  -> useState, single component, nobody else needs it
  SERVER -> TanStack Query (or equiv) — lives on a server, can go stale,
            needs caching/dedup/revalidation, NOT owned client data
  URL    -> search params/route — survives refresh, shareable/bookmarkable,
            back/forward should work (filters, tabs, page number, sort)
  GLOBAL CLIENT -> Zustand/Jotai — shared across unrelated UI, not server
            data, not naturally URL-representable (cart, modal stack, theme)

CORE ARGUMENT: most "global state" bugs are misplaced SERVER state —
  a fetched array in useState/Redux/Zustand reinvents caching per-team,
  inconsistently, with real staleness bugs after mutations

TANSTACK QUERY provides (beyond useState+useEffect):
  - DEDUP: identical concurrent queries by key -> ONE network request, shared cache
  - BACKGROUND REFETCH: on window refocus/reconnect/interval, automatic
  - staleTime: how long cached data is trusted before refetch triggers fire
  - invalidateQueries() in mutation onSuccess: ties writes back to cached reads

ZUSTAND/JOTAI vs CONTEXT: useContext subscribes to WHOLE value, any field
  change re-renders every consumer. Selector-based stores subscribe to just
  the selected slice (reference-equality check) — only re-render on actual
  slice change. Zustand ~486B gzipped (5.0.x).

REDUX (Toolkit) still right when: large team needs enforced unidirectional
  flow w/ explicit serializable actions, OR needs Redux DevTools time-travel
  debugging for complex multi-step state. RTK Query = Redux's own server-
  state layer, shares store/DevTools. NOT a default starting point in 2026.

DOMINANT 2026 PATTERN: server state -> TanStack Query. client state -> Zustand/
  Jotai. URL state -> router search params. The two layers don't need to
  know about each other.
```

## Sources

- [TanStack Query docs](https://tanstack.com/query/latest/docs/framework/react/overview) — accessed 2026-08-02
- [Zustand — GitHub / docs](https://github.com/pmndrs/zustand) — accessed 2026-08-02
- [Redux Toolkit docs](https://redux-toolkit.js.org/) — accessed 2026-08-02
- [Zustand vs Redux Toolkit — theroadtoenterprise.com](https://theroadtoenterprise.com/blog/zustand-vs-redux-toolkit) — accessed 2026-08-02
- [Stop Choosing State Management Blindly — Aryan Garg, Medium](https://medium.com/lets-code-future/stop-choosing-state-management-blindly-zustand-tanstack-query-and-redux-toolkit-finally-9be18cd0ae51) — accessed 2026-08-02

## Changelog
- 2026-08-02 — created
