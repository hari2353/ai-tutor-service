# The Browser: Parse → DOM/CSSOM → Layout → Paint → Composite, and the Critical Path

> **Track:** T33 Frontend & UI Engineering · **Time:** 2.5h · **Prereqs:** none
> **Module id:** `T33-browser-rendering` · **Tags:** fundamentals, critical

## The 30-second version

A browser turns HTML and CSS into pixels through five stages: parse HTML into the DOM and CSS into the CSSOM, combine them into a render tree (visible nodes only, with computed styles), compute geometry in layout (position and size, in pixels, for every box), rasterize pixels in paint, and composite the resulting layers on the GPU into the final frame. The critical distinction is that these stages have different costs: a change to `width`, `top`, or any property that affects an element's geometry forces layout to re-run for that element and everything downstream of it in the tree (a "reflow"), a change to `color` or `background` skips layout but still forces paint (a "repaint"), and a change to `transform` or `opacity` on a layer that already has its own GPU texture skips both layout and paint entirely and only re-runs the compositor thread. That's why `transform: translateX()` is cheap enough to animate at 60fps and `left` is not: the compositor thread runs independently of the main thread and doesn't wait for JavaScript, so moving a box via transform never blocks on a slow layout or a busy main thread, while moving it via `top`/`left` forces synchronous layout and paint on every single frame. The practical rule for animation: promote the element to its own layer (`transform`, `opacity`, `will-change`, or `filter`), animate only `transform`/`opacity` on it, and everything else is a performance bug waiting to be found in a DevTools trace.

## Why this gets asked

Because "the browser is slow" is one of the most common vague bug reports a frontend engineer gets, and diagnosing it requires knowing which pipeline stage is actually the bottleneck rather than guessing. The interviewer has almost certainly opened DevTools' Performance panel on a real incident — a scroll-jank bug, a laggy drag interaction, an animation that stutters on mid-range Android but not on their MacBook — and traced it down to purple (layout) or green (paint) bars stacking up on every frame instead of a clean compositor-only path. They want to know whether you reach for "just use `transform`" as a memorized incantation or actually understand why it works: that it routes the change to a thread that isn't contending with the JavaScript that's also fighting for the main thread's 16.7ms budget. A candidate who can explain *why* `top` forces layout but `transform` doesn't — not just that it does — is the one who can debug a jank report they haven't seen before.

---

## Lineage: past → present → future

**What came before.** Early browsers (Netscape/Mosaic era, early-to-mid 1990s) rendered largely synchronously and incrementally with a single-threaded model: parse a bit of HTML, lay it out, paint it, repeat, with no real separation between "the thing that computes geometry" and "the thing that draws pixels" — because pages were mostly static documents, not applications running 60 layout-triggering DOM writes a second. The pain that broke this model was the rise of JavaScript-heavy, animation-rich web apps in the 2000s and 2010s (Ajax-era dashboards, then SPAs): every animated `left`/`top` change or jQuery `.animate()` call forced the main thread to synchronously re-run layout and paint on every frame, and a busy main thread (a slow JS callback, a big layout tree) meant dropped frames and visible stutter, because there was no execution path for "draw a moving box" that didn't route through the same thread doing everything else.

