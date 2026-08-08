# Build Tooling: Vite, esbuild/SWC, Module Resolution, Tree Shaking, Source Maps

> **Track:** T33 Frontend & UI Engineering · **Time:** 2h · **Prereqs:** T33-js-deep
> **Module id:** `T33-build-tooling` · **Tags:** tooling

## The 30-second version

Vite (currently v8.x, with Vite 8 shipping March 2026) works by splitting the problem in two: during development it serves your source code as native ES modules directly to the browser (no bundling needed, since modern browsers understand `import`/`export` natively) while pre-bundling dependencies once with a fast native tool, which is why Vite's dev server starts almost instantly regardless of app size; for production it still bundles, because unbundled ESM in production means too many network round trips and no cross-module optimization. Historically that meant esbuild (a Go-based bundler, written from scratch for speed, roughly 20-100x faster than Webpack on real benchmarks) handled dev-time transforms while Rollup handled production bundling — two different tools with two different plugin systems that had to be kept in sync; Vite's newer engine, Rolldown (a Rust bundler built by the Vite team's own company, using the Oxc parser/transformer/minifier), unifies both into one Rust-native pipeline with a Rollup-compatible plugin API, eliminating that dev/prod inconsistency entirely. Tree shaking (dead code elimination via static analysis of ES module imports/exports) is defeated by three common things: CommonJS modules (whose `require`/`module.exports` can't be statically analyzed the way ESM's static `import`/`export` can), code with unpredictable side effects the bundler can't prove are safe to remove, and — a specific, well-documented case — barrel files (an `index.js` re-exporting dozens of things from a directory) that traditionally force a bundler to parse and potentially include every re-exported module even if a consumer only imports one. Source maps translate minified/transformed production code back to original source for debugging and error reporting, at a real security tradeoff (shipping full source maps to production exposes original source structure to anyone who opens dev tools) that needs a deliberate policy, not a default. Monorepo tooling (Turborepo, Nx, pnpm/Yarn workspaces) exists specifically to make `build`/`test`/`lint` fast and correct across many interdependent packages via task-graph-aware caching (only rebuild what actually changed, in dependency order) and remote caching (share build outputs across a whole team/CI fleet, not just one machine).

## Why this gets asked

Because build tooling sits at exactly the intersection of "things that quietly get slower over 18 months until someone finally profiles them" and "things most engineers configure once from a template and never revisit." The interviewer has almost certainly either debugged a mysteriously bloated production bundle (tree shaking silently defeated by an accidental CommonJS import, or a barrel file pulling in an entire icon library for one icon) or sat through a CI pipeline that takes 25 minutes to run tests for a one-line change in an unrelated package, because the monorepo's task runner had no dependency-aware caching. They want to know if you understand build tooling as a system with real, debuggable mechanics (why does tree shaking work, specifically, and what breaks it) rather than a black box you occasionally poke config values into hoping for the best. This is also one of the areas where "I just used the framework default" is a legitimate answer only if you can also explain what the default is actually doing.

---

## Lineage: past → present → future

**What came before.** Early JS build tooling (Grunt, Gulp circa 2012-2014) was task-runner-oriented — explicit, imperative pipelines of file transformations — which worked but scaled poorly in complexity as apps grew. Webpack (2014 onward) introduced the module-bundler model that became dominant for the better part of a decade: a single dependency graph, code splitting, loaders/plugins for arbitrary transforms — genuinely powerful, but the tooling itself was written in JavaScript and became the bottleneck it was meant to manage as codebases grew, with dev server startup and rebuild times becoming a real, measured pain point (multi-second to multi-minute cold starts and rebuilds on large real-world apps were common complaints through the late 2010s). The pain this caused was specific and well-documented: because JavaScript-based bundlers are single-threaded-by-default and JIT-compiled (meaning the tool itself has no optimization advantage on its first run, right when a cold build needs it most), performance didn't scale with codebase size the way teams needed as SPAs grew from thousands to hundreds of thousands of lines.

**Where it stands now.** The current generation of build tools is built in systems languages specifically to escape that ceiling — esbuild (Go, first released 2020) demonstrated the magnitude of the gap directly: esbuild's own published benchmark (bundling three.js duplicated 10x, ~547K lines, with minification and source maps) shows esbuild finishing in 0.39s versus Rollup+Terser at 34.1s (87x slower) and Webpack 5 at 41.2s (106x slower) — not a marginal improvement, an order-of-magnitude-plus difference, achieved via native compilation, aggressive parallelism across CPU cores, and a from-scratch implementation avoiding the overhead of gluing together multiple JS libraries with different internal data representations. SWC (Rust, used as Next.js's default compiler in place of Babel) made the same bet for JS/TS transformation specifically. Vite (2020 onward) built its dev-time speed on top of this generation of native tooling while keeping Rollup for production bundling, and the live, still-actively-changing story is Vite's own migration to Rolldown — a Rust bundler unifying what used to be two separate tools (esbuild for dev, Rollup for prod) into one consistent pipeline, currently shipping as the default/stable path in recent Vite majors, specifically to eliminate the inconsistency and glue-code cost of maintaining two separate transform pipelines with different plugin systems.

