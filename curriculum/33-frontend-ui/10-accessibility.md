# Accessibility: Semantics, ARIA, Keyboard, Focus Management, Screen Readers, WCAG

> **Track:** T33 Frontend & UI Engineering · **Time:** 2.5h · **Prereqs:** T33-css-layout, T33-react-core
> **Module id:** `T33-accessibility` · **Tags:** quality, critical

## The 30-second version

Reach for semantic HTML first — a native `<button>` gets keyboard operability, focus, role, and state for free from the browser, while a `<div onClick>` requires you to hand-roll all of it and will still miss edge cases; ARIA is a last resort that adds a role or state to the accessibility tree but changes zero behavior, so `role="button"` on a div still doesn't make it focusable or Enter-activatable without you also adding `tabindex="0"` and a keydown handler — this is why "no ARIA is better than bad ARIA" is a real W3C rule, not a platitude: an incorrect `aria-*` attribute actively lies to a screen reader user in a way that silence never would. Keyboard navigation means every interactive element is reachable via Tab, operable via Enter/Space/Arrow keys as appropriate for its role, and never trapped except deliberately (a modal's focus trap); focus management in SPAs means manually moving focus to a heading or the main landmark on route change (since there's no full page load to reset focus for you) and, for modals, moving focus in on open, trapping it inside, and restoring it to the trigger element on close. WCAG has three conformance levels (A, AA, AAA), and AA is the level virtually every legal standard (ADA-linked lawsuits, Section 508, EN 301 549) actually requires — AAA has criteria (like 7:1 contrast) that are aspirational for most real products, not a bar to hold yourself to universally. Automated tools like axe-core catch roughly 57% of WCAG issues in isolation; the rest genuinely requires manual keyboard-only and screen-reader testing, because things like "does this error message make sense when read aloud out of visual context" are not mechanically detectable.

## Why this gets asked

Because accessibility is one of the few areas where "it looks fine and works when I click around" is actively misleading — the interviewer wants to know whether you've used a screen reader yourself, whether you understand keyboard-only navigation as a first-class interaction mode rather than an edge case, and whether you can tell the difference between a component that merely renders correctly and one that's actually operable by someone who can't use a mouse or can't see the screen. Many companies now face real legal exposure (ADA lawsuits over inaccessible websites have risen sharply), so this is increasingly a compliance question with a real cost attached, not just an ethics question — the interviewer has likely either dealt with an accessibility audit finding that blocked a launch, or has watched a team ship an ARIA-heavy component library that technically passed automated scans while being genuinely broken for real assistive technology users, which is exactly the "bad ARIA is worse than no ARIA" failure mode.

---

## Lineage: past → present → future

**What came before.** Early web accessibility work (1990s-2000s) was almost entirely about semantic HTML and basic alt text, because that's mostly all there was to work with — pages were server-rendered documents, and the browser's native semantics (headings, lists, form labels, links) did most of the accessibility work automatically as a side effect of using the right tags. The pain that broke this model was the rise of rich, JavaScript-driven interactive widgets (custom dropdowns, tab panels, tree views, drag-and-drop) that HTML had no native elements for — a `<div>`-based custom dropdown looked like a dropdown visually but was invisible and inoperable to a screen reader, because divs carry no semantic meaning and no keyboard behavior by default. This gap is exactly what WAI-ARIA (first published as a W3C spec around 2008, WCAG 2.0 in 2008) was built to fill: a vocabulary of roles, states, and properties that could retrofit accessibility semantics onto elements HTML didn't have native equivalents for.

**Where it stands now.** WCAG 2.2 (published October 2023) is the current baseline, with Level AA the conformance target virtually every legal and organizational standard requires (ADA-linked case law, Section 508 in the US, EN 301 549 in the EU). The live disagreement in practice isn't about the standard itself but about where ARIA belongs in the actual build process: the WAI-ARIA "first rule" — use a native HTML element or attribute instead of re-purposing an element and adding ARIA, whenever one exists — is broadly agreed on in principle but violated constantly in practice, especially in component libraries built by teams optimizing for visual design flexibility over semantic correctness, producing components that pass a quick automated scan (which mostly checks for the *presence* of ARIA attributes, not their *correctness*) while being functionally broken for real screen reader users. The other live tension: automated testing (axe-core and similar) catches roughly 57% of WCAG issues on its own — real, useful, but nowhere near sufficient — which means teams that treat a clean CI accessibility scan as "done" are, in a specific and measurable way, wrong, and the gap has to be closed with manual keyboard and screen-reader testing that many teams still don't budget time for.

**Where it's heading.** Framework-level accessibility primitives (Radix UI, React Aria, Headless UI) have shifted a meaningful amount of the correctness burden from individual engineers hand-rolling ARIA onto battle-tested unstyled component libraries that get the keyboard/focus/ARIA mechanics right so teams only own the visual styling — this is a real and durable trend, not a fad, because it converts "every team re-solves focus trapping correctly" into "one library solves it once." It's speculative but plausible that AI-assisted code review and generation tools meaningfully reduce the rate of "looks fine, is actually broken" ARIA misuse over the next few years, since these are exactly the kind of pattern-matchable mistakes (missing `aria-live` on a dynamic region, a custom control with a role but no keyboard handler) that automated review is well suited to catch — but the genuinely judgment-dependent parts (does this experience actually make sense to someone using a screen reader, is this error message actually clear out of visual context) remain a human-testing problem for the foreseeable future, and nothing on the horizon changes that.

---

## Mental model

Think of every interactive element as needing to satisfy two independent, cooperating systems, and semantic HTML is the only thing that satisfies both for free:

```
                    ┌─────────────────────────────┐
                    │   The Accessibility Tree      │  <- what screen readers read
                    │  (role, name, state, value)   │     (built from DOM + ARIA)
                    └─────────────────────────────┘
                              ▲
                              │  ARIA can ADD to this tree
                              │  (role, aria-label, aria-expanded...)
                              │  but changes NOTHING below
                              │
    ┌─────────────────────────────────────────────────┐
    │            Actual browser behavior                │  <- what keyboard/mouse
    │  (focusable? tab-reachable? Enter/Space fires      │     users actually get
    │   click? arrow keys navigate? native for <button>, │
    │   <a>, <input> — NOT native for <div>, <span>)     │
    └─────────────────────────────────────────────────┘

<button>          -> BOTH layers correct automatically
<div role="button">  -> top layer says "button" to a screen reader,
                        bottom layer does NOTHING unless you add
                        tabindex="0" + keydown handler yourself
```

The failure mode this diagram makes obvious: a `<div role="button" aria-label="Submit">` with no `tabindex` and no keydown handler announces itself correctly to a screen reader user (top layer looks fixed) while being completely unreachable by keyboard (bottom layer is still broken) — worse than doing nothing, because it actively told an assistive technology user "this is an operable button" when it isn't.

---

## How it actually works

### Semantic HTML first — what it buys you for free

A native `<button>` gets: keyboard focusability (`tabindex` implicitly 0), Enter and Space both trigger `click`, the accessibility tree reports `role: button` with the visible text as its accessible name, and it participates correctly in forms (`type="submit"` inside a `<form>`). Recreate that with a `<div>` and you must manually add `tabindex="0"` (focusability), a `keydown` handler checking for both `Enter` and `Space` (native buttons fire click on both, and easy to forget Space specifically), `role="button"` (accessibility tree), and handle the fact that a div has no implicit accessible name (needs visible text, `aria-label`, or `aria-labelledby`). Every one of those is a place to introduce a bug, and semantic HTML has none of them because the browser has already solved it. The same logic applies across the board: `<nav>`/`<main>`/`<header>`/`<footer>` give screen reader users landmark navigation (jump between regions) for free; `<label for="...">` (or wrapping) associates a form control with its text without any JS; a real `<table>` with `<th scope="col">` lets a screen reader announce which column/row a cell belongs to when navigating cell by cell, something no amount of CSS-styled divs replicates without extensive ARIA.

### ARIA: additive, not behavioral — and the "no ARIA is better than bad ARIA" rule

The WAI-ARIA spec's own "first rule of ARIA" is explicit: if a native HTML element or attribute has the semantics and behavior you need, use it instead of re-purposing an element and adding ARIA to make it accessible. This isn't stylistic preference — it's because ARIA only ever changes what's reported to the accessibility tree; it never changes actual browser behavior (focus, keyboard event handling, form participation). `aria-expanded="true"` on a custom dropdown trigger only helps if that trigger is also actually focusable and actually responds to Enter/Space/Arrow keys — the attribute alone is a claim, not an implementation. This is precisely why an incorrect ARIA attribute is worse than none: `role="button"` without the matching keyboard behavior tells a screen reader user "activate this with Enter/Space" when nothing will happen if they try, which is a worse experience than an unstyled, unlabeled div that at least doesn't create a false expectation. The correct order of operations, every time: (1) can a native element do this — use it; (2) if not, does an ARIA design pattern exist for this widget type (the ARIA Authoring Practices Guide documents canonical patterns for combobox, tabs, tree, dialog, etc.) — implement the *complete* pattern, not just the role; (3) verify the complete pattern with an actual keyboard and an actual screen reader, not just an automated scanner, since scanners mostly check for presence of attributes, not correctness of behavior.

### Keyboard navigation, concretely

Every interactive element needs three things working together: it's reachable via `Tab` (in a sensible order — usually just DOM order, which is why visually reordering elements with CSS `order` or absolute positioning without also reordering the DOM creates a mismatch between visual and tab order that's disorienting), it's operable via the key appropriate to its role (`Enter`/`Space` for buttons and links, arrow keys for radio groups/tabs/comboboxes/menus per the ARIA APG patterns, `Escape` to dismiss transient UI), and focus is never silently lost (a component that unmounts the currently focused element without moving focus somewhere deliberate drops focus back to `<body>`, disorienting a keyboard user who has no idea where they are anymore).

