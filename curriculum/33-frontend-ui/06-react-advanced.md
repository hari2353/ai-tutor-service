# RSC, Suspense, Server Actions, Next.js App Router, Hydration and Its Failure Modes

> **Track:** T33 Frontend & UI Engineering · **Time:** 3.0h · **Prereqs:** T33-react-core
> **Module id:** `T33-react-advanced` · **Tags:** react, critical

## The 30-second version

React Server Components (RSC) run exclusively on the server, never ship their code to the client, and can `await` data directly in the component body — they render to a special serialized stream (not HTML directly, a distinct RSC payload format) that describes the resulting element tree, which the client then reconciles against; Client Components (`"use client"`) are the ones that actually hydrate and run interactive JS in the browser, and the two compose in a tree where Server Components can render Client Components but not vice versa (a Client Component can only receive already-rendered Server Components as `children`/props, it can't import and render one directly). Suspense lets a component tree declare "this part isn't ready yet" and show a fallback while data streams in, and combined with Server Components it enables **streaming SSR**: the server sends the shell HTML immediately and streams in slower parts as their data resolves, rather than blocking the entire response on the slowest data dependency. Server Actions are functions marked `"use server"` that the client can call as if they were local async functions, but which actually execute as a POST request on the server — they're the mechanism behind progressive-enhancement-capable forms that work before JS hydrates. Next.js 16 (React 19.2 under the hood, Turbopack as the default bundler for both dev and build) made `params`/`searchParams`/`cookies`/`headers` **strictly async**, requiring `await` everywhere they're read, and introduced Cache Components (the `"use cache"` directive) making caching explicit and opt-in rather than the previous implicit, frequently-surprising defaults. Hydration failure is what happens when server-rendered HTML doesn't match what the client would render on first pass — common causes are browser-only APIs read during server render (`window`, `localStorage`), non-deterministic values (`Date.now()`, `Math.random()`) used in initial render output instead of `useId`, and invalid HTML nesting — and the failure mode is React discarding the mismatched server-rendered subtree and re-rendering it client-side, producing visible flicker and, for a large enough subtree, effectively erasing the point of doing SSR at all for that section.

## Why this gets asked

Because RSC/Suspense/streaming SSR is where the framework-level abstraction leaks the most, and debugging it requires understanding what's actually happening across the server/client boundary rather than trusting the mental model of "it's just React." The interviewer has hit a hydration mismatch warning in production that took real effort to trace to a `Date` formatted differently on server vs. client due to timezone, or debugged a waterfall where sequential `await`s inside nested Server Components turned what should have been a fast page into a slow one because each level blocked on the previous. In 2026, with the App Router as the only sensible default in Next.js and RSC becoming the mainstream mental model rather than a novelty, interviewers expect candidates to reason about *where code runs* (server vs. client, and when) as a first-class architectural decision, not an afterthought.

---

## Lineage: past → present → future

**What came before.** Classic client-side-rendered SPAs (2013-2019-ish era of Create React App, client-only React Router) shipped a near-empty HTML shell and a JS bundle that rendered everything client-side after hydration — simple mentally, but it meant a blank page (or a spinner) until JS downloaded, parsed, and executed, which was measurably bad for both perceived performance and SEO/crawlability. Traditional server-side rendering (`renderToString`, pre-streaming) fixed the blank-page problem by rendering full HTML on the server, but introduced its own specific pain: the entire page's SSR had to complete — including waiting on every data dependency — before *any* HTML could be sent, so one slow database query on an otherwise-fast page blocked the whole response (a "waterfall" at the framework level, not just in application code), and then the client still had to re-run the entire component tree during hydration to attach event listeners, which was pure repeated work with no way to skip client-JS for genuinely static parts of the page.

**Where it stands now.** React Server Components (stabilized as part of React 19's core APIs, December 2024) are Meta/Vercel's answer to both problems simultaneously: components that never ship JS to the client at all (not just render HTML then hydrate — the component's *code* never reaches the browser), reducing bundle size for anything that doesn't need interactivity, and Suspense-driven streaming that sends the shell immediately and streams in slower sections independently rather than blocking on the slowest one. Next.js's App Router, built on this model, is now Next.js's stable, primary, recommended router — the Pages Router (the older, client/SSR-without-RSC model) is explicitly in maintenance mode as of Next.js 16. This is genuinely deployed at scale (Vercel's own production infrastructure, and a large fraction of new Next.js projects default to App Router), not merely published research — but there's real, live disagreement in the ecosystem about RSC's complexity cost: the server/client component boundary, the "can't import a Client Component into a Server Component the naive way" rules, and debugging across a serialization boundary that isn't plain HTTP/JSON are genuinely harder to reason about than plain client-side React, and some teams explicitly choose to stay on simpler client-rendered architectures (or Pages Router / other frameworks) for that reason — that tradeoff is a legitimate, currently-unresolved debate, not settled consensus that RSC is unconditionally better.

**Where it's heading.** Next.js 16's Cache Components (`"use cache"`) directly targets the other major live complaint about the App Router's earlier caching model — that caching was implicit and defaults changed in confusing ways across versions — by making caching an explicit, opt-in directive at the page/component/function level, working with Partial Prerendering to produce a static shell that streams in dynamic content. This is real and shipping (Next.js 16, 2026), not speculative. What's more genuinely uncertain is how much of this RSC/Server Actions model other meta-frameworks and non-Next.js React usage converges on versus Next.js-specific innovation staying Next.js-specific — RSC itself is a React core feature usable outside Next.js, but the specific caching/routing conventions (Cache Components, the App Router's file conventions) are Next.js's own design, and it's a real open question how much the rest of the React ecosystem adopts equivalent patterns versus diverging.

---

## Mental model

```
SERVER                                          CLIENT
┌─────────────────────────┐
│ Server Component tree    │
│  - runs ONLY on server    │
│  - can await data directly│
│  - code NEVER ships to    │──RSC payload──▶  ┌──────────────────────────┐
│    the client              │  (serialized      │ React reconciles the      │
│  - renders Client           │   element tree,   │ RSC payload against the   │
│    Components as "holes"    │   NOT html)       │ existing client tree      │
│    filled with their own    │                   │                            │
│    serialized props          │                  │ Client Components          │
└─────────────────────────┘                    │  ("use client") DO ship   │
                                                  │  JS, DO hydrate, DO run   │
                                                  │  interactive code         │
                                                  └──────────────────────────┘

STREAMING SSR + SUSPENSE:
  <Shell>                          server sends this IMMEDIATELY
    <Suspense fallback={<Spin/>}>  placeholder streams first...
      <SlowComponent />            ...then this streams in when its
    </Suspense>                       data resolves, injected into
  </Shell>                            the already-sent HTML via an
                                       inline <script> that swaps it in

HYDRATION MISMATCH:
  Server renders:  <div>{new Date().toLocaleTimeString()}</div>  -> "3:04:12 PM"
  Client renders:  <div>{new Date().toLocaleTimeString()}</div>  -> "3:04:13 PM" (1s later!)
  React compares server HTML vs. what client WOULD render -> MISMATCH
  -> discards server HTML for that subtree, re-renders client-side -> flicker
```

---

## How it actually works

### Server Components vs Client Components — the actual boundary rules

```jsx
// ServerComponent.jsx — no directive needed, this IS the default in the App Router
async function ProductPage({ id }) {
  const product = await db.products.findById(id);   // direct await, runs on the server, no useEffect/loading state needed
  return (
    <div>
      <h1>{product.name}</h1>
      <AddToCartButton productId={product.id} />      {/* passing a Server Component's data DOWN to a Client Component is fine */}
    </div>
  );
}

// AddToCartButton.jsx
"use client";                                          // marks this and everything it imports as Client
import { useState } from "react";
export function AddToCartButton({ productId }) {
  const [pending, setPending] = useState(false);
  return <button onClick={() => { setPending(true); addToCart(productId); }}>Add</button>;
}
```

The rule that trips people up: `"use client"` marks a **module boundary**, not just one component — everything imported into that file (and transitively, unless it itself declares its own boundary) becomes part of the client bundle. And the composition direction is one-way: a Server Component can render a Client Component (passing serializable props), but a Client Component **cannot** `import` and directly render a Server Component the normal way — because by the time client code is running in the browser, there's no server available to run that component's `async`/data-fetching code. The actual escape hatch is passing Server Components **as children/props** to a Client Component from a Server Component parent — the Client Component treats them as an opaque already-rendered slot, never trying to import or re-render them itself.

```jsx
// this pattern works — Server Component passed as children, not imported
"use client";
function ClientWrapper({ children }) { return <div className="fancy-border">{children}</div>; }

// in a Server Component:
function Page() {
  return <ClientWrapper><ServerRenderedContent /></ClientWrapper>;  // OK — ServerRenderedContent
}                                                                     // is rendered on the server
                                                                       // BEFORE being handed to
                                                                       // ClientWrapper as an
                                                                       // already-resolved slot
```

### Suspense and streaming, mechanically

```jsx
// untested sketch — App Router page with independent streaming sections
export default function Page() {
  return (
    <div>
      <Header />                                {/* fast, sent immediately */}
      <Suspense fallback={<ReviewsSkeleton />}>
        <Reviews />                              {/* slow query, streams in independently */}
      </Suspense>
      <Suspense fallback={<RecommendationsSkeleton />}>
        <Recommendations />                      {/* different slow query, streams independently too */}
      </Suspense>
    </div>
  );
}
```

The server sends the initial HTML with the `Header` content and both fallback skeletons immediately (this is the point where Time To First Byte / First Contentful Paint effectively completes). As each `Suspense` boundary's data resolves, the server streams an additional chunk containing the real content plus a small inline script that swaps it into the already-delivered DOM in place of the fallback — critically, **the two Suspense boundaries resolve independently**, so a slow `Recommendations` query doesn't block `Reviews` from appearing as soon as its own data is ready. This is the mechanical fix for the pre-RSC problem where one slow dependency blocked the entire SSR response.

### Server Actions

```jsx
// untested sketch — a Server Action used directly as a form action
async function createPost(formData) {
  "use server";                                   // marks this function as server-only,
  const title = formData.get("title");             // callable from the client as if local
  await db.posts.create({ title });
  revalidatePath("/posts");                        // invalidate cached data so the list updates
}

function NewPostForm() {
  return (
    <form action={createPost}>                      {/* works BEFORE JS hydrates — progressive enhancement */}
      <input name="title" />
      <button type="submit">Create</button>
    </form>
  );
}
```

Passing a `"use server"` function directly as a `<form action={...}>` means the form is a genuine HTML form submission at the network level (a real POST, with a serialized reference to the specific server function to invoke) — it works even if client JS hasn't loaded/hydrated yet, which is the actual "progressive enhancement" claim, not marketing language. Once JS is active, the same action can be called imperatively (`await createPost(formData)` from an event handler) with pending/error state managed via `useActionState`/`useFormStatus`.

### Next.js 16 specifics: async APIs and Cache Components

```jsx
// Next.js 16 — params, searchParams, cookies, headers are ALL strictly async now
export default async function Page({ params, searchParams }) {
  const { id } = await params;               // BREAKING vs. pre-16: params used to be a plain object
  const { sort } = await searchParams;
  const cookieStore = await cookies();
  // ...
}
```

This is the highest-file-count breaking change in the Next.js 16 migration — every page, layout, and route handler that reads `params`/`searchParams`/`cookies()`/`headers()` needs updating (a codemod handles most of it automatically). **Cache Components** (`"use cache"`) replace the older implicit caching model:

```jsx
async function getProducts() {
  "use cache";                                // this function's OUTPUT is cached, with an
  return db.products.findMany();                // automatically-derived cache key from its inputs
}
```

Placed at the top of an async Server Component or function body, `"use cache"` caches the *rendered output*, not just the raw data, and composes with Partial Prerendering to produce a static shell for the cached parts while genuinely dynamic parts still stream in. The distinction that matters in practice: `revalidateTag()` invalidates cached content where eventual consistency is fine (a blog post list that can be a few seconds stale), while `updateTag()` is for Server Actions where the user needs to see their own change immediately (a profile update) — conflating the two produces either stale UI after a user's own action, or unnecessarily aggressive cache invalidation for content that didn't need it.

### Hydration and its failure modes

React's hydration process reuses server-rendered DOM nodes and attaches event listeners/state to them, **assuming** the client's first render pass produces the identical output to what the server sent. When it doesn't match:

1. **Browser-only APIs read during server render** — `window`, `localStorage`, `navigator` are all `undefined` on the server; code that reads them unconditionally either crashes during SSR or (if guarded with a check like `typeof window !== "undefined"`) produces different output between server (no window) and client (has window), a classic mismatch.
2. **Non-deterministic values used in the initially-rendered output** — `Date.now()`, `Math.random()`, or an incrementing counter used to generate an id will almost certainly differ between the server's render and the client's re-render pass. `useId()` exists specifically to solve this for generated ids: it produces a stable, server/client-consistent identifier by deriving it from the component's position in the tree rather than a random/incrementing source.
3. **Timezone/locale-dependent date formatting** — `new Date().toLocaleString()` can differ between a server running in UTC and a client browser in the user's local timezone, a specific, frequently-hit version of the non-determinism problem above.
4. **Invalid HTML nesting** — e.g., a `<div>` inside a `<p>`, which browsers silently "fix" by restructuring the DOM during parsing; the browser's corrected DOM structure doesn't match what React expected to hydrate against, producing a mismatch that has nothing to do with data at all, purely markup structure.

When React detects a mismatch, its behavior (in modern React, since the introduction of selective hydration and the current error-recovery approach) is to log a warning/error, discard the mismatched server-rendered DOM for the affected subtree, and re-render that subtree entirely client-side — which causes visible flicker, can break in-flight form state or focus, and for a large enough affected subtree substantially undermines the actual performance benefit SSR was providing.

**Streaming adds its own timing dimension to hydration bugs**: since different Suspense boundaries resolve and get injected at different times, a component that appears stable when tested in a full, non-streamed static render can still exhibit a mismatch specifically under streaming conditions if its output subtly depends on *when* during the stream it happens to render (e.g., reading a value that's still updating client-side while an earlier part of the page has already hydrated and started running effects).

---

## Build it from scratch

A minimal streaming-shell simulator, proving the "send shell immediately, inject resolved content later" mechanism without a full framework:

```js
// untested sketch — simplified streaming SSR: shell first, chunks injected as data resolves
async function streamPage(res, sections) {
  res.write(`<html><body><div id="header">Header</div>`);
  for (const section of sections) {
    res.write(`<div id="${section.id}">${section.fallback}</div>`);  // fallback sent immediately
  }
  res.write(`</body></html>`);
  // NOTE: real response headers would need to be flushed/chunked-encoding here;
  // this sketch illustrates ordering, not the actual HTTP mechanics

  for (const section of sections) {
    const data = await section.resolve();          // each resolves independently, in whatever order finishes first
    res.write(`
      <template id="${section.id}-content">${section.render(data)}</template>
      <script>
        document.getElementById('${section.id}').replaceWith(
          document.getElementById('${section.id}-content').content
        );
      </script>
    `);
  }
  res.end();
}

// usage
streamPage(res, [
  { id: "reviews", fallback: "<p>Loading reviews...</p>", resolve: fetchReviews, render: renderReviews },
  { id: "recs", fallback: "<p>Loading recommendations...</p>", resolve: fetchRecs, render: renderRecs },
]);
// if fetchRecs resolves before fetchReviews, its <script> swap is written FIRST —
// this is the actual mechanism behind "independent Suspense boundaries don't
// block each other," proven by writing the chunk-and-swap logic explicitly
```

---

## How it's done in production

| Symptom | Cause | Fix |
|---|---|---|
| Console warning: "Text content does not match server-rendered HTML" / "Hydration failed" | A value that differs between server and client render (Date formatting, `Math.random()`-based id, a browser-only API read unconditionally, invalid HTML nesting) | Use `useId()` for generated ids; move browser-API reads into `useEffect` (runs only client-side, after hydration) instead of directly in render; validate HTML nesting; format dates deterministically or defer locale-specific formatting to a client-only pass |
| A page is slow to first byte despite most of its content being static | A Server Component `await`s multiple independent data sources sequentially instead of in parallel, or a slow data dependency isn't wrapped in its own `Suspense` boundary so it blocks the whole shell | Parallelize independent server-side data fetches (`Promise.all`), and wrap genuinely slow, non-critical sections in their own `Suspense` boundary so they stream independently instead of blocking the initial response |
| A Client Component throws "Cannot import a Server Component into a Client Component" (or the equivalent build error) | Directly `import`-ing a Server Component file from inside a `"use client"` module, which can't work since the Client Component's code runs in the browser with no server available to execute the Server Component's logic | Restructure to pass the Server Component as `children`/props from a Server Component parent instead of importing it directly inside the Client Component |
| A user submits a profile update via a Server Action, and the UI still shows stale data momentarily after the action completes | `revalidateTag()` was used (eventual-consistency semantics) for something that actually needed immediate consistency after the user's own action | Use `updateTag()` (or the framework's equivalent immediate-invalidation primitive) specifically for Server Actions where the acting user needs to see their own change reflected right away |
| `params`/`searchParams` access throws or returns a Promise unexpectedly after upgrading Next.js | Next.js 16 made these APIs strictly async; code written against the pre-16 synchronous object shape breaks | `await params`/`await searchParams`/`await cookies()`/`await headers()` everywhere they're read; run the official codemod, which handles the majority of call sites automatically |
| A page renders correctly in isolated testing but shows a hydration mismatch only in production/under real streaming | A component's output depends on *timing* relative to when its Suspense boundary resolves and streams in, which differs between a full static render (testing) and genuinely staggered streaming (production) | Audit the component for any dependency on wall-clock timing, load order, or other stream-position-sensitive state; ensure it renders identically regardless of when during the stream it's injected |

---

## Tradeoffs & when NOT to use it

- **Don't default every component to a Server Component reflexively "because it's the new best practice."** Anything genuinely interactive (event handlers, local UI state, browser APIs) needs to be a Client Component regardless — RSC's benefit is for the parts of the tree that don't need interactivity, and forcing everything server-side just adds server/client boundary complexity without benefit for components that were always going to need `"use client"` anyway.
- **Don't adopt the App Router/RSC model for a small app or team where the added mental model cost (server/client boundaries, a new caching model, debugging across a non-HTTP serialization format) isn't paying for itself.** This is a legitimate, currently-live disagreement in the ecosystem, not a settled "always better" — a simpler client-rendered SPA or the older Pages Router model can be the right call for a small, mostly-interactive app with modest SEO/first-paint requirements.
- **Don't treat Server Actions as a substitute for a real API layer if the app also needs a genuine external API** (mobile clients, third-party integrations) — Server Actions are tightly coupled to the specific framework's form/action model; a separate API layer is still the right tool when the same logic needs to be callable from outside the web app itself.
- **Don't rely on hydration-mismatch warnings alone as your only signal.** They're development-mode warnings; a mismatch that happens to be visually unnoticeable (e.g., a slightly different but visually identical DOM structure) can still be silently discarding and re-rendering a subtree client-side in production, costing real performance without an obvious visible symptom — profiling client-side render cost on "already SSR'd" pages is worth doing periodically, not just reacting to console warnings.

---

## Interview questions

### Q1 — What's the fundamental difference between a Server Component and a component that's server-side rendered in the older (pre-RSC) sense?
**Testing:** whether the "code never ships to the client" distinction is actually understood, not just "it renders on the server."
**Answer:** Traditional SSR renders a component to HTML on the server, then ships the *same component's JavaScript* to the client so it can hydrate and potentially re-render. A React Server Component's code never reaches the client at all — it renders to a serialized RSC payload describing the resulting tree, and if it has no interactive behavior, zero of its JS is ever sent to the browser, directly reducing bundle size rather than just moving the initial render server-side.
**Follow-up trap:** *"So does a Server Component ever re-render on the client?"* — no, never — it can only be re-rendered by the server producing a new RSC payload (e.g., after a Server Action triggers `revalidatePath`); any client-side interactivity has to live in a Client Component that receives data from the Server Component tree.

### Q2 — Can a Client Component import and render a Server Component? Why or why not?
**Answer:** Not directly — a Client Component's code runs in the browser, where there's no server execution context available to run a Server Component's `async` data-fetching logic. The composition works the other direction: a Server Component renders a Client Component and passes it Server Components as `children`/props, and the Client Component treats those as an already-resolved, opaque slot rather than importing/rendering them itself.
**Follow-up trap:** *"What happens if you try to `import` a Server Component file into a `\"use client\"` module anyway?"* — it's a build-time error in frameworks enforcing the boundary correctly, since that file would need to be bundled into client JS, which breaks the entire premise of a Server Component never shipping code to the client.

### Q3 — Explain how Suspense enables streaming SSR, and why two independent Suspense boundaries resolving at different times matters.
**Answer:** The server sends the shell HTML (including Suspense fallbacks) immediately without waiting on slow data, then streams additional HTML chunks plus small inline scripts that swap real content into the DOM as each boundary's data resolves. Because boundaries resolve independently, a slow dependency in one section doesn't block a faster section elsewhere on the page from appearing as soon as it's ready — contrasted with pre-streaming SSR, where the entire response waited on the single slowest data dependency.
**Follow-up trap:** *"What determines the order the chunks arrive in?"* — whichever boundary's data resolves first, streams first — it's not tied to their position in the JSX tree, so a fast, later-in-the-page section can visually populate before a slower, earlier section.

### Q4 — What is a Server Action, and why does `<form action={serverActionFn}>` work before JavaScript has loaded?
**Answer:** A function marked `"use server"` that's callable from the client as if local but actually executes as a real request on the server. When passed directly as a form's `action`, the form becomes a genuine HTML form submission (a real POST, carrying a serialized reference to which server function to invoke) — this is native browser behavior that doesn't require any client JS to have loaded or hydrated, which is the actual mechanism behind the progressive-enhancement claim, not a metaphor.
**Follow-up trap:** *"What changes once JS has hydrated?"* — the same action can be invoked imperatively from an event handler with pending/error UI state managed via `useActionState`/`useFormStatus`, giving a richer client experience once JS is available, while the no-JS path still functions as a plain form submission as a fallback.

### Q5 — Give three concrete causes of a hydration mismatch, and explain what React does when it detects one.
**Answer:** (1) Reading browser-only APIs (`window`, `localStorage`) unconditionally during server render, producing different output server vs. client. (2) Non-deterministic values (`Date.now()`, `Math.random()`, an incrementing id) used directly in initial render output instead of `useId()`. (3) Invalid HTML nesting that the browser silently restructures during parsing, producing a DOM shape different from what React expected to hydrate against. When React detects the mismatch, it discards the server-rendered DOM for the affected subtree and re-renders it entirely client-side, causing visible flicker and potentially losing focus/form state in that subtree.
**Follow-up trap:** *"Does React fail the entire page on any mismatch, or is it scoped?"* — scoped to the affected subtree in modern React (selective hydration/recovery), not the whole page — but a large enough mismatched subtree still meaningfully undermines the performance benefit SSR was providing for that section.

### Q6 — Why does `useId()` solve the generated-id hydration mismatch specifically, mechanically?
**Answer:** `useId()` derives a stable identifier from the component's position within the render tree rather than from a random or incrementing runtime source, so the server's render and the client's initial render pass compute the *same* id for the *same* component position, deterministically — unlike `Math.random()` or a module-level counter, which produce different values on each separate execution (server process vs. browser).
**Follow-up trap:** *"Is it safe to use `useId()` output as a value shown to the user, or only for DOM attribute wiring (like `htmlFor`/`aria-describedby`)?"* — it's designed for internal DOM wiring (linking a label to an input, ARIA relationships), not as user-facing content — its format is intentionally opaque/unstable across React versions, so treating it as meaningful displayed data is a misuse even though nothing prevents it syntactically.

### Q7 — What changed about `params`/`searchParams` in Next.js 16, and why?
**Answer:** They became strictly asynchronous — every page, layout, and route handler that reads `params`, `searchParams`, `cookies()`, or `headers()` must `await` them now, whereas pre-16 they were synchronous plain objects. This is part of a broader move toward explicit async boundaries for anything request-dependent, and it's the single highest-file-count breaking change in the 16 migration, though a codemod handles most call sites automatically.
**Follow-up trap:** *"Why would the framework want this to be async at all, architecturally?"* — it aligns with enabling more flexible request handling (e.g., partial prerendering, where the framework needs to be able to defer resolving request-specific data independently of static shell generation) — making it async at the API level, rather than synchronous, is what allows that flexibility without a separate, parallel API for the deferred case.

### Q8 — What does `"use cache"` (Cache Components, Next.js 16) do, and how is it different from the App Router's earlier caching model?
**Answer:** Placed at the top of an async function/component, it caches the function's *rendered output* (not just raw fetched data) with a cache key automatically derived from its inputs, and composes with Partial Prerendering to produce a static shell for cached content while genuinely dynamic parts stream separately. The earlier model's caching was largely implicit (fetch requests cached by default under specific, version-shifting rules), which was a widely-cited source of confusion; Cache Components make caching explicit and opt-in at the call site instead.
**Follow-up trap:** *"When would you use `revalidateTag()` vs `updateTag()`?"* — `revalidateTag()` for content where eventual consistency is fine (a blog post list that can lag by seconds); `updateTag()` inside Server Actions specifically when the acting user needs to see their own change immediately (a profile update) — conflating the two produces either visible staleness after a user's own action or unnecessarily aggressive invalidation for content that didn't need it.

### Q9 — A page that looks fine in local testing shows a hydration mismatch only under real production streaming. What class of bug is this, and how do you find it?
**Answer:** The component's output likely depends on *when* during the stream it happens to resolve and get injected — something timing- or load-order-sensitive that behaves identically in a full, non-streamed static render (typical local testing) but differs when Suspense boundaries genuinely stagger in production. Finding it requires reasoning about what state the component reads that could differ depending on whether it's hydrating early (right after the shell) versus late (after a slow boundary resolves) — often something touching wall-clock time, a value another already-hydrated part of the page has since mutated, or an assumption about DOM/measurement state that isn't actually stable across that timing gap.
**Follow-up trap:** *"Is this bug class unique to RSC/streaming, or did it exist before?"* — it's meaningfully new/exacerbated by streaming specifically — pre-streaming SSR hydrated the whole page in one synchronous pass with no internal timing variance to depend on accidentally; streaming introduces genuine, production-only timing nondeterminism that didn't exist in the simpler all-at-once model.

### Q10 — Explain selective hydration: what problem does it solve that plain streaming SSR leaves open, and what does it do mechanically?
**Testing:** whether the candidate understands hydration scheduling under streaming, not just mismatch avoidance.
**Answer:** With streaming, Suspense boundaries resolve at different times, but classic hydration processes content strictly in DOM order — a slow upper boundary delays hydrating a faster lower one, and pre-React-18 a click landing on not-yet-hydrated content was effectively lost. Selective hydration lets React hydrate each boundary independently as its content arrives, and if the user interacts with a pending boundary, React prioritizes that one: a capture-phase listener at the root records the event and replays it once that boundary finishes hydrating. Time-to-interactive therefore tracks what the user actually touches instead of document order.
**Follow-up trap:** *"So selective hydration makes my page interactive sooner overall?"* — no — total hydration work is unchanged; it reschedules work toward the boundary the user clicked and parallelizes across arriving boundaries, but the same shipped JS reaches full interactivity at roughly the same time — it's scheduling, not a smaller workload.

---

## Red flags that fail you

- Describing Server Components as "just SSR" with no acknowledgment that their code never ships to the client at all.
- Claiming a Client Component can freely `import` and render a Server Component.
- Not knowing at least three concrete causes of hydration mismatches beyond a vague "server and client don't match."
- Treating `Math.random()`/`Date.now()`-based ids as fine for SSR'd content, unaware of `useId()`.
- Confusing `revalidateTag()` and `updateTag()`'s consistency guarantees.
- Not knowing that Next.js 16 made `params`/`searchParams`/`cookies()`/`headers()` async, if claiming current Next.js familiarity.

---

## Cheat card

```
SERVER COMPONENTS (RSC): run ONLY on server, code NEVER ships to client, can await
  data directly. Render to a serialized RSC payload (not raw HTML), client reconciles
  against it. Composition: Server -> Client component OK (as children/props).
  Client -> Server component import: NOT OK (no server exists in the browser).

"use client" = marks a MODULE BOUNDARY, everything imported transitively included
  unless it declares its own boundary.

SUSPENSE + STREAMING: shell + fallbacks sent immediately -> each boundary streams
  its real content independently as ITS OWN data resolves -> no single slow query
  blocks the whole response (fixes pre-RSC SSR waterfall-at-the-framework-level)

SERVER ACTIONS ("use server"): callable like a local async fn, actually a server
  POST. <form action={fn}> = real progressive enhancement, works before JS hydrates.
  useActionState/useFormStatus for pending/error UI once hydrated.

HYDRATION MISMATCH CAUSES: browser-only APIs read during server render (window,
  localStorage) | non-deterministic values (Date.now, Math.random, counters) ->
  use useId() instead | invalid HTML nesting silently restructured by the browser
  RESULT: React discards mismatched subtree, re-renders client-side -> flicker,
  lost focus/form state, undermines SSR's benefit for that subtree

NEXT.JS 16: params/searchParams/cookies()/headers() now STRICTLY ASYNC (await
  everywhere) — highest-file-count breaking change, codemod available.
  Turbopack = default bundler (dev AND build). React 19.2 under the hood.
  "use cache" (Cache Components): caches RENDERED OUTPUT, explicit/opt-in,
  works with Partial Prerendering for a static shell + streamed dynamic parts.
  revalidateTag() = eventual consistency OK. updateTag() = Server Action, user
  needs to see THEIR OWN change immediately.

App Router = stable/primary/recommended. Pages Router = maintenance mode (NN16).
```

## Sources

- [React docs: Server Components](https://react.dev/reference/rsc/server-components) — accessed 2026-08-02
- [React docs: Server Functions (Server Actions)](https://react.dev/reference/rsc/server-functions) — accessed 2026-08-02
- [Next.js 16 release blog](https://nextjs.org/blog/next-16) — accessed 2026-08-02
- [Next.js 16 upgrade guide](https://nextjs.org/docs/app/guides/upgrading/version-16) — accessed 2026-08-02
- [Next.js 16 Cache Components migration guide — Shubhra Dev](https://shubhra.dev/tutorials/nextjs-16-cache-components) — accessed 2026-08-02
- [Next.js Hydration Errors in 2026 — Ankit Khoiwal](https://medium.com/@blogs-world/next-js-hydration-errors-in-2026-the-real-causes-fixes-and-prevention-checklist-4a8304d53702) — accessed 2026-08-02

## Changelog
- 2026-08-02 — created