**Where it's heading.** Vite's own team is explicit that the "unbundled ESM in dev" model — the thing that made Vite's initial reputation — was the right tradeoff specifically because no tool was previously both fast enough and had sufficient HMR/plugin capability to bundle during development; now that Rolldown exists, they're actively exploring a "full bundle mode" for dev servers on very large codebases, since even HTTP/2 doesn't eliminate the overhead of thousands of individual unbundled module requests at sufficient scale (a default per-connection concurrent-stream limit around 100, plus real per-request overhead, means an app with thousands of modules can still bottleneck even without HTTP/1.1's connection limits). This is a live, ongoing architectural evolution, not a settled endpoint — worth stating explicitly as still-in-motion rather than a completed transition. Separately, the Environment API (letting a single Vite instance define custom deployment targets — edge runtimes, service workers — beyond just "client" and "SSR," each with its own module resolution rules) reflects a broader, durable trend: JavaScript now runs in meaningfully more places than "browser or Node," and build tooling architecture is adapting to treat that as a first-class axis rather than a special case bolted onto a browser/Node binary split.

---

## Mental model

Think of a modern build tool as answering three separable questions, and understand that dev and production can legitimately answer them differently:

```
1. HOW DO I SERVE CODE DURING DEVELOPMENT (fast iteration)?
   Vite dev: native ESM, on-demand per-file transform, deps pre-bundled once
   -> near-instant startup regardless of app size, HMR swaps just the changed module

2. HOW DO I PRODUCE OPTIMIZED OUTPUT FOR PRODUCTION (fast for users)?
   Bundle: combine modules, tree-shake dead code, minify, split into chunks
   -> fewer requests, fewer bytes, faster parse/execute in the browser

3. HOW DO I KEEP MANY PACKAGES' BUILDS FAST AND CORRECT AS THE REPO GROWS?
   Monorepo tooling: task graph (what depends on what) + caching (skip
   unchanged work) + remote cache (share across the whole team/CI fleet)
```

The critical insight that resolves most "why does dev behave differently than prod" confusion: dev-time unbundled serving and production bundling are not the same pipeline doing the same thing faster or slower — they're two different strategies chosen because they optimize for different things (iteration speed vs. shipped-artifact efficiency), which is exactly why a bug that only appears in production (and not in `vite dev`) is a real, structurally-expected category of bug, not necessarily a tooling flaw.

---

## How it actually works

### Why esbuild/Rust-based tools are so much faster, mechanically

esbuild's own documented reasons, worth knowing precisely rather than as a vague "it's written in a faster language": native-compiled code (Go) avoids the JIT warm-up cost that hits JS-based tools every single invocation — a JS bundler's own code has to be parsed and JIT-optimized by the JS VM on every cold run, which is a fixed tax paid before any actual bundling work starts. Aggressive parallelism across CPU cores is used throughout parsing and code generation (the two most expensive phases), enabled by shared memory between threads (Go) versus JS's need to serialize data across worker thread boundaries. And a from-scratch implementation avoids the overhead of gluing together multiple third-party libraries with incompatible internal representations — esbuild touches the JavaScript AST exactly three times total (lex/parse/scope-setup, then bind/minify-syntax/transform, then minify-identifiers/generate-code/generate-source-maps), maximizing CPU cache reuse, versus older pipelines that might convert between string↔AST representations multiple times gluing separate tools together. The measured result on esbuild's own published three.js-based benchmark: esbuild 0.39s, Parcel 2 at 14.91s (38x), Rollup 4 + Terser at 34.10s (87x), Webpack 5 at 41.21s (106x) — not marginal, order-of-magnitude-plus.

### Module resolution: how `import` actually finds a file

