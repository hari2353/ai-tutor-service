# CSS That Holds Up: Box Model, Flexbox, Grid, Stacking Contexts, Container Queries

> **Track:** T33 Frontend & UI Engineering · **Time:** 2.5h · **Prereqs:** T33-browser-rendering
> **Module id:** `T33-css-layout` · **Tags:** fundamentals

## The 30-second version

The box model is content + padding + border + margin, and `box-sizing: border-box` (now the near-universal reset default) makes `width`/`height` include padding and border rather than add to them, which is the single most common source of "why is this 20px wider than I set it" bugs when a reset isn't applied consistently. Flexbox is for **one-dimensional** layout (distributing space along a single axis, with wrapping as a secondary concern) and Grid is for **two-dimensional** layout (rows and columns simultaneously, with explicit placement); the decision rule that actually holds up is: if you're aligning/distributing items in a row or column and don't need precise control over both axes at once, use Flexbox; if you're laying out a structure where items need to align across both rows and columns (a page shell, a card grid, a form with labeled fields), use Grid — and the two compose fine together, a Grid container full of Flexbox items is a completely normal, common pattern. Stacking contexts are the actual reason `z-index` "doesn't work" in practice: `z-index` only compares elements within the *same* stacking context, and a huge number of common properties silently create a new one (`opacity < 1`, `transform`, `filter`, `position: fixed`/`sticky`, `will-change`, `isolation: isolate`), so a `z-index: 9999` on an element trapped inside a low-z-index stacking context can never appear above a sibling outside it, no matter how high the number goes. A containing block determines what a `position: absolute` element is positioned relative to — the nearest ancestor with `position` other than `static` — and that ancestor-search behavior is a frequent source of confusion when a `transform` on an unrelated ancestor silently becomes the containing block. Container queries let a component respond to its own container's size rather than the viewport's, which is the actual missing piece that made truly reusable, context-independent components possible, and as of 2026 they have full support across all major browsers. Logical properties (`margin-inline-start` vs `margin-left`) express layout in flow-relative terms so it correctly flips for RTL languages and vertical writing modes without manual overrides.

## Why this gets asked

Because CSS looks simple and produces some of the most confusing, hard-to-Google bugs in frontend engineering — a `z-index` that "just doesn't work," an absolutely positioned element that jumps to the wrong ancestor, a component that looks fine at every viewport size except one weird in-between width inside a sidebar. The interviewer has debugged a stacking-context bug that took an embarrassingly long time to trace to an unrelated `opacity` animation three ancestors up, and wants to know if you reason from the actual cascade/containing-block/stacking rules or just add `!important` and `z-index: 99999` until it visually works. The flexbox-vs-grid decision also tests architectural judgment beyond syntax knowledge — whether you default to one tool out of habit or actually pick based on the dimensionality of the layout problem.

---

## Lineage: past → present → future

**What came before.** Pre-Flexbox layout (through the mid-2010s) relied on floats, `display: table`, and increasingly baroque hacks (`clearfix`, negative margins for equal-height columns, `inline-block` with careful whitespace management to avoid stray gaps) because CSS had no native concept of "distribute this extra space" or "align these items along an axis" — floats were designed for wrapping text around images, not for building application layouts, and using them for layout meant fighting a tool built for a different job. The specific pain that killed float-based layout was vertical centering: centering something vertically with 2010s-era CSS required either knowing the exact height in advance (`position: absolute` + negative margin) or a `display: table-cell` hack, both of which were widely mocked as absurd for something conceptually this simple — "how do I center a div" became a genuine industry-wide punchline precisely because the tooling was that inadequate.

