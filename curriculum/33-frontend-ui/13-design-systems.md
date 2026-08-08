# Design Systems & Component Architecture: Composition, Variants, Tokens, Versioning

> **Track:** T33 Frontend & UI Engineering · **Time:** 2.5h · **Prereqs:** T33-react-core, T33-css-layout
> **Module id:** `T33-design-systems` · **Tags:** architecture

## The 30-second version

Composition over configuration is the central design discipline: instead of one component with an ever-growing prop surface trying to handle every rendering variation (`<Card imageUrl title subtitle footerButtons showDivider ... />`), break it into smaller pieces consumers assemble themselves (`<Card><Card.Image /><Card.Title /><Card.Footer>...</Card.Footer></Card>`), because prop-driven configuration hits a combinatorial wall — every new requirement adds another prop, and eventually the component can't express a layout its own API didn't anticipate, while composition can, since consumers control arrangement directly. Design tokens are the single source of truth for design decisions (color, spacing, typography, radius) as data, not hardcoded values scattered through components — the W3C Design Tokens Community Group format (first stable spec, October 2025) standardized `$value`/`$type` so tools like Figma, Style Dictionary, and code can share one definition instead of each maintaining a parallel, drifting copy. Variants (a button's `primary`/`secondary`/`danger`, its `sm`/`md`/`lg`) should be a constrained, enumerated set defined by the design system, not open-ended style props, because an open `style` or arbitrary-className escape hatch defeats the entire point of having a system — consistency by construction, not by convention. Theming works by mapping semantic tokens (`color.background.primary`) to primitive tokens (`gray.900`) per theme, so a component only ever references the semantic layer and never needs to know which theme is active. Versioning a design system is genuinely harder than versioning a typical library because a "minor" visual change (a token update to spacing or color) can silently break dozens of consuming surfaces without any component API changing at all — semver's version number can lie about the actual blast radius. And a design system is premature for a single product with one team and no near-term plans for a second surface — the coordination overhead (a separate package, a review process, a deprecation policy) only pays for itself once genuine reuse across multiple consumers exists.

## Why this gets asked

Because building reusable component APIs is one of the clearest signals of engineering maturity available in an interview — it's easy to make a component work once, and hard to make it work for every consumer that shows up over the next two years without either becoming an unmaintainable prop-soup mess or breaking half its callers on every change. The interviewer has almost certainly maintained (or been a frustrated consumer of) a component library that went one of two wrong directions: over-configured (a `Button` with 40 boolean props, most combinations untested and some contradictory) or over-abstracted too early (a "flexible" design system built for a single product with no second consumer, whose flexibility was pure speculative cost). They want to see whether you reason about API design as a tradeoff between flexibility and simplicity with actual criteria for where to draw the line, not a default toward maximal configurability or maximal composability without justification.

---

## Lineage: past → present → future

**What came before.** Early component libraries (Bootstrap circa 2011, and countless in-house equivalents through the mid-2010s) were largely CSS-class-driven: apply `btn btn-primary btn-lg` and get styled output, with JavaScript behavior (if any) bolted on separately and minimally configurable. The pain this caused was twofold — visual consistency was achievable but component *behavior* (accessibility, keyboard interaction, state management for anything beyond the simplest widgets) had to be re-implemented per consumer, and CSS specificity wars made overriding or extending styles for edge cases fragile and unpredictable. As component-based frameworks (React from 2013 onward) matured, teams shifted toward JS-driven prop-configured components that encapsulated both style and behavior — a real improvement, but one that introduced its own failure mode: as a shared `Button` or `Card` accumulated more use cases, its prop API grew unboundedly (`isLoading`, `iconLeft`, `iconRight`, `fullWidth`, `noBorder`...) until the component became genuinely difficult to reason about, test exhaustively, or extend for a case its author hadn't anticipated.

**Where it stands now.** The current consensus, driven heavily by libraries like Radix UI, React Aria, and the shadcn/ui pattern (which popularized "copy the component source into your own codebase rather than depending on an opaque package"), favors composition and headless/unstyled primitives: separate the *behavior and accessibility logic* (a hook or headless component handling focus management, keyboard interaction, ARIA state) from the *visual presentation* (styled by the consuming team, using whatever styling approach — CSS-in-JS, Tailwind, vanilla CSS — fits their stack), and expose composable subcomponents rather than monolithic configured ones. Design tokens reaching a genuine W3C standard (DTCG, first stable spec October 2025) is a real, recent, and consequential shift — before this, every design tool and build pipeline used its own token format, and translation between Figma's internal representation, Style Dictionary's config, and a team's actual CSS variables was a constant, error-prone manual process; a shared standard format that Figma, Style Dictionary, and other major tools now support directly reduces that translation loss. The live disagreement that remains unresolved: how much a design system should own behavior versus purely visual tokens — some teams (Radix, React Aria) draw the line at "behavior and accessibility only, you own all styling," others (Material UI, Chakra) ship fully styled, opinionated components with an escape hatch for customization, and reasonable teams land in different places depending on how much visual differentiation their product actually needs versus how much engineering time they can spend re-solving accessibility correctness themselves.

**Where it's heading.** AI-assisted component generation (scaffolding a new component variant from a design file, or generating Style Dictionary token transforms) is a genuinely active area of tooling investment, but it's speculative how much it changes the fundamental API design judgment calls (composition versus configuration, where to draw the variant boundary) that remain a human design decision regardless of how the code is generated — generating code faster doesn't resolve the harder question of what the API surface *should* be. What looks more durable: continued convergence on the DTCG token standard reducing tool fragmentation, and the "copy the source, don't depend on an opaque package" pattern (popularized by shadcn/ui) gaining ground specifically because it sidesteps the hardest part of design-system versioning — you can't have a breaking change in a dependency you don't have, at the cost of losing centralized bug fixes and updates, which is a real and explicit tradeoff, not a free win.

---

## Mental model

Think of a design system as three independent layers, each solving a different problem, and most real confusion in interviews comes from not separating them:

```
┌──────────────────────────────────────────────────────┐
│  TOKENS (data)                                          │
│  color.blue.500 = #3B82F6                                │
│  semantic: color.background.primary -> {color.blue.500}   │  <- theme swaps here
│  spacing.md = 16px                                          │
└──────────────────────────────────────────────────────┘
                          │ consumed by
                          ▼
┌──────────────────────────────────────────────────────┐
│  BEHAVIOR (headless logic)                               │
│  useButton() -> { role, tabIndex, onKeyDown, onClick }     │
│  (focus management, keyboard interaction, ARIA state —      │
│   zero visual opinion, testable independent of styling)      │
└──────────────────────────────────────────────────────┘
                          │ consumed by
                          ▼
┌──────────────────────────────────────────────────────┐
│  COMPOSITION (structure)                                  │
│  <Card><Card.Image/><Card.Title/><Card.Footer/></Card>       │
│  (consumer controls arrangement; component controls           │
│   what pieces exist and how they cooperate via context)         │
└──────────────────────────────────────────────────────┘
```

A "premature design system" almost always means jumping straight to building all three layers formally (a token pipeline, headless hooks, a composed component API) for a single product with one consumer, when a handful of well-organized CSS variables and a few genuinely reusable components would have solved the actual problem at a fraction of the coordination cost.

---

## How it actually works

### Composition over configuration, concretely

The failure mode composition solves: a component that tries to anticipate every layout need via props eventually can't express something its author didn't foresee, and the props themselves become hard to reason about (which combinations are valid? what happens if `iconLeft` and `fullWidth` and `isLoading` are all true?).

```jsx
// CONFIGURATION-DRIVEN — untested sketch, illustrates the failure mode
function Card({ imageUrl, title, subtitle, footerButtons, showDivider, badge, ... }) {
  return (
    <div className="card">
      {imageUrl && <img src={imageUrl} />}
      {badge && <span className="badge">{badge}</span>}
      <h3>{title}</h3>
      {subtitle && <p>{subtitle}</p>}
      {showDivider && <hr />}
      {footerButtons && <div className="footer">{footerButtons.map(...)}</div>}
    </div>
  );
  // adding a new layout need (e.g. title AND a secondary badge both above the image)
  // means adding more props, or the component genuinely can't express it
}

// COMPOSITION-DRIVEN — consumer controls arrangement directly
function Card({ children, className }) {
  return <div className={cx("card", className)}>{children}</div>;
}
Card.Image = function CardImage({ src, alt }) { return <img className="card-image" src={src} alt={alt} />; };
Card.Title = function CardTitle({ children }) { return <h3 className="card-title">{children}</h3>; };
Card.Footer = function CardFooter({ children }) { return <div className="card-footer">{children}</div>; };

// consumer:
<Card>
  <Card.Image src="..." alt="..." />
  <Card.Title>Product name</Card.Title>
  <Card.Footer>
    <Button variant="primary">Buy</Button>
  </Card.Footer>
</Card>
```

The composed version can express any arrangement the primitives allow, including ones the original author never anticipated, because the consumer controls structure directly rather than requesting it through a prop the author had to have already built. The tradeoff, stated honestly: composition pushes more responsibility (and more code) onto the consumer for simple cases — a consumer who just wants "a standard card with an image, title, and one button" writes more JSX for the composed version than they would with a single well-configured prop-driven component. This is exactly why real systems (Radix, Chakra, most mature libraries) offer both: composable primitives for genuine flexibility needs, plus a small number of pre-assembled, sensibly-defaulted compound patterns for the common case.

### Compound components: sharing state without prop drilling

The mechanism that makes `<Card.Image>`/`<Card.Title>` cooperate (e.g., a `Tabs` component where `Tabs.List`, `Tabs.Tab`, and `Tabs.Panel` all need to agree on which tab is active) without the consumer manually wiring props between them is React Context, scoped to the compound component:

```jsx
// untested sketch — compound component sharing state via context
const TabsContext = createContext(null);

function Tabs({ defaultValue, children }) {
  const [value, setValue] = useState(defaultValue);
  return <TabsContext.Provider value={{ value, setValue }}>{children}</TabsContext.Provider>;
}

Tabs.List = function TabsList({ children }) {
  return <div role="tablist">{children}</div>;
};

Tabs.Tab = function Tab({ value: tabValue, children }) {
  const { value, setValue } = useContext(TabsContext);
  return (
    <button role="tab" aria-selected={value === tabValue} onClick={() => setValue(tabValue)}>
      {children}
    </button>
  );
};

Tabs.Panel = function TabPanel({ value: panelValue, children }) {
  const { value } = useContext(TabsContext);
  return value === panelValue ? <div role="tabpanel">{children}</div> : null;
};
```

The consumer never manually threads `activeTab`/`setActiveTab` between `Tabs.List`, `Tabs.Tab`, and `Tabs.Panel` — the context does it invisibly, while the consumer still controls the actual DOM arrangement (could nest `Tabs.List` differently, add custom elements between panels, etc.) that a single monolithic `<Tabs items={[...]} />` prop API couldn't express.

### Design tokens: the DTCG standard, concretely

A design token is a named, single-sourced design decision. The W3C Design Tokens Community Group's format (first stable specification, October 2025) standardizes the shape:

```json
{
  "color": {
    "blue": {
      "500": { "$value": "#3B82F6", "$type": "color" }
    }
  },
  "spacing": {
    "md": { "$value": "16px", "$type": "dimension" }
  },
  "semantic": {
    "background": {
      "primary": { "$value": "{color.blue.500}", "$type": "color" }
    }
  }
}
```

`$value`/`$type` are the standardized keys (replacing the fragmented, tool-specific formats — plain values, `value`/`type` without the `$` prefix, or entirely custom shapes — that different vendors used before the standard existed), and `{color.blue.500}` is a reference/alias, letting a semantic token point at a primitive one so the primitive can change (a rebrand, a palette adjustment) without touching every place that referenced the semantic name. Style Dictionary (version 4+ has first-class DTCG support) consumes this format and transforms it into whatever output a given platform needs — CSS custom properties, SCSS variables, JS/TS constants, iOS/Android native formats — from one source definition, which is the entire point: one token definition, many generated outputs, instead of hand-maintaining parallel copies per platform that inevitably drift.

### Theming: primitive tokens vs semantic tokens

The critical architectural decision that makes theming (light/dark, brand variants) tractable: components should reference *semantic* tokens (`color.background.primary`, `color.text.muted`) never *primitive* tokens (`gray.900`, `blue.500`) directly. A theme is then just a different mapping from semantic tokens to primitives:

```json
// theme: light
{ "color.background.primary": "{color.gray.50}", "color.text.primary": "{color.gray.900}" }

// theme: dark
{ "color.background.primary": "{color.gray.900}", "color.text.primary": "{color.gray.50}" }
```

A component that hardcodes `background: var(--color-gray-50)` breaks in dark mode because it bypassed the semantic indirection layer entirely — this is one of the most common real bugs in poorly executed theming, and it's structural (the component referenced the wrong layer), not a one-off mistake to catch in review each time.

### Variants: an enumerated, constrained API

```jsx
// untested sketch — variant API via a well-typed union, not an open style prop
type ButtonVariant = "primary" | "secondary" | "danger";
type ButtonSize = "sm" | "md" | "lg";

function Button({ variant = "primary", size = "md", children, ...props }: {
  variant?: ButtonVariant; size?: ButtonSize; children: React.ReactNode;
}) {
  return <button className={cx("btn", `btn-${variant}`, `btn-${size}`)} {...props}>{children}</button>;
}
```

Constraining `variant`/`size` to a closed TypeScript union (rather than accepting an open `className` or `style` prop that lets any consumer inject arbitrary visual overrides) is what makes the system a system — every button in the product is guaranteed to be one of a known, designed set of visual states, and a design change to `btn-primary` propagates everywhere consistently. An escape hatch (an explicitly named `className` prop for genuine edge cases) is reasonable, but it should be a deliberate, visible exception, not the default way consumers customize appearance.

### Versioning: why it's harder than typical library versioning

Standard semver (major = breaking, minor = additive, patch = fix) assumes a component's public surface is fully captured by its code API — but in a design system, a token change can have a blast radius semver's version number doesn't reflect: a spacing token adjustment or a semantic color rename can visually or functionally break dozens of consuming surfaces without a single component prop or function signature changing at all, meaning it *looks* like a safe minor/patch bump by the code-API definition while behaving like a breaking change for anyone relying on the previous visual output. The practical mitigation many mature systems adopt: treat token changes with the same rigor as API changes (a token *rename* is a breaking/major change requiring a deprecation period, not a patch), maintain deprecated tokens/components with clear warnings and an announced end-of-life date rather than removing them abruptly, and — for organizations serving many independent products on different release cadences — consider per-component/per-package versioning rather than a single monolithic system version, so consumers can adopt updates incrementally rather than all-or-nothing.

---

## Build it from scratch

A concrete, checkable exercise: build a minimal `Tabs` compound component (List/Tab/Panel via Context, as sketched above) with full keyboard support (arrow keys move between tabs per the ARIA APG tabs pattern, not just click), then define its colors and spacing entirely via a small DTCG-format token file, wire Style Dictionary to generate CSS custom properties from it, and implement a light/dark theme swap purely by changing which semantic-to-primitive mapping is active — with zero changes to the component itself, proving the semantic indirection layer actually works. Reference: `labs/js/13-design-systems/`.

---

## How it's done in production

Production design systems typically separate into (at least) three repositories or packages with independent release cadences: a tokens package (source JSON, Style Dictionary config, generated per-platform outputs), a headless/behavior package (Radix-style unstyled primitives, or in-house equivalents), and a styled component package consuming both. Documentation and visual regression (Storybook plus Chromatic or a similar visual diffing tool) run against every component variant combination in CI, since manual QA of every variant×theme×size combination doesn't scale past a small system.

| Symptom | Cause | Fix |
|---|---|---|
| A component looks correct in light mode but breaks visually in dark mode | Component references a primitive token directly (`--color-gray-50`) instead of a semantic token (`--color-background-primary`), bypassing the theme indirection layer | Audit and enforce (via lint rule or design-token-usage linter) that components only ever reference semantic tokens, never primitives directly |
| A "minor" token update breaks visual consistency across dozens of unrelated surfaces | Token changes have a blast radius semver's code-API-based versioning doesn't capture — a spacing/color token rename or value change affects every consumer referencing it | Treat token renames/removals with the same rigor as breaking API changes (major version, deprecation period), and diff visual regression snapshots across the whole system before releasing a token update, not just the component that "obviously" changed |
| A component's prop API has grown to 20+ props and is hard to use correctly | Configuration-driven design accumulated one prop per new requirement instead of being refactored toward composition once the pattern was clearly recurring | Identify the genuinely reusable substructure and refactor toward compound components/composition for the flexible cases, keeping a small set of sensible pre-assembled defaults for the common case |
| Two teams' React trees can't share a design system component because one uses styled-components and the other uses Tailwind | The design system's behavior/accessibility logic is tightly coupled to a specific styling approach instead of separated into a headless layer | Separate behavior (hooks/headless components with zero visual opinion) from presentation, so each team can style the same behavioral primitive with their own approach |
| A design system built for one product turns out to slow down that product's own iteration speed | The system was built with cross-product flexibility (theming, multi-brand support, extensive configurability) that the single actual consumer never needed, adding coordination overhead with no offsetting reuse benefit | Recognize the system was premature for the current scale; scope back to what the single product actually needs, and defer the generalized system until a genuine second consumer exists |

---

## Tradeoffs & when NOT to use it

- **Don't build a formal design system (token pipeline, headless behavior layer, versioned package, governance process) for a single product with one team and no near-term second consumer.** The coordination overhead (a separate release process, cross-team review, deprecation policies) only pays for itself once genuine reuse exists; before that point, a handful of well-organized shared components and CSS variables in the same codebase solves the actual problem with far less process cost.
- **Don't default to composition for every component.** Composition pushes more responsibility onto the consumer, which is the wrong tradeoff for genuinely simple, common-case components (a standard button, a standard badge) where a well-configured prop API with sensible defaults is faster to use correctly and harder to misuse than assembling primitives every time.
- **Don't leave an open `style`/`className` escape hatch as the primary customization mechanism.** If most consumers reach for it regularly, the variant system hasn't actually captured the real design space, and the system is providing false consistency — visible inconsistency that gets caught in review is arguably better than a "system" that's silently bypassed everywhere.
- **Don't version token changes as casually as patch-level bug fixes.** A token rename or value change can have a broader, harder-to-predict blast radius than a typical code change; treat it with deliberate deprecation and communication, not an automatic patch bump.
- **Don't couple behavior/accessibility logic tightly to one specific styling approach** if there's any realistic chance of multiple consuming teams with different styling preferences (CSS-in-JS, Tailwind, vanilla CSS) — the headless/behavior-separated pattern costs more upfront but avoids forcing every consumer onto one styling technology just to get correct accessibility behavior.

---

## Interview questions

### Q1 — Explain "composition over configuration" with a concrete example of where a prop-driven API breaks down.
**Testing:** whether the candidate can name the specific failure mode, not just recite the phrase.
**Answer:** A prop-driven component (e.g., `Card` with `imageUrl`, `title`, `footerButtons`, `showDivider`, `badge`...) accumulates one new prop per new layout requirement, and eventually can't express an arrangement its author didn't anticipate, while the growing prop surface also makes invalid/contradictory combinations possible and hard to reason about. A composed API (`<Card><Card.Image/><Card.Title/></Card>`) lets the consumer arrange primitives directly, expressing any layout the primitives support without waiting on new props.
**Follow-up trap:** *"Is composition strictly better, then — should every component be composition-driven?"* — no; composition pushes more responsibility onto the consumer for simple, common cases, which is the wrong tradeoff when a component's use cases are genuinely uniform (a standard button) — a well-configured prop API with sensible defaults is faster and harder to misuse there. The right answer chooses per component based on how varied its real use cases are, not a blanket rule.

### Q2 — How does a compound component (like `Tabs.List`/`Tabs.Tab`/`Tabs.Panel`) share state between its parts without prop drilling, and what does the consumer still control?
**Testing:** the actual mechanism (React Context scoped to the compound component), not just naming the pattern.
**Answer:** A parent component (`Tabs`) holds the shared state (which tab is active) and provides it via React Context; the child subcomponents (`Tabs.Tab`, `Tabs.Panel`) consume that context internally, so the consumer never manually wires an `activeTab` prop between them. The consumer still fully controls DOM arrangement and structure — which children exist, how they're nested, what's between them — which a single monolithic `<Tabs items={[...]} />` prop API couldn't offer.
**Follow-up trap:** *"What happens if a consumer renders Tabs.Tab outside of a Tabs provider?"* — the context value is `null`/undefined, and the subcomponent should explicitly handle that (throw a clear developer-facing error like "Tabs.Tab must be used within a Tabs component") rather than silently failing or throwing an obscure runtime error from trying to destructure `null` — good compound component APIs guard this deliberately.

### Q3 — What problem does the W3C DTCG token standard actually solve, and why does it matter that it's a genuine cross-vendor standard rather than one tool's format?
**Testing:** whether the candidate understands the standard as solving translation loss, not just "it's a JSON format for colors."
**Answer:** Before a shared standard, every design tool (Figma) and build pipeline (Style Dictionary, custom scripts) used its own token format, so translating a design decision from Figma's internal representation into a build pipeline's config into actual CSS/JS output was a manual, error-prone, per-tool process, with drift a constant risk. DTCG's `$value`/`$type` format (first stable spec, October 2025), now supported directly by Figma, Style Dictionary, and other major tools, means one token definition can flow through the whole pipeline without hand-translation at each hop.
**Follow-up trap:** *"What's the actual mechanism that lets a semantic token reference a primitive token, and why does that indirection matter?"* — token aliasing/references (`{color.blue.500}` inside a semantic token's `$value`), which matters because it's the mechanism theming depends on — a semantic token like `color.background.primary` can point at different primitives per theme without any component needing to know which theme is active, since components only ever reference the semantic layer.

### Q4 — A component looks fine in light mode but renders with unreadable low-contrast text in dark mode. Diagnose the likely architectural cause.
**Testing:** connecting a visible bug to the semantic-vs-primitive token architecture, not just "check the CSS."
**Answer:** The component almost certainly references a primitive token directly (e.g., hardcoded `--color-gray-900` for text) instead of a semantic token (`--color-text-primary`) that's meant to resolve differently per theme — bypassing the indirection layer that makes theming work, so the "dark mode" theme swap never actually reached that component's styling.
**Follow-up trap:** *"How would you prevent this class of bug systemically, not just fix this one instance?"* — a lint rule or custom token-usage linter that flags direct references to primitive tokens in component code (allowing them only inside the token definition/mapping files themselves), enforced in CI, rather than relying on manual review to catch every instance across a growing component library.

### Q5 — Why is versioning a design system genuinely harder than versioning a typical utility library?
**Testing:** understanding that semver's assumptions don't fully hold for design systems specifically.
**Answer:** Standard semver assumes a package's public surface is captured by its code API (function signatures, exported types) — but a design system's real "surface" includes visual output driven by tokens, and a token value change or rename can silently break the visual appearance or layout of dozens of consuming surfaces without any component prop or function signature changing at all. That kind of change looks like a safe patch/minor bump by code-API rules while behaving like a breaking change for consumers relying on the previous visual output.
**Follow-up trap:** *"If a designer changes a spacing token by 2px and engineering ships it as a patch release, what's the actual risk, and how would a mature team handle this differently?"* — the risk is silent layout breakage across every surface using that token, potentially shipped with no one specifically reviewing the blast radius since it "looks like" a trivial patch. A mature team runs visual regression across the whole system (not just the component that "obviously" changed) before releasing any token change, and treats token renames/value changes with deliberate versioning rigor comparable to an API change, not a routine patch.

### Q6 — When is building a formal design system premature, and what's the actual cost being avoided by waiting?
**Testing:** whether the candidate has a real, specific answer versus reflexively endorsing design systems as always good practice.
**Answer:** It's premature for a single product with one team and no concrete near-term plan for a second consuming surface — the coordination overhead (a separate versioned package, cross-team review process, deprecation policies, documentation investment) is real, ongoing cost that only pays for itself once genuine reuse across multiple consumers exists. Before that point, a well-organized set of shared components and token-like CSS variables living directly in the product's own codebase solves the actual problem without the process overhead.
**Follow-up trap:** *"If a second product is being planned for 'sometime next year,' should the design system work start now?"* — generally no, or only in the lightest possible form (documenting existing shared patterns, not building a formal package/pipeline) — building for a consumer that doesn't exist yet risks solving a set of requirements guessed in advance rather than the second product's actual real needs, which are usually clearer in hindsight than in speculation; the more defensible move is starting the formal extraction once the second product's real requirements are known, informed by the first product's actual patterns.

### Q7 — Explain the tradeoff between a "ship fully styled, opinionated components" design system (Material UI-style) versus a "behavior-only, you style everything" one (Radix-style).
**Testing:** staff-level: whether the candidate can articulate both sides of a genuinely live disagreement rather than picking one as universally correct.
**Answer:** Fully styled, opinionated systems get a team to a consistent, functional UI fastest with the least design/styling effort, at the cost of visual differentiation being hard to achieve without fighting the library's defaults, and customization often meaning CSS specificity battles or override APIs that feel bolted on. Behavior-only systems (correct accessibility/keyboard/focus logic exposed via hooks or unstyled primitives) require every consuming team to invest in their own visual design and styling implementation, but impose zero visual opinion and no fight against defaults, and the hard, error-prone part (getting ARIA/keyboard interaction exactly right per the APG patterns) is solved once and shared.
**Follow-up trap:** *"Which would you choose for a product that needs strong, distinctive brand differentiation as a core competitive requirement?"* — behavior-only/headless, since a fully opinionated styled system fights against distinctive visual differentiation by design (its whole value proposition is a consistent default look), whereas headless primitives impose no visual opinion at all, letting the team's own design work drive differentiation while still getting correct behavior for free.

### Q8 — A design system's `Button` component has an open `style` prop that most consuming teams use regularly to override its appearance. What does that indicate, and how would you address it?
**Testing:** staff-level: reading an escape-hatch usage pattern as a diagnostic signal about the system's actual coverage, not just a minor cleanup task.
**Answer:** Regular reliance on an open style escape hatch indicates the variant system hasn't actually captured the real design space consuming teams need — the "system" is providing an illusion of consistency that's silently bypassed in practice, which is arguably worse than visible inconsistency, since the latter at least gets caught in code review while override-via-style-prop often doesn't. Address it by auditing actual usage of the escape hatch across consumers, identifying the recurring patterns being expressed through it, and formalizing those as proper first-class variants (or composition points) in the next system iteration.
**Follow-up trap:** *"Should the fix always be adding more variants to close the gap?"* — not necessarily; if the override usage is highly varied and product-specific rather than converging on a small recurring set of patterns, that's a signal the component's scope was drawn too narrowly for what's actually needed, and the better fix might be exposing a genuine composition point (a slot, a render prop) rather than trying to enumerate an ever-growing, still-incomplete variant list.

### Q9 — A design system needs to ship a breaking prop rename across a component used in 200+ places across a dozen consuming teams. What's the actual mechanism for doing this without a coordinated big-bang migration?
**Testing:** codemod-based migration tooling as a concrete, staff-level answer to a problem "just version it well" doesn't fully solve.
**Answer:** Ship the breaking change behind a codemod — an automated AST transformation (commonly written with `jscodeshift` or a similar tool) that rewrites consuming code from the old API shape to the new one mechanically, published alongside the new major version so each consuming team runs it against their own codebase on their own schedule rather than the design-system team touching 200+ call sites by hand or requiring every team to migrate in lockstep. The old prop can also be supported for a deprecation window (accepted at runtime with a console warning, internally mapped to the new prop) so teams that haven't run the codemod yet aren't immediately broken, decoupling "the new version is released" from "every consumer has migrated."
**Follow-up trap:** *"What fraction of a rename like this can a codemod actually handle automatically, versus needing human review?"* — a straightforward prop rename with no semantic change is close to 100% automatable; the codemod becomes unreliable specifically when the change also alters *behavior* or *type* (not just the prop name, but what values are valid, or a structural shape change), where an automated rewrite can produce syntactically valid but semantically wrong code — flagging those cases for manual review rather than silently auto-migrating them incorrectly is the actual engineering judgment call in writing the codemod, not just the AST mechanics.

### Q10 — How do you actually measure whether a design system is succeeding, beyond "the components exist and teams say they like it"?
**Testing:** whether the candidate can name concrete, gameable-resistant adoption metrics rather than vague sentiment.
**Answer:** Concrete, checkable signals: the percentage of UI surface actually built from system components versus custom one-off implementations (measurable via static analysis of component imports across the codebase, not survey data), the frequency and size of the style-prop/escape-hatch usage covered in Q8 (a rising trend is a leading indicator of eroding fit), time-to-ship for a new feature using system components versus historical baselines before the system existed, and — for a system with a federated contribution model — the ratio of contributions from consuming teams versus the core design-system team, which indicates whether the system is a genuinely shared asset or a centrally-imposed one teams merely tolerate.
**Follow-up trap:** *"A team reports high 'component usage percentage' but their product still looks visibly inconsistent with the rest of the org's products. What's the gap?"* — usage percentage measures whether system *components* are being used, not whether they're being used *correctly* (consistent variant choices, consistent spacing tokens rather than one-off overrides) — a team can hit 100% component usage while still selecting inconsistent variants or overriding heavily via the style-prop escape hatch, so usage percentage needs to be paired with the escape-hatch-frequency metric from Q8 to actually capture consistency, not just adoption.

---

## Red flags that fail you

- Treating composition and configuration as if one is unconditionally correct, with no discussion of when each is the right tradeoff.
- Not knowing what a design token is beyond "a CSS variable," or being unaware of the semantic-vs-primitive distinction that makes theming work.
- Referencing primitive tokens directly in component code and not recognizing why that breaks theming.
- Treating a token change as automatically safe to ship as a patch release with no discussion of its actual blast radius.
- Recommending building a full formal design system for a single-product, single-team context with no second consumer.
- Not being able to name a real tradeoff of the headless/behavior-only component pattern versus a fully styled one.

---

## Cheat card

```
COMPOSITION > CONFIGURATION: prop-driven components hit a combinatorial wall —
  every new layout need = another prop, eventually can't express what author
  didn't anticipate. Composed subcomponents (<Card><Card.Image/></Card>) let
  consumer control arrangement directly. Tradeoff: composition = more consumer
  code for simple cases — use configuration for genuinely uniform components.

COMPOUND COMPONENTS: share state via React Context scoped to the compound
  component (Tabs -> Tabs.List/Tab/Panel), so consumer never manually threads
  props between parts but still controls DOM structure/arrangement.

DESIGN TOKENS (W3C DTCG, first stable spec Oct 2025): $value/$type standardized
  format. Figma, Style Dictionary (v4+), Penpot, others support it directly —
  ends per-tool format fragmentation/translation loss.
  Aliasing: {color.blue.500} lets semantic tokens reference primitives.

SEMANTIC vs PRIMITIVE TOKENS: components reference SEMANTIC ONLY
  (color.background.primary), NEVER primitive (gray.900) directly. Theme =
  different semantic->primitive mapping. Hardcoding a primitive in a component
  = the #1 real bug that breaks theming (bypasses the indirection layer).

VARIANTS: closed enumerated set (TypeScript union: "primary"|"secondary"|
  "danger"), NOT an open style/className prop as primary customization —
  open escape hatches used regularly = signal the variant system doesn't
  actually cover real usage.

VERSIONING IS HARDER THAN TYPICAL LIBS: semver assumes public surface = code
  API, but a token rename/value change can break dozens of visual surfaces
  with ZERO code API change — "looks like" a safe minor/patch, behaves like
  breaking. Treat token renames with deprecation rigor; visual-regression the
  WHOLE system before releasing a token change, not just the "obvious" component.

WHEN PREMATURE: single product, one team, no near-term second consumer ->
  formal system (versioned package, governance, token pipeline) is pure
  coordination overhead with no reuse payoff yet. Shared components + CSS
  vars in the same codebase solves it more cheaply until real reuse exists.

HEADLESS vs STYLED: Radix/React Aria (behavior+a11y only, you style) = correct
  ARIA/keyboard logic solved once, zero visual opinion, more setup per team.
  Material UI/Chakra (fully styled, opinionated) = fastest to consistent UI,
  harder to achieve distinctive visual differentiation without fighting defaults.
```

## Sources

- [Design Tokens Community Group (DTCG) — W3C](https://www.w3.org/community/design-tokens/) — accessed 2026-08-02
- [Design Tokens Community Group — Style Dictionary](https://styledictionary.com/info/dtcg/) — accessed 2026-08-02
- [Headless Component: a pattern for composing React UIs — Martin Fowler](https://martinfowler.com/articles/headless-component.html) — accessed 2026-08-02
- [Versioning Design Systems — Nathan Curtis, EightShapes](https://medium.com/eightshapes-llc/versioning-design-systems-48cceb5ace4d) — accessed 2026-08-02
- [Design System Versioning: Manage Your UI/UX in 2026 — Figr](https://figr.design/blog/design-system-versioning) — accessed 2026-08-02
- Radix UI, React Aria official documentation — headless/behavior-separated component pattern reference — living reference docs

## Changelog
- 2026-08-02 — created