**Where it stands now.** Every major engine (Chromium's Blink, Safari's WebKit, Firefox's Gecko/WebRender) now runs a compositor thread separate from the main thread, promotes elements to GPU-backed layers under specific triggers (`transform`, `opacity`, `will-change`, `<video>`, `<canvas>`, 3D transforms, and a few others), and can animate `transform`/`opacity` on those layers purely on the compositor thread without touching layout, paint, or even JavaScript. This is universal and load-bearing — Chrome's rendering architecture documentation, Firefox's WebRender (shipped by default since Firefox 78 in 2020, a GPU-first rasterizer built in Rust), and Safari's UI-process compositor all converge on the same layered-compositing model, even though the internal implementations differ. The live disagreement isn't over whether this architecture is right (nobody argues for going back to synchronous single-threaded rendering), it's over *how aggressively* to promote elements to layers: `will-change` is a direct hint but each promoted layer consumes GPU memory (roughly width × height × 4 bytes for an RGBA texture, so a full-screen layer at 1920×1080 is about 8MB), and over-promoting ("layer explosion" from scattering `will-change` everywhere) has caused real production slowdowns on memory-constrained devices — Chrome's own guidance explicitly warns against applying `will-change` broadly or leaving it on indefinitely rather than toggling it just before an animation starts.

**Where it's heading.** The trend is compositor-thread work absorbing more of what used to require main-thread layout: CSS scroll-driven animations (`animation-timeline: scroll()`, shipped in Chrome 115+ and gaining cross-browser support through 2025-2026) let scroll-linked animations run entirely off the main thread instead of the old `scroll` event + `requestAnimationFrame` + manual `transform` pattern, which was always vulnerable to main-thread jank blocking the very animation meant to feel smooth during that jank. View Transitions API (stable in Chromium, shipping incrementally elsewhere) is pushing more transition/animation logic into browser-native, compositor-friendly primitives rather than hand-rolled JS. This is a real, shipping direction, not speculative — but layout and paint as *concepts* aren't going away: anything that changes geometry or draws new pixel content will always need the main thread to compute it, because a compositor can only cheaply reuse pixels it already has, not invent new ones.

---

## Mental model

Think of the pipeline as a factory line with a checkpoint at each stage — and the further downstream your change re-enters the line, the cheaper it is:

```
 HTML  ──parse──▶  DOM
 CSS   ──parse──▶  CSSOM
                     │
                     ▼
              ┌─────────────┐
              │ Render Tree │  (DOM ∩ CSSOM, visible nodes only,
              └─────────────┘   with computed styles resolved)
                     │
                     ▼
              ┌─────────────┐
              │   LAYOUT    │  geometry: x, y, width, height for
              │  (reflow)   │  every box — MAIN THREAD, expensive
              └─────────────┘
                     │
                     ▼
              ┌─────────────┐
              │   PAINT     │  rasterize: fill pixels for each layer
              │  (repaint)  │  — MAIN THREAD, moderately expensive
              └─────────────┘
                     │
                     ▼
              ┌─────────────┐
              │  COMPOSITE  │  assemble layers, apply transform/opacity
              │             │  — COMPOSITOR THREAD, cheap, GPU
              └─────────────┘
                     │
                     ▼
                  SCREEN

Entry point for a change determines cost:
  change width/top/font-size  → re-enter at LAYOUT (all 3 stages re-run)
  change color/background     → re-enter at PAINT   (2 stages re-run)
  change transform/opacity    → re-enter at COMPOSITE (1 stage, off main thread)
```

The whole game of rendering performance is: figure out the earliest stage your change re-enters at, and push it as far downstream (right) as you can.

---

## How it actually works

### Parse: HTML → DOM, CSS → CSSOM

The HTML parser is byte-streaming and incremental — it doesn't wait for the whole document before starting the DOM tree, which is why a large HTML response can start rendering before it fully arrives. It's also **blocking on `<script>` by default**: an unmarked `<script src="...">` in the document body halts HTML parsing until the script downloads and executes, because the script might call `document.write()` and change what comes next — this is exactly why `defer` (execute after parsing completes, in document order) and `async` (execute whenever it arrives, no order guarantee) exist as escape hatches. CSS parsing produces the CSSOM, a tree of style rules with specificity/cascade already resolved conceptually (the actual cascade resolution — which rule wins — happens when computing styles for the render tree, not during CSSOM construction itself). CSS is **render-blocking**: the browser cannot safely paint anything until it knows the CSSOM, because any rule anywhere in the stylesheet could apply to any element already parsed. This is why a slow, render-blocking stylesheet in `<head>` delays First Contentful Paint even if the HTML itself streamed in instantly, and it's the mechanical reason performance guidance says to inline critical CSS and defer the rest.

### Render tree, layout, paint

The render tree is the DOM filtered to visible nodes only (elements with `display: none` and their subtrees are excluded entirely — they contribute nothing to layout or paint; `visibility: hidden` is different, the element *is* in the render tree, it's laid out and taking up space, it just isn't painted) with computed style attached to each node.

**Layout** (also called reflow) walks this tree and computes the exact box geometry — x, y, width, height in pixels — for every node. This is fundamentally a **whole-subtree** operation in the worst case: changing one element's width can change its neighbors' positions (if they're in flow), which can change their parent's height (if it's sized by content), which can change everything below that parent. The layout algorithm's complexity depends on the layout mode — normal flow and even most flexbox/grid layouts are effectively linear or near-linear in node count per pass in modern engines, but a **layout invalidation still triggers a pass over the affected subtree**, and if you trigger many of them in a tight loop (see forced synchronous layout below) that cost multiplies badly.

**Paint** rasterizes: for every element (or more precisely, for the pixels within each paint-worthy layer), it converts "draw a blue rounded rectangle with this shadow" into actual pixel data. Paint is ordered — the browser has to respect stacking order (see the CSS module for stacking contexts) so overlapping elements composite correctly. Paint is cheaper than layout because it doesn't need to recompute geometry, only redraw pixel content, but it's still main-thread work proportional to the area and complexity (shadows, gradients, and border-radius are all measurably more expensive to rasterize than a flat fill — `box-shadow` in particular is a well-known paint-cost offender on large areas).

**Composite** runs on a separate compositor thread (in Chromium, literally a different OS thread from the one running JS/layout/paint) and assembles pre-rasterized layers into the final frame, applying `transform` and `opacity` as GPU operations on the *existing* rasterized texture — no re-rasterization needed. This is why it's so much cheaper: it's matrix math and alpha blending on pixels that are already drawn, not a request to draw new pixels.

### The property-to-stage mapping, concretely

| Property class | Examples | Re-enters at | Cost |
|---|---|---|---|
| Geometry | `width`, `height`, `top`/`left` (positioned), `margin`, `padding`, `font-size`, `border-width` | Layout | Highest — layout + paint + composite |
| Visual, non-geometric | `color`, `background-color`, `box-shadow`, `visibility`, `outline` | Paint | Medium — paint + composite |
| Layer-composited | `transform`, `opacity` (on a promoted layer), `filter` (on a promoted layer in modern engines) | Composite | Lowest — compositor thread only |

`top`/`left` specifically only skip layout if the element is `position: fixed`/`absolute` *and* removed from normal flow in a way that doesn't affect siblings — but even then, in most engines it still isn't purely compositor-only the way `transform` is, because the browser still needs to know the new box position for hit-testing, scroll anchoring, and other bookkeeping. The unambiguous cheap path is `transform`/`opacity` on an already-promoted layer; treat everything else as "probably triggers layout or at least paint" unless you've verified otherwise in a trace.

### Forced synchronous layout ("layout thrashing")

Layout is normally lazy: the browser batches DOM writes and only actually runs layout once, right before it needs to paint the frame. But reading certain properties — `offsetWidth`, `offsetHeight`, `getBoundingClientRect()`, `getComputedStyle()`, `scrollTop`, and others — forces the browser to synchronously flush any pending layout-invalidating writes *right then*, because the answer would be wrong otherwise. The classic bug is:

```js
// untested sketch — deliberately pathological, illustrates the failure
for (const el of elements) {
  el.style.width = el.offsetWidth + 10 + "px"; // WRITE then READ, every iteration
}
```

Every loop iteration writes a style (invalidating layout) then immediately reads `offsetWidth` (forcing layout to run *right now* to answer the read) — turning what should be one layout pass per frame into N synchronous layout passes, one per element, all on the main thread, all blocking. This is directly observable in a DevTools Performance trace as a sawtooth of purple "Layout" bars, often flagged explicitly as "Forced reflow" with a warning icon. The fix (the pattern popularized by the FastDOM library, though the technique predates any specific library) is to batch all reads before all writes:

```js
// untested sketch — batched reads, then batched writes
const widths = elements.map(el => el.offsetWidth); // all reads first
elements.forEach((el, i) => { el.style.width = widths[i] + 10 + "px"; }); // then all writes
```

Now layout is invalidated once by the write batch and only computed once, lazily, before the next paint — not N times synchronously in the loop.

### The 16.7ms budget

For 60fps, the browser has **16.7ms per frame** (1000ms / 60) to run any JS callbacks, style recalculation, layout, and paint before compositing and presenting the frame — miss it and a frame is dropped, which is what "jank" looks like to a user. High-refresh-rate displays (90Hz, 120Hz) shrink this further: **11.1ms at 90Hz, 8.3ms at 120Hz**. This budget is why `requestAnimationFrame` (schedules a callback right before the next paint, synced to the display's refresh) is correct for visual updates and `setTimeout(fn, 16)` is not — `setTimeout` has no relationship to the actual paint cycle and will drift, double-fire within a frame, or run at the wrong time relative to layout/paint.

---

## Build it from scratch

A full layout engine is out of scope for an interview answer, but a minimal box-model layout simulator proves the geometry-propagation model is actually understood, not just diagrammed:

```python
# untested sketch — simplified block layout, vertical stacking only,
# no floats/inline/flex — proves the "geometry propagates downstream" model
from dataclasses import dataclass, field

@dataclass
class Box:
    width: int = 0
    height: int = 0
    padding: int = 0
    children: list = field(default_factory=list)
    x: int = 0
    y: int = 0

def layout(box: Box, available_width: int, cursor_y: int = 0) -> int:
    """Returns the total height consumed. Mutates box.x/y in place —
    this is literally what a browser's layout pass does: walk the tree,
    assign geometry, and a change to one node's height shifts every
    sibling/ancestor that comes after it."""
    box.x = 0
    box.y = cursor_y
    box.width = available_width
    inner_width = available_width - 2 * box.padding
    child_y = cursor_y + box.padding

    for child in box.children:
        consumed = layout(child, inner_width, child_y)
        child_y += consumed

    content_height = child_y - (cursor_y + box.padding)
    box.height = content_height + 2 * box.padding if box.children else box.height
    return box.height + 0  # blocks stack vertically, no margin collapsing modeled

root = Box(padding=10, children=[
    Box(height=50, padding=5),
    Box(height=30, padding=5, children=[Box(height=20, padding=2)]),
])
layout(root, available_width=300)
print(root.height)                 # 10 + 50 + 30 + 10 = 100 (root padding*2 + children)
print(root.children[1].y)          # shifts if children[0].height changes — this IS reflow
root.children[0].height = 200      # simulate a geometry change to the first child
layout(root, available_width=300)
print(root.children[1].y)          # moved — demonstrates why layout is a subtree-wide op
```

The point of writing this out: changing `root.children[0].height` and re-running `layout()` moves every node after it — that single fact, mechanically demonstrated, is the entire reason a layout-triggering property change on an early DOM node can be more expensive than the same change on a leaf node with no siblings after it.

---

## How it's done in production

Chrome DevTools' **Performance panel** is the actual tool: record a trace, and the flame chart shows color-coded bars — purple for Layout/Recalculate Style, green for Paint/Composite, yellow for Scripting — stacked per frame. A healthy 60fps animation shows a thin, repeating pattern of mostly compositor (green, short) work; a janky one shows purple bars eating most of the 16.7ms budget, often with an explicit "Forced reflow" or "Layout Shift" warning annotation. **Paint flashing** (DevTools Rendering tab → "Paint flashing") highlights repainted regions in green in real time — turning it on while scrolling or interacting instantly shows whether you're repainting far more of the page than the actual visual change warrants (a common bug: a `box-shadow` or `border-radius` on a large container that gets repainted on every keystroke of an unrelated sibling input, because it shares a paint-invalidating ancestor). **Layer visualization** (Rendering tab → "Layer borders", or the dedicated Layers panel) shows which elements got their own GPU-backed compositing layer and why — each layer listed with its reason (`will-change`, `transform`, video element, etc.) and its memory footprint.

| Symptom | Cause | Fix |
|---|---|---|
| Scroll/drag jank, purple "Layout" bars filling every frame in the trace | Animating a geometry property (`top`, `width`, `margin`) instead of `transform` | Switch to `transform: translate()`/`scale()`; promote the element to a layer first if it isn't already |
| DevTools flags "Forced reflow" / "Layout thrashing" warning | Interleaved DOM writes and geometry reads (`offsetWidth`/`getBoundingClientRect`) in a loop | Batch all reads before all writes (FastDOM pattern); or use `ResizeObserver`/`IntersectionObserver` instead of manual polling |
| Smooth on desktop, stutters badly on mid-range Android | Too many GPU-backed layers (`will-change` applied broadly, or many `transform`-animated elements) exhausting GPU memory/compositing budget on a weaker GPU | Remove blanket `will-change`; toggle it on only just before an animation starts and off after (`will-change: auto` when idle); reduce simultaneous animated-layer count |
| Large `box-shadow`/`border-radius`/gradient area causes visible paint lag on unrelated interactions | The element sits in a shared paint/stacking region with something that's repainting frequently, or the shadow itself is expensive to rasterize at that size | Isolate it onto its own layer (`will-change: transform` or `contain: paint`) so its rasterization isn't re-triggered by unrelated sibling repaints |
| First Contentful Paint is slow despite a small, fast-arriving HTML payload | A render-blocking stylesheet (or a synchronous blocking `<script>` in `<head>`) is delaying CSSOM/DOM completion before any paint can happen | Inline critical above-the-fold CSS, defer non-critical CSS, mark scripts `defer`/`async` |

---

## Tradeoffs & when NOT to use it

- **Don't reach for `will-change` as a blanket "make it fast" incantation.** Every promoted layer costs GPU memory (roughly width × height × 4 bytes for its texture) and compositing overhead; applying it to dozens of elements or leaving it on indefinitely rather than toggling it around the actual animation is a documented cause of *worse* performance on memory-constrained devices, not better — this is exactly the kind of thing that reads as junior-level cargo-culting in an interview if stated without the caveat.
- **Don't assume `transform`/`opacity`-only animation is always achievable.** Some real interactions genuinely need to affect layout — reflowing text around a resizing element, a layout that must respond to another element's actual size, drag-to-reorder lists where siblings need to physically make room. In these cases the honest answer is "this needs layout, so the goal shifts to minimizing the *size* of the subtree that re-layouts," not pretending everything can be composited.
- **Don't over-invest in micro-optimizing paint/layout on a page whose actual bottleneck is JavaScript execution or network.** The Performance panel is the tiebreaker: if the flame chart shows scripting (yellow) dominating, not layout/paint, chasing `will-change` and layer promotion is solving the wrong problem — profile first, don't guess.
- **`contain` (CSS containment: `contain: layout`/`paint`/`content`) is a real tool for scoping invalidation but changes behavior**, not just performance — it can affect how `position: absolute` descendants resolve their containing block and how overflow is clipped; treat it as a layout-semantics decision, not a free performance toggle.

---

## Interview questions

### Q1 — Walk me through what happens between a browser receiving HTML/CSS and pixels appearing on screen.
**Testing:** whether the five stages are known in order, and named correctly (not just "it renders the page").
**Answer:** Parse HTML into the DOM and CSS into the CSSOM (both incremental/streaming, but CSS is render-blocking). Combine into the render tree — DOM nodes that are actually visible, each with computed style. Layout computes geometry (x/y/width/height) for every box. Paint rasterizes pixel content per layer. Composite (on a separate compositor thread) assembles layers into the final frame, applying transform/opacity as cheap GPU operations on already-rasterized textures.
**Follow-up trap:** *"Is layout re-run for the whole page every time, or just what changed?"* — only the affected subtree is re-computed, but "affected subtree" can propagate widely (a height change on an early sibling shifts everything after it and potentially its ancestor's size), which is exactly why layout cost isn't a fixed per-change constant.

### Q2 — Why is animating `transform` cheaper than animating `top`/`left`?
**Testing:** the actual mechanism, not the memorized rule.
**Answer:** `top`/`left` are geometry properties — changing them invalidates layout, which must re-run on the main thread, followed by paint, followed by composite, all before the frame can be presented, and all contending with any other main-thread work (JS, style recalc) for the 16.7ms frame budget. `transform` on an element already promoted to its own GPU-backed compositing layer skips layout and paint entirely — the compositor thread just re-applies a matrix transform to the existing rasterized texture, which runs independently of the main thread.
**Follow-up trap:** *"Is `transform` always compositor-only, with zero exceptions?"* — only if the element already has (or gets) its own layer; an unpromoted element animated via `transform` may still trigger a layer-creation/paint cost on the first frame, and some `transform` changes (ones that affect layout-adjacent behavior in specific edge cases) aren't purely compositor-only in every engine — verify with a trace rather than asserting it unconditionally.

### Q3 — What's the difference between `display: none` and `visibility: hidden` for layout/paint cost?
**Answer:** `display: none` removes the element from the render tree entirely — no layout, no paint, zero cost, and it doesn't occupy space. `visibility: hidden` keeps the element in the render tree and fully laid out (it occupies space, affects siblings' positions) but skips painting it — so toggling `visibility` is cheaper than toggling `display` if you need to preserve layout stability (no reflow of surrounding content) but still want to hide the pixels.
**Follow-up trap:** *"Which one should you use for a frequently-toggled element to minimize cost?"* — depends on whether layout stability matters: if the surrounding layout must not shift, `visibility: hidden` (or `opacity: 0` if it also needs to stay interactive-avoidant/non-interactive via other means) avoids a reflow; but repeatedly toggling `display: none` on/off forces a full layout+paint cycle each time, which is the actual expensive case worth naming.

### Q4 — What's "layout thrashing" / forced synchronous layout, and how do you fix it?
**Answer:** Reading a geometry property (`offsetWidth`, `getBoundingClientRect()`, `getComputedStyle()`) right after writing a style forces the browser to synchronously flush pending layout invalidations to answer the read correctly, instead of batching layout lazily before the next paint. Doing this in a loop (write, read, write, read...) turns one layout pass into N synchronous passes. Fix: batch all reads before all writes — read every needed geometry value first, then perform all DOM writes afterward.
**Follow-up trap:** *"Name two more properties that force this besides `offsetWidth`."* — `scrollTop`/`scrollLeft`, `getComputedStyle()`, `getBoundingClientRect()`, `clientWidth`/`clientHeight`, `focus()` in some cases — the general rule is anything that needs an up-to-date geometric/computed answer forces the flush; candidates who only know `offsetWidth` haven't actually hit this in production.

### Q5 — Your DevTools Performance trace for a scroll interaction shows big purple bars every frame. What's your hypothesis and how do you confirm it?
**Answer:** Purple is Layout/Recalculate Style — hypothesis is something in the scroll handler (or a CSS effect triggered by scroll, e.g. a parallax effect using `top`) is triggering layout on every frame. Confirm by clicking into one of the purple bars in the flame chart, which shows the call stack that triggered it — if it points at a scroll listener setting a geometry-affecting style, that's the culprit; also check DevTools Rendering → "Layout Shift Regions" and paint flashing to see the affected area visually.
**Follow-up trap:** *"What if it's not your own code — what if it's a `box-shadow` in an unrelated part of the DOM?"* — paint and layout invalidation can cascade beyond obvious causes via stacking/shared paint regions or `contain` boundaries not being set; isolating the actual trigger sometimes requires bisecting by temporarily removing suspect elements/styles and re-profiling, not just trusting the first plausible call stack.

### Q6 — What does `will-change` do, and why shouldn't you apply it to everything "just in case"?
**Answer:** `will-change: transform` (or `opacity`, etc.) is a hint that tells the browser to promote the element to its own GPU-backed compositing layer in advance, so the first animation frame doesn't pay a layer-creation cost mid-animation. The cost: every promoted layer consumes GPU memory (roughly width × height × 4 bytes for its raster texture) and adds compositing overhead — applying it broadly or leaving it on indefinitely causes "layer explosion," which measurably degrades performance on memory/GPU-constrained devices (mid-range mobile) rather than improving it.
**Follow-up trap:** *"So when exactly should you apply and remove it?"* — apply it shortly before the animation starts (e.g., on `:hover`/`:focus` intent, or programmatically right before triggering the animation) and remove it (`will-change: auto`) once the animation finishes — treat it as a temporary hint tied to an actual imminent animation, not a permanent property.

### Q7 — Why does a render-blocking stylesheet delay First Contentful Paint even if the HTML arrives instantly?
**Answer:** The browser cannot safely paint anything until the CSSOM is complete, because any rule anywhere in an unparsed stylesheet could apply to already-parsed DOM nodes — painting before the full CSSOM would risk showing unstyled or incorrectly styled content and then having to redo it (a flash of unstyled content). So a slow stylesheet in `<head>` blocks paint even though DOM construction itself already finished.
**Follow-up trap:** *"How do you fix it without just removing CSS?"* — inline critical above-the-fold CSS directly in `<head>` (avoids a network round trip for the CSS that actually gates the first paint), and load the rest non-render-blocking (e.g., `<link rel="preload">` + swap, or `media` attribute tricks, or simply defer non-critical stylesheets) — this is standard critical-CSS extraction, covered in depth in the web performance module.

### Q8 — Explain why an unmarked `<script src="...">` in the document body blocks HTML parsing, and what `defer` and `async` each change about that.
**Answer:** A plain synchronous script can call `document.write()` or otherwise mutate the DOM being parsed, so the browser must halt HTML parsing, fetch and execute the script, then resume — this is a real, historically load-bearing correctness requirement, not an accidental slowdown. `defer` downloads the script in parallel with parsing but delays execution until parsing completes, in document order relative to other deferred scripts. `async` downloads in parallel and executes as soon as it's ready, with no ordering guarantee relative to other scripts or parsing state.
**Follow-up trap:** *"Which one would you use for an analytics script, and which for a script that manipulates the DOM the page needs at load?"* — `async` for analytics (order/timing relative to page content doesn't matter, and you want it off the critical path immediately); `defer` for anything that needs the DOM to exist and needs predictable ordering relative to other scripts — conflating the two is a common but consequential mistake (an `async` script that assumes DOM elements exist can run before they're parsed).

### Q9 — What is a compositing layer, and name three things that cause an element to get its own layer.
**Answer:** A compositing layer is a separately rasterized texture that the compositor thread can transform/blend independently without re-invoking layout or paint on the main thread. Triggers: `will-change: transform` (or other compositor-eligible properties), 3D transforms (`transform: translateZ(0)` or any `transform3d`), `<video>`/`<canvas>` elements, elements with `opacity` animations already in flight, and certain `position: fixed` cases relative to scrolling containers (engine-specific specifics vary).
**Follow-up trap:** *"Is more layers always better?"* — no — this loops back to the `will-change` overuse problem: each layer has a real memory cost (texture size × 4 bytes/pixel) and excessive layer count degrades compositing performance, especially on GPU-constrained devices; the goal is exactly as many layers as needed for the actual animations, not maximum layering.

### Q10 — At 120Hz, what's your frame budget, and why does that matter for `requestAnimationFrame` vs `setTimeout`?
**Answer:** 1000ms / 120 = 8.3ms per frame, versus 16.7ms at 60Hz — meaning any per-frame JS/layout/paint work has roughly half the time it used to have to avoid dropping a frame on a high-refresh display. `requestAnimationFrame` schedules its callback synchronized to the actual next paint, whatever the display's real refresh rate is, so it naturally adapts; `setTimeout` has no relationship to the paint cycle at all, and a hardcoded `setTimeout(fn, 16)` assumes 60Hz and will visibly under- or over-fire relative to a 120Hz or 90Hz display's actual cadence.
**Follow-up trap:** *"Does `requestAnimationFrame` guarantee your callback finishes before the frame's deadline?"* — no — it schedules the callback to *start* before the next paint, but if the callback itself takes too long (heavy computation, forced synchronous layout inside it), it can blow through the frame budget and still cause a dropped frame; `rAF` solves scheduling/timing alignment, not execution-time correctness.

### Q11 — A drag-to-reorder list needs siblings to visibly make room for the dragged item as it moves. Can this be done compositor-only?
**Testing:** staff-level judgment — recognizing when the "always use transform" rule doesn't fully apply.
**Answer:** Not purely — the siblings genuinely need to change position/size in response to the drag, which is a layout-affecting change by definition (their actual flow position is changing, not just their painted appearance). The realistic approach is a hybrid: use `transform` to move the *dragged* element itself (compositor-only, follows the pointer at 60fps+ with no layout cost), while animating the *siblings'* position shift with `transform` too (translate them to their new slot visually) and only commit the real DOM/layout reorder at drag-end — this is exactly the technique behind libraries like dnd-kit and Framer Motion's layout animations (FLIP: First-Last-Invert-Play).
**Follow-up trap:** *"What's FLIP, concretely?"* — measure the First position, let layout happen to compute the Last position, compute the Invert transform that visually snaps the element back to where it started, then Play an animation removing that transform — net effect: the actual layout change happens instantly/synchronously (once, not per-frame), and the *animation* the user sees is a pure `transform` interpolation, getting compositor-cheap animation for something that is genuinely a layout change.

### Q12 — Why can `box-shadow` on a large, frequently-repainted area be a measurable performance problem, and what's the fix?
**Answer:** Rasterizing a shadow (computing the blur/spread across every affected pixel) is measurably more expensive than filling a flat rectangle, and if that element shares a paint-invalidation region with something that repaints often (e.g., a sibling input being typed into, if they're not isolated into separate layers), the expensive shadow gets re-rasterized far more often than its own visual state actually changes.
**Follow-up trap:** *"How do you isolate it without introducing a `will-change` memory cost you don't need?"* — `contain: paint` (or `contain: content`) scopes paint invalidation to the element's own subtree without necessarily promoting a full GPU layer the way `will-change: transform` does, which is a lighter-weight tool for this specific "stop unrelated repaints from touching me" problem — knowing this distinction from `will-change` is the staff-level signal.

### Q13 — What's the actual complexity/cost model for layout — is it O(1) per change, O(n) in DOM size, or something else?
**Answer:** There's no fixed universal constant — it depends on how far the geometry change propagates. A leaf node with `position: absolute` and no layout-dependent siblings can be nearly free to re-layout. A change to an early flow-participating element's height can force re-layout of every subsequent sibling and potentially its parent (if the parent's size depends on content), which is proportional to the size of the affected subtree, not the whole document, but "affected subtree" is doing a lot of work in that sentence and can be surprisingly large in a deeply nested, content-sized layout.
**Follow-up trap:** *"Does `contain: layout` change this?"* — yes, meaningfully: `contain: layout` tells the browser the element's internal layout doesn't affect anything outside its own box (and vice versa), letting the engine scope layout invalidation to just that subtree with a real guarantee rather than a heuristic — a legitimate, staff-level performance lever for large lists/grids of independently-changing items.

---

## Red flags that fail you

- Saying "use `transform` for animations" without being able to explain *why* it's cheap (the layer/compositor-thread mechanism).
- Not knowing the difference between `display: none` and `visibility: hidden` in terms of layout/paint cost.
- Recommending `will-change` broadly/permanently as a general performance fix, with no mention of its memory cost or the layer-explosion failure mode.
- Confusing "reflow" and "repaint" — using them interchangeably when asked to distinguish which properties trigger which.
- Not recognizing forced synchronous layout (interleaved geometry reads/writes) as a real, nameable bug pattern.
- Claiming everything can always be animated compositor-only, with no acknowledgment that genuine layout-affecting interactions (reordering, resizing that affects siblings) exist and need a different strategy (e.g., FLIP).

---

## Cheat card

```
PIPELINE: Parse(HTML->DOM, CSS->CSSOM) -> Render Tree -> LAYOUT -> PAINT -> COMPOSITE
  CSS is render-blocking (any rule could affect any parsed node)
  unmarked <script> blocks HTML parsing; defer=after parse+ordered, async=whenever+unordered

COST BY PROPERTY CLASS:
  geometry (width/top/left/margin/font-size) -> LAYOUT (+paint+composite) = expensive
  visual non-geometric (color/background/box-shadow) -> PAINT (+composite) = medium
  transform/opacity on a promoted layer -> COMPOSITE only = cheap, off main thread

display:none = removed from render tree, zero cost, no space
visibility:hidden = still laid out/occupies space, just not painted

FORCED SYNC LAYOUT ("layout thrashing"): write style then read offsetWidth/
  getBoundingClientRect/scrollTop/getComputedStyle in a loop -> N sync layouts
  FIX: batch all reads before all writes (FastDOM pattern)

FRAME BUDGET: 16.7ms @60Hz, 11.1ms @90Hz, 8.3ms @120Hz
  requestAnimationFrame = synced to actual next paint; setTimeout = not synced, drifts

will-change: promotes to GPU layer early. COST: ~width*height*4 bytes texture/layer.
  Apply right before animation, remove after (will-change:auto) — NOT a blanket default.
  Overuse -> "layer explosion" -> worse perf on GPU-constrained (mobile) devices.

FLIP (First-Last-Invert-Play): for layout-affecting animations (drag-reorder) —
  commit real layout change once, animate the VISUAL delta via transform only.

contain: layout/paint scopes invalidation to subtree — real perf lever for
  large lists of independently-changing items, distinct from will-change.
```

## Sources

- [Rendering performance — web.dev](https://web.dev/articles/rendering-performance) — accessed 2026-08-02
- [Populating the page: how browsers work — MDN](https://developer.mozilla.org/en-US/docs/Web/Performance/Guides/How_browsers_work) — accessed 2026-08-02
- [CSS Triggers reference (layout/paint/composite property mapping)](https://csstriggers.com) — accessed 2026-08-02
- [will-change — MDN](https://developer.mozilla.org/en-US/docs/Web/CSS/will-change) — accessed 2026-08-02
- [Avoid large, complex layouts and layout thrashing — web.dev](https://web.dev/articles/avoid-large-complex-layouts-and-layout-thrashing) — accessed 2026-08-02
- [Scroll-driven animations — Chrome for Developers](https://developer.chrome.com/docs/css-ui/scroll-driven-animations) — accessed 2026-08-02

## Changelog
- 2026-08-02 — created