**Where it stands now.** Flexbox (CSS Flexible Box Layout, a W3C spec that reached broad browser support around 2015) and Grid (CSS Grid Layout, broad support from 2017 onward) are both mature, fully-supported, and the unambiguous consensus tools for layout — nobody seriously argues for float-based layout in new code anymore. Container queries (`@container`), which let a component query its containing element's size rather than the viewport's, reached full support across Chrome, Firefox, and Safari and are now considered safe for production use as of 2026 — this closes a specific, long-standing gap: media queries only ever let you respond to the *viewport*, which made a genuinely reusable component (one that looks right whether it's in a wide main content area or a narrow sidebar) require either JavaScript-based `ResizeObserver` workarounds or accepting the component wasn't truly context-independent. `:has()` (the "parent selector," letting you style an ancestor based on its descendants) similarly reached full cross-browser support in 2026, closing a gap that previously required JavaScript for what's conceptually a pure CSS relationship. The live disagreement in practice isn't Flexbox-vs-Grid-as-technology (both are settled), it's how much utility-class-first tooling (Tailwind-style) versus component-scoped CSS (CSS Modules, CSS-in-JS, or increasingly just plain CSS with `@scope`) is the right authoring model — that debate is genuinely unresolved and largely a team/ecosystem preference rather than a technical correctness question.

**Where it's heading.** Native CSS nesting (standardized and broadly supported since 2023-2024) and `@scope` (for explicitly bounding a style rule's applicability without relying on naming conventions like BEM) are both real, shipping features reducing the historical case for CSS-in-JS/preprocessor tooling purely for organizational reasons — the trend is native CSS absorbing capabilities that used to require a build step or a JS runtime cost. This is a real direction, not speculative, though it's genuinely uncertain how fast large existing codebases migrate off Sass/CSS-in-JS given the sunk cost of existing tooling and team familiarity — that's an organizational-inertia question more than a technical one.

---

## Mental model

```
BOX MODEL (content-box, the CSS default, vs border-box):

  content-box:  width:200px means CONTENT is 200px.
                actual rendered width = 200 + padding*2 + border*2
                (a common bug source: width creeps beyond what you set)

  border-box:   width:200px means CONTENT+PADDING+BORDER together = 200px.
                (near-universal reset: * { box-sizing: border-box; })

FLEXBOX = ONE axis            GRID = TWO axes simultaneously
┌─────────────────────┐       ┌─────┬─────┬─────┐
│ [A] [B]    [C]       │       │  A  │  B  │  C  │
└─────────────────────┘       ├─────┼─────┼─────┤
  distribute along a line      │  D  │  E  │  F  │
  (row OR column, wrapping     └─────┴─────┴─────┘
   is a secondary concern)      explicit row+column placement,
                                 items can span multiple cells

STACKING CONTEXT (the z-index trap):
  z-index only compares SIBLINGS within the SAME stacking context.
  A NEW stacking context is created by: opacity<1, transform, filter,
  position:fixed/sticky, will-change, isolation:isolate, and more.

  .parent { opacity: 0.99; }        <- accidentally creates a new
    .child { z-index: 9999; }          stacking context on .parent!
  .sibling-outside { z-index: 1; }  <- .child can NEVER appear above
                                        this, no matter how high its
                                        z-index goes — it's trapped
                                        inside .parent's context.
```

---

## How it actually works

### Box model, precisely

```css
.content-box-example { width: 200px; padding: 20px; border: 5px solid; box-sizing: content-box; }
/* rendered width = 200 (content) + 40 (padding, both sides) + 10 (border, both sides) = 250px */

.border-box-example { width: 200px; padding: 20px; border: 5px solid; box-sizing: border-box; }
/* rendered width = 200px exactly. content area shrinks to 200 - 40 - 10 = 150px */
```

`box-sizing: border-box` is the default in essentially every modern CSS reset (including the implicit defaults many frameworks ship) because `content-box` (the actual CSS spec default) makes width composition unintuitive the moment padding or border is involved — "set it to 200px and it renders at 250px" is a real, common confusion for anyone new to CSS, and border-box eliminates the entire class of bug by making the declared width the *final* width.

Margin collapsing is a real, separate box-model gotcha: adjacent vertical margins between block-level siblings (and between a parent and its first/last child, under specific conditions) collapse to the *larger* of the two rather than summing — `margin-bottom: 20px` on one element followed by `margin-top: 30px` on the next produces a 30px gap, not 50px. This only applies to vertical margins in normal flow, not horizontal margins, and doesn't happen with Flexbox/Grid children at all (a genuinely useful side effect of switching to Flexbox/Grid: margin collapsing stops being a surprise).

### Flexbox vs Grid — the actual decision rule

```css
/* FLEXBOX: one-dimensional — a navbar distributing items along a row */
.navbar { display: flex; justify-content: space-between; align-items: center; }

/* GRID: two-dimensional — a page shell with header/sidebar/main/footer */
.page {
  display: grid;
  grid-template-columns: 240px 1fr;
  grid-template-rows: auto 1fr auto;
  grid-template-areas:
    "header header"
    "sidebar main"
    "footer footer";
}
.header { grid-area: header; }
.sidebar { grid-area: sidebar; }
```

