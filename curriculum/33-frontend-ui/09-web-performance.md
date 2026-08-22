# Core Web Vitals, Bundle Budgets, Code Splitting, Images, and Measuring Before Optimising

> **Track:** T33 Frontend & UI Engineering · **Time:** 3h · **Prereqs:** T33-browser-rendering
> **Module id:** `T33-web-performance` · **Tags:** performance, critical

## The 30-second version

Core Web Vitals are three measurable proxies for perceived speed: LCP (largest contentful paint, target under 2.5s) measures loading, INP (interaction to next paint, target under 200ms, replaced FID in March 2024) measures responsiveness across the page's entire lifetime rather than just the first click, and CLS (cumulative layout shift, target under 0.1) measures visual stability — all three graded at the 75th percentile of real users over a rolling 28-day window via Chrome's CrUX dataset, not a single Lighthouse run. LCP is almost always dominated by one of four things: slow server response (TTFB), render-blocking CSS/JS, resource load time (usually the LCP image itself, often not discovered until late because it's buried in a JS-rendered tree), or client-side rendering delay; fixing it starts with identifying which of those four is actually the bottleneck for your specific page, not applying a generic checklist. INP is dominated by long tasks blocking the main thread during user interaction — anything over 50ms is a "long task," and the fix is almost always breaking up JavaScript execution (yielding to the main thread, deferring non-critical work) rather than "just use a faster framework." CLS is caused by content shifting after initial render — images/ads/embeds without reserved dimensions, web fonts swapping in with different metrics, or content injected above existing content. The one discipline that separates senior engineers from junior ones here: measure with real user data (RUM) or at minimum a representative Lighthouse/WebPageTest run before changing anything, because intuition about what's slow is wrong more often than it's right, and "I optimized X" without a before/after number is not a completed task.

## Why this gets asked

Because performance work is where frontend engineering meets business metrics directly, and the interviewer has almost certainly watched a team ship a "performance improvement" that didn't move the number that mattered, or worse, made it worse, because nobody measured before touching code. They want to see whether you reach for a specific, ordered diagnostic process (identify the metric, identify the bottleneck for that specific page, fix that bottleneck, measure again) versus a grab-bag of tips applied without a hypothesis. They've also likely dealt with the org dynamic where "make it faster" is a vague mandate from leadership after a Core Web Vitals field-data drop in Search Console, and the real skill being tested is turning that vague mandate into a specific, prioritized, measurable engineering plan — which image is the LCP element, which script is blocking the main thread during the interaction users actually do, which layout shift is real and which is Lighthouse lab noise.

---

## Lineage: past → present → future

**What came before.** Performance measurement in the 2000s-early 2010s was almost entirely synthetic and single-metric: page load time (the `onload` event), sometimes broken into waterfall charts via tools like YSlow and early PageSpeed Insights. The pain this caused was well understood but hard to fix systemically: `onload` fires when every resource has loaded, including things the user never sees or waits on (a hidden analytics beacon, a footer image below the fold), so a page could have a terrible `onload` time while feeling fast to a real user, or a great `onload` time while the actual perceived-critical content loaded last. There was no standardized way to measure "did this feel fast to a human," which meant teams optimized numbers that didn't correlate with user-perceived experience or business outcomes, and different teams invented ad hoc proxies (time to first paint, custom "hero element visible" markers) with no cross-site comparability.

**Where it stands now.** Google's Web Vitals initiative (introduced 2020, with INP replacing FID in March 2024) standardized three metrics specifically chosen to map to what users actually perceive — loading, interactivity, visual stability — and made them measurable both in the lab (Lighthouse, synthetic) and in the field (CrUX, real Chrome user telemetry, the metric that actually feeds Google Search ranking signals). The live disagreement isn't really about the metrics themselves anymore — there's broad practitioner consensus they're reasonable proxies — it's about measurement methodology: lab scores (consistent, reproducible, but on a fixed simulated device/network profile) versus field data (reflects real diverse users, but noisy and slow to see changes reflected, since CrUX uses a 28-day rolling window). A team that only watches Lighthouse scores in CI can ship a regression that field users actually experience but that CI never caught, because the CI run's device/network profile doesn't match the long tail of real user hardware. A separate live disagreement: how much weight synthetic performance budgets in CI should carry versus RUM-driven alerting, given that budgets catch regressions before ship but RUM is what actually reflects the metric Google grades.

**Where it's heading.** INP is a relatively young metric (2024) and its interaction with increasingly interactive, JS-heavy interfaces (rich text editors, canvas-based UIs, streaming AI chat interfaces like the previous module) is still being worked out in practice — expect continued tooling investment in long-task attribution (which specific script, which specific React component, caused a given slow interaction) since that's currently the hardest part to debug precisely. Speculative but plausible: as more UI ships as React Server Components and streaming SSR (see the react-advanced module), the loading-metric story shifts from "one big client bundle" toward "server compute time plus incremental hydration," which changes what "slow load" even means and is likely to eventually warrant new or adjusted metrics from the Web Vitals initiative, though nothing concrete has shipped to replace LCP as of 2026.

---

## Mental model

Think of a page load as four sequential budgets, each gating the next, with the interaction budget running continuously afterward:

```
[Network: TTFB]  ->  [Parse + render-blocking resources]  ->  [LCP element loads + paints]  ->  [Hydration/interactive]
     server            CSS/JS blocking <head>                     often the bottleneck              INP starts mattering
     time                                                          nobody profiles                    from here onward

INP is not a single moment — it's the WORST interaction (98th percentile) across the entire page
lifetime, so a page that's fast to load but janky on the 40th click still fails INP.
```

The critical insight most people miss: LCP is a loading metric that happens once, near the start; INP is a responsiveness metric that's evaluated continuously for as long as the user stays on the page, and it specifically reports something close to the worst interaction they experienced, not the average — so a page can look fine in a 10-second manual test and still fail INP in the field because the failure only shows up on the 47th interaction, after some accumulated state (a memory leak, a growing list re-rendering) has degraded main-thread responsiveness.

---

## How it actually works

### LCP: finding the actual element and its actual bottleneck

The LCP element is whichever content element (image, video poster, block-level text) has the largest rendered area within the viewport at the point it's identified — Chrome DevTools' Performance panel and `web-vitals` JS library both report exactly which DOM node it picked, and that's the first thing to check, because "optimize LCP" without knowing the specific element is directionless. Once you know the element, the delay decomposes into four phases with real, separately measurable durations:

```javascript
import { onLCP } from 'web-vitals';

onLCP((metric) => {
  const entry = metric.entries[metric.entries.length - 1];
  console.log({
    element: entry.element,           // the actual DOM node
    renderTime: entry.renderTime,     // when it painted
    loadTime: entry.loadTime,         // when the resource finished downloading (0 for text)
    ttfb: metric.attribution?.timeToFirstByte,
    resourceLoadDelay: metric.attribution?.resourceLoadDelay,   // time between TTFB and starting the fetch
    resourceLoadTime: metric.attribution?.resourceLoadTime,      // the fetch itself
    elementRenderDelay: metric.attribution?.elementRenderDelay,  // time between load and actual paint
  });
});
```

The most common production LCP bug: the LCP image is discovered late because it's not in the initial HTML — it's rendered by client-side JS after a data fetch, so the browser's preload scanner (which parses raw HTML for `<img>`/`<link>` tags before JS even runs) never sees it and can't start downloading it early. The fix is either server-rendering the image tag directly in HTML, or adding `fetchpriority="high"` plus a `<link rel="preload">` for it — Google's own measurements found `fetchpriority="high"` alone cut LCP from 2.6s to 1.9s on a representative page. Lazy-loading the LCP image itself (a common mistake from blanket-applying `loading="lazy"` to every `<img>` on a page) is actively harmful: measured field data shows lazy-loading the actual LCP element moves p75 LCP from 364ms to 720ms and drops the share of "good" pages from 79% to 52% — `loading="lazy"` should never be applied to the above-the-fold hero image.

### INP: long tasks and the 50ms threshold

A "long task" is any main-thread JavaScript execution exceeding 50ms without yielding — during a long task the browser cannot process input, update the display, or run other scripts, so a click landing mid-long-task waits for the task to finish before anything visibly responds. INP measures the full latency of an interaction: input delay (waiting for the main thread to be free) + processing time (the event handler and any synchronous work it triggers) + presentation delay (time to actually paint the next frame). Diagnosing it means finding the specific interaction and specific script responsible, not guessing:

```javascript
import { onINP } from 'web-vitals';

onINP((metric) => {
  const entry = metric.entries[0];
  console.log({
    interactionType: entry.name,       // 'click', 'keydown', etc.
    duration: metric.value,
    target: entry.target,               // the DOM element interacted with
    // attribution reports which specific event handler / script contributed most
  });
}, { reportAllChanges: false });
```

The fix pattern, in order of how often each actually applies: (1) break up a single expensive synchronous handler into chunks that yield control back to the browser between chunks (`scheduler.yield()` where supported, or `setTimeout(fn, 0)` as a fallback) so input can be processed between chunks; (2) move genuinely heavy computation (large data transforms, non-trivial parsing) off the main thread into a Web Worker; (3) defer non-critical work that doesn't need to happen synchronously with the interaction (analytics calls, prefetching) using `requestIdleCallback` or scheduling it after the interaction's visible result has painted; (4) reduce the amount of DOM the interaction has to touch (virtualize long lists rather than re-rendering all of them on every state change).

### CLS: what actually causes it and what doesn't

CLS accumulates a score per unexpected layout shift, weighted by how much of the viewport moved and how far. The three causes that account for the overwhelming majority of real CLS regressions: images/iframes/embeds without explicit `width`/`height` (or `aspect-ratio`) reserved before the resource loads, so the browser can't allocate space up front and shifts content down when it arrives; web fonts swapping in with different metrics than the fallback font (a custom font that's noticeably wider or taller per character reflows every line it's used on); and content injected above existing content after initial render (a banner, an ad, a "we detected you're in EU, click to accept cookies" bar that pushes the page down instead of overlaying it). Fix for the first: always set `width`/`height` attributes (the browser computes aspect ratio from them even with a fluid CSS width) or `aspect-ratio` in CSS. Fix for the second: either `font-display: optional` (gives the browser roughly 100ms to load the font; if it's not ready by then, the fallback is used for the entire page view and no swap ever happens — zero CLS, at the cost of not always showing the custom font) or size-matching a fallback font via `size-adjust`/`ascent-override` font-face descriptors so the swap doesn't visibly reflow even when it happens. Fix for the third: reserve space (a fixed-height skeleton) for anything that will be injected, or push it to an overlay that doesn't affect layout.

### Bundle budgets and code splitting, with real numbers

A representative unoptimized React SPA bundle can run 2-2.5MB of JS before any splitting; route-based code splitting alone (each route's component tree loaded via `React.lazy()`/dynamic `import()` rather than bundled into one entry chunk) commonly gets the *initial* bundle down to something like 120KB critical-path plus on-demand chunks per route (a chart library at 340KB, a rich text editor at 520KB, an admin panel at 280KB) loaded only when that route is actually visited. Combined with tree shaking and switching heavy dependencies for lighter alternatives (the canonical example being `moment.js`, whose locale data alone can add hundreds of KB, replaced by `date-fns` or the native `Intl` API), a 60-80% total bundle size reduction before touching any application logic is a realistic target, not an aspirational one. Performance budgets belong in CI, not just dashboards — a build step that fails if a route's initial JS exceeds a set threshold (e.g., 170KB gzipped for the critical path) catches a regression before it ships rather than after a Search Console alert three weeks later:

```javascript
// vite.config.js — untested sketch, illustrates the mechanism
import { defineConfig } from 'vite';

export default defineConfig({
  build: {
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (id.includes('node_modules/react-dom')) return 'vendor-react';
          if (id.includes('node_modules/@tanstack')) return 'vendor-query';
        },
      },
    },
  },
});
```

CI budget enforcement typically runs a bundle analyzer against the build output and fails on threshold breach — `bundlesize`, `size-limit`, or a custom script comparing gzipped chunk sizes against a checked-in budget file; the specific tool matters less than having *any* automated gate, since the alternative is bundle size only getting attention during an occasional manual audit, by which point it's often grown 3-4x from where it started.

### Image strategy, concretely

Images are roughly 45-55% of average page weight (2.5-3MB desktop, ~2MB mobile per HTTP Archive data) and the LCP element on the large majority of pages (~85% of desktop pages), which makes image strategy disproportionately high-leverage for LCP specifically. Format: AVIF is roughly 50% smaller than JPEG at comparable perceived quality and has ~95% global browser support as of early 2026; WebP is 25-35% smaller than JPEG with slightly broader (~96%) support — serve AVIF with WebP and JPEG fallbacks via `<picture>`, not a single format assumption:

```html
<picture>
  <source srcset="hero-800.avif 800w, hero-1600.avif 1600w" type="image/avif">
  <source srcset="hero-800.webp 800w, hero-1600.webp 1600w" type="image/webp">
  <img src="hero-800.jpg" srcset="hero-800.jpg 800w, hero-1600.jpg 1600w"
       sizes="(max-width: 600px) 100vw, 800px"
       width="800" height="450" fetchpriority="high" alt="...">
</picture>
```

`fetchpriority="high"` on the LCP image tells the browser to prioritize it over other discovered resources of similar type; `width`/`height` reserve layout space and prevent CLS; `srcset`/`sizes` let the browser pick an appropriately sized variant instead of downloading a 1600px-wide image to display at 400px on mobile. Everything below the fold should get `loading="lazy"` — the inverse mistake of applying it to the LCP image, but equally real: not lazy-loading offscreen images wastes bandwidth and can itself delay the LCP resource by competing for connection slots.

### Font loading, concretely

`font-display: swap` is used by roughly half of sites and shows fallback text immediately (good for a text-based LCP), but creates a real CLS risk when the custom font's metrics differ enough from the fallback to reflow text on swap. `font-display: optional` avoids that entirely — the browser gives the font roughly 100ms to arrive (typically satisfied by a preload or a warm cache) and if it doesn't make it in time, the fallback is used for that entire page view with no later swap, trading "sometimes shows the fallback font" for "zero font-driven CLS." For teams that need the custom font to always eventually appear, size-matching the fallback (`size-adjust`, `ascent-override`, `descent-override` font-face descriptors, computed from the difference between the custom font's and the fallback's metrics) keeps `swap`'s guarantee of eventually showing the real font while eliminating the visible reflow.

```html
<link rel="preload" href="/fonts/inter-var.woff2" as="font" type="font/woff2" crossorigin>
```

```css
@font-face {
  font-family: "Inter";
  src: url("/fonts/inter-var.woff2") format("woff2");
  font-display: optional; /* or swap + size-adjust tuning */
}
```

---

## Build it from scratch

A minimal but real performance-diagnosis exercise: instrument a page with the `web-vitals` library's `onLCP`/`onINP`/`onCLS` callbacks, log the attribution data to the console, then deliberately introduce three specific regressions one at a time (a lazy-loaded hero image, an unyielding 300ms synchronous click handler, an image without `width`/`height`) and confirm each one is visible in the corresponding metric's attribution data before fixing it. This exercise is valuable specifically because it forces measuring the effect of each regression individually rather than reasoning about performance in the abstract. Reference: `(lab pending)`.

---

## How it's done in production

Real-user monitoring (RUM) is what actually matters for the metric Google grades (CrUX field data), and lab tools (Lighthouse, WebPageTest) are what catch regressions before they reach real users — production setups run both. Common stack: `web-vitals` JS library reporting to an analytics/RUM backend (Datadog RUM, SpeedCurve, Vercel Analytics, or a custom beacon to your own metrics pipeline) for field data, plus Lighthouse CI (or a bundlesize/budget check) gating pull requests on synthetic regressions.

| Symptom | Cause | Fix |
|---|---|---|
| Lighthouse score is excellent (95+) but Search Console/CrUX field data shows "poor" LCP | Lab test runs on a fixed, often fast simulated profile (specific throttling preset), doesn't reflect the long tail of real user devices/networks (older phones, slow mobile networks in real markets) | Prioritize RUM/CrUX data as the source of truth over lab scores; if you must optimize for lab, test against representative throttling (e.g. "Slow 4G"/mid-tier mobile CPU throttling), not the default |
| LCP is fine on repeat visits but poor on first visit | LCP image/font not cached on first visit and not prioritized by the preload scanner (client-rendered, not in initial HTML) | Server-render the LCP element into initial HTML, add `fetchpriority="high"` + `<link rel="preload">` |
| INP is fine in manual testing but fails in the field on a specific page | The failing interaction only manifests after accumulated state (long session, growing list, memory pressure) that a short manual test never reaches | Use RUM attribution data (which interaction, which element) rather than trying to reproduce blind; profile with a realistic session length/data volume |
| CLS spikes specifically on slow connections, not fast ones | Web font or late-loading embed has more time to arrive *after* initial paint on a slow connection, making the swap/shift more likely to be visible (fast connections often have the font ready before first paint, masking the issue) | Test CLS specifically under throttled network conditions, not just fast dev-network conditions where the bug is invisible |
| Bundle size creeps up steadily release over release with no single obvious cause | No CI budget gate — small additions (a new dependency here, an un-tree-shaken import there) each look negligible individually | Add a bundle-size budget check to CI that fails the build on regression past a threshold, not just a periodic manual audit |

---

## Tradeoffs & when NOT to use it

- **Don't optimize a metric you haven't measured for your actual page.** Applying a generic "performance checklist" (compress images, add lazy loading, code split) without first identifying which specific Core Web Vital is failing and why wastes effort and sometimes actively regresses a metric you didn't check (blanket lazy-loading regressing LCP is the textbook example).
- **Don't chase a perfect Lighthouse score at the expense of RUM reality.** A 100/100 Lighthouse score on a synthetic run with no bearing on your real user device/network mix is a vanity number; CrUX field data at p75 is what Google actually grades and what real users actually experience.
- **Don't code-split so aggressively that you trade one problem for another.** Over-splitting into many tiny chunks increases the number of network round trips (especially costly on HTTP/1.1 or high-latency mobile connections) and can make INP worse if a route now needs to fetch-then-execute several sequential chunks synchronously on interaction; group by actual usage boundary (route, or a genuinely optional heavy feature), not by file.
- **Don't treat `font-display: optional` as a free win everywhere.** It's the right choice when brand-font consistency matters less than guaranteed zero CLS (most body text), but a brand that depends heavily on a distinctive display font for a hero section may prefer `swap` plus metric-matching over risking the custom font never appearing at all for a meaningful fraction of visits.
- **Don't treat AVIF as a strict replacement for WebP/JPEG everywhere yet.** AVIF encoding is slower and some image processing pipelines/CDNs handle it less maturely than WebP; serve it as the first `<picture>` `<source>` with fallbacks, not as the only format, until your specific asset pipeline has verified support end to end.

---

## Interview questions

### Q1 — What are the three Core Web Vitals, their "good" thresholds, and what does each actually measure?
**Testing:** baseline currency — whether the candidate knows INP replaced FID and knows real threshold numbers, not vague ones.
**Answer:** LCP (largest contentful paint) under 2.5s measures loading; INP (interaction to next paint) under 200ms measures responsiveness across the full page lifetime (replaced FID in March 2024); CLS (cumulative layout shift) under 0.1 measures visual stability. All three are graded at the 75th percentile of real users over CrUX's rolling 28-day window.
**Follow-up trap:** *"Is a 100/100 Lighthouse score the same thing as passing Core Web Vitals?"* — no; Lighthouse is a synthetic lab score on a fixed simulated profile, while the metric Google actually grades (and that appears in Search Console) is CrUX field data from real users. A page can score perfectly in Lighthouse and still fail CWV in the field for users on slower real devices/networks.

### Q2 — A page's LCP is 4.2 seconds. Walk through how you'd diagnose which of the four LCP phases is the bottleneck.
**Testing:** structured diagnosis versus generic tip-application.
**Answer:** Use the `web-vitals` library's attribution data (or DevTools' Performance panel) to break LCP into TTFB, resource load delay (time between TTFB and the resource fetch starting), resource load time (the fetch itself), and element render delay (time between load and actual paint) — each is separately measurable, and the fix depends entirely on which phase dominates: slow TTFB points at the server/CDN, a large load delay often means the resource wasn't discoverable early (client-rendered, not in initial HTML), a large load time points at resource size/compression, and a large render delay can mean render-blocking CSS/JS ahead of the element.
**Follow-up trap:** *"The LCP element is an image loaded via client-side JS after a data fetch. Why does that specifically hurt LCP even if the image itself is small and fast to download?"* — the browser's preload scanner parses raw HTML for resource hints before JS executes; an image only added to the DOM after a JS fetch completes is invisible to that early scanner, so its download doesn't even start until much later in the pipeline than a server-rendered `<img>` tag would allow, regardless of the image's own size.

### Q3 — Why is blanket-applying `loading="lazy"` to every image on a page a mistake?
**Testing:** whether a specific, measured production failure mode is known versus a rule applied without understanding its exception.
**Answer:** `loading="lazy"` on the actual LCP image delays its discovery and download until the browser determines it's near the viewport, directly hurting the metric it's supposed to help overall page performance with — measured field data shows lazy-loading the LCP element moves p75 LCP from 364ms to 720ms and drops the share of "good" pages from 79% to 52%. Lazy loading should apply to below-the-fold images only; the LCP candidate should instead get `fetchpriority="high"`.
**Follow-up trap:** *"How do you know which image is the LCP candidate before the page ships, so you know which one NOT to lazy-load?"* — it's usually deterministic from layout (the largest above-the-fold content element, commonly a hero image or headline text block) and confirmable in DevTools' Performance panel or via the `web-vitals` `onLCP` callback logging `entry.element` during development/staging testing, not guessed.

### Q4 — What is a "long task," and why does it specifically hurt INP?
**Testing:** mechanical understanding of the main-thread blocking model.
**Answer:** Any main-thread JS execution exceeding 50ms without yielding control back to the browser. During a long task, the browser can't process input or paint, so a click or keypress landing mid-task has to wait for the entire task to finish before input delay even ends, directly inflating INP's input-delay component.
**Follow-up trap:** *"Your click handler is fast (10ms) but INP is still bad on that interaction. What else could be responsible?"* — INP includes processing time AND presentation delay (time to actually paint the next frame after the handler runs), not just the handler's own execution — a fast handler that triggers an expensive synchronous re-render (large list, unmemoized expensive computation) downstream, or that's queued behind an unrelated long task already running on the main thread, still produces a bad INP even though the handler code itself is quick.

### Q5 — How would you fix a slow, JS-heavy click handler that's causing bad INP, in order of what to try first?
**Testing:** whether the candidate has an actual prioritized remediation strategy versus a single silver-bullet answer.
**Answer:** First, break the handler into chunks that yield back to the browser between them (`scheduler.yield()` or a `setTimeout(fn, 0)` fallback) so queued input gets a chance to process. Second, move genuinely heavy computation off the main thread into a Web Worker. Third, defer non-critical work that doesn't need to complete synchronously with the visible result (analytics, prefetching) via `requestIdleCallback` or after-paint scheduling. Fourth, reduce the actual DOM work (virtualize long lists instead of re-rendering everything).
**Follow-up trap:** *"Would you always start with a Web Worker since it's the 'correct' fix?"* — no; a Web Worker adds real complexity (serialization overhead for data crossing the boundary, no DOM access) and is worth it specifically when the work is CPU-heavy and self-contained; for a handler whose cost is mostly triggering a large synchronous render rather than raw computation, yielding/chunking or reducing render scope is usually cheaper and more directly targeted at the actual bottleneck.

### Q6 — Name the three most common real causes of CLS and the specific fix for each.
**Testing:** concrete, production-grounded knowledge rather than a vague "layout shifts are bad" answer.
**Answer:** (1) Images/embeds without reserved dimensions — fix with explicit `width`/`height` attributes or CSS `aspect-ratio`. (2) Web fonts swapping in with different metrics than the fallback, reflowing text — fix with `font-display: optional` (zero CLS, sometimes no custom font) or metric-matching via `size-adjust`/`ascent-override` font-face descriptors (keeps `swap`'s guarantee, eliminates the visible reflow). (3) Content injected above existing content post-render (banners, cookie notices, late ads) — fix by reserving space up front or using an overlay that doesn't affect layout flow.
**Follow-up trap:** *"Why might CLS look fine in your local dev testing but spike specifically for users on slow connections?"* — on a fast connection the web font or late resource often arrives before first paint, masking the shift entirely; on a slow connection there's more time between initial paint and the resource arriving, making the swap/shift visible and counted. CLS should specifically be tested under throttled network conditions, not just a fast dev environment.

### Q7 — A React SPA ships a 2.3MB initial bundle. Walk through a prioritized plan to reduce it, with realistic expected impact.
**Testing:** whether the candidate can sequence a real optimization plan with plausible numbers rather than list unordered tips.
**Answer:** First, route-based code splitting via `React.lazy()`/dynamic imports so only the current route's code is in the initial bundle — this alone commonly gets the initial critical-path bundle to roughly 100-150KB with the rest loaded on demand per route. Second, tree shaking plus auditing large dependencies for lighter alternatives (the canonical example: replacing `moment.js`, whose locale data adds hundreds of KB, with `date-fns` or `Intl`). Combined, a 60-80% total reduction before touching application logic is realistic, not aspirational. Third, add a CI bundle-size budget so the gain doesn't silently erode over subsequent releases.
**Follow-up trap:** *"Is more code splitting always better?"* — no; splitting too granularly increases network round trips (costly on high-latency connections) and can hurt INP if an interaction now has to fetch-then-execute multiple sequential chunks synchronously. Split along real usage boundaries (route, or a genuinely optional heavy feature), not by arbitrary file count.

### Q8 — Your team ships a performance fix and Lighthouse CI shows a clear improvement, but the CrUX field data three weeks later shows no change. What happened?
**Testing:** staff-level: understanding the gap between synthetic and field measurement, including the reporting lag.
**Answer:** Several possibilities worth checking in order: CrUX uses a rolling 28-day window, so a fix needs real user traffic to accumulate before the reported number moves — three weeks may simply not be enough data yet depending on traffic volume. Separately, Lighthouse runs on a fixed simulated device/network profile that may not represent your actual traffic mix (if your real users skew toward older devices or slower networks than Lighthouse's default throttling profile, a lab win doesn't necessarily translate). It's also possible the fix targeted a page or interaction that isn't actually where the field-measured regression is concentrated.
**Follow-up trap:** *"How would you get faster feedback than waiting on CrUX's 28-day window?"* — instrument your own RUM (the `web-vitals` library reporting to your own analytics backend) which gives you near-real-time field data at whatever percentile/breakdown you choose, rather than waiting on Google's aggregated, delayed, less granular CrUX report.

### Q9 — Explain the difference between `font-display: swap` and `font-display: optional`, and when you'd choose each.
**Testing:** whether the candidate understands the CLS/LCP/brand-consistency tradeoff rather than reciting definitions.
**Answer:** `swap` shows the fallback font immediately and swaps in the custom font whenever it arrives, which is good for LCP (text visible immediately) but risks a visible layout shift on swap if the fonts' metrics differ. `optional` gives the browser roughly 100ms to load the font (typically satisfied by a preload or warm cache); if it's not ready by then, the fallback is used for the entire page view with no later swap — zero CLS risk, at the cost of sometimes never showing the custom font for that visit. Choose `optional` when zero CLS matters more than guaranteed brand-font display (most body text); choose `swap` (ideally combined with `size-adjust` metric matching) when the custom font is important enough to guarantee eventual display.
**Follow-up trap:** *"What does size-adjust actually do, mechanically?"* — it's a font-face descriptor that scales the font's metrics (ascent, descent, advance widths) to match a specified fallback more closely, computed from the numeric difference between the custom font's and the fallback's own metrics, so that when `swap` does swap fonts, the new font occupies nearly the same space per character and line, minimizing or eliminating the visible reflow that would otherwise occur.

### Q10 — Why can two pages with identical Lighthouse scores have very different real-world INP, and how would you find the actual difference?
**Testing:** staff-level distinguishing of lab versus field limitations specifically for INP.
**Answer:** Lighthouse's lab environment runs a fixed, short interaction script (or none at all for some checks) on a simulated device profile — it doesn't capture the full diversity of real user interaction patterns, session length, or accumulated page state (memory growth, a list that's grown large through use) that field INP reflects. Two pages can have identical initial-load lab scores while one degrades badly after extended real use in a way no short lab test would surface. Find the difference using RUM attribution data — which specific interaction type, which specific element, is driving the field p75/p98 — rather than trying to blindly reproduce it from a cold lab run.
**Follow-up trap:** *"If RUM data points to a 'growing list' component as the culprit, what's the actual fix, and why doesn't just 'optimizing the render' typically solve it at scale?"* — the durable fix is virtualization (rendering only the visible subset of a long list, e.g. via `react-window`/`react-virtual`) rather than reducing individual item render cost, because at sufficient list length even a well-optimized per-item render still means O(n) DOM nodes and reconciliation work scaling with data size — virtualization changes the complexity class of the interaction rather than shaving a constant factor off it.

---

## Red flags that fail you

- Reciting Core Web Vitals thresholds without knowing INP replaced FID in March 2024, or citing FID as current.
- Treating a high Lighthouse score as equivalent to passing Core Web Vitals in the field.
- Recommending `loading="lazy"` on the LCP image without recognizing the mistake.
- Proposing a performance fix with no measurement plan — "this should be faster" instead of a before/after number.
- Not knowing that CLS is specifically caused by unreserved layout space, font swap metric mismatches, and late content injection — giving only a vague "things moving around" answer.
- Assuming more code splitting is unconditionally better with no mention of the round-trip/INP tradeoff.

---

## Cheat card

```
CORE WEB VITALS (p75, CrUX 28-day rolling window, real users — not just Lighthouse):
  LCP < 2.5s   (loading)       INP < 200ms  (responsiveness, replaced FID March 2024)
  CLS < 0.1    (visual stability)

LCP 4 PHASES: TTFB -> resource load delay -> resource load time -> element render delay
  measure each separately via web-vitals attribution before guessing the fix

LCP GOTCHA: LCP image loaded via client JS (not in initial HTML) -> preload scanner
  misses it, discovered late. Fix: SSR the <img> tag + fetchpriority="high" + preload.
  Google measured: fetchpriority="high" alone cut LCP 2.6s -> 1.9s.

LAZY-LOAD MISTAKE: loading="lazy" on the LCP image -> p75 LCP 364ms -> 720ms,
  "good" page share 79% -> 52%. Never lazy-load the LCP candidate; DO lazy-load
  everything below the fold.

LONG TASK: main-thread JS >50ms without yielding = blocks input processing & paint.
  INP fix order: (1) chunk+yield (scheduler.yield/setTimeout) (2) Web Worker for
  heavy compute (3) requestIdleCallback for non-critical work (4) virtualize long lists

CLS 3 CAUSES: (1) no width/height/aspect-ratio reserved on images/embeds
  (2) font swap metric mismatch -> font-display:optional (0 CLS) or size-adjust match
  (3) content injected above existing content post-render -> reserve space/overlay

BUNDLE: unoptimized SPA ~2-2.5MB JS typical. Route-based code split -> ~100-150KB
  critical path + on-demand route chunks. + tree shaking/dep swaps (moment->date-fns)
  = 60-80% realistic total reduction. Gate regressions with a CI bundle-size budget.

IMAGES: ~45-55% of page weight, LCP element on ~85% of desktop pages.
  AVIF ~50% smaller than JPEG (~95% browser support), WebP 25-35% smaller (~96%)
  -> serve via <picture> with fallbacks, not single-format.

FONTS: font-display:swap (immediate fallback text, CLS risk on swap) vs
  font-display:optional (~100ms grace, then locked to fallback for that visit, 0 CLS)

MEASURE FIRST: lab (Lighthouse/WebPageTest, fixed simulated profile, fast feedback)
  != field (CrUX/RUM, real diverse users, what Google actually grades, 28-day lag).
  Both needed: lab in CI to gate regressions, RUM as ground truth.
```

## Sources

- [Core Web Vitals 2026: INP, LCP & CLS Optimization — DigitalApplied](https://www.digitalapplied.com/blog/core-web-vitals-2026-inp-lcp-cls-optimization-guide) — accessed 2026-08-02
- [Image Optimization for Core Web Vitals in 2026: What Actually Moves the Needle — SitePoint](https://www.sitepoint.com/image-optimization-for-core-web-vitals-in-2026-what-actually-moves-the-needle/) — accessed 2026-08-02
- [Best practices for fonts — web.dev](https://web.dev/articles/font-best-practices) — accessed 2026-08-02
- [Ensure text remains visible during webfont load — Chrome for Developers](https://developer.chrome.com/docs/lighthouse/performance/font-display) — accessed 2026-08-02
- [JavaScript Bundle Size Optimization: From 2MB to 200KB — DEV Community](https://dev.to/_d7eb1c1703182e3ce1782/javascript-bundle-size-optimization-from-2mb-to-200kb-a-practical-guide-blb) — accessed 2026-08-02
- web.dev / Chrome for Developers — `web-vitals` JS library documentation and INP attribution API — living reference docs

## Changelog
- 2026-08-02 — created