Resolving `import { Button } from '@myapp/ui'` involves a specific, mostly-standardized algorithm: check for a matching entry in the nearest `package.json`'s `exports` field first (the modern, more precise mechanism — it can map subpaths, conditionally resolve to different files for `import` vs `require`, and explicitly restrict what's importable, unlike the older `main`/`module` fields which just point at one file each with no conditional logic); if no `exports` field exists, fall back to `main` (traditionally CJS entry) or `module` (a community convention, not officially part of Node's resolution algorithm, that bundlers use to prefer an ESM entry point over `main`'s CJS one for better tree shaking); then walk up directories checking `node_modules` at each level (Node's classic resolution algorithm) until found or exhausted. The `exports` field's conditional resolution is specifically why some packages behave differently when imported via `require()` vs `import` — the package author can ship genuinely different code (a CJS build and an ESM build) behind the same import specifier, resolved based on how the consumer is importing it.

```json
{
  "name": "@myapp/ui",
  "exports": {
    ".": {
      "import": "./dist/index.mjs",
      "require": "./dist/index.cjs"
    },
    "./button": {
      "import": "./dist/button.mjs",
      "require": "./dist/button.cjs"
    }
  }
}
```

### Tree shaking: what makes it possible, and what defeats it

Tree shaking relies on static analyzability: ES modules' `import`/`export` statements are structurally fixed at parse time (you can't conditionally `import` a different set of names based on runtime logic the way you can conditionally `require()` in CommonJS), which means a bundler can build a precise graph of "what's actually imported and used" without running any code, and prune anything unreachable from an entry point. This breaks down in three well-documented, real ways:

1. **CommonJS interop.** `module.exports = {...}` and `require()` are dynamic — the set of exported names isn't statically fixed the way ESM's is, and `require()` can be called conditionally or with a computed path. A bundler processing a CJS module generally has to treat its entire exports object as potentially used, defeating shaking for that module (and, transitively, for anything that only reaches a needed export through a CJS module in the import chain).

2. **Side effects the bundler can't prove are safe to remove.** If a module does something at import time beyond defining exports (registers a global, mutates a shared object, runs a polyfill), the bundler can't safely drop that module even if none of its named exports are used, because doing so would change program behavior. This is exactly what the `"sideEffects"` field in `package.json` is for — a package author explicitly declaring `"sideEffects": false` (or an array of specific files that do have side effects) tells the bundler "you can safely drop any file in this package whose exports aren't used, I promise none of them do anything at import time beyond exporting," which is an assertion the bundler otherwise can't verify through static analysis alone.

3. **Barrel files.** A directory's `index.js` re-exporting dozens of things (`export { Button } from './Button'; export { Card } from './Card'; ...`) is a specific, well-documented tree-shaking hazard — traditionally, bundlers had to parse (and in some pipelines, actually include) every re-exported module reachable through the barrel, even when a consumer only imports one named export from it, because determining which re-exports are "dead" requires following the whole re-export chain, which many bundler architectures historically did imprecisely or not at all before actually bundling. Newer bundlers (Rolldown specifically documents "lazy barrel optimization" as a named feature) address this directly by resolving which re-exports are actually reachable before fully processing the barrel's dependencies, rather than eagerly including everything the barrel touches.

```json
// package.json — enabling aggressive tree shaking
{
  "name": "@myapp/ui",
  "sideEffects": false
}
```

```javascript
// if a specific file DOES have a real side effect (e.g. injecting global CSS),
// it must be excluded from the blanket sideEffects:false claim
{
  "sideEffects": ["./src/global-styles.css", "./src/polyfills.js"]
}
```

Claiming `sideEffects: false` when a module actually has one is a real, silent bug source: the bundler will trust the assertion and drop code that was actually needed, producing a bundle that works in dev (where side effects might still run via a different path) but breaks in production once the "dead" module is genuinely excluded.

### Source maps: what they encode, and the production tradeoff

A source map is a JSON file mapping positions in the generated (minified/transformed) output back to positions in the original source — line/column pairs plus original file/symbol names, encoded compactly via VLQ (variable-length quantity) base64 in the `mappings` field, which is why source maps are unreadable as raw text but let dev tools reconstruct original stack traces and let you set breakpoints in original source even though the browser is executing minified code. The build-time choice of source map type is a genuine tradeoff between build speed, map accuracy, and output size — a `hidden` or `no-source-map` style option skips this cost during fast local iteration, while production builds typically generate a full external source map file. The production security tradeoff is real and often mishandled: shipping the actual `.map` file publicly alongside minified JS means anyone opening browser dev tools can reconstruct readable original source (including comments, original variable names, and structure) — the standard mitigations are uploading source maps only to an error-tracking service (Sentry, Datadog) via an authenticated upload step in CI rather than serving them publicly, or omitting the `//# sourceMappingURL` reference from the public bundle entirely while still retaining the map file privately for symbolicating error reports server-side.

### Monorepo tooling: task graphs and caching