The rule that survives contact with real layouts: **ask whether the items need to align across both rows and columns simultaneously.** A card grid where every card in a row should line up with the card above/below it in a strict grid — Grid. A toolbar where buttons just need to sit in a row with even spacing and wrap sensibly on overflow — Flexbox. They compose freely: a Grid-laid-out card whose *internal* content (icon, title, button aligned to the bottom) uses Flexbox is completely normal and extremely common — this composability, not "pick one and use it everywhere," is the actual production pattern.

`gap` (originally a Flexbox/Grid-only property, now also valid in regular block/inline flow layouts in current browsers) replaced margin-based spacing hacks for both — it's the correct tool for consistent inter-item spacing regardless of which layout mode you're in, and it doesn't participate in margin collapsing weirdness at all.

### Stacking contexts — where `z-index` actually goes to die

`z-index` only has meaning *within* a stacking context — it compares the relative order of elements that are siblings **in the same stacking context**, not globally across the whole page. A new stacking context is created by (a non-exhaustive but production-relevant list): `position: fixed` or `sticky` (always), `position: absolute`/`relative` **combined with** a non-`auto` `z-index`, `opacity` less than 1, `transform` (any value other than `none`), `filter`, `backdrop-filter`, `will-change` (if it names a property that would itself create a stacking context), `isolation: isolate`, and being a flex/grid item with a non-`auto` `z-index`.

```css
.card {
  position: relative;
  opacity: 0.99;           /* <-- creates a new stacking context, often ACCIDENTALLY */
}
.card .badge { position: absolute; z-index: 9999; }
.tooltip { position: fixed; z-index: 10; }  /* completely unrelated element, low z-index */

/* .badge, no matter its z-index, can NEVER render above .tooltip if .tooltip is
   OUTSIDE .card's stacking context and .card's own stacking-context-level
   position (among its siblings) is below .tooltip's — .badge's z-index:9999
   only wins comparisons INSIDE .card's own stacking context, it has no
   meaning relative to elements outside it. */
```