```jsx
// untested sketch — minimal accessible custom dropdown trigger, illustrates the
// gap semantic HTML avoids and ARIA + manual behavior has to fill in otherwise
function DropdownTrigger({ label, expanded, onToggle }) {
  return (
    <button
      type="button"
      aria-expanded={expanded}
      aria-haspopup="listbox"
      onClick={onToggle}
      // no manual keydown handler needed here — it's a real <button>,
      // Enter/Space are native. This is the whole point of semantic-first.
    >
      {label}
    </button>
  );
}
```

Note this uses a real `<button>` even though it's a "custom" dropdown trigger — the customization is the dropdown panel's appearance and the `aria-expanded`/`aria-haspopup` state, not the trigger's fundamental interactivity, which native HTML already handles correctly.

### Focus management in SPAs and modals

A traditional multi-page site resets focus to the top of the document on every navigation as a side effect of a full page load — an SPA has no such reset, so without deliberate handling, focus silently stays wherever it was (often on a nav link that's no longer visually in context) after a client-side route change, leaving keyboard and screen reader users without any signal that navigation happened. The fix: on route change, move focus programmatically to either the new page's main heading or a landmark (commonly an `<h1 tabIndex={-1}>` given a negative tabindex so it's programmatically focusable without being in the natural Tab order) and, for screen reader users specifically, ensure the page title changes so it's announced.

```jsx
// untested sketch — route-change focus management
function usePageFocus(pathname) {
  const headingRef = useRef(null);
  useEffect(() => {
    headingRef.current?.focus();
  }, [pathname]);
  return headingRef;
}

function PageShell({ pathname, title, children }) {
  const headingRef = usePageFocus(pathname);
  return (
    <>
      <h1 ref={headingRef} tabIndex={-1}>{title}</h1>
      {children}
    </>
  );
}
```

Modals need a four-part discipline, all four required: move focus into the modal on open (typically to the first focusable element or a heading), trap focus inside it while open (Tab on the last focusable element wraps to the first, Shift+Tab on the first wraps to the last — otherwise a keyboard user can Tab straight out of an open modal into the obscured page behind it), close on `Escape`, and restore focus to whatever triggered the modal when it closes (without this, focus resets to `<body>` on close, and a keyboard user has to re-navigate from the top of the page to get back to where they were).

```jsx
// untested sketch — minimal focus trap
function useFocusTrap(containerRef, isOpen) {
  useEffect(() => {
    if (!isOpen || !containerRef.current) return;
    const container = containerRef.current;
    const focusable = container.querySelectorAll(
      'a[href], button:not([disabled]), textarea, input, select, [tabindex]:not([tabindex="-1"])'
    );
    const first = focusable[0];
    const last = focusable[focusable.length - 1];
    first?.focus();

    function onKeydown(e) {
      if (e.key === "Escape") { /* close modal */ }
      if (e.key !== "Tab") return;
      if (e.shiftKey && document.activeElement === first) {
        e.preventDefault(); last?.focus();
      } else if (!e.shiftKey && document.activeElement === last) {
        e.preventDefault(); first?.focus();
      }
    }
    container.addEventListener("keydown", onKeydown);
    return () => container.removeEventListener("keydown", onKeydown);
  }, [isOpen, containerRef]);
}
```

In production, use a battle-tested implementation (Radix UI's `Dialog`, React Aria's `useDialog`/`FocusScope`, or the native `<dialog>` element with `showModal()`, which handles trapping and top-layer stacking natively in modern browsers) rather than hand-rolling this — the edge cases (nested modals, dynamically added/removed focusable children, `inert` on background content) are easy to get subtly wrong.

### Screen reader behavior: what's actually announced, and `aria-live`

Static content is read in DOM order when a screen reader user navigates by heading, landmark, or line. Dynamic content that changes *without* a focus or navigation event (a toast notification, a form validation error appearing after submit, a live search result count updating) is invisible to a screen reader unless it's inside an `aria-live` region — `aria-live="polite"` announces the change after the user's current activity finishes (the common choice for most updates), `aria-live="assertive"` interrupts immediately (reserved for genuinely urgent things — a session-expiry warning, a critical error — because overuse is disorienting). A validation error injected into the DOM with no `aria-live` ancestor and no focus movement will be completely silent to a screen reader user even though it's clearly visible on screen — this is one of the single most common real-world accessibility bugs in form validation UX, and it's invisible in a purely visual QA pass.

```jsx
function FormError({ message }) {
  return (
    <div role="alert" aria-live="assertive">
      {message}
    </div>
  );
}
```

`role="alert"` implies `aria-live="assertive"` and `aria-atomic="true"` (the whole region is re-announced, not just the diff) — appropriate here because a form submission error is exactly the kind of thing that should interrupt.

### WCAG levels and what they actually require

WCAG 2.2 (October 2023) organizes success criteria into three levels, each building on the last: Level A is the floor — criteria that, unmet, make content unusable for some group entirely (e.g., all functionality operable via keyboard, no keyboard traps, images have text alternatives). Level AA adds criteria that most organizations are legally and practically expected to meet (4.5:1 contrast ratio for normal text, 3:1 for large text, consistent navigation, visible focus indicators, resizable text up to 200% without loss of function) — AA is the level referenced by ADA-linked litigation, Section 508, and EN 301 549, and is the realistic target for essentially every commercial product. Level AAA is the highest bar (7:1 contrast, sign language interpretation for video, no exceptions for reading level) and is explicitly *not* recommended by the W3C as a general requirement for entire sites — some individual AAA criteria are worth adopting selectively, but treating AAA as the universal target usually isn't proportionate to the benefit for most products.

---

## Build it from scratch

A concrete, checkable exercise: take an existing custom dropdown or modal component in a codebase and audit it against the ARIA Authoring Practices Guide's reference pattern for that widget type, then fix any gap found by (1) turning off the mouse entirely and operating it keyboard-only, and (2) turning on a real screen reader (VoiceOver on macOS with Cmd+F5, NVDA on Windows, free) and confirming what's actually announced matches what's visually shown. This exercise reliably surfaces real bugs — a missing focus trap, a dropdown that opens but can't be closed with Escape, a toast that's invisible to the screen reader — that a purely visual review never catches. Reference: `labs/js/10-accessibility/`.

---

## How it's done in production

Production accessibility work leans heavily on unstyled, behavior-correct component primitives (Radix UI, React Aria, Headless UI, Base UI) rather than hand-rolled ARIA, specifically because focus trapping, roving tabindex for composite widgets (tabs, comboboxes), and the full keyboard interaction model for each ARIA design pattern are easy to get subtly wrong and expensive to re-verify per team. Automated testing (axe-core, integrated via `@axe-core/react`, `eslint-plugin-jsx-a11y` at lint time, or Playwright's accessibility testing integration) runs in CI as a floor, catching roughly 57% of WCAG issues on its own — real coverage, but explicitly partial.

| Symptom | Cause | Fix |
|---|---|---|
| Automated accessibility scan passes clean, but a real screen reader user reports the page is unusable | Automated tools check for presence/structure of ARIA and semantic markup, not correctness of behavior or actual user experience (axe-core-class tools catch ~57% of WCAG issues) | Add manual keyboard-only and screen-reader testing to the QA process; automated scans are a floor, not a certification |
| Custom dropdown/menu announces correctly to a screen reader but can't be operated by keyboard | ARIA role/state added without the matching native or hand-rolled keyboard behavior (focusability, key handlers) — ARIA changes the accessibility tree, not actual browser behavior | Implement the full ARIA Authoring Practices Guide pattern for that widget, not just the role attribute, or use a native element/behavior-correct library instead |
| Keyboard users get "stuck" inside or locked out of a modal | No focus trap (Tab escapes into the obscured background) or an overly aggressive trap with no Escape handler and no way out | Implement all four modal focus requirements: move focus in, trap it, close on Escape, restore focus to the trigger on close |
| Form validation errors are invisible to screen reader users despite being visually obvious | Error text injected into the DOM with no `aria-live` region and no focus movement to it | Wrap dynamic error content in `role="alert"` (implies `aria-live="assertive"`) or move focus to the first invalid field |
| SPA route changes leave screen reader users unaware navigation happened | No page title update and no programmatic focus move on client-side route change (no full page load to reset focus/announce the new page automatically) | Move focus to the new page's `<h1>` (with `tabIndex={-1}`) and update `document.title` on route change |
| Color contrast fails only in dark mode or only for a specific theme variant | Contrast checked once against the default theme, not re-verified per theme/color-token combination | Run contrast checks (automated, per theme) as part of the design-token pipeline itself, not a one-time manual check against a single theme |

---

## Tradeoffs & when NOT to use it

- **Don't add ARIA roles/states without also implementing the full behavioral pattern.** A role with no matching keyboard support is actively worse than no role at all, because it creates a false expectation for assistive technology users rather than an honest gap.
- **Don't treat AAA as the universal target.** The W3C itself doesn't recommend requiring AAA conformance sitewide; it's appropriate to selectively adopt specific AAA criteria where the cost/benefit makes sense (e.g., higher contrast for a data-dense dashboard used by an older user base) rather than pursuing full AAA as a blanket policy that consumes disproportionate effort relative to AA's already-substantial coverage.
- **Don't treat a clean automated scan as "accessible."** At roughly 57% detection coverage on its own, a passing axe-core run is a necessary floor, not sufficient evidence — real screen reader and keyboard testing is not optional if the goal is an actually usable product, not just a passing CI check.
- **Don't hand-roll complex widget patterns (combobox, tree, date picker) from scratch when a behavior-correct library exists** — these patterns have enough documented edge cases (the ARIA APG's combobox pattern alone has a dozen keyboard interaction requirements) that re-implementing them per project is both expensive and a likely source of subtle regressions; reserve custom ARIA implementation for genuinely novel interaction patterns without an existing library solution.
- **Don't over-apply `aria-live="assertive"`.** Interrupting a screen reader user's current context is disruptive and should be reserved for genuinely urgent information; most dynamic updates belong on `polite`, and defaulting everything to `assertive` produces a worse experience than silence for non-critical updates.

---

## Interview questions

### Q1 — What's the practical difference between using a native `<button>` and a `<div role="button">`, and why does it matter?
**Testing:** baseline understanding of the semantic-first principle with a concrete mechanism, not just "semantic HTML is good practice."
**Answer:** A native `<button>` is focusable, fires `click` on both Enter and Space, reports `role: button` to the accessibility tree, and participates in forms — all automatically. A `<div role="button">` only gets the accessibility-tree role; it needs manual `tabindex="0"` for focusability and a manual keydown handler for Enter/Space, and if either is missing it's inoperable by keyboard despite announcing itself as an operable button.
**Follow-up trap:** *"If you had to use a div for some layout reason, what's the minimum you'd need to add to make it fully equivalent?"* — `role="button"`, `tabindex="0"`, a `keydown` handler checking for both `Enter` and `Space` (not just one), and an accessible name (visible text, `aria-label`, or `aria-labelledby`) — and even then, it's worth pausing to ask why a real button couldn't be styled to fit the layout need instead, since this is exactly the situation the "no ARIA is better than bad ARIA" first rule warns against re-creating.

### Q2 — Explain, precisely, why "no ARIA is better than bad ARIA" is true rather than just a slogan.
**Testing:** whether the candidate understands ARIA's actual mechanism (additive to the accessibility tree, zero effect on behavior) versus treating it as a magic accessibility fix.
**Answer:** ARIA only changes what's reported to the accessibility tree — it never changes actual browser behavior like focus management or keyboard event handling. An incorrect ARIA attribute (a role implying interactivity with no matching keyboard support, an `aria-expanded` that never updates) actively tells assistive technology users something false about the element, which is a worse experience than an honest absence of any claim, because it creates a false expectation the user then has to discover is wrong through failed interaction.
**Follow-up trap:** *"Can you give a real example where adding ARIA actively made a component worse, not just neutral?"* — a custom dropdown with `role="listbox"` and `aria-expanded` added for a scanner to pass, but no arrow-key navigation between options and no Enter-to-select — a screen reader announces "listbox, 5 options" implying standard listbox keyboard behavior, and the user's expected interaction (arrow keys) does nothing, which is more confusing than an unstyled, unlabeled list of clickable divs that create no expectation of arrow-key support.

### Q3 — Walk through everything an accessible modal dialog needs to do around focus, in order.
**Testing:** whether all four required behaviors are known, not just "trap focus."
**Answer:** On open, move focus into the modal (first focusable element or a heading). While open, trap focus inside it — Tab from the last focusable element wraps to the first, Shift+Tab from the first wraps to the last, so a keyboard user can never Tab out into the obscured background. Close on Escape. On close, restore focus to whatever element triggered the modal, so the user doesn't lose their place and have to re-navigate from the top of the page.
**Follow-up trap:** *"What happens if you skip the 'restore focus on close' step specifically, and why is it easy to miss in testing?"* — closing the modal without restoring focus leaves it on `document.body` (or wherever the modal's DOM node was, now removed), so a keyboard user has no idea where they are and has to Tab from the very beginning of the page to get back to context. It's easy to miss because mouse-driven QA never notices — a mouse user just clicks wherever they want next regardless of focus state, so this bug is invisible without deliberate keyboard-only testing.

### Q4 — Why is a form validation error that's clearly visible on screen sometimes completely silent to a screen reader user?
**Testing:** understanding of `aria-live` as the mechanism for announcing dynamic content changes.
**Answer:** Screen readers announce content when the user navigates to it (via heading, landmark, Tab) or when it's inside a live region that's configured to announce changes. Content injected into the DOM dynamically, with no `aria-live` ancestor and no focus movement to it, produces no announcement at all — it's visually present but the screen reader has no signal that anything changed, since the user's focus and reading position haven't moved.
**Follow-up trap:** *"When would you use aria-live='assertive' versus 'polite', and what goes wrong if you default everything to assertive?"* — `polite` waits for the user's current activity to finish before announcing (appropriate for most updates: a search result count, a save confirmation); `assertive` interrupts immediately (reserved for genuinely urgent things: a session-expiry warning, a critical form error). Defaulting everything to `assertive` means minor updates constantly interrupt whatever the user is doing, which is disorienting and often worse than the silence it's meant to fix.

### Q5 — Why does client-side routing in an SPA specifically break something that traditional multi-page sites got for free?
**Testing:** whether the candidate connects the SPA architecture pattern to a concrete accessibility regression, not just "SPAs need extra a11y work" as a vague statement.
**Answer:** A full page load resets focus to the top of the document and the browser announces the new page title as a side effect — an SPA's client-side route change does neither automatically, so without deliberate handling, focus silently remains wherever it was (often on a now-stale nav link) and screen reader users get no signal that navigation happened at all.
**Follow-up trap:** *"What's the minimum fix, and why use tabIndex={-1} on the heading rather than tabIndex={0}?"* — move focus programmatically to the new page's `<h1>` and update `document.title` on route change. `tabIndex={-1}` makes the heading programmatically focusable (so `.focus()` works) without adding it to the natural Tab order — a heading shouldn't be a Tab stop during normal keyboard navigation of the page, it should only receive focus as a deliberate one-time landing point right after navigation.

### Q6 — What does axe-core (or a similar automated accessibility scanner) actually catch, and what does it structurally miss?
**Testing:** whether the candidate understands automated testing's real, bounded coverage rather than treating a passing scan as certification.
**Answer:** Automated scanners reliably catch structural and presence-based issues — missing alt text, insufficient color contrast against computed styles, missing form labels, invalid ARIA attribute values, missing landmark roles. Real-world data puts this at roughly 57% of WCAG issues on average. What it structurally can't catch: whether an interaction actually makes sense to a screen reader user in context, whether a keyboard flow is logically ordered even if every individual element is technically focusable, whether an error message is clear when read aloud without visual context, or whether a custom widget's *behavior* (not just its markup) matches its announced role.
**Follow-up trap:** *"If automated coverage is only ~57%, is manual testing optional for a team under time pressure, or is there a middle ground?"* — not optional if genuine usability for assistive technology users is the goal, but it can be prioritized: run automated scans on every PR as a floor (catches regressions cheaply), and schedule periodic manual keyboard-only and screen-reader passes on high-traffic or high-risk flows (checkout, auth, primary navigation) rather than attempting full manual coverage of every page on every release.

### Q7 — Explain WCAG's three conformance levels and why AAA isn't the target most teams should pursue.
**Testing:** whether the candidate knows the actual structure (each level builds on the last) and has a defensible opinion on scope, not just "more accessible is always better."
**Answer:** Level A is the floor — criteria whose absence makes content unusable for some group entirely (keyboard operability, no keyboard traps, text alternatives for images). AA adds criteria most organizations are legally and practically expected to meet (4.5:1 text contrast, visible focus indicators, consistent navigation) and is the level referenced by most accessibility law and litigation. AAA is the highest bar (7:1 contrast, sign language interpretation for video) and the W3C itself doesn't recommend requiring full AAA conformance as a general policy — the cost/benefit for many AAA criteria doesn't scale the same way AA's does across a whole product.
**Follow-up trap:** *"Is there ever a good reason to adopt specific AAA criteria selectively?"* — yes, when it maps to a real, known user need — e.g., higher contrast ratios for a data-dense dashboard used disproportionately by an older user base, or providing sign language interpretation for a specific high-stakes video (legal/medical content) even without pursuing full AAA sitewide. Selective, justified adoption of individual AAA criteria is different from blanket AAA as a universal target.

### Q8 — A component library's custom `<Select>` component passes every automated accessibility check. A user reports it's completely unusable with a screen reader. What's your diagnostic process?
**Testing:** staff-level: knowing exactly what to check manually when automated tooling has already given a false sense of completeness.
**Answer:** Turn off the mouse and try to operate it with keyboard only — checking Tab reachability, whether arrow keys move between options (per the ARIA APG's listbox/combobox pattern), whether Enter/Space selects, whether Escape closes it. Then turn on an actual screen reader (VoiceOver/NVDA) and confirm the announced role, state changes (`aria-expanded`, `aria-selected`), and the accessible name all match what's visually happening — automated tools verify markup structure and attribute presence, not that the live behavior matches the announced semantics.
**Follow-up trap:** *"The keyboard interaction works fine when you test it yourself. What else could explain the user's report?"* — screen reader + browser combination matters (VoiceOver/Safari, NVDA/Firefox, JAWS/Chrome all have known quirks and aren't perfectly interchangeable), and the user may be on a specific combination with a known compatibility gap; also worth checking whether the component behaves differently depending on how it's reached (e.g., a bug that only appears when focus arrives via a specific prior element) — reproducing on the exact reported AT/browser pairing, not just "a" screen reader, is often necessary.

### Q9 — Why might color contrast pass for a component's default theme but fail in dark mode, and how would you prevent this systemically rather than catching it after the fact?
**Testing:** staff-level: connecting accessibility to the design-token/theming pipeline rather than treating it as a one-off manual check.
**Answer:** Contrast ratio is a function of the specific foreground/background color pair, and a token or component often gets manually verified against only the default (usually light) theme; a dark-mode variant introduces a new color pair that was never independently checked and can easily fall under the 4.5:1 (normal text) or 3:1 (large text/UI components) AA thresholds even if the light-mode pairing was fine.
**Follow-up trap:** *"How would you catch this automatically before it ships, across every theme, without manually checking every combination by hand?"* — bake contrast validation into the design-token pipeline itself — a build-time or CI check that computes contrast ratios for every semantic color-pair combination across every defined theme and fails if any combination is below threshold, rather than relying on a human to remember to manually re-check contrast every time a new theme or token value is added.

---

## Red flags that fail you

- Adding `role="button"` (or similar) without also adding the matching keyboard behavior, and not recognizing that as a problem.
- Treating a passing automated accessibility scan as proof the product is accessible.
- Claiming AAA conformance should be the universal target for all content.
- Not knowing that ARIA changes the accessibility tree but never changes actual browser behavior.
- Building a modal without a focus trap, or without restoring focus to the trigger on close.
- Using `aria-live="assertive"` as the default for all dynamic content updates.
- Never having actually tested a component with a real screen reader.

---

## Cheat card

```
SEMANTIC-FIRST RULE (WAI-ARIA "first rule"): use a native element/attribute if
  one has the needed semantics+behavior, before re-purposing an element + ARIA.

<button> vs <div role="button">: native gets focus/Enter/Space/role for FREE.
  div needs: tabindex="0" + keydown handler (Enter AND Space) + role + accessible name.

ARIA IS ADDITIVE ONLY: changes accessibility tree, NEVER changes actual browser
  behavior (focus, keyboard events). Wrong role/state = false claim to AT user
  = WORSE than no ARIA at all ("no ARIA > bad ARIA" is a literal W3C rule).

MODAL FOCUS (all 4 required): move focus in on open -> trap Tab/Shift+Tab inside
  -> close on Escape -> restore focus to trigger element on close.

SPA ROUTE CHANGE: no full page load = no automatic focus reset/title announce.
  Fix: focus new <h1 tabIndex={-1}> + update document.title on navigation.

ARIA-LIVE: dynamic content with no aria-live ancestor + no focus move = SILENT
  to screen readers even if visually obvious. polite = waits for current activity
  (most updates). assertive = interrupts NOW (reserve for urgent only).
  role="alert" implies aria-live="assertive" + aria-atomic="true".

WCAG 2.2 (Oct 2023) LEVELS: A = floor (unusable-if-missing). AA = legal/practical
  target (4.5:1 text contrast, 3:1 large text/UI, visible focus, consistent nav) —
  referenced by ADA case law, Section 508, EN 301 549. AAA (7:1 contrast, etc.) =
  NOT recommended by W3C as a universal target; adopt selected criteria only.

AUTOMATED TESTING COVERAGE: axe-core catches ~57% of WCAG issues on average
  (real-world data, 13K+ pages). Manual keyboard + screen reader testing required
  for the rest — automated scan passing != accessible.

TEST TOOLS: keyboard-only (unplug the mouse), VoiceOver (macOS, Cmd+F5), NVDA
  (Windows, free), axe-core/eslint-plugin-jsx-a11y in CI as the floor.

PRODUCTION LIBS: Radix UI, React Aria, Headless UI — behavior-correct unstyled
  primitives; prefer over hand-rolling complex widget patterns (combobox, tree).
```

## Sources

- [Web Content Accessibility Guidelines (WCAG) 2.2 — W3C](https://www.w3.org/TR/WCAG22/) — accessed 2026-08-02
- [WCAG Levels Explained: A vs. AA vs. AAA (2026) — Level Access](https://www.levelaccess.com/blog/ada-compliance-levels/) — accessed 2026-08-02
- [The Automated Accessibility Coverage Report — Deque](https://www.deque.com/automated-accessibility-coverage-report/) — accessed 2026-08-02
- [How to Build Accessible Modals with Focus Traps (2026 Guide) — UXPin](https://www.uxpin.com/studio/blog/how-to-build-accessible-modals-with-focus-traps/) — accessed 2026-08-02
- [Accessibility for Single Page Applications (SPAs) — TestParty](https://testparty.ai/blog/spa-accessibility) — accessed 2026-08-02
- W3C WAI-ARIA Authoring Practices Guide (APG) — canonical widget interaction patterns — living reference docs

## Changelog
- 2026-08-02 — created