The problem monorepo tooling (Turborepo, Nx, and the underlying package manager workspace features in pnpm/Yarn/npm) solves: in a repo with many interdependent packages, running `build`/`test`/`lint` naively means either running everything on every change (wasteful, slow) or manually tracking what changed and what depends on it (error-prone, doesn't scale past a small team). The mechanism is a declared task graph — each package's task can declare dependencies on other packages' tasks (`"build": { "dependsOn": ["^build"] }`, where `^build` means "the build task of this package's own dependencies must run first") — combined with content-addressed caching: a task's cache key is derived from the actual inputs that affect its output (source files, config, dependency versions), so an unchanged package's build/test/lint is skipped entirely and its previous output reused, both locally and (with remote caching configured) across every teammate's machine and every CI run, meaning the *first* person or CI run to build a given input hash pays the cost once and everyone else gets a cache hit.

```json
// turbo.json — untested sketch, illustrates the task graph declaration
{
  "tasks": {
    "build": { "dependsOn": ["^build"], "outputs": ["dist/**"] },
    "test": { "dependsOn": ["build"], "outputs": [] },
    "lint": { "outputs": [] }
  }
}
```

`dependsOn: ["^build"]` on the `build` task specifically encodes "build this package's dependencies first, in the correct topological order" — without this declared graph, a naive script-runner has no way to know that package B must finish building before package A (which imports from B) can build correctly, and teams either hand-order scripts (fragile, breaks silently when the dependency graph changes) or rebuild everything every time (correct but slow). Nx takes a similar task-graph-and-caching approach with additional emphasis on a plugin-driven "inferred tasks" model and a more opinionated project-graph visualization; the practical choice between Turborepo and Nx in most real teams comes down to how much opinionated structure/tooling integration a team wants versus a lighter, more manually-configured setup, not a large capability gap between them for the core caching problem.

---

## Build it from scratch

A concrete, checkable exercise: create a small monorepo with two packages (`ui` exporting a few components, `app` consuming them), configure a basic Turborepo `turbo.json` with a `build` task declaring `dependsOn: ["^build"]`, run `turbo run build` twice and confirm the second run is a full cache hit (near-instant, explicitly reported as such) with zero source changes, then modify one file in `ui` and confirm only `ui` (and anything depending on it) rebuilds, not `app`'s independent tasks that don't actually depend on the changed output. Follow with a tree-shaking check: build a small bundle importing one named export from a barrel file with a dozen re-exports, inspect the output bundle, and confirm (or disprove) that unused re-exports were actually excluded — this is a genuinely useful habit to build, since "tree shaking should have removed that" is a claim worth verifying directly in bundle output rather than assuming. Reference: `labs/js/14-build-tooling/`.

---

## How it's done in production

Production Vite/Rolldown-based builds are typically wired into CI with bundle-size budget checks (see the web-performance module) gating merges, source maps generated and uploaded to an error-tracking service via an authenticated CI step rather than served publicly, and — in a monorepo — Turborepo/Nx remote caching configured against a shared cache backend so CI doesn't rebuild unchanged packages on every run.

| Symptom | Cause | Fix |
|---|---|---|
| A production bundle is much larger than expected despite tree shaking being "on" | A dependency is CommonJS (or has a CJS-only entry resolved via `require`), so its exports can't be statically analyzed and the whole module is included regardless of what's actually used | Check the dependency's `package.json` `exports`/`module` fields for an ESM build; if only CJS is available, consider an ESM-native alternative or accept the cost consciously rather than assuming shaking is working |
| Setting `"sideEffects": false` on a package causes a subtle production-only bug (a global style or polyfill stops applying) | The blanket `sideEffects: false` claim was inaccurate — some file in the package does have a real side effect at import time, and the bundler trusted the assertion and dropped it | Audit files with real side effects (global CSS imports, polyfills, singleton registration) and list them explicitly in the `sideEffects` array instead of a blanket `false` |
| Importing one icon from an icon library pulls in a much larger chunk than expected | The library's `index.js` is a barrel file re-exporting hundreds of icons, and the bundler (or its version) doesn't perform lazy barrel resolution, so the whole re-export chain gets parsed/pulled into the bundle graph | Import directly from the specific icon's file path if the library supports it (`icon-library/IconName` instead of `icon-library`), or verify the bundler's actual barrel-handling behavior for that specific case rather than assuming named-import tree shaking always works through a barrel |
| Production error stack traces show minified variable names and unreadable line numbers | Source maps aren't being generated, or aren't uploaded to the error-tracking service that symbolicates the stack trace | Generate source maps in the production build config and add an authenticated upload step to the error-tracking service in CI, decoupled from whether the map is served publicly |
| A public production bundle's original, human-readable source (including internal comments) is visible via browser dev tools | The `.map` file (or a `//# sourceMappingURL` pointing at a publicly accessible one) is being served alongside the production bundle | Upload source maps privately to the error-tracking service only; omit the public `sourceMappingURL` reference (or serve maps behind auth) in the deployed bundle |
| CI takes 25+ minutes to build/test a monorepo for a one-line change in a single leaf package | No task-graph-aware caching configured — every package rebuilds/retests on every CI run regardless of what actually changed | Configure Turborepo/Nx with a declared task graph and remote caching, so only the changed package and its actual dependents rebuild, with cache hits reused across CI runs and teammates |

---

## Tradeoffs & when NOT to use it

- **Don't assume `sideEffects: false` is free to set on every package.** It's a real, verifiable-by-you-not-by-the-bundler assertion; setting it incorrectly produces a bug that's easy to miss in development (where the side effect might still run through some other path) and only surfaces in the actually-shaken production bundle.
- **Don't reach for a monorepo task runner (Turborepo/Nx) for a single-package repo, or a very small number of loosely related packages with no real build interdependency.** The task-graph and caching machinery solves a coordination problem that only exists once there's real cross-package build dependency and enough packages that naive full rebuilds are actually slow — for a small enough repo, the setup and mental overhead isn't worth it yet.
- **Don't serve production source maps publicly by default "for easier debugging."** The convenience of occasionally being able to inspect a stack trace directly in browser dev tools is rarely worth exposing full original source structure to anyone who looks; route maps through an authenticated error-tracking pipeline instead.
- **Don't treat esbuild as a complete, all-in-one bundler replacement for every use case without checking its stated scope.** esbuild's own maintainer is explicit that it deliberately excludes some things (advanced code splitting is still described as comparatively primitive, no built-in TypeScript type checking — that's still `tsc`'s job run separately, no HMR, no module federation) — for those specific needs, you're reaching for Vite (which uses esbuild/Rolldown under the hood but adds the missing pieces) or another tool layered on top, not esbuild alone.
- **Don't blindly trust that "tree shaking is on" means a specific import was actually removed.** It's a real, verifiable claim — inspect the actual bundle output (a bundle analyzer, or just grep the built file) for anything you're relying on shaking to remove, especially through barrel files or CJS-adjacent dependencies, rather than assuming the mechanism worked as expected.

---

## Interview questions

### Q1 — Explain why Vite's dev server starts almost instantly regardless of application size, mechanically.
**Testing:** whether the candidate understands the actual mechanism (unbundled native ESM serving) versus a vague "it's fast."
**Answer:** Vite doesn't bundle the application's own source code during development at all — it serves it as native ES modules directly to the browser, transforming each file on-demand only as the browser actually requests it (following `import` statements lazily), while pre-bundling only third-party dependencies once (since those rarely change and often ship as CommonJS or many small files that benefit from being combined). Startup time is therefore roughly independent of total application size, since no work happens on files the browser hasn't requested yet.
**Follow-up trap:** *"Why does Vite still bundle for production, then, if unbundled serving works fine in dev?"* — unbundled ESM in production means real network cost at scale: browsers cap concurrent connections/streams per origin (commonly around 100 even under HTTP/2), every request carries fixed overhead, and deep import chains create waterfalls (sequential round trips to resolve nested imports) — bundling combines modules into an optimal number of chunks specifically to avoid that, which matters far more for a real end user on a real network than for a local dev server on localhost.

### Q2 — Name the three main things that defeat tree shaking, and explain the mechanism for each.
**Testing:** whether the candidate can name the actual mechanisms, not just "sometimes tree shaking doesn't work."
**Answer:** (1) CommonJS modules — `require`/`module.exports` are dynamic and not statically analyzable the way ESM's `import`/`export` is, so a bundler generally can't prove which exports are unused and has to include the whole module. (2) Side effects the bundler can't prove are safe to remove — a module that does something at import time beyond defining exports can't be safely dropped even if its exports are unused, unless explicitly marked side-effect-free via `package.json`'s `sideEffects` field. (3) Barrel files — an index re-exporting many things forces (in bundlers without specific barrel optimization) parsing/inclusion of the whole re-export chain even when only one export is actually used.
**Follow-up trap:** *"If a package sets `sideEffects: false` but actually has a file that registers a global at import time, what happens, and why is this bug hard to catch?"* — the bundler trusts the assertion and drops that file if its named exports aren't used, silently removing the side effect from the production bundle. It's hard to catch because development builds (unbundled or less aggressively optimized) may still run the side effect through a different code path, so the bug is invisible until the actually-shaken production build ships.

### Q3 — What is the `sideEffects` field in `package.json`, and why can't a bundler determine this automatically through static analysis alone?
**Testing:** precise understanding of what the field asserts and why it's necessary.
**Answer:** It's an explicit author assertion (`false`, or an array of specific files) telling the bundler which files, if any, do something at import time beyond defining their exports (mutating a global, registering a singleton, injecting CSS) — information the bundler can't fully verify through static analysis alone, since determining whether arbitrary code has an observable side effect is not generally statically decidable, so the field exists as a trust boundary between package author and bundler.
**Follow-up trap:** *"Would you ever set sideEffects: false on a package without actually auditing every file for real side effects?"* — no, and doing so is a common real mistake — the field is a promise the bundler will act on without verification, so an incorrect blanket `false` produces a silent production bug (a needed side effect dropped) that's specifically hard to trace back to this one config line.

### Q4 — Why does esbuild (and similarly Rust/Go-based tools generally) achieve order-of-magnitude speedups over JS-based bundlers, beyond just "compiled languages are faster"?
**Testing:** whether the candidate can cite the actual documented mechanisms rather than a hand-wave about compiled-vs-interpreted.
**Answer:** Several compounding factors: native compilation avoids the JIT warm-up cost a JS-based tool pays on every fresh invocation (the tool's own code has to be parsed/optimized by the VM before doing any real work); genuine multi-core parallelism is easier with shared memory between threads (Go/Rust) versus JS needing to serialize data across worker boundaries; and a from-scratch implementation avoids the overhead of gluing together multiple third-party libraries with incompatible internal representations, minimizing how many times the same data has to be converted between forms. esbuild's own published benchmark shows roughly 87-106x speedups over Rollup+Terser and Webpack 5 respectively on a real-world-scale JS bundling benchmark.
**Follow-up trap:** *"Does this mean Webpack is now obsolete and should never be chosen for a new project?"* — not automatically; Webpack's plugin ecosystem and configurability remain genuinely more mature and battle-tested for certain complex, non-standard build requirements, and plenty of large, established codebases have sunk cost in a working Webpack setup where a migration's engineering cost may not be justified purely by build speed — the right choice depends on the specific requirements and migration cost, not a blanket "always pick the fastest tool."

### Q5 — Explain how Node's `package.json` `exports` field changes module resolution compared to the older `main` field, and why a package might resolve to different code depending on how it's imported.
**Testing:** understanding of the actual resolution mechanism and its conditional-resolution capability.
**Answer:** `main` points at a single entry file unconditionally; `exports` allows conditional resolution — different files can be resolved depending on how the module is being consumed (`import` vs `require`, or other custom conditions), and it can also restrict/scope exactly which subpaths are importable at all, unlike `main`'s single unconditional entry point. A package can therefore ship a genuinely different build (an ESM-native file for `import`, a CJS-transpiled file for `require`) behind the identical import specifier, with Node/bundlers picking the right one automatically based on the consuming code's own module system.
**Follow-up trap:** *"If a package's ESM build tree-shakes well but its CJS build doesn't, and a consumer's bundler somehow resolves the CJS version anyway, why might that happen despite the package correctly providing both?"* — often a bundler/loader configuration issue — some bundler setups, especially older ones or those without correct `exports` support, fall back to `main` (typically CJS) rather than respecting the `exports` field's `import` condition, or a `require()` call somewhere in the dependency chain (even indirectly, via another dependency) forces CJS resolution for that specific import path regardless of what the package author intended to be the "modern" entry.

### Q6 — What does a source map actually encode, and what's the real tradeoff in deciding whether to serve one publicly in production?
**Testing:** mechanical understanding plus the security tradeoff, not just "source maps help debugging."
**Answer:** A source map is a JSON file mapping positions in generated (minified/transformed) output back to original source positions (line/column, original symbol/file names), encoded compactly as VLQ base64 in the `mappings` field — this is what lets dev tools reconstruct readable stack traces and let you debug against original source even though the browser executes minified code. The tradeoff: publicly serving the actual map file alongside production JS lets anyone with browser dev tools reconstruct full original source (including comments, structure, variable names), which is a real exposure most teams don't want; the standard mitigation is uploading maps privately to an error-tracking service via authenticated CI rather than serving them alongside the public bundle.
**Follow-up trap:** *"If you omit the sourceMappingURL comment from the public bundle, does that fully solve the exposure problem?"* — it stops casual dev-tools inspection from finding the map automatically, but the map file itself, if it's still deployed to a guessable or discoverable public path, remains fetchable directly — the actual fix is not deploying the map file to any publicly reachable location at all (or gating it behind auth), not merely omitting the reference comment, which is a weaker, easily-bypassed mitigation on its own.

### Q7 — Design a monorepo build task graph for three packages: `utils` (no dependencies), `ui` (depends on `utils`), and `app` (depends on `ui`). Explain what `dependsOn: ["^build"]` actually encodes and why it matters.
**Testing:** whether the candidate understands task-graph declaration as solving a real correctness problem, not just a performance one.
**Answer:** Each package declares `"build": { "dependsOn": ["^build"] }`; the `^` prefix means "run this task in each of this package's own dependencies first" — so building `app` triggers `ui`'s build first (since `app` depends on `ui`), which in turn triggers `utils`'s build first (since `ui` depends on `utils`), establishing correct topological build order automatically from the declared package dependency graph rather than a hand-maintained script order. This matters for correctness, not just speed: without it, `app` could attempt to build against a stale or missing `ui` build output, and the ordering bug wouldn't necessarily be obvious from a script that "usually" runs in the right order by coincidence of file listing.
**Follow-up trap:** *"If you change a file inside utils only, what specifically gets rebuilt, and what's skipped?"* — `utils` rebuilds (its content hash changed), `ui` rebuilds (it depends on `utils`'s build output, so its own cache key/inputs changed transitively), and `app` rebuilds (same transitive reasoning) — but any *sibling* package with no dependency relationship to `utils` is skipped entirely, since its own cache key (derived from its own inputs) is unaffected; this selective rebuild is the entire point of the declared, cached task graph versus a naive "rebuild everything" script.

### Q8 — A production bundle is significantly larger than expected after adding one new dependency, but the code only imports a single named export from it. Walk through your diagnostic process.
**Testing:** staff-level: synthesizing tree-shaking failure modes into an actual triage sequence, not just naming them abstractly.
**Answer:** First, check the dependency's actual module format — inspect its `package.json` for an `exports`/`module` field pointing at a genuine ESM build; if it only ships CommonJS, tree shaking for that dependency is structurally limited regardless of what's imported. Second, if it is ESM, check whether the specific import path goes through a barrel file (an `index.js` re-exporting many things) — inspect whether the actual bundler/version in use performs lazy/optimized barrel resolution, or whether importing the specific submodule path directly (bypassing the barrel) produces a meaningfully smaller result, which would confirm the barrel as the cause. Third, verify with the bundle analyzer directly rather than assuming — inspect the actual built output to see what got included from that dependency and whether it matches expectations.
**Follow-up trap:** *"The dependency is confirmed ESM with no barrel involved, and the bundle is still large. What else could explain it?"* — the dependency itself might declare `sideEffects` too conservatively (e.g., no `sideEffects` field at all, which most bundlers treat as "assume everything has side effects, don't shake anything" by default, the safe-but-pessimistic fallback) — checking whether the dependency has an explicit and accurate `sideEffects` declaration is a distinct check from confirming it's ESM, and a missing/overly-conservative declaration produces the identical symptom (large bundle despite ESM and minimal actual imports) through a completely different mechanism.

### Q9 — Explain what actually happens, mechanically, when a bundler encounters a dynamic `import()` call, and why chunk boundary decisions aren't purely automatic.
**Testing:** whether the candidate understands code splitting as a real build-graph transformation, not just "lazy loading happens."
**Answer:** A dynamic `import()` call is a signal to the bundler to create a separate chunk containing that module and its exclusive dependencies (anything not also reachable from the main entry graph), emit it as its own output file, and replace the `import()` call site with runtime code that fetches and evaluates that chunk on demand rather than including it in the initial bundle. The boundary isn't purely automatic because shared dependencies between two lazy-loaded routes create a real choice: duplicate the shared module into both chunks (fast initial load per-route, wasted bytes if both routes are ever visited in the same session) or extract it into a separate shared chunk both routes reference (no duplication, but an extra network request and cache dependency) — this is a genuine tuning decision (`splitChunks`/`manualChunks` configuration) with no universally correct default, and getting it wrong either bloats initial loads or creates chunk-fetching waterfalls.
**Follow-up trap:** *"Your app has 40 routes, each dynamically imported, but users report the SAME shared UI library code re-downloading on every route navigation with no caching benefit."* — this means the shared dependency is being duplicated into every route chunk rather than extracted into a common chunk, likely because the bundler's automatic common-chunk heuristic threshold (minimum number of chunks that must share a module before it's extracted) wasn't tuned for a 40-route app's actual sharing pattern — the fix is explicit `splitChunks.cacheGroups` (webpack) or `manualChunks` (Rollup/Vite) configuration pulling the shared library into its own long-lived, independently-cached chunk.

### Q10 — Why do production JS bundles ship with content hashes in their filenames (`app.3f8a2b1c.js`), and what specifically breaks if a team instead deploys with stable filenames and relies on HTTP cache-control headers alone?
**Testing:** the actual mechanism connecting build output naming to a real production caching/deployment correctness issue.
**Answer:** A content hash derived from the file's actual bytes means the filename itself changes whenever the content changes, which lets the deployment set an extremely long, aggressive cache lifetime (`Cache-Control: max-age=31536000, immutable`) on hashed assets with zero risk of serving stale content — a browser that cached `app.3f8a2b1c.js` forever will simply request `app.9d21ff44.js` after the next deploy, a different URL entirely, rather than needing cache invalidation at all. With stable filenames and cache-control-only invalidation, there's a real, unavoidable race during a deploy: some users' browsers (or intermediate CDN edge nodes) can hold a cached old version of `app.js` past its stated max-age due to network conditions, aggressive local caching, or CDN propagation lag, and the specific failure mode is a stale JS bundle making requests against a *new* deployed API version whose contract changed — a version-skew bug that's hard to reproduce because it depends on exactly which cache layer served stale content to which user.
**Follow-up trap:** *"Does content hashing eliminate version-skew risk entirely?"* — no, and this is the real trap: the *entry* HTML file (which references the hashed asset URLs) must itself never be aggressively cached, since it's the one artifact that has to update on every deploy to point at the new hashes — if the HTML is cached long-lived too, users get a stable HTML referencing old, hashed JS/CSS URLs indefinitely; the correct policy is `Cache-Control: no-cache` (or very short-lived) specifically on the HTML entry point, paired with `immutable` long-lived caching on everything the HTML references by hash.

---

## Red flags that fail you

- Claiming tree shaking "just works" on any ES module import without acknowledging CommonJS, side effects, and barrel files as real, specific limitations.
- Setting `sideEffects: false` without having actually audited the package's files for real side effects.
- Not knowing the difference between `main`/`module`/`exports` in `package.json` and why a package can resolve differently for `import` vs `require`.
- Serving production source maps publicly with no discussion of the exposure tradeoff.
- Recommending a monorepo task runner (Turborepo/Nx) reflexively for any multi-package repo regardless of actual build interdependency or repo size.
- Attributing build tool speed improvements purely to "it's written in Rust/Go" without understanding the actual mechanisms (parallelism, avoiding JIT warm-up, avoiding cross-library data conversion overhead).

---

## Cheat card

```
VITE: dev = native ESM served on-demand, deps pre-bundled once (fast tool) ->
  near-instant startup regardless of app size. Prod = still bundles (network
  request overhead + waterfalls make unbundled ESM impractical at scale even
  on HTTP/2, default ~100 concurrent streams/connection cap).
  Current: Vite 8.x (Vite 8 shipped March 2026). Rolldown (Rust, Oxc parser,
  Rollup-compatible plugin API) unifies what used to be esbuild(dev)+Rollup(prod)
  into one consistent pipeline.

ESBUILD SPEED (own published benchmark, 3x three.js dupe, ~547K loc):
  esbuild 0.39s vs Rollup+Terser 34.10s (87x) vs Webpack 5 41.21s (106x).
  Why: native compiled (no JIT warmup per-run), real multi-core parallelism
  (shared memory, Go/Rust vs JS's serialize-across-workers), from-scratch impl
  (AST touched only 3x total, no cross-library data-format conversion overhead).
  esbuild explicit non-goals: TS type checking (still tsc's job), advanced
  code splitting (still "primitive"), HMR, module federation.

MODULE RESOLUTION: package.json "exports" field (modern) > "main"/"module"
  (legacy, "module" = community convention not official Node algo).
  exports enables CONDITIONAL resolution (different file for import vs
  require) + restricts importable subpaths, unlike main's single entry.

TREE SHAKING DEFEATED BY: (1) CommonJS (require/module.exports not statically
  analyzable) (2) side effects bundler can't prove safe to remove -> use
  "sideEffects": false (or explicit file array) in package.json to assert
  safety — WRONG assertion = silent prod-only bug, side effect dropped
  (3) barrel files (index.js re-exporting many things) -> traditionally forces
  parsing/including the whole re-export chain; newer bundlers (Rolldown) do
  "lazy barrel optimization" to resolve only what's actually reachable.

SOURCE MAPS: JSON mapping generated position -> original position (VLQ base64
  in "mappings"). Production tradeoff: public .map file = anyone in devtools
  reconstructs full original source. Fix: upload privately to error-tracking
  service (Sentry/Datadog) via authenticated CI step, don't serve publicly;
  omitting sourceMappingURL comment alone is NOT sufficient if the .map file
  is still deployed to a reachable path.

MONOREPO TOOLING (Turborepo/Nx): task graph (turbo.json "dependsOn":["^build"]
  = "build this package's deps first, correct topological order") + content-
  addressed caching (cache key from actual inputs -> skip unchanged work) +
  remote caching (share cache across team/CI, not just one machine). Solves
  BOTH correctness (build order) and speed (skip unaffected packages).
  Not worth it for a single-package repo or a few loosely-related packages
  with no real cross-package build dependency yet.
```

## Sources

- [Why Vite — Vite official docs](https://vite.dev/guide/why.html) — accessed 2026-08-02 (live fetch, current version v8.1.5, Vite 8 announced March 2026)
- [Why do we still need bundlers? — Rolldown docs](https://rolldown.rs/in-depth/why-bundlers) — accessed 2026-08-02 (live fetch)
- [Barrel Module — Rolldown glossary](https://rolldown.rs/glossary/barrel-module) — accessed 2026-08-02 (live fetch)
- [esbuild FAQ — Why is esbuild fast? / Benchmark details](https://esbuild.github.io/faq/) — accessed 2026-08-02 (live fetch, published benchmark numbers)
- [Turborepo — official site](https://turborepo.dev/) — accessed 2026-08-02 (live fetch)
- Node.js documentation — `package.json` `exports` field resolution algorithm — living reference docs

## Changelog
- 2026-08-02 — created