The debugging method that actually works: open DevTools, and in Chrome specifically, the **Layers panel** or the 3D view (via the Rendering tab / Elements panel's computed styles) shows stacking context boundaries directly — walk up from the misbehaving element checking each ancestor's computed `opacity`/`transform`/`position` for anything that silently created a context, rather than guessing and incrementing z-index numbers.

### Containing blocks

The containing block for a `position: absolute` element is the nearest ancestor with `position` other than `static` (i.e., `relative`, `absolute`, `fixed`, or `sticky`) — if none exists, it falls all the way back to the initial containing block (viewport-relative, roughly). For `position: fixed`, historically the containing block was always the viewport, **but** a `transform`, `filter`, `will-change: transform`, `perspective`, or `contain: layout` on any ancestor also establishes a new containing block for `fixed`/`absolute` descendants in current browser behavior — meaning a `fixed`-positioned element can silently stop being fixed to the viewport if it's inside a container with one of these properties, a subtle, frequently-surprising interaction between transform and positioning that catches people who assume "fixed" unconditionally means "relative to the viewport."

### Container queries

```css
.card-container { container-type: inline-size; container-name: card; }

@container card (min-width: 400px) {
  .card { grid-template-columns: 120px 1fr; }  /* switch to a horizontal layout
                                                    once the CONTAINER (not viewport)
                                                    is wide enough */
}
```

`container-type: inline-size` opts an element into being a query container along its inline axis (width, in a standard horizontal writing mode) — descendants can then use `@container` rules that respond to *that* container's size, regardless of viewport width. This is the mechanical fix for the "same card component looks wrong crammed into a narrow sidebar vs. a wide main area" problem, which media queries structurally cannot solve because they only ever see the viewport.

### Logical properties

```css
/* physical (assumes LTR, horizontal writing mode) */
.box { margin-left: 16px; padding-right: 8px; }

/* logical (flow-relative — correct automatically in RTL / vertical writing modes) */
.box { margin-inline-start: 16px; padding-inline-end: 8px; }
```

`inline-start`/`inline-end` map to left/right in a horizontal LTR context but automatically flip for `dir: rtl` content or reorient for vertical writing modes — using them instead of `left`/`right` removes an entire class of "the layout is mirrored/broken in Arabic/Hebrew" bugs that would otherwise require a separate RTL stylesheet override for every physical-direction property.

---

## Build it from scratch

A minimal stacking-context resolver proves the "z-index only compares within the same context" model is actually understood, not just recited:

```js
// untested sketch — simplified stacking context resolution
function createsStackingContext(styles) {
  return (
    (styles.position === "fixed" || styles.position === "sticky") ||
    (["absolute", "relative"].includes(styles.position) && styles.zIndex !== "auto") ||
    (styles.opacity !== undefined && styles.opacity < 1) ||
    (styles.transform && styles.transform !== "none") ||
    styles.filter && styles.filter !== "none" ||
    styles.isolation === "isolate"
  );
}

function buildStackingTree(node, parentContext = null) {
  const context = createsStackingContext(node.styles) ? { node, children: [], parent: parentContext } : parentContext;
  if (context && context.node === node) {
    if (parentContext) parentContext.children.push(context);
  }
  for (const child of node.children || []) {
    buildStackingTree(child, context);
  }
  return context;
}

// The point: z-index on `node` only ever gets compared against SIBLINGS
// within the same `context` object — never against nodes belonging to
// a different stacking context, no matter their numeric z-index value.
```

Writing this out mechanically forces the same realization a real debugging session does: z-index isn't a single global ordering number, it's scoped, and the scope boundary is silently created by a specific, memorizable list of properties.

---

## How it's done in production

| Symptom | Cause | Fix |
|---|---|---|
| `z-index: 9999` doesn't bring an element above another element with a much lower z-index | The high-z-index element is trapped inside an ancestor's stacking context (often created accidentally by `opacity`, `transform`, or `will-change` on an unrelated ancestor), and z-index comparisons don't cross stacking context boundaries | Trace ancestors for anything that creates a stacking context (DevTools Layers panel or manual computed-style inspection); either remove the unintended stacking-context trigger, or raise the z-index of the *stacking context root itself* relative to its own siblings |
| A `position: fixed` element scrolls with the page instead of staying pinned to the viewport | An ancestor has `transform`, `filter`, `will-change: transform`, or `perspective` set, which establishes a new containing block for fixed descendants, overriding the expected viewport-relative behavior | Remove the transform/filter from the ancestor if possible, or restructure so the fixed element isn't a descendant of it (e.g., render it via a portal to `document.body`) |
| A component looks correct at every breakpoint tested against the viewport, but wrong when placed inside a narrow sidebar | Media queries only respond to viewport width, not the actual available width of the component's container | Switch to container queries (`container-type: inline-size` on the wrapper, `@container` rules on the component) so it responds to its real available space |
| Vertical spacing between two stacked elements is smaller than the sum of their margins | Adjacent vertical margins in normal block flow collapse to the larger value, not the sum | Either account for this explicitly, or switch the parent to `display: flex`/`grid` with `gap`, which doesn't participate in margin collapsing at all |
| Layout looks mirrored/broken only for RTL locale users | Physical properties (`margin-left`, `left`, `text-align: left`) were used where flow-relative behavior was actually needed | Replace with logical properties (`margin-inline-start`, `inset-inline-start`, `text-align: start`) so the layout automatically adapts to `dir: rtl` without a parallel RTL override stylesheet |
| A card grid has uneven card heights within the same row despite `align-items: stretch` (Grid default) | The cards are Flexbox children of a Flexbox container, not Grid items — Flexbox's cross-axis stretch only applies within a single flex line, not across independent rows the way Grid's implicit row-track sizing does | Switch to Grid for the outer layout if row-to-row alignment across the whole set of cards is actually required, since that's fundamentally a two-dimensional alignment problem |

---

## Tradeoffs & when NOT to use it

- **Don't default to Grid for everything just because it's more powerful.** A simple row of buttons or a centered single item is more code and more indirection as Grid (`grid-template-columns`, explicit placement) than as Flexbox (`display:flex; justify-content:center`) — Grid's two-dimensional power is unnecessary overhead for a genuinely one-dimensional layout problem.
- **Don't reach for container queries as a default replacement for media queries everywhere.** Media queries are still correct and simpler for page-level, viewport-driven layout decisions (e.g., hiding a sidebar entirely below a breakpoint) — container queries solve the specific problem of *component* layout needing to respond to its *local* available space, not every responsive design decision.
- **Don't fight stacking contexts with ever-increasing z-index numbers.** Once you're at `z-index: 999999` and it's still not working, the bug is almost never "not high enough," it's a stacking-context boundary — chasing bigger numbers instead of tracing the actual containment hierarchy wastes time and produces fragile, unmaintainable z-index values that the next person has to exceed again.
- **Don't blanket-apply `isolation: isolate` or extra wrapper `div`s as a stacking-context "fix" without understanding why it works** — it's a legitimate, deliberate tool (creating an intentional, contained stacking context so a component's internal z-index values can never leak out and conflict with the rest of the page), but applied without understanding, it can just as easily trap something that needed to stack above content outside its own subtree.

---

## Interview questions

### Q1 — Explain `box-sizing: content-box` vs `border-box` with a concrete width calculation.
**Testing:** baseline box model arithmetic.
**Answer:** With `content-box` (the CSS spec default), `width: 200px` sets the content area to exactly 200px, and padding/border are added on top — `width:200px; padding:20px; border:5px` renders at 250px total. With `border-box`, `width: 200px` is the *final* rendered width including padding and border — the content area shrinks to accommodate them (150px content in the same example).
**Follow-up trap:** *"Why do virtually all CSS resets set border-box globally?"* — because content-box's default composition (width doesn't include padding/border) is a widely-cited source of "why is this wider than I set it" confusion, especially once nested elements and percentage widths are involved; border-box makes the declared width authoritative.

### Q2 — Give the decision rule for Flexbox vs Grid, not just "Flexbox is 1D, Grid is 2D."
**Answer:** Ask whether items need to align across both rows and columns simultaneously as a structural requirement — a page shell, a card grid where cards must line up row-to-row, a form with aligned labels/inputs across multiple rows: Grid. Distributing/aligning items along a single row or column, with wrapping as a secondary concern rather than a structural alignment requirement: Flexbox. They compose: Grid for the outer structure, Flexbox for alignment inside individual grid items, is the common real pattern.
**Follow-up trap:** *"Can Flexbox do a grid-like layout with `flex-wrap`?"* — approximately, but wrapped flex items don't guarantee alignment across "rows" the way Grid's explicit row tracks do — with varying content heights, wrapped flex items in different rows won't necessarily align to a shared column grid, which is exactly the class of bug that pushes people back to Grid once they hit it.

### Q3 — Why doesn't `z-index: 9999` bring an element above a sibling with `z-index: 1`?
**Answer:** z-index only compares elements within the same stacking context — if the high-z-index element is nested inside an ancestor that itself created a new stacking context (via `opacity < 1`, `transform`, `filter`, `position: fixed/sticky`, `will-change`, `isolation: isolate`, or `position: relative/absolute` with a non-auto z-index), its z-index value only has meaning relative to siblings *inside that same context* — it can never win a comparison against something entirely outside it, regardless of the number.
**Follow-up trap:** *"List the properties that create a new stacking context."* — `position:fixed`/`sticky` unconditionally; `position:relative`/`absolute` combined with a non-auto z-index; `opacity<1`; `transform`/`filter`/`backdrop-filter` other than none; `will-change` naming a stacking-context-triggering property; `isolation:isolate`; being a flex/grid item with non-auto z-index — missing several of these (especially opacity and transform) is the most common gap in a candidate's answer.

### Q4 — What is a containing block, and how does an ancestor's `transform` change `position: fixed` behavior?
**Answer:** The containing block for `position: absolute` is the nearest ancestor with a non-static `position`; falling back to the initial containing block if none exists. `position: fixed` is normally viewport-relative, but a `transform`, `filter`, `will-change: transform`, or `perspective` on any ancestor establishes a new containing block for fixed descendants, meaning the "fixed" element becomes positioned relative to that transformed ancestor instead of the viewport — it will scroll with the page if that ancestor scrolls.
**Follow-up trap:** *"How would you keep a modal truly fixed to the viewport if it must be rendered inside a component with a transform ancestor?"* — render it via a portal (e.g., React's `createPortal`) directly to `document.body` or another element outside the transformed subtree, sidestepping the containing-block issue entirely rather than trying to counteract it with CSS.

### Q5 — What's the difference between media queries and container queries, and when do you actually need the latter?
**Answer:** Media queries respond only to the viewport's dimensions. Container queries (`container-type: inline-size` on a wrapper, `@container` rules on descendants) respond to the actual size of a specific ancestor container, regardless of viewport width. You need container queries when a component must render correctly across genuinely different available widths depending on where it's placed (a card component used both in a wide main area and a narrow sidebar) — a scenario media queries structurally cannot solve since they have no knowledge of the component's actual container width.
**Follow-up trap:** *"Should you replace all your media queries with container queries?"* — no — page-level, viewport-driven decisions (e.g., hiding a whole sidebar navigation below a breakpoint) are still correctly and more simply expressed with media queries; container queries solve local component-context problems specifically, not general responsive design.

### Q6 — Explain margin collapsing with an example, and why Flexbox/Grid children don't have this behavior.
**Answer:** Adjacent vertical margins between block-level siblings in normal flow collapse to the larger of the two values rather than summing — `margin-bottom: 20px` followed by `margin-top: 30px` produces a 30px gap total, not 50px. This is specific to vertical margins in normal block flow; Flexbox and Grid items don't participate in margin collapsing at all, which is one reason `gap` on a flex/grid container is a more predictable spacing tool than relying on margins.
**Follow-up trap:** *"Does this apply to horizontal margins too?"* — no, margin collapsing is a vertical-margins-in-normal-flow phenomenon specifically; horizontal margins never collapse, and it also doesn't apply to elements that establish a block formatting context (e.g., `overflow: hidden`, `display: flow-root`) even in normal flow.

### Q7 — What are logical properties, and why do they matter beyond RTL languages?
**Answer:** Logical properties (`margin-inline-start`, `padding-block-end`, `inset-inline-start`) express spacing/positioning in terms of text flow direction rather than fixed physical directions — `inline-start` maps to left in LTR horizontal writing but automatically flips to right in RTL, and reorients entirely for vertical writing modes (some CJK typesetting). Using them instead of `margin-left`/`right` avoids maintaining a parallel RTL override stylesheet and correctly supports vertical writing modes without any special-casing.
**Follow-up trap:** *"Is there a performance cost to using logical properties?"* — no meaningful one; they're resolved to physical values by the engine the same as any other CSS property — the objection some teams raise is unfamiliarity/readability for developers used to physical properties, not an actual technical cost.

### Q8 — Debug this: a modal's `position: fixed` overlay scrolls away with the page content instead of staying pinned. Where do you look first?
**Answer:** Check every ancestor of the fixed element for `transform`, `filter`, `will-change: transform`, or `perspective` — any of these establishes a new containing block for fixed descendants, which silently changes "fixed relative to the viewport" into "fixed relative to that ancestor," and if that ancestor scrolls within its own context, the "fixed" element appears to scroll with it.
**Follow-up trap:** *"What if none of the ancestors have those properties, and it's still not viewport-fixed?"* — check for `contain: layout`/`paint`/`content` on an ancestor as well, which also establishes a containing block for absolutely/fixed positioned descendants in current spec behavior — a less commonly known but real trigger beyond the transform/filter list.

### Q9 — A card grid component needs to switch from a stacked to a side-by-side internal layout once it has at least 400px of available width, but it's rendered inside both a wide dashboard and a narrow sidebar. Design the CSS approach.
**Answer:** `container-type: inline-size` on the card's wrapper element, then `@container (min-width: 400px) { .card { grid-template-columns: ...; } }` on the card's internal layout — this makes the card's own layout decision based on the actual space it has, correctly switching in the wide dashboard placement and staying stacked in the narrow sidebar, with zero JavaScript and no dependency on the viewport width.
**Follow-up trap:** *"What did teams do before container queries existed for this exact problem?"* — `ResizeObserver` in JavaScript, watching the container element and toggling a class or inline style based on measured width — functional but adds JS runtime cost, a layout-thrashing risk if not batched carefully, and an extra render cycle lag that pure CSS container queries eliminate entirely.

### Q10 — What does `isolation: isolate` do, and when would you deliberately use it as a stacking fix rather than a bug?
**Answer:** It forces the element to create a new stacking context without needing any other side-effecting property (no forced `opacity`, `transform`, etc.) — used deliberately to contain a component's internal z-index values so they can never leak out and conflict with unrelated z-index values elsewhere on the page, a genuinely useful "sandbox my stacking" pattern for a self-contained component (e.g., a design-system dropdown/menu component that manages its own internal layering).
**Follow-up trap:** *"What's the risk of applying it too broadly?"* — a component that legitimately needs to visually stack *above* content outside its own subtree (e.g., a tooltip that must render above a sibling modal) can get trapped by an `isolation: isolate` on an ancestor, the exact same "z-index number wars against a boundary you can't see" problem it was meant to prevent, just self-inflicted instead of accidental — it needs to be applied with the same ancestor-tracing discipline as diagnosing the original bug.

---

## Red flags that fail you

- Explaining `z-index` bugs by suggesting "just increase the number" with no mention of stacking contexts.
- Not knowing which properties create a new stacking context (especially missing `opacity` and `transform`, the two most commonly-accidental triggers).
- Treating Flexbox and Grid as interchangeable, or defaulting to one without a stated reason.
- Claiming `position: fixed` is always relative to the viewport with no awareness of the transform/filter containing-block override.
- Not knowing the difference between media queries and container queries, or claiming container queries should replace all media queries.
- Explaining margin collapsing as "margins always add together."

---

## Cheat card

```
BOX MODEL: content-box (spec default) -> width EXCLUDES padding/border, they ADD on top
  border-box (near-universal reset) -> width INCLUDES padding/border, content shrinks

MARGIN COLLAPSE: adjacent VERTICAL margins in normal flow -> collapse to LARGER value,
  not sum. Doesn't apply horizontally, doesn't apply to flex/grid children, doesn't
  apply across a block formatting context boundary (overflow:hidden, flow-root)

FLEXBOX = 1D (row OR column, wrapping secondary)   GRID = 2D (rows+cols simultaneously)
  decision rule: need alignment across BOTH rows and columns? -> Grid. else -> Flexbox.
  they compose: Grid outer shell + Flexbox inside individual items = normal pattern

STACKING CONTEXT creators: position:fixed/sticky (always); position:relative/absolute
  + non-auto z-index; opacity<1; transform!=none; filter/backdrop-filter!=none;
  will-change (naming a triggering property); isolation:isolate; flex/grid item + z-index
  RULE: z-index only compares SIBLINGS in the SAME stacking context — never crosses
  a context boundary no matter the number. Debug via DevTools Layers panel, trace ancestors.

CONTAINING BLOCK: position:absolute -> nearest ancestor w/ position != static
  position:fixed -> normally viewport, BUT transform/filter/will-change:transform/
  perspective/contain:layout on ANY ancestor overrides this to that ancestor instead

CONTAINER QUERIES: container-type:inline-size on wrapper + @container (min-width:...)
  on descendant -> responds to ACTUAL container width, not viewport. Full support 2026.
  Use for reusable components; media queries still correct for page-level breakpoints.

:has() = parent selector, full support 2026, e.g. .card:has(img) { ... }

LOGICAL PROPERTIES: margin-inline-start/padding-block-end/inset-inline-start
  flow-relative -> auto-correct for RTL/vertical writing modes, no parallel override sheet
```

## Sources

- [CSS Box Model — MDN](https://developer.mozilla.org/en-US/docs/Web/CSS/CSS_box_model) — accessed 2026-08-02
- [The Stacking Context — MDN](https://developer.mozilla.org/en-US/docs/Web/CSS/CSS_positioned_layout/Stacking_context) — accessed 2026-08-02
- [Containing Block — MDN](https://developer.mozilla.org/en-US/docs/Web/CSS/CSS_display/Containing_block) — accessed 2026-08-02
- [CSS Container Queries — MDN](https://developer.mozilla.org/en-US/docs/Web/CSS/Guides/Containment/Container_queries) — accessed 2026-08-02
- [CSS Container Queries Support 2026 — CSS-Zone](https://css-zone.com/blog/css-container-queries-responsive-components) — accessed 2026-08-02
- [Logical Properties — MDN](https://developer.mozilla.org/en-US/docs/Web/CSS/CSS_logical_properties_and_values) — accessed 2026-08-02

## Changelog
- 2026-08-02 — created
